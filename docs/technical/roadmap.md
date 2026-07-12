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
> **Track readiness (2026-07-13, corrected):** Track 1 and Track 2 are both blocked, on the same underlying dependency. Track 1's code-level work (SA77) is complete; only its final restricted-role verification remains, and that verification cannot run until SA79 (Track 2) closes. Track 2 (SA79) is itself blocked on CR-PLAN-SA79-004 — no decision needed, just execution: an actual `make test-integration` rerun under the full retained-role environment has not yet been performed. CR-PLAN-SA79-005 (status-ledger harmonization) is resolved as of this pass — roadmap.md, CHANGELOG.md, tech-audit.md, and arch-audit.md now all agree on SA77/SA79's open state.
> - **Track 1** — blocked. SA77 code fix implemented 2026-07-12 (full root-cause/fix detail in [CHANGELOG.md](../../CHANGELOG.md)'s SA77 entry). Nothing further to do on Track 1 until SA79 unblocks the restricted-role rerun.
> - **Track 2** — blocked. SA79 reopened — CR-PLAN-SA79-004 (retained-role rerun) is the sole remaining blocker; see below for the decision this requires.
> - **Track 3** — no open items; fully available for new work.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — fix orgs restricted-role        SA79 — reopened/blocked                    (no open items)
  test failures                          (CR-PLAN-SA79-004: retained-role
  ◐ code fix landed 2026-07-12;          rerun still owed — sole remaining
    verification blocked on Track 2       blocker; CR-PLAN-SA79-005 resolved)
```

SA77 (Track 1) code fix landed 2026-07-12; full detail in CHANGELOG.md. Only the final restricted-role verification step stays blocked behind SA79's closeout, because the current rerun aborts in forms 0007 before reaching the orgs seam. SA79 (Track 2) is reopened with one remaining blocker, CR-PLAN-SA79-004 (CR-PLAN-SA79-005 resolved this pass). Track 3 has no open work and is available for new items.

### Track 1 — Tenant-context surface

SA59 (umbrella, SA59.1–SA59.4) closed 2026-07-12 — see CHANGELOG.md. SA77 code fix implemented 2026-07-12; final DB verification blocked by SA79 (see below).

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, orgs restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA77 — Root-cause and fix orgs' restricted-role test failures.** `Tier 1 · Track 1 · deps: code fix landed 2026-07-12; final verification depends on SA79 (blocked)`
  Code fix landed 2026-07-12 — full root-cause and fix detail (psycopg2→`connection.cursor()` conversion in two test helpers; 6 dynamic-DDL tests marked `@pytest.mark.bypass_rls`) is in [CHANGELOG.md](../../CHANGELOG.md)'s SA77 entry, not repeated here.

  *Acceptance:* the 3 helper-path restricted-role tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the 6 dynamic-DDL tests skip in restricted mode and pass only when `QUICKSCALE_ALLOW_BYPASSRLS` is explicitly enabled. The corresponding `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  **Blocked:** the restricted-role rerun currently aborts in forms 0007 FK validation before reaching the orgs seam (Track 2 SA79, CR-PLAN-SA79-004). Full acceptance cannot be confirmed until SA79 unblocks and a full `make MODULE=orgs test-integration` passes.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

SA79 is reopened/blocked — the closeout verification revealed that the current handoff is not yet truthful enough to call complete.

#### Finding — SA79 closeout verification and reconciliation (`why →` closeout-review cap; CR-PLAN-SA79-004, CR-PLAN-SA79-005)

- [ ] **SA79 — Closeout verification/reconciliation.** `Tier 1 · Track 2 · deps: none`
  Direct forms 0007 proof must be rerun under the exact retained-role environment (full `QS_*_DB_USER=quickscale_test_role` set, BYPASSRLS hatch closed). Notifications suite must pass unquarantined (no forms 0007 FK errors) before SA79 can honestly close.

  **Pending blockers/decisions:**
  - **CR-PLAN-SA79-004 (high/blocking):** Exact retained-role execution shape must be explicit for SA79 proof and `make test-integration` (`QS_FORMS_DB_USER=quickscale_test_role`, full `QS_*_DB_USER=quickscale_test_role` set for the integration gate, BYPASSRLS hatch closed) — must be exercised in an actual rerun, not just documented. **Sole remaining blocker** — see the maintainer decision point below.
  - **CR-PLAN-SA79-005 (resolved 2026-07-13):** Status ledger is now fully harmonized — roadmap.md, CHANGELOG.md, tech-audit.md, and arch-audit.md all agree that SA77/SA79 remain open with the same blockers.

  **Maintainer decision needed on CR-PLAN-SA79-004:** a live retained-role rerun (`make test-integration` with the full `QS_*_DB_USER=quickscale_test_role` set and the BYPASSRLS hatch closed) has not yet been performed. Options:
  - **(a) Run it now.** A local PostgreSQL 18 container is already available in this environment (Docker). Pro: closes SA79 and, transitively, unblocks SA77's final verification and Track 1 in the same session. Con: this is real verification work — provisioning the retained roles, running the full integration gate, and triaging any genuinely new failures it surfaces — not a documentation edit, and could take a while if new failures appear.
  - **(b) Defer to a dedicated verification session.** Pro: keeps this pass scoped to the doc cleanup that was asked for. Con: Track 1 and Track 2 both stay blocked, and Track 3 remains the only track available for new work in the meantime.
  - Given this repo's own fail-hard/no-premature-closeout convention (the 2026-07-12 "SA79 blocked checkpoint" entry in CHANGELOG.md exists specifically because a prior pass claimed closure without running this exact rerun), option (a) — actually running it — is the organically-consistent way to close SA79 rather than re-documenting the blocker again next pass.

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
