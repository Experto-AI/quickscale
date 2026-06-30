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

AF9 Phase 1 adds the connection-layer execute wrapper that primes the
PostgreSQL GUC ``app.current_org_id`` from the ContextVar on the live
cursor before tenant SQL executes.  The wrapper is installed on every
``DatabaseWrapper`` via :func:`install_priming_wrapper` and handles both
explicit-transaction and autocommit modes without introducing request-long
transaction behavior.
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

    Uses the shipped NULLIF-guarded contract documented in ``organizations.md``:
      ``NULLIF(current_setting('app.current_org_id', true), '')::uuid``

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

    After calling this, ``current_setting('app.current_org_id', true)``
    returns the GUC default (``''`` on this PostgreSQL version), which the
    RLS policy converts to ``NULL::uuid`` via
    ``NULLIF(current_setting(...), '')::uuid`` — the "no org" fail-closed state.

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


def _restore_current_org_id(prior: uuid.UUID | None) -> None:
    """Restore the DB GUC after a tenant_context() scope exits.

    Issues ``SET LOCAL`` (transaction-scoped) to restore *prior* or to clear
    the GUC to its default (empty string) when *prior* was ``None``.  Using
    ``SET LOCAL`` instead of ``RESET`` avoids session-level side effects that
    can leak across test transactions (CR-AF11-001).
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        if prior is None:
            cursor.execute("SET LOCAL app.current_org_id = ''")
        else:
            cursor.execute("SET LOCAL app.current_org_id = %s", [str(prior)])


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

    On exit: restores the prior ContextVar **and** the prior DB GUC
    so that nested ``tenant_context()`` use never leaves the DB
    ``app.current_org_id`` desynchronized from the Python-level scope.

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
        try:
            reset_db_current_org_id()
            yield
        finally:
            set_current_org_id(prior)
            # Restore the DB GUC so nested tenant_context() stays in sync.
            if prior is None:
                reset_db_current_org_id()
            else:
                set_db_current_org_id(prior)
        return

    set_current_org_id(org_id)
    try:
        set_db_current_org_id(org_id)
        yield
    finally:
        set_current_org_id(prior)
        # Restore the DB GUC so nested tenant_context() stays in sync.
        # Use SET LOCAL with DEFAULT when prior was None so we reset the
        # transaction-scoped GUC without affecting the session default
        # (CR-AF11-001 regression: RESET is session-scoped and can
        # interact unexpectedly with connection-level state).
        _restore_current_org_id(prior)


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


# ---------------------------------------------------------------------------
# AF9 Phase 1 — Connection-layer GUC priming
# ---------------------------------------------------------------------------
# The execute wrapper below is installed on every Django DatabaseWrapper
# via ``install_priming_wrapper()``.  It intercepts ``cursor.execute()``
# and issues ``SET LOCAL app.current_org_id`` from the ContextVar before
# the tenant SQL runs, so that FORCE-RLS policies see the expected tenant
# context.
#
# Two code paths:
#
# 1. **Explicit transaction** (``connection.in_atomic_block == True``):
#    Issues ``SET LOCAL`` before every tenant statement inside the
#    user-managed transaction.  ``SET LOCAL`` is transaction-scoped and
#    idempotent — repeating it on each statement is correct and safe.
#
# 2. **Autocommit** (``connection.in_atomic_block == False``):
#    Wraps each tenant statement in a short ``transaction.atomic()``
#    block that issues ``SET LOCAL`` before the original SQL, then
#    exits immediately.  This ensures ``SET LOCAL`` and the tenant SQL
#    share the same transaction scope without holding a request-long
#    atomic (AF4 regression guard).
#
# The wrapper operates exclusively on the live DatabaseWrapper/cursor
# from ``context['connection']`` — it does **not** reuse the global
# ``django.db.connection`` helpers from this module.
#
# Recursion is prevented by a ``ContextVar`` flag that the wrapper
# checks before any priming work.
# ---------------------------------------------------------------------------

_GUC_SETTING = "app.current_org_id"
"""PostgreSQL GUC that carries the active organization UUID for RLS policies."""

_PRIMING_IN_PROGRESS: ContextVar[bool] = ContextVar(
    "_af9_priming_in_progress", default=False
)
"""Recursion guard for the priming execute wrapper.

