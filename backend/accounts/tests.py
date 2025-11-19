from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Instructor, ensure_instructor

User = get_user_model()

class InstructorModelTests(TestCase):
    def test_create_instructor(self):
        user = User.objects.create_user(username='testuser', password='password')
        instructor = Instructor.objects.create(user=user)
        self.assertEqual(instructor.user, user)
        self.assertEqual(str(instructor), 'testuser')
        self.assertEqual(instructor.username, 'testuser')
        self.assertEqual(instructor.display_name, 'testuser')

    def test_display_name_with_names(self):
        user = User.objects.create_user(username='nameduser', password='password', first_name='John', last_name='Doe')
        instructor = Instructor.objects.create(user=user)
        self.assertEqual(instructor.display_name, 'John Doe')

    def test_ensure_instructor_creates_new(self):
        user = User.objects.create_user(username='newuser', password='password')
        instructor = ensure_instructor(user)
        self.assertTrue(Instructor.objects.filter(user=user).exists())
        self.assertEqual(instructor.user, user)

    def test_ensure_instructor_returns_existing(self):
        user = User.objects.create_user(username='existinguser', password='password')
        existing_instructor = Instructor.objects.create(user=user)
        instructor = ensure_instructor(user)
        self.assertEqual(instructor, existing_instructor)
        self.assertEqual(Instructor.objects.filter(user=user).count(), 1)
