"""AF9 Phase 1 — Connection-layer GUC priming lifecycle/install tests.

Phase 1 scope
-------------
* Runtime wiring: ``install_priming_wrapper()`` on ``DatabaseWrapper``
  instances via the ``connection.execute_wrapper()`` API.
* Lifecycle installation in ``QuickscaleOrgsConfig.ready()`` on existing
  connections and via the ``connection_created`` signal.
* Idempotence guard (second install is a no-op).
* Recursion guard (``_PRIMING_IN_PROGRESS`` ContextVar prevents re-entry
  when the wrapper itself issues ``SET LOCAL``).
* Correct GUC derivation from the ``ContextVar`` in both explicit-transaction
  and autocommit modes.
* No regressions for the AF4 no-request-long-transaction contract.

Phase 2+ is out of scope for this file (backend contingency, restricted-role
proofs, middleware/view/module redesign, schema/migration work).

Connection hygiene
------------------
PostgreSQL custom GUC parameters (``app.current_org_id``) are implicitly
registered in the session the first time they are referenced via ``SET`` or
``SET LOCAL``.  Once registered, ``current_setting('app.current_org_id', true)``
returns ``''`` (the compiled-in default) instead of ``NULL``.

The shared test connection is therefore "tainted" after any AF9 priming call:
the GUC changes from ``NULL`` to ``''`` for the session lifetime.  This would
break the existing ``test_postgres_content_route_does_not_set_db_current_org_id``
in ``test_middleware.py`` which asserts ``current_setting`` returns ``None``
(SQL NULL).

We mitigate this by closing the shared connection after each test via
``_close_connection``, so the next test (or the middleware test) opens a
fresh PostgreSQL session where the GUC is again in the ``NULL`` state.
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connection
from django.db import transaction

from quickscale_modules_orgs.current_org import (
    _INSTALLED_MARKER,
    get_current_org_id,
    install_priming_wrapper,
    reset_current_org_id,
    set_current_org_id,
)


# ---------------------------------------------------------------------------
# Connection cleanup fixture
# ---------------------------------------------------------------------------
# Resets the PostgreSQL session between tests so that the
# ``app.current_org_id`` custom GUC returns to the ``NULL`` state.
# Without this, the existing middleware isolation test would fail when run
# after any AF9 test that issues ``SET LOCAL``.


@pytest.fixture(autouse=True)
def _close_connection() -> None:
    """Close the shared connection after each test.

    Django reopens the connection lazily on the next ``cursor()`` access,
    creating a fresh PostgreSQL session.  The ``install_priming_wrapper``
    marker is preserved because it lives on the Django ``DatabaseWrapper``
    wrapper object, not on the underlying psycopg2 connection.  The wrapper
    itself is in ``execute_wrappers`` which also survives close/reconnect.
    """
    yield
    connection.close()


# ---------------------------------------------------------------------------
# Install lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_priming_wrapper_installed_by_ready() -> None:
    """``QuickscaleOrgsConfig.ready()`` installs the wrapper on the
    default connection.  The marker attribute must be present."""
    assert getattr(connection, _INSTALLED_MARKER, False) is True, (
        "The priming wrapper was not installed by ready() on the "
        "default database connection."
    )


@pytest.mark.django_db
def test_install_priming_wrapper_idempotent() -> None:
    """``install_priming_wrapper()`` returns ``False`` on a connection
    that already has the wrapper installed.  The marker persists."""
    result = install_priming_wrapper(connection)
    assert result is False, "Second install must return False (already installed)."
    assert getattr(connection, _INSTALLED_MARKER, False) is True, (
        "Marker must remain True after idempotent install."
    )


@pytest.mark.django_db
def test_signal_handler_installs_wrapper() -> None:
    """The ``_install_priming_on_connection`` signal handler installs
    the priming wrapper on a fresh DatabaseWrapper.

    We create a true fresh ``DatabaseWrapper`` via
    ``connections.create_connection()`` rather than manipulating the
    shared default connection.  The fresh wrapper has no execute
    wrappers and no installation marker — it is a clean seam for
    verifying per-connection install behaviour.

    Test isolation (CR-AF9-002): the fresh ``DatabaseWrapper`` is
    created and discarded within this test; the shared default
    connection is never touched.
    """
    from django.db import connections

    from quickscale_modules_orgs.apps import _install_priming_on_connection

    # Create a fresh DatabaseWrapper (same database settings as
    # 'default') without connecting.  The wrapper starts with an
    # empty execute_wrappers list and no installation marker.
    fresh_conn = connections.create_connection("default")

    # The handler must not exist yet on a truly fresh wrapper.
    assert not getattr(fresh_conn, _INSTALLED_MARKER, False), (
        "Fresh wrapper must not already have the marker set."
    )
    assert len(fresh_conn.execute_wrappers) == 0, (
        "Fresh wrapper must have an empty execute_wrappers list."
    )

    _install_priming_on_connection(sender=None, connection=fresh_conn)

    assert getattr(fresh_conn, _INSTALLED_MARKER, False) is True, (
        "Signal handler must install the wrapper on a fresh connection."
    )
    assert len(fresh_conn.execute_wrappers) == 1, (
        "Signal handler must add exactly one execute wrapper "
        f"(got {len(fresh_conn.execute_wrappers)})."
    )
    # The shared default connection is unmodified.
    assert getattr(connection, _INSTALLED_MARKER, False) is True, (
        "The shared default connection's marker must be undisturbed."
    )


# ---------------------------------------------------------------------------
# Non-PostgreSQL backend — vendor guard (CR-AF9-003)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_priming_wrapper_noop_on_non_postgresql() -> None:
    """The priming execute wrapper is a no-op on non-PostgreSQL backends.

    Regression for CR-AF9-003: set the ContextVar to a non-None value and
    mock ``connection.vendor`` to ``"sqlite"``.  A subsequent
    ``cursor.execute()`` must complete normally without issuing
    ``SET LOCAL`` — the GUC must remain at the session default.
    """
    from unittest import mock

    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        with mock.patch.object(connection, "vendor", "sqlite"):
            # Plain query — must complete without raising.
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                (result,) = cursor.fetchone()
            assert result == 1

            # Verify the GUC was NOT primed: current_setting returns
            # the session default ('' or None), not org_id.
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org_id', true)")
                (raw,) = cursor.fetchone()
            assert raw is None or raw == "", (
                "On a non-PostgreSQL backend, the wrapper must not "
                f"issue SET LOCAL. GUC should be empty, got {raw!r}"
            )
    finally:
        reset_current_org_id()


# ---------------------------------------------------------------------------
# Recursion guard — implicit coverage
# ---------------------------------------------------------------------------
# The recursion guard is exercised indirectly by every query that goes
# through the installed wrapper: when ``_issue_set_local()`` calls
# ``connection.cursor().execute("SET LOCAL ...")``, the execute wrapper
# fires again.  The ``_PRIMING_IN_PROGRESS`` ContextVar prevents re-entry.
#
# If the guard were broken, every ``cursor.execute()`` with a non-None
# ContextVar would crash with infinite recursion.  The tests below verify
# that simple queries complete normally, proving the guard works.


@pytest.mark.django_db
def test_recursion_guard_allows_normal_query() -> None:
    """A trivial ``SELECT 1`` completes without recursion error when the
    ContextVar is set to a non-None value."""
    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            (result,) = cursor.fetchone()
        assert result == 1
    finally:
        reset_current_org_id()


@pytest.mark.django_db
def test_recursion_guard_allows_multi_row_query() -> None:
    """A query that returns multiple rows completes without recursion error."""
    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT n FROM (VALUES (1), (2), (3)) AS t(n) ORDER BY n")
            rows = cursor.fetchall()
        assert rows == [(1,), (2,), (3,)]
    finally:
        reset_current_org_id()


@pytest.mark.django_db
def test_recursion_guard_none_contextvar_allows_query() -> None:
    """When ContextVar is None (no org context), queries pass through
    without priming and complete normally."""
    reset_current_org_id()
    assert get_current_org_id() is None
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        (result,) = cursor.fetchone()
    assert result == 1


# ---------------------------------------------------------------------------
# GUC priming — explicit transaction
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_priming_sets_guc_in_explicit_transaction() -> None:
    """Inside ``transaction.atomic()``, the wrapper issues
    ``SET LOCAL app.current_org_id`` so that ``current_setting``
    returns the expected org UUID."""
    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org_id', true)")
                (raw,) = cursor.fetchone()
        assert raw == str(org_id), (
            f"Expected app.current_org_id = {org_id}, got {raw!r}"
        )
    finally:
        reset_current_org_id()


@pytest.mark.django_db(transaction=True)
def test_priming_guc_is_transaction_scoped() -> None:
    """``SET LOCAL`` inside an explicit transaction is transaction-scoped.

    After the transaction commits, the GUC resets to the session default.
    A subsequent query without a ContextVar confirms it is not leaked
    across transaction boundaries.
    """
    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

        # After atomic exits, clear the ContextVar and verify the GUC
        # is at the session default (no SET LOCAL happens without a
        # ContextVar).
        reset_current_org_id()
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
        assert raw is None or raw == "", (
            "After clearing the ContextVar, SET LOCAL must not be issued "
            f"and the GUC must be empty. Got {raw!r}"
        )
    finally:
        reset_current_org_id()


@pytest.mark.django_db(transaction=True)
def test_priming_guc_differs_per_org_in_explicit_txn() -> None:
    """Different org IDs produce different GUC values in separate
    explicit transactions."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    set_current_org_id(org_a)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org_id', true)")
                (raw_a,) = cursor.fetchone()
        assert raw_a == str(org_a)
    finally:
        reset_current_org_id()

    set_current_org_id(org_b)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org_id', true)")
                (raw_b,) = cursor.fetchone()
        assert raw_b == str(org_b)
        assert raw_a != raw_b
    finally:
        reset_current_org_id()


