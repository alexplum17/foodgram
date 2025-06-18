"""backend/api/permissions.py."""


from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Позволяет только автору редактировать/удалять объект."""

    def has_object_permission(self, request, view, obj):
        """Позволяет только автору редактировать/удалять объект."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user
