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
1. **SA96-GATE** (green-gate join) — SA93's dependency is met; next release-path step.
2. **SA96-PUBLISH** (staged PyPI publish), deps on SA96-GATE.
3. **Audit remediation status** — SA97+SA98 complete arch-audit Finding 9, SA99 completes Finding 7's cheap sub-item, and SA100 completes tech-audit TA58/TA59; all are independent of the release critical path. See [CHANGELOG.md](../../CHANGELOG.md). Arch Findings 2 and 4 stay deferred with the (unscheduled) teams module — **not ticketed**.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gates and repo-global gates — CLOSED

All per-module restricted-role gates (CRM/SA84, blog/SA83+SA95, forms/SA85, listings/SA86, orgs/SA77, notifications/SA79) and repo-global gates (GATE-lint, GATE-typecheck, GATE-check-suite, GATE-quality, SA91 parallel worker pool), including **SA93** (e2e in the green-gate), are **complete**. Both former cross-track prerequisites (SA84 CRM, SA95 blog) are met. See [CHANGELOG.md](../../CHANGELOG.md).

- [x] **SA93 — Fold the e2e lane into the green-gate definition of done.** `Tier 1 · Track 3 · deps: none remaining (SA84 CRM + SA95 blog prerequisites met)`
  **Closed by hosted evidence (SA93-EVID-001). All 11 prerequisites were resolved and open decisions were zero before closeout.** Initial hosted run [29641299861](https://github.com/Experto-AI/quickscale/actions/runs/29641299861) aborted its generated-project Docker job because the workflow supplied one apply confirmation while the current CLI required two. Workflow-only remediation was published in commit `667396cc` (pipe `y\ny\n`); successful hosted rerun [29641954573](https://github.com/Experto-AI/quickscale/actions/runs/29641954573) on `v87` passed with both jobs green. This does not include any PyPI publish (that is SA96-PUBLISH, human-gated below).

  Implementation, exact local gate, independent review, and all resolved prerequisites are recorded in [CHANGELOG.md §SA93 continuation](../../CHANGELOG.md#sa93-continuation) (local `make ci-e2e` green — 12 stages, 91.90% combined coverage, empty quarantine; blog/CRM cross-track prerequisites met via SA95/SA84). Independent review resolved SA93-REV-002, SA93-REV-003, SA93-REV-004, and SA93-REV-006; SA93-REV-005 remains an unresolved advisory/out-of-scope test gap. The hosted evidence is separate: it owns only the two green hosted jobs and generated-project Docker contract, not the local 12-stage coverage/quarantine result.

  **Closeout evidence (SA93-EVID-001):** Hosted run [29641954573](https://github.com/Experto-AI/quickscale/actions/runs/29641954573) has verified metadata `headBranch=v87`, `headSha=667396cc44ac7c1737c0b7825963c72963bc9fd2`, `event=workflow_dispatch`, `status=completed`, and `conclusion=success`; jobs **Test Generated Project Docker Build** and **Full E2E Tests (PostgreSQL + Playwright)** both succeeded.

  **Advisory (open, non-gating — defer as separate hardening):** SA93-ADV-001 (pytest-10 class-scoped fixture warning in `TestReactThemePnpmIntegration.test_pnpm_install_succeeds`); SA93-ADV-002 (app-init DB access + orgs teardown warning); SA93-ADV-003 (unlabelled worker-pool substage between stages 9–10); SA93-ADV-004 (non-finite `NaN`/`Inf` coverage-threshold overrides fail open).

  *(Acceptance met:* local `make ci-e2e` exits 0 on a fresh clone with its 12-stage/coverage/quarantine evidence; the hosted `e2e.yml` run has both jobs green on `v87` with URL/ref/SHA retained; independent review passes; exit-criteria prose lists the e2e lane.)*
  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Pre-publish verification & release sweep (SA96)

Pre-release re-verification: **SA96-T1 (Track 1) and SA96-T2 (Track 2) module sweeps are complete** — all 12 modules re-verified green in isolation on post-SA92 v87, no regression, empty quarantine. **SA93 is complete and its dependency is met; SA96-GATE is the next release-path step.** See [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA96-GATE — Green-gate join (cross-track).** `Tier 1 · v87 integration · deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93` · *assistant-executable*
  With both module sweeps complete and the SA93 dependency met, on a fresh clone + fresh `migrate` (post-SA92 squash) run until all exit 0 with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`:
  `make check` → `make quality` → `make ci` → `make ci-e2e`. All four green + empty quarantine = publishable (single definition of done, see the exit-criteria above). A coding assistant may run this join and report the result; it stops here and hands off to a human for SA96-PUBLISH.

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE` · **HUMAN-ONLY — do not delegate to an assistant**
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — TP (test-parallelization) suite open

Prior Track 1 tickets are closed — SA92 (migration squash), SA84 (CRM restricted-role), SA86 (listings), **SA96-T1** module sweep, Finding 8, plus the two audit-remediation tickets **SA97** (arch-audit Finding 9 test-plumbing half) and **SA99** (arch-audit Finding 7 devtools→ruff/mypy), both completed 2026-07-17. See [CHANGELOG.md](../../CHANGELOG.md).

Track 1 was idle and has been assigned the **TP (test-parallelization)** suite. Goal: shorten the SDLC feedback loop (and let an AI assistant run partial tests concurrently) by parallelizing the long-running quality gates. Motivation and full analysis: the parallelization audit summarized under *(why →* …*)* on each ticket. **The integration suite is already parallel (SA91, `QS_INTEGRATION_JOBS`)** — these tickets cover the surfaces that are *not* yet parallel: the serial static-gate chain and the un-xdist'd unit suites. **The E2E-concurrency sub-chain (TP3a/TP3b) has been rebalanced to Track 2** (2026-07-18) to run in parallel; it is file-disjoint from the Track 1 tickets here (E2E touches only `scripts/test_e2e.sh`). None are on the SA96 release critical path; they are pure cycle-time improvements and must not regress any existing gate's pass/fail set or coverage thresholds.

- [ ] **TP1 — Fan out the independent static gates in `check_ci_locally.sh`.** `Tier 2 · Track 1 · deps: none`
  `scripts/check_ci_locally.sh` runs stages 2–9 strictly serially, but they share no mutable state and have no data dependency on each other: `make lint` (stage 2), the five repo gates `check-core-compat` / `check-module-core-imports` / `check-manifest-sync` / `check-org-context-primitives` / `check-csrf-exempt` (stages 3–7), `make typecheck` (stage 8), `make test-cov-policy` + `make test-integration-worker-pool` (stage 9). Only the DB-dependent stages 10 (`test-cov`) and 11 (`test-integration`) must stay after them.
  - Launch stages 2–9 as concurrent background jobs, capture each job's exit code and buffered output, `wait` on all, then replay output in a deterministic (declaration) order and fail the script if any job failed. Reuse the existing subshell/`wait`/exit-aggregation pattern from `scripts/_qs_jobs.sh` (`_qs_join_workers`, `_qs_replay_worker_logs`) rather than inventing a new one — source it if practical, or mirror its structure.
  - Preserve the current fail-fast *semantics* at the script level (overall non-zero exit if any gate fails, banner on failure) even though gates now run concurrently rather than short-circuiting. Keep stage numbering/labels legible in the replayed output.
  - Gate the fan-out behind an opt-out env var (e.g. `QS_CI_PARALLEL=0` → current serial behavior) so the serial path remains available for debugging, mirroring how `QS_INTEGRATION_JOBS=1` forces serial in the integration runner.
  - Verify: `make ci` still exits 0 on a clean tree and non-zero when any single gate is broken (inject a lint error, a mypy error, and a manifest-sync drift in separate runs); confirm each failure is attributed to the right gate in the replayed output; confirm wall-clock drops versus serial.
  *(why →* parallelization audit Tier 3 "orchestration" item — 8 independent read-only gates run serially in the pre-push script; safest available speedup, no test-code changes*)*

- [ ] **TP2 — Add `pytest-xdist` and run the unit suites with `-n auto`.** `Tier 2 · Track 1 · deps: none`
  Unit suites (`make test-unit`, core + CLI) run serially; `pytest-xdist` is not installed. Per-test DB isolation already exists (`quickscale_core/tests/conftest.py` → `unique_db_name` / `per_test_db`, `qs_test_<uuid>` databases), so worker-level parallelism is safe for DB-backed unit tests; pure-unit tests are trivially safe.
  - Add `pytest-xdist` to `[tool.poetry.group.dev.dependencies]` in the root `pyproject.toml` (next to `pytest`, `pytest-cov`), then `poetry lock` + `poetry install --with dev`.
  - Add `-n auto` to the `test-unit` core and CLI pytest invocations in the `Makefile` (`test-unit` target, ~lines 303–318). Keep coverage correct under xdist: `pytest-cov` already supports parallel workers via its subprocess hook, but confirm the `--cov` + `--cov-report=xml` outputs still aggregate (xdist workers write to the same coverage data through pytest-cov's combine step — validate, don't assume). Do **not** touch `test-cov` in this ticket (its `--cov-append` phase ordering is handled separately in TP2b).
  - Make the worker count overridable (e.g. honor a `PYTEST_XDIST_AUTO` / explicit `-n` passthrough) so CI can pin it; `-n auto` locally, bounded in CI runners if needed.
  - Verify: `make test-unit` pass/fail set is identical with and without `-n auto` (diff the collected+result set); coverage percentage is unchanged (must still satisfy the CLI `--cov-fail-under=90`); wall-clock drops on a multi-core host.
  *(why →* parallelization audit Tier 2 — unit suites are pure-CPU and near-linearly shrinkable; isolation precondition already met*)*

- [ ] **TP2b — Convert `test-cov` from `--cov-append` phase-ordering to `coverage combine` so it is xdist-safe.** `Tier 2 · Track 1 · deps: TP2`
  `make test-cov` (`Makefile` `test-cov` target, ~lines 362–443) relies on ordered `--cov-append` across Phase 1 (core+CLI) and Phase 2 (backups module), which is not safe to parallelize as-is. Rework to the standard parallel-safe flow: each phase writes an isolated data file (`COVERAGE_FILE` per phase, as the SA91 integration workers already do), then a single `coverage combine` + `coverage report`/`html`/`json` before the Phase 4 policy check (`scripts/check_coverage_policy.py`).
  - Preserve the existing dual-threshold policy (90% equal-weight package mean + 80% per-file) and the `REQUIRE_BACKUPS_COVERAGE` behavior exactly.
  - Only after this lands may `-n auto` be added to the `test-cov` phase invocations (do it in this ticket, guarded/validated).
  - Verify: combined coverage numbers match the pre-change `test-cov` output within rounding on the same tree; `make test-cov REQUIRE_BACKUPS_COVERAGE=1` still enforces the backups requirement; policy check passes/fails identically.
  *(why →* parallelization audit Tier 2 caveat — append ordering blocks xdist on the coverage suite; combine is the standard fix*)*

- [ ] **TP4 — Document the AI-assistant fast partial-test recipes.** `Tier 1 · Track 1 · deps: none · docs-only (review-only closeout)`
  The repo already supports targeted, safe partial runs that an AI assistant should prefer during iteration, but they are underused/undocumented as a coherent workflow: section flags (`make lint -- --core`, `make typecheck -- --cli`, `make test-unit -- --core`), single-module reruns (`make MODULE=<name> test -- --modules`), and bounded integration concurrency (`QS_INTEGRATION_JOBS=<N> make test-integration`).
  - Add a short "Fast feedback loop for AI-assisted / incremental development" subsection to `docs/technical/development.md` (or the closest testing doc): the iterate → pre-merge → E2E-last ladder, the targeted-rerun recipes above, and the new `QS_CI_PARALLEL` (TP1, Track 1) / `QS_E2E_PARALLEL` (TP3b, **Track 2**) knobs once they land (cross-reference, don't block on them — this is the one cross-track reference the rebalance introduces; land TP4 after both TP1 and TP3b merge to `v87`).
  - Verify: every command in the doc runs as written on a clean tree.
  *(why →* parallelization audit Tier 4 — scoped partial runs already exist; the gap is discoverability for the incremental-dev loop*)*

### Track 2 — Module contracts & settings — ASSIGNED the E2E-concurrency sub-chain (TP3a/TP3b)

Prior development tickets closed — SA88b (forms diagnosis), SA86 (listings), SA94 (react-only theme), SA95 (blog fixture-finalizer regression), GATE-lint/typecheck/check-suite, **SA96-T2** module sweep, and **SA98** (sanitizer consolidation; SA97+SA98 close arch-audit **Finding 9**). See [CHANGELOG.md](../../CHANGELOG.md).

Track 2 was idle after SA98 and has been assigned the **E2E-concurrency sub-chain of the TP suite** — TP3a→TP3b, rebalanced off Track 1 (2026-07-18) so the E2E port-namespacing + concurrent-lanes work runs in parallel with Track 1's TP1/TP2/TP2b. Both tickets touch only `scripts/test_e2e.sh` (and reuse the read-only `_qs_jobs.sh` join/replay helpers), so they share no source files with Track 1's TP work — the only overlap is the shared closeout files (`CHANGELOG.md`, `roadmap.md`), which the Merge procedure already reconciles. Off the SA96 release critical path; must not regress any gate's pass/fail set or coverage thresholds.

- [ ] **TP3a — Namespace E2E host ports so lanes/workers no longer collide on 5432/8000.** `Tier 2 · Track 2 · deps: none`
  `scripts/test_e2e.sh` and the generated projects assume fixed host ports (Postgres 5432, app 8000) — the cleanup greps (`:(5432|5433|8000)->`) and the Core→CLI teardown+`sleep 2` exist precisely because two E2E runs cannot coexist. `pytest-docker` already returns a mapped port via `docker_services.port_for("postgres", 5432)` in `quickscale_core/tests/conftest.py`, but the app port and the cleanup logic are still hard-coded.
  - Introduce dynamic/per-lane host-port allocation for the generated project's app server and any test Postgres not managed by pytest-docker; thread the chosen port through the E2E fixtures and any generated-project startup the tests drive. Replace fixed-port cleanup greps with label/name-scoped container cleanup (filter by a per-run container name prefix) so one lane never kills another's containers.
  - Keep the current single-lane behavior working unchanged when only one lane runs.
  - Verify: run two `test_e2e.sh`-style lanes concurrently by hand and confirm via `docker ps` there is no 5432/8000 contention and neither lane tears down the other's containers; single-lane `make test-e2e` still passes.
  *(why →* parallelization audit Tier 1 — fixed host ports are the sole blocker to any E2E concurrency; this is the enabling refactor*)*

- [ ] **TP3b — Run Core-E2E and CLI-E2E as two concurrent lanes in `test_e2e.sh`.** `Tier 2 · Track 2 · deps: TP3a`
  With ports namespaced (TP3a), split the currently-serial Core-E2E → teardown → CLI-E2E flow in `scripts/test_e2e.sh` into two lanes launched concurrently (reuse the `_qs_join_workers`/`_qs_replay_worker_logs` join+replay pattern), aggregate exit codes, and drop the inter-suite `sleep 2` teardown that only existed to free shared ports.
  - Preserve per-lane cleanup traps and the final pass/fail banner + non-zero exit on any lane failure. Keep `--headed`, `--no-cleanup`, `--full` flags working (pass through to both lanes).
  - Gate concurrency behind an opt-out (e.g. `QS_E2E_PARALLEL=0`) for debugging, consistent with TP1.
  - Verify: `make test-e2e` and `make ci-e2e` exit 0 on a clean tree; injecting a failure into only the CLI lane still fails the overall run and is attributed correctly; wall-clock drops versus the serial Core→CLI sequence.
  *(why →* parallelization audit Tier 1 — E2E is the dominant SDLC cost and Core/CLI lanes are independent once ports are namespaced*)*

### Track 3 — Core/CLI plumbing — SA93 complete; SA96-GATE next

arch-audit **Finding 1** is closed (SA89a+SA89b, DR persistence port). All four GATEs, **SA91** (parallel worker pool), and **SA93** (e2e in the green-gate) are complete. SA93's local gate and hosted evidence are recorded in its task block; **SA96-GATE** is the next release-path step. **SA100** (tech-audit TA58/TA59 theme-preflight remediation) is complete — see [CHANGELOG.md](../../CHANGELOG.md). **No cross-track prerequisite or maintainer decision remains.**

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92/SA84/SA86 ✓ (dev tickets)      SA94/SA88b/SA86/SA95 ✓ (dev tickets)    Finding 1 ✓ (SA89a+SA89b)
SA96-T1 ── module sweep ✓            SA96-T2 ── module sweep ✓               GATE-lint/typecheck/check/quality ✓
SA97 ✓ + SA99 ✓ (audit remed.)      SA98 ✓ (sanitizer consolidation)         SA91 ✓ (parallel loop, non-gating)
TP1/TP2/TP2b/TP4                    TP3a → TP3b (E2E concurrency)            SA93 ✓ ── e2e in green-gate
 (test-parallelization; off crit.)   (rebalanced from Track 1; off crit.)    SA100 ✓ (TA58/TA59 theme preflight)
                       ┌─────────────────────┴───────────────────────────────────────┐
                       ▼   (SA98 ✓ / SA100 ✓; both off the release critical path — independent; SA97 ✓ landed)
        SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 + SA96-T2 + SA93 ✓
                       ▼
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE
```

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** is complete and its dependency is met; **SA96-GATE** is the next release-path step, followed by **SA96-PUBLISH**. **SA98** and **SA100** are complete independent audit-remediation tickets; neither blocks SA96-GATE. SA97 and SA99 are also complete (see [CHANGELOG.md](../../CHANGELOG.md)).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). Both module sweeps and SA93 are complete, so SA96-GATE is the next release-path step. SA93's cross-track blockers are resolved; component Core/CLI E2E, exact local `make ci-e2e`, and the two hosted jobs are green. SA93-EVID-001 records the verified hosted run metadata.

### Track readiness (2026-07-18)

- **Track 1 — IN PROCESS on the TP (test-parallelization) suite.** All prior release tickets closed (SA92, SA84, SA86, SA96-T1) and both audit-remediation tickets — **SA97** (arch Finding 9 test-plumbing half) and **SA99** (arch Finding 7 devtools→ruff/mypy) — completed 2026-07-17. Now carries **TP1** (static-gate fan-out), **TP2**/**TP2b** (unit xdist + coverage-combine), and **TP4** (AI fast-loop docs). The E2E sub-chain **TP3a/TP3b** was rebalanced to Track 2 (2026-07-18); it is file-disjoint from these (E2E touches only `scripts/test_e2e.sh`). All Tier 1–2, none on the SA96 release critical path — pure SDLC cycle-time work; must not regress any gate's pass/fail set or coverage thresholds. **Clean to continue.** Evidence for closed work in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 2 — ASSIGNED the E2E-concurrency sub-chain (TP3a→TP3b); clean to start.** Release tickets and audit remediation are closed (SA94, SA88b, SA86, SA95, SA96-T2, and SA98; SA97+SA98 close arch-audit Finding 9). Track 2 was idle after SA98 and now carries **TP3a** (E2E port-namespacing) → **TP3b** (concurrent Core/CLI E2E lanes), rebalanced off Track 1 to run in parallel. Both touch only `scripts/test_e2e.sh` (+ read-only `_qs_jobs.sh` helpers) — no source overlap with Track 1's TP work; the only shared surface is the closeout files, covered by the Merge procedure. Off the release critical path. Evidence for closed work in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 3 — SA93 COMPLETE; SA96-GATE next.** Finding 1, all four GATEs, SA91, SA100, and SA93 are complete. SA93's local gate and verified hosted evidence are recorded above; SA96-GATE is the next release-path step. The PyPI publish (SA96-PUBLISH) remains explicitly excluded from assistant work (human-only). SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004, SA93-REV-005, and SA93-ADV-001..004 remain non-gating advisories.

**Net — all three tracks have assigned work; no maintainer decisions pending.** Track 1 carries the off-critical-path TP test-parallelization suite (TP1/TP2/TP2b/TP4) and Track 2 the rebalanced E2E-concurrency sub-chain (TP3a/TP3b) — both off the release critical path, running in parallel with no source-file overlap. Both pre-publish module sweeps and SA93 are complete. **SA96-GATE** is the next release-path step; a coding assistant may run its four-command join and report the result, then hand off to the human-only **SA96-PUBLISH** step. **SA98** and **SA100** are complete independent audit remediation, while SA97 and SA99 are also complete. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
