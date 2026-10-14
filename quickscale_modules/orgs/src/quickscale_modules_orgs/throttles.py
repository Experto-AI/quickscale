"""DRF throttle classes for the orgs module."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

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


class _CheckThenChargeThrottleMixin:
    """Split DRF's throttle check from its charge (Module rule 32).

    ``SimpleRateThrottle.allow_request`` records the hit as it checks the
    window, so a view that checks the sender bucket and then the organization
    bucket would charge the sender before the organization can refuse.
    ``check`` inspects one bucket and records nothing; ``charge`` records the
    hit a passing check allowed; the invite views run every ``check`` first
    and charge only when they all passed, so a refusal spends neither budget.
    ``allow_request`` keeps DRF's combined contract for any caller that uses
    a throttle class directly.

    The host class binds the attributes below in its ``__init__`` (DRF's
    ``SimpleRateThrottle``) and owns ``get_cache_key``; they are declared here
    so the mixin sees them.
    """

    rate: str | None
    num_requests: int
    duration: int
    cache: Any
    timer: Callable[[], float]
    key: str | None
    history: list[float]
    now: float

    if TYPE_CHECKING:

        def get_cache_key(self, request: Any, view: Any) -> str | None: ...

        def throttle_failure(self) -> bool: ...

    def check(self, request: Any, view: Any) -> bool:
        """Return whether a hit would be allowed, recording nothing."""
        if self.rate is None:
            self.key = None
            return True
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        return len(self.history) < self.num_requests

    def charge(self) -> None:
        """Record the hit a passing :meth:`check` allowed.

        A check that allowed without a bucket (no rate configured, or no
        bucket identity) records nothing, exactly like DRF's own path.
        """
        if self.rate is None or self.key is None:
            return
        self.history.insert(0, self.now)
        self.cache.set(self.key, self.history, self.duration)

    def allow_request(self, request: Any, view: Any) -> bool:
        """Check and, only when the check passed, charge (DRF's contract)."""
        if not self.check(request, view):
            return self.throttle_failure()
        self.charge()
        return True


class OrgInviteThrottle(_CheckThenChargeThrottleMixin, SimpleRateThrottle):
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


class OrgInviteOrganizationThrottle(_CheckThenChargeThrottleMixin, SimpleRateThrottle):
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
