# QuickScale Forms Module

Generic, customizable form builder module for QuickScale Django projects. It lets you define,
render, and manage any kind of form (contact, feedback, support, newsletter) through a
data-driven admin interface — no code changes required to add or modify forms.

## Overview

- Data-driven forms: forms, fields, and validation live in the database and are managed in the
  Django admin.
- Four built-in presets (`contact`, `newsletter`, `feedback`, `support`) are created by the
  initial migration.
- A public schema and submit API, and a member-role submission-management API.
- Honeypot spam protection and per-IP rate limiting.
- Tenant-scoped: submissions belong to an organization through orgs' `TenantModel`.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_FORMS_ENABLED` | Mount the module's pages and APIs. Off keeps the app and its data installed, serves none of its URLs, and stops the scheduled retention command. |
| `submissions_per_page` | integer | `25` | `QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE` | Number of submissions shown per page in the admin submissions API. |
| `per_page` | integer | `25` | `QUICKSCALE_FORMS_PER_PAGE` | Number of forms per page in the admin form list API. |
| `spam_protection_enabled` | boolean | `true` | `QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED` | Enable honeypot spam protection globally for forms that also keep their per-form flag enabled. |
| `rate_limit` | string | `5/hour` | `QUICKSCALE_FORMS_RATE_LIMIT` | Throttle rate for form submissions, per IP. Format: `<count>/<period>`. |
| `retention_days` | integer | `365` | `QUICKSCALE_FORMS_RETENTION_DAYS` | Default days assigned to newly created forms before anonymization (`0` = keep forever); existing forms keep their stored value. |
| `api_enabled` | boolean | `true` | `QUICKSCALE_FORMS_API_ENABLED` | Enable REST API endpoints for organization submission management. |

A manual installation must set these settings explicitly; generated projects have them rendered
by `quickscale apply`. The public schema and submit endpoints stay available regardless of
`QUICKSCALE_FORMS_API_ENABLED`.

## Public surface

### API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `forms/api/{slug}/` | Public | Fetch form schema |
| `POST` | `forms/api/{slug}/submit/` | Public | Submit form data |
| `GET` | `forms/api/admin/forms/` | Viewer+ | List forms with submission counts |
| `GET` | `forms/api/admin/forms/{id}/submissions/` | Viewer+ | List submissions |
| `GET/PATCH` | `forms/api/admin/forms/{id}/submissions/{sub_id}/` | Viewer+ / Member+ | Submission detail (GET) and update (PATCH) |
| `GET` | `forms/api/admin/forms/{id}/submissions/export/` | Viewer+ | Download CSV |

Every error answers the shared `{"error": {"code", "message", "fields"}}` shape (`fields` only
for validation errors), produced by `quickscale_core.runtime.conventions.exception_handler` —
the handler `quickscale apply` installs in `REST_FRAMEWORK`; a manual installation must install
it the same way (see Operations).

Forms emits the `quickscale_forms_submitted` analytics event for each accepted submission
through analytics' generic `capture_event`; `analytics` is declared in `required_modules` and
the capture path asks its `is_enabled()` directly, so a disabled analytics module registers no
emission. The module's public service surface (`services.py`) names that event.

### Built-in form presets

| Slug | Fields |
|------|--------|
| `contact` | full_name, email, company (optional), subject, project_context |
| `newsletter` | full_name, email |
| `feedback` | full_name (optional), email (optional), rating (1–5), message |
| `support` | full_name, email, subject, priority (low/medium/high), description |

### Spam protection

When both the global `QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED` setting and a form's `spam_protection_enabled`
flag are true, the public schema includes a honeypot field (`_hp_name`) and submission
handling treats a populated value as spam while still returning success — preventing bot
enumeration. If either switch is off, `_hp_name` is ignored. Rate limiting
(the scoped throttle with `QUICKSCALE_FORMS_RATE_LIMIT`, keyed by client IP)
adds a second layer of protection.

### Email notifications

Set `notify_emails` on a `Form` to receive an email on every legitimate (non-spam) submission.
The message is dispatched through the notifications module's `send_notification` service
(tagged `forms`, workflow `form-submission`) under the module-owned
`quickscale_forms.submission` template key, declared through notifications'
`notification_templates` capability with the bodies under
`templates/quickscale_forms/email/`, so delivery is tracked; the module declares
`notifications` in `required_modules` and carries no fallback sender. The send runs only after
the submission commits, so a rolled-back submission sends nothing; delivery failures are logged
and never block submission processing, and a skipped send (notifications disabled, spam, or no
recipients) reports a non-`queued` notification status.

### Access model

Admin access (`forms/api/admin/forms/*`) authorizes by the active organization's role; an active
organization selection is required for a regular member to see any data. Reads (list, retrieve,
export) require the `viewer` role and writes (`PATCH`) require the `member` role.

| Role | Org context | Behavior |
|------|-------------|----------|
| Superuser | After org selection | Cross-tenant SELECT via `operator_access` (audited). All `GET`/list operations run inside `operator_access`, which is gated to superusers and logged at `INFO` level. `PATCH` saves inside the target submission's `org_scope`. Without an active org selected, the middleware redirects to `/orgs/`; a direct superuser call with no org context still reaches this audited operator path (`200`). |
| Organization member | Active org selected | Data is scoped via RLS to the request's active organization; only records belonging to that org are visible. Reads need `viewer` or above; writes need `member` or above; a caller below the action's minimum is refused (`403`). |
| Organization member | None | Fail-closed: `TenantMiddleware` redirects to `/orgs/` before view execution (302). A non-superuser view-unit call without org context is refused by the permission (`403`). No data is leaked. |
| Anonymous | N/A | Denied (`403 Forbidden`). |

