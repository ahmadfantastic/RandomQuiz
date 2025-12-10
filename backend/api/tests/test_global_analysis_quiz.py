from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User, Instructor
from problems.models import ProblemBank, Problem
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption

class GlobalAnalysisQuizTest(APITestCase):
    def setUp(self):
        # Create user and instructor
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        # Create 2 Quizzes
        from django.utils import timezone
        from datetime import timedelta
        self.quiz1 = Quiz.objects.create(title="Quiz 1", owner=self.instructor)
        self.quiz2 = Quiz.objects.create(title="Quiz 2", owner=self.instructor)

        # Setup Quiz 1: Rating Slot + Text Slot
        
        self.c1 = QuizRatingCriterion.objects.create(quiz=self.quiz1, order=1, criterion_id='C1', name='Criterion 1', description='Desc 1', instructor_criterion_code='IC1')
        self.c2 = QuizRatingCriterion.objects.create(quiz=self.quiz1, order=2, criterion_id='C2', name='Criterion 2', description='Desc 2', instructor_criterion_code='IC2')
        
        # Scale Options
        for i in range(1, 6):
            QuizRatingScaleOption.objects.create(quiz=self.quiz1, order=i, value=i, label=str(i), mapped_value=float(i))
        
        # Slots and Problems
        self.bank = ProblemBank.objects.create(owner=self.instructor, name="Bank 1")
        self.prob1 = Problem.objects.create(problem_bank=self.bank, statement="P1", order_in_bank=1)
        self.prob2 = Problem.objects.create(problem_bank=self.bank, statement="P2", order_in_bank=2)
        
        self.slot1 = QuizSlot.objects.create(quiz=self.quiz1, order=1, label="Rating Slot", problem_bank=self.bank, response_type=QuizSlot.ResponseType.RATING)
        self.slot2 = QuizSlot.objects.create(quiz=self.quiz1, order=2, label="Text Slot", problem_bank=self.bank, response_type=QuizSlot.ResponseType.OPEN_TEXT)

        # Attempts on Quiz 1
        now = timezone.now()
        # Attempt 1: 30 mins
        start1 = now - timedelta(minutes=60)
        end1 = now - timedelta(minutes=30)
        self.a1 = QuizAttempt.objects.create(quiz=self.quiz1, student_identifier="S1", completed_at=end1)
        self.a1.started_at = start1
        self.a1.save()
        
        self.as1 = QuizAttemptSlot.objects.create(attempt=self.a1, slot=self.slot1, assigned_problem=self.prob1, answer_data={'ratings': {'C1': 5, 'C2': 4}})
        self.as2 = QuizAttemptSlot.objects.create(attempt=self.a1, slot=self.slot2, assigned_problem=self.prob2, answer_data={'text': "Hello world this is a test"}) # 6 words

        # Attempt 2: 10 mins
        start2 = now - timedelta(minutes=10)
        end2 = now
        self.a2 = QuizAttempt.objects.create(quiz=self.quiz1, student_identifier="S2", completed_at=end2)
        self.a2.started_at = start2
        self.a2.save()

        self.as3 = QuizAttemptSlot.objects.create(attempt=self.a2, slot=self.slot1, assigned_problem=self.prob1, answer_data={'ratings': {'C1': 3, 'C2': 2}})
        self.as4 = QuizAttemptSlot.objects.create(attempt=self.a2, slot=self.slot2, assigned_problem=self.prob2, answer_data={'text': "Another test"}) # 2 words

        # Attempt 3: Incomplete
        self.a3 = QuizAttempt.objects.create(quiz=self.quiz1, student_identifier="S3") # started_at auto set to now

        # Quiz 2: Empty, no attempts
        
    def test_global_analysis_quiz_stats(self):
        url = reverse('global-analysis')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('quiz_analysis', response.data)
        
        qa = response.data['quiz_analysis']
        self.assertIn('quizzes', qa)
        self.assertIn('all_criteria', qa)
        
        quizzes = qa['quizzes']
        self.assertEqual(len(quizzes), 2)
        
        # Verify Quiz 1 Stats
        q1_stats = next(q for q in quizzes if q['id'] == self.quiz1.id)
        self.assertEqual(q1_stats['title'], "Quiz 1")
        self.assertEqual(q1_stats['response_count'], 2) # Only completed counts
        
        # Time: (30 + 10) / 2 = 20 mins
        self.assertEqual(q1_stats['avg_time_minutes'], 20.0)
        
        # Word Count: (6 + 2) / 2 = 4
        self.assertEqual(q1_stats['avg_word_count'], 4.0)
        
        # Ratings
        # C1: (5 + 3) / 2 = 4.0
        # C2: (4 + 2) / 2 = 3.0
        means = q1_stats['means']
        self.assertEqual(means['C1'], 4.0)
        self.assertEqual(means['C2'], 3.0)
        
        # Alpha
        # Should be calculated. Just verify it's a float or null.
        # With 2 items, 2 cases, and variance...
        # Items: C1 [5, 3], C2 [4, 2]. 
        # Var(C1) = Var([5,3]) = 2.0 (sample var)
        # Var(C2) = Var([4,2]) = 2.0
        # Sum(Vars) = 4.0
        # Totals: [9, 5]. Mean=7. Var([9,5]) = 8.0
        # K=2. Alpha = (2/1) * (1 - 4/8) = 2 * 0.5 = 1.0
        # Wait, if sample var is N-1.
        self.assertIsNotNone(q1_stats['cronbach_alpha'])
        self.assertAlmostEqual(q1_stats['cronbach_alpha'], 1.0, places=2)

        # Verify Quiz 2 Stats
        q2_stats = next(q for q in quizzes if q['id'] == self.quiz2.id)
        self.assertEqual(q2_stats['response_count'], 0)
        self.assertIsNone(q2_stats['cronbach_alpha'])

    def test_global_inter_criterion_correlation(self):
        url = reverse('global-analysis')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('inter_criterion_correlation', response.data)
        
        icc = response.data['inter_criterion_correlation']
        # Based on setup:
        # A1: C1=5, C2=4
        # A2: C1=3, C2=2
        # Correlation should be perfect 1.0 because 5->3 (-2) and 4->2 (-2). Linear relationship.
        
        self.assertIsNotNone(icc)
        self.assertEqual(icc['criteria'], ['Criterion 1', 'Criterion 2'])
        
        matrix = icc['matrix']
        self.assertEqual(len(matrix), 2)
        
        # Row 0 (C1): [None, {r: 1.0, ...}] because diag is None
        # Row 1 (C2): [{r: 1.0, ...}, None]
        
        # Cells
        c1_c2 = matrix[0][1]
        self.assertIsNotNone(c1_c2)
        self.assertAlmostEqual(c1_c2['r'], 1.0, places=3)
        self.assertEqual(c1_c2['n'], 2)
        
        c2_c1 = matrix[1][0]
        self.assertIsNotNone(c2_c1)
        self.assertAlmostEqual(c2_c1['r'], 1.0, places=3)
        self.assertEqual(c2_c1['n'], 2)
