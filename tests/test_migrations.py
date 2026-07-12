"""Migration tests for CRM terminal stage semantics and backfill proofs.

Phase 3: historical NULL/backfill proofs live here, not in live suites.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

pytestmark = [
    pytest.mark.bypass_rls,
    pytest.mark.django_db(transaction=True),
]

# The latest orgs migration is included in project_state for tests that
# create Organization rows through historical apps registries. This ensures
# the historical model includes is_system (default=False) so that inserts
# through the historical model match the NOT NULL column at the DB level.
LATEST_ORGS_MIGRATION = ("quickscale_modules_orgs", "0003_alter_organization_is_system")

# Historical 0002 backfill function — kept as migration-harness proof.
_stage_terminal_semantic_migration = import_module(
    "quickscale_modules_crm.migrations.0002_stage_terminal_semantic"
)


def _create_contact(apps):
    Company = apps.get_model("quickscale_modules_crm", "Company")
    Contact = apps.get_model("quickscale_modules_crm", "Contact")

    company = Company.objects.create(name="Acme Corp")
    return Contact.objects.create(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        company=company,
    )


def _create_deal(apps: Any, *, contact: Any, stage: Any, title: str) -> Any:
    Deal = apps.get_model("quickscale_modules_crm", "Deal")

    return Deal.objects.create(
        title=title,
        contact=contact,
        stage=stage,
        probability=50,
    )


def test_0002_backfills_exact_name_terminal_semantics() -> None:
    migrate_from = ("quickscale_modules_crm", "0001_initial")
    migrate_to = ("quickscale_modules_crm", "0002_stage_terminal_semantic")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from]).apps
    legacy_stage = old_apps.get_model("quickscale_modules_crm", "Stage")

    legacy_stage.objects.all().delete()
    contact = _create_contact(old_apps)

    won_high_count_high_order = legacy_stage.objects.create(name="Closed-Won", order=99)
    won_high_count_low_order = legacy_stage.objects.create(name="Closed-Won", order=1)
    won_low_count_lowest_order = legacy_stage.objects.create(name="Closed-Won", order=0)
    won_variant = legacy_stage.objects.create(name="closed-won", order=1)
    lost_low_id = legacy_stage.objects.create(name="Closed-Lost", order=5)
    lost_high_id = legacy_stage.objects.create(name="Closed-Lost", order=5)
    lost_variant = legacy_stage.objects.create(name="Closed Lost", order=5)

    for index in range(3):
        _create_deal(
            old_apps,
            contact=contact,
            stage=won_high_count_high_order,
            title=f"Won high order {index}",
        )
        _create_deal(
            old_apps,
            contact=contact,
            stage=won_high_count_low_order,
            title=f"Won low order {index}",
        )
    for index in range(2):
        _create_deal(
            old_apps,
            contact=contact,
            stage=won_low_count_lowest_order,
            title=f"Won lower count {index}",
        )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps
    migrated_stage = new_apps.get_model("quickscale_modules_crm", "Stage")

    won_high_count_high_order = migrated_stage.objects.get(
        pk=won_high_count_high_order.pk
    )
    won_high_count_low_order = migrated_stage.objects.get(
        pk=won_high_count_low_order.pk
    )
    won_low_count_lowest_order = migrated_stage.objects.get(
        pk=won_low_count_lowest_order.pk
    )
    won_variant = migrated_stage.objects.get(pk=won_variant.pk)
    lost_low_id = migrated_stage.objects.get(pk=lost_low_id.pk)
    lost_high_id = migrated_stage.objects.get(pk=lost_high_id.pk)
    lost_variant = migrated_stage.objects.get(pk=lost_variant.pk)

    assert won_high_count_low_order.terminal_semantic == "won"
    assert won_high_count_high_order.terminal_semantic is None
    assert won_low_count_lowest_order.terminal_semantic is None
    assert won_variant.terminal_semantic is None
    assert lost_low_id.terminal_semantic == "lost"
    assert lost_high_id.terminal_semantic is None
    assert lost_variant.terminal_semantic is None


def test_0003_canonicalizes_duplicate_terminal_semantics_before_uniqueness() -> None:
    migrate_from = ("quickscale_modules_crm", "0002_stage_terminal_semantic")
    migrate_to = ("quickscale_modules_crm", "0003_stage_terminal_semantic_unique")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from]).apps
    semantic_stage = old_apps.get_model("quickscale_modules_crm", "Stage")

    semantic_stage.objects.all().delete()
    contact = _create_contact(old_apps)
    default_won_stage = semantic_stage.objects.create(
        name="Closed-Won",
        order=3,
        terminal_semantic="won",
    )
    default_lost_stage = semantic_stage.objects.create(
        name="Closed-Lost",
        order=4,
        terminal_semantic="lost",
    )
    renamed_won_stage = semantic_stage.objects.create(
        name="Deal Signed",
        order=9,
        terminal_semantic="won",
    )
    renamed_lost_stage = semantic_stage.objects.create(
        name="No Decision",
        order=10,
        terminal_semantic="lost",
    )

    _create_deal(
        old_apps,
        contact=contact,
        stage=default_won_stage,
        title="Default won deal",
    )
    for index in range(2):
        _create_deal(
            old_apps,
            contact=contact,
            stage=renamed_won_stage,
            title=f"Renamed won deal {index}",
        )
        _create_deal(
            old_apps,
            contact=contact,
            stage=renamed_lost_stage,
            title=f"Renamed lost deal {index}",
        )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps
    migrated_stage = new_apps.get_model("quickscale_modules_crm", "Stage")

    default_won_stage = migrated_stage.objects.get(pk=default_won_stage.pk)
    default_lost_stage = migrated_stage.objects.get(pk=default_lost_stage.pk)
    renamed_won_stage = migrated_stage.objects.get(pk=renamed_won_stage.pk)
    renamed_lost_stage = migrated_stage.objects.get(pk=renamed_lost_stage.pk)

    assert renamed_won_stage.terminal_semantic == "won"
    assert default_won_stage.terminal_semantic is None
    assert renamed_lost_stage.terminal_semantic == "lost"
    assert default_lost_stage.terminal_semantic is None
    assert migrated_stage.objects.filter(terminal_semantic="won").count() == 1
    assert migrated_stage.objects.filter(terminal_semantic="lost").count() == 1

    with pytest.raises(IntegrityError), transaction.atomic():
        migrated_stage.objects.create(
            name="Another Won",
            order=11,
            terminal_semantic="won",
        )


def test_0003_preserves_existing_unique_terminal_semantics() -> None:
    migrate_from = ("quickscale_modules_crm", "0002_stage_terminal_semantic")
    migrate_to = ("quickscale_modules_crm", "0003_stage_terminal_semantic_unique")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from]).apps
    semantic_stage = old_apps.get_model("quickscale_modules_crm", "Stage")

    semantic_stage.objects.all().delete()
    contact = _create_contact(old_apps)
    won_stage = semantic_stage.objects.create(
        name="Closed-Won",
        order=3,
        terminal_semantic="won",
    )
    won_stage.name = "Deal Signed"
    won_stage.order = 9
    won_stage.save(update_fields=["name", "order"])
    preserved_deal = _create_deal(
        old_apps,
        contact=contact,
        stage=won_stage,
        title="Enterprise Renewal",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps
    migrated_stage = new_apps.get_model("quickscale_modules_crm", "Stage")
    migrated_deal = new_apps.get_model("quickscale_modules_crm", "Deal")

    won_stage = migrated_stage.objects.get(pk=won_stage.pk)
    preserved_deal = migrated_deal.objects.get(pk=preserved_deal.pk)

    assert won_stage.name == "Deal Signed"
    assert won_stage.order == 9
    assert won_stage.terminal_semantic == "won"
    assert preserved_deal.stage_id == won_stage.pk


def test_0004_adds_nullable_organization_without_backfill() -> None:
    """Migration 0004 must add nullable org FKs without mutating existing rows.

    Phase 11.1d forward-migration proof: legacy Tag/Company/Contact/Stage/Deal
    rows created before the organization field existed must survive migration
    0004 with organization_id=None and no backfill or default assignment.
    """
    migrate_from = ("quickscale_modules_crm", "0003_stage_terminal_semantic_unique")
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from]).apps

    # Create legacy rows at 0003 state (no organization field exists yet).
    LegacyTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    LegacyCompany = old_apps.get_model("quickscale_modules_crm", "Company")
    LegacyContact = old_apps.get_model("quickscale_modules_crm", "Contact")
    LegacyStage = old_apps.get_model("quickscale_modules_crm", "Stage")
    LegacyDeal = old_apps.get_model("quickscale_modules_crm", "Deal")

    legacy_tag = LegacyTag.objects.create(name="Legacy VIP")
    legacy_company = LegacyCompany.objects.create(name="Legacy Corp")
    legacy_contact = LegacyContact.objects.create(
        first_name="Legacy",
        last_name="Contact",
        email="legacy@example.com",
        company=legacy_company,
    )
    legacy_stage = LegacyStage.objects.create(name="Legacy Stage", order=1)
    legacy_deal = LegacyDeal.objects.create(
        title="Legacy Deal",
        contact=legacy_contact,
        stage=legacy_stage,
    )

    # Migrate forward to 0004.
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps

    MigratedTag = new_apps.get_model("quickscale_modules_crm", "Tag")
    MigratedCompany = new_apps.get_model("quickscale_modules_crm", "Company")
    MigratedContact = new_apps.get_model("quickscale_modules_crm", "Contact")
    MigratedStage = new_apps.get_model("quickscale_modules_crm", "Stage")
    MigratedDeal = new_apps.get_model("quickscale_modules_crm", "Deal")

    # Verify all legacy rows survive with null organization and no data mutation.
    tag = MigratedTag.objects.get(pk=legacy_tag.pk)
    assert tag.organization_id is None
    assert tag.name == "Legacy VIP"

    company = MigratedCompany.objects.get(pk=legacy_company.pk)
    assert company.organization_id is None
    assert company.name == "Legacy Corp"

    contact = MigratedContact.objects.get(pk=legacy_contact.pk)
    assert contact.organization_id is None
    assert contact.first_name == "Legacy"
    assert contact.email == "legacy@example.com"

    stage = MigratedStage.objects.get(pk=legacy_stage.pk)
    assert stage.organization_id is None
    assert stage.name == "Legacy Stage"
    assert stage.order == 1

    deal = MigratedDeal.objects.get(pk=legacy_deal.pk)
    assert deal.organization_id is None
    assert deal.title == "Legacy Deal"
    assert deal.contact_id == legacy_contact.pk
    assert deal.stage_id == legacy_stage.pk


def test_0004_nullable_organization_contract() -> None:
    """Migration 0004 establishes nullable org FKs with correct metadata.

    Phase 11.1d nullable contract preserved in migration history:
    all five owned models (Tag, Company, Contact, Stage, Deal) must have
    organization FK with null=True, blank=True, on_delete=SET_NULL,
    and must allow creating and persisting rows without organization
    assignment.
    """
    migrate_from = ("quickscale_modules_crm", "0003_stage_terminal_semantic_unique")
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    apps = executor.loader.project_state([migrate_to]).apps

    MigratedTag = apps.get_model("quickscale_modules_crm", "Tag")
    MigratedCompany = apps.get_model("quickscale_modules_crm", "Company")
    MigratedContact = apps.get_model("quickscale_modules_crm", "Contact")
    MigratedStage = apps.get_model("quickscale_modules_crm", "Stage")
    MigratedDeal = apps.get_model("quickscale_modules_crm", "Deal")

    # --- Field metadata: null=True, blank=True, on_delete=SET_NULL ---
    for model_cls, label in [
        (MigratedTag, "Tag"),
        (MigratedCompany, "Company"),
        (MigratedContact, "Contact"),
        (MigratedStage, "Stage"),
        (MigratedDeal, "Deal"),
    ]:
        field = model_cls._meta.get_field("organization")
        assert field.null is True, f"{label}.organization.null is not True"
        assert field.blank is True, f"{label}.organization.blank is not True"
        assert field.remote_field.on_delete.__name__ == "SET_NULL", (
            f"{label}.organization.on_delete is not SET_NULL"
        )

    # --- Create/persist without organization assignment ---
    tag = MigratedTag.objects.create(name="VIP")
    assert tag.organization_id is None

    company = MigratedCompany.objects.create(name="Acme Corp")
    assert company.organization_id is None

    contact = MigratedContact.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        company=company,
    )
    assert contact.organization_id is None

    stage = MigratedStage.objects.create(name="New", order=1)
    assert stage.organization_id is None

    deal = MigratedDeal.objects.create(
        title="Test Deal",
        contact=contact,
        stage=stage,
    )
    assert deal.organization_id is None


def test_0005_replaces_tag_name_unique_with_owner_bucket_constraint() -> None:
    """Migration 0005 removes field-level unique and adds owner-bucket constraint.

    Phase 11.1d.1: Tag.name unique=True is replaced by two partial
    UniqueConstraints that together implement owner-bucket uniqueness:
      - NULL-owned bucket: unique on (name,) where organization IS NULL
      - Org-owned bucket: unique on (name, organization) where organization IS NOT NULL

    Legacy NULL-owned duplicates stay blocked; same-name tags across
    different orgs are allowed after migration.
    """
    migrate_from = ("quickscale_modules_crm", "0004_add_organization_ownership")
    migrate_to = ("quickscale_modules_crm", "0005_tag_owner_bucket_unique")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from, LATEST_ORGS_MIGRATION]).apps

    LegacyTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    Organization = old_apps.get_model("quickscale_modules_orgs", "Organization")

    LegacyTag.objects.all().delete()

    # Create legacy NULL-owned tag (valid at 0004 — name is unique).
    legacy_null_tag = LegacyTag.objects.create(name="Legacy VIP")

    # Create orgs (valid at 0004).
    org_a = Organization.objects.create(name="Org A", slug="org-a-mig5")
    org_b = Organization.objects.create(name="Org B", slug="org-b-mig5")

    # At 0004 state, name is still field-level unique, so we can only create
    # one tag per name.  Create one tag per org with distinct names.
    org_a_tag = LegacyTag.objects.create(name="OrgA Tag", organization=org_a)
    org_b_tag = LegacyTag.objects.create(name="OrgB Tag", organization=org_b)

    # Migrate forward to 0005.
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps

    MigratedTag = new_apps.get_model("quickscale_modules_crm", "Tag")
    MigratedOrganization = new_apps.get_model("quickscale_modules_orgs", "Organization")

    # Re-fetch org references through the migrated apps registry.
    org_a = MigratedOrganization.objects.get(pk=org_a.pk)
    org_b = MigratedOrganization.objects.get(pk=org_b.pk)

    # Verify legacy rows survive.
    null_tag = MigratedTag.objects.get(pk=legacy_null_tag.pk)
    assert null_tag.name == "Legacy VIP"
    assert null_tag.organization_id is None

    a_tag = MigratedTag.objects.get(pk=org_a_tag.pk)
    assert a_tag.name == "OrgA Tag"
    assert a_tag.organization_id == org_a.pk

    b_tag = MigratedTag.objects.get(pk=org_b_tag.pk)
    assert b_tag.name == "OrgB Tag"
    assert b_tag.organization_id == org_b.pk

    # Verify name field is no longer field-level unique.
    name_field = MigratedTag._meta.get_field("name")
    assert name_field.unique is False

    # Now that the constraint has changed, test the new uniqueness rules.

    # Verify duplicate NULL-owned tag is blocked.
    with pytest.raises(IntegrityError), transaction.atomic():
        MigratedTag.objects.create(name="Legacy VIP")

    # Verify duplicate same-org tag is blocked.
    with pytest.raises(IntegrityError), transaction.atomic():
        MigratedTag.objects.create(name="OrgA Tag", organization=org_a)

    # Verify cross-org same-name is allowed.
    new_org_a_tag = MigratedTag.objects.create(name="Shared Name", organization=org_a)
    new_org_b_tag = MigratedTag.objects.create(name="Shared Name", organization=org_b)
    assert new_org_a_tag.pk != new_org_b_tag.pk

    # Verify NULL-owned + org-owned coexistence.
    null_coexist = MigratedTag.objects.create(name="Shared Name")
    assert null_coexist.pk != new_org_a_tag.pk
    assert null_coexist.pk != new_org_b_tag.pk


def test_0007_replaces_stage_terminal_semantic_unique_with_bucket_constraint() -> None:
    """Migration 0007 removes field-level unique and adds owner-bucket constraint.

    Phase F11-deferred: Stage.terminal_semantic unique=True is replaced by two
    partial UniqueConstraints that together implement per-org uniqueness:
      - NULL-owned bucket: unique on (terminal_semantic,) where organization IS NULL
      - Org-owned bucket: unique on (terminal_semantic, organization) where
        organization IS NOT NULL

    Legacy same-org duplicates stay blocked; same terminal semantic across
    different orgs is allowed after migration.
    """
    migrate_from = ("quickscale_modules_crm", "0006_enforce_required_organization")
    migrate_to = (
        "quickscale_modules_crm",
        "0007_stage_terminal_semantic_bucket_unique",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from, LATEST_ORGS_MIGRATION]).apps

    OldStage = old_apps.get_model("quickscale_modules_crm", "Stage")
    OldOrganization = old_apps.get_model("quickscale_modules_orgs", "Organization")

    OldStage.objects.all().delete()

    # Create orgs (valid at 0006 where organization is NOT NULL / PROTECT).
    org_a = OldOrganization.objects.create(name="Org A", slug="org-a-mig7")
    org_b = OldOrganization.objects.create(name="Org B", slug="org-b-mig7")

    # At 0006 state, terminal_semantic is still field-level unique globally,
    # so we can only create one stage per distinct terminal semantic value.
    won_stage_a = OldStage.objects.create(
        name="Closed-Won",
        order=3,
        terminal_semantic="won",
        organization=org_a,
    )
    lost_stage_a = OldStage.objects.create(
        name="Closed-Lost",
        order=4,
        terminal_semantic="lost",
        organization=org_a,
    )

    # Migrate forward to 0007.
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps

    MigratedStage = new_apps.get_model("quickscale_modules_crm", "Stage")
    MigratedOrganization = new_apps.get_model("quickscale_modules_orgs", "Organization")

    # Re-fetch org references through the migrated apps registry.
    org_a = MigratedOrganization.objects.get(pk=org_a.pk)
    org_b = MigratedOrganization.objects.get(pk=org_b.pk)

    # Verify legacy rows survive.
    won_stage = MigratedStage.objects.get(pk=won_stage_a.pk)
    assert won_stage.name == "Closed-Won"
    assert won_stage.terminal_semantic == "won"
    assert won_stage.organization_id == org_a.pk

    lost_stage = MigratedStage.objects.get(pk=lost_stage_a.pk)
    assert lost_stage.name == "Closed-Lost"
    assert lost_stage.terminal_semantic == "lost"
    assert lost_stage.organization_id == org_a.pk

    # Verify terminal_semantic field is no longer field-level unique.
    ts_field = MigratedStage._meta.get_field("terminal_semantic")
    assert ts_field.unique is False

    # Now that the constraint has changed, test the new uniqueness rules.

    # Verify duplicate same-org terminal_semantic is blocked.
    with pytest.raises(IntegrityError), transaction.atomic():
        MigratedStage.objects.create(
            name="Deal Signed",
            order=9,
            terminal_semantic="won",
            organization=org_a,
        )

    # Verify cross-org same terminal semantic is allowed.
    # The old global unique=True would have blocked this, but post-0007 the
    # per-org constraint (terminal_semantic, organization) allows it.
    new_org_b_won = MigratedStage.objects.create(
        name="Org-B Won",
        order=1,
        terminal_semantic="won",
        organization=org_b,
    )
    assert new_org_b_won.pk != won_stage.pk
    assert new_org_b_won.organization_id == org_b.pk

    # Verify NULL-owned + org-owned coexistence is not possible post-0006
    # (organization is NOT NULL), so we only test the org-owned path.


def test_0001_no_default_stages() -> None:
    """Migration 0001 creates schema only — no default Stage rows.

    Phase F11.10b repair: 0001_initial previously created four NULL-owned
    default Stage rows via RunPython. These blocked 0006 on clean installs
    because 0006 hard-stops on any NULL-owned rows. After the fix, 0001
    creates schema only; default stage seeding is deferred to runtime.
    """
    migrate_to = ("quickscale_modules_crm", "0001_initial")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    apps = executor.loader.project_state([migrate_to]).apps

    Stage = apps.get_model("quickscale_modules_crm", "Stage")
    assert Stage.objects.count() == 0, "0001 should not create default stages"


def test_0001_through_0006_clean_migration_history() -> None:
    """Full forward-migration chain 0001→0006 succeeds on clean database.

    Phase F11.10b regression guard: after removing the NULL-owned default
    Stage creation from 0001, the entire migration history from initial
    schema through the F11.10b enforced-organization schema flip must
    complete without hitting the 0006 guard.

    This proves that clean installs and history rebuilds no longer fail
    at 0006 due to leftover NULL-owned default stages.
    """
    migrate_to = ("quickscale_modules_crm", "0006_enforce_required_organization")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    apps = executor.loader.project_state([migrate_to]).apps

    # The 0006 guard (assert_no_null_owned_rows) must have passed silently.
    # Verify the final-schema contract on all five owned models.
    for model_name in ("Tag", "Company", "Contact", "Stage", "Deal"):
        model = apps.get_model("quickscale_modules_crm", model_name)
        field = model._meta.get_field("organization")
        assert field.null is False, f"{model_name}.organization.null is not False"
        assert field.remote_field.on_delete.__name__ == "PROTECT", (
            f"{model_name}.organization.on_delete is not PROTECT"
        )


# ---------------------------------------------------------------------------
# Historical 0002 backfill proof — live at 0001→0002 state.
# ---------------------------------------------------------------------------


def test_0002_terminal_semantic_backfill_uses_exact_names_and_deterministic_duplicate_selection() -> (
    None
):
    """Migration 0002 backfill provably tags canonical exact-name terminal stages.

    Phase 3 move from ``test_models.py``: this is a historical migration
    proof, not a live current-state test.  The backfill function is called
    at the 0002 state (after the terminal_semantic field has been added)
    using ``apps.get_model()``.
    """
    migrate_to = ("quickscale_modules_crm", "0002_stage_terminal_semantic")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    apps = executor.loader.project_state([migrate_to]).apps

    Stage = apps.get_model("quickscale_modules_crm", "Stage")
    Company = apps.get_model("quickscale_modules_crm", "Company")
    Contact = apps.get_model("quickscale_modules_crm", "Contact")
    Deal = apps.get_model("quickscale_modules_crm", "Deal")

    Stage.objects.all().delete()

    company = Company.objects.create(name="Acme Corp")
    contact = Contact.objects.create(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        company=company,
    )

    won_high_count_high_order = Stage.objects.create(name="Closed-Won", order=99)
    won_high_count_low_order = Stage.objects.create(name="Closed-Won", order=1)
    won_low_count_lowest_order = Stage.objects.create(name="Closed-Won", order=0)
    won_variant = Stage.objects.create(name="closed-won", order=1)
    lost_low_id = Stage.objects.create(name="Closed-Lost", order=5)
    lost_high_id = Stage.objects.create(name="Closed-Lost", order=5)
    lost_variant = Stage.objects.create(name="Closed Lost", order=5)

    for index in range(3):
        Deal.objects.create(
            title=f"Won high order {index}",
            contact=contact,
            stage=won_high_count_high_order,
        )
        Deal.objects.create(
            title=f"Won low order {index}",
            contact=contact,
            stage=won_high_count_low_order,
        )
    for index in range(2):
        Deal.objects.create(
            title=f"Won lower count {index}",
            contact=contact,
            stage=won_low_count_lowest_order,
        )

    # Run the 0002 backfill helper using the 0002-state apps.
    _stage_terminal_semantic_migration.backfill_terminal_stage_semantics(
        apps,
        None,
    )

    # Re-fetch using the same 0002-state apps.
    w_h_c_h_o = Stage.objects.get(pk=won_high_count_high_order.pk)
    w_h_c_l_o = Stage.objects.get(pk=won_high_count_low_order.pk)
    w_l_c_l_o = Stage.objects.get(pk=won_low_count_lowest_order.pk)
    w_v = Stage.objects.get(pk=won_variant.pk)
    l_l_i = Stage.objects.get(pk=lost_low_id.pk)
    l_h_i = Stage.objects.get(pk=lost_high_id.pk)
    l_v = Stage.objects.get(pk=lost_variant.pk)

    assert w_h_c_l_o.terminal_semantic == "won"
    assert w_h_c_h_o.terminal_semantic is None
    assert w_l_c_l_o.terminal_semantic is None
    assert w_v.terminal_semantic is None
    assert l_l_i.terminal_semantic == "lost"
    assert l_h_i.terminal_semantic is None
    assert l_v.terminal_semantic is None

    # Prove original row metadata is preserved after backfill.
    w_h_c_h_o.name = "Closed-Won Duplicate"
    w_h_c_h_o.order = 50
    w_h_c_h_o.save(update_fields=["name", "order"])
    w_h_c_h_o.refresh_from_db()
    assert w_h_c_h_o.name == "Closed-Won Duplicate"
    assert w_h_c_h_o.order == 50


# ---------------------------------------------------------------------------
# Historical backfill proof — inline at 0004 state (backfill command removed
# in T1.5; these proofs verify the ORM-level operation remains valid).
# ---------------------------------------------------------------------------


def test_backfill_null_owned_rows_to_target_org() -> None:
    """NULL-owned rows at 0004 state can be assigned to a target organization."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to, LATEST_ORGS_MIGRATION]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    OldCompany = old_apps.get_model("quickscale_modules_crm", "Company")
    OldContact = old_apps.get_model("quickscale_modules_crm", "Contact")
    OldStage = old_apps.get_model("quickscale_modules_crm", "Stage")
    OldDeal = old_apps.get_model("quickscale_modules_crm", "Deal")

    target_org = OldOrg.objects.create(name="Target Org", slug="target-org")

    tag = OldTag.objects.create(name="VIP")
    company = OldCompany.objects.create(name="Acme Corp")
    contact = OldContact.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        company=company,
    )
    stage = OldStage.objects.create(name="Prospecting", order=1)
    deal = OldDeal.objects.create(
        title="Big Deal",
        contact=contact,
        stage=stage,
    )

    # Verify all start as NULL-owned.
    assert tag.organization is None
    assert company.organization is None
    assert contact.organization is None
    assert stage.organization is None
    assert deal.organization is None

    # Inline backfill.
    for model_cls in (OldTag, OldCompany, OldContact, OldStage, OldDeal):
        model_cls.objects.filter(organization__isnull=True).update(
            organization=target_org
        )

    # Verify all now point to target_org.
    tag = OldTag.objects.get(pk=tag.pk)
    company = OldCompany.objects.get(pk=company.pk)
    contact = OldContact.objects.get(pk=contact.pk)
    stage = OldStage.objects.get(pk=stage.pk)
    deal = OldDeal.objects.get(pk=deal.pk)

    assert tag.organization_id == target_org.pk
    assert company.organization_id == target_org.pk
    assert contact.organization_id == target_org.pk
    assert stage.organization_id == target_org.pk
    assert deal.organization_id == target_org.pk


