"""Django-allauth adapter hooks for QuickScale organizations."""

from __future__ import annotations

from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

from .models import Organization, OrganizationMembership

try:
    from quickscale_modules_auth.adapters import (  # type: ignore
        QuickscaleAccountAdapter as _BaseAccountAdapter,
    )
except ImportError:  # pragma: no cover - auth is optional in isolated module tests
    _BaseAccountAdapter = DefaultAccountAdapter


class OrgsAccountAdapter(_BaseAccountAdapter):
    """Account adapter that applies the org-aware post-auth redirect contract."""

    def get_login_redirect_url(self, request: Any) -> str:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return super().get_login_redirect_url(request)

        saas_mode = getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"
        if (
            not saas_mode
            and not OrganizationMembership.objects.filter(user=user).exists()
        ):
            Organization.objects.create_personal_for(user)
            return super().get_login_redirect_url(request)
        if saas_mode and not OrganizationMembership.objects.filter(user=user).exists():
            return "/orgs/new/"
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request: Any) -> str:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return super().get_signup_redirect_url(request)

        saas_mode = getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"
        if not saas_mode:
            Organization.objects.create_personal_for(user)
            return "/"

        if OrganizationMembership.objects.filter(user=user).exists():
            return super().get_signup_redirect_url(request)
        return "/orgs/new/"
