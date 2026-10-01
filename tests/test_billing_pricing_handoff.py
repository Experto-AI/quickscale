"""Tests for the organization-creation billing pricing handoff (rule 4).

The orgs create flow asks the declared ``organization_pricing_url_hooks``
capability for a post-create pricing URL; billing answers through its public
service, so orgs' source names no billing route, label, or setting.
"""

from __future__ import annotations

import json

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.urls import reverse

from quickscale_modules_orgs import views as org_views
from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
)


def test_billing_declares_the_pricing_url_capability() -> None:
    """Rule 4: billing declares its pricing URL on its own AppConfig."""
    from quickscale_core.runtime import collect_capabilities
    from quickscale_modules_billing.services import organization_pricing_page_url

    config = apps.get_app_config("quickscale_billing")

    assert config.organization_pricing_url_hooks() == (organization_pricing_page_url,)
    assert organization_pricing_page_url in collect_capabilities(
        "organization_pricing_url_hooks"
    )


def test_billing_pricing_url_is_the_module_pricing_page() -> None:
    """The declared hook answers billing's real flat pricing route."""
    from quickscale_modules_billing.services import organization_pricing_page_url

    assert reverse("quickscale_billing:pricing_page") == "/billing/pricing/"
    assert organization_pricing_page_url(None) == "/billing/pricing/"


def test_billing_pricing_path_uses_the_first_declared_url(monkeypatch) -> None:
    """The collector returns the first provider that answers a URL."""
    monkeypatch.setattr(
        org_views,
        "collect_capabilities",
        lambda capability: (
            lambda organization: None,
            lambda organization: "/billing/pricing/",
        ),
    )

    assert org_views._billing_pricing_path(None) == "/billing/pricing/"


def test_billing_pricing_path_returns_none_without_a_declared_provider(
    monkeypatch,
) -> None:
    """No provider means no handoff; the create flow keeps its fallback."""
    monkeypatch.setattr(org_views, "collect_capabilities", lambda capability: ())

    assert org_views._billing_pricing_path(None) is None


@pytest.mark.django_db
def test_saas_org_create_redirects_to_the_declared_billing_pricing_url(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="handoff-builder",
        email="handoff-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": "Handoff Labs"}, follow=True)

    organization = Organization.objects.get(slug="handoff-labs")
    membership = OrganizationMembership.objects.get(
        user=user,
        organization=organization,
    )
    # The followed request resolves the new organization through the session
    # and reaches billing's pricing page instead of bouncing to /orgs/.
    assert response.redirect_chain == [("/billing/pricing/", 302)]
    assert response.status_code == 200
    assert client.session[ACTIVE_ORG_SESSION_KEY] == str(organization.pk)
    assert membership.role == OrgRole.OWNER


@pytest.mark.django_db
def test_org_api_create_returns_the_declared_billing_pricing_url(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="api-handoff-builder",
        email="api-handoff-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.post(
        "/orgs/api/",
        data=json.dumps({"name": "API Handoff Labs"}),
        content_type="application/json",
    )

    organization = Organization.objects.get(slug="api-handoff-labs")
    assert response.status_code == 201
    assert response.json()["next_url"] == "/billing/pricing/"
    assert response.json()["billing_pricing_url"] == "/billing/pricing/"
    assert client.session[ACTIVE_ORG_SESSION_KEY] == str(organization.pk)
    assert OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
    ).exists()
    # The returned URL opens under the new organization through the middleware.
    followed = client.get(response.json()["next_url"])
    assert followed.status_code == 200


@pytest.mark.django_db
def test_saas_org_create_activates_the_new_organization_over_a_stale_session(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="stale-builder",
        email="stale-builder@example.com",
        password="secret123",
    )
    client.force_login(user)
    stale_organization = Organization.objects.create(name="Stale Org", slug="stale-org")
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(stale_organization.pk)
    session.save()
    assert client.session[ACTIVE_ORG_SESSION_KEY] == str(stale_organization.pk)

    response = client.post("/orgs/new/", {"name": "Fresh Labs"})

    organization = Organization.objects.get(slug="fresh-labs")
    assert response.status_code == 302
    assert response.headers["Location"] == "/billing/pricing/"
    assert client.session[ACTIVE_ORG_SESSION_KEY] == str(organization.pk)


@pytest.mark.django_db
def test_saas_org_create_falls_back_when_billing_is_switched_off(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    settings.QUICKSCALE_BILLING_ENABLED = False
    user = get_user_model().objects.create_user(
        username="off-builder",
        email="off-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": "Switched Off Labs"})

    organization = Organization.objects.get(slug="switched-off-labs")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/"


@pytest.mark.django_db
def test_org_api_create_returns_null_pricing_url_when_switched_off(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    settings.QUICKSCALE_BILLING_ENABLED = False
    user = get_user_model().objects.create_user(
        username="api-off-builder",
        email="api-off-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.post(
        "/orgs/api/",
        data=json.dumps({"name": "API Switched Off Labs"}),
        content_type="application/json",
    )

    organization = Organization.objects.get(slug="api-switched-off-labs")
    assert response.status_code == 201
    assert response.json()["next_url"] == f"/orgs/{organization.slug}/"
    assert response.json()["billing_pricing_url"] is None
