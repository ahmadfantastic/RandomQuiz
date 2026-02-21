from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import (
    ProblemBank,
    Problem,
    InstructorProblemRating,
    InstructorProblemRatingEntry,
    Rubric,
    RubricScaleOption,
    RubricCriterion,
)


class ProblemSerializer(serializers.ModelSerializer):
    display_label = serializers.CharField(read_only=True)
    problem_bank = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Problem
        fields = ['id', 'problem_bank', 'order_in_bank', 'group', 'statement', 'display_label']
        extra_kwargs = {
            'order_in_bank': {'required': False, 'allow_null': True},
            'problem_bank': {'read_only': True},
        }


class ProblemSummarySerializer(serializers.ModelSerializer):
    display_label = serializers.CharField(read_only=True)
    problem_bank = serializers.PrimaryKeyRelatedField(read_only=True)
    rating_status = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = ['id', 'problem_bank', 'order_in_bank', 'group', 'display_label', 'rating_status']

    def get_rating_status(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 'unrated'
        
        try:
            # Efficiently check if rating exists
            # For "completely rated", we'd ideally check entry count vs rubric criteria count.
            # Assuming if InstructorProblemRating exists, it's at least partially rated.
            # To be more precise, we can check if it has entries.
            # But let's start with checking existence of the rating object.
            # AND ideally checking if it matches the number of criteria in the bank's rubric.
            
            # Simple version: Check if rating exists
            # rating_exists = obj.instructor_ratings.filter(instructor__user=request.user).exists()
            # return 'complete' if rating_exists else 'unrated'

            # Better version: Check entries?
            # This might be N+1 if not prefetched.
            # But usually we load one bank's problems, so we could prefetch ratings.
            
            rating = obj.instructor_ratings.filter(instructor__user=request.user).first()
            if not rating:
                return 'unrated'
            
            # If rating exists, check entries count
            rubric = obj.problem_bank.rubric
            if not rubric:
                return 'unrated'
                
            criteria_count = rubric.criteria.count()
            entries_count = rating.entries.count()
            
            if entries_count >= criteria_count and criteria_count > 0:
                return 'complete'
            elif entries_count > 0:
                return 'partial'
            else:
                return 'unrated' # Rating object exists but no entries? Treated as unrated/partial.

        except Exception:
            return 'unrated'


class ProblemBankSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.user.username', read_only=True)
    is_owner = serializers.SerializerMethodField()
    rubric_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    completion_stats = serializers.SerializerMethodField()

    class Meta:
        model = ProblemBank
        fields = ['id', 'name', 'description', 'owner', 'owner_username', 'is_owner', 'rubric_id', 'completion_stats']
        read_only_fields = ['owner']

    def get_completion_stats(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {'rated': 0, 'total': 0, 'status': 'incomplete'}
            
        total = obj.problems.count()
        if total == 0:
            return {'rated': 0, 'total': 0, 'status': 'empty'}

        # Calculate rated count
        # A problem is rated if... logic should match get_rating_status ideally.
        # But for list view efficiency, let's say "has a rating entry" or "has rating object".
        # Checking strictly "complete" for ALL problems is expensive without complex annotations.
        # Let's count how many problems have at least one rating entry from this user?
        # Or just "InstructorProblemRating exists".
        
        # Using "InstructorProblemRating exists" for now for efficiency.
        # FIX: Ensure it has entries so it matches ProblemSummary logic (at least partial).
        rated_count = InstructorProblemRating.objects.filter(
            problem__problem_bank=obj, 
            instructor__user=request.user,
            entries__isnull=False
        ).distinct().count()
        
        status = 'incomplete'
        if rated_count == total:
            status = 'complete'
        elif rated_count > 0:
            status = 'partial'
            
        return {'rated': rated_count, 'total': total, 'status': status}

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        try:
            instructor = user.instructor
        except ObjectDoesNotExist:
            return False
        return bool(instructor and obj.owner_id == instructor.id)

    def create(self, validated_data):
        rubric_id = validated_data.pop('rubric_id', None)
        bank = super().create(validated_data)
        if rubric_id:
            try:
                bank.rubric = Rubric.objects.get(id=rubric_id)
                bank.save()
            except Rubric.DoesNotExist:
                pass
        return bank




class InstructorProblemRatingEntrySerializer(serializers.Serializer):
    criterion_id = serializers.CharField(source='criterion.criterion_id')
    value = serializers.FloatField(source='scale_option.value')


class InstructorProblemRatingSerializer(serializers.ModelSerializer):
    entries = InstructorProblemRatingEntrySerializer(many=True)
    instructor_name = serializers.CharField(source='instructor.user.get_full_name', read_only=True)

    class Meta:
        model = InstructorProblemRating
        fields = ['id', 'problem', 'instructor', 'instructor_name', 'entries', 'created_at', 'updated_at']
        read_only_fields = ['id', 'problem', 'instructor', 'created_at', 'updated_at']

    def create(self, validated_data):
        entries_data = validated_data.pop('entries')
        rating = InstructorProblemRating.objects.create(**validated_data)
        self._save_entries(rating, entries_data)
        return rating

    def update(self, instance, validated_data):
        entries_data = validated_data.pop('entries', None)
        if entries_data is not None:
            instance.entries.all().delete()
            self._save_entries(instance, entries_data)
        return super().update(instance, validated_data)

    def _save_entries(self, rating, entries_data):
        rubric = rating.problem.problem_bank.rubric
        if not rubric:
            raise serializers.ValidationError("Problem bank has no rubric assigned.")

        # Prefetch for performance? Or just get.
        # Given small number of criteria/options, get is fine.
        # But to avoid N queries, we could fetch all options/criteria for the rubric.
        criteria_map = {c.criterion_id: c for c in rubric.criteria.all()}
        options_map = {o.value: o for o in rubric.scale_options.all()}

        new_entries = []
        for entry_data in entries_data:
            # entries_data structure is nested due to 'source' in Serializer
            # e.g. {'criterion': {'criterion_id': '...'}, 'scale_option': {'value': ...}}
            cid = entry_data.get('criterion', {}).get('criterion_id')
            val = entry_data.get('scale_option', {}).get('value')
            
            # Fallback if structure changes (though unlikely with current serializer)
            if cid is None: cid = entry_data.get('criterion_id')
            if val is None: val = entry_data.get('value')
            
            criterion = criteria_map.get(cid)
            scale_option = options_map.get(val)
            
            if not criterion:
                raise serializers.ValidationError(f"Invalid criterion_id: {cid}")
            if not scale_option:
                raise serializers.ValidationError(f"Invalid value: {val}")
            
            new_entries.append(InstructorProblemRatingEntry(
                rating=rating,
                criterion=criterion,
                scale_option=scale_option
            ))
        
        InstructorProblemRatingEntry.objects.bulk_create(new_entries)


class RubricScaleOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubricScaleOption
        fields = ['order', 'value', 'label']

class RubricCriterionSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='criterion_id')
    
    class Meta:
        model = RubricCriterion
        fields = ['order', 'id', 'name', 'description']

class RubricSerializer(serializers.ModelSerializer):
    scale_options = RubricScaleOptionSerializer(many=True)
    criteria = RubricCriterionSerializer(many=True)
    owner_name = serializers.CharField(source='owner.user.get_full_name', read_only=True)

    class Meta:
        model = Rubric
        fields = ['id', 'name', 'description', 'owner', 'owner_name', 'scale_options', 'criteria']
        read_only_fields = ['owner']

    def create(self, validated_data):
        scale_options_data = validated_data.pop('scale_options', [])
        criteria_data = validated_data.pop('criteria', [])
        rubric = Rubric.objects.create(**validated_data)

        for option_data in scale_options_data:
            RubricScaleOption.objects.create(rubric=rubric, **option_data)
        
        for criterion_data in criteria_data:
            criterion_id = criterion_data.pop('criterion_id')
            RubricCriterion.objects.create(rubric=rubric, criterion_id=criterion_id, **criterion_data)
        
        return rubric

    def update(self, instance, validated_data):
        scale_options_data = validated_data.pop('scale_options', None)
        criteria_data = validated_data.pop('criteria', None)
        
        instance = super().update(instance, validated_data)

        if scale_options_data is not None:
            instance.scale_options.all().delete()
            for option_data in scale_options_data:
                RubricScaleOption.objects.create(rubric=instance, **option_data)
        
        if criteria_data is not None:
            instance.criteria.all().delete()
            for criterion_data in criteria_data:
                criterion_id = criterion_data.pop('criterion_id')
                RubricCriterion.objects.create(rubric=instance, criterion_id=criterion_id, **criterion_data)
        
        return instance
