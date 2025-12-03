import csv
import random
from datetime import timedelta
from io import StringIO
from django.contrib.auth import authenticate, login, logout
from django.db import models, transaction
from django.db.models import Count, Avg, Min, Max, StdDev
from django.db.models.functions import TruncDate
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, parsers, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
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
    QuizAttemptInteraction,
    QuizRatingScaleOption,
    QuizRatingCriterion,
    GradingRubric,
    GradingRubric,
    QuizSlotGrade,
    QuizSlotGradeItem,
)
from quizzes.response_config import load_response_config
from quizzes.serializers import (
    QuizSerializer,
    QuizSlotSerializer,
    QuizSlotProblemSerializer,
    QuizAttemptSerializer,
    QuizAttemptSlotSerializer,
    QuizAttemptInteractionSerializer,
    GradingRubricSerializer,
    QuizSlotGradeSerializer,
)


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


class QuizRubricScaleSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    label = serializers.CharField()


class QuizRubricCriterionSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()


class QuizRubricPayloadSerializer(serializers.Serializer):
    scale = QuizRubricScaleSerializer(many=True)
    criteria = QuizRubricCriterionSerializer(many=True)

    def validate_scale(self, value):
        seen = set()
        for option in value:
            val = option['value']
            if val in seen:
                raise serializers.ValidationError('Duplicate rating values are not allowed.')
            seen.add(val)
        return value

    def validate_criteria(self, value):
        seen = set()
        normalized = []
        for criterion in value:
            criterion_id = str(criterion.get('id') or '').strip()
            if not criterion_id:
                raise serializers.ValidationError('Each criterion must include an id.')
            if criterion_id in seen:
                raise serializers.ValidationError(f'Duplicate criterion id: {criterion_id}')
            seen.add(criterion_id)
            normalized.append({**criterion, 'id': criterion_id})
        return normalized


class QuizRubricView(APIView):
    permission_classes = [IsInstructor]

    def _get_quiz(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        return get_object_or_404(
            Quiz.objects.filter(models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)).distinct(),
            id=quiz_id,
        )

    def get(self, request, quiz_id):
        quiz = self._get_quiz(request, quiz_id)
        return Response(quiz.get_rubric())

    def put(self, request, quiz_id):
        quiz = self._get_quiz(request, quiz_id)
        serializer = QuizRubricPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        with transaction.atomic():
            quiz.rating_scale_options.all().delete()
            quiz.rating_criteria.all().delete()
            scale_objects = [
                QuizRatingScaleOption(
                    quiz=quiz,
                    order=index,
                    value=option['value'],
                    label=option['label'],
                )
                for index, option in enumerate(payload['scale'])
            ]
            criterion_objects = [
                QuizRatingCriterion(
                    quiz=quiz,
                    order=index,
                    criterion_id=criterion['id'],
                    name=criterion['name'],
                    description=criterion['description'],
                )
                for index, criterion in enumerate(payload['criteria'])
            ]
            if scale_objects:
                QuizRatingScaleOption.objects.bulk_create(scale_objects)
            if criterion_objects:
                QuizRatingCriterion.objects.bulk_create(criterion_objects)
        return Response(quiz.get_rubric())


