"""DRF permission classes for the blog module."""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsStaffUser(BasePermission):
    """Allow only staff accounts.

    The blog automation API is the module's platform-level write path
    (Module Conventions rule 19's operator path), so ``is_staff`` gates it
    until org-role authorization replaces it for tenant-scoped surfaces.
    """

    message = "Staff access required"

    def has_permission(self, request: Request, view: APIView) -> bool:
        del view
        user = request.user
        return bool(
            getattr(user, "is_authenticated", False)
            and getattr(user, "is_staff", False)
        )
