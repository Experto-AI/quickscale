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
| v0.82.0 | ✅ Released | Disaster recovery & environment promotion | Public `quickscale dr` capture/plan/execute/report workflows with `snapshot_id` lookup, resumable capture/execute, rollback pins, conservative env-var sync, and source-side media sync; archived in release note and changelog |
| v0.83.0 | 🟡 In progress (unreleased) | Hardening release | Phases 1-8 are complete in repo; Phase 8b is the remaining pre-tag hardening and release-closeout backlog before tag/release artifacts |
| v0.84.0 | 📋 Planned | Billing module | Stripe integration after v0.83.0 hardening closes the current platform and module contract gaps |
| v0.85.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.86.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the hardening, billing, and teams milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo but not yet tagged/released
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.82.0 is the published release
- **Current in-repo milestone:** v0.83.0 hardening has Phases 1-8 complete in repo; Phase 8b is the remaining pre-tag backlog before tag/release-time artifacts
- **Next planned feature milestone:** v0.84.0 billing module
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.85.0 - auth, billing, teams modules complete on top of the notifications foundation

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Release doc layout:** [CHANGELOG.md](../../CHANGELOG.md) is the canonical history index; for each published release, `docs/releases/release-vX.XX.X.md` is the single official release note linked from the GitHub tag and release PR; the roadmap tracks active and unreleased release status until that note exists
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [Release Summary Template](./release_summary_template.md) for the single public release-note workflow

## ROADMAP

List of upcoming releases with detailed implementation tasks:

---

After release closeout, keep only a concise pointer in the roadmap. Put canonical history in [CHANGELOG.md](../../CHANGELOG.md), and for published releases add `docs/releases/release-vX.XX.X.md` as the single official release note linked from the GitHub tag and release PR. Keep unreleased closeout status in the roadmap until that release note exists.

---

### v0.83.0: Hardening Release

**Status**: 🟡 Phases 1-8 complete in repo; Phase 8b remains (unreleased)

**Goal**: Close the repo-wide audit findings before shipping the next new public module release. This milestone hardens the current plan/apply surface, managed wiring behavior, shipped starter themes, module contract fidelity, metadata parity, and regression coverage so later billing and teams work lands on a stable documented base.

**Current status (2026-05-01)**: The hardening implementation now has Phases 1-8 complete in repo. Phase 8 closeout finished with generated production-settings fail-hard behavior, CRM dashboard access-control parity plus shipped starter-theme caller parity, forms/backups operator-surface hardening, and blog upload resource guards recorded below. Phase 8b is now the remaining pre-tag backlog: it consolidates the pending deep-review follow-ups plus the still-unrun Docker-backed release closeout, and publish-time artifacts remain deferred until a real tag/release exists, so v0.82.0 remains the current published release.

**Completed scope retained as a pointer**

- Phase 1 complete: CLI state and managed wiring failure semantics landed and were validated.
- Phase 2 complete: shipped starter-theme contract cleanup landed.
- Phase 3 complete: shared dependency and install contract infrastructure landed.
- Phase 4 complete: blog and listings runtime contract fixes landed.
- Phase 5 complete: auth/forms/CRM shipped contract cleanup landed.
- Phase 6 complete: packaged metadata parity and placeholder leakage cleanup landed.

Detailed completed checklists for Phases 1-6 were removed from this section to keep continuation focused on the remaining pre-tag work.

#### Phase 7: Cross-Cutting Release Gates and Docs Closeout

**Primary code grouping**: repo-wide validation, SSOT reconciliation, package/module documentation alignment, and milestone closeout tracking.

**Current status (2026-05-01)**: Phase 7 is complete in repo. The final planner follow-up now hard-rejects invalid live notifications settings before existing-project add/reconfigure writes, including the state-only reconfigure path, and the previously landed schema/auth/docs/SSOT/test/syntax cleanup work remains in place. Phase 8b is now the remaining v0.83.0 pre-tag hardening backlog.

**Resolved planning decisions retained here**

- Schema version stays canonical at `"1"` for both `quickscale.yml` and `.quickscale/state.yml`; the remaining drift is docs/SSOT/example alignment, not parser or writer behavior selection.
- Existing-project planner handling for config-only legacy auth desired config is a deliberate breaking change: reject it hard with remediation instead of adding planner-side canonicalization or backward-compatible prefills.
- Desired-config rejection must happen at raw `validate_config` / module-option boundaries for every `quickscale.yml` consumer before `ModuleConfig` sanitization. Tolerance for legacy auth shapes remains only when loading already-written applied state and state-derived wiring.

