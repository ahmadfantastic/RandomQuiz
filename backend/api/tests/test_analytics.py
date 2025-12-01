
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from accounts.models import Instructor
from quizzes.models import Quiz, QuizSlot, ProblemBank, Problem, QuizAttempt, QuizAttemptSlot, QuizAttemptInteraction
from django.utils import timezone
from datetime import timedelta

class QuizAnalyticsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        self.quiz = Quiz.objects.create(
            title='Test Quiz',
            owner=self.instructor,
            start_time=timezone.now() - timedelta(hours=1)
        )
        
        self.bank = ProblemBank.objects.create(name='Bank 1', owner=self.instructor)
        self.problem = Problem.objects.create(problem_bank=self.bank, statement='Problem 1', order_in_bank=1)
        
        self.slot = QuizSlot.objects.create(
            quiz=self.quiz,
            label='Slot 1',
            order=1,
            problem_bank=self.bank,
            response_type='open_text'
        )

    def test_analytics_empty(self):
        url = reverse('quiz-analytics', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_attempts'], 0)
        self.assertEqual(response.data['avg_score'], 0)
        self.assertEqual(response.data['min_score'], 0)
        self.assertEqual(response.data['max_score'], 0)

    def test_analytics_data(self):
        # Create a completed attempt
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student_identifier='student1',
            completed_at=timezone.now() - timedelta(minutes=10)
        )
        attempt.started_at = timezone.now() - timedelta(minutes=30)
        attempt.save()
        
        # Create an answer
        QuizAttemptSlot.objects.create(
            attempt=attempt,
            slot=self.slot,
            assigned_problem=self.problem,
            answer_data={'text': 'This is a test answer'},
            answered_at=timezone.now() - timedelta(minutes=20)
        )
        
        # Create an interaction
        QuizAttemptInteraction.objects.create(
            attempt_slot=attempt.attempt_slots.first(),
            event_type='typing',
            created_at=timezone.now() - timedelta(minutes=25)
        )

        url = reverse('quiz-analytics', args=[self.quiz.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_attempts'], 1)
        # self.assertEqual(response.data['completion_rate'], 0) # Placeholder logic returns 0
        self.assertEqual(response.data['time_distribution']['count'], 1)
        
        # Check time stats
        self.assertGreater(response.data['time_distribution']['mean'], 0)
        
        # Check word count stats
        # "This is a test answer" = 5 words
        self.assertEqual(response.data['word_count_stats']['mean'], 5)
        self.assertEqual(response.data['word_count_stats']['median'], 5)
        self.assertEqual(response.data['word_count_stats']['min'], 5)
        self.assertEqual(response.data['word_count_stats']['max'], 5)
        
        # Check slot stats
        slot_data = response.data['slots'][0]
        self.assertEqual(slot_data['id'], self.slot.id)
        self.assertEqual(slot_data['data']['count'], 1)
        self.assertEqual(slot_data['data']['mean'], 5) # "This is a test answer" = 5 words
        
        # Check problem distribution
        self.assertEqual(len(slot_data['problem_distribution']), 1)
        # Should be display_label "Problem 1", not statement "Problem 1" (though they might be same string in this test setup)
        # In setup: Problem.objects.create(..., statement='Problem 1', order_in_bank=1)
        # display_label is "Problem {order_in_bank}" -> "Problem 1"
        self.assertEqual(slot_data['problem_distribution'][0]['label'], 'Problem 1')
        self.assertEqual(slot_data['problem_distribution'][0]['count'], 1)

        # Check interactions (now nested in slot)
        self.assertEqual(len(slot_data['interactions']), 1)
        self.assertEqual(slot_data['interactions'][0]['event_type'], 'typing')
