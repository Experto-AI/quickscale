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

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline for the remaining restricted-role cluster. Under it the closed modules are blog (SA83 + SA95), forms (SA85), listings (SA86), orgs (SA77), and notifications (SA79) — see [CHANGELOG.md](../../CHANGELOG.md). One red remains open: **CRM (SA84, Track 1)**. SA95 (blog fixture-finalizer regression) was closed after SA92 confirmed the regression was not reproducible on the synced v87 baseline — see the SA95 completed checkpoint under Track 2 below and [CHANGELOG.md](../../CHANGELOG.md).

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel.** `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate (the parallelizable axis)

- [ ] **SA84 — CRM restricted-role fixtures (67 fail).** `Tier 2 · Track 1 · deps: none` — full brief in the SA84 ticket under Track 1 below. Gate line: `make MODULE=crm test -- --modules` → 0 failures at the 80%/90% floors, no quarantine entry.
- [x] **SA95 — Blog fixture-finalizer regression — closed (no reproducible defect).** `Tier 2 · Track 2 · deps: none` — blog was closed green by SA83 but SA93's broad run re-surfaced `pytest-django` fixture-finalizer failures; after SA92 landed the regression did not reproduce on the synced v87 baseline — see the completed checkpoint under Track 2 below and [CHANGELOG.md](../../CHANGELOG.md).

  forms (SA85), listings (SA86), orgs (SA77), notifications (SA79), and blog (SA95) are green under the SA82 baseline — see [CHANGELOG.md](../../CHANGELOG.md).

#### Repo-global gates (run once at v87 integration, after per-module work lands)

GATE-lint, GATE-typecheck, GATE-check-suite, **GATE-quality**, and the reassigned **SA91** tooling are all **done** (see [CHANGELOG.md](../../CHANGELOG.md)). The remaining closeout is **SA93** (e2e in the green-gate), assigned to Track 3 after SA89a/b closed Finding 1. SA93 carries a hidden cross-track prerequisite — see its entry below.

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
  - **SA93-BLOCK-001 (high/blocking, historical):** the prior SA93 pre-review run failed in both Blog and CRM integration shards with `pytest-django` fixture-finalizer errors. CRM maps to open **SA84** (Track 1); Blog is now resolved by **SA95** (closed 2026-07-17 — no reproducible defect found on post-SA92 v87). CRM remains open under SA84.
  - **SA93-BLOCK-002 (high/blocking):** core and CLI E2E remain unexecuted because integration fails first. The current post-review 12-stage flow has not received a broad rerun; only the focused post-fix evidence above is current.

  **Decisions needed (resolved 2026-07-16):**
  - Blog-regression ownership is **decided**: it is a dedicated ticket, **SA95** (Track 2), and — together with CRM/**SA84** (Track 1) — is now an explicit cross-track prerequisite for SA93. Preserve the exact unquarantined `make ci-e2e` contract; quarantine and threshold weakening are not acceptable.
  - No design decision is needed for CR-SA93-REV-002 or CR-SA93-REV-004; they are deterministic first fixes for the next Track 3 continuation.

  **Clean continuation:** fix CR-SA93-REV-002/004 → land SA84 (CRM) fixes on `v87` (SA95 blog prerequisite resolved) → resync `wt-track3` → rerun exact `make ci-e2e` → verify both E2E suites execute and `e2e.yml` is green on `v87` → independent final review → mark SA93 complete.

  *(Acceptance unchanged:* `make ci-e2e` exits 0 on a fresh clone; `e2e.yml` green on `v87`; exit-criteria prose lists the e2e lane.*)*
  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Track 1 — Tenant-context surface

> **Migration-squash context (SA92, complete 2026-07-16).** The cross-org-*migration* half of arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`) was eliminated by squashing every module to a final-schema `0001_initial` (`organization_id NOT NULL` from row zero) — nothing to backfill, so the SA88 gate saga was deleted, not completed. Full decision record: [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md §SA88/§SA92](../../CHANGELOG.md). The **fixture** half survives (squashing does nothing to test fixtures): **SA84 (CRM, `deps: none`)** is the sole remaining open Track 1 work; the sibling **SA95 (blog)** was reassigned to Track 2 (2026-07-17) for parallel execution and closed after SA92 confirmed no reproducible defect on the synced v87 baseline; SA86 (listings) is done.

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS fixture failures (plus 20 skipped).** `Tier 2 · Track 1 · deps: none (decoupled from SA88 by the squash)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). These are ContextVar-seeded fixtures failing under NOBYPASSRLS and are unaffected by SA92. Route each cross-org *fixture* through the shared org-context helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry.
  *(why →* CR-SA82-NT-003; arch-audit Finding 8 (fixture half)*)*

  **Blocked checkpoint (2026-07-16; maintainer-selected stop-and-merge at change-review cap; not complete):**
  - **Done:** Resynced the clean Track 1 worktree to `v87`; reproduced the SA82 baseline as 67 fixture/setup RLS failures, 195 passes, and 21 skips; routed CRM fixture/setup writes through the shared org-context helpers; added forms-parity pre/post ContextVar/GUC/operator/role/AF9 cleanup; replaced deprecated direct DB setter usage with `org_scope` plus savepoints; corrected solo-route tests to the personal-org middleware contract; and made post-request assertions explicitly org-scoped. Restricted-role validation reached **262 passed / 21 skipped / 0 failed**, **95.25% aggregate coverage**, every CRM source file at or above 80%, and an empty quarantine map. Independent review resolved **SA84-REV-002**, **SA84-REV-003**, and **SA84-REV-004**.
  - **Pending/Blocking:** **SA84-REV-001 (high/blocking)** — `staff_user` installs the same personal-org ContextVar that `OrgEnrichedAPIClient.request()` captures and restores, so request exit does not return to a fail-closed baseline; seven post-request `refresh_from_db()` checks in `test_views.py` still rely on the residual transaction-local GUC. Reset fixture-held context before request scope and wrap each listed verification in its expected `org_scope`, then rerun restricted-role/coverage validation and independent review. **SA84-REV-005 (low/advisory)** — one bulk-stage serializer test description still calls solo routes unscoped despite the personal-org contract. SA84 stays unchecked.
  - **Decisions needed:** none. At the cycle-2 cap, the maintainer selected stop, record this blocked checkpoint, and merge. A clean continuation should fix SA84-REV-001 first, optionally clean up SA84-REV-005, rerun the exact restricted-role coverage gate, and obtain `STATUS: ok` review before marking SA84 complete.

### Track 2 — Module contracts & settings

> **Prior Track 2 work is complete** (SA88b forms diagnosis 2026-07-14; SA86 listings 2026-07-15; GATE-lint / GATE-typecheck / GATE-check-suite 2026-07-15; **SA94 react-only theme + Barrier B review 2026-07-16, STATUS ok**; **SA95 blog regression closed 2026-07-17** — ledger in [CHANGELOG.md](../../CHANGELOG.md)). The GATE-quality / SA91 / SA93 closeout items were reassigned to the freed Track 3. SA95 (blog regression) was reassigned here 2026-07-17 to run in parallel with Track 1's SA84 — it was `deps: none`, independent of CRM, and shortened the SA84+SA95 cross-track join that gates SA93. The regression did not reproduce on the post-SA92 v87 baseline and was closed without a speculative code change.

- [x] **SA95 — Blog restricted-role fixture-finalizer regression: closed — no reproducible defect found (2026-07-17).** `Tier 2 · Track 2 · deps: none`
  SA83 closed blog green (211 passed/0 failed under the SA82 gate), but SA93's broad pre-review run re-surfaced blog integration-shard failures with `pytest-django` fixture-finalizer errors. After SA92 landed (final-schema squashed migrations), the blog restricted-role suite was re-run on the synced v87 baseline.

  **Evidence:**
  - `QS_BLOG_DB_USER=quickscale_test_role make MODULE=blog test -- --modules` → **211 passed, 0 failed, 1 pre-existing AppConfig.ready DB-access warning** (non-blocking, pre-existing).
  - `make test-integration` → **exit 0; Blog 211 passed, 0 failed, 1 warning, 91.62% coverage; all modules green; overall mean 94.40%; no quarantine.**
  - Existing regression proof from SA83 lifecycle coverage: autouse ContextVar reset before/after each test, canonical `blog_org_scope`, and two `transaction=True` restricted-role list/feed tests with explicit org scopes and guaranteed `RESET ROLE` cleanup.

  **Findings:**
  - No fixture-finalizer, migration-state, or runtime-query defect reproduced on synced v87 after SA92 — therefore **no speculative executable change was made**.
  - Initial `no-listener` and `missing-named-DB` failures observed during the first triage attempt were **environment-only** (absent local PostgreSQL then absent named database) and resolved via CI-parity PostgreSQL/role/database provisioning before valid evidence could be gathered. No evidence links these setup failures to SA93; the relationship remains unproven.
  - The AppConfig.ready warning is non-blocking and pre-existing.

  *Acceptance:* blog restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry — **achieved.**
  *(why →* SA93-BLOCK-001; blog regression re-surfaced after SA83 closure; closed without code change because no defect reproduced on post-SA92 v87*)*

### Track 3 — Core/CLI plumbing

> **Finding 1 closed.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed: SA89a (persistence protocol in `core` + `restore_admin_uploaded_backup` port, done 2026-07-14) and SA89b (orchestration port closeout — declarative reverse import ban + modules-absent runtime proof, custom boundary scanner deleted, done 2026-07-15). Detail in [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

**Reassigned closeout work (from Track 2, to use freed Track 3 capacity):**

> **SA91 complete (2026-07-16)** — parallel integration worker pool validated and independently reviewed; identical verdicts/coverage vs sequential mode, no cross-worker DB collision. Detail in [CHANGELOG.md §SA91](../../CHANGELOG.md). Non-gating (CI-time speedup only). Residual **CR-SA91-REV-006 (low/advisory)** open: bounded scheduling can temporarily underutilize capacity — correctness/failure-propagation unaffected. SA93 remains Track 3's open closeout item.

- **GATE-quality** (done 2026-07-15, see [CHANGELOG.md](../../CHANGELOG.md)) and **SA93** (fold e2e into the green-gate) were also reassigned here; SA93 is defined in the green-gate section above and remains open (blocked checkpoint on the SA84/SA95 cross-track prerequisite).

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92 ✓ DONE (squash migrations) +   SA94 ✓ DONE (react-only theme)          Finding 1 ✓ DONE (SA89a+SA89b)
  delete SA88 gate saga               SA88b/SA86 ✓ DONE                      GATE-lint/typecheck/check/quality ✓
  deps: none                          SA95 ✓ DONE (blog regression, deps: none)    SA93 — e2e in green-gate (blocked)
      │                                     │  (reassigned from Track 1              SA91 ✓ DONE (parallel loop, non-gating)
      ▼                                     ▼   2026-07-17, runs || to SA84)
SA84 — CRM (67 fixtures)                SA95 ✓ DONE ─┐
  deps: none                                       ├─ per-module gates; SA93 prereqs
  │  ────────────────────────────────────────────┘
  Track 1                            Track 2                               Track 3
```

