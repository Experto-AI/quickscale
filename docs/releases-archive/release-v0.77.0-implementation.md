# Release v0.77.0: Backups Module - ✅ Archived Retrospective Implementation Record

**Release Baseline**: Internal main-branch baseline before the published v0.78.0 release line

**Archive Date**: 2026-03-31

**Archive Update**: 2026-04-02 roadmap detail for the 2026-04-01 hardening continuation moved here from `roadmap.md`

## Overview

This retrospective archive captures the implemented v0.77.0 backups scope that previously lived only in the roadmap. It also preserves the 2026-04-01 hardening continuation that finalized the PostgreSQL 18 restore contract and moved the remaining v0.77.0 follow-up detail out of `roadmap.md`. The release closed out QuickScale's MVP line with a first-party operational safety module centered on private database backups, optional private remote offload, planner/apply integration, operator-facing Django admin workflows, and guarded restore execution.

The implementation deliberately kept backup artifacts outside public media delivery. Backups use private local storage by default, can optionally offload to private S3-compatible storage, and avoid any dependency on `public_base_url` or public CDN URLs. Scheduler orchestration remained command-driven so the release could ship the operational core without prematurely introducing a shared background-job framework. The hardening continuation stayed attached to v0.77.0 rather than being re-scoped into a later numbered release.

## Verifiable Improvements Achieved

- ✅ Added `quickscale_modules.backups` as a first-party operational safety module for generated projects.
- ✅ Shipped private local backups by default with optional private remote offload for S3-compatible targets.
- ✅ Delivered admin workflows for create, validate, download, prune, and delete operations.
- ✅ Delivered guarded restore execution, with unchanged CLI restore entrypoints and a guarded BackupPolicy-admin local-only restore surface added in the hardening continuation.
- ✅ Wired the module through QuickScale's planner/apply flow, generated settings, and operator next-step guidance.
- ✅ Added retention, checksum, metadata, and concurrency guardrails without exposing backup artifacts through media routes.
- ✅ Hardened generated PostgreSQL projects around PostgreSQL 18 custom dumps as the real disaster-recovery path while keeping JSON export artifacts limited to non-PostgreSQL dev/test fixture workflows.

## Implemented Scope

### Backup and restore capabilities

- Database-focused backup creation with PostgreSQL custom/compressed dump support as the real recovery path for generated PostgreSQL projects, with JSON export retained only for CI-safe local or non-PostgreSQL dev/test workflows
- Deterministic artifact naming using project, environment, and timestamp information
- Backup metadata manifest carrying engine details, best-effort version information, checksums, size, creation time, and storage target
- Pre-restore validation covering checksum, format and engine compatibility, JSON payload validation for JSON exports, and explicit destructive-action confirmation
- Optional dry-run validation path before restore execution

### Private storage and operator access

- Local private backup directory kept separate from public media paths
- Optional private remote target using storage-compatible settings for S3-compatible providers
- Dedicated private backup prefix and bucket semantics, never public media URL helpers
- Staff-only download flow through admin stream or local-path retrieval
- Retention pruning and delete synchronization across local metadata and private remote objects

### Django admin and command surfaces

- Read-only `BackupPolicy` applied snapshot for retention, naming, target mode, and schedule metadata sourced from generated settings
- `BackupArtifact` history with checksum, size, validation state, operator attribution, and restore markers
- Admin actions for create, validate, download, prune, and delete
- No standalone admin upload/offload action; private remote offload only happens during backup creation when configured
- Guarded restore uses a BackupPolicy-admin local-only surface for row-backed artifacts already present on disk, while CLI restore keeps the positional `artifact_id` and additive `--file PATH` entrypoints under the same confirmation and environment guards
- Admin download and validate remain local-file-only in v1, and admin restore never materializes remote-only artifacts

### Planner and apply integration

- Manifest-backed configuration for retention, naming prefix, local vs private-remote target selection, and optional schedule metadata
- Apply-time wiring for settings, admin registration, management-command guidance, and private-remote prerequisite checks
- Next-step output describing environment-variable configuration and restore safety expectations

### Security and operational guardrails

- Privileged-access-only backup surfaces for staff or superusers
- Secret-safe logging and no backup exposure through public template context or media URLs
- Private-remote credentials stored only as environment-variable references
- Concurrency protection to prevent overlapping manual and scheduled runs
- Additional at-rest encryption explicitly deferred beyond v0.77.0 because it would expand key-management and restore-UX scope

## 2026-04-01 Hardening Continuation

This archived continuation completed the post-release backups hardening work that previously remained detailed in `roadmap.md`. It moved backups from same-instance operational artifacts toward PostgreSQL 18 disaster-recovery/shareable dumps that can be restored into local Docker-style and Railway deployments, while preserving the work as a v0.77.0 continuation rather than turning it into a later numbered release.

**Out of scope for this continuation**:
- provider snapshots
- rowless remote-key restore
- broader admin restore expansion beyond the guarded local-only BackupPolicy surface
- import/register workflows
- scheduler extraction
- broad project-snapshot bundles

### Completed continuation phases

- **Phase 1 - contract and docs first**:
  - [x] Update the backups contract in `decisions.md` first, then align `README.md`, `user_manual.md`, the module README, and Railway deployment docs.
  - [x] Make the user-facing contract explicit: generated QuickScale PostgreSQL local/Railway flows target PostgreSQL 18, native PostgreSQL custom dumps are the real backup path, JSON artifacts are export-only rather than disaster-recovery backups, and BackupPolicy-admin restore is guarded local-only while CLI restore syntax stays unchanged.
