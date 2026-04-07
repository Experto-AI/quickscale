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
