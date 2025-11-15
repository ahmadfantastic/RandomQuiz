from django.contrib import admin

from .models import Quiz, QuizSlot, QuizSlotProblemBank, QuizAttempt, QuizAttemptSlot


class QuizSlotInline(admin.TabularInline):
    model = QuizSlot
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'start_time', 'end_time', 'public_id')
    inlines = [QuizSlotInline]
    filter_horizontal = ('allowed_instructors',)


class QuizSlotProblemInline(admin.TabularInline):
    model = QuizSlotProblemBank
    extra = 0


@admin.register(QuizSlot)
class QuizSlotAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'label', 'order', 'problem_bank')
    inlines = [QuizSlotProblemInline]


@admin.register(QuizSlotProblemBank)
class QuizSlotProblemBankAdmin(admin.ModelAdmin):
    list_display = ('quiz_slot', 'problem')


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'student_identifier', 'started_at', 'completed_at')


@admin.register(QuizAttemptSlot)
class QuizAttemptSlotAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'slot', 'assigned_problem', 'answered_at')
