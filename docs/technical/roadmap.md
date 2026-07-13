# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work. Detailed completed implementation history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here.
- Move detailed completed implementation history to CHANGELOG.md.
- Each open phase links back (`why →`) to the finding that justifies it.

---

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

> **Shared closeout files (`CHANGELOG.md` and `docs/technical/roadmap.md`):** Because every track touches these files, they are the most likely source of merge conflicts. The procedure above already handles this — the `git merge v87` before merge-back ensures you resolve any conflicting entries on your track branch rather than on `v87`. Do not skip or reorder that step. When resolving, keep both tracks' entries (don't overwrite another track's completed work).

---

## Open work

> Completed and archived work lives in [CHANGELOG.md](../../CHANGELOG.md). This section retains checked closeout entries for completed items as evidence of acceptance (their full implementation detail lives in CHANGELOG.md). Active and blocked work stays open below.
>
> **Track readiness (2026-07-13, updated):** SA82 (Track 3) completed — the SA76 `orgs`/`notifications` quarantine entries are removed; the full `make test-integration` gate ran with both suites unquarantined (exit 1, as expected: orgs 847 passed/11 BYPASSRLS-skips/0 failed, notifications 39 passed/0 failed, overall mean coverage 92.95% passed). SA77 and SA79 closed by this result — their acceptance conditions are met. SA85 (Track 2) blocked — forms restricted-role implementation/validation complete (196p/8s/12d/0f/0e; E2E 12p; intermediate 186p/0f/0e, 95.70%; QG2 gate 93.00% mean, exit 1 solely from other findings); independent review blocked on CR-SA85-REV-001 (high/blocking — admin-route/session parity contract remains incomplete in tests/README). CR-SA85-REV-002 through CR-SA85-REV-007 resolved. User directed stop, commit, merge blocked checkpoint. The repository integration gate remains red due to separate independent restricted-role findings (SA83, SA84, SA86) that do not affect SA77/SA79 closure.
> - **Track 1** — unblocked from SA82 (SA77 closed); open findings SA83 (blog, 86 RLS failures) and SA84 (CRM, 67 RLS failures/20 skipped) recorded below — each is a separate restricted-role residual, not a blocker for SA77/SA85 closure.
> - **Track 2** — unblocked from SA82 (SA79 closed); its own acceptance conditions (forms 0007 backfill + unquarantined notifications under the full gate) are satisfied. Reassigned 2026-07-13 from Track 1 (parallelization): SA85 (forms residual) impl/validation complete 2026-07-13 — review blocked on CR-SA85-REV-001, see below; SA86 (listings, 6 RLS failures) open, no deps.
> - **Track 3** — SA80 (venv + retained-role env wiring) done; SA82 (gate rerun) completed; SA80.3a (pg_dump install) done 2026-07-13; SA80.3b (backups suite rerun) completed 2026-07-13; SA81 (no deps) remains open; SA87 (username-independent restore test) completed 2026-07-13.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — done (SA82, 2026-07-13)         SA79 — done (SA82, 2026-07-13)            SA80 — done (2026-07-13)
  orgs 847p/11 BYPASSRLS-skips/0f        notifications 39p/0f;                     SA82 — done (2026-07-13)
  code fix verified live under gate      forms 0007 acceptance verified            SA80.3a — done (2026-07-13)
SA83 — blog (86 RLS failures) open,      SA85 — forms residual —                     SA80.3b (backups rerun)
  no deps, unknown root cause              impl/validation complete;                  done (2026-07-13)
SA84 — CRM (67 RLS failures/20             CR-SA85-REV-002–007 resolved;              SA81 — open, no deps
  skipped) open, no deps, unknown          blocked: CR-SA85-REV-001                   SA87 — username-independent
  root cause                               Current: 196p/8s/12d/0f/0e                  restore test
                                           QG2: 192p/8s/95.73%/93.00% mean            done (2026-07-13)
                                           Intermed: 186p/8s/0f/0e/95.70%
                                           E2E 12p, no quarantine
                                            SA86 — listings (6 RLS failures)
                                              open, no deps, unknown root
                                              cause (reassigned from Track 1,
                                              2026-07-13)
