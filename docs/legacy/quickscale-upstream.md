# Quickscale Upstream Hardening Plan from `bap-web` Dogfood

## Document Purpose
This document captures the upstream Quickscale work discovered while integrating `auth` and `listings` in `bap-web`, the first real dogfood project.

It is written to be moved into the Quickscale repository and handed off to engineers who may not know the history of this integration.

## Why This Matters
- `bap-web` is the first real-world validation target for Quickscale module architecture.
- Breaking changes are acceptable now and preferred over preserving flawed compatibility.
- Issues discovered here are architecture-level and should be fixed in Quickscale itself, not repeatedly patched per generated project.

## Context Snapshot (from Dogfood Project)
- Project slug in `quickscale.yml`: `bap-web`.
- Django package path: `bap_web`.
- Modules to integrate: `auth`, `listings`.
- Existing migrations had already been applied before `auth` embed attempt.

## High-Level Findings
1. Module configuration path resolution assumes folder name equals Python package name.
2. Auth embed safety check is too coarse and can block/allow incorrectly.
3. `quickscale apply` can continue after embed failures, leaving partial state.
4. Module configuration contract is inconsistent (`module.yml` vs CLI configurator keys).
5. `listings` has no `module.yml`, reducing mutability support.
6. URL wiring for auth can be duplicated (`allauth.urls` in two places).
7. Plan wizard exposes modules that are not truly ready/published.
8. Generated local settings strategy favors SQLite even when Docker Postgres context exists.

## Reproducible Symptoms and Root Causes

### Symptom 1: Module auto-configuration skipped in hyphenated projects
- Observed behavior:
  - Module embed can succeed, but settings and URL auto-wiring can be skipped.
- Root cause:
  - Several Quickscale code paths build settings/URL paths using `project_path.name` directly.
  - For slug `bap-web`, expected package path becomes `bap-web/settings/base.py` instead of `bap_web/settings/base.py`.
- Affected code:
  - `quickscale_cli/src/quickscale_cli/commands/module_config.py`
  - `quickscale_core/src/quickscale_core/settings_manager.py`
  - `quickscale_cli/src/quickscale_cli/commands/remove_command.py`

### Symptom 2: Auth embed blocked in non-interactive mode after any prior migration
- Observed behavior:
  - `quickscale apply` embedding `auth` fails in non-interactive mode when migrations have already run.
- Root cause:
  - `has_migrations_been_run()` checks `db.sqlite3` existence and lightweight command output heuristics.
  - This is not robust across DB engines and project states.
- Affected code:
  - `quickscale_cli/src/quickscale_cli/commands/module_config.py`
  - `quickscale_cli/src/quickscale_cli/commands/module_commands.py`

### Symptom 3: Apply proceeds after module embed failure
- Observed behavior:
  - Apply can continue to `poetry install` and `migrate` after one or more module embed failures.
- Root cause:
  - `_embed_modules_step()` logs warning and continues.
  - Post-generation steps still run.
- Affected code:
  - `quickscale_cli/src/quickscale_cli/commands/apply_command.py`

### Symptom 4: Config mutability mismatch between manifests and configurators
- Observed behavior:
  - Auth manifest uses `registration_enabled`; configurator uses `allow_registration`.
  - Delta/mutable update logic can become inconsistent.
- Root cause:
  - No single canonical source of truth enforced for option keys.
- Affected files:
  - `quickscale_modules/auth/module.yml`
  - `quickscale_cli/src/quickscale_cli/commands/module_config.py`
  - `quickscale_cli/src/quickscale_cli/schema/delta.py`

### Symptom 5: Listings lacks manifest
- Observed behavior:
  - No `module.yml` for listings; mutable/immutable behavior falls back to generic immutable assumptions.
- Root cause:
  - Missing manifest in module package.
- Affected path:
  - `quickscale_modules/listings/` (missing `module.yml`)

### Symptom 6: Duplicate auth URL ownership
- Observed behavior:
  - Configurator inserts `allauth.urls`.
  - Auth module also includes `allauth.urls`.
