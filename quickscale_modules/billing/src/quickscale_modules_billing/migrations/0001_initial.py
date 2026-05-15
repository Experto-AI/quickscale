"""Initial migration for the QuickScale billing module."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(unique=True)),
                ("stripe_price_id", models.CharField(max_length=255, unique=True)),
                ("credits_per_period", models.PositiveIntegerField()),
                ("price_cents", models.PositiveIntegerField()),
                ("currency", models.CharField(default="usd", max_length=3)),
                (
                    "billing_interval",
                    models.CharField(
                        choices=[
                            ("monthly", "Monthly"),
                            ("yearly", "Yearly"),
                            ("one_time", "One-time"),
                        ],
                        default="monthly",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CreditBalance",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("balance", models.IntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credit_balance",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CreditTransaction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("amount", models.IntegerField()),
                (
                    "transaction_type",
                    models.CharField(
                        choices=[
                            ("plan", "Plan"),
                            ("purchase", "Purchase"),
                            ("usage", "Usage"),
                            ("refund", "Refund"),
                            ("adjustment", "Adjustment"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "stripe_event_id",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                (
                    "stripe_object_id",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                ("stripe_reference_data", models.JSONField(blank=True, default=dict)),
                ("description", models.TextField(blank=True)),
                ("balance_after", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credit_transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "stripe_subscription_id",
                    models.CharField(max_length=255, unique=True),
                ),
                ("stripe_customer_id", models.CharField(db_index=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("incomplete", "Incomplete"),
                            ("active", "Active"),
                            ("past_due", "Past due"),
                            ("canceled", "Canceled"),
                            ("unpaid", "Unpaid"),
                        ],
                        default="incomplete",
                        max_length=32,
                    ),
                ),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="quickscale_modules_billing.plan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("stripe_event_id", models.CharField(db_index=True, max_length=255)),
                ("event_type", models.CharField(max_length=100)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed", models.BooleanField(default=False)),
                ("processing_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="webhookevent",
            constraint=models.UniqueConstraint(
                fields=("stripe_event_id",),
                name="quickscale_billing_unique_stripe_event_id",
            ),
        ),
    ]
