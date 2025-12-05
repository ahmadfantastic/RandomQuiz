import csv
from io import StringIO
import numpy as np
from scipy import stats
from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from accounts.permissions import IsInstructor
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ensure_instructor
from problems.models import ProblemBank, Problem, Rubric, InstructorProblemRating
from problems.serializers import (
    ProblemBankSerializer, 
    ProblemSerializer, 
    ProblemSummarySerializer,
    RubricSerializer,
    InstructorProblemRatingSerializer
)


class ProblemBankViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemBankSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        instructor = ensure_instructor(self.request.user)
        return ProblemBank.objects.filter(owner=instructor)

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
        bank = get_object_or_404(ProblemBank, id=bank_id, owner=instructor)
        
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
                        val = int(float(val_str))
                    except ValueError:
                        continue
                        
                    # Find criterion ID
                    rubric = bank.get_rubric() # Returns dict
                    criteria = rubric.get('criteria', [])
                    # Match by name (case-insensitive?) - Let's stick to exact or stripped match for now
                    # The c_name comes from the CSV header.
                    c_id = next((c['id'] for c in criteria if c['name'].strip().lower() == c_name.strip().lower()), None)
                    
                    if c_id:
                        from problems.models import InstructorProblemRatingEntry
                        
                        InstructorProblemRatingEntry.objects.update_or_create(
                            rating=rating,
                            criterion_id=c_id,
                            defaults={'value': val}
                        )
                        
                imported_count += 1

            return Response({'detail': f'Imported ratings for {imported_count} problems.'})

        except Exception as e:
            return Response({'detail': f'Error processing file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


def calculate_weighted_kappa(y1, y2):
    # y1, y2 are lists of ratings
    # Assume scale is ordinal integers
    
    # Ensure inputs are numpy arrays
    y1 = np.array(y1, dtype=int)
    y2 = np.array(y2, dtype=int)
    
    # Get unique categories
    categories = np.unique(np.concatenate((y1, y2)))
    categories.sort()
    
    # Map categories to 0..k-1
    cat_map = {c: i for i, c in enumerate(categories)}
    y1_idx = np.array([cat_map[c] for c in y1])
    y2_idx = np.array([cat_map[c] for c in y2])
    
    k = len(categories)
    n = len(y1)
    
    if k < 2:
        return 1.0 # Perfect agreement if only 1 category
        
    # Confusion matrix
    conf_mat = np.zeros((k, k))
    for i in range(n):
        conf_mat[y1_idx[i], y2_idx[i]] += 1
        
    # Weights matrix (quadratic)
    w_mat = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            w_mat[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)
            
    # Expected matrix
    row_sums = np.sum(conf_mat, axis=1)
    col_sums = np.sum(conf_mat, axis=0)
    expected_mat = np.outer(row_sums, col_sums) / n
    
    # Calculate Kappa
    numerator = np.sum(w_mat * conf_mat)
    denominator = np.sum(w_mat * expected_mat)
    
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
        
    return 1.0 - (numerator / denominator)


class ProblemBankAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, bank_id):
        instructor = ensure_instructor(request.user)
        bank = get_object_or_404(ProblemBank, id=bank_id)
        
        # We want to analyze ratings for problems in this bank.
        # 1. Get all ratings for problems in this bank.
        ratings = InstructorProblemRating.objects.filter(
            problem__problem_bank=bank
        ).select_related('problem', 'instructor').prefetch_related('entries')
        
        # Structure: Problem -> { Instructor -> { Criterion -> Value } }
        data = {}
        instructors = set()
        criteria = set()
        
        rubric = bank.get_rubric()
        rubric_criteria = {c['id']: c['name'] for c in rubric.get('criteria', [])}
        
        for r in ratings:
            pid = r.problem_id
            iid = r.instructor.user.username # Use username as identifier
            instructors.add(iid)
            
            if pid not in data:
                data[pid] = {
                    'problem_label': r.problem.display_label,
                    'ratings': {}
                }
            
            if iid not in data[pid]['ratings']:
                data[pid]['ratings'][iid] = {}
                
            for entry in r.entries.all():
                c_id = entry.criterion_id
                c_name = rubric_criteria.get(c_id, c_id)
                criteria.add(c_name)
                data[pid]['ratings'][iid][c_name] = entry.value

        # Calculate statistics
        # For each problem, calculate mean/std per criterion
        # Calculate Inter-Rater Reliability (IRR) if multiple raters
        
        problem_stats = []
        
        for pid, p_data in data.items():
            p_stats = {
                'id': pid,
                'label': p_data['problem_label'],
                'criteria_stats': {},
                'irr': {}
            }
            
            p_ratings = p_data['ratings']
            raters = list(p_ratings.keys())
            
            for c in criteria:
                values = []
                for rater in raters:
                    val = p_ratings[rater].get(c)
                    if val is not None:
                        values.append(val)
                
                if values:
                    p_stats['criteria_stats'][c] = {
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'count': len(values)
                    }
                    
                # IRR (Weighted Kappa) - Pairwise average
                if len(raters) > 1:
                    kappas = []
                    for i in range(len(raters)):
                        for j in range(i + 1, len(raters)):
                            r1 = raters[i]
                            r2 = raters[j]
                            v1 = p_ratings[r1].get(c)
                            v2 = p_ratings[r2].get(c)
                            
                            if v1 is not None and v2 is not None:
                                # We can only calculate kappa if we have a set of items, 
                                # but here we are looking at ONE problem.
                                # Kappa is usually calculated across multiple items.
                                # For a single item, we can just look at absolute difference?
                                # Or maybe we want IRR across the whole BANK?
                                pass
            
            problem_stats.append(p_stats)
            
        # Calculate Bank-wide IRR per criterion
        bank_irr = {}
        if len(instructors) > 1:
            raters_list = sorted(list(instructors))
            
            for c in criteria:
                # Collect paired ratings across all problems
                # We need common problems rated by pairs
                
                pairwise_kappas = []
                
                for i in range(len(raters_list)):
                    for j in range(i + 1, len(raters_list)):
                        r1 = raters_list[i]
                        r2 = raters_list[j]
                        
                        y1 = []
                        y2 = []
                        
                        for pid, p_data in data.items():
                            v1 = p_data['ratings'].get(r1, {}).get(c)
                            v2 = p_data['ratings'].get(r2, {}).get(c)
                            
                            if v1 is not None and v2 is not None:
                                y1.append(v1)
                                y2.append(v2)
                        
                        if len(y1) >= 5: # Minimum sample size
                            k = calculate_weighted_kappa(y1, y2)
                            pairwise_kappas.append(k)
                            
                if pairwise_kappas:
                    bank_irr[c] = np.mean(pairwise_kappas)
        
        return Response({
            'bank_id': bank.id,
            'problem_stats': problem_stats,
            'bank_irr': bank_irr,
            'raters': list(instructors)
        })


class GlobalAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        instructor = ensure_instructor(request.user)
        
        # Analyze all banks owned by instructor
        banks = ProblemBank.objects.filter(owner=instructor)
        
        results = []
        
        for bank in banks:
            # Similar logic to ProblemBankAnalysisView but summarized
            ratings = InstructorProblemRating.objects.filter(
                problem__problem_bank=bank
            ).prefetch_related('entries')
            
            if not ratings.exists():
                continue
                
            # Calculate average scores per criterion
            rubric = bank.get_rubric()
            rubric_criteria = {c['id']: c['name'] for c in rubric.get('criteria', [])}
            
            c_totals = {}
            c_counts = {}
            
            # Also calculate IRR if possible
            # Need to reconstruct the data structure
            data = {} # pid -> { rater -> { c -> val } }
            raters = set()
            
            for r in ratings:
                pid = r.problem_id
                iid = r.instructor_id
                raters.add(iid)
                
                if pid not in data:
                    data[pid] = {}
                if iid not in data[pid]:
                    data[pid][iid] = {}
                
                for entry in r.entries.all():
                    c_id = entry.criterion_id
                    c_name = rubric_criteria.get(c_id, c_id)
                    
                    if c_name not in c_totals:
                        c_totals[c_name] = 0
                        c_counts[c_name] = 0
                    
                    c_totals[c_name] += entry.value
                    c_counts[c_name] += 1
                    
                    data[pid][iid][c_name] = entry.value
            
            means = {c: c_totals[c]/c_counts[c] for c in c_totals}
            
            # IRR
            irr = {}
            raters_list = list(raters)
            if len(raters_list) > 1:
                # Calculate IRR for each criterion
                for c in means.keys():
                    kappas = []
                    for i in range(len(raters_list)):
                        for j in range(i+1, len(raters_list)):
                            r1 = raters_list[i]
                            r2 = raters_list[j]
                            y1, y2 = [], []
                            for pid in data:
                                v1 = data[pid].get(r1, {}).get(c)
                                v2 = data[pid].get(r2, {}).get(c)
                                if v1 is not None and v2 is not None:
                                    y1.append(v1)
                                    y2.append(v2)
                            if len(y1) >= 5:
                                kappas.append(calculate_weighted_kappa(y1, y2))
                    if kappas:
                        irr[c] = np.mean(kappas)

            # Collect criteria values for ANOVA
            criteria_values = {} # criterion -> list of all values
            for r in ratings:
                for entry in r.entries.all():
                    c_id = entry.criterion_id
                    c_name = rubric_criteria.get(c_id, c_id)
                    if c_name not in criteria_values:
                        criteria_values[c_name] = []
                    criteria_values[c_name].append(entry.value)

            results.append({
                'id': bank.id,
                'name': bank.name,
                'means': means,
                'inter_rater_reliability': irr,
                'criteria_values': criteria_values
            })
            
        # Perform ANOVA if requested or always?
        # Let's do ANOVA for each criterion across banks
        
        # We need to know the order of criteria to display them consistently
        # Let's assume a standard set of criteria names if possible, or union them.
        # For now, just return the data.
        
        # To support the "Order Analysis Criteria" requirement, we need to respect the rubric order.
        # Since we are aggregating across banks, they might have different rubrics.
        # But usually they share a rubric structure if they are being compared.
        # Let's try to get a "master" order from the first bank or just alphabetical?
        # The requirement said "as defined by the rubric".
        # If banks have different rubrics, comparison is hard.
        # Let's assume they are similar.
        
        criteria_order_map = {}
        if banks.exists():
            # Use the first bank's rubric for ordering
            first_rubric = banks.first().get_rubric()
            for idx, c in enumerate(first_rubric.get('criteria', [])):
                criteria_order_map[c['name']] = idx
                
        all_criteria = set()
        for res in results:
            all_criteria.update(res['means'].keys())
            
        # Sort all_criteria based on the collected order
        sorted_criteria = sorted([c for c in all_criteria if c != 'weighted_score'], key=lambda x: (criteria_order_map.get(x, 999), x))

        anova_results = []
        
        for cid in sorted_criteria:
            groups = []
            group_names = []
            
            for res in results:
                if cid in res['criteria_values'] and len(res['criteria_values'][cid]) > 1:
                    groups.append(res['criteria_values'][cid])
                    group_names.append(res['name'])
            
            if len(groups) > 1:
                try:
                    f_stat, p_val = stats.f_oneway(*groups)
                except Exception:
                    f_stat, p_val = None, None

                if f_stat is not None and (np.isinf(f_stat) or np.isnan(f_stat)):
                    f_stat = None
                if p_val is not None and (np.isinf(p_val) or np.isnan(p_val)):
                    p_val = None
                
                anova_results.append({
                    'criterion_id': cid,
                    'f_stat': float(f_stat) if f_stat is not None else None,
                    'p_value': float(p_val) if p_val is not None else None,
                    'significant': p_val < 0.05 if p_val is not None else False,
                    'banks_included': group_names
                })

        return Response({
            'banks': [{
                'id': r['id'], 
                'name': r['name'], 
                'means': r['means'],
                'inter_rater_reliability': r['inter_rater_reliability']
            } for r in results],
            'anova': anova_results,
            'criteria_order': sorted_criteria
        })


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


class ProblemBankRubricView(APIView):
    permission_classes = [IsInstructor]

    def _get_bank(self, request, bank_id):
        instructor = ensure_instructor(request.user)
        return get_object_or_404(ProblemBank, id=bank_id, owner=instructor)

    def get(self, request, bank_id):
        bank = get_object_or_404(ProblemBank, id=bank_id)
        # Check if user is owner or has access (for now just owner for editing, but maybe public for viewing?)
        # The requirement says "Add feature for instructors to rate problems in problem bank".
        # Assuming the owner sets the rubric.
        return Response(bank.get_rubric())

    def put(self, request, bank_id):
        bank = self._get_bank(request, bank_id)
        
        rubric_id = request.data.get('rubric_id')
        if rubric_id is not None:
            if rubric_id == '':
                bank.rubric = None
            else:
                rubric = get_object_or_404(Rubric, id=rubric_id)
                bank.rubric = rubric
            bank.save()
            return Response(bank.get_rubric())
        
        return Response({'detail': 'Rubric ID is required.'}, status=status.HTTP_400_BAD_REQUEST)


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
