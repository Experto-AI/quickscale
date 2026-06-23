"""Model contract tests for the QuickScale organizations module."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from quickscale_modules_orgs.admin import OrganizationInvitationAdminForm
from quickscale_modules_orgs.constants import SYSTEM_ORG_NAME, SYSTEM_ORG_SLUG
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    TenantModel,
)
from quickscale_modules_orgs.tenancy import tenant_org_fk


def test_org_role_preserves_expected_hierarchy_order() -> None:
    """OrgRole should keep the documented low-to-high privilege ordering."""

    assert [role.value for role in OrgRole] == [
        OrgRole.VIEWER,
        OrgRole.MEMBER,
        OrgRole.ADMIN,
        OrgRole.OWNER,
    ]


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
def test_last_owner_cannot_be_demoted_via_model_save() -> None:
    """Direct ORM role changes should not allow an org to lose its last owner."""

    user = get_user_model().objects.create_user(
        username="owner",
        email="owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")
    membership = OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )

    membership.role = OrgRole.ADMIN

    with pytest.raises(ValidationError) as exc_info:
        membership.save(update_fields=["role"])

    membership.refresh_from_db()
    assert exc_info.value.message_dict == {
        "role": [OrganizationMembership.LAST_OWNER_DEMOTION_MESSAGE]
    }
    assert membership.role == OrgRole.OWNER


@pytest.mark.django_db
def test_last_owner_cannot_be_removed_via_model_delete() -> None:
    """Direct ORM deletes should not remove an organization's final owner."""

    user = get_user_model().objects.create_user(
        username="remove-owner",
        email="remove-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Orbit", slug="orbit")
    membership = OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )

    with pytest.raises(ValidationError) as exc_info:
        membership.delete()

    assert exc_info.value.messages == [
        OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE
    ]
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_last_owner_save_uses_locked_persisted_role_for_stale_instances() -> None:
    """Stale membership saves should validate against the locked persisted role."""

    first_owner = get_user_model().objects.create_user(
        username="save-first-owner",
        email="save-first-owner@example.com",
        password="secret123",
    )
    promoted_user = get_user_model().objects.create_user(
        username="save-promoted-owner",
        email="save-promoted-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Apex", slug="apex")
    existing_owner_membership = OrganizationMembership.objects.create(
        user=first_owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    promoted_membership = OrganizationMembership.objects.create(
        user=promoted_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    stale_membership = OrganizationMembership.objects.get(pk=promoted_membership.pk)

    OrganizationMembership.objects.filter(pk=promoted_membership.pk).update(
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.filter(pk=existing_owner_membership.pk).update(
        role=OrgRole.ADMIN,
    )

    stale_membership.role = OrgRole.ADMIN
    original_persisted_owner_state = OrganizationMembership._persisted_owner_state

    def simulated_racy_persisted_owner_state(
        self: OrganizationMembership,
        *,
        for_update: bool = False,
    ) -> tuple[object | None, str | None]:
        if not for_update:
            return organization.pk, OrgRole.MEMBER
        return original_persisted_owner_state(self, for_update=True)

    with patch.object(
        OrganizationMembership,
        "_persisted_owner_state",
        autospec=True,
        side_effect=simulated_racy_persisted_owner_state,
    ) as persisted_owner_state:
        with pytest.raises(ValidationError) as exc_info:
            stale_membership.save(update_fields=["role"])

    persisted_owner_state.assert_called_once_with(stale_membership, for_update=True)
    stale_membership.refresh_from_db()
    assert exc_info.value.message_dict == {
        "role": [OrganizationMembership.LAST_OWNER_DEMOTION_MESSAGE]
    }
    assert stale_membership.role == OrgRole.OWNER


@pytest.mark.django_db
def test_last_owner_delete_uses_persisted_role_for_stale_instances() -> None:
    """Stale membership instances should still respect the persisted owner guard."""

    first_owner = get_user_model().objects.create_user(
        username="first-owner",
        email="first-owner@example.com",
        password="secret123",
    )
    promoted_user = get_user_model().objects.create_user(
        username="promoted-owner",
        email="promoted-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Vertex", slug="vertex")
    existing_owner_membership = OrganizationMembership.objects.create(
        user=first_owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    promoted_membership = OrganizationMembership.objects.create(
        user=promoted_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    stale_membership = OrganizationMembership.objects.get(pk=promoted_membership.pk)

    OrganizationMembership.objects.filter(pk=promoted_membership.pk).update(
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.filter(pk=existing_owner_membership.pk).update(
        role=OrgRole.ADMIN,
    )

    with pytest.raises(ValidationError) as exc_info:
        stale_membership.delete()

    assert exc_info.value.messages == [
        OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE
    ]
    assert OrganizationMembership.objects.filter(pk=promoted_membership.pk).exists()


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


# ---------------------------------------------------------------------------
# T1.1 — System org + NOT NULL ownership contract
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_system_org_creates_singleton_on_first_call() -> None:
    """get_system_org() should create the System org on first invocation."""
    org = Organization.objects.get_system_org()

    assert org.is_system is True
    assert org.is_personal is False
    assert org.slug == SYSTEM_ORG_SLUG
    assert org.name == SYSTEM_ORG_NAME


@pytest.mark.django_db
def test_get_system_org_is_idempotent() -> None:
    """get_system_org() should return the same instance on repeated calls."""
    org1 = Organization.objects.get_system_org()
    org2 = Organization.objects.get_system_org()

    assert org2.pk == org1.pk
    assert org2.is_system is True
    assert Organization.objects.count() == 1


@pytest.mark.django_db
def test_get_system_org_returns_existing_row_when_already_present() -> None:
    """get_system_org() should find and return an existing System org."""
    existing = Organization.objects.create(
        name=SYSTEM_ORG_NAME,
        slug=SYSTEM_ORG_SLUG,
        is_system=True,
    )
    found = Organization.objects.get_system_org()

    assert found.pk == existing.pk
    assert found.is_system is True


@pytest.mark.django_db
def test_second_is_system_row_with_wrong_slug_rejected_by_validation() -> None:
    """Model validation should reject a second is_system=True row with a non-reserved slug."""
    Organization.objects.get_system_org()

    with pytest.raises(ValidationError) as exc_info:
        Organization.objects.create(
            name="Duplicate System",
            slug="duplicate-system",
            is_system=True,
        )

    assert "must use the reserved slug" in str(exc_info.value)


@pytest.mark.django_db
def test_second_is_system_row_with_reserved_slug_rejected_by_db_constraint() -> None:
    """The DB partial unique constraint should reject a second is_system=True row
    even when the slug is correct (backstop for raw-SQL bypass)."""
    Organization.objects.get_system_org()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Organization.objects.create(
                name="Duplicate System",
                slug=SYSTEM_ORG_SLUG,
                is_system=True,
            )


@pytest.mark.django_db
def test_is_system_field_defaults_to_false() -> None:
    """New organizations should have is_system=False by default."""
    org = Organization.objects.create(name="Normal", slug="normal")

    assert org.is_system is False


@pytest.mark.django_db
def test_system_slug_reserved_rejects_non_system_org() -> None:
    """Using slug=__system__ with is_system=False should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Organization.objects.create(
            name="Impersonator",
            slug=SYSTEM_ORG_SLUG,
            is_system=False,
        )

    assert SYSTEM_ORG_SLUG in str(exc_info.value)


@pytest.mark.django_db
def test_system_slug_reserved_rejects_is_system_none() -> None:
    """Using slug=__system__ with is_system=None should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Organization.objects.create(
            name="Impersonator",
            slug=SYSTEM_ORG_SLUG,
            is_system=None,
        )

    assert "must not be null" in str(exc_info.value)


@pytest.mark.django_db
def test_system_org_rejects_is_personal_true() -> None:
    """Creating an org with is_system=True and is_personal=True should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Organization.objects.create(
            name="Bad System",
            slug="__system__",
            is_system=True,
            is_personal=True,
        )

    assert "must not be a personal organization" in str(exc_info.value)


@pytest.mark.django_db
def test_get_system_org_raises_on_wrong_slug_system_row() -> None:
    """get_system_org() should raise RuntimeError when a corrupt row with
    is_system=True but the wrong slug blocks the singleton.

    Uses bulk_create to bypass model validation, simulating a corrupt row
    that predates the invariant enforcement (e.g. from an older schema or
    raw SQL bypass).
    """
    Organization.objects.bulk_create(
        [
            Organization(
                name="Wrong Slug",
                slug="wrong-slug",
                is_system=True,
            ),
        ]
    )

    with pytest.raises(RuntimeError, match="Corrupt System org"):
        Organization.objects.get_system_org()


@pytest.mark.django_db
def test_get_system_org_raises_on_reserved_slug_non_system() -> None:
    """get_system_org() should raise RuntimeError when a corrupt row with
    slug=__system__ but is_system=False blocks creation.

    Uses bulk_create to bypass model validation, simulating a corrupt row
    that predates the invariant enforcement (e.g. from an older schema or
    raw SQL bypass).
    """
    Organization.objects.bulk_create(
        [
            Organization(
                name="Impersonator",
                slug=SYSTEM_ORG_SLUG,
                is_system=False,
            ),
        ]
    )

    with pytest.raises(RuntimeError, match="is_system=False"):
        Organization.objects.get_system_org()


@pytest.mark.django_db
def test_get_system_org_raises_on_personal_system_org() -> None:
    """get_system_org() should raise RuntimeError when a corrupt row with
    slug=__system__, is_system=True, and is_personal=True is returned by
    the fast path.

    Uses bulk_create to bypass model validation, simulating a corrupt row
    that predates the invariant enforcement (e.g. from an older schema or
    raw SQL bypass).
    """
    Organization.objects.bulk_create(
        [
            Organization(
                name="Personal System",
                slug=SYSTEM_ORG_SLUG,
                is_system=True,
                is_personal=True,
            ),
        ]
    )

    with pytest.raises(RuntimeError, match="is_personal=True"):
        Organization.objects.get_system_org()


@pytest.mark.django_db
def test_is_system_none_rejected_by_model_validation() -> None:
    """Persisting an organization with is_system=None should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Organization.objects.create(
            name="Null Is System",
            slug="null-is-system",
            is_system=None,
        )

    assert "must not be null" in str(exc_info.value)


def test_tenant_org_fk_produces_protect_contract() -> None:
    """tenant_org_fk() should return a NOT NULL FK with on_delete=PROTECT."""
    fk = tenant_org_fk(related_name="test_related")

    assert isinstance(fk, models.ForeignKey)
    assert fk.remote_field.on_delete == models.PROTECT
    assert fk.null is False
    # The FK is not yet contributed to a concrete model, so remote_field.model
    # is stored as the lazy string reference.
    assert fk.remote_field.model == "quickscale_modules_orgs.Organization"


def test_tenant_org_fk_defaults_db_index_to_true() -> None:
    """tenant_org_fk() should default to indexed for query performance."""
    fk = tenant_org_fk(related_name="test_indexed")

    assert fk.db_index is True


def test_tenant_org_fk_supports_custom_related_name() -> None:
    """tenant_org_fk() should propagate the supplied related_name."""
    fk = tenant_org_fk(related_name="custom_workspace")

    assert fk.remote_field.related_name == "custom_workspace"


# ---------------------------------------------------------------------------
# Existing — TenantModel contract
# ---------------------------------------------------------------------------


def test_tenant_model_declares_org_foreign_key() -> None:
    """TenantModel should expose the org foreign key expected by later phases."""
    organization_field = TenantModel._meta.get_field("organization")

    assert TenantModel._meta.abstract is True
    assert organization_field.db_index is True
    assert organization_field.related_model is Organization
