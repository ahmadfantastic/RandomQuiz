import random
from django.contrib.auth import authenticate, login, logout
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Instructor, ensure_instructor
from accounts.permissions import IsAdminInstructor, IsInstructor
from accounts.serializers import InstructorSerializer
from problems.models import ProblemBank, Problem
from problems.serializers import ProblemBankSerializer, ProblemSerializer
from quizzes.models import (
    Quiz,
    QuizSlot,
    QuizSlotProblemBank,
    QuizAttempt,
    QuizAttemptSlot,
)
from quizzes.serializers import (
    QuizSerializer,
    QuizSlotSerializer,
    QuizSlotProblemSerializer,
    QuizAttemptSerializer,
    QuizAttemptSlotSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

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
    def post(self, request):
        logout(request)
        return Response({'detail': 'Logged out'})


class InstructorViewSet(viewsets.ModelViewSet):
    serializer_class = InstructorSerializer
    queryset = Instructor.objects.select_related('user').all()
    permission_classes = [IsAdminInstructor]


class ProblemBankViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemBankSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        instructor = ensure_instructor(self.request.user)
        return ProblemBank.objects.filter(owner=instructor)

    def perform_create(self, serializer):
        serializer.save(owner=ensure_instructor(self.request.user))


class ProblemViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        instructor = ensure_instructor(self.request.user)
        return Problem.objects.filter(problem_bank__owner=instructor)

    def perform_create(self, serializer):
        instructor = ensure_instructor(self.request.user)
        bank_id = self.request.data.get('problem_bank')
        bank = get_object_or_404(ProblemBank, id=bank_id, owner=instructor)
        serializer.save(problem_bank=bank)

    def perform_update(self, serializer):
        instructor = ensure_instructor(self.request.user)
        bank = serializer.validated_data.get('problem_bank')
        if bank and bank.owner != instructor:
            raise PermissionDenied('Cannot move problem to another instructor bank')
        serializer.save()


class ProblemBankProblemListCreate(generics.ListCreateAPIView):
    serializer_class = ProblemSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        instructor = ensure_instructor(self.request.user)
        return Problem.objects.filter(problem_bank_id=self.kwargs['bank_id'], problem_bank__owner=instructor)

    def perform_create(self, serializer):
        instructor = ensure_instructor(self.request.user)
        bank = get_object_or_404(ProblemBank, id=self.kwargs['bank_id'], owner=instructor)
        serializer.save(problem_bank=bank)


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
        serializer = QuizSlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(quiz=quiz)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QuizAllowedInstructorList(APIView):
    permission_classes = [IsInstructor]

    def get_quiz(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        return get_object_or_404(
            Quiz.objects.filter(
                models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)
            ).distinct(),
            id=quiz_id,
        )

    def get(self, request, quiz_id):
        quiz = self.get_quiz(request, quiz_id)
        serializer = InstructorSerializer(quiz.allowed_instructors.all(), many=True)
        return Response(serializer.data)

    def post(self, request, quiz_id):
        quiz = self.get_quiz(request, quiz_id)
        instructor_id = request.data.get('instructor_id')
        instructor = get_object_or_404(Instructor, id=instructor_id)
        quiz.allowed_instructors.add(instructor)
        return Response({'detail': 'Instructor added'})


class QuizAllowedInstructorDelete(APIView):
    permission_classes = [IsInstructor]

    def delete(self, request, quiz_id, instructor_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(
            Quiz.objects.filter(models.Q(owner=instructor) | models.Q(allowed_instructors=instructor)).distinct(),
            id=quiz_id,
        )
        quiz.allowed_instructors.remove(instructor_id)
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
        problem_ids = request.data.get('problem_ids', [])
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
        identifier = request.data.get('student_identifier')
        if not identifier:
            return Response({'detail': 'student_identifier is required'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        if now < quiz.start_time:
            return Response({'detail': 'Quiz not started yet'}, status=status.HTTP_400_BAD_REQUEST)
        if quiz.end_time and now > quiz.end_time:
            return Response({'detail': 'Quiz ended'}, status=status.HTTP_400_BAD_REQUEST)
        attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier=identifier)
        attempt_slots = []
        for slot in quiz.slots.all():
            options = list(slot.slot_problems.select_related('problem').values_list('problem_id', flat=True))
            if not options:
                attempt.delete()
                return Response({'detail': f'Slot {slot.label} has no problems configured'}, status=status.HTTP_400_BAD_REQUEST)
            problem_id = random.choice(options)
            problem = Problem.objects.get(id=problem_id)
            attempt_slot = QuizAttemptSlot.objects.create(
                attempt=attempt,
                slot=slot,
                assigned_problem=problem,
            )
            attempt_slots.append(attempt_slot)
        serializer = QuizAttemptSlotSerializer(attempt_slots, many=True)
        return Response({'attempt_id': attempt.id, 'slots': serializer.data})


class PublicAttemptSlotAnswer(APIView):
    permission_classes = [AllowAny]

    def post(self, request, attempt_id, slot_id):
        attempt_slot = get_object_or_404(QuizAttemptSlot, attempt_id=attempt_id, slot_id=slot_id)
        answer = request.data.get('answer_text', '')
        attempt_slot.answer_text = answer
        attempt_slot.answered_at = timezone.now()
        attempt_slot.save()
        return Response({'detail': 'Answer saved'})


class PublicAttemptComplete(APIView):
    permission_classes = [AllowAny]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, id=attempt_id)
        attempt.completed_at = timezone.now()
        attempt.save()
        serializer = QuizAttemptSerializer(attempt)
        return Response(serializer.data)
