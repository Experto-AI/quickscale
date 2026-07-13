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

> Completed and archived work lives in [CHANGELOG.md](../../CHANGELOG.md). Keep only active or blocked work here. Completed items (SA60, SA70, SA74, SA75, SA76, SA78, SA80, SA59 umbrella including SA59.1–SA59.4) were pruned from this section — their full implementation detail lives in CHANGELOG.md. **SA79 is reopened/blocked (see Track 2 below).**
>
> **Track readiness (2026-07-13):** Track 1 and Track 2 remain blocked despite SA80 (Track 3) landing and verifying clean — SA80's rerun used direct pytest invocations against the retained-role env, not a full `make test-integration` gate run with the SA76 quarantine entries for `orgs`/`notifications` removed. That numeric result (orgs 847 passed/11 BYPASSRLS-skips; notifications 39 passed) is suggestive but not the same proof standard this project has required at prior SA79 checkpoints (see the corrected-fix episode, CR-SA79-001/002) — a partial/direct-invocation pass has previously masked unrelated failures under quarantine (see CHANGELOG's 2026-07-13 CR-PLAN-SA79-004 entry). **Next concrete step to unblock both tracks:** remove the `orgs` and `notifications` entries from `scripts/test_integration.sh`'s `QUARANTINE_TICKETS` and rerun the full `make test-integration` gate — a clean run there is the acceptance bar for both SA77 and SA79.
> - **Track 1** — blocked on SA79 (shared gate rerun above). SA77's code fix landed 2026-07-12; unconfirmed under the full gate.
> - **Track 2** — blocked on the same gate rerun. SA79's acceptance (forms 0007 backfill + unquarantined notifications) is not yet confirmed under `make test-integration` itself.
> - **Track 3** — clean. SA80 (venv + retained-role env wiring) is done; only SA80.3 (pg_dump, non-blocking) remains open, alongside new item SA81.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — fix orgs restricted-role        SA79 — reopened/blocked                    SA80 — done (2026-07-13)
  test failures                          (needs a clean full                       SA80.3 (pg_dump) open,
  ◐ code fix landed 2026-07-12;          make test-integration gate                non-blocking
    unconfirmed under the full             rerun, quarantine removed)              SA81 — open, no deps
    gate rerun
```

SA77 (Track 1) code fix landed 2026-07-12; full detail in CHANGELOG.md. SA80 (Track 3) is complete and verified (CHANGELOG.md). Track 1 and Track 2 both wait on the same next step: a full `make test-integration` gate rerun with the `orgs`/`notifications` quarantine entries removed.

### Track 1 — Tenant-context surface

SA59 (umbrella, SA59.1–SA59.4) closed 2026-07-12 — see CHANGELOG.md. SA77 code fix implemented 2026-07-12; final DB verification blocked by SA79 (see below).

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, orgs restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA77 — Root-cause and fix orgs' restricted-role test failures.** `Tier 1 · Track 1 · deps: code fix landed 2026-07-12; final verification depends on SA79`
  Code fix landed 2026-07-12 — full root-cause and fix detail (psycopg2→`connection.cursor()` conversion in two test helpers; 6 dynamic-DDL tests marked `@pytest.mark.bypass_rls`) is in [CHANGELOG.md](../../CHANGELOG.md)'s SA77 entry, not repeated here.

  *Acceptance:* the 3 helper-path restricted-role tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the 6 dynamic-DDL tests skip in restricted mode. The `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  **Blocked:** SA80's direct-pytest rerun (2026-07-13) showed orgs reaching this code path clean (847 passed, 11 BYPASSRLS-skips), but that is not yet a full `make test-integration` gate rerun with the quarantine entry removed — see the Track readiness note above for why that distinction matters here. Next step is shared with SA79 (Track 2): drop the quarantine entries and rerun the full gate.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

SA79 is reopened/blocked — the closeout verification revealed that the current handoff is not yet truthful enough to call complete.

#### Finding — SA79 closeout verification and reconciliation (`why →` closeout-review cap; CR-PLAN-SA79-004, CR-PLAN-SA79-005)

