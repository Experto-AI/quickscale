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

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA90 squash), `make check`, `make quality`, and `make ci` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`).

**Only the integration suite shards by module.** `scripts/test_integration.sh` loops `quickscale_modules/*` sequentially (one pytest stage per module, each with its own per-file 80% / mean 90% coverage floor). `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate (the parallelizable axis)

- [ ] **SA84 — CRM restricted-role fixtures (67 fail).** `Tier 2 · Track 1 · deps: none` — the one open per-module blocker; full brief in the SA84 ticket under Track 1 below. Gate line: `make MODULE=crm test -- --modules` → 0 failures at the 80%/90% floors, no quarantine entry.
- [x] blog (SA83) · forms (SA85) · listings (SA86) · orgs (SA77) · notifications (SA79) — green under the SA82 baseline (see [CHANGELOG.md](../../CHANGELOG.md)).

#### Repo-global gates (run once at v87 integration, after per-module work lands)

Assigned to **Track 2** (its module work — SA86, SA88b — is complete, so it owns the green-gate closeout). GATE-typecheck coordinates with Track 3 (SA89b).

- [x] **GATE-lint** — `make lint` (Ruff) green. `Track 2`
- [ ] **GATE-typecheck** — `make typecheck` (MyPy) green. `Track 2 · deps: SA89b (Track 3)` — blocked on SA89b removing the `mypy.ini:94` backups ignore; until then MyPy passes only on a suppressed baseline, so this gate is not truly green.
- [ ] **GATE-check-suite** — `check-core-compat`, `check-module-core-imports`, `check-manifest-sync`, `check-org-context-primitives`, `check-csrf-exempt` all green. `Track 2`
- [ ] **GATE-quality** — `make quality` (vulture / radon / pylint) within agreed thresholds. `Track 2`

- [ ] **SA91 — Fork the per-module integration loop for true parallel execution.** `Tier 2 · Track 2 · deps: none`
  `scripts/test_integration.sh` runs module stages serially (loop at `:414–442`). Fork each module's pytest stage and join exit codes + coverage. Contention points to resolve: the shared `COVERAGE_RESULTS_FILE` mktemp (`:57`) must become per-module and be merged before `check_overall_mean_coverage`; the per-module `QS_*_DB_USER` role setup (`:375–386`) and pre-created test databases must not collide across concurrent workers. Kept separate from the SA84 correctness work — this is CI-time speedup only, not a gate for green.

  *Acceptance:* parallel run produces the identical pass/fail verdict and the identical overall-mean coverage as the serial run; no cross-worker DB collision under the restricted role.
  *(why →* green-gate milestone; parallelize testing by module*)*

### Cross-cutting decision (re-based 2026-07-15) — eliminate the cross-org-migration class by squashing to a final-schema initial migration (arch-audit Finding 8)

SA84 and SA86 were originally framed as two instances of **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: RLS-context acquisition is procedural — cross-org *data migrations* and test fixtures must remember to acquire `operator_access`. The blanket BYPASSRLS hatch masked every omission until SA82 removed it.

**Decision re-based (2026-07-15) — drop backward compatibility; squash migrations.** The entire cross-org-*migration* half of Finding 8 is an artifact of **schema evolution**: `organization_id` was added to already-populated tables, so historical migrations (`crm/0006`, `crm/0009`, `forms/0007`) carry `_backfill_*_org` `RunPython` steps that walk existing rows and need elevated context. Since the project is **pre-launch with no deployed database to carry forward**, we squash every module's migrations to a single **final-schema `0001_initial`** where `organization_id` is `NOT NULL` from row zero. **There is then nothing to backfill → the cross-org-migration class is empty → the entire SA88 conformance-gate saga has no target and is deleted.** RLS policies (installed via `apply_force_rls` / `operator_access_rls`, not auto-generated) are manually re-attached to each squashed migration. This supersedes the seam-plus-gate approach (SA88/SA88a–e) below; the shared `operator_access_migration` helper becomes dead code and is retired (`apply_force_rls`/`revert_force_rls` stay).

**What this leaves.** The *fixture* half of Finding 8 survives untouched — squashing migrations does nothing to test fixtures. CRM triage confirmed the split: 67 failures bucket **0 migration / 67 fixture / 0 runtime-query** (test-posture; no production isolation bug). So **SA84 (CRM, 67) and SA86 (listings, 6) remain real work, but decouple from SA88 entirely** — they become "route cross-org test fixtures through the shared org-context helper under NOBYPASSRLS," with `deps: none`. The runtime RLS enforcement itself (SA59/SA82, PostgreSQL FORCE RLS under `quickscale_test_role`) is unchanged and load-bearing.

**Superseded work.** The seam baseline (69cabb47), the runtime-oracle pivot, and the SA88a–e static-analyzer line are all **obsoleted by the squash** — not merely superseded by a stronger proof, but rendered targetless. The gate file `test_sa88_migration_operator_access_conformance.py` (7,144 lines) is deleted; open findings **CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004** close as **obsoleted-by-schema-squash**. A tiny forward guardrail replaces the gate (see SA90). Historical detail in [CHANGELOG.md §SA88](../../CHANGELOG.md).

### Track 1 — Tenant-context surface

> **↪ HAND-OFF — SA90 (squash migrations) → SA84 (CRM fixtures).** Replaces the deleted SA88d/SA88e runtime-oracle line (see the re-based cross-cutting decision above). The self-contained brief:
> - **Work location:** Track 1 worktree `/home/victor/code/quickscale-wt-track1` (branch `wt-track1`). Run the roadmap start procedure (`git merge v87`) first. Commit checkpoints on `wt-track1`; **do not merge to `v87`** — the maintainer keeps the merge decision and the final independent review.
> - **Compat posture (ratified 2026-07-15):** no deployed database to carry forward. A clean `migrate` on a fresh DB is the only supported path; old migration history is discarded, not `--squash`-chained.
> - **Modules to squash:** `orgs`, `auth`, `blog`, `crm`, `forms`, `listings`, `billing`, `social`, `notifications`. Each collapses `0001..000N` into one final-schema `0001_initial`.
> - **RLS is NOT auto-generated — re-attach it by hand.** Each squashed migration must keep its `RunPython(apply_force_rls, <targets>)` (and for `orgs`: `operator_access_rls` + `operator_access_readonly`). Source the current live policy set from the existing `*_enable_rls` / `*_refresh_rls*` migrations; verify by diffing `pg_policies` before/after against `v87`.
> - **Drop:** all `_backfill_*_org` `RunPython` steps (crm `0006`/`0009`, forms `0007`) — a fresh DB has no rows to backfill. Retire `operator_access_migration` from `tenancy.py` once `forms/0007` is gone; **keep** `apply_force_rls`/`revert_force_rls`.
> - **Delete:** `quickscale_modules/orgs/tests/test_sa88_migration_operator_access_conformance.py` (7,144 lines) in full, plus any SA88 boundary-proof helpers. Replace with the ~30-line guardrail in SA90.
> - **Then SA84:** the CRM fixture failures are ContextVar (`set_current_org_id`) seeding under NOBYPASSRLS — untouched by the squash. Route cross-org fixtures through the shared org-context helper.

- [ ] **SA90 — Squash all module migrations to a final-schema initial migration; delete the SA88 gate saga.** `Tier 2 · Track 1 · deps: none`
  Collapse each module's migrations to one `0001_initial` at the final model state, with `organization_id NOT NULL` from creation. Manually re-attach each module's RLS `RunPython` (`apply_force_rls`, orgs `operator_access_rls`/`operator_access_readonly`); drop all `_backfill_*_org` steps. Delete `test_sa88_migration_operator_access_conformance.py` and retire the now-dead `operator_access_migration` helper. Add a **~30-line forward guardrail** unit test asserting no module migration contains cross-table org-id DML (`UPDATE ... SET organization_id` referencing another table), so the eliminated class cannot silently return.

  *Acceptance:* fresh `migrate` on an empty DB builds the identical schema **and identical RLS policy set** as `v87` (diff `pg_policies`); NOBYPASSRLS integration suite behaves as before the squash; guardrail test green; MyPy + orgs lint green; independent review confirms the RLS re-attachment is complete and no backfill logic was silently lost. Closes CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 as **obsoleted-by-schema-squash**.
  *(why →* arch-audit Finding 8; 2026-07-15 squash re-base*)*

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS fixture failures (plus 20 skipped).** `Tier 2 · Track 1 · deps: none (decoupled from SA88 by the squash)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). These are ContextVar-seeded fixtures failing under NOBYPASSRLS and are unaffected by SA90. Route each cross-org *fixture* through the shared org-context helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry.
  *(why →* CR-SA82-NT-003; arch-audit Finding 8 (fixture half)*)*

### Track 2 — Module contracts & settings

> **SA88b (forms diagnosis, SA88-QG-FORMS-001) — done 2026-07-14; detail in [CHANGELOG.md §SA88b](../../CHANGELOG.md).** Forms passed clean (196 passed / 8 skipped / 12 deselected / 0 failed); independent review closed SA88-QG-FORMS-001 as transient/environment-dependent, no product source changed. **SA86 — done 2026-07-15; detail in [CHANGELOG.md §SA86](../../CHANGELOG.md).** Listings restricted-role suite 134 passed/0 failed, 95.73% coverage, no quarantine. Track 2 is complete.

- [x] **SA86 — Fix listings' 6 restricted-role RLS fixture failures.** `Tier 1 · Track 2 · deps: none (decoupled from SA88 by the squash)` *(completed 2026-07-15)*
  All six original errors were fixture-time INSERT RLS failures under `quickscale_test_role`. Routed each cross-org fixture through the shared `org_scope` helper, which primes the `app.current_org_id` GUC for FORCE RLS (same pattern as SA83/SA85). The fix revealed one intentional cross-tenant `all_objects` admin query that required explicit `operator_access()` — not a production isolation defect. No production source isolation defect was found; all six were test-posture only (Finding 8 fixture half).

  *Acceptance:* focused restricted-role suite 134 passed/0 failed; full `make test-integration` listings stage 134 passed/0 failed at 95.73% coverage; no listings quarantine entry. The only full-gate blocker remains out-of-scope CRM SA84 (67 failures), not an SA86 blocker. Closes SA86.
  *(why →* CR-SA82-NT-005; arch-audit Finding 8 (fixture half)*)*

### Track 3 — Core/CLI plumbing

arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) — **activated 2026-07-14** to use idle Track 3 capacity. Independent of the SA88/SA84/SA86 cluster. Pre-split into two Tier 2 sub-tickets (the whole is Tier 3):

> **SA89a (persistence protocol in `core` + `restore_admin_uploaded_backup` port) — done 2026-07-14; detail in [CHANGELOG.md §SA89a](../../CHANGELOG.md).** Core persistence contracts, fail-hard registry, runtime-facade wiring, backups `ready()` injection, and the SA54-seam port all landed; 64 core persistence + 24 backups + 2125 core unit + 320 backups tests, Ruff/MyPy green, 92.73% coverage; advisory CR-SA89A-ADV-001 resolved; independent review STATUS ok.

- [ ] **SA89b — Migrate the remaining DR orchestration model-access onto the injected persistence.** `Tier 2 · Track 3 · deps: SA89a · status: blocked checkpoint (2026-07-15)`
  Remove the `orchestration.py:80` core→module import, the `_LAZY_*` tables, and the `mypy.ini:94` backups ignore.

  **Blocked checkpoint (2026-07-15; maintainer-selected stop-and-merge at the review cap):**
  - **Done:** the remaining orchestration model access is routed through fail-hard injected persistence; the direct core→backups import, DR `_LAZY_*` tables, and backups-specific MyPy ignore are removed; runtime/provider caller parity and the root-private streaming S3 adapter landed and validated. The boundary scanner now traverses intervening control-flow, separates ordinary nested functions/classes from parent attribution, and carries 32 passing focused tests plus green changed-file lint/MyPy and 2,295 passing core tests / 1 pre-existing skip. These are incremental scanner improvements, not a clean-gate or completion claim. Detail in [CHANGELOG.md §SA89b](../../CHANGELOG.md).
  - **Pending/Blocking:** **SA89B-CR-001 (medium/blocking)** remains open. The scanner does not yet assign every call to its nearest lexical owner: nested lambdas can be omitted or leaked into an outer lambda, non-`Name` receivers are ignored, and function/class decorators and default expressions are skipped. The direct `if`/`for` assertions also do not prove the expected diagnostic form or exact-once analysis. Required continuation: an owner-aware scope visitor plus exact diagnostic-count regressions for nested lambdas, non-`Name` receivers, definition-time expressions, and direct control flow. The SA89b checkbox stays unchecked.
  - **Resolved this checkpoint:** **SA89B-DOC-001 (medium/blocking)** — independent checkpoint review confirmed the roadmap/changelog no longer overclaim scanner completeness and are safe to merge as blocked status.
  - **Decisions needed:** none. At `review_cycles=2`, with blocker count unchanged at two medium findings, the maintainer selected **stop, record this truthful blocked checkpoint, and merge**. A future continuation must retain the finding IDs and pass fresh validation and independent review before completion.
  - **Advisory:** **SA89B-CR-004 (low/advisory)** remains open: the module-core compatibility checker can chase a submodule alias without proving matching parent `__getattr__` delegation.
  - **Coverage note:** The final focused boundary suite passed 32/32 and the core suite passed 2,295 tests / 1 pre-existing skip. Repository-wide command reds observed in this pass remain unrelated baseline issues: backups MyPy errors, aggregate core coverage below the configured 90%, and the local BYPASSRLS integration-role constraint. The concurrent `v87` sync closed the previously observed SA86 listings failures.
  *(why →* arch-audit Finding 1 Option 2*)*

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA90 — squash migrations +          SA88b — forms diagnosis ✓ DONE          SA89a — DR persistence protocol ✓ DONE
  delete SA88 gate saga             SA86 — listings ✓ DONE                    (Finding 1, no deps)
  deps: none                            │                                        │
      │                                 ▼                                        ▼
      ▼                             Green-gate closeout:                     SA89b — DR orchestration port
SA84 — CRM (67 fixtures)             GATE-lint / check-suite / quality          deps: SA89a
  deps: none                         GATE-typecheck  deps: SA89b ────────────────┤
  │                                  SA91 — parallel integration loop            │
  │  (per-module gate)                 deps: none                                │
  Track 1                            Track 2                               Track 3
```

**Ordering.** The squash (SA90) eliminates the cross-org-migration class, so the SA88 gate saga (SA88a–e) is deleted, not completed. SA84 and SA86 survived as **fixture** cleanups, independent of each other. Track 1 runs SA90 → SA84; SA86 is complete on Track 2. Track 3 runs SA89a → SA89b fully independently.

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join: the per-module gate (SA84, Track 1) plus the repo-global gates and the SA91 parallel-loop tooling (Track 2) must all land on `v87`, and GATE-typecheck additionally waits on SA89b (Track 3) to remove the `mypy.ini:94` backups ignore. Track 2, having finished its module work, owns the closeout; it can start GATE-lint / GATE-check-suite / GATE-quality / SA91 immediately and holds GATE-typecheck until SA89b merges.

### Track readiness (2026-07-15)

- **Track 1 — READY (SA90, deps: none).** The squash-and-drop-backward-compat decision (see cross-cutting decision above) makes the whole cross-org-migration problem disappear: no static analyzer, no runtime boundary proofs, no gate. SA90 is fresh, dependency-free work; SA84 follows it and is unblocked by it. The retired SA88a–e findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) close as obsoleted-by-schema-squash.
- **Track 2 — module work complete; owns green-gate closeout.** SA88b and SA86 are both done (listings restricted-role suite passes clean, 134 passed/0 failed, no quarantine entry). With its module work finished, Track 2 now owns the green-gate closeout: GATE-lint / GATE-check-suite / GATE-quality and the SA91 parallel-integration-loop tooling are startable immediately (deps: none); GATE-typecheck is held until Track 3's SA89b removes the `mypy.ini:94` backups ignore.
- **Track 3 — BLOCKED (SA89b; maintainer-selected checkpoint, 2026-07-15).** The runtime/provider migration and incremental scanner improvements are validated, but implementation review remains `STATUS: partial` at the two-cycle cap. **SA89B-CR-001** still requires nearest-owner scope attribution and exact-count regressions; checkpoint review resolved **SA89B-DOC-001** and accepted the blocked-status wording for merge. The maintainer selected stop-and-merge with SA89b unchecked; no clean-gate or completion claim is made. Independent of the SA84/SA86 cluster.

**Decision re-based (2026-07-15) — Track 1: squash migrations, delete the SA88 gate saga.** After the static-analyzer line and its runtime-oracle successor both proved to be chasing an artifact of schema evolution, the maintainer confirmed (no deployed DB to preserve) that squashing every module to a final-schema `0001_initial` eliminates the cross-org-*migration* class outright. **Why:** the backfills only exist because `organization_id` was added to populated tables; a fresh schema has no rows to backfill, so there is no invariant left to gate. RLS enforcement (SA59/SA82) is unchanged; the *fixture* failures (SA84/SA86) are a separate, ContextVar-level concern the squash does not touch. **Sub-decisions (maintainer-selected):** (1) squash-and-drop-compat over continue-oracle; (2) manually re-attach RLS `RunPython` to the squashed migrations (not auto-generated); (3) keep a ~30-line forward guardrail against reintroducing cross-org migration DML. This supersedes every SA88 decision below.

**Decision re-based (2026-07-15) — ~~Track 1 SA88 gate oracle: runtime/behavioral proof.~~ SUPERSEDED** by the squash decision above (the runtime oracle proved an invariant that the squash removes entirely). Kept for the reasoning trail: after the static analyzer hit the review cap four times, the maintainer had re-based to *running* each cross-org migration under the restricted role (SA88d thin static layer + SA88e seeded boundary proofs). Retired along with SA88a–e.

**Decision deepened (2026-07-15) — ~~Track 1 SA88a: keep Option 2 (AST analyzer), split REV-006 into three chunks.~~ SUPERSEDED** by the squash. Kept for the trail: the maintainer had split residual REV-006 into SA88a.1/.2/.3 + SA88c on the shared analyzer file. Retired.

**Decision made (2026-07-14) — ~~Track 1 gate scope: Option A, multi-pass, split one-per-finding.~~ SUPERSEDED** by the squash. Kept for the trail: the maintainer had chosen a persistent multi-pass static-analyzer hand-off over a best-effort tripwire. SA88b (Track 2) and the SA89 line (Track 3) were and remain independent.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