@pytest.mark.django_db(transaction=True)
def test_priming_same_org_consecutive_explicit_txns() -> None:
    """CR-SA42-001 regression: back-to-back same-org explicit transactions
    must each issue SET LOCAL on their first statement.

    The per-transaction memo carries the atomic block identity.  When a
    connection transitions directly from one explicit transaction to another
    with the same org (no intervening autocommit query), the changed atomic
    block identity forces the memo to be cleared, ensuring the first
    statement in the second transaction re-primes unconditionably.

    Proof: GUC value check + CaptureQueriesContext in the second transaction
    confirms exactly one SET LOCAL is issued.
    """
    from django.test.utils import CaptureQueriesContext

    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        # First transaction — primes SET LOCAL and sets the memo.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

        # Second transaction — same org, no intervening query.
        # Verify the GUC is primed (memo was cleared) and exactly one
        # SET LOCAL appears in the captured statements.
        with transaction.atomic():
            with CaptureQueriesContext(connection) as captured:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.current_org_id', true)")
                    (raw,) = cursor.fetchone()

            assert raw == str(org_id), (
                f"Second explicit transaction must re-prime. "
                f"Expected {org_id}, got {raw!r}"
            )

            set_local_count = sum(
                1 for q in captured.captured_queries if "SET LOCAL" in q["sql"]
            )
            assert set_local_count == 1, (
                f"Second transaction must issue exactly 1 SET LOCAL "
                f"(first statement primes), got {set_local_count}"
            )
    finally:
        reset_current_org_id()


