from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Allow access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsUser(permissions.BasePermission):
    """
    Allow access only to regular users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'user'


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of a profile to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.user == request.user