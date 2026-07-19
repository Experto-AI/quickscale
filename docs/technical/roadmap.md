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
>
> **Conditionally shared — `docs/technical/decisions.md`:** Added to the shared-closeout set when repository-wide policy or acceptance evidence changes (e.g., recording that a previously open ticket is closed). The existing `git merge v87` synchronization and preserve-both-sides resolution procedure above covers this surface — decisions.md entries must be reconciled with the same discipline as CHANGELOG.md and roadmap.md entries, not overwritten across tracks.

---

## Open work

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active and blocked work.

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is green with all per-module restricted-role gates closed. See [CHANGELOG.md](../../CHANGELOG.md).

**Open workstreams before release:**
1. **SA96-GATE** (green-gate join) — SA93's dependency is met; next release-path step, but **blocked** on quality-baseline regressions (SA96-GATE-BLK-002). The prior coverage blocker (SA96-GATE-BLK-001) is superseded by the restored canonical coverage evidence.
2. **SA96-PUBLISH** (staged PyPI publish), deps on SA96-GATE.
3. **Audit remediation status** — SA97+SA98 complete arch-audit Finding 9, SA99 completes Finding 7's cheap sub-item, and SA100 completes tech-audit TA58/TA59; all are independent of the release critical path. See [CHANGELOG.md](../../CHANGELOG.md). Arch Findings 2 and 4 stay deferred with the (unscheduled) teams module — **not ticketed**.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gates and repo-global gates — CLOSED

