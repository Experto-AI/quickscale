"""Reusable current-organization helpers for request-scoped org access.

This module provides a small, explicit contract for reading and writing the
current organization on a Django request.  ``request.org`` remains the
back-compat carrier so that existing callers (including the billing module)
continue to work unchanged.

The ``require_current_org`` accessor is the strict fail-closed entry point:
it raises :class:`CurrentOrgError` when no organization context is available
instead of silently returning ``None``.
"""

from __future__ import annotations

from typing import Any


class CurrentOrgError(Exception):
    """Raised when strict org access is required but no org context is set."""


def set_current_org(request: Any, organization: Any) -> None:
    """Attach *organization* to *request* as the active org for this cycle."""
    request.org = organization


def get_current_org(request: Any) -> Any | None:
    """Return the active organization on *request*, or ``None`` if unset."""
    return getattr(request, "org", None)


def clear_current_org(request: Any) -> None:
    """Remove any active organization from *request*."""
    request.org = None


def require_current_org(request: Any) -> Any:
    """Return the active organization or raise :class:`CurrentOrgError`.

    This is the strict fail-closed accessor.  Callers that must have an
    organization context should prefer this over :func:`get_current_org`
    so that missing context is an explicit error rather than a silent
    ``None``.
    """
    organization = get_current_org(request)
    if organization is None:
        raise CurrentOrgError(
            "No current organization context available for this request."
        )
    return organization