- Root cause:
  - Overlapping URL wiring responsibilities.
- Affected files:
  - `quickscale_cli/src/quickscale_cli/commands/module_config.py`
  - `quickscale_modules/auth/src/quickscale_modules_auth/urls.py`

### Symptom 7: Plan wizard module list not filtered by readiness
- Observed behavior:
  - Placeholder/not-ready modules can appear selectable.
- Root cause:
  - Static module list in plan command without release readiness checks.
- Affected file:
  - `quickscale_cli/src/quickscale_cli/commands/plan_command.py`

## Upstream Work Packages

## WP-01: Project Identity Model (Breaking Change)
### Goal
Stop deriving Python package path from project directory slug.

### Recommended Design
Introduce explicit project identity fields:
- `project.slug`: filesystem/service/human name
- `project.package`: Python import/package name

### Tasks
- [ ] Update config schema and validation for `slug` and `package`.
- [ ] Add migration path for old configs:
  - If only `name` exists, map:
    - `slug = name`
    - `package = name.replace("-", "_")`
- [ ] Replace all `project_path.name` assumptions in module config/remove/settings update code.
- [ ] Persist package name in state file.
- [ ] Update generators/templates/docs to use explicit package field.

### Acceptance Criteria
- [ ] Hyphenated slug with underscored package works for module apply, mutable config updates, and remove command.
- [ ] Non-hyphenated projects still work after migration.
- [ ] No code path infers package path from folder name.

## WP-02: Deterministic Module Wiring Engine
### Goal
Replace brittle text injection into `settings.py` and `urls.py`.

### Recommended Design
Use generated, managed integration files:
- `<package>/settings/modules.py`
- `<package>/urls_modules.py`

Base files import/include managed blocks exactly once.

### Tasks
- [ ] Add module wiring renderer in Quickscale core.
- [ ] Generate idempotent module settings and URL include files.
- [ ] Refactor configurators to emit structured config, not string patches.
- [ ] Ensure auth URL ownership is single-source (module or project, not both).
- [ ] Update remove flow to regenerate wiring files rather than ad-hoc string deletion.

### Acceptance Criteria
- [ ] Re-running apply is idempotent with zero duplicate lines.
- [ ] Remove/add module operations do not leave stale imports/includes.
- [ ] Manual user edits outside managed files are preserved.

## WP-03: Auth Migration Guardrails
### Goal
Prevent invalid custom-user adoption sequences with accurate checks and clear remediation.

### Tasks
- [ ] Replace `has_migrations_been_run()` heuristic with DB-aware migration recorder checks.
- [ ] Add explicit blocking condition:
  - If auth module requested and default user tables/history already applied, stop with actionable steps.
- [ ] Improve remediation output:
  - clean DB path
  - reverse migration path
  - data-loss warning path
- [ ] Add non-interactive behavior:
  - hard fail with non-zero exit and no partial continue.

### Acceptance Criteria
- [ ] Auth can be embedded only in valid states.
- [ ] Error output contains copy-paste-safe remediation commands.
- [ ] No false positives from just `db.sqlite3` existence.

## WP-04: Apply Transaction and Failure Semantics
### Goal
`quickscale apply` must be atomic enough for trust: no silent partial success.

### Tasks
- [ ] Introduce strict step gating:
  - if any required module embed fails, abort apply.
- [ ] Skip post-generation install/migrate when required earlier steps failed.
- [ ] Save state only for confirmed successful module operations.
- [ ] Add summary with explicit success/failure by step.

### Acceptance Criteria
- [ ] Failed embed returns non-zero exit.
- [ ] No misleading "apply complete" when required module failed.
- [ ] State file cannot claim module applied when embed failed.

## WP-05: Manifest Contract Enforcement
### Goal
All modules must have valid manifest and consistent option keys.

### Tasks
- [ ] Add `module.yml` to listings module.
- [ ] Align auth configurator keys with auth manifest keys.
- [ ] Add CI check:
  - every module in release list has valid manifest.
  - configurator options match manifest schema.
