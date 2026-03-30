# QuickScale Notifications Module

Transactional email foundation for QuickScale.

This package provides:

- a read-only operational settings snapshot backed by Django settings and env vars
- app-owned template rendering with context validation
- recipient-granular delivery tracking
- Django email delivery compatible with the Anymail Resend backend
- signed, replay-safe webhook ingestion for delivery events

The authoritative configuration surfaces remain generated Django settings and environment variables. The database snapshot exists for operator visibility and auditability only.
