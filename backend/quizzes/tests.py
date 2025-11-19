from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import Instructor
from problems.models import ProblemBank, Problem
from .models import Quiz, QuizSlot, QuizSlotProblemBank

User = get_user_model()

class QuizModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)

    def test_create_quiz(self):
        quiz = Quiz.objects.create(title='Test Quiz', owner=self.instructor)
        self.assertEqual(str(quiz), 'Test Quiz')
        self.assertFalse(quiz.is_open())

    def test_is_open_logic(self):
        quiz = Quiz.objects.create(title='Test Quiz', owner=self.instructor)
        
        # Not started
        self.assertFalse(quiz.is_open())
        
        # Started now
        quiz.start_time = timezone.now() - timezone.timedelta(minutes=1)
        self.assertTrue(quiz.is_open())
        
        # Ended
        quiz.end_time = timezone.now() - timezone.timedelta(seconds=1)
        self.assertFalse(quiz.is_open())

class QuizSlotModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.quiz = Quiz.objects.create(title='Test Quiz', owner=self.instructor)
        self.bank = ProblemBank.objects.create(name='Bank', owner=self.instructor)

    def test_create_slot(self):
        slot = QuizSlot.objects.create(quiz=self.quiz, label='Slot 1', problem_bank=self.bank, order=1)
        self.assertEqual(str(slot), 'Test Quiz: Slot 1')

    def test_slot_ordering_auto(self):
        slot1 = QuizSlot.objects.create(quiz=self.quiz, label='Slot 1', problem_bank=self.bank)
        slot2 = QuizSlot.objects.create(quiz=self.quiz, label='Slot 2', problem_bank=self.bank)
        self.assertEqual(slot1.order, 1)
        self.assertEqual(slot2.order, 2)

class QuizSlotProblemBankTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor', password='password')
        self.instructor = Instructor.objects.create(user=self.user)
        self.quiz = Quiz.objects.create(title='Test Quiz', owner=self.instructor)
        self.bank1 = ProblemBank.objects.create(name='Bank 1', owner=self.instructor)
        self.bank2 = ProblemBank.objects.create(name='Bank 2', owner=self.instructor)
        self.problem1 = Problem.objects.create(problem_bank=self.bank1, statement='P1', order_in_bank=1)
        self.problem2 = Problem.objects.create(problem_bank=self.bank2, statement='P2', order_in_bank=1)
        self.slot = QuizSlot.objects.create(quiz=self.quiz, label='Slot 1', problem_bank=self.bank1)

    def test_clean_valid(self):
        link = QuizSlotProblemBank(quiz_slot=self.slot, problem=self.problem1)
        link.clean() # Should not raise

    def test_clean_invalid_bank_mismatch(self):
        link = QuizSlotProblemBank(quiz_slot=self.slot, problem=self.problem2)
        with self.assertRaises(ValidationError):
            link.clean()
