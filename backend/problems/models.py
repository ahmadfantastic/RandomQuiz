from django.db import models
from accounts.models import Instructor


class ProblemBank(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(Instructor, on_delete=models.SET_NULL, null=True, blank=True, related_name='problem_banks')

    def __str__(self) -> str:
        return self.name


class Problem(models.Model):
    problem_bank = models.ForeignKey(ProblemBank, on_delete=models.CASCADE, related_name='problems')
    order_in_bank = models.IntegerField()
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
