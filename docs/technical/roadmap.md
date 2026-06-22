# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work Only)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks only pending roadmap work. Completed history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep only open todo items here.
- Move completed implementation history to CHANGELOG.md in concise form.
- Each phase links back (`why →`) to the finding that justifies it.

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Track assignment

| Track | Worktree | Branch | Owns |
|-------|---------|--------|------|
| 1 | `quickscale-wt-track1` | `wt-track1` | M7 — F11 module isolation (complete) |

### Cross-track dependency

All track work is complete. No remaining cross-track dependencies.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

> **Why every phase:** other tracks land changes on `v87` between your phases. Starting from a stale base makes conflicts larger and harder to resolve later.

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

### Merge checkpoints

| # | Track | Phases | Status | Condition |
|---|-------|--------|--------|-----------|
| M1 | 1 | F11.2–F11.5 | 🟢 | **Merged to v87.** F11.2 ✅ F11.3 ✅ F11.4 ✅ F11.5 ✅. |
| M3 | 1 | F11.6–F11.10 | 🟢 | **Merged to v87.** F11.6 ✅ F11.7 ✅ F11.8 ✅ F11.9 ✅ F11.10a ✅ F11.10b ✅ F11.10c ✅ F11.10d ✅ F11.10e ✅. Full closeout: same-org FK audit/fix (225/225), pre-sync and post-sync closeout slices each 254/254, all runtime tests passing. **Next:** M7 / F11.11. |
| M5 | 3 | F2.5–F2.9b | 🟢 | **Merged to v87.** F2.5 ✅ F2.6 ✅ F2.7 ✅ F2.8 ✅ F2.9a ✅ F2.9b ✅. |
| M7 | 1 | F11.11–F11.13b | 🟢 | **Merged to v87.** F11.11 ✅ F11.12a ✅ F11.12b ✅ F11.13a ✅ SOCIAL-CR-002 ✅ F11.13b ✅. Structural isolation rollout complete — non-view path audit, blog admin org safeguards, historical forms seed fix, migration/adoption docs, and isolation/coverage closeout all landed. |
| M8 | 3 | F12.1–F12.3b | 🟢 | **Merged to v87.** F12.1 ✅ F12.2 ✅ F12.3a ✅ F12.3b ✅. Railway rollback/resume closeout complete. |
| M9 | 1 | F13.1–F13.3 | 🟢 | **Merged to v87.** F13.1 ✅ F13.2 ✅ F13.3 ✅. Org-authoritative billing contract; `quickscale_billing_unique_current_subscription_per_organization` constraint; dual-FK rows backfilled via migration; mgmt command provided. |
| M10 | 2 | F5.2a–F5.4 | 🟢 | **Merged to v87.** M6 ✅ + M8 ✅ merged; F5.1 ✅ boundary contract in decisions.md. F5.2a ✅ snapshot/archive primitives extracted to `quickscale_core.dr_engine.primitives`. F5.2b ✅ restore/orchestration/verification extracted to `dr_engine.recovery` and `dr_engine.verification`. F5.3 ✅ protocol replacement + module slimming. F5.4 ✅ migration docs added to `docs/technical/dr_engine_migration.md`. All Track 2 phases complete. |
| M11 | 3 | F7.1–F7.3 | 🟢 | **Merged to v87.** F7.1 ✅ F7.2 ✅ F7.3 ✅. All runtime-pin phases complete. |

---
## Backlog

### Sequencing

Execute top-down. Earlier items are prerequisites for or de-risk later items.

| Priority | Finding | Milestone(s) | Status |
|----------|---------|-------------|--------|
| 2 | F2 — Project state + module provenance | M5 | 🟢 M5 merged to v87 |
| 3 \| parallel | F13 — Single billing customer SSOT | M9 | 🟢 M9 merged to v87 |
| 5 | F5 — DR engine split | M10 | 🟢 M10 merged to v87. |
| 6 | F7 — Generator vs generated-project runtime pins | M11 | 🟢 M11 merged to v87. All phases complete. |

**F11-deferred — Stage `terminal_semantic` per-org uniqueness** _(Adaptive tier: 2)_ _(unlocked by F11.5)_

- [ ] Split `Stage.terminal_semantic` uniqueness to per-bucket partial `UniqueConstraint`s; add migration + serializer + API regression coverage.

---

## Deferred / Monitor

- [ ] **Documentation consolidation** _(Adaptive tier: 2)_ — defer until doc drift causes real onboarding failures; manifest work (F1) simplifies auto-generated module facts.
- [ ] **Broader compatibility-window widening** _(Adaptive tier: 2)_ (F7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] **Emitted-project operability & API-contract substrate** _(deferred — split into Tier 1/2 sub-items below)_ — generated modules ship with no structured logging/correlation IDs, no versioned public API, and no webhook payload boundary validation. Promote to active backlog when a second external provider lands or the first public-API consumer appears. Stripe SDK `api_version` pinning is already listed below as a one-liner.
  - [ ] _(Tier 1)_ Add structured logging and correlation-ID baseline to generated modules.
  - [ ] _(Tier 2)_ Add versioned public-API surface (`/api/vN`) to generated module `urls.py`.
  - [ ] _(Tier 2)_ Add webhook payload boundary validation baseline.

### Explicitly out of scope

Single-PR/ticket items that do not change the design:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` as a one-liner.
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines.

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
