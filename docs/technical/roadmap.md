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
| v0.81.0 | 📋 Planned | Beta-site migration maintainer tooling | Make-invoked Python automation for the fresh-first and in-place beta-site catch-up workflows |
| v0.82.0 | 📋 Planned | Disaster recovery | Disaster recovery plus environment migration and promotion workflows |
| v0.83.0 | 📋 Planned | Listings theme | Real-estate vertical baseline with static pages, listings, and social links |
| v0.84.0 | 📋 Planned | CRM theme | React frontend for the CRM module |
| v0.85.0 | 📋 Planned | Billing module | Stripe integration |
| v0.86.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.87.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance |
| v0.88.0 | 📋 Planned | Module management UX | Advanced update, status, and discovery workflows |
| v0.89.0 | 📋 Planned | Workflow validation | Real-world multi-module, storage/CDN, deployment, safety, and end-to-end validation |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.80.0 is the published release
- **Active next milestone:** v0.81.0 listings theme is the current planning and implementation-prep scope
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.86.0 - auth, billing, teams modules complete on top of the notifications foundation

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

**Status**: 📋 Planned

**Planning document**: [Beta Site Migration Playbook](../planning/beta-site-migration.md) — maintainer-only catch-up workflows for `experto-ai-web` and `bap-web`.

**Objective**: Ship beta-site-only maintainer automation for the fresh-first and in-place catch-up flows as Make-invoked Python tooling. The supported surface is `make beta-migrate-fresh` and `make beta-migrate-in-place`; this milestone does not add a public `quickscale` CLI command or a QuickScale module.

**Scope Guardrails**:
- beta-site-only maintainer workflow; keep the surface out of `quickscale --help`
- use Make as the maintainer entrypoint and Python scripts under `scripts/`; prefer structured TOML/YAML/JSON manipulation over bash-heavy pipelines
- keep `DONOR` and `RECIPIENT` as explicit required inputs; no path auto-discovery
- preserve QuickScale ownership boundaries: older user-owned theme files remain manual-adoption territory outside this documented beta-site workflow
- fresh-first is the primary deterministic path; in-place may pause at explicit review checkpoints rather than guessing through destructive merges
- do not automate git push, PR merge, Railway deploy, or secret population; print next steps instead
- do not copy `.git`, `media/`, `.env`, or `poetry.lock` between projects; regenerate derived artifacts only inside the active working tree when the workflow explicitly reaches that step

#### A. Maintainer Command Surface

- [ ] Add `make beta-migrate-fresh DONOR=/abs/path RECIPIENT=/abs/path`
- [ ] Add `make beta-migrate-in-place DONOR=/abs/path RECIPIENT=/abs/path`
- [ ] Add `make beta-migrate-help` to print required variables, modes, and safety notes
- [ ] Route the Make targets through `poetry run python scripts/beta_migrate.py <mode>` so the implementation stays in Python rather than shell
- [ ] Document the targets in `Makefile` help, `scripts/README.md`, and the migration playbook

#### B. Python Script Architecture

- [ ] Create `scripts/beta_migrate.py` as the single entrypoint with `fresh-first` and `in-place` modes
- [ ] Use stdlib `argparse`, `pathlib`, `shutil`, `subprocess`, `json`, and `tomllib`; use existing YAML/TOML writer dependencies only where writes are required
- [ ] Model shared state explicitly with typed data structures for resolved identities, migration inputs, planned actions, and pending manual actions
- [ ] Keep shared helpers in Python functions first; split into an additional helper module only if the file becomes hard to review

#### C. Shared Deterministic Helpers

- [ ] Resolve `project.slug`, `project.package`, module lists, and filesystem paths from `quickscale.yml` and `pyproject.toml`
- [ ] Validate required files exist before mutation begins, with explicit blocker messages when they do not
- [ ] Enforce clean git state for the in-place recipient before destructive file replacement or `quickscale apply`
- [ ] Implement a `--dry-run` mode that prints the exact planned actions without mutating files
- [ ] Emit a machine-readable and human-readable report with `completed_steps`, `skipped_steps`, `changed_files`, and `pending_manual_actions`
- [ ] Stop with a pending-actions report whenever the script cannot safely choose between multiple valid outcomes

#### D. Fresh-First Flow

- [ ] Implement the current reference steps in order: identity reconciliation, `App.tsx`, custom-only pages, non-`ui/` component directories, src utilities, selected Django files, and missing module path dependencies
- [ ] Preserve the fresh scaffold's managed files and fresher infrastructure exactly as classified in the playbook table
- [ ] Add verification subprocess steps for `poetry lock`, `poetry install`, `pnpm install`, `pnpm build`, `quickscale manage migrate`, `pytest`, and `pnpm test`
- [ ] Treat the production-repo replacement, push, and deploy sequence as a printed follow-up checklist rather than an automatic side effect

