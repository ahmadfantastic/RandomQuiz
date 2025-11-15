from django.contrib import admin
from .models import ProblemBank, Problem


class ProblemInline(admin.TabularInline):
    model = Problem
    extra = 0


@admin.register(ProblemBank)
class ProblemBankAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner')
    inlines = [ProblemInline]


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('problem_bank', 'order_in_bank')
    list_filter = ('problem_bank',)