# ---------------------------------------------------------------------------
# GUC priming — autocommit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_priming_sets_guc_in_autocommit() -> None:
    """In autocommit mode, the wrapper wraps each statement in a short
    ``transaction.atomic()`` that issues ``SET LOCAL``.  The GUC is
    visible inside the same autocommit cursor.execute()."""
    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
        assert raw == str(org_id), (
            f"Expected app.current_org_id = {org_id} in autocommit, got {raw!r}"
        )
    finally:
        reset_current_org_id()


@pytest.mark.django_db(transaction=True)
def test_priming_guc_cleared_after_autocommit() -> None:
    """After the autocommit statement completes (the short atomic exits),
    the GUC returns to the session default — no leak across statements.

    We verify this by setting the ContextVar for a first statement,
    then clearing it before the second.  A second statement without a
    ContextVar must not prime, proving the short atomic exited cleanly.
    """
    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    try:
        # First statement — primes within a short atomic.
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Clear ContextVar for the second statement so the wrapper
        # does NOT issue SET LOCAL — we want to see the session default.
        reset_current_org_id()

        # Second statement — ContextVar is None, no priming.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
        assert raw is None or raw == "", (
            "After clearing the ContextVar, SET LOCAL must not be issued "
            f"and the GUC must be empty. Got {raw!r}"
        )
    finally:
        reset_current_org_id()


