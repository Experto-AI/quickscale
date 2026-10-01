# QuickScale Forms Module

Generic, customizable form builder module for QuickScale Django projects. It lets you define,
render, and manage any kind of form (contact, feedback, support, newsletter) through a
data-driven admin interface — no code changes required to add or modify forms.

## Overview

- Data-driven forms: forms, fields, and validation live in the database and are managed in the
  Django admin.
- Four built-in presets (`contact`, `newsletter`, `feedback`, `support`) are created by the
  initial migration.
- A public schema and submit API, and a staff-only submission-management API.
- Honeypot spam protection and per-IP rate limiting.
- Tenant-scoped: submissions belong to an organization through orgs' `TenantModel`.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `submissions_per_page` | integer | `25` | `QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE` | Number of submissions shown per page in the staff submissions API. |
| `spam_protection_enabled` | boolean | `true` | `QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED` | Enable honeypot spam protection globally for forms that also keep their per-form flag enabled. |
| `rate_limit` | string | `5/hour` | `QUICKSCALE_FORMS_RATE_LIMIT` | Throttle rate for form submissions, per IP. Format: `<count>/<period>`. |
| `retention_days` | integer | `365` | `QUICKSCALE_FORMS_RETENTION_DAYS` | Default days assigned to newly created forms before anonymization (`0` = keep forever); existing forms keep their stored value. |
| `api_enabled` | boolean | `true` | `QUICKSCALE_FORMS_API_ENABLED` | Enable REST API endpoints for staff submission management. |

A manual installation must set these settings explicitly; generated projects have them rendered
by `quickscale apply`. The public schema and submit endpoints stay available regardless of
`QUICKSCALE_FORMS_API_ENABLED`.

## Public surface

### API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `forms/api/{slug}/` | Public | Fetch form schema |
| `POST` | `forms/api/{slug}/submit/` | Public | Submit form data |
| `GET` | `forms/api/admin/forms/` | Staff+ | List forms with submission counts |
| `GET` | `forms/api/admin/forms/{id}/submissions/` | Staff+ | List submissions |
| `GET/PATCH` | `forms/api/admin/forms/{id}/submissions/{sub_id}/` | Staff+ | Submission detail/update |
| `GET` | `forms/api/admin/forms/{id}/submissions/export/` | Staff+ | Download CSV |

Every error answers the shared `{"error": {"code", "message", "fields"}}` shape (`fields` only
for validation errors), produced by `quickscale_core.runtime.conventions.exception_handler` —
the handler `quickscale apply` installs in `REST_FRAMEWORK`; a manual installation must install
it the same way (see Operations).

Forms emits the `quickscale_forms_submitted` analytics event for each accepted submission
through analytics' generic `capture_event`, guarded on the analytics module being installed and
enabled. The module's public service surface (`services.py`) names that event.

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
(`ScopedRateThrottle` with `QUICKSCALE_FORMS_RATE_LIMIT`) adds a second layer of protection.

### Email notifications

Set `notify_emails` on a `Form` to receive an email on every legitimate (non-spam) submission.
The message is dispatched through the notifications module's `send_notification` service
(tagged `forms`, workflow `form-submission`) so delivery is tracked; the module declares
`notifications` in `required_modules` and carries no fallback sender. The send runs only after
the submission commits, so a rolled-back submission sends nothing; delivery failures are logged
and never block submission processing.

### Staff access model

Staff-level access (`forms/api/admin/forms/*`) follows a retained-role model; an active organization
selection is required for regular staff to see any data.

| Role | Org context | Behavior |
|------|-------------|----------|
| Superuser | After org selection | Cross-tenant SELECT via `operator_access` (audited). All `GET`/list operations run inside `operator_access`, which is gated to superusers and logged at `INFO` level. `PATCH` saves inside the target submission's `org_scope`. Without an active org selected, the middleware redirects to `/orgs/` — same as regular staff. |
| Regular staff | Active org selected | Data is scoped via RLS to the request's active organization; only records belonging to that org are visible. |
| Regular staff | None | Fail-closed: `TenantMiddleware` redirects to `/orgs/` before view execution (302). View-unit tests without middleware show an empty list or 404. No data is leaked. |
| Anonymous | N/A | Denied (`403 Forbidden`). |

The `QUICKSCALE_FORMS_API_ENABLED` setting is checked on every admin request before any role-specific
logic — a disabled API returns 404 for both superuser and regular staff.

## URLs

`quickscale apply` mounts the module at `forms/` (its manifest `url_includes` entry); the
module's paths are:

| URL name | Path | View |
|----------|------|------|
| `quickscale_forms:form_list` | `forms/` | Public form index (React mount point) |
| `quickscale_forms:form_page` | `forms/<slug>/` | Public form page (React mount point) |
| `quickscale_forms:form_schema` | `forms/api/<slug>/` | Public form schema |
| `quickscale_forms:form_submit` | `forms/api/<slug>/submit/` | Public submission endpoint |
| `quickscale_forms:admin_form_list` | `forms/api/admin/forms/` | Staff form list |
| `quickscale_forms:admin_submission_list` | `forms/api/admin/forms/<pk>/submissions/` | Staff submission list |
| `quickscale_forms:admin_submission_detail` | `forms/api/admin/forms/<pk>/submissions/<sub_pk>/` | Staff submission detail |
| `quickscale_forms:admin_submission_export` | `forms/api/admin/forms/<pk>/submissions/export/` | Staff CSV export |

## Management commands

- `quickscale_forms_seed_presets` — creates the four built-in form presets. Idempotent and safe
  to run multiple times.
- `quickscale_forms_anonymize_submissions` — nulls `ip_address` and clears `user_agent` for
  submissions older than each form's `data_retention_days`; a GDPR compliance helper.

## Operations

Add the module through QuickScale:

```bash
quickscale plan --add forms
quickscale apply
```

A manual installation adds `rest_framework`, `django_filters`, `quickscale_modules_notifications`
(forms requires it), and `quickscale_modules_forms` to `INSTALLED_APPS`, mounts the module's
URLs, sets `REST_FRAMEWORK["EXCEPTION_HANDLER"]` to
`quickscale_core.runtime.conventions.exception_handler`, and runs `python manage.py migrate`. A fresh
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

Schedule `python manage.py quickscale_forms_anonymize_submissions` periodically — daily is a
reasonable interval — through your cron or platform scheduler; the module ships no scheduler,
and anonymization runs only when the command is invoked.

## Extending

- The module provides a React mount point template: the Django template renders
  `<div id="form-root" data-form-slug="contact"></div>`, and your React entry point mounts the
  `FormRenderer` component into it, reading the slug from the `data-*` attributes. The
  generated project ships `FormRenderer` and `FormFieldRenderer` in `src/components/forms/`
  and the `useFormSchema` hook in `src/hooks/`.
