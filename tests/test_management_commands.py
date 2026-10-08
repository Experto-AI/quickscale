"""Tests for billing's operator checkout-reconciliation command."""

from __future__ import annotations

import quickscale_modules_billing._payload as _payload

from dataclasses import dataclass, field
from datetime import timedelta
from io import StringIO
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from quickscale_modules_billing.models import Plan, PurchaseCheckout, Subscription
from quickscale_modules_orgs.current_org import org_scope
from quickscale_modules_orgs.models import Organization


@dataclass
class _FakeReconciliationClient:
    """Provider double for the command's read-only reconciliation lookups."""

    checkout_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    searched_customer_references: list[str] = field(default_factory=list)

    def search_customers(
        self, *, organization_reference: str = "", **kwargs: Any
    ) -> list[dict[str, Any]]:
        del kwargs
        self.searched_customer_references.append(organization_reference)
        return []

    def retrieve_checkout_session(self, *, checkout_session_id: str) -> dict[str, Any]:
        return dict(self.checkout_sessions.get(checkout_session_id, {}))

    def find_checkout_session_by_reference(
        self,
        *,
        customer_id: str,
        metadata_key: str,
        reference: str,
    ) -> dict[str, Any] | None:
        del customer_id
        for session in self.checkout_sessions.values():
            metadata = session.get("metadata") or {}
            if str(metadata.get(metadata_key) or "") == reference:
                return dict(session)
        return None


def _plan(*, slug: str = "reconcile-command-plan") -> Plan:
    return Plan.objects.create(
        name="Command",
        slug=slug,
        stripe_price_id=f"price_{slug}",
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.ONE_TIME,
    )


def _run_command(
    fake_client: _FakeReconciliationClient,
    **options: Any,
) -> tuple[str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with patch(
        "quickscale_modules_billing._stripe_client.get_stripe_client",
        return_value=fake_client,
    ):
        call_command(
            "quickscale_billing_reconcile_checkouts",
            stdout=stdout,
            stderr=stderr,
            **options,
        )
    return stdout.getvalue(), stderr.getvalue()


@pytest.mark.django_db
def test_reconcile_checkouts_closes_an_unknown_purchase_outcome(
    user,
    organization,
    org_context,
) -> None:
    """A session-less reservation the provider does not hold is closed."""
    reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(),
        status=PurchaseCheckout.Status.PREPARING,
    )

    stdout, stderr = _run_command(_FakeReconciliationClient())

    reservation.refresh_from_db()
    assert reservation.status == PurchaseCheckout.Status.EXPIRED
    assert stderr == ""
    assert "Closed 1 reservation(s); 0 organization(s) still blocked." in stdout


@pytest.mark.django_db
def test_reconcile_checkouts_dry_run_writes_nothing(
    user,
    organization,
    org_context,
) -> None:
    """``--dry-run`` resolves nothing locally and says so."""
    reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-dry-run"),
        status=PurchaseCheckout.Status.PREPARING,
    )

    stdout, _stderr = _run_command(
        _FakeReconciliationClient(),
        dry_run=True,
    )

    reservation.refresh_from_db()
    assert reservation.status == PurchaseCheckout.Status.PREPARING
    assert "Dry run" in stdout


@pytest.mark.django_db
def test_reconcile_checkouts_reports_a_blocked_subscription(
    user,
    organization,
    org_context,
) -> None:
    """A live session found by reference is adopted, reported, and left open."""
    reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-blocked"),
        status=Subscription.Status.INCOMPLETE,
        stripe_customer_id="cus_command_blocked",
    )
    reference = _payload._subscription_checkout_reference(reservation)
    fake_client = _FakeReconciliationClient(
        checkout_sessions={
            "cs_command_open": {
                "id": "cs_command_open",
                "status": "open",
                "metadata": {
                    "quickscale_subscription_checkout_reference": reference,
                },
            }
        }
    )

    stdout, stderr = _run_command(fake_client)

    reservation.refresh_from_db()
    assert reservation.stripe_checkout_session_id == "cs_command_open"
    assert "is still open" in stderr
    assert "0 organization(s) still blocked." not in stdout
    assert "1 organization(s) still blocked." in stdout


@pytest.mark.django_db
def test_reconcile_checkouts_limits_to_the_requested_organization(
    user,
    organization,
    org_context,
) -> None:
    """``--organization`` leaves other organizations untouched."""
    targeted = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-targeted"),
        status=PurchaseCheckout.Status.PREPARING,
    )
    other_organization = Organization.objects.create(
        name="Other Reconcile",
        slug="other-reconcile",
    )
    with org_scope(other_organization):
        untargeted = PurchaseCheckout.all_objects.create(
            organization=other_organization,
            plan=_plan(slug="reconcile-command-untargeted"),
            status=PurchaseCheckout.Status.PREPARING,
        )

    _stdout, _stderr = _run_command(
        _FakeReconciliationClient(),
        organization=str(organization.pk),
    )

    targeted.refresh_from_db()
    with org_scope(other_organization):
        untargeted.refresh_from_db()
    assert targeted.status == PurchaseCheckout.Status.EXPIRED
    assert untargeted.status == PurchaseCheckout.Status.PREPARING


