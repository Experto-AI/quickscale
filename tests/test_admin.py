"""Admin contract tests for the QuickScale organizations module."""

from django.contrib import admin

from quickscale_modules_orgs.admin import (
    OrganizationAdmin,
    OrganizationInvitationAdmin,
    OrganizationMembershipAdmin,
)
from quickscale_modules_orgs.models import (
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
