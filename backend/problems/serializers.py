from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import ProblemBank, Problem


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
