"""Tests for billing's published plan-feature gate."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import force_authenticate

from quickscale_core.runtime import QuickscaleSessionAuthentication
from quickscale_modules_billing._settings import require_org_feature
from quickscale_modules_billing.models import Plan, Subscription
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


def _create_user(*, username: str) -> Any:
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="secret123",
    )


def _feature_view(feature_key: str = "crm"):
    """Return the gate wrapping an API view, as a project mounts it."""

    @api_view(["GET"])
    @authentication_classes([QuickscaleSessionAuthentication])
    @permission_classes([AllowAny])
    @require_org_feature(feature_key)
    def feature_view(request, org_slug: str) -> Response:
        return Response({"ok": True})

    return feature_view


def _build_feature_request(*, organization: Organization | None, user: Any = None):
    request = RequestFactory().get("/")
    if user is not None:
        force_authenticate(request, user=user)
    request.org = organization
    return request


@pytest.mark.django_db
def test_require_org_feature_returns_200_when_feature_is_enabled() -> None:
    """An active plan that lists the feature lets the guarded API run."""
    organization = Organization.objects.create(name="Acme", slug="acme")
    plan = _create_plan(slug="growth-with-crm", features=["crm", "billing"])
    _create_active_subscription(organization=organization, plan=plan)
    user = _create_user(username="feature-user-acme")
    request = _build_feature_request(organization=organization, user=user)

    response = _feature_view()(request, org_slug="acme")

    assert response.status_code == 200
    assert response.data == {"ok": True}


@pytest.mark.django_db
def test_require_org_feature_returns_the_one_error_shape_without_feature() -> None:
    """A plan without the feature answers 402 in rule 9's shared shape."""
    organization = Organization.objects.create(name="Bravo", slug="bravo")
    plan = _create_plan(slug="growth-without-crm", features=["billing"])
    _create_active_subscription(organization=organization, plan=plan)
    user = _create_user(username="feature-user-bravo")
    request = _build_feature_request(organization=organization, user=user)

    response = _feature_view()(request, org_slug="bravo")

    assert response.status_code == 402
    assert response.data["error"]["code"] == "feature_not_available"
    assert isinstance(response.data["error"]["message"], str)
    assert "fields" not in response.data["error"]


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
    user = _create_user(username="feature-user-charlie")
    request = _build_feature_request(organization=organization, user=user)

    response = _feature_view()(request, org_slug="charlie")

    assert response.status_code == 402
    assert response.data["error"]["code"] == "feature_not_available"


@pytest.mark.django_db
def test_require_org_feature_ignores_request_subscription_stub_and_uses_orm() -> None:
    """A stubbed request subscription never decides the gate; the ORM row does."""
    organization = Organization.objects.create(name="Delta", slug="delta")
    plan = _create_plan(slug="growth-delta-billing", features=["billing"])
    _create_active_subscription(organization=organization, plan=plan)
    user = _create_user(username="feature-user-delta")
    request = _build_feature_request(organization=organization, user=user)
    request.org.subscription = type(
        "SubscriptionStub",
        (),
        {"plan": type("PlanStub", (), {"features": ["crm"]})()},
    )()

    response = _feature_view()(request, org_slug="delta")

    assert response.status_code == 402
    assert response.data["error"]["code"] == "feature_not_available"


def test_require_org_feature_returns_401_for_anonymous_user() -> None:
    """An anonymous request answers the declared 401 in the shared shape."""
    request = _build_feature_request(organization=None)

    response = _feature_view()(request, org_slug="anything")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"


@pytest.mark.django_db
def test_require_org_feature_returns_402_when_org_not_found() -> None:
    """An unknown organization slug answers the shaped 402 instead of raising."""
    user = _create_user(username="feature-lost")
    request = _build_feature_request(organization=None, user=user)

    response = _feature_view()(request, org_slug="nonexistent")

    assert response.status_code == 402
    assert response.data["error"]["code"] == "feature_not_available"


@pytest.mark.django_db
def test_require_org_feature_returns_402_when_no_org_context() -> None:
    """The gate fails closed with the shaped 402 when no org context exists."""
    user = _create_user(username="no-context-feature")
    request = _build_feature_request(organization=None, user=user)
    clear_current_org(request)

    response = _feature_view()(request, org_slug="anything")

    assert response.status_code == 402
    assert response.data["error"]["code"] == "feature_not_available"
