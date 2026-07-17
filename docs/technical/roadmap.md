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

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline. **All per-module restricted-role gates are green** — blog (SA83/SA95), forms (SA85), listings (SA86), orgs (SA77), notifications (SA79), and CRM (SA84) are all closed; see [CHANGELOG.md](../../CHANGELOG.md). The only remaining open item is **SA93** (fold the e2e lane into the green-gate definition of done), a blocked checkpoint on Track 3.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate — CLOSED

All per-module restricted-role gates pass green under the SA82 baseline with an empty quarantine: **CRM (SA84), blog (SA83/SA95), forms (SA85), listings (SA86), orgs (SA77), notifications (SA79)** — see [CHANGELOG.md](../../CHANGELOG.md). The parallelizable per-module axis is complete; only the repo-global e2e closeout (SA93) remains.

#### Repo-global gates (run once at v87 integration, after per-module work lands)

GATE-lint, GATE-typecheck, GATE-check-suite, **GATE-quality**, and the **SA91** parallel worker pool are all **done** (see [CHANGELOG.md](../../CHANGELOG.md)). The remaining closeout is **SA93** (e2e in the green-gate), on Track 3. Both of its former cross-track prerequisites (SA84 CRM, SA95 blog) are now met.

- [ ] **SA93 — Fold the e2e lane into the green-gate definition of done.** `Tier 1 · Track 3 · deps: none remaining (SA84 CRM + SA95 blog prerequisites met)`
  **Blocked checkpoint (2026-07-17; maintainer-selected stop-and-merge; not complete). No maintainer decision remains — continuation is one deterministic formatting fix, the exact broad rerun, and independent review.**

  **Implemented/evidence available (not final closure):**
  - Added the combined core/CLI/backups coverage path, `scripts/check_coverage_policy.py`, maintained helper tests, and focused DR-engine lock/path/sidecar tests.
  - Implemented **CR-SA93-REV-002** fail-closed coverage parsing: validate JSON roots and file records, require both core and CLI package populations, reject non-canonical traversal paths, and cover malformed/missing-package/traversal cases. Focused evidence: **37/37 helper tests passed**, Ruff passed, and `bash -n scripts/check_ci_locally.sh` passed.
  - Implemented **CR-SA93-REV-004** conditional CI stage totals: non-E2E runs use 11 numbered stages, E2E runs use 12, and the skip message is unnumbered.
  - Removed the Stage-12 environment/test blockers exposed by the first broad rerun: aligned the forms `django-filter` expectation, isolated each Core E2E database through pytest-docker, removed the ambient `localhost:5432` dependency, hardened CLI Docker cleanup/readiness and development-command database-role handling, and repaired the no-modules React TypeScript contract. The explicit maintainer decision is recorded in the implementation: `QuickScaleModules.auth` is always typed/defaulted false while runtime availability still gates visibility.
  - Phase evidence is green: **35/35 Core E2E**, **29/29 CLI E2E**, **470/470 CLI unit tests**, **82/82 React template/integration tests**, the original Docker/apply migration test, and a real no-modules `pnpm` type-check/build proof all passed with no relevant E2E skips. These component results do not replace the required exact root gate.
  - The final exact `make ci-e2e` attempt reached the normalized 12-stage flow: dependency installation passed; Ruff lint checks passed; Ruff format-check then stopped Stage 2 on one formatting-only diff in `quickscale_core/tests/generator/test_themes.py`. Stages 3–12 were therefore not reached in that exact run.
  - Independent review resolved **CR-SA93-REV-001** (equal-package arithmetic/final authority) and **CR-SA93-REV-003** (maintained helper-test collection).

  **Pending/Blocking:**
  - **SA93-BLOCK-003 (medium/blocking):** run `poetry run ruff format quickscale_core/tests/generator/test_themes.py`. This is the only currently observed failure in the latest exact root-gate attempt; no semantic code change or maintainer decision is needed.
  - **SA93-BLOCK-002 (high/blocking):** exact root-gate closure remains unproven because the latest `make ci-e2e` stopped at Stage 2 before coverage, integration, and E2E. After formatting, rerun exact `make ci-e2e` with sufficient timeout and require exit 0 with all 12 stages, both E2E suites, unchanged thresholds, and an empty quarantine.
  - **Final review/CI evidence:** independently review the complete SA93 delta (including CR-SA93-REV-002/004, database isolation, CLI lifecycle behavior, and the generated React contract), then verify `.github/workflows/e2e.yml` is green on `v87` before marking SA93 complete.
  - **SA93-ADV-001 (low/advisory):** pytest reports a future pytest-10 warning for the class-scoped fixture pattern in `TestReactThemePnpmIntegration.test_pnpm_install_succeeds`; it does not block the current gate but should be normalized before a pytest 10 upgrade.

  **Resolved prerequisites:** SA93-BLOCK-001 (blog + CRM integration fixture-finalizer failures) is resolved — blog closed by **SA95** (2026-07-17, no reproducible defect on post-SA92 v87) and CRM closed by **SA84** (2026-07-17, 263 pass/21 skip/0 fail, review STATUS ok). Both former cross-track prerequisites for SA93 are met. Preserve the exact unquarantined `make ci-e2e` contract; quarantine and threshold weakening are not acceptable.

  **Clean continuation:** no design or maintainer decision is pending. Resume with the exact worktree sequence below, then independently review the full SA93 delta, verify `e2e.yml` is green on `v87`, and update CHANGELOG/roadmap before marking SA93 complete.

  ```bash
  cd /home/victor/code/quickscale-wt-track3
  git status                 # must be clean
  git merge v87              # resync the merged checkpoint
  poetry run ruff format quickscale_core/tests/generator/test_themes.py
  make ci-e2e                # allow sufficient time for all 12 stages
  ```

  *(Acceptance:* `make ci-e2e` exits 0 on a fresh clone; `e2e.yml` green on `v87`; exit-criteria prose lists the e2e lane.*)*
  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Track 1 — Tenant-context surface — COMPLETE

