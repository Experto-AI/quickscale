"""Middleware contract tests for the QuickScale organizations module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory

from quickscale_modules_orgs.middleware import TenantMiddleware
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


@pytest.mark.django_db
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
    assert response.content.decode().startswith("alice|")
    assert Organization.objects.filter(
        is_personal=True, memberships__user=user
    ).exists()


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
def test_saas_mode_returns_403_for_non_member_org_route(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="carol",
        email="carol@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")
    client.force_login(user)

    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_request_org_is_none_for_non_org_routes(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="dave",
        email="dave@example.com",
        password="secret123",
    )
    Organization.objects.create_personal_for(user)
    client.force_login(user)

    response = client.get("/healthcheck/")

    assert response.status_code == 200
    assert response.content.decode() == "none|none"


@pytest.mark.django_db
def test_anonymous_saas_org_routes_redirect_to_login(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Delta", slug="delta")

    index_response = client.get("/orgs/")
    detail_response = client.get(f"/orgs/{organization.slug}/")

    assert index_response.status_code == 302
    assert index_response.headers["Location"].startswith("/accounts/login/")
    assert detail_response.status_code == 302
    assert detail_response.headers["Location"].startswith("/accounts/login/")


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

    settings.QUICKSCALE_MODE = "solo"
    solo_response = client.get("/")

    settings.QUICKSCALE_MODE = "saas"
    saas_response = client.get("/")

    assert solo_response.status_code == 200
    assert solo_response.content.decode().startswith("frank|")
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
