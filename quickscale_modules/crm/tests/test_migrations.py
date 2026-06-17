"""Migration tests for CRM terminal stage semantics."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


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


def _create_deal(apps, *, contact, stage, title: str):
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
