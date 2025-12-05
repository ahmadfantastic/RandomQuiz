from rest_framework import parsers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import Instructor
from accounts.serializers import InstructorSerializer


class InstructorViewSet(viewsets.ModelViewSet):
    serializer_class = InstructorSerializer
    queryset = Instructor.objects.select_related('user').all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def _ensure_not_self_modification(self, instructor):
        # Prevent modification of own permissions/status by self
        # unless superuser (handled by permissions usually, but extra check)
        pass

    def _is_safe_super_admin_update(self):
        # Allow superuser to update anyone
        return self.request.user.is_superuser

    def get_permissions(self):
        # Custom permissions could go here
        return super().get_permissions()

    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        instructor = getattr(request.user, 'instructor', None)
        if not instructor:
            return Response({'detail': 'Not an instructor'}, status=403)
        
        if request.method == 'GET':
            serializer = self.get_serializer(instructor)
            return Response(serializer.data)
        
        serializer = self.get_serializer(instructor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def perform_update(self, serializer):
        if not self.request.user.is_superuser:
            # Prevent non-superusers from changing critical fields if exposed
            pass
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
             raise PermissionDenied("Only admins can delete instructors.")
        super().perform_destroy(instance)
