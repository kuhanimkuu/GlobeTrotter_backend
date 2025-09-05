from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
   
    def has_object_permission(self, request, view, obj):
        # Read-only safe methods are allowed
        if request.method in permissions.SAFE_METHODS:
            return True
        # Admins can do anything
        if request.user and request.user.is_staff:
            return True
        # Object must have `user` attribute for ownership check
        return getattr(obj, "user", None) == request.user