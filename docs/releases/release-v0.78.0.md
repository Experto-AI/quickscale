# Release v0.78.0 - Notifications Module

**Date:** 2026-03-30 · **Status:** ✅ Released

## Summary

This release ships **`quickscale_modules.notifications`** and adds a transactional email foundation to the published QuickScale stack. The new module provides app-owned template rendering, a read-only operational settings snapshot backed by generated Django settings and environment variables, recipient-granular delivery tracking, Django email compatibility with the Anymail Resend backend, signed replay-safe webhook ingestion for delivery events, and generated-project wiring through QuickScale's planner and apply flows.

## Highlights

### Features

- **Transactional Email Foundation**: QuickScale now ships a first-party notifications module for auth flows, forms follow-up, admin or ops messages, and later QuickScale features that need email delivery.
- **App-Owned Rendering**: Notification content is rendered inside the Django application so templates, layout behavior, and context validation stay testable and portable.
- **Recipient-Granular Tracking**: Delivery tracking is recorded per recipient instead of per bulk send, making provider IDs, event history, and failures easier to audit.
- **Signed Webhook Ingestion**: Delivery-event webhooks are replay-safe and verified before status updates are written into QuickScale-owned records.
- **Read-Only Operational Snapshot**: Operator-facing settings visibility comes from a database snapshot backed by generated settings and environment variables rather than a second mutable configuration surface.
- **Planner and Apply Wiring**: Generated projects can configure notifications through QuickScale's module flows, which manage installed apps, URLs, environment-variable placeholders, and email-backend ownership when notifications is enabled.
- **Forms Integration**: Forms submissions can now fan out through tracked notifications when the module is installed and enabled, while preserving the existing untracked fallback path when it is absent or disabled.

### Improvements

- **Published Stack Expansion**: v0.78.0 adds notifications to the released first-party module line.
- **Current Module Set Updated**: Public docs now reflect notifications alongside auth, backups, blog, crm, forms, listings, and storage as the current first-party module set.
- **Runtime Guardrails**: Production-targeted notifications configurations now fail loudly when live-delivery requirements are incomplete instead of silently falling back to console email.

## Breaking changes

None — this is a new additive module and release-metadata synchronization cut.
