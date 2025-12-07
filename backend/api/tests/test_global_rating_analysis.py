from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Instructor
from problems.models import Problem, ProblemBank
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizRatingScaleOption
from django.contrib.auth.models import User
import json

class GlobalRatingAnalysisTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        # Problem Bank & Problems
        self.bank = ProblemBank.objects.create(name="Bank", owner=self.instructor)
        self.p1 = Problem.objects.create(problem_bank=self.bank, statement="P1", order_in_bank=1)
        self.p2 = Problem.objects.create(problem_bank=self.bank, statement="P2", order_in_bank=2)
        
        # Create Quiz 1
        self.quiz1 = Quiz.objects.create(
            title="Quiz 1",
            owner=self.instructor
        )
        
        # Criterion "Quality" for Quiz 1
        self.q1_c1 = QuizRatingCriterion.objects.create(
            quiz=self.quiz1,
            criterion_id="quality_1",
            name="Quality",
            order=1,
            instructor_criterion_code="QUAL" # Needed for global aggregation logic map
        )
        
        # Scale for Quiz 1: 1-3
        self.q1_s1 = QuizRatingScaleOption.objects.create(quiz=self.quiz1, value=1.0, label="Low", order=1, mapped_value=1.0)
        self.q1_s2 = QuizRatingScaleOption.objects.create(quiz=self.quiz1, value=2.0, label="Med", order=2, mapped_value=2.0)
        self.q1_s3 = QuizRatingScaleOption.objects.create(quiz=self.quiz1, value=3.0, label="High", order=3, mapped_value=3.0)
        
        # Slot for Quiz 1
        self.q1_slot = QuizSlot.objects.create(
            quiz=self.quiz1,
            response_type=QuizSlot.ResponseType.RATING,
            label="Rate Q1",
            order=1,
            problem_bank=self.bank
        )
        
        # Create Quiz 2
        self.quiz2 = Quiz.objects.create(
            title="Quiz 2",
            owner=self.instructor
        )
        
        # Criterion "Quality" for Quiz 2 (Same name, different ID)
        self.q2_c1 = QuizRatingCriterion.objects.create(
            quiz=self.quiz2,
            criterion_id="quality_2",
            name="Quality", 
            order=1,
            instructor_criterion_code="QUAL"
        )
        
        # Scale for Quiz 2: 1-3
        self.q2_s1 = QuizRatingScaleOption.objects.create(quiz=self.quiz2, value=1.0, label="Bad", order=1, mapped_value=1.0)
        self.q2_s2 = QuizRatingScaleOption.objects.create(quiz=self.quiz2, value=2.0, label="OK", order=2, mapped_value=2.0)
        self.q2_s3 = QuizRatingScaleOption.objects.create(quiz=self.quiz2, value=3.0, label="Good", order=3, mapped_value=3.0)

        # Slot for Quiz 2
        self.q2_slot = QuizSlot.objects.create(
            quiz=self.quiz2,
            response_type=QuizSlot.ResponseType.RATING,
            label="Rate Q2",
            order=1,
            problem_bank=self.bank
        )
        


        # Criterion "Accuracy" for Quiz 1 (Order 2) - Alphabetically first, but Order second
        self.q1_c2 = QuizRatingCriterion.objects.create(
            quiz=self.quiz1,
            criterion_id="accuracy_1",
            name="Accuracy",
            order=2,
            instructor_criterion_code="ACC"
        )

    def test_global_rating_distribution_aggregation(self):
        # Create attempts and ratings
        
        # Attempt 1 for Quiz 1: Quality=1 (Low), Accuracy=2
        a1 = QuizAttempt.objects.create(quiz=self.quiz1, student_identifier="s1", completed_at="2023-01-01T12:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=a1, slot=self.q1_slot, assigned_problem=self.p1,
            answer_data={'ratings': {self.q1_c1.criterion_id: 1.0, self.q1_c2.criterion_id: 2.0}}
        )
        
        # Attempt 2 for Quiz 1: Quality=2 (Med)
        a2 = QuizAttempt.objects.create(quiz=self.quiz1, student_identifier="s2", completed_at="2023-01-01T12:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=a2, slot=self.q1_slot, assigned_problem=self.p2,
            answer_data={'ratings': {self.q1_c1.criterion_id: 2.0}}
        )
        
        # Attempt 3 for Quiz 2: Quality=3 (Good) -> Mapped Value in DB is 3.0, but let's change it to test raw usage
        # Change mapped_value of q2_s3 to 10.0. If logic uses raw, we should see 3.0. If mapped, 10.0.
        self.q2_s3.mapped_value = 10.0
        self.q2_s3.save()
        
        a3 = QuizAttempt.objects.create(quiz=self.quiz2, student_identifier="s3", completed_at="2023-01-01T12:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=a3, slot=self.q2_slot, assigned_problem=self.p1,
            answer_data={'ratings': {self.q2_c1.criterion_id: 3.0}}
        )
        
        # Attempt 4 for Quiz 2: Quality=1 (Bad)
        a4 = QuizAttempt.objects.create(quiz=self.quiz2, student_identifier="s4", completed_at="2023-01-01T12:00:00Z")
        QuizAttemptSlot.objects.create(
            attempt=a4, slot=self.q2_slot, assigned_problem=self.p2,
            answer_data={'ratings': {self.q2_c1.criterion_id: 1.0}}
        )
        
        # Expected Aggregation for "Quality":
        # Value 1.0: 2 counts (Low, Bad)
        # Value 2.0: 1 count (Med)
        # Value 3.0: 1 count (Good) - RAW VALUE used, not mapped 10.0
        # Total: 4
        # Mean: (1+1+2+3)/4 = 1.75
        
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('global_rating_distribution', data)
        global_dist = data['global_rating_distribution']
        self.assertIn('criteria', global_dist)
        
        criteria_list = global_dist['criteria']
        
        # VERIFY SORTING: Quality (order 1) should be before Accuracy (order 2), even though "A" < "Q"
        self.assertEqual(len(criteria_list), 2)
        self.assertEqual(criteria_list[0]['name'], 'Quality')
        self.assertEqual(criteria_list[1]['name'], 'Accuracy')
        
        # Find Quality
        quality_data = next((c for c in criteria_list if c['name'] == 'Quality'), None)
        self.assertIsNotNone(quality_data)
        
        self.assertEqual(quality_data['total'], 4)
        self.assertEqual(quality_data['mean'], 1.75)
        
        # Check distribution items
        dist = quality_data['distribution']
        # Should have entries for 1.0, 2.0, 3.0
        v1 = next((d for d in dist if d['value'] == 1.0), None)
        v2 = next((d for d in dist if d['value'] == 2.0), None)
        v3 = next((d for d in dist if d['value'] == 3.0), None)
        
        self.assertIsNotNone(v1)
        self.assertEqual(v1['count'], 2)
        
        self.assertIsNotNone(v2)
        self.assertEqual(v2['count'], 1)
        
        self.assertIsNotNone(v3)
        self.assertEqual(v3['count'], 1) # Raw value verified

        # VERIFY ZERO COUNTS:
        # Quiz 1 Scale is 1, 2, 3.
        # "Quality" has ratings 1, 2. (Count of 3 is 0)
        # Wait, q1_slot attempts:
        # a1: Q=1
        # a2: Q=2
        # q2_slot attempts:
        # a3: Q=3 (mapped to 10 but we use raw so 3)
        # a4: Q=1
        # Total Quality counts: 1:2, 2:1, 3:1. No zeros here.
        
        # Let's add a new scale option to Quiz 1 "4.0 - Super" that no one used.
        QuizRatingScaleOption.objects.create(quiz=self.quiz1, value=4.0, label="Super", order=4, mapped_value=4.0)
        
        # Now re-fetch. "Quality" for Quiz 1 has scale 1,2,3,4.
        # "Quality" for Quiz 2 has scale 1,2,3.
        # Merged scale for "Quality" should be 1,2,3,4.
        # Count for 4.0 shoud be 0.
        
        url = reverse('global-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        global_dist = data['global_rating_distribution']
        criteria_list = global_dist['criteria']
        quality_data = next((c for c in criteria_list if c['name'] == 'Quality'), None)
        
        dist = quality_data['distribution']
        # Should have 4 entries now: 1, 2, 3, 4
        # Note: Depending on set behavior, order might vary unless sorted. Code sorts.
        self.assertEqual(len(dist), 4)
        
        v4 = next((d for d in dist if d['value'] == 4.0), None)
        self.assertIsNotNone(v4)
        self.assertEqual(v4['count'], 0)
        self.assertEqual(v4['label'], "Super")

