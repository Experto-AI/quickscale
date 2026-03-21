# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Timeline & Tasks)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Release Archive](release-archive.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document outlines the development timeline, implementation phases, and specific tasks for building QuickScale.

**Content Guidelines:**
- Organize tasks by phases with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

**What to Add Here:**
- New development phases and milestone planning
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

**What NOT to Add Here:**
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- Technical specifications or architectural decisions (belongs in decisions.md)
- User documentation or getting started guides (belongs in README.md)
- Directory structures or scaffolding details (belongs in scaffolding.md)

## Broad Overview of the Roadmap

QuickScale follows an evolution-aligned roadmap that starts as a personal toolkit and potentially evolves into a community platform based on real usage and demand.

**Evolution Strategy:** Personal toolkit first, community platform later. See [quickscale.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first).


**Roadmap Phases:**

1. **Phase 1: Foundation + Core Modules (React Theme Default)** 🚧 _In Progress_
   - ✅ Theme system infrastructure and split branch management (v0.61.0-v0.62.0)
   - ✅ Auth module (v0.63.0) - production-ready with django-allauth
   - ✅ Listings module (v0.67.0) - generic base for vertical themes
   - ✅ Plan/Apply System core (v0.68.0-v0.70.0) - Terraform-style configuration
   - ✅ **Plan/Apply System complete** (v0.71.0) - Module manifests & config mutability
   - ✅ Plan/Apply Cleanup (v0.72.0) - Remove legacy init/embed commands
   - ✅ CRM module (v0.73.0) - native Django CRM app (API-only)
   - ✅ **React Default Theme** (v0.74.0) - React + shadcn/ui as default
   - ✅ **Forms module** (v0.75.0) - generic form builder with CLI integration ✅ Complete
  - 🚧 Storage module (v0.76.0) - cloud file hosting, media storage adapters, CDN integration
  - 📋 Social & Link Tree module (v0.77.0) - social links page + media embeds
  - 📋 Listings Theme (v0.78.0) - React frontend for property listings (sell/rent)
  - 📋 CRM Theme (v0.79.0) - React frontend for CRM module
  - 📋 Billing module (v0.80.0) - Stripe integration
  - 📋 Teams module (v0.81.0) - multi-tenancy

2. **Phase 2: Additional Themes (Secondary Options)** 📋 _Planned_
  - 📋 HTMX theme with Alpine.js (v0.82.0+) - alternative for progressive enhancement
   - HTML theme remains as secondary option (simpler projects)

3. **Phase 3: Expand Features (All Themes)** 📋 _Planned_
  - 📋 Notifications module with email infrastructure (v0.83.0)
  - 📋 Advanced module management features (v0.84.0)
  - 📋 Workflow validation and real-world testing (v0.85.0)

4. **Phase 4: Community Platform (Optional v1.0.0+)** 📋 _Future_
   - 📋 PyPI package distribution
   - 📋 Theme package system
   - 📋 Marketplace and community features

**Legend:**
- ✅ = Completed
- 🚧 = In Progress
- 📋 = Planned/Not Started

**Key Milestones:**
- **v0.71.0:** Plan/Apply System Complete ✅
- **v0.72.0:** Plan/Apply Cleanup (remove legacy commands) ✅
- **v0.74.0:** React Default Theme (React + shadcn/ui) ✅
- **v0.75.0:** Forms Module (generic form builder with DRF API, spam protection, GDPR anonymization) ✅
- **v0.76.0:** Storage Module (cloud file hosting + CDN-ready media infrastructure) 🎯
- **v0.78.0:** Real Estate MVP (static + listings + social links) 🎯
- **v0.81.0:** SaaS Feature Parity (auth, billing, teams) 🎯
- **v1.0.0+:** Community platform (if demand exists)

**Status:**
- **Current Status:** v0.75.0 — Forms Module ✅ Complete
- **In Progress:** v0.76.0 — Storage Module
- **Next Milestone:** v0.78.0 - Real Estate MVP
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.81.0 - auth, billing, teams modules complete

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)

## ROADMAP

List of upcoming releases with detailed implementation tasks:

---

### v0.75.0: `quickscale_modules.forms` - Generic Forms Module

**Status**: ✅ Complete — Backend + React frontend + CLI integration done

**Strategic Context**: A generic, fully customizable form-builder module for Django SaaS projects. Enables developers to define, render, and manage any kind of form (contact, feedback, support, newsletter) through a data-driven admin interface, with no code changes required to add or modify forms. The first production use case is the **experto.ai/contact** page — a professional inquiry form collecting Name, Email, Company, Subject, and Project Context, with email notifications to the site owner.

**Prerequisites**:
- ✅ React Default Theme (v0.74.0)
- ✅ Auth Module (v0.63.0) — optional dependency; anonymous submissions must also work

---

#### Implementation Checklist

**Backend**:
- [x] Data Models (`Form`, `FormField`, `FormSubmission`, `FormFieldValue` + migration)
- [x] REST API Endpoints (schema, submit, admin CRUD, CSV export)
- [x] Serializers (`FormFieldSerializer`, `FormSchemaSerializer`, `FormSubmissionCreateSerializer`, admin serializers)
- [x] Views (`FormSchemaAPIView`, `FormSubmitAPIView`, admin views, `AdminSubmissionExportView`, `FormPageView`)
- [x] Django Admin (`FormAdmin` + `FormFieldInline`, `FormSubmissionAdmin` + `FormFieldValueInline`)
- [x] URL Configuration (`app_name = "quickscale_forms"`)
- [x] Spam Protection — honeypot (`_hp_name`) + `ScopedRateThrottle` (`throttles.py`)
- [x] Email Notifications (`notifications.py` — `notify_submission()` helper + email templates)
- [x] Data retention management command (`forms_anonymize_submissions`)
- [x] Built-in presets management command (`forms_seed_presets`: contact, newsletter, feedback, support)
- [x] `module.yml` manifest
- [x] Templates (`form_page.html` React mount point, `form_email.html` notification template)

**React Frontend** (`src/components/forms/`):
- [x] `FormRenderer` — dynamic form component (TanStack Query + React Hook Form + Zod)
- [x] `FormFieldRenderer` — field type switch (shadcn/ui `Input`, `Textarea`, `Select`, `Checkbox`, `RadioGroup`)
- [x] `FormSuccess` — success message display
- [x] `useFormSchema(slug)` — TanStack Query hook

**New shadcn/ui components added to showcase_react theme**:
- [x] `components/ui/textarea.tsx` — Textarea input
- [x] `components/ui/select.tsx` — Select dropdown (Radix)
- [x] `components/ui/checkbox.tsx` — Checkbox (Radix)
- [x] `components/ui/radio-group.tsx` — Radio group (Radix)
- [x] `components/ui/form.tsx` — Form wrapper (React Hook Form integration)

**Route integration**:
- [x] `pages/FormsPage.tsx` — SPA page at `/forms/:slug`
- [x] `App.tsx` — `/forms/:slug` route added
- [x] `Dashboard.tsx` — Forms module card added to installed modules grid

