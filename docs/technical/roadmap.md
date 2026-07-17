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
  **Blocked checkpoint (2026-07-17; maintainer-selected stop-and-merge; not complete). No maintainer decision remains — continuation is the exact broad rerun and independent review.**

  **Implemented/evidence available (not final closure):**
  - Added the combined core/CLI/backups coverage path, `scripts/check_coverage_policy.py`, maintained helper tests, and focused DR-engine lock/path/sidecar tests.
  - Implemented **CR-SA93-REV-002** fail-closed coverage parsing: validate JSON roots and file records, require both core and CLI package populations, reject non-canonical traversal paths, and cover malformed/missing-package/traversal cases. Focused evidence: **37/37 helper tests passed**, Ruff passed, and `bash -n scripts/check_ci_locally.sh` passed.
  - Implemented **CR-SA93-REV-004** conditional CI stage totals: non-E2E runs use 11 numbered stages, E2E runs use 12, and the skip message is unnumbered.
  - Removed the Stage-12 environment/test blockers exposed by the first broad rerun: aligned the forms `django-filter` expectation, isolated each Core E2E database through pytest-docker, removed the ambient `localhost:5432` dependency, hardened CLI Docker cleanup/readiness and development-command database-role handling, and repaired the no-modules React TypeScript contract. The explicit maintainer decision is recorded in the implementation: `QuickScaleModules.auth` is always typed/defaulted false while runtime availability still gates visibility.
  - Phase evidence is green: **35/35 Core E2E**, **29/29 CLI E2E**, **470/470 CLI unit tests**, **82/82 React template/integration tests**, the original Docker/apply migration test, and a real no-modules `pnpm` type-check/build proof all passed with no relevant E2E skips. These component results do not replace the required exact root gate.
  - The final exact `make ci-e2e` attempt reached the normalized 12-stage flow: dependency installation passed; Ruff lint checks passed; Ruff format-check then stopped Stage 2 on one formatting-only diff in `quickscale_core/tests/generator/test_themes.py`. Stages 3–12 were therefore not reached in that exact run.
  - The checkpoint commit hook subsequently applied Ruff formatting to the staged Python delta and completed `ruff check` plus `ruff format` successfully. This removes the observed formatting defect, but the exact root gate has not been rerun and final disposition remains pending validation/review.
  - Independent review resolved **CR-SA93-REV-001** (equal-package arithmetic/final authority) and **CR-SA93-REV-003** (maintained helper-test collection).

  **Pending/Blocking:**
  - **SA93-BLOCK-002 (high/blocking):** exact root-gate closure remains unproven because the latest `make ci-e2e` stopped at Stage 2 before coverage, integration, and E2E. Rerun exact `make ci-e2e` with sufficient timeout and require exit 0 with all 12 stages, both E2E suites, unchanged thresholds, and an empty quarantine.
  - **Final review/CI evidence:** independently review the complete SA93 delta (including CR-SA93-REV-002/004, database isolation, CLI lifecycle behavior, and the generated React contract), then verify `.github/workflows/e2e.yml` is green on `v87` before marking SA93 complete.
  - **SA93-ADV-001 (low/advisory):** pytest reports a future pytest-10 warning for the class-scoped fixture pattern in `TestReactThemePnpmIntegration.test_pnpm_install_succeeds`; it does not block the current gate but should be normalized before a pytest 10 upgrade.

  **Resolved prerequisites:** SA93-BLOCK-001 (blog + CRM integration fixture-finalizer failures) is resolved — blog closed by **SA95** (2026-07-17, no reproducible defect on post-SA92 v87) and CRM closed by **SA84** (2026-07-17, 263 pass/21 skip/0 fail, review STATUS ok). Both former cross-track prerequisites for SA93 are met. Preserve the exact unquarantined `make ci-e2e` contract; quarantine and threshold weakening are not acceptable.

  **Clean continuation:** no design or maintainer decision is pending. Resume with the exact worktree sequence below, then independently review the full SA93 delta, verify `e2e.yml` is green on `v87`, and update CHANGELOG/roadmap before marking SA93 complete.

  ```bash
  cd /home/victor/code/quickscale-wt-track3
  git status                 # must be clean
  git merge v87              # resync the merged checkpoint
  make ci-e2e                # allow sufficient time for all 12 stages
  ```

  *(Acceptance:* `make ci-e2e` exits 0 on a fresh clone; `e2e.yml` green on `v87`; exit-criteria prose lists the e2e lane.*)*
  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Pre-publish verification & release sweep (SA96)

A fresh, pre-release re-verification pass. The per-module gates are already green under the SA82 baseline (see the CLOSED section above); this milestone **re-runs each module in isolation on the current `v87`** to confirm no regression before publishing, then executes the green-gate join and the staged PyPI ladder. Split across the two freed tracks (Track 3 continues SA93 in parallel).

**Inner loop (per module).** For each module run `make MODULE=<name> test -- --modules`; fix→iterate until green with per-file 80% / mean 90% coverage floors satisfied. Commit fixes on the owning track branch — never on `v87`.