The `QUICKSCALE_FORMS_API_ENABLED` setting is checked on every admin request before any role-specific
logic — a disabled API returns 404 for every caller.

## URLs

`quickscale apply` mounts the module at `forms/` (its manifest `url_includes` entry); the
module's paths are:

| URL name | Path | View |
|----------|------|------|
| `quickscale_forms:form_list` | `forms/` | Public form index (React mount point) |
| `quickscale_forms:form_page` | `forms/<slug>/` | Public form page (React mount point) |
| `quickscale_forms:form_schema` | `forms/api/<slug>/` | Public form schema |
| `quickscale_forms:form_submit` | `forms/api/<slug>/submit/` | Public submission endpoint |
| `quickscale_forms:admin_form_list` | `forms/api/admin/forms/` | Viewer-role form list |
| `quickscale_forms:admin_submission_list` | `forms/api/admin/forms/<pk>/submissions/` | Viewer-role submission list |
| `quickscale_forms:admin_submission_detail` | `forms/api/admin/forms/<pk>/submissions/<sub_pk>/` | Viewer-role GET / member-role PATCH submission detail |
| `quickscale_forms:admin_submission_export` | `forms/api/admin/forms/<pk>/submissions/export/` | Viewer-role CSV export |

## Management commands

- `quickscale_forms_seed_presets` — creates the four built-in form presets. Idempotent and safe
  to run multiple times.
- `quickscale_forms_anonymize_submissions` — nulls `ip_address` and clears `user_agent` for
  submissions older than each form's `data_retention_days`; a GDPR compliance helper. `--trigger`
  defaults to `manual`; a `scheduled` run refuses while the module is switched off. `--dry-run`
  reports the submissions that would be anonymized without changing them.

## Operations

Add the module through QuickScale:

```bash
quickscale plan --add forms
quickscale apply
```

A manual installation adds `rest_framework`, `django_filters`, `quickscale_modules_analytics`
and `quickscale_modules_notifications` (forms requires both), and `quickscale_modules_forms` to
`INSTALLED_APPS`, defines their declared settings (including `QUICKSCALE_FORMS_*`,
`QUICKSCALE_ANALYTICS_*`, and `QUICKSCALE_NOTIFICATIONS_*`), mounts the module's
URLs, composes `REST_FRAMEWORK` through
`quickscale_core.runtime.settings.compose_rest_framework` (the shared error handler and core's
default throttle classes) with the `quickscale_forms_submit` rate from
`QUICKSCALE_FORMS_RATE_LIMIT` contributed under `DEFAULT_THROTTLE_RATES`, and runs
`python manage.py migrate`. A fresh
`migrate` on a clean database creates the four built-in presets as part of the initial data
migration — no separate seed step is needed on first install. Run
`python manage.py quickscale_forms_seed_presets` to re-create a preset that was manually
deleted or to recover presets in an older database that was not created by the current squashed
migration.

New `Form` rows created after migrations complete — including those created by a manual
`quickscale_forms_seed_presets` run — inherit `QUICKSCALE_FORMS_RETENTION_DAYS` when
`data_retention_days` is omitted. Fresh-install preset rows created by the initial seed
migration hardcode the historical 365-day default and do not inherit the runtime setting.
Existing forms always keep their stored per-row retention window regardless of how they were
created.

Schedule `python manage.py quickscale_forms_anonymize_submissions --trigger scheduled`
periodically — daily is a reasonable interval — through your cron or platform scheduler; the
module ships no scheduler, a scheduled run refuses while the module is switched off, and
anonymization runs only when the command is invoked.

## Extending

### What QuickScale owns

The module package under `modules/forms/` — models, migrations, admin, public and admin APIs,
the retention command, and its templates — its manifest options and derived settings, and the
managed wiring `quickscale apply` writes (`<package>/settings/modules.py`,
`<package>/urls_modules.py`).

### What the project owns

The actual forms, fields, preset choices, and submission data operators create; `quickscale.yml`
values for the options above; project template overrides; the React entry point and components
that consume the schema and submit APIs; and all project-owned apps.

### Update-safe customizations

Change option values, override templates, and mount project React components into the documented
`#form-root` markers with the `data-*` attributes. QuickScale never rewrites user-owned frontend
or template files.

### Structured extension points

The public schema and submit APIs, the submission-management API contract, and the
`quickscale_forms.submission` notification template are the documented surfaces. The form model
is data-driven, so adding or changing a form is configuration in the admin, not code. Forms
emits `quickscale_forms_submitted` through analytics' generic `capture_event` service.

### Upgrade expectations

Tier 1 settings, API contracts, service events, and template overrides survive normal module
updates. Preset rows created by migrations keep their historical values; new rows inherit the
runtime settings. Never edit `modules/forms/`: `quickscale update` refuses a local edit unless
`--allow-local-changes`, and managed wiring is regenerated.

The module provides a React mount point template: the Django template renders
`<div id="form-root" data-form-slug="contact"></div>`, and your React entry point mounts the
`FormRenderer` component into it, reading the slug from the `data-*` attributes. The generated
project ships `FormRenderer` and `FormFieldRenderer` in `src/components/forms/` and the
`useFormSchema` hook in `src/hooks/`.
