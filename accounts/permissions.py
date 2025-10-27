from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Allow access only to admin users.
    """
    def has_permission(self, request, view):
        return (
            request.user 
            and request.user.is_authenticated 
            and getattr(request.user, 'role', None) == 'admin'
        )


class IsUser(permissions.BasePermission):
    """
    Allow access only to regular users.
    """
    def has_permission(self, request, view):
        return (
            request.user 
            and request.user.is_authenticated 
            and getattr(request.user, 'role', None) == 'user'
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allow only admins (owners) to edit or delete.
    Regular users can only read.
    """
    def has_object_permission(self, request, view, obj):
        # Read-only permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for admins
        return (
            request.user 
            and request.user.is_authenticated 
            and getattr(request.user, 'role', None) == 'admin'
        )