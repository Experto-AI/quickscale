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

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline. **All per-module restricted-role gates are green** — blog (SA83/SA95), forms (SA85), listings (SA86), orgs (SA77), notifications (SA79), and CRM (SA84) are all closed; see [CHANGELOG.md](../../CHANGELOG.md).

**Two open workstreams remain before release:**
1. **SA93** (fold the e2e lane into the green-gate definition of done), a blocked checkpoint on Track 3.
2. **Pre-publish verification & release sweep (SA96)** — a fresh per-module test+coverage re-verification across Tracks 1 and 2, then the green-gate join and the staged PyPI publish. Defined in its own milestone below.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate — CLOSED

All per-module restricted-role gates pass green under the SA82 baseline with an empty quarantine: **CRM (SA84), blog (SA83/SA95), forms (SA85), listings (SA86), orgs (SA77), notifications (SA79)** — see [CHANGELOG.md](../../CHANGELOG.md). The parallelizable per-module axis is complete; only the repo-global e2e closeout (SA93) remains.

#### Repo-global gates (run once at v87 integration, after per-module work lands)

GATE-lint, GATE-typecheck, GATE-check-suite, **GATE-quality**, and the **SA91** parallel worker pool are all **done** (see [CHANGELOG.md](../../CHANGELOG.md)). The remaining closeout is **SA93** (e2e in the green-gate), on Track 3. Both of its former cross-track prerequisites (SA84 CRM, SA95 blog) are now met.