**Testing**:
- [x] `test_models.py` — Form/Field CRUD, ordering, submission creation, value snapshot
- [x] `test_serializers.py` — schema serialization, dynamic submission validation
- [x] `test_views.py` — public API (schema, submit, spam, rate limit), admin API (list, detail, CSV)
- [x] `test_admin.py` — admin registration, list_display, actions, CSV export
- [x] `test_notifications.py` — email triggered on submit, spam silenced, SMTP failure safe
- [x] `test_validators.py` — dynamic field-level validator factory
- [x] `test_management.py` — seed presets command, anonymize submissions command
- [x] E2E test: Plan → Apply → Working contact form project (seed `contact` preset, submit, verify in admin)

---

#### CLI Integration Checklist

**Status: ✅ Complete** — All CLI integration tasks implemented in v0.75.0.

**React showcase theme integration is already complete** — `FormsPage.tsx`, the `/forms/:slug` route in `App.tsx`, and the Dashboard module card are already part of the generated theme template files and require no apply-step injection (same pattern as all other modules). The `forms` module activation condition was also added to `index.html.j2`.

**Files changed** (5 files):

**1. `quickscale_cli/src/quickscale_cli/module_catalog.py`** — Register `forms` as a ready module:
- [x] Added `ModuleCatalogEntry(name="forms", ...)` after `crm` entry and before `billing`
- [x] `get_module_entries(include_experimental=False)` now returns 5 entries (auth, blog, listings, crm, forms)

**2. `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py`** — Wiring spec added:
- [x] Added `_forms_wiring(options)` function with full settings injection (`FORMS_*` settings + `REST_FRAMEWORK` when `submissions_api_enabled=True`)
- [x] Registered in `MODULE_WIRING_BUILDERS` after `crm`

**3. `quickscale_cli/src/quickscale_cli/commands/module_config.py`** — Config + apply functions added:
- [x] `get_default_forms_config()` returns all 6 manifest option keys
- [x] `configure_forms_module(non_interactive)` for interactive and non-interactive modes
- [x] `apply_forms_configuration(project_path, config)` calls `_regenerate_wiring_for_module`
- [x] Added `"forms": (configure_forms_module, apply_forms_configuration)` to `MODULE_CONFIGURATORS`

**4. `quickscale_cli/src/quickscale_cli/commands/module_commands.py`** — Dependency install:
- [x] Added `"forms"` to the dependency install list in `_perform_module_embed`

**5. `quickscale_cli/tests/test_module_manifest_contract.py`** — Contract tests extended:
- [x] Imported `get_default_forms_config` and added to `DEFAULT_CONFIG_FACTORIES`

**Additional changes**:
- [x] `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/templates/index.html.j2` — Added `forms` module activation condition
- [x] `quickscale_core/tests/test_react_theme_integration.py` — Updated `MODULES` list to include `forms`
- [x] `quickscale_cli/tests/test_plan_add.py` — Updated `TestPlanAddAllModulesInstalled` to include `forms` in state

---

#### Core Design Principles

- [x] **Data-driven**: Forms and their fields are defined entirely through admin or fixtures — no code changes needed to add a new form.
- [x] **Generic**: Supports any use case — contact, feedback, support ticket, newsletter sign-up, RFQ, etc.
- [x] **Customizable**: Per-field validation rules, ordering, conditional visibility (roadmap), and layout hints (full-width, two-column).
- [x] **Theme-agnostic backend**: Django models and DRF API are fully decoupled from the React frontend.
- [x] **React frontend**: Dynamic form renderer using React Hook Form + Zod (v0.74.0 mandated stack); fetches schema from the REST API.
- [x] **Spam protection**: Honeypot field + configurable rate limiting (no external CAPTCHA dependency).
- [x] **Notification-ready**: Email notification hooks on every submission; plugs into future `quickscale_modules.notifications` (v0.83.0).
- [x] **GDPR-aware**: Configurable data retention period; submission anonymization support.

---

#### Data Models

- [x] `Form` model implemented
- [x] `FormField` model implemented
- [x] `FormSubmission` model implemented
- [x] `FormFieldValue` model implemented

**`Form`** — top-level form definition:
- `title` (CharField) — human-readable name shown in the admin
- `slug` (SlugField, unique) — URL-friendly identifier; used in the API endpoint (`/api/forms/{slug}/`)
- `description` (TextField, blank) — optional intro text rendered above the form
- `success_message` (TextField) — shown after successful submission (default: "Thank you, we'll be in touch.")
- `redirect_url` (URLField, blank) — optional redirect after submission instead of inline success message
- `is_active` (BooleanField, default True) — disables the form without deleting it
- `spam_protection_enabled` (BooleanField, default True) — enables honeypot field injection
- `notify_emails` (TextField, blank) — comma-separated list of notification recipient emails
- `data_retention_days` (PositiveIntegerField, default 365) — submissions older than this are eligible for anonymization
- `created_by` (ForeignKey to `settings.AUTH_USER_MODEL`, null/blank, SET_NULL) — tracks creating admin
- `created_at`, `updated_at` (auto timestamps)
- DB table: `quickscale_modules_forms_form`

**`FormField`** — an individual field belonging to a form:
- `form` (ForeignKey to `Form`, related_name `fields`)
- `field_type` (CharField with choices): `text`, `email`, `textarea`, `select`, `checkbox`, `radio`, `number`, `url`, `tel`, `date`, `hidden`
- `label` (CharField) — visible label (e.g., "Project Context")
- `name` (SlugField) — machine name used as the key in submission data (e.g., `project_context`)
- `placeholder` (CharField, blank)
- `help_text` (CharField, blank)
- `required` (BooleanField, default True)
- `order` (PositiveIntegerField) — display order within the form
- `options` (JSONField, blank) — list of `{value, label}` dicts for `select`, `radio`, `checkbox` types
- `validation_rules` (JSONField, blank) — e.g., `{"min_length": 10, "max_length": 500, "regex": "^[a-z]+$"}`
- `layout_hint` (CharField, choices: `full`, `half_left`, `half_right`, default `full`) — layout hint for the React renderer
- `is_active` (BooleanField, default True)
- DB table: `quickscale_modules_forms_formfield`
- Constraint: `unique_together = [["form", "name"]]`

**`FormSubmission`** — a single form fill event:
- `form` (ForeignKey to `Form`, related_name `submissions`, on_delete=PROTECT)
- `ip_address` (GenericIPAddressField, null/blank) — anonymized to null when retention expires
- `user_agent` (CharField, blank) — browser info for spam scoring
- `submitted_at` (DateTimeField, auto_now_add)
- `is_spam` (BooleanField, default False) — manually or automatically flagged
- `status` (CharField, choices: `pending`, `read`, `replied`, `archived`, default `pending`)
- DB table: `quickscale_modules_forms_formsubmission`

