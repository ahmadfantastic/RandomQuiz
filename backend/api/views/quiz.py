from datetime import timedelta
from django.db import models
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from accounts.permissions import IsInstructor
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Instructor, ensure_instructor
from problems.models import ProblemBank, Problem
from quizzes.models import Quiz, QuizSlot, QuizAttempt
from quizzes.serializers import QuizSerializer, QuizSlotSerializer
from accounts.serializers import InstructorSerializer


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
