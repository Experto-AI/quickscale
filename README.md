# quickscale-module-forms

Generic, customizable form builder module for QuickScale Django projects. Enables developers to define, render, and manage any kind of form (contact, feedback, support, newsletter) through a data-driven admin interface — no code changes required to add or modify forms.

## Quick Start

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_filters",
    "quickscale_modules_forms",
]
```

### 2. Include URLs

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    # ...
    path("", include("quickscale_modules_forms.urls")),
]
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Seed presets (optional)

```bash
python manage.py forms_seed_presets
```

This seeds four ready-to-use forms: `contact`, `newsletter`, `feedback`, and `support`.

## Configuration

All settings have defaults and can be overridden in your Django settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `FORMS_PER_PAGE` | `25` | Submission page size for the staff `/api/admin/forms/{id}/submissions/` endpoint |
| `FORMS_SPAM_PROTECTION` | `True` | Enable honeypot spam protection |
| `FORMS_RATE_LIMIT` | `"5/hour"` | Throttle rate per IP (format: `count/period`) |
| `FORMS_DATA_RETENTION_DAYS` | `365` | Days before submission anonymization |
| `FORMS_SUBMISSIONS_API` | `True` | Enable the staff admin REST endpoints under `/api/admin/forms/`; when disabled they return `404` |

## REST API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/forms/{slug}/` | Public | Fetch form schema |
| `POST` | `/api/forms/{slug}/submit/` | Public | Submit form data |
| `GET` | `/api/admin/forms/` | Staff | List forms with submission counts |
| `GET` | `/api/admin/forms/{id}/submissions/` | Staff | List submissions |
| `GET/PATCH` | `/api/admin/forms/{id}/submissions/{sub_id}/` | Staff | Submission detail/update |
| `GET` | `/api/admin/forms/{id}/submissions/export/` | Staff | Download CSV |

The staff endpoints above are controlled by `FORMS_SUBMISSIONS_API`. The public schema and submit endpoints remain available regardless of that setting.

## Built-in Form Presets

Run `python manage.py forms_seed_presets` to create:

| Slug | Fields |
|------|--------|
| `contact` | full_name, email, company (optional), subject, project_context |
| `newsletter` | full_name, email |
| `feedback` | full_name (optional), email (optional), rating (1–5), message |
| `support` | full_name, email, subject, priority (low/medium/high), description |

## Management Commands

### `forms_seed_presets`

Creates all four built-in form presets. Idempotent — safe to run multiple times.

```bash
python manage.py forms_seed_presets
```

### `forms_anonymize_submissions`

Anonymizes (nulls `ip_address`, clears `user_agent`) for submissions older than each form's `data_retention_days`. GDPR compliance helper.

```bash
python manage.py forms_anonymize_submissions
```

## React Integration

The module provides a React mount point template. In your React frontend, use the `FormRenderer` component pointing at the API endpoint:

```tsx
// The Django template renders: <div id="form-root" data-form-slug="contact"></div>
// Your React entry point mounts FormRenderer into this element, reading the slug from data-*
```

See the generated project's `src/components/forms/` directory for the React `FormRenderer`, `FormFieldRenderer`, and `useFormSchema` hook.

## Spam Protection

Every form submission checks for a **honeypot field** (`_hp_name`). If it's populated, the submission is silently accepted and marked `is_spam=True` — preventing bot enumeration. Rate limiting (`ScopedRateThrottle`) adds a second layer of protection.

## Email Notifications

Set `notify_emails` on a `Form` to receive an email on every legitimate (non-spam) submission. Uses Django's built-in `send_mail` — configure any email backend. SMTP errors are silently swallowed to avoid blocking form submissions.
