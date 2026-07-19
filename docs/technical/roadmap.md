# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [How QuickScale Uses Adaptive](../others/adaptive.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work. Detailed completed implementation history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as [Adaptive](../others/adaptive.md) Tier 1–2; split before implementing if a checklist item is Tier 3.

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
1. **SA101** (quality-baseline remediation, Track 3) → **SA96-GATE** (green-gate join). SA93's dependency is met; SA96-GATE is the release-path join but **blocked** on quality-baseline regressions (SA96-GATE-BLK-002), whose decision is now made (Option A — remediate) and cut as **SA101**. The prior coverage blocker (SA96-GATE-BLK-001) is superseded by the restored canonical coverage evidence.
2. **SA96-PUBLISH** (staged PyPI publish), deps on SA96-GATE.
3. **Audit remediation status** — SA97+SA98 complete arch-audit Finding 9, SA99 completes Finding 7's cheap sub-item, and SA100 completes tech-audit TA58/TA59; all are independent of the release critical path. See [CHANGELOG.md](../../CHANGELOG.md). Arch Findings 2 and 4 stay deferred with the (unscheduled) teams module — **not ticketed**.
4. **2026-07-19 audit-sweep remediation** — the delta pass opened two tech-audit findings (**TA60** frontend-proof-ungated, **TA61** devtools-gates-absent) and promoted arch-audit **Finding 10** (frontend-source specialization). **SA102** (TA61) has landed on Track 1 (see [CHANGELOG.md](../../CHANGELOG.md); TA61 closed). Remaining: **SA103** (TA60 + the matching arch red flag, **Track 1** — rebalanced from Track 3 on 2026-07-19 to run in parallel with SA101) and the staged frontend workstream **SA104 → SA105/SA106** (Finding 10, Track 2). SA103 is a gate-tightening that should land **before the SA96-GATE join re-runs** (per the arch red flag); the SA104 chain is off the release critical path. Arch **Finding 7** stays unscheduled (SA104 shrinks its surface — sequence any tuple-derivation work after it); Findings 2/4 remain **not ticketed** with teams.

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
    - **Decision (2026-07-19; maintainer-approved): Option A — remediate, do not re-baseline.** The 19 regressions are cleared by fixing the offending complexity/dead-code so the code passes the **existing** `scripts/quality_baseline.json`, not by resetting the baseline. Rationale (organic fit with prior decisions): the baseline was already reset wholesale in `76c5cc55` for v87, and both audits flag a *second* silent reset as regression-grandfathering (arch-audit watchlist + open question "Is the quality baseline intended to be shrink-only?"); a fresh re-baseline would contradict the fail-hard principle. Routed as the standalone ticket **SA101** below. If any individual regression proves to be intended (not a real defect), record *that specific exemption* in `decisions.md` with a shrink-only rule rather than a blanket re-baseline — which also answers the arch-audit open question.
  - **Validation, rollback, and re-plan rules:** Execution remains serial and the green-gate definition is unchanged. The coverage requirement is met, but SA96-GATE remains blocked by BLK-002 until its required quality decision and follow-up evidence are complete. The user approved merging this blocked checkpoint without claiming SA96-GATE completion.
  - **Next action:** The quality-baseline decision is made (Option A — remediate; see above). Execute ticket **SA101** to clear the 19 regressions against the unchanged baseline, then re-run the SA96-GATE four-command join. The independent review of the coverage checkpoint is complete and is not a remaining action. `make ci` and `make ci-e2e` must not be represented as run until SA101 lands and the join is re-run.

