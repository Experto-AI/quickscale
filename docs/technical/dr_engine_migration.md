# DR Engine Migration Guide (F5 / M10)

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **DR Engine Migration**
> **Related docs**: [Decisions § DR Engine Boundary Contract](decisions.md#disaster-recovery-engine-boundary-contract-f5--m10) | [Roadmap](roadmap.md) | [CHANGELOG](../../CHANGELOG.md)

## Purpose

This document describes the migration path for existing generated projects that adopt the split DR engine architecture (Finding 5 / Milestone 10). The DR engine has been extracted from the embeddable `backups` module into centrally owned code in `quickscale_core.dr_engine`, with the hidden management-command + environment-variable protocol replaced by an explicit typed adapter.

The change is primarily **maintainer-internal** — the `quickscale dr` CLI surface is unchanged, and the module code can be updated via `quickscale update`. However, the `backups` module now imports from `quickscale-core` at runtime. The `quickscale apply` command syncs the `quickscale-core` dependency entry from the embedded module manifest into the generated project's root `pyproject.toml`. Standalone projects may still need to replace or satisfy that synced entry with a resolvable source for their layout before `poetry install` succeeds. See the migration path below for the available options.

## What Changed

### Phase F5.2a — Snapshot and Archive Primitives (Extraction)

Django-free snapshot/archive primitives were extracted from `quickscale_modules_backups.services` into `quickscale_core.dr_engine.primitives`:

- Backup error classes (`BackupError`, `BackupConfigurationError`)
- Archive constants (PostgreSQL major version, sidecar filename conventions)
- Database engine helpers and pg_dump/pg_restore command builders
- Version extraction helpers for PostgreSQL client tooling
- Snapshot structure helpers (ID minting, path construction, JSON writing)
- Archive integrity helpers (SHA-256 computation)

The `backups` module imports these extracted items from `quickscale_core.dr_engine.primitives` with backward-compatible re-exports — no import changes were needed in the existing module code.

### Phase F5.2b — Restore, Orchestration, and Verification (Extraction)

Django-free restore/orchestration and verification logic was extracted into:

- **`quickscale_core.dr_engine.recovery`** — restore validation, ordered execution sequencing, destructive-operation gating, orchestration flow
- **`quickscale_core.dr_engine.verification`** — verification-record assembly, rollback-pin lifecycle and pin-field logic

The `backups` module retains higher-level platform orchestration that genuinely depends on Django project context.

### Phase F5.3 — Protocol Replacement and Module Slimming

The hidden protocol was replaced:

- **Old protocol:** `docker exec` → `manage.py backups_*` → environment variables → stdout JSON parsing, spread across multiple management commands.
- **New protocol:** `quickscale_core.dr_engine.adapter` — an explicit typed adapter with registered functions (`capture_snapshot`, `fetch_snapshot_report`, `record_verification`, `set_rollback_pin`, `build_database_plan`, `execute_database_restore`, `sync_media`) called through a single `dr_adapter_call` management command bridge (subprocess + JSON stdout).

The CLI no longer uses:
- `_run_backend_container_command`
- `_run_manage_json`
- `_build_manage_overrides` / `_source_manage_overrides` / `_target_manage_overrides`
- `_prefix_target_runtime_variables`
- `_target_media_sync_variables`
- `_is_manual_only_restore_gate`
- The `_TARGET_ENV_PREFIX` env-var protocol

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ CLI (quickscale_cli)                                             │
│ dr_commands.py → adapter functions → dr_adapter_call mgmt cmd   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ subprocess + JSON stdout
┌───────────────────────────▼─────────────────────────────────────┐
│ Backups Module (quickscale_modules_backups)                      │
│                                                                   │
│  dr_adapter_call management command (single bridge dispatch)     │
│  services.py (thin Django-facing orchestration wrappers)         │
│  models: BackupArtifact, BackupPolicy, BackupSnapshot             │
│  Admin UI for local-file restore surface                         │
│  Retained management commands                                    │
│   (backups_create, backups_report, backups_restore,              │
│    backups_record_verification, backups_pin, backups_sync_media, │
│    backups_validate, backups_prune)                              │
│   → retain backward-compatible env-var fallback for admin/manual │
└───────────────────────────┬─────────────────────────────────────┘
                            │ imports
┌───────────────────────────▼─────────────────────────────────────┐
│ DR Engine (quickscale_core.dr_engine) — Centrally Owned          │
│                                                                   │
│  primitives/    — Snapshot/archive (Django-free)                  │
│  recovery/      — Restore/orchestration (Django-free)             │
│  verification/  — Verification/rollback-pin (Django-free)         │
│  adapter/       — Explicit typed boundary (Django-free imports,   │
│                    lazy-imports module services at call time)     │
└─────────────────────────────────────────────────────────────────┘
```

### Current Responsibility Split

- **Centrally owned DR engine (`quickscale_core.dr_engine`):**
  - `primitives` — snapshot creation, archive packaging, database custom-dump
    capture.
  - `recovery` — restore validation, ordered execution sequencing,
    destructive-operation gating, orchestration flow.
  - `verification` — verification-record assembly, rollback-pin lifecycle and
    pin-field logic.
  - `adapter` — explicit typed adapter boundary (`capture_snapshot`,
    `fetch_snapshot_report`, `record_verification`,
    `set_rollback_pin`, `build_database_plan`, `execute_database_restore`,
    `sync_media`) that the CLI calls through a single bridge management
    command.
- **Embeddable `backups` module (`quickscale_modules_backups.services`):**
  retains Django-backed orchestration surfaces including snapshot capture,
  archive upload, sidecar capture, media-sync orchestration, and report-assembly
  logic that reference the `quickscale_modules` Django app environment — the
  higher-level platform orchestration that depends on Django project context.
  ``sync_backup_snapshot_media`` takes an explicit ``target_runtime_settings``
  parameter, with an env-var fallback preserved for admin/manual use through
  the management commands below.
- **CLI protocol:** The CLI
  (`quickscale_cli/src/quickscale_cli/commands/dr_commands.py`) drives DR
  through the explicit typed adapter (`quickscale_core.dr_engine.adapter`), called
  via the single ``dr_adapter_call`` management command bridge (subprocess +
  JSON stdout). The route kind marker is carried explicitly via the
  ``target_runtime_settings`` dict — there is no env-var protocol in CLI
  orchestration. Remaining management commands (``backups_create``,
  ``backups_report``, etc.) are thin Django/admin-facing surfaces for manual
  use, with env-var fallback in the service layer
  (``_load_target_runtime_settings``). Railway-target media sync fail-closed
  guard is preserved through the explicit ``ROUTE_KIND`` marker in the adapter
  path.

The authoritative *target* ownership split, boundary-interface rules, and
preserved invariants are in
[decisions.md § DR Engine Boundary Contract](./decisions.md#disaster-recovery-engine-boundary-contract-f5--m10).

## Migration Path for Existing Generated Projects

The DR engine split is a maintainer-side code reorganization. The `backups` module now imports from `quickscale-core` at runtime.

> **Important:** `quickscale update` updates module subtree code only and does not add root dependency constraints. The generated project's `pyproject.toml` template does not include `quickscale-core` by default. However, `quickscale apply` syncs the `quickscale-core` dependency entry from the embedded module manifest into the root `pyproject.toml`. The synced entry uses a repo-relative path reference (`{path = "../../quickscale_core"}`) that resolves in the maintainer layout but may not be valid for standalone projects. Those projects must replace or satisfy the synced entry with a resolvable source before `poetry install` succeeds.

### Steps

1. **Run module update:**
   ```bash
   quickscale update
   ```
   This embeds the updated module code, including the new `dr_adapter_call` management command and the slimmed `services.py`.

2. **Make `quickscale-core` available:**
   The `backups` module's `pyproject.toml` declares `quickscale-core` as a dependency. For the generated project to resolve this, `quickscale-core` must be accessible. Options include:
   - **Personal monorepo layout** (documented in [repository_layout.md](./repository_layout.md)): place `quickscale_core` at a known relative path and add a path dependency in the generated project's `pyproject.toml`.
   - **Publish `quickscale-core`** to a private package index and add the published version to the generated project's `pyproject.toml`.
   - **Vendor** the required code from `quickscale_core.dr_engine` directly into the generated project's codebase.

3. **Install dependencies:**
   ```bash
   poetry install
   ```

4. **Verify the CLI surface:**
   ```bash
   quickscale dr capture --help
   quickscale dr plan --help
   quickscale dr execute --help
   quickscale dr report --help
   ```
   All four commands remain available with identical syntax.

### Notes for Existing Projects

The following surfaces are preserved:
- **Management commands** (e.g., cron jobs calling `manage.py backups_create --scheduled`): these are **preserved** and continue to work with backward-compatible env-var fallback. Note that they import from `quickscale-core` at runtime, so the dependency must be satisfied (see Step 2 above).

- **If you rely on the stdout-JSON format of the old management commands for scripting:** the management commands remain thin wrappers over the same service layer. The output format is functionally equivalent. Verify your integration if you parse specific keys from `backups_report` or `backups_restore`.

- **If you wrote custom scripts that call `_TARGET_ENV_PREFIX` environment variables directly** (`QUICKSCALE_DR_TARGET_*`): these have been removed from the CLI orchestration path. The adapter now passes target runtime settings as an explicit `target_runtime_settings` dict. If you need the env-var protocol for scripting, use the retained management commands (which still accept `QUICKSCALE_DR_TARGET_*` env vars through the `_load_target_runtime_settings()` fallback).

- **The Railway-target media sync fail-closed guard** is preserved. The adapter path marks the route kind explicitly via `target_runtime_settings["ROUTE_KIND"]`. The management-command fallback retains the old env-var-based guard.

### New Generated Projects

Fresh generated projects that include the `backups` module will receive the updated module code through `quickscale apply`. The `apply` command syncs the `quickscale-core` dependency entry from the module manifest into the root `pyproject.toml`, but the synced path reference may need adjustment for the new project's layout — see Step 2 above.

## Backward Compatibility

| Surface | Status |
|---------|--------|
| `quickscale dr capture/plan/execute/report` CLI | **Unchanged** — same syntax, same behavior |
| Management commands (backups_create, etc.) | **Preserved** — thin wrappers with backward-compatible env-var fallback |
| `BackupArtifact` / `BackupPolicy` models | **Unchanged** — same ORM contract, same migrations |
| Admin UI (guarded restore surface) | **Unchanged** — same interface |
| `quickscale update` workflow | **Unchanged** — embeds updated module code |
| PostgreSQL 18 custom-dump contract | **Unchanged** — same restore path, same guardrails |
| JSON artifact export (non-PostgreSQL dev/test) | **Unchanged** — export-only, not a restore surface |

## Dependency Changes

- **New dependency:** The `backups` module now depends on `quickscale-core` (the module imports from `quickscale_core.dr_engine`).
- **No removed dependencies:** All existing module dependencies remain.
- **No new runtime requirements:** The extracted primitives/recovery/verification modules have no Django dependency — they are imported by the module's `services.py` at call time.

## Verification Checklist

After migration:

- [ ] `quickscale dr capture` creates a snapshot and returns a report
- [ ] `quickscale dr plan` builds a route plan from a stored snapshot
- [ ] `quickscale dr report` reads back stored snapshots
- [ ] Management commands continue to work:
  ```bash
  python manage.py backups_create --scheduled
  python manage.py backups_report <snapshot_id>
  ```
- [ ] The retained management commands accept env-var fallback (`QUICKSCALE_DR_TARGET_*`)
- [ ] All existing backups tests pass after migration

## References

- [decisions.md § Disaster Recovery Engine Boundary Contract](./decisions.md#disaster-recovery-engine-boundary-contract-f5--m10) — authoritative boundary definition and target ownership split
- [CHANGELOG.md](../../CHANGELOG.md) — phase tracking, completion status, and implementation summaries
- `quickscale_core/src/quickscale_core/dr_engine/` — current DR engine source
- `quickscale_modules/backups/src/quickscale_modules_backups/services.py` — retained module orchestration
