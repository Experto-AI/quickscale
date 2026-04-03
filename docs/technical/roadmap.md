# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Timeline & Tasks)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Archive](release-archive.md) | [Start Here](../../START_HERE.md)

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

1. **Phase 1: Foundation + Core Modules (React Theme Default)** ✅ _Complete_
   - ✅ Theme system infrastructure and split branch management (v0.61.0-v0.62.0)
   - ✅ Auth module (v0.63.0) - production-ready with django-allauth
   - ✅ Listings module (v0.67.0) - generic base for vertical themes
   - ✅ Plan/Apply System core (v0.68.0-v0.70.0) - Terraform-style configuration
   - ✅ **Plan/Apply System complete** (v0.71.0) - Module manifests & config mutability
   - ✅ Plan/Apply Cleanup (v0.72.0) - Remove legacy init/embed commands
   - ✅ CRM module (v0.73.0) - native Django CRM app (API-only)
   - ✅ **React Default Theme** (v0.74.0) - React + shadcn/ui as default
   - ✅ **Forms module** (v0.75.0) - generic form builder with CLI integration ✅ Complete
  - ✅ Storage module (v0.76.0) - cloud file hosting, media storage adapters, CDN integration
  - ✅ Backups module (v0.77.0) - private database backups, optional private remote offload, guarded BackupPolicy-admin local restore plus CLI restore, and scheduler-ready command hooks

2. **Phase 2: Notifications, Analytics, Vertical Modules & Theme Expansion (Post-MVP)** 🚧 _In Progress_
  - ✅ Notifications module (v0.78.0) - transactional email foundation with app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery
  - 🚧 Social & Link Tree module (v0.79.0) - implementation archived; release closeout pending
  - 📋 Analytics module (v0.80.0) - PostHog-backed website analytics with React + HTML theme injection and cross-module conversion hooks
  - 📋 Listings Theme (v0.81.0) - React frontend for property listings (sell/rent)
  - 📋 CRM Theme (v0.82.0) - React frontend for CRM module
  - 📋 Billing module (v0.83.0) - Stripe integration
  - 📋 Teams module (v0.84.0) - multi-tenancy

3. **Phase 3: Secondary Theme, Validation & Platform Expansion** 📋 _Planned_
  - 📋 HTML theme polish and parity improvements (v0.85.0+) - maintain the server-rendered secondary option alongside the React default
   - HTML theme remains as secondary option (simpler projects)
  - 📋 Advanced module management features (v0.86.0)
  - 📋 Workflow validation and real-world testing (v0.87.0)
  - 📋 Disaster recovery & environment migration workflows (v0.88.0)

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
- **v0.77.0:** Backups module (private local + optional private remote workflows, guarded BackupPolicy-admin local restore plus CLI restore) ✅
- **v0.78.0:** Notifications Module (transactional email foundation; app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery) ✅
- **v0.79.0:** Social & Link Tree module (implementation archived; reader-facing release summary still pending) 🚧
- **v0.80.0:** Analytics Module (PostHog website analytics; React + HTML theme injection; cross-module conversion hooks) 🎯
- **v0.81.0:** Real Estate MVP (static + listings + social links) 🎯
- **v0.84.0:** SaaS Feature Parity (auth, billing, teams, notifications foundation) 🎯
- **v0.87.0:** Workflow validation (multi-module, storage/CDN, and deployment validation) 🎯
- **v0.88.0:** Disaster recovery & environment migration workflows 🎯
- **v1.0.0+:** Community platform (if demand exists)

**Status:**
- **Current Status:** the published release remains v0.78.0, while main branch now carries the v0.79.0 social-module implementation and is in release-closeout verification
- **In Progress:** v0.79.0 release closeout, reader-facing summary, and release preparation
- **Next Planned Scope After v0.79.0:** v0.80.0 - Analytics module (PostHog website analytics + React/HTML theme injection)
- **Next Milestone:** v0.80.0 - Analytics Module
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.84.0 - auth, billing, teams modules complete on top of the notifications foundation

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Release doc layout:** [CHANGELOG.md](../../CHANGELOG.md) is the canonical history index; [docs/releases/](../releases/) holds the default public summaries; [docs/releases-archive/](../releases-archive/) is reserved for exception-only maintainer records and legacy archived docs
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)

## ROADMAP

List of upcoming releases with detailed implementation tasks:

---

After release closeout, keep only a concise pointer in the roadmap. Put canonical history in [CHANGELOG.md](../../CHANGELOG.md), use [docs/releases/](../releases/) for the default reader-facing summary, and use [docs/releases-archive/](../releases-archive/) only when an exceptional maintainer record is needed.

---

### v0.76.0: `quickscale_modules.storage` - Media Storage & CDN Integration Module

**Status**: ✅ Released and archived on 2026-03-21