**`FormFieldValue`** — the value for a single field in a submission:
- `submission` (ForeignKey to `FormSubmission`, related_name `values`)
- `field` (ForeignKey to `FormField`, null/blank, SET_NULL) — null-safe for deleted fields; historical data preserved
- `field_name` (CharField) — snapshot of `FormField.name` at submission time (protects historical data)
- `field_label` (CharField) — snapshot of `FormField.label` at submission time
- `value` (TextField) — the submitted value as text
- DB table: `quickscale_modules_forms_formfieldvalue`

---

#### REST API Endpoints

- [x] `GET /api/forms/{slug}/` (public schema)
- [x] `POST /api/forms/{slug}/submit/` (public submit)
- [x] `GET /api/admin/forms/` (staff list)
- [x] `GET /api/admin/forms/{id}/submissions/` (staff submissions list)
- [x] `GET /api/admin/forms/{id}/submissions/{sub_id}/` (staff submission detail)
- [x] `PATCH /api/admin/forms/{id}/submissions/{sub_id}/` (staff submission update)
- [x] `GET /api/admin/forms/{id}/submissions/export/` (staff CSV export)

All endpoints live under the prefix configured via `urls.py` (recommended: `/forms/api/`):

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/forms/{slug}/` | Public | Fetch form schema (fields, metadata). Returns 404 if inactive. |
| `POST` | `/api/forms/{slug}/submit/` | Public | Submit form data. Returns 201 on success, 400 on validation error. |
| `GET` | `/api/admin/forms/` | Staff only | List all forms with submission counts. |
| `GET` | `/api/admin/forms/{id}/submissions/` | Staff only | List submissions for a form (paginated). |
| `GET` | `/api/admin/forms/{id}/submissions/{sub_id}/` | Staff only | Single submission detail with all field values. |
| `PATCH` | `/api/admin/forms/{id}/submissions/{sub_id}/` | Staff only | Update `status` or `is_spam` flag. |
| `GET` | `/api/admin/forms/{id}/submissions/export/` | Staff only | Download submissions as CSV. |

**Public schema response example** (`GET /api/forms/contact/`):
```json
{
  "slug": "contact",
  "title": "Get in Touch",
  "description": "Share your current constraints, timeline, and target outcomes.",
  "success_message": "Thank you, we will respond within 24 hours.",
  "fields": [
    {"name": "full_name", "field_type": "text", "label": "Name", "required": true, "order": 1, "layout_hint": "half_left"},
    {"name": "email", "field_type": "email", "label": "Email", "required": true, "order": 2, "layout_hint": "half_right"},
    {"name": "company", "field_type": "text", "label": "Company", "required": false, "order": 3, "layout_hint": "half_left"},
    {"name": "subject", "field_type": "text", "label": "Subject", "required": true, "order": 4, "layout_hint": "half_right"},
    {"name": "project_context", "field_type": "textarea", "label": "Project Context", "required": true, "order": 5, "layout_hint": "full", "placeholder": "Describe your constraints, timeline, and target outcomes..."}
  ]
}
```

**Submit response** (`POST /api/forms/contact/submit/`):
- `201 Created` → `{"message": "Thank you, we will respond within 24 hours.", "redirect_url": null}`
- `400 Bad Request` → `{"errors": {"email": ["Enter a valid email address."]}}`
- `429 Too Many Requests` → when rate limit exceeded
- `404 Not Found` → form slug does not exist or is inactive

---

#### Serializers (`serializers.py`)

- [x] `FormFieldSerializer` — read-only schema serializer for public API (excludes `validation_rules` internals exposed only partially as needed by Zod)
- [x] `FormSchemaSerializer` — wraps `Form` + nested `FormFieldSerializer` list for `GET /api/forms/{slug}/`
- [x] `FormSubmissionCreateSerializer` — write-only; validates against the form's fields dynamically; raises field-level `ValidationError` keyed by `field.name`
- [x] `FormSubmissionAdminSerializer` — full submission detail for admin endpoints
- [x] `FormFieldValueSerializer` — value snapshot for admin submission detail

---

#### Views (`views.py`)

- [x] `FormSchemaAPIView(RetrieveAPIView)` — returns `FormSchemaSerializer`; permission: `AllowAny`; filters out inactive forms via `get_object()`
- [x] `FormSubmitAPIView(CreateAPIView)` — processes submission; invokes spam check (honeypot); triggers notification; permission: `AllowAny`; throttled via `ScopedRateThrottle`
- [x] `AdminFormListAPIView(ListAPIView)` — staff-only; annotates with `submission_count`
- [x] `AdminSubmissionListAPIView(ListAPIView)` — staff-only; filterable by `status`, `is_spam`, date range
- [x] `AdminSubmissionDetailAPIView(RetrieveUpdateAPIView)` — staff-only; `PATCH` allows updating `status`/`is_spam`
- [x] `AdminSubmissionExportView(View)` — staff-only; streams CSV response with all field values
- [x] `FormPageView(TemplateView)` — optional server-side entry point; renders a placeholder `<div id="form-root">` that the React `FormRenderer` component mounts into; passes `slug` to React via `data-*` attribute

---

#### Admin (`admin.py`)

- [x] `FormFieldInline(admin.TabularInline)` configured
- [x] `FormAdmin(admin.ModelAdmin)` registered and configured
- [x] `FormFieldValueInline(admin.TabularInline)` configured read-only
- [x] `FormSubmissionAdmin(admin.ModelAdmin)` registered and configured
- [x] Admin actions implemented (`mark_inactive/active`, `mark_as_spam/read/replied/archived`)

**`FormFieldInline(admin.TabularInline)`**:
- Model: `FormField`
- `extra = 1`
- `fields`: `field_type`, `label`, `name`, `required`, `order`, `is_active`
- Sortable by `order`

**`@admin.register(Form) class FormAdmin(admin.ModelAdmin)`**:
- `list_display`: `title`, `slug`, `is_active`, `submission_count`, `created_at`
- `list_filter`: `is_active`, `created_at`
- `search_fields`: `title`, `slug`
- `prepopulated_fields`: `{"slug": ("title",)}`
- `readonly_fields`: `created_at`, `updated_at`, `created_by`
- `fieldsets`: General (title, slug, description), Behaviour (is_active, spam_protection_enabled), Notifications (notify_emails), Data Retention (data_retention_days, success_message, redirect_url), Metadata (created_by, created_at, updated_at)
- `inlines`: `[FormFieldInline]`
- `save_model()` override: sets `created_by = request.user` on creation
- `get_queryset()` annotates `submission_count`
- `submission_count()` method with `short_description = "Submissions"`
- Actions: `mark_inactive`, `mark_active`

**`FormFieldValueInline(admin.TabularInline)`**:
- Model: `FormFieldValue`
- `readonly_fields`: all fields
- `extra = 0`
- `can_delete = False`

**`@admin.register(FormSubmission) class FormSubmissionAdmin(admin.ModelAdmin)`**:
- `list_display`: `form`, `status`, `is_spam`, `submitted_at`, `ip_address`
- `list_filter`: `status`, `is_spam`, `form`, `submitted_at`
- `search_fields`: `values__value`, `ip_address`
- `readonly_fields`: `form`, `ip_address`, `user_agent`, `submitted_at`
- `inlines`: `[FormFieldValueInline]`
- Actions: `mark_as_spam`, `mark_as_read`, `mark_as_replied`, `mark_as_archived`
- CSV export action via `AdminSubmissionExportView`

---

#### URL Configuration (`urls.py`)

- [x] `GET /forms/` → `FormPageView`
- [x] `GET /forms/<slug:slug>/` → `FormPageView`
- [x] `GET /api/forms/<slug:slug>/` → `FormSchemaAPIView`
- [x] `POST /api/forms/<slug:slug>/submit/` → `FormSubmitAPIView`
- [x] `GET /api/admin/forms/` → `AdminFormListAPIView`
- [x] `GET /api/admin/forms/<int:pk>/submissions/` → `AdminSubmissionListAPIView`
- [x] `GET /api/admin/forms/<int:pk>/submissions/<int:sub_pk>/` → `AdminSubmissionDetailAPIView`
- [x] `PATCH /api/admin/forms/<int:pk>/submissions/<int:sub_pk>/` → `AdminSubmissionDetailAPIView`
- [x] `GET /api/admin/forms/<int:pk>/submissions/export/` → `AdminSubmissionExportView`

```
app_name = "quickscale_forms"
urlpatterns:
  GET  /forms/                           → FormPageView (React mount point, optional)
  GET  /forms/<slug:slug>/               → FormPageView with slug context
  GET  /api/forms/<slug:slug>/           → FormSchemaAPIView
  POST /api/forms/<slug:slug>/submit/    → FormSubmitAPIView
  GET  /api/admin/forms/                         → AdminFormListAPIView
  GET  /api/admin/forms/<int:pk>/submissions/    → AdminSubmissionListAPIView
  GET  /api/admin/forms/<int:pk>/submissions/<int:sub_pk>/   → AdminSubmissionDetailAPIView
  PATCH /api/admin/forms/<int:pk>/submissions/<int:sub_pk>/  → AdminSubmissionDetailAPIView
  GET  /api/admin/forms/<int:pk>/submissions/export/  → AdminSubmissionExportView
