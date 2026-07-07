"""Focused view tests for the QuickScale organizations module."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import resolve_url
from django.test import override_settings
from django.utils import timezone

from quickscale_modules_orgs import forms as org_forms
from quickscale_modules_orgs import views as org_views
from quickscale_modules_orgs.constants import (
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


class DummyOrganizationContextView(org_views.OrganizationContextMixin):
    pass


@pytest.mark.django_db
def test_saas_org_create_post_creates_org_and_redirects_to_billing(
    client, settings, monkeypatch
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="builder",
        email="builder@example.com",
        password="secret123",
    )
    client.force_login(user)
    monkeypatch.setattr(
        org_views,
        "_billing_pricing_path",
        lambda organization: f"/orgs/{organization.slug}/billing/pricing/",
    )

    response = client.post("/orgs/new/", {"name": "Acme Labs"})

    organization = Organization.objects.get(slug="acme-labs")
    membership = OrganizationMembership.objects.get(
        user=user,
        organization=organization,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/acme-labs/billing/pricing/"
    assert membership.role == OrgRole.OWNER
    assert organization.is_personal is False


@pytest.mark.django_db
def test_saas_org_create_post_falls_back_to_org_dashboard_without_billing(
    client, settings, monkeypatch
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="fallback-builder",
        email="fallback-builder@example.com",
        password="secret123",
    )
    client.force_login(user)
    monkeypatch.setattr(org_views, "_billing_pricing_path", lambda organization: None)

    response = client.post("/orgs/new/", {"name": "Fallback Labs"})

    organization = Organization.objects.get(slug="fallback-labs")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/"


@pytest.mark.django_db
def test_saas_org_create_uses_suffixed_slug_when_name_is_taken(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="suffix-builder",
        email="suffix-builder@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Acme Labs", slug="acme-labs")
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": "Acme Labs"})

    assert response.status_code == 302
    assert Organization.objects.filter(slug="acme-labs-2").exists()


@pytest.mark.django_db
def test_saas_org_create_truncates_overlong_slug_and_reserves_suffix_room(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="long-builder",
        email="long-builder@example.com",
        password="secret123",
    )
    long_name = "A" * 200
    max_length = Organization._meta.get_field("slug").max_length or 150
    Organization.objects.create(name="Taken", slug="a" * max_length)
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": long_name})

    organization = Organization.objects.get(name=long_name)
    assert response.status_code == 302
    assert len(organization.slug) == max_length
    assert organization.slug == f"{'a' * (max_length - 2)}-2"


@pytest.mark.django_db
def test_saas_org_create_retries_after_insert_collision(
    client, settings, monkeypatch
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="race-builder",
        email="race-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    original_create = Organization.objects.create
    attempts = {"count": 0}

    def flaky_create(*args, **kwargs):
        if kwargs.get("slug") == "acme-labs" and attempts["count"] == 0:
            attempts["count"] += 1
            raise IntegrityError("duplicate key value violates unique constraint")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(Organization.objects, "create", flaky_create)

    response = client.post("/orgs/new/", {"name": "Acme Labs"})

    organization = Organization.objects.get(name="Acme Labs")
    assert response.status_code == 302
    assert attempts["count"] == 1
    assert organization.slug == "acme-labs-2"


@pytest.mark.parametrize(
    "slugified_value",
    ["", "-"],
)
def test_generated_slug_candidates_reject_invalid_values(
    monkeypatch, slugified_value
) -> None:
    monkeypatch.setattr(org_forms, "slugify", lambda value: slugified_value)

    with pytest.raises(ValidationError):
        next(org_forms._generated_slug_candidates("Acme"))


def test_generated_slug_candidates_increment_suffixes() -> None:
    candidates = org_forms._generated_slug_candidates("Acme Labs")

    assert next(candidates) == "acme-labs"
    assert next(candidates) == "acme-labs-2"
    assert next(candidates) == "acme-labs-3"


def test_generated_slug_candidates_fail_when_suffix_wont_fit(monkeypatch) -> None:
    monkeypatch.setattr(
        Organization._meta,
        "get_field",
        lambda name: SimpleNamespace(max_length=1),
    )
    candidates = org_forms._generated_slug_candidates("A")

    assert next(candidates) == "a"
    with pytest.raises(RuntimeError, match="max_length"):
        next(candidates)


def test_org_create_form_clean_name_rejects_blank_values() -> None:
    form = org_forms.OrgCreateForm()
    form.cleaned_data = {"name": "   "}

    with pytest.raises(ValidationError, match="This field is required"):
        form.clean_name()


def test_normalize_unique_slug_rejects_non_slugifiable_values() -> None:
    with pytest.raises(ValidationError, match="Enter a slug"):
        org_forms._normalize_unique_slug("!!!")


@pytest.mark.django_db
def test_org_settings_form_clean_name_rejects_blank_values() -> None:
    organization = Organization.objects.create(name="Delta", slug="delta")
    form = org_forms.OrgSettingsForm(instance=organization)
    form.cleaned_data = {"name": "   "}

    with pytest.raises(ValidationError, match="This field is required"):
        form.clean_name()


@pytest.mark.django_db
def test_invite_form_rejects_existing_members_by_normalized_email() -> None:
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    owner = get_user_model().objects.create_user(
        username="atlas-owner",
        email="Owner@Example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    form = org_forms.InviteForm(
        {"email": "owner@example.com", "role": OrgRole.ADMIN},
        organization=organization,
        invited_by=owner,
        owner_like=True,
    )

    assert not form.is_valid()
    assert form.errors["email"] == ["This email already belongs to a current member."]


@pytest.mark.django_db
def test_invite_form_rejects_duplicate_pending_invites_by_normalized_email() -> None:
    organization = Organization.objects.create(name="Nebula", slug="nebula")
    owner = get_user_model().objects.create_user(
        username="nebula-owner",
        email="nebula-owner@example.com",
        password="secret123",
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="Invitee@Example.com",
        role=OrgRole.MEMBER,
        invited_by=owner,
        expires_at=timezone.now() + timedelta(days=7),
    )
    form = org_forms.InviteForm(
        {"email": "invitee@example.com", "role": OrgRole.ADMIN},
        organization=organization,
        invited_by=owner,
        owner_like=True,
    )

    assert not form.is_valid()
    assert form.errors["email"] == ["This email already has a pending invitation."]


@pytest.mark.django_db
def test_invite_form_allows_reinviting_after_expiry() -> None:
    organization = Organization.objects.create(name="Comet", slug="comet")
    owner = get_user_model().objects.create_user(
        username="comet-owner",
        email="comet-owner@example.com",
        password="secret123",
    )
    expired_invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="Invitee@Example.com",
        role=OrgRole.MEMBER,
        invited_by=owner,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    form = org_forms.InviteForm(
        {"email": "invitee@example.com", "role": OrgRole.ADMIN},
        organization=organization,
        invited_by=owner,
        owner_like=True,
    )

    assert form.is_valid(), form.errors

    invitation = form.save()

    assert invitation.pk != expired_invitation.pk
    assert invitation.email == "invitee@example.com"
    assert invitation.role == OrgRole.ADMIN
    assert invitation.expires_at > timezone.now()


@pytest.mark.django_db
def test_invite_form_save_rejects_duplicate_created_after_validation() -> None:
    organization = Organization.objects.create(name="Pioneer", slug="pioneer")
    owner = get_user_model().objects.create_user(
        username="pioneer-owner",
        email="pioneer-owner@example.com",
        password="secret123",
    )
    form = org_forms.InviteForm(
        {"email": "invitee@example.com", "role": OrgRole.ADMIN},
        organization=organization,
        invited_by=owner,
        owner_like=True,
    )

    assert form.is_valid(), form.errors

    OrganizationInvitation.objects.create(
        organization=organization,
        email="INVITEE@example.com",
        role=OrgRole.MEMBER,
        invited_by=owner,
        expires_at=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(ValidationError) as exc_info:
        form.save()

    invitations = OrganizationInvitation.objects.filter(
        organization=organization,
        email__iexact="invitee@example.com",
        accepted_at__isnull=True,
    )

    assert exc_info.value.message_dict == {
        "email": ["This email already has a pending invitation."]
    }
    assert invitations.count() == 1
    assert invitations.get().role == OrgRole.MEMBER


@pytest.mark.django_db
def test_role_change_form_rejects_non_owner_transfer_to_owner() -> None:
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    actor = get_user_model().objects.create_user(
        username="atlas-admin",
        email="atlas-admin@example.com",
        password="secret123",
    )
    target = get_user_model().objects.create_user(
        username="atlas-target",
        email="atlas-target@example.com",
        password="secret123",
    )
    acting_membership = OrganizationMembership.objects.create(
        user=actor,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    target_membership = OrganizationMembership.objects.create(
        user=target,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    form = org_forms.RoleChangeForm(
        {"role": OrgRole.OWNER},
        target_membership=target_membership,
        acting_membership=acting_membership,
    )

    form.cleaned_data = {"role": OrgRole.OWNER}

    with pytest.raises(ValidationError, match="Only an owner can transfer ownership"):
        form.clean_role()


@pytest.mark.django_db
def test_role_change_form_save_updates_membership() -> None:
    organization = Organization.objects.create(name="Comet", slug="comet")
    owner = get_user_model().objects.create_user(
        username="comet-owner",
        email="comet-owner@example.com",
        password="secret123",
    )
    member = get_user_model().objects.create_user(
        username="comet-member",
        email="comet-member@example.com",
        password="secret123",
    )
    owner_membership = OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    target_membership = OrganizationMembership.objects.create(
        user=member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    form = org_forms.RoleChangeForm(
        {"role": OrgRole.ADMIN},
        target_membership=target_membership,
        acting_membership=owner_membership,
    )

    assert form.is_valid()
    saved_membership = form.save()

    target_membership.refresh_from_db()
    assert saved_membership.role == OrgRole.ADMIN
    assert target_membership.role == OrgRole.ADMIN


@pytest.mark.django_db
def test_organization_context_uses_org_slug_when_request_org_missing(rf) -> None:
    organization = Organization.objects.create(name="Fallback Org", slug="fallback-org")
    view = DummyOrganizationContextView()
    view.request = rf.get("/")
    view.kwargs = {"org_slug": organization.slug}

    assert view.get_organization() == organization
    assert str(organization) == "Fallback Org"


def test_organization_context_requires_org_slug_or_request_org(rf) -> None:
    view = DummyOrganizationContextView()
    view.request = rf.get("/")
    view.kwargs = {}

    with pytest.raises(Http404, match="Organization not found"):
        view.get_organization()


@pytest.mark.django_db
def test_organization_context_superuser_has_no_acting_membership(rf) -> None:
    superuser = get_user_model().objects.create_superuser(
        username="orgs-superuser",
        email="orgs-superuser@example.com",
        password="secret123",
    )
    view = DummyOrganizationContextView()
    request = rf.get("/")
    request.user = superuser
    view.request = request
    view.kwargs = {"org_slug": "unused"}

    assert view.get_acting_membership() is None


@pytest.mark.django_db
def test_saas_org_create_rejects_non_slugifiable_name(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="invalid-builder",
        email="invalid-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": "!!!"})

    assert response.status_code == 200
    assert (
        "Enter a name that contains at least one letter or number."
        in response.content.decode()
    )
    assert not Organization.objects.filter(name="!!!").exists()


@pytest.mark.django_db
def test_member_list_requires_admin_role(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Northwind", slug="northwind")
    admin_user = get_user_model().objects.create_user(
        username="northwind-admin",
        email="northwind-admin@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="northwind-member",
        email="northwind-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    client.force_login(admin_user)
    admin_response = client.get(f"/orgs/{organization.slug}/members/")
    client.logout()

    client.force_login(member_user)
    member_response = client.get(f"/orgs/{organization.slug}/members/")

    assert admin_response.status_code == 200
    assert "Update role" in admin_response.content.decode()
    assert member_response.status_code == 403


@pytest.mark.django_db
def test_member_list_renders_pending_invitations(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Northwind", slug="northwind")
    admin_user = get_user_model().objects.create_user(
        username="northwind-admin",
        email="northwind-admin@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.MEMBER,
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(admin_user)

    response = client.get(f"/orgs/{organization.slug}/members/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Pending invitations" in content
    assert "invitee@example.com" in content
    assert "Revoke invitation" in content


@pytest.mark.django_db
def test_invite_view_creates_invitation_and_dispatches_notification(
    client,
    settings,
    monkeypatch,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Helios", slug="helios")
    admin_user = get_user_model().objects.create_user(
        username="helios-admin",
        email="helios-admin@example.com",
        password="secret123",
        first_name="Helios",
        last_name="Admin",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    captured_calls: list[dict[str, object]] = []

    def fake_sender(**kwargs: object) -> object:
        captured_calls.append(dict(kwargs))
        return SimpleNamespace()

    monkeypatch.setattr(
        org_views,
        "_load_invitation_notification_sender",
        lambda: fake_sender,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/invite/",
        {"email": "Invitee@Example.com", "role": OrgRole.ADMIN},
    )

    invitation = OrganizationInvitation.objects.get(organization=organization)
    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/members/"
    assert invitation.email == "invitee@example.com"
    assert invitation.role == OrgRole.ADMIN
    assert len(captured_calls) == 1
    assert captured_calls[0]["template_key"] == "notifications.org_invitation"
    assert captured_calls[0]["recipients"] == ["invitee@example.com"]
    assert captured_calls[0]["tags"] == ["auth"]
    assert captured_calls[0]["metadata"] == {"workflow": "org-invitation"}
    assert captured_calls[0]["context"] == {
        "organization_name": organization.name,
        "invitee_email": "invitee@example.com",
        "inviter_name": "Helios Admin",
        "role_display": "Admin",
        "accept_url": (
            f"http://testserver/orgs/invitations/{invitation.token}/accept/"
        ),
        "expires_at": invitation.expires_at.astimezone(timezone.UTC).isoformat(),
    }


@pytest.mark.django_db
def test_invite_view_rejects_existing_member_without_sending_notification(
    client,
    settings,
    monkeypatch,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nova", slug="nova")
    admin_user = get_user_model().objects.create_user(
        username="nova-admin",
        email="nova-admin@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="nova-member",
        email="member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    dispatched: list[dict[str, object]] = []

    monkeypatch.setattr(
        org_views,
        "_load_invitation_notification_sender",
        lambda: lambda **kwargs: dispatched.append(dict(kwargs)),
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/invite/",
        {"email": "MEMBER@example.com", "role": OrgRole.ADMIN},
    )

    assert response.status_code == 400
    assert OrganizationInvitation.objects.count() == 0
    assert dispatched == []
    assert "already belongs to a current member" in response.content.decode()


@pytest.mark.django_db
def test_invite_view_rejects_save_time_validation_without_sending_notification(
    client,
    settings,
    monkeypatch,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Pioneer", slug="pioneer")
    admin_user = get_user_model().objects.create_user(
        username="pioneer-admin",
        email="pioneer-admin@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    dispatched: list[dict[str, object]] = []

    monkeypatch.setattr(
        org_views,
        "_load_invitation_notification_sender",
        lambda: lambda **kwargs: dispatched.append(dict(kwargs)),
    )

    def rejecting_save(self: org_forms.InviteForm) -> OrganizationInvitation:
        raise ValidationError(
            {"email": ["This email already has a pending invitation."]}
        )

    monkeypatch.setattr(org_forms.InviteForm, "save", rejecting_save)
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/invite/",
        {"email": "invitee@example.com", "role": OrgRole.ADMIN},
    )

    assert response.status_code == 400
    assert OrganizationInvitation.objects.filter(organization=organization).count() == 0
    assert dispatched == []
    assert "already has a pending invitation" in response.content.decode()


@pytest.mark.django_db
def test_invitation_accept_view_redeems_matching_authenticated_user_and_clears_session(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="accept-inviter",
        email="accept-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="accept-invitee",
        email="Invitee@Example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Aperture", slug="aperture")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(invited_user)
    session = client.session
    session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)
    session.save()

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    invitation.refresh_from_db()
    membership = OrganizationMembership.objects.get(
        user=invited_user,
        organization=organization,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/"
    assert membership.role == OrgRole.ADMIN
    assert membership.invited_by == inviter
    assert invitation.accepted_at is not None
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_invitation_accept_view_is_idempotent_for_existing_member_with_matching_email(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="idempotent-inviter",
        email="idempotent-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="idempotent-invitee",
        email="invitee@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    membership = OrganizationMembership.objects.create(
        user=invited_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="INVITEE@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(invited_user)
    session = client.session
    session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)
    session.save()

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    invitation.refresh_from_db()
    membership.refresh_from_db()
    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/"
    assert (
        OrganizationMembership.objects.filter(
            user=invited_user,
            organization=organization,
        ).count()
        == 1
    )
    assert membership.role == OrgRole.MEMBER
    assert invitation.accepted_at is not None
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_invitation_accept_view_redirects_anonymous_user_to_login_and_stores_session(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="anon-inviter",
        email="anon-inviter@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Beacon", slug="beacon")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    assert response.status_code == 302
    assert response.headers["Location"] == (
        f"{resolve_url(settings.LOGIN_URL)}"
        f"?next=/orgs/invitations/{invitation.token}/accept/"
    )
    assert client.session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] == str(
        invitation.token
    )


@pytest.mark.django_db
def test_invitation_accept_view_rejects_authenticated_email_mismatch_and_clears_session(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="mismatch-inviter",
        email="mismatch-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="mismatch-invitee",
        email="other@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Beacon", slug="beacon")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(invited_user)
    session = client.session
    session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)
    session.save()

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    invitation.refresh_from_db()
    content = response.content.decode()
    assert response.status_code == 403
    assert not OrganizationMembership.objects.filter(
        user=invited_user,
        organization=organization,
    ).exists()
    assert invitation.accepted_at is None
    assert "Invitation email mismatch" in content
    assert "only be accepted by the invited email address" in content
    assert invited_user.email in content
    assert invitation.email in content
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_invitation_accept_view_returns_410_and_clears_session_for_expired_invitation(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="expired-inviter",
        email="expired-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="expired-invitee",
        email="expired-invitee@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Comet", slug="comet")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=invited_user.email,
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    client.force_login(invited_user)
    session = client.session
    session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)
    session.save()

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    invitation.refresh_from_db()
    content = response.content.decode()
    assert response.status_code == 410
    assert not OrganizationMembership.objects.filter(
        user=invited_user,
        organization=organization,
    ).exists()
    assert invitation.accepted_at is None
    assert "Invitation expired" in content
    assert "Ask an organization admin to send you a new invite" in content
    assert organization.name in content
    assert invitation.email in content
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_invitation_accept_view_returns_410_and_clears_session_for_used_invitation(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="used-inviter",
        email="used-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="used-invitee",
        email="used-invitee@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Delta", slug="delta")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=invited_user.email,
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
        accepted_at=timezone.now() - timedelta(minutes=1),
    )
    client.force_login(invited_user)
    session = client.session
    session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)
    session.save()

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    content = response.content.decode()
    assert response.status_code == 410
    assert not OrganizationMembership.objects.filter(
        user=invited_user,
        organization=organization,
    ).exists()
    assert "Invitation already used" in content
    assert "already been redeemed" in content
    assert organization.name in content
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_invitation_accept_view_fails_closed_for_persisted_owner_invitation(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="owner-gap-inviter",
        email="owner-gap-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="owner-gap-invitee",
        email="owner-gap-invitee@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Vertex", slug="vertex")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=invited_user.email,
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    OrganizationInvitation.objects.filter(pk=invitation.pk).update(role=OrgRole.OWNER)
    client.force_login(invited_user)
    session = client.session
    session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)
    session.save()

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    invitation.refresh_from_db()
    content = response.content.decode()
    assert response.status_code == 410
    assert not OrganizationMembership.objects.filter(
        user=invited_user,
        organization=organization,
    ).exists()
    assert invitation.accepted_at is None
    assert "Invitation unavailable" in content
    assert "owner invitations are not supported" in content
    assert (
        "Ask Vertex to send a new invitation to owner-gap-invitee@example.com "
        "for a supported role." in content
    )
    assert "to join as Owner" not in content
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_invitation_accept_view_returns_404_and_clears_session_for_revoked_invitation(
    client,
    settings,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="revoked-inviter",
        email="revoked-inviter@example.com",
        password="secret123",
    )
    invited_user = get_user_model().objects.create_user(
        username="revoked-invitee",
        email="revoked-invitee@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Echo", slug="echo")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=invited_user.email,
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    invitation_token = invitation.token
    invitation.delete()
    client.force_login(invited_user)
    session = client.session
    session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation_token)
    session.save()

    response = client.get(f"/orgs/invitations/{invitation_token}/accept/")

    assert response.status_code == 404
    assert not OrganizationMembership.objects.filter(
        user=invited_user,
        organization=organization,
    ).exists()
    assert PENDING_ORG_INVITATION_TOKEN_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_revoke_invitation_view_deletes_pending_invitation(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Summit", slug="summit")
    admin_user = get_user_model().objects.create_user(
        username="summit-admin",
        email="summit-admin@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.MEMBER,
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/invitations/{invitation.pk}/revoke/"
    )

    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/members/"
    assert not OrganizationInvitation.objects.filter(pk=invitation.pk).exists()


@pytest.mark.django_db
def test_member_list_allows_superuser_without_membership(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Summit", slug="summit")
    owner = get_user_model().objects.create_user(
        username="summit-owner",
        email="summit-owner@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    superuser = get_user_model().objects.create_superuser(
        username="platform-owner",
        email="platform-owner@example.com",
        password="secret123",
    )
    client.force_login(superuser)

    response = client.get(f"/orgs/{organization.slug}/members/")

    assert response.status_code == 200
    assert "Update role" in response.content.decode()


@pytest.mark.django_db
def test_member_list_blocks_last_owner_demotion_but_allows_removal_when_sole_member(
    client, settings
) -> None:
    """Last-owner demotion is blocked (model-level invariant) but
    removal is now permitted when the owner is the sole member —
    nobody is stranded (SA47)."""
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Orbit", slug="orbit")
    owner = get_user_model().objects.create_user(
        username="orbit-owner",
        email="orbit-owner@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    client.force_login(owner)

    demote_response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "change-role",
            "membership_id": membership.pk,
            "role": OrgRole.ADMIN,
        },
    )

    # Demotion is blocked (last-owner invariant).
    assert demote_response.status_code == 400
    membership.refresh_from_db()
    assert membership.role == OrgRole.OWNER

    remove_response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": membership.pk,
        },
    )

    # Removal succeeds — sole owner with no other members is not blocking.
    assert remove_response.status_code == 302
    assert not OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_blocks_last_owner_removal_when_other_members_exist(
    client, settings
) -> None:
    """Last-owner removal is blocked when other members would be
    stranded ownerless (SA47)."""
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Vega", slug="vega")
    owner = get_user_model().objects.create_user(
        username="vega-owner",
        email="vega-owner@example.com",
        password="secret123",
    )
    other_member = get_user_model().objects.create_user(
        username="vega-member",
        email="vega-member@example.com",
        password="secret123",
    )
    owner_membership = OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.create(
        user=other_member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(owner)

    remove_response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": owner_membership.pk,
        },
    )

    assert remove_response.status_code == 400
    assert "You cannot remove the last owner" in remove_response.content.decode()
    assert OrganizationMembership.objects.filter(pk=owner_membership.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("json_request", [False, True], ids=["html", "json"])
def test_member_role_updates_translate_save_time_validation_errors(
    client,
    settings,
    monkeypatch,
    json_request,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Aster", slug="aster")
    acting_owner = get_user_model().objects.create_user(
        username=f"aster-acting-{json_request}",
        email=f"aster-acting-{json_request}@example.com",
        password="secret123",
    )
    target_owner = get_user_model().objects.create_user(
        username=f"aster-target-{json_request}",
        email=f"aster-target-{json_request}@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=acting_owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    target_membership = OrganizationMembership.objects.create(
        user=target_owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    def rejecting_save(self: org_forms.RoleChangeForm) -> OrganizationMembership:
        raise ValidationError(
            {"role": [OrganizationMembership.LAST_OWNER_DEMOTION_MESSAGE]}
        )

    monkeypatch.setattr(org_forms.RoleChangeForm, "save", rejecting_save)
    client.force_login(acting_owner)

    if json_request:
        response = client.post(
            f"/api/orgs/{organization.slug}/members/{target_membership.pk}/role/",
            data=json.dumps({"role": OrgRole.ADMIN}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"role": [OrganizationMembership.LAST_OWNER_DEMOTION_MESSAGE]}
        }
    else:
        response = client.post(
            f"/orgs/{organization.slug}/members/",
            {
                "action": "change-role",
                "membership_id": target_membership.pk,
                "role": OrgRole.ADMIN,
            },
        )
        assert response.status_code == 400
        assert (
            OrganizationMembership.LAST_OWNER_DEMOTION_MESSAGE
            in response.content.decode()
        )

    target_membership.refresh_from_db()
    assert target_membership.role == OrgRole.OWNER


@pytest.mark.django_db
def test_member_list_changes_role_and_redirects_on_success(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Helios", slug="helios")
    owner = get_user_model().objects.create_user(
        username="helios-owner",
        email="helios-owner@example.com",
        password="secret123",
    )
    member = get_user_model().objects.create_user(
        username="helios-member",
        email="helios-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    member_membership = OrganizationMembership.objects.create(
        user=member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(owner)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "change-role",
            "membership_id": member_membership.pk,
            "role": OrgRole.ADMIN,
        },
    )

    member_membership.refresh_from_db()
    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/members/"
    assert member_membership.role == OrgRole.ADMIN


@pytest.mark.django_db
def test_member_list_removes_members_and_redirects_on_success(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nova", slug="nova")
    admin_user = get_user_model().objects.create_user(
        username="nova-admin",
        email="nova-admin@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="nova-member",
        email="nova-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    membership = OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": membership.pk,
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/members/"
    assert not OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_rejects_unknown_actions(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Quasar", slug="quasar")
    admin_user = get_user_model().objects.create_user(
        username="quasar-admin",
        email="quasar-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "archive",
            "membership_id": membership.pk,
        },
    )

    assert response.status_code == 400
    assert "Unknown member action." in response.content.decode()


@pytest.mark.django_db
def test_member_list_rejects_malformed_membership_id(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nebula", slug="nebula")
    admin_user = get_user_model().objects.create_user(
        username="nebula-admin",
        email="nebula-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": "not-a-number",
        },
    )

    assert response.status_code == 400
    assert "Invalid member selection." in response.content.decode()
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_rejects_oversized_numeric_membership_id(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Pulsar", slug="pulsar")
    admin_user = get_user_model().objects.create_user(
        username="pulsar-admin",
        email="pulsar-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": "9" * 1000,
        },
    )

    assert response.status_code == 400
    assert "Invalid member selection." in response.content.decode()
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_rejects_negative_overflow_membership_id(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Zenith", slug="zenith")
    admin_user = get_user_model().objects.create_user(
        username="zenith-admin",
        email="zenith-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": f"-{'9' * 1000}",
        },
    )

    assert response.status_code == 400
    assert "Invalid member selection." in response.content.decode()
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_blocks_second_owner_assignment_without_transfer(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    owner = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    member = get_user_model().objects.create_user(
        username="atlas-member",
        email="atlas-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    member_membership = OrganizationMembership.objects.create(
        user=member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(owner)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "change-role",
            "membership_id": member_membership.pk,
            "role": OrgRole.OWNER,
        },
    )

    member_membership.refresh_from_db()
    assert response.status_code == 400
    assert member_membership.role == OrgRole.MEMBER


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("slug", "expected_error"),
    [
        ("!!!", "Enter a valid"),
        ("taken", "This slug is already in use."),
    ],
)
def test_org_settings_rejects_invalid_and_duplicate_slugs(
    client,
    settings,
    slug,
    expected_error,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Delta", slug="delta")
    Organization.objects.create(name="Taken", slug="taken")
    admin_user = get_user_model().objects.create_user(
        username="delta-admin",
        email="delta-admin@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/settings/",
        {"name": organization.name, "slug": slug},
    )

    organization.refresh_from_db()
    assert response.status_code == 200
    assert expected_error in response.content.decode()
    assert organization.slug == "delta"


@pytest.mark.django_db
def test_org_settings_requires_admin_and_updates_slug(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Beacon", slug="beacon")
    admin_user = get_user_model().objects.create_user(
        username="beacon-admin",
        email="beacon-admin@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="beacon-member",
        email="beacon-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    client.force_login(member_user)
    forbidden_response = client.get(f"/orgs/{organization.slug}/settings/")
    client.logout()

    client.force_login(admin_user)
    update_response = client.post(
        f"/orgs/{organization.slug}/settings/",
        {"name": "Beacon Labs", "slug": "beacon-labs"},
    )

    organization.refresh_from_db()
    assert forbidden_response.status_code == 403
    assert update_response.status_code == 302
    assert update_response.headers["Location"] == "/orgs/beacon-labs/settings/"
    assert organization.name == "Beacon Labs"
    assert organization.slug == "beacon-labs"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_pre_home")
def test_saas_pre_home_root_redirects_to_org_index(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="saas-owner",
        email="saas-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Vertex", slug="vertex")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_pre_home")
def test_solo_pre_home_root_route_renders_org_dashboard(client, settings) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="solo-owner",
        email="solo-owner@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 200
    assert "Organization dashboard" in response.content.decode()
    assert Organization.objects.filter(
        is_personal=True,
        memberships__user=user,
    ).exists()


@pytest.mark.django_db
def test_saas_org_api_create_requires_authentication(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"

    response = client.post(
        "/api/orgs/",
        data=json.dumps({"name": "Acme Labs"}),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}


@pytest.mark.django_db
def test_saas_org_api_create_post_creates_org_and_returns_json(
    client, settings, monkeypatch
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="api-builder",
        email="api-builder@example.com",
        password="secret123",
    )
    client.force_login(user)
    monkeypatch.setattr(
        org_views,
        "_billing_pricing_path",
        lambda organization: f"/orgs/{organization.slug}/billing/pricing/",
    )

    response = client.post(
        "/api/orgs/",
        data=json.dumps({"name": "Acme Labs"}),
        content_type="application/json",
    )

    organization = Organization.objects.get(slug="acme-labs")
    membership = OrganizationMembership.objects.get(
        user=user,
        organization=organization,
    )
    assert response.status_code == 201
    assert response.json() == {
        "organization": {
            "id": str(organization.id),
            "name": "Acme Labs",
            "slug": "acme-labs",
            "is_personal": False,
            "role": OrgRole.OWNER,
            "role_label": "Owner",
        },
        "next_url": "/orgs/acme-labs/billing/pricing/",
        "billing_pricing_url": "/orgs/acme-labs/billing/pricing/",
    }
    assert membership.role == OrgRole.OWNER
    assert organization.is_personal is False


@pytest.mark.django_db
def test_saas_org_api_create_falls_back_to_org_dashboard_without_billing(
    client, settings, monkeypatch
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="api-fallback-builder",
        email="api-fallback-builder@example.com",
        password="secret123",
    )
    client.force_login(user)
    monkeypatch.setattr(org_views, "_billing_pricing_path", lambda organization: None)

    response = client.post(
        "/api/orgs/",
        data=json.dumps({"name": "Fallback Labs"}),
        content_type="application/json",
    )

    organization = Organization.objects.get(slug="fallback-labs")
    assert response.status_code == 201
    assert response.json()["next_url"] == f"/orgs/{organization.slug}/"
    assert response.json()["billing_pricing_url"] is None


@pytest.mark.django_db
def test_saas_org_api_list_returns_memberships(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="erin-api",
        email="erin-api@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Echo", slug="echo")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get("/api/orgs/")

    assert response.status_code == 200
    assert response.json() == {
        "organizations": [
            {
                "id": str(organization.id),
                "name": "Echo",
                "slug": "echo",
                "is_personal": False,
                "role": OrgRole.MEMBER,
                "role_label": "Member",
            }
        ]
    }


@pytest.mark.django_db
def test_saas_org_api_list_returns_empty_state_without_memberships(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="frank-api",
        email="frank-api@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/api/orgs/")

    assert response.status_code == 200
    assert response.json() == {"organizations": []}


@pytest.mark.django_db
def test_saas_org_api_detail_returns_org_payload(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="harper-api",
        email="harper-api@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Harbor", slug="harbor")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get(f"/api/orgs/{organization.slug}/")

    assert response.status_code == 200
    assert response.json() == {
        "organization": {
            "id": str(organization.id),
            "name": "Harbor",
            "slug": "harbor",
            "is_personal": False,
            "role": OrgRole.MEMBER,
            "role_label": "Member",
            "member_count": 1,
        },
        "actor": {
            "role": OrgRole.MEMBER,
            "is_owner_like": False,
        },
    }


@pytest.mark.django_db
def test_saas_org_api_detail_returns_403_for_non_member(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="harper-api-403",
        email="harper-api-403@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Harbor", slug="harbor")
    client.force_login(user)

    response = client.get(f"/api/orgs/{organization.slug}/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_org_api_members_returns_members_and_pending_invitations(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Northwind", slug="northwind")
    admin_user = get_user_model().objects.create_user(
        username="northwind-admin-api",
        email="northwind-admin-api@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="northwind-member-api",
        email="northwind-member-api@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.MEMBER,
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(admin_user)

    response = client.get(f"/api/orgs/{organization.slug}/members/")

    payload = response.json()
    member_payloads = {member["user"]["email"]: member for member in payload["members"]}
    assert response.status_code == 200
    assert payload["organization"] == {
        "id": str(organization.id),
        "name": organization.name,
        "slug": organization.slug,
        "is_personal": False,
    }
    assert payload["actor"] == {"role": OrgRole.ADMIN, "is_owner_like": False}
    assert set(member_payloads) == {
        admin_user.email,
        member_user.email,
    }
    assert member_payloads[admin_user.email]["role"] == OrgRole.ADMIN
    assert member_payloads[member_user.email]["role"] == OrgRole.MEMBER
    assert payload["pending_invitations"] == [
        {
            "id": str(invitation.pk),
            "email": "invitee@example.com",
            "role": OrgRole.MEMBER,
            "role_label": "Member",
            "expires_at": invitation.expires_at.astimezone(timezone.UTC).isoformat(),
        }
    ]
    assert payload["role_choices"] == [
        {"value": OrgRole.VIEWER, "label": "Viewer"},
        {"value": OrgRole.MEMBER, "label": "Member"},
        {"value": OrgRole.ADMIN, "label": "Admin"},
    ]


@pytest.mark.django_db
def test_org_api_invite_creates_invitation_and_dispatches_notification(
    client,
    settings,
    monkeypatch,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Helios", slug="helios")
    admin_user = get_user_model().objects.create_user(
        username="helios-admin-api",
        email="helios-admin-api@example.com",
        password="secret123",
        first_name="Helios",
        last_name="Admin",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    captured_calls: list[dict[str, object]] = []

    def fake_sender(**kwargs: object) -> object:
        captured_calls.append(dict(kwargs))
        return SimpleNamespace()

    monkeypatch.setattr(
        org_views,
        "_load_invitation_notification_sender",
        lambda: fake_sender,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/api/orgs/{organization.slug}/members/invite/",
        data=json.dumps({"email": "Invitee@Example.com", "role": OrgRole.ADMIN}),
        content_type="application/json",
    )

    invitation = OrganizationInvitation.objects.get(organization=organization)
    assert response.status_code == 201
    assert response.json() == {
        "invitation": {
            "id": str(invitation.pk),
            "email": "invitee@example.com",
            "role": OrgRole.ADMIN,
            "role_label": "Admin",
            "expires_at": invitation.expires_at.astimezone(timezone.UTC).isoformat(),
        }
    }
    assert len(captured_calls) == 1
    assert captured_calls[0]["template_key"] == "notifications.org_invitation"
    assert captured_calls[0]["recipients"] == ["invitee@example.com"]


@pytest.mark.django_db
def test_org_api_member_role_update_returns_json(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Helios", slug="helios")
    owner = get_user_model().objects.create_user(
        username="helios-owner-api",
        email="helios-owner-api@example.com",
        password="secret123",
    )
    member = get_user_model().objects.create_user(
        username="helios-member-api",
        email="helios-member-api@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    member_membership = OrganizationMembership.objects.create(
        user=member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(owner)

    response = client.post(
        f"/api/orgs/{organization.slug}/members/{member_membership.pk}/role/",
        data=json.dumps({"role": OrgRole.ADMIN}),
        content_type="application/json",
    )

    member_membership.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["member"]["id"] == member_membership.pk
    assert response.json()["member"]["role"] == OrgRole.ADMIN
    assert member_membership.role == OrgRole.ADMIN


@pytest.mark.django_db
def test_org_api_member_remove_returns_json(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nova", slug="nova")
    admin_user = get_user_model().objects.create_user(
        username="nova-admin-api",
        email="nova-admin-api@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="nova-member-api",
        email="nova-member-api@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    membership = OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/api/orgs/{organization.slug}/members/{membership.pk}/remove/",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"status": "removed", "member_id": membership.pk}
    assert not OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("json_request", [False, True], ids=["html", "json"])
def test_member_removals_translate_delete_time_validation_errors(
    client,
    settings,
    monkeypatch,
    json_request,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Lyra", slug="lyra")
    acting_owner = get_user_model().objects.create_user(
        username=f"lyra-acting-{json_request}",
        email=f"lyra-acting-{json_request}@example.com",
        password="secret123",
    )
    target_owner = get_user_model().objects.create_user(
        username=f"lyra-target-{json_request}",
        email=f"lyra-target-{json_request}@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=acting_owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    target_membership = OrganizationMembership.objects.create(
        user=target_owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    def rejecting_delete(
        self: OrganizationMembership,
        *args: object,
        **kwargs: object,
    ) -> tuple[int, dict[str, int]]:
        del self, args, kwargs
        raise ValidationError(OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE)

    monkeypatch.setattr(OrganizationMembership, "delete", rejecting_delete)
    client.force_login(acting_owner)

    if json_request:
        response = client.post(
            f"/api/orgs/{organization.slug}/members/{target_membership.pk}/remove/",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "non_field_errors": [OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE]
            }
        }
    else:
        response = client.post(
            f"/orgs/{organization.slug}/members/",
            {
                "action": "remove",
                "membership_id": target_membership.pk,
            },
        )
        assert response.status_code == 400
        assert (
            OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE
            in response.content.decode()
        )

    assert OrganizationMembership.objects.filter(pk=target_membership.pk).exists()


@pytest.mark.django_db
def test_org_api_revoke_invitation_returns_json(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Summit", slug="summit")
    admin_user = get_user_model().objects.create_user(
        username="summit-admin-api",
        email="summit-admin-api@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.MEMBER,
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(admin_user)

    response = client.post(
        f"/api/orgs/{organization.slug}/members/invitations/{invitation.pk}/revoke/",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "revoked",
        "invitation_id": str(invitation.pk),
    }
    assert not OrganizationInvitation.objects.filter(pk=invitation.pk).exists()


@pytest.mark.django_db
def test_org_api_settings_updates_slug_and_returns_json(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Beacon", slug="beacon")
    admin_user = get_user_model().objects.create_user(
        username="beacon-admin-api",
        email="beacon-admin-api@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/api/orgs/{organization.slug}/settings/",
        data=json.dumps({"name": "Beacon Labs", "slug": "beacon-labs"}),
        content_type="application/json",
    )

    organization.refresh_from_db()
    assert response.status_code == 200
    assert response.json() == {
        "organization": {
            "id": str(organization.id),
            "name": "Beacon Labs",
            "slug": "beacon-labs",
            "is_personal": False,
        }
    }
    assert organization.name == "Beacon Labs"
    assert organization.slug == "beacon-labs"
