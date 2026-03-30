"""Data models for the QuickScale notifications module."""

from django.db import models


class NotificationSettings(models.Model):
    """Read-only operational snapshot of the authoritative notification settings."""

    key = models.CharField(
        max_length=32,
        unique=True,
        default="default",
        editable=False,
    )
    enabled = models.BooleanField(default=True)
    provider_name = models.CharField(max_length=32, default="resend")
    email_backend = models.CharField(max_length=255, default="")
    sender_name = models.CharField(max_length=255, default="QuickScale")
    sender_email = models.EmailField(max_length=255)
    reply_to_email = models.EmailField(max_length=255, blank=True)
    resend_domain = models.CharField(max_length=255, blank=True)
    resend_api_key_env_var = models.CharField(max_length=255, default="RESEND_API_KEY")
    webhook_secret_env_var = models.CharField(
        max_length=255,
        default="QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET",
    )
    default_tags = models.JSONField(default=list, blank=True)
    allowed_tags = models.JSONField(default=list, blank=True)
    webhook_ttl_seconds = models.PositiveIntegerField(default=300)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_notifications"
        verbose_name = "Notification settings"
        verbose_name_plural = "Notification settings"

    def __str__(self) -> str:
        return f"Notification settings ({self.provider_name})"


class NotificationMessage(models.Model):
    """Logical notification send request rendered by the module."""

    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_PARTIAL, "Partial failure"),
        (STATUS_FAILED, "Failed"),
    ]

    template_key = models.CharField(max_length=100)
    subject = models.CharField(max_length=255)
    from_email = models.CharField(max_length=255)
    reply_to_email = models.CharField(max_length=255, blank=True)
    rendered_text = models.TextField()
    rendered_html = models.TextField(blank=True)
    context_json = models.JSONField(default=dict, blank=True)
    provider_name = models.CharField(max_length=32, default="resend")
    tags_json = models.JSONField(default=list, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    last_error = models.TextField(blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    last_event_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_notifications"
        ordering = ["-created_at"]
        verbose_name = "Notification message"
        verbose_name_plural = "Notification messages"

    def __str__(self) -> str:
        return f"{self.template_key} ({self.status})"


class NotificationDelivery(models.Model):
    """Recipient-granular delivery tracking for a logical notification message."""

    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_BOUNCED = "bounced"
    STATUS_COMPLAINED = "complained"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_FAILED, "Failed"),
        (STATUS_BOUNCED, "Bounced"),
        (STATUS_COMPLAINED, "Complained"),
    ]

    message = models.ForeignKey(
        NotificationMessage,
        related_name="deliveries",
        on_delete=models.CASCADE,
    )
    recipient_email = models.EmailField(max_length=255)
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    last_event_type = models.CharField(max_length=64, blank=True)
    failure_reason = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    last_event_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_notifications"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "recipient_email"],
                name="quickscale_notifications_unique_message_recipient",
            )
        ]
        verbose_name = "Notification delivery"
        verbose_name_plural = "Notification deliveries"

    def __str__(self) -> str:
        return f"{self.recipient_email} ({self.status})"


class NotificationDeliveryEvent(models.Model):
    """Provider event history for a recipient delivery."""

    delivery = models.ForeignKey(
        NotificationDelivery,
        related_name="events",
        on_delete=models.CASCADE,
    )
    provider_event_id = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=64)
    provider_message_id = models.CharField(max_length=255, blank=True)
    status_after = models.CharField(max_length=20)
    payload_json = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "quickscale_modules_notifications"
        ordering = ["received_at"]
        verbose_name = "Notification delivery event"
        verbose_name_plural = "Notification delivery events"

    def __str__(self) -> str:
        if self.provider_event_id:
            return f"{self.event_type} ({self.provider_event_id})"
        return f"{self.event_type} ({self.idempotency_key})"
