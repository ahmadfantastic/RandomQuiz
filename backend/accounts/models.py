import os
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


def instructor_profile_picture_upload_to(instance, filename):
    base, extension = os.path.splitext(filename or '')
    safe_extension = extension.lower() if extension else ''
    name = uuid.uuid4().hex
    return f'profile_pictures/{instance.user_id}_{name}{safe_extension}'


class Instructor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_admin_instructor = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to=instructor_profile_picture_upload_to, blank=True, null=True)

    def __str__(self) -> str:
        return self.user.get_username()

    @property
    def username(self) -> str:
        return self.user.get_username()

    @property
    def display_name(self) -> str:
        first_name = self.user.first_name or ''
        last_name = self.user.last_name or ''
        name = f"{first_name} {last_name}".strip()
        return name or self.username


User = get_user_model()


def ensure_instructor(user: User) -> 'Instructor':
    instructor, _ = Instructor.objects.get_or_create(user=user)
    return instructor
