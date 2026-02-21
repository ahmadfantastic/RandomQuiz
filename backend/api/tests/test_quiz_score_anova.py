from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User, Instructor
from problems.models import ProblemBank, Problem
from quizzes.models import (
    Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, 
    GradingRubric, GradingRubricItem, GradingRubricItemLevel,
    QuizSlotGrade, QuizSlotGradeItem
)

class QuizScoreANOVATest(APITestCase):
    def setUp(self):
        # Create user and instructor
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        # Create 2 Quizzes
        self.quiz1 = Quiz.objects.create(title="Quiz High", owner=self.instructor)
        self.quiz2 = Quiz.objects.create(title="Quiz Low", owner=self.instructor)

        # Rubric for grading (Per quiz in this model structure)
        self.rubric1 = GradingRubric.objects.create(quiz=self.quiz1)
        self.r_item1 = GradingRubricItem.objects.create(rubric=self.rubric1, label="Correctness", order=1)
        self.l_high1 = GradingRubricItemLevel.objects.create(rubric_item=self.r_item1, label="High", points=10, order=1)
        self.l_high1_var = GradingRubricItemLevel.objects.create(rubric_item=self.r_item1, label="High-ish", points=9, order=2)
        
        self.rubric2 = GradingRubric.objects.create(quiz=self.quiz2)
        self.r_item2 = GradingRubricItem.objects.create(rubric=self.rubric2, label="Correctness", order=1)
        self.l_low2 = GradingRubricItemLevel.objects.create(rubric_item=self.r_item2, label="Low", points=2, order=2)
        self.l_low2_var = GradingRubricItemLevel.objects.create(rubric_item=self.r_item2, label="Low-ish", points=3, order=3)

        # Slots
        self.bank = ProblemBank.objects.create(owner=self.instructor, name="Bank 1")
        self.prob = Problem.objects.create(problem_bank=self.bank, statement="P", order_in_bank=1)
        
        self.slot1 = QuizSlot.objects.create(quiz=self.quiz1, order=1, label="S1", problem_bank=self.bank, response_type=QuizSlot.ResponseType.OPEN_TEXT)
        self.slot2 = QuizSlot.objects.create(quiz=self.quiz2, order=1, label="S2", problem_bank=self.bank, response_type=QuizSlot.ResponseType.OPEN_TEXT)

        # Create attempts and grades
        # Quiz 1: High scores (mix of 10 and 9)
        for i in range(5):
            a = QuizAttempt.objects.create(quiz=self.quiz1, student_identifier=f"S1_{i}", completed_at="2024-01-01 12:00:00")
            aslot = QuizAttemptSlot.objects.create(attempt=a, slot=self.slot1, assigned_problem=self.prob, answer_data={'text': 'ans'})
            level = self.l_high1 if i % 2 == 0 else self.l_high1_var
            self.grade_attempt_slot(aslot, self.r_item1, level)

        # Quiz 2: Low scores (mix of 2 and 3)
        for i in range(5):
            a = QuizAttempt.objects.create(quiz=self.quiz2, student_identifier=f"S2_{i}", completed_at="2024-01-01 13:00:00")
            aslot = QuizAttemptSlot.objects.create(attempt=a, slot=self.slot2, assigned_problem=self.prob, answer_data={'text': 'ans'})
            level = self.l_low2 if i % 2 == 0 else self.l_low2_var
            self.grade_attempt_slot(aslot, self.r_item2, level)

    def grade_attempt_slot(self, attempt_slot, rubric_item, level):
        # Create Grade
        grade = QuizSlotGrade.objects.create(
            attempt_slot=attempt_slot,
            grader=self.instructor, # Needs to be Instructor instance
            
        )
        # Create Grade Item
        QuizSlotGradeItem.objects.create(
            grade=grade,
            rubric_item=rubric_item,
            selected_level=level
        )
        # Mark as graded (grade creation above is enough for the query usually, link via OneToOne)
        attempt_slot.refresh_from_db()

    def test_quiz_score_anova_significant(self):
        url = reverse('global-analysis-student')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # print(response.data.keys()) 
        self.assertIn('quiz_score_anova', response.data)
        
        anova = response.data['quiz_score_anova']
        
        # If anova is null, it means calculation failed or conditions not met.
        # We expect it to be present.
        self.assertIsNotNone(anova, "Quiz Score ANOVA should not be None")
        
        self.assertTrue(anova['significant'], "Expected significant difference between High and Low scores")
        self.assertIsNotNone(anova['f_stat'])
        self.assertIsNotNone(anova['p_value'])
        self.assertEqual(len(anova['quizzes_included']), 2)
        self.assertIn("Quiz High", anova['quizzes_included'])
        self.assertIn("Quiz Low", anova['quizzes_included'])

        # Verify Std Dev in quiz_analysis
        self.assertIn('quiz_analysis', response.data)
        quizzes = response.data['quiz_analysis']['quizzes']
        
        # Quiz 1 has mixed scores 10 and 9. 
        # Mean = 9.5?
        # 3 * 10, 2 * 9 -> sum=48, mean=9.6
        # Vars: (10-9.6)^2 = 0.16 (x3) = 0.48
        # (9-9.6)^2 = 0.36 (x2) = 0.72
        # Sum Sq Diff = 1.2. 
        # Sample Var = 1.2 / 4 = 0.3
        # Std Dev = sqrt(0.3) approx 0.5477
        
        q1 = next(q for q in quizzes if q['title'] == "Quiz High")
        self.assertIsNotNone(q1['score_std_dev'])
        self.assertGreater(q1['score_std_dev'], 0)
        self.assertAlmostEqual(q1['score_std_dev'], 0.5477, places=3)
