from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import Instructor
from quizzes.models import Quiz, QuizSlot
from problems.models import ProblemBank, Problem
import uuid

class PublicQuizTests(APITestCase):
    def setUp(self):
        self.username = 'instructor'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.instructor = Instructor.objects.create(user=self.user)
        
        self.quiz = Quiz.objects.create(
            title='Public Quiz',
            owner=self.instructor,
            public_id=uuid.uuid4(),
            start_time=timezone.now() - timezone.timedelta(hours=1)
        )
        
        self.bank = ProblemBank.objects.create(name='Bank', owner=self.instructor)
        self.problem = Problem.objects.create(problem_bank=self.bank, statement='Q1', order_in_bank=1)
        self.slot = QuizSlot.objects.create(quiz=self.quiz, label='Slot 1', problem_bank=self.bank, order=1)
        # Need to assign problem to slot via QuizSlotProblemBank if that's how it works, 
        # or if it picks randomly from bank.
        # Checking views.py PublicQuizStart:
        # slots = list(quiz.slots.prefetch_related('slot_problems__problem').all())
        # It seems it uses slot_problems.
        # Let's add the problem to the slot.
        from quizzes.models import QuizSlotProblemBank
        QuizSlotProblemBank.objects.create(quiz_slot=self.slot, problem=self.problem)

        self.detail_url = reverse('public-quiz-detail', args=[self.quiz.public_id])
        self.start_url = reverse('public-quiz-start', args=[self.quiz.public_id])

    def test_get_quiz_detail(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Public Quiz')
        self.assertTrue(response.data['is_open'])

    def test_start_quiz_success(self):
        data = {'student_identifier': 'student1'}
        response = self.client.post(self.start_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('attempt_id', response.data)
        self.assertIn('slots', response.data)

    def test_start_quiz_missing_identifier(self):
        data = {}
        response = self.client.post(self.start_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_quiz_not_started(self):
        self.quiz.start_time = timezone.now() + timezone.timedelta(hours=1)
        self.quiz.save()
        
        data = {'student_identifier': 'student1'}
        response = self.client.post(self.start_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Quiz not started yet')

    def test_resume_attempt(self):
        # Start first time
        data = {'student_identifier': 'student1'}
        response1 = self.client.post(self.start_url, data)
        attempt_id = response1.data['attempt_id']
        
        # Start second time (resume)
        response2 = self.client.post(self.start_url, data)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data['attempt_id'], attempt_id)
