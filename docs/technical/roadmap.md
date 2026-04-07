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
| v0.83.0 | 📋 Planned | Hardening release | Repo-wide contract, explicit-failure, dependency, theme, and test hardening before the next new public module release |
| v0.84.0 | 📋 Planned | Billing module | Stripe integration after v0.83.0 hardening closes the current platform and module contract gaps |
| v0.85.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.86.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the hardening, billing, and teams milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.82.0 is the published release
- **Active next milestone:** v0.83.0 hardening release is the current planning scope
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

**Status**: 📋 Planned

**Goal**: Close the repo-wide audit findings before shipping the next new public module release. This milestone hardens the current plan/apply surface, managed wiring behavior, shipped starter themes, module contract fidelity, metadata parity, and regression coverage so later billing and teams work lands on a stable documented base.

**Implementation Review**: The original checklist covers the right hardening surface, but it mixes platform, generator, module-runtime, metadata, and closeout work into one flat milestone. For handoff, v0.83.0 should run as phased slices grouped by related code so each implementation pass can stay localized, testable, and reviewable.

**Implementation Phases (handoff order)**:

| Phase | Focus | Primary code areas | Depends on |
|---|---|---|---|
| 1 | CLI state and managed wiring failure semantics | `quickscale_cli`, desired/applied state writers, managed wiring helpers, remove/update/push consumers, CLI integration tests | none |
| 2 | Theme contract and shipped starter surface cleanup | starter theme generators, `showcase_react`, `showcase_html`, theme routing/navigation/templates, starter-theme tests, theme SSOT docs | none |
| 3 | Shared dependency and install contract infrastructure | shared module apply/install helpers, manifest contract checks, dependency-sync logic, CI contract checks | none |
| 4 | Content module contract fixes | `quickscale_modules/blog`, `quickscale_modules/listings`, related manifests, runtime settings, module tests | Phase 3 |
| 5 | Auth, forms, and CRM option contract cleanup | `quickscale_modules/auth`, `quickscale_modules/forms`, `quickscale_modules/crm`, public manifest/CLI/docs surface, module tests | Phase 3 |
| 6 | Packaged metadata parity and placeholder leakage cleanup | packaged module metadata, `module.yml`, `pyproject.toml`, exported version metadata, generated starter metadata/app-label/nav surfaces | Phases 2, 4, 5 |
| 7 | Cross-cutting release gates and docs closeout | repo-wide regression suites, generated-project smoke tests, `docs/technical`, package/module READMEs, milestone closeout checks | Phases 1-6 |

**Parallelization note**: Phases 1, 2, and 3 are grouped by different code areas and can be handed off independently. Phase 3 should land before Phases 4 and 5 so module-specific fixes inherit the shared dependency/install contract. Phase 6 should wait for the shipped surface to settle, and Phase 7 is the final release-gate and SSOT reconciliation pass.

#### Phase 1: CLI State and Managed Wiring Failure Semantics

**Primary code grouping**: `quickscale remove`, desired/applied state persistence, managed wiring regeneration, legacy tracking consumers, CLI failure handling, and operator-facing command tests.

**Current status (2026-04-06)**: Audit and handoff-prep notes are complete, but no Phase 1 implementation slice has landed yet and the next handoff is still blocked on the decisions listed below. The completed item below captures the investigation work; the behavior-change and regression items remain open until code and tests merge.

- [x] Audit the current `remove`/`apply`/managed-wiring behavior and capture the blocking handoff scope for the next Phase 1 implementation slice.

- [ ] Update `quickscale remove` to keep legacy module tracking synchronized with desired and applied state, or explicitly retire the legacy tracking file as a source of truth for update, push, and template consumers.
- [ ] Make `quickscale remove` return a non-zero failure and suppress the success banner when `quickscale.yml` writes, state writes, or managed wiring regeneration fail.
- [ ] Reorder removal orchestration or add rollback so destructive filesystem removal does not complete before managed-file updates and state writes are known-good.
- [ ] Make managed wiring fail explicitly when `quickscale.yml` or `.quickscale/state.yml` cannot be parsed instead of silently falling back to empty or default option maps.
- [ ] Review every `regenerate_managed_wiring` call path and ensure malformed config or state errors reach the operator command instead of being downgraded to warnings.
- [ ] Add integration coverage proving remove, update, push, and template-context consumers no longer see a removed module after the command completes.
- [ ] Add regression coverage for malformed desired or applied state so unrelated managed module settings are preserved by aborting the write rather than resetting to defaults.
- [ ] Harden CLI tests so success-path assertions check `exit_code` up front and stop swallowing exceptions or conditionally accepting failure paths.
- [ ] Add command-level regression coverage for remove partial-failure behavior, malformed config/state behavior, and managed wiring abort semantics.

