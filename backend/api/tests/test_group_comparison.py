
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from accounts.models import Instructor
from problems.models import ProblemBank, Problem, Rubric, RubricCriterion, RubricScaleOption, InstructorProblemRating, InstructorProblemRatingEntry
import numpy as np

class GroupComparisonDebugTests(APITestCase):
    def setUp(self):
        # Create user and instructor
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        # Create Rubric
        self.rubric = Rubric.objects.create(name="Test Rubric")
        self.criterion_normal = RubricCriterion.objects.create(rubric=self.rubric, name="Normal Criterion", criterion_id="normal", order=1, description="Normal")
        self.criterion_zero_var = RubricCriterion.objects.create(rubric=self.rubric, name="Zero Var Criterion", criterion_id="zerovar", order=2, description="Zero Var")
        self.criterion_low_n = RubricCriterion.objects.create(rubric=self.rubric, name="Low N Criterion", criterion_id="lown", order=3, description="Low N")
        
        # Scale options
        for val in range(1, 6):
            RubricScaleOption.objects.create(rubric=self.rubric, value=val, label=str(val), order=val)

        # Create Problem Bank
        self.bank = ProblemBank.objects.create(name="Test Bank", owner=self.instructor, rubric=self.rubric)

        # Create Problems in Groups
        # Group A: 3 problems
        # Group B: 3 problems
        self.probs_a = []
        for i in range(3):
            p = Problem.objects.create(problem_bank=self.bank, statement=f"Prob A{i}", group="Group A", order_in_bank=i+1)
            self.probs_a.append(p)
            
        self.probs_b = []
        for i in range(3):
            p = Problem.objects.create(problem_bank=self.bank, statement=f"Prob B{i}", group="Group B", order_in_bank=i+4)
            self.probs_b.append(p)

        self.url = reverse('bank-analysis', args=[self.bank.id])

    def rate_problem(self, problem, criterion_values):
        rating, _ = InstructorProblemRating.objects.get_or_create(problem=problem, instructor=self.instructor)
        for c_id, val in criterion_values.items():
            if c_id == 'normal': crit = self.criterion_normal
            elif c_id == 'zerovar': crit = self.criterion_zero_var
            elif c_id == 'lown': crit = self.criterion_low_n
            else: continue
            
            option = RubricScaleOption.objects.get(rubric=self.rubric, value=val)
            InstructorProblemRatingEntry.objects.create(rating=rating, criterion=crit, scale_option=option)

    def test_group_comparison_missing_criteria(self):
        # 1. Normal Criterion: Different ratings -> Should appear
        # Group A: 1, 2, 3
        # Group B: 3, 4, 5
        for i, p in enumerate(self.probs_a):
            self.rate_problem(p, {'normal': i+1})
        for i, p in enumerate(self.probs_b):
            self.rate_problem(p, {'normal': i+3})

        # 2. Zero Var Criterion: Same ratings -> p-value NaN? -> Might be missing
        # Group A: 3, 3, 3
        # Group B: 3, 3, 3
        for p in self.probs_a:
            self.rate_problem(p, {'zerovar': 3})
        for p in self.probs_b:
            self.rate_problem(p, {'zerovar': 3})
            
        # 3. Low N Criterion: Only 1 rating in Group A -> Should be missing because code checks len > 1
        self.rate_problem(self.probs_a[0], {'lown': 2})
        # Rate all in Group B
        for p in self.probs_b:
            self.rate_problem(p, {'lown': 4})

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        import json
        print(json.dumps(data, indent=2))
        
        # Check instructors data
        inst_data = data['instructors'][0]
        comparisons = inst_data['group_comparisons']
        
        found_criteria = [c['criteria_id'] for c in comparisons]
        
        print("Found Criteria in Comparisons:", found_criteria)
        
        # Expect 'normal' to be present
        self.assertIn('normal', found_criteria)
        self.assertIn('zerovar', found_criteria)
        self.assertIn('lown', found_criteria)
        
        # Check specific values
        zerovar_comp = next(c for c in comparisons if c['criteria_id'] == 'zerovar')
        self.assertEqual(zerovar_comp['p_value'], 1.0)
        
        lown_comp = next(c for c in comparisons if c['criteria_id'] == 'lown')
        self.assertIsNone(lown_comp['p_value'])
        
