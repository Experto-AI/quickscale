"""ContextVar seam and connection-layer GUC priming for current-org scope.

``current_org.py`` re-exports these names (Module Conventions rule 28).  The
ContextVar-backed current-org id and the AF9 execute wrapper that primes
``app.current_org_id`` from it live here; the request-scoped scopes and the
operator-access seam stay on the facade.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

_SENTINEL = object()
"""Sentinel for detecting unset memo-atomic attribute."""

_current_org_id_var: ContextVar[uuid.UUID | None] = ContextVar(
    "_current_org_id", default=None
)


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
    prior request is not leaked.  Clearing the connection priming memo is
    equally important: a nested transaction can roll back the ``SET LOCAL``
    that established the prior organization while leaving Python connection
    attributes untouched.  A later scope for the same organization must then
    re-prime the database instead of trusting that stale memo.
    """
    _current_org_id_var.set(None)
    from django.db import connection

    _clear_priming_memo(connection)


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

_PRIMED_FOR_TXN = "_af9_primed_for_txn"
"""Connection attribute name for the per-transaction priming memo value."""

_PRIMED_ATOMIC = "_af9_primed_atomic"
"""Connection attribute name for the per-transaction priming memo outer Atomic ref."""


def _clear_priming_memo(connection: Any) -> None:
    """Clear the per-transaction priming memo on *connection*.

    Must be called whenever the GUC is modified outside the priming
    execute wrapper so that the next wrapped statement re-primes
    unconditionally (SA83).  Idempotent — safe to call when the memo
    is already absent.
    """
    if hasattr(connection, _PRIMED_FOR_TXN):
        delattr(connection, _PRIMED_FOR_TXN)
    if hasattr(connection, _PRIMED_ATOMIC):
        delattr(connection, _PRIMED_ATOMIC)


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
    # NOTE(SA4.2): Per-transaction priming memo eliminates redundant
    #   SET LOCAL calls inside the same explicit transaction.  We store
    #   a connection attribute ``_af9_primed_for_txn`` set to the primed
    #   org_id string, and ``_af9_primed_atomic`` set to the outermost
    #   ``Atomic`` object reference.  On subsequent wrapper calls inside
    #   the same atomic block, if the memo matches the current org_id we
    #   skip the SET LOCAL.
    #
    #   CR-SA42-001 fix: the memo carries the outermost Atomic object
    #   reference so it is invalidated across explicit-transaction
    #   boundaries even when no intervening autocommit query fires on a
    #   reused connection.  We use Python's ``is`` operator on the stored
    #   Atomic reference to detect object identity changes.  This avoids
    #   CPython memory-address reuse where ``id()`` returns the same value
    #   for two different Atomic objects allocated at the same address
    #   (the core CR-SA42-001 defect).  Each ``transaction.atomic()``
    #   creates a new ``Atomic`` instance, so ``current_atomic is not
    #   memo_atomic`` across transactions — the memo is cleared on
    #   mismatch, forcing the first statement in the new transaction to
    #   re-prime unconditionally, regardless of whether the org_id
    #   matches.  This is correct because ``SET LOCAL`` is
    #   transaction-scoped — the prior transaction's GUC setting is gone.

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

        # ---- Non-PostgreSQL backend — pass through without priming -------
        if conn.vendor != "postgresql":
            return execute(sql, params, many, context)

        org_id = get_current_org_id()

        # ---- No org context — pass through without priming ---------------
        if org_id is None:
            return execute(sql, params, many, context)

        org_id_str = str(org_id)

        # ---- Explicit transaction path ----------------------------------
        # CR-SA42-001: Per-transaction memo with atomic block identity.
        # The memo carries the outermost ``atomic_blocks[0]`` identity so
        # it is invalidated across explicit-transaction boundaries even
        # when no intervening autocommit query fires on a reused connection.
        # ``SET LOCAL`` is transaction-scoped; a memo from a prior
        # transaction must not prevent re-priming in a new transaction.
        if conn.in_atomic_block:
            # Detect atomic-block boundary via outermost atomic object
            # identity.  Each ``transaction.atomic()`` creates a new
            # ``Atomic`` instance; we store a direct reference to the
            # atomic object so that the ``is`` operator reliably detects
            # object identity changes across transactions.  Using
            # ``is`` on the stored reference avoids CPython memory-address
            # reuse where ``id()`` can return the same value for two
            # different atomic objects (CR-SA42-001).
            current_atomic = conn.atomic_blocks[0] if conn.atomic_blocks else None
            memo_atomic = getattr(conn, "_af9_primed_atomic", _SENTINEL)
            if memo_atomic is not _SENTINEL and current_atomic is not memo_atomic:
                if hasattr(conn, "_af9_primed_for_txn"):
                    del conn._af9_primed_for_txn

            already_primed = getattr(conn, "_af9_primed_for_txn", None)
            if already_primed != org_id_str:
                _issue_set_local(conn, org_id_str)
                conn._af9_primed_for_txn = org_id_str
                conn._af9_primed_atomic = current_atomic
            return execute(sql, params, many, context)

        # ---- Autocommit path --------------------------------------------
        # Clear any stale per-transaction memo from a prior
        # explicit transaction.  The next explicit transaction will
        # prime unconditionally because the memo is absent.
        if hasattr(conn, "_af9_primed_for_txn"):
            del conn._af9_primed_for_txn
        if hasattr(conn, "_af9_primed_atomic"):
            del conn._af9_primed_atomic

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

    Priming is only active for PostgreSQL.  The wrapper checks
    ``connection.vendor`` on each invocation and passes through without
    priming on non-PostgreSQL backends (e.g. SQLite).

    Args:
        connection: A Django ``DatabaseWrapper`` instance (any database
            backend).  Priming is only active for PostgreSQL; the wrapper
            detects the vendor at runtime and passes through on non-PostgreSQL
            connections.

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
