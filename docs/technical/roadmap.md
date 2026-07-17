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

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is green with all per-module restricted-role gates closed. See [CHANGELOG.md](../../CHANGELOG.md).

**Open workstreams before release:**
1. **SA93** (e2e in the green-gate) on Track 3 — the sole open input to the green-gate join.
2. **SA96-GATE → SA96-PUBLISH** (green-gate join → staged PyPI publish), deps on SA93.
3. **Audit remediation (SA97–SA100)** in freed Track 1/2/3 capacity — arch-audit Finding 7 cheap sub-item (SA99), Finding 9 test-plumbing and runtime halves (SA97/SA98), and tech-audit TA58/TA59 (SA100, rides SA93 review). Arch Findings 2 and 4 stay deferred with the (unscheduled) teams module — **not ticketed**.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gates and repo-global gates — CLOSED

All per-module restricted-role gates (CRM/SA84, blog/SA83+SA95, forms/SA85, listings/SA86, orgs/SA77, notifications/SA79) and repo-global gates (GATE-lint, GATE-typecheck, GATE-check-suite, GATE-quality, SA91 parallel worker pool) are **complete**. Only **SA93** (e2e in the green-gate) remains on Track 3 — both former cross-track prerequisites (SA84 CRM, SA95 blog) are met. See [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA93 — Fold the e2e lane into the green-gate definition of done.** `Tier 1 · Track 3 · deps: none`
  **Blocked checkpoint (2026-07-17; maintainer-selected stop-and-merge; not complete). No maintainer decision remains — exact rerun and independent review only.**

  **Pending/Blocking:**
  - **SA93-BLOCK-002 (high/blocking):** latest `make ci-e2e` stopped at Stage 2 before coverage, integration, and E2E. Rerun with sufficient timeout; require exit 0 with all 12 stages, both E2E suites, unchanged thresholds, empty quarantine.
  - **Final review:** independently review the complete SA93 delta (CR-SA93-REV-002/004, DB isolation, CLI lifecycle, generated React contract); verify `e2e.yml` green on `v87`.
  - **SA93-ADV-001 (low/advisory):** future pytest-10 warning in `TestReactThemePnpmIntegration.test_pnpm_install_succeeds` — not blocking.

  **Cross-track prerequisites resolved:** SA95 (blog) and SA84 (CRM) closed. See [CHANGELOG.md](../../CHANGELOG.md) for implemented/landed evidence (deterministic fixes, component E2E green, resolved review items).

  ```bash
  cd /home/victor/code/quickscale-wt-track3
  git status && git merge v87 && make ci-e2e
  ```

  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Pre-publish verification & release sweep (SA96)

Pre-release re-verification: **SA96-T1 (Track 1) and SA96-T2 (Track 2) module sweeps are complete** — all 12 modules re-verified green in isolation on post-SA92 v87, no regression, empty quarantine. **SA93 is the sole remaining input to SA96-GATE.** See [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA96-GATE — Green-gate join (cross-track).** `Tier 1 · v87 integration · deps: SA96-T1 ✓ + SA96-T2 ✓ + SA93`
  After both module sweeps **and** SA93 land, on a fresh clone + fresh `migrate` (post-SA92 squash) run until all exit 0 with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`:
  `make check` → `make quality` → `make ci` → `make ci-e2e`. All four green + empty quarantine = publishable (single definition of done, see the exit-criteria above).

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE`
  Only after SA96-GATE passes. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — confirm version + green-gate status before `publish-prod`.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — SA97/SA99 open (audit remediation)

Prior development tickets closed — SA92 (migration squash), SA84 (CRM restricted-role), SA86 (listings), **SA96-T1** module sweep, Finding 8 closed. Track 1 picks up the arch-audit **Finding 9** test-plumbing half (SA97) and **Finding 7**'s cheap sub-item (SA99, moved from Track 2 for parallelism — no file conflicts or ordering deps with SA97).

- [ ] **SA97 — Commons rule + consolidate the tenant test-state reset plumbing.** `Tier 2 · Track 1 · deps: none`
  arch-audit [Finding 9](../others/arch-audit.md) (`module-commons-unowned`), Option 1 — test-plumbing half. Three divergent `_reset_test_state` fixture variants in crm/forms/blog; sanctioned `tests_shared/isolation.py` has one consumer.
  - Record the commons rule in [decisions.md](./decisions.md): **orgs** owns org-context runtime helpers; **`tests_shared/`** owns cross-module test plumbing. Cite the SA92 `apply_force_rls`/`revert_force_rls` seam as the house pattern.
  - Promote the crm/forms `_reset_test_state` fixture into a conftest-importable module under `tests_shared/`; point crm/forms/blog at it (reconciling blog's divergent ContextVar-only variant).
  - Verify: full restricted-role suite stays green under empty quarantine; no module conftest keeps a private copy.
  *(why →* arch-audit Finding 9, Option 1 — the glue is where the SA83–SA86 failures lived*)*

- [ ] **SA99 — Bring `quickscale_devtools` into the ruff/mypy universe.** `Tier 1 · Track 1 · deps: none`
  arch-audit [Finding 7](../others/arch-audit.md) (`generated-file-ownership-unmodeled`) cheap sub-item. `quickscale_devtools` is import-load-bearing for the release gate yet sits outside `ruff.toml`, `mypy.ini`, and Makefile lint/typecheck targets.
  - Add `quickscale_devtools` to `ruff.toml` and `mypy.ini` (and Makefile typecheck loop if it enumerates packages); fix any newly-surfaced lint/type findings.
  - Verify: `make lint` and `make typecheck` cover devtools and exit 0. Finding 7 tuple-derivation remainder stays **unscheduled** (gated on third consumer / public update command).
  *(why →* arch-audit Finding 7 — removes the ungoverned-but-load-bearing edge*)*

### Track 2 — Module contracts & settings — SA98 open (audit remediation)

Prior development tickets closed — SA88b (forms diagnosis), SA86 (listings), SA94 (react-only theme), SA95 (blog fixture-finalizer regression), GATE-lint/typecheck/check-suite, **SA96-T2** module sweep. **SA99 moved to Track 1 for parallelism** (independent, no file conflicts). Track 2 picks up the arch-audit **Finding 9** runtime-copy half.

- [ ] **SA98 — Consolidate the `_sanitize_href`/`_sanitize_rendered_html` sanitizer copy-pair.** `Tier 2 · Track 2 · deps: SA97 (commons rule) — soft`
  **Blocked on SA97.** The maintainer-selected sequence requires SA97's commons-rule decision to land before SA98 implementation begins.

  arch-audit [Finding 9](../others/arch-audit.md), Option 1 — runtime half (sixth pass unconsolidated). Byte-similar sanitizer in `blog/views.py:69-115` and `listings/views.py:42-88` with no parity test or gate.
  - After SA97 lands: merge `v87`, use SA97's sanctioned runtime home if the rule applies; otherwise record an explicit sanitizer-home decision. Move the sanitizer there, have blog and listings consume it.
  - Verify: both sanitizer regression suites pass against the shared implementation; no second copy remains.
  *(why →* arch-audit Finding 9 — one-sided fixes to a duplicated sanitizer are XSS-class drift on public pages*)*

### Track 3 — Core/CLI plumbing — SA93/SA100 open

arch-audit **Finding 1** closed (SA89a+SA89b, DR persistence port). All four GATEs and **SA91** (parallel worker pool) are complete. The single open release-path item is **SA93** (e2e in green-gate) — implementation and component E2E evidence present, exact root-gate closure and independent final review remain. **SA100** (tech-audit TA58/TA59) rides SA93's pending review. **No cross-track prerequisite or maintainer decision remains.**

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
SA97 ── commons rule + reset        SA98 ── sanitizer consolidation         SA93 ── e2e in green-gate (open)
        fixture (F9 test half)              (F9 runtime half) deps: SA97·soft SA100 ── TA58/TA59 theme preflight
SA99 ── devtools→ruff/mypy (F7)                                                    (rides SA93 review)
        │                                     │                                       │
        └──────────────┬──────────────────────┴───────────────────────────────────────┘
                       ▼   (SA97/98/99/100 are off the release critical path — independent)
        SA96-GATE ── green-gate join (make check/quality/ci/ci-e2e)  deps: SA96-T1 + SA96-T2 + SA93
                       ▼
        SA96-PUBLISH ── build → publish-test → publish-prod          deps: SA96-GATE
```

**Critical path.** Both pre-publish module sweeps are complete: **SA96-T1** (Track 1) and **SA96-T2** (Track 2). **SA93** is the sole open input to **SA96-GATE**; **SA96-PUBLISH** follows. The remaining SA93 path is exact `make ci-e2e` → independent review → green `e2e.yml` on `v87` → close SA93. **SA100** (TA58/TA59) folds into that same review. The audit-remediation tickets **SA97/SA98/SA99** are independent of the release critical path — none blocks SA96-GATE. SA99 (moved to Track 1) runs in parallel with SA97 (different files, no ordering deps). SA98 remains soft-blocked on SA97's commons-rule checkpoint; a sanitizer-home decision is needed only if the merged SA97 rule does not cover that helper.

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join (SA96-GATE). It cannot start until both module sweeps and SA93 are complete. SA93's cross-track blockers are resolved; remaining root-gate path is the exact rerun and independent review.

### Track readiness (2026-07-17)

- **Track 1 — clean to continue (SA97 + SA99, both independent).** Release tickets closed (SA92, SA84, SA86, SA96-T1). Now carries **SA97** (arch Finding 9 test-plumbing half) and **SA99** (arch Finding 7 devtools→ruff/mypy, moved from Track 2) — both independent of each other and of the release path. SA97 and SA99 touch different files (conftests vs config files) with no ordering deps, so they can run in parallel on the same track.
- **Track 2 — blocked on SA97 (SA98 only).** Release tickets closed (SA94, SA88b, SA86, SA95, SA96-T2). Carries **SA98** (arch Finding 9 sanitizer half, soft-deps SA97). **SA98 cannot start until SA97's commons-rule decision lands on `v87`.** SA99 moved to Track 1 for better parallelism. The maintainer must decide: either (a) wait for SA97 and follow its rule, or (b) record a provisional sanitizer-home decision on Track 2 now and reconcile later — option (a) was previously selected and remains the lower-risk path.
- **Track 3 — NOT BLOCKED ON A DECISION; execution pending (SA93 + SA100).** Finding 1, all four GATEs, and SA91 are complete. SA93 continuation is the exact `make ci-e2e` rerun, independent review, and green `e2e.yml` evidence — no maintainer decision or cross-track prerequisite remains; **SA100** folds into the same review. Non-gating: CR-SA91-REV-006 (low/advisory), SA89B-CR-004, SA93-ADV-001.

**Net — no release-path maintainer decisions pending.** SA93 (+ SA100) is the sole release-path item. The audit-remediation tickets SA97/SA98/SA99 run in Track 1/2 capacity, independent of the critical path. SA98 waits for SA97 per the previously selected sequence; a sanitizer-home decision is needed only if the merged SA97 rule does not cover that helper. **Proposed rebalance applied:** SA99 moved from Track 2 to Track 1 (independent workload, no file conflicts, no ordering deps) — pure speedup, no downside for Track 2's closeout since SA98 is already blocked on SA97. Full decision trail in [CHANGELOG.md](../../CHANGELOG.md); squash-migrations decision in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
