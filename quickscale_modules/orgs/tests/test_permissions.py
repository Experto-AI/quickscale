"""Permission contract tests for the QuickScale organizations module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.current_org import (
    CurrentOrgError,
    clear_current_org,
    get_current_org,
    require_current_org,
    set_current_org,
)
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership
from quickscale_modules_orgs.permissions import (
    ROLE_HIERARCHY,
    HasOrgRole,
    resolve_request_org,
    user_has_org_role,
)


class _OrgRoleProbeView(APIView):
    """Minimal DRF view whose only gate is the configured HasOrgRole."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [HasOrgRole(OrgRole.MEMBER)]

    def get(self, request: object, **kwargs: object) -> Response:
        del request, kwargs
        return Response({"ok": True})


def _drf_request(user: object, organization: Organization | None = None):
    """Build a forced-authenticated DRF request with an optional org context."""
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    if organization is not None:
        request.org = organization
    return request


def _member_user(organization: Organization, role: OrgRole, username: str):
    user = get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )
    return user


@pytest.mark.django_db
def test_has_org_role_configured_instance_is_what_drf_calls() -> None:
    """DRF instantiates each permission_classes entry; the configured one returns itself."""
    permission = HasOrgRole(OrgRole.ADMIN)

    assert permission() is permission
    assert permission.min_role == OrgRole.ADMIN


@pytest.mark.django_db
def test_has_org_role_refuses_viewer_and_allows_member_or_higher() -> None:
    """A member gate admits member/admin/owner and refuses a viewer."""
    organization = Organization.objects.create(name="RoleGate", slug="role-gate")
    statuses = {}
    view = _OrgRoleProbeView.as_view()

    for role in (OrgRole.VIEWER, OrgRole.MEMBER, OrgRole.ADMIN, OrgRole.OWNER):
        user = _member_user(organization, role, f"role-gate-{role}")
        response = view(_drf_request(user, organization))
        statuses[role] = response.status_code

    assert statuses == {
        OrgRole.VIEWER: 403,
        OrgRole.MEMBER: 200,
        OrgRole.ADMIN: 200,
        OrgRole.OWNER: 200,
    }


@pytest.mark.django_db
def test_has_org_role_refuses_an_absent_membership() -> None:
    """An authenticated caller with no membership in the active org is refused."""
    organization = Organization.objects.create(
        name="NoMembership", slug="no-membership"
    )
    outsider = get_user_model().objects.create_user(
        username="role-gate-outsider",
        email="role-gate-outsider@example.com",
        password="secret123",
    )

    response = _OrgRoleProbeView.as_view()(_drf_request(outsider, organization))

    assert response.status_code == 403


@pytest.mark.django_db
def test_has_org_role_fails_closed_without_an_organization_context() -> None:
    """A member of some organization is still refused when the request has no org."""
    organization = Organization.objects.create(name="NoContext", slug="no-context")
    member = _member_user(organization, OrgRole.OWNER, "role-gate-nocontext")

    response = _OrgRoleProbeView.as_view()(_drf_request(member))

    assert response.status_code == 403


@pytest.mark.django_db
def test_has_org_role_resolves_the_org_slug_route_kwarg() -> None:
    """Without request.org, the routed org_slug resolves the organization."""
    organization = Organization.objects.create(
        name="SlugResolved", slug="slug-resolved"
    )
    member = _member_user(organization, OrgRole.MEMBER, "role-gate-slug")
    viewer = _member_user(organization, OrgRole.VIEWER, "role-gate-slug-viewer")
    view = _OrgRoleProbeView.as_view()

    member_request = APIRequestFactory().get(f"/orgs/{organization.slug}/probe/")
    force_authenticate(member_request, user=member)
    member_response = view(member_request, org_slug=organization.slug)

    viewer_request = APIRequestFactory().get(f"/orgs/{organization.slug}/probe/")
    force_authenticate(viewer_request, user=viewer)
    viewer_response = view(viewer_request, org_slug=organization.slug)

    assert member_response.status_code == 200
    assert viewer_response.status_code == 403


@pytest.mark.django_db
def test_has_org_role_grants_superusers() -> None:
    """A superuser passes the role gate for the request's organization."""
    organization = Organization.objects.create(name="SuperGate", slug="super-gate")
    superuser = get_user_model().objects.create_superuser(
        username="role-gate-super",
        email="role-gate-super@example.com",
        password="secret123",
    )

    response = _OrgRoleProbeView.as_view()(_drf_request(superuser, organization))

    assert response.status_code == 200


@pytest.mark.django_db
def test_has_org_role_admits_superusers_without_an_org_context() -> None:
    """A superuser is the operator path and passes even with no org context."""
    superuser = get_user_model().objects.create_superuser(
        username="role-gate-superless",
        email="role-gate-superless@example.com",
        password="secret123",
    )

    response = _OrgRoleProbeView.as_view()(_drf_request(superuser))

    assert response.status_code == 200


@pytest.mark.django_db
def test_has_org_role_refuses_anonymous_callers() -> None:
    """An anonymous DRF request is refused, not admitted by a default role."""
    response = _OrgRoleProbeView.as_view()(APIRequestFactory().get("/"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_require_org_role_admin_matrix(client, settings) -> None:
    settings.QUICKSCALE_ORGS_MODE = "saas"
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
    settings.QUICKSCALE_ORGS_MODE = "saas"
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
    settings.QUICKSCALE_ORGS_MODE = "saas"
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
    settings.QUICKSCALE_ORGS_MODE = "saas"
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


@pytest.mark.django_db
def test_resolve_request_org_resolves_via_url_pattern() -> None:
    """resolve_request_org: should resolve org slug via URL resolver."""
    organization = Organization.objects.create(name="UrlResolved", slug="urlresolved")
    request = RequestFactory().get(f"/orgs/{organization.slug}/admin-only/")
    request.org = None  # no org set on request

    # Pass empty kwargs so the function falls through to URL resolution
    result = resolve_request_org(request, {})
    assert result is not None
    assert result.slug == "urlresolved"


def test_resolve_request_org_returns_none_on_resolver404() -> None:
    """resolve_request_org: returns None when URL can't be resolved."""
    request = RequestFactory().get("/not-a-real-path-xyz/")
    request.org = None
    result = resolve_request_org(request, {})
    assert result is None


@pytest.mark.django_db
def test_resolve_request_org_returns_none_when_slug_not_in_url() -> None:
    """resolve_request_org: returns None when URL resolves but has no org_slug."""
    request = RequestFactory().get("/")
    request.org = None
    result = resolve_request_org(request, {})
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
    settings.QUICKSCALE_ORGS_MODE = "saas"
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
def test_resolve_request_org_sets_org_via_helper() -> None:
    """resolve_request_org must use set_current_org when resolving via slug."""
    organization = Organization.objects.create(
        name="HelperResolve", slug="helper-resolve"
    )
    request = RequestFactory().get(f"/orgs/{organization.slug}/admin-only/")
    clear_current_org(request)

    result = resolve_request_org(request, {})
    assert result is not None
    assert result.pk == organization.pk
    assert get_current_org(request) is not None
    assert get_current_org(request).pk == organization.pk