- [x] Existing-project planner reconfigure and add-modules flows now fail hard for config-only legacy auth snapshots instead of rewriting `quickscale.yml`, with actionable remediation and dedicated regression coverage in place.
- [x] The analytics regression expectation in `quickscale_modules/analytics/tests/test_services.py` now matches the shipped enabled-by-default behavior when the setting is missing.
- [x] CLI desired-config auth boundary enforcement for shipped auth/module options now happens at the raw validation boundary across `quickscale.yml` consumers before `ModuleConfig` sanitization can hide drift, with regression coverage protecting the strict contract.
- [x] The notifications planner/apply boundary now rejects the `noreply@example.com` `sender_email` placeholder whenever live Resend delivery is targeted, keeping planner/apply validation aligned with the shipped manifest contract.
- [x] `docs/technical/plan-apply-system.md` and `docs/technical/user_manual.md` are aligned to schema version `"1"` and the fail-hard auth guidance.
- [x] `docs/technical/decisions.md` now uses the narrowed module-API wording that matches the shipped routed endpoint surface.
- [x] A refreshed active-source sweep no longer finds comma-form `except A, B:` multi-exception syntax in `quickscale_cli/src`, `quickscale_core/src`, or `quickscale_modules/*/src`.

**Phase 7 completion record (2026-05-01)**

Phase 7 no longer has an execution handoff. The remaining unreleased v0.83.0 backlog now starts at Phase 8b.

1. Existing-project planner add/reconfigure flows now abort before rewriting `quickscale.yml` when live notifications config is incomplete or still using the production placeholder, including the state-only reconfigure path.
2. Planner regression coverage now includes `quickscale_cli/tests/test_plan_add.py::test_plan_add_aborts_before_rewrite_for_invalid_live_notifications_config` and `quickscale_cli/tests/test_plan_reconfigure.py::test_plan_reconfigure_state_only_aborts_before_write_for_invalid_live_notifications`; apply/module-config notifications parity coverage also passed.
3. `docs/technical/plan-apply-system.md` and `docs/technical/user_manual.md` already reflect schema version `"1"` and canonical auth guidance, so the docs/SSOT cleanup tracked in this phase is closed.
4. `docs/technical/decisions.md` already carries the narrowed module-API wording, and `quickscale_modules/analytics/tests/test_services.py` now matches the shipped enabled-by-default analytics behavior when the setting is absent.
5. A refreshed active-source sweep no longer finds comma-form `except A, B:` syntax in `quickscale_cli/src`, `quickscale_core/src`, or `quickscale_modules/*/src`.
6. v0.82.0 remains the current published release; Phase 8b is now the remaining v0.83.0 pre-tag backlog.

**Recorded validation context**

- Phase 1-6 closeout validation remains the previously recorded `make ci-e2e` and `make version-check` evidence.
- Phase 7 completion evidence includes the planner add/reconfigure regressions for invalid live notifications config plus passed apply/module-config notifications parity coverage.
- The current published release pointer stays at v0.82.0 until a v0.83.0 tag/release exists.

#### Phase 8: Hardening Review Follow-Ups

**Primary code grouping**: generated production settings, privileged operator surfaces, exported-data hygiene, module access-control parity, and upload resource guards.

**Current status (2026-05-01)**: Phase 8 is complete in repo. Generated production settings now fail hard for blank or shipped-placeholder `SECRET_KEY` values while local startup remains valid; the CRM HTML dashboard is staff-only with README parity and shipped starter-theme caller parity; forms CSV exports neutralize formula-prefixed headers and values; backup admin downloads enforce authoritative-root containment with symlink rejection; and blog automation uploads enforce API-boundary max-dimension guards. Phase 8b is now the remaining unreleased v0.83.0 hardening backlog, including the still-pending Pillow follow-ups beyond those API-boundary guards.

