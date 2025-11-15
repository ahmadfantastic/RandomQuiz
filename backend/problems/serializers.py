from rest_framework import serializers

from .models import ProblemBank, Problem


class ProblemSerializer(serializers.ModelSerializer):
    display_label = serializers.CharField(source='display_label', read_only=True)

    class Meta:
        model = Problem
        fields = ['id', 'problem_bank', 'order_in_bank', 'statement', 'display_label']


class ProblemBankSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.user.username', read_only=True)

    class Meta:
        model = ProblemBank
        fields = ['id', 'name', 'description', 'owner', 'owner_username']
        read_only_fields = ['owner']
