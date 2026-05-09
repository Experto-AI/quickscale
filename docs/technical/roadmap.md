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
| v0.83.0 | ✅ Released | Hardening release | Repo-wide hardening release published; archived in the release note and changelog |
| v0.84.0 | 📋 Planned | Backups hardening release | Admin backup artifact download, full backup completeness, uploaded backup restore, and latest-stable runtime and toolchain refresh across modules |
| v0.85.0 | 📋 Planned | Billing module | Stripe integration after v0.84.0 backups hardening closes the remaining backup lifecycle gaps |
| v0.86.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.87.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the hardening, billing, and teams milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo but not yet tagged/released
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.83.0 is the published release
- **Current in-repo milestone:** v0.83.0 hardening is published and archived; active forward roadmap work now begins at v0.84.0 backups hardening
- **Next planned milestone:** v0.84.0 backups hardening release
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
- **Release Documentation Policy**: [Release Summary Template](./release_summary_template.md) for the single public release-note workflow

## ROADMAP
List of upcoming releases with detailed implementation tasks:

---

After release closeout, keep only a concise pointer in the roadmap. Put canonical history in [CHANGELOG.md](../../CHANGELOG.md), and for published releases add `docs/releases/release-vX.XX.X.md` as the single official release note linked from the GitHub tag and release PR. Keep unreleased closeout status in the roadmap until that release note exists.

---

### v0.83.0: Hardening Release

**Status**: ✅ Released
**Release date**: 2026-05-03

v0.83.0 closed the pre-billing hardening track across plan/apply validation, shipped starter and runtime contract fidelity, privileged operator surfaces, export and upload safety guards, and release-closeout validation.

**Canonical history**

- See [CHANGELOG.md](../../CHANGELOG.md) for the version index entry.
- See [Release v0.83.0](../releases/release-v0.83.0.md) for the single public release note linked from the GitHub tag and release PR.
- Publication validation completed through `make version-check`, `make lint`, `make typecheck`, `make test`, `make test-e2e`, and `make ci-e2e`.
- v0.84.0 backups hardening is now the next planned milestone.

---

### v0.84.0: Backups Hardening Release

**Status**: 📋 Planned

**Dependency note**: This milestone starts after v0.83.0 and closes the remaining backup lifecycle gaps before billing work begins.

**Admin backup artifact access**:
- [ ] Add a reliable download flow for backup artifacts listed in `http://localhost:8000/admin/quickscale_modules_backups/backupartifact/`
- [ ] Ensure the admin surface exposes the generated backup file directly without maintainer-only shell access
- [ ] Verify the download path preserves the expected backup filename, content type, and storage-backed access rules
- [ ] Expose artifact provenance fields in the admin changelist: checksum (SHA256), restore_scope, storage location, validated_at, size — so operators can assess artifact health without CLI access
- [ ] Add an admin action to trigger on-demand backup creation from the `BackupArtifact` changelist, so non-CLI operators can initiate captures from the web UI (not just download existing ones)
- [ ] Add an admin action to run artifact integrity validation (checksum re-verification) directly from the changelist

**Full backup completeness**:
- [ ] Ensure generated backups contain both database structure and all records instead of structure-only or records-only snapshots
- [ ] Define and validate the exact backup contract for schema, relational data, and required app-owned backup metadata
- [ ] Add verification coverage that proves a generated backup is restorable as a full application snapshot

**Restore from uploaded backup**:
- [ ] Add an upload-driven restore workflow so a previously downloaded backup can be restored back into the environment
- [ ] Validate uploaded backup files before restore and fail safely on incomplete or incompatible archives; validate format, checksum, and archive integrity before any destructive step begins
- [ ] Add a pre-flight compatibility check that surfaces database engine and major-version mismatches between the backup's recorded metadata and the current live database, and surfaces these as blocking warnings before restore executes
- [ ] Ensure restore execution covers both schema and data recovery for a complete environment rebuild