- [ ] **SA101 — Clear the SA96-GATE-BLK-002 quality-baseline regressions (remediation, Option A).** `Tier 2 · Track 3 · deps: none (feeds SA96-GATE) · on the release critical path` · *assistant-executable*
  Fix the **9 critical + 10 warning** complexity/dead-code regressions reported by `make quality` at `.quickscale/quality_report.md` lines 32–52 so the target exits 0 against the **existing** `scripts/quality_baseline.json`. **Do not** edit `quality_baseline.json`, thresholds, or the quality gate itself — the decision is remediate, not re-baseline (see SA96-GATE-BLK-002 Decision). Each fix is a real complexity/dead-code reduction; if a specific entry is a legitimate intended shape, record a shrink-only exemption in [decisions.md](./decisions.md) for that entry only, with rationale, rather than a blanket reset.
  - Verify: `make quality` exits 0 with no new regressions; `make check` still exits 0 (no behavioral change); scope stays within the flagged functions/files — no source refactor beyond what the report names.
  - On completion, SA96-GATE's only remaining blocker is cleared; hand back to the SA96-GATE four-command join.
  *(why →* SA96-GATE-BLK-002; keeps the v87 quality baseline honest per the fail-hard principle and the arch-audit shrink-only open question*)*

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE` · **HUMAN-ONLY — do not delegate to an assistant**
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — TP (test-parallelization) suite + SA103 frontend-proof gate

Prior Track 1 tickets are closed — SA92 (migration squash), SA84 (CRM restricted-role), SA86 (listings), **SA96-T1** module sweep, Finding 8, the two audit-remediation tickets **SA97** (arch-audit Finding 9 test-plumbing half) and **SA99** (arch-audit Finding 7 devtools→ruff/mypy), and **SA102** (TA61 devtools CI gate — rebalanced here from Track 3, landed 2026-07-19, TA61 closed). See [CHANGELOG.md](../../CHANGELOG.md).

Track 1 was idle and carries the **TP (test-parallelization)** suite plus the rebalanced **SA103** frontend-proof gate. TP goal: shorten the SDLC feedback loop (and let an AI assistant run partial tests concurrently) by parallelizing the long-running quality gates. Motivation and full analysis: the parallelization audit summarized under *(why →* …*)* on each ticket. **The integration suite is already parallel (SA91, `QS_INTEGRATION_JOBS`)**; **TP1** (serial static-gate fan-out) and **TP2** (unit-suite xdist) are complete (see [CHANGELOG.md](../../CHANGELOG.md)), while TP2b implementation and focused evidence are landed — its `Makefile` `test-cov` edits are already merged to v87 — but its closeout is validation-blocked pending independent review. The remaining Track 1 tickets are **SA103** (frontend-proof gate — feeds SA96-GATE, rebalanced from Track 3 on 2026-07-19 to parallelize with SA101; file-disjoint from TP2b/TP4), **TP2b** (make `test-cov` xdist-safe via `coverage combine`), and **TP4** (docs-only AI fast-loop recipes). **The E2E-concurrency sub-chain (TP3a/TP3b) was rebalanced to Track 2** (2026-07-18) and is complete. Only SA103 feeds the release critical path (it tightens the SA96-GATE join and must land before the join re-runs); TP2b/TP4 are pure cycle-time improvements and must not regress any existing gate's pass/fail set or coverage thresholds.

- [ ] **SA103 — Wire the rendered-frontend proof into a blocking gate (TA60 + arch red flag).** `Tier 2 · Track 1 (rebalanced from Track 3, 2026-07-19) · deps: none · feeds SA96-GATE · assistant-executable`
  `make lint-frontend` (render → ESLint+tsc) and `make frontend-proof` (render → pnpm install/build) are the only executable proof the shipped theme renders to buildable frontend code, and both are wired into no gate (`Makefile:691,695`; zero node/pnpm refs in `ci.yml`/`publish.yml`; the e2e docker-build layer compiles the frontend but sits on no publish-*blocking* path). A theme edit introducing a TS/build error can ship to PyPI through a green `publish.yml`.
  - (1) Add a `lint-frontend` job to `ci.yml` (node+pnpm setup → `make lint-frontend`) and add the target to the `check` umbrella / `check_ci_locally.sh` fan-out behind a node-availability guard.
  - (2) Make the publish path depend on the frontend proof — a `frontend-proof` step in `publish.yml`'s `test` job, or convert e2e's `docker-build-test` job into a `workflow_call` dependency of publish.
  - Verify: introduce a deliberate TS error in `Dashboard.tsx.j2` on a branch — the new gate must go red in `make ci` and `ci.yml`; revert.
  - **Landed on Track 1 (rebalanced 2026-07-19):** file-disjoint from Track 1's TP2b (whose `Makefile` `test-cov` edits are already merged to v87) and TP4 (docs-only), from Track 3's SA101 (quality-baseline source), and from the Track 2 frontend chain (`showcase_react` template tree). Runs in parallel with SA101; Track 3 still owns the SA96-GATE join once both land.
  - **Chain (cross-track, non-blocking):** SA104 (Track 2) turns the 60 byte-static `.j2` files into real `.ts`/`.tsx` the repo's ESLint/tsc could gate directly, retiring this finding's structural cause. The two are compatible — fixing SA103 cheaply now is still worth it; do not block SA103 on SA104.
  *(why →* tech-audit TA60 / arch-audit red flag — ungated build/type validity of the generator's frontend artifact*)*

- [ ] **TP2b — Convert `test-cov` from `--cov-append` phase-ordering to `coverage combine` so it is xdist-safe.** `Tier 2 · Track 1 · deps: TP2 · implementation checkpoint 2026-07-18; validation blocked; final independent review pending`
  `make test-cov` (`Makefile` `test-cov` target) now uses isolated phase `COVERAGE_FILE` paths, one explicit `coverage combine` pipeline before the HTML/report/JSON outputs and policy check, guarded xdist defaults, and the `PYTEST_XDIST_WORKERS=0` serial debugging override. The `REQUIRE_BACKUPS_COVERAGE` behavior remains unchanged.
  - Done: review fixes applied; structural and behavioral coverage-policy tests pass (50 policy tests and 10 behavioral tests); bounded two-worker xdist validation produced a 91.90% equal-weight policy mean (core 93.45%, CLI 90.36%, 84 files); the first pre-review exact gate passed.
  - Blocker ledger: **CR-TP2B-001** and **CR-TP2B-002** are resolved by independent change-review pass 2. **QG-TP2B-001** remains medium/blocking, is not waived, and records that the exact default command timed out after 30 minutes at 99% with exit 143; the required-backups command was not reached. Pending recovery commands (both require sufficient runtime; preserve results): `QS_BACKUPS_DB_USER=quickscale_test_role make test-cov` and `QS_BACKUPS_DB_USER=quickscale_test_role make test-cov REQUIRE_BACKUPS_COVERAGE=1`. After both finish, preserve the results and obtain final independent review. No design decision is pending.
  - **Diagnostic evidence (2026-07-19 session; root cause for the QG-TP2B-001 99% stall — investigate/fix later):** A live `make ci-e2e` stage-10 hang on `v87` was inspected mid-run. `Makefile` defaults `PYTEST_XDIST_WORKERS=auto` → `-n auto --dist loadfile`, which spawned **24 xdist workers** for the `test-cov` Phase 1 core+CLI pytest. `ps`/`pstree` showed **all 24 workers idle** in `futex_do_wait`/`poll_schedule_timeout`, while **five workers had each forked a long-lived `poetry lock` subprocess** (≈14 min elapsed, 0% CPU, parked in `ep_poll`). Each `poetry lock` ran in a **distinct generated-project cwd** (`testproject`, `testapp`, `react_auth_always_partial/`, `react_org_shell_routes/`, etc.), i.e. concurrent `poetry lock` invocations from generated-project E2E/apply tests contending on Poetry's lockfile/caches. Stopping the run and retrying with `PYTEST_XDIST_WORKERS=2 QS_BACKUPS_DB_USER=quickscale_test_role make ci-e2e` completed all 12 stages green (Phase 1 4401 passed, coverage 91.90%, Core E2E 35, CLI E2E 29). **This is not the xdist straggler hypothesis** (QG-TP2B-001's prior framing) — the stall is concurrent-Poetry-lock contention triggered by the `auto` worker count, not a slow final worker. TP3b did **not** change stage 10 behavior (`Makefile:68-69` still defaults to `auto`), so the hang can recur. **Follow-up (not yet ticketed):** (a) audit which generated-project tests invoke real `poetry lock` and whether they should mock/subprocess-stub it instead (the CLI already has `_run_poetry_lock` seams — `test_apply_command_extended.py:559-577`); (b) consider a bounded default for `PYTEST_XDIST_WORKERS` in the coverage phase, or a `PYTEST_XDIST_WORKERS=2` recommendation in `make ci-e2e`/`TP4` docs; (c) reproducible diagnostic: `py-spy` or `gdb -p <poetry-pid>` on the stalled `ep_poll` to confirm whether it is a Poetry cache/file lock or an interactive prompt. Track this under TP2b's recovery rather than a new ticket, since it explains QG-TP2B-001's mechanism rather than introducing new scope.
  - Preserve the existing dual-threshold policy (90% equal-weight package mean + 80% per-file) and the `REQUIRE_BACKUPS_COVERAGE` behavior exactly.
  - `-n auto` is now threaded through both `test-cov` phases, while `PYTEST_XDIST_WORKERS=0` remains the serial debugging override.
  - Focused evidence: 50 policy tests, 10 behavioral tests, serial baseline, post-change serial parity, and bounded `PYTEST_XDIST_WORKERS=2` xdist validation passed with a 91.90% equal-weight policy mean (core 93.45%, CLI 90.36%, 84 files). The first pre-review exact gate passed; the post-review exact default timed out after 30 minutes at 99% with exit 143, so the required-backups exact command was not reached. Recovery remains pending for both exact commands above; sufficient runtime and preserved results are required before final independent review.
  *(why →* parallelization audit Tier 2 caveat — append ordering blocks xdist on the coverage suite; combine is the standard fix*)*

- [ ] **TP4 — Document the AI-assistant fast partial-test recipes.** `Tier 1 · Track 1 · deps: none · docs-only (review-only closeout)`
  The repo already supports targeted, safe partial runs that an AI assistant should prefer during iteration, but they are underused/undocumented as a coherent workflow: section flags (`make lint -- --core`, `make typecheck -- --cli`, `make test-unit -- --core`), single-module reruns (`make MODULE=<name> test -- --modules`), and bounded integration concurrency (`QS_INTEGRATION_JOBS=<N> make test-integration`).
  - Add a short "Fast feedback loop for AI-assisted / incremental development" subsection to `docs/technical/development.md` (or the closest testing doc): the iterate → pre-merge → E2E-last ladder, the targeted-rerun recipes above, and the landed `QS_CI_PARALLEL` (TP1, Track 1) / `QS_E2E_PARALLEL` (TP3b, **Track 2**) knobs (cross-reference, don't block on them — this is the one cross-track reference the rebalance introduces; land TP4 after both TP1 and TP3b merge to `v87`).
  - Verify: every command in the doc runs as written on a clean tree.
  *(why →* parallelization audit Tier 4 — scoped partial runs already exist; the gap is discoverability for the incremental-dev loop*)*

### Track 2 — Module contracts & settings — E2E-concurrency sub-chain (TP3a ✓ → TP3b ✓)

Prior development tickets closed — SA88b (forms diagnosis), SA86 (listings), SA94 (react-only theme), SA95 (blog fixture-finalizer regression), GATE-lint/typecheck/check-suite, **SA96-T2** module sweep, and **SA98** (sanitizer consolidation; SA97+SA98 close arch-audit **Finding 9**). See [CHANGELOG.md](../../CHANGELOG.md).

Track 2 was idle after SA98 and carried the **E2E-concurrency sub-chain of the TP suite** — TP3a→TP3b, rebalanced off Track 1 (2026-07-18) so the E2E port-namespacing + concurrent-lanes work ran in parallel with Track 1's TP1/TP2/TP2b. **TP3a (E2E port-namespacing) and TP3b (concurrent Core/CLI E2E lanes) are complete — see [CHANGELOG.md](../../CHANGELOG.md);** TP3a delivered port-namespacing in `scripts/test_e2e.sh` plus `quickscale_cli/tests/test_e2e_development_workflow.py`; TP3b extends `scripts/test_e2e.sh` for concurrent-lane orchestration and modifies shared `_qs_jobs.sh` join/replay helper behavior. TP3b also shares `Makefile` with Track 1 TP2b for maintained harness wiring. The existing pre-merge `v87` synchronization procedure governs these seams; other source files remain disjoint, and the shared closeout files (`CHANGELOG.md`, `roadmap.md`) remain covered by the Merge procedure. Off the SA96 release critical path; no gate's pass/fail set or coverage threshold changed.

#### Frontend-theme de-specialization (arch-audit Finding 10 — SA104 → SA105/SA106)

The 2026-07-19 arch pass promoted **Finding 10** (`frontend-source-generation-specialized`) to the top-ranked finding: the `showcase_react` theme bakes project identity and the module universe into user-editable frontend *source* at generation time (74 theme files; 60 are byte-static yet carry `.j2` names + `{% raw %}` wrappers; the module universe is hand-synced across ≥5 stations), duplicating facts the `window.__QUICKSCALE__` runtime config seam already delivers per request. Consequences: every generated frontend is a unique source tree, migration is a per-file merge procedure instead of a copy, and every frontend-visible module adds an entry to each of the ≥5 stations (billing shipped flag-only to skip the tax). This is the frontend counterpart to Track 2's SA94 react-only work, so it lands here. The recommended fix is **Option 1, staged** — do not add a second injection mechanism; extend the existing `window.__QUICKSCALE__` seam and adopt the generator's existing verbatim-copy path (`_theme_non_jinja_emitted_paths`). Off the SA96 release critical path; must not regress any gate or coverage threshold. **File ownership vs. Track 1's TP work:** this workstream owns the `quickscale_core` generator + `showcase_react` template tree only — no overlap with the CI/Makefile surfaces SA102/SA103 touch, so it runs fully in parallel.

- [ ] **SA104 — Stage 1: move byte-static theme files onto the verbatim-copy path.** `Tier 2 · Track 2 · deps: none · safe now (byte-identical) · assistant-executable`
  Mechanical, semantics-preserving: take the ~60 zero-Jinja `.j2` theme files under `frontend/src`, drop the `.j2` suffix and the `{% raw %}` wrappers, and route them through the generator's existing non-Jinja copy path (`_theme_non_jinja_emitted_paths`, `quickscale_core/src/quickscale_core/generator/generator.py:110-146`). Emitted bytes are unchanged — the **SA90 emission-parity fixture is the proof**: it must stay green (only the mapping paths rebase; if any emitted byte changes, stop — the file was not actually static). Large mechanical multi-file edit, single concern (Tier 2, not Tier 3): the ~60 files are one mechanical repeat, not independent objectives.
  - Value even alone: these become real `.ts`/`.tsx` files the repo's ESLint/tsc can parse, making SA103's gate cover them directly and closing census-row-20's structural cause.
  - Verify: SA90 parity fixture green (byte-identical emission); a two-project diff of `frontend/src` for the now-static files shows zero differences; generated project still boots (`test_generated_project_runtime.py`).
  *(why →* arch-audit Finding 10 stage 1 — de-duplicate byte-static source out of the per-project specialization surface*)*

- [ ] **SA105 — Stage 2a: de-specialize the module-availability surface via runtime config.** `Tier 2 · Track 2 · deps: SA104 + maintainer decision (dormant files) · assistant-executable after decision`
  Remove the generation-time narrowing of the module universe: make the `QuickScaleModules` TS interface all-modules-optional (flags default `false` when a module is absent — the Django `INSTALLED_APPS` ladder already emits runtime truth into `window.__QUICKSCALE__`), and convert `main.tsx`'s social-conditional imports into unconditional imports with **flag-gated routes**. Removes the src-side module stations (`useModules.ts.j2` tuples, `main.tsx` conditionals) so a new frontend-visible module no longer edits them.
  - **Blocking maintainer decision:** this makes unselected modules' pages exist as inert, flag-gated files in generated trees. If accepted → proceed. If rejected → fall back to Finding 10 **Option 3** (ownership-manifest overlay, extends Finding 7) and re-scope this ticket. *Record the decision in [decisions.md](./decisions.md) before implementing.*
  - Verify: generate projects with different module sets — the module-availability files are byte-identical across them; dormant module pages tree-shake/lazy-load and do not render when the flag is false; ESLint/tsc (via SA103) green.
  *(why →* arch-audit Finding 10 stage 2, module half — collapse the ≥5 hand-synced module stations onto the existing runtime seam*)*

- [ ] **SA106 — Stage 2b: de-specialize project identity via runtime config.** `Tier 2 · Track 2 · deps: SA104 · assistant-executable`
  Replace generation-baked project identity in frontend source with reads from the existing runtime seam: `Sidebar.tsx`/`Dashboard.tsx` "Welcome to {{ project_name }}" JSX → `window.__QUICKSCALE__.projectName` (already injected at `templates/index.html.j2:14-15`); confine remaining Jinja specialization to the Django-side templates and (at most) `package.json`. After this, `frontend/src` is project-agnostic and byte-identical across projects on the same theme version, so migration becomes "copy user-owned dirs, rebuild."
  - Independent of SA105's product decision; both depend only on SA104 and are largely file-disjoint (SA105: `useModules`/`main.tsx`; SA106: `Sidebar`/`Dashboard`/`package.json`) — order either way within the track.
  - Verify: two-project `frontend/src` diff shows zero identity-bearing differences; generated project renders the correct project name from runtime config; boot smoke + SA103 gate green.
  *(why →* arch-audit Finding 10 stage 2, identity half — stop double-encoding `projectName` in source*)*

### Track 3 — Core/CLI plumbing — SA93 complete; SA96-GATE next

arch-audit **Finding 1** is closed (SA89a+SA89b, DR persistence port). All four GATEs, **SA91** (parallel worker pool), and **SA93** (e2e in the green-gate) are complete. SA93's local gate and hosted evidence are recorded in its task block; **SA96-GATE** is the next release-path step. **SA100** (tech-audit TA58/TA59 theme-preflight remediation) is complete — see [CHANGELOG.md](../../CHANGELOG.md). **No cross-track prerequisite remains; the SA96-GATE-BLK-002 quality-baseline decision is made (Option A — remediate), cut as ticket SA101 on this track, which then unblocks the SA96-GATE join.**

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

**CI-gate remediation from the 2026-07-19 sweep — both tickets now on Track 1.** Two audit findings landed on the CI/release plumbing, and both were rebalanced off this track to run in parallel with SA101. **SA102** (TA61, trivial) landed on Track 1 on 2026-07-19 (TA61 closed). **SA103** (TA60, frontend-proof gate) was **rebalanced to Track 1 on 2026-07-19**: with TP2b's `Makefile` `test-cov` edits already merged to v87, SA103's files (`ci.yml`/`publish.yml`/`Makefile` umbrellas + `scripts/check_ci_locally.sh`) are file-disjoint from all live Track 1 work, so it parallelizes SA101 instead of queuing behind it here. Track 3 retains **SA101** and still owns the SA96-GATE join once both feeders land. SA103 **must land before the SA96-GATE four-command join re-runs** since it tightens what "green" means.

### Dependency & parallelization overview

Completed history (SA92/SA84/SA86/SA93/SA94/SA95/SA96-T1/T2/SA97/SA98/SA99/SA100/SA91/TP1/TP2/TP3a/TP3b,
Finding 1, all four GATEs) lives in [CHANGELOG.md](../../CHANGELOG.md); only open work is shown below.

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92/SA84/SA86 ✓ (dev tickets)      SA94/SA88b/SA86/SA95 ✓ (dev tickets)    Finding 1 ✓ (SA89a+SA89b)
SA96-T1 ── module sweep ✓            SA96-T2 ── module sweep ✓               GATE-lint/typecheck/check/quality ✓
SA97 ✓ + SA99 ✓ (audit remed.)      SA98 ✓ (sanitizer consolidation)         SA91 ✓ (parallel loop, non-gating)
SA102 ✓ (devtools CI gate, TA61)    TP3a ✓ → TP3b ✓ (E2E concurrency;        SA93 ✓ (e2e in green-gate)
SA103 ── frontend-proof gate          rebalanced from Track 1; off crit.)    SA100 ✓ (TA58/TA59 theme preflight)
  (TA60/red flag; feeds SA96-GATE;   SA104 ── FE static-source move (Fin.10
  rebalanced from Track 3 to           stage 1; safe now, byte-identical)     SA101 ── clear BLK-002 quality
  parallelize SA101; node-gated,     ├─ SA105 ── module de-spec (2a;            regressions (Option A: remediate)
  file-disjoint from TP2b/TP4)       │    deps SA104 + dormant-files decision)   feeds SA96-GATE; on crit. path
TP2b ⧗ → TP4 (off crit.; TP1/TP2 ✓)  └─ SA106 ── identity de-spec (2b; deps SA104)
                       └─────────────────────┬───────────────────────────────────────┘
                                             ▼   (all release inputs ✓: SA96-T1, SA96-T2, SA93;
                                                  the TP + frontend chains run in parallel, off the
                                                  critical path and gate-neutral; Track 3 owns the join)
        SA101 (Track 3) ── clear BLK-002 quality regressions (Option A: remediate, no re-baseline) ┐ both
        SA103 (Track 1) ── frontend-proof gate (land before the join re-runs; parallelizes SA101)  ┘ feed
                       ▼
        SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93 ✓ + SA101 (+ SA103 tightens the gate)
                       ▼                        (blocked: SA96-GATE-BLK-002 — quality baseline has 19 regressions; decision made, SA101 clears it)
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE  (human-only)
```

