from django.db import models
from accounts.models import Instructor


class Rubric(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(Instructor, on_delete=models.CASCADE, null=True, blank=True, related_name='rubrics')

    def __str__(self) -> str:
        return self.name

class RubricScaleOption(models.Model):
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name='scale_options')
    order = models.PositiveIntegerField()
    value = models.FloatField()
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['rubric', 'value'], name='unique_rubric_scale_value')
        ]

class RubricCriterion(models.Model):
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name='criteria')
    order = models.PositiveIntegerField()
    criterion_id = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    description = models.TextField()
    weight = models.IntegerField(default=1)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['rubric', 'criterion_id'], name='unique_rubric_criterion_id')
        ]


class ProblemBank(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(Instructor, on_delete=models.SET_NULL, null=True, blank=True, related_name='problem_banks')
    rubric = models.ForeignKey(Rubric, on_delete=models.SET_NULL, null=True, blank=True, related_name='problem_banks')

    def __str__(self) -> str:
        return self.name

    def get_rubric(self) -> dict:
        if not self.rubric:
            return {'scale': [], 'criteria': [], 'rubric_id': None, 'rubric_name': None}

        scale_options = list(self.rubric.scale_options.all())
        criteria_entries = list(self.rubric.criteria.all())
        
        return {
            'scale': [{'value': option.value, 'label': option.label} for option in scale_options],
            'criteria': [
                {
                    'id': criterion.criterion_id,
                    'name': criterion.name,
                    'description': criterion.description,
                    'weight': getattr(criterion, 'weight', 1),
                }
                for criterion in criteria_entries
            ],
            'rubric_id': self.rubric.id,
            'rubric_name': self.rubric.name,
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
    criterion = models.ForeignKey(RubricCriterion, on_delete=models.CASCADE)
    scale_option = models.ForeignKey(RubricScaleOption, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['rating', 'criterion'], name='unique_rating_entry_criterion')
        ]

    def __str__(self) -> str:
        return f"{self.rating}: {self.criterion}={self.scale_option}"
