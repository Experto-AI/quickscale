"""DRF throttle classes for the orgs module."""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework.throttling import SimpleRateThrottle


def _view_organization(view: Any) -> Any | None:
    """Return the invite view's target organization, or ``None``.

    The route's slug resolves through the view's own organization resolver,
    so the bucket follows the organization row even when its slug changes.
    A view without a resolver, or one whose slug resolves to nothing, gets no
    bucket here; the view's own gates answer that request.
    """
    get_organization = getattr(view, "get_organization", None)
    if not callable(get_organization):
        return None
    try:
        return get_organization()
    except Http404:
        return None


class OrgInviteThrottle(SimpleRateThrottle):
    """Rate limiting for organization invitation sends, per sender.

    The scope carries the module stem and its rate is the orgs module's
    ``invite_rate_limit`` option, contributed to
    ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` by the orgs wiring through
    rule 30's merge (Module Conventions rule 32).  The bucket is the sender:
    revoking and re-inviting does not reset it, and a sender's invitations
    share one budget across every organization, so creating another
    organization cannot multiply the sends.  An anonymous caller gets no
    bucket here; the invite views reject it through their own gates.
    """

    scope = "quickscale_orgs_invite"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        """Key throttle buckets by the sender's user id."""
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return self.cache_format % {"scope": self.scope, "ident": user.pk}


class OrgInviteOrganizationThrottle(SimpleRateThrottle):
    """Rate limiting for organization invitation sends, per organization.

    The scope carries the module stem and the same ``invite_rate_limit``
    option rate (Module Conventions rule 32).  The bucket is the target
    organization, so every sender of one organization shares one time-based
    budget; adding admins, revoking, or re-inviting cannot multiply the
    organization's sends.  An anonymous caller gets no bucket here either.
    """

    scope = "quickscale_orgs_invite_organization"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        """Key throttle buckets by the target organization's id."""
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        organization = _view_organization(view)
        if organization is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": organization.pk}
