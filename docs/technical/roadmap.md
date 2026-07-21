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

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active work.

The release critical path is fully de-risked in code: the green-gate join (SA96-GATE) is green with empty quarantine, and both installed-wheel blockers (SA109 discovery fix, SA110 installed-artifact smoke gate) are complete, verified, and merged (see [CHANGELOG.md](../../CHANGELOG.md)). Only one item remains open:

1. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. All deps met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓); awaits a human maintainer to execute the irreversible publish. This is the only remaining release-path step.

SA108 (frontend de-specialization migration-doc rewrite, Track 2) is **complete** — closes arch-audit Finding 10. See [CHANGELOG.md](../../CHANGELOG.md) for details. Off the release critical path.

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays unscheduled — SA108's parent chain shrank its surface; sequence any tuple-derivation work after it. Arch Findings **2/4** remain **not ticketed**, deferred with the (unscheduled) teams module.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at the prior synced code baseline (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). The four-command join covers everything end to end — unit **and** integration **and** e2e. `make check` is the **fast** repo gate — `lint` + `typecheck` + `test-unit` (unit only) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`; `make check QUIET=1` is the quiet LLM/agent variant). **Integration coverage lives in `make ci`** (unit + integration when PostgreSQL is available), and e2e in `make ci-e2e` (`.github/workflows/e2e.yml`). So `make check` alone does not prove integration — the `ci`/`ci-e2e` legs of the join do.

The join runs entirely **inside the monorepo** and does **not** exercise the pip-installed wheel — that gap was closed by SA109/SA110 (both complete; see [CHANGELOG.md](../../CHANGELOG.md)). `make smoke-install` builds wheels from per-run staged copies (no source mutation), installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109 ✓ and SA110 ✓ closed (installed wheel runs non-mutating commands clean); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface

**COMPLETE — no open tickets.** All Track 1 work (SA92/SA84/SA86/SA96-T1, Finding 8, SA97/SA99, SA102/SA103, and the full TP test-parallelization suite SA91/TP1/TP2/TP2b/TP3a/TP3b/TP4) is closed. See [CHANGELOG.md](../../CHANGELOG.md). Off the release critical path; none of its changes regressed any gate's pass/fail set or coverage thresholds.

### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

The frontend-theme de-specialization chain (arch-audit Finding 10, `frontend-source-generation-specialized`) de-specializes the `showcase_react` theme so `frontend/src` is project-agnostic and byte-identical across projects on the same theme version, with all project/module facts flowing through the existing `window.__QUICKSCALE__` runtime seam. Stages SA104 → SA105 → SA106 → SA107 are complete (see [CHANGELOG.md](../../CHANGELOG.md)); **SA108** closes the chain. Off the SA96 release critical path; must not regress any gate or coverage threshold.

**File ownership:** SA108 owns `docs/planning/beta-site-migration.md` only — disjoint from the CI/Makefile surfaces and the release path, so it runs fully in parallel with Track 3. Only the shared closeout files (`CHANGELOG.md`, `roadmap.md`) overlap, covered by the Merge procedure.

- [x] **SA108 — Rewrite `beta-site-migration.md` as part of this chain (not deferred).** `Tier 2 · Track 2 · deps: SA105 ✓ + SA106 ✓ + SA107 ✓ · docs-only`
  Finding 10 collapses migration from a per-file merge into "copy user-owned dirs, rebuild" — but that win is only realized when the playbook stops describing the old merge process. `docs/planning/beta-site-migration.md` is the artifact most invalidated by SA105/SA106: its identity-fix step (Step 1 `useModules.ts`/`projectName`, `Sidebar`/`Dashboard` transplant), `main.tsx`-conditional patching, per-module page-copy logic (in-place Step 6), and the per-file classification table all describe the pre-de-specialization scaffold. Rewrite it so the frontend sections reflect the project-agnostic, byte-identical `frontend/src` reality: shrink the fresh-first/in-place frontend transplant steps to the user-owned-dirs copy, drop the now-obsolete identity/module-station patches, and note the dormant-file model (SA105 Option A) so maintainers understand why unselected-module pages appear in their tree.
  - Verify: playbook frontend sections contain no `projectName`/`useModules.ts`/`main.tsx`-conditional patch steps that SA105/SA106 removed; the classification table distinguishes fresh current-theme recipients (all module surfaces as dormant files per SA105) from legacy pre-SA105 in-place recipients (no retroactive dormant guarantee; running `quickscale apply` does not guarantee or backfill blog/crm/listings; post-apply adoption copies only missing forms/social surfaces and does not backfill blog/crm/listings); cross-references to the runtime seam (and SA107 `validateQuickScaleConfig()` fail-hard behavior) are present with correct function names and responsibilities.
  *(why →* the Finding 10 win is not banked until the migration doc matches the new copy-not-merge reality; otherwise the drift moves from generator source into the playbook*)*

