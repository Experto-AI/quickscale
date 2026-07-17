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

**Open workstreams before release:**
1. **SA93** (fold the e2e lane into the green-gate definition of done), a blocked checkpoint on Track 3.
2. **Pre-publish verification & release sweep (SA96)** — a fresh per-module test+coverage re-verification across Tracks 1 and 2, then the green-gate join and the staged PyPI publish. Defined in its own milestone below.
3. **Audit remediation backlog (SA97–SA100)** — findings from the 2026-07-17 [tech-audit](../others/tech-audit.md) (TA58/TA59) and [arch-audit](../others/arch-audit.md) (Findings 7 and 9) passes, filled into the idle Track 1/2 capacity. SA97 completed (2026-07-17); the remaining open tickets (SA98–SA100) are independent of the SA93 → SA96-GATE → SA96-PUBLISH critical path and touch no release-gated surface. Defined in the per-track sections below. Arch Findings 2 and 4 stay deferred with the (unscheduled) teams module and are **not ticketed**.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate — CLOSED

All per-module restricted-role gates pass green under the SA82 baseline with an empty quarantine: **CRM (SA84), blog (SA83/SA95), forms (SA85), listings (SA86), orgs (SA77), notifications (SA79)** — see [CHANGELOG.md](../../CHANGELOG.md). The parallelizable per-module axis is complete; only the repo-global e2e closeout (SA93) remains.

#### Repo-global gates (run once at v87 integration, after per-module work lands)

GATE-lint, GATE-typecheck, GATE-check-suite, **GATE-quality**, and the **SA91** parallel worker pool are all **done** (see [CHANGELOG.md](../../CHANGELOG.md)). The remaining closeout is **SA93** (e2e in the green-gate), on Track 3. Both of its former cross-track prerequisites (SA84 CRM, SA95 blog) are now met.

- [ ] **SA93 — Fold the e2e lane into the green-gate definition of done.** `Tier 1 · Track 3 · deps: none remaining (SA84 CRM + SA95 blog prerequisites met)`
  **Blocked checkpoint (2026-07-17; maintainer-selected stop-and-merge; not complete). No maintainer decision remains — continuation is the exact broad rerun and independent review.**

  Implemented/landed evidence (deterministic fixes, component E2E green, review CR-SA93-REV-001/002/003/004 resolved) is recorded in [CHANGELOG.md §SA93 continuation](../../CHANGELOG.md). What remains is exact root-gate closure and final review only.

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

A fresh, pre-release re-verification pass. The per-module gates are green under the SA82 baseline; this milestone **re-ran each module in isolation on the current `v87`** to confirm no regression before publishing (SA96-T1 + SA96-T2, both complete — see [CHANGELOG.md](../../CHANGELOG.md)), then executes the green-gate join and the staged PyPI ladder. Track 3 continued SA93 in parallel.

> **SA96-T1 (Track 1 module sweep) and SA96-T2 (Track 2 module sweep) are complete** (2026-07-17) — analytics · auth · backups · billing · blog · crm and forms · listings · notifications · orgs · social · storage all re-verified green in isolation on the post-SA92 `v87` baseline, no regression, empty quarantine. Full evidence in [CHANGELOG.md](../../CHANGELOG.md). **SA93 is the sole remaining input to SA96-GATE.**

- [ ] **SA96-GATE — Green-gate join (cross-track).** `Tier 1 · v87 integration · deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93`
  After both module sweeps **and** SA93 land, on a fresh clone + fresh `migrate` (post-SA92 squash) run until all exit 0 with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`:
  `make check` → `make quality` → `make ci` → `make ci-e2e`. All four green + empty quarantine = publishable (single definition of done, see the exit-criteria above).

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE`
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — confirm version + green-gate status before `publish-prod`.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — SA97 completed (audit remediation)

Prior development tickets closed — SA92 (migration squash to final-schema `0001_initial`), SA84 (CRM restricted-role fixtures), SA86 (listings); the pre-publish sweep **SA96-T1** closed 2026-07-17. See [CHANGELOG.md](../../CHANGELOG.md). The squash eliminated the cross-org-*migration* half of arch-audit [Finding 8](../others/arch-audit.md) and SA84/SA86 drained the surviving **fixture** half — Finding 8 is now closed. Full decision record: [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92). Track 1 picks up the arch-audit **Finding 9** test-plumbing half from its freed capacity.

