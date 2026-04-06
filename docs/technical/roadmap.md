# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Timeline & Tasks)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document tracks the active development timeline, versioned milestone scope, and archived pointers for recent QuickScale releases.

**Content Guidelines:**
- Organize work by versioned milestones with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

**What to Add Here:**
- New milestone planning and release-specific task tracking
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

QuickScale's roadmap is milestone-led. It tracks shipped release pointers, the current implementation line, and the next versioned scopes already tied to concrete repository work. Older phase labels still appear in some historical notes, but they are not the active roadmap structure.

## Current Milestone Summary

This table is the single milestone summary for shipped history and the active forward roadmap.

| Version | Status | Milestone | Details |
|---------|--------|-----------|---------|
| v0.71.0 | ✅ Completed | Plan/Apply system | Terraform-style configuration system complete |
| v0.72.0 | ✅ Completed | Plan/Apply cleanup | Legacy commands removed after the Plan/Apply rollout |
| v0.74.0 | ✅ Completed | React default theme | React + shadcn/ui baseline shipped |
| v0.75.0 | ✅ Completed | Forms module | Generic form builder with DRF API, spam protection, and GDPR anonymization |
| v0.76.0 | ✅ Released | Storage module | Cloud file hosting plus CDN-ready media infrastructure; archived in release note and changelog |
| v0.77.0 | ✅ Internal baseline | Backups module | Private local and optional private remote workflows, guarded BackupPolicy-admin local restore, and CLI restore; changelog-only historical baseline |
| v0.78.0 | ✅ Released | Notifications module | Transactional email foundation with app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery; archived in release note and changelog |
| v0.79.0 | ✅ Released | Social and Link Tree module | Curated social links and embeds, backend-owned preview metadata, and React public pages for fresh `showcase_react` generations; older projects adopt them manually |
| v0.80.0 | ✅ Released | Analytics module | PostHog website analytics with flat mutable settings, service-style backend hooks, and fresh `showcase_react` starter support; existing projects adopt frontend snippets manually |
| v0.81.0 | ✅ Released | Beta-site migration maintainer tooling | Maintainer-only fresh-first and checkpoint-first in-place beta-site migration workflows; archived in release note and changelog |
| v0.82.0 | 📋 Planned | Disaster recovery | Disaster recovery plus environment migration and promotion workflows |
| v0.83.0 | 📋 Planned | Billing module | Stripe integration |
| v0.84.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.85.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.80.0 is the published release
- **Active next milestone:** v0.81.0 beta-site migration maintainer tooling is the current planning and implementation-prep scope
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.84.0 - auth, billing, teams modules complete on top of the notifications foundation

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Release doc layout:** [CHANGELOG.md](../../CHANGELOG.md) is the canonical history index; for each published release, `docs/releases/release-vX.XX.X.md` is the single official release note linked from the GitHub tag and release PR; the roadmap tracks active and unreleased release status until that note exists
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)

## ROADMAP

List of upcoming releases with detailed implementation tasks:

---

After release closeout, keep only a concise pointer in the roadmap. Put canonical history in [CHANGELOG.md](../../CHANGELOG.md), and for published releases add `docs/releases/release-vX.XX.X.md` as the single official release note linked from the GitHub tag and release PR. Keep unreleased closeout status in the roadmap until that release note exists.

---

### v0.80.0: `quickscale_modules.analytics` - Analytics Module

**Status**: ✅ Released

**Release note**: [Release v0.80.0 - Analytics Module](../releases/release-v0.80.0.md)

**Closeout note**: Canonical release history now lives in [CHANGELOG.md](../../CHANGELOG.md) and the official release note above. Only deferred follow-up items remain unchecked in this archived milestone section.

**Planning document**: [Analytics Provider Comparison](../planning/analytics-provider-comparison.md) — provider evaluation and reviewed v0.80.0 implementation contract.

**Objective**: Shipped PostHog as the only approved website-analytics provider for v0.80.0. The implementation stays intentionally backend-first: flat mutable analytics settings, service-style capture helpers, guarded forms/social hooks, fresh-generation `showcase_react` starter support, and a manual server-rendered template-tag path without rewriting existing user-owned theme files.

