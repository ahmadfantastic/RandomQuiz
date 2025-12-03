from django.db import models
from accounts.models import Instructor


class ProblemBank(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(Instructor, on_delete=models.SET_NULL, null=True, blank=True, related_name='problem_banks')

    def __str__(self) -> str:
        return self.name

    def get_rubric(self) -> dict:
        scale_options = list(self.rating_scale_options.all())
        criteria_entries = list(self.rating_criteria.all())
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


class Problem(models.Model):
    problem_bank = models.ForeignKey(ProblemBank, on_delete=models.CASCADE, related_name='problems')
    order_in_bank = models.IntegerField()
    group = models.CharField(max_length=255, blank=True, null=True)
    statement = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['problem_bank', 'order_in_bank'], name='unique_problem_order_in_bank')
        ]
        ordering = ['order_in_bank']

    def __str__(self) -> str:
        return f"Problem {self.order_in_bank} ({self.problem_bank.name})"

    @property
    def display_label(self) -> str:
        return f"Problem {self.order_in_bank}"


class ProblemBankRatingScaleOption(models.Model):
    problem_bank = models.ForeignKey(ProblemBank, on_delete=models.CASCADE, related_name='rating_scale_options')
    order = models.PositiveIntegerField()
    value = models.FloatField()
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['problem_bank', 'value'], name='unique_bank_scale_value')
        ]

    def __str__(self) -> str:
        return f"{self.problem_bank.name}: {self.label} ({self.value})"


class ProblemBankRatingCriterion(models.Model):
    problem_bank = models.ForeignKey(ProblemBank, on_delete=models.CASCADE, related_name='rating_criteria')
    order = models.PositiveIntegerField()
    criterion_id = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    description = models.TextField()

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['problem_bank', 'criterion_id'], name='unique_bank_criterion_id')
        ]

    def __str__(self) -> str:
        return f"{self.problem_bank.name}: {self.criterion_id}"


class InstructorProblemRating(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='instructor_ratings')
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='problem_ratings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['problem', 'instructor'], name='unique_instructor_problem_rating')
        ]

    def __str__(self) -> str:
        return f"Rating by {self.instructor} for {self.problem}"


class InstructorProblemRatingEntry(models.Model):
    rating = models.ForeignKey(InstructorProblemRating, on_delete=models.CASCADE, related_name='entries')
    criterion_id = models.CharField(max_length=32)
    value = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['rating', 'criterion_id'], name='unique_rating_entry_criterion')
        ]

    def __str__(self) -> str:
        return f"{self.rating}: {self.criterion_id}={self.value}"
