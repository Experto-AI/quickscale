"""Middleware contract tests for the QuickScale organizations module."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.http import Http404
from django.test import RequestFactory
from django.test import override_settings
from django.utils import timezone

from quickscale_modules_orgs.constants import (
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from quickscale_modules_orgs.middleware import TenantMiddleware
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from quickscale_modules_orgs.views import org_detail_view, org_index_view, org_new_view


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_pre_home")
def test_solo_mode_auto_creates_personal_org_and_sets_request_org(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="alice",
        email="alice@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 200
    assert "Organization dashboard" in response.content.decode()
    assert "alice" in response.content.decode()
    assert Organization.objects.filter(
        is_personal=True, memberships__user=user
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/orgs/",
        "/orgs/new/",
        "/orgs/acme/",
        "/orgs/invitations/00000000-0000-0000-0000-000000000000/accept/",
    ],
)
def test_solo_mode_hides_org_namespace_routes(client, settings, path) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="alice-hidden",
        email="alice-hidden@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get(path)

    assert response.status_code == 404


@pytest.mark.django_db
def test_saas_mode_redirects_unscoped_requests_without_membership(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="bob",
        email="bob@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/new/"


@pytest.mark.django_db
def test_saas_mode_allows_public_invitation_accept_without_membership(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="beck",
        email="beck@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Beacon", slug="beacon")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="blair@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    assert response.status_code == 302
    assert response.headers["Location"] == (
        f"/accounts/login/?next=/orgs/invitations/{invitation.token}/accept/"
    )
    assert client.session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] == str(
        invitation.token
    )


@pytest.mark.django_db
def test_saas_mode_keeps_non_accept_invitation_paths_redirecting_to_org_creation(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="blake",
        email="blake@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/invitations/pending/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/new/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/orgs/{slug}/",
        "/orgs/{slug}/current-org-id/",
        "/orgs/{slug}/admin-only/",
        "/orgs/{slug}/owner-only/",
        "/orgs/{slug}/admin-mixin/",
    ],
)
def test_saas_mode_returns_403_for_non_member_org_routes(
    client, settings, path
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="carol",
        email="carol@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")
    client.force_login(user)

    response = client.get(path.format(slug=organization.slug))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/healthcheck/", "/accounts/profile/"])
def test_request_org_is_none_for_exempt_routes(client, settings, path) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="dave",
        email="dave@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Delta", slug="delta")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get(path)

    assert response.status_code == 200
    assert response.content.decode() == "none|none"


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/orgs/", "/orgs/new/", "/orgs/{slug}/"])
def test_anonymous_saas_org_routes_redirect_to_login(client, settings, path) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Delta", slug="delta")

    response = client.get(path.format(slug=organization.slug))

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/accounts/login/")


@pytest.mark.django_db
def test_saas_mode_org_index_lists_memberships(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="erin",
        email="erin@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Echo", slug="echo")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get("/orgs/")

    assert response.status_code == 200
    assert organization.name in response.content.decode()
    assert organization.slug in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_org_index_shows_empty_state_without_memberships(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="frank",
        email="frank@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/")

    assert response.status_code == 200
    assert "Create your organization" in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_org_new_is_available_to_authenticated_users(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="grace",
        email="grace@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/new/")

    assert response.status_code == 200
    assert "Create your organization" in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_org_detail_renders_dashboard(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="harper",
        email="harper@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Harbor", slug="harbor")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 200
    assert "Organization dashboard" in response.content.decode()
    assert organization.name in response.content.decode()
    assert organization.slug in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_returns_404_for_unknown_org_routes(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="irene",
        email="irene@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/missing/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_current_org_id_route_returns_member_org_context(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="ivy",
        email="ivy@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Indigo", slug="indigo")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get(f"/orgs/{organization.slug}/current-org-id/")

    assert response.status_code == 200
    expected_current_org_id = (
        str(organization.id) if connection.vendor == "postgresql" else "none"
    )
    assert response.content.decode() == expected_current_org_id


@pytest.mark.django_db
def test_saas_mode_superusers_can_access_org_routes_without_membership(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_superuser(
        username="jules",
        email="jules@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Jade", slug="jade")
    client.force_login(user)

    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 200
    assert organization.name in response.content.decode()
    assert organization.slug in response.content.decode()


@pytest.mark.django_db
def test_resolve_org_slug_uses_personal_org_in_solo_mode(settings) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="erin",
        email="erin@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/")
    request.user = user
    middleware = TenantMiddleware(lambda _: None)

    org_slug = middleware._resolve_org_slug(request, saas_mode=False)

    assert org_slug == "erin"


def test_resolve_org_slug_returns_none_for_unmatched_paths_in_saas_mode() -> None:
    request = RequestFactory().get("/not-a-route/")
    middleware = TenantMiddleware(lambda _: None)

    org_slug = middleware._resolve_org_slug(request, saas_mode=True)

    assert org_slug is None


@pytest.mark.parametrize(
    ("view", "path", "kwargs"),
    [
        (org_index_view, "/orgs/", {}),
        (org_new_view, "/orgs/new/", {}),
        (org_detail_view, "/orgs/acme/", {"org_slug": "acme"}),
    ],
)
def test_org_views_raise_404_in_solo_mode(settings, view, path, kwargs) -> None:
    settings.QUICKSCALE_MODE = "solo"
    request = RequestFactory().get(path)
    request.user = SimpleNamespace(is_authenticated=True)

    with pytest.raises(Http404):
        view(request, **kwargs)


@pytest.mark.django_db
def test_switching_mode_changes_route_behaviour_without_model_changes(
    client, settings
) -> None:
    user = get_user_model().objects.create_user(
        username="frank",
        email="frank@example.com",
        password="secret123",
    )
    Organization.objects.create_personal_for(user)
    organization = Organization.objects.create(name="Beta", slug="beta")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(user)

    with override_settings(
        QUICKSCALE_MODE="solo",
        ROOT_URLCONF="tests.urls_pre_home",
    ):
        solo_response = client.get("/")

    with override_settings(QUICKSCALE_MODE="saas"):
        with override_settings(ROOT_URLCONF="tests.urls"):
            saas_response = client.get("/")

    assert solo_response.status_code == 200
    assert "Organization dashboard" in solo_response.content.decode()
    assert saas_response.status_code == 200
    assert saas_response.content.decode() == "none|none"


@pytest.mark.django_db(transaction=True)
def test_postgres_request_sets_current_org_id_for_org_scoped_requests(
    client, settings
) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("current_setting validation requires PostgreSQL")

    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="gina",
        email="gina@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Gamma", slug="gamma")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(user)

    org_response = client.get(f"/orgs/{organization.slug}/current-org-id/")
    healthcheck_response = client.get("/healthcheck/")

    assert org_response.status_code == 200
    assert org_response.content.decode() == str(organization.id)
    assert healthcheck_response.content.decode() == "none|none"