```


SA82 (Track 3) completed 2026-07-13 — the `orgs`/`notifications` quarantine entries are removed; the full gate rerun confirmed orgs (847 passed/11 BYPASSRLS-skips/0 failed) and notifications (39 passed/0 failed) clean. SA77 and SA79 are closed by this result. Track 1 is unblocked from SA82 with SA83–SA84 open; Track 2 is unblocked from SA82 with SA85 impl/validation-complete/review-blocked (see below; CR-SA85-REV-001 high/blocking, REV-002–007 resolved) and SA86 open. The integration gate remains red due to separate independent restricted-role findings (SA83, SA84, SA86) recorded below. (SA81 is unrelated cleanup — per-module lockfile removal — and does not affect the gate.)

### Track 1 — Tenant-context surface

SA59 (umbrella, SA59.1–SA59.4) closed 2026-07-12 — see CHANGELOG.md. SA77 closed 2026-07-13 by SA82 — see below and CHANGELOG.md. Two independent restricted-role residuals in blog and CRM are recorded as SA83–SA84 below; the forms and listings residuals (SA85–SA86) were reassigned to Track 2 on 2026-07-13 to parallelize the four findings across both tracks.

- [x] **SA77 — Root-cause and fix orgs' restricted-role test failures.** `Tier 1 · Track 1 · deps: none → closed 2026-07-13`
  Code fix landed 2026-07-12 — full root-cause and fix detail (psycopg2→`connection.cursor()` conversion in two test helpers; 6 dynamic-DDL tests marked `@pytest.mark.bypass_rls`) is in [CHANGELOG.md](../../CHANGELOG.md)'s SA77 entry, not repeated here.

  *Acceptance:* the 3 helper-path restricted-role tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the 6 dynamic-DDL tests skip in restricted mode. The `scripts/test_integration.sh` quarantine entry was removed in SA82. The full `make test-integration` gate run (2026-07-13) confirmed orgs 847 passed/11 BYPASSRLS-skips/0 failed, 93.04% coverage. SA77 closed.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — Blog restricted-role RLS failures (`why →` CR-SA82-NT-002; discovered during SA82 full-gate rerun)

- [ ] **SA83 — Investigate and fix blog's 86 restricted-role RLS failures.** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate run with quarantine entries removed, blog's restricted-role suite showed 121 passed, 86 RLS failures. Root cause is unknown/unconfirmed — the failures are RLS policy violations under `quickscale_test_role` (NOBYPASSRLS), but the specific mechanism (missing org context, missing `operator_access`, or policy gap) has not been isolated.

  *Acceptance:* blog's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-002*)*

#### Finding — CRM restricted-role RLS failures (`why →` CR-SA82-NT-003; discovered during SA82 full-gate rerun)

- [ ] **SA84 — Investigate and fix CRM's 67 restricted-role RLS failures (plus 20 skipped).** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate run, CRM's restricted-role suite showed 195 passed, 67 RLS failures, 20 skipped. Root cause is unknown/unconfirmed — RLS policy violations under `quickscale_test_role`.

  *Acceptance:* CRM's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-003*)*

### Track 2 — Module contracts & settings

SA79 closed 2026-07-13 by SA82 — see below and CHANGELOG.md. SA85 impl/validation complete 2026-07-13 (see below); independent review blocked on CR-SA85-REV-001 (high/blocking); CR-SA85-REV-002 through CR-SA85-REV-007 resolved. SA86 reassigned here from Track 1 on 2026-07-13; remains open. See CHANGELOG.md for SA85 implementation detail; current status is impl/validation-complete/review-blocked — do not close before CR-SA85-REV-001 is resolved.

- [x] **SA79 — Closeout verification/reconciliation.** `Tier 1 · Track 2 · deps: none → closed 2026-07-13`

  The full `make test-integration` gate run (SA82, 2026-07-13) confirmed notifications 39 passed/0 failed, 91.76% coverage — unquarantined, clean. Forms 0007 backfill acceptance verified under the full retained-role environment with the BYPASSRLS hatch closed and quarantine entries removed.

  SA80 (Track 3) resolved the local env gaps; SA82 removed the quarantine entries and confirmed both acceptance conditions under `make test-integration` itself rather than a narrower direct-pytest rerun. Audit/status docs refreshed in this pass.

  *Acceptance:* forms 0007 backfill passes under full retained-role env; notifications suite runs clean (unquarantined) under a full `make test-integration` gate run; audit/status docs reflect current state. **Achieved.** SA79 closed.

- [ ] **SA85 — Fix forms' residual restricted-role test failures (implementation/validation complete; independent review blocked — CR-SA85-REV-001 high/blocking; CR-SA85-REV-002 through CR-SA85-REV-007 resolved).** `Tier 1 · Track 2 · deps: none → impl/validation complete 2026-07-13; review blocked on CR-SA85-REV-001` *(reassigned from Track 1, 2026-07-13)*

  Under the SA82 full `make test-integration` gate run, forms' restricted-role suite showed 140 passed, 33 RLS failures, 8 skipped, 10 errors (historical SA82 baseline; individual reproduction on the current branch before fixes: 139 passed/29 failed/8 skipped/11 deselected/15 errors). Root cause: RLS policy violations and test-structural errors under `quickscale_test_role` — tests created rows outside an `org_scope` context, so FORCE RLS blocked both reads and writes on tenant-managed models; management commands used `all_objects` without `operator_access` for cross-tenant reads and wrote outside `org_scope`; admin views and notification content building lacked role-aware org scoping.

  **Fix summary (4 phases):**
  - **Phase 1 (bounded fixture/test org scopes):** conftest, `test_models.py`, `test_serializers.py`, `test_validators.py`, `test_notifications.py`, `test_admin.py`, `test_isolation.py`, `test_management.py`, `test_migrations.py`, `test_views.py` — model creation and mutations wrapped in `org_scope()` so FORCE RLS sees the correct `app.current_org_id` GUC. Two slug-uniqueness / field-duplicate expected-failure paths use `set_current_org_id` + `set_db_current_org_id` to avoid the AF9 priming-memo staleness and savepoint-abort issues inside `org_scope`.
  - **Phase 2 (retained-role management read-inventory/per-org writes):** `forms_anonymize_submissions.py` and `forms_seed_presets.py` rewritten with a three-phase pattern: `operator_access(reason=...)` for cross-tenant SELECT inventory reads, per-organization writes inside `org_scope()`, all wrapped in `transaction.atomic()`. `operator_access` is SELECT-only (SA14.5) audit-logged at INFO via `operator_access`.
  - **Phase 3 (notification content scoped and post-commit tested):** `notifications.py::_enqueue_notification` now wraps `_build_submission_notification_content(submission)` inside `org_scope(submission.organization)` so FORCE RLS allows reading committed `FormFieldValue` rows via the DB-level GUC. The scope exits before email delivery, ensuring no live transaction is held across a remote call. New `TestNotifySubmissionNoContext` regression test proves `notify_submission` works without ambient org context or active `transaction.atomic()` — the content renders correctly and field values appear in the email body.
  - **Phase 4 (Staff current-org/superuser operator contract across source/tests/README/E2E):** `views.py::FormsAdminApiMixin` gains `_is_superuser()`, `_get_org_bound_queryset()` (superuser → `all_objects`, regular staff with active org → `objects`, regular staff without org → `objects.none()` fail-closed), and `_with_superuser_operator_access()` for cross-tenant read audit. All four admin views (`AdminFormListAPIView`, `AdminSubmissionListAPIView`, `AdminSubmissionDetailAPIView`, `AdminSubmissionExportView`) are role-aware: superuser reads through `operator_access`, regular staff scoped to active org, PATCH saves inside the target record's `org_scope`. `test_e2e.py` adapted for the new contract. README `Retained-Role Contract` table documents the superuser/staff/anonymous matrix.

  **SA77 boundary helper reuse:** `test_rls_boundary.py::_ensure_rls_test_role()` reuses the SA77 `connection.cursor()` + savepoint pattern (psycopg2 → Django managed connection) with best-effort GRANTs wrapped in `transaction.atomic()` savepoints so permission-denied failures under NOBYPASSRLS do not abort the outer test transaction.

  **Serializer/validator context amendment:** `test_serializers.py` and `test_validators.py` tests wrap data setup in `org_scope()`, making assertions non-vacuous — previously they passed because `all_objects.create` silently bypassed RLS; now they prove the serializer/validator paths work correctly under FORCE RLS.

  *Evidence:*
  - Intermediate (post-Phase 1–3, pre-Phase 4): module suite **186 passed/8 existing DDL-only skips/12 e2e deselected/0 failed/0 errors/95.70% coverage** (lint, type, org-context all pass).
  - Forms E2E: **12 passed**.
  - QG2 full gate (`QUICKSCALE_ALLOW_BYPASSRLS=0 make test-integration`): forms runs without quarantine entry; overall mean coverage **93.00%**; **exit 1 solely** from unchanged SA83 (blog 86), SA84 (CRM 67 failures/20 skips), SA86 (listings 6).
  - All other modules clean — no regression introduced.

  **Non-blocking discovered observations:**
  - Disposable Forms test DB had one stale `postgres`-owned `django_session` table (from earlier non-`quickscale_test_role` runs); it was recreated under `quickscale_test_role` for transaction-test teardown — environment evidence, not a product change.
  - Existing Django app-init DB-access warning (BYPASSRLS/SUPERUSER boot guard during `manage.py test` discovery) remains unchanged — it fires before any module-specific setup, is a pre-existing Django test-runner pattern, and is unrelated to SA85.

  **No Forms quarantine entry needed** — the fixed suite runs clean under the full retained-role gate without any `QUARANTINE_TICKETS` entry.

  **Review status (7 findings):**
  - **CR-SA85-REV-001** (high, blocking): Forms admin session tests/README still rely on a false `/admin/` exemption premise — tests do not create own/foreign Forms using real `force_login` + `ACTIVE_ORG_SESSION_KEY` without direct context, failing to assert staff inclusion/exclusion and superuser cross-tenant parity. No-org staff/superuser behavior not tested (expected 302 redirect to `/orgs/`). README contract table and comments/references incomplete.
  - **CR-SA85-REV-002 through CR-SA85-REV-007** (resolved in earlier review passes).

  *Required next action:* rewrite `test_views.py` admin-form-list tests to create own/foreign Forms, use real `force_login` + `ACTIVE_ORG_SESSION_KEY` with no direct context, assert staff inclusion/exclusion and superuser cross-tenant; no-org staff/superuser must request admin-form-list and assert 302 Location `/orgs/`; correct README contract table, comments, and references.

  **Settled decisions (no product decision remains):**
  - TenantMiddleware redirect is the correct mechanism for driving users to select/switch organizations — preserved as-is.
  - QG2 backups-port attribution: user accepted the backups port artifact; no further action needed.
  - User explicitly directed: stop review iteration, update roadmap/CHANGELOG to reflect blocked checkpoint, commit, merge to `v87` as a blocked checkpoint branch. No product decision remains.

  **Current code checkpoint:** Forms 196p/8s/12d/0f/0e; E2E 12p; lint/type/context/diff pass. QG2 earlier 192p/8s/95.73%, overall mean 93.00%, user-accepted backups port artifact. SA83/84/86 remain on Tracks 1–2.

  **SA85 checkbox remains `[ ]`** — closing CR-SA85-REV-001 (or a user decision to waive/descope) is required before closure. No product decision remains.
  *(why →* CR-SA82-NT-004; CR-SA85-REV-001 through CR-SA85-REV-007*)
#### Finding — Listings restricted-role RLS failures (`why →` CR-SA82-NT-005; discovered during SA82 full-gate rerun)

- [ ] **SA86 — Investigate and fix listings' 6 restricted-role RLS failures.** `Tier 1 · Track 2 · deps: none` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 full `make test-integration` gate run, listings' restricted-role suite showed 128 passed, 6 RLS failures. Root cause is unknown/unconfirmed — RLS policy violations under `quickscale_test_role`.

  *Acceptance:* listings' restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-005*)*

### Track 3 — Core/CLI plumbing

SA80 closed 2026-07-13 (venv re-provision + retained-role env wiring) — see CHANGELOG.md. SA82 completed 2026-07-13. SA80.3a closed 2026-07-13. SA80.3b completed 2026-07-13. SA81 (no deps) is open. SA87 (username-independent restore test) completed 2026-07-13.

- [x] **SA82 — Remove the SA76 `orgs`/`notifications` quarantine entries and rerun the full `make test-integration` gate to prove SA77/SA79 clean.** `Tier 1 · Track 3 · deps: none → completed 2026-07-13`

  Removed `orgs` and `notifications` from `QUARANTINE_TICKETS` in `scripts/test_integration.sh` (passed `bash -n` syntax check). Ran `make test-integration` end-to-end — exit 1 (expected: separate findings remain). Target evidence: orgs 847 passed/11 BYPASSRLS-skips/0 failed, 93.04% coverage; notifications 39 passed/0 failed, 91.76% coverage. Overall mean coverage 92.95% passed.

  SA77 closed and SA79 closed by this result — their acceptance conditions are met under the full unquarantined gate. The four independent restricted-role findings surfaced by removing the quarantine are recorded as SA83 (blog, 86 RLS failures) and SA84 (CRM, 67 RLS failures/20 skipped) in Track 1 above, and SA85 (forms residual, blocked checkpoint — impl/validation complete, review blocked on CR-SA85-REV-001 — see above) and SA86 (listings, 6 RLS failures) in Track 2 (reassigned 2026-07-13 to parallelize). Backups was tracked by SA80.3b — resolved 2026-07-13 (see below).

  *Acceptance:* orgs and notifications both pass clean under the full unquarantined gate. **Achieved.** SA77 and SA79 closed.
  *(why →* 2026-07-13 roadmap closeout checkpoint, [CHANGELOG.md](../../CHANGELOG.md)*)*

#### Finding — PostgreSQL client tools missing locally (`why →` CR-SA82-NT-001; discovered during SA82 full-gate rerun)

SA80.3 split 2026-07-13 into SA80.3a (done) and SA80.3b (done) — the local pg_dump/pg_restore 18.4 install resolved the tooling gap; the rerun confirmed 0 missing-`pg_dump`/`pg_restore` failures (retained-role: 298 passed/1 failed/2 skipped; default-user: 299 passed/2 skipped). The 1 retained-role failure was a pre-existing test expectation mismatch tracked as SA87 (resolved 2026-07-13).

- [x] **SA80.3a — Install PostgreSQL 18 client tools locally.** `Tier 1 · Track 3 · deps: none → completed 2026-07-13`
  Added the PGDG apt repository (signed-by keyring at `/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg`, source list `/etc/apt/sources.list.d/pgdg.list` pointing at `noble-pgdg main`) and installed `postgresql-client-18` via `apt-get`, matching the guidance already printed in the `BackupError` message (`quickscale_core/src/quickscale_core/dr_engine/primitives.py::_postgresql_18_client_tooling_guidance`). Verified: `pg_dump --version` → `pg_dump (PostgreSQL) 18.4 (Ubuntu 18.4-1.pgdg24.04+1)`.
  *Acceptance:* `pg_dump`/`pg_restore` 18.x resolve on `PATH` locally. **Achieved.**

- [x] **SA80.3b — Rerun the `backups` suite to confirm the 24 missing-`pg_dump` failures are resolved.** `Tier 1 · Track 3 · deps: SA80.3a (done) → completed 2026-07-13`
  0 missing-`pg_dump`/`pg_restore` failures remain. pg_dump and pg_restore 18.4 confirmed on PATH. Ran `QS_BACKUPS_DB_USER=quickscale_test_role make MODULE=backups test -- --modules`: 298 passed, 1 failed, 2 skipped in 55.98s. The 1 failure (`test_restore_file_mode_executes_pg_restore_for_operator_dump`) is a pre-existing test expectation mismatch — it hardcodes `--username postgres` but the retained-role env uses `quickscale_test_role`. Without the env var (default `postgres` user): 299 passed, 2 skipped in 55.61s — 0 failures. All 24 original missing-`pg_dump` failures resolved. Updated SA82 evidence block and Track 3 summary. See CHANGELOG.md for full detail.
  *Acceptance:* 0 failures attributable to missing `pg_dump`/`pg_restore`. **Achieved.**
  *(why →* CR-SA82-NT-001, SA80.3a follow-up*)*

#### Finding — Pre-existing test expectation mismatch for operator-restore username under retained role (`why →` SA80.3b discovery)
When running the `backups` suite with `QS_BACKUPS_DB_USER=quickscale_test_role`, test `test_restore_file_mode_executes_pg_restore_for_operator_dump` (`test_services.py:2869`) fails because it hardcodes `--username postgres` in the expected `pg_restore` command, but `_build_pg_restore_command` reads the Django `DATABASES['default']['USER']` (which picks up the `QS_BACKUPS_DB_USER` env var). Under the default (`postgres`), the test passes. The test tolerates the default because `_set_postgresql_default_connection` does not monkeypatch USER. This is a minor test-isolation issue — the test should either set the expected username from env or mock the USER field to make the assertion env-independent. Not a regression from SA80.3 — `make test-integration` has the same env setting and would hit the same failure. Low severity; does not affect SA80.3b acceptance.

- [x] **SA87 — Make `test_restore_file_mode_executes_pg_restore_for_operator_dump` username-independent.** `Tier 1 · Track 3 · deps: none → completed 2026-07-13`
  Replaced the hardcoded `--username postgres` expectation with `connections["default"].settings_dict["USER"]`, so the assertion dynamically derives the expected database user from the active connection settings. Both suites confirmed: default-user mode 299 passed/2 skipped (0 failures); retained-role (`QS_BACKUPS_DB_USER=quickscale_test_role`) mode 299 passed/2 skipped (0 failures). The 2 skips are pre-existing and unchanged. Production behavior was already correct under both paths — this was purely a test-isolation fix. No blockers were found. The SA87 code change passed review with no code findings. Closes SA87.

  **CR-SA87-REV-001 (consistency finding):** Two stale audit current-status references were discovered during review — `tech-audit.md` §current-status still listed SA87 among open findings, and `arch-audit.md` enforcement-census row 2 still included SA87 in the open range SA83–SA87. Both were synchronized to reflect SA87 completion while preserving the historical SA87 entries at `tech-audit.md:319` (Reconciliation log) and `arch-audit.md:395–406` (Fix order and interactions). No blockers remain.
  *(why →* SA80.3b discovery, [CHANGELOG.md](../../CHANGELOG.md)*)*

#### Finding — Dead per-module `poetry.lock`/sibling-version constraints (`why →` discovered 2026-07-13 during a routine dependency-update pass)

- [ ] **SA81 — Remove the 8 unused per-module `poetry.lock` files and the sibling-module version-range constraints that never resolve standalone.** `Tier 1 · Track 3 · deps: none`
  While updating dependencies to their latest stable versions (2026-07-13), found that `quickscale_core`, `quickscale_cli`, and 8 of the 12 `quickscale_modules/*` packages (`auth`, `billing`, `blog`, `crm`, `forms`, `listings`, `orgs`, `storage`) each carry their own `poetry.lock`, alongside the root monorepo `poetry.lock` that every `make`/CI target actually installs from (root `pyproject.toml` wires every module in as `path = "...", develop = true`). Confirmed with the maintainer: standalone installation of an individual module outside the `quickscale` bundle is **not a supported use case** — modules are only meant to run interconnected via the `quickscale` CLI's bundle generation. That means these per-module lockfiles serve no purpose today:
  - 6 of the 8 (`auth`, `billing`, `blog`, `crm`, `listings`, `orgs`) can't even be re-locked standalone — their `pyproject.toml` declares sibling deps like `quickscale-module-orgs = ">=0.86.0,<0.87.0"` as plain version ranges with no `path =`, so `poetry lock` run from inside the module directory fails immediately with "doesn't match any versions" (there's nowhere to fetch an unpublished sibling package from). Their existing committed lockfiles don't even list those sibling packages, confirming this has been broken for a while, silently.
  - The other 4 modules (`notifications`, `analytics`, `backups`, `social`) never had a standalone lockfile at all — already inconsistent with the other 8, further evidence this was never a maintained/tested path.
  - Nothing in `.github/workflows/*.yml` or the `Makefile` ever `cd`s into a module directory and runs `poetry install`/`poetry lock` there — CI and `make test`/`make test-integration` install everything from the root lockfile only.

  *Acceptance:* delete the 8 per-module `poetry.lock` files (`quickscale_core`, `quickscale_cli`, `quickscale_modules/{auth,billing,blog,crm,forms,listings,orgs,storage}`); remove the sibling-module version-range dependency declarations from the 6 modules' `pyproject.toml` `[tool.poetry.dependencies]` that never resolve standalone (the real inter-module relationship is already expressed via the root `pyproject.toml` path deps and `quickscale_core`'s manifest/module-catalog system, so nothing else needs to encode it); confirm `make test`/`make test-integration`/CI are unaffected (they don't touch these files); note in each affected module's `poetry.toml` comment (already states "use root monorepo venv instead") that standalone lock/install is explicitly unsupported, to prevent the drift from recurring.
  *(why →* discovered while updating `mypy`, `posthog`, `django-anymail`, `django-filter` to latest stable in the root lockfile; maintainer confirmed standalone module installation is out of scope for this project*)*

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work (SA75, SA76) lives in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
