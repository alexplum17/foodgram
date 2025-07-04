"""backend/api/permissions.py."""


from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Позволяет только автору редактировать/удалять объект."""

    def has_object_permission(self, request, view, obj):
        """Позволяет только автору редактировать/удалять объект."""
        return request.method in permissions.SAFE_METHODS or (
            obj.author == request.user)