```

---

#### React Frontend Components

All components live in the generated project's React frontend under `src/components/forms/`:

- [x] **`FormRenderer`** — the top-level dynamic form component
  - [x] Receives `slug` prop via React Router `useParams`
  - [x] Fetches form schema from `GET /api/forms/{slug}/` using `TanStack Query`
  - [x] Builds Zod validation schema dynamically from the returned `fields` array (`required`, `field_type` → Zod types, `validation_rules` → `.min()/.max()/.regex()`)
  - [x] Passes schema to `useForm()` from React Hook Form (`zodResolver`)
  - [x] Renders `<FormFieldRenderer>` for each field, in order
  - [x] On submit: `POST /api/forms/{slug}/submit/`; maps server-side field errors back to React Hook Form `setError()`
  - [x] Shows `<FormSuccess>` or redirects on success
- [x] **`FormFieldRenderer`** — switches on `field_type` to render the correct input component (shadcn/ui `Input`, `Textarea`, `Select`, `Checkbox`, `RadioGroup`)
- [x] **`FormSuccess`** — displays the `success_message` returned from the API
- [x] **`useFormSchema(slug)`** — TanStack Query hook for fetching and caching the form schema

---

#### Spam Protection

- [x] **Honeypot**: `FormSubmitAPIView` injects a hidden `_hp_name` field into the schema response; if non-empty on submit, the submission is silently marked `is_spam=True` and returns `201` (no error revealed to bot)
- [x] **Rate limiting**: `ScopedRateThrottle` with scope `form_submit`; default rate `5/hour` per IP; configurable via `FORMS_RATE_LIMIT` Django setting

---

#### Email Notifications

- [x] On successful (non-spam) submission, `FormSubmitAPIView` calls `notify_submission(submission)` from `quickscale_modules_forms.notifications`
- [x] `notify_submission()` sends a plain-text + HTML email to all addresses in `Form.notify_emails`
- [x] Uses Django's built-in `send_mail()` (no external dependency); plugs seamlessly into future `quickscale_modules.notifications` (v0.83.0)
- [x] Email subject: `"[{form.title}] New submission from {name_field_value}"`
- [x] Email body: all field label → value pairs, IP address, timestamp
- [x] Silently swallows `SMTPException` — submission is never blocked by a notification failure

---

#### Built-in Presets (Management Command)

- [x] Management command `forms_seed_presets` implemented
- [x] `contact` preset implemented
- [x] `newsletter` preset implemented
- [x] `feedback` preset implemented
- [x] `support` preset implemented

Management command `python manage.py forms_seed_presets` creates ready-to-use form fixtures:

| Preset slug | Fields |
|-------------|--------|
| `contact` | full_name (text), email (email), company (text, optional), subject (text), project_context (textarea) |
| `newsletter` | full_name (text), email (email) |
| `feedback` | full_name (text, optional), email (email, optional), rating (select 1–5), message (textarea) |
| `support` | full_name (text), email (email), subject (text), priority (select: low/medium/high), description (textarea) |

The `contact` preset directly maps to **experto.ai/contact** fields and can be used out of the box.

---

#### `module.yml` Manifest

- [x] Manifest file created (`quickscale_modules/forms/module.yml`)
- [x] Module metadata defined (`name`, `version`, `description`)
- [x] Mutable config options defined
- [x] Immutable config options defined
- [x] Dependencies declared
- [x] Django app registration declared

```yaml
name: forms
version: 0.76.0
description: "Generic, customizable form builder module with admin management and React frontend renderer."
config:
  mutable:
    forms_per_page:
      type: integer
      default: 25
      django_setting: FORMS_PER_PAGE
      description: "Number of submissions shown per page in admin."
    spam_protection_enabled:
      type: boolean
      default: true
      django_setting: FORMS_SPAM_PROTECTION
      description: "Enable honeypot spam protection globally."
    rate_limit:
      type: string
      default: "5/hour"
      django_setting: FORMS_RATE_LIMIT
      description: "Throttle rate for form submissions (per IP). Format: '<count>/<period>'."
    data_retention_days:
      type: integer
      default: 365
      django_setting: FORMS_DATA_RETENTION_DAYS
      description: "Days to keep submission data before anonymization (0 = keep forever)."
    submissions_api_enabled:
      type: boolean
      default: true
      django_setting: FORMS_SUBMISSIONS_API
      description: "Enable REST API endpoints for admin submission management."
  immutable:
    storage_backend:
      type: string
      default: "django"
      description: "Storage backend for form data. 'django' uses the project database."
dependencies:
  - djangorestframework>=3.14
  - django-filter>=23.0
django_apps:
  - quickscale_modules_forms