**Runtime and tooling refresh**:

Target versions (latest with LTS or long-term support coverage where applicable; latest stable otherwise):

**Language runtimes and package managers**

| Tool | Target | Rationale |
|------|--------|-----------|
| Python | **3.13** | Latest active-bugfix release (EOL Oct 2029). Python 3.12 entered security-only maintenance Oct 2025. Update Docker images and `requires-python` constraint from `>=3.12,<3.14` to `>=3.13,<3.15`. Note: repo CI already runs 3.14 — generated project templates are the ones that need the bump from 3.12 → 3.13. |
| Django | **6.0.x** (latest patch) | Project is already on the 6.0 line. Django 5.2 is the latest LTS (EOL Apr 2028); Django 6.2 is the next LTS target (Apr 2027). Staying on 6.0 is an intentional non-LTS interim choice — do not downgrade to 5.2. |
| Poetry | **2.4.0** | Latest stable (May 2026). Update the pinned version in `Dockerfile.j2`. |
| Node.js | **24** (LTS) | Already on Active LTS (EOL Apr 2028). Node 26 does not enter LTS until Oct 2026 — do not upgrade yet. |
| pnpm | **11.x** (latest stable) | Major release Apr 2026; requires Node ≥ 22. Update `packageManager` field in `package.json.j2` and the pinned version in `ci.yml.j2`. |
| React | **19.x** (latest stable) | No LTS scheme; track latest stable patch. |
| TypeScript | **6.x** (latest stable) | Major release Mar 2026. Audit `tsconfig` for breaking changes after bumping. |
| Vite | **8.x** (latest stable) | Major release Mar 2026 (Rolldown-based bundler). Breaking changes expected — validate build output after bump. |
| Vitest | **4.x** (latest stable) | Track latest stable minor within the 4.x series. |
| PostgreSQL | **18** | Already on latest major (EOL Nov 2030). No change. |

**Docker base images**

| Image | Target | Files | Notes |
|-------|--------|-------|-------|
| `python:3.12-slim-bookworm` | `python:3.13-slim-bookworm` | `Dockerfile.j2` (builder stage and runtime stage) | Both stages must be bumped together; also update the `site-packages` copy path from `python3.12` → `python3.13`. |
| `node:24-slim` | `node:24-slim` | `docker-compose.yml.j2`, `Dockerfile.j2` | Already on Active LTS — no change. |
| `postgres:18-alpine` | `postgres:18-alpine` | `docker-compose.yml.j2`, `e2e.yml` | Already current — no change. |
| `postgres:17-alpine` | `postgres:18-alpine` | `quickscale_core/tests/docker-compose.test.yml` | **Bug: inconsistent with the rest of the repo.** Must be aligned to 18. |

**CI/CD infrastructure (GitHub Actions)**

| Action | Current | Target | Files |
|--------|---------|--------|-------|
| `actions/checkout` | `@v6` | `@v6` | No change. |
| `actions/setup-python` | `@v6` | `@v6` | No change. |
| `actions/cache` | `@v5` | `@v5` | No change. |
| `actions/upload-artifact` | `@v7` | `@v7` | No change. |
| `actions/download-artifact` | `@v8` | `@v8` | No change. |
| `snok/install-poetry` | `@v1` | `@v1` | No change. |
| `pnpm/action-setup` | `@v5` | `@v5` | No change (`ci.yml.j2`). |
| `codecov/codecov-action` | `@v4` | **`@v5`** | `ci.yml`, `e2e.yml` — minor version bump. |
| `softprops/action-gh-release` | `@v2` | **`@v3`** | `publish.yml` — v3 runs on Node 24. |
| `pypa/gh-action-pypi-publish` | `@release/v1` | `@release/v1` | No change. |

**Structural tooling**

