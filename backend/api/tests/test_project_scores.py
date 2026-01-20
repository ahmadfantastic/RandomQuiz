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
        self.assertIn('team_variance', response.data)
        self.assertIn('global_stats', response.data)
        self.assertIn('raw_scores', response.data)
        
        self.assertEqual(len(response.data['raw_scores']), 1)
        self.assertEqual(response.data['raw_scores'][0]['project_score'], 10)
        
        # Check correlation analysis data
        analysis = response.data['score_correlation'][0]
        self.assertEqual(analysis['count'], 1)
        self.assertEqual(analysis['points'][0]['x'], 20)
        self.assertEqual(analysis['points'][0]['y'], 10)

    def test_team_variance_structure(self):
        # Create scores for two teams
        QuizProjectScore.objects.create(quiz=self.quiz, project_score=90, quiz_score=80, team="Team A")
        QuizProjectScore.objects.create(quiz=self.quiz, project_score=90, quiz_score=70, team="Team A")
        QuizProjectScore.objects.create(quiz=self.quiz, project_score=80, quiz_score=60, team="Team B")
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        team_variance = response.data['team_variance']
        self.assertEqual(len(team_variance), 2)
        
        # Sorted by project score (80 then 90)
        self.assertEqual(team_variance[0]['team'], "Team B")
        self.assertEqual(team_variance[1]['team'], "Team A")
        
        # Check Team A scores
        team_a = team_variance[1]
        self.assertEqual(len(team_a['quiz_scores']), 2)
        self.assertIn(80.0, team_a['quiz_scores'])
        self.assertIn(70.0, team_a['quiz_scores'])
        self.assertIn('project_scores_list', team_a)
        self.assertEqual(len(team_a['project_scores_list']), 2)
        self.assertEqual(team_a['project_scores_list'][0], 90.0)
        
        # Check Per-Team Stats
        self.assertEqual(team_a['project_mean'], 90.0)
        self.assertEqual(team_a['project_variance'], 0.0)
        self.assertEqual(team_a['quiz_mean'], 75.0) # (80+70)/2
        self.assertEqual(team_a['quiz_variance'], 50.0) # Variance of [80, 70] is 50.0
        
        # Check Global Stats
        stats = response.data['global_stats']
        self.assertIsNotNone(stats['project_mean'])
        self.assertIsNotNone(stats['project_variance'])
        
        # 2x 90, 1x 80 -> Mean ~ 86.67
        # 80, 70, 60 -> Mean 70, Variance 100
        self.assertEqual(stats['quiz_mean'], 70.0)
        self.assertEqual(stats['quiz_variance'], 100.0)

        # Check Quadrants Config
        quadrants = response.data.get('quadrants_config')
        self.assertIsNotNone(quadrants)
        # Project scores: 90, 90, 80 -> Median 90. Max 90 -> 95% = 85.5
        # Project scores: 90, 90, 80 -> Median 90. Max 90 -> 95% = 85.5
        self.assertEqual(quadrants['project_median'], 90.0)
        self.assertEqual(quadrants['project_thresh_val'], 85.5)
        self.assertEqual(quadrants['project_threshold_ratio'], 0.95)
        # Quiz scores: 80, 70, 60 -> Median 70.
        self.assertEqual(quadrants['quiz_median'], 70.0)
        # Max possible is 25 because default rubric is created (5 criteria * 5 max scale)
        self.assertEqual(quadrants['quiz_max_possible'], 25)

    def test_quadrant_rubric_calculation(self):
        # Create explicit Grading Rubric
        from quizzes.models import GradingRubric, GradingRubricItem, GradingRubricItemLevel
        
        # Override default rubric if present? 
        # Actually default rubric creates scale options/criteria, not GradingRubric model.
        # GradingRubric is separate OneToOne.
        
        rubric = GradingRubric.objects.create(quiz=self.quiz)
        
        # Item 1: Max 10 pts
        item1 = GradingRubricItem.objects.create(rubric=rubric, order=1, label="I1")
        GradingRubricItemLevel.objects.create(rubric_item=item1, order=1, points=5, label="L1")
        GradingRubricItemLevel.objects.create(rubric_item=item1, order=2, points=10, label="L2")
        
        # Item 2: Max 5 pts
        item2 = GradingRubricItem.objects.create(rubric=rubric, order=2, label="I2")
        GradingRubricItemLevel.objects.create(rubric_item=item2, order=1, points=5, label="L1")
        
        # Total should be 10 + 5 = 15
        
        # Make a request
        # Need some scores to trigger calculation?
        QuizProjectScore.objects.create(quiz=self.quiz, project_score=50, quiz_score=10)
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        quadrants = response.data.get('quadrants_config')
        self.assertIsNotNone(quadrants)
        self.assertEqual(quadrants['quiz_max_possible'], 15.0)
        self.assertEqual(quadrants['quiz_max_50'], 7.5)
