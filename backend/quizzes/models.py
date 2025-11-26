import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Instructor
from problems.models import ProblemBank, Problem
from .response_config import load_response_config


class Quiz(models.Model):
    IDENTITY_INSTRUCTION_DEFAULT = 'Required so your instructor can match your submission.'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    identity_instruction = models.TextField(
        blank=True,
        default=IDENTITY_INSTRUCTION_DEFAULT,
        help_text='Instructions shown to students when confirming their identity.',
    )
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

    def get_rubric(self) -> dict:
        scale_options = list(self.rating_scale_options.all())
        criteria_entries = list(self.rating_criteria.all())
        if scale_options and criteria_entries:
            return {
                'scale': [{'value': option.value, 'label': option.label} for option in scale_options],
                'criteria': [
                    {
                        'id': criterion.criterion_id,
                        'name': criterion.name,
                        'description': criterion.description,
                    }
                    for criterion in criteria_entries
                ],
            }
        try:
            return load_response_config()
        except FileNotFoundError:
            return {'scale': [], 'criteria': []}


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


class QuizAttemptInteraction(models.Model):
    class EventType(models.TextChoices):
        TYPING = 'typing', 'Typing input'
        RATING_SELECTION = 'rating_selection', 'Rating selection'

    attempt_slot = models.ForeignKey(
        QuizAttemptSlot,
        on_delete=models.CASCADE,
        related_name='interactions',
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"{self.attempt_slot} {self.event_type} @ {self.created_at.isoformat()}"


class QuizRatingScaleOption(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='rating_scale_options')
    order = models.PositiveIntegerField()
    value = models.IntegerField()
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['quiz', 'value'], name='unique_quiz_scale_value')
        ]

    def __str__(self) -> str:
        return f"{self.quiz.title}: {self.label} ({self.value})"


class QuizRatingCriterion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='rating_criteria')
    order = models.PositiveIntegerField()
    criterion_id = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    description = models.TextField()

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['quiz', 'criterion_id'], name='unique_quiz_criterion_id')
        ]

    def __str__(self) -> str:
        return f"{self.quiz.title}: {self.criterion_id}"


def _load_default_rubric_config():
    try:
        return load_response_config()
    except FileNotFoundError:
        return {'scale': [], 'criteria': []}


def _build_scale_entries(config):
    entries = []
    for index, option in enumerate(config.get('scale') or []):
        value = option.get('value')
        label = option.get('label')
        if value is None or label is None:
            continue
        entries.append({'order': index, 'value': value, 'label': label})
    return entries


def _build_criteria_entries(config):
    entries = []
    for index, criterion in enumerate(config.get('criteria') or []):
        criterion_id = str(criterion.get('id') or '').strip()
        name = criterion.get('name')
        description = criterion.get('description')
        if not criterion_id or name is None or description is None:
            continue
        entries.append(
            {'order': index, 'criterion_id': criterion_id, 'name': name, 'description': description}
        )
    return entries


def create_default_quiz_rubric(quiz):
    if quiz.rating_scale_options.exists() or quiz.rating_criteria.exists():
        return
    config = _load_default_rubric_config()
    scale_entries = _build_scale_entries(config)
    criteria_entries = _build_criteria_entries(config)
    if scale_entries:
        QuizRatingScaleOption.objects.bulk_create(
            [
                QuizRatingScaleOption(quiz=quiz, order=entry['order'], value=entry['value'], label=entry['label'])
                for entry in scale_entries
            ]
        )
    if criteria_entries:
        QuizRatingCriterion.objects.bulk_create(
            [
                QuizRatingCriterion(
                    quiz=quiz,
                    order=entry['order'],
                    criterion_id=entry['criterion_id'],
                    name=entry['name'],
                    description=entry['description'],
                )
                for entry in criteria_entries
            ]
        )

class GradingRubric(models.Model):
    quiz = models.OneToOneField(Quiz, on_delete=models.CASCADE, related_name='grading_rubric')

    def __str__(self) -> str:
        return f"Rubric for {self.quiz.title}"


class GradingRubricItem(models.Model):
    rubric = models.ForeignKey(GradingRubric, on_delete=models.CASCADE, related_name='items')
    order = models.PositiveIntegerField()
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['rubric', 'order'], name='unique_rubric_item_order')
        ]

    def __str__(self) -> str:
        return f"{self.rubric}: {self.label}"


class GradingRubricItemLevel(models.Model):
    rubric_item = models.ForeignKey(GradingRubricItem, on_delete=models.CASCADE, related_name='levels')
    order = models.PositiveIntegerField()
    points = models.FloatField()
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['rubric_item', 'order'], name='unique_rubric_item_level_order')
        ]

    def __str__(self) -> str:
        return f"{self.rubric_item}: {self.label} ({self.points} pts)"


class QuizSlotGrade(models.Model):
    attempt_slot = models.OneToOneField(QuizAttemptSlot, on_delete=models.CASCADE, related_name='grade')
    grader = models.ForeignKey(Instructor, on_delete=models.SET_NULL, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Grade for {self.attempt_slot}"


class QuizSlotGradeItem(models.Model):
    grade = models.ForeignKey(QuizSlotGrade, on_delete=models.CASCADE, related_name='items')
    rubric_item = models.ForeignKey(GradingRubricItem, on_delete=models.CASCADE)
    selected_level = models.ForeignKey(GradingRubricItemLevel, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['grade', 'rubric_item'], name='unique_grade_rubric_item')
        ]

    def __str__(self) -> str:
        return f"{self.grade} - {self.rubric_item}: {self.selected_level.points} pts"
