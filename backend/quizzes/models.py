import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Instructor
from problems.models import ProblemBank, Problem


class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='owned_quizzes')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    public_id = models.SlugField(unique=True, default=uuid.uuid4, editable=False)
    allowed_instructors = models.ManyToManyField(Instructor, related_name='shared_quizzes', blank=True)

    def __str__(self) -> str:
        return self.title

    def is_open(self) -> bool:
        if self.start_time is None:
            return False
        now = timezone.now()
        if now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True


class QuizSlot(models.Model):
    class ResponseType(models.TextChoices):
        OPEN_TEXT = 'open_text', 'Open-ended answer'
        RATING = 'rating', 'Problem rating'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='slots')
    label = models.CharField(max_length=255)
    instruction = models.TextField(
        blank=True,
        default='',
        help_text='Guidance shown to students when they respond to this slot',
    )
    order = models.IntegerField()
    problem_bank = models.ForeignKey(
        ProblemBank,
        on_delete=models.PROTECT,
        related_name='slots',
    )
    response_type = models.CharField(max_length=32, choices=ResponseType.choices, default=ResponseType.OPEN_TEXT)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['quiz', 'order'], name='unique_quiz_slot_order')
        ]

    def __str__(self) -> str:
        return f"{self.quiz.title}: {self.label}"

    def save(self, *args, **kwargs):
        if self.order is None:
            last_order = (
                self.__class__.objects.filter(quiz=self.quiz).aggregate(models.Max('order'))['order__max'] or 0
            )
            self.order = last_order + 1
        return super().save(*args, **kwargs)


class QuizSlotProblemBank(models.Model):
    quiz_slot = models.ForeignKey(QuizSlot, on_delete=models.CASCADE, related_name='slot_problems')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='slot_links')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['quiz_slot', 'problem'], name='unique_slot_problem_link')
        ]

    def clean(self):
        if self.problem.problem_bank_id != self.quiz_slot.problem_bank_id:
            raise ValidationError('Problem must belong to the slot\'s problem bank')

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student_identifier = models.CharField(max_length=255)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    extra_info = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Attempt {self.id} on {self.quiz.title}"


class QuizAttemptSlot(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='attempt_slots')
    slot = models.ForeignKey(QuizSlot, on_delete=models.CASCADE, related_name='attempt_slots')
    assigned_problem = models.ForeignKey(Problem, on_delete=models.PROTECT)
    answer_data = models.JSONField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['attempt', 'slot'], name='unique_attempt_slot_entry')
        ]

    def __str__(self) -> str:
        return f"Attempt {self.attempt_id} - {self.slot.label}"