**Scope Guardrails**:
- PostHog only in v0.80.0; no runtime multi-provider seam and no Plausible implementation path in this milestone
- website analytics only; product analytics, session replay, experiments, funnels, and feature flags remain out of scope
- use flat mutable `QUICKSCALE_ANALYTICS_*` settings rather than a single settings dict
- secrets remain env-var references only; raw API keys never live in `quickscale.yml`, generated settings, or state files
- anonymous distinct IDs stay the default; authenticated identity linkage remains explicit operator opt-in
- no analytics-specific context processor expansion
- no generated project-owned extension-app requirement for analytics v0.80.0
- no apply-time rewrites of existing React or HTML theme files
- frontend automation is limited to dormant `showcase_react` starter support on fresh generation; existing projects adopt frontend snippets manually
- social click tracking is limited to QuickScale-owned generated public pages/templates
- forms integration must use a guarded direct optional import and degrade to a clean no-op when analytics is absent or disabled

---

#### A. Analytics Contract (`analytics_contract.py`)

Add `quickscale_cli/src/quickscale_cli/analytics_contract.py` following the same pattern as `notifications_contract.py` and `social_contract.py`.

**Constants and defaults**:
- [x] Define `ANALYTICS_PROVIDER_POSTHOG = "posthog"` and `ANALYTICS_PROVIDERS = ("posthog",)` as the approved v0.80.0 provider set
- [x] Define `DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR = "POSTHOG_API_KEY"` and `DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR = "POSTHOG_HOST"`
- [x] Define `ANALYTICS_POSTHOG_DEFAULT_HOST = "https://us.i.posthog.com"` and `ANALYTICS_POSTHOG_EU_HOST = "https://eu.i.posthog.com"` as known host values
- [x] Define the first-party event vocabulary constants: `ANALYTICS_EVENT_PAGEVIEW`, `ANALYTICS_EVENT_FORM_SUBMIT`, `ANALYTICS_EVENT_SOCIAL_LINK_CLICK`

**Contract functions**:
- [x] `default_analytics_module_options()` returns `enabled`, `provider`, `posthog_api_key_env_var`, `posthog_host_env_var`, `posthog_host`, `exclude_debug`, `exclude_staff`, `anonymous_by_default`
- [x] `normalize_analytics_module_options(options)` strips leading/trailing whitespace, lower-cases provider token, and validates env-var name pattern
- [x] `resolve_analytics_module_options(options)` merges defaults with normalized overrides
- [x] `validate_analytics_env_var_reference(option_name, value)` reuses the same `^[A-Z][A-Z0-9_]*$` pattern as notifications
- [x] `validate_analytics_module_options(options)` returns issue list: provider must be in `ANALYTICS_PROVIDERS`; env-var references must pass pattern; `exclude_debug`, `exclude_staff`, and `anonymous_by_default` must be booleans
- [x] `analytics_production_targeted(options)` returns True when analytics is enabled and a non-placeholder API key env var reference is set
- [x] Export canonical `__all__`

---

#### B. Module Catalog Registration

- [x] Add `analytics` entry to `MODULE_CATALOG` in `quickscale_cli/src/quickscale_cli/module_catalog.py` with a description aligned to the narrower contract:
  ```python
  ModuleCatalogEntry(
      name="analytics",
      description="PostHog website analytics with flat settings and starter-theme support",
      ready=True,
  )
  ```

---

#### C. Module Wiring Spec (`module_wiring_specs.py`)

Add `_analytics_wiring(options)` following the same pattern as `_notifications_wiring` and `_social_wiring`.

**Generated Django settings**:
- [x] Add `quickscale_modules_analytics` to `INSTALLED_APPS`
- [x] Write flat mutable settings instead of a single `QUICKSCALE_ANALYTICS` dict:
  - [x] `QUICKSCALE_ANALYTICS_ENABLED`
  - [x] `QUICKSCALE_ANALYTICS_PROVIDER`
  - [x] `QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR`
  - [x] `QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR`
  - [x] `QUICKSCALE_ANALYTICS_POSTHOG_HOST`
  - [x] `QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG`
  - [x] `QUICKSCALE_ANALYTICS_EXCLUDE_STAFF`
  - [x] `QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT`
- [x] Do not add an analytics context processor
- [x] Document in the generated settings comments that analytics is disabled automatically in `DEBUG=True` environments when `exclude_debug=True`

**`.env.example` additions**:
- [x] `POSTHOG_API_KEY=` (required for live analytics)
- [x] `POSTHOG_HOST=` (optional, defaults to `https://us.i.posthog.com`)
- [x] `VITE_POSTHOG_KEY=` and `VITE_POSTHOG_HOST=` for fresh `showcase_react` generations or explicit manual frontend adoption

