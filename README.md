# QuickScale Notifications Module

Transactional email foundation for QuickScale projects.

## Overview

- A read-only operational settings snapshot backed by Django settings and environment
  variables.
- App-owned template rendering with context validation.
- Recipient-granular delivery tracking, including per-delivery event history.
- Django email delivery compatible with the Anymail Resend backend.
- Resend Svix-signature-verified, replay-safe webhook ingestion for delivery events.
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
| `webhook_secret_env_var` | string | `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET` | `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR` | Environment-variable name containing the Resend Svix webhook signing secret. |
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
- `NotificationDeliveryEvent` records the accepted provider event receipts for a delivery,
  including a late event whose target status did not advance it.
- The admin registers the settings, message, and delivery models as read-only surfaces for
  operators.

### Services

- `send_notification()` sends one transactional email and `dispatch_notification_message()`
  fans a stored message out to its recipients.
- `render_notification()` renders a named template definition with a validated context.
- `load_settings_snapshot()` and `ensure_default_settings()` expose the operational settings
  snapshot.
- `build_webhook_signature_headers()` signs Svix-style requests for tests, and
  `ingest_webhook_event()` verifies Resend's Svix signature and ingests delivery events
  replay-safely.
- `sanitize_provider_tags()` and `sanitize_provider_metadata()` restrict what reaches the
  provider.

The module's own errors live in `exceptions.py` under `NotificationsError`, with
`NotificationConfigurationError`, `NotificationDisabledError`, `NotificationTemplateError`,
`NotificationValidationError`, `NotificationWebhookError`, and
`NotificationWebhookSignatureError` for callers to catch.

Notifications ships only its own generic template under `templates/quickscale_notifications/email/`.
Every other sender owns its template key (`quickscale_<module>.<purpose>`) and subject/text/HTML
bodies under its own `templates/quickscale_<module>/email/`, declared through the
`notification_templates` capability; `render_notification()` collects every installed sender's
declaration, so notifications names no other module's key or path.

### Startup checks

Startup checks run through the shared `quickscale_core.runtime` helper: the module's declared
settings are validated against the schema `quickscale apply` writes, and a secret a switched-on
feature needs — the webhook signing secret while notifications are enabled, the Resend API key
while the live Resend backend is active — fails startup when empty or unusable; the webhook
signing secret must carry the `whsec_` prefix and decode as base64.

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
- **Secrets:** the API key and webhook secret reach module code as the
  `QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY` and `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET` settings;
  `quickscale apply` renders each one from the environment variable its `resend_api_key_env_var`
  or `webhook_secret_env_var` option names (rule 35), so set the real values in the deployment
  environment, never in `quickscale.yml`.
- **Webhook endpoint:** point the Resend webhook at `notifications/webhooks/resend/` and set the
  environment variable `webhook_secret_env_var` names to Resend's signing secret (the `whsec_…`
  value from the webhook settings). Resend signs each attempt with the Svix `svix-id`,
  `svix-timestamp`, and `svix-signature` headers; the endpoint accepts any advertised `v1`
  signature, refuses events outside `webhook_ttl_seconds` of clock skew, and deduplicates
  retries by `svix-id`.
- **Provider tags:** only tags in `allowed_tags` reach the provider; `default_tags` must be a
  subset of that allowlist.
- **Delivery observability:** message and delivery rows, with their event history, are the
  operator's view of what was sent; the settings snapshot is read-only and cannot change
  runtime behavior.

## Extending

### What QuickScale owns

The module package under `modules/notifications/` — models, migrations, admin, services, the
Resend adapter, webhook ingestion, and its generic email template — its manifest options, and
the managed wiring `quickscale apply` writes (`<package>/settings/modules.py`,
`<package>/urls_modules.py`).

### What the project owns

`quickscale.yml` values for the options above, deployment secrets and the Resend account, the
project's own sender modules and their email templates under
`templates/quickscale_<module>/email/`, and all application data.

### Update-safe customizations

Change option values, send through the module's services instead of Django's email helpers, and
declare a `notification_templates` capability on a project-owned `AppConfig`; the project
supplies the template bodies and notifications collects the declaration at render time. Project
templates are never rewritten by an update.

### Structured extension points

`send_notification()`, `dispatch_notification_message()`, `render_notification()`, the settings
snapshot accessors, the webhook signature/ingestion helpers, and the provider sanitizers are
the documented service surface. A sending module owns its template key
(`quickscale_<module>.<purpose>`) and a `NotificationTemplateDefinition`; notifications refuses
an unknown key. The signed, replay-safe Resend webhook endpoint is the transport contract.

### Upgrade expectations

Tier 1 settings, services, capabilities, and the webhook contract survive normal module updates.
Never edit `modules/notifications/`: `quickscale update` refuses a local edit unless
`--allow-local-changes`, and managed wiring is regenerated.
