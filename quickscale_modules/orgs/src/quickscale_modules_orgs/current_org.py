"""Reusable current-organization helpers for request-scoped org access.

This module provides a small, explicit contract for reading and writing the
current organization on a Django request.  ``request.org`` remains the
back-compat carrier so that existing callers (including the billing module)
continue to work unchanged.

The ``require_current_org`` accessor is the strict fail-closed entry point:
it raises :class:`CurrentOrgError` when no organization context is available
instead of silently returning ``None``.

T1.2 adds ``ContextVar``-backed helpers (``set_current_org_id``,
``get_current_org_id``, ``reset_current_org_id``) so that tenant-scoped
managers can auto-filter without a ``request`` reference.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any


_current_org_id_var: ContextVar[uuid.UUID | None] = ContextVar(
    "_current_org_id", default=None
)


class CurrentOrgError(Exception):
    """Raised when strict org access is required but no org context is set."""


def set_current_org(request: Any, org: Any) -> None:
    """Attach *org* to *request* as the active org for this cycle."""
    request.org = org


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


# ---------------------------------------------------------------------------
# T1.2 — ContextVar-backed current org id seam for tenant-scoped managers
# ---------------------------------------------------------------------------


def set_current_org_id(org_id: uuid.UUID | None) -> None:
    """Set the current organization ID for the active execution context.

    This is used by :class:`~.middleware.TenantMiddleware` to propagate the
    resolved org into the ``ContextVar`` so that :class:`~.managers.TenantManager`
    can auto-filter querysets without a ``request`` reference.
    """
    _current_org_id_var.set(org_id)


def get_current_org_id() -> uuid.UUID | None:
    """Return the current organization ID for the active execution context.

    Returns ``None`` when no org context is set (e.g. on exempt paths or
    before middleware has resolved the tenant).  Callers that require strict
    fail-closed behavior should check for ``None`` explicitly.
    """
    return _current_org_id_var.get()


def reset_current_org_id() -> None:
    """Reset the current organization ID to ``None`` for this context.

    Called at the start of each new request in
    :class:`~.middleware.TenantMiddleware` to ensure stale context from a
    prior request is not leaked.
    """
    _current_org_id_var.set(None)


# ---------------------------------------------------------------------------
# T1.15 — shared SET LOCAL helper for non-middleware callers
# ---------------------------------------------------------------------------


def set_db_current_org_id(org_id: uuid.UUID | str) -> None:
    """Set PostgreSQL ``app.current_org_id`` for the active transaction scope.

    Non-middleware callers (e.g. generated social managed views) should call
    this inside a ``transaction.atomic()`` block alongside
    :func:`set_current_org_id`.

    Uses the authoritative DB-side form documented in ``organizations.md``:
      ``current_setting('app.current_org_id', true)::uuid``

    Does nothing when the database backend is not PostgreSQL.
    This is the same ``SET LOCAL`` primitive used by
    :class:`~.middleware.TenantMiddleware` in its request lifecycle.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.current_org_id = %s", [str(org_id)])


