import csv
import random
from datetime import timedelta
from io import StringIO
from django.contrib.auth import authenticate, login, logout
from django.db import models, transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, parsers, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Instructor, ensure_instructor
from accounts.permissions import IsAdminInstructor, IsInstructor
from accounts.serializers import InstructorSerializer
from problems.models import ProblemBank, Problem
from problems.serializers import ProblemBankSerializer, ProblemSerializer, ProblemSummarySerializer
from quizzes.models import (
    Quiz,
    QuizSlot,
    QuizSlotProblemBank,
    QuizAttempt,
    QuizAttemptSlot,
)
from quizzes.response_config import load_response_config
from quizzes.serializers import (
    QuizSerializer,
    QuizSlotSerializer,
    QuizSlotProblemSerializer,
    QuizAttemptSerializer,
    QuizAttemptSlotSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        ensure_instructor(user)
        return Response({'detail': 'Logged in', 'username': user.get_username()})


class LogoutView(APIView):
    authentication_classes = []

    def post(self, request):
        logout(request)
        return Response({'detail': 'Logged out'})


class CSRFTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class InstructorViewSet(viewsets.ModelViewSet):
    serializer_class = InstructorSerializer
    queryset = Instructor.objects.select_related('user').all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    # Allow anyone to create an instructor (POST) so admins can invite via the UI,
    # but keep list/update/delete restricted to admin instructors.

    def _ensure_not_self_modification(self, instructor):
        user = self.request.user
        if user.is_superuser and instructor.user_id == user.id:
            if self._is_safe_super_admin_update():
                return
            raise PermissionDenied('Super admins cannot modify their own instructor entry.')

    def _is_safe_super_admin_update(self):
        allowed_fields = {'first_name', 'last_name', 'profile_picture'}
        data = getattr(self.request, 'data', {})
        if not data:
            return False
        # QueryDict and dict both support keys()
        keys = set()
        try:
            keys = set(data.keys())
        except Exception:
            return False
        extra = keys - allowed_fields
        # Allow CSRF token injected by middleware (if present)
        extra = {key for key in extra if not key.endswith('csrfmiddlewaretoken')}
        return len(extra) == 0

    def get_permissions(self):
        action = getattr(self, 'action', None)
        if action == 'create':
            return [AllowAny()]
        if action == 'me':
            return [IsInstructor()]
        return [IsAdminInstructor()]

    @action(detail=False, methods=['get'], permission_classes=[IsInstructor], url_path='me')
    def me(self, request):
        instructor = ensure_instructor(request.user)
        serializer = self.get_serializer(instructor)
        return Response(serializer.data)

    def perform_update(self, serializer):
        self._ensure_not_self_modification(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_not_self_modification(instance)
        super().perform_destroy(instance)


class ProblemBankViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemBankSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        return ProblemBank.objects.select_related('owner__user').all()

    def perform_create(self, serializer):
        serializer.save(owner=ensure_instructor(self.request.user))

    def _ensure_owner(self, bank):
        instructor = ensure_instructor(self.request.user)
        if bank.owner != instructor:
            raise PermissionDenied('Only the owner can modify this problem bank.')
        return instructor

    def perform_update(self, serializer):
        self._ensure_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_owner(instance)
        super().perform_destroy(instance)

    @action(detail=False, methods=['post'], url_path='import', parser_classes=[parsers.MultiPartParser, parsers.FormParser])
    def import_from_csv(self, request, *args, **kwargs):
        instructor = ensure_instructor(request.user)
        upload = request.FILES.get('file')
        name = (request.data.get('name') or '').strip()
        description = (request.data.get('description') or '').strip()

        if not name:
            return Response({'detail': 'Provide a name for the new bank.'}, status=status.HTTP_400_BAD_REQUEST)
        if not upload:
            return Response({'detail': 'Upload a CSV file that lists the problems.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'detail': 'CSV must be UTF-8 encoded.'}, status=status.HTTP_400_BAD_REQUEST)

        csv_stream = StringIO(decoded)
        try:
            reader = csv.DictReader(csv_stream)
        except csv.Error:
            return Response({'detail': 'Could not read the CSV file.'}, status=status.HTTP_400_BAD_REQUEST)

        if not reader.fieldnames:
            return Response(
                {'detail': 'CSV must include headers named "order" and "problem".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_headers = {name.strip().lower(): name for name in reader.fieldnames if name}
        order_header = normalized_headers.get('order')
        problem_header = normalized_headers.get('problem')
        if not order_header or not problem_header:
            return Response(
                {'detail': 'CSV headers must contain "order" and "problem" columns.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        problems = []
        seen_orders = set()
        row_number = 1  # header row
        try:
            for row in reader:
                row_number += 1
                raw_order = (row.get(order_header) or '').strip()
                statement = (row.get(problem_header) or '').strip()

                if not raw_order:
                    return Response(
                        {'detail': f'Row {row_number} is missing an order value.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not statement:
                    return Response(
                        {'detail': f'Row {row_number} is missing a problem statement.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    order = int(raw_order)
                except ValueError:
                    return Response(
                        {'detail': f'Row {row_number} has an invalid order value: {raw_order!r}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if order in seen_orders:
                    return Response(
                        {'detail': f'Duplicate order {order} found in the CSV file.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                seen_orders.add(order)
                problems.append({'order': order, 'statement': statement})
        except csv.Error:
            return Response({'detail': 'CSV file is malformed.'}, status=status.HTTP_400_BAD_REQUEST)

        if not problems:
            return Response({'detail': 'Add at least one problem to the CSV file.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            bank = ProblemBank.objects.create(name=name, description=description, owner=instructor)
            Problem.objects.bulk_create(
                [Problem(problem_bank=bank, order_in_bank=item['order'], statement=item['statement']) for item in problems]
            )

        serializer = self.get_serializer(bank)
        return Response({'bank': serializer.data, 'problem_count': len(problems)}, status=status.HTTP_201_CREATED)


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


class QuizViewSet(viewsets.ModelViewSet):
    serializer_class = QuizSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        instructor = ensure_instructor(self.request.user)
        return Quiz.objects.filter(
            models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
        ).distinct().prefetch_related('allowed_instructors')

    def perform_create(self, serializer):
        serializer.save(owner=ensure_instructor(self.request.user))

    @action(detail=True, methods=['post'], url_path='open')
    def open(self, request, pk=None):
        quiz = self.get_object()
        readiness_error = self._validate_publish_ready(quiz)
        if readiness_error:
            return Response({'detail': readiness_error}, status=status.HTTP_400_BAD_REQUEST)
        quiz.start_time = timezone.now()
        quiz.end_time = None
        quiz.save(update_fields=['start_time', 'end_time'])
        serializer = self.get_serializer(quiz)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='close')
    def close(self, request, pk=None):
        quiz = self.get_object()
        quiz.end_time = timezone.now()
        quiz.save(update_fields=['end_time'])
        serializer = self.get_serializer(quiz)
        return Response(serializer.data)

    def _validate_publish_ready(self, quiz):
        slots = (
            quiz.slots.annotate(problem_count=Count('slot_problems'))
            .select_related('problem_bank')
        )
        if not slots.exists():
            return 'Add at least one slot before opening this quiz.'
        for slot in slots:
            if slot.problem_bank_id is None:
                return 'Assign a problem bank to every slot before opening the quiz.'
            if getattr(slot, 'problem_count', 0) == 0:
                return f'Add at least one problem to the "{slot.label}" slot before opening the quiz.'
        return None


class QuizSlotViewSet(viewsets.ModelViewSet):
    serializer_class = QuizSlotSerializer
    permission_classes = [IsInstructor]
    queryset = QuizSlot.objects.select_related('quiz', 'problem_bank')

    def get_queryset(self):
        instructor = ensure_instructor(self.request.user)
        return QuizSlot.objects.filter(
            models.Q(quiz__owner=instructor) | models.Q(quiz__allowed_instructors=instructor)
        ).distinct().select_related('quiz', 'problem_bank')


class QuizSlotListCreate(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )
        slots = quiz.slots.all()
        serializer = QuizSlotSerializer(slots, many=True)
        return Response(serializer.data)

    def post(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )
        serializer = QuizSlotSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(quiz=quiz)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DashboardStatsView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        instructor = ensure_instructor(request.user)
        quiz_qs = (
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            )
            .distinct()
        )
        quiz_data = QuizSerializer(quiz_qs, many=True).data

        slot_qs = QuizSlot.objects.filter(quiz__in=quiz_qs)
        bank_qs = ProblemBank.objects.filter(owner=instructor)
        problem_qs = Problem.objects.filter(problem_bank__owner=instructor)
        attempt_qs = QuizAttempt.objects.filter(quiz__in=quiz_qs)

        attempts_by_date = (
            attempt_qs.filter(started_at__isnull=False)
            .annotate(date=TruncDate('started_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('-date')
        )

        today = timezone.now().date()
        date_window = [today - timedelta(days=i) for i in range(6, -1, -1)]
        attempts_by_date_map = {entry['date']: entry['count'] for entry in attempts_by_date}
        attempts_over_time = [
            {'date': day.isoformat(), 'count': attempts_by_date_map.get(day, 0)} for day in date_window
        ]

        attempts_by_quiz = (
            attempt_qs.values('quiz_id', 'quiz__title')
            .annotate(total=Count('id'))
            .order_by('-total')[:3]
        )

        completed_attempts = attempt_qs.filter(completed_at__isnull=False).count()
        attempts_today = attempt_qs.filter(started_at__date=today).count()
        slot_total = slot_qs.count()
        bank_total = bank_qs.count()
        problem_total = problem_qs.count()
        quiz_total = quiz_qs.count()
        avg_slots_per_quiz = round(slot_total / quiz_total, 1) if quiz_total else 0
        avg_problems_per_bank = round(problem_total / bank_total, 1) if bank_total else 0
        assigned_slots = slot_qs.filter(problem_bank__isnull=False).count()

        super_admin_stats = None
        if request.user.is_superuser:
            super_admin_stats = {
                'total_instructors': Instructor.objects.count(),
                'admin_instructors': Instructor.objects.filter(is_admin_instructor=True).count(),
                'total_quizzes': Quiz.objects.count(),
                'total_problem_banks': ProblemBank.objects.count(),
            }

        return Response(
            {
                'quizzes': quiz_data,
                'quiz_count': quiz_total,
                'scheduled_quizzes': quiz_qs.filter(start_time__isnull=False).count(),
                'published_quizzes': quiz_qs.filter(public_id__isnull=False).count(),
                'slot_count': slot_total,
                'assigned_slots': assigned_slots,
                'problem_bank_count': bank_total,
                'problem_count': problem_total,
                'avg_slots_per_quiz': avg_slots_per_quiz,
                'avg_problems_per_bank': avg_problems_per_bank,
                'attempt_count': attempt_qs.count(),
                'completed_attempts': completed_attempts,
                'attempts_today': attempts_today,
                'attempts_over_time': attempts_over_time,
                'top_quizzes': [
                    {'quiz_id': entry['quiz_id'], 'title': entry['quiz__title'], 'attempts': entry['total']}
                    for entry in attempts_by_quiz
                ],
                'super_admin': request.user.is_superuser,
                'super_admin_stats': super_admin_stats,
            }
        )


class QuizAllowedInstructorList(APIView):
    permission_classes = [IsInstructor]

    def get_quiz(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )
        return quiz, instructor

    def get(self, request, quiz_id):
        quiz, instructor = self.get_quiz(request, quiz_id)
        owner = quiz.owner
        owner_data = InstructorSerializer(owner, context={'request': request}).data
        owner_data['is_owner'] = True
        allowed_qs = quiz.allowed_instructors.exclude(id=owner.id)
        allowed_data = InstructorSerializer(allowed_qs, many=True, context={'request': request}).data
        for entry in allowed_data:
            entry['is_owner'] = False
        return Response(
            {
                'instructors': [owner_data, *allowed_data],
                'can_manage': quiz.owner_id == instructor.id,
            }
        )

    def post(self, request, quiz_id):
        quiz, instructor = self.get_quiz(request, quiz_id)
        if quiz.owner != instructor:
            raise PermissionDenied('Only the quiz owner can manage collaborators.')
        instructor_username = request.data.get('instructor_username')
        instructor_to_add = get_object_or_404(Instructor, user__username=instructor_username)
        quiz.allowed_instructors.add(instructor_to_add)
        return Response({'detail': 'Instructor added'})


class QuizAllowedInstructorDelete(APIView):
    permission_classes = [IsInstructor]

    def delete(self, request, quiz_id, instructor_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor:
            raise PermissionDenied('Only the quiz owner can manage collaborators.')
        quiz.allowed_instructors.remove(instructor_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuizAttemptList(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )
        attempts = quiz.attempts.prefetch_related(
            'attempt_slots__slot',
            'attempt_slots__assigned_problem',
        ).order_by('-started_at')
        serializer = QuizAttemptSerializer(attempts, many=True)
        return Response(serializer.data)


class QuizAttemptDetail(APIView):
    permission_classes = [IsInstructor]

    def delete(self, request, quiz_id, attempt_id):
        instructor = ensure_instructor(request.user)
        attempt = get_object_or_404(
            QuizAttempt.objects.filter(
                models.Q(quiz__owner=instructor) | models.Q(quiz__allowed_instructors=instructor)
            ).distinct(),
            id=attempt_id,
            quiz_id=quiz_id,
        )
        attempt.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SlotProblemListCreate(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, slot_id):
        instructor = ensure_instructor(request.user)
        slot = get_object_or_404(
            QuizSlot.objects.filter(
                models.Q(quiz__owner=instructor) | models.Q(quiz__allowed_instructors=instructor)
            ).distinct(),
            id=slot_id,
        )
        serializer = QuizSlotProblemSerializer(slot.slot_problems.all(), many=True)
        return Response(serializer.data)

    def post(self, request, slot_id):
        instructor = ensure_instructor(request.user)
        slot = get_object_or_404(
            QuizSlot.objects.filter(
                models.Q(quiz__owner=instructor) | models.Q(quiz__allowed_instructors=instructor)
            ).distinct(),
            id=slot_id,
        )
        if slot.problem_bank_id is None:
            return Response(
                {'detail': 'Assign a problem bank to this slot before selecting problems.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        problem_ids = request.data.get('problem_ids', [])
        if not isinstance(problem_ids, (list, tuple)):
            return Response({'detail': 'problem_ids must be a list of ids.'}, status=status.HTTP_400_BAD_REQUEST)
        if not problem_ids:
            return Response({'detail': 'Provide at least one problem id.'}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        for problem_id in problem_ids:
            problem = get_object_or_404(Problem, id=problem_id, problem_bank=slot.problem_bank)
            link, _ = QuizSlotProblemBank.objects.get_or_create(quiz_slot=slot, problem=problem)
            created.append(link)
        serializer = QuizSlotProblemSerializer(created, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SlotProblemDeleteView(generics.DestroyAPIView):
    permission_classes = [IsInstructor]
    serializer_class = QuizSlotProblemSerializer

    def get_queryset(self):
        instructor = ensure_instructor(self.request.user)
        return QuizSlotProblemBank.objects.filter(
            models.Q(quiz_slot__quiz__owner=instructor) | models.Q(quiz_slot__quiz__allowed_instructors=instructor)
        ).distinct()


class PublicQuizDetail(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        quiz = get_object_or_404(Quiz, public_id=public_id)
        data = {
            'title': quiz.title,
            'description': quiz.description,
            'start_time': quiz.start_time,
            'end_time': quiz.end_time,
            'is_open': quiz.is_open(),
        }
        return Response(data)


class PublicQuizStart(APIView):
    permission_classes = [AllowAny]

    def post(self, request, public_id):
        quiz = get_object_or_404(Quiz, public_id=public_id)
        identifier = (request.data.get('student_identifier') or '').strip()
        if not identifier:
            return Response({'detail': 'student_identifier is required'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        if quiz.start_time and now < quiz.start_time:
            return Response({'detail': 'Quiz not started yet'}, status=status.HTTP_400_BAD_REQUEST)
        if quiz.end_time and now > quiz.end_time:
            return Response({'detail': 'Quiz ended'}, status=status.HTTP_400_BAD_REQUEST)
        existing_attempt = (
            quiz.attempts.filter(student_identifier__iexact=identifier)
            .order_by('-started_at')
            .first()
        )
        if existing_attempt:
            if existing_attempt.completed_at:
                return Response({'detail': 'You have already submitted this quiz.'}, status=status.HTTP_400_BAD_REQUEST)
            attempt_slots = existing_attempt.attempt_slots.select_related('slot', 'assigned_problem').all()
            serializer = QuizAttemptSlotSerializer(attempt_slots, many=True)
            return Response({'attempt_id': existing_attempt.id, 'slots': serializer.data})

        slots = list(
            quiz.slots.prefetch_related('slot_problems__problem').all()
        )
        if not slots:
            return Response({'detail': 'Quiz has no problem slots configured'}, status=status.HTTP_400_BAD_REQUEST)
        slot_problem_map = {}
        for slot in slots:
            options = list(slot.slot_problems.all())
            if not options:
                return Response(
                    {'detail': f'Slot "{slot.label}" has no problems configured'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            slot_problem_map[slot.id] = options
        attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier=identifier)
        attempt_slots = []
        for slot in slots:
            selected_link = random.choice(slot_problem_map[slot.id])
            attempt_slot = QuizAttemptSlot.objects.create(
                attempt=attempt,
                slot=slot,
                assigned_problem=selected_link.problem,
            )
            attempt_slots.append(attempt_slot)
        serializer = QuizAttemptSlotSerializer(attempt_slots, many=True)
        return Response({'attempt_id': attempt.id, 'slots': serializer.data})


class PublicAttemptSlotAnswer(APIView):
    permission_classes = [AllowAny]

    def post(self, request, attempt_id, slot_id):
        attempt_slot = get_object_or_404(QuizAttemptSlot, attempt_id=attempt_id, slot_id=slot_id)
        if attempt_slot.attempt.completed_at:
            return Response({'detail': 'This attempt has already been submitted.'}, status=status.HTTP_400_BAD_REQUEST)
        quiz = attempt_slot.attempt.quiz
        if not quiz.is_open():
            return Response(
                {'detail': 'This quiz window has closed and new answers are no longer accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = request.data.get('answer_data')
        if not isinstance(payload, dict):
            legacy_answer = request.data.get('answer_text')
            if isinstance(legacy_answer, str):
                payload = {
                    'response_type': QuizSlot.ResponseType.OPEN_TEXT,
                    'text': legacy_answer,
                }
        if not isinstance(payload, dict):
            return Response({'detail': 'answer_data must be provided.'}, status=status.HTTP_400_BAD_REQUEST)
        normalized = self.normalize_answer(attempt_slot.slot, payload)
        attempt_slot.answer_data = normalized
        attempt_slot.answered_at = timezone.now()
        attempt_slot.save(update_fields=['answer_data', 'answered_at'])
        return Response({'detail': 'Answer saved', 'answer_data': normalized})

    def normalize_answer(self, slot, payload):
        if slot.response_type == QuizSlot.ResponseType.OPEN_TEXT:
            text = (payload.get('text') or '').strip()
            if not text:
                raise serializers.ValidationError({'detail': 'Please provide an answer before saving.'})
            return {
                'response_type': QuizSlot.ResponseType.OPEN_TEXT,
                'text': text,
            }
        if slot.response_type == QuizSlot.ResponseType.RATING:
            return self.normalize_rating_answer(payload)
        raise serializers.ValidationError({'detail': 'Unsupported response type.'})

    def normalize_rating_answer(self, payload):
        try:
            config = load_response_config()
        except FileNotFoundError as exc:
            raise serializers.ValidationError({'detail': 'Rating rubric configuration is missing.'}) from exc
        scale_options = config.get('scale') or []
        criteria = config.get('criteria') or []
        if not scale_options or not criteria:
            raise serializers.ValidationError({'detail': 'Rating rubric configuration is incomplete.'})
        ratings = payload.get('ratings')
        if not isinstance(ratings, dict):
            raise serializers.ValidationError({'detail': 'Provide a rating for each rubric criterion.'})
        scale_map = {str(option.get('value')): option.get('value') for option in scale_options if 'value' in option}
        if not scale_map:
            raise serializers.ValidationError({'detail': 'Rating scale has no options configured.'})
        normalized = {}
        missing = []
        expected_keys = []
        for criterion in criteria:
            criterion_id = str(criterion.get('id', '')).strip()
            if not criterion_id:
                continue
            expected_keys.append(criterion_id)
            if criterion_id not in ratings:
                missing.append(criterion_id)
                continue
            raw_value = ratings[criterion_id]
            key = str(raw_value)
            if key not in scale_map:
                name = criterion.get('name') or criterion_id
                raise serializers.ValidationError({'detail': f'Invalid rating selected for {name}.'})
            normalized[criterion_id] = scale_map[key]
        if missing:
            raise serializers.ValidationError({'detail': f'Missing ratings for: {", ".join(missing)}.'})
        extra_keys = [key for key in ratings.keys() if key not in expected_keys]
        if extra_keys:
            raise serializers.ValidationError({'detail': f'Unknown rubric criteria submitted: {", ".join(extra_keys)}.'})
        return {
            'response_type': QuizSlot.ResponseType.RATING,
            'ratings': normalized,
        }


class PublicAttemptDetail(APIView):
    permission_classes = [AllowAny]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt.objects.prefetch_related(
                'attempt_slots__slot',
                'attempt_slots__assigned_problem',
            ),
            id=attempt_id,
        )
        serializer = QuizAttemptSerializer(attempt)
        return Response(serializer.data)


class ResponseConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            config = load_response_config()
        except FileNotFoundError:
            return Response({'detail': 'Response configuration file is missing.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(config)


class PublicAttemptComplete(APIView):
    permission_classes = [AllowAny]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, id=attempt_id)
        if attempt.completed_at:
            return Response({'detail': 'This attempt has already been submitted.'}, status=status.HTTP_400_BAD_REQUEST)
        if not attempt.quiz.is_open():
            return Response(
                {'detail': 'This quiz window has closed and submissions are no longer accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pending_slots = request.data.get('slots')
        if pending_slots is not None:
            self._save_pending_answers(attempt, pending_slots)
        attempt.completed_at = timezone.now()
        attempt.save()
        serializer = QuizAttemptSerializer(attempt)
        return Response(serializer.data)

    def _save_pending_answers(self, attempt, slots_payload):
        if not isinstance(slots_payload, list):
            raise serializers.ValidationError({'detail': 'slots must be a list of answers.'})
        attempt_slots = list(attempt.attempt_slots.select_related('slot').all())
        slot_map = {slot.slot_id: slot for slot in attempt_slots}
        attempt_slot_map = {slot.id: slot for slot in attempt_slots}
        normalizer = PublicAttemptSlotAnswer()
        now = timezone.now()
        updates = []
        for entry in slots_payload:
            slot_id = entry.get('slot_id') if isinstance(entry, dict) else None
            answer_data = entry.get('answer_data') if isinstance(entry, dict) else None
            if slot_id is None:
                raise serializers.ValidationError({'detail': 'Each slot answer must include a slot_id.'})
            if not isinstance(answer_data, dict):
                raise serializers.ValidationError({'detail': f'Answer data for slot {slot_id} must be an object.'})
            attempt_slot = slot_map.get(slot_id) or attempt_slot_map.get(slot_id)
            if attempt_slot is None:
                raise serializers.ValidationError({'detail': f'Unknown slot id: {slot_id}.'})
            normalized = normalizer.normalize_answer(attempt_slot.slot, answer_data)
            attempt_slot.answer_data = normalized
            attempt_slot.answered_at = now
            updates.append(attempt_slot)
        if updates:
            QuizAttemptSlot.objects.bulk_update(updates, ['answer_data', 'answered_at'])
