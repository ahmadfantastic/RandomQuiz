from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import (
    ProblemBank,
    Problem,
    ProblemBankRatingScaleOption,
    ProblemBankRatingCriterion,
    InstructorProblemRating,
    InstructorProblemRatingEntry,
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

    class Meta:
        model = Problem
        fields = ['id', 'problem_bank', 'order_in_bank', 'group', 'display_label']


class ProblemBankSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.user.username', read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = ProblemBank
        fields = ['id', 'name', 'description', 'owner', 'owner_username', 'is_owner']
        read_only_fields = ['owner']

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


class ProblemBankRatingScaleOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProblemBankRatingScaleOption
        fields = ['order', 'value', 'label']


class ProblemBankRatingCriterionSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='criterion_id')

    class Meta:
        model = ProblemBankRatingCriterion
        fields = ['order', 'id', 'name', 'description']


class InstructorProblemRatingEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorProblemRatingEntry
        fields = ['criterion_id', 'value']


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
        for entry_data in entries_data:
            InstructorProblemRatingEntry.objects.create(rating=rating, **entry_data)
        return rating

    def update(self, instance, validated_data):
        entries_data = validated_data.pop('entries', None)
        if entries_data is not None:
            instance.entries.all().delete()
            for entry_data in entries_data:
                InstructorProblemRatingEntry.objects.create(rating=instance, **entry_data)
        return super().update(instance, validated_data)
