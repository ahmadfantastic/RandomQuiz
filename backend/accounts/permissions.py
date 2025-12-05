from rest_framework.permissions import BasePermission


class IsInstructor(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or hasattr(request.user, 'instructor'))
        )


class IsAdminInstructor(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or (
                    hasattr(request.user, 'instructor')
                    and request.user.instructor.is_admin_instructor
                )
            )
        )


class IsSelfOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or hasattr(request.user, 'instructor'))
        )

    def has_object_permission(self, request, view, obj):
        # Allow superusers
        if request.user.is_superuser:
            return True

        # Allow admin instructors
        if hasattr(request.user, 'instructor') and request.user.instructor.is_admin_instructor:
            return True

        # Allow users to edit their own profile
        return obj.user == request.user
