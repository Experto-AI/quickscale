"""Tests for billing checkout and webhook views."""

from __future__ import annotations

from datetime import timedelta
import json
from typing import Any

import pytest
from django.conf import settings
from django.test import Client, RequestFactory
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils import timezone

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_billing.services import (
    BillingConfigurationError,
    BillingDisabledError,
    BillingValidationError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    StripeWebhookResult,
)
from quickscale_modules_billing.views import (
    BillingPortalReturnView,
    CreateCheckoutSessionView,
    PricingPageView,
)
from quickscale_modules_orgs.middleware import TenantMiddleware
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


def _create_one_time_plan(
    *,
    slug: str = "credits-pack",
    price_id: str = "price_credits_pack",
    credits: int = 250,
    price_cents: int = 4900,
) -> Plan:
    return Plan.objects.create(
        name="Credits Pack",
        slug=slug,
        stripe_price_id=price_id,
        credits_per_period=credits,
        price_cents=price_cents,
        currency="usd",
        billing_interval=Plan.BillingInterval.ONE_TIME,
        is_active=True,
    )


def _create_recurring_plan(
    *,
    slug: str = "starter-monthly",
    price_id: str = "price_starter_monthly",
    credits: int = 100,
    price_cents: int = 1900,
    currency: str = "usd",
    interval: str = Plan.BillingInterval.MONTHLY,
    is_active: bool = True,
    name: str = "Starter Monthly",
) -> Plan:
    return Plan.objects.create(
        name=name,
        slug=slug,
        stripe_price_id=price_id,
        credits_per_period=credits,
        price_cents=price_cents,
        currency=currency,
        billing_interval=interval,
        is_active=is_active,
    )


def _create_credit_transaction(
    *,
    user: Any,
    amount: int,
    balance_after: int,
    description: str,
    organization: Any | None = None,
) -> CreditTransaction:
    return CreditTransaction.objects.create(
        user=user,
        organization=organization,
        amount=amount,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description=description,
        balance_after=balance_after,
    )


_OWNER_ONLY_ROLES = (OrgRole.ADMIN, OrgRole.MEMBER, OrgRole.VIEWER)
_ORG_OWNER_ONLY_READ_ROUTES = (
    "org-billing-dashboard",
    "org-credit-balance",
    "org-credit-transactions",
    "org-subscription-detail",
)
_FLAT_OWNER_ONLY_READ_ROUTES = (
    "billing-dashboard",
    "credit-balance",
    "credit-transactions",
    "subscription-detail",
)
_ORG_OWNER_ONLY_MUTATION_ROUTES = (
    (
        "org-purchase-checkout",
        {"plan_slug": "ignored-owner-checkout"},
        "quickscale_modules_billing.views.create_checkout_session",
        "https://checkout.stripe.test/ignored",
    ),
    (
        "org-subscription-checkout",
        {"plan_slug": "ignored-owner-subscription"},
        "quickscale_modules_billing.views.create_subscription_checkout_session",
        "https://checkout.stripe.test/ignored-subscription",
    ),
    (
        "org-subscription-cancel-current",
        {},
        "quickscale_modules_billing.views.cancel_current_subscription",
        None,
    ),
    (
        "org-billing-portal-session",
        {},
        "quickscale_modules_billing.views.create_billing_portal_session",
        "https://billing.example.com/ignored-portal",
    ),
)
_FLAT_OWNER_ONLY_MUTATION_ROUTES = (
    (
        "purchase-checkout",
        {"plan_slug": "ignored-flat-owner-checkout"},
        "quickscale_modules_billing.views.create_checkout_session",
        "https://checkout.stripe.test/ignored-flat",
    ),
    (
        "subscription-checkout",
        {"plan_slug": "ignored-flat-owner-subscription"},
        "quickscale_modules_billing.views.create_subscription_checkout_session",
        "https://checkout.stripe.test/ignored-flat-subscription",
    ),
    (
        "subscription-cancel-current",
        {},
        "quickscale_modules_billing.views.cancel_current_subscription",
        None,
    ),
    (
        "billing-portal-session",
        {},
        "quickscale_modules_billing.views.create_billing_portal_session",
        "https://billing.example.com/ignored-flat-portal",
    ),
)


def test_checkout_view_returns_json_401_for_anonymous_requests() -> None:
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps({"plan_slug": "credits-pack"}),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}


def test_subscription_checkout_view_returns_json_401_for_anonymous_requests() -> None:
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(
        reverse("quickscale_billing:subscription-checkout"),
        data=json.dumps({"plan_slug": "starter-monthly"}),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}


def test_cancel_subscription_view_returns_json_401_for_anonymous_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    called = False

    def fake_cancel_current_subscription(
        auth_user,
        *,
        organization: Any | None = None,
    ) -> None:
        del auth_user, organization
        nonlocal called
        called = True

    monkeypatch.setattr(
        "quickscale_modules_billing.views.cancel_current_subscription",
        fake_cancel_current_subscription,
    )

    response = csrf_client.post(
        reverse("quickscale_billing:subscription-cancel-current"),
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}
    assert called is False


def test_billing_portal_session_view_returns_json_401_for_anonymous_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    called = False

    def fake_create_billing_portal_session(
        auth_user,
        return_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        del auth_user, return_url, organization
        nonlocal called
        called = True
        return "https://billing.example.com/portal-session"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_billing_portal_session",
        fake_create_billing_portal_session,
    )

    response = csrf_client.post(
        reverse("quickscale_billing:billing-portal-session"),
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}
    assert called is False