**Ordering.** The squash (SA92) eliminates the cross-org-migration class, so the SA88 gate saga (SA88a–e) is deleted, not completed. SA84 and SA95 survived as **fixture / test-posture** cleanups. Track 1 runs SA92 → SA84; **SA95 (blog) was reassigned to Track 2** (2026-07-17) so blog and CRM fixtures land in parallel — SA95 is `deps: none` and independent of CRM. **Track 2's original implementation and SA95 closeout are complete** (module work, its own gates, SA94 react-only theme — Barrier B STATUS ok; SA95 closed without code change). Track 3, freed after closing Finding 1, took over the remaining closeout (all GATEs done, SA93, SA91).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join: the per-module gates (SA84 CRM on Track 1 + SA95 blog on Track 2) plus the repo-global closeout (SA93 e2e, Track 3) must all land on `v87`. GATE-lint, GATE-typecheck, GATE-check-suite, and GATE-quality are complete. SA95 (blog) is now closed — no reproducible defect found. **SA93 is a blocked checkpoint** — the broad pre-review run reached coverage but CRM integration failed before E2E (the blog failure is resolved by SA95 closure), and independent review leaves CR-SA93-REV-002/004 open in the post-fix local-CI path. See the SA93 entry above for the exact Done / Pending-Blocking / Decisions-needed ledger. SA91 is a separate non-gating optimization (Track 3) — CI-time speedup only, not a gate for green.

