"""Permission contract tests for the QuickScale organizations module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory

from quickscale_modules_billing.models import Plan, Subscription
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership
from quickscale_modules_orgs.permissions import ROLE_HIERARCHY, require_org_feature


@pytest.mark.django_db
def test_require_org_role_admin_matrix(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Acme", slug="acme")
    role_to_status = {
        OrgRole.VIEWER: 403,
        OrgRole.MEMBER: 403,
        OrgRole.ADMIN: 200,
        OrgRole.OWNER: 200,
    }

    for role, expected_status in role_to_status.items():
        user = get_user_model().objects.create_user(
            username=f"user-{role}",
            email=f"{role}@example.com",
            password="secret123",
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=role,
        )
        client.force_login(user)

        response = client.get(f"/orgs/{organization.slug}/admin-only/")

        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.content.decode() == organization.slug
        client.logout()


@pytest.mark.django_db
def test_require_org_role_owner_matrix(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Beta", slug="beta")
    admin = get_user_model().objects.create_user(
        username="beta-admin",
        email="beta-admin@example.com",
        password="secret123",
    )
    owner = get_user_model().objects.create_user(
        username="beta-owner",
        email="beta-owner@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    client.force_login(admin)
    admin_response = client.get(f"/orgs/{organization.slug}/owner-only/")
    client.logout()

    client.force_login(owner)
    owner_response = client.get(f"/orgs/{organization.slug}/owner-only/")

    assert admin_response.status_code == 403
    assert owner_response.status_code == 200
    assert owner_response.content.decode() == organization.slug


@pytest.mark.django_db
def test_org_role_mixin_uses_same_role_contract(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Gamma", slug="gamma")
    admin = get_user_model().objects.create_user(
        username="gamma-admin",
        email="gamma-admin@example.com",
        password="secret123",
    )
    viewer = get_user_model().objects.create_user(
        username="gamma-viewer",
        email="gamma-viewer@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=viewer,
        organization=organization,
        role=OrgRole.VIEWER,
    )

    client.force_login(admin)
    admin_response = client.get(f"/orgs/{organization.slug}/admin-mixin/")
    client.logout()

    client.force_login(viewer)
    viewer_response = client.get(f"/orgs/{organization.slug}/admin-mixin/")

    assert admin_response.status_code == 200
    assert viewer_response.status_code == 403


@pytest.mark.django_db
def test_role_guards_forbid_anonymous_requests(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Epsilon", slug="epsilon")

    decorator_response = client.get(f"/orgs/{organization.slug}/admin-only/")
    mixin_response = client.get(f"/orgs/{organization.slug}/admin-mixin/")

    assert decorator_response.status_code == 403
    assert mixin_response.status_code == 403


def test_role_hierarchy_matches_roadmap_order() -> None:
    assert ROLE_HIERARCHY == {
        OrgRole.VIEWER: 0,
        OrgRole.MEMBER: 1,
        OrgRole.ADMIN: 2,
        OrgRole.OWNER: 3,
    }


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
    organization = Organization.objects.create(name="Acme", slug="acme")
    plan = _create_plan(slug="growth-with-crm", features=["crm", "billing"])
    Subscription.objects.create(
        organization=organization,
        plan=plan,
        status=Subscription.Status.ACTIVE,
    )
    request = _build_feature_request(organization=organization)

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")

    response = feature_view(request, org_slug="acme")

    assert response.status_code == 200


@pytest.mark.django_db
def test_require_org_feature_returns_402_without_feature() -> None:
    organization = Organization.objects.create(name="Bravo", slug="bravo")
    plan = _create_plan(slug="growth-without-crm", features=["billing"])
    Subscription.objects.create(
        organization=organization,
        plan=plan,
        status=Subscription.Status.ACTIVE,
    )
    request = _build_feature_request(organization=organization)

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")

    response = feature_view(request, org_slug="bravo")

    assert response.status_code == 402


@pytest.mark.django_db
def test_require_org_feature_returns_402_without_active_subscription() -> None:
    organization = Organization.objects.create(name="Charlie", slug="charlie")
    plan = _create_plan(slug="growth-trialing-crm", features=["crm"])
    Subscription.objects.create(
        organization=organization,
        plan=plan,
        status=Subscription.Status.TRIALING,
    )
    request = _build_feature_request(organization=organization)

    @require_org_feature("crm")
    def feature_view(request, org_slug: str):
        return HttpResponse("ok")

    response = feature_view(request, org_slug="charlie")

    assert response.status_code == 402


@pytest.mark.django_db
def test_require_org_feature_ignores_request_subscription_stub_and_uses_orm() -> None:
    organization = Organization.objects.create(name="Delta", slug="delta")
    plan = _create_plan(slug="growth-delta-billing", features=["billing"])
    Subscription.objects.create(
        organization=organization,
        plan=plan,
        status=Subscription.Status.ACTIVE,
    )
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