All per-module restricted-role gates (CRM/SA84, blog/SA83+SA95, forms/SA85, listings/SA86, orgs/SA77, notifications/SA79) and repo-global gates (GATE-lint, GATE-typecheck, GATE-check-suite, GATE-quality, SA91 parallel worker pool), including **SA93** (e2e in the green-gate), are **complete** — see [CHANGELOG.md §SA93 continuation](../../CHANGELOG.md#sa93-continuation) for the local `make ci-e2e` gate and the verified hosted evidence (SA93-EVID-001). Both former cross-track prerequisites (SA84 CRM, SA95 blog) are met. Non-gating advisories SA93-REV-005 and SA93-ADV-001..004 remain deferred (tracked in the Track 3 readiness bullet).

### Pre-publish verification & release sweep (SA96)

Pre-release re-verification: **SA96-T1 (Track 1) and SA96-T2 (Track 2) module sweeps are complete** — all 12 modules re-verified green in isolation on post-SA92 v87, no regression, empty quarantine. **SA93 is complete and its dependency is met; SA96-GATE is the next release-path step.** See [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA96-GATE — Green-gate join (cross-track).** `Tier 1 · v87 integration · deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93` · *assistant-executable*
  With both module sweeps complete and the SA93 dependency met, on a fresh clone + fresh `migrate` (post-SA92 squash) run until all exit 0 with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`:
  `make check` → `make quality` → `make ci` → `make ci-e2e`. All four green + empty quarantine = publishable (single definition of done, see the exit-criteria above). A coding assistant may run this join and report the result; it stops here and hands off to a human for SA96-PUBLISH.
  - **Checkpoint `SA96-GATE-BLK-001` (2026-07-18; resolved/superseded by current canonical evidence):** The prior core-coverage blocker is resolved for this checkpoint: canonical coverage recorded **2,480 passed, 1 skipped, 90 deselected; 6,026/6,670 = 90.34%**, including orchestration **745/1,011 = 73.69%** (**+35 from 5,991**). Focused authored tests passed (127); Ruff/MyPy passed; `make check` exited 0 in **3m35.303s** with a **94.41%** integration-policy mean; and the quarantine source is empty. The authored implementation is limited to five new test modules; no source, config, baseline, or threshold changes were made.
  - **Baseline and target:** Discovery snapshot `quickscale-core-cov-remediation-v2` recorded 6,670 statements, an exact floor of 6,003, and an operational target of 6,004. Current canonical evidence is 6,026/6,670 (90.34%), so the coverage target is met for this checkpoint; the former BLK-001 coverage evidence is superseded.
  - **Approved coverage-remediation plan (big tier; independently reviewed):** Phase 0 was the complete baseline and plan-review checkpoint. Initial plan findings `SA96-PLAN-001`, `SA96-PLAN-002`, and `SA96-PLAN-003` were resolved; plan review pass 2 returned `STATUS: ok`. The approved test-only implementation was executed within scope in five new test modules, with no source, config, baseline, or threshold changes.
  - **Historical plan scope:** The approved pure-mock plan covered orchestration and measured manifest-resolver additions; current evidence supersedes its remaining-gain targets. No further coverage slice is authorized in this checkpoint, and no source, config, baseline, or threshold changes are permitted.
    - **Canonical diagnostic measurement:**
      ```bash
      rm -f .coverage quickscale_core/coverage.xml && poetry run python -m pytest quickscale_core/tests -q --tb=short -o addopts= -p no:django -m "not integration and not e2e" --cov=quickscale_core --cov-report=term-missing --cov-report=xml:quickscale_core/coverage.xml --cov-fail-under=0
      ```
      Record the exit code, tree identity/status, changed-file manifest, lines-valid/covered, overall and orchestration rates, gain, and test counts. The denominator must remain 6,670.
    - **Phase 4 — final gates and closeout:** The checkpoint evidence has `make check` green and the quarantine source empty. `make quality` exited 2 with 9 critical + 10 warning baseline regressions at `.quickscale/quality_report.md` lines 32–52; `make ci` and `make ci-e2e` were not run. Independent change-review pass 2 returned **STATUS ok** with **SA96-CR-001 (blocking)** and **SA96-CR-002 (advisory)** resolved and no new findings. The blocked checkpoint is safe to merge; SA96-PUBLISH remains human-only.
  - **Checkpoint `SA96-GATE-BLK-002` (2026-07-19; blocking):** `make quality` exited 2 with **9 critical + 10 warning baseline regressions** at `.quickscale/quality_report.md` lines 32–52. These are unrelated to the five authored test modules. Preserve this blocker and route it separately as either a separately approved remediation task or an explicitly approved quality-baseline policy reconciliation; do not change baselines, thresholds, source, or config in this checkpoint.
  - **Validation, rollback, and re-plan rules:** Execution remains serial and the green-gate definition is unchanged. The coverage requirement is met, but SA96-GATE remains blocked by BLK-002 until its required quality decision and follow-up evidence are complete. The user approved merging this blocked checkpoint without claiming SA96-GATE completion.
  - **Next action:** Route SA96-GATE-BLK-002 separately to a separately approved quality-baseline decision and remediation/reconciliation task; the independent review is complete and is not a remaining action. `make ci` and `make ci-e2e` must not be represented as run.

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE` · **HUMAN-ONLY — do not delegate to an assistant**
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — TP (test-parallelization) suite open

Prior Track 1 tickets are closed — SA92 (migration squash), SA84 (CRM restricted-role), SA86 (listings), **SA96-T1** module sweep, Finding 8, plus the two audit-remediation tickets **SA97** (arch-audit Finding 9 test-plumbing half) and **SA99** (arch-audit Finding 7 devtools→ruff/mypy), both completed 2026-07-17. See [CHANGELOG.md](../../CHANGELOG.md).

Track 1 was idle and has been assigned the **TP (test-parallelization)** suite. Goal: shorten the SDLC feedback loop (and let an AI assistant run partial tests concurrently) by parallelizing the long-running quality gates. Motivation and full analysis: the parallelization audit summarized under *(why →* …*)* on each ticket. **The integration suite is already parallel (SA91, `QS_INTEGRATION_JOBS`)**; **TP1** (serial static-gate fan-out) and **TP2** (unit-suite xdist) are complete (see [CHANGELOG.md](../../CHANGELOG.md)), while TP2b implementation and focused evidence are landed but its closeout is validation-blocked pending independent review. The two remaining Track 1 tickets are **TP2b** (make `test-cov` xdist-safe via `coverage combine`) and **TP4** (docs-only AI fast-loop recipes). **The E2E-concurrency sub-chain (TP3a/TP3b) has been rebalanced to Track 2** (2026-07-18) to run in parallel; it is file-disjoint from the Track 1 tickets here (TP3a owns `scripts/test_e2e.sh` plus `quickscale_cli/tests/test_e2e_development_workflow.py`; TP3b retains `scripts/test_e2e.sh` for concurrent-lane orchestration). None are on the SA96 release critical path; they are pure cycle-time improvements and must not regress any existing gate's pass/fail set or coverage thresholds.

- [ ] **TP2b — Convert `test-cov` from `--cov-append` phase-ordering to `coverage combine` so it is xdist-safe.** `Tier 2 · Track 1 · deps: TP2 · implementation checkpoint 2026-07-18; validation blocked; final independent review pending`
  `make test-cov` (`Makefile` `test-cov` target) now uses isolated phase `COVERAGE_FILE` paths, one explicit `coverage combine` pipeline before the HTML/report/JSON outputs and policy check, guarded xdist defaults, and the `PYTEST_XDIST_WORKERS=0` serial debugging override. The `REQUIRE_BACKUPS_COVERAGE` behavior remains unchanged.
  - Done: review fixes applied; structural and behavioral coverage-policy tests pass (50 policy tests and 10 behavioral tests); bounded two-worker xdist validation produced a 91.90% equal-weight policy mean (core 93.45%, CLI 90.36%, 84 files); the first pre-review exact gate passed.
  - Blocker ledger: **CR-TP2B-001** and **CR-TP2B-002** are resolved by independent change-review pass 2. **QG-TP2B-001** remains medium/blocking, is not waived, and records that the exact default command timed out after 30 minutes at 99% with exit 143; the required-backups command was not reached. Pending recovery commands (both require sufficient runtime; preserve results): `QS_BACKUPS_DB_USER=quickscale_test_role make test-cov` and `QS_BACKUPS_DB_USER=quickscale_test_role make test-cov REQUIRE_BACKUPS_COVERAGE=1`. After both finish, preserve the results and obtain final independent review. No design decision is pending.
  - Preserve the existing dual-threshold policy (90% equal-weight package mean + 80% per-file) and the `REQUIRE_BACKUPS_COVERAGE` behavior exactly.
  - `-n auto` is now threaded through both `test-cov` phases, while `PYTEST_XDIST_WORKERS=0` remains the serial debugging override.
  - Focused evidence: 50 policy tests, 10 behavioral tests, serial baseline, post-change serial parity, and bounded `PYTEST_XDIST_WORKERS=2` xdist validation passed with a 91.90% equal-weight policy mean (core 93.45%, CLI 90.36%, 84 files). The first pre-review exact gate passed; the post-review exact default timed out after 30 minutes at 99% with exit 143, so the required-backups exact command was not reached. Recovery remains pending for both exact commands above; sufficient runtime and preserved results are required before final independent review.
  *(why →* parallelization audit Tier 2 caveat — append ordering blocks xdist on the coverage suite; combine is the standard fix*)*

- [ ] **TP4 — Document the AI-assistant fast partial-test recipes.** `Tier 1 · Track 1 · deps: none · docs-only (review-only closeout)`
  The repo already supports targeted, safe partial runs that an AI assistant should prefer during iteration, but they are underused/undocumented as a coherent workflow: section flags (`make lint -- --core`, `make typecheck -- --cli`, `make test-unit -- --core`), single-module reruns (`make MODULE=<name> test -- --modules`), and bounded integration concurrency (`QS_INTEGRATION_JOBS=<N> make test-integration`).
  - Add a short "Fast feedback loop for AI-assisted / incremental development" subsection to `docs/technical/development.md` (or the closest testing doc): the iterate → pre-merge → E2E-last ladder, the targeted-rerun recipes above, and the new `QS_CI_PARALLEL` (TP1, Track 1) / `QS_E2E_PARALLEL` (TP3b, **Track 2**) knobs once they land (cross-reference, don't block on them — this is the one cross-track reference the rebalance introduces; land TP4 after both TP1 and TP3b merge to `v87`).
  - Verify: every command in the doc runs as written on a clean tree.
  *(why →* parallelization audit Tier 4 — scoped partial runs already exist; the gap is discoverability for the incremental-dev loop*)*

### Track 2 — Module contracts & settings — E2E-concurrency sub-chain (TP3a ✓ → TP3b)

Prior development tickets closed — SA88b (forms diagnosis), SA86 (listings), SA94 (react-only theme), SA95 (blog fixture-finalizer regression), GATE-lint/typecheck/check-suite, **SA96-T2** module sweep, and **SA98** (sanitizer consolidation; SA97+SA98 close arch-audit **Finding 9**). See [CHANGELOG.md](../../CHANGELOG.md).

Track 2 was idle after SA98 and carries the **E2E-concurrency sub-chain of the TP suite** — TP3a→TP3b, rebalanced off Track 1 (2026-07-18) so the E2E port-namespacing + concurrent-lanes work runs in parallel with Track 1's TP1/TP2/TP2b. **TP3a (E2E port-namespacing) is complete — see [CHANGELOG.md](../../CHANGELOG.md);** only TP3b remains. TP3a owned `scripts/test_e2e.sh` plus `quickscale_cli/tests/test_e2e_development_workflow.py`; TP3b retains `scripts/test_e2e.sh` for the concurrent-lane orchestration and reuses the read-only `_qs_jobs.sh` join/replay helpers. The sub-chain shares no source files with Track 1's TP work — the only overlap is the shared closeout files (`CHANGELOG.md`, `roadmap.md`), which the Merge procedure already reconciles. Off the SA96 release critical path; must not regress any gate's pass/fail set or coverage thresholds.

- [ ] **TP3b — Run Core-E2E and CLI-E2E as two concurrent lanes in `test_e2e.sh`.** `Tier 2 · Track 2 · deps: TP3a ✓`
  - **Precondition carried from TP3a (execution evidence, not a design decision):** TP3a's merged-v87 rerun passed stages 1–11 but the final CLI E2E stage did not complete within the runner allowance, so integrated `make ci-e2e` green was **not** established. Before starting TP3b or claiming integrated CI green, run `make ci-e2e` in an environment with more than a 20-minute allowance and retain the final CLI E2E result.
  With ports namespaced (TP3a), split the currently-serial Core-E2E → teardown → CLI-E2E flow in `scripts/test_e2e.sh` into two lanes launched concurrently (reuse the `_qs_join_workers`/`_qs_replay_worker_logs` join+replay pattern), aggregate exit codes, and drop the inter-suite `sleep 2` teardown that only existed to free shared ports.
  - Preserve per-lane cleanup traps and the final pass/fail banner + non-zero exit on any lane failure. Keep `--headed`, `--no-cleanup`, `--full` flags working (pass through to both lanes).
  - Gate concurrency behind an opt-out (e.g. `QS_E2E_PARALLEL=0`) for debugging, consistent with TP1.
  - Verify: `make test-e2e` and `make ci-e2e` exit 0 on a clean tree; injecting a failure into only the CLI lane still fails the overall run and is attributed correctly; wall-clock drops versus the serial Core→CLI sequence.
  *(why →* parallelization audit Tier 1 — E2E is the dominant SDLC cost and Core/CLI lanes are independent once ports are namespaced*)*

### Track 3 — Core/CLI plumbing — SA93 complete; SA96-GATE next

arch-audit **Finding 1** is closed (SA89a+SA89b, DR persistence port). All four GATEs, **SA91** (parallel worker pool), and **SA93** (e2e in the green-gate) are complete. SA93's local gate and hosted evidence are recorded in its task block; **SA96-GATE** is the next release-path step. **SA100** (tech-audit TA58/TA59 theme-preflight remediation) is complete — see [CHANGELOG.md](../../CHANGELOG.md). **No cross-track prerequisite remains; SA96-GATE-BLK-002 is the outstanding quality-baseline decision.**

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

Completed history (SA92/SA84/SA86/SA93/SA94/SA95/SA96-T1/T2/SA97/SA98/SA99/SA100/SA91/TP1/TP2/TP3a,
Finding 1, all four GATEs) lives in [CHANGELOG.md](../../CHANGELOG.md); only open work is shown below.

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92/SA84/SA86 ✓ (dev tickets)      SA94/SA88b/SA86/SA95 ✓ (dev tickets)    Finding 1 ✓ (SA89a+SA89b)
SA96-T1 ── module sweep ✓            SA96-T2 ── module sweep ✓               GATE-lint/typecheck/check/quality ✓
SA97 ✓ + SA99 ✓ (audit remed.)      SA98 ✓ (sanitizer consolidation)         SA91 ✓ (parallel loop, non-gating)
TP2b ⧗ → TP4 (off crit.; TP1/TP2 ✓)   TP3a ✓ → TP3b (E2E concurrency;          SA93 ✓ (e2e in green-gate)
 (test-parallelization; off crit.)     rebalanced from Track 1; off crit.)    SA100 ✓ (TA58/TA59 theme preflight)
                       └─────────────────────┬───────────────────────────────────────┘
                                             ▼   (all release inputs ✓: SA96-T1, SA96-T2, SA93;
                                                  the two TP chains run in parallel, off the critical
                                                  path and gate-neutral; Track 3 owns the join when idle)
        SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93 ✓
                       ▼                        (blocked: SA96-GATE-BLK-002 — quality baseline has 19 regressions)
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE  (human-only)
```

**Open work only:** Track 1 `TP2b` (validation-blocked) → `TP4`, Track 2 `TP3b` (after completed `TP3a`), and the release join
`SA96-GATE → SA96-PUBLISH`. The two TP chains run in parallel with no source-file overlap
(`Makefile`/`pyproject.toml` vs `scripts/test_e2e.sh` + `quickscale_cli/tests/test_e2e_development_workflow.py`); both are off the release critical path and
must not regress any gate's pass/fail set or coverage thresholds. `TP4` is docs-only and lands after
`TP1` (done) and `TP3b` (Track 2) merge to `v87`.

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** is complete and its dependency is met; **SA96-GATE** is the next release-path step, followed by **SA96-PUBLISH**. **SA98** and **SA100** are complete independent audit-remediation tickets; neither blocks SA96-GATE. SA97 and SA99 are also complete (see [CHANGELOG.md](../../CHANGELOG.md)).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). Both module sweeps and SA93 are complete, so SA96-GATE is the next release-path step. SA93's cross-track blockers are resolved; component Core/CLI E2E, exact local `make ci-e2e`, and the two hosted jobs are green. SA93-EVID-001 records the verified hosted run metadata.

### Track readiness (2026-07-19)

- **Track 1 — ACTIVE on the TP (test-parallelization) suite; TP2b closeout is blocked and TP4 remains pending.** All prior release tickets closed (SA92, SA84, SA86, SA96-T1) and both audit-remediation tickets — **SA97** (arch Finding 9 test-plumbing half) and **SA99** (arch Finding 7 devtools→ruff/mypy) — completed 2026-07-17. **TP1** (static-gate fan-out) and **TP2** (unit xdist) were accepted 2026-07-18; TP2 retains the waived/non-blocking pre-existing core coverage finding. **TP2b** has implementation fixes, focused structural/behavioral evidence, and bounded-xdist evidence, but **QG-TP2B-001** blocks the exact post-fix default and required-backups validation; **CR-TP2B-001/002** were resolved by independent change-review pass 2. **TP4** (AI fast-loop docs) remains pending. The E2E sub-chain **TP3a/TP3b** was rebalanced to Track 2 (2026-07-18); it is file-disjoint from these (TP3a owns `scripts/test_e2e.sh` plus `quickscale_cli/tests/test_e2e_development_workflow.py`; TP3b retains `scripts/test_e2e.sh` for concurrent-lane orchestration). All Tier 1–2, none on the SA96 release critical path — pure SDLC cycle-time work; must not regress any gate's pass/fail set or coverage thresholds. **TP2b is not clean to close out; no design decision is pending.** Evidence for closed work in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 2 — E2E-concurrency sub-chain; TP3a complete, TP3b remaining.** Release tickets and audit remediation are closed (SA94, SA88b, SA86, SA95, SA96-T2, and SA98; SA97+SA98 close arch-audit Finding 9). Track 2 was idle after SA98 and carries the **TP3a → TP3b** sub-chain, rebalanced off Track 1 to run in parallel. **TP3a** (E2E port-namespacing) is complete and recorded in [CHANGELOG.md](../../CHANGELOG.md); **TP3b** (concurrent Core/CLI E2E lanes) remains. TP3b retains `scripts/test_e2e.sh` for concurrent-lane orchestration and reuses the read-only `_qs_jobs.sh` helpers; there is no source overlap with Track 1's TP work, and the only shared surface is the closeout files, covered by the Merge procedure. Off the release critical path. **Track 2 must not start TP3b or claim integrated CI green until `make ci-e2e` is rerun with more than a 20-minute allowance and the final CLI E2E result is retained** (evidence gap carried from TP3a). No design decision is pending; this is execution evidence only. Evidence for closed work in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 3 — SA93 COMPLETE; SA96-GATE in progress but BLOCKED on quality baseline (SA96-GATE-BLK-002).** Finding 1, all four GATEs, SA91, SA100, and SA93 are complete. SA93's local gate and verified hosted evidence are recorded above; **SA96-GATE is the next release-path step but is not currently clean** — canonical coverage is restored and `make check` exits 0, but `make quality` exits 2 with 9 critical + 10 warning baseline regressions, so the four-command join cannot pass yet. Independent change-review pass 2 returned **STATUS ok** with **SA96-CR-001 (blocking)** and **SA96-CR-002 (advisory)** resolved and no new findings. The user approved merging this blocked checkpoint without claiming SA96-GATE completion; route BLK-002 separately for a quality-remediation versus explicit baseline-reconciliation decision. The PyPI publish (SA96-PUBLISH) remains explicitly excluded from assistant work (human-only). SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004, SA93-REV-005, and SA93-ADV-001..004 remain non-gating advisories.

**Net — all three tracks have assigned work; SA96-GATE has one maintainer decision pending.** Track 1 carries the off-critical-path TP test-parallelization suite, with **TP2b pending/blocked** on exact post-fix validation and final independent re-review, and **TP4** pending; Track 2 carries the rebalanced E2E-concurrency sub-chain, with **TP3a** complete and **TP3b** remaining. Both are off the release critical path and run in parallel with no source-file overlap. Both pre-publish module sweeps and SA93 are complete, so **SA96-GATE** is the next release-path step — coverage is restored and `make check` is green, but the gate is **blocked on SA96-GATE-BLK-002** (`make quality` exit 2 with 9 critical + 10 warning baseline regressions). Independent change-review pass 2 returned **STATUS ok** with **SA96-CR-001 (blocking)** and **SA96-CR-002 (advisory)** resolved and no new findings. The user approved merging this blocked checkpoint without claiming completion; route BLK-002 separately for a quality-remediation versus baseline-reconciliation decision before the join can proceed. Once green, a coding assistant runs the join and reports, then hands off to the human-only **SA96-PUBLISH** step. **SA98** and **SA100** are complete independent audit remediation, while SA97 and SA99 are also complete. No TP2b design decision is pending; the remaining work is validation and independent review. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
