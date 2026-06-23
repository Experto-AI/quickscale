"""Migration tests for billing subscription reservation invariants."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

LATEST_ORGS_MIGRATION = ("quickscale_modules_orgs", "0003_alter_organization_is_system")
LATEST_BILLING_MIGRATION = (
    "quickscale_modules_billing",
    "0004_credit_transaction_nullable_user_provenance",
)


@pytest.fixture(autouse=True)
def restore_latest_billing_schema() -> None:
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(
        [
            (LATEST_BILLING_MIGRATION[0], None),
            (LATEST_ORGS_MIGRATION[0], None),
        ]
    )
    executor = MigrationExecutor(connection)
    executor.migrate([LATEST_ORGS_MIGRATION, LATEST_BILLING_MIGRATION])


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


def _create_org(
    apps,
    *,
    name: str,
    slug: str,
    stripe_customer_id: str = "",
    is_personal: bool = False,
):
    Organization = apps.get_model("quickscale_modules_orgs", "Organization")

    return Organization.objects.create(
        name=name,
        slug=slug,
        stripe_customer_id=stripe_customer_id,
        is_personal=is_personal,
    )


def _create_membership(apps, *, user, organization, role: str = "owner"):
    OrganizationMembership = apps.get_model(
        "quickscale_modules_orgs",
        "OrganizationMembership",
    )

    return OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
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


def test_0003_backfills_authoritative_org_fields_from_sole_membership() -> None:
    orgs_target = ("quickscale_modules_orgs", "0001_initial")
    billing_from = (
        "quickscale_modules_billing",
        "0002_subscription_reservation_invariants",
    )
    billing_to = (
        "quickscale_modules_billing",
        "0003_org_authoritative_billing_contract",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([orgs_target, billing_from])
    old_apps = executor.loader.project_state([orgs_target, billing_from]).apps
    Subscription = old_apps.get_model("quickscale_modules_billing", "Subscription")
    CreditBalance = old_apps.get_model("quickscale_modules_billing", "CreditBalance")
    CreditTransaction = old_apps.get_model(
        "quickscale_modules_billing",
        "CreditTransaction",
    )

    user = _create_user(old_apps, "billing-org-backfill-user")
    other_user = _create_user(old_apps, "billing-org-backfill-other")
    plan = _create_plan(old_apps)
    organization = _create_org(old_apps, name="Atlas", slug="atlas")
    _create_membership(old_apps, user=user, organization=organization)

    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_org_backfill",
        stripe_customer_id="cus_org_backfill",
        status="active",
    )
    balance = CreditBalance.objects.create(user=user, balance=75)
    transaction_row = CreditTransaction.objects.create(
        user=user,
        amount=25,
        transaction_type="purchase",
        stripe_event_id="evt_org_backfill",
        stripe_object_id="pi_org_backfill",
        stripe_reference_data={"payment_intent_id": "pi_org_backfill"},
        description="Org-authoritative backfill",
        balance_after=75,
    )

    executor = MigrationExecutor(connection)
    executor.migrate([orgs_target, billing_to])
    new_apps = executor.loader.project_state([orgs_target, billing_to]).apps
    migrated_subscription = new_apps.get_model(
        "quickscale_modules_billing",
        "Subscription",
    )
    migrated_balance = new_apps.get_model("quickscale_modules_billing", "CreditBalance")
    migrated_transaction = new_apps.get_model(
        "quickscale_modules_billing",
        "CreditTransaction",
    )
    migrated_plan = new_apps.get_model("quickscale_modules_billing", "Plan")
    migrated_organization = new_apps.get_model(
        "quickscale_modules_orgs",
        "Organization",
    ).objects.get(pk=organization.pk)
    migrated_user = _get_user_model(new_apps).objects.get(pk=user.pk)
    migrated_other_user = _get_user_model(new_apps).objects.get(pk=other_user.pk)

    subscription = migrated_subscription.objects.get(pk=subscription.pk)
    balance = migrated_balance.objects.get(pk=balance.pk)
    transaction_row = migrated_transaction.objects.get(pk=transaction_row.pk)
    plan = migrated_plan.objects.get(pk=plan.pk)

    assert subscription.organization_id == organization.pk
    assert subscription.user_id == migrated_user.pk
    assert balance.organization_id == organization.pk
    assert balance.user_id == migrated_user.pk
    assert transaction_row.organization_id == organization.pk
    assert migrated_organization.stripe_customer_id == "cus_org_backfill"
    assert plan.features == []

    with pytest.raises(IntegrityError), transaction.atomic():
        migrated_subscription.objects.create(
            user=migrated_other_user,
            organization_id=organization.pk,
            plan=plan,
            stripe_subscription_id="sub_org_duplicate",
            stripe_customer_id="cus_org_duplicate",
            status="active",
        )


def test_0003_creates_personal_org_for_billing_users_without_memberships() -> None:
    orgs_target = ("quickscale_modules_orgs", "0001_initial")
    billing_from = (
        "quickscale_modules_billing",
        "0002_subscription_reservation_invariants",
    )
    billing_to = (
        "quickscale_modules_billing",
        "0003_org_authoritative_billing_contract",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([orgs_target, billing_from])
    old_apps = executor.loader.project_state([orgs_target, billing_from]).apps
    Subscription = old_apps.get_model("quickscale_modules_billing", "Subscription")
    CreditBalance = old_apps.get_model("quickscale_modules_billing", "CreditBalance")

    user = _create_user(old_apps, "billing-personal-org-user")
    plan = _create_plan(old_apps)
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_personal_org",
        stripe_customer_id="cus_personal_org",
        status="active",
    )
    balance = CreditBalance.objects.create(user=user, balance=30)

    executor = MigrationExecutor(connection)
    executor.migrate([orgs_target, billing_to])
    new_apps = executor.loader.project_state([orgs_target, billing_to]).apps
    migrated_subscription = new_apps.get_model(
        "quickscale_modules_billing",
        "Subscription",
    ).objects.get(pk=subscription.pk)
    migrated_balance = new_apps.get_model(
        "quickscale_modules_billing",
        "CreditBalance",
    ).objects.get(pk=balance.pk)
    OrganizationMembership = new_apps.get_model(
        "quickscale_modules_orgs",
        "OrganizationMembership",
    )
    personal_membership = OrganizationMembership.objects.get(user_id=user.pk)

    assert personal_membership.organization.is_personal is True
    assert personal_membership.organization.slug == "billing-personal-org-user"
    assert personal_membership.role == "owner"
    assert personal_membership.organization.stripe_customer_id == "cus_personal_org"
    assert migrated_subscription.organization_id == personal_membership.organization_id
    assert migrated_balance.organization_id == personal_membership.organization_id


def test_0003_reports_ambiguous_user_memberships_without_guessing() -> None:
    orgs_target = ("quickscale_modules_orgs", "0001_initial")
    billing_from = (
        "quickscale_modules_billing",
        "0002_subscription_reservation_invariants",
    )
    billing_to = (
        "quickscale_modules_billing",
        "0003_org_authoritative_billing_contract",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([orgs_target, billing_from])
    old_apps = executor.loader.project_state([orgs_target, billing_from]).apps
    Subscription = old_apps.get_model("quickscale_modules_billing", "Subscription")

    user = _create_user(old_apps, "billing-ambiguous-user")
    plan = _create_plan(old_apps)
    first_org = _create_org(old_apps, name="Alpha", slug="alpha")
    second_org = _create_org(old_apps, name="Bravo", slug="bravo")
    _create_membership(old_apps, user=user, organization=first_org, role="admin")
    _create_membership(old_apps, user=user, organization=second_org, role="member")
    Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_ambiguous_user",
        stripe_customer_id="cus_ambiguous_user",
        status="active",
    )

    executor = MigrationExecutor(connection)
    with pytest.raises(
        RuntimeError,
        match="Billing org backfill requires manual resolution",
    ):
        executor.migrate([orgs_target, billing_to])


def test_0004_preserves_credit_transaction_rows_when_user_is_deleted() -> None:
    orgs_target = ("quickscale_modules_orgs", "0001_initial")
    billing_from = (
        "quickscale_modules_billing",
        "0003_org_authoritative_billing_contract",
    )
    billing_to = (
        "quickscale_modules_billing",
        "0004_credit_transaction_nullable_user_provenance",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([orgs_target, billing_from])
    old_apps = executor.loader.project_state([orgs_target, billing_from]).apps
    CreditTransaction = old_apps.get_model(
        "quickscale_modules_billing",
        "CreditTransaction",
    )

    user = _create_user(old_apps, "billing-transaction-history-user")
    organization = _create_org(old_apps, name="Ledger", slug="ledger")
    transaction_row = CreditTransaction.objects.create(
        user=user,
        organization=organization,
        amount=25,
        transaction_type="purchase",
        description="Deleted user provenance",
        balance_after=25,
    )

    executor = MigrationExecutor(connection)
    executor.migrate([orgs_target, billing_to])
    new_apps = executor.loader.project_state([orgs_target, billing_to]).apps
    migrated_transaction = new_apps.get_model(
        "quickscale_modules_billing",
        "CreditTransaction",
    )
    migrated_user = _get_user_model(new_apps).objects.get(pk=user.pk)

    migrated_user.delete()
    preserved_row = migrated_transaction.objects.get(pk=transaction_row.pk)

    assert preserved_row.user_id is None
    assert preserved_row.organization_id == organization.pk
    assert preserved_row.description == "Deleted user provenance"

    preserved_row.delete()
