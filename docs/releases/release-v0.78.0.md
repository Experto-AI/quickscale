# Release v0.78.0 - Notifications Module

**Release Date:** 2026-03-30
**Status:** ✅ Released

## Summary

This release ships **`quickscale_modules.notifications`** and starts QuickScale's post-MVP expansion release line. The new module provides a transactional email foundation built around app-owned template rendering, a read-only operational settings snapshot backed by generated Django settings and environment variables, recipient-granular delivery tracking, Django email compatibility with the Anymail Resend backend, signed replay-safe webhook ingestion for delivery events, and generated-project wiring through QuickScale's planner and apply flows.

**Related docs:** [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md) | [Release Archive](../technical/release-archive.md)

## Completed Tasks

- [x] Added the `quickscale_modules.notifications` package as QuickScale's first post-MVP expansion module.
- [x] Standardized the initial delivery path around Django email compatibility with the Anymail Resend backend.
- [x] Added app-owned email rendering, context validation, recipient-granular delivery tracking, and signed webhook ingestion.
- [x] Kept notifications configuration authoritative in generated Django settings and environment variables, with the database snapshot limited to read-only operator visibility.
- [x] Wired notifications through planner or apply configuration, generated settings, `.env.example` synchronization, and forms submission delivery.

## What's New

### Features

- **Transactional Email Foundation**: QuickScale now ships a first-party notifications module for auth flows, forms follow-up, admin or ops messages, and future post-MVP modules that need email delivery.
- **App-Owned Rendering**: Notification content is rendered inside the Django application so templates, layout behavior, and context validation stay testable and portable.
- **Recipient-Granular Tracking**: Delivery tracking is recorded per recipient instead of per bulk send, making provider IDs, event history, and failures easier to audit.
- **Signed Webhook Ingestion**: Delivery-event webhooks are replay-safe and verified before status updates are written into QuickScale-owned records.
- **Read-Only Operational Snapshot**: Operator-facing settings visibility comes from a database snapshot backed by generated settings and environment variables rather than a second mutable configuration surface.
- **Planner and Apply Wiring**: Generated projects can configure notifications through QuickScale's module flows, which manage installed apps, URLs, environment-variable placeholders, and email-backend ownership when notifications is enabled.
- **Forms Integration**: Forms submissions can now fan out through tracked notifications when the module is installed and enabled, while preserving the existing untracked fallback path when it is absent or disabled.

### Improvements

- **Post-MVP Release Line Begins**: v0.78.0 is the first published release in QuickScale's post-MVP expansion track.
- **Current Module Set Updated**: Public docs now reflect notifications alongside auth, backups, blog, crm, forms, listings, and storage as the current first-party module set.
- **Runtime Guardrails**: Production-targeted notifications configurations now fail loudly when live-delivery requirements are incomplete instead of silently falling back to console email.

## Breaking Changes

None — this is a new additive module and release-metadata synchronization cut.

## Validation

- ✅ Repository quality gate previously passed via `make check`
- ✅ Public release docs and package metadata are synchronized to `0.78.0`

## Validation Commands

```bash
make check
```

## Deferred Follow-up

The following items remain deferred to later post-MVP releases:

- inbound or reply workflows
- provider-hosted templates, broadcast or newsletter tooling, and multi-provider failover
- shared async worker extraction if notifications later needs to converge with another recurring background-work consumer
