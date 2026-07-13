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
> ### Merge checkpoint: CR-TRACK3-MERGE-002 (medium · blocking · open)
>
> User explicitly accepted merging Track 3 into v87 with this medium blocking finding open. This checkpoint records what is done, what remains blocking, and what evidence/decision is needed.
>
> **Done:**
> - SA81 implementation, review, and validation completed 2026-07-13 (see ✓ checked entry below).
> - SA81 roadmap conflict structurally resolved by preserving incoming v87 content and adding this checkpoint.
>
> **Blocking (current audit prose overstates shared Finding 8 / `operator_access` causality):**
> The incoming v87 arch-audit.md and tech-audit.md (restored to index exactly) describe Finding 8 as a shared structural root for SA83–SA86, with `operator_access` as a candidate shared hypothesis. This overstates what the evidence supports — see the evidence/decision table below.
>
> **Evidence and decisions needed before closing:**
>
> | Dimension | Current incoming prose | Evidence-calibrated statement | Decision |
> |-----------|-----------------------|------------------------------|----------|
> | SA83 root cause | Bundled under Finding 8 shared diagnosis | **AF9 priming-memo staleness only** — 211 passed/0 failed in isolation, fix WIP in wt-track1. Blog's own `operator_access` migration gap is a separate latent concern, not the cause of SA83's 86 gate failures. | Accept SA83 as independent; do not fold into Finding 8 shared diagnosis. |
> | SA84–SA86 relationship | Described as one shared structural root | **Separately bucketed** — SA84 (CRM, `operator_access` candidate), SA85 (forms, `operator_access` already present via SA79, root unknown), SA86 (listings, `operator_access` candidate). No evidence they share one root. | Treat each as independent investigation with its own diagnosis step. |
> | `operator_access` as Finding 8 remedy | Described as the implied shared fix | `operator_access` is a candidate hypothesis for SA84/SA86 only (not SA85, which already has it). Not a shared diagnosis or fix for all four. | Confirm per-module before prescribing a shared mechanism. |
> | Finding 8 scope | Described as an active gate diagnosis | Finding 8 is a **latent census concern** (procedural RLS-context acquisition) unless bucket-triaging confirms a runtime read path that would bite production. Currently it describes the structural pattern, not a confirmed defect class for any specific module. | Maintain Finding 8 as structural observation only; promote if bucket-3 evidence emerges. |
>
> **Preserved:** All historical audit logs, reconciliation entries, and per-pass finding records in both arch-audit.md and tech-audit.md remain intact — only the `current audit prose` (top-of-file orientation, Finding 8 recommendation, and current-status blocks) carry the overstated causality. Historical passes correctly recorded their own evidence-calibrated language.
>
> **Acceptance:** Merge proceeds with this checkpoint — CR-TRACK3-MERGE-002 remains medium/blocking/open. The audit files are restored to their incoming v87 state; no reconciliation edits are applied to them. This roadmap entry is the sole record of the blocker.
>
> > **Track readiness (2026-07-13, updated):** SA82 (Track 3) completed — the SA76 `orgs`/`notifications` quarantine entries are removed; the full `make test-integration` gate ran with both suites unquarantined (exit 1, as expected: orgs 847 passed/11 BYPASSRLS-skips/0 failed, notifications 39 passed/0 failed, overall mean coverage 92.95% passed). SA77 and SA79 closed by this result — their acceptance conditions are met. The repository integration gate remains red due to separate independent restricted-role findings (SA83–SA86) that do not affect SA77/SA79 closure.
> - **Track 1** — unblocked from SA82 (SA77 closed); open findings SA83 (blog) and SA84 (CRM, 67 RLS failures/20 skipped) recorded below. SA83 is **root-caused (AF9 priming-memo staleness) with an in-progress uncommitted fix in wt-track1** — blog now 211 passed/0 failures in isolation under the restricted role; still to commit, merge v87, and confirm under the full gate. SA84 remains a separate restricted-role residual, not a blocker for SA77 closure.
> - **Track 2** — unblocked from SA82 (SA79 closed); its own acceptance conditions (forms 0007 backfill + unquarantined notifications under the full gate) are satisfied. Reassigned 2026-07-13 from Track 1 (parallelization): SA85 (forms, 33 RLS failures/8 skipped/10 errors) and SA86 (listings, 6 RLS failures), both open, no deps.
> - **Track 3** — SA80 (venv + retained-role env wiring) done; SA82 (gate rerun) completed; SA80.3a (pg_dump install) done 2026-07-13; SA80.3b (backups suite rerun) completed 2026-07-13; SA81 (no deps) completed 2026-07-13; SA87 (username-independent restore test) completed 2026-07-13.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — done (SA82, 2026-07-13)         SA79 — done (SA82, 2026-07-13)            SA80 — done (2026-07-13)
  orgs 847p/11 BYPASSRLS-skips/0f        notifications 39p/0f;                     SA82 — done (2026-07-13)
  code fix verified live under gate      forms 0007 acceptance verified            SA80.3a — done (2026-07-13)