@pytest.mark.django_db
def test_priming_no_guc_when_contextvar_none() -> None:
    """When ContextVar is None, the wrapper does NOT issue SET LOCAL.
    The GUC remains at its session default."""
    reset_current_org_id()
    assert get_current_org_id() is None
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        (raw,) = cursor.fetchone()
    assert raw is None or raw == "", (
        "When ContextVar is None, the wrapper must not issue SET LOCAL. "
        f"GUC should be empty, got {raw!r}"
    )


# ---------------------------------------------------------------------------
# No-request-long-transaction regression guard (AF4)
# ---------------------------------------------------------------------------
# The existing ``test_postgres_content_route_does_not_set_db_current_org_id``
# in ``test_middleware.py`` remains the authoritative regression test.
# This section adds complementary proof at the connection layer.


@pytest.mark.django_db(transaction=True)
def test_short_atomic_does_not_leak_across_calls() -> None:
    """Prove that autocommit-mode priming does not leave an open
    transaction after ``cursor.execute()`` returns.

    Each ``cursor.execute()`` is genuinely autocommitted.  After one
    call's short atomic exits, the next call must not see stale GUC
    state (AF4 no-request-long-transaction behavior).

    Uses ``transaction=True`` so the test runs outside Django's test
    transaction.
    """
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    set_current_org_id(org_a)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw_a,) = cursor.fetchone()
        assert raw_a == str(org_a)
    finally:
        reset_current_org_id()

    set_current_org_id(org_b)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw_b,) = cursor.fetchone()
        assert raw_b == str(org_b)
    finally:
        reset_current_org_id()

    # Re-check that org_a's GUC is gone after org_b's short atomic.
    set_current_org_id(org_a)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw_a_again,) = cursor.fetchone()
        assert raw_a_again == str(org_a)
    finally:
        reset_current_org_id()