```

---

#### Package Structure

```
quickscale_modules/forms/
├── README.md
├── module.yml
├── pyproject.toml                   # Package: quickscale-module-forms
├── poetry.lock
├── poetry.toml
├── src/
│   └── quickscale_modules_forms/
│       ├── __init__.py
│       ├── apps.py                  # QuickscaleFormsConfig
│       ├── models.py                # Form, FormField, FormSubmission, FormFieldValue
│       ├── serializers.py           # FormSchema, Submit, Admin serializers
│       ├── views.py                 # Schema, Submit, Admin, Export views
│       ├── admin.py                 # FormAdmin, FormSubmissionAdmin + inlines
│       ├── urls.py                  # app_name = "quickscale_forms"
│       ├── notifications.py         # notify_submission() helper
│       ├── throttles.py             # FormSubmitThrottle (ScopedRateThrottle)
│       ├── validators.py            # Dynamic field-level validator factory
│       ├── management/
│       │   └── commands/
│       │       └── forms_seed_presets.py  # Seeds contact/newsletter/feedback/support fixtures
│       ├── migrations/
│       │   └── 0001_initial.py
│       └── templates/
│           └── quickscale_modules_forms/
│               └── forms/
│                   ├── form_page.html    # React mount point (<div id="form-root">)
│                   └── form_email.html   # Notification email template
└── tests/
    ├── __init__.py
    ├── conftest.py                  # Fixtures: form, field, submission, api_client, staff_client
    ├── settings.py                  # TEST Django settings
    ├── urls.py                      # Test URL config
    ├── test_models.py               # Form/Field CRUD, ordering, submission creation, value snapshot
    ├── test_serializers.py          # Schema serialization, dynamic submission validation
    ├── test_views.py                # Public API: schema, submit, spam, rate limit; Admin API: list, detail, CSV
    ├── test_admin.py                # Admin registration, list_display, actions, CSV export
    └── test_notifications.py        # Email triggered on submit; silenced on spam; SMTP failure safe
