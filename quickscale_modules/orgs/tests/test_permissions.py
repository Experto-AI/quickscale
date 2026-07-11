"""Permission contract tests for the QuickScale organizations module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory

from quickscale_modules_billing.models import Plan, Subscription
from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.current_org import (
    CurrentOrgError,
    clear_current_org,
    get_current_org,
    require_current_org,
    reset_current_org_id,
    set_current_org,
    set_current_org_id,
)
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership
from quickscale_modules_orgs.permissions import (
    ROLE_HIERARCHY,
    _get_active_org_subscription,
    _resolve_request_org,
    require_org_feature,
    user_has_org_role,
)


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
        session = client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

        response = client.get(f"/orgs/{organization.slug}/admin-only/")

        assert response.status_code == expected_status, (
            f"expected {expected_status} for role {role}, got {response.status_code}"
        )
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
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
    session.save()
    admin_response = client.get(f"/orgs/{organization.slug}/owner-only/")
    client.logout()

    client.force_login(owner)
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
    session.save()
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
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
    session.save()
    admin_response = client.get(f"/orgs/{organization.slug}/admin-mixin/")
    client.logout()

    client.force_login(viewer)
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
    session.save()
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
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()
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
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()
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
    organization = Organization.objects.create(name="Delta", slug="delta")
    plan = _create_plan(slug="growth-delta-billing", features=["billing"])
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()
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


# ---------------------------------------------------------------------------
# Direct unit tests for uncovered lines
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_has_org_role_returns_false_for_anonymous_user() -> None:
    """user_has_org_role: unauthenticated user should be denied (line 30)."""
    organization = Organization.objects.create(name="Anon", slug="anon")
    anon = type(
        "AnonymousUser", (), {"is_authenticated": False, "is_superuser": False}
    )()
    assert user_has_org_role(anon, organization, OrgRole.VIEWER) is False


def test_user_has_org_role_returns_false_for_none_user() -> None:
    """user_has_org_role: None user should be denied without hitting DB."""
    from unittest.mock import MagicMock

    org = MagicMock()
    result = user_has_org_role(None, org, OrgRole.VIEWER)
    assert result is False


@pytest.mark.django_db
def test_user_has_org_role_returns_false_when_no_membership() -> None:
    """user_has_org_role: authenticated user with no membership should be denied (line 39)."""
    organization = Organization.objects.create(name="NoMember", slug="nomember")
    user = get_user_model().objects.create_user(
        username="nomember-user",
        email="nomember@example.com",
        password="secret123",
    )
    # No OrganizationMembership created deliberately
    assert user_has_org_role(user, organization, OrgRole.VIEWER) is False


@pytest.mark.django_db
def test_require_org_role_returns_403_when_org_not_found(client, settings) -> None:
    """require_org_role: org not found in DB should return 403 via direct view call (line 55)."""
    from quickscale_modules_orgs.permissions import require_org_role

    user = get_user_model().objects.create_user(
        username="lost-user",
        email="lost@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/orgs/nonexistent/admin-only/")
    request.user = user
    request.org = None  # bypass middleware

    @require_org_role(OrgRole.ADMIN)
    def my_view(request, org_slug: str):
        return HttpResponse("ok")  # pragma: no cover

    response = my_view(request, org_slug="nonexistent")
    assert response.status_code == 403


@pytest.mark.django_db
def test_org_role_mixin_returns_403_when_org_not_found(client, settings) -> None:
    """OrgRoleMixin.dispatch: org not found in DB should return 403 via direct call (line 79)."""
    from django.views import View
    from quickscale_modules_orgs.permissions import OrgRoleMixin

    user = get_user_model().objects.create_user(
        username="mixin-lost",
        email="mixin-lost@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/orgs/nonexistent/admin-mixin/")
    request.user = user
    request.org = None  # bypass middleware

    class MyMixinView(OrgRoleMixin, View):
        min_org_role = OrgRole.ADMIN

        def get(self, request, org_slug: str):
            return HttpResponse("ok")  # pragma: no cover

    response = MyMixinView.as_view()(request, org_slug="nonexistent")
    assert response.status_code == 403


def test_require_org_feature_returns_402_for_anonymous_user() -> None:
    """require_org_feature: anonymous user should receive 402 (line 99)."""
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
def test_require_org_feature_returns_402_when_org_not_found(client, settings) -> None:
    """require_org_feature: unknown org slug should return 402 (line 103)."""
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
def test_get_active_org_subscription_returns_none_when_billing_not_installed() -> None:
    """_get_active_org_subscription: returns None when billing app not installed (line 125)."""
    from unittest.mock import patch

    organization = Organization.objects.create(name="NoBilling", slug="nobilling")
    with patch(
        "quickscale_modules_orgs.permissions.apps.is_installed", return_value=False
    ):
        result = _get_active_org_subscription(organization)
    assert result is None


@pytest.mark.django_db
def test_get_active_org_subscription_returns_none_on_lookup_error() -> None:
    """_get_active_org_subscription: returns None on LookupError (lines 132-133)."""
    from unittest.mock import patch

    organization = Organization.objects.create(name="LookupFail", slug="lookupfail")
    with (
        patch(
            "quickscale_modules_orgs.permissions.apps.is_installed", return_value=True
        ),
        patch(
            "quickscale_modules_orgs.permissions.apps.get_model",
            side_effect=LookupError("no model"),
        ),
    ):
        result = _get_active_org_subscription(organization)
    assert result is None


@pytest.mark.django_db
def test_resolve_request_org_resolves_via_url_pattern() -> None:
    """_resolve_request_org: should resolve org slug via URL resolver (lines 153-162)."""
    organization = Organization.objects.create(name="UrlResolved", slug="urlresolved")
    request = RequestFactory().get(f"/orgs/{organization.slug}/admin-only/")
    request.org = None  # no org set on request

    # Pass empty kwargs so the function falls through to URL resolution
    result = _resolve_request_org(request, {})
    assert result is not None
    assert result.slug == "urlresolved"


def test_resolve_request_org_returns_none_on_resolver404() -> None:
    """_resolve_request_org: returns None when URL can't be resolved (line 158)."""
    request = RequestFactory().get("/not-a-real-path-xyz/")
    request.org = None
    result = _resolve_request_org(request, {})
    assert result is None


