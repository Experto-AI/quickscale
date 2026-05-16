"""Migration tests for billing subscription reservation invariants."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def _get_user_model(apps):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".", maxsplit=1)
    return apps.get_model(app_label, model_name)


def _create_user(apps, username: str):
    User = _get_user_model(apps)

    return User.objects.create(
        username=username,
        email=f"{username}@example.com",
        password="billingpass123",
    )


def _create_plan(
    apps,
    *,
    name: str = "Growth",
    slug: str = "growth",
    price_id: str = "price_growth_monthly",
    price_cents: int = 4900,
):
    Plan = apps.get_model("quickscale_modules_billing", "Plan")

    return Plan.objects.create(
        name=name,
        slug=slug,
        stripe_price_id=price_id,
        credits_per_period=250,
        price_cents=price_cents,
        currency="usd",
        billing_interval="monthly",
    )


def test_0002_reconciles_duplicate_current_subscriptions_before_uniqueness() -> None:
    migrate_from = ("quickscale_modules_billing", "0001_initial")
    migrate_to = (
        "quickscale_modules_billing",
        "0002_subscription_reservation_invariants",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from]).apps
    Subscription = old_apps.get_model("quickscale_modules_billing", "Subscription")

    user = _create_user(old_apps, "billing-migration-user")
    plan = _create_plan(old_apps)
    oldest_period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    oldest_period_end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    oldest_synced = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_oldest_synced",
        stripe_customer_id="cus_oldest_synced",
        status="active",
        current_period_start=oldest_period_start,
        current_period_end=oldest_period_end,
    )
    middle_synced = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_middle_synced",
        stripe_customer_id="cus_middle_synced",
        status="past_due",
    )
    older_unsynced = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id=" ",
        stripe_customer_id=" ",
        status="incomplete",
    )
    newest_unsynced = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="",
        stripe_customer_id="",
        status="incomplete",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps
    migrated_subscription = new_apps.get_model(
        "quickscale_modules_billing",
        "Subscription",
    )
    migrated_user = _get_user_model(new_apps).objects.get(pk=user.pk)
    migrated_plan = new_apps.get_model(
        "quickscale_modules_billing", "Plan"
    ).objects.get(pk=plan.pk)

    oldest_synced = migrated_subscription.objects.get(pk=oldest_synced.pk)
    middle_synced = migrated_subscription.objects.get(pk=middle_synced.pk)
    older_unsynced = migrated_subscription.objects.get(pk=older_unsynced.pk)
    newest_unsynced = migrated_subscription.objects.get(pk=newest_unsynced.pk)

    assert middle_synced.status == "past_due"
    assert middle_synced.stripe_subscription_id == "sub_middle_synced"
    assert middle_synced.stripe_customer_id == "cus_middle_synced"
    assert middle_synced.current_period_start == oldest_period_start
    assert middle_synced.current_period_end == oldest_period_end
    assert oldest_synced.status == "canceled"
    assert oldest_synced.stripe_subscription_id == "sub_oldest_synced"
    assert older_unsynced.status == "incomplete_expired"
    assert newest_unsynced.status == "incomplete_expired"
    assert (
        migrated_subscription.objects.filter(
            user_id=migrated_user.pk,
            status__in=(
                "incomplete",
                "trialing",
                "active",
                "past_due",
                "unpaid",
                "paused",
            ),
        ).count()
        == 1
    )
    assert (
        migrated_subscription.objects.filter(
            user_id=migrated_user.pk,
            status__in=(
                "incomplete",
                "trialing",
                "active",
                "past_due",
                "unpaid",
                "paused",
            ),
        )
        .values_list("pk", flat=True)
        .get()
        == middle_synced.pk
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        migrated_subscription.objects.create(
            user=migrated_user,
            plan=migrated_plan,
            stripe_subscription_id="sub_after_migration",
            stripe_customer_id="cus_after_migration",
            status="active",
        )


def test_0002_prefers_synced_survivor_when_duplicate_current_rows_disagree_on_plan() -> (
    None
):
    migrate_from = ("quickscale_modules_billing", "0001_initial")
    migrate_to = (
        "quickscale_modules_billing",
        "0002_subscription_reservation_invariants",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from]).apps
    Subscription = old_apps.get_model("quickscale_modules_billing", "Subscription")

    user = _create_user(old_apps, "billing-migration-plan-user")
    synced_plan = _create_plan(
        old_apps,
        name="Starter",
        slug="starter",
        price_id="price_starter_monthly",
        price_cents=1900,
    )
    unsynced_plan = _create_plan(
        old_apps,
        name="Scale",
        slug="scale",
        price_id="price_scale_monthly",
        price_cents=6900,
    )
    synced_survivor = Subscription.objects.create(
        user=user,
        plan=synced_plan,
        stripe_subscription_id="sub_synced_survivor",
        stripe_customer_id="cus_synced_survivor",
        status="active",
    )
    newer_unsynced = Subscription.objects.create(
        user=user,
        plan=unsynced_plan,
        stripe_subscription_id="",
        stripe_customer_id="",
        status="incomplete",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps
    migrated_subscription = new_apps.get_model(
        "quickscale_modules_billing",
        "Subscription",
    )
    synced_survivor = migrated_subscription.objects.get(pk=synced_survivor.pk)
    newer_unsynced = migrated_subscription.objects.get(pk=newer_unsynced.pk)

    assert synced_survivor.status == "active"
    assert synced_survivor.plan_id == synced_plan.pk
    assert synced_survivor.stripe_subscription_id == "sub_synced_survivor"
    assert newer_unsynced.status == "incomplete_expired"
    assert newer_unsynced.plan_id == unsynced_plan.pk
    assert (
        migrated_subscription.objects.filter(
            user_id=user.pk,
            status__in=(
                "incomplete",
                "trialing",
                "active",
                "past_due",
                "unpaid",
                "paused",
            ),
        )
        .values_list("pk", flat=True)
        .get()
        == synced_survivor.pk
    )