@pytest.mark.parametrize(
    "route_name",
    [
        "billing-config",
        "credit-balance",
        "credit-transactions",
        "subscription-detail",
    ],
)
def test_billing_read_views_return_json_401_for_anonymous_requests(
    client: Client,
    route_name: str,
) -> None:
    response = client.get(reverse(f"quickscale_billing:{route_name}"))

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}


@pytest.mark.django_db
def test_plan_list_view_is_public_and_returns_only_active_recurring_plans(
    client: Client,
) -> None:
    monthly_plan = _create_recurring_plan(
        slug="starter-monthly",
        price_id="price_starter_monthly",
        name="Starter Monthly",
    )
    yearly_plan = _create_recurring_plan(
        slug="starter-yearly",
        price_id="price_starter_yearly",
        price_cents=19000,
        credits=1200,
        interval=Plan.BillingInterval.YEARLY,
        name="Starter Yearly",
    )
    _create_one_time_plan(slug="credits-pack", price_id="price_credits_pack")
    _create_recurring_plan(
        slug="starter-inactive",
        price_id="price_starter_inactive",
        is_active=False,
        name="Starter Inactive",
    )

    response = client.get(reverse("quickscale_billing:subscription-plans"))

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": monthly_plan.name,
            "slug": monthly_plan.slug,
            "credits_per_period": monthly_plan.credits_per_period,
            "price_cents": monthly_plan.price_cents,
            "currency": monthly_plan.currency,
            "billing_interval": monthly_plan.billing_interval,
        },
        {
            "name": yearly_plan.name,
            "slug": yearly_plan.slug,
            "credits_per_period": yearly_plan.credits_per_period,
            "price_cents": yearly_plan.price_cents,
            "currency": yearly_plan.currency,
            "billing_interval": yearly_plan.billing_interval,
        },
    ]


def test_billing_dashboard_view_redirects_anonymous_users_to_login(
    client: Client,
) -> None:
    dashboard_url = reverse("quickscale_billing:billing-dashboard")

    response = client.get(dashboard_url)

    assert response.status_code == 302
    assert (
        response["Location"]
        == f"{resolve_url(settings.LOGIN_URL)}?next={dashboard_url}"
    )