#### E. In-Place Flow

- [ ] Implement deterministic infrastructure file copies from donor to recipient, including slug/package substitution
- [ ] Merge `pyproject.toml` by taking donor non-path dependencies and retaining recipient module path dependencies
- [ ] Merge `frontend/package.json` while preserving the recipient package name
- [ ] Update `quickscale.yml` with newly introduced modules only
- [ ] Require an explicit review checkpoint before `quickscale apply` when the module diff or infrastructure diff is non-empty
- [ ] After `quickscale apply`, copy only the missing module-owned React pages, hooks, and components documented in the playbook
- [ ] Reuse the same verification subprocess stack as fresh-first

#### F. Deterministic Boundary and Pending Work Contract

- [ ] Fresh-first should be able to run deterministically through local verification on a throwaway recipient
- [ ] In-place should be allowed to stop before `quickscale apply` with a complete pending-actions report if module adoption needs operator review
- [ ] Both modes must print the remaining manual tasks for smoke testing, env vars, PR creation, merge, deploy, and rollback
- [ ] If only a partial implementation ships, the report format becomes the handoff contract for the next AI coding assistant rather than silent TODO comments in code

#### G. Implementation Sequence for an AI Coding Assistant

1. Freeze the maintainer surface first: Make targets, required env vars, script modes, and report format.
2. Implement shared identity and report helpers plus `--dry-run` before any destructive file mutation.
3. Land fresh-first file operations and verification before attempting in-place automation.
4. Implement in-place pre-apply merges next, then add the explicit review checkpoint.
5. Only after the checkpoint is stable, automate the post-apply React page adoption steps.
6. If in-place full automation is not yet safe, stop at the checkpoint and ship the pending-actions report rather than guessing.
7. Keep docs in sync with the shipped behavior: `docs/planning/beta-site-migration.md`, `scripts/README.md`, and `Makefile` help must match the tool exactly.
8. Do not expand this maintainer workflow into a public `quickscale` CLI feature inside v0.81.0.

#### H. Validation

- [ ] Add focused pytest coverage for deterministic transformation helpers using temp directories and fixture projects
- [ ] Rehearse fresh-first on throwaway copies of both beta sites
- [ ] Rehearse in-place on throwaway branches with a deliberately added module diff
- [ ] Verify dry-run and pending-actions outputs are sufficient for a second AI coding assistant to resume without rereading repository history

---

### v0.82.0: Disaster Recovery & Environment Migration Workflows

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

### v0.83.0: Listings Theme (React Frontend for Listings)

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

### v0.84.0: CRM Theme (React Frontend for CRM)

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

### v0.85.0: `quickscale_modules.billing` - Billing Module

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

### v0.86.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

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

### Module Showcase Architecture (Deferred to Post-v0.86.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.86.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on the current core roadmap line through SaaS feature parity first (v0.68.0-v0.86.0)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for the shipped generator output

**Implementation Plan**: After v0.86.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns.

---

### v0.87.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---

### v0.88.0: Advanced Module Management Features

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
- [ ] Filter `quickscale plan` module selection to release-ready modules by default and keep experimental entries opt-in
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

**Future Enhancements** (v0.89.0+, evaluate after v0.86.0):
- [ ] Module versioning: `quickscale plan --add auth@v0.63.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.89.0: Module Workflow Validation & Real-World Testing

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
- [ ] Dogfood regression coverage: hyphenated `project.slug` plus underscored `project.package` must work across apply, reconfigure, and remove flows
- [ ] Auth adoption guardrails: fail early with actionable remediation when auth/custom-user wiring is requested after incompatible migration history already exists
- [ ] Idempotency regression coverage: repeated apply/remove cycles must not duplicate managed settings or URL wiring
- [ ] Storage validation: add upload/write/read integration coverage for local storage and mocked S3-compatible backends
- [ ] Storage/blog workflow validation: add Plan → Apply → Blog publish E2E coverage with CDN-backed media URLs
- [ ] Storage URL regression validation: verify helper-built public media URLs remain canonical across blog rendering and upload flows in real project scaffolds
- [ ] Forms/notifications workflow validation: add Plan → Apply → form submission → tracked delivery coverage, plus fallback validation when notifications is absent or disabled
- [ ] Railway CDN reconciliation: validate Railway edge/custom-domain/CDN guidance against the storage `public_base_url` contract and document the supported static-vs-media split
- [ ] Documentation: Create "Safe Module Updates" guide with screenshots and case studies

**Rationale**: Module embed/update commands implemented in v0.62.0, Plan/Apply system in v0.68.0-v0.71.0. This release validates those systems work safely in production after real usage across multiple client projects.

---
