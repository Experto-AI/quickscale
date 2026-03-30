"""Initial migration for the QuickScale notifications module."""

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="NotificationMessage",
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
                ("template_key", models.CharField(max_length=100)),
                ("subject", models.CharField(max_length=255)),
                ("from_email", models.CharField(max_length=255)),
                ("reply_to_email", models.CharField(blank=True, max_length=255)),
                ("rendered_text", models.TextField()),
                ("rendered_html", models.TextField(blank=True)),
                ("context_json", models.JSONField(blank=True, default=dict)),
                ("provider_name", models.CharField(default="resend", max_length=32)),
                ("tags_json", models.JSONField(blank=True, default=list)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("sent", "Sent"),
                            ("partial", "Partial failure"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("last_error", models.TextField(blank=True)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("last_event_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Notification message",
                "verbose_name_plural": "Notification messages",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="NotificationSettings",
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
                    "key",
                    models.CharField(
                        default="default",
                        editable=False,
                        max_length=32,
                        unique=True,
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("provider_name", models.CharField(default="resend", max_length=32)),
                ("email_backend", models.CharField(default="", max_length=255)),
                ("sender_name", models.CharField(default="QuickScale", max_length=255)),
                ("sender_email", models.EmailField(max_length=255)),
                ("reply_to_email", models.EmailField(blank=True, max_length=255)),
                ("resend_domain", models.CharField(blank=True, max_length=255)),
                (
                    "resend_api_key_env_var",
                    models.CharField(default="RESEND_API_KEY", max_length=255),
                ),
                (
                    "webhook_secret_env_var",
                    models.CharField(
                        default="QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET",
                        max_length=255,
                    ),
                ),
                ("default_tags", models.JSONField(blank=True, default=list)),
                ("allowed_tags", models.JSONField(blank=True, default=list)),
                ("webhook_ttl_seconds", models.PositiveIntegerField(default=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Notification settings",
                "verbose_name_plural": "Notification settings",
            },
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
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
                ("recipient_email", models.EmailField(max_length=255)),
                (
                    "provider_message_id",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("sent", "Sent"),
                            ("delivered", "Delivered"),
                            ("failed", "Failed"),
                            ("bounced", "Bounced"),
                            ("complained", "Complained"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("last_event_type", models.CharField(blank=True, max_length=64)),
                ("failure_reason", models.TextField(blank=True)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("last_event_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="deliveries",
                        to="quickscale_modules_notifications.notificationmessage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Notification delivery",
                "verbose_name_plural": "Notification deliveries",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="NotificationDeliveryEvent",
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
                ("provider_event_id", models.CharField(blank=True, max_length=255)),
                ("idempotency_key", models.CharField(max_length=64, unique=True)),
                ("event_type", models.CharField(max_length=64)),
                ("provider_message_id", models.CharField(blank=True, max_length=255)),
                ("status_after", models.CharField(max_length=20)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                (
                    "delivery",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="events",
                        to="quickscale_modules_notifications.notificationdelivery",
                    ),
                ),
            ],
            options={
                "verbose_name": "Notification delivery event",
                "verbose_name_plural": "Notification delivery events",
                "ordering": ["received_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="notificationdelivery",
            constraint=models.UniqueConstraint(
                fields=("message", "recipient_email"),
                name="quickscale_notifications_unique_message_recipient",
            ),
        ),
    ]