- [x] **SA97 — Commons rule + consolidate the tenant test-state reset plumbing.** `Tier 2 · Track 1 · deps: none`
  arch-audit [Finding 9](../others/arch-audit.md) (`module-commons-unowned`), Option 1 — test-plumbing half. The pattern fired twice this delta (SA84, SA85 landed near-identical hand-rolled autouse `_reset_test_state` fixtures in crm/forms; blog carries a third divergent ContextVar-only variant), while the sanctioned commons `tests_shared/isolation.py` has exactly one consumer.
  - Record the commons rule in [decisions.md](./decisions.md): **orgs** owns org-context runtime helpers; **`tests_shared/`** owns cross-module test plumbing. Cite the SA92 `apply_force_rls`/`revert_force_rls` seam as the house pattern (a working shared-commons precedent).
  - Promote the crm/forms `_reset_test_state` fixture into a conftest-importable fixture module under `tests_shared/`; point crm (`tests/conftest.py:43-83`), forms (`tests/conftest.py:63-90`), and blog (`tests/conftest.py:187-198`, reconciling its divergent variant) at the single implementation.
  - Verify: full restricted-role suite stays green under an empty quarantine after the consolidation; no module conftest keeps a private copy of the reset contract.
  *(why →* arch-audit Finding 9, Option 1 (recommended) — the glue is where the SA83–SA86 failures lived; divergent copies risk false-green isolation tests*)*

  **Completed (2026-07-17).** Independent change-review pass 2 returned **STATUS ok**; CR-SA97-001 (medium/blocking) resolved — six shared imports replace all private reset definitions; zero private copies remain. `make test-integration`: all 12 modules pass, empty quarantine, 94.39% mean coverage.
  - **CR-SA97-002 (low/advisory):** `tests_shared/reset_state.py` — no direct lifecycle edge-case test for the shared fixture. Non-blocking.
  - **CR-SA97-003 (low/advisory):** `tests_shared/reset_state.py:4-6` — docstring states three copies unified, but six consumers were actually migrated. Non-blocking.

### Track 2 — Module contracts & settings — SA98/SA99 open (audit remediation)

Prior development tickets closed — SA88b (forms diagnosis), SA86 (listings), GATE-lint / GATE-typecheck / GATE-check-suite, SA94 (react-only theme + Barrier B review), SA95 (blog fixture-finalizer regression); the pre-publish sweep **SA96-T2** closed 2026-07-17. See [CHANGELOG.md](../../CHANGELOG.md). The GATE-quality / SA91 / SA93 closeout items were reassigned to the freed Track 3. Track 2 picks up the arch-audit **Finding 9** runtime-copy half and **Finding 7**'s cheap sub-item.

- [ ] **SA98 — Consolidate the `_sanitize_href`/`_sanitize_rendered_html` sanitizer copy-pair.** `Tier 2 · Track 2 · deps: SA97 (commons rule) — soft`
  arch-audit [Finding 9](../others/arch-audit.md), Option 1 — runtime half (SA26 lineage, sixth pass unconsolidated). The XSS-sensitive sanitizer is byte-similar in `blog/views.py:69-115` and `listings/views.py:42-88` with no parity test or gate.
  - Move the sanitizer to the single sanctioned runtime home named by the SA97 commons rule; have blog and listings both consume it.
  - Verify: the existing sanitizer regression suites (blog + listings) pass against the shared implementation; no second copy remains. If a deliberate copy is retained instead of consolidated, gate it byte-identical like the module.yml pairs (Finding 9 Option 2 fallback — not preferred).
  *(why →* arch-audit Finding 9 — one-sided fixes to a duplicated sanitizer are an XSS-class drift on public pages*)*

