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
> **Track readiness (2026-07-13, updated after the CR-PLAN-SA79-004 rerun attempt):** Track 1 and Track 2 are both blocked, and the 2026-07-13 rerun changed *why*. The maintainer ran `make test-integration` against the local retained-role environment; it did not reach a state where SA77's or SA79's specific hypotheses could be confirmed or denied — it was blocked earlier by (1) a stale, non-editable local `quickscale-core` venv install missing the `quickscale_core.runtime` package, which broke orgs' test collection with an unrelated `ModuleNotFoundError`, and (2) incomplete local retained-role env wiring for 7 of 13 modules (billing, blog, crm, forms, listings, social, notifications), which fail immediately on `ImproperlyConfigured: role has BYPASSRLS/SUPERUSER` before reaching any SA77/SA79-relevant code path. Both failures were silently absorbed by the SA76 quarantine (which matches on module name only, not failure signature) under the SA77/SA79 tickets respectively, even though neither matches those tickets' described root causes. Full detail: [CHANGELOG.md](../../CHANGELOG.md)'s "CR-PLAN-SA79-004 rerun attempted, blocked checkpoint (2026-07-13)" entry. CR-PLAN-SA79-005 (status-ledger harmonization) is resolved as of the prior pass — roadmap.md, CHANGELOG.md, tech-audit.md, and arch-audit.md agree on SA77/SA79's open state.
> - **Track 1** — blocked. SA77 code fix implemented 2026-07-12. Whether the fix is actually correct under a real restricted-role rerun is still unconfirmed — the 2026-07-13 rerun never reached orgs' RLS-relevant tests due to the venv staleness issue above. Nothing further to do on Track 1 until the environment is re-provisioned and SA79 unblocks.
> - **Track 2** — blocked. SA79's own quarantined suite (notifications) also never reached its described forms-0007 code path in the 2026-07-13 rerun — it crashed earlier on the same role-wiring gap affecting 6 other modules. CR-PLAN-SA79-004 cannot be meaningfully re-attempted until that gap is closed; see below.
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
  **2026-07-13 rerun note:** the attempted verification didn't reach this code path either — orgs' local suite instead hit an unrelated `ModuleNotFoundError` from a stale local `quickscale-core` venv install (environment-only, not a code defect), which the SA76 quarantine absorbed under this ticket anyway. Full detail in [CHANGELOG.md](../../CHANGELOG.md); local env needs re-provisioning before this acceptance criterion can be tested for real.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

SA79 is reopened/blocked — the closeout verification revealed that the current handoff is not yet truthful enough to call complete.

#### Finding — SA79 closeout verification and reconciliation (`why →` closeout-review cap; CR-PLAN-SA79-004, CR-PLAN-SA79-005)

- [ ] **SA79 — Closeout verification/reconciliation.** `Tier 1 · Track 2 · deps: none`
  Direct forms 0007 proof must be rerun under the exact retained-role environment (full `QS_*_DB_USER=quickscale_test_role` set, BYPASSRLS hatch closed). Notifications suite must pass unquarantined (no forms 0007 FK errors) before SA79 can honestly close.

  **Pending blockers/decisions:**
  - **CR-PLAN-SA79-004 (high/blocking, rerun attempted 2026-07-13 — see below):** Exact retained-role execution shape must be explicit for SA79 proof and `make test-integration` (`QS_FORMS_DB_USER=quickscale_test_role`, full `QS_*_DB_USER=quickscale_test_role` set for the integration gate, BYPASSRLS hatch closed) — must be exercised in an actual rerun, not just documented. The 2026-07-13 rerun ran but did not reach the forms-0007 code path for notifications; still open. **Sole remaining blocker.**
  - **CR-PLAN-SA79-005 (resolved 2026-07-13):** Status ledger is now fully harmonized — roadmap.md, CHANGELOG.md, tech-audit.md, and arch-audit.md all agree that SA77/SA79 remain open with the same blockers.

  **2026-07-13 rerun result (full detail in [CHANGELOG.md](../../CHANGELOG.md)):** the maintainer ran `make test-integration` against the local retained-role environment. It did not confirm or deny SA79's forms-0007 hypothesis — the notifications suite (quarantined under SA79) crashed earlier, at Django app-ready, with the same `ImproperlyConfigured: role has BYPASSRLS/SUPERUSER` error that also hit billing/blog/crm/forms/listings/social (6 of 13 modules besides notifications). `storage`/`analytics` passed clean under the retained role, so the mechanism itself works — the gap is in local role/env provisioning coverage for these 7 modules specifically. Separately, `backups` failed 23/299 tests on a missing `pg_dump` binary (environment tooling gap, unrelated to SA79), and orgs' SA77 quarantine absorbed an unrelated `ModuleNotFoundError` caused by a stale non-editable `quickscale-core` venv install (also environment-only, not a code defect). No code was changed in response to these findings per instruction — this entry records them for the next verification attempt.

  **Next step before CR-PLAN-SA79-004 can be re-attempted meaningfully:** re-provision the local dev environment — editable-reinstall `quickscale_core` (to pick up the `runtime` package) and confirm/fix `QS_<MODULE>_DB_USER=quickscale_test_role` wiring for billing, blog, crm, forms, listings, social, and notifications locally (compare against what `ci.yml`/`publish.yml` export, since those are believed to wire it correctly — see arch-audit.md census row 14). Only once the rerun actually reaches forms-0007 for notifications does CR-PLAN-SA79-004 produce real signal.

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
