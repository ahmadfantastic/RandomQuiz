from django.db import models
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
    QuizAttemptInteraction,
    create_default_quiz_rubric,
    GradingRubric,
    GradingRubricItem,
    GradingRubricItemLevel,
    QuizSlotGrade,
    QuizSlotGradeItem,
    QuizProjectScore,
)


class QuizSlotGradeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizSlotGradeItem
        fields = ['id', 'rubric_item', 'selected_level']


class QuizSlotGradeSerializer(serializers.ModelSerializer):
    items = QuizSlotGradeItemSerializer(many=True)
    grader_name = serializers.CharField(source='grader.user.username', read_only=True)

    class Meta:
        model = QuizSlotGrade
        fields = ['id', 'feedback', 'grader', 'grader_name', 'graded_at', 'items']
        read_only_fields = ['grader', 'graded_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        grade = QuizSlotGrade.objects.create(**validated_data)
        for item_data in items_data:
            QuizSlotGradeItem.objects.create(grade=grade, **item_data)
        return grade

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items')
        instance.feedback = validated_data.get('feedback', instance.feedback)
        instance.save()

        # Re-create items
        instance.items.all().delete()
        for item_data in items_data:
            QuizSlotGradeItem.objects.create(grade=instance, **item_data)
        return instance


class GradingRubricItemLevelSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = GradingRubricItemLevel
        fields = ['id', 'order', 'points', 'label', 'description']


class GradingRubricItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    levels = GradingRubricItemLevelSerializer(many=True)

    class Meta:
        model = GradingRubricItem
        fields = ['id', 'order', 'label', 'description', 'levels']


class GradingRubricSerializer(serializers.ModelSerializer):
    items = GradingRubricItemSerializer(many=True)

    class Meta:
        model = GradingRubric
        fields = ['id', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        rubric = GradingRubric.objects.create(**validated_data)
        for item_data in items_data:
            levels_data = item_data.pop('levels')
            item = GradingRubricItem.objects.create(rubric=rubric, **item_data)
            for level_data in levels_data:
                GradingRubricItemLevel.objects.create(rubric_item=item, **level_data)
        return rubric

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        
        existing_items = {item.id: item for item in instance.items.all()}
        
        # 1. Identify IDs present in the payload
        payload_ids = set()
        for item_data in items_data:
            if item_data.get('id'):
                payload_ids.add(item_data.get('id'))
        
        # 2. Delete items not in the payload
        for item_id, item in existing_items.items():
            if item_id not in payload_ids:
                item.delete()
        
        # 3. Temporarily shift orders of remaining items to avoid collisions
        remaining_items = instance.items.all()
        for item in remaining_items:
            item.order += 10000
            item.save()
        
        # Refresh existing_items map since objects might have changed
        existing_items = {item.id: item for item in instance.items.all()}

        # 4. Update or Create Items
        for item_data in items_data:
            item_id = item_data.get('id')
            levels_data = item_data.pop('levels', [])
            
            if item_id and item_id in existing_items:
                # Update existing item
                item = existing_items[item_id]
                for attr, value in item_data.items():
                    setattr(item, attr, value)
                item.save()
            else:
                # Create new item
                item = GradingRubricItem.objects.create(rubric=instance, **item_data)

            # 5. Update or Create Levels for this Item
            self._update_levels(item, levels_data)
        
        return instance

    def _update_levels(self, item, levels_data):
        existing_levels = {level.id: level for level in item.levels.all()}
        
        # 1. Identify IDs present
        payload_ids = set()
        for level_data in levels_data:
            if level_data.get('id'):
                payload_ids.add(level_data.get('id'))
        
        # 2. Delete missing
        for level_id, level in existing_levels.items():
            if level_id not in payload_ids:
                level.delete()
        
        # 3. Shift orders
        remaining_levels = item.levels.all()
        for level in remaining_levels:
            level.order += 10000
            level.save()
            
        existing_levels = {level.id: level for level in item.levels.all()}

        # 4. Update/Create
        for level_data in levels_data:
            level_id = level_data.get('id')
            
            if level_id and level_id in existing_levels:
                # Update existing level
                level = existing_levels[level_id]
                for attr, value in level_data.items():
                    setattr(level, attr, value)
                level.save()
            else:
                # Create new level
                level = GradingRubricItemLevel.objects.create(rubric_item=item, **level_data)


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
        fields = ['id', 'quiz', 'label', 'instruction', 'order', 'problem_bank', 'problem_bank_name', 'response_type', 'slot_problems']
        read_only_fields = ['quiz', 'order']

    def validate_problem_bank(self, value):
        if not value.problems.exists():
            raise serializers.ValidationError('Add at least one problem to this bank before assigning it to a slot.')
        return value

    def create(self, validated_data):
        quiz = validated_data['quiz']
        next_order = (
            QuizSlot.objects.filter(quiz=quiz).aggregate(models.Max('order'))['order__max'] or 0
        ) + 1
        validated_data['order'] = next_order
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'problem_bank' in validated_data:
            new_bank = validated_data.get('problem_bank')
            if instance.problem_bank_id != new_bank.id:
                instance.slot_problems.all().delete()
        return super().update(instance, validated_data)


class QuizSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.user.username', read_only=True)
    allowed_instructors = serializers.PrimaryKeyRelatedField(queryset=Instructor.objects.all(), many=True, required=False)
    slots = QuizSlotSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id',
            'title',
            'description',
            'identity_instruction',
            'owner',
            'owner_username',
            'start_time',
            'end_time',
            'public_id',
            'allowed_instructors',
            'slots',
        ]
        read_only_fields = ['owner']

    def create(self, validated_data):
        allowed_instructors = validated_data.pop('allowed_instructors', [])
        quiz = Quiz.objects.create(**validated_data)
        create_default_quiz_rubric(quiz)
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
    slot_instruction = serializers.CharField(source='slot.instruction', read_only=True)
    problem_statement = serializers.CharField(source='assigned_problem.statement', read_only=True)
    problem_display_label = serializers.CharField(source='assigned_problem.display_label', read_only=True)
    response_type = serializers.CharField(source='slot.response_type', read_only=True)
    grade = QuizSlotGradeSerializer(read_only=True)

    class Meta:
        model = QuizAttemptSlot
        fields = [
            'id',
            'attempt',
            'slot',
            'slot_label',
            'slot_instruction',
            'assigned_problem',
            'problem_statement',
            'problem_display_label',
            'response_type',
            'answer_data',
            'answered_at',
            'grade',
        ]
        read_only_fields = ['attempt', 'slot', 'assigned_problem', 'answered_at', 'grade']


class QuizAttemptSummarySerializer(serializers.ModelSerializer):
    grading_status = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    max_score = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'student_identifier',
            'started_at',
            'completed_at',
            'extra_info',
            'grading_status',
            'score',
            'max_score',
        ]

    def get_grading_status(self, obj):
        # Filter for gradable slots (not rating)
        gradable_slots = [
            s for s in obj.attempt_slots.all() 
            if s.slot.response_type != 'rating'
        ]
        
        if not gradable_slots:
            return {
                'is_fully_graded': False,
                'graded_count': 0,
                'total_count': 0
            }

        graded_count = 0
        for slot in gradable_slots:
            # Check if grade exists and has items
            if hasattr(slot, 'grade') and slot.grade.items.exists():
                graded_count += 1
        
        return {
            'is_fully_graded': graded_count == len(gradable_slots),
            'graded_count': graded_count,
            'total_count': len(gradable_slots)
        }

    def get_score(self, obj):
        total_score = 0
        gradable_slots = [
            s for s in obj.attempt_slots.all() 
            if s.slot.response_type != 'rating'
        ]
        
        for slot in gradable_slots:
            if hasattr(slot, 'grade'):
                for item in slot.grade.items.all():
                    total_score += item.selected_level.points
        return total_score

    def get_max_score(self, obj):
        gradable_slots_count = len([
            s for s in obj.attempt_slots.all() 
            if s.slot.response_type != 'rating'
        ])
        
        if gradable_slots_count == 0:
            return 0

        # Calculate max score per slot from rubric
        try:
            rubric = obj.quiz.grading_rubric
            max_score_per_slot = 0
            for item in rubric.items.all():
                max_points = 0
                for level in item.levels.all():
                    if level.points > max_points:
                        max_points = level.points
                max_score_per_slot += max_points
            
            return max_score_per_slot * gradable_slots_count
        except Exception:
            return 0


class QuizAttemptSerializer(serializers.ModelSerializer):
    attempt_slots = QuizAttemptSlotSerializer(many=True, read_only=True)
    quiz_is_open = serializers.SerializerMethodField()
    quiz = QuizSerializer(read_only=True)
    rubric = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'quiz',
            'student_identifier',
            'started_at',
            'completed_at',
            'extra_info',
            'attempt_slots',
            'quiz_is_open',
            'rubric',
        ]
        read_only_fields = ['quiz', 'student_identifier', 'started_at', 'completed_at']

    def get_quiz_is_open(self, obj):
        return obj.quiz.is_open()

    def get_rubric(self, obj):
        return obj.quiz.get_rubric()


class QuizAttemptInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttemptInteraction
        fields = ['event_type', 'metadata']

    def create(self, validated_data):
        attempt_slot = self.context.get('attempt_slot')
        if attempt_slot is None:
            raise serializers.ValidationError({'detail': 'Unable to associate interaction with a slot.'})
        return QuizAttemptInteraction.objects.create(attempt_slot=attempt_slot, **validated_data)


class QuizProjectScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizProjectScore
        fields = ['id', 'project_score', 'quiz_score', 'team', 'grade_level']

