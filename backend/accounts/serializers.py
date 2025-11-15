from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Instructor


class InstructorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    email = serializers.EmailField(source='user.email', allow_blank=True, required=False)
    password = serializers.CharField(write_only=True, source='user.password', required=False)

    class Meta:
        model = Instructor
        fields = ['id', 'username', 'email', 'is_admin_instructor', 'password']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        password = user_data.pop('password', None)
        UserModel = get_user_model()
        user = UserModel.objects.create(**user_data)
        if password:
            user.set_password(password)
            user.save()
        instructor = Instructor.objects.create(user=user, **validated_data)
        return instructor

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            if attr == 'password' and value:
                instance.user.set_password(value)
            elif attr in ['username', 'email']:
                setattr(instance.user, attr, value)
        instance.user.save()
        return super().update(instance, validated_data)
