"""Shared helpers for VIEW-AS debug mode (superuser-only org impersonation).

This module provides the session/audit primitives used by middleware, views,
admin affordances, and the debug banner to coordinate the VIEW-AS operator
debug runtime slice.  Every function enforces the superuser-only invariant
and logs activation/exit/resolved-use events through stdlib logging with
stable structured ``extra`` fields.
"""

from __future__ import annotations

import uuid

import logging

from django.http import HttpRequest

from .constants import DEBUG_AS_ORG_SESSION_KEY
from .models import Organization

logger = logging.getLogger(__name__)


def _resolve_debug_org_id(org_id: object) -> uuid.UUID | None:
    """Safely parse a session-stored org ID to a UUID, or return None."""
    if isinstance(org_id, uuid.UUID):
        return org_id
    if isinstance(org_id, str):
        try:
            return uuid.UUID(org_id)
        except (ValueError, AttributeError):
            return None
    return None


def get_debug_as_org(request: HttpRequest) -> Organization | None:
    """Return the active VIEW-AS organization, or ``None``.

    Looks up the org from the session key.  Returns ``None`` (and clears
    stale/invalid keys) when:
    * No debug session key is set.
    * The stored org UUID does not match an existing ``Organization`` row.
    * The current user is not a superuser (defence-in-depth — clears the
      key and logs a warning).
    """
    session = getattr(request, "session", None)
    if session is None:
        return None
    raw_org_id = session.get(DEBUG_AS_ORG_SESSION_KEY)
    if raw_org_id is None:
        return None

    # Safely parse the session value to a UUID.
    parsed = _resolve_debug_org_id(raw_org_id)
    if parsed is None:
        request.session.pop(DEBUG_AS_ORG_SESSION_KEY, None)
        return None

    # Resolve the org row.
    try:
        organization = Organization.objects.get(pk=parsed)
    except Organization.DoesNotExist:
        request.session.pop(DEBUG_AS_ORG_SESSION_KEY, None)
        return None

    # Superuser-only invariant.
    user = getattr(request, "user", None)
    if not bool(getattr(user, "is_superuser", False)):
        request.session.pop(DEBUG_AS_ORG_SESSION_KEY, None)
        logger.warning(
            "Cleared debug-as session for non-superuser",
            extra={
                "user_id": getattr(user, "pk", None),
                "org_id": str(parsed),
            },
        )
        return None

    logger.debug(
        "VIEW-AS resolved for request",
        extra={
            "user_id": getattr(user, "pk", None),
            "org_id": str(organization.pk),
            "org_slug": organization.slug,
        },
    )
    return organization


def set_debug_as_org(request: HttpRequest, organization: Organization) -> None:
    """Activate VIEW-AS debug mode for *organization*.

    Stores the org PK in the session.  Logs an ``INFO`` event with
    stable structured ``extra`` fields.  The caller is responsible for
    the superuser check (views enforce it via ``user.is_superuser``).
    """
    request.session[DEBUG_AS_ORG_SESSION_KEY] = str(organization.pk)
    logger.info(
        "VIEW-AS debug mode activated",
        extra={
            "user_id": getattr(request.user, "pk", None),
            "org_id": str(organization.pk),
            "org_slug": organization.slug,
        },
    )


def clear_debug_as_org(request: HttpRequest) -> None:
    """Deactivate VIEW-AS debug mode.

    Removes the session key and logs an ``INFO`` event when a debug
    session was active.
    """
    org_id = request.session.pop(DEBUG_AS_ORG_SESSION_KEY, None)
    if org_id is not None:
        logger.info(
            "VIEW-AS debug mode exited",
            extra={
                "user_id": getattr(request.user, "pk", None),
                "org_id": org_id,
            },
        )


def is_debug_as_active(request: HttpRequest) -> bool:
    """Return ``True`` when a valid VIEW-AS debug session is active.

    Lightweight check — does not resolve the org row from the database.
    Callers that need the resolved org should use :func:`get_debug_as_org`.
    """
    org_id = request.session.get(DEBUG_AS_ORG_SESSION_KEY)
    if org_id is None:
        return False
    user = getattr(request, "user", None)
    return bool(getattr(user, "is_superuser", False))
