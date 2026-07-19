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
1. **SA96-GATE** (green-gate join, Track 3) — next pending Track 3/release-path task. Both module sweeps (SA96-T1/T2), SA93, SA103, and **SA101** are complete. SA101 closed out (`make check` exit 0 — 6,943/86/12/0; independent change-review STATUS ok, confidence 94, no findings). SA96-GATE's only remaining blocker is cleared; the four-command join can now re-run. The prior coverage blocker (SA96-GATE-BLK-001) is superseded by the restored canonical coverage evidence.
2. **SA96-PUBLISH** (staged PyPI publish), deps on SA96-GATE.
3. **Audit remediation status** — SA97+SA98 complete arch-audit Finding 9, SA99 completes Finding 7's cheap sub-item, and SA100 completes tech-audit TA58/TA59; all are independent of the release critical path. See [CHANGELOG.md](../../CHANGELOG.md). Arch Findings 2 and 4 stay deferred with the (unscheduled) teams module — **not ticketed**.
4. **2026-07-19 audit-sweep remediation** — the delta pass opened two tech-audit findings (TA60 frontend-proof-ungated, TA61 devtools-gates-absent) and promoted arch-audit **Finding 10** (frontend-source specialization). **SA102** (TA61) and **SA103** (TA60 + the matching arch red flag) both landed on Track 1 and are closed — see [CHANGELOG.md](../../CHANGELOG.md); TA60/TA61 and arch red-flag row 20 are all closed. The staged frontend workstream **SA104 → SA105/SA106** (Finding 10, Track 2) — **SA104 is complete** (57 static files converted; review STATUS ok; SA104-CR-001 resolved). The SA104 chain is off the release critical path. Arch **Finding 7** stays unscheduled (SA104 shrinks its surface — sequence any tuple-derivation work after it); Findings 2/4 remain **not ticketed** with teams.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gates and repo-global gates — CLOSED