- **Phase 2 - additive schema and admin classification**:
  - [x] Add `restore_scope`, `database_server_major`, and `dump_client_major` to `BackupArtifact`.
  - [x] Backfill legacy JSON artifacts to `export_only`.
  - [x] Backfill legacy `pg_dump_custom` artifacts conservatively to `local_only`.
  - [x] Update admin messaging so `export_only`, `local_only`, and portable artifacts are visibly distinct.
- **Phase 3 - create/restore hardening**:
  - [x] Remove automatic PostgreSQL JSON fallback from the real backup path.
  - [x] Require PostgreSQL 18 tooling and a PostgreSQL 18 server for PostgreSQL create/restore flows.
  - [x] Keep JSON only for non-PostgreSQL dev/test fixture export paths.
- **Phase 4 - smallest safe portable restore contract**:
  - [x] Keep the current positional `artifact_id` restore entrypoint and add additive `--file PATH` support for the CLI surface.
  - [x] Keep exact filename confirmation mandatory for both CLI restore modes and for the guarded BackupPolicy-admin restore flow.
  - [x] Keep BackupPolicy-admin restore limited to row-backed local artifacts already present on disk; do not materialize remote artifacts through the admin surface.
  - [x] Keep admin download/validate local-file-only in v1.
  - [x] Treat file-mode CLI restore as an operator escape hatch for PostgreSQL custom dumps that pass the PG18 preflight; do not claim QuickScale-only provenance in v1.
- **Phase 5 - validation and workflow alignment**:
  - [x] Add service, admin, model, migration, and management-command coverage for the new contract.
  - [x] Add non-debug Railway-mode regressions for hard-fail PostgreSQL create and row-backed remote restore after local-file loss.
  - [x] Pin the active local E2E harness and GitHub E2E workflow to the PostgreSQL 18 contract and current `plan`/`apply` flow.
  - [x] Update generated apply output so restore guidance matches the final artifact-id plus file-mode contract.

### Resolved contract checkpoints

- [x] Confirm this follow-up stays attached to the archived v0.77.0 scope as a hardening continuation, rather than being re-scoped into a later numbered release.
- [x] Confirm the generated-project contract is intentionally PostgreSQL-18-only for both local Docker and Railway, and document the manual adoption path for already-generated projects.
- [x] Confirm `artifact_id` stays the positional restore operand and `--file PATH` remains additive rather than replacing the current CLI shape.
- [x] Confirm file-mode restore must stay behind the same destructive execution guards as artifact-id restore: same dry-run behavior, same environment gate, and same `--allow-production` semantics.
- [x] Confirm BackupPolicy-admin restore only operates on row-backed local artifacts already present on disk and never materializes remote-only artifacts.
- [x] Confirm `local_only` is only a conservative legacy row classification and must not be read as a portability claim for raw file restores.
- [x] Confirm admin download/validate remain local-file-only in v1, and BackupPolicy-admin restore follows the same local-only rule.
- [x] Confirm the explicit PostgreSQL 18 client-packaging route for generated Docker images and repo-owned CI/E2E runners before code work starts, and bind the related assertions to that exact package choice.
- [x] Confirm the GitHub E2E workflow keeps a generated-project validation job on the current `plan`/`apply` flow instead of silently dropping that gate.
- [x] Confirm implementation resumed only after the contract above was reviewed and accepted, because the remaining risk was in restore semantics and validation scope rather than missing code search.

## Historical Validation Surfaces

The release was shipped before QuickScale adopted a dedicated v0.77.0 archive artifact, so this document summarizes the delivered scope and validation surfaces rather than reconstructing original command output.

### Repository quality gate

```bash
make check
```

### Generated-project operational verification

```bash
python manage.py backups_create
python manage.py backups_create --scheduled
python manage.py backups_validate <artifact_id>
python manage.py backups_prune
python manage.py backups_restore <artifact_id> --confirm <artifact_name> --dry-run
python manage.py backups_restore --file /path/to/backup.dump --confirm backup.dump --dry-run
```

For the archived hardening continuation, generated-project verification also included the guarded BackupPolicy admin restore surface for row-backed local artifacts already present on disk.

### Planner and apply verification

```bash
quickscale plan myapp --configure-modules
quickscale apply
```

## Deferred Follow-up

- Comprehensive/provider-level project snapshots (database + media + environment bundle, provider snapshots, rowless remote-key restore, and broad project-snapshot bundles) only if a real operational use case justifies the added scope
- Import/register workflows and broader admin restore expansion beyond the guarded local-only BackupPolicy surface only if later product scope justifies them
- Cross-module scheduler extraction only when more than one QuickScale feature needs shared recurring job infrastructure
- Managed backup dashboards outside Django admin only if operators need richer day-to-day UI than the MVP admin surface

## Notes

- No separate reader-facing v0.77.0 release summary was published before v0.78.0.
- This archive exists so the roadmap can remain focused on active and upcoming releases while preserving the implemented backups scope in a stable location.
- The 2026-04-01 hardening continuation was moved here from `roadmap.md` on 2026-04-02 so the roadmap could return to a concise archived-release pointer.
