"""Tests for billing's published plan-feature gate."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory

from quickscale_modules_billing.models import Plan, Subscription
from quickscale_modules_billing.services import require_org_feature
from quickscale_modules_orgs.current_org import (
    clear_current_org,
    reset_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.models import Organization


def _create_plan(*, slug: str, features: list[str]) -> Plan:
    return Plan.objects.create(
        name="Growth",
        slug=slug,
        stripe_price_id=f"price_{slug}",
        credits_per_period=250,
        price_cents=4900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
        features=features,
    )


def _create_active_subscription(*, organization: Organization, plan: Plan) -> None:
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()


def _build_feature_request(*, organization: Organization):
    request = RequestFactory().get("/")
    request.user = get_user_model().objects.create_user(
        username=f"feature-user-{organization.slug}",
        email=f"feature-user-{organization.slug}@example.com",
        password="secret123",
    )
    request.org = organization
    return request


@pytest.mark.django_db
def test_require_org_feature_returns_200_when_feature_is_enabled() -> None:
    """An active plan that lists the feature lets the guarded view run."""
    organization = Organization.objects.create(name="Acme", slug="acme")
    plan = _create_plan(slug="growth-with-crm", features=["crm", "billing"])
    _create_active_subscription(organization=organization, plan=plan)
    request = _build_feature_request(organization=organization)

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")

    response = feature_view(request, org_slug="acme")

    assert response.status_code == 200


@pytest.mark.django_db
def test_require_org_feature_returns_402_without_feature() -> None:
    """An active plan that does not list the feature answers 402."""
    organization = Organization.objects.create(name="Bravo", slug="bravo")
    plan = _create_plan(slug="growth-without-crm", features=["billing"])
    _create_active_subscription(organization=organization, plan=plan)
    request = _build_feature_request(organization=organization)

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")

    response = feature_view(request, org_slug="bravo")

    assert response.status_code == 402


@pytest.mark.django_db
def test_require_org_feature_returns_402_without_active_subscription() -> None:
    """A non-active subscription answers 402 even when its plan lists the feature."""
    organization = Organization.objects.create(name="Charlie", slug="charlie")
    plan = _create_plan(slug="growth-trialing-crm", features=["crm"])
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.TRIALING,
        )
    finally:
        reset_current_org_id()
    request = _build_feature_request(organization=organization)

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")

    response = feature_view(request, org_slug="charlie")

    assert response.status_code == 402


@pytest.mark.django_db
def test_require_org_feature_ignores_request_subscription_stub_and_uses_orm() -> None:
    """A stubbed request subscription never decides the gate; the ORM row does."""
    organization = Organization.objects.create(name="Delta", slug="delta")
    plan = _create_plan(slug="growth-delta-billing", features=["billing"])
    _create_active_subscription(organization=organization, plan=plan)
    request = RequestFactory().get("/")
    request.user = get_user_model().objects.create_user(
        username="feature-user-delta",
        email="feature-user-delta@example.com",
        password="secret123",
    )
    request.org = organization
    request.org.subscription = type(
        "SubscriptionStub",
        (),
        {"plan": type("PlanStub", (), {"features": ["crm"]})()},
    )()

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")

    response = feature_view(request, org_slug="delta")

    assert response.status_code == 402


def test_require_org_feature_returns_402_for_anonymous_user() -> None:
    """An anonymous request fails closed before any organization lookup."""
    from django.contrib.auth.models import AnonymousUser

    request = RequestFactory().get("/orgs/anything/feature/")
    request.user = AnonymousUser()
    request.org = None

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")  # pragma: no cover

    response = feature_view(request, org_slug="anything")
    assert response.status_code == 402


@pytest.mark.django_db
def test_require_org_feature_returns_402_when_org_not_found() -> None:
    """An unknown organization slug answers 402 instead of raising."""
    user = get_user_model().objects.create_user(
        username="feature-lost",
        email="feature-lost@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/orgs/nonexistent/feature/")
    request.user = user
    request.org = None  # bypass middleware

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")  # pragma: no cover

    response = feature_view(request, org_slug="nonexistent")
    assert response.status_code == 402


@pytest.mark.django_db
def test_require_org_feature_returns_402_when_no_org_context() -> None:
    """The gate fails closed (402) when no organization context is available."""
    user = get_user_model().objects.create_user(
        username="no-context-feature",
        email="no-context-feature@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/orgs/anything/feature/")
    request.user = user
    clear_current_org(request)

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")  # pragma: no cover

    response = feature_view(request, org_slug="anything")
    assert response.status_code == 402
