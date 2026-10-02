"""Post-authentication redirect hooks the orgs AppConfig declares.

Module Conventions rule 4: orgs owns the organization-aware redirect logic,
but it declares it as an ``AppConfig`` capability instead of subclassing
auth's allauth adapter.  Auth's single adapter collects the declared hooks
and uses the first URL one returns, so orgs imports no part of auth (D6
option a: the ``auth ↔ orgs`` cycle is broken).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from ._constants import (
    ORG_INVITATION_ACCEPT_URL_NAME,
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from .models import Organization, OrganizationInvitation, OrganizationMembership


def _pending_invitation_redirect_url(request: Any) -> str | None:
    """Return the pending-invitation accept URL, clearing a terminal token."""
    session = getattr(request, "session", None)
    if session is None:
        return None

    invitation_token = session.get(PENDING_ORG_INVITATION_TOKEN_SESSION_KEY)
    if invitation_token is None:
        return None

    try:
        normalized_token = UUID(str(invitation_token))
    except TypeError, ValueError, AttributeError:
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


def post_login_redirect(request: Any) -> str | None:
    """Answer orgs' post-login redirect, or ``None`` for the base default.

    In solo mode a user without a membership gets a personal organization
    before the base redirect applies.  In saas mode a pending invitation
    wins, a user without a membership goes to org creation, and the base
    default applies otherwise.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    # SA14.6: QUICKSCALE_ORGS_MODE is guaranteed by the boot guard —
    # direct access, no fallback.
    saas_mode = settings.QUICKSCALE_ORGS_MODE == "saas"
    has_membership = OrganizationMembership.objects.filter(user=user).exists()
    if not saas_mode and not has_membership:
        Organization.objects.create_personal_for(user)
        return None

    if saas_mode:
        pending_invitation_redirect = _pending_invitation_redirect_url(request)
        if pending_invitation_redirect is not None:
            return pending_invitation_redirect
        if not has_membership:
            return "/orgs/new/"
    return None


def post_signup_redirect(request: Any) -> str | None:
    """Answer orgs' post-signup redirect, or ``None`` for the base default.

    In solo mode the signup creates the personal organization and lands on
    the site root.  In saas mode a pending invitation wins, a user with a
    membership keeps the base default, and a user without one goes to org
    creation.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    # SA14.6: QUICKSCALE_ORGS_MODE is guaranteed by the boot guard —
    # direct access, no fallback.
    saas_mode = settings.QUICKSCALE_ORGS_MODE == "saas"
    if not saas_mode:
        Organization.objects.create_personal_for(user)
        return "/"

    if OrganizationMembership.objects.filter(user=user).exists():
        return None

    pending_invitation_redirect = _pending_invitation_redirect_url(request)
    if pending_invitation_redirect is not None:
        return pending_invitation_redirect
    return "/orgs/new/"
