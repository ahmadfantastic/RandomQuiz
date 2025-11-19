from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Instructor
from .models import ProblemBank, Problem

User = get_user_model()

class ProblemModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)

    def test_create_problem_bank(self):
        bank = ProblemBank.objects.create(name='Math Bank', owner=self.instructor)
        self.assertEqual(str(bank), 'Math Bank')
        self.assertEqual(bank.owner, self.instructor)

    def test_create_problem(self):
        bank = ProblemBank.objects.create(name='Math Bank', owner=self.instructor)
        problem = Problem.objects.create(problem_bank=bank, order_in_bank=1, statement='1+1=?')
        self.assertEqual(str(problem), 'Problem 1 (Math Bank)')
        self.assertEqual(problem.display_label, 'Problem 1')

    def test_problem_ordering(self):
        bank = ProblemBank.objects.create(name='Math Bank', owner=self.instructor)
        p1 = Problem.objects.create(problem_bank=bank, order_in_bank=2, statement='Q2')
        p2 = Problem.objects.create(problem_bank=bank, order_in_bank=1, statement='Q1')
        
        problems = list(bank.problems.all())
        self.assertEqual(problems[0], p2)
        self.assertEqual(problems[1], p1)
