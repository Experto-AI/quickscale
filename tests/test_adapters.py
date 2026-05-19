"""Adapter contract tests for the QuickScale organizations module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from quickscale_modules_orgs.adapters import OrgsAccountAdapter
from quickscale_modules_orgs.models import Organization


@pytest.mark.django_db
def test_solo_signup_redirect_creates_personal_org(settings) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="alice.org",
        email="alice@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/")
    request.user = user

    redirect_url = OrgsAccountAdapter().get_signup_redirect_url(request)

    assert redirect_url == "/"
    assert Organization.objects.get().slug == "aliceorg"


@pytest.mark.django_db
def test_saas_signup_redirect_without_membership_goes_to_org_creation(settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="bob",
        email="bob@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/")
    request.user = user

    redirect_url = OrgsAccountAdapter().get_signup_redirect_url(request)

    assert redirect_url == "/orgs/new/"


@pytest.mark.django_db
def test_login_redirect_stays_root_when_membership_exists(settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    settings.LOGIN_REDIRECT_URL = "/dashboard/"
    user = get_user_model().objects.create_user(
        username="carol",
        email="carol@example.com",
        password="secret123",
    )
    Organization.objects.create_personal_for(user)
    request = RequestFactory().get("/")
    request.user = user

    redirect_url = OrgsAccountAdapter().get_login_redirect_url(request)

    assert redirect_url == "/dashboard/"


@pytest.mark.django_db
def test_login_redirect_sends_saas_users_without_memberships_to_org_creation(
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    settings.LOGIN_REDIRECT_URL = "/dashboard/"
    user = get_user_model().objects.create_user(
        username="dana",
        email="dana@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/")
    request.user = user

    redirect_url = OrgsAccountAdapter().get_login_redirect_url(request)

    assert redirect_url == "/orgs/new/"


@pytest.mark.django_db
def test_solo_login_redirect_creates_personal_org_and_keeps_base_redirect(
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "solo"
    settings.LOGIN_REDIRECT_URL = "/accounts/profile/"
    user = get_user_model().objects.create_user(
        username="erin",
        email="erin@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/")
    request.user = user

    redirect_url = OrgsAccountAdapter().get_login_redirect_url(request)

    assert redirect_url == "/accounts/profile/"
    assert Organization.objects.filter(
        is_personal=True, memberships__user=user
    ).exists()
