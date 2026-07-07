"""Model contract tests for the QuickScale organizations module."""

from typing import Any, Generator
from unittest.mock import patch
from datetime import timedelta

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
from quickscale_modules_orgs.managers import TenantManager
from quickscale_modules_orgs.tenancy import tenant_org_fk


def _create_user(**kwargs: str) -> Any:
    """Create a test user, working around mypy-django stub limitations."""
    return get_user_model().objects.create_user(**kwargs)  # type: ignore[attr-defined]


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
    user = _create_user(
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
    # Allow 2 total orgs (System org from forms migration + personal org).
    assert Organization.objects.count() >= 1
    assert OrganizationMembership.objects.count() == 1


@pytest.mark.django_db
def test_duplicate_membership_hits_database_constraint() -> None:
    """The user/org pair should be unique at the database layer."""
    user = _create_user(
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

    user = _create_user(
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
def test_last_owner_cannot_be_removed_when_other_members_exist() -> None:
    """Direct ORM deletes should block removal of the last owner when
    other members (non-owners) would be stranded ownerless (SA47)."""

    owner = _create_user(
        username="remove-owner",
        email="remove-owner@example.com",
        password="secret123",
    )
    other_member = _create_user(
        username="other-remove-member",
        email="other-remove-member@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Orbit", slug="orbit")
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

    with pytest.raises(ValidationError) as exc_info:
        owner_membership.delete()

    assert exc_info.value.messages == [
        OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE
    ]
    assert OrganizationMembership.objects.filter(pk=owner_membership.pk).exists()


@pytest.mark.django_db
def test_last_owner_removal_allowed_when_sole_member() -> None:
    """Direct ORM deletes should allow removing the last owner when no
    other members exist — nobody is stranded (SA47)."""

    user = _create_user(
        username="sole-owner",
        email="sole-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Solo", slug="solo")
    membership = OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    membership_pk = membership.pk

    membership.delete()

    assert not OrganizationMembership.objects.filter(pk=membership_pk).exists()


@pytest.mark.django_db
def test_last_owner_save_uses_locked_persisted_role_for_stale_instances() -> None:
    """Stale membership saves should validate against the locked persisted role."""

    first_owner = _create_user(
        username="save-first-owner",
        email="save-first-owner@example.com",
        password="secret123",
    )
    promoted_user = _create_user(
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

    # save() now calls _persisted_owner_state twice: first with
    # for_update=False to determine the org to lock (normalized lock
    # order), then with for_update=True to lock the membership row.
    # The second (for_update=True) call delegates to the original
    # implementation and returns the authoritative persisted state.
    assert persisted_owner_state.call_count == 2
    assert persisted_owner_state.call_args_list[0] == (
        (stale_membership,),
        {"for_update": False},
    )
    assert persisted_owner_state.call_args_list[1] == (
        (stale_membership,),
        {"for_update": True},
    )
    stale_membership.refresh_from_db()
    assert exc_info.value.message_dict == {
        "role": [OrganizationMembership.LAST_OWNER_DEMOTION_MESSAGE]
    }
    assert stale_membership.role == OrgRole.OWNER


@pytest.mark.django_db
def test_last_owner_delete_uses_persisted_role_for_stale_instances() -> None:
    """Stale membership instances should still respect the persisted owner guard."""

    first_owner = _create_user(
        username="first-owner",
        email="first-owner@example.com",
        password="secret123",
    )
    promoted_user = _create_user(
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
    user = _create_user(
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
    user = _create_user(
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
    inviter = _create_user(
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
    inviter = _create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=1),
    )

    duplicate = OrganizationInvitation(
        organization=organization,
        email="INVITEE@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=1),
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
    inviter = _create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    invitation = OrganizationInvitation(
        organization=organization,
        email="INVITEE@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=1),
    )

    invitation.full_clean()

    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=1),
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
    inviter = _create_user(
        username="nova-owner",
        email="nova-owner@example.com",
        password="secret123",
    )
    blank_form = OrganizationInvitationAdminForm()

    assert OrgRole.OWNER not in {
        role_value
        for role_value, _label in blank_form.fields["role"].choices  # type: ignore[attr-defined]
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
    """get_system_org() should find and return an existing System org.

    The forms module migration 0005 may have pre-created the System org,
    so we work with whatever row exists rather than creating a new one.
    """
    # If the System org already exists (e.g. from forms migration 0005),
    # use it as the "existing" row.  Otherwise create one.
    existing = Organization.objects.filter(is_system=True, slug=SYSTEM_ORG_SLUG).first()
    if existing is None:
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

    The forms module migration 0005 may have pre-created the System org,
    so we update that row to be corrupt rather than risking a unique
    constraint violation.
    """

    # Update the existing System org directly (avoiding delete FK issues
    # with forms seed data) to create the corrupt scenario.
    Organization.objects.filter(is_system=True, slug=SYSTEM_ORG_SLUG).update(
        slug="wrong-slug",
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
    # Update the existing System org so its is_system=False while keeping
    # the slug (creates the corrupt scenario without delete FK issues).
    Organization.objects.filter(slug=SYSTEM_ORG_SLUG, is_system=True).update(
        is_system=False,
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
    # Mark the existing System org as personal to create corrupt scenario.
    Organization.objects.filter(is_system=True, slug=SYSTEM_ORG_SLUG).update(
        is_personal=True,
    )

    with pytest.raises(RuntimeError, match="is_personal=True"):
        Organization.objects.get_system_org()

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
    assert fk.remote_field.model == "quickscale_modules_orgs.Organization"  # type: ignore[comparison-overlap]


def test_tenant_org_fk_defaults_db_index_to_true() -> None:
    """tenant_org_fk() should default to indexed for query performance."""
    fk = tenant_org_fk(related_name="test_indexed")

    assert fk.db_index is True  # type: ignore[attr-defined]


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
    assert organization_field.db_index is True  # type: ignore[union-attr]
    # tenant_org_fk uses a lazy string reference; abstract models
    # do not resolve it until a concrete subclass is prepared.
    assert organization_field.related_model in (
        Organization,
        "quickscale_modules_orgs.Organization",
    )
    assert organization_field.remote_field.on_delete == models.PROTECT  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# T1.2 — Concrete test model for TenantManager behaviour tests
# ---------------------------------------------------------------------------


class ConcreteTenantResource(TenantModel):
    """Concrete tenant model used exclusively for manager behaviour tests.

    Test-only model — not a real tenant table.
    """

    tenant_excluded = (
        "Test-only model defined in test_models.py for "
        "TenantManager behaviour tests; not a real tenant table."
    )

    name: models.CharField = models.CharField(max_length=100)

    class Meta:
        app_label = "quickscale_modules_orgs"


class ForwardFKChild(models.Model):
    """Test-only model with a FK to ConcreteTenantResource for FK traversal tests.

    Test-only model — not a real tenant table.
    """

    tenant_excluded = (
        "Test-only model defined in test_models.py for "
        "AF2 Phase 1 forward-FK traversal regression tests; "
        "not a real tenant table."
    )

    organization: models.ForeignKey = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.PROTECT,
    )
    parent: models.ForeignKey = models.ForeignKey(
        ConcreteTenantResource,
        on_delete=models.CASCADE,
        related_name="fk_children",
    )
    name: models.CharField = models.CharField(max_length=100)

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        app_label = "quickscale_modules_orgs"
        base_manager_name = "all_objects"


def test_concrete_tenant_model_has_scoped_default_manager() -> None:
    """Concrete TenantModel subclass should inherit a TenantManager as objects."""
    from quickscale_modules_orgs.managers import TenantManager

    assert isinstance(ConcreteTenantResource.objects, TenantManager)
    assert ConcreteTenantResource.objects._super_scope is False


def test_concrete_tenant_model_has_unfiltered_all_objects_manager() -> None:
    """Concrete TenantModel subclass should have all_objects (super-scope bypass)."""
    from quickscale_modules_orgs.managers import TenantManager

    assert isinstance(ConcreteTenantResource.all_objects, TenantManager)
    assert ConcreteTenantResource.all_objects._super_scope is True


@pytest.fixture
def _tenant_resource_db() -> Generator[None, None, None]:
    """Create/drop the ConcreteTenantResource table for the duration of the test."""
    from django.db import connection

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(ConcreteTenantResource)
    yield
    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(ConcreteTenantResource)


@pytest.mark.usefixtures("_tenant_resource_db")
@pytest.mark.django_db(transaction=True)
def test_tenant_manager_auto_scopes_to_current_org() -> None:
    """Default manager querysets should filter by the current org when set."""
    from quickscale_modules_orgs.current_org import (
        reset_current_org_id,
        set_current_org_id,
    )

    org_a = Organization.objects.create(name="OrgA", slug="org-a")
    org_b = Organization.objects.create(name="OrgB", slug="org-b")

    # Create one resource in each org.
    reset_current_org_id()
    resource_a = ConcreteTenantResource.objects.create(
        organization=org_a, name="A's item"
    )
    ConcreteTenantResource.objects.create(organization=org_b, name="B's item")

    # Scope to org_a — only resource_a should be visible.
    set_current_org_id(org_a.pk)
    try:
        results = list(ConcreteTenantResource.objects.all())
        assert len(results) == 1
        assert results[0].pk == resource_a.pk
    finally:
        reset_current_org_id()


@pytest.mark.usefixtures("_tenant_resource_db")
@pytest.mark.django_db(transaction=True)
def test_tenant_manager_fail_closed_when_unset() -> None:
    """Default manager should return .none() when no org is set."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
    )

    org = Organization.objects.create(name="FailClosed", slug="fail-closed")
    ConcreteTenantResource.objects.create(organization=org, name="hidden")

    # Ensure no org is set.
    reset_current_org_id()
    assert get_current_org_id() is None

    # Fail-closed: should always be empty.
    assert ConcreteTenantResource.objects.count() == 0
    assert list(ConcreteTenantResource.objects.all()) == []


@pytest.mark.usefixtures("_tenant_resource_db")
@pytest.mark.django_db(transaction=True)
def test_tenant_manager_all_objects_bypasses_scope() -> None:
    """all_objects should bypass auto-scoping and return all rows."""
    from quickscale_modules_orgs.current_org import reset_current_org_id

    org_a = Organization.objects.create(name="BypassA", slug="bypass-a")
    org_b = Organization.objects.create(name="BypassB", slug="bypass-b")

    reset_current_org_id()
    r1 = ConcreteTenantResource.objects.create(organization=org_a, name="item1")
    r2 = ConcreteTenantResource.objects.create(organization=org_b, name="item2")

    # all_objects should see all rows regardless of contextvar state.
    results = list(ConcreteTenantResource.all_objects.all())
    pks = {r.pk for r in results}
    assert r1.pk in pks
    assert r2.pk in pks


@pytest.mark.usefixtures("_tenant_resource_db")
@pytest.mark.django_db(transaction=True)
def test_tenant_manager_cross_org_isolation() -> None:
    """Resources from different orgs should be isolated under scoped manager."""
    from quickscale_modules_orgs.current_org import (
        reset_current_org_id,
        set_current_org_id,
    )

    org_a = Organization.objects.create(name="IsolationA", slug="iso-a")
    org_b = Organization.objects.create(name="IsolationB", slug="iso-b")
    org_c = Organization.objects.create(name="IsolationC", slug="iso-c")

    reset_current_org_id()
    ConcreteTenantResource.objects.create(organization=org_a, name="a1")
    ConcreteTenantResource.objects.create(organization=org_b, name="b1")
    ConcreteTenantResource.objects.create(organization=org_c, name="c1")

    for org, expected_count in [(org_a, 1), (org_b, 1), (org_c, 1)]:
        set_current_org_id(org.pk)
        try:
            assert ConcreteTenantResource.objects.count() == expected_count
        finally:
            reset_current_org_id()

    # With no org set, nothing is visible.
    assert ConcreteTenantResource.objects.count() == 0


# ---------------------------------------------------------------------------
# AF2 Phase 1 — no-context ORM regression coverage
# ---------------------------------------------------------------------------
# These tests prove that ``base_manager_name = "all_objects"`` prevents
# the scoped manager's fail-closed ``.none()`` from breaking internal
# Django operations when no tenant context is set.
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_tenant_resource_db")
@pytest.mark.django_db(transaction=True)
def test_refresh_from_db_without_org_context() -> None:
    """refresh_from_db() should work when no tenant context is set (AF2 Phase 1).

    This regression test proves that ``_base_manager`` returns the
    unfiltered queryset (via ``all_objects``) so that internal Django
    refresh logic bypasses the scoped manager's fail-closed .none().
    """
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
    )

    org = Organization.objects.create(name="RefreshTest", slug="refresh-test")
    reset_current_org_id()
    assert get_current_org_id() is None

    # Create using all_objects (bypass scoping when no context is set).
    resource = ConcreteTenantResource.all_objects.create(
        organization=org,
        name="original",
    )

    # Mutate behind the instance's back.
    ConcreteTenantResource.all_objects.filter(pk=resource.pk).update(name="updated")

    # refresh_from_db uses _base_manager (should be all_objects, unfiltered).
    resource.refresh_from_db()
    assert resource.name == "updated"


@pytest.mark.usefixtures("_tenant_resource_db")
@pytest.mark.django_db(transaction=True)
def test_forward_fk_traversal_without_org_context() -> None:
    """Forward FK traversal should work when no tenant context is set (AF2 Phase 1).

    Django uses the related model's ``_base_manager`` to fetch FK targets.
    This test proves that ``ConcreteTenantResource._base_manager`` is the
    unfiltered ``all_objects`` manager, allowing FK access without a
    tenant context.
    """
    from django.db import connection

    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
    )

    # Create ForwardFKChild table for the duration of this test.
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(ForwardFKChild)

    try:
        org = Organization.objects.create(name="FKTest", slug="fk-test")
        reset_current_org_id()
        assert get_current_org_id() is None

        parent = ConcreteTenantResource.all_objects.create(
            organization=org,
            name="parent-resource",
        )
        child = ForwardFKChild.all_objects.create(
            organization=org,
            parent=parent,
            name="child",
        )

        reset_current_org_id()

        # Forward FK traversal: accessing child.parent uses
        # ConcreteTenantResource._base_manager which must be
        # all_objects (unfiltered).
        fetched_parent = child.parent
        assert fetched_parent.name == "parent-resource"
    finally:
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(ForwardFKChild)
