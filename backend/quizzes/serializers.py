from rest_framework import serializers

from accounts.models import Instructor
from problems.serializers import ProblemSerializer
from problems.models import ProblemBank, Problem
from .models import (
    Quiz,
    QuizSlot,
    QuizSlotProblemBank,
    QuizAttempt,
    QuizAttemptSlot,
)


class QuizSlotProblemSerializer(serializers.ModelSerializer):
    problem_statement = serializers.CharField(source='problem.statement', read_only=True)
    display_label = serializers.CharField(source='problem.display_label', read_only=True)

    class Meta:
        model = QuizSlotProblemBank
        fields = ['id', 'quiz_slot', 'problem', 'problem_statement', 'display_label']
        read_only_fields = ['quiz_slot']


class QuizSlotSerializer(serializers.ModelSerializer):
    slot_problems = QuizSlotProblemSerializer(many=True, read_only=True)
    problem_bank_name = serializers.CharField(source='problem_bank.name', read_only=True)

    class Meta:
        model = QuizSlot
        fields = ['id', 'quiz', 'label', 'order', 'problem_bank', 'problem_bank_name', 'slot_problems']
        read_only_fields = ['quiz']


class QuizSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.user.username', read_only=True)
    allowed_instructors = serializers.PrimaryKeyRelatedField(queryset=Instructor.objects.all(), many=True, required=False)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'owner', 'owner_username', 'start_time', 'end_time', 'public_id', 'allowed_instructors']
        read_only_fields = ['owner']

    def create(self, validated_data):
        allowed_instructors = validated_data.pop('allowed_instructors', [])
        quiz = Quiz.objects.create(**validated_data)
        if allowed_instructors:
            quiz.allowed_instructors.set(allowed_instructors)
        return quiz

    def update(self, instance, validated_data):
        allowed_instructors = validated_data.pop('allowed_instructors', None)
        quiz = super().update(instance, validated_data)
        if allowed_instructors is not None:
            quiz.allowed_instructors.set(allowed_instructors)
        return quiz


class QuizAttemptSlotSerializer(serializers.ModelSerializer):
    slot_label = serializers.CharField(source='slot.label', read_only=True)
    problem_statement = serializers.CharField(source='assigned_problem.statement', read_only=True)
    problem_display_label = serializers.CharField(source='assigned_problem.display_label', read_only=True)

    class Meta:
        model = QuizAttemptSlot
        fields = ['id', 'attempt', 'slot', 'slot_label', 'assigned_problem', 'problem_statement', 'problem_display_label', 'answer_text', 'answered_at']
        read_only_fields = ['attempt', 'slot', 'assigned_problem', 'answered_at']


class QuizAttemptSerializer(serializers.ModelSerializer):
    attempt_slots = QuizAttemptSlotSerializer(many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'student_identifier', 'started_at', 'completed_at', 'extra_info', 'attempt_slots']
        read_only_fields = ['quiz', 'student_identifier', 'started_at', 'completed_at']
