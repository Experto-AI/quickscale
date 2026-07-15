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

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active and blocked work.

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline for the remaining restricted-role cluster. Under it the only red remaining is **CRM (SA84)**; blog (SA83), forms (SA85), listings (SA86), orgs (SA77), and notifications (SA79) are all closed — see [CHANGELOG.md](../../CHANGELOG.md).

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, and `make ci` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`).

**Only the integration suite shards by module.** `scripts/test_integration.sh` loops `quickscale_modules/*` sequentially (one pytest stage per module, each with its own per-file 80% / mean 90% coverage floor). `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate (the parallelizable axis)

- [ ] **SA84 — CRM restricted-role fixtures (67 fail).** `Tier 2 · Track 1 · deps: none` — the one open per-module blocker; full brief in the SA84 ticket under Track 1 below. Gate line: `make MODULE=crm test -- --modules` → 0 failures at the 80%/90% floors, no quarantine entry.

  blog (SA83), forms (SA85), listings (SA86), orgs (SA77), notifications (SA79) are green under the SA82 baseline — see [CHANGELOG.md](../../CHANGELOG.md).

#### Repo-global gates (run once at v87 integration, after per-module work lands)

Assigned to **Track 2** (its module work — SA86, SA88b — is complete, so it owns the green-gate closeout). **GATE-lint and GATE-typecheck are done** (2026-07-15; see [CHANGELOG.md](../../CHANGELOG.md)); GATE-quality is the only remaining repo-global gate.

- [x] **GATE-lint** — `make lint` (Ruff) green. `Track 2`
- [x] **GATE-typecheck** — `make typecheck` (MyPy) green. `Track 2 · deps: none` — completed 2026-07-15.
  **Findings/blockers discovered:** After SA89b removed the backups-specific `mypy.ini` override, backups had 69 MyPy errors in 5 files: models.py (51 `var-annotated` + 7 `no-any-return`), migration 0003 (1 `no-untyped-def`), dr_adapter_call.py (1 `no-untyped-def`), services.py (4 `no-any-return`), admin.py (2 `attr-defined` + 3 `no-any-return`). While resolving these, an additional stale `unused-ignore` surfaced in dr_adapter_call.py (it was only visible after the baseline 69 errors cleared). All resolved without restoring a module-level MyPy suppression: models.py added a file-level `# mypy: disable-error-code="var-annotated"` (equivalent to the per-module ini setting other model-bearing modules commonly use, but per-file since the backups override was removed by the boundary-cleanup contract); `cast()` for `no-any-return` on Django field accesses; explicit parameter typing and ignore removals for the remaining minor errors. No blockers remain — `make typecheck` passes across all packages.
- [x] **GATE-check-suite** — `check-core-compat`, `check-module-core-imports`, `check-manifest-sync`, `check-org-context-primitives`, `check-csrf-exempt` all green. `Track 2`
  **Findings/blockers discovered:** None — all five gates passed clean on first run. All five gates were already green from prior SA implementation phases (check-core-compat from SA9.2, check-module-core-imports from SA9.6, check-manifest-sync from SA16.1, check-org-context-primitives from SA13.4, check-csrf-exempt from SA46). No script or source changes were needed to close GATE-check-suite; closeout was documentation-only.
- [ ] **GATE-quality** — `make quality` (vulture / radon / pylint) within agreed thresholds. `Track 2`

### Cross-cutting decision (re-based 2026-07-15) — eliminate the cross-org-migration class by squashing to a final-schema initial migration (arch-audit Finding 8)

SA84 and SA86 were originally framed as two instances of **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: RLS-context acquisition is procedural — cross-org *data migrations* and test fixtures must remember to acquire `operator_access`. The blanket BYPASSRLS hatch masked every omission until SA82 removed it.

**Decision re-based (2026-07-15) — drop backward compatibility; squash migrations.** The entire cross-org-*migration* half of Finding 8 is an artifact of **schema evolution**: `organization_id` was added to already-populated tables, so historical migrations (`crm/0006`, `crm/0009`, `forms/0007`) carry `_backfill_*_org` `RunPython` steps that walk existing rows and need elevated context. Since the project is **pre-launch with no deployed database to carry forward**, we squash every module's migrations to a single **final-schema `0001_initial`** where `organization_id` is `NOT NULL` from row zero. **There is then nothing to backfill → the cross-org-migration class is empty → the entire SA88 conformance-gate saga has no target and is deleted.** RLS policies (installed via `apply_force_rls` / `operator_access_rls`, not auto-generated) are manually re-attached to each squashed migration. This supersedes the seam-plus-gate approach (SA88/SA88a–e) below; the shared `operator_access_migration` helper becomes dead code and is retired (`apply_force_rls`/`revert_force_rls` stay).

**What this leaves.** The *fixture* half of Finding 8 survives untouched — squashing migrations does nothing to test fixtures. CRM triage confirmed the split: 67 failures bucket **0 migration / 67 fixture / 0 runtime-query** (test-posture; no production isolation bug). So **SA84 (CRM, 67) remains real work, but decouples from SA88 entirely** — it becomes "route cross-org test fixtures through the shared org-context helper under NOBYPASSRLS," with `deps: none`. SA86 (listings, 6) — the same fixture cleanup — is already done (Track 2; see [CHANGELOG.md](../../CHANGELOG.md)). The runtime RLS enforcement itself (SA59/SA82, PostgreSQL FORCE RLS under `quickscale_test_role`) is unchanged and load-bearing.

**Superseded work.** The seam baseline (69cabb47), the runtime-oracle pivot, and the SA88a–e static-analyzer line are all **obsoleted by the squash** — not merely superseded by a stronger proof, but rendered targetless. The gate file `test_sa88_migration_operator_access_conformance.py` (7,144 lines) is deleted; open findings **CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004** close as **obsoleted-by-schema-squash**. A tiny forward guardrail replaces the gate (see SA92). Historical detail in [CHANGELOG.md §SA88](../../CHANGELOG.md).

### Track 1 — Tenant-context surface

> **↪ HAND-OFF — SA92 (squash migrations) → SA84 (CRM fixtures).** Replaces the deleted SA88d/SA88e runtime-oracle line (see the re-based cross-cutting decision above). The self-contained brief:
> - **Work location:** Track 1 worktree `/home/victor/code/quickscale-wt-track1` (branch `wt-track1`). Run the roadmap start procedure (`git merge v87`) first. Commit checkpoints on `wt-track1`; **do not merge to `v87`** — the maintainer keeps the merge decision and the final independent review.
> - **Compat posture (ratified 2026-07-15):** no deployed database to carry forward. A clean `migrate` on a fresh DB is the only supported path; old migration history is discarded, not `--squash`-chained.
> - **Modules to squash:** `orgs`, `auth`, `blog`, `crm`, `forms`, `listings`, `billing`, `social`, `notifications`. Each collapses `0001..000N` into one final-schema `0001_initial`.
> - **RLS is NOT auto-generated — re-attach it by hand.** Each squashed migration must keep its `RunPython(apply_force_rls, <targets>)` (and for `orgs`: `operator_access_rls` + `operator_access_readonly`). Source the current live policy set from the existing `*_enable_rls` / `*_refresh_rls*` migrations; verify by diffing `pg_policies` before/after against `v87`.
> - **Drop:** all `_backfill_*_org` `RunPython` steps (crm `0006`/`0009`, forms `0007`) — a fresh DB has no rows to backfill. Retire `operator_access_migration` from `tenancy.py` once `forms/0007` is gone; **keep** `apply_force_rls`/`revert_force_rls`.
> - **Delete:** `quickscale_modules/orgs/tests/test_sa88_migration_operator_access_conformance.py` (7,144 lines) in full, plus any SA88 boundary-proof helpers. Replace with the ~30-line guardrail in SA92.
> - **Then SA84:** the CRM fixture failures are ContextVar (`set_current_org_id`) seeding under NOBYPASSRLS — untouched by the squash. Route cross-org fixtures through the shared org-context helper.

- [ ] **SA92 — Squash all module migrations to a final-schema initial migration; delete the SA88 gate saga.** `Tier 2 · Track 1 · deps: none`
  Collapse each module's migrations to one `0001_initial` at the final model state, with `organization_id NOT NULL` from creation. Manually re-attach each module's RLS `RunPython` (`apply_force_rls`, orgs `operator_access_rls`/`operator_access_readonly`); drop all `_backfill_*_org` steps. Delete `test_sa88_migration_operator_access_conformance.py` and retire the now-dead `operator_access_migration` helper. Add a **~30-line forward guardrail** unit test asserting no module migration contains cross-table org-id DML (`UPDATE ... SET organization_id` referencing another table), so the eliminated class cannot silently return.

  *Acceptance:* fresh `migrate` on an empty DB builds the identical schema **and identical RLS policy set** as `v87` (diff `pg_policies`); NOBYPASSRLS integration suite behaves as before the squash; guardrail test green; MyPy + orgs lint green; independent review confirms the RLS re-attachment is complete and no backfill logic was silently lost. Closes CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 as **obsoleted-by-schema-squash**.
  *(why →* arch-audit Finding 8; 2026-07-15 squash re-base*)*

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS fixture failures (plus 20 skipped).** `Tier 2 · Track 1 · deps: none (decoupled from SA88 by the squash)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). These are ContextVar-seeded fixtures failing under NOBYPASSRLS and are unaffected by SA92. Route each cross-org *fixture* through the shared org-context helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry.
  *(why →* CR-SA82-NT-003; arch-audit Finding 8 (fixture half)*)*

### Track 2 — Module contracts & settings

> **SA88b (forms diagnosis, SA88-QG-FORMS-001) — done 2026-07-14; detail in [CHANGELOG.md §SA88b](../../CHANGELOG.md).** Forms passed clean (196 passed / 8 skipped / 12 deselected / 0 failed); independent review closed SA88-QG-FORMS-001 as transient/environment-dependent, no product source changed. **SA86 — done 2026-07-15; detail in [CHANGELOG.md §SA86](../../CHANGELOG.md).** Listings restricted-role suite 134 passed/0 failed, 95.73% coverage, no quarantine. Track 2 module work is complete.

**Pending non-gating follow-up (Track 2):**

- [ ] **SA91 — Fork the per-module integration loop for true parallel execution.** `Tier 2 · Track 2 · deps: none`
  `scripts/test_integration.sh` runs module stages serially (loop at `:414–442`). Fork each module's pytest stage and join exit codes + coverage. Contention points to resolve: the shared `COVERAGE_RESULTS_FILE` mktemp (`:57`) must become per-module and be merged before `check_overall_mean_coverage`; the per-module `QS_*_DB_USER` role setup (`:375–386`) and pre-created test databases must not collide across concurrent workers. CI-time speedup only — not a gate for the green-gate milestone.

  *Acceptance:* parallel run produces the identical pass/fail verdict and the identical overall-mean coverage as the serial run; no cross-worker DB collision under the restricted role.
  *(why →* parallelize testing by module*)*

### Track 3 — Core/CLI plumbing (complete)

> **Track 3 is complete.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed: SA89a (persistence protocol in `core` + `restore_admin_uploaded_backup` port, done 2026-07-14) and SA89b (orchestration port closeout — declarative reverse import ban + modules-absent runtime proof, custom boundary scanner deleted, done 2026-07-15). Detail in [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92 — squash migrations +          module work ✓ DONE (SA86, SA88b)        ✓ COMPLETE
  delete SA88 gate saga                 │                                     SA89a + SA89b (Finding 1)
  deps: none                            ▼
      │                             Green-gate closeout (remaining):
      ▼                               GATE-quality
SA84 — CRM (67 fixtures)              SA91 — parallel integration loop (non-gating; CI speedup only)
  deps: none                          deps: none  (GATE-lint / GATE-typecheck / GATE-check-suite ✓ DONE)
  │  (per-module gate)
  Track 1                            Track 2                               Track 3
```

**Ordering.** The squash (SA92) eliminates the cross-org-migration class, so the SA88 gate saga (SA88a–e) is deleted, not completed. SA84 survived as a **fixture** cleanup. Track 1 runs SA92 → SA84. Track 2 (module work complete) owns the repo-global closeout. Track 3 is complete.

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join: the per-module gate (SA84, Track 1) plus the repo-global gates must all land on `v87`. GATE-typecheck's former wait on SA89b is satisfied (the backups `mypy.ini` ignore is already removed on `v87`). Track 2, having finished its module work, owns the closeout: GATE-lint, GATE-typecheck, and GATE-check-suite are complete; GATE-quality remains pending. SA91 is a separate pending non-gating optimization follow-up — CI-time speedup only, not a gate for green.

### Track readiness (2026-07-15)

- **Track 1 — READY, clean to continue (SA92, deps: none).** The squash-and-drop-backward-compat decision (see cross-cutting decision above) makes the whole cross-org-migration problem disappear: no static analyzer, no runtime boundary proofs, no gate. The decision is already ratified, so no maintainer decision is pending. SA92 is fresh, dependency-free work; SA84 follows it and is unblocked by it. The retired SA88a–e findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) close as obsoleted-by-schema-squash.
- **Track 2 — module work complete; owns green-gate closeout.** SA88b and SA86 are both done (listings restricted-role suite passes clean, 134 passed/0 failed, no quarantine entry). With its module work finished, Track 2 now owns the green-gate closeout: GATE-lint, GATE-typecheck, and GATE-check-suite are complete; GATE-quality remains pending. SA91 is a separate pending non-gating optimization follow-up — CI-time speedup only, not a gate for green.
- **Track 3 — COMPLETE.** SA89a + SA89b done (2026-07-15); Finding 1 (DR persistence port) closed. No open Track-3 work; **SA89B-CR-004 (low/advisory)** remains against `check_module_core_compatibility.py` independently, not gating.

**No track is blocked. No maintainer decision is pending** — the squash re-base and the SA89b descope were both ratified on 2026-07-15.

**Decision (ratified 2026-07-15) — Track 1: squash migrations, delete the SA88 gate saga.** After the static-analyzer line and its runtime-oracle successor both proved to be chasing an artifact of schema evolution, the maintainer confirmed (no deployed DB to preserve) that squashing every module to a final-schema `0001_initial` eliminates the cross-org-*migration* class outright. **Why:** the backfills only exist because `organization_id` was added to populated tables; a fresh schema has no rows to backfill, so there is no invariant left to gate. RLS enforcement (SA59/SA82) is unchanged; the *fixture* failures (SA84) are a separate, ContextVar-level concern the squash does not touch. **Sub-decisions:** (1) squash-and-drop-compat over continue-oracle; (2) manually re-attach RLS `RunPython` to the squashed migrations (not auto-generated); (3) keep a ~30-line forward guardrail against reintroducing cross-org migration DML. This supersedes every SA88 decision — the SA88a–e static-analyzer line and its runtime-oracle successor (SA88d/e) are all obsoleted-by-squash; their full reasoning trail is preserved in [CHANGELOG.md §SA88](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
