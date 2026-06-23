"""Migration tests for CRM terminal stage semantics and backfill proofs.

Phase 3: historical NULL/backfill proofs live here, not in live suites.
"""

from __future__ import annotations

from importlib import import_module
from io import StringIO
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


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
    old_apps = executor.loader.project_state([migrate_from]).apps

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
    old_apps = executor.loader.project_state([migrate_from]).apps

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
# Historical backfill_crm_org_ownership command proofs — live at 0004 state.
# ---------------------------------------------------------------------------


def test_backfill_requires_org_slug() -> None:
    """Command requires --org-slug argument."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])

    with pytest.raises(CommandError, match="org-slug"):
        call_command(
            "backfill_crm_org_ownership",
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_backfill_rejects_nonexistent_org_slug() -> None:
    """Command rejects an org slug that does not exist."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])

    with pytest.raises(CommandError, match="does not exist"):
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=nonexistent",
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_backfill_null_owned_rows_to_target_org() -> None:
    """Command assigns NULL-owned rows to the target organization."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to]).apps

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

    stdout = StringIO()
    call_command(
        "backfill_crm_org_ownership",
        "--org-slug=target-org",
        stdout=stdout,
        stderr=StringIO(),
    )

    # Refresh and verify all now point to target_org.
    # Note: refresh_from_db() is not available on historical model instances,
    # so we re-fetch via OldTag.objects.get().
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

    output = stdout.getvalue()
    assert "Tag:" in output
    assert "Company:" in output
    assert "Contact:" in output
    assert "Stage:" in output
    assert "Deal:" in output
    assert "Backfill complete" in output


def test_backfill_is_idempotent_on_second_run() -> None:
    """Command is idempotent: second run updates 0 rows."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    OldCompany = old_apps.get_model("quickscale_modules_crm", "Company")

    OldOrg.objects.create(name="Target Org", slug="target-org-backfill-2")

    OldTag.objects.create(name="VIP")
    OldCompany.objects.create(name="Acme Corp")

    first_stdout = StringIO()
    call_command(
        "backfill_crm_org_ownership",
        "--org-slug=target-org-backfill-2",
        stdout=first_stdout,
        stderr=StringIO(),
    )

    second_stdout = StringIO()
    call_command(
        "backfill_crm_org_ownership",
        "--org-slug=target-org-backfill-2",
        stdout=second_stdout,
        stderr=StringIO(),
    )

    output = second_stdout.getvalue()
    assert "Tag: 0" in output
    assert "Company: 0" in output


def test_backfill_aborts_on_conflicting_ownership() -> None:
    """Command aborts without writes when conflicting ownership exists."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    OldCompany = old_apps.get_model("quickscale_modules_crm", "Company")

    OldOrg.objects.create(name="Target Org", slug="target-org-backfill-3")
    other_org = OldOrg.objects.create(name="Other Org", slug="other-org-backfill-3")

    tag = OldTag.objects.create(name="VIP")
    company = OldCompany.objects.create(name="Acme Corp", organization=other_org)

    with pytest.raises(CommandError, match="conflicting organization ownership"):
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org-backfill-3",
            stdout=StringIO(),
            stderr=StringIO(),
        )

    tag = OldTag.objects.get(pk=tag.pk)
    company = OldCompany.objects.get(pk=company.pk)
    assert tag.organization is None
    assert company.organization_id == other_org.pk


def test_backfill_aborts_on_mixed_ownership() -> None:
    """Command aborts when target-org, other-org, and NULL rows all coexist."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")

    target_org = OldOrg.objects.create(name="Target Org", slug="target-org-mixed")
    other_org = OldOrg.objects.create(name="Other Org", slug="other-org-mixed")

    target_tag = OldTag.objects.create(name="TargetTag", organization=target_org)
    other_tag = OldTag.objects.create(name="OtherTag", organization=other_org)
    null_tag = OldTag.objects.create(name="NullTag")

    with pytest.raises(CommandError, match="conflicting organization ownership"):
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org-mixed",
            stdout=StringIO(),
            stderr=StringIO(),
        )

    target_tag = OldTag.objects.get(pk=target_tag.pk)
    other_tag = OldTag.objects.get(pk=other_tag.pk)
    null_tag = OldTag.objects.get(pk=null_tag.pk)
    assert target_tag.organization_id == target_org.pk
    assert other_tag.organization_id == other_org.pk
    assert null_tag.organization is None


def test_backfill_allows_when_existing_rows_match_target_org() -> None:
    """Command succeeds when existing non-null rows already point to target org."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")

    target_org = OldOrg.objects.create(name="Target Org", slug="target-org-backfill-5")

    OldTag.objects.create(name="Existing", organization=target_org)
    null_tag = OldTag.objects.create(name="NullTag")

    stdout = StringIO()
    call_command(
        "backfill_crm_org_ownership",
        "--org-slug=target-org-backfill-5",
        stdout=stdout,
        stderr=StringIO(),
    )

    null_tag = OldTag.objects.get(pk=null_tag.pk)
    assert null_tag.organization_id == target_org.pk

    output = stdout.getvalue()
    assert "Tag: 1" in output


def test_backfill_dry_run_does_not_write() -> None:
    """Command with --dry-run shows what would be updated without writing."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    OldCompany = old_apps.get_model("quickscale_modules_crm", "Company")

    OldOrg.objects.create(name="Target Org", slug="target-org-backfill-6")

    tag = OldTag.objects.create(name="VIP")
    company = OldCompany.objects.create(name="Acme Corp")

    stdout = StringIO()
    call_command(
        "backfill_crm_org_ownership",
        "--org-slug=target-org-backfill-6",
        "--dry-run",
        stdout=stdout,
        stderr=StringIO(),
    )

    tag = OldTag.objects.get(pk=tag.pk)
    company = OldCompany.objects.get(pk=company.pk)
    assert tag.organization is None
    assert company.organization is None

    output = stdout.getvalue()
    assert "Dry run" in output
    assert "would update" in output


def test_backfill_reports_zero_null_rows_gracefully() -> None:
    """Command reports success when no NULL-owned rows exist."""
    migrate_to = ("quickscale_modules_crm", "0004_add_organization_ownership")

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    old_apps = executor.loader.project_state([migrate_to]).apps

    OldOrg = old_apps.get_model("quickscale_modules_orgs", "Organization")
    OldTag = old_apps.get_model("quickscale_modules_crm", "Tag")
    OldCompany = old_apps.get_model("quickscale_modules_crm", "Company")
    OldContact = old_apps.get_model("quickscale_modules_crm", "Contact")
    OldStage = old_apps.get_model("quickscale_modules_crm", "Stage")
    OldDeal = old_apps.get_model("quickscale_modules_crm", "Deal")

    target_org = OldOrg.objects.create(name="Target Org", slug="target-org-backfill-7")

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

    stdout = StringIO()
    call_command(
        "backfill_crm_org_ownership",
        "--org-slug=target-org-backfill-7",
        stdout=stdout,
        stderr=StringIO(),
    )

    output = stdout.getvalue()
    assert "No NULL-owned rows found" in output or "Nothing to backfill" in output
