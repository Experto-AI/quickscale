"""Tests for billing's organization-removal provider-state declarations.

Module Conventions rule 34: billing declares the executor hooks its
boundary-guarded provider fields name, and the purge boundary runs them
through the declaration, so no lower-layer module names billing.
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest

from quickscale_modules_billing.apps import QuickscaleBillingConfig
from quickscale_modules_billing.models import Plan, Subscription
from quickscale_modules_billing._removal import (
    guard_organization_removal_provider_state,
)
from quickscale_modules_orgs.removal import (
    BILLING_PERSONAL_DATA,
    BILLING_PROVIDER_STATE,
    BoundaryGuardedHooks,
    RemovalAction,
)


def _billing_config() -> QuickscaleBillingConfig:
    return QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )


def _plan() -> Plan:
    return Plan.objects.create(
        name="Starter",
        slug="starter",
        stripe_price_id="price_starter_monthly",
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )


def test_removal_obligation_declares_its_boundary_guard_hooks() -> None:
    """The guarded obligation names billing's own executor hooks."""
    provider_state, personal_data = _billing_config().removal_obligations()

    assert provider_state.name == BILLING_PROVIDER_STATE
    assert provider_state.boundary_guarded_hooks == BoundaryGuardedHooks(
        guard="guard_organization_removal_provider_state",
        reconcile="reconcile_organization_removal_provider_state",
        mutation_lock="organization_removal_provider_mutation_lock",
    )
    assert personal_data.name == BILLING_PERSONAL_DATA
    assert personal_data.anonymize_action is RemovalAction.ANONYMIZE
    assert personal_data.purge_action is RemovalAction.SKIP
    assert callable(_billing_config().anonymize_account)


def test_guard_hook_delegates_to_the_service() -> None:
    """The declared hook runs the billing service, not another module's code."""
    with patch(
        "quickscale_modules_billing._removal.guard_organization_removal_provider_state",
        return_value="Cannot purge.",
    ) as guard:
        result = _billing_config().guard_organization_removal_provider_state(
            "org-1",
            provider_expired_checkout_id="cs_expired",
        )

    assert result == "Cannot purge."
    guard.assert_called_once_with("org-1", provider_expired_checkout_id="cs_expired")


@pytest.mark.django_db
def test_guard_allows_an_organization_with_no_provider_state(
    organization, org_context
) -> None:
    """An organization without billing rows is removable."""
    assert guard_organization_removal_provider_state(organization) == ""


@pytest.mark.django_db
def test_guard_refuses_a_current_subscription(user, organization, org_context) -> None:
    """A current subscription with a provider id refuses the purge."""
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(),
        stripe_subscription_id="sub_live",
        status=Subscription.Status.ACTIVE,
    )

    reason = guard_organization_removal_provider_state(organization)

    assert "current Stripe subscriptions: sub_live" in reason


@pytest.mark.django_db
def test_guard_refuses_a_current_subscription_without_a_provider_id(
    user, organization, org_context
) -> None:
    """A current subscription with no provider id cannot be reconciled."""
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(),
        status=Subscription.Status.ACTIVE,
    )

    reason = guard_organization_removal_provider_state(organization)

    assert "no provider id" in reason


@pytest.mark.django_db
def test_guard_refuses_a_pending_checkout(user, organization, org_context) -> None:
    """An incomplete checkout Stripe has not confirmed expired refuses the purge."""
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(),
        stripe_checkout_session_id="cs_pending",
        status=Subscription.Status.INCOMPLETE,
    )

    reason = guard_organization_removal_provider_state(organization)

    assert "checkout is pending" in reason


@pytest.mark.django_db
def test_guard_excludes_a_provider_confirmed_expired_checkout(
    user, organization, org_context
) -> None:
    """A checkout the caller reconciled to provider expiry does not refuse."""
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=_plan(),
        stripe_checkout_session_id="cs_expired",
        status=Subscription.Status.INCOMPLETE,
    )

    assert (
        guard_organization_removal_provider_state(
            organization,
            provider_expired_checkout_id="cs_expired",
        )
        == ""
    )
