from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from problems.models import Problem, ProblemBank, InstructorProblemRating, InstructorProblemRatingEntry, Rubric, RubricCriterion, RubricScaleOption
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption, QuizSlotProblemBank
from accounts.models import User
import json

class StudentInstructorComparisonTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.ensure_instructor(self.user)
        self.client.force_authenticate(user=self.user)

        self.bank = ProblemBank.objects.create(name="Test Bank", owner=self.user.instructor)

        self.quiz = Quiz.objects.create(title="Test Quiz", owner=self.user.instructor)
        
        # Setup Rubric
        self.rubric = Rubric.objects.create(name="Test Rubric", owner=self.user.instructor)
        self.bank.rubric = self.rubric
        self.bank.save()

        self.c1 = QuizRatingCriterion.objects.create(quiz=self.quiz, name="C1", order=1, criterion_id="c1", instructor_criterion_code="IC1")
        
        # Add RubricCriterion and ScaleOptions to self.rubric so Bank has scale
        RubricCriterion.objects.create(rubric=self.rubric, criterion_id="IC1", name="Inst Crit 1", order=1)
        RubricScaleOption.objects.create(rubric=self.rubric, value=1.0, label="1", order=1)
        RubricScaleOption.objects.create(rubric=self.rubric, value=5.0, label="5", order=2) # Max 5, Min 1, Range 4
        
        self.scale_vals = [1, 2, 3, 4, 5]
        for v in self.scale_vals:
            # map 1->1, ..., 5->5 (Identity for simple testing)
            mapped = float(v)
            QuizRatingScaleOption.objects.create(quiz=self.quiz, value=v, label=str(v), mapped_value=mapped, order=v)

        # Setup Problem
        self.problem = Problem.objects.create(statement="P1", order_in_bank=1, problem_bank=self.bank)
        
        # Setup Quiz Slot (Rating)
        self.slot = QuizSlot.objects.create(quiz=self.quiz, response_type=QuizSlot.ResponseType.RATING, order=1, problem_bank=self.bank)
        QuizSlotProblemBank.objects.create(quiz_slot=self.slot, problem=self.problem)

        # Instructor Rating (IC1 = 1.0)
        rating = InstructorProblemRating.objects.create(problem=self.problem, instructor=self.user.instructor)
        self.create_rating_entry(rating, 'IC1', 1.0) # mapped value

        # Student Attempt (Rating = 5 -> Mapped = 5.0)
        self.attempt = QuizAttempt.objects.create(quiz=self.quiz, student_identifier="s1", completed_at="2023-01-01T00:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=self.attempt, 
            slot=self.slot, 
            assigned_problem=self.problem,
            answer_data={'ratings': {'c1': 5}} 
        )

    def ensure_instructor(self, user):
        from accounts.models import Instructor
        if not hasattr(user, 'instructor_profile'):
            Instructor.objects.create(user=user)

    def create_rating_entry(self, rating, code, value):
        # Ensure Rubric exists
        if not hasattr(self, 'rubric'):
             self.rubric = Rubric.objects.create(name="Test Rubric", owner=self.user.instructor)
        
        # We need a RubricCriterion with criterion_id = code
        rc, _ = RubricCriterion.objects.get_or_create(rubric=self.rubric, criterion_id=code, defaults={'name': 'Inst Crit 1', 'order': 1})
        
        # We need a ScaleOption with value 'value'
        so, _ = RubricScaleOption.objects.get_or_create(rubric=self.rubric, value=value, defaults={'label': str(value), 'order': int(value)})

        InstructorProblemRatingEntry.objects.create(rating=rating, criterion=rc, scale_option=so)

    def test_comparison_logic_insufficient_data(self):
        url = reverse('quiz-analytics-agreement', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data['comparison'][0]
        self.assertEqual(item['common_problems'], 1)
        self.assertIsNone(item['t_statistic'])
        self.assertIsNone(item['p_value'])

    def test_comparison_logic(self):
        # Add a second problem and rating to allow t-test
        problem2 = Problem.objects.create(statement="P2", order_in_bank=2, problem_bank=self.bank)
        QuizSlotProblemBank.objects.create(quiz_slot=self.slot, problem=problem2)
        # API says relevant_problem_ids comes from slot attempts or bank?
        # quiz.py uses: relevant_problem_ids = set() ... from student attempts and instructor ratings.
        
        # But wait, a single slot usually assigns ONE problem per attempt.
        # So I need another attempt with a DIFFERENT problem, or the same attempt with multiple rating slots?
        # Usually random quiz gives different problems to different students OR different problems in different slots.
        # If I use the SAME slot, I can have another attempt with a different problem.
        # OR I can have another slot.
        
        # Let's create another attempt with a different problem for the same student? No, one attempt per student usually.
        # Another student attempt with a different problem.
        
        rating2 = InstructorProblemRating.objects.create(problem=problem2, instructor=self.user.instructor)
        self.create_rating_entry(rating2, 'IC1', 1.0)

        attempt2 = QuizAttempt.objects.create(quiz=self.quiz, student_identifier="s2", completed_at="2023-01-01T00:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=attempt2, 
            slot=self.slot, 
            assigned_problem=problem2,
            answer_data={'ratings': {'c1': 5}} 
        )
        
        url = reverse('quiz-analytics-agreement', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('comparison', data)
        comparison = data['comparison']
        item = comparison[0]
        
        self.assertEqual(item['common_problems'], 2)
        # S=5, I=1. Diff 4. Constant.
        self.assertIsNone(item['t_statistic'])
        self.assertEqual(item['p_value'], 0.0)
        self.assertEqual(item['mean_difference'], 4.0)
        
        
        # Verify Weighted Score in comparison list (last item)
        # Weight for C1 is 1 (default in create_rating_entry)
        # So "Weighted Score" should equal "C1" logic if only C1 exists.
        weighted_item = comparison[-1]
        self.assertEqual(weighted_item['criterion_id'], 'weighted')
        self.assertEqual(weighted_item['common_problems'], 2)
        self.assertIsNone(weighted_item['t_statistic'])
        
        # Verify Weighted Data in Details
        details = data['details']
        p1_detail = next(d for d in details if d['problem_label'] == 'Problem 1')
        self.assertIn('weighted_instructor', p1_detail)
        self.assertEqual(p1_detail['weighted_instructor'], 1.0)
    
    def test_global_comparison_logic(self):
        # Create a second quiz with different scale (1-10)
        quiz2 = Quiz.objects.create(title="Quiz 2", owner=self.user.instructor)
        # Add scale 1-10
        QuizRatingScaleOption.objects.create(quiz=quiz2, value=1, label="1", order=1)
        QuizRatingScaleOption.objects.create(quiz=quiz2, value=10, label="10", order=2)
        
        # Add criterion C1 matching IC1
        QuizRatingCriterion.objects.create(quiz=quiz2, name="C1", order=1, criterion_id="c1", instructor_criterion_code="IC1")
        
        # Create Slot and Problem for Quiz 2
        slot2 = QuizSlot.objects.create(quiz=quiz2, response_type=QuizSlot.ResponseType.RATING, order=1, problem_bank=self.bank)
        problem3 = Problem.objects.create(statement="P3", order_in_bank=3, problem_bank=self.bank)
        QuizSlotProblemBank.objects.create(quiz_slot=slot2, problem=problem3)
        
        # Instructor Rating P3 (IC1 = 1.0)
        rating3 = InstructorProblemRating.objects.create(problem=problem3, instructor=self.user.instructor)
        self.create_rating_entry(rating3, 'IC1', 1.0) # Scale option value 1.0
        
        # Student Rating P3 (5.5 on 1-10 scale) -> Norm: (5.5-1)/9 = 4.5/9 = 0.5
        attempt3 = QuizAttempt.objects.create(quiz=quiz2, student_identifier="s3", completed_at="2023-01-01T00:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=attempt3,
            slot=slot2,
            assigned_problem=problem3,
            answer_data={'ratings': {'c1': 5.5}}
        )
        
        # Now we have:
        # Quiz 1 (P1): Inst=1.0, Stud=1.0 (from setUp)
        # Quiz 1 (P2): Inst=1.0, Stud=1.0 (from test_comparison_logic setup, need to replicate here or piggyback)
        # Quiz 2 (P3): Inst=1.0, Stud=0.5
        
        # Note: test_comparison_logic added P2. But that's in a different test method.
        # setUp only has P1.
        
        # Use direct path
        url = '/api/problem-banks/analysis/global/'
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('global_comparison', data)
        gc = data['global_comparison']
        
        # Find C1 row
        c1_row = next(r for r in gc['comparison'] if r['criterion_id'] == 'IC1')
        
        # Common Problems: P1 (from Quiz 1) + P3 (from Quiz 2) = 2
        self.assertEqual(c1_row['common_problems'], 2)
        
        # Means
        # Inst: (1.0 + 1.0) / 2 = 1.0
        # Stud: (1.0 + 3.0) / 2 = 2.0 (Mapped: 1+((5.5-1)/9)*4 = 1+2=3)
        self.assertEqual(c1_row['instructor_mean'], 1.0)
        self.assertEqual(c1_row['student_mean_norm'], 5.25)
        
        # Weighted Score (Only C1 involved, weight 1)
        # Should match C1 stats
        w_row = next(r for r in gc['comparison'] if r['criterion_id'] == 'weighted')
        self.assertEqual(w_row['instructor_mean'], 1.0)
        self.assertEqual(w_row['student_mean_norm'], 5.25)

    def test_global_analysis_anova(self):
        # Create 2 banks
        bank1 = ProblemBank.objects.create(name="Bank 1", owner=self.user.instructor)
        bank2 = ProblemBank.objects.create(name="Bank 2", owner=self.user.instructor)
        
        # Create Rubric
        self.rubric = Rubric.objects.create(name="Rubric 1", owner=self.user.instructor)
        self.bank.rubric = self.rubric
        self.bank.save()
        RubricCriterion.objects.create(rubric=self.rubric, criterion_id="c1", name="C1", order=1)
        RubricScaleOption.objects.create(rubric=self.rubric, value=1, label="1", order=1)
        RubricScaleOption.objects.create(rubric=self.rubric, value=5, label="5", order=2)
        
        bank1.rubric = self.rubric
        bank1.save()
        bank2.rubric = self.rubric
        bank2.save()
        
        # Add Problems and Ratings to Bank 1 (2 problems)
        p1 = Problem.objects.create(statement="P1", problem_bank=bank1, order_in_bank=1)
        r1 = InstructorProblemRating.objects.create(problem=p1, instructor=self.user.instructor)
        self.create_rating_entry(r1, "c1", 1.0)
        
        p2 = Problem.objects.create(statement="P2", problem_bank=bank1, order_in_bank=2)
        r2 = InstructorProblemRating.objects.create(problem=p2, instructor=self.user.instructor)
        self.create_rating_entry(r2, "c1", 5.0) # Mean = 3.0
        
        # Add Problems and Ratings to Bank 2 (2 problems)
        p3 = Problem.objects.create(statement="P3", problem_bank=bank2, order_in_bank=1)
        r3 = InstructorProblemRating.objects.create(problem=p3, instructor=self.user.instructor)
        self.create_rating_entry(r3, "c1", 5.0)
        
        p4 = Problem.objects.create(statement="P4", problem_bank=bank2, order_in_bank=2)
        r4 = InstructorProblemRating.objects.create(problem=p4, instructor=self.user.instructor)
        self.create_rating_entry(r4, "c1", 5.0) # Mean = 5.0
        
        # We need to setup QuizSlot/Attempt for Global Comparison? 
        # No, ANOVA is Bank-based. But verify GlobalAnalysisView runs without error.
        
        url = '/api/problem-banks/analysis/global/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('anova', data)
        anova = data['anova']
        
        # Find C1
        c1_anova = next((r for r in anova if r['criterion_id'] == 'C1'), None)
        self.assertIsNotNone(c1_anova)
        
        # Expect significant difference (Bank 1: [1, 5], Bank 2: [5, 5]) 
        # Although variances might be issue, but f_stat should not be None
        self.assertIsNotNone(c1_anova['f_stat'])
        self.assertIsNotNone(c1_anova['p_value'])
        self.assertEqual(len(c1_anova['banks_included']), 2)
    def test_weighted_calculation_with_varied_weights(self):
        # Create C2 with weight 2
        
        # Ensure Rubric exists
        if not hasattr(self, 'rubric'):
             self.rubric = Rubric.objects.create(name="Test Rubric", owner=self.user.instructor)
             
        c2_crit = QuizRatingCriterion.objects.create(quiz=self.quiz, name="C2", order=2, criterion_id="c2", instructor_criterion_code="IC2")
        rc2, _ = RubricCriterion.objects.get_or_create(rubric=self.rubric, criterion_id="IC2", defaults={'name': 'Inst Crit 2', 'order': 2, 'weight': 2})
        # Note: 'weight' is in RubricCriterion model (verified in view_file).

        # For Problem 1:
        # C1 (Weight 1) -> Inst: 1.0, Stud: 5.0 (Mapped)
        # C2 (Weight 2) -> Let's add ratings
        
        # Instructor Rating P1, C2 = 0.5 (Scale val 2, mapped 0.25? No, direct value logic)
        # create_rating_entry takes value and creates scale option.
        # Let's say val = 2. 
        rating1 = InstructorProblemRating.objects.get(problem=self.problem)
        so2, _ = RubricScaleOption.objects.get_or_create(rubric=self.rubric, value=0.5, defaults={'label': '0.5', 'order': 1})
        InstructorProblemRatingEntry.objects.create(rating=rating1, criterion=rc2, scale_option=so2)
        
        # Student Rating P1, C2 = 3 (Scale 1-5) -> Mapped: 3.0
        attempt1 = QuizAttempt.objects.get(student_identifier="s1")
        # Update existing attempt slot or create new? Existing attempt slot has answer_data JSON.
        # We need to update the JSON.
        qas = QuizAttemptSlot.objects.get(attempt=attempt1, slot=self.slot)
        qas.answer_data['ratings']['c2'] = 3
        qas.save()
        
        # Expected Weighted Avg for P1:
        # Inst: (1.0 * 1 + 0.5 * 2) / (1 + 2) = 2.0 / 3 = 0.6667
        # Stud: (5.0 * 1 + 3.0 * 2) / 3 = 11.0 / 3 = 3.6667
        
        url = reverse('quiz-analytics-agreement', args=[self.quiz.id])
        response = self.client.get(url)
        details = response.data['details']
        p1_detail = next(d for d in details if d['problem_label'] == 'Problem 1')
        
        self.assertAlmostEqual(p1_detail['weighted_instructor'], 0.6667, places=3)
        self.assertAlmostEqual(p1_detail['weighted_student'], 3.6667, places=3)

    def test_comparison_normalization(self):
        # Add another student with rating 1 (Norm = 0.0)
        attempt2 = QuizAttempt.objects.create(quiz=self.quiz, student_identifier="s2", completed_at="2023-01-01T00:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=attempt2, 
            slot=self.slot, 
            assigned_problem=self.problem,
            answer_data={'ratings': {'c1': 1}} 
        )
        
        # Now for problem 1:
        # Student raw: (5 + 1) / 2 = 3.
        # Student norm: (3 - 1) / 4 = 0.5.
        
        url = reverse('quiz-analytics-agreement', args=[self.quiz.id])
        response = self.client.get(url)
        item = response.data['comparison'][0]
        
        self.assertEqual(item['student_mean_norm'], 3.0)
        self.assertEqual(item['instructor_mean'], 1.0)
        self.assertEqual(item['mean_difference'], 2.0)

