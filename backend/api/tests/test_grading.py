from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Instructor
from problems.models import ProblemBank, Problem
from quizzes.models import Quiz, GradingRubric, GradingRubricItem, GradingRubricItemLevel, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizSlotGrade


class GradingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.quiz = Quiz.objects.create(title='Test Quiz', owner=self.instructor)
        
        # Setup Rubric
        self.rubric = GradingRubric.objects.create(quiz=self.quiz)
        self.rubric_item = GradingRubricItem.objects.create(rubric=self.rubric, order=0, label='Accuracy')
        self.level = GradingRubricItemLevel.objects.create(rubric_item=self.rubric_item, order=0, points=10, label='Good')

        # Setup Attempt
        self.bank = ProblemBank.objects.create(name='Test Bank', owner=self.instructor)
        self.problem = Problem.objects.create(problem_bank=self.bank, order_in_bank=0, statement='Test Problem')
        self.slot = QuizSlot.objects.create(quiz=self.quiz, order=0, label='Q1', problem_bank=self.bank)
        self.attempt = QuizAttempt.objects.create(quiz=self.quiz, student_identifier='student1')
        self.attempt_slot = QuizAttemptSlot.objects.create(attempt=self.attempt, slot=self.slot, assigned_problem=self.problem)

        self.url = reverse('quiz-slot-grade', args=[self.quiz.id, self.attempt.id, self.slot.id])

    def test_grade_slot(self):
        data = {
            'feedback': 'Good job',
            'items': [
                {
                    'rubric_item': self.rubric_item.id,
                    'selected_level': self.level.id
                }
            ]
        }
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify DB
        grade = QuizSlotGrade.objects.get(attempt_slot=self.attempt_slot)
        self.assertEqual(grade.feedback, 'Good job')
        self.assertEqual(grade.items.count(), 1)
        self.assertEqual(grade.items.first().selected_level, self.level)

    def test_update_grade(self):
        # Create initial grade
        data = {
            'feedback': 'Initial',
            'items': []
        }
        self.client.put(self.url, data, format='json')

        # Update
        data['feedback'] = 'Updated'
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        grade = QuizSlotGrade.objects.get(attempt_slot=self.attempt_slot)
        self.assertEqual(grade.feedback, 'Updated')