**Planner/apply operator output**:
- [x] Show the PostHog dashboard URL and live events verification link
- [x] Remind operators to set `POSTHOG_API_KEY` and `POSTHOG_HOST` as Railway service variables for runtime
- [x] Remind operators that `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` are build-time vars for fresh `showcase_react` generations or manual frontend adoption
- [x] State explicitly that existing React/HTML theme files remain user-owned and are not rewritten by `quickscale apply`

---

#### D. Django Module (`quickscale_modules/analytics/`)

Create the analytics module as a service-style integration module rather than a model-heavy Django app.

```
quickscale_modules/analytics/
├── src/quickscale_modules_analytics/
│   ├── __init__.py
│   ├── apps.py
│   ├── events.py
│   └── services.py
├── tests/
│   ├── test_apps.py
│   ├── test_events.py
│   └── test_services.py
├── pyproject.toml
└── README.md
```

**Service-style module exception**:
- [x] Use the documented exception in `decisions.md`: v0.80.0 analytics does not require `models.py`, `admin.py`, `urls.py`, or migrations because the approved contract is integration-only

**`apps.py`** — PostHog Python SDK initialization:
- [x] Read the flat `QUICKSCALE_ANALYTICS_*` settings from `django.conf.settings`
- [x] If analytics is disabled, or if `exclude_debug=True` while `settings.DEBUG` is true, set the SDK to disabled and return
- [x] Read the API key from `os.environ.get(QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR, "")`
- [x] Read the host from `os.environ.get(QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR, "")` and fall back to `QUICKSCALE_ANALYTICS_POSTHOG_HOST`
- [x] If the API key is empty, disable the SDK and emit a warning outside DEBUG mode
- [x] If configuration is present, initialize the PostHog SDK without raising startup exceptions
- [x] Analytics failure must never prevent Django app startup

**`events.py`** — first-party event vocabulary:
- [x] `ANALYTICS_EVENT_FORM_SUBMIT = "form_submit"`
- [x] `ANALYTICS_EVENT_SOCIAL_LINK_CLICK = "social_link_click"`
- [x] `ANALYTICS_EVENT_PAGEVIEW = "$pageview"`
- [x] Other modules import these constants instead of hardcoding event names

**`services.py`** — server-side capture helpers:
- [x] `is_analytics_active() -> bool` returns True only when the SDK is initialized and not disabled
- [x] `capture_event(distinct_id: str, event: str, properties: dict | None = None) -> None` wraps `posthog.capture()` and never raises
- [x] `capture_form_submit(distinct_id: str, form_id: int | str, form_name: str = "", extra: dict | None = None) -> None` emits the canonical forms event payload
- [x] `capture_social_link_click(distinct_id: str, provider: str, link_id: int | str, extra: dict | None = None) -> None` emits the canonical social link click payload
- [x] `get_distinct_id(request) -> str` returns a user PK string only when the operator has opted out of anonymous-by-default; otherwise it uses a stable session identifier

---

#### E. Frontend Scope and Adoption Boundaries

**Fresh `showcase_react` generations only**:
- [x] Add dormant PostHog starter support inside the generator-owned `showcase_react` templates
- [x] The starter wiring initializes only when `VITE_POSTHOG_KEY` is present and not a placeholder
- [x] React route tracking uses PostHog's `history_change` pageview mode
- [x] Fresh generations pick up the starter support automatically after the template update lands

**Existing React and HTML projects**:
- [x] `quickscale apply` does not rewrite existing `frontend/package.json`, `src/main.*`, `src/App.*`, or Django template files
- [x] Existing projects adopt any React or HTML analytics snippets manually if they want frontend capture
- [x] Documentation must keep that manual-adoption boundary explicit rather than implying managed retrofits

**HTML theme scope in v0.80.0**:
- [x] Add and document the manual template-tag path for server-rendered pages
- [x] Do not add an analytics context processor or promise apply-managed HTML template mutation

---

#### F. Cross-Module Hooks

**Forms → Analytics**:
- [x] Wire the forms submission success path with a guarded direct optional import of `analytics.services.capture_form_submit`
- [x] If analytics is not installed, not enabled, or not importable, forms submission continues normally with no analytics side effect
- [x] Do not generate analytics-specific glue in a project-owned extension app for v0.80.0

**Social → Analytics**:
- [x] Limit click tracking to QuickScale-owned generated public pages/templates that QuickScale already owns
- [x] Do not promise automatic instrumentation for project-owned custom social pages or existing user-owned theme files

---

#### G. CLI Plan/Apply Integration