**Blocking items for handoff**

- `quickscale remove` still deletes the embedded module tree before desired state, applied state, legacy tracking, and managed outputs are known-good, so Phase 1 still needs staged writes or rollback across `quickscale.yml`, `.quickscale/state.yml`, `.quickscale/config.yml`, managed outputs, and the module directory.
- Managed wiring still falls back to empty or default option maps on malformed `quickscale.yml` or `.quickscale/state.yml` on some call paths, so strict abort semantics and operator-visible error propagation remain open.
- `apply` still reaches managed wiring through both the final apply-wide regeneration path and the earlier per-module configurator path, so the implementation handoff must cover both paths or explicitly remove one of them.
- The touched CLI suites still contain permissive success/failure assertions, so exit-code-first hardening and explicit failure-path coverage remain part of the open Phase 1 scope rather than follow-up cleanup.

**Decision needed at next handoff**

- Decide whether `apply` should bypass per-module managed-wiring regeneration during embed and rely only on the final authoritative regeneration pass, or whether the `module_config` path stays active and must adopt the same blocking staged and rollback-safe behavior.
- Decide whether a managed-wiring failure after one or more embeds succeed should keep the planned partial-embed contract, or whether Phase 1 should expand to full embed rollback in the same slice.

#### Phase 2: Theme Contract and Shipped Starter Surface Cleanup

**Primary code grouping**: generated theme output, placeholder route/nav/dashboard surface, React Router dependency alignment, HTML social route ownership, starter-theme tests, and theme-related SSOT updates.

- [x] Remove billing and teams placeholder routes, flags, dashboard cards, and navigation from generated starter output until those modules actually ship as valid public plan/apply selections.
- [x] Remove the matching placeholder expectations from starter-theme tests so the test suite enforces the shipped module surface rather than preserving dead placeholder output.
- [x] Confirm that `showcase_html` public `/social` and `/social/embeds` routes were residual placeholder output rather than part of the shipped contract.
- [x] Keep the supported public-page contract on fresh `showcase_react` generations, where Django-owned `/social` and `/social/embeds` pages are auto-generated while the backend-managed social transport remains theme-agnostic.
- [x] Remove the static placeholder templates and route wiring from shipped `showcase_html` output and align the SSOT/docs accordingly.
- [x] Record that existing projects and non-React themes must manually adopt any equivalent public social pages instead of receiving automatic route/template rewrites.
- [x] Approve the React Router v7 line as the `showcase_react` routing baseline and keep the SSOT aligned with the generated dependency surface.
- [x] Add regression coverage that asserts billing and teams do not appear in generated starter output until those modules ship.
- [x] Add regression coverage that asserts only fresh `showcase_react` auto-generates public social pages while `showcase_html` and other non-React themes rely on manual adoption.

#### Phase 3: Shared Dependency and Install Contract Infrastructure

**Primary code grouping**: shared module dependency-sync logic, install/apply contract helpers, manifest/package dependency policy, storage dependency exceptions, and CI contract enforcement.

**Current status (2026-04-07)**: Phase 3 is implemented. Shared dependency sync now runs through one CLI-owned path with lock-refresh and fail-fast install semantics, ready shipped modules enforce manifest/package/version parity in tests and CI, storage keeps cloud packages optional behind an explicit cloud extra, and maintainer-side generated-project smoke coverage now verifies the required dependency surface across the ready shipped module set.

- [x] Create one shared dependency-sync path for module apply/install so per-module appliers do not drift from package or manifest requirements.
- [x] Audit all shipped modules for dependency parity across `module.yml`, package metadata, and the actual apply/install path instead of fixing blog and listings only.
- [x] Decide whether `module.yml` dependency declarations are meant to be authoritative runtime requirements or a narrower compatibility surface, then codify that rule in tests.
- [x] Fix the storage metadata drift by either declaring Pillow in `module.yml` or documenting and enforcing a deliberate exception policy.
- [x] Extend manifest contract checks so dependency parity regressions fail in CI rather than surfacing during later module releases.
- [x] Add generated-project smoke coverage that syncs and installs the ready shipped module set through the shared dependency path and verifies the required third-party distributions are present.

#### Phase 4: Content Module Contract Fixes

**Primary code grouping**: blog and listings runtime behavior, their apply/install paths, pagination/feed settings, related manifests, and targeted module regressions.

**Current status (2026-04-07)**: The shipped dependency/install contract for blog and listings now runs through the shared Phase 3 manifest-driven sync path rather than through module-specific dependency mutation, and the remaining content-module runtime and cleanup work in this slice has landed in the current worktree. Blog pagination now reads `BLOG_POSTS_PER_PAGE`, the blog feed route is gated by runtime `BLOG_ENABLE_RSS`, listings pagination now reads `LISTINGS_PER_PAGE`, targeted module plus CLI regression coverage exists for the changed behavior, and the stale pre-Phase-3 listings direct-dependency helper path is removed. No further unimplemented blog/listings contract gap was verified in this pass, so Phase 4 is closed.

