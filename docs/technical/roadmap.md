# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work, plus recently-completed handoff)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work and, when open items are resolved, a brief recently-completed handoff section. Detailed completed implementation history remains in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here, plus optionally a recently-completed handoff section.
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

### Structural Autopsy Remediation (opened 2026-06-30)

Fix plan derived from the [2026-06-30 autopsy](../../findings.md#autopsy--2026-06-30). Each task below is sized Adaptive **Tier 1 or Tier 2** (one concern, statable in one sentence; isolation work is sensitive-domain → `RISK LEVEL: medium` → floors at Tier 2). Every task carries a `why →` link to the finding it closes.

**Naming:** `SAn.m` = Structural-Autopsy finding *n*, task *m*.

**Status (2026-07-02):** Findings 2, 3, 4, and 5 are fully closed — all their tasks (SA2.1, SA2.2, SA3.1, SA3.2, SA4.1, SA4.2, SA5.1, SA5.2) shipped and merged to `v87`; detail archived in [CHANGELOG.md](../../CHANGELOG.md). Finding 1 is nearly closed: SA1.1–SA1.4 shipped, leaving **SA1.5** as the only open task project-wide.

**Cross-track safety:** file ownership is partitioned so concurrent tracks never edit the same file. Track 1 owns `orgs/tenancy.py` + generator templates; Track 2 owns `orgs/apps.py`, `orgs/current_org.py`, and `quickscale_modules/crm/`; Track 3 owns `quickscale_modules/blog/`, `quickscale_modules/analytics/`, and CLI wiring.

> **Shared closeout files:** `CHANGELOG.md` and this file (`docs/technical/roadmap.md`) are **not** owned by any single track. Every track updates them when closing out a completed task — they are the only files where concurrent edits are expected. To avoid merge conflicts, follow the shared-file merge procedure in the next section: always merge `v87` into your track branch first, resolve conflicts in these two files on the track branch, then merge back.

#### Finding 1 — Single enforced tenant-model contract (`why →` [Finding 1](../../findings.md#finding-1--tenant-isolation-is-a-hand-assembled-per-model-ritual-and-its-enforcement-gate-cannot-see-the-user-code-that-generated-projects-exist-to-host))

- [ ] **SA1.5 — Ship the isolation gate into generated-project CI.** `Tier 2 · Track 1 · deps: SA1.3 (closed)`
  Wire `check_tenant_isolation` into the generated project's CI/test scaffold so it runs in the **user's** repo against the user's apps.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/` (CI workflow + `Makefile`/test target template).
  *Acceptance:* a freshly generated project runs the isolation check in CI; conformance fixture proves a deliberately-unprotected model fails the generated CI.

#### Findings 2, 3, 4, 5 — all closed

Full remediation history for Findings 2 (fail-closed master isolation switch), 3 (contract single source of truth), 4 (O(1) tenant-context priming), and 5 (declarative module-config cutover) is in [CHANGELOG.md](../../CHANGELOG.md) (SA2.1, SA2.2, SA3.1, SA3.2, SA4.1, SA4.2, SA5.1, SA5.2 entries). Findings 4 and 5 closed 2026-07-02 by maintainer decision: each shipped the lowest-effort mitigation the autopsy prescribed (a per-transaction priming memo; an analytics pilot plus a freeze guardrail) and left the larger structural fix as explicitly deferred/unscheduled backlog rather than an open roadmap task — see [findings.md](../../findings.md) for the closure rationale on each.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