**`quickscale plan`**:
- [x] Add `analytics` to the module selection menu with description "PostHog website analytics (free tier: 1M events/month)"
- [x] Prompt for enable/disable, API key env var name, host, exclude-debug, exclude-staff, and anonymous-by-default behavior
- [x] Keep the planner output focused on PostHog only; Plausible remains documentation, not a runtime option

**`quickscale apply`**:
- [x] Add the analytics module to `INSTALLED_APPS`
- [x] Write the flat `QUICKSCALE_ANALYTICS_*` settings
- [x] Update `.env.example` with the PostHog runtime vars and the React build-time vars
- [x] Emit operator next steps and manual-adoption guidance for existing frontend files
- [x] Do not mutate existing React or HTML theme files

**`quickscale plan --reconfigure`**:
- [x] Analytics settings remain mutable and re-runnable through the planner
- [x] Disabling analytics removes the backend/module wiring and flat settings
- [x] Disabling analytics does not attempt to clean up user-owned frontend snippets or custom event calls

**`quickscale status`**:
- [ ] Show provider, host, API key env var name, env-var presence in the current environment, and SDK state

---

#### H. Railway Compatibility

- [x] `POSTHOG_API_KEY` and `POSTHOG_HOST` must be Railway service variables for runtime use
- [x] `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` are build-time vars for fresh `showcase_react` generations or manual adoption paths
- [x] `https://eu.i.posthog.com` remains the documented EU host option
- [x] Apply-time guidance should call out CSP or referrer-policy implications when operators lock down outbound script or API hosts

---

#### I. Module Extension Contract

Following [module-extension.md](./module-extension.md), analytics v0.80.0 uses the narrower service-style contract.

**What QuickScale owns**:
- [x] Flat `QUICKSCALE_ANALYTICS_*` settings
- [x] `apps.py`, `events.py`, and `services.py`
- [x] Guarded forms hook support
- [x] Social click tracking only where QuickScale owns the generated public page/template
- [x] Dormant `showcase_react` starter support for fresh generations

**What the project owns**:
- [x] Existing theme files and any manual analytics adoption inside them
- [x] Custom event capture from project-owned views, templates, and React components
- [x] Any project-owned extension-app glue beyond the shipped module contract
- [x] PostHog dashboards, funnels, goals, and broader product analytics configuration

**Structured extension points (Tier 1)**:
- [x] `QUICKSCALE_ANALYTICS_*` settings
- [x] `analytics.services.capture_event(...)`
- [x] `analytics.services.capture_form_submit(...)`
- [x] `analytics.services.capture_social_link_click(...)`
- [x] `analytics.services.get_distinct_id(request)`
- [x] `analytics.events.*`

**Upgrade expectations**:
- [x] Existing user-owned frontend files are not rewritten by analytics apply/reconfigure flows
- [x] Direct edits under `modules/analytics/` remain outside the supported extension contract

---

#### J. Testing Scope

**Contract unit tests** (`quickscale_cli/tests/test_analytics_contract.py`):
- [x] Defaults, normalization, validation, and production-targeted checks cover the approved PostHog-only options

**Wiring spec tests** (`quickscale_cli/tests/test_module_wiring_specs.py`):
- [x] Analytics enabled writes the flat `QUICKSCALE_ANALYTICS_*` settings and adds `quickscale_modules_analytics` to `INSTALLED_APPS`
- [x] Analytics disabled omits the module wiring
- [x] No analytics context processor is added

**Module unit tests** (`quickscale_modules/analytics/tests/`):
- [x] `apps.py` disables safely when configuration is missing or DEBUG exclusion applies, and never raises
- [x] `services.py` no-ops safely when analytics is inactive and emits the expected event payload shapes when active
- [x] `events.py` exposes the stable event vocabulary constants

**Cross-module tests**:
- [x] Forms submission keeps working when analytics is absent and emits the expected event only when the guarded optional import path is available
- [x] Social click tracking coverage is limited to QuickScale-owned generated public pages/templates

**Frontend/generator tests**:
- [x] Fresh `showcase_react` generations include the dormant analytics starter support
- [x] Applying analytics to an existing project does not rewrite user-owned React or HTML theme files

**Manual / smoke verification**:
- [ ] PostHog live events view confirms pageviews and first-party conversion events on a fresh-generated React project
- [x] Existing projects rely on documented manual adoption steps for frontend analytics

---

### v0.81.0: Beta-Site Migration Maintainer Tooling

**Status**: ✅ Released

