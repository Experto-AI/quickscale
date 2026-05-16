"""Add reservation-capable subscription invariants for recurring checkout."""

from django.db import migrations, models


CURRENT_SUBSCRIPTION_STATUSES = (
    "incomplete",
    "trialing",
    "active",
    "past_due",
    "unpaid",
    "paused",
)
FIELDS_TO_MERGE = (
    "stripe_subscription_id",
    "stripe_customer_id",
    "current_period_start",
    "current_period_end",
)


def _has_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _is_synced_subscription_row(row):
    return _has_value(row.stripe_subscription_id)


def _select_subscription_survivor(current_rows):
    for row in current_rows:
        if _is_synced_subscription_row(row):
            return row
    return current_rows[0]


def reconcile_duplicate_current_subscriptions(apps, schema_editor):
    """Keep the newest current row per user before partial uniqueness lands."""

    Subscription = apps.get_model("quickscale_modules_billing", "Subscription")
    db_alias = schema_editor.connection.alias
    user_ids = (
        Subscription.objects.using(db_alias)
        .filter(status__in=CURRENT_SUBSCRIPTION_STATUSES)
        .values_list("user_id", flat=True)
        .distinct()
    )

    for user_id in user_ids:
        current_rows = list(
            Subscription.objects.using(db_alias)
            .filter(user_id=user_id, status__in=CURRENT_SUBSCRIPTION_STATUSES)
            .order_by("-id")
        )
        if len(current_rows) <= 1:
            continue

        survivor = _select_subscription_survivor(current_rows)
        survivor_update_fields = set()

        for duplicate_row in current_rows:
            if duplicate_row.pk == survivor.pk:
                continue

            synced_row = _is_synced_subscription_row(duplicate_row)
            duplicate_row_update_fields = {"status"}

            if synced_row:
                for field_name in FIELDS_TO_MERGE:
                    if _has_value(getattr(survivor, field_name)):
                        continue

                    candidate_value = getattr(duplicate_row, field_name)
                    if not _has_value(candidate_value):
                        continue

                    setattr(survivor, field_name, candidate_value)
                    survivor_update_fields.add(field_name)

                    if field_name == "stripe_subscription_id":
                        duplicate_row.stripe_subscription_id = ""
                        duplicate_row_update_fields.add("stripe_subscription_id")

                duplicate_row.status = "canceled"
            else:
                duplicate_row.status = "incomplete_expired"

            duplicate_row.save(update_fields=sorted(duplicate_row_update_fields))

        if survivor_update_fields:
            survivor.save(update_fields=sorted(survivor_update_fields))


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_billing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="checkout_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="subscription",
            name="stripe_checkout_session_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="status",
            field=models.CharField(
                choices=[
                    ("incomplete", "Incomplete"),
                    ("incomplete_expired", "Incomplete expired"),
                    ("trialing", "Trialing"),
                    ("active", "Active"),
                    ("past_due", "Past due"),
                    ("canceled", "Canceled"),
                    ("unpaid", "Unpaid"),
                    ("paused", "Paused"),
                ],
                default="incomplete",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="stripe_customer_id",
            field=models.CharField(
                blank=True, db_index=True, max_length=255, null=True
            ),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="stripe_subscription_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(
            reconcile_duplicate_current_subscriptions,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    models.Q(("stripe_subscription_id__isnull", False)),
                    ~models.Q(("stripe_subscription_id", "")),
                ),
                fields=("stripe_subscription_id",),
                name="quickscale_billing_unique_stripe_subscription_id_when_populated",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    models.Q(("stripe_checkout_session_id__isnull", False)),
                    ~models.Q(("stripe_checkout_session_id", "")),
                ),
                fields=("stripe_checkout_session_id",),
                name="quickscale_billing_unique_stripe_checkout_session_id_present",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=CURRENT_SUBSCRIPTION_STATUSES),
                fields=("user",),
                name="quickscale_billing_unique_current_subscription_per_user",
            ),
        ),
    ]
