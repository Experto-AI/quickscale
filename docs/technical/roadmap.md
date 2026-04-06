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

**CLI State, Remove Flow, and Managed Wiring**:
- [ ] Update `quickscale remove` to keep legacy module tracking synchronized with desired and applied state, or explicitly retire the legacy tracking file as a source of truth for update, push, and template consumers.
- [ ] Make `quickscale remove` return a non-zero failure and suppress the success banner when `quickscale.yml` writes, state writes, or managed wiring regeneration fail.
- [ ] Reorder removal orchestration or add rollback so destructive filesystem removal does not complete before managed-file updates and state writes are known-good.
- [ ] Make managed wiring fail explicitly when `quickscale.yml` or `.quickscale/state.yml` cannot be parsed instead of silently falling back to empty or default option maps.
- [ ] Review every `regenerate_managed_wiring` call path and ensure malformed config or state errors reach the operator command instead of being downgraded to warnings.
- [ ] Add integration coverage proving remove, update, push, and template-context consumers no longer see a removed module after the command completes.
- [ ] Add regression coverage for malformed desired or applied state so unrelated managed module settings are preserved by aborting the write rather than resetting to defaults.

**Theme Contract Hardening**:
- [ ] Remove billing and teams placeholder routes, flags, dashboard cards, and navigation from generated starter output until those modules actually ship as valid public plan/apply selections.
- [ ] Remove the matching placeholder expectations from starter-theme tests so the test suite enforces the shipped module surface rather than preserving dead placeholder output.
- [ ] Decide whether `showcase_html` public `/social` and `/social/embeds` routes are part of the supported shipped contract or residual placeholder output.
- [ ] If `showcase_html` public social routes are supported, wire them end-to-end to the managed social surface and cover enabled, empty, disabled, error, and published-record behavior.
- [ ] If `showcase_html` public social routes are not supported, remove the static placeholder templates and route wiring from shipped HTML output and align the SSOT/docs accordingly.
- [ ] Align the documented React Router major version with the generated React theme dependency surface by either approving the current v7 pin in SSOT docs or pinning the theme back to the documented line.
- [ ] Add regression coverage that asserts billing and teams do not appear in generated starter output until those modules ship.
- [ ] Add generated-theme regression coverage for HTML social route behavior once the supported contract is confirmed.

**Module Dependency and Install Contract Parity**:
- [ ] Create one shared dependency-sync path for module apply/install so per-module appliers do not drift from package or manifest requirements.
- [ ] Make the blog module apply path install every runtime dependency the shipped module requires, including the current markdown and image-related dependencies if they remain part of the module contract.
- [ ] Make the listings module apply path install every runtime dependency the shipped module requires, including current image support dependencies.
- [ ] Audit all shipped modules for dependency parity across `module.yml`, package metadata, and the actual apply/install path instead of fixing blog and listings only.
- [ ] Decide whether `module.yml` dependency declarations are meant to be authoritative runtime requirements or a narrower compatibility surface, then codify that rule in tests.
- [ ] Fix the storage metadata drift by either declaring Pillow in `module.yml` or documenting and enforcing a deliberate exception policy.
- [ ] Extend manifest contract checks so dependency parity regressions fail in CI rather than surfacing during later module releases.

**Module Option Contract Alignment**:
- [ ] Confirm and document whether auth `social_providers` remains future-facing in v0.83.0 or graduates to a shipped public contract.
- [ ] If auth `social_providers` remains future-facing, remove it from the public manifest/CLI/docs surface until provider apps, dependencies, and settings are actually wired.
- [ ] If auth `social_providers` ships in v0.83.0, implement provider app installation, dependency sync, and settings wiring end to end and add direct regression coverage.
- [ ] Make blog pagination read `BLOG_POSTS_PER_PAGE` from settings instead of using hardcoded page sizes in runtime views.
- [ ] Make the blog RSS toggle control the feed route itself instead of indirectly toggling unrelated markdown URL wiring.
- [ ] Make forms spam protection use one shared predicate between schema generation and submission handling.
- [ ] Make `FORMS_DATA_RETENTION_DAYS` either drive the actual default retention behavior or remove it from the shipped mutable option surface.
- [ ] Make CRM `default_pipeline_stages` either drive initial stage creation and stage lookup behavior or remove it from the shipped immutable contract until it is real.
- [ ] Make listings pagination read `LISTINGS_PER_PAGE` from settings instead of using a hardcoded runtime page size.
- [ ] Audit the remaining shipped mutable and immutable module options for other advertised-but-unused behavior beyond the audited auth, blog, crm, forms, and listings cases.

**Metadata and Version Parity**:
- [ ] Align auth package metadata with the canonical manifest version and any exported version metadata.
- [ ] Audit every packaged module for `module.yml`, `pyproject.toml`, and exported version parity and fix any drift found during the pass.
- [ ] Confirm that placeholder-only modules do not leak into generated starter metadata, app-label flags, or user-facing navigation before billing and teams actually ship.

**Tests and Quality Gates**:
- [ ] Harden CLI tests so success-path assertions check `exit_code` up front and stop swallowing exceptions or conditionally accepting failure paths.
- [ ] Add command-level regression coverage for remove partial-failure behavior, malformed config/state behavior, and managed wiring abort semantics.
- [ ] Add generated-project smoke coverage that embeds each shipped module and verifies required third-party dependencies are present after apply.
- [ ] Add module-level regression coverage for blog pagination, blog RSS toggling, listings pagination, forms retention defaults, forms spam-protection behavior, auth social-provider wiring, and CRM stage seeding behavior.
- [ ] Add a release gate proving billing and teams stay rejected by `quickscale plan`, `quickscale.yml` validation, `quickscale apply`, and starter-theme output until their own release milestones ship.

**Docs, SSOT, and Comprobation**:
- [ ] Update `decisions.md`, `scaffolding.md`, `user_manual.md`, package/module READMEs, and related release notes as fixes land so shipped behavior and public documentation match again.
- [ ] Confirm whether `showcase_html` public social pages were intentionally shipped or accidentally preserved from partial theme work, and record the decision in SSOT docs.
- [ ] Confirm whether React Router v7 is the approved architecture line for `showcase_react` and update the SSOT or generated dependency surface accordingly.
- [ ] Confirm whether any other shipped modules have CLI-written settings that are ignored by runtime code, and add the results of that verification to this milestone before closeout.
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
