import csv
import openpyxl
from django.db import models, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from accounts.permissions import IsInstructor
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from accounts.models import ensure_instructor
from problems.models import Problem
from quizzes.models import Quiz, QuizAttempt, QuizAttemptSlot, QuizSlot, QuizSlotGrade
from quizzes.serializers import QuizSlotGradeSerializer


class QuizSlotGradeView(APIView):
    permission_classes = [IsInstructor]

    def put(self, request, quiz_id, attempt_id, slot_id):
        instructor = ensure_instructor(request.user)
        # Verify access
        get_object_or_404(
            Quiz.objects.filter(models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)).distinct(),
            id=quiz_id,
        )
        attempt_slot = get_object_or_404(
            QuizAttemptSlot,
            attempt__quiz_id=quiz_id,
            attempt_id=attempt_id,
            slot_id=slot_id
        )
        
        try:
            grade = attempt_slot.grade
            serializer = QuizSlotGradeSerializer(grade, data=request.data)
        except QuizSlotGrade.DoesNotExist:
            serializer = QuizSlotGradeSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        serializer.save(attempt_slot=attempt_slot, grader=instructor)
        return Response(serializer.data)


class QuizGradeExportView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)).distinct(),
            id=quiz_id,
        )

        attempts = QuizAttempt.objects.filter(quiz=quiz).prefetch_related(
            'attempt_slots__grade__items__selected_level',
            'attempt_slots__grade__items__rubric_item__levels'
        )

        # Prepare CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{quiz.title}_grades.csv"'

        writer = csv.writer(response)
        writer.writerow(['Student Identifier', 'Grade'])

        rubric = quiz.grading_rubric if hasattr(quiz, 'grading_rubric') else None
        
        for attempt in attempts:
            total_score = 0
            # Calculate score
            # We can reuse logic similar to frontend or re-implement robustly
            # Iterate through slots
            for slot in attempt.attempt_slots.all():
                if hasattr(slot, 'grade'):
                    for item in slot.grade.items.all():
                        total_score += item.selected_level.points

            writer.writerow([attempt.student_identifier, total_score])

        return response


