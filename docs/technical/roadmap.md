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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA21.2 (2026-07-07), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA41 (2026-07-07), SA42 (2026-07-07), SA43 (2026-07-07), SA44 (2026-07-07), SA45 (2026-07-06), SA46 (2026-07-07), SA47 (2026-07-07), SA48 (2026-07-07), SA49 (2026-07-07), SA50 (2026-07-07), SA51 (2026-07-07), SA52 (2026-07-07), SA53 (2026-07-08), SA54 (2026-07-08), SA55 (2026-07-07), SA56 (2026-07-08). All closed per template rule — detail lives in CHANGELOG.md.
>
> **Origin note:** SA34–SA47 trace to the 2026-07-06 triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5), each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred and remain tracked in arch-audit.md itself).
>
> **Origin note (2026-07-07, fix-plan pass):** SA48–SA56 trace to the 2026-07-07 delta-pass findings in [tech-audit.md](../others/tech-audit.md) (TA42–TA46) and [arch-audit.md](../others/arch-audit.md) (Finding 1's red flags and CR-SA44-REV-001 blocker, Finding 4's coverage-boundary sub-item, Finding 5's two remaining Option 1 pieces plus the billing migration promoted from "long tail" to scheduled work per user decision — no idiom is grandfathered as permanent legacy), each sized Tier 1–2. Every item fit Tier 1–2 without splitting; the two items large enough to flag (SA50, the `OrgApiBaseView` fold; SA56, the billing DRF migration) are Tier 2, not Tier 3.

> **Track status (2026-07-08, SA54 complete):** Track 1 — **0 open items, all complete** (SA48, SA49, SA50). Track 2 — **0 open items, all complete** (SA51/SA52/SA53/SA54 complete). Track 3 — **0 open items, all complete** (SA56 complete — SA44 complete).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
(none — track complete)                 SA54 (complete — all tracks done)         (none — track complete)
```

All three tracks run fully in parallel — no hard cross-track implementation dependencies exist; each track's implementation files are independent. (The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` are the one exception — every track touches them during closeout, but that overlap is managed by the merge procedure above rather than being an implementation dependency.) The "soft-seq" notes above are intra-track only: same-file edits ordered to avoid needless rebasing, not hard technical dependencies.

### Track 1 — Tenant-context surface

All items in Track 1 are complete (SA47, SA48, SA49, SA50) — detail in [CHANGELOG.md](../../CHANGELOG.md). SA50 folded the `JsonApiMixin`/`JsonOrganizationAccessMixin` stack into one `OrgApiBaseView` as part of the `json-api-boundary-idiom-fragmentation` finding (see [arch-audit.md Finding 5](../others/arch-audit.md)).

### Track 2 — Module contracts & settings

SA21.2, SA37, SA38, SA40, SA43, SA51, SA52, SA53, plus its earlier share of the SA19–SA33 batch, are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). The `backups-dispatch-fail-open-robustness` finding (SA52/SA53, `why →` [tech-audit.md TA46](../others/tech-audit.md)) is fully closed — both items landed and TA46 is resolved. SA54 was completed this pass — detail below.

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), compounding evidence — doc drift + duplicated literal)

- [x] **SA54 — Deduplicate the stale-restore threshold constant.** `Tier 1 · Track 2 · deps: none (soft-sequence after SA53 — same file; also touches dr_engine/orchestration.py)`
  `dr_engine/orchestration.py:2804` hardcodes `timedelta(minutes=30)` in the CR-SA38-001 parity block while `backups/services.py:524` defines the canonical `STALE_RESTORE_THRESHOLD_MINUTES = 30` — the two can drift silently since core cannot import module services.
  **Decided (2026-07-08), ready for implementation:** pass the threshold as a parameter into `restore_admin_uploaded_backup()` rather than moving the constant into core. Its only caller is `admin.py` in the backups module (verified — it is not registered in `ADAPTER_FUNCTIONS`, so no CLI or other core-internal path needs its own copy of the value), so `admin.py` can pass `services.STALE_RESTORE_THRESHOLD_MINUTES` in explicitly. The module keeps sole ownership of the constant and core receives it via injection instead of owning backups-domain policy — this matches arch-audit.md Finding 1's own stated target shape for this exact value ("gives the stale-guard one home (module-side, with core receiving it via the port)") and makes zero changes to `runtime/dr.py`'s facade/export surface. (Rejected: moving the constant into `dr_engine` and having `services.py` import/re-export it — this follows existing import precedent in the file, but pulls a backups-domain policy value into core, the opposite of Finding 1's target direction, and touches the facade file the audit already flags as fragile.)
  *Files:* `quickscale_core/src/quickscale_core/dr_engine/orchestration.py:2777-2804` (`restore_admin_uploaded_backup` signature); `quickscale_modules/backups/src/quickscale_modules_backups/admin.py:436` (call site); `quickscale_modules/backups/src/quickscale_modules_backups/services.py:524` (constant — location unchanged).
  *Acceptance:* the threshold exists in exactly one place (`services.py`); `orchestration.py` no longer hardcodes `timedelta(minutes=30)`; a test asserts both paths agree after changing the value in its single location.
  *(why →* [tech-audit.md TA45](../others/tech-audit.md)*)*

### Track 3 — Core/CLI plumbing

SA44 (Finding 1 stage 1, `dr-engine-module-circular-lattice`) is complete — detail in [CHANGELOG.md](../../CHANGELOG.md). SA56 (Finding 5, `json-api-boundary-idiom-fragmentation`) is also complete — Finding 5 is fully closed (see [arch-audit.md](../others/arch-audit.md)). Track 3 has 0 open items.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
