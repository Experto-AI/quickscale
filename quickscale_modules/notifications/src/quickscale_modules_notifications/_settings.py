"""Runtime settings snapshot for the notifications module.

``NotificationSettingsSnapshot`` reads the applied settings once and answers
every runtime question from that immutable view; the admin mirror row is kept
in sync from the same snapshot.  ``services.py`` re-exports this surface
(Module Conventions rule 28).
"""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import formataddr
from typing import Any

from django.conf import settings

from quickscale_modules_notifications._sanitization import _normalize_tag_sequence
from quickscale_modules_notifications.exceptions import NotificationDisabledError
from quickscale_modules_notifications.models import NotificationSettings

_LIVE_RESEND_BACKEND = "anymail.backends.resend.EmailBackend"
_PLACEHOLDER_SENDER_EMAIL = "noreply@example.com"


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_NOTIFICATIONS_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_NOTIFICATIONS_ENABLED)


@dataclass(frozen=True)
class NotificationSettingsSnapshot:
    """Immutable runtime view of the authoritative notification settings."""

    enabled: bool
    provider_name: str
    email_backend: str
    sender_name: str
    sender_email: str
    reply_to_email: str
    resend_domain: str
    resend_api_key_env_var: str
    webhook_secret_env_var: str
    default_tags: tuple[str, ...]
    allowed_tags: tuple[str, ...]
    webhook_ttl_seconds: int

    @classmethod
    def from_model(
        cls, settings_row: NotificationSettings
    ) -> NotificationSettingsSnapshot:
        """Create a snapshot from a database row."""
        return cls(
            enabled=settings_row.enabled,
            provider_name=settings_row.provider_name,
            email_backend=settings_row.email_backend,
            sender_name=settings_row.sender_name,
            sender_email=settings_row.sender_email,
            reply_to_email=settings_row.reply_to_email,
            resend_domain=settings_row.resend_domain,
            resend_api_key_env_var=settings_row.resend_api_key_env_var,
            webhook_secret_env_var=settings_row.webhook_secret_env_var,
            default_tags=_normalize_tag_sequence(settings_row.default_tags),
            allowed_tags=_normalize_tag_sequence(settings_row.allowed_tags),
            webhook_ttl_seconds=settings_row.webhook_ttl_seconds,
        )

    @classmethod
    def from_settings(cls) -> NotificationSettingsSnapshot:
        """Create a snapshot from Django settings.

        Rule 3: every declared value is read directly; apply wrote the
        canonical values and the module's startup check has validated them,
        so the snapshot neither defaults nor coerces.  ``EMAIL_BACKEND`` is
        Django's own setting.
        """
        return cls(
            enabled=bool(settings.QUICKSCALE_NOTIFICATIONS_ENABLED),
            provider_name=str(settings.QUICKSCALE_NOTIFICATIONS_PROVIDER),
            email_backend=str(settings.EMAIL_BACKEND),
            sender_name=str(settings.QUICKSCALE_NOTIFICATIONS_SENDER_NAME),
            sender_email=str(settings.QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL),
            reply_to_email=str(settings.QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL),
            resend_domain=str(settings.QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN),
            resend_api_key_env_var=str(
                settings.QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
            ),
            webhook_secret_env_var=str(
                settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR
            ),
            default_tags=tuple(settings.QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS),
            allowed_tags=tuple(settings.QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS),
            webhook_ttl_seconds=int(
                settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS
            ),
        )

    def as_model_defaults(self) -> dict[str, Any]:
        """Convert the immutable snapshot into model-compatible defaults."""
        return {
            "enabled": self.enabled,
            "provider_name": self.provider_name,
            "email_backend": self.email_backend,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "reply_to_email": self.reply_to_email,
            "resend_domain": self.resend_domain,
            "resend_api_key_env_var": self.resend_api_key_env_var,
            "webhook_secret_env_var": self.webhook_secret_env_var,
            "default_tags": list(self.default_tags),
            "allowed_tags": list(self.allowed_tags),
            "webhook_ttl_seconds": self.webhook_ttl_seconds,
        }

    def resolve_resend_api_key(self) -> str:
        """Resolve the live Resend API key from the applied secret setting (rule 35).

        Rule 3: the applied setting is the only source.  An unset or empty
        setting resolves to no key, and the startup check refuses the enabled
        module rather than this method substituting a runtime fallback.
        """
        return str(settings.QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY).strip()

    def resolve_webhook_secret(self) -> str:
        """Resolve the shared webhook signing secret from the applied setting (rule 35).

        Rule 3: the applied setting is the only source.  An unset or empty
        setting resolves to no secret, and the startup check refuses the
        enabled module rather than this method substituting a runtime
        fallback.
        """
        return str(settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET).strip()

    def live_delivery_enabled(self) -> bool:
        """Return whether the active email backend is the Anymail Resend backend."""
        return self.email_backend.strip() == _LIVE_RESEND_BACKEND

    def formatted_from_email(self) -> str:
        """Return a user-friendly from email value for Django email sending."""
        if self.sender_name.strip():
            return formataddr((self.sender_name.strip(), self.sender_email.strip()))
        return self.sender_email.strip()


def ensure_default_settings() -> NotificationSettings:
    """Ensure the read-only settings snapshot row exists and matches settings."""
    snapshot = NotificationSettingsSnapshot.from_settings()
    defaults = snapshot.as_model_defaults()
    settings_row, _ = NotificationSettings.objects.get_or_create(
        key="default",
        defaults=defaults,
    )
    updated_fields = [
        field_name
        for field_name, value in defaults.items()
        if getattr(settings_row, field_name) != value
    ]
    if updated_fields:
        for field_name in updated_fields:
            setattr(settings_row, field_name, defaults[field_name])
        settings_row.save(update_fields=[*updated_fields, "updated_at"])
    return settings_row


def load_settings_snapshot() -> NotificationSettingsSnapshot:
    """Load the authoritative settings snapshot, keeping the admin row in sync."""
    if NotificationSettings.objects.exists():
        ensure_default_settings()
    return NotificationSettingsSnapshot.from_settings()


def _ensure_notifications_enabled(
    settings_snapshot: NotificationSettingsSnapshot,
) -> None:
    if not settings_snapshot.enabled:
        raise NotificationDisabledError("Notifications module is disabled.")