- [x] **SA96-T1 — Track 1 module sweep.** `Tier 1 · Track 1 · deps: none`
  Re-verify (in isolation) each of: **analytics · auth · backups · billing · blog · crm**. Notes: `backups` also feeds the combined core/CLI/backups coverage path in `ci-e2e` (SA93); `blog` re-verify no fixture-finalizer regression (SA83/SA95); `crm` re-verify restricted-role fixture isolation (SA84).

  **Verification evidence (2026-07-17, wt-track1 @ f0368dc4):** Six `make MODULE=<name> test -- --modules` runs executed serially. All pass with no unqualified failures. Module test-settings DB_USER default changed from `postgres` to `quickscale_test_role` in auth, billing, blog, and crm (they include `quickscale_modules_orgs` in INSTALLED_APPS, which triggers the SA58 RLS boot guard; the pre-provisioned `quickscale_test_role` has NOBYPASSRLS NOSUPERUSER and satisfies the guard). Detailed results:

  | Module  | Passed | Skipped | Time  |
  |---------|--------|---------|-------|
  | analytics | 40    | 0       | 0.94s |
  | auth      | 55    | 0       | 14.25s |
  | backups   | 323   | 2       | 66.99s |
  | billing   | 216   | 20      | 38.80s |
  | blog      | 211   | 0       | 40.04s |
  | crm       | 263   | 21      | 79.03s |

  Skipped tests are pre-existing `@pytest.mark.bypass_rls` tests (requiring `QUICKSCALE_ALLOW_BYPASSRLS=1`). No module-suite regression found. Coverage floors not measured in this pass (deferred to SA96-GATE closeout). The `quickscale_test_role` default-user fix applies only to the isolated `make MODULE=... test -- --modules` path; `scripts/test_integration.sh` already set the env vars.

  **Discovery:** Four modules (auth, billing, blog, crm) initially hit the SA58 RLS boot guard because `DB_USER` defaulted to `postgres` (superuser). The default was aligned to the pre-provisioned `quickscale_test_role` (NOBYPASSRLS NOSUPERUSER), matching the pattern used by `scripts/test_integration.sh`, while preserving caller env-var overrides.

  **Validation evidence:** Six focused module suites — 1108 passed / 43 skipped / 0 failed. Maintained full integration (all 12 modules) — 2456 passed / 86 skipped / 0 failed/errors, 94.40% equal-weight mean, no file below 80%, quarantine empty. Independent change-review: **STATUS ok / no findings**. Closes SA96-T1.

- [x] **SA96-T2 — Track 2 module sweep.** `Tier 1 · Track 2 · deps: none`
  Re-verify (in isolation) each of: **forms · listings · notifications · orgs · social · storage**. Notes: `orgs` is the largest suite (tenant-table + RLS conformance, SA77); `notifications`→`forms` cross-module import resolves during bootstrap (SA79); **`storage` has only one test file — the module most likely to fall short of the mean-90% floor; add tests if needed.**
  > **`teams` is excluded** — 0 test files (deferred/unscheduled per both audits). It still globs into `quickscale_modules/*`; confirm the sharded loop skips zero-test modules, otherwise it becomes a hidden 13th task.

  **Evidence (2026-07-17):** All six module Make suites passed in isolation under the retained-role contract (SA82 baseline). All commands exited 0. Worker-pool skip proof confirmed zero-test modules are safely excluded — teams is correctly skipped, not a hidden 13th task. No remediation, blockers, quarantine, or source/test changes were needed — every module passed as-is.

  | Module | Results | Coverage | Lowest file |
  |---|---|---|---|
  | forms | 180 passed / 32 skipped / 12 deselected | 95.73% | admin.py 86.25% |
  | listings | 137 passed | 95.74% | views.py 92.77% |
  | notifications | 39 passed | 91.76% | services.py 88.42% |
  | orgs | 858 passed / 11 skipped | 93.08% | adapters.py 87.72% |
  | social | 108 passed | 95.11% | models.py 93.66% |
  | storage | 26 passed | 97.73% | helpers.py 97.60% |

  All per-file values ≥80%, all package means ≥90%. Storage exceeded expectations at 97.73% (lowest helpers.py 97.60%) — no additional tests were needed. SA96-T2 complete.

- [ ] **SA96-GATE — Green-gate join (cross-track).** `Tier 1 · v87 integration · deps: SA96-T1 + SA96-T2 + SA93`
  After both module sweeps **and** SA93 land, on a fresh clone + fresh `migrate` (post-SA92 squash) run until all exit 0 with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`:
  `make check` → `make quality` → `make ci` → `make ci-e2e`. All four green + empty quarantine = publishable (single definition of done, see the exit-criteria above).

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE`
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — confirm version + green-gate status before `publish-prod`.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — SA96-T1 closed

