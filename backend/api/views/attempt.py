from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from accounts.permissions import IsInstructor
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ensure_instructor
from problems.models import Problem
from quizzes.models import Quiz, QuizSlot, QuizSlotProblemBank, QuizAttempt, QuizAttemptSlot
from quizzes.serializers import QuizAttemptSummarySerializer, QuizAttemptSerializer, QuizSlotProblemSerializer


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
                'attempt_slots__grade__items',
                'quiz__rating_scale_options',
                'quiz__rating_criteria',
                'quiz__grading_rubric__items__levels',
            )
            .order_by('-started_at')
        )
        serializer = QuizAttemptSummarySerializer(attempts, many=True)
        return Response(serializer.data)


class QuizAttemptDetail(APIView):
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
        serializer = QuizAttemptSerializer(attempt)
        return Response(serializer.data)

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
