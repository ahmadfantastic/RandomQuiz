from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import Instructor
from problems.models import ProblemBank, Problem
from io import BytesIO

class ProblemBankTests(APITestCase):
    def setUp(self):
        self.username = 'instructor'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        self.bank_list_url = reverse('problem-bank-list')

    def test_create_bank(self):
        data = {
            'name': 'Math Bank',
            'description': 'Math problems'
        }
        response = self.client.post(self.bank_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProblemBank.objects.count(), 1)
        self.assertEqual(ProblemBank.objects.get().name, 'Math Bank')

    def test_list_banks(self):
        ProblemBank.objects.create(name='Bank 1', owner=self.instructor)
        ProblemBank.objects.create(name='Bank 2', owner=self.instructor)
        
        response = self.client.get(self.bank_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_import_csv(self):
        # Prepare CSV content
        csv_content = b'order,problem\n1,Problem 1\n2,Problem 2'
        file = BytesIO(csv_content)
        file.name = 'problems.csv'
        
        url = reverse('problem-bank-import-from-csv')
        data = {
            'name': 'Imported Bank',
            'file': file
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProblemBank.objects.count(), 1)
        bank = ProblemBank.objects.get()
        self.assertEqual(bank.name, 'Imported Bank')
        self.assertEqual(bank.problems.count(), 2)

class ProblemTests(APITestCase):
    def setUp(self):
        self.username = 'instructor'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        self.bank = ProblemBank.objects.create(name='My Bank', owner=self.instructor)
        self.problem_list_url = reverse('problem-list')

    def test_create_problem(self):
        data = {
            'problem_bank': self.bank.id,
            'statement': 'What is 1+1?',
            'order_in_bank': 1
        }
        response = self.client.post(self.problem_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(Problem.objects.get().statement, 'What is 1+1?')

    def test_update_problem(self):
        problem = Problem.objects.create(problem_bank=self.bank, statement='Old', order_in_bank=1)
        url = reverse('problem-detail', args=[problem.id])
        data = {'statement': 'New', 'problem_bank': self.bank.id}
        
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        problem.refresh_from_db()
        self.assertEqual(problem.statement, 'New')

    def test_delete_problem(self):
        problem = Problem.objects.create(problem_bank=self.bank, statement='Delete me', order_in_bank=1)
        url = reverse('problem-detail', args=[problem.id])
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Problem.objects.count(), 0)