class GradingRubricView(APIView):
    permission_classes = [IsInstructor]

    def _get_quiz(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        return get_object_or_404(
            Quiz.objects.filter(models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)).distinct(),
            id=quiz_id,
        )

    def get(self, request, quiz_id):
        quiz = self._get_quiz(request, quiz_id)
        try:
            rubric = quiz.grading_rubric
        except GradingRubric.DoesNotExist:
            return Response({'items': []})
        serializer = GradingRubricSerializer(rubric)
        return Response(serializer.data)

    def put(self, request, quiz_id):
        quiz = self._get_quiz(request, quiz_id)
        rubric, created = GradingRubric.objects.get_or_create(quiz=quiz)
        serializer = GradingRubricSerializer(rubric, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


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
        attempts = (
            quiz.attempts
            .select_related('quiz')
            .prefetch_related(
                'attempt_slots__slot',
                'attempt_slots__assigned_problem',
                'quiz__rating_scale_options',
                'quiz__rating_criteria',
            )
            .order_by('-started_at')
        )
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


class QuizAttemptInteractions(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, quiz_id, attempt_id):
        instructor = ensure_instructor(request.user)
        attempt = get_object_or_404(
            QuizAttempt.objects.filter(
                models.Q(quiz__owner=instructor) | models.Q(quiz__allowed_instructors=instructor)
            ).distinct(),
            id=attempt_id,
            quiz_id=quiz_id,
        )
        attempt_slots = (
            attempt.attempt_slots.select_related('slot').prefetch_related('interactions').all()
        )
        slots_payload = []
        for attempt_slot in attempt_slots:
            slot = attempt_slot.slot
            slots_payload.append(
                {
                    'id': attempt_slot.id,
                    'slot_id': slot.id,
                    'slot_label': slot.label,
                    'response_type': slot.response_type,
                    'interactions': [
                        {
                            'event_type': interaction.event_type,
                            'metadata': interaction.metadata,
                            'created_at': interaction.created_at,
                        }
                        for interaction in attempt_slot.interactions.order_by('created_at')
                    ],
                }
            )
        return Response(
            {
                'attempt_id': attempt.id,
                'started_at': attempt.started_at,
                'completed_at': attempt.completed_at,
                'slots': slots_payload,
            }
        )


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
            'identity_instruction': quiz.identity_instruction or Quiz.IDENTITY_INSTRUCTION_DEFAULT,
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
            return self.normalize_rating_answer(slot, payload)
        raise serializers.ValidationError({'detail': 'Unsupported response type.'})

    def normalize_rating_answer(self, slot, payload):
        rubric = slot.quiz.get_rubric()
        scale_options = rubric.get('scale') or []
        criteria = rubric.get('criteria') or []
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


class PublicAttemptSlotInteraction(APIView):
    permission_classes = [AllowAny]

    def post(self, request, attempt_id, slot_id):
        attempt_slot = get_object_or_404(QuizAttemptSlot, attempt_id=attempt_id, slot_id=slot_id)
        attempt = attempt_slot.attempt
        if attempt.completed_at:
            return Response({'detail': 'This attempt has already been submitted.'}, status=status.HTTP_400_BAD_REQUEST)
        if not attempt.quiz.is_open():
            return Response(
                {'detail': 'This quiz window has closed and new answers are no longer accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = QuizAttemptInteractionSerializer(data=request.data, context={'attempt_slot': attempt_slot})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Interaction logged'}, status=status.HTTP_201_CREATED)


class PublicAttemptDetail(APIView):
    permission_classes = [AllowAny]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt.objects.prefetch_related(
                'attempt_slots__slot',
                'attempt_slots__assigned_problem',
                'quiz__rating_scale_options',
                'quiz__rating_criteria',
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



import openpyxl
from django.http import HttpResponse

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


class QuizAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        # Get optional per-slot problem filters
        # Format: slot_filters={"slot_id": "problem_label", ...}
        slot_filters_param = request.query_params.get('slot_filters')
        slot_filters = {}
        if slot_filters_param:
            try:
                import json
                slot_filters = json.loads(slot_filters_param)
            except:
                pass
        
        # Get optional global problem filter (legacy support)
        problem_id = request.query_params.get('problem_id')
        
        attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
        
        # If filtering by problem, only include attempts that have that problem assigned
        if problem_id:
            attempts = attempts.filter(
                attempt_slots__assigned_problem_id=problem_id
            ).distinct()
        
        total_attempts = attempts.count()
        
        # Completion stats - since we only query completed attempts, completion rate is 100%
        # unless we want to compare against all attempts (including incomplete ones)
        all_attempts = QuizAttempt.objects.filter(quiz=quiz).count()
        completion_rate = (total_attempts / all_attempts * 100) if all_attempts > 0 else 0
        
        # Time distribution
        durations = []
        for attempt in attempts:
            if attempt.started_at and attempt.completed_at:
                diff = (attempt.completed_at - attempt.started_at).total_seconds()
                if diff > 0:
                    durations.append(diff / 60.0) # minutes

        time_stats = {
            'min': min(durations) if durations else 0,
            'max': max(durations) if durations else 0,
            'mean': sum(durations) / len(durations) if durations else 0,
            'median': sorted(durations)[len(durations) // 2] if durations else 0,
            'count': len(durations),
            'raw_values': durations
        }

        # Slot analytics
        slots_data = []
        quiz_slots = quiz.slots.all().order_by('order')
        
        # Pre-fetch all interactions for this quiz's attempts to avoid N+1 and reduce memory
        # Group by slot_id
        interactions_by_slot = {}
        # Use values() to avoid creating model instances
        all_interactions = QuizAttemptInteraction.objects.filter(
            attempt_slot__attempt__in=attempts
        ).values(
            'attempt_slot__slot_id',
            'event_type',
            'created_at',
            'metadata',
            'attempt_slot__attempt__student_identifier',
            'attempt_slot__attempt__started_at',
            'attempt_slot__attempt__completed_at'
        )
        
        for interaction in all_interactions:
            slot_id = interaction['attempt_slot__slot_id']
            if slot_id not in interactions_by_slot:
                interactions_by_slot[slot_id] = []
            
            # Calculate relative position if possible
            start = interaction['attempt_slot__attempt__started_at']
            end = interaction['attempt_slot__attempt__completed_at']
            created_at = interaction['created_at']
            position = 0
            if start and end and created_at:
                total_duration = (end - start).total_seconds()
                if total_duration > 0:
                    event_time = (created_at - start).total_seconds()
                    position = min(max(event_time / total_duration, 0), 1) * 100

            interactions_by_slot[slot_id].append({
                'event_type': interaction['event_type'],
                'created_at': created_at,
                'metadata': interaction['metadata'],
                'position': position,
                'student_id': interaction['attempt_slot__attempt__student_identifier'],
                'attempt_started_at': start,
                'attempt_completed_at': end
            })

        rubric = quiz.get_rubric()
        criteria = rubric.get('criteria', [])
        scale = rubric.get('scale', [])
        scale_values = [s['value'] for s in scale] if scale else []

        # Pre-fetch all attempt slots for these attempts to avoid N+1 and reduce memory
        # Use values() to avoid creating model instances
        all_attempt_slots = QuizAttemptSlot.objects.filter(
            attempt__in=attempts
        ).values(
            'id',
            'slot_id',
            'assigned_problem__order_in_bank',
            'assigned_problem__id',
            'assigned_problem__group',
            'answer_data',
            'attempt__started_at',
            'attempt__completed_at',
            'attempt__student_identifier',
            'attempt_id'
        )

        # Fetch grades and items
        # We need to map attempt_slot_id -> grade info
        grades = QuizSlotGrade.objects.filter(
            attempt_slot__attempt__in=attempts
        ).prefetch_related('items__rubric_item', 'items__selected_level')
        
        grades_map = {}
        for grade in grades:
            items_data = {}
            total_score = 0
            for item in grade.items.all():
                items_data[item.rubric_item.id] = item.selected_level.points
                total_score += item.selected_level.points
            
            grades_map[grade.attempt_slot_id] = {
                'total_score': total_score,
                'items': items_data
            }

        # Group attempt slots by slot_id
        attempt_slots_by_slot = {}
        for attempt_slot in all_attempt_slots:
            slot_id = attempt_slot['slot_id']
            if slot_id not in attempt_slots_by_slot:
                attempt_slots_by_slot[slot_id] = []
            
            # Calculate duration
            start = attempt_slot['attempt__started_at']
            end = attempt_slot['attempt__completed_at']
            duration = (end - start).total_seconds() / 60.0 if start and end else None
            attempt_slot['attempt__duration'] = duration
            
            # Attach grade info
            if attempt_slot['id'] in grades_map:
                attempt_slot['grade'] = grades_map[attempt_slot['id']]
            
            attempt_slots_by_slot[slot_id].append(attempt_slot)

        # Collect all word counts for global average
        all_word_counts = []

        for slot in quiz_slots:
            # Get pre-fetched slots for this slot
            slot_attempts_list = attempt_slots_by_slot.get(slot.id, [])
            
            # Check if this slot has a specific problem filter
            slot_filter = slot_filters.get(str(slot.id))
            
            filtered_slot_attempts = []
            if slot_filter and slot_filter != 'all':
                # Filter by problem label (order in bank)
                try:
                    filter_order = int(slot_filter.split()[-1])
                    filtered_slot_attempts = [
                        sa for sa in slot_attempts_list 
                        if sa['assigned_problem__order_in_bank'] == filter_order
                    ]
                except (ValueError, IndexError):
                    filtered_slot_attempts = slot_attempts_list
            elif problem_id:
                # Fall back to global filter
                try:
                    pid = int(problem_id)
                    filtered_slot_attempts = [
                        sa for sa in slot_attempts_list 
                        if sa['assigned_problem__id'] == pid
                    ]
                except ValueError:
                    filtered_slot_attempts = slot_attempts_list
            else:
                filtered_slot_attempts = slot_attempts_list
            
            # Problem distribution
            prob_stats = {}
            prob_order = {}  # Track order_in_bank for each problem
            group_stats = {} # group_name -> { criterion_id -> { value -> count } }
            
            for sa in filtered_slot_attempts:
                order = sa['assigned_problem__order_in_bank']
                label = f"Problem {order}"
                group_name = sa.get('assigned_problem__group') or 'Ungrouped'
                
                if group_name not in group_stats:
                    group_stats[group_name] = {}
                
                if label not in prob_stats:
                    prob_stats[label] = {
                        'count': 0,
                        'total_score': 0,
                        'total_time': 0,
                        'total_words': 0,
                        'scores_count': 0, # Denominator for score avg (only graded)
                        'times_count': 0, # Denominator for time avg (only completed attempts)
                        'words_count': 0, # Denominator for word avg (only text answers)
                        'criteria_scores': {}, # criterion_id -> {total, count}
                        'rating_counts': {}, # criterion_id -> {value -> count}
                        'problem_id': sa['assigned_problem__id']
                    }
                
                stats = prob_stats[label]
                stats['count'] += 1
                prob_order[label] = order
                
                # Time
                if sa.get('attempt__duration') is not None:
                     stats['total_time'] += sa['attempt__duration']
                     stats['times_count'] += 1

                # Word count
                if sa['answer_data'] and 'text' in sa['answer_data']:
                    text = sa['answer_data']['text']
                    count = len(text.split())
                    stats['total_words'] += count
                    stats['words_count'] += 1
                
                # Score
                if 'grade' in sa:
                    grade = sa['grade']
                    stats['total_score'] += grade['total_score']
                    stats['scores_count'] += 1
                    
                    for c_id, score in grade['items'].items():
                        if c_id not in stats['criteria_scores']:
                            stats['criteria_scores'][c_id] = {'total': 0, 'count': 0}
                        stats['criteria_scores'][c_id]['total'] += score
                        stats['criteria_scores'][c_id]['count'] += 1

                # Rating distribution
                if sa['answer_data'] and 'ratings' in sa['answer_data']:
                    ratings = sa['answer_data']['ratings']
                    for c_id, val in ratings.items():
                        if c_id not in stats['rating_counts']:
                            stats['rating_counts'][c_id] = {}
                        if val not in stats['rating_counts'][c_id]:
                            stats['rating_counts'][c_id][val] = 0
                        stats['rating_counts'][c_id][val] += 1

                        # Aggregate for average calculation
                        if c_id not in stats['criteria_scores']:
                            stats['criteria_scores'][c_id] = {'total': 0, 'count': 0}
                        stats['criteria_scores'][c_id]['total'] += val
                        stats['criteria_scores'][c_id]['total'] += val
                        stats['criteria_scores'][c_id]['count'] += 1

                        # Group aggregation
                        if c_id not in group_stats[group_name]:
                            group_stats[group_name][c_id] = {}
                        if val not in group_stats[group_name][c_id]:
                            group_stats[group_name][c_id][val] = 0
                        group_stats[group_name][c_id][val] += 1

            prob_dist_list = []
            for label, stats in prob_stats.items():
                avg_criteria = {}
                for c_id, c_stats in stats['criteria_scores'].items():
                    avg_criteria[c_id] = c_stats['total'] / c_stats['count'] if c_stats['count'] > 0 else 0

                prob_dist_list.append({
                    'label': label,
                    'problem_id': stats['problem_id'],
                    'count': stats['count'],
                    'avg_score': stats['total_score'] / stats['scores_count'] if stats['scores_count'] > 0 else 0,
                    'avg_time': stats['total_time'] / stats['times_count'] if stats['times_count'] > 0 else 0,
                    'avg_words': stats['total_words'] / stats['words_count'] if stats['words_count'] > 0 else 0,
                    'avg_words': stats['total_words'] / stats['words_count'] if stats['words_count'] > 0 else 0,
                    'avg_criteria_scores': avg_criteria,
                    'criteria_distributions': []
                })
                
                # Format rating distribution for this problem
                if stats['rating_counts']:
                    c_dists = []
                    for criterion in criteria:
                        c_id = criterion['id']
                        c_name = criterion['name']
                        
                        counts = stats['rating_counts'].get(c_id, {})
                        # Ensure all scale values are present
                        dist_data = []
                        total_responses = sum(counts.values())
                        
                        for val in scale_values:
                            count = counts.get(val, 0)
                            percentage = (count / total_responses * 100) if total_responses > 0 else 0
                            label = next((s['label'] for s in scale if s['value'] == val), str(val))
                            dist_data.append({
                                'value': val,
                                'label': label,
                                'count': count,
                                'percentage': percentage
                            })
                            
                        c_dists.append({
                            'criterion_id': c_id,
                            'name': c_name,
                            'distribution': dist_data,
                            'total': total_responses
                        })
                    prob_dist_list[-1]['criteria_distributions'] = c_dists

            # Sort by order in bank
            prob_dist_list.sort(key=lambda x: prob_order.get(x['label'], 0))

            slot_data = {
                'id': slot.id,
                'label': slot.label,
                'response_type': slot.response_type,
                'problem_distribution': prob_dist_list,
                'interactions': interactions_by_slot.get(slot.id, [])
            }

            if slot.response_type == QuizSlot.ResponseType.OPEN_TEXT:
                word_counts = []
                for sa in filtered_slot_attempts:
                    answer_data = sa['answer_data']
                    if answer_data and 'text' in answer_data:
                        text = answer_data['text']
                        count = len(text.split())
                        if count > 0:
                            word_counts.append(count)
                            all_word_counts.append(count)
                
                slot_data['data'] = {
                    'min': min(word_counts) if word_counts else 0,
                    'max': max(word_counts) if word_counts else 0,
                    'mean': sum(word_counts) / len(word_counts) if word_counts else 0,
                    'median': sorted(word_counts)[len(word_counts) // 2] if word_counts else 0,
                    'count': len(word_counts),
                    'raw_values': word_counts
                }
            
            elif slot.response_type == QuizSlot.ResponseType.RATING:
                # Per-criterion distribution
                criteria_stats = []
                
                for criterion in criteria:
                    c_id = criterion['id']
                    c_name = criterion['name']
                    
                    # Initialize counts for each scale value
                    counts = {val: 0 for val in scale_values}
                    total_responses = 0
                    
                    for sa in filtered_slot_attempts:
                        answer_data = sa['answer_data']
                        if answer_data and 'ratings' in answer_data:
                            ratings = answer_data['ratings']
                            if c_id in ratings:
                                val = ratings[c_id]
                                if val in counts:
                                    counts[val] += 1
                                    total_responses += 1
                    
                    # Format for chart
                    dist_data = []
                    for val in scale_values:
                        count = counts[val]
                        percentage = (count / total_responses * 100) if total_responses > 0 else 0
                        # Find label for value
                        label = next((s['label'] for s in scale if s['value'] == val), str(val))
                        dist_data.append({
                            'value': val,
                            'label': label,
                            'count': count,
                            'percentage': percentage
                        })
                    
                    criteria_stats.append({
                        'criterion_id': c_id,
                        'name': c_name,
                        'distribution': dist_data,
                        'total': total_responses
                    })
                
                # Format group stats
                grouped_charts_data = []
                sorted_group_names = sorted(group_stats.keys())
                for group_name in sorted_group_names:
                    g_counts = group_stats[group_name]
                    g_criteria_data = []
                    for criterion in criteria:
                        c_id = criterion['id']
                        c_name = criterion['name']
                        c_counts = g_counts.get(c_id, {})
                        
                        dist_data = []
                        total_c = sum(c_counts.values())
                        
                        for s_opt in scale:
                            val = s_opt['value']
                            count = c_counts.get(val, 0)
                            percentage = (count / total_c * 100) if total_c > 0 else 0
                            dist_data.append({
                                'label': s_opt['label'],
                                'value': val,
                                'count': count,
                                'percentage': percentage
                            })
                        g_criteria_data.append({
                            'name': c_name,
                            'distribution': dist_data
                        })
                    grouped_charts_data.append({
                        'group': group_name,
                        'data': {'criteria': g_criteria_data}
                    })

                slot_data['data'] = {
                    'criteria': criteria_stats,
                    'grouped_data': grouped_charts_data
                }

            slots_data.append(slot_data)

        # Get all unique problems used in this quiz for the filter dropdown
        all_problems = Problem.objects.filter(
            slot_links__quiz_slot__quiz=quiz
        ).distinct().order_by('order_in_bank')
        
        available_problems = [
            {'id': p.id, 'label': p.display_label}
            for p in all_problems
        ]
        
        word_count_stats = {
            'min': min(all_word_counts) if all_word_counts else 0,
            'max': max(all_word_counts) if all_word_counts else 0,
            'mean': sum(all_word_counts) / len(all_word_counts) if all_word_counts else 0,
            'median': sorted(all_word_counts)[len(all_word_counts) // 2] if all_word_counts else 0,
        }

        # Calculate average quiz score
        # We need to sum up all grades for each attempt
        # We already fetched grades in 'grades_map' (attempt_slot_id -> grade info)
        # But we need to group by attempt
        
        attempt_scores = {}
        for attempt_slot in all_attempt_slots:
            attempt_id = attempt_slot.get('attempt_id') # We didn't fetch attempt_id explicitly in values() but we can get it
            # Wait, we fetched 'attempt__student_identifier' etc but not 'attempt_id' directly in the values() call?
            # Let's check the values() call again.
            pass
        
        # Calculate score stats
        # We annotate each attempt with its total score, then aggregate min/max/avg
        from django.db.models.functions import Coalesce
        
        score_stats = attempts.annotate(
            score=Coalesce(models.Sum('attempt_slots__grade__items__selected_level__points'), 0.0)
        ).aggregate(
            min_score=models.Min('score'),
            max_score=models.Max('score'),
            avg_score=models.Avg('score')
        )
        
        avg_score = score_stats['avg_score'] or 0
        min_score = score_stats['min_score'] or 0
        max_score = score_stats['max_score'] or 0

        # Calculate Cronbach's Alpha
        cronbach_alpha = None
        try:
            # 1. Identify rating slots and criteria
            rating_slots = [s for s in quiz_slots if s.response_type == QuizSlot.ResponseType.RATING]
            if rating_slots and criteria:
                # Items are (slot_id, criterion_id)
                # We need to map attempt_id -> { (slot_id, c_id): value }
                attempt_ratings = {}
                
                # We need to iterate all_attempt_slots again
                for sa in all_attempt_slots:
                    a_id = sa['attempt_id']
                    if a_id not in attempt_ratings:
                        attempt_ratings[a_id] = {}
                    
                    if sa['answer_data'] and 'ratings' in sa['answer_data']:
                        ratings = sa['answer_data']['ratings']
                        for c_id, val in ratings.items():
                            # Key: slot_id_criterion_id
                            key = f"{sa['slot_id']}_{c_id}"
                            attempt_ratings[a_id][key] = val

                # 2. Build matrix
                # Columns: all combinations of rating_slot.id and criterion.id
                item_keys = []
                for s in rating_slots:
                    for c in criteria:
                        item_keys.append(f"{s.id}_{c['id']}")
                
                K = len(item_keys)
                
                if K > 1:
                    # Rows
                    scores_matrix = []
                    for a_id, ratings in attempt_ratings.items():
                        # Check if complete (listwise deletion)
                        if all(k in ratings for k in item_keys):
                            row = [float(ratings[k]) for k in item_keys]
                            scores_matrix.append(row)
                    
                    N = len(scores_matrix)
                    if N > 1:
                        # 3. Calculate variances
                        item_variances = []
                        for col_idx in range(K):
                            col_values = [row[col_idx] for row in scores_matrix]
                            mean = sum(col_values) / N
                            var = sum((x - mean) ** 2 for x in col_values) / (N - 1) # Sample variance
                            item_variances.append(var)
                        
                        total_scores = [sum(row) for row in scores_matrix]
                        mean_total = sum(total_scores) / N
                        var_total = sum((x - mean_total) ** 2 for x in total_scores) / (N - 1)
                        
                        if var_total > 0:
                            cronbach_alpha = (K / (K - 1)) * (1 - (sum(item_variances) / var_total))
        except Exception as e:
            print(f"Error calculating Cronbach's Alpha: {e}")
            pass

        return Response({
            'avg_score': avg_score,
            'min_score': min_score,
            'max_score': max_score,
            'completion_rate': completion_rate,
            'total_attempts': total_attempts,
            'time_distribution': time_stats,
            'slots': slots_data,
            'interactions': [],
            'available_problems': available_problems,
            'available_problems': available_problems,
            'word_count_stats': word_count_stats,
            'cronbach_alpha': cronbach_alpha
        })
class QuizSlotProblemStudentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id, slot_id, problem_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        slot = get_object_or_404(QuizSlot, id=slot_id, quiz=quiz)
        
        # Fetch attempts that have this problem assigned for this slot
        attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            attempt_slots__slot=slot,
            attempt_slots__assigned_problem_id=problem_id,
            completed_at__isnull=False
        ).select_related('quiz').prefetch_related('attempt_slots')

        students_data = []
        
        for attempt in attempts:
            # Find the specific slot attempt
            # Since we filtered by attempt_slots, we know it exists.
            # But we need to grab the specific one efficiently.
            # We can use the prefetch or just query again if list is small.
            # Let's iterate the prefetched slots.
            target_slot_attempt = None
            for sa in attempt.attempt_slots.all():
                if sa.slot_id == slot.id and sa.assigned_problem_id == problem_id:
                    target_slot_attempt = sa
                    break
            
            if not target_slot_attempt:
                continue

            # Calculate duration
            duration = 0
            if attempt.started_at and attempt.completed_at:
                duration = (attempt.completed_at - attempt.started_at).total_seconds() / 60.0

            # Get grade info
            grade_info = {
                'total_score': 0,
                'items': {}
            }
            try:
                grade = QuizSlotGrade.objects.get(attempt_slot=target_slot_attempt)
                for item in grade.items.all():
                    grade_info['items'][item.rubric_item.id] = item.selected_level.points
                    grade_info['total_score'] += item.selected_level.points
            except QuizSlotGrade.DoesNotExist:
                pass

            # Word count
            word_count = 0
            if target_slot_attempt.answer_data and 'text' in target_slot_attempt.answer_data:
                word_count = len(target_slot_attempt.answer_data['text'].split())

            # Ratings
            ratings = {}
            if target_slot_attempt.answer_data and 'ratings' in target_slot_attempt.answer_data:
                ratings = target_slot_attempt.answer_data['ratings']

            students_data.append({
                'student_identifier': attempt.student_identifier,
                'attempt_id': attempt.id,
                'score': grade_info['total_score'],
                'criteria_scores': grade_info['items'],
                'time_taken': duration,
                'word_count': word_count,
                'ratings': ratings,
            })

        return Response(students_data)