```

---

#### Testing Plan

**Coverage target**: ≥80% per file, ≥90% overall (CI enforced).

**`test_models.py`**:
- [x] `Form` creation, `__str__`, `slug` uniqueness constraint
- [x] `FormField` ordering (ordered by `order`), `unique_together` enforcement on `(form, name)`
- [x] `FormSubmission` creation with status default `pending`
- [x] `FormFieldValue` preserves field snapshot when `FormField` is deleted (SET_NULL + `field_name` snapshot)
- [x] `data_retention_days` default value
- [x] `is_active=False` does not expose form through API

**`test_serializers.py`**:
- [x] `FormSchemaSerializer` returns all active fields ordered by `order`
- [x] `FormSchemaSerializer` excludes inactive fields
- [x] `FormSubmissionCreateSerializer` validates required fields
- [x] `FormSubmissionCreateSerializer` raises field-named error on invalid `email` field type
- [x] `FormSubmissionCreateSerializer` accepts optional fields when `required=False`
- [x] `FormSubmissionCreateSerializer` rejects unknown field names
- [x] Dynamic Zod schema hint: `validation_rules` `{max_length: N}` reflected in serializer validation

**`test_views.py`**:
- [x] `GET /api/forms/{slug}/` → 200 with correct schema shape; 404 for unknown/inactive slug
- [x] `POST /api/forms/{slug}/submit/` → 201 with success message; 400 with field errors; honeypot flag sets `is_spam=True` silently returns 201; 404 for inactive form
- [x] Rate limit: 6th request within hour returns 429
- [x] Admin `GET /api/admin/forms/` → 403 for anonymous; 200 with submission count for staff
- [x] Admin CSV export → `text/csv` content-type; all field values present in rows
- [x] `PATCH submission` → status update `pending → read` reflects in DB

**`test_admin.py`**:
- [x] `FormAdmin` registered; `list_display` includes `submission_count`; `prepopulated_fields` slug
- [x] `FormFieldInline` present in `FormAdmin`
- [x] `FormSubmissionAdmin` registered; `list_display` includes `status`, `is_spam`
- [x] `FormFieldValueInline` read-only with `can_delete=False`
- [x] Bulk action `mark_as_spam` updates `is_spam=True` for all selected
- [x] `save_model` sets `created_by = request.user`

**`test_notifications.py`**:
- [x] `notify_submission()` sends one email to all `notify_emails` addresses
- [x] Email subject contains form title and submitter name
- [x] Email body contains all field labels and values
- [x] No email sent when `notify_emails` is empty
- [x] Spam submission does not trigger notification
- [x] `SMTPException` raised by backend does not propagate (submission is not rolled back)

**E2E tests**:
- [x] `Plan → Apply → Working contact form project` — seed `contact` preset, submit form, verify submission in admin

---

#### Integration with Future Modules

| Future Module | Integration Point |
|--------------|-------------------|
| `notifications` (v0.83.0) | Replace `notify_submission()` Django `send_mail` call with `notifications.send()` for template-based emails, tracking, and queue |
| `auth` (v0.63.0, existing) | Optional: associate submission with authenticated user if logged in; expose "My Submissions" view |
| `billing` (v0.80.0) | Not directly integrated; forms can collect payment intent context before Stripe checkout |
| `teams` (v0.81.0) | Team-scoped forms: filter admin views by team membership |

---

### v0.76.0: `quickscale_modules.storage` - Media Storage & CDN Integration Module

**Status**: 🚧 In Progress — core module, CLI wiring, and blog compatibility implemented

**Strategic Context**: Shared infrastructure module for user-uploaded files and media delivery. Provides a production-ready path beyond local filesystem storage by standardizing cloud object storage, CDN URL generation, image handling, and deployment wiring across QuickScale modules.

QuickScale-generated projects already work well in local development, but production media handling is still a project-by-project concern. That becomes a serious limitation when a workflow depends on uploaded files being durable across redeployments, publicly accessible at stable URLs, and efficiently cacheable through a CDN. The first concrete use case is **experto.ai blog automation**, where the publishing pipeline must upload images first, receive final public URLs, rewrite Markdown content to those URLs, and then publish the post without relying on local container disk.

This module should solve that infrastructure concern once, centrally, instead of repeating custom storage setup in every generated project or feature module. It should be a reusable dependency layer for media storage concerns, while business modules such as `blog`, `listings`, or future attachment-heavy modules continue to own their domain logic. In practice:

- `quickscale_modules.blog` should continue owning publishing workflows and content models.
- `quickscale_modules.storage` should own where uploaded files live, how their public URLs are built, and how production-safe delivery is configured.
- local filesystem storage must remain the default for development and simple projects.
- cloud-backed storage must be a documented, opt-in path for production projects that need durable media.

**Primary Objectives**:
- [x] Standardize media storage across QuickScale modules
- [x] Make uploaded files durable across Railway redeployments and container restarts
- [x] Provide stable, CDN-ready public URLs for uploaded assets
- [x] Reduce repeated per-project storage and CDN configuration work
- [x] Create a reusable foundation for blog images, avatars, galleries, and future attachments

**Non-Goals for v0.76.0**:
- [ ] No infrastructure provisioning / Terraform automation
- [ ] No video transcoding or advanced media pipeline
- [ ] No full DAM/media-library product scope
- [ ] No forced migration of existing local-media projects
- [ ] No provider-specific premium features unless they fit the shared abstraction cleanly

**Prerequisites**:
- ✅ React Default Theme (v0.74.0)
- ✅ Blog API image upload support available in the blog module

**Implementation Approach**:
- Build this as an infrastructure module, not a vertical feature module
- Keep local filesystem as the default development mode
- Add explicit opt-in configuration for cloud storage providers
- Prefer S3-compatible interfaces first so AWS S3 and Cloudflare R2 share most of the implementation
- Expose simple project-level helpers that other modules can use without importing provider-specific logic

**Temporary implementation handoff**: See [docs/planning/temporary-storage-blog-planner-handoff.md](../planning/temporary-storage-blog-planner-handoff.md) for the implementation-oriented handoff covering `public_base_url`, `custom_domain` deprecation, blog URL cleanup, planner configuration, `plan --reconfigure` safety, and the remote thumbnail MVP. Delete that handoff doc only after the v0.76.0 work and the referenced v0.84.0 planner follow-up are implemented and folded into permanent docs.

#### Implementation Checklist

**Architecture & Boundaries**:
- [x] Define module boundary: what belongs in `storage` vs what remains in `blog` and other modules
- [x] Define supported provider matrix for v0.76.0 (minimum: local + S3-compatible + Cloudflare R2)
- [x] Define stable public URL contract for uploaded files and CDN fronting
- [x] Define upload path strategy by module / asset type / date / collision-safe suffix
- [x] Define fallback strategy so projects can remain on local storage if desired
- [x] Define the future extension point for private media even if v0.76.0 only ships public media delivery
- [ ] Standardize `public_base_url` as the only public URL source of truth for storage-backed media and blog-facing asset URLs
- [ ] Deprecate `custom_domain` for public media URL generation so it no longer interferes with host + path CDN setups
- [ ] Fold mixed blog URL behavior into the storage integration plan so uploads, Markdown rewrites, featured images, and future blog-owned assets resolve through one canonical public URL helper

**Core Storage Features**:
- [x] Storage backend abstraction: local filesystem, S3-compatible, Cloudflare R2
- [x] Provider configuration contract with explicit required and optional fields
- [x] Project-level settings wiring for Django `STORAGES["default"]`
- [x] Canonical media URL generation helpers
- [x] CDN base URL support for uploaded media
- [x] Upload path conventions for images, documents, and generic assets
- [x] Validation helpers for file size, content type, and image dimensions
- [x] Shared helper for converting stored file references into final public URLs
- [x] Shared helper for generating immutable, cache-friendly asset names

**Image & Media Processing**:
- [ ] Reusable image variant helpers (thumbnail, medium, original)
- [ ] Optional WebP/optimized image generation hooks
- [x] Cache-friendly filename/versioning strategy for immutable media URLs
- [x] Shared utilities for modules that attach uploaded files to models
- [ ] Decide whether image processing is synchronous for v0.76.0 or deferred to future async integration
- [ ] Define a clean extension point for future background processing without blocking the initial release
- [ ] Ship a minimum viable remote thumbnail generation path for storage-backed images, acceptable as a synchronous first pass
- [ ] Ensure generated thumbnail URLs use the same `public_base_url` contract as original media URLs
- [ ] Defer richer variants, async/background processing, and broader media-pipeline expansion to a later release

**Module Integrations**:
- [x] Blog integration: use storage module for uploaded featured and inline images
- [ ] Author/avatar compatibility for existing blog author profiles
- [ ] React showcase guidance for consuming CDN-backed media URLs safely
- [ ] Future-ready integration hooks for listings galleries, CRM attachments, and social embeds
- [x] Ensure blog upload/publish APIs continue working when the storage backend changes from local to cloud
- [x] Define how feature modules should depend on `storage` without importing provider-specific code
- [ ] Make blog templates and model helpers stop relying on direct `.url` for public rendering, using storage-backed public URL helpers instead
- [ ] Extend the same canonical public URL strategy to blog author/avatar and similar blog-owned image fields
- [ ] Verify blog publish flows no longer mix raw storage URLs, deprecated `custom_domain` behavior, and `public_base_url`-based URLs in the same project

**CLI & Plan/Apply Integration**:
- [x] Add `module.yml` manifest with mutable and immutable config boundaries
- [x] Define `quickscale plan --add storage` prompts / defaults
- [x] Add CLI wiring so generated projects receive provider-specific settings only when enabled
- [x] Ensure `quickscale apply` can regenerate settings safely without clobbering unrelated project code
- [ ] Decide whether `blog` should optionally detect and integrate with `storage` automatically during apply
- [ ] Add interactive `quickscale plan` module configuration for `storage` so backend/provider settings and `public_base_url` can be captured during planning
- [ ] Add a planner flag for interactive module configuration instead of forcing manual `quickscale.yml` edits for storage-specific setup
- [ ] Fix `quickscale plan --reconfigure` to preserve existing per-module option dictionaries instead of rebuilding them with empty values
- [ ] Acceptance: `plan --reconfigure` round-trips unchanged module options safely while updating only the fields the user reconfigures

**Configuration & Deployment**:
- [ ] Environment variable contract (`AWS_*`, bucket, endpoint, CDN URL)
- [ ] Document minimum environment variables for AWS S3 and Cloudflare R2
- [ ] Railway deployment guide for external media storage
- [ ] Local development fallback preserving current filesystem behavior
- [ ] Staging vs production guidance for media storage
- [ ] Explicit note that Railway local disk should not be treated as durable production media storage
- [ ] CDN cache guidance for immutable uploaded assets
- [ ] Migration guide for moving existing local-media projects to cloud-backed storage
- [ ] Document `public_base_url` as the canonical environment-specific override for swapping S3/CDN host or base path without changing stored media keys
- [ ] Document `custom_domain` as deprecated/legacy for public media delivery so new setups rely on `public_base_url` only

**Documentation & Acceptance Criteria**:
- [x] Add a module README with local/dev, staging, and production setup paths
- [ ] Add troubleshooting guidance for missing credentials, invalid buckets, and broken CDN URLs
- [ ] Document how other modules should integrate with storage helpers
- [x] Acceptance: a generated project can run locally with filesystem storage and no cloud credentials
- [x] Acceptance: a generated project can switch to S3-compatible storage via documented environment variables
- [x] Acceptance: blog image upload + publish workflow works end-to-end with cloud-backed URLs
- [x] Acceptance: resulting media URLs are stable and cache-friendly for CDN delivery
- [ ] Acceptance: Railway deployment guidance is documented and production-safe
- [ ] Acceptance: `public_base_url` is the documented public URL source of truth for storage/blog media in v0.76.0
- [ ] Acceptance: deprecated `custom_domain` behavior no longer changes generated public blog/storage asset URLs
- [ ] Acceptance: cloud-backed originals and generated thumbnails both resolve to stable, cache-friendly public URLs

**Testing**:
- [x] Unit tests for storage backend selection and URL helpers
- [ ] Integration tests for upload/write/read flows against local and mocked S3-compatible storage
- [x] Blog integration tests for uploaded images using storage-backed URLs
- [ ] E2E tests: Plan → Apply → Blog publish with uploaded CDN-backed images
- [x] Regression tests proving local-development behavior still works without cloud configuration
- [ ] Regression tests proving public blog rendering never depends on direct storage `.url` when storage helpers are available
- [ ] Planner tests covering interactive storage configuration, option persistence, and safe `plan --reconfigure` round-trips
- [ ] Thumbnail tests covering local and storage-backed generation with identical `public_base_url` URL resolution

---

### v0.77.0: `quickscale_modules.social` - Social & Link Tree Module

**Status**: 📋 Planned

**Strategic Context**: Social media presence module providing a link tree page (social network links) and social media embed integration. Supports progressive enhancement from simple social links to rich media embeds.

**Prerequisites**:
- ✅ React Default Theme (v0.74.0)

**Link Tree Features**:
- [ ] Configurable social links page (Instagram, TikTok, YouTube, Facebook, X/Twitter, LinkedIn)
- [ ] Link tree models: SocialLink (platform, url, icon, order, is_active)
- [ ] Admin interface for managing social links
- [ ] Link tree React component with platform icons and branding
- [ ] Customizable link tree layout (grid, list, card styles)
- [ ] Click tracking and analytics (optional)

**Social Media Embed Integration**:
- [ ] oEmbed protocol support for rich media embeds
- [ ] Instagram feed/post embed component
- [ ] TikTok video embed component
- [ ] YouTube video/channel embed component
- [ ] Facebook post embed component
- [ ] Embed gallery page (aggregate social feeds)
- [ ] Caching layer for embed data (reduce API calls)

**Backend**:
- [ ] Social media models and Django Admin
- [ ] REST API endpoints for social links and embeds
- [ ] oEmbed resolver service
- [ ] Rate limiting for external API calls

**Testing**:
- [ ] Unit tests for social models and oEmbed resolver
- [ ] Integration tests for embed components
- [ ] E2E tests: Plan → Apply → Working social links project

---

### v0.78.0: Listings Theme (React Frontend for Listings)

**Status**: 📋 Planned

**Strategic Context**: React frontend for property listings (sell & rent), building on the `showcase_react` foundation from v0.74.0 and the Listings module backend from v0.67.0. Prioritized for the Real Estate Agency use case.

**Prerequisites**:
- ✅ Listings Module (v0.67.0)
- ✅ React Default Theme (v0.74.0)

**Theme Features**:
- **Extends**: `showcase_react` base patterns
- **Components**: Property Cards, Search/Filter Bar, Detail View, Image Gallery, Map View
- **API Integration**: Consumes Listings Module REST APIs
- **Listing Types**: Sell and Rent with type-specific filters

**Implementation Tasks**:
- [ ] Listings-specific page layouts (grid, list, map views)
- [ ] Property card component with image, price, type (sell/rent), location
- [ ] Search and filter bar (price range, type, location, bedrooms, etc.)
- [ ] Property detail view with image gallery and contact form
- [ ] Listings dashboard with stats and featured properties
- [ ] Responsive design for mobile property browsing
- [ ] SEO-friendly property pages (meta tags, structured data)

**Testing**:
- [ ] E2E tests: Plan → Apply → Working Listings project
- [ ] Unit tests for filter/search components
- [ ] API integration tests with Listings backend

---

### v0.79.0: CRM Theme (React Frontend for CRM)

**Status**: 📋 Planned

**Strategic Context**: React frontend specifically for the CRM module, building on the `showcase_react` foundation from v0.74.0.

**Prerequisites**:
- ✅ CRM Module (v0.73.0)
- ✅ React Default Theme (v0.74.0)

**Theme Features**:
- **Extends**: `showcase_react` base patterns
- **Components**: Kanban Board, Contact List, Deal Detail View, Pipeline Management
- **API Integration**: Consumes CRM Module REST APIs

**Implementation Tasks**:
- [ ] CRM-specific page layouts
- [ ] Kanban board for deal pipeline
- [ ] Contact and company list views
- [ ] Detail views with inline editing
- [ ] Dashboard with CRM metrics

**Testing**:
- [ ] E2E tests: Plan → Apply → Working CRM project

---

### v0.80.0: `quickscale_modules.billing` - Billing Module

**Status**: 📋 Planned

**Stripe Integration**:
- [ ] Set up dj-stripe for Stripe API integration
- [ ] Configure webhook endpoints for payment events
- [ ] Implement subscription lifecycle management
- [ ] Add payment method handling (cards, etc.)

**Pricing & Plans**:
- [ ] Create pricing tier models and admin
- [ ] Implement plan creation and management
- [ ] Add usage tracking and limits
- [ ] Create pricing page templates

**Subscription Management**:
- [ ] Build subscription dashboard for users
- [ ] Implement plan upgrades/downgrades
- [ ] Add billing history and invoices
- [ ] Create cancellation and pause functionality

**Testing**:
- [ ] Unit tests for billing models and logic
- [ ] Integration tests with Stripe webhooks
- [ ] E2E tests for subscription flows

---

### v0.81.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

**Status**: 📋 Planned

**Team Management**:
- [ ] Create team and membership models
- [ ] Implement team creation and settings
- [ ] Add member invitation system
- [ ] Build team dashboard interface

**Role-Based Permissions**:
- [ ] Define role hierarchy (Owner, Admin, Member)
- [ ] Implement permission checking decorators
- [ ] Add role assignment and management
- [ ] Create permission-based UI elements

**Multi-Tenancy**:
- [ ] Implement row-level security patterns
- [ ] Add team-scoped data isolation
- [ ] Create tenant-aware querysets
- [ ] Handle cross-team data access

**Testing**:
- [ ] Unit tests for team models and permissions
- [ ] Integration tests for invitation flows
- [ ] E2E tests for multi-tenancy scenarios

---

### Module Showcase Architecture (Deferred to Post-v0.81.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.81.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on Plan/Apply system and core modules first (v0.68-v0.81)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for MVP

**Implementation Plan**: After v0.81.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns.

---

### v0.82.0+: HTMX Frontend Theme (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). HTMX provides an optional alternative for users preferring progressive enhancement.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation specifications including HTMX + Alpine.js base templates and progressive enhancement patterns.

---

### v0.83.0: `quickscale_modules.notifications` - Notifications Module

**Status**: 📋 Planned (after SaaS Feature Parity)

**Email Backend Integration**:
- [ ] Set up django-anymail for multiple email providers
- [ ] Configure transactional email templates
- [ ] Implement async email sending with Celery
- [ ] Add email backend failover handling

**Notification System**:
- [ ] Create notification models and admin
- [ ] Implement email template management
- [ ] Add notification scheduling and queuing
- [ ] Create notification dashboard for users

**Multi-Theme Support**:
- [ ] Port notifications to HTML theme
- [ ] Port notifications to HTMX theme (when available)
- [ ] Port notifications to React theme (when available)
- [ ] Ensure theme-agnostic backend code

**Testing**:
- [ ] Unit tests for email sending (80%+ per file coverage)
- [ ] Integration tests with email providers
- [ ] Test async processing with Celery
- [ ] Cross-theme compatibility testing

**See**: [competitive_analysis.md Module Roadmap](../overview/competitive_analysis.md#phase-2-post-mvp-v1---saas-essentials) for competitive context.

---

### v0.84.0: Advanced Module Management Features

**Note**: Basic module management commands (`quickscale update`, `quickscale push`) are implemented in **v0.62.0**. Plan/Apply system implemented in **v0.68.0-v0.71.0**. This release adds advanced features for managing multiple modules.

**Temporary implementation handoff**: The cross-module planner follow-up is also tracked in [docs/planning/temporary-storage-blog-planner-handoff.md](../planning/temporary-storage-blog-planner-handoff.md#deferred-follow-up-for-v0840-cross-module-planner-work) until implementation is complete.

**Batch Operations**:
- [ ] Implement `quickscale update --all` command
- [ ] Add batch conflict resolution
- [ ] Create progress indicators for batch operations
- [ ] Implement rollback for failed batch updates

**Status & Discovery**:
- [ ] Create `quickscale status` command showing installed modules and versions
- [ ] Implement `quickscale list-modules` command for available modules
- [ ] Add module version tracking and compatibility checking

**Enhanced UX**:
- [ ] Improve diff previews and summaries
- [ ] Add interactive conflict resolution
- [ ] Implement better error messages and progress indicators

**Planner UX & Cross-Module Configuration**:
- [ ] Generalize interactive per-module configuration so `quickscale plan` can invoke manifest-backed configurators across all supported modules
- [ ] Add dependency-aware planner sequencing for multi-module setups
- [ ] Expand `quickscale plan --reconfigure` into a safe all-modules workflow with merge-preserving updates
- [ ] Add planner regression coverage for mixed module stacks, dependency prompts, and option-retention behavior

**Testing**:
- [ ] Test batch operations with multiple modules
- [ ] Verify status and discovery commands
- [ ] Test conflict resolution workflows
- [ ] E2E testing of enhanced UX features

**Future Enhancements** (v0.85.0+, evaluate after v0.81.0):
- [ ] Module versioning: `quickscale plan --add auth@v0.63.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.85.0: Module Workflow Validation & Real-World Testing