def reset_db_current_org_id() -> None:
    """Reset PostgreSQL ``app.current_org_id`` to the default (cleared).

    After calling this, ``current_setting('app.current_org_id', true)::uuid``
    returns ``NULL``, which is the "no org" RLS fail-closed state.

    Must be called inside an active ``transaction.atomic()`` block because
    ``RESET`` (like ``SET LOCAL``) is transaction-scoped.
    Does nothing when the database backend is not PostgreSQL.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("RESET app.current_org_id")


# ---------------------------------------------------------------------------
# T1.17 — combined helper for non-middleware callers
# ---------------------------------------------------------------------------


def set_current_org_for_context(*, org_id: uuid.UUID) -> None:
    """Set both the ContextVar and ``SET LOCAL app.current_org_id``.

    Non-middleware callers (management commands, background tasks, or any
    code outside the request cycle) should call this inside a
    ``transaction.atomic()`` block to establish consistent org context for
    both Python-level tenant-scoped managers and database-level row security.

    Combines :func:`set_current_org_id` and :func:`set_db_current_org_id`
    so callers do not need to remember both calls.

    Example::

        with transaction.atomic():
            set_current_org_for_context(org_id=organization.pk)
            # ... tenant-scoped queries and DB SET LOCAL are in sync ...
    """
    set_current_org_id(org_id)
    set_db_current_org_id(org_id)


# ---------------------------------------------------------------------------
# Phase 2 — request-scoped tenant_context (no atomic wrapper)
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def tenant_context(org_id: uuid.UUID | None) -> Iterator[None]:
    """Request-scoped activation: set ContextVar + DB ``app.current_org_id``.

    Unlike :func:`org_scope`, this does **not** wrap in
    ``transaction.atomic()`` — the caller is responsible for managing
    database transaction boundaries.  An active transaction is required
    for the ``SET LOCAL`` commands to succeed.

    Intended for request-scoped callers (admin views, endpoints) that
    already manage their own transaction lifecycle or run inside a
    middleware atomic block.

    On entry:
    * Captures the prior ContextVar value.
    * Sets the ContextVar to *org_id* (or ``None`` for fail-closed).
    * Issues ``SET LOCAL app.current_org_id`` (or ``RESET`` when *org_id*
      is ``None``) so that FORCE RLS on PostgreSQL allows or denies queries.

    On exit: restores the prior ContextVar value.
    DB-side ``app.current_org_id`` is automatically cleaned up when the
    caller's transaction commits or rolls back (``SET LOCAL`` is
    transaction-scoped).

    Examples
    --------
    Inside an admin view with explicit transaction management::

        with transaction.atomic():
            with tenant_context(org_id):
                # ... queries run with ContextVar and DB GUC set ...

    Inside middleware (which wraps the entire request in ``org_scope``
    or an equivalent atomic block)::

        with tenant_context(organization.pk):
            response = self.get_response(request)
    """
    prior = get_current_org_id()
    if org_id is None:
        set_current_org_id(None)
        reset_db_current_org_id()
        try:
            yield
        finally:
            set_current_org_id(prior)
        return

    set_current_org_id(org_id)
    set_db_current_org_id(org_id)
    try:
        yield
    finally:
        set_current_org_id(prior)


# ---------------------------------------------------------------------------
# T1.19 — unified org_scope context manager
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def org_scope(organization: Any) -> Iterator[None]:
    """Set ContextVar + DB ``app.current_org_id`` for the active execution context.

    This is the **preferred, unified entry point** for entering org scope
    from middleware and module-level callers.  On entry it sets the ContextVar
    and opens a ``transaction.atomic()`` block that wraps ``SET LOCAL
    app.current_org_id`` so that RLS-protected tables see the expected tenant
    context.

    On exit it restores both the prior ContextVar value and the prior DB-side
    ``app.current_org_id`` so tenant context never leaks across call
    boundaries, even under nested ``org_scope()`` use (T1.19 fail-closed
    contract).

    Parameters
    ----------
    organization : object or None
        A Django model instance with a ``pk`` attribute (typically
        ``Organization``), or ``None`` to clear the ContextVar and reset
        the DB setting (fail-closed — RLS queries return zero rows).

    Yields
    ------
    None
    """
    prior = get_current_org_id()
    if organization is None:
        # Reset both ContextVar and DB so that RLS fail-closed behavior
        # is enforced even under a nested scope (CR-T119-001).
        set_current_org_id(None)
        from django.db import transaction

        with transaction.atomic():
            reset_db_current_org_id()
            try:
                yield
            finally:
                # Restore DB side first, then ContextVar — both inside the
                # atomic so SET LOCAL takes effect in the same transaction.
                if prior is None:
                    reset_db_current_org_id()
                else:
                    set_db_current_org_id(prior)
                set_current_org_id(prior)
        return

    # DB-backed path: set both ContextVar and DB inside an atomic block,
    # and restore both before the atomic exits so that nested scopes do
    # not leave the DB side desynchronized (CR-T119-001).
    set_current_org_id(organization.pk)
    from django.db import transaction

    with transaction.atomic():
        set_db_current_org_id(organization.pk)
        try:
            yield
        finally:
            # Restore DB side first, then ContextVar — both inside the
            # atomic so SET LOCAL takes effect in the same transaction.
            if prior is None:
                reset_db_current_org_id()
            else:
                set_db_current_org_id(prior)
            set_current_org_id(prior)
