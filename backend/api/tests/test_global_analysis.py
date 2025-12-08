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

    def test_global_analysis_rating_distribution_ids(self):
        # Create Quiz Setup
        from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption
        
        quiz = Quiz.objects.create(title="Test Quiz", owner=self.instructor)
        
        # Create Quiz Rating Criterion matching the Rubric one? 
        # Global Analysis aggregates by Name usually, or Code. 
        # The view maps quiz criteria. 
        # We need a QuizRatingCriterion.
        qc = QuizRatingCriterion.objects.create(
            quiz=quiz, order=1, criterion_id='Q_QUAL', name='Quality', instructor_criterion_code='QUAL'
        )
        
        # Scale
        QuizRatingScaleOption.objects.create(quiz=quiz, value=1, label="1", mapped_value=1, order=1)
        QuizRatingScaleOption.objects.create(quiz=quiz, value=5, label="5", mapped_value=5, order=2)
        
        # Slot
        slot = QuizSlot.objects.create(quiz=quiz, order=1, label="Rating Slot", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        
        # Attempt
        attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier="student1", completed_at="2023-01-01T12:00:00Z")
        
        # Answer with Rating
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1)
        
        # We need answer_data with ratings matching criterion_id
        QuizAttemptSlot.objects.create(
            attempt=attempt, 
            slot=slot, 
            assigned_problem=p1,
            answer_data={'ratings': {'Q_QUAL': 5}},
            answered_at="2023-01-01T12:00:00Z"
        )
        
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        dist_data = response.data.get('global_rating_distribution', {})
        criteria_dist = dist_data.get('criteria', [])
        
        self.assertTrue(len(criteria_dist) > 0)
        item = next((c for c in criteria_dist if c['name'] == 'Quality'), None)
        self.assertIsNotNone(item)
        
        # Verify ID is present and matches code
        self.assertIn('id', item)
        self.assertEqual(item['id'], 'QUAL')

    def test_grouped_rating_distribution(self):
        # Create problems in different groups
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1, group="Easy")
        p2 = Problem.objects.create(problem_bank=self.bank_a, statement="P2", order_in_bank=2, group="Easy")
        p3 = Problem.objects.create(problem_bank=self.bank_a, statement="P3", order_in_bank=3, group="Hard")
        p4 = Problem.objects.create(problem_bank=self.bank_a, statement="P4", order_in_bank=4, group="Hard")

        # Create Quiz Environment
        from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption
        quiz = Quiz.objects.create(title="Test Quiz Group", owner=self.instructor)
        
        # Link 'Quality' Criterion
        # Global Analysis aggregates by Name. 
        # API requires criteria mapping
        qc = QuizRatingCriterion.objects.create(
            quiz=quiz, order=1, criterion_id='Q_QUAL', name='Quality', instructor_criterion_code='QUAL'
        )
        
        # Scale (needed for View to process)
        QuizRatingScaleOption.objects.create(quiz=quiz, value=1, label="1", mapped_value=1, order=1)
        QuizRatingScaleOption.objects.create(quiz=quiz, value=5, label="5", mapped_value=5, order=2)

        # Slots
        slot1 = QuizSlot.objects.create(quiz=quiz, order=1, label="Slot1", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        slot2 = QuizSlot.objects.create(quiz=quiz, order=2, label="Slot2", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        slot3 = QuizSlot.objects.create(quiz=quiz, order=3, label="Slot3", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        slot4 = QuizSlot.objects.create(quiz=quiz, order=4, label="Slot4", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)

        # Attempt
        attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier="student1", completed_at="2023-01-01T12:00:00Z")
        
        # Add Answer Data (Student Ratings)
        # Using the criterion_id 'Q_QUAL' which maps to 'Quality'
        
        # P1 (Easy, Val 1)
        QuizAttemptSlot.objects.create(
            attempt=attempt, slot=slot1, assigned_problem=p1,
            answer_data={'ratings': {'Q_QUAL': 1}}, answered_at="2023-01-01T12:00:00Z"
        )
        
        # P2 (Easy, Val 1 => Count 2 for 'Easy'-'Quality'-1)
        QuizAttemptSlot.objects.create(
            attempt=attempt, slot=slot2, assigned_problem=p2,
            answer_data={'ratings': {'Q_QUAL': 1}}, answered_at="2023-01-01T12:00:00Z"
        )
        
        # P3 (Hard, Val 5)
        QuizAttemptSlot.objects.create(
            attempt=attempt, slot=slot3, assigned_problem=p3,
            answer_data={'ratings': {'Q_QUAL': 5}}, answered_at="2023-01-01T12:00:00Z"
        )
        
        # P4 (Hard, Val 5 => Count 2 for 'Hard'-'Quality'-5)
        QuizAttemptSlot.objects.create(
            attempt=attempt, slot=slot4, assigned_problem=p4,
            answer_data={'ratings': {'Q_QUAL': 5}}, answered_at="2023-01-01T12:00:00Z"
        )
            
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('grouped_rating_distribution', data)
        grouped_dist = data['grouped_rating_distribution']
        
        # Should have 2 groups
        self.assertEqual(len(grouped_dist), 2)
        
        easy_group = next((g for g in grouped_dist if g['group'] == 'Easy'), None)
        hard_group = next((g for g in grouped_dist if g['group'] == 'Hard'), None)
        
        self.assertIsNotNone(easy_group)
        self.assertIsNotNone(hard_group)
        
        # Check Easy Group Data for 'Quality'
        # Expect values 1 to have count 2 (from logic above)
        easy_criteria = easy_group['data']['criteria']
        qual_easy = next((c for c in easy_criteria if c['name'] == 'Quality'), None)
        self.assertIsNotNone(qual_easy)
        
        dist_easy = qual_easy['distribution']
        val_1 = next((v for v in dist_easy if v['value'] == 1.0), None)
        self.assertIsNotNone(val_1)
        self.assertEqual(val_1['count'], 2)
        
        # Check Hard Group Data for 'Quality'
        # Expect values 5 to have count 2
        hard_criteria = hard_group['data']['criteria']
        qual_hard = next((c for c in hard_criteria if c['name'] == 'Quality'), None)
        
        dist_hard = qual_hard['distribution']
        val_5 = next((v for v in dist_hard if v['value'] == 5.0), None)
        self.assertIsNotNone(val_5)
        self.assertEqual(val_5['count'], 2)

    def test_grouped_rating_distribution_zero_filling(self):
        # Verify that if a group doesn't use a scale value, it is still reported with count 0
        p1 = Problem.objects.create(problem_bank=self.bank_a, statement="P1", order_in_bank=1, group="GroupA")

        # Quiz Setup
        from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption
        quiz = Quiz.objects.create(title="Test Quiz Zero Fill", owner=self.instructor)
        
        qc = QuizRatingCriterion.objects.create(
            quiz=quiz, order=1, criterion_id='Q_QUAL', name='Quality', instructor_criterion_code='QUAL'
        )
        
        # Scale 1, 2, 3
        QuizRatingScaleOption.objects.create(quiz=quiz, value=1, label="1", mapped_value=1, order=1)
        QuizRatingScaleOption.objects.create(quiz=quiz, value=2, label="2", mapped_value=2, order=2)
        QuizRatingScaleOption.objects.create(quiz=quiz, value=3, label="3", mapped_value=3, order=3)

        slot = QuizSlot.objects.create(quiz=quiz, order=1, label="Slot", response_type=QuizSlot.ResponseType.RATING, problem_bank=self.bank_a)
        attempt = QuizAttempt.objects.create(quiz=quiz, student_identifier="student1", completed_at="2023-01-01T12:00:00Z")
        
        # Answer ONLY with value 1
        QuizAttemptSlot.objects.create(
            attempt=attempt, slot=slot, assigned_problem=p1,
            answer_data={'ratings': {'Q_QUAL': 1}}, answered_at="2023-01-01T12:00:00Z"
        )
        
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        grouped_dist = response.data.get('grouped_rating_distribution', [])
        group_a = next((g for g in grouped_dist if g['group'] == 'GroupA'), None)
        self.assertIsNotNone(group_a)
        
        # Check distribution for 'Quality'
        qual_dist = next((c['distribution'] for c in group_a['data']['criteria'] if c['name'] == 'Quality'), [])
        
        # Verify 1 is present (count 1)
        v1 = next((x for x in qual_dist if x['value'] == 1.0), None)
        self.assertIsNotNone(v1)
        self.assertEqual(v1['count'], 1)
        self.assertEqual(v1['label'], "1") # Label matches defined scale label
        
        # Verify 2 is present (count 0) - This confirms zero-filling works
        v2 = next((x for x in qual_dist if x['value'] == 2.0), None)
        self.assertIsNotNone(v2, "Value 2.0 (unused) should be present in distribution")
        self.assertEqual(v2['count'], 0)
        self.assertEqual(v2['label'], "2")
        
        # Verify 3 is present (count 0)
        v3 = next((x for x in qual_dist if x['value'] == 3.0), None)
        self.assertIsNotNone(v3, "Value 3.0 (unused) should be present in distribution")
        self.assertEqual(v3['count'], 0)
        self.assertEqual(v3['label'], "3")
