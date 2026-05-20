"""Model contract tests for the QuickScale organizations module."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from quickscale_modules_orgs.admin import OrganizationInvitationAdminForm
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    TenantModel,
)


@pytest.mark.django_db
def test_create_personal_for_is_idempotent() -> None:
    """create_personal_for should return the same personal org on repeat calls."""
    user = get_user_model().objects.create_user(
        username="alice",
        email="alice@example.com",
        password="secret123",
    )

    organization = Organization.objects.create_personal_for(user)
    repeated = Organization.objects.create_personal_for(user)
    membership = OrganizationMembership.objects.get(
        user=user, organization=organization
    )

    assert repeated == organization
    assert organization.is_personal is True
    assert organization.slug == "alice"
    assert membership.role == OrgRole.OWNER
    assert Organization.objects.count() == 1
    assert OrganizationMembership.objects.count() == 1


@pytest.mark.django_db
def test_duplicate_membership_hits_database_constraint() -> None:
    """The user/org pair should be unique at the database layer."""
    user = get_user_model().objects.create_user(
        username="bob",
        email="bob@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrgRole.MEMBER,
            )


@pytest.mark.django_db
def test_create_personal_for_retries_when_username_slug_is_taken() -> None:
    """Personal org creation should fall back when the username slug already exists."""
    user = get_user_model().objects.create_user(
        username="acme",
        email="acme@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Acme", slug="acme")

    organization = Organization.objects.create_personal_for(user)

    assert organization.slug == "acmeexamplecom"
    assert organization.is_personal is True


@pytest.mark.django_db
def test_create_personal_for_uses_suffixed_slug_after_multiple_collisions() -> None:
    """Personal org creation should keep trying deterministic suffixes after base collisions."""
    user = get_user_model().objects.create_user(
        username="omega",
        email="omega@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Omega", slug="omega")
    Organization.objects.create(name="Omega Email", slug="omegaexamplecom")
    Organization.objects.create(name="Omega User", slug=f"user-{user.pk}")

    organization = Organization.objects.create_personal_for(user)

    assert organization.slug == "omega-2"
    assert organization.is_personal is True


@pytest.mark.django_db
def test_organization_invitation_save_rejects_owner_role() -> None:
    """Direct invitation saves should fail closed for unsupported owner role."""

    organization = Organization.objects.create(name="Atlas", slug="atlas")
    inviter = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    invitation = OrganizationInvitation(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.OWNER,
        invited_by=inviter,
        expires_at=timezone.now(),
    )

    with pytest.raises(ValidationError) as exc_info:
        invitation.save()

    assert exc_info.value.message_dict == {
        "role": [OrganizationInvitation.INVALID_OWNER_ROLE_MESSAGE]
    }
    assert OrganizationInvitation.objects.count() == 0


@pytest.mark.django_db
def test_organization_invitation_save_rejects_duplicate_active_email() -> None:
    """Direct invitation saves should reject a second live invite by normalized email."""

    organization = Organization.objects.create(name="Atlas", slug="atlas")
    inviter = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    duplicate = OrganizationInvitation(
        organization=organization,
        email="INVITEE@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    with pytest.raises(ValidationError) as exc_info:
        duplicate.save()

    assert exc_info.value.message_dict == {
        "email": [OrganizationInvitation.DUPLICATE_ACTIVE_INVITATION_MESSAGE]
    }
    assert OrganizationInvitation.objects.count() == 1


@pytest.mark.django_db
def test_organization_invitation_save_revalidates_after_prior_clean() -> None:
    """Direct saves should relock and revalidate if the world changed after clean."""

    organization = Organization.objects.create(name="Atlas", slug="atlas")
    inviter = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    invitation = OrganizationInvitation(
        organization=organization,
        email="INVITEE@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    invitation.full_clean()

    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    with patch.object(
        Organization.objects,
        "select_for_update",
        wraps=Organization.objects.select_for_update,
    ) as select_for_update:
        with pytest.raises(ValidationError) as exc_info:
            invitation.save()

    assert exc_info.value.message_dict == {
        "email": [OrganizationInvitation.DUPLICATE_ACTIVE_INVITATION_MESSAGE]
    }
    select_for_update.assert_called_once_with()
    assert OrganizationInvitation.objects.count() == 1


@pytest.mark.django_db
def test_organization_invitation_admin_form_excludes_owner_role() -> None:
    """The admin form should not offer owner as a valid invitation role."""

    organization = Organization.objects.create(name="Nova", slug="nova")
    inviter = get_user_model().objects.create_user(
        username="nova-owner",
        email="nova-owner@example.com",
        password="secret123",
    )
    blank_form = OrganizationInvitationAdminForm()

    assert OrgRole.OWNER not in {
        role_value for role_value, _label in blank_form.fields["role"].choices
    }

    form = OrganizationInvitationAdminForm(
        data={
            "organization": str(organization.pk),
            "email": "invitee@example.com",
            "role": OrgRole.OWNER,
            "invited_by": str(inviter.pk),
            "expires_at": (timezone.now()).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    assert not form.is_valid()
    assert "valid choice" in form.errors["role"][0]


def test_tenant_model_declares_org_foreign_key() -> None:
    """TenantModel should expose the org foreign key expected by later phases."""
    organization_field = TenantModel._meta.get_field("organization")

    assert TenantModel._meta.abstract is True
    assert organization_field.db_index is True
    assert organization_field.related_model is Organization
