from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from accounts.models import Instructor
from quizzes.models import Quiz, QuizProjectScore

class GlobalProjectAnalysisTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        # Create Quizzes
        self.quiz1 = Quiz.objects.create(title="Quiz 1", owner=self.instructor)
        self.quiz2 = Quiz.objects.create(title="Quiz 2", owner=self.instructor)
        
        # Create Scores for Quiz 1
        QuizProjectScore.objects.create(quiz=self.quiz1, project_score=80, quiz_score=10, team="Team A")
        QuizProjectScore.objects.create(quiz=self.quiz1, project_score=90, quiz_score=15, team="Team B")
        
        # Create Scores for Quiz 2
        QuizProjectScore.objects.create(quiz=self.quiz2, project_score=70, quiz_score=12, team="Team C")
        QuizProjectScore.objects.create(quiz=self.quiz2, project_score=85, quiz_score=14, team="Team D")

    def test_global_project_analysis_structure(self):
        url = '/api/problem-banks/analysis/global/project-scores/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('quiz_correlations', data)
        self.assertIn('aggregated_quadrants', data)
        
        # Check Quiz Correlations
        correlations = data['quiz_correlations']
        # We have 2 quizzes with data
        self.assertEqual(len(correlations), 2)
        q1_corr = next((c for c in correlations if c['quiz_title'] == "Quiz 1"), None)
        self.assertIsNotNone(q1_corr)
        self.assertEqual(q1_corr['count'], 2)
        # Check R values exist (even if imperfect with n=2)
        
        # Check Aggregated Quadrants
        quads = data['aggregated_quadrants']
        self.assertIn('med_med', quads)
        self.assertIn('masters', quads['med_med'])
        
        # Total count check: 2 students in Quiz 1, 2 in Quiz 2 = 4 total
        total_med = sum(quads['med_med'][k] for k in ['masters', 'implementers', 'conceptualizers', 'strugglers'])
        self.assertEqual(total_med, 4)

    def test_global_project_analysis_empty(self):
        # Create new instructor with no quizzes
        user2 = User.objects.create_user(username='instr2', password='pw')
        Instructor.objects.create(user=user2)
        self.client.force_authenticate(user=user2)
        
        url = '/api/problem-banks/analysis/global/project-scores/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(len(data['quiz_correlations']), 0)
        # Check quad counts are zero
        self.assertEqual(data['aggregated_quadrants']['med_med']['masters'], 0)
