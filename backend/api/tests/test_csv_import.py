from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, Instructor
from problems.models import ProblemBank, Problem

class ProblemBankRatingImportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.bank = ProblemBank.objects.create(owner=self.instructor, name="Test Bank")
        self.problem = Problem.objects.create(problem_bank=self.bank, order_in_bank=1, statement="Test")
        self.url = reverse('bank-import-ratings', args=[self.bank.id])

    def test_import_csv_normal(self):
        content = b"Problem,Criterion1\n1,5"
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("ratings.csv", content, content_type="text/csv")
        response = self.client.post(self.url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_import_csv_with_bom(self):
        content = b"\xef\xbb\xbfProblem,Criterion1\n1,5"
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("ratings_bom.csv", content, content_type="text/csv")
        response = self.client.post(self.url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_import_csv_with_whitespace(self):
        content = b" Problem , Criterion1 \n1,5"
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("ratings_whitespace.csv", content, content_type="text/csv")
        response = self.client.post(self.url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_preview_csv(self):
        content = b"Problem,Criterion1\n1,5\n1,4"
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("ratings_preview.csv", content, content_type="text/csv")
        response = self.client.post(self.url, {'file': file, 'preview': 'true'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['preview'])
        self.assertEqual(len(response.data['rows']), 2)
        self.assertEqual(response.data['headers'], ['Problem', 'Criterion1'])

    def test_case_insensitive_header(self):
        content = b"problem,Criterion1\n1,5"
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("ratings_lower.csv", content, content_type="text/csv")
        response = self.client.post(self.url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_single_column_csv(self):
        content = b"Problem\n1"
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("ratings_single.csv", content, content_type="text/csv")
        response = self.client.post(self.url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