**Objective**: Validate that module updates work safely in real client projects and don't affect user's custom code.

**Success Criteria**:
- Automated tests verify user's `templates/`, `static/`, and project code never modified by module updates
- Module update workflow documented with real project examples
- Safety features prevent accidental code modification
- Rollback procedure documented and tested
- Case studies from 3+ client projects using modules

**Implementation Tasks**:
- [ ] Real-world validation: Embed modules in 3+ client projects and document edge cases
- [ ] Safety validation: Automated tests verify user's code never modified by module updates
- [ ] Testing: E2E tests for multi-module workflows, conflict scenarios, and rollback functionality
- [ ] Documentation: Create "Safe Module Updates" guide with screenshots and case studies

**Rationale**: Module embed/update commands implemented in v0.62.0, Plan/Apply system in v0.68.0-v0.71.0. This release validates those systems work safely in production after real usage across multiple client projects.

---

### v1.0.0+: Community Platform (Optional Evolution)

**🎯 Objective**: IF proven successful personally, evolve into community platform.

**Timeline**: 12-18+ months after MVP (or never, if personal toolkit is enough)

**Version Strategy**: Major version (v1.0.0) for community platform features

**Example Release Sequence**:
- **v1.0.0**: PyPI publishing + package distribution
- **v1.1.0**: Theme package system
- **v1.2.0**: Marketplace basics
- **v1.x.0**: Advanced community features

