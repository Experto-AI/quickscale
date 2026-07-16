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

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline for the remaining restricted-role cluster. Under it the closed modules are blog (SA83), forms (SA85), listings (SA86), orgs (SA77), and notifications (SA79) — see [CHANGELOG.md](../../CHANGELOG.md). Two reds remain open: **CRM (SA84)** and a **blog fixture-finalizer regression (SA95)** that SA93's broad run re-surfaced after SA83 had closed blog green (see SA95 under Track 1).

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module.** `scripts/test_integration.sh` loops `quickscale_modules/*` sequentially (one pytest stage per module, each with its own per-file 80% / mean 90% coverage floor). `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate (the parallelizable axis)

- [ ] **SA84 — CRM restricted-role fixtures (67 fail).** `Tier 2 · Track 1 · deps: none` — full brief in the SA84 ticket under Track 1 below. Gate line: `make MODULE=crm test -- --modules` → 0 failures at the 80%/90% floors, no quarantine entry.
- [ ] **SA95 — Blog fixture-finalizer regression.** `Tier 2 · Track 1 · deps: none` — blog was closed green by SA83 but SA93's broad run re-surfaced `pytest-django` fixture-finalizer failures; full brief in the SA95 ticket under Track 1 below.

  forms (SA85), listings (SA86), orgs (SA77), notifications (SA79) are green under the SA82 baseline — see [CHANGELOG.md](../../CHANGELOG.md).

#### Repo-global gates (run once at v87 integration, after per-module work lands)

GATE-lint, GATE-typecheck, GATE-check-suite, and **GATE-quality** are all **done** (2026-07-15; see [CHANGELOG.md](../../CHANGELOG.md)). Track 2's module work and its own gates are complete, so the remaining closeout — the **SA91** tooling and the new **SA93** (e2e in the green-gate) — is **reassigned to the freed Track 3** (idle after SA89a/b closed Finding 1). SA91 has no dependencies. SA93 now carries a hidden cross-track prerequisite — see SA93 entry below.

- [ ] **SA93 — Fold the e2e lane into the green-gate definition of done.** `Tier 1 · Track 3 · deps: blog+CRM integration green (previously unstated cross-track join prerequisite)`
  **Blocked checkpoint (2026-07-15; maintainer-selected stop-and-merge; not complete).**

  **Done:**
  - Added the combined core/CLI/backups coverage path, `scripts/check_coverage_policy.py`, maintained helper tests, and focused DR-engine lock/path/sidecar tests.
  - The broad pre-review QG run reached the then-current coverage stage: its statement-weighted report was **92.02%** with **0/83 per-file offenders** (`_lock 97%`, `_paths 100%`, `_sidecar 94%); integration then failed in blog and CRM, so E2E did not run.
  - Review follow-up corrected the intended policy to an **equal-weight core/CLI package mean**, deferred pytest's weighted threshold so the helper is the final authority, and wired `make test-cov-policy` into the local CI path. Post-fix focused evidence is **24/24 helper tests passed**, Ruff passed, and `bash -n scripts/check_ci_locally.sh` passed.
  - Independent review resolved **CR-SA93-REV-001** (equal-package arithmetic/final authority) and **CR-SA93-REV-003** (maintained helper-test collection).

  **Pending/Blocking:**
  - **CR-SA93-REV-002 (high/blocking):** coverage JSON validation is not fully fail-closed. Scalar/null roots and non-dict file records can raise; reports missing either expected package can pass; prefix-only classification accepts non-canonical traversal paths. Add root/container/record validation, require both packages, reject non-canonical paths, and add malformed/missing-package/traversal proofs.
  - **CR-SA93-REV-004 (medium/blocking):** `scripts/check_ci_locally.sh` advertises 12 stages but uses inconsistent `/11` denominators and duplicates `[11/11]` on the non-E2E path. Normalize conditional stage totals and make the E2E-skip message unnumbered before relying on stage-number evidence.
  - **SA93-BLOCK-001 (high/blocking):** blog and CRM integration shards fail with `pytest-django` fixture-finalizer errors. CRM maps to open **SA84** (Track 1); the blog regression is now owned by dedicated ticket **SA95** (Track 1).
  - **SA93-BLOCK-002 (high/blocking):** core and CLI E2E remain unexecuted because integration fails first. The current post-review 12-stage flow has not received a broad rerun; only the focused post-fix evidence above is current.

  **Decisions needed (resolved 2026-07-16):**
  - Blog-regression ownership is **decided**: it is a dedicated ticket, **SA95** (Track 1), and — together with CRM/**SA84** — is now an explicit cross-track prerequisite for SA93. Preserve the exact unquarantined `make ci-e2e` contract; quarantine and threshold weakening are not acceptable.
  - No design decision is needed for CR-SA93-REV-002 or CR-SA93-REV-004; they are deterministic first fixes for the next Track 3 continuation.

  **Clean continuation:** fix CR-SA93-REV-002/004 → land SA84 (CRM) + SA95 (blog) fixes on `v87` → resync `wt-track3` → rerun exact `make ci-e2e` → verify both E2E suites execute and `e2e.yml` is green on `v87` → independent final review → mark SA93 complete.

  *(Acceptance unchanged:* `make ci-e2e` exits 0 on a fresh clone; `e2e.yml` green on `v87`; exit-criteria prose lists the e2e lane.*)*
  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Cross-cutting decision — eliminate the cross-org-migration class by squashing to a final-schema initial migration (arch-audit Finding 8)

**Ratified and landed.** The full decision record is the SSOT in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); the reasoning trail and the retired SA88 gate saga are in [CHANGELOG.md §SA88/§SA92](../../CHANGELOG.md). One-paragraph summary for planning:

The cross-org-*migration* half of arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`) was an artifact of schema evolution — `organization_id` added to populated tables forced `_backfill_*_org` `RunPython` steps that needed elevated RLS context. Pre-launch with **no deployed DB to carry forward**, we squashed every module to a final-schema `0001_initial` (`organization_id NOT NULL` from row zero). Nothing to backfill → the class is empty → the entire SA88 conformance-gate saga (seam + SA88a–e static analyzer + SA88d/SA88e runtime oracle, `operator_access_migration` helper, 7,144-line gate file) is **deleted, not completed**; retired findings CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 close as **obsoleted-by-schema-squash**. RLS enforcement (SA59/SA82, FORCE RLS under `quickscale_test_role`) is unchanged.

**What this leaves for open work.** The *fixture* half survives (squashing does nothing to test fixtures). CRM triage confirmed 67 failures bucket **0 migration / 67 fixture / 0 runtime-query** (test-posture, no production isolation bug), so **SA84 (CRM) remains real work with `deps: none`**, decoupled from SA88. SA86 (listings) — same fixture cleanup — is done. SA92 itself is a merged blocked checkpoint (unchecked; see Track 1).

### Track 1 — Tenant-context surface

- [ ] **SA92 — Squash all module migrations to a final-schema initial migration; delete the SA88 gate saga.** `Tier 2 · Track 1 · deps: none`
  Collapse each module's migrations to one `0001_initial` at the final model state, with `organization_id NOT NULL` from creation. Manually re-attach each module's RLS `RunPython` (`apply_force_rls`, orgs `operator_access_rls`/`operator_access_readonly`); drop all `_backfill_*_org` steps. Delete `test_sa88_migration_operator_access_conformance.py` and retire the now-dead `operator_access_migration` helper. Add a **~30-line forward guardrail** unit test asserting no module migration contains cross-table org-id DML (`UPDATE ... SET organization_id` referencing another table), so the eliminated class cannot silently return.

  *Acceptance:* fresh `migrate` on an empty DB builds the identical schema **and identical RLS policy set** as `v87` (diff `pg_policies`); NOBYPASSRLS integration suite behaves as before the squash; guardrail test green; MyPy + orgs lint green; independent review confirms the RLS re-attachment is complete and no backfill logic was silently lost. Closes CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 as **obsoleted-by-schema-squash**.
  *(why →* arch-audit Finding 8; 2026-07-15 squash re-base*)*

  **Implementation landed on `v87` as a merged blocked checkpoint (unchecked).** Done-history — one `0001_initial` per module, 35 intermediates + SA88 gate deleted, `operator_access_migration` retired, forward guardrail added, exact `pg_policies`/catalog/RLS/data parity against `v87` — is in [CHANGELOG.md §SA92](../../CHANGELOG.md). Two maintainer cap decisions (stop/record/merge). What remains open on the ticket:

  - **Pending/Blocking:** **CR-SA90-MSQ-002 (high/blocking)** and **CR-SA90-MSQ-003 (medium/blocking)** — after two non-converging review cycles, the forward guardrail's handwritten Python/SQL scanner (`orgs/tests/test_sa92_migration_squash_guardrail.py`, now **910 lines** vs the ~30 originally scoped) still has concrete false negatives for post-control-flow bindings, parameter/import scope, nested named provenance, complete RHS validation, PostgreSQL E-string/comment lexing (MSQ-002), and escaped-quote/outer-paren normalization + positive-preservation/populated-ID controls (MSQ-003). SA92 stays unchecked until review resolves or waives both.
  - **Decisions needed (maintainer) — bounded guardrail strategy.** This is the same non-convergence trap the SA88 static-analyzer line hit four times: proving DML provenance by scanning arbitrary Python/SQL source is undecidable, and the scanner has grown 30×. Do **not** approve another round of extending the ad-hoc scanner without a reviewed, bounded contract. See the guidance and options below the Track 1 tickets. At the current cap the maintainer selected stop/record/merge; no completion or waiver is implied.
  - **Advisory:** **CR-SA90-MSQ-005 (low/advisory)** — roadmap/decisions prose should not imply orgs installs operator policies; each tenant module's `0001_initial` installs its own, and orgs installs none at its migration point.

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS fixture failures (plus 20 skipped).** `Tier 2 · Track 1 · deps: none (decoupled from SA88 by the squash)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). These are ContextVar-seeded fixtures failing under NOBYPASSRLS and are unaffected by SA92. Route each cross-org *fixture* through the shared org-context helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry.
  *(why →* CR-SA82-NT-003; arch-audit Finding 8 (fixture half)*)*

- [ ] **SA95 — Fix the blog restricted-role fixture-finalizer regression.** `Tier 2 · Track 1 · deps: none`
  SA83 closed blog green (211 passed/0 failed under the SA82 gate), but SA93's broad pre-review run re-surfaced blog integration-shard failures with `pytest-django` fixture-finalizer errors. **First step — triage before fixing** (matches the SA83–SA86 discipline): run blog's restricted-role suite on current `v87` (`QS_BLOG_DB_USER=quickscale_test_role make MODULE=blog test -- --modules`) and bucket the failures into fixture-teardown-ordering vs migration-state vs runtime-query. Fix the confirmed root; a runtime-query-bucket failure is a real isolation bug (with its own regression test), not test-posture. Note the interaction with SA92: the squash regenerates blog's migrations, so re-run this suite after SA92 lands to confirm the regression is not a migration-state artifact before closing.

  *Acceptance:* blog restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; regression test pins the finalizer fix.
  *(why →* SA93-BLOCK-001; blog regression re-surfaced after SA83 closure*)*

> **⚠ Decision needed (maintainer) — SA92 forward-guardrail strategy.** SA92 is a merged blocked checkpoint on CR-SA90-MSQ-002/003. The block is *not* the squash (schema/RLS/data parity is exact against `v87`); it is the ~30-line "forward guardrail" that grew into a 910-line handwritten Python/SQL source scanner and hit the same undecidable-provenance wall the SA88 static analyzer hit four times. **Extending that scanner again is a §0 fix-regression** and the roadmap explicitly rules it out without a reviewed bounded contract. Options, best-fit first (all preserve the exact fresh-migrate parity gate, which is the real proof the class stays empty):
>
> 1. **Retire the scanner; rely on the structural guarantee + parity gate, plus a deliberately shallow literal tripwire (recommended).** The squash makes each `0001_initial` backfill-free *by construction*; the checked-in `pg_policies`/catalog/data parity gate already fails loud on any schema/RLS drift. Replace the 910-line analyzer with the originally-scoped ~30-line assertion: one migration file per module + a literal substring/regex scan for the `UPDATE … SET organization_id` cross-table DML shape with an explicit allowlist, documented as a *smoke alarm, not a proof*. Converges immediately; decidable; matches the ratified SA88 lesson (don't build the undecidable analyzer) and the "governance by gate, bounded" house style. CR-SA90-MSQ-002/003 dissolve because the fragile provenance surface is deleted, not hardened.
> 2. **Runtime/behavioral guardrail (mirror the retired SA88e oracle).** Assert the property by *execution*: a seeded restricted-role `MigrationExecutor` run proving no migration performs cross-org writes. Escapes the static-lexing trap entirely and is consistent with arch-audit's "restricted-role gate is the real oracle." Heavier to build and largely redundant now that the class is empty by construction — reach for it only if a forward tripwire against *future* backfill migrations is judged worth the infra.
> 3. **Drop the forward guardrail entirely.** Rely solely on squash-by-construction + parity gate + maintainer review of any new migration. Zero non-convergence surface, but no automated tripwire if a future migration reintroduces a backfill.
>
> **Recommendation: Option 1** — it closes CR-SA90-MSQ-002/003 by *removing* the undecidable surface rather than hardening it, keeps a cheap forward tripwire, and organically matches the SA88 oracle-pivot precedent (a bespoke source analyzer over arbitrary Python/SQL has no finish line). Then rerun affected gates and obtain clean independent review before checking SA92.

### Track 2 — Module contracts & settings

> **Prior Track 2 work is complete.** SA88b (forms diagnosis) done 2026-07-14; SA86 (listings) done 2026-07-15; GATE-lint / GATE-typecheck / GATE-check-suite all green 2026-07-15; **SA94 (react-only theme) implementation and documentation complete 2026-07-16; Barrier B (independent full code-and-docs review) pending before merge** — detail in [CHANGELOG.md](../../CHANGELOG.md). The remaining closeout items (GATE-quality, SA91, SA93) were reassigned to the freed Track 3 to balance load — see the green-gate section and Track 3 below. **Track 2 has no remaining open implementation work** after SA94.

- [x] **SA94 — Remove the `showcase_html` generator theme; make `showcase_react` the sole theme.** `Tier 2 · Track 2 · deps: none`
  **Implementation and documentation complete 2026-07-16.** The HTML demo (`showcase_html`) never gained adoption but carried ongoing maintenance cost. Implementation covered 8 phases across source deletion, wiring pruning, template collapse, test migration, frontend-only E2E input change, coverage isolation, fail-closed identity validation, and docs alignment. Barrier A (change-review pass 2: `STATUS ok`) passed; Barrier B (independent full code-and-docs review) is pending before merge.
  - **Barrier A** (change-review pass 2: `STATUS ok`): resolved SA94-PLAN-CALLER-001 (high/blocking — DR `_build_context` and `up` now validate retired-theme identity before Docker-backed checks, with no-subprocess/no-mutation sentinels), CR-SA94-REV-A-001 (malformed/missing/non-mapping project structure could bypass central preflight before development up/DR probes), CR-SA94-REV-A-002 (arbitrary apply config filenames and the actual resolved output-root state/recovery could evade preflight), CR-SA94-REV-A-003 (standalone embed/remove could probe or mutate before the shared wiring guard).
  - **Advisory** CR-SA94-REV-A-004 (low) — broad invalid-config assertions in `test_apply_command.py` could mask ordering regressions; dedicated SA94 sentinel tests provide sufficient coverage. Remains advisory, not resolved by Barrier A.
  - **Documentation alignment:** all current docs updated to React-only/fail-closed semantics; historical release notes and prior changelog entries unchanged. Existing generated `showcase_html` projects keep user-owned files — no automatic rewrite. Any desired/state/recovery reference to `showcase_html` fails closed before operational side effects. Barrier B (independent full review) pending before merge.
  - **User-accepted baseline gaps** (eight pre-existing failures reproduced identically on the pre-SA94 baseline and explicitly accepted by the user after `qg_runs=2`): one backups assertion failure plus seven E2E/runtime integration failures. These are pre-existing, not introduced by SA94.

  *Evidence:* `grep -rn "showcase_html" quickscale_core quickscale_cli quickscale_devtools quickscale_modules docs .github` returns only explicit rejection references (retired-theme validation, test adapters, fixture manifests), historical release notes, and this roadmap entry. All current docs updated to React-only/fail-closed semantics.
  *(why →* unused theme, ongoing maintenance cost; single supported frontend is `showcase_react`*)*

### Track 3 — Core/CLI plumbing

> **Finding 1 closed.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed: SA89a (persistence protocol in `core` + `restore_admin_uploaded_backup` port, done 2026-07-14) and SA89b (orchestration port closeout — declarative reverse import ban + modules-absent runtime proof, custom boundary scanner deleted, done 2026-07-15). Detail in [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

**Reassigned closeout work (from Track 2, to use freed Track 3 capacity):**

> **↪ Next up for Track 3 (hand off now): SA91.** It is unblocked (`deps: none`), non-gating, and independent of the SA93 cross-track wait — start it immediately rather than idling behind SA93.

- [ ] **SA91 — Fork the per-module integration loop for true parallel execution.** `Tier 2 · Track 3 · deps: none`
  `scripts/test_integration.sh` runs module stages serially (loop at `:414–442`). Fork each module's pytest stage and join exit codes + coverage. Contention points to resolve: the shared `COVERAGE_RESULTS_FILE` mktemp (`:57`) must become per-module and be merged before `check_overall_mean_coverage`; the per-module `QS_*_DB_USER` role setup (`:375–386`) and pre-created test databases must not collide across concurrent workers. CI-time speedup only — not a gate for the green-gate milestone.

  *Acceptance:* parallel run produces the identical pass/fail verdict and the identical overall-mean coverage as the serial run; no cross-worker DB collision under the restricted role.
  *(why →* parallelize testing by module*)*

- **GATE-quality** (done 2026-07-15, see [CHANGELOG.md](../../CHANGELOG.md)) and **SA93** (fold e2e into the green-gate) were also reassigned here; SA93 is defined in the green-gate section above and remains open (blocked checkpoint on the SA84/SA95 cross-track prerequisite).

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92 — squash migrations +          SA94 ✓ DONE (react-only theme)          Finding 1 ✓ DONE (SA89a+SA89b)
  delete SA88 gate saga               deps: none (non-gating)               GATE-lint/typecheck/check/quality ✓
  deps: none                          (Track 2 complete)                     SA93 — e2e in green-gate (blocked)
      │                                                                       SA91 — parallel loop (non-gating)
      ▼
SA84 — CRM (67 fixtures) ┐
SA95 — blog regression   ┘ deps: none
  │  (per-module gates; SA93 prereqs)
  Track 1                            Track 2                               Track 3
```

**Ordering.** The squash (SA92) eliminates the cross-org-migration class, so the SA88 gate saga (SA88a–e) is deleted, not completed. SA84 and SA95 survived as **fixture / test-posture** cleanups. Track 1 runs SA92 → SA84 → SA95. **Track 2 implementation complete** — module work, its own gates, and SA94 (react-only theme) are all done (Barrier B review pending before merge). Track 3, freed after closing Finding 1, took over the remaining closeout (all GATEs done, SA93, SA91).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join: the per-module gates (SA84 CRM + SA95 blog, Track 1) plus the repo-global closeout (SA93 e2e, Track 3) must all land on `v87`. GATE-lint, GATE-typecheck, GATE-check-suite, and GATE-quality are complete. **SA93 is a blocked checkpoint** — the broad pre-review run reached coverage but blog+CRM integration failed before E2E, and independent review leaves CR-SA93-REV-002/004 open in the post-fix local-CI path. See the SA93 entry above for the exact Done / Pending-Blocking / Decisions-needed ledger. SA91 is a separate non-gating optimization (Track 3) — CI-time speedup only, not a gate for green.

### Track readiness (2026-07-16)

- **Track 1 — CLEAN to continue on SA84/SA95; one maintainer decision gates SA92.** SA84 (CRM fixtures) and SA95 (blog regression) are both `deps: none` and can start now — this is the productive Track 1 work. The merged SA92 blocked checkpoint (unchecked) needs the **bounded guardrail-strategy decision** framed above (⚠ block, between the Track 1 tickets and Track 2) before its continuation can converge; the squash itself is landed and parity-exact, so this decision does not gate SA84/SA95. CR-SA90-MSQ-005 stays advisory. Rerun SA84/SA95 suites on the post-squash `v87` to confirm no failure is a migration-state artifact. Retired SA88a–e findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) close as obsoleted-by-schema-squash.
- **Track 2 — implementation complete; Barrier B (independent full review) pending.** Prior module work (SA86, SA88b), its gates (GATE-lint/typecheck/check-suite), and **SA94** (react-only theme) are all implemented and documented. Barrier B (independent full code-and-docs review) must clear before the SA94 merge is final. Track 2 has no remaining open implementation work.
- **Track 3 — CLEAN to continue on SA91; SA93 blocked on cross-track work.** Finding 1 (DR persistence port, SA89a+SA89b) and all four GATEs are done. **SA91** (non-gating parallel-loop tooling, `deps: none`) is the productive Track 3 work now. **SA93** (e2e in green-gate) is a blocked checkpoint needing the deterministic CR-SA93-REV-002/004 fixes (no decision), then cannot complete until CRM (**SA84**) and blog (**SA95**) shards are green on `v87` — a cross-track dependency on Track 1. **SA89B-CR-004 (low/advisory)** remains independent, not gating.

**Net — one maintainer decision outstanding (Track 1 SA92 guardrail strategy).** Everything else is runnable now: Track 1 → SA84 + SA95; Track 2 → no remaining implementation work (Barrier B review pending for SA94); Track 3 → SA91 in parallel. SA93 waits on SA84/SA95 landing green (green-gate cross-track join). The squash-migrations decision itself is ratified and SSOT'd in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md §SA88/§SA92](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
