"""Adapter contract tests for the QuickScale organizations module."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from quickscale_modules_orgs.adapters import OrgsAccountAdapter
from quickscale_modules_orgs.constants import (
    ORG_INVITATION_ACCEPT_URL_NAME,
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from quickscale_modules_orgs.models import Organization, OrganizationInvitation


def _attach_session(request) -> None:
    middleware = SessionMiddleware(lambda _: None)
    middleware.process_request(request)
    request.session.save()


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
    assert (
        Organization.objects.get(is_personal=True, memberships__user=user).slug
        == "aliceorg"
    )


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
def test_saas_signup_redirect_prefers_pending_invitation_accept_path(settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="alix",
        email="alix@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="bryn",
        email="bryn@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Alpha", slug="alpha")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=invited_user.email,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    request = RequestFactory().get("/")
    request.user = invited_user
    _attach_session(request)
    request.session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)

    redirect_url = OrgsAccountAdapter().get_signup_redirect_url(request)

    assert redirect_url == reverse(
        ORG_INVITATION_ACCEPT_URL_NAME,
        kwargs={"token": invitation.token},
    )


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
def test_login_redirect_prefers_pending_invitation_accept_path(settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    settings.LOGIN_REDIRECT_URL = "/dashboard/"
    inviter = get_user_model().objects.create_user(
        username="cato",
        email="cato@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="drew",
        email="drew@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Delta", slug="delta")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=invited_user.email,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    request = RequestFactory().get("/")
    request.user = invited_user
    _attach_session(request)
    request.session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)

    redirect_url = OrgsAccountAdapter().get_login_redirect_url(request)

    assert redirect_url == reverse(
        ORG_INVITATION_ACCEPT_URL_NAME,
        kwargs={"token": invitation.token},
    )


@pytest.mark.django_db
def test_login_redirect_prefers_pending_invitation_even_when_membership_exists(
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    settings.LOGIN_REDIRECT_URL = "/dashboard/"
    inviter = get_user_model().objects.create_user(
        username="existing-member-inviter",
        email="existing-member-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="existing-member-invitee",
        email="existing-member-invitee@example.com",
        password="secret123",
    )
    existing_org = Organization.objects.create(name="Existing", slug="existing")
    Organization.objects.create_personal_for(invited_user)
    organization = Organization.objects.create(name="Delta", slug="delta")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=invited_user.email,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    request = RequestFactory().get("/")
    request.user = invited_user
    _attach_session(request)
    request.session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)

    redirect_url = OrgsAccountAdapter().get_login_redirect_url(request)

    assert Organization.objects.filter(pk=existing_org.pk).exists()
    assert redirect_url == reverse(
        ORG_INVITATION_ACCEPT_URL_NAME,
        kwargs={"token": invitation.token},
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "redirect_method", ["get_login_redirect_url", "get_signup_redirect_url"]
)
@pytest.mark.parametrize("state", ["expired", "accepted"])
def test_post_auth_redirect_falls_back_to_org_creation_when_pending_invitation_is_terminal(
    settings,
    redirect_method,
    state,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    settings.LOGIN_REDIRECT_URL = "/dashboard/"
    inviter = get_user_model().objects.create_user(
        username=f"{state}-inviter",
        email=f"{state}-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username=f"{state}-invitee",
        email=f"{state}-invitee@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Helios", slug="helios")
    invitation_kwargs = {
        "organization": organization,
        "email": invited_user.email,
        "invited_by": inviter,
        "expires_at": timezone.now() + timedelta(days=7),
    }
    if state == "expired":
        invitation_kwargs["expires_at"] = timezone.now() - timedelta(minutes=1)
    else:
        invitation_kwargs["accepted_at"] = timezone.now() - timedelta(minutes=1)
    invitation = OrganizationInvitation.objects.create(**invitation_kwargs)
    request = RequestFactory().get("/")
    request.user = invited_user
    _attach_session(request)
    request.session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)

    redirect_url = getattr(OrgsAccountAdapter(), redirect_method)(request)

    assert redirect_url == "/orgs/new/"
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in request.session


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