- [x] Confirm that the blog module now inherits runtime dependency installation from the shared Phase 3 manifest-driven apply/install sync, including its current markdown and image-related dependencies where they remain part of the shipped contract.
- [x] Confirm that the listings module now inherits runtime dependency installation from the shared Phase 3 manifest-driven apply/install sync, including its current image-support dependencies where they remain part of the shipped contract.
- [x] Make blog pagination read `BLOG_POSTS_PER_PAGE` from settings instead of using hardcoded page sizes in runtime views.
- [x] Make the blog RSS toggle control the feed route itself instead of indirectly toggling unrelated markdown URL wiring.
- [x] Make listings pagination read `LISTINGS_PER_PAGE` from settings instead of using a hardcoded runtime page size.
- [x] Add module-level regression coverage for blog pagination, blog RSS toggling, and listings pagination.
- [x] Record that `blog.enable_rss` is now a mutable runtime option backed by `BLOG_ENABLE_RSS`, so re-apply updates the managed setting and feed-route behavior without forcing a re-embed.
- [x] Remove the stale listings direct-dependency helper path now that the shared Phase 3 manifest-driven sync owns dependency installation.

**Phase 4 closeout notes**

- Dependency installation ownership for blog and listings now lives in the shared Phase 3 manifest-driven sync path rather than in blog/listings-specific appliers.
- `blog.enable_rss` is now a mutable runtime contract option. The feed route is gated at runtime, while `markdownx` URL wiring remains part of the base blog wiring regardless of RSS state.

#### Phase 5: Auth, Forms, and CRM Option Contract Cleanup

**Primary code grouping**: auth public option surface, forms runtime/schema behavior, CRM pipeline seeding behavior, related manifests/docs, and targeted module regressions.

- [ ] Confirm and document whether auth `social_providers` remains future-facing in v0.83.0 or graduates to a shipped public contract.
- [ ] If auth `social_providers` remains future-facing, remove it from the public manifest/CLI/docs surface until provider apps, dependencies, and settings are actually wired.
- [ ] If auth `social_providers` ships in v0.83.0, implement provider app installation, dependency sync, and settings wiring end to end and add direct regression coverage.
- [ ] Make forms spam protection use one shared predicate between schema generation and submission handling.
- [ ] Make `FORMS_DATA_RETENTION_DAYS` either drive the actual default retention behavior or remove it from the shipped mutable option surface.
- [ ] Make CRM `default_pipeline_stages` either drive initial stage creation and stage lookup behavior or remove it from the shipped immutable contract until it is real.
- [ ] Audit the remaining shipped mutable and immutable module options for other advertised-but-unused behavior beyond the audited auth, blog, crm, forms, and listings cases.
- [ ] Confirm whether any other shipped modules have CLI-written settings that are ignored by runtime code, and add the results of that verification to this milestone before closeout.
- [ ] Add module-level regression coverage for forms retention defaults, forms spam-protection behavior, auth social-provider wiring, and CRM stage seeding behavior.

#### Phase 6: Packaged Metadata Parity and Placeholder Leakage Cleanup

**Primary code grouping**: packaged module metadata, manifest/version export alignment, generated starter metadata/app-label/nav leakage, and public release-surface gates.

- [ ] Align auth package metadata with the canonical manifest version and any exported version metadata.
- [ ] Audit every packaged module for `module.yml`, `pyproject.toml`, and exported version parity and fix any drift found during the pass.
- [ ] Confirm that placeholder-only modules do not leak into generated starter metadata, app-label flags, or user-facing navigation before billing and teams actually ship.
- [ ] Add a release gate proving billing and teams stay rejected by `quickscale plan`, `quickscale.yml` validation, `quickscale apply`, and starter-theme output until their own release milestones ship.

#### Phase 7: Cross-Cutting Release Gates and Docs Closeout

**Primary code grouping**: repo-wide validation, SSOT reconciliation, package/module documentation alignment, and milestone closeout tracking.

- [ ] Run and record the final repo-wide regression pass for the hardening milestone, including the generated-project smoke suite and any release gates added in earlier phases.
- [ ] Update `decisions.md`, `scaffolding.md`, `user_manual.md`, package/module READMEs, and related release notes as fixes land so shipped behavior and public documentation match again.
- [ ] Close the milestone only after the blocking audit items are fixed or explicitly removed from the shipped contract and the remaining advisory drifts are either resolved or documented with owner-approved follow-up.

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
