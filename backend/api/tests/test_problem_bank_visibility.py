from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from accounts.models import Instructor
from problems.models import ProblemBank, Problem, Rubric, RubricCriterion, RubricScaleOption

class ProblemBankVisibilityTests(APITestCase):
    def setUp(self):
        # Create Instructor A (Owner)
        self.user_a = User.objects.create_user(username='instructor_a', password='password')
        self.instructor_a = Instructor.objects.create(user=self.user_a)
        
        # Create Instructor B (Viewer/Rater)
        self.user_b = User.objects.create_user(username='instructor_b', password='password')
        self.instructor_b = Instructor.objects.create(user=self.user_b)
        
        # Create Rubric
        self.rubric = Rubric.objects.create(name="Test Rubric", owner=self.instructor_a)
        
        # Create a Problem Bank for A
        self.bank = ProblemBank.objects.create(
            name="Instructor A's Bank",
            owner=self.instructor_a,
            rubric=self.rubric
        )
        
        # Create a problem in the bank
        self.problem = Problem.objects.create(
            problem_bank=self.bank,
            statement="Test Problem",
            order_in_bank=1
        )
        
        self.list_url = reverse('problem-bank-list')
        self.rating_url = reverse('problem-rate', kwargs={'problem_id': self.problem.id})

    def test_non_owner_can_see_problem_bank(self):
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should see the bank
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.bank.id)

    def test_non_owner_can_rate_problem(self):
        self.client.force_authenticate(user=self.user_b)
        
        # Rate the problem
        data = {
            'entries': [] # Empty entries is fine for testing access
        }
        response = self.client.put(self.rating_url, data, format='json')
        
        if response.status_code == status.HTTP_403_FORBIDDEN:
             self.fail("Non-owner could not rate problem")
             
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_owner_can_import_ratings(self):
        self.client.force_authenticate(user=self.user_b)
        import_url = reverse('bank-import-ratings', kwargs={'bank_id': self.bank.id})
        
        # Create a simple CSV content
        csv_content = "Problem,Criterion 1\n1,5"
        
        # Create a mock file
        from django.core.files.uploadedfile import SimpleUploadedFile
        file_obj = SimpleUploadedFile("ratings.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        data = {
            'file': file_obj
        }
        
        response = self.client.post(import_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

