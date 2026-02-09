# Upstream Hardening TODO Tracker

Last updated: 2026-02-09
Source plan: `quickscale-upstream.md`

## Summary
- [x] Review complete and baseline validated for current branch.
- [x] Additional finding resolved: CRM `enable_api` mutable option now includes `django_setting`.
- [x] Full scope implemented: WP-01..WP-08.
- [x] Immediate hard break enforced for legacy `project.name` schema.
- [x] Local settings are Postgres-only (no SQLite fallback in `local.py`).
- [x] Auth module owns `allauth` URL inclusion.
- [x] `quickscale apply` is fail-fast with no rollback.
- [x] `billing`/`teams` hidden by default; exposed with `--include-experimental`.

## Public API / Interface Changes
- [x] `quickscale.yml` schema migrated to `project.slug` + `project.package`.
- [x] `.quickscale/state.yml` schema migrated to `project.slug` + `project.package`.
- [x] `quickscale plan` positional arg uses semantic `PROJECT_SLUG`.
- [x] `quickscale plan --package` implemented.
- [x] `quickscale plan --include-experimental` implemented.
- [x] Generated managed integration files added:
- [x] `<package>/settings/modules.py`
- [x] `<package>/urls_modules.py`
- [x] Generated local settings require `DATABASE_URL` (Postgres-only).
- [x] `quickscale apply` failure semantics updated (fatal module embed failures, downstream skipped, explicit summary).

## Phase 1: Project Identity Model (WP-01)
- [x] `config_schema.py` updated to `slug`, `package`, `theme`.
- [x] Strict independent validation for slug and package.
- [x] Hard error on missing `project.slug` or `project.package`.
- [x] YAML generation writes new fields only.
- [x] `state_schema.py` updated to `slug`, `package`, `theme`, timestamps.
- [x] Legacy `project.name` rejected with migration hint.
- [x] Removed `project_path.name` assumptions in command paths:
- [x] `module_config.py`
- [x] `remove_command.py`
- [x] `settings_manager.py`
- [x] `status_command.py`
- [x] Added `project_identity.py` resolver (order: config -> state; no folder inference).
- [x] `plan_command.py` updated for `PROJECT_SLUG`, package prompt/default, and writing both fields.
- [x] `apply_command.py` uses slug output dir, passes explicit package to generator, writes slug/package into state.
- [x] `generator.py` supports optional explicit package argument.

## Phase 2: Deterministic Wiring Engine (WP-02)
- [x] Added core renderer: `quickscale_core/src/quickscale_core/module_wiring.py`.
- [x] Added structured CLI specs: `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py`.
- [x] Managed wiring targets implemented:
- [x] `<package>/settings/modules.py`
- [x] `<package>/urls_modules.py`
- [x] Templates updated to consume managed files once:
- [x] `base.py.j2`
- [x] `urls.py.j2`
- [x] Added `modules.py.j2` and `urls_modules.py.j2` templates.
- [x] Configurators refactored to regenerate managed files (no ad-hoc settings/urls patching).
- [x] Auth URL ownership enforced: project wiring includes only `quickscale_modules_auth.urls`.
- [x] Remove flow regenerates managed files from remaining modules.

## Phase 3: Auth Guardrails (WP-03)
- [x] Replaced heuristic with DB-aware migration recorder check via Django runtime.
- [x] Added explicit incompatible/unverifiable detection for auth embed in `module_commands.py`.
- [x] Non-interactive mode hard-fails on incompatible/unverifiable state.
- [x] Added remediation output paths (fresh DB, Docker volume reset, destructive reset warning).
- [x] Fixed remediation formatting to true newline output (copy-paste-safe).

## Phase 4: Apply Failure Semantics (WP-04)
- [x] `_embed_modules_step` returns structured `EmbedModulesResult`.
- [x] Fail-fast on first required module embed failure.
- [x] Skip install/migrate/docker when embed fails.
- [x] Save state only for successful module operations in failed run.
- [x] Explicit failure summary printed.
- [x] Non-zero exit on failure via `click.Abort`.
- [x] No rollback behavior retained.