| Tool | Current | Target | Files | Notes |
|------|---------|--------|-------|-------|
| `pre-commit-hooks` | `v4.5.0` | **`v6.0.0`** | `.pre-commit-config.yaml.j2` | Generated app template hook is stale. |
| `ruff-pre-commit` | `v0.6.0` | **`v0.15.12`** | `.pre-commit-config.yaml.j2` | Must match the `ruff` version pinned in dev dependencies. |
| `docker compose` | `docker-compose` (v1, apt package) | **`docker compose`** (v2 plugin) | `e2e.yml` | `docker-compose` v1 is deprecated and removed from Ubuntu 24.04 runners. Replace `apt-get install docker-compose` + `docker-compose config` calls with the v2 plugin syntax (`docker compose config`). The compose file format is fully backward-compatible. |

All libraries that depend on these runtimes or toolchains must be updated to versions compatible with the targets above. A partially upgraded stack (e.g. a module pinning an older Django patch, or a frontend package incompatible with TypeScript 6) is not acceptable — the refresh must be coherent repo-wide.

- [ ] Update Python Docker base images from `python:3.12-slim-bookworm` → `python:3.13-slim-bookworm` in `Dockerfile.j2`; update `site-packages` copy path from `python3.12` → `python3.13`
- [ ] Update `postgres:17-alpine` → `postgres:18-alpine` in `quickscale_core/tests/docker-compose.test.yml`
- [ ] Update `codecov/codecov-action` from `@v4` → `@v5` in `ci.yml` and `e2e.yml`
- [ ] Update `softprops/action-gh-release` from `@v2` → `@v3` in `publish.yml`
- [ ] Replace deprecated `docker-compose` (v1) with `docker compose` (v2 plugin) in `e2e.yml`
- [ ] Update `pre-commit-hooks` from `v4.5.0` → `v6.0.0` and `ruff-pre-commit` from `v0.6.0` → `v0.15.12` in `.pre-commit-config.yaml.j2`
- [ ] Update Python runtime to 3.13 in generated project templates: `requires-python` in `pyproject.toml.j2`, CI matrix in `ci.yml.j2`, mypy `python_version`, ruff `target-version`
- [ ] Update Django to the latest 6.0.x patch across all module `pyproject.toml` files and the generated app template
- [ ] Update Poetry to 2.4.0 in `Dockerfile.j2` and any other pinned references
- [ ] Update pnpm to latest 11.x in `package.json.j2` (`packageManager` field) and `ci.yml.j2` (pinned version step)
- [ ] Update React, TypeScript, Vite, Vitest, and all frontend devDependencies in `package.json.j2` to compatible latest-stable versions
- [ ] Update all Python library dependencies (django-storages, boto3, gunicorn, whitenoise, psycopg2-binary, Jinja2, pyyaml, anymail, etc.) to the latest versions compatible with Django 6.0.x and Python 3.13
- [ ] Update all frontend libraries (Radix UI, TanStack Query, react-router-dom, lucide-react, motion, zod, zustand, etc.) to versions compatible with React 19 and TypeScript 6
- [ ] Validate with `make lint`, `make typecheck`, `make test`, `make test-e2e`, and a full frontend `pnpm build` + `pnpm type-check` after all bumps are applied

**Testing**:
- [ ] Unit tests for backup artifact download permissions, storage access, and backup composition
- [ ] Integration tests covering backup generation, download, upload, and restore as one round-trip workflow
- [ ] Admin-path or end-to-end validation proving a generated backup can be downloaded and restored successfully

---

### v0.85.0: `quickscale_modules.billing` - Billing Module

**Status**: 📋 Planned

**Dependency note**: This milestone starts only after v0.84.0 closes the backup hardening work for admin download, full backup completeness, upload-driven restore, and the repo-wide stable runtime/tooling refresh.

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

**Dependency note**: This milestone remains the SaaS-parity target after the v0.84.0 backups hardening release and the v0.85.0 billing milestone.

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

### v0.87.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack. Any blocking HTML contract corrections discovered in v0.83.0 belong to the hardening release; this later milestone is for optional polish after the shipped contract is stable again.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---