**Release note**: [Release v0.81.0 - Beta-Site Migration Maintainer Tooling](../releases/release-v0.81.0.md)

**Closeout note**: Maintainer-only beta-site migration tooling shipped with deterministic fresh-first execution and checkpoint-first in-place continuation. Canonical history now lives in [CHANGELOG.md](../../CHANGELOG.md) and the official release note; this roadmap entry remains only as a concise navigation pointer together with the [Beta Site Migration Playbook](../planning/beta-site-migration.md).

---

### v0.82.0: Disaster Recovery & Environment Migration Workflows

**Status**: 📋 Planned

**Phase 1 note**: This milestone update locks the authoritative docs contract only. Runtime capture, resume, restore, rollback, and promotion behavior remain planned until the corresponding implementation and validation land.

**Objective**: Extend the current database-first backups line into controlled stored project snapshots and environment migration workflows for generated projects across local, Railway develop, and Railway production, while keeping the v0.77 dump-restore contract authoritative.

**Scope Guardrails**:
- keep the v0.77 database-first restore contract authoritative until broader portability workflows are specified, implemented, and validated
- keep secrets as references or required operator inputs only; never persist raw credential values in stored snapshot artifacts or migration manifests
- keep generated-project config/state surfaces limited to `quickscale.yml`, `.quickscale/state.yml`, and `.quickscale/config.yml`; v0.82 does not add a second project-owned config or state channel
- derive all v0.82 stored snapshot files from one private operational root under `modules.backups.local_directory`
- keep `restore_scope` database-artifact-only for stored snapshots; broader route eligibility is evaluated separately by later CLI workflows
- keep direct operator file-path restore as the separate dump-restore mode from v0.77 rather than a competing stored-snapshot locator
- treat database dump, media sync, environment-variable metadata, release metadata, and promotion verification as separate operational surfaces rather than a single opaque "whole system" blob

**Stored Snapshot Contract (authoritative planning baseline, not yet shipped)**:
- stored project snapshots are internal row-backed records in the backups module; they are not user-authored config files or generated project structure
- each stored snapshot receives an immutable opaque `snapshot_id` when its row is created, and `snapshot_id` is the only supported stored-snapshot locator
- each stored snapshot owns exactly one authoritative database-dump `BackupArtifact` row
- the private local layout is fixed under the backups root:

```text
<modules.backups.local_directory>/
└── snapshots/
  └── <snapshot_id>/
    ├── database/
    │   └── <backup filename>
    ├── media-sync-manifest.json
    ├── env-var-manifest.json
    ├── release-metadata.json
    └── promotion-verification.json
```

- local copies remain primary; optional private remote offload mirrors the same child keys remotely
- `restore_scope` resolves only the authoritative database dump artifact for stored snapshots; media, env-var, release-metadata, and verification files remain adjacent but separate surfaces
- direct operator file-path restore stays separate from stored-snapshot lookup by `snapshot_id`
- rollback pins are time-bounded, prune-aware operational references tied to retained snapshot data; they must fail cleanly once the pinned retained data has expired or been pruned

**Portable Artifact Boundaries**:

| Artifact / surface | Included in the promotion workflow | Boundary rule |
| --- | --- | --- |
| **Database dump artifact** | Yes | exactly one authoritative `BackupArtifact` dump row per stored snapshot; this is the only stored-snapshot artifact addressable by `restore_scope` |
| **Media sync manifest** | Yes | carry object keys, paths, checksums, and target mapping; keep separate from `restore_scope` and do not treat public URLs or CDN hostnames as source-of-truth state |
| **Environment-variable name manifest** | Yes | carry names, purpose, required/optional status, and target owner; never persist raw secret values |
| **Release metadata** | Yes | carry QuickScale version, enabled modules, git SHA, and sanitized config/version notes needed to reproduce the environment |
| **Promotion verification report** | Yes | carry dry-run output, smoke-test results, operator confirmations, and rollback-pin references without collapsing the other surfaces into a single blob |
| **Raw secrets / provider tokens** | No | remain in local secret storage, Railway variables, or the target secret manager only |
| **CDN, DNS, and custom-domain resources** | No | reference by host or resource name only; manage them as provider-owned infrastructure outside backup artifacts |
| **Static build artifacts** | No | rebuild through the normal git/deploy pipeline; do not ship them as restore/promotion artifacts |

Application source code also moves through the normal git/deploy pipeline. The portable artifact set is limited to the operational surfaces above and must not turn into a second code-distribution channel.

**Workflow Checklist**:

