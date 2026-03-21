# Release v0.75.0 - Forms Module

**Release Date:** 2026-02-23
**Status:** ✅ Released

## Summary

This release introduces the **`quickscale-module-forms`** package — a generic, fully customizable form-builder module for Django SaaS projects. Developers can define, render, and manage any kind of form (contact, feedback, support, newsletter) through a data-driven admin interface with zero code changes. The primary production use case is contact/inquiry pages with email notifications.

**Related docs:** [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md)

## Completed Tasks

- [x] Added the `quickscale_modules.forms` backend package with data models, serializers, views, admin, and URLs.
- [x] Added React-facing form rendering support and a Django mount-point template for the default React stack.
- [x] Wired the forms module into QuickScale CLI planning and apply flows.
- [x] Added spam protection, rate limiting, notifications, anonymization, and preset-seeding workflows.
- [x] Validated the release with automated tests, linting, and migration checks.

## What's New

### Features

- **Generic Form Builder**: Data-driven `Form` + `FormField` models allow any form structure to be created and managed entirely through the Django admin interface.
- **DRF REST API**:
  - `GET /api/forms/<slug>/schema/` — returns the renderable form schema (public, no auth required).
  - `POST /api/forms/<slug>/submit/` — accepts form submissions (public, throttled at 5/hour per IP).
  - `GET /api/admin/forms/` — admin form list with submission counts.
  - `GET/PATCH /api/admin/submissions/<pk>/` — admin submission detail and status management.
  - `GET /api/admin/submissions/<pk>/export/` — CSV export of all field values for a submission.
- **Honeypot Spam Protection**: Hidden `_hp_name` field check flags submissions as spam automatically with zero user friction.
- **Rate Limiting**: DRF `ScopedRateThrottle` on the submit endpoint (configurable via `FORMS_RATE_LIMIT` in `module.yml`).
- **Custom Field Validation**: Per-field `validation_rules` JSON supports `min_length`, `max_length`, and `regex` constraints via a `make_field_validator()` closure.
- **Email Notifications**: `notify_submission()` sends HTML email to configurable `notify_emails`; name field auto-detection for subject line; graceful failure with logged warning (never crashes a submission).
- **GDPR Anonymization**: `forms_anonymize_submissions` management command nulls `ip_address` and clears `user_agent` for submissions older than `Form.data_retention_days`.
- **Preset Seeding**: `forms_seed_presets` management command creates four starter forms (`contact`, `newsletter`, `feedback`, `support`) idempotently.
- **React Mount Point**: `FormPageView` template (`form_page.html`) provides a Django-rendered page with a `<div id="form-root">` mount point for the React form renderer (v0.74.0 stack).
- **Admin Interface**: `FormAdmin` with submission count column, `mark_active`/`mark_inactive` bulk actions, and audit `created_by` tracking. `FormSubmissionAdmin` with inline field values, spam/read/replied/archived status actions.

### Module Configuration (`module.yml`)

Mutable settings (user-adjustable after apply):
- `FORMS_PER_PAGE` — admin list page size (default: 25)
- `FORMS_SPAM_PROTECTION` — enable/disable honeypot (default: true)
- `FORMS_RATE_LIMIT` — submission rate limit (default: `5/hour`)
- `FORMS_DATA_RETENTION_DAYS` — days before IP anonymization (default: 730)
- `FORMS_SUBMISSIONS_API` — enable/disable public submission API (default: true)

Immutable settings (set at apply time only):
- `storage_backend` — submission storage backend (default: `db`)

## Data Model

```
Form (slug, title, is_active, notify_emails, data_retention_days, created_by)
  └── FormField (name, label, field_type, is_required, is_active, order, validation_rules, placeholder, help_text)

FormSubmission (form[PROTECT], status, is_spam, ip_address, user_agent, submitted_at)
  └── FormFieldValue (submission, field[SET_NULL], field_name, value)
```

Historical data is preserved when fields are deleted: `FormFieldValue.field` uses `SET_NULL` and denormalizes `field_name` at submission time.

## Breaking Changes

None — this is a new additive module with no impact on existing modules.

## Validation

- ✅ 82 tests passing
- ✅ 97.78% coverage (threshold: 90%)
- ✅ `ruff check` — 0 linting errors
- ✅ Migration successfully generated and applied

## Validation Commands

```bash
cd quickscale_modules/forms
poetry install
poetry run pytest          # 82 passed, 97.78% coverage
poetry run ruff check src/ tests/  # 0 errors
```

## Next Steps

- Keep future module-planning work aligned with the active roadmap in [docs/technical/roadmap.md](../technical/roadmap.md).
- Reuse the forms module as a dependency pattern for future feature modules that need public submissions or admin-managed schemas.
- Maintain release-specific follow-up in release documents instead of re-expanding completed scope in the roadmap.
