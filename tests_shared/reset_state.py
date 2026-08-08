"""
Shared per-test state reset fixture for cross-module tenant test isolation.

SA97 consolidates three divergent private copies (CRM ``_reset_crm_test_state``,
forms ``_reset_test_state``, blog ``_reset_current_org_context``) into one
conftest-importable autouse fixture that each module can import.

The fixture resets the following in both setup and teardown phases:

- Org ContextVar via ``reset_current_org_id()`` (so the baseline is always
  ``None``, fail-closed)
- PostgreSQL GUCs ``app.current_org_id``, ``app.operator_access``, and the
  session ROLE (so per-test SET LOCAL / SET ROLE never leaks across tests)
- The AF9 per-transaction priming memo (``connection._af9_primed_for_txn``
  and ``connection._af9_primed_atomic``)
- The Django cache (``cache.clear()``)

All Django imports are deferred until fixture execution so the fixture is safe
for both pytest-django-managed (CRM) and self-managed (forms, blog) conftests.

Tests without the ``db`` marker safely skip DB GUC resets.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def reset_test_state() -> Iterator[None]:
    """
    Reset per-test state: ContextVar, DB GUCs, AF9 memo, and cache.

    ContextVars persist across tests within the same thread; this fixture
    clears the org ContextVar before each test so the baseline is always
    ``None`` (fail-closed).  Also clears PostgreSQL GUCs
    ``app.current_org_id``, ``app.operator_access``, resets the DB role
    to the session default, clears the AF9 per-transaction priming memo,
    and clears the Django cache.

    Tests without the ``db`` marker safely skip DB GUC resets.

    Resolves arch-audit Finding 9 (module-commons-unowned) Option 1 —
    test-plumbing half.
    """
    from quickscale_modules_orgs.current_org import reset_current_org_id

    reset_current_org_id()
    from django.db import connection

    if connection.vendor == "postgresql":
        try:
            with connection.cursor() as cur:
                cur.execute("RESET app.current_org_id")
                cur.execute("RESET app.operator_access")
                cur.execute("RESET ROLE")
        except RuntimeError:
            # Database access not allowed (test without db marker).
            pass
    if hasattr(connection, "_af9_primed_for_txn"):
        del connection._af9_primed_for_txn
    if hasattr(connection, "_af9_primed_atomic"):
        del connection._af9_primed_atomic
    from django.core.cache import cache

    cache.clear()
    yield
    # Post-yield symmetric teardown.
    reset_current_org_id()
    from django.db import connection
    from django.db.utils import InterfaceError

    if connection.vendor == "postgresql":
        try:
            with connection.cursor() as cur:
                cur.execute("RESET app.current_org_id")
                cur.execute("RESET app.operator_access")
                cur.execute("RESET ROLE")
        except RuntimeError, InterfaceError:
            # Database access not allowed or connection already closed
            # (pytest-django tears down the db fixture before autouse
            # fixture teardown in some fixture-resolution orders).
            pass
    if hasattr(connection, "_af9_primed_for_txn"):
        del connection._af9_primed_for_txn
    if hasattr(connection, "_af9_primed_atomic"):
        del connection._af9_primed_atomic
    from django.core.cache import cache

    cache.clear()