- [x] Generated production settings now fail hard when `SECRET_KEY` is blank or still using the shipped placeholder. `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2` no longer falls back to `"django-insecure-change-this-in-production"`, local/dev examples stay convenient without implying production safety, and generator template regressions cover both empty and placeholder env cases.
- [x] The CRM dashboard now requires staff authentication, and shipped starter themes no longer present `/crm/` as a generic destination. `quickscale_modules/crm/src/quickscale_modules_crm/views.py` guards the HTML surface, the README/runtime contract is aligned to the staff-only boundary, `quickscale_core` showcase HTML/React starters now match that boundary, and CRM plus generator regressions keep this surface from drifting public again.
- [x] Forms CSV exports now neutralize spreadsheet formula injection. `quickscale_modules/forms/src/quickscale_modules_forms/views.py` applies a shared CSV-cell sanitizer to exported field values and dynamic headers that can originate from form definitions, with regression coverage for formula-prefixed payloads.
- [x] Backup admin downloads are now constrained to authoritative backup roots instead of trusting `artifact.local_path` blindly. `quickscale_modules/backups/src/quickscale_modules_backups/services.py` and `quickscale_modules/backups/src/quickscale_modules_backups/admin.py` resolve against the active backup roots, reject symlinks and out-of-tree paths, and include service/admin regressions proving tampered or drifted rows cannot become arbitrary staff downloads.
- [x] Blog automation uploads now enforce API-boundary pixel-dimension guards. `quickscale_modules/blog/src/quickscale_modules_blog/views.py` and `quickscale_modules/storage/src/quickscale_modules_storage/helpers.py` apply explicit width/height ceilings for automation uploads, with upload regressions covering oversized dimensions. The remaining Pillow `DecompressionBombError` follow-ups are tracked in Phase 8b.

**Phase 8 completion record (2026-05-01)**

Phase 8 no longer has an execution handoff. The remaining unreleased v0.83.0 hardening backlog now starts at Phase 8b.

1. Generated production settings now hard-fail for blank or shipped-placeholder `SECRET_KEY` values while local startup remains valid. Focused generator template coverage passed via `poetry run pytest quickscale_core/tests/test_generator/test_templates.py`.
2. The CRM HTML dashboard now matches the staff-only runtime contract, README wording is aligned, and shipped starter themes now keep generic CRM navigation off the staff-only `/crm/` surface. Focused CRM view coverage passed via `poetry run pytest quickscale_modules/crm/tests/test_views.py`, and focused starter-theme parity coverage passed via `poetry run pytest --no-cov quickscale_core/tests/test_html_theme_integration.py quickscale_core/tests/test_react_theme_integration.py`.
3. Forms CSV exports now neutralize formula-prefixed headers and values, and backup admin downloads now enforce authoritative-root containment with symlink rejection. Focused validations passed via `poetry run pytest quickscale_modules/forms/tests` and `make MODULE=backups test-unit -- --modules`.
4. Blog automation uploads now enforce width/height ceilings at the API boundary. Focused validations passed via `poetry run pytest quickscale_modules/storage/tests/test_helpers.py` and `poetry run pytest -o addopts='-v --cov=quickscale_modules_blog --cov-report=term-missing --cov-fail-under=90' quickscale_modules/blog/tests`; the remaining Pillow exception-path gaps are tracked in Phase 8b.
5. Phase 8b is now the remaining unreleased v0.83.0 hardening backlog, and v0.82.0 remains the current published release.

**Recorded validation context**

- Focused validations for the generator, CRM, `quickscale_core` starter-theme caller parity, forms, backups, storage-helper, and blog slices passed as listed above.
- Full `make test` also passed after the starter-theme CRM caller-parity follow-up; Docker-backed `make test-e2e` / `make ci-e2e` remain pending and are tracked in Phase 8b because no local container runtime is available in this shell yet.
- Combined `forms` + `backups` and combined `blog` + `storage` pytest invocations are intentionally not recorded here because module-local Django harness separation and cross-module import-path mismatch make those mixed commands unreliable in this repo.
- Publish-time artifacts remain deferred until a real v0.83.0 tag/release exists.

---

#### Phase 8b: Remaining Release-Closeout and Deep-Review Follow-Ups

**Primary code grouping**: release-closeout prerequisites, Docker-backed E2E validation, Pillow exception gaps, CRM API access-control parity, silent error suppression in core utilities, and missing rate-limiting on write APIs.

**Current status (2026-05-01)**: This is the active v0.83.0 handoff section. Phase 8 code work is complete in repo, but release-grade closeout is still pending. Local `make test` passed after the final starter-theme CRM caller-parity follow-up, while Docker-backed `make test-e2e` / `make ci-e2e` remain blocked in this shell because no `docker`, `docker compose`, or `docker-compose` command is installed and passwordless `sudo` is unavailable for unattended package installation. The source-confirmed deep-review backlog below also remains unfixed. This Phase 8b section consolidates the former Phase 9 hardening backlog plus the remaining release-closeout environment work so continuation can start from one place.

