"""Cross-tenant isolation tests for the billing module.

Tenant isolation is enforced by the ``TenantManager`` (ambient ContextVar).
These tests prove that every organization-scoped billing model hides one
organization's rows from another, that the managers stay fail-closed
without an org context, and that the operator escape hatch still sees
every organization's rows.
"""

from __future__ import annotations

from typing import Any, NamedTuple

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    PurchaseCheckout,
    Subscription,
)
from quickscale_modules_orgs.current_org import operator_access, set_current_org_id
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
)

_TENANT_MODELS = (CreditTransaction, CreditBalance, PurchaseCheckout, Subscription)


class _Tenants(NamedTuple):
    org_a: Organization
    org_b: Organization
    admin_a: object
    plan: Plan


@pytest.fixture
def billing_tenants(db) -> _Tenants:
    """Two organizations, one admin, and a system-wide plan."""
    user_model = get_user_model()
    org_a = Organization.objects.create(name="Org A", slug="billing-org-a")
    org_b = Organization.objects.create(name="Org B", slug="billing-org-b")
    admin_a = user_model.objects.create_user(
        username="billing-org-a-admin",
        email="billing-org-a-admin@example.com",
        password="TestPass123!",
    )
    OrganizationMembership.objects.create(
        user=admin_a,
        organization=org_a,
        role=OrgRole.ADMIN,
    )
    plan = Plan.objects.create(
        name="Isolation Plan",
        slug="billing-isolation-plan",
        stripe_price_id="price_billing_isolation",
        credits_per_period=100,
        price_cents=0,
    )
    return _Tenants(org_a=org_a, org_b=org_b, admin_a=admin_a, plan=plan)


def _create_transaction(
    *,
    org: Organization,
    user: object,
    description: str,
    amount: int,
) -> CreditTransaction:
    """Create one credit transaction while the org context is active."""
    set_current_org_id(org.id)
    try:
        return CreditTransaction.objects.create(
            organization=org,
            user=user,
            amount=amount,
            transaction_type=CreditTransaction.TransactionType.PURCHASE,
            description=description,
            balance_after=amount,
        )
    finally:
        set_current_org_id(None)


def _create_balance(
    *,
    org: Organization,
    user: object,
    balance: int,
) -> CreditBalance:
    """Create one credit balance while the org context is active."""
    set_current_org_id(org.id)
    try:
        return CreditBalance.objects.create(
            organization=org,
            user=user,
            balance=balance,
        )
    finally:
        set_current_org_id(None)


def _create_checkout(
    *,
    org: Organization,
    user: object,
    plan: Plan,
) -> PurchaseCheckout:
    """Create one purchase checkout while the org context is active."""
    set_current_org_id(org.id)
    try:
        return PurchaseCheckout.objects.create(
            organization=org,
            user=user,
            plan=plan,
        )
    finally:
        set_current_org_id(None)


def _create_subscription(
    *,
    org: Organization,
    user: object,
    plan: Plan,
    suffix: str,
) -> Subscription:
    """Create one subscription while the org context is active."""
    set_current_org_id(org.id)
    try:
        return Subscription.objects.create(
            organization=org,
            user=user,
            plan=plan,
            stripe_customer_id=f"cus_{suffix}",
        )
    finally:
        set_current_org_id(None)


def _create_tenant_rows(
    tenants: _Tenants, *, org: Organization, suffix: str
) -> dict[type, Any]:
    """Create one row of every billing tenant model for *org*."""
    return {
        CreditTransaction: _create_transaction(
            org=org,
            user=tenants.admin_a,
            description=f"{suffix} transaction",
            amount=10,
        ),
        CreditBalance: _create_balance(org=org, user=tenants.admin_a, balance=10),
        PurchaseCheckout: _create_checkout(
            org=org, user=tenants.admin_a, plan=tenants.plan
        ),
        Subscription: _create_subscription(
            org=org, user=tenants.admin_a, plan=tenants.plan, suffix=suffix
        ),
    }


@pytest.mark.isolation
@pytest.mark.django_db
class TestBillingIsolation:
    """Default-manager isolation across billing tenant tables."""

    def test_every_tenant_model_scopes_to_the_ambient_org(
        self,
        billing_tenants: _Tenants,
    ) -> None:
        """Each manager shows the ambient org's row and hides the other's."""
        tenants = billing_tenants
        rows_a = _create_tenant_rows(tenants, org=tenants.org_a, suffix="org-a")
        rows_b = _create_tenant_rows(tenants, org=tenants.org_b, suffix="org-b")

        for model in _TENANT_MODELS:
            set_current_org_id(tenants.org_a.id)
            try:
                assert model.objects.filter(pk=rows_a[model].pk).exists(), (
                    f"{model.__name__}: Org A cannot read its own row"
                )
                assert not model.objects.filter(pk=rows_b[model].pk).exists(), (
                    f"{model.__name__}: Org B's row is visible to Org A"
                )
            finally:
                set_current_org_id(None)

            set_current_org_id(tenants.org_b.id)
            try:
                assert model.objects.filter(pk=rows_b[model].pk).exists(), (
                    f"{model.__name__}: Org B cannot read its own row"
                )
                assert not model.objects.filter(pk=rows_a[model].pk).exists(), (
                    f"{model.__name__}: Org A's row is visible to Org B"
                )
            finally:
                set_current_org_id(None)

    def test_tenant_models_are_fail_closed_without_an_org_context(
        self,
        billing_tenants: _Tenants,
    ) -> None:
        """With no ambient org, every tenant manager returns nothing."""
        _create_tenant_rows(billing_tenants, org=billing_tenants.org_a, suffix="org-a")

        set_current_org_id(None)
        for model in _TENANT_MODELS:
            assert model.objects.count() == 0, (
                f"{model.__name__} must fail closed without an org context"
            )


@pytest.mark.isolation
@pytest.mark.django_db(transaction=True)
def test_operator_access_sees_all_organizations_tenant_rows(
    billing_tenants: _Tenants,
) -> None:
    """``all_objects`` inside ``operator_access()`` sees cross-org rows."""
    tenants = billing_tenants
    rows_a = _create_tenant_rows(tenants, org=tenants.org_a, suffix="org-a")
    rows_b = _create_tenant_rows(tenants, org=tenants.org_b, suffix="org-b")

    with transaction.atomic():
        with operator_access(reason="billing cross-tenant operator read"):
            for model in _TENANT_MODELS:
                visible = set(
                    model.all_objects.filter(
                        pk__in=[rows_a[model].pk, rows_b[model].pk]
                    ).values_list("pk", flat=True)
                )
                assert visible == {rows_a[model].pk, rows_b[model].pk}, (
                    f"{model.__name__}: operator access cannot read both orgs' rows"
                )