Prior development tickets all closed — SA92 (migration squash to final-schema `0001_initial`), SA84 (CRM restricted-role fixtures), and SA86 (listings); see [CHANGELOG.md](../../CHANGELOG.md). The squash eliminated the cross-org-*migration* half of arch-audit [Finding 8](../others/arch-audit.md); the surviving **fixture** half (SA84 CRM, SA86 listings) is drained. SA95 (blog) was reassigned to Track 2 and closed there. Full decision record: [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92).

**Reactivated for the pre-publish sweep:** completed **SA96-T1** — re-verified analytics · auth · backups · billing · blog · crm in isolation (see the Pre-publish milestone above).

### Track 2 — Module contracts & settings — SA96-T2 completed

Prior development tickets all closed — SA88b (forms diagnosis), SA86 (listings), GATE-lint / GATE-typecheck / GATE-check-suite, SA94 (react-only theme + Barrier B review), and SA95 (blog fixture-finalizer regression — closed with no reproducible defect on the post-SA92 v87 baseline); see [CHANGELOG.md](../../CHANGELOG.md). The GATE-quality / SA91 / SA93 closeout items were reassigned to the freed Track 3.

**Reactivated for the pre-publish sweep:** ticket **SA96-T2** completed (2026-07-17) — all six modules (forms · listings · notifications · orgs · social · storage) passed in isolation under the retained-role contract with no remediation, blockers, quarantine, or source/test changes. See the checked SA96-T2 entry above for the full evidence table.

### Track 3 — Core/CLI plumbing — SA93 open

> **Finding 1 closed.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed by SA89a + SA89b — see [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

Finding 1 (DR persistence port, SA89a+SA89b), all four GATEs, and **SA91** (parallel integration worker pool) are complete — see [CHANGELOG.md](../../CHANGELOG.md). SA91 retains **CR-SA91-REV-006** (low/advisory, throughput only). The single open item is **SA93** (fold e2e into the green-gate), defined in the green-gate section above — its implementation and component E2E evidence are present, but exact root-gate closure and independent final review remain open. **No cross-track prerequisite or maintainer decision remains.**

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92/SA84/SA86 ✓ (dev tickets)      SA94/SA88b/SA86/SA95 ✓ (dev tickets)    Finding 1 ✓ (SA89a+SA89b)
                                                                            GATE-lint/typecheck/check/quality ✓
SA96-T1 ── module sweep ✓      SA96-T2 ── module sweep ✓          SA91 ✓ (parallel loop, non-gating)
 analytics·auth·backups·             forms·listings·notifications·          SA93 ── e2e in green-gate (blocked)
 billing·blog·crm                    orgs·social·storage                     deps: none remaining
        │                                     │                                       │
        └──────────────┬──────────────────────┴───────────────────────────────────────┘
                       ▼
        SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 + SA96-T2 + SA93
                       ▼
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE
```

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** remains the sole open input to the **SA96-GATE** cross-track join; **SA96-PUBLISH** follows that join. The remaining SA93 path is exact `make ci-e2e` → independent review → green `e2e.yml` evidence on `v87` → close SA93.

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). It cannot start until both completed module sweeps and SA93 are present. SA93's cross-track blockers are resolved, component Core/CLI E2E is green, and the remaining root-gate path is the exact rerun and independent review recorded above.

### Track readiness (2026-07-17)

- **Track 1 — SA96-T1 complete (all modules green).** All prior dev tickets (SA92, SA84, SA86) closed. The pre-publish module sweep (SA96-T1) completed: six focused suites 1108 passed/43 skipped/0 failed; maintained full integration 2456 passed/86 skipped/0 failed/errors; 94.40% equal-weight mean, no file below 80%, empty quarantine; independent review STATUS ok/no findings.
- **Track 2 — SA96-T2 completed (2026-07-17).** All prior dev tickets (SA94, SA88b, SA86, SA95) closed. The per-module re-verification sweep (forms · listings · notifications · orgs · social · storage) is complete with no remediation, blockers, quarantine, or source/test changes. Every per-file value ≥80%, every package mean ≥90%. Storage exceeded expectations at 97.73% (lowest helpers.py 97.60%) — no additional tests were needed. See the checked SA96-T2 entry above for the full evidence table.
- **Track 3 — BLOCKED CHECKPOINT (SA93 open).** Finding 1, all four GATEs, and SA91 are complete. SA93 implementation, hook-applied formatting, and component E2E evidence are present; continuation needs exact `make ci-e2e`, independent review, and green `e2e.yml` evidence. **No maintainer decision and no cross-track prerequisite remain.** SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004 (low/advisory) and SA93-ADV-001 (low/advisory) are non-gating.

**Net — no maintainer decisions pending.** Both pre-publish module sweeps are complete (SA96-T1 and SA96-T2); SA93 continues as the sole remaining open item. Rerun exact `make ci-e2e`, independently review the full SA93 delta, and prove E2E success on `v87`; then SA96-GATE can run the four-command publishability join and SA96-PUBLISH can proceed. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