**Prerequisites Before Starting v1.0.0**:
- ✅ 10+ successful client projects built with QuickScale
- ✅ 5+ proven reusable modules extracted
- ✅ Clear evidence that others want to use your patterns
- ✅ Bandwidth to support community and marketplace

#### v1.0.0: Package Distribution

When you're ready to share with community:

- [ ] **Setup PyPI publishing for modules**
  - [ ] Convert git subtree modules to pip-installable packages
  - [ ] Use PEP 420 implicit namespaces (`quickscale_modules.*`)
  - [ ] Implement semantic versioning and compatibility tracking
  - [ ] Create GitHub Actions for automated publishing
- [ ] **Create private PyPI for commercial modules** (see [commercial.md](../overview/commercial.md))
  - [ ] Set up private package repository
  - [ ] Implement license validation for commercial modules
  - [ ] Create subscription-based access system
- [ ] **Document package creation for community contributors**
  - [ ] Package structure guidelines
  - [ ] Contribution process
  - [ ] Quality standards and testing requirements

---

#### v1.1.0: Theme Package System

If reusable business logic patterns emerge:

- [ ] **Create theme package structure** (`quickscale_themes.*`)
  - [ ] Define theme interface and base classes
  - [ ] Implement theme inheritance system
  - [ ] Create theme packaging guidelines
- [ ] **Create example themes**
  - [ ] `quickscale_themes.starter` - Basic starter theme
  - [ ] `quickscale_themes.todo` - TODO app example
  - [ ] Document theme customization patterns
- [ ] **Document theme creation guide**
  - [ ] Theme architecture overview
  - [ ] Base model and business logic patterns
  - [ ] Frontend integration guidelines

**Theme Structure Reference**: See [scaffolding.md §4 (Post-MVP Themes)](./scaffolding.md#post-mvp-structure).

---

#### v1.2.0: Marketplace & Community

Only if there's real demand:

- [ ] **Build package registry/marketplace**
  - [ ] Package discovery and search
  - [ ] Ratings and reviews system
  - [ ] Module/theme compatibility tracking
- [ ] **Create community contribution guidelines**
  - [ ] Code of conduct
  - [ ] Contribution process and standards
  - [ ] Issue and PR templates
- [ ] **Setup extension approval process**
  - [ ] Quality review checklist
  - [ ] Security audit process
  - [ ] Compatibility verification
- [ ] **Build commercial module subscription system**
  - [ ] License management
  - [ ] Payment integration
  - [ ] Customer access control

See [commercial.md](../overview/commercial.md) for detailed commercial distribution strategies.

---

#### v1.3.0: Advanced Configuration

If YAML config proves useful in Phase 2:

- [ ] **Implement full configuration schema**
  - [ ] Module/theme selection via config
  - [ ] Environment-specific overrides
  - [ ] Customization options
- [ ] **Add module/theme selection via config**
  - [ ] Declarative module dependencies
  - [ ] Theme selection and variants
- [ ] **Create migration tools for config updates**
  - [ ] Schema version migration scripts
  - [ ] Backward compatibility checks
- [ ] **Build configuration validation UI** (optional)
  - [ ] Web-based config editor
  - [ ] Real-time validation
  - [ ] Preview generated project

**IMPORTANT**: v1.0.0+ is OPTIONAL. Many successful solo developers and agencies never need a community platform. Evaluate carefully before investing in marketplace features.