@pytest.mark.django_db
def test_billing_dashboard_view_redirects_single_saas_org_membership_to_canonical_route(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:billing-dashboard"))

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/atlas/billing/dashboard/"


@pytest.mark.django_db
def test_billing_dashboard_view_redirects_ambiguous_saas_org_memberships_to_org_index(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    first_org = Organization.objects.create(name="Atlas", slug="atlas")
    second_org = Organization.objects.create(name="Beacon", slug="beacon")
    OrganizationMembership.objects.create(
        user=user,
        organization=first_org,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=second_org,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:billing-dashboard"))

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"


@pytest.mark.django_db
def test_billing_dashboard_view_renders_for_authenticated_users(
    client: Client,
    user,
) -> None:
    plan = _create_recurring_plan(
        slug="growth-monthly-dashboard-view",
        price_id="price_growth_monthly_dashboard_view",
        name="Growth Monthly",
    )
    current_period_start = timezone.now()
    CreditBalance.objects.create(user=user, balance=275)
    Subscription.objects.create(
        user=user,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        current_period_start=current_period_start,
        current_period_end=current_period_start + timedelta(days=30),
    )
    for index in range(11):
        _create_credit_transaction(
            user=user,
            amount=25,
            balance_after=25 * (index + 1),
            description=f"Dashboard entry {index + 1:02d}",
        )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:billing-dashboard"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Billing dashboard" in content
    assert "Credit balance" in content
    assert "275" in content
    assert "available credits" in content
    assert "Growth Monthly" in content
    assert "Active" in content
    assert "Manage via Stripe portal" in content
    assert "Cancel subscription" in content
    assert "Recent transactions" in content
    assert "Dashboard entry 11" in content
    assert "Dashboard entry 01" not in content
    assert 'id="billing-root"' in content
    assert 'data-view="dashboard"' in content


@pytest.mark.django_db
def test_org_billing_dashboard_view_renders_org_authoritative_state(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Helios", slug="helios")
    plan = _create_recurring_plan(
        slug="growth-monthly-org-dashboard-view",
        price_id="price_growth_monthly_org_dashboard_view",
        name="Growth Monthly",
    )
    current_period_start = timezone.now()
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    CreditBalance.objects.create(organization=organization, user=None, balance=275)
    Subscription.objects.create(
        user=user,
        organization=organization,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        current_period_start=current_period_start,
        current_period_end=current_period_start + timedelta(days=30),
    )
    for index in range(11):
        _create_credit_transaction(
            user=user,
            organization=organization,
            amount=25,
            balance_after=25 * (index + 1),
            description=f"Org dashboard entry {index + 1:02d}",
        )
    client.force_login(user)

    response = client.get(
        reverse(
            "quickscale_billing:org-billing-dashboard",
            kwargs={"org_slug": organization.slug},
        )
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Billing dashboard" in content
    assert "275" in content
    assert "Growth Monthly" in content
    assert "Org dashboard entry 11" in content
    assert "Org dashboard entry 01" not in content
    assert response.context["pricing_url"] == "/orgs/helios/billing/pricing/"


@pytest.mark.django_db
@pytest.mark.parametrize("role", _OWNER_ONLY_ROLES)
@pytest.mark.parametrize("route_name", _ORG_OWNER_ONLY_READ_ROUTES)
def test_org_billing_read_surfaces_require_owner_role(
    client: Client,
    user,
    settings,
    role: str,
    route_name: str,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Orion", slug="orion")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )
    client.force_login(user)

    response = client.get(
        reverse(
            f"quickscale_billing:{route_name}",
            kwargs={"org_slug": organization.slug},
        )
    )

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("role", _OWNER_ONLY_ROLES)
@pytest.mark.parametrize("route_name", _FLAT_OWNER_ONLY_READ_ROUTES)
def test_flat_billing_read_shims_require_owner_when_resolving_single_org(
    client: Client,
    user,
    settings,
    role: str,
    route_name: str,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Quasar", slug="quasar")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )
    client.force_login(user)

    response = client.get(reverse(f"quickscale_billing:{route_name}"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_pricing_page_view_is_public_and_render(client: Client) -> None:
    _create_recurring_plan(
        slug="growth-monthly",
        price_id="price_growth_monthly",
        name="Growth Monthly",
        price_cents=2900,
        credits=200,
    )
    _create_recurring_plan(
        slug="scale-yearly",
        price_id="price_scale_yearly",
        name="Scale Yearly",
        price_cents=24900,
        credits=3000,
        currency="eur",
        interval=Plan.BillingInterval.YEARLY,
    )
    _create_one_time_plan(
        slug="credits-pack-pricing-page",
        price_id="price_credits_pack_pricing_page",
        credits=500,
        price_cents=9900,
    )

    response = client.get(reverse("quickscale_billing:pricing-page"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Choose a billing plan" in content
    assert 'id="billing-root"' in content
    assert 'data-view="pricing"' in content
    assert "Monthly plans" in content
    assert "Yearly plans" in content
    assert "One-time credits" in content
    assert "Growth Monthly" in content
    assert "$29.00" in content
    assert "Scale Yearly" in content
    assert "EUR 249.00" in content
    assert "500 credits" in content
    assert "Sign in to purchase" in content
    assert f'href="{resolve_url(settings.LOGIN_URL)}?next=/billing/pricing/"' in content


@pytest.mark.django_db
def test_pricing_page_view_shows_dashboard_cta_for_authenticated_users(
    client: Client,
    user,
) -> None:
    _create_recurring_plan(
        slug="starter-authenticated",
        price_id="price_starter_authenticated",
        name="Starter Monthly",
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:pricing-page"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Go to dashboard" in content
    assert 'href="/billing/dashboard/"' in content
    assert "Sign in to purchase" not in content


@pytest.mark.django_db
def test_pricing_page_view_keeps_flat_dashboard_cta_for_authenticated_solo_request_org(
    user,
) -> None:
    _create_recurring_plan(
        slug="starter-authenticated-solo-request-org",
        price_id="price_starter_authenticated_solo_request_org",
        name="Starter Monthly",
    )
    request = RequestFactory().get("/billing/pricing/")
    request.user = user

    response = TenantMiddleware(PricingPageView.as_view())(request)
    response.render()
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Go to dashboard" in content
    assert 'href="/billing/dashboard/"' in content


@pytest.mark.django_db
def test_pricing_page_view_routes_single_saas_non_owner_to_canonical_org_pricing(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nova", slug="nova")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    _create_recurring_plan(
        slug="starter-authenticated-non-owner",
        price_id="price_starter_authenticated_non_owner",
        name="Starter Monthly",
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:pricing-page"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Go to dashboard" not in content
    assert "View pricing" in content
    assert 'href="/orgs/nova/billing/pricing/"' in content
    assert "Billing changes require an organization owner." in content


@pytest.mark.django_db
def test_org_pricing_page_view_shows_canonical_org_dashboard_cta_for_owner(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nova", slug="nova")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    _create_recurring_plan(
        slug="starter-authenticated-org",
        price_id="price_starter_authenticated_org",
        name="Starter Monthly",
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "quickscale_billing:org-pricing-page",
            kwargs={"org_slug": organization.slug},
        )
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Go to dashboard" in content
    assert 'href="/orgs/nova/billing/dashboard/"' in content


@pytest.mark.django_db
def test_org_pricing_page_view_keeps_non_owner_on_org_pricing_surface(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nova", slug="nova")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    _create_recurring_plan(
        slug="starter-authenticated-org-non-owner",
        price_id="price_starter_authenticated_org_non_owner",
        name="Starter Monthly",
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "quickscale_billing:org-pricing-page",
            kwargs={"org_slug": organization.slug},
        )
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Go to dashboard" not in content
    assert "View pricing" in content
    assert 'href="/orgs/nova/billing/pricing/"' in content
    assert "Billing changes require an organization owner." in content


@pytest.mark.django_db
def test_pricing_page_view_prompts_org_selection_for_ambiguous_saas_memberships(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    first_org = Organization.objects.create(name="Atlas", slug="atlas")
    second_org = Organization.objects.create(name="Beacon", slug="beacon")
    OrganizationMembership.objects.create(
        user=user,
        organization=first_org,
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=second_org,
        role=OrgRole.OWNER,
    )
    _create_recurring_plan(
        slug="starter-authenticated-ambiguous",
        price_id="price_starter_authenticated_ambiguous",
        name="Starter Monthly",
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:pricing-page"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Go to dashboard" not in content
    assert "Choose organization" in content
    assert 'href="/orgs/"' in content
    assert "Billing access requires choosing an organization first." in content


@pytest.mark.django_db
def test_pricing_page_view_formats_supported_zero_decimal_currency_without_fractional_division(
    client: Client,
) -> None:
    _create_recurring_plan(
        slug="jpy-monthly",
        price_id="price_jpy_monthly",
        name="Japan Monthly",
        price_cents=4900,
        credits=300,
        currency="jpy",
    )

    response = client.get(reverse("quickscale_billing:pricing-page"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Japan Monthly" in content
    assert "JPY 4,900" in content
    assert "JPY 49.00" not in content


@pytest.mark.django_db
def test_pricing_page_view_renders_empty_state_when_no_active_plans(
    client: Client,
) -> None:
    response = client.get(reverse("quickscale_billing:pricing-page"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "No billing plans are active right now." in content


@pytest.mark.django_db
def test_billing_config_view_returns_publishable_key_without_secret_key(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
    settings,
) -> None:
    settings.QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR = "PHASE_6A_PUBLISHABLE_KEY"
    settings.QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR = "PHASE_6A_SECRET_KEY"
    monkeypatch.setenv("PHASE_6A_PUBLISHABLE_KEY", "pk_test_phase_6a")
    monkeypatch.setenv("PHASE_6A_SECRET_KEY", "sk_test_phase_6a")
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:billing-config"))

    assert response.status_code == 200
    assert response.json() == {"publishable_key": "pk_test_phase_6a"}
    assert "secret_key" not in response.json()
    assert "sk_test_phase_6a" not in response.content.decode("utf-8")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("publishable_key_value",),
    [(None,), ("   ",)],
    ids=["missing", "blank"],
)
def test_billing_config_view_returns_500_for_missing_or_blank_publishable_key(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
    settings,
    publishable_key_value: str | None,
) -> None:
    settings.QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR = "PHASE_6A_PUBLISHABLE_KEY"
    settings.QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR = "PHASE_6A_SECRET_KEY"
    monkeypatch.setenv("PHASE_6A_SECRET_KEY", "sk_test_phase_6a")
    if publishable_key_value is None:
        monkeypatch.delenv("PHASE_6A_PUBLISHABLE_KEY", raising=False)
    else:
        monkeypatch.setenv("PHASE_6A_PUBLISHABLE_KEY", publishable_key_value)
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:billing-config"))

    assert response.status_code == 500
    assert response.json() == {
        "error": "Stripe publishable key is not configured in the runtime environment."
    }
    assert "publishable_key" not in response.json()
    assert "sk_test_phase_6a" not in response.content.decode("utf-8")


def test_checkout_view_missing_csrf_returns_403(user) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)

    response = csrf_client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps({"plan_slug": "credits-pack"}),
        content_type="application/json",
    )

    assert response.status_code == 403


def test_subscription_checkout_view_missing_csrf_returns_403(user) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)

    response = csrf_client.post(
        reverse("quickscale_billing:subscription-checkout"),
        data=json.dumps({"plan_slug": "starter-monthly"}),
        content_type="application/json",
    )

    assert response.status_code == 403


def test_cancel_subscription_view_missing_csrf_returns_403_without_calling_service(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    called = False

    def fake_cancel_current_subscription(
        auth_user,
        *,
        organization: Any | None = None,
    ) -> None:
        del auth_user, organization
        nonlocal called
        called = True

    monkeypatch.setattr(
        "quickscale_modules_billing.views.cancel_current_subscription",
        fake_cancel_current_subscription,
    )

    response = csrf_client.post(
        reverse("quickscale_billing:subscription-cancel-current"),
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert called is False


def test_billing_portal_session_view_missing_csrf_returns_403_without_calling_service(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    called = False

    def fake_create_billing_portal_session(
        auth_user,
        return_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        del auth_user, return_url, organization
        nonlocal called
        called = True
        return "https://billing.example.com/portal-session"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_billing_portal_session",
        fake_create_billing_portal_session,
    )

    response = csrf_client.post(
        reverse("quickscale_billing:billing-portal-session"),
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert called is False


@pytest.mark.django_db
def test_credit_balance_view_creates_zero_balance_on_first_use(
    client: Client,
    user,
) -> None:
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:credit-balance"))

    assert response.status_code == 200
    assert response.json()["balance"] == 0
    assert response.json()["updated_at"] is not None
    balance = CreditBalance.objects.get(user=user)
    assert balance.balance == 0


@pytest.mark.django_db
def test_credit_balance_view_returns_only_authenticated_users_balance(
    client: Client,
    user,
    django_user_model,
) -> None:
    other_user = django_user_model.objects.create_user(
        username="other-balance-user",
        email="other-balance@example.com",
        password="password123",
    )
    CreditBalance.objects.create(user=user, balance=125)
    CreditBalance.objects.create(user=other_user, balance=900)
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:credit-balance"))

    assert response.status_code == 200
    assert response.json()["balance"] == 125


@pytest.mark.django_db
def test_checkout_view_rejects_caller_supplied_redirect_fields(
    client: Client,
    user,
) -> None:
    plan = _create_one_time_plan(slug="credits-redirect-view")
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps(
            {
                "plan_slug": plan.slug,
                "success_url": "https://app.example.com/custom/success",
                "cancel_url": "https://app.example.com/custom/cancel",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "errors": {
            "cancel_url": ["This field is not allowed."],
            "success_url": ["This field is not allowed."],
        }
    }


@pytest.mark.django_db
def test_subscription_checkout_view_rejects_caller_supplied_redirect_fields(
    client: Client,
    user,
) -> None:
    plan = _create_recurring_plan(slug="starter-redirect-view")
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:subscription-checkout"),
        data=json.dumps(
            {
                "plan_slug": plan.slug,
                "success_url": "https://app.example.com/custom/subscription/success",
                "cancel_url": "https://app.example.com/custom/subscription/cancel",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "errors": {
            "cancel_url": ["This field is not allowed."],
            "success_url": ["This field is not allowed."],
        }
    }


@pytest.mark.django_db
def test_cancel_subscription_view_rejects_caller_supplied_return_url_without_calling_service(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_cancel_current_subscription(
        auth_user,
        *,
        organization: Any | None = None,
    ) -> None:
        del auth_user, organization
        nonlocal called
        called = True

    monkeypatch.setattr(
        "quickscale_modules_billing.views.cancel_current_subscription",
        fake_cancel_current_subscription,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:subscription-cancel-current"),
        data=json.dumps({"return_url": "https://app.example.com/custom/return"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "errors": {
            "return_url": ["This field is not allowed."],
        }
    }
    assert called is False


@pytest.mark.django_db
def test_billing_portal_session_view_rejects_caller_supplied_return_url_without_calling_service(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_create_billing_portal_session(
        auth_user,
        return_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        del auth_user, return_url, organization
        nonlocal called
        called = True
        return "https://billing.example.com/portal-session"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_billing_portal_session",
        fake_create_billing_portal_session,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:billing-portal-session"),
        data=json.dumps({"return_url": "https://app.example.com/custom/return"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "errors": {
            "return_url": ["This field is not allowed."],
        }
    }
    assert called is False


@pytest.mark.django_db
def test_credit_transactions_view_returns_only_authenticated_users_transactions(
    client: Client,
    user,
    django_user_model,
) -> None:
    other_user = django_user_model.objects.create_user(
        username="other-transactions-user",
        email="other-transactions@example.com",
        password="password123",
    )
    user_transaction = _create_credit_transaction(
        user=user,
        amount=125,
        balance_after=125,
        description="Current user purchase",
    )
    _create_credit_transaction(
        user=other_user,
        amount=900,
        balance_after=900,
        description="Other user purchase",
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:credit-transactions"))

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": user_transaction.pk,
            "amount": 125,
            "transaction_type": CreditTransaction.TransactionType.PURCHASE,
            "description": "Current user purchase",
            "balance_after": 125,
            "created_at": user_transaction.created_at.isoformat().replace(
                "+00:00", "Z"
            ),
        }
    ]


@pytest.mark.django_db
def test_credit_transactions_view_uses_fixed_page_size_without_client_override(
    client: Client,
    user,
) -> None:
    for index in range(30):
        _create_credit_transaction(
            user=user,
            amount=index + 1,
            balance_after=index + 1,
            description=f"Purchase {index + 1}",
        )
    client.force_login(user)

    first_page_response = client.get(
        reverse("quickscale_billing:credit-transactions"),
        {"page_size": 5},
    )
    second_page_response = client.get(
        reverse("quickscale_billing:credit-transactions"),
        {"page": 2, "page_size": 5},
    )

    assert first_page_response.status_code == 200
    assert isinstance(first_page_response.json(), list)
    assert len(first_page_response.json()) == 25
    assert second_page_response.status_code == 200
    assert len(second_page_response.json()) == 5


@pytest.mark.django_db
def test_credit_transactions_view_breaks_same_timestamp_ties_by_descending_id(
    client: Client,
    user,
) -> None:
    created_transactions = [
        _create_credit_transaction(
            user=user,
            amount=index + 1,
            balance_after=index + 1,
            description=f"Purchase {index + 1}",
        )
        for index in range(26)
    ]
    shared_timestamp = timezone.now()
    CreditTransaction.objects.filter(
        pk__in=[transaction_row.pk for transaction_row in created_transactions]
    ).update(created_at=shared_timestamp)
    expected_ids = sorted(
        (transaction_row.pk for transaction_row in created_transactions),
        reverse=True,
    )
    client.force_login(user)

    first_page_response = client.get(reverse("quickscale_billing:credit-transactions"))
    second_page_response = client.get(
        reverse("quickscale_billing:credit-transactions"),
        {"page": 2},
    )

    assert first_page_response.status_code == 200
    assert second_page_response.status_code == 200
    assert [item["id"] for item in first_page_response.json()] == expected_ids[:25]
    assert [item["id"] for item in second_page_response.json()] == expected_ids[25:]


@pytest.mark.django_db
def test_checkout_view_creates_session_with_server_owned_redirect_urls(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(slug="credits-checkout-view")
    captured_call: dict[str, Any] = {}

    def fake_create_checkout_session(
        auth_user,
        auth_plan,
        success_url: str,
        cancel_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        captured_call["user"] = auth_user
        captured_call["plan"] = auth_plan
        captured_call["success_url"] = success_url
        captured_call["cancel_url"] = cancel_url
        captured_call["organization"] = organization
        return "https://checkout.stripe.test/session/view"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_checkout_session",
        fake_create_checkout_session,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps({"plan_slug": plan.slug}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "checkout_url": "https://checkout.stripe.test/session/view"
    }
    assert captured_call == {
        "user": user,
        "plan": plan,
        "success_url": "http://testserver/billing/purchase/success/",
        "cancel_url": "http://testserver/billing/purchase/cancel/",
        "organization": None,
    }


@pytest.mark.django_db
def test_checkout_view_keeps_flat_redirect_urls_for_authenticated_solo_request_org(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(slug="credits-checkout-solo-request-org")
    captured_call: dict[str, Any] = {}

    def fake_create_checkout_session(
        auth_user,
        auth_plan,
        success_url: str,
        cancel_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        captured_call["user"] = auth_user
        captured_call["plan"] = auth_plan
        captured_call["success_url"] = success_url
        captured_call["cancel_url"] = cancel_url
        captured_call["organization"] = organization
        return "https://checkout.stripe.test/session/solo-request-org"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_checkout_session",
        fake_create_checkout_session,
    )

    request = RequestFactory().post(
        "/billing/purchase/checkout/",
        data=json.dumps({"plan_slug": plan.slug}),
        content_type="application/json",
    )
    request.user = user
    request._dont_enforce_csrf_checks = True

    response = TenantMiddleware(CreateCheckoutSessionView.as_view())(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "checkout_url": "https://checkout.stripe.test/session/solo-request-org"
    }
    assert captured_call["user"] == user
    assert captured_call["plan"] == plan
    assert captured_call["success_url"] == "http://testserver/billing/purchase/success/"
    assert captured_call["cancel_url"] == "http://testserver/billing/purchase/cancel/"
    assert captured_call["organization"] is not None


@pytest.mark.django_db
def test_org_checkout_view_creates_session_with_org_scoped_redirect_urls(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Aperture", slug="aperture")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    plan = _create_one_time_plan(slug="credits-org-checkout-view")
    captured_call: dict[str, Any] = {}

    def fake_create_checkout_session(
        auth_user,
        auth_plan,
        success_url: str,
        cancel_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        captured_call["user"] = auth_user
        captured_call["plan"] = auth_plan
        captured_call["success_url"] = success_url
        captured_call["cancel_url"] = cancel_url
        captured_call["organization"] = organization
        return "https://checkout.stripe.test/session/org-view"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_checkout_session",
        fake_create_checkout_session,
    )
    client.force_login(user)

    response = client.post(
        reverse(
            "quickscale_billing:org-purchase-checkout",
            kwargs={"org_slug": organization.slug},
        ),
        data=json.dumps({"plan_slug": plan.slug}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "checkout_url": "https://checkout.stripe.test/session/org-view"
    }
    assert captured_call == {
        "user": user,
        "plan": plan,
        "success_url": "http://testserver/orgs/aperture/billing/purchase/success/",
        "cancel_url": "http://testserver/orgs/aperture/billing/purchase/cancel/",
        "organization": organization,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("role", _OWNER_ONLY_ROLES)
@pytest.mark.parametrize(
    ("route_name", "payload", "service_target", "service_return_value"),
    _ORG_OWNER_ONLY_MUTATION_ROUTES,
)
def test_org_billing_mutation_surfaces_require_owner_role(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
    settings,
    role: str,
    route_name: str,
    payload: dict[str, Any],
    service_target: str,
    service_return_value: Any,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Lyra", slug="lyra")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )
    called = False

    def fake_service(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        nonlocal called
        called = True
        return service_return_value

    monkeypatch.setattr(service_target, fake_service)
    client.force_login(user)

    response = client.post(
        reverse(
            f"quickscale_billing:{route_name}",
            kwargs={"org_slug": organization.slug},
        ),
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert called is False


@pytest.mark.django_db
@pytest.mark.parametrize("role", _OWNER_ONLY_ROLES)
@pytest.mark.parametrize(
    ("route_name", "payload", "service_target", "service_return_value"),
    _FLAT_OWNER_ONLY_MUTATION_ROUTES,
)
def test_flat_billing_mutation_shims_require_owner_when_resolving_single_org(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
    settings,
    role: str,
    route_name: str,
    payload: dict[str, Any],
    service_target: str,
    service_return_value: Any,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Vega", slug="vega")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )
    called = False

    def fake_service(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        nonlocal called
        called = True
        return service_return_value

    monkeypatch.setattr(service_target, fake_service)
    client.force_login(user)

    response = client.post(
        reverse(f"quickscale_billing:{route_name}"),
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert called is False


@pytest.mark.django_db
def test_flat_checkout_view_rejects_ambiguous_saas_org_selection_without_calling_service(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    first_org = Organization.objects.create(name="Atlas", slug="atlas")
    second_org = Organization.objects.create(name="Beacon", slug="beacon")
    OrganizationMembership.objects.create(
        user=user,
        organization=first_org,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=second_org,
        role=OrgRole.ADMIN,
    )
    plan = _create_one_time_plan(slug="credits-ambiguous-shim-view")
    called = False

    def fake_create_checkout_session(*args: Any, **kwargs: Any) -> str:
        del args, kwargs
        nonlocal called
        called = True
        return "https://checkout.stripe.test/session/should-not-run"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_checkout_session",
        fake_create_checkout_session,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps({"plan_slug": plan.slug}),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json() == {"error": "Organization selection required."}
    assert called is False


@pytest.mark.django_db
def test_subscription_checkout_view_creates_session_with_server_owned_redirect_urls(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(slug="starter-checkout-view")
    captured_call: dict[str, Any] = {}

    def fake_create_subscription_checkout_session(
        auth_user,
        auth_plan,
        success_url: str,
        cancel_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        captured_call["user"] = auth_user
        captured_call["plan"] = auth_plan
        captured_call["success_url"] = success_url
        captured_call["cancel_url"] = cancel_url
        captured_call["organization"] = organization
        return "https://checkout.stripe.test/subscription/view"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_subscription_checkout_session",
        fake_create_subscription_checkout_session,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:subscription-checkout"),
        data=json.dumps({"plan_slug": plan.slug}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "checkout_url": "https://checkout.stripe.test/subscription/view"
    }
    assert captured_call == {
        "user": user,
        "plan": plan,
        "success_url": "http://testserver/billing/subscription/success/",
        "cancel_url": "http://testserver/billing/subscription/cancel/",
        "organization": None,
    }


@pytest.mark.django_db
def test_subscription_checkout_view_blocks_while_current_subscription_exists(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(slug="starter-existing-view")
    Subscription.objects.create(
        user=user,
        plan=plan,
        status=Subscription.Status.ACTIVE,
    )

    def fake_create_subscription_checkout_session(
        auth_user,
        auth_plan,
        success_url: str,
        cancel_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        del auth_plan, success_url, cancel_url
        assert organization is None
        assert Subscription.objects.filter(
            Subscription.current_status_q(),
            user=auth_user,
        ).exists()
        raise BillingValidationError(
            "User already has a current recurring subscription."
        )

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_subscription_checkout_session",
        fake_create_subscription_checkout_session,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:subscription-checkout"),
        data=json.dumps({"plan_slug": plan.slug}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "User already has a current recurring subscription."
    }


@pytest.mark.django_db
def test_cancel_subscription_view_returns_204_and_calls_service(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_user: Any | None = None
    captured_organization: Any | None = None

    def fake_cancel_current_subscription(
        auth_user,
        *,
        organization: Any | None = None,
    ) -> None:
        nonlocal captured_user
        nonlocal captured_organization
        captured_user = auth_user
        captured_organization = organization

    monkeypatch.setattr(
        "quickscale_modules_billing.views.cancel_current_subscription",
        fake_cancel_current_subscription,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:subscription-cancel-current"),
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 204
    assert response.content == b""
    assert captured_user == user
    assert captured_organization is None


@pytest.mark.django_db
def test_billing_portal_session_view_returns_server_owned_return_url(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_call: dict[str, Any] = {}

    def fake_create_billing_portal_session(
        auth_user,
        return_url: str,
        *,
        organization: Any | None = None,
    ) -> str:
        captured_call["user"] = auth_user
        captured_call["return_url"] = return_url
        captured_call["organization"] = organization
        return "https://billing.example.com/portal-session"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_billing_portal_session",
        fake_create_billing_portal_session,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:billing-portal-session"),
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "portal_url": "https://billing.example.com/portal-session"
    }
    assert captured_call == {
        "user": user,
        "return_url": "http://testserver/billing/portal/return/",
        "organization": None,
    }


@pytest.mark.django_db
def test_subscription_detail_view_returns_current_subscription(
    client: Client,
    user,
) -> None:
    plan = _create_recurring_plan(slug="starter-current-detail")
    period_start = timezone.now()
    period_end = period_start + timedelta(days=30)
    Subscription.objects.create(
        user=user,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        current_period_start=period_start,
        current_period_end=period_end,
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:subscription-detail"))

    assert response.status_code == 200
    assert response.json() == {
        "plan": {
            "name": plan.name,
            "slug": plan.slug,
            "credits_per_period": plan.credits_per_period,
            "price_cents": plan.price_cents,
            "currency": plan.currency,
            "billing_interval": plan.billing_interval,
        },
        "status": Subscription.Status.ACTIVE,
        "checkout_expires_at": None,
        "current_period_start": period_start.isoformat().replace("+00:00", "Z"),
        "current_period_end": period_end.isoformat().replace("+00:00", "Z"),
    }


@pytest.mark.django_db
def test_org_subscription_detail_view_returns_current_subscription_for_requested_org(
    client: Client,
    user,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    first_org = Organization.objects.create(name="Atlas", slug="atlas")
    second_org = Organization.objects.create(name="Beacon", slug="beacon")
    first_plan = _create_recurring_plan(
        slug="starter-current-org-detail",
        price_id="price_starter_current_org_detail",
    )
    second_plan = _create_recurring_plan(
        slug="growth-current-org-detail",
        price_id="price_growth_current_org_detail",
        name="Growth Monthly",
    )
    period_start = timezone.now()
    period_end = period_start + timedelta(days=30)
    OrganizationMembership.objects.create(
        user=user,
        organization=first_org,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=second_org,
        role=OrgRole.OWNER,
    )
    Subscription.objects.create(
        user=user,
        organization=first_org,
        plan=first_plan,
        status=Subscription.Status.ACTIVE,
        current_period_start=period_start,
        current_period_end=period_end,
    )
    Subscription.objects.create(
        user=user,
        organization=second_org,
        plan=second_plan,
        status=Subscription.Status.ACTIVE,
        current_period_start=period_start,
        current_period_end=period_end,
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "quickscale_billing:org-subscription-detail",
            kwargs={"org_slug": second_org.slug},
        )
    )

    assert response.status_code == 200
    assert response.json()["plan"]["slug"] == second_plan.slug
    assert response.json()["plan"]["name"] == second_plan.name


@pytest.mark.django_db
def test_subscription_detail_view_returns_404_when_current_subscription_is_missing(
    client: Client,
    user,
) -> None:
    plan = _create_recurring_plan(slug="starter-missing-detail")
    Subscription.objects.create(
        user=user,
        plan=plan,
        status=Subscription.Status.CANCELED,
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:subscription-detail"))

    assert response.status_code == 404
    assert response.json() == {"error": "Current subscription not found."}


def test_webhook_view_passes_raw_body_and_signature_header(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_call: dict[str, Any] = {}

    def fake_handle_stripe_event(*, body: bytes, signature: str) -> StripeWebhookResult:
        captured_call["body"] = body
        captured_call["signature"] = signature
        return StripeWebhookResult(
            duplicate=False,
            event_type="invoice.paid",
            status="processed",
        )

    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        fake_handle_stripe_event,
    )
    body = b'{"id":"evt_view"}'

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=view-signature",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "duplicate": False,
        "event_type": "invoice.paid",
        "processing_status": "processed",
    }
    assert captured_call == {
        "body": body,
        "signature": "t=1,v1=view-signature",
    }


@pytest.mark.parametrize(
    ("route_name", "expected_text", "expected_purchase_status"),
    [
        ("purchase-success", "Purchase complete", "success"),
        ("purchase-cancel", "Purchase canceled", "cancel"),
    ],
)
def test_purchase_return_views_are_public_and_render(
    client: Client,
    route_name: str,
    expected_text: str,
    expected_purchase_status: str,
) -> None:
    response = client.get(reverse(f"quickscale_billing:{route_name}"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert expected_text in content
    assert 'id="billing-purchase-root"' in content
    assert 'id="billing-subscription-root"' not in content
    assert f'data-purchase-status="{expected_purchase_status}"' in content


@pytest.mark.parametrize(
    (
        "route_name",
        "expected_text",
        "expected_subscription_status",
        "expected_primary_action",
    ),
    [
        ("subscription-success", "Subscription started", "success", "Go to dashboard"),
        ("subscription-cancel", "Subscription not started", "cancel", "View plans"),
    ],
)
def test_subscription_return_views_are_public_and_render(
    client: Client,
    route_name: str,
    expected_text: str,
    expected_subscription_status: str,
    expected_primary_action: str,
) -> None:
    response = client.get(reverse(f"quickscale_billing:{route_name}"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert expected_text in content
    assert expected_primary_action in content
    assert "Back to app" in content
    assert 'id="billing-subscription-root"' in content
    assert 'id="billing-purchase-root"' not in content
    assert f'data-subscription-status="{expected_subscription_status}"' in content


def test_billing_portal_return_view_is_public_and_render(client: Client) -> None:
    response = client.get(reverse("quickscale_billing:portal-return"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Back from billing portal" in content
    assert "Go to dashboard" in content
    assert "Back to app" in content
    assert 'id="billing-portal-root"' in content
    assert 'data-portal-status="return"' in content
    assert 'id="billing-purchase-root"' not in content
    assert 'id="billing-subscription-root"' not in content


@pytest.mark.django_db
def test_billing_portal_return_view_keeps_flat_dashboard_link_for_authenticated_solo_request_org(
    user,
) -> None:
    request = RequestFactory().get("/billing/portal/return/")
    request.user = user

    response = TenantMiddleware(BillingPortalReturnView.as_view())(request)
    response.render()
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'href="/billing/dashboard/"' in content


@pytest.mark.django_db
def test_org_billing_portal_return_view_links_back_to_org_dashboard(
    client: Client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Summit", slug="summit")

    response = client.get(
        reverse(
            "quickscale_billing:org-portal-return",
            kwargs={"org_slug": organization.slug},
        )
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'href="/orgs/summit/billing/dashboard/"' in content


@pytest.mark.django_db
def test_org_subscription_cancel_view_links_back_to_org_pricing(
    client: Client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Vertex", slug="vertex")

    response = client.get(
        reverse(
            "quickscale_billing:org-subscription-cancel",
            kwargs={"org_slug": organization.slug},
        )
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'href="/orgs/vertex/billing/pricing/"' in content


def test_webhook_view_maps_signature_errors_to_403(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingWebhookSignatureError("Webhook signature is invalid.")
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=invalid",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "Webhook signature is invalid."


def test_webhook_view_maps_disabled_runtime_to_403(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingDisabledError("Billing module is disabled.")
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=disabled",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "Billing module is disabled."


def test_webhook_view_maps_processing_errors_to_400(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingWebhookError("Stripe invoice payload is missing an id.")
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=broken",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Stripe invoice payload is missing an id."


def test_webhook_view_maps_configuration_errors_to_500(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingConfigurationError(
                "Stripe webhook secret is not configured in the runtime environment."
            )
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=config",
    )

    assert response.status_code == 500
    assert response.json()["error"] == (
        "Stripe webhook secret is not configured in the runtime environment."
    )
