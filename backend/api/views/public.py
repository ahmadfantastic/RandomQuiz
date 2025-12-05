import random
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot
from quizzes.serializers import QuizAttemptSlotSerializer, QuizAttemptInteractionSerializer, QuizAttemptSerializer
from quizzes.response_config import load_response_config


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
