import csv
from io import StringIO
from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsInstructor
from accounts.models import ensure_instructor
from problems.models import ProblemBank, Problem, InstructorProblemRating
from problems.serializers import (
    ProblemBankSerializer, 
    ProblemSerializer, 
    ProblemSummarySerializer,
    InstructorProblemRatingSerializer
)


class ProblemBankViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemBankSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        # Allow all instructors to see all banks (for rating/sharing purposes)
        return ProblemBank.objects.all()

    def perform_create(self, serializer):
        serializer.save(owner=ensure_instructor(self.request.user))

    def _ensure_owner(self, bank):
        instructor = ensure_instructor(self.request.user)
        if bank.owner != instructor:
            raise PermissionDenied('You do not own this problem bank.')

    def perform_update(self, serializer):
        self._ensure_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_owner(instance)
        instance.delete()

    @action(detail=True, methods=['post'], parser_classes=[parsers.MultiPartParser])
    def import_from_csv(self, request, *args, **kwargs):
        bank = self.get_object()
        self._ensure_owner(bank)
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_file = file_obj.read().decode('utf-8')
            io_string = StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            created_count = 0
            errors = []
            
            for row in reader:
                # Expected columns: statement, answer, group (optional), display_label (optional)
                statement = row.get('statement')
                answer = row.get('answer')
                
                if not statement or not answer:
                    continue
                    
                group = row.get('group') or ''
                display_label = row.get('display_label') or ''
                
                # Determine order
                last_order = bank.problems.aggregate(max_order=models.Max('order_in_bank'))['max_order'] or 0
                new_order = last_order + 1
                
                Problem.objects.create(
                    problem_bank=bank,
                    statement=statement,
                    answer=answer,
                    group=group,
                    display_label=display_label,
                    order_in_bank=new_order
                )
                created_count += 1
                
            return Response({'detail': f'Imported {created_count} problems.'})
            
        except Exception as e:
            return Response({'detail': f'Error processing file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


class ProblemBankRatingImportView(APIView):
    permission_classes = [IsInstructor]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, bank_id):
        instructor = ensure_instructor(request.user)
        bank = get_object_or_404(ProblemBank, id=bank_id)
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        is_preview = request.data.get('preview') == 'true'

        try:
            # Read and decode file
            # Use utf-8-sig to handle BOM
            content = file_obj.read().decode('utf-8-sig')
            
            # Helper to check if a dialect/delimiter yields valid headers
            def get_valid_reader(content, dialect_or_delimiter):
                try:
                    io_string = StringIO(content)
                    reader = csv.DictReader(io_string, dialect=dialect_or_delimiter)
                    if not reader.fieldnames:
                        return None, None
                    
                    # Normalize headers
                    original_headers = reader.fieldnames
                    header_map = {h.strip().lower(): h for h in original_headers}
                    
                    if 'problem' in header_map:
                        return reader, header_map
                    return None, None
                except csv.Error:
                    return None, None

            reader = None
            header_map = None
            
            # 1. Try Sniffer
            try:
                dialect = csv.Sniffer().sniff(content[:1024])
                reader, header_map = get_valid_reader(content, dialect)
            except csv.Error:
                pass
            
            # 2. If Sniffer failed or didn't yield "Problem" column, try explicit delimiters
            if not reader:
                delimiters = [',', ';', '\t']
                for d in delimiters:
                    # Create a simple dialect with this delimiter
                    class SimpleDialect(csv.Dialect):
                        delimiter = d
                        quotechar = '"'
                        doublequote = True
                        skipinitialspace = True
                        lineterminator = '\r\n'
                        quoting = csv.QUOTE_MINIMAL
                    
                    reader, header_map = get_valid_reader(content, SimpleDialect)
                    if reader:
                        break
            
            if not reader or not header_map:
                 return Response({'detail': 'CSV must have a "Problem" column. Could not detect valid CSV format.'}, status=status.HTTP_400_BAD_REQUEST)
            
            original_headers = reader.fieldnames
            problem_col = header_map['problem']

            # If preview, return first 5 rows
            if is_preview:
                preview_rows = []
                for i, row in enumerate(reader):
                    if i >= 5:
                        break
                    preview_rows.append(row)
                
                return Response({
                    'preview': True,
                    'headers': original_headers,
                    'rows': preview_rows
                })

            # Import logic
            imported_count = 0
            
            # Identify criterion columns
            # All columns except the problem column are treated as criteria
            criterion_names = [h for h in original_headers if h != problem_col]
            
            for row in reader:
                problem_label = row.get(problem_col)
                if not problem_label:
                    continue
                
                # Find problem by label (display_label) or order?
                # display_label is a property, so we can't filter by it.
                # We expect the label to be the order number or "Problem X".
                
                problem = None
                
                # Try to parse order from label
                try:
                    # If label is just a number
                    order = int(problem_label)
                    problem = bank.problems.filter(order_in_bank=order).first()
                except ValueError:
                    # If label is "Problem X"
                    if problem_label.lower().startswith('problem '):
                        try:
                            order = int(problem_label.split(' ')[1])
                            problem = bank.problems.filter(order_in_bank=order).first()
                        except (ValueError, IndexError):
                            pass

                if not problem:
                    continue
                
                # Get or create rating object
                rating, _ = InstructorProblemRating.objects.get_or_create(
                    problem=problem,
                    instructor=instructor
                )
                
                for c_name in criterion_names:
                    val_str = row.get(c_name)
                    if not val_str:
                        continue
                    try:
                        # Support floats (e.g. 0.5)
                        val = float(val_str)
                    except ValueError:
                        continue
                        
                    # Find criterion ID
                    rubric = bank.get_rubric() # Returns dict
                    criteria = rubric.get('criteria', [])
                    
                    # Match by name OR id (case-insensitive)
                    c_id = None
                    c_name_clean = c_name.strip().lower()
                    
                    for c in criteria:
                        if c['name'].strip().lower() == c_name_clean:
                            c_id = c['id']
                            break
                        if str(c['id']).strip().lower() == c_name_clean:
                            c_id = c['id']
                            break
                            
                    if not c_id:
                        continue
                    
                    from problems.models import InstructorProblemRatingEntry, RubricCriterion, RubricScaleOption
                    
                    # We need the actual RubricCriterion model instance
                    criterion_obj = RubricCriterion.objects.filter(rubric__id=bank.rubric.id, criterion_id=c_id).first()

                    # Find the scale option
                    # We have `val` which is the value.
                    # Handle float comparison carefully? Exact match for now.
                    scale_option = RubricScaleOption.objects.filter(rubric__id=bank.rubric.id, value=val).first()
                    
                    if criterion_obj and scale_option:
                        InstructorProblemRatingEntry.objects.update_or_create(
                            rating=rating,
                            criterion=criterion_obj,
                            defaults={'scale_option': scale_option}
                        )
                        
                imported_count += 1

            return Response({'detail': f'Imported ratings for {imported_count} problems.'})
            
        except Exception as e:
            return Response({'detail': f'Error processing file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


class ProblemViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        return Problem.objects.select_related('problem_bank', 'problem_bank__owner').all()

    def perform_create(self, serializer):
        instructor = ensure_instructor(self.request.user)
        bank_id = self.request.data.get('problem_bank')
        bank = get_object_or_404(ProblemBank, id=bank_id)
        if bank.owner != instructor:
            raise PermissionDenied('Only the owner can add problems to this bank.')
        order = serializer.validated_data.get('order_in_bank')
        if order is None:
            last_order = bank.problems.aggregate(max_order=models.Max('order_in_bank'))['max_order'] or 0
            order = last_order + 1
        serializer.save(problem_bank=bank, order_in_bank=order)

    def perform_update(self, serializer):
        instructor = ensure_instructor(self.request.user)
        problem = serializer.instance
        if problem.problem_bank.owner != instructor:
            raise PermissionDenied('Only the bank owner can edit this problem.')
        bank = serializer.validated_data.get('problem_bank')
        if bank and bank.owner != instructor:
            raise PermissionDenied('Cannot move problem to another instructor bank')
        serializer.save()

    def perform_destroy(self, instance):
        instructor = ensure_instructor(self.request.user)
        if instance.problem_bank.owner != instructor:
            raise PermissionDenied('Only the bank owner can delete this problem.')
        super().perform_destroy(instance)


class ProblemBankProblemListCreate(generics.ListCreateAPIView):
    permission_classes = [IsInstructor]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ProblemSummarySerializer
        return ProblemSerializer

    def get_queryset(self):
        bank = self._get_bank()
        return Problem.objects.filter(problem_bank=bank)

    def perform_create(self, serializer):
        instructor = ensure_instructor(self.request.user)
        bank = self._get_bank()
        if bank.owner != instructor:
            raise PermissionDenied('Only the owner can add problems to this bank.')
        order = serializer.validated_data.get('order_in_bank')
        if order is None:
            last_order = bank.problems.aggregate(max_order=models.Max('order_in_bank'))['max_order'] or 0
            order = last_order + 1
        serializer.save(problem_bank=bank, order_in_bank=order)

    def _get_bank(self):
        if not hasattr(self, '_bank_cache'):
            self._bank_cache = get_object_or_404(ProblemBank, id=self.kwargs['bank_id'])
        return self._bank_cache


class InstructorProblemRatingView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, problem_id):
        instructor = ensure_instructor(request.user)
        problem = get_object_or_404(Problem, id=problem_id)
        
        # Check if rating exists
        try:
            rating = InstructorProblemRating.objects.get(problem=problem, instructor=instructor)
            serializer = InstructorProblemRatingSerializer(rating)
            return Response(serializer.data)
        except InstructorProblemRating.DoesNotExist:
            return Response({'entries': []})

    def put(self, request, problem_id):
        instructor = ensure_instructor(request.user)
        problem = get_object_or_404(Problem, id=problem_id)
        
        try:
            rating = InstructorProblemRating.objects.get(problem=problem, instructor=instructor)
            serializer = InstructorProblemRatingSerializer(rating, data=request.data)
        except InstructorProblemRating.DoesNotExist:
            serializer = InstructorProblemRatingSerializer(data=request.data)
            
        serializer.is_valid(raise_exception=True)
        serializer.save(problem=problem, instructor=instructor)
        return Response(serializer.data)
