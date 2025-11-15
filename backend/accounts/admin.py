from django.contrib import admin
from .models import Instructor


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_admin_instructor')
    search_fields = ('user__username', 'user__email')
    list_filter = ('is_admin_instructor',)