**Open work only:** Track 1 `SA103` (frontend-proof gate — rebalanced from Track 3, feeds SA96-GATE) + `TP2b` (validation-blocked) → `TP4`, Track 2's frontend chain `SA104 → SA105/SA106` (arch Finding 10), Track 3 `SA101` (clears BLK-002; on the critical path), and the release join
`SA96-GATE → SA96-PUBLISH`. The frontend chain (SA104+) owns the `quickscale_core` generator + `showcase_react` template tree only, disjoint from the TP work and the SA103 CI surfaces, so the remaining workstreams run concurrently. All of TP and the frontend chain are off the release critical path; **SA103 feeds the gate** (arch red flag — land before the SA96-GATE join re-runs) and runs in parallel with SA101. None may regress any gate's pass/fail set or coverage thresholds. `TP4` is docs-only and unblocked (TP1 done, TP3b merged to `v87`); it remains pending.

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** is complete and its dependency is met; the remaining critical-path chain is **SA101** (clear the BLK-002 quality regressions, Track 3) → **SA96-GATE** (green-gate join) → **SA96-PUBLISH** (human-only). **SA103** (frontend-proof gate, Track 1) is the parallel gate-tightener that must also land before the join re-runs, but runs concurrently with SA101 rather than serially behind it. **SA98** and **SA100** are complete independent audit-remediation tickets; neither blocks SA96-GATE. SA97, SA99, and SA102 are also complete (see [CHANGELOG.md](../../CHANGELOG.md)).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). Both module sweeps and SA93 are complete, so SA96-GATE is the next release-path step. SA93's cross-track blockers are resolved; component Core/CLI E2E, exact local `make ci-e2e`, and the two hosted jobs are green. SA93-EVID-001 records the verified hosted run metadata.

