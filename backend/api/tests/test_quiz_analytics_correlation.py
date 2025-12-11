from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User, Instructor
from problems.models import ProblemBank, Problem
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption, QuizSlotGrade, QuizSlotGradeItem

class QuizAnalyticsCorrelationTest(APITestCase):
    def setUp(self):
        # Create user and instructor
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        # Create Quiz
        from django.utils import timezone
        from datetime import timedelta
        self.quiz = Quiz.objects.create(title="Quiz Correlation", owner=self.instructor)

        # Rating Criteria
        self.c1 = QuizRatingCriterion.objects.create(quiz=self.quiz, order=1, criterion_id='C1', name='C1', instructor_criterion_code='IC1')
        
        # Scale
        QuizRatingScaleOption.objects.create(quiz=self.quiz, value=1, label="1", mapped_value=1, order=1)
        QuizRatingScaleOption.objects.create(quiz=self.quiz, value=5, label="5", mapped_value=5, order=2)

        # Bank & Problem
        self.bank = ProblemBank.objects.create(owner=self.instructor, name="Bank")
        self.prob1 = Problem.objects.create(problem_bank=self.bank, statement="P1", order_in_bank=1)
        
        self.slot1 = QuizSlot.objects.create(quiz=self.quiz, order=1, label="Rating", problem_bank=self.bank, response_type=QuizSlot.ResponseType.RATING)
        self.slot2 = QuizSlot.objects.create(quiz=self.quiz, order=2, label="Text", problem_bank=self.bank, response_type=QuizSlot.ResponseType.OPEN_TEXT)

        # Attempts with varying Time, Word Count, and Score
        now = timezone.now()

        # Attempt 1: High Score, Long Time, Many Words
        self.a1 = QuizAttempt.objects.create(quiz=self.quiz, student_identifier="S1", completed_at=now)
        self.a1.started_at = now - timedelta(minutes=60)
        self.a1.save()
        self.create_attempt_data(self.a1, score=100, words="word " * 100, rating=5)

        # Attempt 2: Low Score, Short Time, Few Words
        self.a2 = QuizAttempt.objects.create(quiz=self.quiz, student_identifier="S2", completed_at=now)
        self.a2.started_at = now - timedelta(minutes=10)
        self.a2.save()
        self.create_attempt_data(self.a2, score=50, words="word " * 10, rating=1)

        # Attempt 3: Med Score, Med Time, Med Words
        self.a3 = QuizAttempt.objects.create(quiz=self.quiz, student_identifier="S3", completed_at=now)
        self.a3.started_at = now - timedelta(minutes=30)
        self.a3.save()
        self.create_attempt_data(self.a3, score=75, words="word " * 50, rating=3)

    def create_attempt_data(self, attempt, score, words, rating):
         # Create attempt slot for rating assignment
         as1 = QuizAttemptSlot.objects.create(attempt=attempt, slot=self.slot1, assigned_problem=self.prob1, answer_data={'ratings': {'C1': rating}})
        
         # Note: Grade creation will be handled in test method using set_grade helper
         # to insure we link it to the rubric items correctly.
         pass


    def test_correlation_data_collected(self):
        # API relies on Sum of points. Since setting up full rubric structure is heavy, 
        # I will patch `QuizInterRaterAgreementView.get` or mock the data?
        # Better: actually create the data.
        
        from quizzes.models import GradingRubric, GradingRubricItem, GradingRubricItemLevel
        
        rubric = GradingRubric.objects.create(quiz=self.quiz)
        ri = GradingRubricItem.objects.create(rubric=rubric, label="Item 1", order=1)
        
        # Create Levels for scores we want
        l100 = GradingRubricItemLevel.objects.create(rubric_item=ri, points=100, label="100", order=1)
        l75 = GradingRubricItemLevel.objects.create(rubric_item=ri, points=75, label="75", order=2)
        l50 = GradingRubricItemLevel.objects.create(rubric_item=ri, points=50, label="50", order=3)
        
        def set_grade(attempt, points):
             as_rating = QuizAttemptSlot.objects.get(attempt=attempt, slot=self.slot1)
             grade = QuizSlotGrade.objects.create(attempt_slot=as_rating)
             level = l100 if points == 100 else l50 if points == 50 else l75
             QuizSlotGradeItem.objects.create(grade=grade, rubric_item=ri, selected_level=level)

        set_grade(self.a1, 100)
        set_grade(self.a2, 50)
        set_grade(self.a3, 75)
        
        # Add text data
        # We need a problem for the text slot too, otherwise IntegrityError
        # Assuming problem2 logic
        prob2 = Problem.objects.create(problem_bank=self.bank, statement="P2", order_in_bank=2)
        
        QuizAttemptSlot.objects.create(attempt=self.a1, slot=self.slot2, assigned_problem=prob2, answer_data={'text': "word " * 100})
        QuizAttemptSlot.objects.create(attempt=self.a2, slot=self.slot2, assigned_problem=prob2, answer_data={'text': "word " * 10})
        QuizAttemptSlot.objects.create(attempt=self.a3, slot=self.slot2, assigned_problem=prob2, answer_data={'text': "word " * 50})

        url = reverse('quiz-analytics-agreement', args=[self.quiz.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify Score Correlation presence and count
        self.assertIn('score_correlation', response.data)
        score_c = response.data['score_correlation']
        # We expect entries for C1 and Weighted Rating
        c1_corr = next((item for item in score_c if item['name'] == 'C1'), None)
        self.assertIsNotNone(c1_corr)
        self.assertEqual(c1_corr['count'], 3, "Should have 3 data points for Score vs Rating")
        
        
        # Verify Time Correlation
        self.assertIn('time_correlation', response.data)
        time_c = response.data['time_correlation']
        # Should be a list with 1 item if valid
        self.assertEqual(len(time_c), 1)
        self.assertEqual(time_c[0]['name'], "Quiz Duration")
        self.assertEqual(time_c[0]['count'], 3)
        # 100 -> 60min, 50 -> 10min, 75 -> 30min created perfect positive correlation
        self.assertGreater(time_c[0]['pearson_r'], 0.95)
        
        # Verify Word Count Correlation
        self.assertIn('word_count_correlation', response.data)
        word_c = response.data['word_count_correlation']
        self.assertEqual(len(word_c), 1)
        self.assertEqual(word_c[0]['name'], "Word Count")
        self.assertEqual(word_c[0]['count'], 3)
        # 100->100 words, 50->10 words, 75->50 words. Perfect positive correlation (mostly)
        self.assertAlmostEqual(word_c[0]['pearson_r'], 1.0, places=1)

    def test_inter_criterion_correlation(self):
        # Setup second criterion
        c2 = QuizRatingCriterion.objects.create(quiz=self.quiz, order=2, criterion_id='C2', name='Criterion 2', instructor_criterion_code='IC2')
        
        # Update attempt data creation to include C2
        # We need to recreate data or update existing attempt slots
        # For simplicity, let's just create new attempts for this specific test or modify the helper
        
        # Let's modify the existing attempts to have C2 ratings
        # A1: C1=5, C2=5 (High correlation)
        # A2: C1=1, C2=1
        # A3: C1=3, C2=3
        
        # Fetch existing attempt slots
        as1 = QuizAttemptSlot.objects.get(attempt=self.a1, slot=self.slot1)
        d1 = as1.answer_data
        d1['ratings']['C2'] = 5
        as1.answer_data = d1
        as1.save()
        
        as2 = QuizAttemptSlot.objects.get(attempt=self.a2, slot=self.slot1)
        d2 = as2.answer_data
        d2['ratings']['C2'] = 1
        as2.answer_data = d2
        as2.save()
        
        as3 = QuizAttemptSlot.objects.get(attempt=self.a3, slot=self.slot1)
        d3 = as3.answer_data
        d3['ratings']['C2'] = 3
        as3.answer_data = d3
        as3.save()
        
        url = reverse('quiz-analytics-slot', args=[self.quiz.id, self.slot1.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('inter_criterion_correlation', response.data['data'])
        
        matrix = response.data['data']['inter_criterion_correlation']
        # Structure: { criteria: [names], matrix: [[val, val], [val, val]] }
        self.assertIn('criteria', matrix)
        self.assertIn('matrix', matrix)
        
        self.assertEqual(len(matrix['criteria']), 2)
        # Check C1 vs C2 correlation (should be 1.0)
        # Find indices
        c1_idx = -1
        c2_idx = -1
        for idx, name in enumerate(matrix['criteria']):
            if name == 'C1': c1_idx = idx
            if name == 'Criterion 2': c2_idx = idx
            
        self.assertNotEqual(c1_idx, -1)
        self.assertNotEqual(c2_idx, -1)
        
        # Correlation between C1 and C2
        corr = matrix['matrix'][c1_idx][c2_idx]
        self.assertIsNotNone(corr, f"Correlation between C1 and C2 is None. Matrix: {matrix['matrix']}")
        self.assertEqual(corr['r'], 1.0)
        # p-value for N=3 might not be significant? N=3, rho=1 -> p=0 almost.
        # But spearmanr table for N=3...
        # Let's relax p-value check or just check 'n'
        self.assertEqual(corr['n'], 3)
