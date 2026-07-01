"""SA4.1 — Statement amplification measurement harness.

Measures statements-per-request and ``BEGIN``/``COMMIT`` counts for
representative tenant traffic through the orgs module, providing a
reproducible documented baseline for the per-statement priming overhead
introduced by the AF9 connection-layer execute wrapper.

Scenarios
---------
1. **No org context (baseline)** — queries execute without AF9 priming.
   Establishes the minimum statement count for a given query pattern.

2. **Org context, autocommit** — queries execute with the AF9 wrapper
   active in autocommit mode, exercised through the real
   ``OrgDashboardView`` dispatch chain via ``TenantMiddleware``
   (session-org resolution, not manual ``set_current_org_id``).
   Each data query is wrapped in a short ``transaction.atomic()`` +
   ``SET LOCAL`` (the "per-statement priming" whose cost this task
   quantifies).

3. **Org context, explicit transaction** — queries execute inside a
   caller-managed ``transaction.atomic()``, exercised through the real
   ``OrgDashboardView`` dispatch chain via ``TenantMiddleware``.
   AF9 issues ``SET LOCAL`` before every statement (idempotent but
   additive — the redundant-SET overhead that SA4.2 aims to eliminate
   via per-transaction memo).

The multi-query pattern exercises the ``OrgDashboardView`` data-access
sequence through the real view dispatch: ``OrgRoleMixin.dispatch()``
(org resolved from ``request.org`` pre-set by middleware, then
membership role check) then ``OrgDashboardView.get_context_data()``
(member count).  The test drives them through the actual view code path
via a non-management URL route (``/sa41-bench/<slug>/``) so that
``TenantMiddleware`` resolves the org from the session and populates the
ContextVar via ``_call_with_org()`` — the same path production content
routes use.

Acceptance (from the roadmap)
-----------------------------
A reproducible measurement of statement-amplification on a multi-query
endpoint; documented baseline.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import connection, transaction as db_transaction
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext

from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.current_org import (
    get_current_org_id,
    reset_current_org_id,
)
from quickscale_modules_orgs.middleware import TenantMiddleware
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
)
from quickscale_modules_orgs.views import OrgDashboardView

# ---------------------------------------------------------------------------
# Documented baseline  (SA4.1 acceptance criteria — measured on 2026-07-01
# against v0.87.0-unreleased, PostgreSQL 18, NOBYPASSRLS restricted role)
#
# All values are for the ``OrgDashboardView`` endpoint exercised through
# the real ``TenantMiddleware`` saas session-org resolution path via the
# test-only non-management URL ``/sa41-bench/<slug>/``.  The middleware
# pre-sets ``request.org`` so ``OrgRoleMixin.dispatch()`` skips the slug
# lookup, leaving 2 data SELECTs (membership role check → member count).
# The no-org scenario establishes the theoretical minimum via direct ORM
# calls (AF9 pass-through adds zero cost, so the counts are endpoint
# equivalent for the unprimed case).
#
# B = BEGIN, C = COMMIT, SL = SET LOCAL, D = data SELECT
# ---------------------------------------------------------------------------

# --- Scenario 1: no org context (AF9 pass-through) -------------------------
# Pattern:  3 × D
# Total:    3  (D D D)

BASELINE_NO_ORG_TOTAL = 3
"""Total SQL statements for a 3-query pattern without AF9 priming."""

BASELINE_NO_ORG_DATA = 3
"""Data (SELECT) statements without AF9 priming."""

BASELINE_NO_ORG_BEGIN = 0
"""BEGIN count without AF9 priming."""

BASELINE_NO_ORG_COMMIT = 0
"""COMMIT count without AF9 priming."""

BASELINE_NO_ORG_SET_LOCAL = 0
"""SET LOCAL count without AF9 priming."""

# --- Scenario 2: org context, autocommit (AF9 per-statement wrapping) -------
# Each data query: BEGIN + SET LOCAL + data + COMMIT
# Pattern:  2 × (B SL D C)  =  2B 2SL 2D 2C
# Total:    8

BASELINE_AUTOCOMMIT_TOTAL = 8
"""Total SQL statements with AF9 active in autocommit mode."""

BASELINE_AUTOCOMMIT_DATA = 2
"""Data (SELECT) statements with AF9 active in autocommit mode."""

BASELINE_AUTOCOMMIT_BEGIN = 2
"""BEGIN count with AF9 active in autocommit mode (one per wrapped query)."""

BASELINE_AUTOCOMMIT_COMMIT = 2
"""COMMIT count with AF9 active in autocommit mode."""

BASELINE_AUTOCOMMIT_SET_LOCAL = 2
"""SET LOCAL count with AF9 active in autocommit mode (one per query)."""

BASELINE_AUTOCOMMIT_AMPLIFICATION = 4.0
"""Amplification factor: total / data = 8 / 2."""

# --- Scenario 3: org context, explicit transaction -------------------------
# The caller wraps the dispatch in ``transaction.atomic()``.  AF9's
# explicit-transaction path fires ``SET LOCAL`` before every query inside
# the atomic.  ``CaptureQueriesContext`` is nested inside the outer atomic,
# so the outer atomic's BEGIN/COMMIT are not captured (in
# ``transaction=True`` mode the outer atomic creates a savepoint before
# the capture window opens).
# Pattern:  (SL D) (SL D)  =  0B 2SL 2D 0C
# Total:    4

BASELINE_EXPLICIT_TXN_TOTAL = 4
"""Total captured SQL statements with AF9 active inside an explicit transaction.