- [ ] **SA99 — Bring `quickscale_devtools` into the ruff/mypy universe.** `Tier 1 · Track 2 · deps: none`
  arch-audit [Finding 7](../others/arch-audit.md) (`generated-file-ownership-unmodeled`) cheap sub-item. `quickscale_devtools` is import-load-bearing for the release gate (its conformance test runs in ci.yml/publish.yml unit stages) yet sits outside `ruff.toml`, `mypy.ini`, and the Makefile lint/typecheck targets.
  - Add `quickscale_devtools` to `ruff.toml` and `mypy.ini` (and the Makefile typecheck loop if it enumerates packages); fix any lint/type findings the newly-covered package surfaces.
  - Verify: `make lint` and `make typecheck` cover devtools and exit 0. The Finding 7 tuple-derivation remainder (deriving `beta_migration.py`'s taxonomy from `get_generator_emission_mapping()`) stays **unscheduled**, correctly gated on a third consumer / public update command — out of scope here.
  *(why →* arch-audit Finding 7 — removes the ungoverned-but-load-bearing edge for one config line each*)*

### Track 3 — Core/CLI plumbing — SA93 open

> **Finding 1 closed.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed by SA89a + SA89b — see [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

Finding 1 (DR persistence port, SA89a+SA89b), all four GATEs, and **SA91** (parallel integration worker pool) are complete — see [CHANGELOG.md](../../CHANGELOG.md). SA91 retains **CR-SA91-REV-006** (low/advisory, throughput only). The single open item is **SA93** (fold e2e into the green-gate), defined in the green-gate section above — its implementation and component E2E evidence are present, but exact root-gate closure and independent final review remain open. **No cross-track prerequisite or maintainer decision remains.**

- [ ] **SA100 — Fix the `up` recovery-ledger theme exemption + remove the dead probe constant.** `Tier 1 · Track 3 · deps: fold into SA93 independent review`
  Two S4 tech-audit findings, both in the theme-preflight surface the SA93 checkpoint touched — [tech-audit](../others/tech-audit.md) TA58/TA59. TA58 landed in the SA93 checkpoint `022a88fb`, so it should ride SA93's pending independent review rather than a separate PR.
  - **TA58** (`development_commands.py:281-303`, `up`): the exemption keys on any single-line `"recovery ledger"` error, so a stale ledger carrying retired `showcase_html` or missing `project.theme` passes `up` silently — broader than the `__checkpoint__` placeholder rationale. Fix: key the exemption on `theme == "__checkpoint__"` (via a `validate_theme_preflight` variant flag or a per-error `theme` attribute on the aggregate error), not on the source label. Also fix the two `.quickscape` typos in the adjacent comments.
  - **TA59** (`quickscale_core/utils/theme_validation.py:70-73`): delete the dead `_RECOVERY_PROBE_PATHS` constant (referenced nowhere; the preflight probes `_RECOVERY_FILE` directly).
  - Verify: a test that `up` **fails** (with remediation text) on a recovery ledger carrying `showcase_html`, and **proceeds** on one carrying `__checkpoint__`.
  *(why →* tech-audit TA58 (declared-invariant / quick win) + TA59 (dead code); TA58 softened a barrier SA94 had just erected*)*

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92/SA84/SA86 ✓ (dev tickets)      SA94/SA88b/SA86/SA95 ✓ (dev tickets)    Finding 1 ✓ (SA89a+SA89b)
SA96-T1 ── module sweep ✓            SA96-T2 ── module sweep ✓               GATE-lint/typecheck/check/quality ✓
                                                                            SA91 ✓ (parallel loop, non-gating)
SA97 ✓ ── commons rule + reset      SA98 ── sanitizer consolidation         SA93 ── e2e in green-gate (open)
          fixture (F9 test half)              (F9 runtime half) deps: SA97·soft SA100 ── TA58/TA59 theme preflight
                                     SA99 ── devtools→ruff/mypy (F7 cheap)           (rides SA93 review)
        │                                     │                                       │
        └──────────────┬──────────────────────┴───────────────────────────────────────┘
                       ▼   (SA97/98/99/100 are off the release critical path — independent)
        SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 + SA96-T2 + SA93
                       ▼
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE
```

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** remains the sole open input to the **SA96-GATE** cross-track join; **SA96-PUBLISH** follows that join. The remaining SA93 path is exact `make ci-e2e` → independent review → green `e2e.yml` evidence on `v87` → close SA93. **SA100** (TA58/TA59) folds into that same SA93 independent review. The audit-remediation tickets **SA97** (completed), **SA98**, and **SA99** are independent of the release critical path (SA98's dependency on the SA97 commons rule is now satisfied); none blocks SA96-GATE.

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). It cannot start until both completed module sweeps and SA93 are present. SA93's cross-track blockers are resolved, component Core/CLI E2E is green, and the remaining root-gate path is the exact rerun and independent review recorded above.

### Track readiness (2026-07-17)

- **Track 1 — release tickets closed; SA97 completed.** Release tickets closed (SA92, SA84, SA86, SA96-T1). **SA97** (arch Finding 9 test-plumbing half) completed 2026-07-17 — independent of the release path. Evidence in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 2 — release tickets closed; SA98/SA99 open (audit).** Release tickets closed (SA94, SA88b, SA86, SA95, SA96-T2). Now carries **SA98** (arch Finding 9 sanitizer half, soft-deps SA97) and **SA99** (arch Finding 7 devtools→ruff/mypy) — both independent of the release path. Evidence in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 3 — NOT BLOCKED ON A DECISION; execution pending (SA93 + SA100 open).** Finding 1, all four GATEs, and SA91 are complete. SA93 continuation is the exact `make ci-e2e` rerun, independent review, and green `e2e.yml` evidence — no maintainer decision and no cross-track prerequisite remain; **SA100** (tech-audit TA58/TA59) folds into that same review. SA91 retains CR-SA91-REV-006 (low/advisory); SA89B-CR-004 and SA93-ADV-001 are non-gating low advisories.

**Net — no maintainer decisions pending.** Both pre-publish module sweeps are complete (SA96-T1 and SA96-T2); SA93 (+ SA100, riding its review) continues on the release path. The audit-remediation tickets SA98 and SA99 run in Track 2 (SA97 completed on Track 1), independent of the SA93 → SA96-GATE → SA96-PUBLISH chain. Rerun exact `make ci-e2e`, independently review the full SA93 delta, and prove E2E success on `v87`; then SA96-GATE can run the four-command publishability join and SA96-PUBLISH can proceed. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
