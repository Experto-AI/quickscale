# QuickScale Notifications Module

Transactional email foundation for QuickScale projects.

## Overview

- A read-only operational settings snapshot backed by Django settings and environment
  variables.
- App-owned template rendering with context validation.
- Recipient-granular delivery tracking, including per-delivery event history.
- Django email delivery compatible with the Anymail Resend backend.
- Signed, replay-safe webhook ingestion for delivery events.
- A declarative `module.yml` manifest with a flat `QUICKSCALE_NOTIFICATIONS_*` settings surface.

The authoritative configuration surfaces remain generated Django settings and environment
variables. The database snapshot exists for operator visibility and auditability only.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_NOTIFICATIONS_ENABLED` | Enable the notifications module runtime. Safe local backends remain valid when live delivery is not configured. |
| `provider` | string | `resend` | `QUICKSCALE_NOTIFICATIONS_PROVIDER` | Transactional email provider backing the notifications runtime. |
| `sender_name` | string | `QuickScale` | `QUICKSCALE_NOTIFICATIONS_SENDER_NAME` | Display name used for outbound transactional email. |
| `sender_email` | string | `noreply@example.com` | `QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL` | Authoritative sender email address used for outbound transactional email. The default placeholder must be overridden before live delivery is configured. |
| `reply_to_email` | string | `""` | `QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL` | Optional reply-to email address for transactional messages. |
| `resend_domain` | string | `""` | `QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN` | Verified Resend sending domain for operational visibility. |
| `resend_api_key_env_var` | string | `RESEND_API_KEY` | `QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR` | Environment-variable name containing the Resend API key. |
| `webhook_secret_env_var` | string | `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET` | `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR` | Environment-variable name containing the shared webhook signing secret. |
| `default_tags` | list | `["quickscale", "transactional"]` | `QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS` | Provider-visible default tags from the approved non-sensitive allowlist. |
| `allowed_tags` | list | `["quickscale", "transactional", "notifications", "auth", "forms", "ops", "testing"]` | `QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS` | Non-sensitive allowlist for provider-visible tags. |
| `webhook_ttl_seconds` | integer | `300` | `QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS` | Maximum accepted webhook timestamp skew in seconds. |

Retired option keys (`resend_api_key`, `webhook_secret`) are refused by name; use the
`_env_var` options to reference environment variables instead.

## Public surface

### Models and admin

- `NotificationSettings` is the read-only settings snapshot.
- `NotificationMessage` records one outbound message with its rendered content and status.
- `NotificationDelivery` records per-recipient delivery state.
- `NotificationDeliveryEvent` records the provider events that advanced a delivery.
- The admin registers the settings, message, and delivery models as read-only surfaces for
  operators.

### Services

- `send_notification()` sends one transactional email and `dispatch_notification_message()`
  fans a stored message out to its recipients.
- `render_notification()` renders a named template definition with a validated context.
- `load_settings_snapshot()` and `ensure_default_settings()` expose the operational settings
  snapshot.
- `build_webhook_signature_headers()` and `ingest_webhook_event()` implement signature
  verification and replay-safe event ingestion.
- `sanitize_provider_tags()` and `sanitize_provider_metadata()` restrict what reaches the
  provider.

The module's own errors live in `exceptions.py` under `NotificationError`, with
`NotificationConfigurationError`, `NotificationDisabledError`, `NotificationTemplateError`,
`NotificationValidationError`, `NotificationWebhookError`, and
`NotificationWebhookSignatureError` for callers to catch.

Templates live under `templates/quickscale_notifications/email/` (`base_email.html`
plus subject/body pairs for generic messages, form submissions, and organization invitations).

### Startup checks

Startup checks run through the shared `quickscale_core.runtime` helper: the module's declared
settings are validated against the schema `quickscale apply` writes, and a secret a switched-on
feature needs — the webhook signing secret while notifications are enabled, the Resend API key
while the live Resend backend is active — fails startup when empty.

## URLs

`quickscale apply` mounts the module at `notifications/` (its manifest `url_includes` entry);
the single route is:

| URL name | Path | View |
|----------|------|------|
| `quickscale_notifications:resend_webhook` | `notifications/webhooks/resend/` | Signed, replay-safe delivery-event ingestion |

## Management commands

This module ships no management commands.

## Operations

- **Sender identity:** override `sender_email` before configuring live delivery; the default
  placeholder is refused by validation when live Resend delivery is configured.
- **Secrets:** the API key and webhook secret are read from the environment variables named by
  `resend_api_key_env_var` and `webhook_secret_env_var`; set the real values in the deployment
  environment, never in `quickscale.yml`.
- **Webhook endpoint:** point the Resend webhook at `notifications/webhooks/resend/` and use
  the same signing secret the `webhook_secret_env_var` names. Events outside
  `webhook_ttl_seconds` of clock skew are refused, and events are deduplicated for replay
  safety.
- **Provider tags:** only tags in `allowed_tags` reach the provider; `default_tags` must be a
  subset of that allowlist.
- **Delivery observability:** message and delivery rows, with their event history, are the
  operator's view of what was sent; the settings snapshot is read-only and cannot change
  runtime behavior.

## Extending

- Modules and projects send email through notifications' services instead of Django's email
  helpers, so delivery tracking and provider configuration stay in one place.
- Add a template definition under `templates/quickscale_notifications/email/` plus a
  `NotificationTemplateDefinition` to expose a new message shape.