Note: ``CaptureQueriesContext`` is nested inside the outer
``db_transaction.atomic()``, so the outer atomic's BEGIN/COMMIT are not
captured.  In ``transaction=True`` test mode the outer atomic creates a
savepoint before the capture window opens.
"""

BASELINE_EXPLICIT_TXN_DATA = 2
"""Data (SELECT) statements with AF9 active inside an explicit transaction."""

BASELINE_EXPLICIT_TXN_BEGIN = 0
"""BEGIN count — not captured (outer atomic is a savepoint in ``transaction=True``)."""

BASELINE_EXPLICIT_TXN_COMMIT = 0
"""COMMIT count — not captured (outer atomic is a savepoint in ``transaction=True``)."""

BASELINE_EXPLICIT_TXN_SET_LOCAL = 2
"""SET LOCAL count — one per data query, even inside the same transaction."""

BASELINE_EXPLICIT_TXN_AMPLIFICATION = 2.0  # 4 / 2
"""Amplification factor: total / data = 4 / 2.

    The first SET LOCAL is required priming (it establishes the org
    context for the transaction); only the second SET LOCAL inside the
    same transaction is redundant.  That redundant SET LOCAL is the
    overhead that **SA4.2 will eliminate** with per-transaction memo.
    Reducing from 4→3 statements (1 SET LOCAL saved).
