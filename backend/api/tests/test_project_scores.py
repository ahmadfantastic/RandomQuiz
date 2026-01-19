from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User, Instructor
from quizzes.models import Quiz, QuizProjectScore

class ProjectScoreTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        
        self.quiz = Quiz.objects.create(
            title='Test Quiz',
            owner=self.instructor
        )
        
        self.client.force_authenticate(user=self.user)
        self.url = reverse('quiz-project-scores', args=[self.quiz.id])

    def test_upload_csv_scores(self):
        csv_content = (
            "Project Score,Quiz Score,Team,Grade\n"
            "95,80,Team A,A\n"
            "85,70,Team B,B\n"
        )
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("scores.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(self.url, {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(QuizProjectScore.objects.count(), 2)
        
        score1 = QuizProjectScore.objects.get(project_score=95)
        self.assertEqual(score1.quiz_score, 80)
        self.assertEqual(score1.team, 'Team A')
        
        score2 = QuizProjectScore.objects.get(project_score=85)
        self.assertEqual(score2.quiz_score, 70)

    def test_upload_csv_scores_case_insensitive(self):
        csv_content = (
            "project SCORe, qUIZ score\n"
            "100,90\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("scores.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(self.url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(QuizProjectScore.objects.count(), 1)
        self.assertEqual(QuizProjectScore.objects.first().project_score, 100)

    def test_get_scores(self):
        QuizProjectScore.objects.create(quiz=self.quiz, project_score=10, quiz_score=20)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check new structure
        self.assertIn('score_correlation', response.data)
        self.assertIn('raw_scores', response.data)
        
        self.assertEqual(len(response.data['raw_scores']), 1)
        self.assertEqual(response.data['raw_scores'][0]['project_score'], 10)
        
        # Check correlation analysis data
        analysis = response.data['score_correlation'][0]
        self.assertEqual(analysis['count'], 1)
        self.assertEqual(analysis['points'][0]['x'], 20)
        self.assertEqual(analysis['points'][0]['y'], 10)