This release completed QuickScale's shared media-storage milestone: the storage contract now uses `public_base_url` as the single public media URL source, the deprecated `custom_domain` path was removed from module/CLI/planner behavior, and blog uploads plus thumbnails resolve through canonical helper-built URLs.

**Release artifacts**:
- [Reader-facing summary](../releases/release-v0.76.0.md)

**Deferred follow-up**:
- deeper storage upload/write/read integration coverage moved to [v0.87.0](#v0870-module-workflow-validation--real-world-testing)
- Plan → Apply → Blog publish E2E workflow validation with CDN-backed media moved to [v0.87.0](#v0870-module-workflow-validation--real-world-testing)

---

### v0.77.0: `quickscale_modules.backups` - Database Backup & Restore Module

**Status**: ✅ Archived retrospectively on 2026-03-31; hardening continuation archived on 2026-04-01

This completed release now lives outside the active roadmap. The original MVP closeout scope and the detailed PostgreSQL 18 / guarded BackupPolicy-admin restore hardening continuation now live in an exception-only maintainer implementation archive.

**Release artifacts**:
- [Maintainer implementation archive (exception)](../releases-archive/release-v0.77.0-implementation.md)

**Deferred follow-up**:
- broader database + media + environment portability workflows moved to [v0.88.0](#v0880-disaster-recovery--environment-migration-workflows)

---

### v0.78.0: `quickscale_modules.notifications` - Notifications Module

**Status**: ✅ Released on 2026-03-30

This release starts QuickScale's post-MVP expansion line and ships the notifications module as the new transactional-email foundation. Generated projects now have an opinionated delivery path centered on a read-only operational settings snapshot backed by Django settings and environment variables, app-owned email rendering, recipient-granular delivery tracking, Django email compatibility with the Anymail Resend backend, and signed webhook ingestion for delivery events.

**Release artifacts**:
- [Reader-facing summary](../releases/release-v0.78.0.md)

**Deferred follow-up**:
- inbound or reply workflows, provider-hosted templates, and richer broadcast/newsletter tooling remain deferred to later post-MVP releases
- multi-provider failover and shared async worker extraction remain deferred beyond v0.78.0

---

### v0.79.0: `quickscale_modules.social` - Social & Link Tree Module

**Status**: 🚧 Maintainer implementation archive exists; published release still pending

This implemented release scope now lives outside the active roadmap. The detailed v0.79.0 checklist, support matrix, validation notes, and deferred items now live in an exception-only maintainer implementation archive, while the published release metadata remains at v0.78.0 until the v0.79.0 reader-facing summary and release cut are completed.

**Release artifacts**:
- [Maintainer implementation archive (exception)](../releases-archive/release-v0.79.0-implementation.md)

**Current closeout scope**:
- publish the reader-facing v0.79.0 release summary and update release metadata when the release is cut
- keep end-to-end `quickscale plan` → `quickscale apply` → React public-page coverage deferred to [v0.87.0](#v0870-module-workflow-validation--real-world-testing)
- keep provider auth or write APIs, automated sync, and HTML-theme polish deferred beyond v0.79.0
- track analytics foundations and public-page instrumentation follow-up under v0.80.0 (Analytics Module)

---

### v0.80.0: `quickscale_modules.analytics` - Analytics Module

**Status**: 📋 Planned

**Planning document**: [Analytics Provider Comparison](../planning/analytics-provider-comparison.md) — full provider evaluation matrix and decision record.

**Objective**: Ship PostHog as the approved website-analytics provider across both React and HTML theme families. Wire a small, stable first-party event vocabulary covering page views, React SPA route changes, forms module submissions, and social module link clicks. Keep the scope disciplined: website analytics first, single provider, anonymous-default posture, no product-analytics complexity in this release.

**Scope Guardrails**:
- website analytics first; product analytics (funnels, retention, experiments, session replay) remain opt-in expansion for later releases
- one approved provider (PostHog) with Plausible documented as the secondary EU-data-residency path
- generated projects must be able to go live with zero provider cost (PostHog free tier: 1M events/month)
- secrets as env-var references only; never persist raw API keys in quickscale.yml or generated settings
- anonymous distinct IDs by default; authenticated-user identity linkage is an explicit operator opt-in

---

#### A. Analytics Contract (`analytics_contract.py`)

Add `quickscale_cli/src/quickscale_cli/analytics_contract.py` following the same pattern as `notifications_contract.py` and `social_contract.py`.

**Constants and defaults**:
- [ ] Define `ANALYTICS_PROVIDER_POSTHOG = "posthog"` and `ANALYTICS_PROVIDERS = ("posthog",)` as the approved v0.80.0 provider set
- [ ] Define `DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR = "POSTHOG_API_KEY"` and `DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR = "POSTHOG_HOST"`
- [ ] Define `ANALYTICS_POSTHOG_DEFAULT_HOST = "https://us.i.posthog.com"` and `ANALYTICS_POSTHOG_EU_HOST = "https://eu.i.posthog.com"` as known host values
- [ ] Define the first-party event vocabulary constants: `ANALYTICS_EVENT_PAGEVIEW`, `ANALYTICS_EVENT_FORM_SUBMIT`, `ANALYTICS_EVENT_SOCIAL_LINK_CLICK`

**Contract functions**:
- [ ] `default_analytics_module_options()` — returns `enabled`, `provider`, `posthog_api_key_env_var`, `posthog_host_env_var`, `posthog_host`, `exclude_debug`, `exclude_staff`, `anonymous_by_default`
- [ ] `normalize_analytics_module_options(options)` — strips leading/trailing whitespace, lower-cases provider token, validates env-var name pattern
- [ ] `resolve_analytics_module_options(options)` — merges defaults with normalized overrides
- [ ] `validate_analytics_env_var_reference(option_name, value)` — reuses the same `^[A-Z][A-Z0-9_]*$` pattern as notifications
- [ ] `validate_analytics_module_options(options)` — returns issue list: provider must be in `ANALYTICS_PROVIDERS`; env-var references must pass pattern; `exclude_debug` and `exclude_staff` must be booleans; `anonymous_by_default` must be boolean
- [ ] `analytics_production_targeted(options)` — returns True when enabled and a non-placeholder API key env var is set
- [ ] Export canonical `__all__`

---

#### B. Module Catalog Registration

- [ ] Add `analytics` entry to `MODULE_CATALOG` in `quickscale_cli/src/quickscale_cli/module_catalog.py`:
  ```python
  ModuleCatalogEntry(
      name="analytics",
      description="PostHog website analytics with React and HTML theme injection",
      ready=True,
  )
  ```

---

#### C. Module Wiring Spec (`module_wiring_specs.py`)

Add `_analytics_wiring(options)` following the same pattern as `_notifications_wiring` and `_social_wiring`.

**Django settings block** generated at apply time:
- [ ] `QUICKSCALE_ANALYTICS` dict: `ENABLED`, `PROVIDER`, `POSTHOG_API_KEY_ENV_VAR`, `POSTHOG_HOST_ENV_VAR`, `POSTHOG_HOST`, `EXCLUDE_DEBUG`, `EXCLUDE_STAFF`, `ANONYMOUS_BY_DEFAULT`
- [ ] Add `quickscale_modules_analytics` to `INSTALLED_APPS`
- [ ] Add `quickscale_modules_analytics.context_processors.analytics` to `TEMPLATES[0]["OPTIONS"]["context_processors"]`
- [ ] When `exclude_debug=True`, the generated settings block must document that the SDK is disabled in `DEBUG=True` environments

**`.env.example` additions**:
- [ ] `POSTHOG_API_KEY=` (placeholder, required for live analytics)
- [ ] `POSTHOG_HOST=` (optional, defaults to `https://us.i.posthog.com`)
- [ ] `VITE_POSTHOG_KEY=` (React theme: build-time injection via Vite)
- [ ] `VITE_POSTHOG_HOST=` (React theme: build-time injection via Vite, optional)

**Planner apply-time output** (operator next-steps message):
- [ ] Show PostHog dashboard URL and live events verification link
- [ ] Remind operator to set `POSTHOG_API_KEY` in Railway service variables before deploy
- [ ] Remind operator to set `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` in Railway service variables so the React build picks them up at build time (Railway injects `VITE_*` vars into the build environment)
- [ ] Note the EU host option (`https://eu.i.posthog.com`) for EU data residency

---

#### D. Django Module (`quickscale_modules/analytics/`)

Create the module following the same structure as notifications and social:

```
quickscale_modules/analytics/
├── src/quickscale_modules_analytics/
│   ├── __init__.py
│   ├── apps.py                  # AppConfig with PostHog Python SDK init
│   ├── context_processors.py   # Injects analytics config into templates
│   ├── services.py              # Server-side capture helpers + event vocabulary
│   ├── events.py                # First-party event name constants (import-safe)
│   ├── admin.py                 # Diagnostics: settings snapshot + test-event action
│   ├── models.py                # No models; placeholder for extension compliance
│   └── migrations/
│       └── __init__.py
├── tests/
│   ├── test_apps.py
│   ├── test_context_processors.py
│   ├── test_services.py
│   └── test_admin.py
├── pyproject.toml
└── README.md
```

**`apps.py`** — PostHog Python SDK initialization:
- [ ] `QuickscaleAnalyticsConfig.ready()` reads `QUICKSCALE_ANALYTICS` from `django.conf.settings`
- [ ] If `ENABLED` is False → `posthog.disabled = True`; return immediately
- [ ] Read `api_key` from `os.environ.get(POSTHOG_API_KEY_ENV_VAR, "")` — never from settings directly
- [ ] Read `host` from `os.environ.get(POSTHOG_HOST_ENV_VAR, "")` falling back to `POSTHOG_HOST` config value
- [ ] If `api_key` is empty → set `posthog.disabled = True`, emit a `warnings.warn` in non-DEBUG mode (operators misconfigured production)
- [ ] If both are present → `posthog.project_api_key = api_key; posthog.host = host`
- [ ] Do not raise exceptions in `ready()`; analytics failure must never prevent app startup

**`context_processors.py`** — template context injection:
- [ ] `analytics(request)` reads `QUICKSCALE_ANALYTICS` from settings
- [ ] Returns `ANALYTICS_ENABLED: False` if disabled or if `EXCLUDE_DEBUG` and `settings.DEBUG`
- [ ] Returns `ANALYTICS_ENABLED`, `ANALYTICS_PROVIDER`, `POSTHOG_API_KEY`, `POSTHOG_HOST` when active
- [ ] Never exposes raw secrets from settings — reads API key value from `os.environ`
- [ ] Excludes staff users from tracking if `EXCLUDE_STAFF` is True and `request.user.is_staff`

**`events.py`** — first-party event vocabulary:
- [ ] `ANALYTICS_EVENT_FORM_SUBMIT = "form_submit"`
- [ ] `ANALYTICS_EVENT_SOCIAL_LINK_CLICK = "social_link_click"`
- [ ] `ANALYTICS_EVENT_PAGEVIEW = "$pageview"` (PostHog canonical pageview event name)
- [ ] These constants are the stable cross-module import surface; no other module should hardcode string event names

**`services.py`** — server-side capture:
- [ ] `is_analytics_active() -> bool` — returns True only when SDK is initialized and not disabled
- [ ] `capture_event(distinct_id: str, event: str, properties: dict | None = None) -> None` — wraps `posthog.capture()`; no-op when `is_analytics_active()` is False; never raises
- [ ] `capture_form_submit(distinct_id: str, form_id: int | str, form_name: str = "", extra: dict | None = None) -> None` — calls `capture_event` with `ANALYTICS_EVENT_FORM_SUBMIT` and normalized properties
- [ ] `capture_social_link_click(distinct_id: str, provider: str, link_id: int | str, extra: dict | None = None) -> None` — calls `capture_event` with `ANALYTICS_EVENT_SOCIAL_LINK_CLICK`
- [ ] `get_distinct_id(request) -> str` — returns `str(request.user.pk)` if authenticated and `anonymous_by_default=False`; otherwise returns a session-scoped anonymous ID (use `request.session.session_key` as a stable anonymous identifier, creating session if not present)

**`admin.py`** — operator diagnostics:
- [ ] Read-only `AnalyticsDiagnosticsAdmin` (no model; registered via `AdminSite.register` on a proxy or via a custom `ModelAdmin` with `get_queryset` override returning nothing)
- [ ] Change list displays: provider, API key env var name, resolved host, SDK status (enabled/disabled/misconfigured), current env var presence (yes/no, not the value)
- [ ] Admin action: "Send test event" → calls `capture_event("test", "$pageview", {"source": "admin_diagnostics"})` and shows success/failure inline

---

#### E. React Theme Integration (`showcase_react`)

The React theme integration lives in the managed theme files. QuickScale's apply command updates these via a managed section pattern.

**PostHog initialization** (`src/analytics.js` — new managed file):
- [ ] `posthog.init(import.meta.env.VITE_POSTHOG_KEY, { api_host: import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com', capture_pageview: 'history_change', person_profiles: 'identified_only' })` — `identified_only` enforces anonymous-by-default
- [ ] Guard: only init if `VITE_POSTHOG_KEY` is non-empty and not the placeholder string `'your-posthog-key'`
- [ ] In dev mode (`import.meta.env.DEV`), call `posthog.opt_out_capturing()` to suppress dev traffic

**App root wrapping** (`src/main.jsx` or `src/App.jsx` — managed section):
- [ ] Wrap with `<PostHogProvider client={posthog}>` from `posthog-js/react`
- [ ] The managed section comment markers (`// --- QuickScale analytics: BEGIN` / `END`) allow apply to regenerate without touching surrounding user code

**React package dependencies** (`package.json` — managed section):
- [ ] Add `"posthog-js": "^1"` to dependencies when analytics is enabled
- [ ] Remove it when analytics is disabled via `quickscale plan --reconfigure`

**Vite env validation** (`vite.config.js` or `src/env.js` — managed section):
- [ ] Log a dev-only console warning if `VITE_POSTHOG_KEY` is empty at startup

**Custom event helpers** (`src/analytics-events.js` — new managed file):
- [ ] `trackFormSubmit(formId, formName)` → `posthog.capture('form_submit', { form_id: formId, form_name: formName })`
- [ ] `trackSocialLinkClick(provider, linkId)` → `posthog.capture('social_link_click', { provider, link_id: linkId })`
- [ ] These are thin wrappers; the forms and social React components import from here, not from posthog directly

---

#### F. HTML Theme Integration (`showcase_html`)

The HTML theme integration lives in Django templates managed by the apply command.

**Base template managed section** (`templates/base.html.j2` or equivalent):
- [ ] Add a `{% analytics_head %}` template tag or inline managed block in `<head>` that renders the PostHog JavaScript snippet when `ANALYTICS_ENABLED` is True and `POSTHOG_API_KEY` is non-empty
- [ ] Snippet must use the context-processor-injected `POSTHOG_API_KEY` and `POSTHOG_HOST` — never hardcoded values
- [ ] Use the `posthog-js` CDN snippet (pinned version) via a `<script>` tag with `defer`
- [ ] Include `posthog.opt_out_capturing()` call when running in a managed debug/staging context (inject via `{{ ANALYTICS_DEBUG_OPT_OUT }}` context variable)

**Managed template tag** (`quickscale_modules_analytics/templatetags/analytics_tags.py`):
- [ ] `{% analytics_head %}` — renders the full PostHog initialization snippet using context from settings, or renders an empty string when analytics is disabled
- [ ] `{% analytics_event event_name properties_json %}` — renders an inline `posthog.capture(...)` call for server-side-rendered interaction points

---

#### G. Cross-Module Wiring

Cross-module event capture flows through the project-owned extension app (the standard QuickScale extension surface), not through direct module-to-module imports.

**Forms → Analytics signal wiring** (generated in the project-owned extension app's `apps.py`):
- [ ] Connect `post_save` or a forms-module-owned signal to `analytics.services.capture_form_submit`
- [ ] The apply command generates a managed `AppConfig.ready()` block wiring the signal only when both `forms` and `analytics` modules are enabled in `quickscale.yml`
- [ ] The generated signal handler calls `get_distinct_id(request)` if request context is available, or uses `"server"` as the anonymous distinct ID for background/management-command triggers

**Social → Analytics event wiring** (generated in the project-owned extension app):
- [ ] Wire a view-level or signal-level hook to `analytics.services.capture_social_link_click` on social link page visits
- [ ] Generated only when both `social` and `analytics` modules are enabled

**Wiring spec guard** (in `module_wiring_specs.py`):
- [ ] `_analytics_cross_module_wiring(enabled_modules)` — returns the cross-module glue code only when the relevant modules are co-enabled; never generates dead import paths

---

#### H. CLI Plan/Apply Integration

**`quickscale plan` (interactive wizard)**:
- [ ] Add `analytics` to the module selection menu with description "PostHog website analytics (free tier: 1M events/month)"
- [ ] Planner prompts (in order):
  1. Enable analytics? `[y/N]` — default no for `plan`, default preserved for `plan --reconfigure`
  2. PostHog API key env var name — default `POSTHOG_API_KEY`; must match `^[A-Z][A-Z0-9_]*$`
  3. PostHog host — choices: `us.i.posthog.com (default)` / `eu.i.posthog.com (EU data residency)` / custom; stored as resolved URL
  4. Exclude analytics in DEBUG mode? `[Y/n]` — default yes
  5. Exclude staff users from tracking? `[y/N]` — default no
- [ ] Show planner output block: "Analytics (PostHog): enabled. API key: $POSTHOG_API_KEY. Host: https://us.i.posthog.com. React VITE_ vars required at Railway build time."

**`quickscale apply` (execution)**:
- [ ] Write `QUICKSCALE_ANALYTICS` settings block via wiring spec
- [ ] Add `quickscale_modules_analytics` to `INSTALLED_APPS`
- [ ] Add context processor
- [ ] Update `.env.example` with `POSTHOG_API_KEY`, `POSTHOG_HOST`, `VITE_POSTHOG_KEY`, `VITE_POSTHOG_HOST`
- [ ] Write managed React init file and wrap app root
- [ ] Add `posthog-js` to React `package.json`
- [ ] Write HTML base template managed section
- [ ] Generate cross-module signal wiring in extension app when co-enabled modules are present
- [ ] Apply-time operator output: PostHog dashboard link, Railway variable checklist, EU host note

**`quickscale plan --reconfigure`**:
- [ ] Analytics options are all mutable; `--reconfigure` must re-run the analytics prompts and merge updates into existing `quickscale.yml`
- [ ] If analytics is reconfigured from enabled → disabled, apply removes `posthog-js` from `package.json` and clears the managed sections in React and HTML templates

**`quickscale status`**:
- [ ] Analytics module row: shows provider, host, API key env var presence in current environment (yes/no), SDK state (active/disabled/misconfigured)

---

#### I. Railway Compatibility

- [ ] Document that `POSTHOG_API_KEY` and `POSTHOG_HOST` must be set as Railway service variables (not shared variables) so they are available at runtime
- [ ] Document that `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` must be set as Railway service variables and that Railway injects them into the build environment; they are consumed by Vite at build time, not runtime
- [ ] Document that PostHog's EU cloud (`https://eu.i.posthog.com`) is the correct `POSTHOG_HOST` value for projects targeting EU data residency under Railway's EU region
- [ ] Verify that the PostHog JavaScript snippet loads correctly behind Railway's edge/proxy layer; the `api_host` override in the PostHog init must match `POSTHOG_HOST` exactly
- [ ] The `posthog-js` npm package is bundled by Vite at build time; no CDN dependency at runtime for the React theme
- [ ] The HTML theme uses a pinned CDN snippet; document the CDN URL and advise operators to self-host it via Railway static serving if strict CSP policies are required
- [ ] Validate that Django's `SECURE_REFERRER_POLICY` and `CONTENT_SECURITY_POLICY` settings (if set) allow PostHog's `api_host` domain; include a CSP note in the apply-time operator output

---

#### J. Module Extension Contract

Following the standard from `module-extension.md`:

**What QuickScale owns**:
- `apps.py` AppConfig initialization and SDK lifecycle
- `context_processors.py` template context injection
- `services.py` server-side capture helpers and event vocabulary
- `events.py` first-party event name constants
- `admin.py` diagnostics admin
- Managed sections in React `src/analytics.js` and `src/main.jsx`
- Managed section in HTML `base.html` template tag

**What the project owns**:
- Cross-module signal wiring in the project-owned extension app's `AppConfig.ready()`
- Custom event calls in project-owned views and components
- PostHog dashboard configuration (goals, funnels, dashboards) — outside QuickScale scope

**Update-safe customizations**:
- Add `posthog.group()` calls or custom property enrichment in the project-owned extension app
- Add new custom event calls from project-owned views using `analytics.services.capture_event`
- Import and call `trackFormSubmit` / `trackSocialLinkClick` from `src/analytics-events.js` in custom React components

**Structured extension points (Tier 1)**:
- `QUICKSCALE_ANALYTICS` settings dict — all keys documented and stable
- `analytics.services.capture_event(distinct_id, event, properties)` — stable public API
- `analytics.services.get_distinct_id(request)` — stable public API
- `analytics.events.*` constants — stable import surface

**Upgrade expectations**:
- Settings keys in `QUICKSCALE_ANALYTICS` are stable across minor releases
- `capture_event`, `capture_form_submit`, `capture_social_link_click` signatures are stable
- Managed file sections regenerate on `quickscale apply`; do not edit content inside managed section markers
- Direct edits under `modules/analytics/` are outside the supported extension contract

---

#### K. Testing Scope

**Contract unit tests** (`quickscale_cli/tests/test_analytics_contract.py`):
- [ ] `default_analytics_module_options()` returns all required keys with correct defaults
- [ ] `validate_analytics_module_options` passes clean options and returns issues for invalid provider, bad env-var name pattern, non-boolean flags
- [ ] `validate_analytics_env_var_reference` rejects lowercase, spaces, leading underscores
- [ ] `analytics_production_targeted` returns True only when enabled and env-var reference is non-empty

**Wiring spec tests** (`quickscale_cli/tests/test_module_wiring_specs.py`):
- [ ] Analytics enabled: settings block contains all required keys; INSTALLED_APPS includes module; context processor added
- [ ] Analytics disabled: no settings block; module not in INSTALLED_APPS; no context processor
- [ ] Cross-module wiring: signal glue generated when both analytics + forms enabled; not generated when only one is enabled

**Module unit tests** (`quickscale_modules/analytics/tests/`):
- [ ] `apps.py`: SDK disabled when `ENABLED=False`; SDK disabled when `POSTHOG_API_KEY` env var empty; SDK initialized when both key and host are present; `ready()` never raises
- [ ] `context_processors.py`: returns `ANALYTICS_ENABLED=False` in DEBUG when `exclude_debug=True`; returns correct keys in non-DEBUG; excludes staff when `exclude_staff=True`; never exposes raw key value (only env-var-resolved value)
- [ ] `services.py`: `capture_event` is a no-op when `is_analytics_active()` is False; `capture_form_submit` calls `capture_event` with correct event name and properties; `get_distinct_id` returns anonymous session ID for anonymous users; returns user PK string for authenticated users when `anonymous_by_default=False`
- [ ] `events.py`: all constants are non-empty strings; `ANALYTICS_EVENT_FORM_SUBMIT` matches PostHog best-practice naming

**Planner/apply integration tests**:
- [ ] Lifecycle: enabled → apply → settings correct; disabled → apply → no settings
- [ ] Reconfigure: enabled → reconfigure to disabled → apply removes module from INSTALLED_APPS and clears managed sections
- [ ] Missing API key env var: apply succeeds but operator output includes a clear warning
- [ ] Cross-module: forms + analytics co-enabled → signal wiring generated; analytics alone → no wiring

**Theme injection tests**:
- [ ] HTML theme base template contains PostHog snippet block when analytics enabled; omits it when disabled
- [ ] React `src/analytics.js` exists and contains init call when analytics enabled; is absent or empty when disabled
- [ ] React `package.json` contains `posthog-js` when enabled; does not contain it when disabled
- [ ] `.env.example` contains all four env vars when analytics enabled

**Railway-specific verification** (manual / smoke):
- [ ] `VITE_POSTHOG_KEY` injected at Railway build time results in PostHog init running in the deployed React app
- [ ] `POSTHOG_HOST` set to `eu.i.posthog.com` routes events to PostHog EU without error
- [ ] Missing `POSTHOG_API_KEY` at runtime logs a warning but does not crash the Django app on startup

---

### v0.81.0: Listings Theme (React Frontend for Listings)

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

### v0.82.0: CRM Theme (React Frontend for CRM)

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

### v0.83.0: `quickscale_modules.billing` - Billing Module

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

### v0.84.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

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

### Module Showcase Architecture (Deferred to Post-v0.84.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.84.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on notifications, Plan/Apply system, and core modules first (v0.68-v0.83)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for MVP

**Implementation Plan**: After v0.84.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns.

---

### v0.85.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---

### v0.86.0: Advanced Module Management Features

**Note**: Basic module management commands (`quickscale update`, `quickscale push --module <name>`) are implemented in **v0.62.0**. Plan/Apply system implemented in **v0.68.0-v0.71.0**. This release adds advanced features for managing multiple modules.

**Planner follow-up**: Cross-module planner work now lives directly in the checklist below; there is no separate temporary handoff doc.

**Batch Operations**:
- [ ] Implement `quickscale update --all` command
- [ ] Add batch conflict resolution
- [ ] Create progress indicators for batch operations
- [ ] Implement rollback for failed batch updates

**Status & Discovery**:
- [ ] Expand `quickscale status` to show installed modules, versions, and richer diagnostics
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
- [ ] Expose explicit forms → notifications planner/apply configuration for submission delivery defaults, recipients, and template wiring when both modules are enabled
- [ ] Add planner regression coverage for mixed module stacks, dependency prompts, and option-retention behavior
- [ ] Add mixed-module regression coverage for forms + notifications delivery, fallback behavior, and option-retention across reconfigure flows

**Testing**:
- [ ] Test batch operations with multiple modules
- [ ] Verify status and discovery commands
- [ ] Test conflict resolution workflows
- [ ] E2E testing of enhanced UX features

**Future Enhancements** (v0.87.0+, evaluate after v0.84.0):
- [ ] Module versioning: `quickscale plan --add auth@v0.63.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.87.0: Module Workflow Validation & Real-World Testing

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
- [ ] Storage validation: add upload/write/read integration coverage for local storage and mocked S3-compatible backends
- [ ] Storage/blog workflow validation: add Plan → Apply → Blog publish E2E coverage with CDN-backed media URLs
- [ ] Storage URL regression validation: verify helper-built public media URLs remain canonical across blog rendering and upload flows in real project scaffolds
- [ ] Forms/notifications workflow validation: add Plan → Apply → form submission → tracked delivery coverage, plus fallback validation when notifications is absent or disabled
- [ ] Railway CDN reconciliation: validate Railway edge/custom-domain/CDN guidance against the storage `public_base_url` contract and document the supported static-vs-media split
- [ ] Documentation: Create "Safe Module Updates" guide with screenshots and case studies

**Rationale**: Module embed/update commands implemented in v0.62.0, Plan/Apply system in v0.68.0-v0.71.0. This release validates those systems work safely in production after real usage across multiple client projects.

---

### v0.88.0: Disaster Recovery & Environment Migration Workflows

**Status**: 📋 Planned

**Objective**: Extend the current database-first backups line into controlled project snapshot and environment migration workflows for generated projects across local, Railway develop, and Railway production.

**Scope Guardrails**:
- keep the v0.77 database-first restore contract authoritative until broader portability workflows are specified, implemented, and validated
- keep secrets as references or required operator inputs only; never persist raw credential values in snapshot artifacts or migration manifests
- treat database dumps, media sync, and environment metadata as separate surfaces with explicit restore/promotion rules instead of a single opaque "whole system" blob

**Portable Artifact Boundaries**:

| Artifact / surface | Included in the promotion workflow | Boundary rule |
| --- | --- | --- |
| **Database dump** | Yes | PostgreSQL custom dump is the restore artifact for generated PostgreSQL projects; JSON export remains inspection/test-fixture only |
| **Media sync manifest** | Yes | carry object keys, paths, checksums, and target mapping; do not treat public URLs or CDN hostnames as source-of-truth state |
| **Environment-variable name manifest** | Yes | carry names, purpose, required/optional status, and target owner; never persist raw secret values |
| **Release metadata snapshot** | Yes | carry QuickScale version, enabled modules, git SHA, and sanitized config/version notes needed to reproduce the environment |
| **Promotion verification report** | Yes | carry dry-run output, smoke-test results, operator confirmations, and rollback references |
| **Raw secrets / provider tokens** | No | remain in local secret storage, Railway variables, or the target secret manager only |
| **CDN, DNS, and custom-domain resources** | No | reference by host or resource name only; manage them as provider-owned infrastructure outside backup artifacts |
| **Static build artifacts** | No | rebuild through the normal deploy pipeline; do not ship them as restore/promotion artifacts |

Application source code also moves through the normal git/deploy pipeline. The portable artifact set is limited to the operational surfaces above and must not turn into a second code-distribution channel.

**Workflow Checklist**:

**Local → Railway develop**:
- [ ] Capture a fresh local release checkpoint: current git SHA via the normal deploy path, plus a PostgreSQL dump, media sync manifest, environment-variable name manifest, release metadata snapshot, and baseline smoke-check notes
- [ ] Provision Railway develop prerequisites: PostgreSQL 18 target, storage backend, media host/CDN target, and environment-variable slots owned by Railway rather than the artifact set
- [ ] Run a dry-run migration plan against Railway develop and fail early on missing variables, incompatible storage targets, or restore-surface mismatches
- [ ] Apply the generated project/configuration to Railway develop without exporting or storing raw secrets inside migration artifacts
- [ ] Restore the database dump, sync media objects through the manifest, and run migrations or repair steps required by the target environment
- [ ] Verify Railway develop with smoke checks covering auth, forms/notifications, storage URLs, and backups guardrails before treating it as the next promotion source

**Railway develop → Railway production**:
- [ ] Capture a fresh develop snapshot instead of reusing the earlier local artifact set so production promotion starts from the validated develop state
- [ ] Diff the develop and production environment-variable name manifests and resolve required production-only values before promotion begins
- [ ] Confirm production storage, `public_base_url`, CDN/domain prerequisites, and destructive-step confirmations before any restore or sync action
- [ ] Run a dry-run production promotion plan with explicit rollback references and a signed operator checkpoint
- [ ] Promote database and media using the same separated artifact surfaces rather than a single opaque environment bundle
- [ ] Run production smoke checks, record the promotion verification report, and preserve rollback artifacts long enough to reverse the cutover if needed

**Railway production → Railway develop (recovery rehearsal / disaster recovery)**:
- [ ] Capture a fresh production recovery checkpoint: current production git SHA/release metadata, a production database dump, media sync manifest, environment-variable name manifest, and the latest verification report references
- [ ] Provision or refresh an isolated Railway develop recovery target so production data is restored into non-production database, storage, and domain surfaces only
- [ ] Run a dry-run recovery plan that remaps production hosts, media targets, and variable ownership into develop-safe values before any restore begins
- [ ] Restore database and media into Railway develop using the separated artifact set, with any required data-sanitization or operator-access controls applied before broader testing
- [ ] Reconcile the recovered develop environment with the target git/deploy state for the improvements you want to test, without copying raw production secrets into the recovery artifacts
- [ ] Run smoke and regression checks in Railway develop, then record the recovery verification report and rollback references so the same flow can serve both rehearsal and disaster-recovery needs

**Implementation Tasks**:
- [ ] Define the supported project-snapshot contract: database dump, media sync manifest, environment-variable name inventory, version metadata, and restore/promotion instructions
- [ ] Decide whether broader project portability remains inside `quickscale_modules.backups` or becomes a companion ops workflow
- [ ] Add dry-run environment migration plans for local → Railway develop, Railway develop → Railway production, and Railway production → Railway develop based on the explicit artifact boundaries above
- [ ] Add Railway-specific capture/apply helpers for service variables, media prerequisites, and release metadata without persisting raw credentials
- [ ] Add integrity checks, rollback guidance, and explicit operator confirmations for destructive restore/promotion steps
- [ ] Document disaster-recovery workflows separately from environment-promotion workflows so operators know what is and is not transported automatically

**Testing**:
- [ ] Validate database restore, media sync, and environment metadata handoff independently before full project-promotion flows
- [ ] End-to-end rehearse representative local → Railway develop, Railway develop → Railway production, and Railway production → Railway develop migrations
- [ ] Verify backup artifacts and migration manifests never expose raw secrets or public backup URLs

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
