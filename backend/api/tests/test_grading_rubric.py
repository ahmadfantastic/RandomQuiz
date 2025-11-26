from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Instructor
from quizzes.models import Quiz, GradingRubric, GradingRubricItem, GradingRubricItemLevel


class GradingRubricTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.quiz = Quiz.objects.create(title='Test Quiz', owner=self.instructor)
        self.url = reverse('quiz-grading-rubric', args=[self.quiz.id])

    def test_get_empty_rubric(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'items': []})

    def test_create_rubric(self):
        data = {
            'items': [
                {
                    'order': 0,
                    'label': 'Accuracy',
                    'description': 'How accurate the answer is',
                    'levels': [
                        {
                            'order': 0,
                            'points': 0,
                            'label': 'Incorrect',
                            'description': 'Completely wrong'
                        },
                        {
                            'order': 1,
                            'points': 5,
                            'label': 'Correct',
                            'description': 'Perfect'
                        }
                    ]
                }
            ]
        }
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['label'], 'Accuracy')
        self.assertEqual(len(response.data['items'][0]['levels']), 2)

        # Verify DB
        rubric = GradingRubric.objects.get(quiz=self.quiz)
        self.assertEqual(rubric.items.count(), 1)
        item = rubric.items.first()
        self.assertEqual(item.label, 'Accuracy')
        self.assertEqual(item.levels.count(), 2)

    def test_update_rubric(self):
        # Create initial rubric
        rubric = GradingRubric.objects.create(quiz=self.quiz)
        item = GradingRubricItem.objects.create(rubric=rubric, order=0, label='Old Item')
        GradingRubricItemLevel.objects.create(rubric_item=item, order=0, points=10, label='Level 1')

        # Update with new data
        data = {
            'items': [
                {
                    'order': 0,
                    'label': 'New Item',
                    'description': 'New Description',
                    'levels': [
                        {
                            'order': 0,
                            'points': 5,
                            'label': 'New Level',
                            'description': 'New Level Desc'
                        }
                    ]
                }
            ]
        }
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['items'][0]['label'], 'New Item')

        # Verify DB updated
        rubric.refresh_from_db()
        self.assertEqual(rubric.items.count(), 1)
        self.assertEqual(rubric.items.first().label, 'New Item')
