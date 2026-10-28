
from rest_framework.permissions import BasePermission

from .models import UserProfile


class IsAdminUser(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return UserProfile.objects.filter(
            user=request.user,
            role=UserProfile.Role.ADMIN,
        ).exists()
