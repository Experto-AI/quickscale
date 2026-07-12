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

> Completed and archived work lives in [CHANGELOG.md](../../CHANGELOG.md). Keep only active or blocked work here. Completed items (SA60, SA70, SA74, SA75, SA76, SA78, SA59 umbrella including SA59.1–SA59.4) were pruned from this section — their full implementation detail lives in CHANGELOG.md. **SA79 is reopened/blocked (see Track 2 below).**
>
> **Track readiness (2026-07-12, corrected):** Track 2 is blocked (SA79 closeout verification findings pending) and Track 1 is blocked behind it.
> - **Track 1** — SA77 open but blocked — the Track 2 SA79 handoff is not yet truthful enough to call complete (restricted-role rerun aborts in forms 0007 FK validation before reaching the orgs seam).
> - **Track 2** — SA79 reopened/blocked — closeout verification findings CR-PLAN-SA79-004 and CR-PLAN-SA79-005 must be resolved before Track 2 can honestly close.
> - **Track 3** — no open items; fully available for new work.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — fix orgs restricted-role        SA79 — reopened/blocked                    (no open items)
  CREATE ROLE failures                   (closeout verification findings
  ⬤ blocked behind Track 2 handoff       CR-PLAN-SA79-004, CR-PLAN-SA79-005)
```

SA77 (Track 1) is blocked behind SA79 closeout verification/reconciliation — the current restricted-role rerun aborts in forms 0007 FK validation before reaching the orgs seam. SA79 (Track 2) is reopened with pending blockers. Track 3 has no open work and is available for new items.

### Track 1 — Tenant-context surface

SA59 (umbrella, SA59.1–SA59.4) closed 2026-07-12 — see CHANGELOG.md. SA77 is open but blocked by SA79 handoff (see below).

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, orgs restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA77 — Root-cause and fix orgs' restricted-role `CREATE ROLE`-dependent test failures.** `Tier 1 · Track 1 · deps: SA79 (blocked)`
  3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py` persist under the NOBYPASSRLS integration role. These depend on restricted-role `CREATE ROLE` behavior (SA59.3-style territory) and were not resolved by SA59.1's Phase 3 test-only adaptations or by SA59.3's create-then-use → assert-then-use conversion. Root cause not yet established — investigate whether these tests still attempt a `CREATE ROLE` call SA59.3 didn't cover, or exercise a role capability the shared `quickscale_test_role`/`quickscale_rls_test_role` contract doesn't grant.
  *Files:* `quickscale_modules/orgs/tests/test_tenant_table_conformance.py`, `quickscale_modules/orgs/tests/test_operator_access.py`, `quickscale_modules/orgs/tests/test_models.py` — plus `scripts/provision_test_roles.sh` if the fix is a role-contract gap rather than a test-helper gap.
  *Acceptance:* all 9 failing tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the corresponding `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  **Blocker:** The restricted-role rerun aborts in forms 0007 FK validation before reaching the orgs seam — SA79 handoff is not yet truthful enough to call complete. SA77 verification is blocked until Track 2 SA79 closeout verification is resolved. (See pending blockers CR-PLAN-SA79-004, CR-PLAN-SA79-005 below.)
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

SA79 is reopened/blocked — the closeout verification revealed that the current handoff is not yet truthful enough to call complete.

#### Finding — SA79 closeout verification and reconciliation (`why →` closeout-review cap; CR-PLAN-SA79-004, CR-PLAN-SA79-005)

- [ ] **SA79 — Closeout verification/reconciliation.** `Tier 1 · Track 2 · deps: none`
  Direct forms 0007 proof must be rerun under the exact retained-role environment (full `QS_*_DB_USER=quickscale_test_role` set, BYPASSRLS hatch closed). Notifications suite must pass unquarantined (no forms 0007 FK errors) before SA79 can honestly close. Same-fact status docs and audit docs must be refreshed together — current-state audit docs still assert SA79/SA77 remain open.

  **Pending blockers/decisions:**
  - **CR-PLAN-SA79-004 (high/blocking):** Exact retained-role execution shape must be explicit for SA79 proof and `make test-integration` (`QS_FORMS_DB_USER=quickscale_test_role`, full `QS_*_DB_USER=quickscale_test_role` set for the integration gate, BYPASSRLS hatch closed).
  - **CR-PLAN-SA79-005 (medium/blocking):** Same-fact status refresh must include current-state audit docs that still assert SA79/SA77 remain open.

  *Acceptance:* forms 0007 backfill passes under full retained-role env; notifications suite runs clean (unquarantined); audit/status docs reflect current state.

### Track 3 — Core/CLI plumbing

No open items. Fully available for new work.

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work (SA75, SA76) lives in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