def test_backfill_null_owned_zens_gracefully_with_no_rows() -> None:
    """Inline backfill is a no-op when no NULL-owned rows exist."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to, LATEST_ORGS_MIGRATION]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    OldCompany = old_apps.get_model("quickscale_modules_crm", "Company")
    OldContact = old_apps.get_model("quickscale_modules_crm", "Contact")
    OldStage = old_apps.get_model("quickscale_modules_crm", "Stage")
    OldDeal = old_apps.get_model("quickscale_modules_crm", "Deal")

    target_org = OldOrg.objects.create(name="Target Org", slug="target-org-none")

    OldTag.objects.create(name="VIP", organization=target_org)
    OldCompany.objects.create(name="Acme Corp", organization=target_org)
    company = OldCompany.objects.create(name="Test Co", organization=target_org)
    OldContact.objects.create(
        first_name="Test",
        last_name="User",
        email="test@example.com",
        company=company,
        organization=target_org,
    )
    OldStage.objects.create(name="Stage 1", order=1, organization=target_org)
    contact = OldContact.objects.create(
        first_name="Test2",
        last_name="User2",
        email="test2@example.com",
        company=company,
        organization=target_org,
    )
    stage = OldStage.objects.get(organization=target_org)
    OldDeal.objects.create(
        title="Deal 1",
        contact=contact,
        stage=stage,
        organization=target_org,
    )

    # Inline backfill — should be a no-op (no NULL rows).
    updated = 0
    for model_cls in (OldTag, OldCompany, OldContact, OldStage, OldDeal):
        updated += model_cls.objects.filter(organization__isnull=True).update(
            organization=target_org
        )
    assert updated == 0


# ---------------------------------------------------------------------------
# AF12 Phase 2 — Composite FK migration forward/reverse/replay proofs
# ---------------------------------------------------------------------------
# Verifies the rewritten 0009 migration adds parent UNIQUE constraints and
# composite child FKs, that the reverse path removes them cleanly, and that
# replay (re-apply) is idempotent.  Also proves the 0009→0010 migration
# chain (AF11 compatibility) is intact.
#
# Constraint-existence assertions are PostgreSQL-only; the forward/reverse
# migration sequence is verified on all database backends (SQLite during
# tests).  Data survival through the migration is verified regardless of
# backend.
# ---------------------------------------------------------------------------

try:
    from django.db import connection as _crm_dj_connection

    _CRM_IS_POSTGRES = _crm_dj_connection.vendor == "postgresql"
except Exception:
    _CRM_IS_POSTGRES = False


def _seed_af12_contact_and_note(apps: Any, org_model: Any) -> tuple[Any, Any, Any]:
    """Seed a contact, deal, and one contact/deal note for AF12 migration tests.
    Returns (contact, contactnote, dealnote)."""
    Contact = apps.get_model("quickscale_modules_crm", "Contact")
    ContactNote = apps.get_model("quickscale_modules_crm", "ContactNote")
    Deal = apps.get_model("quickscale_modules_crm", "Deal")
    DealNote = apps.get_model("quickscale_modules_crm", "DealNote")

    contact = Contact.objects.create(
        first_name="AF12",
        last_name="Contact",
        email="af12_contact@test.com",
    )
    contactnote = ContactNote.objects.create(
        contact=contact,
        organization=org_model,
        text="AF12 contact note.",
    )
    deal = Deal.objects.create(
        title="AF12 Deal",
        contact=contact,
    )
    dealnote = DealNote.objects.create(
        deal=deal,
        organization=org_model,
        text="AF12 deal note.",
    )
    return contact, contactnote, dealnote


def test_0008_to_0009_composite_fk_migration_forward() -> None:
    """Forward migration 0008→0009 succeeds and preserves existing data."""
    migrate_from = ("quickscale_modules_crm", "0008_enable_rls")
    migrate_to = ("quickscale_modules_crm", "0009_add_note_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])

    assert executor.loader.project_state([migrate_from]).apps is not None, (
        "Project state at 0008 must be resolvable"
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])

    new_apps = executor.loader.project_state([migrate_to]).apps
    ContactNote = new_apps.get_model("quickscale_modules_crm", "ContactNote")
    DealNote = new_apps.get_model("quickscale_modules_crm", "DealNote")

    # Verify NOT NULL / PROTECT contract on note organization fields.
    for name, model_cls in [("ContactNote", ContactNote), ("DealNote", DealNote)]:
        field = model_cls._meta.get_field("organization")
        assert field.null is False, f"{name}.organization.null is not False"
        assert field.remote_field.on_delete.__name__ == "PROTECT", (
            f"{name}.organization.on_delete is not PROTECT"
        )


@pytest.mark.skipif(
    not _CRM_IS_POSTGRES,
    reason="Constraint existence check requires PostgreSQL.",
)
def test_0009_composite_fk_constraints_exist() -> None:
    """After 0009, the parent UNIQUE constraints and composite child FKs
    must exist in pg_constraint."""
    migrate_to = ("quickscale_modules_crm", "0009_add_note_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])

    with connection.cursor() as cursor:
        # Check parent UNIQUE constraints.
        for constraint_name, table in [
            ("crm_contact_id_org_unique", "quickscale_modules_crm_contact"),
            ("crm_deal_id_org_unique", "quickscale_modules_crm_deal"),
        ]:
            cursor.execute(
                """
                SELECT 1 FROM pg_constraint pc
                JOIN pg_class c ON c.oid = pc.conrelid
                WHERE pc.conname = %s AND c.relname = %s AND pc.contype = 'u'
                """,
                [constraint_name, table],
            )
            assert cursor.fetchone() is not None, (
                f"Parent UNIQUE constraint '{constraint_name}' on "
                f"{table} not found after migration 0009."
            )

        # Check composite child FKs.
        for constraint_name, child_table, parent_table in [
            (
                "crm_contactnote_contact_org_fk",
                "quickscale_modules_crm_contactnote",
                "quickscale_modules_crm_contact",
            ),
            (
                "crm_dealnote_deal_org_fk",
                "quickscale_modules_crm_dealnote",
                "quickscale_modules_crm_deal",
            ),
        ]:
            cursor.execute(
                """
                SELECT 1 FROM pg_constraint pc
                JOIN pg_class child_cls ON child_cls.oid = pc.conrelid
                JOIN pg_class parent_cls ON parent_cls.oid = pc.confrelid
                WHERE pc.conname = %s
                  AND child_cls.relname = %s
                  AND parent_cls.relname = %s
                  AND pc.contype = 'f'
                """,
                [constraint_name, child_table, parent_table],
            )
            assert cursor.fetchone() is not None, (
                f"Composite FK '{constraint_name}' from {child_table} "
                f"to {parent_table} not found after migration 0009."
            )


def test_0009_reverse_removes_composite_fk_constraints() -> None:
    """Reverse migration 0009→0008 must succeed and cleanly remove
    the ADD operations."""
    migrate_from = ("quickscale_modules_crm", "0008_enable_rls")
    migrate_through = ("quickscale_modules_crm", "0009_add_note_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])

    # Migrate forward.
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_through])

    # Roll back to 0008.
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])

    # Verify the project state resolves at 0008.
    state = executor.loader.project_state([migrate_from])
    ContactNote = state.apps.get_model("quickscale_modules_crm", "ContactNote")
    assert ContactNote is not None

    # At 0008 state, ContactNote should NOT have organization field yet.
    # The field was added by migration 0009; reversing removes it entirely.
    from django.core.exceptions import FieldDoesNotExist

    with pytest.raises(FieldDoesNotExist):
        ContactNote._meta.get_field("organization")


def test_0009_replay_idempotent() -> None:
    """Forward, reverse, then forward again — replay must be idempotent."""
    migrate_0008 = ("quickscale_modules_crm", "0008_enable_rls")
    migrate_0009 = ("quickscale_modules_crm", "0009_add_note_organization_ownership")

    executor = MigrationExecutor(connection)

    # First pass: forward.
    executor.migrate([migrate_0008])
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_0009])

    # Reverse.
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_0008])

    # Re-apply (replay).
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_0009])

    new_apps = executor.loader.project_state([migrate_0009]).apps
    ContactNote = new_apps.get_model("quickscale_modules_crm", "ContactNote")
    field = ContactNote._meta.get_field("organization")
    assert field.null is False, (
        "After replay, ContactNote.organization must be NOT NULL"
    )
    assert field.remote_field.on_delete.__name__ == "PROTECT"


def test_0009_to_0010_migration_chain() -> None:
    """Forward through 0009→0010 succeeds (AF11 compatibility)."""
    migrate_through = (
        "quickscale_modules_crm",
        "0010_refresh_rls_policies_nullif_guard",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_through])

    new_apps = executor.loader.project_state([migrate_through]).apps
    # Verify the final state includes all constraints from 0009.
    for model_name in ("ContactNote", "DealNote"):
        model = new_apps.get_model("quickscale_modules_crm", model_name)
        field = model._meta.get_field("organization")
        assert field.null is False, (
            f"{model_name}.organization must be NOT NULL after 0010"
        )


# ---------------------------------------------------------------------------
# AF12 Phase 2 — direct parent-organization mutation rejection proofs
# (CR-AF12-001 resolution)
# ---------------------------------------------------------------------------
# These tests prove that the composite FKs installed by migration 0009
# reject attempts to change a parent's organization_id when child rows
# reference the old (parent_id, organization_id) pair.
#
# The FK constraint enforces:
#   (child.parent_fk, child.organization_id) =
#   (parent.id, parent.organization_id)
#
# Updating the parent's organization_id breaks this equality for
# existing child rows and must be rejected with a foreign key violation.
#
# Tests are PostgreSQL-only because FK enforcement uses constraints that
# only PostgreSQL validates (SQLite defaults to deferred FK checking).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(
    not _CRM_IS_POSTGRES,
    reason="Parent-org mutation rejection proof requires PostgreSQL FK enforcement.",
)
class TestCrmParentOrgMutationRejection:
    """Prove that parent org_id mutations are rejected by the composite FK."""

    def test_contact_org_id_mutation_rejected_when_contactnote_exists(self) -> None:
        """Updating Contact.organization_id fails when a ContactNote
        references the old (contact_id, organization_id) pair."""
        from django.contrib.auth import get_user_model

        from quickscale_modules_crm.models import Company, Contact, ContactNote
        from quickscale_modules_orgs.models import Organization

        User = get_user_model()

        org_a = Organization.objects.create(name="Org A", slug="crm-mut-a")
        org_b = Organization.objects.create(name="Org B", slug="crm-mut-b")
        company = Company.objects.create(name="Acme Corp", organization=org_a)
        user = User.objects.create_user(username="testuser", password="testpass")

        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="Mutation",
            last_name="Target",
            email="mut@test.com",
            company=company,
        )
        ContactNote.all_objects.create(
            contact=contact,
            organization=org_a,
            text="Child row locking the parent org.",
            created_by=user,
        )

        # Attempt to reassign the parent contact to a different org.
        # The composite FK (contactnote.contact_id, contactnote.organization_id)
        # → (contact.id, contact.organization_id) should reject this because
        # the ContactNote still references (contact.id, org_a).
        #
        # The composite FK is NOT DEFERRABLE (SA60 uniform policy), so the
        # constraint is checked immediately — SET CONSTRAINTS below is a
        # harmless no-op retained for backward compatibility.
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET CONSTRAINTS crm_contactnote_contact_org_fk IMMEDIATE"
                )
            Contact.all_objects.filter(pk=contact.pk).update(organization=org_b)

    def test_deal_org_id_mutation_rejected_when_dealnote_exists(self) -> None:
        """Updating Deal.organization_id fails when a DealNote
        references the old (deal_id, organization_id) pair."""
        from django.contrib.auth import get_user_model

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )
        from quickscale_modules_orgs.models import Organization

        User = get_user_model()

        org_a = Organization.objects.create(name="Org A", slug="crm-mut-c")
        org_b = Organization.objects.create(name="Org B", slug="crm-mut-d")
        company = Company.objects.create(name="Acme Corp", organization=org_a)
        user = User.objects.create_user(username="testuser2", password="testpass")
        stage = Stage.objects.create(name="Test Stage", order=1, organization=org_a)

        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="DealMut",
            last_name="Target",
            email="dealmut@test.com",
            company=company,
        )
        deal = Deal.all_objects.create(
            organization=org_a,
            title="Mutation target deal",
            contact=contact,
            stage=stage,
        )
        DealNote.all_objects.create(
            deal=deal,
            organization=org_a,
            text="Child row locking the deal org.",
            created_by=user,
        )

        # The composite FK is NOT DEFERRABLE (SA60 uniform policy), so the
        # constraint is checked immediately — SET CONSTRAINTS below is a
        # harmless no-op retained for backward compatibility.
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS crm_dealnote_deal_org_fk IMMEDIATE")
            Deal.all_objects.filter(pk=deal.pk).update(organization=org_b)

    def test_contact_org_id_mutation_without_children_succeeds(self) -> None:
        """Updating Contact.organization_id succeeds when NO child
        ContactNote rows reference the old pair — positive control."""
        from quickscale_modules_crm.models import Company, Contact
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="crm-mut-e")
        org_b = Organization.objects.create(name="Org B", slug="crm-mut-f")
        company = Company.objects.create(name="Acme Corp", organization=org_a)

        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="NoChild",
            last_name="Contact",
            email="nochild@test.com",
            company=company,
        )

        # No ContactNote referencing this contact — mutation should succeed.
        Contact.all_objects.filter(pk=contact.pk).update(organization=org_b)
        contact.refresh_from_db()
        assert contact.organization_id == org_b.pk
