from django.db import transaction, models
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from accounts.permissions import IsInstructor
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ensure_instructor
from quizzes.models import Quiz, QuizRatingScaleOption, QuizRatingCriterion, GradingRubric
from quizzes.serializers import GradingRubricSerializer


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