@pytest.mark.django_db
def test_resolve_request_org_returns_none_when_slug_not_in_url() -> None:
    """_resolve_request_org: returns None when URL resolves but has no org_slug (line 160-161)."""
    request = RequestFactory().get("/")
    request.org = None
    result = _resolve_request_org(request, {})
    assert result is None


# ---------------------------------------------------------------------------
# Strict fail-closed current-org accessor tests
# ---------------------------------------------------------------------------


def test_require_current_org_raises_when_no_org_context() -> None:
    """require_current_org must raise CurrentOrgError when request.org is None."""
    request = RequestFactory().get("/")
    clear_current_org(request)

    with pytest.raises(CurrentOrgError):
        require_current_org(request)


def test_require_current_org_returns_org_when_context_is_set() -> None:
    """require_current_org returns the org when request.org is set."""
    request = RequestFactory().get("/")
    organization = Organization(name="Strict", slug="strict")
    set_current_org(request, organization)

    result = require_current_org(request)
    assert result is organization


@pytest.mark.django_db
def test_require_org_role_returns_403_when_no_org_context(client, settings) -> None:
    """require_org_role must fail closed (403) when no org context is available."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="no-context-user",
        email="no-context@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/orgs/anything/admin-only/")
    request.user = user
    clear_current_org(request)

    from quickscale_modules_orgs.permissions import require_org_role

    @require_org_role(OrgRole.ADMIN)
    def guarded_view(request, org_slug: str):
        return HttpResponse("ok")  # pragma: no cover

    response = guarded_view(request, org_slug="anything")
    assert response.status_code == 403


@pytest.mark.django_db
def test_require_org_feature_returns_402_when_no_org_context(client, settings) -> None:
    """require_org_feature must fail closed (402) when no org context is available."""
    settings.QUICKSCALE_MODE = "saas"
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


@pytest.mark.django_db
def test_resolve_request_org_sets_org_via_helper() -> None:
    """_resolve_request_org must use set_current_org when resolving via slug."""
    organization = Organization.objects.create(
        name="HelperResolve", slug="helper-resolve"
    )
    request = RequestFactory().get(f"/orgs/{organization.slug}/admin-only/")
    clear_current_org(request)

    result = _resolve_request_org(request, {})
    assert result is not None
    assert result.pk == organization.pk
    assert get_current_org(request) is not None
    assert get_current_org(request).pk == organization.pk
