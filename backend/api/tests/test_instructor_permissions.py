from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from accounts.models import Instructor

User = get_user_model()

class InstructorPermissionTests(APITestCase):
    def setUp(self):
        # Create non-admin instructor
        self.user_non_admin = User.objects.create_user(username='nonadmin', password='password')
        self.instructor_non_admin = Instructor.objects.create(user=self.user_non_admin, is_admin_instructor=False)

        # Create admin instructor
        self.user_admin = User.objects.create_user(username='admin_inst', password='password')
        self.instructor_admin = Instructor.objects.create(user=self.user_admin, is_admin_instructor=True)

        # Create superuser (just in case)
        self.superuser = User.objects.create_superuser(username='super', password='password')
        
        self.list_url = '/api/instructors/'

    def test_non_admin_cannot_list_instructors(self):
        self.client.force_authenticate(user=self.user_non_admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_instructors(self):
        self.client.force_authenticate(user=self.user_admin)
        response = self.client.get(self.list_url)
        # Assuming list returns 200 and a list
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) >= 2) # check we got data

    def test_non_admin_cannot_create_instructor(self):
        self.client.force_authenticate(user=self.user_non_admin)
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123',
            'is_admin_instructor': False
        }
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_instructor(self):
        self.client.force_authenticate(user=self.user_admin)
        data = {
            'username': 'newuser_admin_created',
            'email': 'new2@example.com',
            'password': 'password123',
            'is_admin_instructor': False
        }
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_me_access_allowed_for_all(self):
        # Non-admin
        self.client.force_authenticate(user=self.user_non_admin)
        response = self.client.get(f'{self.list_url}me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'nonadmin')

        # Admin
        self.client.force_authenticate(user=self.user_admin)
        response = self.client.get(f'{self.list_url}me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'admin_inst')