All per-module restricted-role gates (CRM/SA84, blog/SA83+SA95, forms/SA85, listings/SA86, orgs/SA77, notifications/SA79) and repo-global gates (GATE-lint, GATE-typecheck, GATE-check-suite, GATE-quality, SA91 parallel worker pool), including **SA93** (e2e in the green-gate), are **complete** — see [CHANGELOG.md §SA93 continuation](../../CHANGELOG.md#sa93-continuation) for the local `make ci-e2e` gate and the verified hosted evidence (SA93-EVID-001). Both former cross-track prerequisites (SA84 CRM, SA95 blog) are met. Non-gating advisories SA93-REV-005 and SA93-ADV-001..004 remain deferred (tracked in the Track 3 readiness bullet).

### Pre-publish verification & release sweep (SA96)

Pre-release re-verification: **SA96-T1 (Track 1) and SA96-T2 (Track 2) module sweeps are complete** — all 12 modules re-verified green in isolation on post-SA92 v87, no regression, empty quarantine. **SA93 is complete and its dependency is met; SA96-GATE is the next release-path step.** See [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA96-GATE — Green-gate join (cross-track).** `Tier 1 · v87 integration · deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93 ✓ + SA103 ✓ + SA101 ✓` · *assistant-executable*
  With both module sweeps complete, the SA93 dependency met, and the SA103 frontend-proof gate live, on a fresh clone + fresh `migrate` (post-SA92 squash) run until all exit 0 with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`:
  `make check` → `make quality` → `make ci` → `make ci-e2e`. All four green + empty quarantine = publishable (single definition of done, see the exit-criteria above). A coding assistant may run this join and report the result; it stops here and hands off to a human for SA96-PUBLISH.
  - **Coverage evidence (met — supersedes `SA96-GATE-BLK-001`):** canonical coverage 6,026/6,670 = 90.34% (orchestration 745/1,011 = 73.69%), focused authored tests 127 passed, Ruff/MyPy green, `make check` exit 0, empty quarantine. Implementation was five new test modules only — no source/config/baseline/threshold changes. Detail in [CHANGELOG.md](../../CHANGELOG.md).
  - **Checkpoint `SA96-GATE-BLK-002` (2026-07-19; resolved by SA101):** `make quality` had exited 2 with **9 critical + 10 warning baseline regressions** at `.quickscale/quality_report.md` lines 32–52. These were unrelated to the five authored test modules. This blocker was preserved and routed as the separately approved remediation task SA101, which resolved all 19 regressions against the unchanged baseline per Option A (remediate, no re-baseline) — no baselines, thresholds, source, or config were changed in this checkpoint.
    - **Decision (2026-07-19; maintainer-approved): Option A — remediate, do not re-baseline.** The 19 regressions were cleared by fixing the offending complexity/dead-code so the code passes the **existing** `scripts/quality_baseline.json`, not by resetting the baseline. Rationale (organic fit with prior decisions): the baseline was already reset wholesale in `76c5cc55` for v87, and both audits flagged a *second* silent reset as regression-grandfathering (arch-audit watchlist + open question "Is the quality baseline intended to be shrink-only?"); a fresh re-baseline would have contradicted the fail-hard principle. Routed as the standalone ticket **SA101** below. No individual regression proved to be intended, so the shrink-only rule stands without exemptions — which also answers the arch-audit open question.
  - **Validation, rollback, and re-plan rules:** Execution remained serial and the green-gate definition unchanged. The coverage requirement was met, but SA96-GATE was blocked by BLK-002 until its required quality decision and follow-up evidence were complete. The user approved merging this blocked checkpoint without claiming SA96-GATE completion.
  - **Next action (completed):** SA101 was completed — `make check` exit 0 (6,943/86/12/0), independent change-review STATUS ok (confidence 94, no findings). The 19 regressions were cleared against the unchanged baseline per Option A. The SA96-GATE four-command join is the sole next release-path action and has not been re-run.

- [x] **SA101 — Clear the SA96-GATE-BLK-002 quality-baseline regressions (remediation, Option A).** `Tier 2 · Track 3 · deps: none (feeds SA96-GATE) · on the release critical path` · *assistant-executable — complete*
  **Closeout evidence (2026-07-19):** `make check` exit 0 — 6,943 passed, 86 skipped, 12 deselected, zero failures; core 90.36%, CLI 90.49%, integration aggregate 94.41%. Independent full change-review returned `STATUS: ok`, confidence 94, no blocking or advisory findings. Worktree remained clean throughout. Known BYPASSRLS-dependent skips are pre-existing. `make ci` and `make ci-e2e` were not run. With SA101 validated and SA103's feeder condition met, SA96-GATE's only remaining blocker is cleared; the SA96-GATE four-command join is the next pending Track 3/release-path step.
  - Implementation cleared all 19 baseline regressions (9 critical + 10 warning) against the unchanged `scripts/quality_baseline.json` per the Option A decision — nine serial behavior-preserving phases (ledger 19→0). `make quality` exit 0. CRM/forms migration compaction proven byte-parity (SHA-256-matched). Plan-review pass 2 `STATUS: ok`. `SA101-VAL-001` resolved via option (a): restricted-role CRM/forms failures confirmed pre-existing on clean pre-SA101, not caused by compaction. Detail in [CHANGELOG.md](../../CHANGELOG.md).
  *(why →* SA96-GATE-BLK-002; keeps the v87 quality baseline honest per the fail-hard principle and the arch-audit shrink-only open question*)*

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE` · **HUMAN-ONLY — do not delegate to an assistant**
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — TP (test-parallelization) suite

Prior Track 1 tickets are closed — SA92 (migration squash), SA84 (CRM restricted-role), SA86 (listings), **SA96-T1** module sweep, Finding 8, the two audit-remediation tickets **SA97** (arch-audit Finding 9 test-plumbing half) and **SA99** (arch-audit Finding 7 devtools→ruff/mypy), **SA102** (TA61 devtools CI gate), and **SA103** (TA60 + arch red-flag row 20 frontend-proof gate — rebalanced here from Track 3, landed 2026-07-19). See [CHANGELOG.md](../../CHANGELOG.md).

Track 1 was idle and carries the **TP (test-parallelization)** suite. TP goal: shorten the SDLC feedback loop (and let an AI assistant run partial tests concurrently) by parallelizing the long-running quality gates. Motivation and full analysis: the parallelization audit summarized under *(why →* …*)* on each ticket. **The integration suite is already parallel (SA91, `QS_INTEGRATION_JOBS`)**; **TP1** (serial static-gate fan-out), **TP2** (unit-suite xdist), and **TP2b** (xdist-safe coverage phases) are complete (see [CHANGELOG.md](../../CHANGELOG.md)). The remaining Track 1 ticket is **TP4** (docs-only AI fast-loop recipes). **The E2E-concurrency sub-chain (TP3a/TP3b) was rebalanced to Track 2** (2026-07-18) and is complete. TP4 is a pure cycle-time improvement, off the release critical path, and must not regress any existing gate's pass/fail set or coverage thresholds.

- [x] **TP2b — Convert `test-cov` from `--cov-append` phase-ordering to `coverage combine` so it is xdist-safe.** `Tier 2 · Track 1 · deps: TP2 · completed 2026-07-19`
  `make test-cov` (`Makefile` `test-cov` target) uses isolated phase `COVERAGE_FILE` paths, one explicit `coverage combine` pipeline before the HTML/report/JSON outputs and policy check, guarded xdist defaults, and the `PYTEST_XDIST_WORKERS=0` serial debugging override. The `REQUIRE_BACKUPS_COVERAGE` behavior remains unchanged. All findings resolved — **CR-TP2B-001**, **CR-TP2B-002** (change-review findings), and **QG-TP2B-001** (quality-gate timeout) closed by independent review. Final change-review returned **STATUS ok** (confidence 94); no blocking findings remain.
  - **Accepted evidence (both exact commands green, 2026-07-19):** `QS_BACKUPS_DB_USER=quickscale_test_role make test-cov` exit 0; `QS_BACKUPS_DB_USER=quickscale_test_role make test-cov REQUIRE_BACKUPS_COVERAGE=1` exit 0. Each run: **4,536 core/CLI passed, 323 backups passed, 2 skipped** (backups policy); coverage combine/report/JSON/policy succeeded; **92.88% equal-weight package mean** (core 95.27%, CLI 90.49%); **all 90 files ≥80%**; default 24 `auto` workers, no stall.
  - **Non-blocking advisory — concurrent Poetry-lock contention:** The prior QG-TP2B-001 timeout (24-worker `auto` xdist with concurrent generated-project `poetry lock` invocations) was diagnosed as concurrent-Poetry-lock contention, not an xdist straggler. This can recur under the default `auto` worker count but **did not recur** in the accepted runs. No TP2b blocker remains.

- [ ] **TP4 — Document the AI-assistant fast partial-test recipes.** `Tier 1 · Track 1 · deps: none · docs-only (review-only closeout)`
  The repo already supports targeted, safe partial runs that an AI assistant should prefer during iteration, but they are underused/undocumented as a coherent workflow: section flags (`make lint -- --core`, `make typecheck -- --cli`, `make test-unit -- --core`), single-module reruns (`make MODULE=<name> test -- --modules`), and bounded integration concurrency (`QS_INTEGRATION_JOBS=<N> make test-integration`).
  - Add a short "Fast feedback loop for AI-assisted / incremental development" subsection to `docs/technical/development.md` (or the closest testing doc): the iterate → pre-merge → E2E-last ladder, the targeted-rerun recipes above, and the landed `QS_CI_PARALLEL` (TP1, Track 1) / `QS_E2E_PARALLEL` (TP3b, **Track 2**) knobs (cross-reference, don't block on them — this is the one cross-track reference the rebalance introduces; land TP4 after both TP1 and TP3b merge to `v87`).
  - Verify: every command in the doc runs as written on a clean tree.
  *(why →* parallelization audit Tier 4 — scoped partial runs already exist; the gap is discoverability for the incremental-dev loop*)*

### Track 2 — Module contracts & settings — E2E-concurrency sub-chain (TP3a ✓ → TP3b ✓)

Prior development tickets closed — SA88b (forms diagnosis), SA86 (listings), SA94 (react-only theme), SA95 (blog fixture-finalizer regression), GATE-lint/typecheck/check-suite, **SA96-T2** module sweep, and **SA98** (sanitizer consolidation; SA97+SA98 close arch-audit **Finding 9**). See [CHANGELOG.md](../../CHANGELOG.md).

Track 2 was idle after SA98 and carried the **E2E-concurrency sub-chain of the TP suite** — TP3a→TP3b, rebalanced off Track 1 (2026-07-18) so the E2E port-namespacing + concurrent-lanes work ran in parallel with Track 1's TP1/TP2/TP2b. **TP3a (E2E port-namespacing) and TP3b (concurrent Core/CLI E2E lanes) are complete — see [CHANGELOG.md](../../CHANGELOG.md);** TP3a delivered port-namespacing in `scripts/test_e2e.sh` plus `quickscale_cli/tests/test_e2e_development_workflow.py`; TP3b extends `scripts/test_e2e.sh` for concurrent-lane orchestration and modifies shared `_qs_jobs.sh` join/replay helper behavior. TP3b also shares `Makefile` with Track 1 TP2b for maintained harness wiring. The existing pre-merge `v87` synchronization procedure governs these seams; other source files remain disjoint, and the shared closeout files (`CHANGELOG.md`, `roadmap.md`) remain covered by the Merge procedure. Off the SA96 release critical path; no gate's pass/fail set or coverage threshold changed.

#### Frontend-theme de-specialization (arch-audit Finding 10 — SA104 → SA105/SA106)

The 2026-07-19 arch pass promoted **Finding 10** (`frontend-source-generation-specialized`) to the top-ranked finding: the `showcase_react` theme bakes project identity and the module universe into user-editable frontend *source* at generation time (74 theme files; a pre-implementation audit census counted 60 that were byte-static yet carried `.j2` names + `{% raw %}` wrappers; the module universe was hand-synced across ≥5 stations), duplicating facts the `window.__QUICKSCALE__` runtime config seam already delivers per request. Consequences: every generated frontend is a unique source tree, migration is a per-file merge procedure instead of a copy, and every frontend-visible module adds an entry to each of the ≥5 stations (billing shipped flag-only to skip the tax). This is the frontend counterpart to Track 2's SA94 react-only work, so it lands here. The recommended fix is **Option 1, staged** — do not add a second injection mechanism; extend the existing `window.__QUICKSCALE__` seam and adopt the generator's existing verbatim-copy path (`_theme_non_jinja_emitted_paths`). Off the SA96 release critical path; must not regress any gate or coverage threshold. **File ownership vs. Track 1's TP work:** this workstream owns the `quickscale_core` generator + `showcase_react` template tree only — no overlap with the CI/Makefile surfaces SA102/SA103 touch, so it runs fully in parallel.

- [x] **SA104 — Stage 1: move byte-static theme files onto the verbatim-copy path.** `Tier 2 · Track 2 · deps: none · complete`
  **Completion evidence (2026-07-19):** 57 byte-static theme files across the `showcase_react` frontend theme/verbatim-copy surface (including the converted theme-root `frontend/index.html`) moved onto the verbatim-copy path — `.j2` suffix and `{% raw %}` wrappers removed, now routed through the generator's existing non-Jinja copy path (`_theme_non_jinja_emitted_paths`). 13 genuine active-Jinja files remain. Emitted byte/path/mode unchanged: SA90 emission-parity fixture stayed green; a two-project diff of `frontend/src` for the now-static files showed zero differences; `test_generated_project_runtime.py` passed. Added `test_non_jinja_theme_root_index_html_routed_correctly` regression test. QG run 2/2: Ruff/MyPy; SA90 20/20; React 51/51; zero unexpected differences across 61 verbatim-copied frontend files and identical `frontend/index.html` SHA-256; runtime 5/5; frontend proof/lint; `make test-unit` 4,482.
  - **Review:** Pass 1 found **SA104-CR-001** (medium/blocking completeness: root `index.html.j2` was raw-only static); fix converted it and added the regression test. Pass 2 returned **STATUS ok**, **SA104-CR-001 resolved**, Caller-Parity PASS. No blocker or open decision remains.
  - **Chain:** SA105 and SA106 are now unblocked by SA104. SA105 remains blocked by its own dormant-files maintainer decision; SA106 is assistant-executable.
  - **Root pre-commit check-json integration (post-review):** Root `.pre-commit-config.yaml` explicit `check-json` exclude reviewed `STATUS ok`. Targeted `check-json --files` excluded only `^quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/tsconfig\.json$` (JSONC); `check-json --all-files` passed. `pre-commit run --all-files` all 10 hooks pass. SHA-256 `9aaae682d5e2df06d1375bc66e738ab372a9cd42106353752f42cdda2d875d99` unchanged.
  - **Advisory SA104-ADV-001 (severity: medium, disposition: advisory (non-blocking), category: consistency):** Generated projects' own `quickscale_core/src/quickscale_core/generator/templates/.pre-commit-config.yaml.j2:10` still runs strict `check-json` against emitted `frontend/tsconfig.json` JSONC. Pre-existing; deferred to separate follow-up because fixing it changes generated output and fixture hashes. Not a completion blocker.
  *(why →* arch-audit Finding 10 stage 1 — de-duplicate byte-static source out of the per-project specialization surface*)*

- [ ] **SA105 — Stage 2a: de-specialize the module-availability surface via runtime config.** `Tier 2 · Track 2 · deps: SA104 ✓ + maintainer decision (dormant files) · assistant-executable after decision`
  Remove the generation-time narrowing of the module universe: make the `QuickScaleModules` TS interface all-modules-optional (flags default `false` when a module is absent — the Django `INSTALLED_APPS` ladder already emits runtime truth into `window.__QUICKSCALE__`), and convert `main.tsx`'s social-conditional imports into unconditional imports with **flag-gated routes**. Removes the src-side module stations (`useModules.ts.j2` tuples, `main.tsx` conditionals) so a new frontend-visible module no longer edits them.
  - **Blocking maintainer decision:** this makes unselected modules' pages exist as inert, flag-gated files in generated trees. If accepted → proceed. If rejected → fall back to Finding 10 **Option 3** (ownership-manifest overlay, extends Finding 7) and re-scope this ticket. *Record the decision in [decisions.md](./decisions.md) before implementing.*
  - Verify: generate projects with different module sets — the module-availability files are byte-identical across them; dormant module pages tree-shake/lazy-load and do not render when the flag is false; ESLint/tsc (via SA103) green.
  *(why →* arch-audit Finding 10 stage 2, module half — collapse the ≥5 hand-synced module stations onto the existing runtime seam*)*

- [ ] **SA106 — Stage 2b: de-specialize project identity via runtime config.** `Tier 2 · Track 2 · deps: SA104 ✓ · assistant-executable`
  Replace generation-baked project identity in frontend source with reads from the existing runtime seam: `Sidebar.tsx`/`Dashboard.tsx` "Welcome to {{ project_name }}" JSX → `window.__QUICKSCALE__.projectName` (already injected at `templates/index.html.j2:14-15`); confine remaining Jinja specialization to the Django-side templates and (at most) `package.json`. After this, `frontend/src` is project-agnostic and byte-identical across projects on the same theme version, so migration becomes "copy user-owned dirs, rebuild."
  - Independent of SA105's product decision; both depend only on SA104 (now ✓) and are largely file-disjoint (SA105: `useModules`/`main.tsx`; SA106: `Sidebar`/`Dashboard`/`package.json`) — order either way within the track.
  - Verify: two-project `frontend/src` diff shows zero identity-bearing differences; generated project renders the correct project name from runtime config; boot smoke + SA103 gate green.
  *(why →* arch-audit Finding 10 stage 2, identity half — stop double-encoding `projectName` in source*)*

### Track 3 — Core/CLI plumbing — SA93 and SA101 complete; SA96-GATE next

arch-audit **Finding 1** is closed (SA89a+SA89b, DR persistence port). All four GATEs, **SA91** (parallel worker pool), **SA93** (e2e in the green-gate), and **SA101** (quality remediation) are complete. SA93's local gate and hosted evidence are recorded in its task block; **SA96-GATE** is the next release-path step. **SA100** (tech-audit TA58/TA59 theme-preflight remediation) is complete — see [CHANGELOG.md](../../CHANGELOG.md). **No cross-track prerequisite remains; SA101 cleared the SA96-GATE-BLK-002 regressions against the unchanged baseline (Option A — remediate) and its closeout is verified, so SA96-GATE's only remaining blocker is cleared.**

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

**CI-gate remediation from the 2026-07-19 sweep — both tickets landed on Track 1.** Two audit findings landed on the CI/release plumbing, and both were rebalanced off this track to run in parallel with SA101: **SA102** (TA61, trivial) and **SA103** (TA60, frontend-proof gate). Both are closed on Track 1 — see [CHANGELOG.md](../../CHANGELOG.md); SA103's release-feeding condition for SA96-GATE is met. Track 3 completed **SA101** and owns the SA96-GATE join; the join must not be represented as run until its own four-command re-run and re-verification occur.

### Dependency & parallelization overview

Completed history (SA92/SA84/SA86/SA93/SA94/SA95/SA96-T1/T2/SA97/SA98/SA99/SA100/SA91/SA102/SA103/SA101/TP1/TP2/TP3a/TP3b,
Finding 1, all four GATEs) lives in [CHANGELOG.md](../../CHANGELOG.md); only open work is shown below.

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92/SA84/SA86 ✓ (dev tickets)      SA94/SA88b/SA86/SA95 ✓ (dev tickets)    Finding 1 ✓ (SA89a+SA89b)
SA96-T1 ── module sweep ✓            SA96-T2 ── module sweep ✓               GATE-lint/typecheck/check/quality ✓
SA97 ✓ + SA99 ✓ (audit remed.)      SA98 ✓ (sanitizer consolidation)         SA91 ✓ (parallel loop, non-gating)
SA102 ✓ + SA103 ✓ (CI gates,        TP3a ✓ → TP3b ✓ (E2E concurrency;        SA93 ✓ (e2e in green-gate)
  TA61 + TA60 frontend-proof)          rebalanced from Track 1; off crit.)    SA100 ✓ (TA58/TA59 theme preflight)
                                      SA104 ✓ ── FE static-source move (Fin.10
TP2b ✓ → TP4 (off crit.; TP1/TP2 ✓)   stage 1; complete)                     SA101 ✓ ── cleared BLK-002
                                       ├─ SA105 ── module de-spec (2a;            regressions (closeout complete;
                                       │    deps SA104 ✓ + dormant-files decision)   make check exit 0; review ok)
                                       └─ SA106 ── identity de-spec (2b; deps SA104 ✓)  feeds SA96-GATE; on crit. path
                       └─────────────────────┬───────────────────────────────────────┘
                                             ▼   (all release inputs ✓: SA96-T1, SA96-T2, SA93;
the TP + frontend chains run in parallel, off the
                                                  critical path and gate-neutral; Track 3 owns the join)
         SA101 ✓ (Track 3) ── cleared BLK-002 quality regressions (Option A: remediate, no re-baseline) ── feeds SA96-GATE
                        │  make check exit 0 (6,943/86/12/0, core 90.36%, CLI 90.49%, int. 94.41%);
                        │  change-review STATUS ok (confidence 94), no findings; worktree clean
                        │  (SA103 ✓ frontend-proof gate on Track 1 also feeds this join; feeder condition met)
                        ▼
         SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93 ✓ + SA103 ✓ + SA101 ✓
                        ▼                        (SA101 closeout complete; four-command join is the next pending step)
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE  (human-only)
```

**Open work only:** Track 1 `TP4` (docs-only), Track 2's frontend chain `SA104 ✓ → SA105/SA106` (arch Finding 10; SA104 complete), and the release join
`SA96-GATE → SA96-PUBLISH`. **TP2b** is complete — see completed task block above. **SA101** is complete — see completed task block above. The frontend chain (SA104 ✓+) owns the `quickscale_core` generator + `showcase_react` template tree only, disjoint from the TP work and the SA103 CI surfaces, so the remaining workstreams run concurrently. All of TP and the frontend chain are off the release critical path; SA101's feeder condition for SA96-GATE is met, while the SA96-GATE join awaits only its own four-command re-run. None may regress any gate's pass/fail set or coverage thresholds. `TP4` is docs-only and unblocked (TP1 done, TP3b merged to `v87`); it remains pending.

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** is complete and its dependency is met; **SA101** (clear the BLK-002 quality regressions, Track 3) is **complete** — the final closeout (`make check` exit 0, 6,943/86/12/0; independent change-review STATUS ok, confidence 94, no findings) has been verified. The remaining critical-path chain is **SA96-GATE** (green-gate join) → **SA96-PUBLISH** (human-only). **SA103** (frontend-proof gate, Track 1) is complete and its gate-tightening feeder condition is met; it ran concurrently with SA101. SA101 closeout evidence: `make check` exit 0 (6,943 passed, 86 skipped, 12 deselected, zero failures; core 90.36%, CLI 90.49%, integration aggregate 94.41%); full change-review STATUS ok, confidence 94, no blocking or advisory findings; worktree clean throughout. Known BYPASSRLS-dependent skips are pre-existing. SA96-GATE's only remaining blocker is cleared; the four-command join can now re-run. **SA98** and **SA100** are complete independent audit-remediation tickets; neither blocks SA96-GATE. SA97, SA99, and SA102 are also complete (see [CHANGELOG.md](../../CHANGELOG.md)).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). Both module sweeps and SA93 are complete, so SA96-GATE is the next release-path step. SA93's cross-track blockers are resolved; component Core/CLI E2E, exact local `make ci-e2e`, and the two hosted jobs are green. SA93-EVID-001 records the verified hosted run metadata.

### Track readiness (2026-07-19)

- **Track 1 — ACTIVE (off critical path); TP2b complete, TP4 clean to continue.** The two 2026-07-19 CI-gate tickets rebalanced here from Track 3 — **SA102** (TA61 devtools CI gate) and **SA103** (TA60 frontend-proof gate) — are both **closed** (see [CHANGELOG.md](../../CHANGELOG.md)); SA103's **SA96-GATE** feeder condition is met. **TP1** and **TP2** were accepted 2026-07-18. **TP2b** is complete — both exact `test-cov` commands green: 4,536 core/CLI passed, 323 backups passed, 2 skipped; 92.88% equal-weight package mean; all 90 files ≥80%; final change-review **STATUS ok**; CR-TP2B-001, CR-TP2B-002, and QG-TP2B-001 resolved. The prior `auto`-worker Poetry-lock contention did not recur in the accepted runs and is a non-blocking advisory. **TP4** is docs-only and unblocked (TP1 done, TP3b merged to `v87`) — clean to continue. The E2E sub-chain **TP3a/TP3b** was rebalanced to Track 2 and is complete. TP4 is off the SA96 release critical path and must not regress any gate's pass/fail set or coverage thresholds. Evidence for closed work is in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 2 — E2E-concurrency sub-chain complete (TP3a ✓ → TP3b ✓) + the arch Finding 10 frontend chain (SA104 ✓ → SA105/SA106).** Release tickets and audit remediation are closed (SA94, SA88b, SA86, SA95, SA96-T2, and SA98; SA97+SA98 close arch-audit **Finding 9**). Track 2 carries the completed **TP3a → TP3b** sub-chain (rebalanced off Track 1) plus the newly-cut **frontend-theme de-specialization** workstream (arch Finding 10, the frontend counterpart to this track's SA94 react-only work): **SA104 ✓** (stage 1, byte-static source move — 57 files converted, SA90-fixture-verified, review STATUS ok), then **SA105** (stage 2a, module de-spec — deps SA104 ✓ + a maintainer dormant-files decision) and **SA106** (stage 2b, identity de-spec — deps SA104 ✓). **TP3a** delivered E2E port-namespacing and **TP3b** delivered concurrent Core/CLI E2E lanes; TP3b modifies shared `_qs_jobs.sh` helper behavior and shares `Makefile` with Track 1 TP2b for maintained harness wiring. The existing pre-merge `v87` synchronization procedure governs these seams, while other source files remain disjoint. The frontend chain owns the `quickscale_core` generator + `showcase_react` template tree, with no source overlap with the TP work, Track 1, or Track 1's SA103 CI surfaces, so the remaining workstreams run in parallel (only the closeout files are shared, covered by the Merge procedure). All off the release critical path; must not regress any gate or coverage threshold. **SA105 has a pending maintainer decision** (dormant module files in generated trees — record in decisions.md before implementing). Evidence for closed work is in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 3 — SA93 COMPLETE; SA101 COMPLETE — closeout verified.** Finding 1, all four GATEs, SA91, SA100, SA93, and SA101 are complete. SA101 implementation remediated all 19 BLK-002 regressions through nine serial phases (file-local extraction + direct-identity alias refactors + migration-local compaction) with `make quality` reaching exit 0 and exact migration parity proven for CRM/forms. Plan review pass 2 `STATUS: ok`. **`SA101-VAL-001` resolved: the restricted-role CRM/forms failures were confirmed pre-existing on clean pre-SA101, not caused by compaction; SA101 at HEAD is green (CRM 284 / Forms 212 passed under `NOBYPASSRLS`).** Final closeout evidence: `make check` exit 0 — 6,943 passed, 86 skipped, 12 deselected, zero failures; core 90.36%, CLI 90.49%, integration aggregate 94.41%. Independent full change-review returned `STATUS: ok`, confidence 94, no blocking or advisory findings. Worktree remained clean. Known BYPASSRLS-dependent skips are pre-existing. `make ci` and `make ci-e2e` were not run. With SA101 closeout complete and SA103's feeder condition met, **SA96-GATE** is the next pending Track 3/release-path step — its four-command join can now re-run. **The 2026-07-19 audit-sweep CI-gate tickets were rebalanced off this track to Track 1** — SA102 and SA103 (frontend-proof gate) both landed there, parallelizing SA101 rather than queuing behind it here; SA103's SA96-GATE feeder condition is met. The PyPI publish (SA96-PUBLISH) remains explicitly excluded from assistant work (human-only). SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004, SA93-REV-005, and SA93-ADV-001..004 remain non-gating advisories.


**Net — all three tracks have assigned work; the 2026-07-19 audit sweep added five tickets (SA102 + SA103 landed on Track 1, SA104 ✓→SA105/SA106 on Track 2). One maintainer decision remains open — SA105 (dormant frontend files, downstream of SA104). SA101 closeout is complete — `make check` exit 0 (6,943/86/12/0) and independent change-review STATUS ok (confidence 94, no findings).** Track 1 carries the off-critical-path TP test-parallelization suite (SA102/SA103 closed), with **TP2b complete** (both exact commands green; final change-review STATUS ok; CR-TP2B-001, CR-TP2B-002, QG-TP2B-001 resolved) and **TP4** pending (docs-only, clean to continue); Track 2 carries the completed E2E-concurrency sub-chain (**TP3a** and **TP3b** complete) plus the new arch-Finding-10 frontend chain (**SA104 ✓** (complete), then **SA105/SA106**); Track 3's **SA101** is **complete** (implementation, validation, and closeout all verified). Both pre-publish module sweeps and SA93 are complete, so **SA96-GATE** is the next pending Track 3/release-path step — its only remaining blocker (SA101 closeout) is cleared; the four-command join can now re-run. **SA103's feeder condition is met**. **SA98**, **SA100**, SA97, SA99, and SA102 are landed; no TP2b design decision is pending. The squash-migrations decision, bounded guardrail strategy, and v87 shrink-only quality-maxima policy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
