from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import Instructor
from quizzes.models import Quiz, QuizSlot
from problems.models import ProblemBank

class QuizTests(APITestCase):
    def setUp(self):
        self.username = 'instructor'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        self.quiz_list_url = reverse('quiz-list')

    def test_create_quiz(self):
        data = {
            'title': 'Test Quiz',
            'description': 'A test quiz'
        }
        response = self.client.post(self.quiz_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Quiz.objects.count(), 1)
        self.assertEqual(Quiz.objects.get().title, 'Test Quiz')
        self.assertEqual(Quiz.objects.get().owner, self.instructor)

    def test_list_quizzes(self):
        Quiz.objects.create(title='Quiz 1', owner=self.instructor)
        Quiz.objects.create(title='Quiz 2', owner=self.instructor)
        
        response = self.client.get(self.quiz_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_update_quiz(self):
        quiz = Quiz.objects.create(title='Old Title', owner=self.instructor)
        url = reverse('quiz-detail', args=[quiz.id])
        data = {'title': 'New Title'}
        
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        quiz.refresh_from_db()
        self.assertEqual(quiz.title, 'New Title')

    def test_delete_quiz(self):
        quiz = Quiz.objects.create(title='To Delete', owner=self.instructor)
        url = reverse('quiz-detail', args=[quiz.id])
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_open_quiz_validation(self):
        # Quiz needs slots and problems to be opened
        quiz = Quiz.objects.create(title='Empty Quiz', owner=self.instructor)
        url = reverse('quiz-open', args=[quiz.id])
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Add at least one slot', response.data['detail'])

class QuizSlotTests(APITestCase):
    def setUp(self):
        self.username = 'instructor'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.instructor = Instructor.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        self.quiz = Quiz.objects.create(title='My Quiz', owner=self.instructor)
        self.bank = ProblemBank.objects.create(name='My Bank', owner=self.instructor)
        from problems.models import Problem
        Problem.objects.create(problem_bank=self.bank, statement='Q1', order_in_bank=1)
        self.slots_url = reverse('quiz-slots', args=[self.quiz.id])

    def test_create_slot(self):
        data = {
            'label': 'Slot 1',
            'problem_bank': self.bank.id,
            'response_type': 'open_text'
        }
        # Checking model for response_type choices would be good, but assuming standard for now or string.
        # Actually, let's check QuizSlot model if possible, but I'll assume 'text' or similar is fine or it defaults.
        # Wait, I should check what fields are required.
        # Looking at views.py, QuizSlotSerializer is used.
        
        response = self.client.post(self.slots_url, data)
        if response.status_code != status.HTTP_201_CREATED:
             print(response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(QuizSlot.objects.count(), 1)
        self.assertEqual(QuizSlot.objects.get().label, 'Slot 1')

    def test_list_slots(self):
        QuizSlot.objects.create(quiz=self.quiz, label='Slot A', problem_bank=self.bank, order=1)
        QuizSlot.objects.create(quiz=self.quiz, label='Slot B', problem_bank=self.bank, order=2)
        
        response = self.client.get(self.slots_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