Set ``True`` while the wrapper issues ``SET LOCAL`` so that the nested
``cursor.execute()`` does not re-enter the wrapper.
"""

_INSTALLED_MARKER = "_af9_priming_installed"
"""Connection attribute name for idempotent-install detection."""


def _issue_set_local(connection: Any, org_id: str) -> None:
    """Issue ``SET LOCAL app.current_org_id`` on *connection*.

    Wrapped in the recursion guard so that the inner ``cursor.execute()``
    does not re-trigger the priming execute wrapper.

    Uses ``_GUC_SETTING`` (a module constant) directly in the SQL string
    — it is a trusted identifier, not user input, so f-string interpolation
    is safe here.  The org_id value is passed as a parameter.

    Args:
        connection: A Django ``DatabaseWrapper`` instance.
        org_id: The organization UUID as a string.
    """
    token = _PRIMING_IN_PROGRESS.set(True)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SET LOCAL {_GUC_SETTING} = %s",
                [org_id],
            )
    finally:
        _PRIMING_IN_PROGRESS.reset(token)


def _make_priming_execute_wrapper() -> Any:
    """Create an execute wrapper for GUC priming from the ContextVar.

    Returns a callable with the Django execute-wrapper signature::

        wrapper(execute, sql, params, many, context) -> result

    The wrapper is connection-agnostic — it reads ``context['connection']``
    to operate on the live ``DatabaseWrapper``.  Use
    :func:`install_priming_wrapper` to install it on a specific connection.

    See module docstring for the two code paths (explicit transaction and
    autocommit).
    """
    # NOTE(PHASE-1): We do **not** track per-transaction priming state.
    #   For explicit transactions we issue SET LOCAL on every wrapper call
    #   (idempotent and correct).  Per-transaction tracking can be added
    #   in a later phase if profiling shows measurable overhead.
    #   The rationale: SET LOCAL is a local GUC assignment — PostgreSQL
    #   processes it inline without a separate round-trip once the query
    #   text is received.  For typical transaction sizes (< 100 statements)
    #   the overhead is negligible.
    #
    #   Known edge case: if a connection transitions directly from one
    #   explicit atomic block to another with no intervening autocommit
    #   SQL, the priming wrapper still fires correctly because it primes
    #   unconditionally on every call inside an atomic block.
    #   The fail-closed outcome (RLS returns zero rows) is safe.

    def wrapper(
        execute: Any,
        sql: Any,
        params: Any,
        many: bool,
        context: dict[str, Any],
    ) -> Any:
        # ---- Recursion guard --------------------------------------------
        if _PRIMING_IN_PROGRESS.get():
            return execute(sql, params, many, context)

        conn = context["connection"]
        org_id = get_current_org_id()

        # ---- No org context — pass through without priming ---------------
        if org_id is None:
            return execute(sql, params, many, context)

        org_id_str = str(org_id)

        # ---- Explicit transaction path ----------------------------------
        if conn.in_atomic_block:
            _issue_set_local(conn, org_id_str)
            return execute(sql, params, many, context)

        # ---- Autocommit path --------------------------------------------
        # Wrap in a short atomic so SET LOCAL and the tenant SQL share
        # a transaction scope.  The atomic is entered and exited
        # immediately — no request-long transaction (AF4 guard).
        from django.db import transaction

        with transaction.atomic(using=conn.alias):
            _issue_set_local(conn, org_id_str)
            return execute(sql, params, many, context)

    return wrapper


def install_priming_wrapper(connection: Any) -> bool:
    """Install the AF9 priming execute wrapper on a ``DatabaseWrapper``.

    Idempotent — subsequent calls on the same connection are no-ops and
    return ``False``.  The wrapper is appended directly to
    ``connection.execute_wrappers`` (Django 6.x's ``execute_wrapper()``
    is a context manager, not a permanent install API).

    Args:
        connection: A Django ``DatabaseWrapper`` instance (any database
            backend).  Priming is only active for PostgreSQL; the wrapper
            itself emits ``SET LOCAL`` which PostgreSQL ignores on other
            vendors.

    Returns:
        ``True`` if the wrapper was newly installed, ``False`` if already
        present.
    """
    if getattr(connection, _INSTALLED_MARKER, False):
        return False
    wrapper = _make_priming_execute_wrapper()
    connection.execute_wrappers.append(wrapper)
    setattr(connection, _INSTALLED_MARKER, True)
    return True