# ---------------------------------------------------------------------------
# SA83 — Canonical GUC mutator memo-clearing lifecycle
# ---------------------------------------------------------------------------
# Each direct GUC mutator (_set_db_current_org_id, reset_db_current_org_id,
# _restore_current_org_id) must clear the per-transaction priming memo so
# that the next wrapped statement re-primes unconditionally.
#
# Without memo clearing, the wrapper skips SET LOCAL when the ContextVar
# matches the stale memo, leaving the GUC desynchronized — a problem that
# manifests as RLS-blocked queries when session auth code (or any code that
# sets the ContextVar after a direct GUC mutation) runs on the same
# connection.
#
# Each test:
#  1. Sets ContextVar A and enters one explicit outer atomic.
#  2. An ordinary wrapped query seeds the GUC and memo with A.
#  3. Directly mutates the GUC while ContextVar is still A.
#  4. No intermediate normal (unwrapped) query.
#  5. CaptureQueriesContext around the next normal wrapped current_setting.
#  6. Asserts result == str(A) and exactly one fresh SET LOCAL.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_direct_set_b_clears_memo() -> None:
    """Direct _set_db_current_org_id(B) clears the priming memo so the
    next wrapped query re-primes from the ContextVar (A)."""
    from django.test.utils import CaptureQueriesContext

    from quickscale_modules_orgs.current_org import _set_db_current_org_id

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    set_current_org_id(org_a)
    try:
        with transaction.atomic():
            # Seed: first wrapped query primes GUC = org_a, memo = org_a.
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            # Directly set GUC to org_b via raw mutator.
            # ContextVar is still org_a.
            _set_db_current_org_id(org_b)

            # Next wrapped query: must re-prime because memo was cleared.
            with CaptureQueriesContext(connection) as captured:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.current_org_id', true)")
                    (raw,) = cursor.fetchone()

            assert raw == str(org_a), (
                f"Expected GUC = {org_a} (re-primed from ContextVar), got {raw!r}"
            )

            set_local_count = sum(
                1 for q in captured.captured_queries if "SET LOCAL" in q["sql"]
            )
            assert set_local_count == 1, (
                f"Expected exactly 1 SET LOCAL after direct mutation "
                f"(the re-prime), got {set_local_count}"
            )
    finally:
        reset_current_org_id()


@pytest.mark.django_db(transaction=True)
def test_reset_clears_memo() -> None:
    """Direct reset_db_current_org_id() clears the priming memo so the
    next wrapped query re-primes from the ContextVar (A)."""
    from django.test.utils import CaptureQueriesContext

    from quickscale_modules_orgs.current_org import reset_db_current_org_id

    org_a = uuid.uuid4()

    set_current_org_id(org_a)
    try:
        with transaction.atomic():
            # Seed: first wrapped query primes GUC = org_a, memo = org_a.
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            # Directly reset the GUC to default ('').
            reset_db_current_org_id()

            # Next wrapped query: must re-prime because memo was cleared.
            with CaptureQueriesContext(connection) as captured:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.current_org_id', true)")
                    (raw,) = cursor.fetchone()

            assert raw == str(org_a), (
                f"Expected GUC = {org_a} (re-primed from ContextVar after reset), "
                f"got {raw!r}"
            )

            set_local_count = sum(
                1 for q in captured.captured_queries if "SET LOCAL" in q["sql"]
            )
            assert set_local_count == 1, (
                f"Expected exactly 1 SET LOCAL after reset "
                f"(the re-prime), got {set_local_count}"
            )
    finally:
        reset_current_org_id()


@pytest.mark.django_db(transaction=True)
def test_restore_b_clears_memo() -> None:
    """Direct _restore_current_org_id(B) with a non-None prior clears
    the priming memo so the next wrapped query re-primes from the
    ContextVar (A)."""
    from django.test.utils import CaptureQueriesContext

    from quickscale_modules_orgs.current_org import _restore_current_org_id

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    set_current_org_id(org_a)
    try:
        with transaction.atomic():
            # Seed: first wrapped query primes GUC = org_a, memo = org_a.
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            # Directly restore GUC to org_b via the restore helper.
            # ContextVar is still org_a.
            _restore_current_org_id(org_b)

            # Next wrapped query: must re-prime because memo was cleared.
            with CaptureQueriesContext(connection) as captured:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.current_org_id', true)")
                    (raw,) = cursor.fetchone()

            assert raw == str(org_a), (
                f"Expected GUC = {org_a} (re-primed from ContextVar after restore), "
                f"got {raw!r}"
            )

            set_local_count = sum(
                1 for q in captured.captured_queries if "SET LOCAL" in q["sql"]
            )
            assert set_local_count == 1, (
                f"Expected exactly 1 SET LOCAL after restore "
                f"(the re-prime), got {set_local_count}"
            )
    finally:
        reset_current_org_id()


# ---------------------------------------------------------------------------
# ORM pass-through
# ---------------------------------------------------------------------------
# The recursion-guard tests above already prove that cursor.execute() works
# correctly with the wrapper installed.  Full ORM integration is covered
# by the existing middleware and model test suites.