- [ ] **SA79 — Closeout verification/reconciliation.** `Tier 1 · Track 2 · deps: shared gate rerun with SA77`
  Direct forms 0007 proof must be rerun under the exact retained-role environment (full `QS_*_DB_USER=quickscale_test_role` set, BYPASSRLS hatch closed). Notifications suite must pass unquarantined before SA79 can honestly close.

  SA80 (Track 3, done 2026-07-13) resolved the local env gaps that previously blocked any rerun from reaching this code path, and its direct-pytest verification already shows notifications at 39 passed/0 failed. Per the Track readiness note above, that's not yet the same proof standard as a clean `make test-integration` gate run with the quarantine entries removed — **CR-PLAN-SA79-004 remains the sole blocker**, now reduced to: drop `orgs`/`notifications` from `scripts/test_integration.sh`'s `QUARANTINE_TICKETS` and rerun the full gate. Full history of the 2026-07-13 rerun attempt is in [CHANGELOG.md](../../CHANGELOG.md).

  *Acceptance:* forms 0007 backfill passes under full retained-role env; notifications suite runs clean (unquarantined) under a full `make test-integration` gate run; audit/status docs reflect current state.

### Track 3 — Core/CLI plumbing

SA80 closed 2026-07-13 (venv re-provision + retained-role env wiring) — see CHANGELOG.md. Track 3 is clean; SA80.3 and SA81 below are both open with no dependencies.

#### Finding — PostgreSQL client tools missing locally (`why →` [CHANGELOG.md](../../CHANGELOG.md)'s SA80 entry)

- [ ] **SA80.3 — Install PostgreSQL 18 client tools locally.** `Tier 1 · Track 3 · deps: none`
  `backups` fails 23/299 tests locally on a missing `pg_dump` binary. Install `postgresql-client-18` (PGDG apt repo), matching the guidance already printed in the `BackupError` message this raises. Not a blocker for SA77/SA79 or the shared gate rerun — only needed for a fully green local `make test-integration` run.

#### Finding — Dead per-module `poetry.lock`/sibling-version constraints (`why →` discovered 2026-07-13 during a routine dependency-update pass)

- [ ] **SA81 — Remove the 8 unused per-module `poetry.lock` files and the sibling-module version-range constraints that never resolve standalone.** `Tier 1 · Track 3 · deps: none`
  While updating dependencies to their latest stable versions (2026-07-13), found that `quickscale_core`, `quickscale_cli`, and 8 of the 12 `quickscale_modules/*` packages (`auth`, `billing`, `blog`, `crm`, `forms`, `listings`, `orgs`, `storage`) each carry their own `poetry.lock`, alongside the root monorepo `poetry.lock` that every `make`/CI target actually installs from (root `pyproject.toml` wires every module in as `path = "...", develop = true`). Confirmed with the maintainer: standalone installation of an individual module outside the `quickscale` bundle is **not a supported use case** — modules are only meant to run interconnected via the `quickscale` CLI's bundle generation. That means these per-module lockfiles serve no purpose today:
  - 6 of the 8 (`auth`, `billing`, `blog`, `crm`, `listings`, `orgs`) can't even be re-locked standalone — their `pyproject.toml` declares sibling deps like `quickscale-module-orgs = ">=0.86.0,<0.87.0"` as plain version ranges with no `path =`, so `poetry lock` run from inside the module directory fails immediately with "doesn't match any versions" (there's nowhere to fetch an unpublished sibling package from). Their existing committed lockfiles don't even list those sibling packages, confirming this has been broken for a while, silently.
  - The other 4 modules (`notifications`, `analytics`, `backups`, `social`) never had a standalone lockfile at all — already inconsistent with the other 8, further evidence this was never a maintained/tested path.
  - Nothing in `.github/workflows/*.yml` or the `Makefile` ever `cd`s into a module directory and runs `poetry install`/`poetry lock` there — CI and `make test`/`make test-integration` install everything from the root lockfile only.

  *Acceptance:* delete the 8 per-module `poetry.lock` files (`quickscale_core`, `quickscale_cli`, `quickscale_modules/{auth,billing,blog,crm,forms,listings,orgs,storage}`); remove the sibling-module version-range dependency declarations from the 6 modules' `pyproject.toml` `[tool.poetry.dependencies]` that never resolve standalone (the real inter-module relationship is already expressed via the root `pyproject.toml` path deps and `quickscale_core`'s manifest/module-catalog system, so nothing else needs to encode it); confirm `make test`/`make test-integration`/CI are unaffected (they don't touch these files); note in each affected module's `poetry.toml` comment (already states "use root monorepo venv instead") that standalone lock/install is explicitly unsupported, to prevent the drift from recurring.
  *(why →* discovered while updating `mypy`, `posthog`, `django-anymail`, `django-filter` to latest stable in the root lockfile; maintainer confirmed standalone module installation is out of scope for this project*)*

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work (SA75, SA76) lives in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