### Track readiness (2026-07-19)

- **Track 1 — ACTIVE; carries the release-feeding SA103 alongside the blocked TP2b and pending TP4.** **Rebalance (2026-07-19):** two CI-gate tickets moved here from Track 3 — **SA102** (TA61 devtools CI gate, Tier 1) **landed** (TA61 closed; see [CHANGELOG.md](../../CHANGELOG.md)), and **SA103** (TA60 frontend-proof gate, Tier 2) was moved here to parallelize with Track 3's SA101 now that TP2b's `Makefile` `test-cov` edits are already merged to v87, leaving SA103 file-disjoint from all live Track 1 work (TP2b/TP4). SA103 **feeds SA96-GATE** and must land before the join re-runs; it is the one release-critical item on this track. **TP1** and **TP2** were accepted 2026-07-18; **TP2b** remains validation-blocked by **QG-TP2B-001** pending exact post-fix default and required-backups validation plus final independent review; **TP4** remains pending (docs-only, unblocked). The E2E sub-chain **TP3a/TP3b** was rebalanced to Track 2 and is complete. TP2b/TP4 are off the SA96 release critical path and must not regress any gate's pass/fail set or coverage thresholds. Evidence for closed work is in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 2 — E2E-concurrency sub-chain complete (TP3a ✓ → TP3b ✓) + the arch Finding 10 frontend chain (SA104 → SA105/SA106).** Release tickets and audit remediation are closed (SA94, SA88b, SA86, SA95, SA96-T2, and SA98; SA97+SA98 close arch-audit Finding 9). Track 2 carries the completed **TP3a → TP3b** sub-chain (rebalanced off Track 1) plus the newly-cut **frontend-theme de-specialization** workstream (arch Finding 10, the frontend counterpart to this track's SA94 react-only work): **SA104** (stage 1, byte-static source move — safe now, SA90-fixture-verified), then **SA105** (stage 2a, module de-spec — deps SA104 + a maintainer dormant-files decision) and **SA106** (stage 2b, identity de-spec — deps SA104). **TP3a** delivered E2E port-namespacing and **TP3b** delivered concurrent Core/CLI E2E lanes; TP3b modifies shared `_qs_jobs.sh` helper behavior and shares `Makefile` with Track 1 TP2b for maintained harness wiring. The existing pre-merge `v87` synchronization procedure governs these seams, while other source files remain disjoint. The frontend chain owns the `quickscale_core` generator + `showcase_react` template tree, with no source overlap with the TP work, Track 1, or Track 1's SA103 CI surfaces, so the remaining workstreams run in parallel (only the closeout files are shared, covered by the Merge procedure). All off the release critical path; must not regress any gate or coverage threshold. **SA105 has a pending maintainer decision** (dormant module files in generated trees — record in decisions.md before implementing). Evidence for closed work in [CHANGELOG.md](../../CHANGELOG.md).
 - **Track 3 — SA93 COMPLETE; SA96-GATE blocked on SA96-GATE-BLK-002, now with the decision made and SA101 ready to execute.** Finding 1, all four GATEs, SA91, SA100, and SA93 are complete. SA93's local gate and verified hosted evidence are recorded above; **SA96-GATE is the next release-path step but is not currently clean** — canonical coverage is restored and `make check` exits 0, but `make quality` exits 2 with 9 critical + 10 warning baseline regressions, so the four-command join cannot pass yet. Independent change-review pass 2 returned **STATUS ok** with **SA96-CR-001 (blocking)** and **SA96-CR-002 (advisory)** resolved and no new findings. **The maintainer decision on BLK-002 is made (2026-07-19): Option A — remediate against the existing baseline, do not re-baseline** — cut as the standalone assistant-executable ticket **SA101** (Track 3, on the critical path). Track 3 is therefore hand-off-ready on the release path: execute SA101, then (once the parallel SA103 has also landed) re-run the SA96-GATE join, which this track owns. **The 2026-07-19 audit-sweep CI-gate tickets were rebalanced off this track to Track 1** — SA102 landed, and SA103 (frontend-proof gate) now parallelizes SA101 rather than queuing behind it here; both still feed SA96-GATE. The PyPI publish (SA96-PUBLISH) remains explicitly excluded from assistant work (human-only). SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004, SA93-REV-005, and SA93-ADV-001..004 remain non-gating advisories.


**Net — all three tracks have assigned work; the 2026-07-19 audit sweep added five tickets (SA102 landed + SA103 rebalanced onto Track 1, SA104→SA105/SA106 on Track 2) with one pending maintainer decision on SA105 (dormant frontend files).** Track 1 carries the release-feeding **SA103** (frontend-proof gate, rebalanced from Track 3 to parallelize SA101) plus the off-critical-path TP test-parallelization suite, with **TP2b pending/blocked** on exact post-fix validation and final independent re-review and **TP4** pending; Track 2 carries the completed E2E-concurrency sub-chain (**TP3a** and **TP3b** complete) plus the new arch-Finding-10 frontend chain (**SA104** safe-now, then **SA105/SA106**); Track 3 carries the critical-path **SA101**. Both pre-publish module sweeps and SA93 are complete, so **SA96-GATE** is next but remains **blocked on SA96-GATE-BLK-002** until SA101 remediates the existing baseline; **SA103 also feeds SA96-GATE** and must land before the join reruns, running concurrently with SA101. **SA98**, **SA100**, SA97, SA99, and SA102 are landed; no TP2b design decision is pending. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
