from rest_framework import viewsets
from accounts.permissions import IsInstructor
from problems.models import Rubric
from problems.serializers import RubricSerializer
from accounts.models import ensure_instructor

class RubricViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInstructor]
    serializer_class = RubricSerializer

    def get_queryset(self):
        # Return all rubrics
        return Rubric.objects.all()

    def perform_create(self, serializer):
        instructor = ensure_instructor(self.request.user)
        serializer.save(owner=instructor)