**Local → Railway develop**:
- [ ] Capture a fresh local stored project snapshot: current git SHA via the normal deploy path, one authoritative PostgreSQL dump artifact, the separate media sync manifest, env-var name manifest, release metadata, and baseline smoke-check notes under `snapshots/<snapshot_id>/`
- [ ] Provision Railway develop prerequisites: PostgreSQL 18 target, storage backend, media host/CDN target, and environment-variable slots owned by Railway rather than by the stored snapshot
- [ ] Run a dry-run migration plan against Railway develop and fail early on missing variables, incompatible storage targets, or attempts to widen `restore_scope` beyond the stored database dump artifact
- [ ] Apply the generated project/configuration to Railway develop without exporting or storing raw secrets inside stored snapshot artifacts
- [ ] Restore the authoritative database dump, sync media objects through the manifest, and run migrations or repair steps required by the target environment
- [ ] Verify Railway develop with smoke checks covering auth, forms/notifications, storage URLs, and backups guardrails before treating it as the next promotion source

**Railway develop → Railway production**:
- [ ] Capture a fresh develop stored project snapshot instead of reusing the earlier local snapshot set so production promotion starts from the validated develop state
- [ ] Diff the develop and production environment-variable name manifests and resolve required production-only values before promotion begins
- [ ] Confirm production storage, `public_base_url`, CDN/domain prerequisites, destructive-step confirmations, and rollback-pin retention before any restore or sync action
- [ ] Run a dry-run production promotion plan with explicit rollback-pin references and a signed operator checkpoint
- [ ] Promote the database dump and media manifest using the same separated artifact surfaces rather than a single opaque environment bundle
- [ ] Run production smoke checks, record the promotion verification report, and preserve rollback references only for the documented time-bounded retention window

**Railway production → Railway develop (recovery rehearsal / disaster recovery)**:
- [ ] Capture a fresh production recovery checkpoint: current production git SHA/release metadata, a production database dump artifact, media sync manifest, environment-variable name manifest, and the latest verification report references
- [ ] Provision or refresh an isolated Railway develop recovery target so production data is restored into non-production database, storage, and domain surfaces only
- [ ] Run a dry-run recovery plan that remaps production hosts, media targets, variable ownership, and rollback-pin expectations into develop-safe values before any restore begins
- [ ] Restore the database dump and media manifest into Railway develop using the separated artifact set, with any required data sanitization or operator-access controls applied before broader testing
- [ ] Reconcile the recovered develop environment with the target git/deploy state for the improvements you want to test, without copying raw production secrets into the recovery artifacts
- [ ] Run smoke and regression checks in Railway develop, then record the recovery verification report and rollback references so the same flow can serve both rehearsal and disaster-recovery needs

**Implementation Tasks**:
- [x] Lock the stored project-snapshot contract across the authoritative docs before runtime work mutates code or CLI behavior
- [ ] Define the internal stored-snapshot row shape and immutable `snapshot_id` minting rules inside the backups module
- [ ] Keep direct file-path restore as separate dump-restore mode while adding `snapshot_id`-based stored-snapshot resolution for planned v0.82 workflows
- [ ] Add dry-run environment migration plans for local → Railway develop, Railway develop → Railway production, and Railway production → Railway develop based on the explicit artifact boundaries above
- [ ] Add Railway-specific capture/apply helpers for service variables, media prerequisites, and release metadata without persisting raw credentials
- [ ] Add integrity checks, resume behavior, rollback-pin handling, and explicit operator confirmations for destructive restore/promotion steps
- [ ] Document disaster-recovery workflows separately from environment-promotion workflows so operators know what is and is not transported automatically

**Acceptance Gates**:
- [ ] Runtime closeout requires resume coverage for interrupted snapshot capture, private-remote mirroring, and promotion flows without minting alternate stored-snapshot locators
- [ ] Runtime closeout requires rollback coverage using time-bounded, prune-aware rollback pins with clear operator feedback when the pinned data is gone
- [ ] Runtime closeout requires partial-failure coverage so database, media, env-var metadata, release metadata, and verification surfaces can fail or recover independently with auditable status

**Testing**:
- [ ] Validate database dump restore, media sync, environment metadata handoff, release metadata capture, and verification reporting independently before full project-promotion flows
- [ ] End-to-end rehearse representative local → Railway develop, Railway develop → Railway production, and Railway production → Railway develop migrations
- [ ] Verify backup artifacts and migration manifests never expose raw secrets or public backup URLs

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

### v0.85.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---
