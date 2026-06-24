import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
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
                ("features", models.JSONField(blank=True, default=list)),
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
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="credit_balance",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
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
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="credit_transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="credit_transactions",
                        to="quickscale_modules_orgs.organization",
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
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "stripe_customer_id",
                    models.CharField(
                        blank=True, db_index=True, max_length=255, null=True
                    ),
                ),
                (
                    "stripe_checkout_session_id",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "status",
                    models.CharField(
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
                ("checkout_expires_at", models.DateTimeField(blank=True, null=True)),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="billing_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="quickscale_modules_billing.plan",
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
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("stripe_subscription_id__isnull", False),
                    models.Q(("stripe_subscription_id", ""), _negated=True),
                ),
                fields=("stripe_subscription_id",),
                name="quickscale_billing_unique_stripe_subscription_id_when_populated",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("stripe_checkout_session_id__isnull", False),
                    models.Q(("stripe_checkout_session_id", ""), _negated=True),
                ),
                fields=("stripe_checkout_session_id",),
                name="quickscale_billing_unique_stripe_checkout_session_id_present",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    models.Q(
                        (
                            "status__in",
                            [
                                "incomplete",
                                "trialing",
                                "active",
                                "past_due",
                                "unpaid",
                                "paused",
                            ],
                        )
                    ),
                ),
                fields=("organization",),
                name="quickscale_billing_unique_current_subscription_per_organization",
            ),
        ),
        migrations.AddConstraint(
            model_name="webhookevent",
            constraint=models.UniqueConstraint(
                fields=("stripe_event_id",),
                name="quickscale_billing_unique_stripe_event_id",
            ),
        ),
    ]