- [ ] Restore local release-closeout prerequisites for E2E. Install Docker Engine, ensure a working daemon, and provide a Compose-compatible command path for this environment. Current local blocker: Ubuntu 24.04 host has `apt-get`, `curl`, and `sudo`, but no `docker`, `docker compose`, or `docker-compose`; `sudo -n` fails, so unattended installation from this session is blocked until privileged package install is available.
- [ ] Install or verify Playwright Chromium prerequisites for local E2E once Docker is available. The current repo runner uses `poetry run playwright install chromium`; use the deps path if the host still lacks browser system dependencies.
- [ ] Run the remaining release-grade validation stack and record the result: `make test-e2e`, then `make ci-e2e`, plus `make version-check` if fresh release-closeout evidence is needed.

- [ ] Catch `PIL.Image.DecompressionBombError` in all three Pillow `image.load()` call sites that currently miss it. `quickscale_modules/storage/src/quickscale_modules_storage/helpers.py:289` catches only `(UnidentifiedImageError, OSError)`, `quickscale_modules/blog/src/quickscale_modules_blog/views.py:266` has the same gap in the fallback path when the storage helper is absent, and `quickscale_modules/blog/src/quickscale_modules_blog/models.py:365` catches `(AttributeError, FileNotFoundError, NotImplementedError, OSError, ValueError)` in `Post.generate_thumbnails()` but omits `DecompressionBombError`. Phase 8 adds max-dimension guards at the API boundary; these three sites are reached via admin uploads, direct storage saves, and the thumbnail-generation signal — paths that bypass the API guard. Add `DecompressionBombError` (and `DecompressionBombWarning` where appropriate) to each handler, and add regressions proving that oversized-pixel images raised from stored content are caught cleanly at each site.
- [ ] Restrict CRM REST API endpoints to staff-only access. `quickscale_modules/crm/src/quickscale_modules_crm/views.py:137` uses `permission_classes = [IsAuthenticated]` on `CRMModelViewSet`, which exposes full contact records (names, emails), company data, deal amounts, and pipeline stages to any authenticated user — not just staff. Phase 8 covers the unauthenticated HTML dashboard; this gap is in the REST API layer. Elevate the permission class to `IsAdminUser` or introduce a `IsStaffUser` custom permission, align the `CRM_ENABLE_API` documentation, and add regression coverage for non-staff authenticated rejections across the Tag, Company, Contact, Stage, and Deal viewsets.
- [ ] Replace the two bare `except Exception: pass` blocks in `quickscale_core/src/quickscale_core/settings_manager.py:31` and `:41` with `except Exception as exc: logger.debug(...)`. Both blocks silently discard YAML parse errors when reading `quickscale.yml` and `state.yml`, causing the caller to receive a generic `SettingsError` with no indication of whether the file was unreadable, empty, or contained invalid YAML. The fix is diagnostic-only (keep the fail-through to `SettingsError`), but the logged message must include the parse-error context so operators can distinguish corrupt config from missing config.
- [ ] Add configurable rate-limiting to the blog write API endpoints. `quickscale_modules/blog/src/quickscale_modules_blog/views.py:437` (`upload_media_api`) and `:468` (`publish_post_api`) have no throttle class, unlike the forms module's `FormSubmitThrottle` / `FORMS_RATE_LIMIT` design. A compromised or misconfigured staff credential can drive unbounded upload or publish volume, causing storage exhaustion or database bloat. Add a `BLOG_API_RATE_LIMIT` setting (defaulting to a conservative ceiling), apply a `ScopedRateThrottle` subclass consistent with the forms pattern, and add regression coverage verifying that the throttle fires after the configured number of requests within the window.
- [ ] Surface startup import errors instead of silencing them in `quickscale_cli/src/quickscale_cli/__init__.py:18` and `quickscale_modules/analytics/src/quickscale_modules_analytics/apps.py:26`. Both use bare `except Exception:` to swallow all initialization errors; `__init__.py:18` suppresses version-import failures and `apps.py:26` suppresses `AppConfig.ready()` errors. Replace both with `except Exception as exc: logger.debug(...)` (and re-raise or emit a clear user-facing message where appropriate), so broken installs or missing dependencies surface at startup instead of silently degrading the running process. Add regressions verifying the error path produces a message rather than silent continuation.

