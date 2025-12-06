from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Instructor
from problems.models import ProblemBank, Problem, Rubric, RubricCriterion, RubricScaleOption, InstructorProblemRating, InstructorProblemRatingEntry
from django.contrib.auth.models import User

class GlobalAnalysisAnovaTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        # Create separate raters
        self.user2 = User.objects.create_user(username='rater2', password='password')
        self.rater2 = Instructor.objects.create(user=self.user2)

        # Create Rubric
        self.rubric = Rubric.objects.create(name="Test Rubric")
        self.criterion = RubricCriterion.objects.create(rubric=self.rubric, name="Quality", description="desc", order=1, weight=1)
        self.scale_options = []
        for i in range(1, 6):
            self.scale_options.append(RubricScaleOption.objects.create(rubric=self.rubric, value=float(i), label=str(i), order=i))

        # Create Banks
        self.bank_a = ProblemBank.objects.create(
            name="Bank A", 
            owner=self.instructor,
            rubric=self.rubric
        )
        self.bank_b = ProblemBank.objects.create(
            name="Bank B", 
            owner=self.instructor,
            rubric=self.rubric
        )

    def test_anova_input_values_averaged_per_problem(self):
        # Setup Problem in Bank A
        # Problem A1: Rater1=2, Rater2=4 -> Avg 3.0
        p_a1 = Problem.objects.create(problem_bank=self.bank_a, statement="A1", order_in_bank=1)
        r1 = InstructorProblemRating.objects.create(problem=p_a1, instructor=self.instructor)
        r1.entries.create(criterion=self.criterion, scale_option=self.scale_options[1]) # Val 2
        r2 = InstructorProblemRating.objects.create(problem=p_a1, instructor=self.rater2)
        r2.entries.create(criterion=self.criterion, scale_option=self.scale_options[3]) # Val 4

        # Problem A2: Rater1=5 -> Avg 5.0
        p_a2 = Problem.objects.create(problem_bank=self.bank_a, statement="A2", order_in_bank=2)
        r3 = InstructorProblemRating.objects.create(problem=p_a2, instructor=self.instructor)
        r3.entries.create(criterion=self.criterion, scale_option=self.scale_options[4]) # Val 5
        
        # Bank A Values: [3.0, 5.0]

        # Setup Bank B
        # Problem B1: Rater1=8?? scaling is 1-5. Let's stick to valid range 1-5 to be safe, though model doesn't enforce? 
        # Actually scale_options only go up to 5. So I normally can't assign 8.
        # I will adjust values to be within range but distinct.
        # Bank A: [1.0, 3.0] -> Mean 2.0.
        #   P1: 1, 1 -> Avg 1.
        #   P2: 3, 3 -> Avg 3.
        # Bank B: [4.0, 5.0] -> Mean 4.5.
        #   P3: 4, 4 -> Avg 4.
        #   P4: 5, 5 -> Avg 5.
        
        # Let's clean up and do:
        # Bank A
        # P1: Rater1=1, Rater2=1 -> Avg 1
        InstructorProblemRating.objects.all().delete()
        Problem.objects.all().delete()
        
        p_a1 = Problem.objects.create(problem_bank=self.bank_a, statement="A1", order_in_bank=1)
        r_a1_1 = InstructorProblemRating.objects.create(problem=p_a1, instructor=self.instructor)
        r_a1_1.entries.create(criterion=self.criterion, scale_option=self.scale_options[0]) # Val 1
        r_a1_2 = InstructorProblemRating.objects.create(problem=p_a1, instructor=self.rater2)
        r_a1_2.entries.create(criterion=self.criterion, scale_option=self.scale_options[0]) # Val 1
        
        p_a2 = Problem.objects.create(problem_bank=self.bank_a, statement="A2", order_in_bank=2)
        r_a2_1 = InstructorProblemRating.objects.create(problem=p_a2, instructor=self.instructor)
        r_a2_1.entries.create(criterion=self.criterion, scale_option=self.scale_options[2]) # Val 3
        # Avg 3
        
        # Bank B
        p_b1 = Problem.objects.create(problem_bank=self.bank_b, statement="B1", order_in_bank=1)
        r_b1_1 = InstructorProblemRating.objects.create(problem=p_b1, instructor=self.instructor)
        r_b1_1.entries.create(criterion=self.criterion, scale_option=self.scale_options[3]) # Val 4
        
        p_b2 = Problem.objects.create(problem_bank=self.bank_b, statement="B2", order_in_bank=2)
        r_b2_1 = InstructorProblemRating.objects.create(problem=p_b2, instructor=self.instructor)
        r_b2_1.entries.create(criterion=self.criterion, scale_option=self.scale_options[4]) # Val 5

        # Bank A: [1, 3]. Mean=2.
        # Bank B: [4, 5]. Mean=4.5.
        
        # Grand Mean = (1+3+4+5)/4 = 3.25
        # SSB = 2*(2-3.25)^2 + 2*(4.5-3.25)^2 = 2*(-1.25)^2 + 2*(1.25)^2 = 2*1.5625 + 2*1.5625 = 3.125 + 3.125 = 6.25
        # SSW = (1-2)^2 + (3-2)^2 + (4-4.5)^2 + (5-4.5)^2 = 1 + 1 + 0.25 + 0.25 = 2.5
        # MSB = 6.25 / 1 = 6.25
        # MSW = 2.5 / 2 = 1.25
        # F = 6.25 / 1.25 = 5.0
        
        # Call Global Analysis
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        anova_results = data.get('anova', [])
        
        # Find Quality criterion results
        qual_res = next((r for r in anova_results if r['criterion_id'] == 'Quality'), None)
        self.assertIsNotNone(qual_res, "ANOVA results for Quality not found")
        

        
        # Verify F-stat
        f_stat = qual_res.get('f_stat')
        self.assertIsNotNone(f_stat)
        self.assertAlmostEqual(f_stat, 5.0, places=2)
        
        # Verify Weighted Score ANOVA exists
        weighted_res = next((r for r in anova_results if r['criterion_id'] == 'Weighted Score'), None)
        self.assertIsNotNone(weighted_res, "ANOVA results for Weighted Score not found")

    def test_global_analysis_nan_sanitization(self):
        # Create condition that might cause NaN (e.g. constant values for t-test)
        # Bank A: Constant values for Quality (Variance = 0)
        p_a1 = Problem.objects.create(problem_bank=self.bank_a, statement="A1", order_in_bank=1)
        r1 = InstructorProblemRating.objects.create(problem=p_a1, instructor=self.instructor)
        r1.entries.create(criterion=self.criterion, scale_option=self.scale_options[2]) # 3

        p_a2 = Problem.objects.create(problem_bank=self.bank_a, statement="A2", order_in_bank=2)
        r2 = InstructorProblemRating.objects.create(problem=p_a2, instructor=self.instructor)
        r2.entries.create(criterion=self.criterion, scale_option=self.scale_options[2]) # 3
        
        # Bank B: Constant values (Variance = 0) 
        p_b1 = Problem.objects.create(problem_bank=self.bank_b, statement="B1", order_in_bank=1)
        r3 = InstructorProblemRating.objects.create(problem=p_b1, instructor=self.instructor)
        r3.entries.create(criterion=self.criterion, scale_option=self.scale_options[2]) # 3
        
        # This constant data across groups might cause t-test issues or at least degenerate cases.
        # But specifically, we want to ensure NO 500 ERROR happens even if calculation yields NaN.
        
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Detailed verification of replaced NaNs is harder without mocking numpy, 
        # but 200 OK means JSON serialization succeeded (no infinity/NaN error).
    
    def test_group_means_precision(self):
        # Verify that group means are calculated with float precision (no integer division rounding)
        # Create 1 problem with avg score 1 and another with avg score 2 in same group
        # Mean should be 1.5
        
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1)
        r1 = InstructorProblemRating.objects.create(problem=p1, instructor=self.instructor)
        r1.entries.create(criterion=self.criterion, scale_option=self.scale_options[0]) # Value 1
        
        # P2 in same group (default group None -> "Ungrouped", or we can set group)
        # Since problems in test setup usually default to empty group, they are "Ungrouped".
        # Let's verify "Ungrouped" mean.
        p2 = Problem.objects.create(problem_bank=self.bank_a, statement="P2", order_in_bank=2)
        r2 = InstructorProblemRating.objects.create(problem=p2, instructor=self.instructor)
        r2.entries.create(criterion=self.criterion, scale_option=self.scale_options[1]) # Value 2
        
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        problem_groups = response.data['problem_groups']
        ungrouped = next((g for g in problem_groups if g['name'] == 'Ungrouped'), None)
        
        if not ungrouped:
             # Maybe the test setup has groups? Check bank_a setup.
             # Test setup doesn't assign groups.
             # Check if 'Ungrouped' is the name.
             pass
        
        self.assertIsNotNone(ungrouped)
        # Quality score
        quality_mean = ungrouped['means'].get('Quality')
        self.assertEqual(quality_mean, 1.5)

