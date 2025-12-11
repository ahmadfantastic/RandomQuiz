from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from accounts.models import Instructor
from quizzes.models import Quiz, QuizSlot, ProblemBank, Problem, QuizAttempt, QuizAttemptSlot, QuizAttemptInteraction
from django.utils import timezone
from datetime import timedelta
import csv
import io

class QuizAnalyticsCSVTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        self.quiz = Quiz.objects.create(
            title='Test Quiz',
            owner=self.instructor
        )
        
        self.bank = ProblemBank.objects.create(name='Test Bank', owner=self.instructor)
        self.problem = Problem.objects.create(
            problem_bank=self.bank,
            statement='Problem 1',
            order_in_bank=1
        )
        
        self.slot = QuizSlot.objects.create(
            quiz=self.quiz,
            label='Slot 1',
            order=1,
            problem_bank=self.bank,
            response_type='open_text'
        )

        # Create a completed attempt
        self.attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student_identifier='student1',
            completed_at=timezone.now()
        )
        self.attempt.started_at = timezone.now() - timedelta(minutes=30)
        self.attempt.save()
        
        self.attempt_slot = QuizAttemptSlot.objects.create(
            attempt=self.attempt,
            slot=self.slot,
            assigned_problem=self.problem
        )
        
        # Create an interaction
        self.interaction = QuizAttemptInteraction.objects.create(
            attempt_slot=self.attempt_slot,
            event_type='typing',
            created_at=timezone.now() - timedelta(minutes=15),
            metadata={'key': 'value'}
        )

    def test_interaction_csv_export(self):
        url = reverse('quiz-analytics-interactions', args=[self.quiz.id])
        response = self.client.get(url, {'download': 'csv'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue('attachment; filename="Test Quiz_interactions.csv"' in response['Content-Disposition'])
        
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)
        
        # Check header
        section_header = rows[0]
        self.assertIn('Student ID', section_header)
        self.assertIn('Slot', section_header)
        self.assertIn('Event Type', section_header)
        self.assertIn('Timestamp', section_header)
        
        # Check data
        data_row = rows[1]
        self.assertEqual(data_row[0], 'student1')
        self.assertEqual(data_row[1], 'Slot 1')
        self.assertEqual(data_row[2], 'typing')
        self.assertIn("{'key': 'value'}", data_row[5])  # Metadata

    def test_interaction_json_response(self):
        # Verify normal JSON response still works
        url = reverse('quiz-analytics-interactions', args=[self.quiz.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.slot.id)
        self.assertEqual(len(response.data[0]['interactions']), 1)
