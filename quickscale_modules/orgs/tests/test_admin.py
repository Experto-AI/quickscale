"""Admin contract tests for the QuickScale organizations module."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from quickscale_modules_orgs.admin import (
    OrganizationAdmin,
    OrganizationInvitationAdmin,
    OrganizationInvitationAdminForm,
    OrganizationMembershipAdmin,
)
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


def test_organization_models_are_registered_in_admin() -> None:
    """The org models should be registered on the default admin site."""
    assert isinstance(admin.site._registry[Organization], OrganizationAdmin)
    assert isinstance(
        admin.site._registry[OrganizationMembership],
        OrganizationMembershipAdmin,
    )
    assert isinstance(
        admin.site._registry[OrganizationInvitation],
        OrganizationInvitationAdmin,
    )


def test_admin_columns_and_filters_match_phase_one_contract() -> None:
    """Admin list displays and filters should match the roadmap contract."""
    organization_admin = admin.site._registry[Organization]
    membership_admin = admin.site._registry[OrganizationMembership]
    invitation_admin = admin.site._registry[OrganizationInvitation]

    assert organization_admin.list_display == [
        "name",
        "slug",
        "is_personal",
        "created_at",
    ]
    assert organization_admin.list_filter == ["is_personal"]

    assert membership_admin.list_display == [
        "user",
        "organization",
        "role",
        "joined_at",
    ]
    assert membership_admin.list_filter == ["role", "organization"]

    assert invitation_admin.list_display == [
        "email",
        "organization",
        "role",
        "expires_at",
        "accepted_at",
    ]
    assert invitation_admin.list_filter == ["organization"]


@pytest.mark.django_db
def test_invitation_admin_form_rejects_duplicate_active_email() -> None:
    """The admin form should surface shared duplicate active invite validation."""

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

    form = OrganizationInvitationAdminForm(
        data={
            "organization": str(organization.pk),
            "email": "INVITEE@example.com",
            "role": OrgRole.MEMBER,
            "invited_by": str(inviter.pk),
            "expires_at": (timezone.now() + timezone.timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
    )

    assert not form.is_valid()
    assert form.errors["email"] == [
        OrganizationInvitation.DUPLICATE_ACTIVE_INVITATION_MESSAGE
    ]


@pytest.mark.django_db
def test_invitation_admin_form_save_revalidates_after_is_valid() -> None:
    """Admin saves should reject duplicates created after the form was validated."""

    organization = Organization.objects.create(name="Atlas", slug="atlas")
    inviter = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    form = OrganizationInvitationAdminForm(
        data={
            "organization": str(organization.pk),
            "email": "INVITEE@example.com",
            "role": OrgRole.MEMBER,
            "invited_by": str(inviter.pk),
            "expires_at": (timezone.now() + timezone.timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
    )

    assert form.is_valid(), form.errors

    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    with pytest.raises(ValidationError) as exc_info:
        form.save()

    assert exc_info.value.message_dict == {
        "email": [OrganizationInvitation.DUPLICATE_ACTIVE_INVITATION_MESSAGE]
    }
    assert OrganizationInvitation.objects.count() == 1