### Track 3 — Core/CLI plumbing — release path

**Implementation COMPLETE.** All Track 3 work is closed (arch-audit Finding 1 via SA89a+SA89b; all four GATEs; SA91 parallel worker pool; SA93 e2e in green-gate; SA100 theme preflight; SA101 quality remediation; SA96-GATE join; SA109 installed-wheel discovery fix; SA110 installed-artifact smoke gate). See [CHANGELOG.md](../../CHANGELOG.md). The only remaining Track 3 item is the human-only **SA96-PUBLISH** (above).

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `refresh_managed_adapters`) remain fail-hard.

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (complete)     Track 2 (complete)                   Track 3 → release (critical path)
────────────────────   ────────────────────────────      ─────────────────────────────────
✓ all tickets closed    SA104 ✓ → SA105 ✓ → SA106 ✓        SA96-GATE ✓ ── green-gate join
                          → SA107 ✓ → SA108 ✓               SA109 ✓ ── installed-wheel discovery
                        (arch Finding 10 chain closed)       SA110 ✓ ── installed-artifact smoke
                                                                      │
                                                                      ▼
                                                                SA96-PUBLISH ── build → publish
                                                                  deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓
                                                                  (human-only)
```

**Parallelism.** Exactly one item remains: **SA96-PUBLISH** (Track 3, human-only). SA108 (Track 2, migration-doc rewrite) is complete — its corrections to `beta-site-migration.md` have been finalized alongside this roadmap update (including the legacy compatibility distinction: SA105 dormant-file model guarantees all module surfaces only for fresh current-theme recipients; legacy pre-SA105 recipients have no retroactive dormant guarantee — running `quickscale apply` does not guarantee or backfill blog/crm/listings; the shipped continuation adopts forms/social surfaces only, with no blog/crm/listings backfill). There is no assistant-executable task sharing files with the human-only publish step, so Track 3 has no merge hazard from Track 2 and can proceed independently.

### Track readiness (2026-07-21)

- **Track 1 — COMPLETE (off critical path).** No open tickets.
- **Track 2 — COMPLETE.** Chain stages SA104/SA105/SA106/SA107/SA108 complete. Track 2 frontend de-specialization chain (arch Finding 10) is fully closed. Legacy compatibility finding documented: SA105 dormant-file guarantee applies only to fresh current-theme recipients; legacy pre-SA105 recipients have no retroactive dormant guarantee for any module surface — running `quickscale apply` does not guarantee or backfill blog/crm/listings; the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill). No blocker.
- **Track 3 — implementation COMPLETE; awaiting human publish.** All assistant work closed (SA96-GATE, SA109, SA110, QG proofs done). The remaining **SA96-PUBLISH** is human-only and requires a maintainer to execute the irreversible PyPI publish after confirming version + green-gate status. Not blocked on any engineering work — blocked only on the human decision to publish. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006 low; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Net.** Tracks 1 and 2 are complete; Track 3 has no open assistant work — its only remaining item is the human-only SA96-PUBLISH. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the recorded squash/guardrail/shrink-only-quality policies; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