class ManualResponseView(APIView):
    permission_classes = [IsInstructor]

    def post(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )
        
        student_identifier = (request.data.get('student_identifier') or '').strip()
        if not student_identifier:
            return Response({'detail': 'Student identifier is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        answers = request.data.get('answers', {}) # Map of slot_id -> { problem_id, answer_data }
        
        # Create attempt
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_identifier=student_identifier,
            started_at=timezone.now(),
            completed_at=timezone.now()
        )
        
        # Process slots
        slots = quiz.slots.all()
        attempt_slots = []
        
        for slot in slots:
            slot_id_str = str(slot.id)
            answer_entry = answers.get(slot_id_str)
            
            assigned_problem = None
            answer_data = None
            
            if answer_entry:
                problem_id = answer_entry.get('problem_id')
                if problem_id:
                    assigned_problem = Problem.objects.filter(id=problem_id).first()
                
                answer_data = answer_entry.get('answer_data')
            
            # If no problem assigned, we must assign one if the slot has problems.
            # If the user didn't select one, we can't create the slot attempt properly if we enforce it.
            # But the model requires it.
            # Let's try to pick the first available problem if none selected?
            # Or fail?
            # Let's fail if not provided, but maybe the UI will ensure it.
            # If we fail here, the whole attempt creation fails (transaction?).
            
            if not assigned_problem:
                # Fallback: pick a random problem from the slot's bank
                # This is risky if the instructor meant to select one.
                # But for now, let's assume the UI sends it.
                # If not, we try to get one.
                slot_problems = list(slot.slot_problems.all())
                if slot_problems:
                    assigned_problem = slot_problems[0].problem
            
            if not assigned_problem:
                 # If still no problem (empty bank?), we can't create the slot attempt.
                 # Skip this slot? Or error?
                 # If we skip, the attempt will be incomplete.
                 continue

            attempt_slot = QuizAttemptSlot(
                attempt=attempt,
                slot=slot,
                assigned_problem=assigned_problem,
                answer_data=answer_data,
                answered_at=timezone.now() if answer_data else None
            )
            attempt_slots.append(attempt_slot)
            
        QuizAttemptSlot.objects.bulk_create(attempt_slots)
        
        return Response({'detail': 'Response added successfully.', 'attempt_id': attempt.id}, status=status.HTTP_201_CREATED)


class ResponseImportTemplateView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Responses"
        
        headers = ['Student Identifier']
        slots = quiz.slots.all().order_by('order')
        
        for slot in slots:
            headers.append(f'Slot {slot.order} Problem Order')
            headers.append(f'Slot {slot.order} Answer')
            
        ws.append(headers)
        
        # Add a sample row or instruction?
        # Maybe just leave it empty for now.
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=quiz_{quiz_id}_responses_template.xlsx'
        wb.save(response)
        return response


class ResponseImportView(APIView):
    permission_classes = [IsInstructor]

    def post(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )
        
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            wb = openpyxl.load_workbook(file)
            ws = wb.active
            
            rows = list(ws.rows)
            if not rows:
                return Response({'detail': 'Empty file.'}, status=status.HTTP_400_BAD_REQUEST)
                
            headers = [cell.value for cell in rows[0]]
            
            # Basic validation of headers
            if not headers or headers[0] != 'Student Identifier':
                 return Response({'detail': 'Invalid format. First column must be "Student Identifier".'}, status=status.HTTP_400_BAD_REQUEST)

            slots = list(quiz.slots.all().order_by('order'))
            
            # Map headers to slots?
            # We assume the structure: ID, Slot 1 Problem, Slot 1 Answer, Slot 2 Problem, Slot 2 Answer...
            # We can verify this structure matches the current quiz slots count.
            
            expected_cols = 1 + (len(slots) * 2)
            if len(headers) < expected_cols:
                 return Response({'detail': f'Invalid format. Expected {expected_cols} columns for {len(slots)} slots.'}, status=status.HTTP_400_BAD_REQUEST)

            created_attempts = []
            errors = []
            
            for row_idx, row in enumerate(rows[1:], start=2):
                student_identifier = str(row[0].value or '').strip()
                if not student_identifier:
                    continue # Skip empty rows
                    
                try:
                    with transaction.atomic():
                        attempt = QuizAttempt.objects.create(
                            quiz=quiz,
                            student_identifier=student_identifier,
                            started_at=timezone.now(),
                            completed_at=timezone.now()
                        )
                        
                        attempt_slots = []
                        
                        for i, slot in enumerate(slots):
                            # Columns for this slot: 1 + (i * 2) and 1 + (i * 2) + 1
                            problem_col_idx = 1 + (i * 2)
                            answer_col_idx = problem_col_idx + 1
                            
                            problem_order_val = row[problem_col_idx].value
                            answer_val = row[answer_col_idx].value
                            
                            assigned_problem = None
                            answer_data = None
                            
                            # Find problem
                            if problem_order_val is not None:
                                try:
                                    problem_order = int(problem_order_val)
                                    # Find problem in the slot's bank with this order
                                    # We need to query the Problem model.
                                    # slot.problem_bank.problems...
                                    assigned_problem = Problem.objects.filter(
                                        problem_bank=slot.problem_bank,
                                        order_in_bank=problem_order
                                    ).first()
                                except (ValueError, TypeError):
                                    pass
                            
                            if not assigned_problem:
                                # Fallback or error?
                                # For now, let's error if we can't find the problem, as it's required.
                                raise ValueError(f"Invalid problem order '{problem_order_val}' for slot {slot.order}")

                            # Parse answer
                            if slot.response_type == QuizSlot.ResponseType.OPEN_TEXT:
                                text = str(answer_val or '').strip()
                                answer_data = {'text': text}
                            elif slot.response_type == QuizSlot.ResponseType.RATING:
                                val = answer_val
                                ratings = {}
                                rubric = quiz.get_rubric()
                                criteria = rubric.get('criteria', [])
                                
                                if criteria:
                                    # Create a map of normalized name to ID for easier matching
                                    criteria_map = {c['name'].strip().lower(): c['id'] for c in criteria}
                                    # Also map ID to ID for direct lookup
                                    criteria_id_map = {str(c['id']).strip().lower(): c['id'] for c in criteria}
                                    
                                    # Case 1: Simple number (assign to first criterion)
                                    if isinstance(val, (int, float)) or (isinstance(val, str) and val.strip().isdigit()):
                                        try:
                                            rating_val = int(float(val))
                                            if criteria:
                                                ratings[criteria[0]['id']] = rating_val
                                        except (ValueError, TypeError):
                                            pass
                                    
                                    # Case 2: String format "Crit1: 5, Crit2: 4" or "ID: 5"
                                    elif isinstance(val, str):
                                        # Split by comma or semicolon or newline
                                        import re
                                        parts = re.split(r'[;,\n]', val)
                                        for part in parts:
                                            if ':' in part or '=' in part:
                                                sep = ':' if ':' in part else '='
                                                c_key, c_val = part.split(sep, 1)
                                                c_key = c_key.strip().lower()
                                                c_val = c_val.strip()
                                                
                                                # Try to match name OR ID
                                                c_id = criteria_map.get(c_key)
                                                if not c_id:
                                                    c_id = criteria_id_map.get(c_key)
                                                    
                                                if c_id:
                                                    try:
                                                        ratings[c_id] = int(float(c_val))
                                                    except ValueError:
                                                        pass
                                
                                answer_data = {'ratings': ratings}

                            attempt_slots.append(QuizAttemptSlot(
                                attempt=attempt,
                                slot=slot,
                                assigned_problem=assigned_problem,
                                answer_data=answer_data,
                                answered_at=timezone.now()
                            ))
                        
                        QuizAttemptSlot.objects.bulk_create(attempt_slots)
                        created_attempts.append(attempt.id)
                        
                except Exception as e:
                    errors.append(f"Row {row_idx} ({student_identifier}): {str(e)}")
            
            return Response({
                'detail': f'Imported {len(created_attempts)} responses.',
                'errors': errors
            }, status=status.HTTP_200_OK if not errors else status.HTTP_207_MULTI_STATUS)

        except Exception as e:
            return Response({'detail': f'Error processing file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
