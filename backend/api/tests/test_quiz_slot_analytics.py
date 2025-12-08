from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User, Instructor
from quizzes.models import Quiz, QuizSlot, QuizRatingCriterion, QuizRatingScaleOption

class QuizSlotAnalyticsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        self.quiz = Quiz.objects.create(title="Slot Analytics Quiz", owner=self.instructor)
        from problems.models import ProblemBank
        self.bank = ProblemBank.objects.create(owner=self.instructor, name="Bank")
        self.slot = QuizSlot.objects.create(quiz=self.quiz, order=1, label="Rating Slot", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank)

        # Create Criterion with ID (code)
        self.c1 = QuizRatingCriterion.objects.create(quiz=self.quiz, order=1, criterion_id='ID_C1', name='Criterion 1 Name', instructor_criterion_code='IC1')
        
        # Scale options
        QuizRatingScaleOption.objects.create(quiz=self.quiz, value=1, label="1", mapped_value=1, order=1)
        QuizRatingScaleOption.objects.create(quiz=self.quiz, value=5, label="5", mapped_value=5, order=2)

    def test_slot_analytics_criteria_structure(self):
        url = reverse('quiz-analytics-slot', args=[self.quiz.id, self.slot.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('criteria', response.data['data'])
        
        criteria = response.data['data']['criteria']
        self.assertTrue(len(criteria) > 0)
        
        c1_data = next((c for c in criteria if c['name'] == 'Criterion 1 Name'), None)
        self.assertIsNotNone(c1_data)
        # Verify 'id' field is present and correct
        self.assertIn('id', c1_data)
        self.assertEqual(c1_data['id'], 'ID_C1')