- [ ] Ensure mutable options map to valid Django settings keys only.

### Acceptance Criteria
- [ ] `auth` and `listings` config deltas correctly classify mutable vs immutable changes.
- [ ] Option key mismatch fails CI before release.

## WP-06: Module Catalog Readiness
### Goal
Plan wizard should present only shippable modules for selection.

### Tasks
- [ ] Add module metadata registry with readiness state.
- [ ] Filter `plan` selection to ready modules by default.
- [ ] Optional: add `--include-experimental` mode.
- [ ] Align docs and help text with actual availability.

### Acceptance Criteria
- [ ] Users cannot select modules that have no valid split branch or are not release-ready.

## WP-07: Generator Local DB Strategy
### Goal
Local settings should support practical Docker parity and auth/listings migration safety.

### Tasks
- [ ] Update generated `settings/local.py` to:
  - prefer `DATABASE_URL` when present
  - fallback to SQLite only when unset
- [ ] Add tests for local settings DB resolution behavior.
- [ ] Update docs to clarify local DB mode and auth custom-user timing requirements.

### Acceptance Criteria
- [ ] Generated project can run local dev with Postgres via env without manual settings rewrite.

## WP-08: End-to-End Test Coverage for Dogfood Scenarios
### Goal
Prevent regressions on exactly the integration path validated in `bap-web`.

### Tasks
- [ ] Add E2E scenario:
  - hyphen slug + underscored package
  - add auth + listings
  - apply
  - migrate
  - validate routes and state
- [ ] Add negative test:
  - auth requested after incompatible migration state must fail hard.
- [ ] Add idempotency test:
  - repeated apply produces no extra settings/URL duplication.

### Acceptance Criteria
- [ ] CI reproduces and protects against all failures discovered during this dogfood integration.

## Breaking Changes and Migration Plan

## Breaking Changes Expected
- Config schema update (`project.name` replacement/split).
- Module wiring implementation strategy (managed files instead of direct edits).
- Apply failure behavior becomes strict (more failures become hard errors).

## Migration Plan
- [ ] Add schema upgrade utility for old `quickscale.yml`.
- [ ] Add compatibility reader for old state files during transition window.
- [ ] Publish clear release notes with "before/after" examples.
- [ ] Provide one release cycle with migration warnings before removing old parser paths.

## Suggested Execution Order
1. WP-01 project identity model.
2. WP-04 apply failure semantics.
3. WP-03 auth migration guardrails.
4. WP-05 manifest contract enforcement.
5. WP-02 deterministic module wiring engine.
6. WP-06 module catalog readiness.
7. WP-07 generator local DB strategy.
8. WP-08 e2e hardening tests.

## Project-Level Handoff Notes
- This plan came from real integration work in `bap-web`.
- Keep project-specific hotfixes minimal.
- Land upstream fixes first when possible, then simplify `bap-web` by removing local workarounds.

## Definition of Done for Upstream Hardening Milestone
- [ ] `bap-web` can be regenerated/applied with auth+listings without manual wiring hacks.
- [ ] Hyphen slug projects no longer break module integration.
- [ ] Auth integration fails safely and predictably when DB state is incompatible.
- [ ] Apply/state behavior is consistent and trustworthy.
- [ ] Module manifests/options are consistent and CI-enforced.


## Update:
- As a creator/maintainer i dont want to use SQLite for local development when a Postgres on docker is viable, so that I can have better parity with production and avoid SQLite-specific issues. Remove all SQLite alternatives from generated settings and use env var detection to switch to Postgres when available. Add documentation on local DB strategy and auth custom-user timing requirements.
- Also i want to review the other modules for the same concepts explained here and update as needed, to ensure consistency across modules and avoid similar issues in the future.
- The bap-web project could be found in ../bap-web. You could check the code there, run railway command or quickscale commands (after global install) to see the issues in action and validate the fixes.
