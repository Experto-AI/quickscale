"""Tests for the QuickScale analytics module-owned page."""

from __future__ import annotations

from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import override_settings
from django.urls import reverse

from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
)

DASHBOARD_TEST_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]


def _dashboard_url() -> str:
    return reverse("quickscale_analytics:dashboard")


def _user(username: str):
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password123",
    )


def _activate_org_in_session(client: Any, organization: Organization) -> None:
    """Set the active org in the client session for TenantMiddleware."""
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.id)
    session.save()


def _viewer_user(username: str = "analytics-viewer"):
    """Create a user whose only org role is viewer."""
    user = _user(username)
    organization = Organization.objects.create_personal_for(user)
    OrganizationMembership.objects.filter(user=user, organization=organization).update(
        role=OrgRole.VIEWER
    )
    return user, organization


@pytest.mark.django_db
def test_analytics_dashboard_redirects_anonymous_users_to_login(client) -> None:
    """Anonymous visitors enter the configured auth flow before the page."""
    dashboard_url = _dashboard_url()

    response = client.get(dashboard_url)

    assert response.status_code == 302
    assert response["Location"] == (
        f"{resolve_url(settings.LOGIN_URL)}?next={dashboard_url}"
    )


@pytest.mark.django_db
@override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
def test_analytics_dashboard_refuses_authenticated_user_without_org_context(
    client,
) -> None:
    """An authenticated user with no organization context is refused (403)."""
    client.force_login(_user("analytics-orgless"))

    response = client.get(_dashboard_url())

    assert response.status_code == 403


@pytest.mark.django_db
def test_analytics_dashboard_refuses_non_member_with_active_session_org(
    client,
) -> None:
    """A session org the user does not belong to is refused (403)."""
    user = _user("analytics-outsider")
    other_org = Organization.objects.create(name="Other Org", slug="other-org")
    client.force_login(user)
    _activate_org_in_session(client, other_org)

    response = client.get(_dashboard_url())

    assert response.status_code == 403


@pytest.mark.django_db
def test_analytics_dashboard_returns_200_for_viewer(client) -> None:
    """An organization viewer renders the analytics overview page."""
    user, organization = _viewer_user()
    client.force_login(user)
    _activate_org_in_session(client, organization)

    response = client.get(_dashboard_url())

    assert response.status_code == 200
    assert "Analytics" in response.content.decode()


@pytest.mark.django_db
@override_settings(QUICKSCALE_ANALYTICS_ENABLED=False)
def test_analytics_dashboard_reports_disabled(client) -> None:
    """The analytics dashboard indicates when analytics is disabled."""
    user, organization = _viewer_user("analytics-viewer-disabled")
    client.force_login(user)
    _activate_org_in_session(client, organization)

    response = client.get(_dashboard_url())

    assert response.status_code == 200
    assert "disabled" in response.content.decode().lower()