### Track readiness (2026-07-17)

- **Track 1 — PARTIAL (SA84 blocked checkpoint; SA95 reassigned to Track 2).** SA84's fixture conversion and restricted-role/coverage evidence are green (262 passed / 21 skipped / 0 failed), but independent review remains open on **SA84-REV-001 (high/blocking)** — request-context restoration and seven post-request `refresh_from_db()` checks in `test_views.py` can still false-green through a residual transaction-local GUC. **SA84-REV-005 (low/advisory)** — one bulk-stage serializer test description still calls solo routes unscoped. The maintainer selected stop-and-merge at the review cap, so SA84 stays unchecked and must close REV-001 before completion. Track 1's only remaining open ticket is now SA84 (SA95 moved to Track 2 for parallelism). **SA92 completed** (bounded guardrail strategy implemented and independently reviewed; CR-SA90-MSQ-002/003/005 and SA92-QG-001 resolved; CR-SA92-ADV-001/002 recorded as low advisories).
- **Track 2 — COMPLETE (no remaining open tickets).** SA94 (react-only theme) removed `showcase_html` across 8 phases; resolved SA94-PLAN-CALLER-001, CR-SA94-REV-A-001/002/003, CR-SA94-REV-B-001/002 (CR-SA94-REV-A-004 low/advisory); eight pre-existing baseline gaps accepted. **SA95 (blog fixture-finalizer regression) was reassigned here 2026-07-17** to run parallel to Track 1's SA84 and closed after the post-SA92 rerun confirmed no reproducible defect — see the SA95 completed checkpoint above. Track 2 has no remaining open tickets.
- **Track 3 — PARTIAL (SA91 complete; SA93 blocked on cross-track work).** Finding 1 (DR persistence port, SA89a+SA89b), all four GATEs, and **SA91** (parallel integration worker pool) are complete. SA91 retains **CR-SA91-REV-006** (low/advisory, throughput only). **SA93** (e2e in green-gate) is a blocked checkpoint needing the deterministic CR-SA93-REV-002/004 fixes (no decision), then cannot complete until CRM (**SA84**, Track 1) shards are green on `v87` — the blog cross-track prerequisite (SA95) is now resolved. **SA89B-CR-004 (low/advisory)** remains independent, not gating.

**Net — no remaining maintainer decisions. SA92 and SA91 completed; SA94 completed; SA95 closed without code change.** Track 1 → close SA84-REV-001; Track 2 is fully complete (SA94 + SA95 done); Track 3 → SA93's deterministic fixes while awaiting the SA84 cross-track join (the SA95 blog prerequisite is now resolved). The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md §SA88/§SA92](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