**Phase 8b execution handoff plan (2026-05-01)**

Resume this consolidated backlog in the following slices so the next implementation pass can start from preserved planning state without redoing discovery. No Phase 8b implementation has started:

1. **Local Docker / release-closeout prerequisite restore**
   - Install Docker Engine and a Compose-compatible command path (`docker compose` and/or `docker-compose`) on the Ubuntu 24.04 host, then verify `docker --version` and daemon access.
   - Current local blocker: no Docker commands are installed, and unattended package installation from this session is blocked because `sudo -n` fails.
   - Validation: `docker --version`, `docker info`, and one of `docker compose version` or `docker-compose --version` succeed in the active shell.
2. **Playwright + release-grade validation**
   - Install or verify Playwright Chromium prerequisites once Docker is working.
   - Run `make test-e2e`, then `make ci-e2e`, and record whether release-closeout is still blocked or fully green.
   - Validation: `make test-e2e` passes before `make ci-e2e`; use `make version-check` if fresh closeout evidence is required.
3. **Pillow DecompressionBombError gap closure**
   - Add `DecompressionBombError` to the exception tuple in `storage/helpers.py:289`, `blog/views.py:266`, and `blog/models.py:365`.
   - In `helpers.py` and `views.py`, raise `ValueError` (matching existing error propagation) after catching the bomb. In `models.py`, return early (matching the existing swallow-and-return pattern for thumbnail failures).
   - Validation: unit tests for each site using a fabricated oversized-pixel buffer, then `make test` on `quickscale_modules/storage` and `quickscale_modules/blog`.
4. **CRM API staff-only permission**
   - Replace `permission_classes = [IsAuthenticated]` with `permission_classes = [IsAdminUser]` (or a custom `IsStaffUser`) on `CRMModelViewSet`.
   - Update the CRM README and any API contract documentation to reflect the staff-only boundary.
   - Validation: CRM view tests for unauthenticated, non-staff authenticated, and staff authenticated requests across all five viewsets.
5. **settings_manager.py parse-error diagnostics**
   - Replace `except Exception: pass` at lines 31 and 41 with `except Exception as exc: logger.debug("Failed to read %s: %s", config_path/state_path, exc)`.
   - No behavior change — the function still raises `SettingsError` on fallthrough; the improvement is that the log entry names the file and the parse error.
   - Validation: unit tests asserting that a corrupt YAML file logs a debug message before raising `SettingsError`.
6. **Blog API rate-limiting**
   - Add `BLOG_API_RATE_LIMIT` setting (default `"20/hour"`) and a `BlogApiThrottle(ScopedRateThrottle)` class in a new `quickscale_modules/blog/src/quickscale_modules_blog/throttles.py`.
   - Apply the throttle to `upload_media_api` and `publish_post_api`; keep the throttle scope consistent with `BLOG_API_RATE_LIMIT`.
   - Validation: throttle unit tests for allowed, boundary, and over-limit request sequences.
7. **Startup error surfacing**
   - Replace both bare `except Exception:` blocks with `except Exception as exc: logger.debug(...)` and (for `__init__.py`) log at `WARNING` level since CLI startup failures are operator-visible.
   - Confirm the fix does not break the version-fallback path for `__init__.py`.
   - Validation: targeted unit tests for the affected import/startup paths, then `make test`.

**Dependency note**: Slices 1-2 unblock the remaining release-grade validation and can proceed as soon as privileged install access is available. Slice 3 is independent and can land immediately once Phase 8b implementation starts. Slice 4 must land before the v0.83.0 tag because it closes a data-access gap on a shipped REST API. Slices 5-7 are low-risk diagnostic improvements and can proceed in any order after Slice 4. The entire Phase 8b checklist should complete before the v0.83.0 tag/release exists.

---

### v0.84.0: `quickscale_modules.billing` - Billing Module

**Status**: 📋 Planned

**Dependency note**: This milestone starts only after v0.83.0 closes the current hardening work for plan/apply, starter themes, and module contract fidelity.

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

### v0.85.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

**Status**: 📋 Planned

**Dependency note**: This milestone remains the SaaS-parity target after the v0.83.0 hardening release and the v0.84.0 billing milestone.

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

### v0.86.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack. Any blocking HTML contract corrections discovered in v0.83.0 belong to the hardening release; this later milestone is for optional polish after the shipped contract is stable again.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---