- [ ] **SA93 — Fold the e2e lane into the green-gate definition of done.** `Tier 1 · Track 3 · deps: none remaining (SA84 CRM + SA95 blog prerequisites met)`
  **Blocked checkpoint (2026-07-17; maintainer-selected stop-and-merge; not complete). No design decision remains — continuation is merge-back, authorized push/dispatch of `v87`, and retention of the green run URL/ref/SHA.**

  Fresh local gate and review evidence is recorded in [CHANGELOG.md §SA93 continuation](../../CHANGELOG.md#sa93-continuation). Prior implemented/landed evidence (deterministic fixes, component E2E green, review CR-SA93-REV-001/002/003/004 resolved) is also recorded there.

  **Done:**
  - **SA93-BLOCK-002:** exact `make ci-e2e` exits 0 locally with all 12 stages, Core 35, CLI 29, all 12 integration modules, 91.90% combined coverage, every file at least 80%, unchanged thresholds, and an empty quarantine.
  - Independent review confirmed the database-isolation, CLI-lifecycle, generated-React, manifest-parity, and local/remote runner contracts. **CR-SA93-REV-005** and **CR-SA93-REV-006** are resolved: bounded production trigger paths invoke the maintained Core+CLI runner, and stale coverage-artifact promises were retired.
  - The **CR-SA93-REV-007** checkpoint correction restores the stable advisory summaries below; the **SA93-DOC-001** correction adds the missing changelog anchor fragment.

  **Pending/Blocking:**
  - **SA93-EVID-001 (high/blocking):** external GitHub Actions evidence for `v87` is absent — origin has no `v87` ref, no GH auth is configured, and the API has no run. Cannot close SA93 without a successful remote run on the merged `v87` commit.
  - **Final CI evidence:** after merge-back, push the intended `v87` ref through an authorized operator, dispatch `.github/workflows/e2e.yml`, and retain the successful run URL, conclusion, ref, and SHA before marking SA93 complete.

  **Advisory:**
  - **SA93-ADV-001 (low/advisory):** pytest reports a future pytest-10 warning for the class-scoped fixture pattern in `TestReactThemePnpmIntegration.test_pnpm_install_succeeds`; normalize it before a pytest 10 upgrade.
  - **SA93-ADV-002 (low/advisory):** local validation reports database access during application initialization and an orgs test-database teardown warning; investigate without weakening the gate.
  - **SA93-ADV-003 (low/advisory):** the worker-pool harness runs between numbered stages 9 and 10 without a stage/substage label; improve auditability when next maintaining the script.
  - **SA93-ADV-004 (low/advisory):** coverage-threshold overrides accept non-finite `NaN`/`Inf` values and can fail open; reject non-finite overrides in a separate hardening task.

  **Decisions needed:** no design or maintainer decision remains. An authorized operator must decide when to push the merged local `v87` ref and dispatch the remote workflow; this operational action is required evidence, not permission to weaken acceptance.

  **Resolved prerequisites:** SA93-BLOCK-001 (blog + CRM integration fixture-finalizer failures) is resolved — blog closed by **SA95** (2026-07-17, no reproducible defect on post-SA92 v87) and CRM closed by **SA84** (2026-07-17, 263 pass/21 skip/0 fail, review STATUS ok). Both former cross-track prerequisites for SA93 are met. Preserve the exact unquarantined `make ci-e2e` contract; quarantine and threshold weakening are not acceptable.

  **Clean continuation:** merge this reviewed blocked checkpoint to local `v87`, then have an authorized operator push that ref and dispatch `e2e.yml`. Record the green run URL/ref/SHA, update CHANGELOG/roadmap, and only then mark SA93 complete.

  *(Acceptance:* `make ci-e2e` exits 0 on a fresh clone; `e2e.yml` green on `v87`; independent review passes; exit-criteria prose lists the e2e lane.*)*
  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Pre-publish verification & release sweep (SA96)

A fresh, pre-release re-verification pass. The per-module gates are green under the SA82 baseline; this milestone **re-ran each module in isolation on the current `v87`** to confirm no regression before publishing (SA96-T1 + SA96-T2, both complete — see [CHANGELOG.md](../../CHANGELOG.md)), then executes the green-gate join and the staged PyPI ladder. Track 3 continued SA93 in parallel.

> **SA96-T1 (Track 1 module sweep) and SA96-T2 (Track 2 module sweep) are complete** (2026-07-17) — analytics · auth · backups · billing · blog · crm and forms · listings · notifications · orgs · social · storage all re-verified green in isolation on the post-SA92 `v87` baseline, no regression, empty quarantine. Full evidence in [CHANGELOG.md](../../CHANGELOG.md). **SA93 is the sole remaining input to SA96-GATE.**

- [ ] **SA96-GATE — Green-gate join (cross-track).** `Tier 1 · v87 integration · deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93`
  After both module sweeps **and** SA93 land, on a fresh clone + fresh `migrate` (post-SA92 squash) run until all exit 0 with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`:
  `make check` → `make quality` → `make ci` → `make ci-e2e`. All four green + empty quarantine = publishable (single definition of done, see the exit-criteria above).

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE`
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — confirm version + green-gate status before `publish-prod`.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — idle (SA96-T1 closed)

All Track 1 work is complete. Prior development tickets closed — SA92 (migration squash to final-schema `0001_initial`), SA84 (CRM restricted-role fixtures), SA86 (listings); the pre-publish sweep **SA96-T1** closed 2026-07-17. See [CHANGELOG.md](../../CHANGELOG.md). The squash eliminated the cross-org-*migration* half of arch-audit [Finding 8](../others/arch-audit.md) and SA84/SA86 drained the surviving **fixture** half — Finding 8 is now closed. Full decision record: [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92). **Track 1 has no open tickets** — free to take on rebalanced work if any arises.

### Track 2 — Module contracts & settings — idle (SA96-T2 closed)

All Track 2 work is complete. Prior development tickets closed — SA88b (forms diagnosis), SA86 (listings), GATE-lint / GATE-typecheck / GATE-check-suite, SA94 (react-only theme + Barrier B review), SA95 (blog fixture-finalizer regression); the pre-publish sweep **SA96-T2** closed 2026-07-17. See [CHANGELOG.md](../../CHANGELOG.md). The GATE-quality / SA91 / SA93 closeout items were reassigned to the freed Track 3. **Track 2 has no open tickets** — free to take on rebalanced work if any arises.

### Track 3 — Core/CLI plumbing — SA93 open

> **Finding 1 closed.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed by SA89a + SA89b — see [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

Finding 1 (DR persistence port, SA89a+SA89b), all four GATEs, and **SA91** (parallel integration worker pool) are complete — see [CHANGELOG.md](../../CHANGELOG.md). SA91 retains **CR-SA91-REV-006** (low/advisory, throughput only). The single open item is **SA93** (fold e2e into the green-gate), defined in the green-gate section above — implementation, component E2E, exact local gate, and independent source-review evidence are present. The sole remaining blocker is SA93-EVID-001: no remote `v87` ref or successful GH Actions run exists. **No cross-track prerequisite or maintainer decision remains.**

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92/SA84/SA86 ✓ (dev tickets)      SA94/SA88b/SA86/SA95 ✓ (dev tickets)    Finding 1 ✓ (SA89a+SA89b)
                                                                            GATE-lint/typecheck/check/quality ✓
SA96-T1 ── module sweep ✓            SA96-T2 ── module sweep ✓               SA91 ✓ (parallel loop, non-gating)
(Track 1 idle)                       (Track 2 idle)                          SA93 ── e2e in green-gate (open)
                                                                              deps: none remaining
        │                                     │                                       │
        └──────────────┬──────────────────────┴───────────────────────────────────────┘
                       ▼
        SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 + SA96-T2 + SA93
                       ▼
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE
```

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** remains the sole open input to the **SA96-GATE** cross-track join; **SA96-PUBLISH** follows that join. The remaining SA93 path is merge-back → authorized push/dispatch → green `e2e.yml` evidence on `v87` (SA93-EVID-001) → close SA93.

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). It cannot start until both completed module sweeps and SA93 are present. SA93's cross-track blockers are resolved; component Core/CLI E2E, exact local `make ci-e2e`, and independent source review are green. The only remaining blocker for SA93 closeout is SA93-EVID-001 (no remote `v87` run).

### Track readiness (2026-07-17)

- **Track 1 — CLEAN, idle.** All tickets closed (SA92, SA84, SA86, and the SA96-T1 pre-publish sweep); no open work. Evidence in [CHANGELOG.md](../../CHANGELOG.md). Available for rebalanced work.
- **Track 2 — CLEAN, idle.** All tickets closed (SA94, SA88b, SA86, SA95, and the SA96-T2 pre-publish sweep); no open work. Evidence in [CHANGELOG.md](../../CHANGELOG.md). Available for rebalanced work.
- **Track 3 — NOT BLOCKED ON A DECISION; external evidence pending (SA93 open).** Finding 1, all four GATEs, and SA91 are complete. SA93 implementation, component E2E, exact local `make ci-e2e`, workflow parity, and independent source-review evidence are present. The sole remaining blocker is SA93-EVID-001 (no remote `v87` ref or GH Actions run). Continuation is merge-back → authorized push/dispatch → green `e2e.yml` evidence on `v87` → close SA93. SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004 and SA93-ADV-001..004 are non-gating low advisories.

**Net — no maintainer decisions pending.** Both pre-publish module sweeps are complete (SA96-T1 and SA96-T2); SA93 continues as the sole remaining open item. Exact local `make ci-e2e` and independent source review are green. SA93-EVID-001 (high/blocking) persists: no remote `v87` ref or successful GH Actions run exists. Remaining path: merge this checkpoint, have an authorized operator push/dispatch `v87`, retain the green run evidence, then close SA93. After SA93 close, SA96-GATE can run the four-command publishability join and SA96-PUBLISH can proceed. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