SA83 — blog: root-caused; fix WIP        SA85 — forms residual (33 RLS             SA80.3b (backups rerun)
  in wt-track1: 211p/0f in isolation       failures/8 skipped/10 errors)             done (2026-07-13)
SA84 — CRM (67 RLS failures/20             open, no deps, unknown root             SA81 — done (2026-07-13)
  skipped) open, no deps, unknown          cause (reassigned from Track 1,          SA87 — username-independent
  root cause                               2026-07-13)                                restore test
                                                                                        done (2026-07-13)
                                           SA86 — listings (6 RLS failures)
                                             open, no deps, unknown root
                                             cause (reassigned from Track 1,
                                             2026-07-13)
```


SA82 (Track 3) completed 2026-07-13 — the `orgs`/`notifications` quarantine entries are removed; the full gate rerun confirmed orgs (847 passed/11 BYPASSRLS-skips/0 failed) and notifications (39 passed/0 failed) clean. SA77 and SA79 are closed by this result. Track 1 is unblocked from SA82 with SA83–SA84 open; Track 2 is unblocked from SA82 with SA85–SA86 open (reassigned from Track 1, 2026-07-13, to parallelize the four independent restricted-role residuals). The integration gate remains red due to separate independent restricted-role findings (SA83–SA86) recorded below. (SA81 is unrelated cleanup — per-module lockfile removal — and does not affect the gate.)

### Track 1 — Tenant-context surface

SA59 (umbrella, SA59.1–SA59.4) closed 2026-07-12 — see CHANGELOG.md. SA77 closed 2026-07-13 by SA82 — see below and CHANGELOG.md. Two independent restricted-role residuals in blog and CRM are recorded as SA83–SA84 below; the forms and listings residuals (SA85–SA86) were reassigned to Track 2 on 2026-07-13 to parallelize the four findings across both tracks.

- [x] **SA77 — Root-cause and fix orgs' restricted-role test failures.** `Tier 1 · Track 1 · deps: none → closed 2026-07-13`
  Code fix landed 2026-07-12 — full root-cause and fix detail (psycopg2→`connection.cursor()` conversion in two test helpers; 6 dynamic-DDL tests marked `@pytest.mark.bypass_rls`) is in [CHANGELOG.md](../../CHANGELOG.md)'s SA77 entry, not repeated here.

  *Acceptance:* the 3 helper-path restricted-role tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the 6 dynamic-DDL tests skip in restricted mode. The `scripts/test_integration.sh` quarantine entry was removed in SA82. The full `make test-integration` gate run (2026-07-13) confirmed orgs 847 passed/11 BYPASSRLS-skips/0 failed, 93.04% coverage. SA77 closed.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — Blog restricted-role RLS failures (`why →` CR-SA82-NT-002; discovered during SA82 full-gate rerun)

- [ ] **SA83 — Investigate and fix blog's 86 restricted-role RLS failures.** `Tier 1 · Track 1 · deps: none → root-caused; fix in progress (uncommitted) in wt-track1, 2026-07-13`
  Under the SA82 full `make test-integration` gate run with quarantine entries removed, blog's restricted-role suite showed 121 passed, 86 RLS failures.

  **Root cause identified (2026-07-13):** AF9 priming-**memo staleness**. The AF9 execute wrapper (`orgs/current_org.py`) primes `app.current_org_id` from the ContextVar and memoizes the primed value per transaction (`_af9_primed_for_txn`) to skip redundant `SET LOCAL`s. When a direct GUC mutator (`_set_db_current_org_id`, `reset_db_current_org_id`, `_restore_current_org_id`) changed the GUC out-of-band while the ContextVar was unchanged, the stale memo made the wrapper *skip* re-priming — leaving the DB GUC desynchronized from the ContextVar, so the next tenant query ran under the wrong (or empty) org context and tripped FORCE-RLS.

  **Fix in progress (uncommitted, wt-track1):** added `_clear_priming_memo(connection)` and call it from all three direct GUC mutators so the next wrapped statement re-primes unconditionally; added 3 orgs regression tests (`test_direct_set_b_clears_memo`, `test_reset_clears_memo`, `test_restore_b_clears_memo` in `test_af9_priming.py`) plus blog test/view updates.

  **Verification so far:** blog's restricted-role suite runs clean in isolation — `QS_BLOG_DB_USER=quickscale_test_role QUICKSCALE_ALLOW_BYPASSRLS=0 make MODULE=blog test -- --modules` → **211 passed, 0 failures** (was 121 passed / 86 failures). `quickscale_test_role` confirmed `NOBYPASSRLS`, so this is a true restricted-role pass.

  **Remaining to close:** commit the wt-track1 work, `git merge v87`, confirm the orgs `test_af9_priming.py` regression tests pass under the restricted role, then confirm blog clean under the full `make test-integration` gate, and merge back to v87.

  *Acceptance:* blog's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-002*)*

#### Finding — CRM restricted-role RLS failures (`why →` CR-SA82-NT-003; discovered during SA82 full-gate rerun)

- [ ] **SA84 — Investigate and fix CRM's 67 restricted-role RLS failures (plus 20 skipped).** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate run, CRM's restricted-role suite showed 195 passed, 67 RLS failures, 20 skipped. Root cause is unknown/unconfirmed — RLS policy violations under `quickscale_test_role`.

  *Acceptance:* CRM's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-003*)*

### Track 2 — Module contracts & settings

SA79 closed 2026-07-13 by SA82 — see below and CHANGELOG.md. SA85 and SA86 reassigned here from Track 1 on 2026-07-13 to parallelize the four independent restricted-role residuals surfaced by SA82.

- [x] **SA79 — Closeout verification/reconciliation.** `Tier 1 · Track 2 · deps: none → closed 2026-07-13`

  The full `make test-integration` gate run (SA82, 2026-07-13) confirmed notifications 39 passed/0 failed, 91.76% coverage — unquarantined, clean. Forms 0007 backfill acceptance verified under the full retained-role environment with the BYPASSRLS hatch closed and quarantine entries removed.

  SA80 (Track 3) resolved the local env gaps; SA82 removed the quarantine entries and confirmed both acceptance conditions under `make test-integration` itself rather than a narrower direct-pytest rerun. Audit/status docs refreshed in this pass.

  *Acceptance:* forms 0007 backfill passes under full retained-role env; notifications suite runs clean (unquarantined) under a full `make test-integration` gate run; audit/status docs reflect current state. **Achieved.** SA79 closed.

#### Finding — Forms residual restricted-role test failures (`why →` CR-SA82-NT-004; discovered during SA82 full-gate rerun)

- [ ] **SA85 — Investigate and fix forms' residual restricted-role test failures.** `Tier 1 · Track 2 · deps: none` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 full `make test-integration` gate run, forms' restricted-role suite showed 140 passed, 33 RLS failures, 8 skipped, 10 errors. Root cause is unknown/unconfirmed — RLS policy violations and test-structural errors under `quickscale_test_role`.

  *Acceptance:* forms' restricted-role suite passes clean (0 failures, 0 errors) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-004*)*

#### Finding — Listings restricted-role RLS failures (`why →` CR-SA82-NT-005; discovered during SA82 full-gate rerun)

- [ ] **SA86 — Investigate and fix listings' 6 restricted-role RLS failures.** `Tier 1 · Track 2 · deps: none` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 full `make test-integration` gate run, listings' restricted-role suite showed 128 passed, 6 RLS failures. Root cause is unknown/unconfirmed — RLS policy violations under `quickscale_test_role`.

  *Acceptance:* listings' restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-005*)*

### Track 3 — Core/CLI plumbing

SA80 closed 2026-07-13 (venv re-provision + retained-role env wiring) — see CHANGELOG.md. SA82 completed 2026-07-13. SA80.3a closed 2026-07-13. SA80.3b completed 2026-07-13. SA81 (no deps) completed 2026-07-13. SA87 (username-independent restore test) completed 2026-07-13.

- [x] **SA82 — Remove the SA76 `orgs`/`notifications` quarantine entries and rerun the full `make test-integration` gate to prove SA77/SA79 clean.** `Tier 1 · Track 3 · deps: none → completed 2026-07-13`

  Removed `orgs` and `notifications` from `QUARANTINE_TICKETS` in `scripts/test_integration.sh` (passed `bash -n` syntax check). Ran `make test-integration` end-to-end — exit 1 (expected: separate findings remain). Target evidence: orgs 847 passed/11 BYPASSRLS-skips/0 failed, 93.04% coverage; notifications 39 passed/0 failed, 91.76% coverage. Overall mean coverage 92.95% passed.

  SA77 closed and SA79 closed by this result — their acceptance conditions are met under the full unquarantined gate. The four independent restricted-role findings surfaced by removing the quarantine are recorded as SA83 (blog, 86 RLS failures) and SA84 (CRM, 67 RLS failures/20 skipped) in Track 1 above, and SA85 (forms, 33 RLS failures/8 skipped/10 errors) and SA86 (listings, 6 RLS failures) in Track 2 (reassigned 2026-07-13 to parallelize) — SA83 root-caused (see Track 1 above), SA84–SA86 open with no deps and unknown root cause. Backups was tracked by SA80.3b — resolved 2026-07-13 (see below).

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

- [x] **SA81 — Remove stale per-module `poetry.lock` files and sibling-module version-range constraints that never resolve standalone.** `Tier 1 · Track 3 · deps: none → completed 2026-07-13`
  2026-07-13 implementation: Cross-checked the per-module `poetry.lock` inventory against the current worktree (branch `wt-track3`, HEAD 41689be7). **4** non-root lock artifacts were present (all already gitignored): `quickscale_core/poetry.lock`, `quickscale_cli/poetry.lock`, `quickscale_modules/orgs/poetry.lock`, `quickscale_modules/backups/poetry.lock`. The original discovery named 11 possible lockfile locations across core, CLI, and all modules; the remaining 7 (`auth`, `billing`, `blog`, `crm`, `forms`, `listings`, `storage`) were already absent from the worktree — previously deleted or never present in this track; the `.gitignore` patterns `quickscale_core/poetry.lock`, `quickscale_cli/poetry.lock`, and `quickscale_modules/*/poetry.lock` (lines 38–40) already cover all non-root lockfile locations. All 4 present lock artifacts deleted. Root `poetry.lock` preserved.

  Sibling-constraint inventory verified against all 12 `quickscale_modules/*/pyproject.toml`: **7** plain version-range sibling dependencies existed and were removed from `[tool.poetry.dependencies]`:
  - `auth` → `quickscale-module-orgs = ">=0.86.0,<0.87.0"`
  - `billing` → `quickscale-module-orgs = ">=0.86.0,<0.87.0"`
  - `blog` → `quickscale-module-orgs = ">=0.86.0,<0.87.0"`
  - `crm` → `quickscale-module-orgs = ">=0.86.0,<0.87.0"`
  - `listings` → `quickscale-module-orgs = ">=0.86.0,<0.87.0"`
  - `orgs` → `quickscale-module-auth = ">=0.71.0,<0.87.0"`
  - `social` → `quickscale-module-orgs = ">=0.86.0,<0.87.0"`

  Poetry local-guidance audit: 5 modules had existing `poetry.toml` files (`auth`, `blog`, `crm`, `forms`, `listings`); 2 of those (`crm`, `forms`) lacked the monorepo-venv comment. Created or updated `poetry.toml` for all 8 modules affected by this cleanup (`auth`, `backups`, `billing`, `blog`, `crm`, `listings`, `orgs`, `social`) to explicitly state that standalone lock/install is unsupported and the root monorepo environment must be used. 5 modules (`backups`, `billing`, `crm`, `orgs`, `social`) had their `poetry.toml` created or rewritten from scratch; 3 modules (`auth`, `blog`, `listings`) had existing but less explicit virtualenv-only guidance updated to the same standalone-unsupported wording. `forms` has a `poetry.toml` but was not directly affected by this cleanup (no lock deleted, no constraint removed); its guidance was not updated — it remains as-is, using a terser `[virtualenvs] in-project = true; create = false` form. `analytics`, `notifications`, `storage`, and `teams` never had locks or sibling constraints and were not affected.

  Validation: `poetry check --lock` returns `All set!`; `make test-unit` passes. CI workflows never `cd` into module directories for `poetry install`/`poetry lock` — no CI impact.

  **Review findings (CR-SA81-REV-001–004):** The implementation pass correctly deleted the 4 present lockfiles and removed the 7 sibling constraints from pyproject.toml files, but review identified four follow‑up items: (1) the root `poetry.lock` still carried the seven sibling dependency edges and needed regeneration; (2) exact test coverage for two required‑modules relationships (auth→orgs, orgs→auth) and lock‑level assertions was missing; (3) roadmap status, lock‑count wording, and CHANGELOG track ownership were inconsistent; (4) `decisions.md` and `development.md` contained contradictory package‑lock and poetry.toml inventory claims. All four are addressed in the SA81 follow‑up pass.

  *Acceptance:* 4 present ignored locks deleted; 7 sibling version constraints removed; `poetry.toml` guidance for affected modules states standalone lock/install is unsupported; `poetry check --lock && make test-unit` pass. **Achieved.** SA81 closed.
  *(why →* discovered 2026-07-13 during a routine dependency-update pass; [CHANGELOG.md](../../CHANGELOG.md)*)*

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work (SA75, SA76) lives in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