@pytest.mark.django_db
def test_reconcile_checkouts_continues_past_a_live_purchase_reservation(
    user,
    organization,
    org_context,
) -> None:
    """A live purchase blocks its own row without hiding a later resolvable one."""
    live_reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-live"),
        stripe_checkout_session_id="cs_command_live",
        status=PurchaseCheckout.Status.OPEN,
    )
    resolvable_reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-behind-live"),
        status=PurchaseCheckout.Status.PREPARING,
    )
    fake_client = _FakeReconciliationClient(
        checkout_sessions={
            "cs_command_live": {"id": "cs_command_live", "status": "open"},
        }
    )

    stdout, stderr = _run_command(fake_client)

    live_reservation.refresh_from_db()
    resolvable_reservation.refresh_from_db()
    assert live_reservation.status == PurchaseCheckout.Status.OPEN
    assert resolvable_reservation.status == PurchaseCheckout.Status.EXPIRED
    assert "is still open" in stderr
    assert "1 organization(s) still blocked." in stdout


@pytest.mark.django_db
def test_reconcile_checkouts_inspects_a_known_session_beyond_local_expiry(
    user,
    organization,
    org_context,
) -> None:
    """A future-expiry reservation is inspected, not reported as unblocked."""
    reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-future"),
        stripe_checkout_session_id="cs_command_future_open",
        stripe_customer_id="cus_command_future",
        status=Subscription.Status.INCOMPLETE,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    fake_client = _FakeReconciliationClient(
        checkout_sessions={
            "cs_command_future_open": {
                "id": "cs_command_future_open",
                "status": "open",
            },
        }
    )

    stdout, stderr = _run_command(fake_client)

    reservation.refresh_from_db()
    assert reservation.status == Subscription.Status.INCOMPLETE
    assert "is still open" in stderr
    assert "1 organization(s) still blocked." in stdout


@pytest.mark.django_db
def test_reconcile_checkouts_clears_a_provider_expired_reservation_beyond_local_expiry(
    user,
    organization,
    org_context,
) -> None:
    """A provider-expired reservation clears even before its local expiry."""
    reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-provider-expired"),
        stripe_checkout_session_id="cs_command_provider_expired",
        stripe_customer_id="cus_command_provider_expired",
        status=Subscription.Status.INCOMPLETE,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    fake_client = _FakeReconciliationClient(
        checkout_sessions={
            "cs_command_provider_expired": {
                "id": "cs_command_provider_expired",
                "status": "expired",
            },
        }
    )

    stdout, stderr = _run_command(fake_client)

    reservation.refresh_from_db()
    assert reservation.status == Subscription.Status.INCOMPLETE_EXPIRED
    assert stderr == ""
    assert "Closed 1 reservation(s); 0 organization(s) still blocked." in stdout


@pytest.mark.django_db
def test_reconcile_checkouts_continues_past_a_provider_lookup_error(
    user,
    organization,
    org_context,
) -> None:
    """A provider failure on one row does not hide a later resolvable row."""
    import stripe

    broken_reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-provider-error"),
        stripe_checkout_session_id="cs_command_missing",
        status=PurchaseCheckout.Status.OPEN,
    )
    resolvable_reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-behind-error"),
        status=PurchaseCheckout.Status.PREPARING,
    )
    fake_client = _FakeReconciliationClient()

    def reject_retrieval(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        raise stripe.InvalidRequestError("No such checkout session", None)

    fake_client.retrieve_checkout_session = reject_retrieval  # type: ignore[method-assign]

    stdout, stderr = _run_command(fake_client)

    broken_reservation.refresh_from_db()
    resolvable_reservation.refresh_from_db()
    assert broken_reservation.status == PurchaseCheckout.Status.OPEN
    assert resolvable_reservation.status == PurchaseCheckout.Status.EXPIRED
    assert "Stripe purchase checkout reconciliation failed" in stderr
    assert "Closed 1 reservation(s); 1 organization(s) still blocked." in stdout


@pytest.mark.django_db
def test_reconcile_checkouts_holds_the_provider_mutation_lock(
    user,
    organization,
    org_context,
) -> None:
    """Selection, lookup, and persistence run under the provider mutex."""
    from contextlib import contextmanager

    PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(slug="reconcile-command-lock"),
        status=PurchaseCheckout.Status.PREPARING,
    )
    lock_state = {"held": False}
    observed: list[bool] = []

    @contextmanager
    def record_lock(locked_organization: Any):
        del locked_organization
        lock_state["held"] = True
        try:
            yield
        finally:
            lock_state["held"] = False

    def record_purchase_pass(organization_id: Any, *, persist: bool):
        del organization_id, persist
        observed.append(lock_state["held"])
        return (), ()

    with (
        patch(
            "quickscale_modules_billing._locks.subscription_provider_mutation_lock",
            record_lock,
        ),
        patch(
            "quickscale_modules_billing.management.commands."
            "quickscale_billing_reconcile_checkouts._reconcile_all_purchase_checkouts",
            record_purchase_pass,
        ),
        patch(
            "quickscale_modules_billing._stripe_client.get_stripe_client",
            return_value=_FakeReconciliationClient(),
        ),
    ):
        call_command(
            "quickscale_billing_reconcile_checkouts",
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert observed == [True]
    assert lock_state["held"] is False


@pytest.mark.django_db
def test_reconcile_checkouts_rejects_unknown_and_malformed_organizations() -> None:
    """A missing or malformed ``--organization`` fails before any lookup."""
    fake_client = _FakeReconciliationClient()
    with patch(
        "quickscale_modules_billing._stripe_client.get_stripe_client",
        return_value=fake_client,
    ):
        with pytest.raises(CommandError, match="No organization found"):
            call_command(
                "quickscale_billing_reconcile_checkouts",
                organization=str(uuid4()),
                stdout=StringIO(),
                stderr=StringIO(),
            )
        with pytest.raises(CommandError, match="Invalid organization primary key"):
            call_command(
                "quickscale_billing_reconcile_checkouts",
                organization="not-a-uuid",
                stdout=StringIO(),
                stderr=StringIO(),
            )