"""


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


class QueryMetrics:
    """Structured measurement of a captured SQL statement batch.

    Each instance categorises the raw ``connection.queries`` entries into
    data statements, transaction-control statements, and priming statements.
    """

    def __init__(self, captured_queries: list[dict]) -> None:
        self.captured = captured_queries
        self.total = len(captured_queries)

        self.begin = 0
        self.commit = 0
        self.rollback = 0
        self.set_local = 0
        self.savepoint = 0
        self.release_savepoint = 0

        for q in captured_queries:
            upper = q["sql"].strip().upper()
            if upper == "BEGIN" or upper.startswith("BEGIN"):
                self.begin += 1
            elif upper == "COMMIT" or upper.startswith("COMMIT"):
                self.commit += 1
            elif upper.startswith("ROLLBACK"):
                self.rollback += 1
            elif "SET LOCAL" in upper:
                self.set_local += 1
            elif upper.startswith("SAVEPOINT"):
                self.savepoint += 1
            elif upper.startswith("RELEASE SAVEPOINT"):
                self.release_savepoint += 1

        self.txn_statements = self.begin + self.commit + self.rollback
        self.priming_statements = self.set_local
        self.bookkeeping = self.savepoint + self.release_savepoint
        self.data_statements = (
            self.total
            - self.txn_statements
            - self.priming_statements
            - self.bookkeeping
        )

    @property
    def amplification_factor(self) -> float:
        """Ratio of total SQL statements to data (SELECT) statements."""
        return self.total / max(self.data_statements, 1)

    def summary(self) -> str:
        """Human-readable one-line summary of the captured batch."""
        txn = f"{self.begin}B+{self.commit}C+{self.rollback}R"
        sp = f"{self.savepoint}SP+{self.release_savepoint}RL"
        return (
            f"total={self.total}, data={self.data_statements}, "
            f"txn=({txn}), set_local={self.set_local}, savepoint=({sp})"
        )


def capture_queries(scenario_fn) -> QueryMetrics:
    """Execute *scenario_fn* and return a ``QueryMetrics`` over the captured
    SQL statements.

    Uses Django's ``CaptureQueriesContext`` to snapshot
    ``connection.queries`` before and after the function runs.
    """
    with CaptureQueriesContext(connection) as captured:
        scenario_fn()
    return QueryMetrics(captured.captured_queries)


# ---------------------------------------------------------------------------
# Endpoint helper: exercise the real OrgDashboardView dispatch chain
# ---------------------------------------------------------------------------


def _make_authenticated_request(path: str, user) -> "HttpRequest":
    """Build an authenticated GET request via ``RequestFactory``.

    Installs session middleware and sets ``request.user`` directly
    (bypassing ``AuthenticationMiddleware``, which would reload the
    user from the database via ``get_user()`` — adding an extra SELECT
    to the measured query counts).  The session object is created but
    not persisted, so no session DB queries appear in the captured
    SQL statements.
    """
    request: HttpRequest = RequestFactory().get(path)
    request.user = user
    # Install session middleware (creates request.session without
    # persisting — no DB queries with signed_cookies or an empty
    # in-memory session).
    SessionMiddleware(lambda r: None).process_request(request)
    return request


def _call_org_dashboard(
    org: Organization,
    user,
) -> tuple["HttpResponse", QueryMetrics]:
    """Exercise ``OrgDashboardView`` through ``TenantMiddleware``.

    Creates an authenticated request at the test-only non-management
    benchmark URL ``/sa41-bench/<slug>/`` and runs it through
    ``TenantMiddleware`` with the session org set so the ContextVar
    is populated via real middleware session-org resolution
    (``_handle_saas_request`` → ``_call_with_org``).

    Returns ``(response, metrics)`` where *metrics* captures only the
    AF9-primed view queries (the middleware's own session-resolving
    queries happen before the ContextVar is set and are excluded).
    """
    request = _make_authenticated_request(f"/sa41-bench/{org.slug}/", user)
    request.session[ACTIVE_ORG_SESSION_KEY] = str(org.pk)

    captured_queries: list[list[dict]] = []

    def _view_call(req: HttpRequest) -> HttpResponse:
        with CaptureQueriesContext(connection) as captured:
            response = OrgDashboardView.as_view()(req, org_slug=org.slug)
        captured_queries.append(captured.captured_queries)
        return response

    with override_settings(
        QUICKSCALE_MODE="saas",
        SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
    ):
        response: HttpResponse = TenantMiddleware(_view_call)(request)

    return response, QueryMetrics(captured_queries[0])


def _unprimed_query_pattern(org: Organization, user) -> None:
    """Execute the same 3 ORM calls as ``OrgDashboardView.get_context_data()``
    without any org context (AF9 pass-through).  This establishes the
    theoretical minimum — the AF9 wrapper issues zero priming overhead
    when ``get_current_org_id()`` is ``None``, so the raw ORM counts
    are endpoint-equivalent for the unprimed case.
    """
    Organization.objects.filter(slug=org.slug).first()
    OrganizationMembership.objects.filter(
        user=user,
        organization=org,
    ).exists()
    OrganizationMembership.objects.filter(
        organization=org,
    ).count()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _seeded_org() -> tuple[Organization, object]:
    """Seed a minimal organisation with one member.

    Uses ``transactional_db`` so that the seeded data survives across
    ``CaptureQueriesContext`` snapshots inside ``transaction=True`` tests.
    """
    user = get_user_model().objects.create_user(
        username="sa41-bench",
        email="sa41-bench@example.com",
        password="secret123",
    )
    org = Organization.objects.create(
        name="SA4.1 Benchmark Org",
        slug="sa41-bench",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=org,
        role=OrgRole.MEMBER,
    )
    return org, user


# ---------------------------------------------------------------------------
# Test class — reproducible measurement scenarios
# ---------------------------------------------------------------------------
# All tests use ``transaction=True`` so that the AF9 wrapper's internal
# ``transaction.atomic()`` calls issue real ``BEGIN``/``COMMIT`` (instead
# of nested savepoints), giving us accurate transaction-boundary counts.
#
# The ``TenantMiddleware._call_with_org()`` handles ContextVar lifecycle
# for org-context scenarios (set before view dispatch, reset in finally),
# and ``transaction=True`` test isolation handles state cleanup.


class TestSa41StatementAmplification:
    """SA4.1 — reproducible statement-amplification measurement harness.

    Scenarios 2 and 3 exercise the real ``OrgDashboardView`` endpoint
    through ``TenantMiddleware`` via a test-only non-management URL
    (``/sa41-bench/<slug>/``) — the same session-org resolution path
    that production content routes use.  Scenario 1 establishes the
    theoretical unprimed minimum via direct ORM calls (AF9 pass-through
    adds zero overhead, so the counts are endpoint-equivalent).

    The documented baselines below are verified as assertions so they
    remain a hard acceptance gate.
    """

    # ------------------------------------------------------------------
    # Scenario 1: No org context (AF9 pass-through, zero priming cost)
    # ------------------------------------------------------------------
    # The query pattern runs while ``get_current_org_id() is None``.
    # The AF9 wrapper sees ``None`` and passes through without issuing
    # SET LOCAL or wrapping in a short atomic.  Measured via direct ORM
    # calls rather than the full endpoint (no org context present in the
    # dispatch for management paths, and the unprimed case is
    # endpoint-equivalent).
    #
    # Expected: 3 data SELECTs, 0 BEGIN/COMMIT, 0 SET LOCAL.

    @pytest.mark.django_db(transaction=True)
    def test_no_org_autocommit(self, _seeded_org) -> None:
        org, user = _seeded_org
        reset_current_org_id()
        assert get_current_org_id() is None

        metrics = capture_queries(lambda: _unprimed_query_pattern(org=org, user=user))

        print(f"\n[SA4.1]  No-org autocommit:        {metrics.summary()}")
        print(
            f"[SA4.1]    → Amplification factor:   {metrics.amplification_factor:.1f}x"
        )

        assert metrics.total == BASELINE_NO_ORG_TOTAL, (
            f"No-org baseline total: expected {BASELINE_NO_ORG_TOTAL}, "
            f"got {metrics.total}"
        )
        assert metrics.data_statements == BASELINE_NO_ORG_DATA, (
            f"No-org baseline data: expected {BASELINE_NO_ORG_DATA}, "
            f"got {metrics.data_statements}"
        )
        assert metrics.begin == BASELINE_NO_ORG_BEGIN, (
            f"No-org baseline BEGIN: expected {BASELINE_NO_ORG_BEGIN}, "
            f"got {metrics.begin}"
        )
        assert metrics.commit == BASELINE_NO_ORG_COMMIT, (
            f"No-org baseline COMMIT: expected {BASELINE_NO_ORG_COMMIT}, "
            f"got {metrics.commit}"
        )
        assert metrics.set_local == BASELINE_NO_ORG_SET_LOCAL, (
            f"No-org baseline SET LOCAL: expected "
            f"{BASELINE_NO_ORG_SET_LOCAL}, got {metrics.set_local}"
        )

    # ------------------------------------------------------------------
    # Scenario 2: Org context, autocommit (AF9 per-statement wrapping)
    # ------------------------------------------------------------------
    # Each data query triggers the AF9 wrapper's autocommit path:
    # ``transaction.atomic()`` → BEGIN + SET LOCAL + data + COMMIT.
    # The queries are exercised through the real ``OrgDashboardView``
    # endpoint via ``TenantMiddleware`` (session-org resolution through
    # the non-management URL ``/sa41-bench/<slug>/``).  The middleware
    # pre-sets ``request.org``, so the view skips the slug lookup and
    # only issues 2 data SELECTs (membership role check + member count).
    #
    # Expected: 8 SQL statements = 2 × (BEGIN + SET LOCAL + SELECT + COMMIT).
    # Amplification: 4× over the unprimed data baseline.

    @pytest.mark.django_db(transaction=True)
    def test_with_org_autocommit(self, _seeded_org) -> None:
        org, user = _seeded_org
        response, metrics = _call_org_dashboard(org=org, user=user)

        assert response.status_code == 200

        print(f"\n[SA4.1]  With-org autocommit:      {metrics.summary()}")
        print(
            f"[SA4.1]    → Amplification factor:   "
            f"{metrics.amplification_factor:.1f}x "
            f"(baseline {BASELINE_AUTOCOMMIT_AMPLIFICATION:.1f}x)"
        )

        assert metrics.total == BASELINE_AUTOCOMMIT_TOTAL, (
            f"Autocommit total: expected {BASELINE_AUTOCOMMIT_TOTAL}, "
            f"got {metrics.total}"
        )
        assert metrics.data_statements == BASELINE_AUTOCOMMIT_DATA, (
            f"Autocommit data: expected {BASELINE_AUTOCOMMIT_DATA}, "
            f"got {metrics.data_statements}"
        )
        assert metrics.begin == BASELINE_AUTOCOMMIT_BEGIN, (
            f"Autocommit BEGIN: expected {BASELINE_AUTOCOMMIT_BEGIN}, "
            f"got {metrics.begin}"
        )
        assert metrics.commit == BASELINE_AUTOCOMMIT_COMMIT, (
            f"Autocommit COMMIT: expected {BASELINE_AUTOCOMMIT_COMMIT}, "
            f"got {metrics.commit}"
        )
        assert metrics.set_local == BASELINE_AUTOCOMMIT_SET_LOCAL, (
            f"Autocommit SET LOCAL: expected "
            f"{BASELINE_AUTOCOMMIT_SET_LOCAL}, got {metrics.set_local}"
        )
        assert metrics.amplification_factor == pytest.approx(
            BASELINE_AUTOCOMMIT_AMPLIFICATION, rel=1e-3
        ), (
            f"Autocommit amplification: expected "
            f"{BASELINE_AUTOCOMMIT_AMPLIFICATION:.1f}x, "
            f"got {metrics.amplification_factor:.1f}x"
        )

    # ------------------------------------------------------------------
    # Scenario 3: Org context, explicit transaction
    # ------------------------------------------------------------------
    # The caller wraps the query pattern in ``transaction.atomic()``.
    # AF9's explicit-transaction path fires on each statement inside the
    # atomic: just ``SET LOCAL`` (no short atomic wrapping).  The queries
    # are exercised through the real ``OrgDashboardView`` endpoint via
    # ``TenantMiddleware``, with the entire dispatch chain inside the
    # caller-managed atomic.  The middleware pre-sets ``request.org``,
    # so only 2 data SELECTs are issued (membership role check + member
    # count).
    #
    # ``CaptureQueriesContext`` is nested inside the outer atomic, so no
    # BEGIN/COMMIT appear in the capture (in ``transaction=True`` mode
    # the outer atomic creates a savepoint before the capture window
    # opens).
    #
    # Expected: 4 SQL statements = 2 × (SET LOCAL + SELECT).
    # Amplification: 2.0× over the unprimed data baseline.
    #
    # The first SET LOCAL is required priming (it establishes the org
    # context for the transaction); only the second SET LOCAL inside the
    # same transaction is redundant.  That redundant SET LOCAL is the
    # overhead that **SA4.2 will eliminate** with per-transaction memo.
    # Saving 1 SET LOCAL reduces the captured total from 4 → 3.

    @pytest.mark.django_db(transaction=True)
    def test_with_org_explicit_transaction(self, _seeded_org) -> None:
        org, user = _seeded_org

        def _call_in_txn():
            with db_transaction.atomic():
                return _call_org_dashboard(org=org, user=user)

        response, metrics = _call_in_txn()

        assert response.status_code == 200

        print(f"\n[SA4.1]  With-org explicit txn:    {metrics.summary()}")
        print(
            f"[SA4.1]    → Amplification factor:   "
            f"{metrics.amplification_factor:.1f}x "
            f"(baseline {BASELINE_EXPLICIT_TXN_AMPLIFICATION:.2f}x)"
        )

        assert metrics.total == BASELINE_EXPLICIT_TXN_TOTAL, (
            f"Explicit-txn total: expected {BASELINE_EXPLICIT_TXN_TOTAL}, "
            f"got {metrics.total}"
        )
        assert metrics.data_statements == BASELINE_EXPLICIT_TXN_DATA, (
            f"Explicit-txn data: expected {BASELINE_EXPLICIT_TXN_DATA}, "
            f"got {metrics.data_statements}"
        )
        assert metrics.begin == BASELINE_EXPLICIT_TXN_BEGIN, (
            f"Explicit-txn BEGIN: expected {BASELINE_EXPLICIT_TXN_BEGIN}, "
            f"got {metrics.begin}"
        )
        assert metrics.commit == BASELINE_EXPLICIT_TXN_COMMIT, (
            f"Explicit-txn COMMIT: expected {BASELINE_EXPLICIT_TXN_COMMIT}, "
            f"got {metrics.commit}"
        )
        assert metrics.set_local == BASELINE_EXPLICIT_TXN_SET_LOCAL, (
            f"Explicit-txn SET LOCAL: expected "
            f"{BASELINE_EXPLICIT_TXN_SET_LOCAL}, got {metrics.set_local}"
        )
        assert metrics.amplification_factor == pytest.approx(
            BASELINE_EXPLICIT_TXN_AMPLIFICATION, rel=1e-2
        ), (
            f"Explicit-txn amplification: expected "
            f"{BASELINE_EXPLICIT_TXN_AMPLIFICATION:.2f}x, "
            f"got {metrics.amplification_factor:.2f}x"
        )

    # ------------------------------------------------------------------
    # Summary output
    # ------------------------------------------------------------------
    # The ``print()`` calls above produce a compact three-line benchmark
    # report when run with ``pytest -s -k TestSa41StatementAmplification``.
    # Example:
    #
    #   [SA4.1]  No-org autocommit:        total=3, data=3, txn=(0B+0C+0R),
    #       set_local=0, savepoint=(0SP+0RL)
    #   [SA4.1]    → Amplification factor:   1.0x
    #   [SA4.1]  With-org autocommit:      total=8, data=2, txn=(2B+2C+0R),
    #       set_local=2, savepoint=(0SP+0RL)
    #   [SA4.1]    → Amplification factor:   4.0x  (baseline 4.0x)
    #   [SA4.1]  With-org explicit txn:    total=4, data=2, txn=(0B+0C+0R),
    #       set_local=2, savepoint=(0SP+0RL)
    #   [SA4.1]    → Amplification factor:   2.0x  (baseline 2.00x)
    #
    # Baselines are request-bound — measured through the real
    # ``TenantMiddleware`` session-org resolution path (via the
    # non-management URL ``/sa41-bench/<slug>/``), so they reflect
    # the exact amplification that production content routes see.
    # The explicit-transaction capture starts inside the outer atomic
    # (``CaptureQueriesContext`` is nested), so no BEGIN/COMMIT appear
    # in the measured totals.
