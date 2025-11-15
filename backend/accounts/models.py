from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


class Instructor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_admin_instructor = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.user.get_username()

    @property
    def username(self) -> str:
        return self.user.get_username()


User = get_user_model()


def ensure_instructor(user: User) -> 'Instructor':
    instructor, _ = Instructor.objects.get_or_create(user=user)
    return instructor
