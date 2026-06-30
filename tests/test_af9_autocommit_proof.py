"""AF9 Phase 3 — Autocommit request-path GUC priming proof (PR-AF9-001).

Proves that the AF9 execute wrapper primes ``app.current_org_id`` from
the ContextVar during an autocommit request-path cursor.execute(), and
that the GUC does NOT persist after the request completes (AF4 regression
guard — no request-long transaction).

Structure
---------
1. Seed an Organization row and establish a session org context via
   ``set_current_org_id()``.
2. Process a synthetic request (``RequestFactory`` + ``TenantMiddleware``)
   through the ``af9_guc_probe_view`` which runs a direct
   ``cursor.execute()`` and returns the DB-level ``app.current_org_id``.
3. Assert the probe response carries the expected org UUID — proving the
   wrapper primed the GUC from the ContextVar in the same transaction as
   the view's DB statement.
4. After the request completes, assert that ``current_setting`` returns
   ``''`` (session default) — proving no request-long GUC leak.
"""

from __future__ import annotations


import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory

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
from tests.urls import af9_guc_probe_view


@pytest.mark.django_db(transaction=True)
class TestAf9AutocommitRequestPathProof:
    """PR-AF9-001: Autocommit GUC priming proof through a request path."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        self.user = get_user_model().objects.create_user(
            username="af9-probe",
            email="af9-probe@example.com",
            password="secret123",
        )
        self.organization = Organization.objects.create(
            name="AF9 Probe Org", slug="af9-probe-org"
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            role=OrgRole.MEMBER,
        )

    def _send_autocommit_request(self) -> str:
        """Send a request through middleware + probe view, return response body."""
        request = RequestFactory().get("/_af9/guc-probe/")
        request.user = self.user
        request.session = {ACTIVE_ORG_SESSION_KEY: str(self.organization.pk)}
        response = TenantMiddleware(af9_guc_probe_view)(request)
        assert response.status_code == 200
        return response.content.decode()

    # ------------------------------------------------------------------
    # Proof A: GUC is primed inside the request-path cursor.execute()
    # ------------------------------------------------------------------

    def test_guc_is_primed_during_request(self) -> None:
        """The autocommit request-path receives the primed GUC inside
        the view's ``cursor.execute()`` — proving the AF9 execute wrapper
        issues ``SET LOCAL`` from the ContextVar in the same short
        ``transaction.atomic()`` block as the view's DB statement."""
        body = self._send_autocommit_request()
        assert body == str(self.organization.pk), (
            f"Expected the probe view to return the org UUID "
            f"({self.organization.pk}), got {body!r}. "
            "The AF9 execute wrapper must prime app.current_org_id "
            "from the ContextVar during autocommit request-path queries."
        )

    # ------------------------------------------------------------------
    # Proof B: No GUC leak after the request completes
    # ------------------------------------------------------------------

    def test_guc_is_not_leaked_after_request(self) -> None:
        """After the autocommit request completes, the GUC returns to
        the session default (empty string) — proving the short atomic
        exited cleanly and no request-long transaction is held."""
        self._send_autocommit_request()

        # ContextVar was reset by middleware cleanup.
        assert get_current_org_id() is None, (
            "Middleware must reset the ContextVar after the request."
        )

        # DB-level GUC must also be at session default.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
        assert raw == "" or raw is None, (
            "After the autocommit request, app.current_org_id must be "
            f"at the session default, got {raw!r}. "
            "The short atomic must commit and the GUC must revert "
            "(AF4 no-request-long-transaction guard)."
        )

    # ------------------------------------------------------------------
    # Proof C: No GUC when ContextVar is not set
    # ------------------------------------------------------------------

    def test_no_guc_when_contextvar_unset(self) -> None:
        """When no ContextVar is active, the probe view returns empty,
        proving the wrapper does not prime without a ContextVar.

        Calls the view directly (bypassing middleware) because the
        middleware redirects to ``/orgs/`` when no session org exists.
        """
        reset_current_org_id()

        request = RequestFactory().get("/_af9/guc-probe/")
        response = af9_guc_probe_view(request)
        assert response.status_code == 200
        body = response.content.decode()
        assert body == "", (
            f"When ContextVar is unset, the probe must return empty, got {body!r}"
        )
