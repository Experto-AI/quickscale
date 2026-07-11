"""Django-allauth adapter hooks for QuickScale organizations."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .constants import (
    ORG_INVITATION_ACCEPT_URL_NAME,
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from .models import Organization, OrganizationInvitation, OrganizationMembership

from quickscale_modules_auth.adapters import (
    QuickscaleAccountAdapter as _BaseAccountAdapter,
)


class OrgsAccountAdapter(_BaseAccountAdapter):
    """Account adapter that applies the org-aware post-auth redirect contract."""

    @staticmethod
    def _get_pending_invitation_redirect_url(request: Any) -> str | None:
        session = getattr(request, "session", None)
        if session is None:
            return None

        invitation_token = session.get(PENDING_ORG_INVITATION_TOKEN_SESSION_KEY)
        if invitation_token is None:
            return None

        try:
            normalized_token = UUID(str(invitation_token))
        except (TypeError, ValueError, AttributeError):
            session.pop(PENDING_ORG_INVITATION_TOKEN_SESSION_KEY, None)
            return None

        if not OrganizationInvitation.objects.filter(
            token=normalized_token,
            accepted_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            session.pop(PENDING_ORG_INVITATION_TOKEN_SESSION_KEY, None)
            return None

        return reverse(
            ORG_INVITATION_ACCEPT_URL_NAME,
            kwargs={"token": normalized_token},
        )

    def get_login_redirect_url(self, request: Any) -> str:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return cast(str, super().get_login_redirect_url(request))

        # SA14.6: QUICKSCALE_MODE is guaranteed by the boot guard —
        # direct access, no fallback.
        saas_mode = settings.QUICKSCALE_MODE == "saas"
        has_membership = OrganizationMembership.objects.filter(user=user).exists()
        if not saas_mode and not has_membership:
            Organization.objects.create_personal_for(user)
            return cast(str, super().get_login_redirect_url(request))

        if saas_mode:
            pending_invitation_redirect = self._get_pending_invitation_redirect_url(
                request
            )
            if pending_invitation_redirect is not None:
                return pending_invitation_redirect
            if not has_membership:
                return "/orgs/new/"
        return cast(str, super().get_login_redirect_url(request))

    def get_signup_redirect_url(self, request: Any) -> str:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return cast(str, super().get_signup_redirect_url(request))

        # SA14.6: QUICKSCALE_MODE is guaranteed by the boot guard —
        # direct access, no fallback.
        saas_mode = settings.QUICKSCALE_MODE == "saas"
        if not saas_mode:
            Organization.objects.create_personal_for(user)
            return "/"

        if OrganizationMembership.objects.filter(user=user).exists():
            return cast(str, super().get_signup_redirect_url(request))

        pending_invitation_redirect = self._get_pending_invitation_redirect_url(request)
        if pending_invitation_redirect is not None:
            return pending_invitation_redirect
        return "/orgs/new/"