## Phase 5: Manifest Contract Enforcement (WP-05)
- [x] Added missing manifests:
- [x] `quickscale_modules/listings/module.yml`
- [x] `quickscale_modules/blog/module.yml`
- [x] Auth key alignment completed (`registration_enabled` canonical; legacy compatibility retained).
- [x] CRM manifest fixed (`enable_api` has `django_setting: CRM_ENABLE_API`).
- [x] Added contract tests: `quickscale_cli/tests/test_module_manifest_contract.py`.
- [x] Contract checks cover ready-module manifest validity, default key alignment, mutable setting-key validity.
- [x] CI gate added in `.github/workflows/ci.yml`.

## Phase 6: Module Catalog Readiness (WP-06)
- [x] Added module metadata source: `quickscale_cli/src/quickscale_cli/module_catalog.py`.
- [x] Ready modules set: `auth`, `blog`, `listings`, `crm`.
- [x] Experimental hidden-by-default modules set: `billing`, `teams`.
- [x] Replaced duplicated module lists in:
- [x] `plan_command.py`
- [x] `module_commands.py`
- [x] `config_schema.py`
- [x] Implemented `quickscale plan --include-experimental`.

## Phase 7: Local DB Strategy + Docs (WP-07)
- [x] `local.py.j2` switched to Postgres-only and requires `DATABASE_URL` with `dj_database_url`.
- [x] Removed SQLite fallback language from base/local README guidance.
- [x] Updated env templates for local Postgres defaults:
- [x] `.env.j2`
- [x] `.env.example.j2`
- [x] Added auth custom-user timing guidance in generated README.
- [x] Updated top-level docs/examples to slug/package schema:
- [x] `README.md`
- [x] `docs/technical/user_manual.md`
- [x] `docs/technical/plan-apply-system.md`

## Phase 8: Dogfood Regression Coverage (WP-08)
- [x] Added/extended tests for slug/package schema + semantics across target files:
- [x] `quickscale_cli/tests/test_schema.py`
- [x] `quickscale_cli/tests/test_state_schema.py`
- [x] `quickscale_cli/tests/test_plan_command.py`
- [x] `quickscale_cli/tests/test_plan_add.py`
- [x] `quickscale_cli/tests/test_plan_reconfigure.py`
- [x] `quickscale_cli/tests/test_apply_command.py`
- [x] `quickscale_cli/tests/test_apply_command_extended.py`
- [x] `quickscale_cli/tests/test_status_command.py`
- [x] `quickscale_cli/tests/test_status_command_extended.py`
- [x] `quickscale_cli/tests/commands/test_module_config.py`
- [x] `quickscale_cli/tests/commands/test_module_config_extended.py`
- [x] `quickscale_cli/tests/commands/test_remove_command.py`
- [x] `quickscale_cli/tests/commands/test_remove_command_extended.py`
- [x] `quickscale_core/tests/test_settings_manager.py`
- [x] `quickscale_core/tests/test_generator/test_templates.py`
- [x] `quickscale_core/tests/test_generator/test_generator.py`
- [x] Added explicit manifest contract coverage.

## Validation Scenarios
- [x] CLI suite green: `poetry run pytest -q --no-cov quickscale_cli` -> `756 passed, 26 deselected`.
- [x] Core suite green: `poetry run pytest -q --no-cov quickscale_core` -> `308 passed, 2 skipped, 14 deselected`.
- [x] Module suites green (CI-style invocations):
- [x] `auth` -> `36 passed`
- [x] `blog` -> `34 passed`
- [x] `listings` -> `68 passed`
- [x] `crm` -> `67 passed`
- [x] Hard break confirmed for legacy `project.name` on temp `bap-web` copy.
- [x] `bap-web`/`bap_web` slug/package resolution confirmed via status + managed wiring generation in `/tmp/bap-web-dogfood`.
- [x] Managed wiring idempotency confirmed on repeated regeneration (same output, no duplicate auth/listings includes).
- [x] Auth migration guard validated in non-interactive mode with actionable remediation and hard fail (`result: False`).
- [x] Manual dogfood run executed against temp copy `/tmp/bap-web-dogfood` (no in-repo mutation path).

## Assumptions and Defaults Locked
- [x] Breaking schema change is immediate (no legacy compatibility mode).
- [x] Auth URL ownership stays in auth module.
- [x] Apply remains fail-fast and non-rollback.
- [x] Local development requires Postgres `DATABASE_URL`.
- [x] `billing` and `teams` remain hidden unless `--include-experimental` is used.

## Pending Items
- [x] None.
