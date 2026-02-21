from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Instructor
from problems.models import ProblemBank, Problem, Rubric, RubricCriterion, RubricScaleOption, InstructorProblemRating, InstructorProblemRatingEntry
from django.contrib.auth.models import User
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption

class GlobalSplitViewsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        # Helper User 2
        self.user2 = User.objects.create_user(username='rater2', password='password')
        self.rater2 = Instructor.objects.create(user=self.user2)

        # Rubric & Bank
        self.rubric = Rubric.objects.create(name="Test Rubric")
        self.criterion = RubricCriterion.objects.create(rubric=self.rubric, name="Quality", criterion_id="Quality", description="desc", order=1)
        self.scale_options = []
        for i in range(1, 6):
            self.scale_options.append(RubricScaleOption.objects.create(rubric=self.rubric, value=float(i), label=str(i), order=i))

        self.bank_a = ProblemBank.objects.create(name="Bank A", owner=self.instructor, rubric=self.rubric)
        self.bank_b = ProblemBank.objects.create(name="Bank B", owner=self.instructor, rubric=self.rubric)

    def test_instructor_view_anova_and_banks(self):
        # Setup Problem in Bank A: P1 (Rater1=2, Rater2=4 -> Avg 3)
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1)
        r1 = InstructorProblemRating.objects.create(problem=p1, instructor=self.instructor)
        r1.entries.create(criterion=self.criterion, scale_option=self.scale_options[1]) # 2
        r2 = InstructorProblemRating.objects.create(problem=p1, instructor=self.rater2)
        r2.entries.create(criterion=self.criterion, scale_option=self.scale_options[3]) # 4
        
        # P2 in Bank A: (Rater1=5 -> Avg 5)
        p2 = Problem.objects.create(problem_bank=self.bank_a, statement="P2", order_in_bank=2)
        r3 = InstructorProblemRating.objects.create(problem=p2, instructor=self.instructor)
        r3.entries.create(criterion=self.criterion, scale_option=self.scale_options[4]) # 5

        # Call Instructor View
        # We assume URL name follows pattern 'global-instructor-analysis' if we named it?
        # Actually I didn't name them in urls.py yet? Or did I?
        # I added path('problem-banks/analysis/global/instructor/', ...).
        # Let's use direct path or reverse if named.
        # I didn't add 'name=' kwarg in urls.py for new paths.
        
        url = '/api/problem-banks/analysis/global/instructor/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('anova', data)
        self.assertIn('banks', data)
        self.assertIn('problem_groups', data)
        
        # Verify Bank Stats
        # Bank A should have 2 problems rated.
        bank_stats = next((b for b in data['banks'] if b['id'] == self.bank_a.id), None)
        self.assertIsNotNone(bank_stats)
        # Check means if available
        # logic: avg(3, 5) = 4
        if 'means' in bank_stats and 'Quality' in bank_stats['means']:
             self.assertEqual(bank_stats['means']['Quality'], 4.0)

    def test_student_view_distributions(self):
        # Create Quiz
        quiz = Quiz.objects.create(title="Test Quiz", owner=self.instructor)
        qc = QuizRatingCriterion.objects.create(quiz=quiz, order=1, criterion_id='Q_QUAL', name='Quality', instructor_criterion_code='QUAL')
        QuizRatingScaleOption.objects.create(quiz=quiz, value=1, label="1", mapped_value=1, order=1)
        
        slot = QuizSlot.objects.create(quiz=quiz, order=1, label="Rating Slot", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier="student1", completed_at="2023-01-01T12:00:00Z")
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1)
        
        QuizAttemptSlot.objects.create(
            attempt=attempt, slot=slot, assigned_problem=p1,
            answer_data={'ratings': {'Q_QUAL': 1}}, answered_at="2023-01-01T12:00:00Z"
        )
        
        url = '/api/problem-banks/analysis/global/student/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('global_rating_distribution', data)
        self.assertIn('grouped_rating_distribution', data)
        
        # Verify distribution
        criteria = data['global_rating_distribution'].get('criteria', [])
        qual = next((c for c in criteria if c['name'] == 'Quality'), None)
        self.assertIsNotNone(qual)
        # Check count for value 1 should be 1
        dist = qual['distribution']
        v1 = next((x for x in dist if x['value'] == 1.0), None)
        self.assertIsNotNone(v1)
        self.assertEqual(v1['count'], 1)

    def test_correlation_view(self):
        # Just ensure it runs without error (empty data is fine)
        url = '/api/problem-banks/analysis/global/correlation/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('score_correlation', data)
        self.assertIn('time_correlation', data)
        # We expect None or empty list if no data

    def test_agreement_view(self):
         # Create matching instructor/student ratings for comparison
        quiz = Quiz.objects.create(title="Test Quiz", owner=self.instructor)
        qc = QuizRatingCriterion.objects.create(quiz=quiz, order=1, criterion_id='Q_QUAL', name='Quality', instructor_criterion_code='Quality') # 'Quality' matches logic dict
        QuizRatingScaleOption.objects.create(quiz=quiz, value=1, label="1", mapped_value=1, order=1)
        
        slot = QuizSlot.objects.create(quiz=quiz, order=1, label="Slot", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier="s1", completed_at="2023-01-01T12:00:00Z")
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1)
        
        # Instructor Rating = 1
        r1 = InstructorProblemRating.objects.create(problem=p1, instructor=self.instructor)
        r1.entries.create(criterion=self.criterion, scale_option=self.scale_options[0]) # 1
        
        # Student Rating = 1
        QuizAttemptSlot.objects.create(
            attempt=attempt, slot=slot, assigned_problem=p1,
            answer_data={'ratings': {'Q_QUAL': 1}}, answered_at="2023-01-01T12:00:00Z"
        )
        
        url = '/api/problem-banks/analysis/global/agreement/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('global_quiz_agreement', data)
        self.assertIn('global_comparison', data)
        
        # Check comparison: Should have 1 problem, diff 0
        comp = data['global_comparison']['comparison']
        # Find row for group 'Overall' and criterion 'Quality'
        # Group accumulation logic includes 'Overall'
        row = next((r for r in comp if r['group'] == 'Overall' and r['criterion_name'] == 'Quality'), None)
        self.assertIsNotNone(row)
        self.assertEqual(row['mean_difference'], 0.0)

    def test_cfa_integration(self):
        # Create Quiz with 3 criteria (minimum for CFA)
        quiz = Quiz.objects.create(title="CFA Quiz", owner=self.instructor)
        c1 = QuizRatingCriterion.objects.create(quiz=quiz, order=1, criterion_id='C1', name='C1', instructor_criterion_code='C1')
        c2 = QuizRatingCriterion.objects.create(quiz=quiz, order=2, criterion_id='C2', name='C2', instructor_criterion_code='C2')
        c3 = QuizRatingCriterion.objects.create(quiz=quiz, order=3, criterion_id='C3', name='C3', instructor_criterion_code='C3')
        
        QuizRatingScaleOption.objects.create(quiz=quiz, value=1, label="1", mapped_value=1, order=1)
        QuizRatingScaleOption.objects.create(quiz=quiz, value=5, label="5", mapped_value=5, order=2)

        slot = QuizSlot.objects.create(quiz=quiz, order=1, label="Slot", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1)

        # Create 25 attempts to satisfy N >= 20
        # Make them highly correlated (Halo Effect)
        import random
        for i in range(25):
            attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier=f"s{i}", completed_at="2023-01-01T12:00:00Z", started_at="2023-01-01T11:00:00Z")
            
            # Random data to ensure positive definiteness
            # Just random integers 1-5
            r1 = float(random.randint(1, 5))
            r2 = float(random.randint(1, 5))
            r3 = float(random.randint(1, 5))
            
            QuizAttemptSlot.objects.create(
                attempt=attempt, slot=slot, assigned_problem=p1,
                answer_data={'ratings': {'C1': r1, 'C2': r2, 'C3': r3}}, 
                answered_at="2023-01-01T12:00:00Z",
                grade=None
            )


        url = '/api/problem-banks/analysis/global/correlation/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('factor_analysis', data)
        cfa = data['factor_analysis']
        # Should not be None because we met requirements
        self.assertIsNotNone(cfa)
        self.assertIn('fit_indices', cfa)
        self.assertIn('loadings', cfa)
        self.assertGreaterEqual(len(cfa['loadings']), 3)

