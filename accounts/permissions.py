from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Allows access only to authenticated users
    whose account role is admin.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )
