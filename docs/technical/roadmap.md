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
1. **SA96-GATE** (green-gate join, Track 3) — next pending release-path task. All deps are met (SA96-T1/T2, SA93, SA103, SA101 all complete — see [CHANGELOG.md](../../CHANGELOG.md)); both blockers (BLK-001 coverage, BLK-002 quality baseline) are cleared. The four-command join can now re-run.
2. **SA96-PUBLISH** (staged PyPI publish, human-only), deps on SA96-GATE.
3. **Frontend-theme de-specialization (arch-audit Finding 10, Track 2)** — staged chain **SA104 ✓ → SA105/SA106**. SA104 (stage 1) is complete; **SA105** (module de-spec, blocked on a maintainer dormant-files decision) and **SA106** (identity de-spec, assistant-executable) remain open. Off the release critical path. Arch **Finding 7** stays unscheduled (SA104 shrank its surface — sequence any tuple-derivation work after it); arch Findings **2/4** remain **not ticketed** with the (unscheduled) teams module.
4. **Track 1 test-parallelization** — **TP4** (docs-only AI fast-loop recipes) is **complete** (see below); no open TP tickets remain. Off the release critical path.

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
  - **Both former blockers cleared.** The coverage blocker (`SA96-GATE-BLK-001`) is superseded by the restored canonical coverage evidence (6,026/6,670 = 90.34%). The quality-baseline blocker (`SA96-GATE-BLK-002`, 19 regressions) was cleared by **SA101** against the unchanged baseline per the maintainer-approved Option A (remediate, do not re-baseline) — see [CHANGELOG.md](../../CHANGELOG.md). No source, config, baseline, or threshold changes remain outstanding; the four-command join is the sole next release-path action and has not been re-run.

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE` · **HUMAN-ONLY — do not delegate to an assistant**
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — TP (test-parallelization) suite

Prior Track 1 tickets are closed — SA92, SA84, SA86, SA96-T1, Finding 8, the audit-remediation tickets SA97/SA99, the CI-gate tickets SA102/SA103 (rebalanced here from Track 3), and the test-parallelization suite SA91/TP1/TP2/TP2b (the E2E sub-chain TP3a/TP3b was rebalanced to Track 2). See [CHANGELOG.md](../../CHANGELOG.md).

Track 1 carried the tail of the **TP (test-parallelization)** suite — the goal was to shorten the SDLC feedback loop (and let an AI assistant run partial tests concurrently) by parallelizing the long-running quality gates. The suite is now **complete** with the landing of **TP4** (docs-only AI fast-loop recipes). All prior TP tickets (TP1, TP2, TP2b, TP3a, TP3b) are closed — see [CHANGELOG.md](../../CHANGELOG.md).

- [x] **TP4 — Document the AI-assistant fast partial-test recipes.** `Tier 1 · Track 1 · deps: none · docs-only (review-only closeout)`
  Added a "Fast feedback loop for AI-assisted / incremental development" subsection to `docs/technical/development.md` covering the iterate → pre-merge → E2E-last ladder, section flags (`make lint -- --core`, `make typecheck -- --cli`, `make test-unit -- --core`), single-module reruns (`QS_ORGS_DB_USER=quickscale_test_role make MODULE=orgs test -- --modules`), bounded integration concurrency (`QS_INTEGRATION_JOBS=2 make test-integration`), and cross-references to `QS_CI_PARALLEL` (TP1), `QS_E2E_PARALLEL` (TP3b), and `PYTEST_XDIST_WORKERS` (TP2). Five commands were verified on the clean `v87` baseline: `make lint -- --core` exit 0; `make typecheck -- --cli` exit 0; `make test-unit -- --core` exit 0 (2,489 passed); `QS_ORGS_DB_USER=quickscale_test_role make MODULE=orgs test -- --modules` exit 0 (874 passed, 11 skipped); `QS_INTEGRATION_JOBS=2 make test-integration` returned nonzero — the bounded worker pool ran all 12 modules (94.39% mean) but `orgs/test_debug.py::TestMiddlewareDebugOverride::test_debug_org_overrides_saas_session` failed with "server closed the connection unexpectedly". A serial rerun (`QS_INTEGRATION_JOBS=1 make test-integration`) subsequently passed (all 12 modules, 94.41% mean). The bounded-run failure is an unresolved non-blocking integration risk for this docs-only task. `QS_CI_PARALLEL=0` and `QS_E2E_PARALLEL=0` are documented as cross-references (their full verification is the responsibility of their owning tickets, which are complete). CR-TP4-001 (shell-invalid `<N>` in presented command syntax) and CR-TP4-002 (overstated verification evidence) were resolved in the follow-up pass.
  *(why →* parallelization audit Tier 4 — scoped partial runs already exist; the gap was discoverability for the incremental-dev loop*)*

### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

Prior Track 2 tickets are closed — SA88b, SA86, SA94, SA95, GATE-lint/typecheck/check-suite, SA96-T2, SA98 (SA97+SA98 close arch-audit **Finding 9**), and the E2E-concurrency sub-chain TP3a→TP3b (rebalanced off Track 1). See [CHANGELOG.md](../../CHANGELOG.md).

#### Frontend-theme de-specialization (arch-audit Finding 10 — SA105/SA106, downstream of the complete SA104)

The 2026-07-19 arch pass promoted **Finding 10** (`frontend-source-generation-specialized`) to the top-ranked finding: the `showcase_react` theme bakes project identity and the module universe into user-editable frontend *source* at generation time, duplicating facts the `window.__QUICKSCALE__` runtime config seam already delivers per request — so every generated frontend is a unique source tree, migration is a per-file merge instead of a copy, and every frontend-visible module adds an entry to ≥5 hand-synced stations (billing shipped flag-only to skip the tax). This is the frontend counterpart to Track 2's SA94 react-only work, so it lands here. The recommended fix is **Option 1, staged** — extend the existing `window.__QUICKSCALE__` seam and the generator's existing verbatim-copy path (`_theme_non_jinja_emitted_paths`), adding no second injection mechanism. **SA104 (stage 1) is complete**; the open work is stages 2a/2b below. Off the SA96 release critical path; must not regress any gate or coverage threshold. **File ownership:** this workstream owns the `quickscale_core` generator + `showcase_react` template tree only — no overlap with the CI/Makefile surfaces SA102/SA103 touch, so it runs fully in parallel with Tracks 1 and 3.

> **SA104 (stage 1, byte-static source move) is complete** — 57 files converted onto the verbatim-copy path, SA90-fixture-verified, review STATUS ok. It unblocked SA105/SA106. See [CHANGELOG.md](../../CHANGELOG.md). The residual **advisory SA104-ADV-001** (generated projects' `.pre-commit-config.yaml.j2:10` still runs strict `check-json` against emitted JSONC `frontend/tsconfig.json`) is a non-blocking deferred follow-up — fixing it changes generated output and fixture hashes.

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

### Track 3 — Core/CLI plumbing — owns the SA96-GATE join

All prior Track 3 work is closed (arch-audit Finding 1 via SA89a+SA89b; all four GATEs; SA91 parallel worker pool; SA93 e2e in green-gate; SA100 TA58/TA59 theme preflight; SA101 quality remediation) — see [CHANGELOG.md](../../CHANGELOG.md). Track 3 owns the **SA96-GATE** join, the sole remaining release-path task; the join must not be represented as run until its own four-command re-run and re-verification occur.

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

All prior release-path and audit-remediation tickets are complete (SA92/SA84/SA86/SA93/SA94/SA95/SA96-T1/T2/SA97/SA98/SA99/SA100/SA91/SA101/SA102/SA103/SA104/TP1/TP2/TP2b/TP3a/TP3b/TP4, Finding 1, all four GATEs) — see [CHANGELOG.md](../../CHANGELOG.md). Only open work is shown below.

```
Track 1 (complete)         Track 2 (off crit. path)          Track 3 → release (critical path)
────────────────────────   ────────────────────────────      ─────────────────────────────────
✓ TP4 complete              SA105 ── module de-spec (2a;       SA96-GATE ── green-gate join
✓ TP suite closed             deps SA104 ✓ + dormant-files       (make check/quality/ci/ci-e2e)
  (TP1/TP2/TP2b/              maintainer decision)               all deps ✓; blockers cleared
   TP3a/TP3b/TP4)           SA106 ── identity de-spec (2b;             │
                              deps SA104 ✓; assistant-exec.)           ▼
                            (arch Finding 10 chain)             SA96-PUBLISH ── build → publish
                                                                  deps: SA96-GATE  (human-only)
```

**Open work only:** Track 2's frontend chain `SA105/SA106` (arch Finding 10, downstream of the complete SA104) and the release join `SA96-GATE → SA96-PUBLISH`. Track 1's TP suite is **complete** (TP1/TP2/TP2b/TP3a/TP3b/TP4). The frontend chain owns the `quickscale_core` generator + `showcase_react` template tree only — disjoint from the TP work and the SA103 CI surfaces — so Track 2 and Track 3 run concurrently; only the closeout files (`CHANGELOG.md`, `roadmap.md`) are shared, covered by the Merge procedure. Tracks 1 and 2 are off the release critical path and must not regress any gate's pass/fail set or coverage thresholds. `SA106` is assistant-executable; `SA105` is blocked only on a maintainer dormant-files decision.

**Critical path.** All SA96-GATE dependencies are complete (SA96-T1/T2, SA93, SA103, SA101) and both blockers (BLK-001 coverage, BLK-002 quality baseline) are cleared, so the remaining critical-path chain is just **SA96-GATE** (green-gate join, assistant-executable) → **SA96-PUBLISH** (human-only). The SA96-GATE join must not be represented as run until its own four-command re-run and re-verification occur.

### Track readiness (2026-07-20)

- **Track 1 — COMPLETE (off critical path).** All TP work (TP1/TP2/TP2b/TP3a/TP3b/TP4) and the two rebalanced CI-gate tickets (SA102/SA103) are closed — see [CHANGELOG.md](../../CHANGELOG.md). The TP suite is fully landed with no open tickets. Off the SA96 release critical path; none of its changes regressed any gate's pass/fail set or coverage thresholds.
- **Track 2 — CLEAN to continue for SA106; SA105 blocked on a maintainer decision (off critical path).** All prior release/audit work is closed (SA94, SA88b, SA86, SA95, SA96-T2, SA98, TP3a/TP3b). The open frontend-theme de-specialization chain (arch Finding 10) is **SA106** (identity de-spec — deps SA104 ✓, assistant-executable — clean to continue) and **SA105** (module de-spec — deps SA104 ✓ **plus a pending maintainer dormant-files decision**, record in decisions.md before implementing). The chain owns the `quickscale_core` generator + `showcase_react` template tree only, disjoint from the TP work and the SA103 CI surfaces; must not regress any gate or coverage threshold.
- **Track 3 — CLEAN to continue (owns the release critical path).** All prior Track 3 work is closed (Finding 1, four GATEs, SA91, SA100, SA93, SA101). The sole open ticket is **SA96-GATE** (green-gate join, assistant-executable) — all deps met and both blockers cleared; its four-command re-run is the next release-path action. **SA96-PUBLISH** (human-only) follows. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006 low; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004).

**Net — Tracks 2 and 3 have assigned, independent work and none is a merge hazard (file-disjoint except the shared closeout files, covered by the Merge procedure).** Track 1 is **complete** (all TP tickets closed). Track 2 = `SA106` (clean) + `SA105` (blocked on one maintainer decision); Track 3 = `SA96-GATE` (clean, critical path) → `SA96-PUBLISH` (human-only). SA96-GATE is the only critical-path task and is a cross-track join that cannot be parallelized, so no rebalancing move helps — see [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92) for the recorded squash/guardrail/shrink-only-quality policies; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