No remaining open tickets. SA92 (migration squash to final-schema `0001_initial`), SA84 (CRM restricted-role fixtures), and SA86 (listings) all closed — see [CHANGELOG.md](../../CHANGELOG.md). The squash eliminated the cross-org-*migration* half of arch-audit [Finding 8](../others/arch-audit.md); the surviving **fixture** half (SA84 CRM, SA86 listings) is drained. SA95 (blog) was reassigned to Track 2 and closed there. Full decision record: [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92).

### Track 2 — Module contracts & settings — COMPLETE

No remaining open tickets. SA88b (forms diagnosis), SA86 (listings), GATE-lint / GATE-typecheck / GATE-check-suite, SA94 (react-only theme + Barrier B review), and SA95 (blog fixture-finalizer regression — closed with no reproducible defect on the post-SA92 v87 baseline) all closed — see [CHANGELOG.md](../../CHANGELOG.md). The GATE-quality / SA91 / SA93 closeout items were reassigned to the freed Track 3.

### Track 3 — Core/CLI plumbing — SA93 open

> **Finding 1 closed.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed by SA89a + SA89b — see [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

Finding 1 (DR persistence port, SA89a+SA89b), all four GATEs, and **SA91** (parallel integration worker pool) are complete — see [CHANGELOG.md](../../CHANGELOG.md). SA91 retains **CR-SA91-REV-006** (low/advisory, throughput only). The single open item is **SA93** (fold e2e into the green-gate), defined in the green-gate section above — its implementation and component E2E evidence are present, but exact root-gate closure is blocked by one Ruff formatting diff followed by the required broad rerun and independent review. **No cross-track prerequisite or maintainer decision remains.**

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92 ✓ (squash migrations)          SA94 ✓ (react-only theme)               Finding 1 ✓ (SA89a+SA89b)
SA84 ✓ CRM  ·  SA86 ✓ listings      SA88b/SA86 ✓                            GATE-lint/typecheck/check/quality ✓
                                    SA95 ✓ (blog regression, deps: none)    SA91 ✓ (parallel loop, non-gating)
   Track 1 COMPLETE                    Track 2 COMPLETE                     SA93 ── e2e in green-gate (blocked)
                                                                              deps: none remaining
                                                                              (critical path → green-gate merge)
```

**Critical path.** With Tracks 1 and 2 complete, the only chain to green-gate closure is **SA93** on Track 3: apply the one-file Ruff format → rerun exact `make ci-e2e` → independent review → verify `e2e.yml` on `v87` → mark complete. There is no parallelism left to exploit and no maintainer decision pending.

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join. The per-module gates (all modules closed) plus GATE-lint/typecheck/check/quality are complete on `v87`. **SA93 is the sole remaining blocked checkpoint** — both cross-track blockers are resolved, component Core/CLI E2E is green, and the remaining root-gate path is the recorded Ruff format, exact rerun, and independent review. See the SA93 entry above for the evidence and blocker ledger.

### Track readiness (2026-07-17)

- **Track 1 — COMPLETE.** No remaining open tickets. SA92, SA84, and SA86 all closed with independent review STATUS ok (see [CHANGELOG.md](../../CHANGELOG.md)).
- **Track 2 — COMPLETE.** No remaining open tickets. SA94 (react-only theme, Barrier B STATUS ok) and SA95 (blog regression, closed with no code change) both closed.
- **Track 3 — BLOCKED CHECKPOINT (SA93 open).** Finding 1, all four GATEs, and SA91 are complete. SA93 implementation and component E2E evidence are present; continuation needs the one-file Ruff format, exact `make ci-e2e`, independent review, and green `e2e.yml` evidence. **No maintainer decision and no cross-track prerequisite remain.** SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004 (low/advisory) and SA93-ADV-001 (low/advisory) are non-gating.

**Net — no maintainer decisions pending.** All per-module gates are green; Tracks 1 and 2 are fully complete. **Track 3 can continue deterministically on SA93**: apply the recorded Ruff format, rerun exact `make ci-e2e`, independently review the full delta, and prove E2E success on `v87` — then update CHANGELOG/roadmap and close the milestone. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
