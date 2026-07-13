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

> Completed and archived work lives in [CHANGELOG.md](../../CHANGELOG.md). This section retains checked closeout entries for completed items as evidence of acceptance (their full implementation detail lives in CHANGELOG.md). Active and blocked work stays open below.
>
> **Track readiness (2026-07-13, updated):** SA82 (Track 3) completed — the SA76 `orgs`/`notifications` quarantine entries are removed; the full `make test-integration` gate ran with both suites unquarantined (exit 1, as expected: orgs 847 passed/11 BYPASSRLS-skips/0 failed, notifications 39 passed/0 failed, overall mean coverage 92.95% passed). SA77 and SA79 closed by this result — their acceptance conditions are met. The repository integration gate remains red due to separate independent findings (SA80.3, SA83–SA86) that do not affect SA77/SA79 closure.
> - **Track 1** — unblocked from SA82 (SA77 closed); open findings SA83 (blog, 86 RLS failures), SA84 (CRM, 67 RLS failures/20 skipped), SA85 (forms, 33 RLS failures/8 skipped/10 errors), and SA86 (listings, 6 RLS failures) recorded below — each is a separate restricted-role residual, not a blocker for SA77 closure.
> - **Track 2** — unblocked from SA82 (SA79 closed); no further open items. Its acceptance conditions (forms 0007 backfill + unquarantined notifications under the full gate) are satisfied.
> - **Track 3** — SA80 (venv + retained-role env wiring) done; SA82 (gate rerun) completed; open work SA80.3 (pg_dump, non-blocking) and SA81 remain, both with no dependencies.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — done (SA82, 2026-07-13)         SA79 — done (SA82, 2026-07-13)            SA80 — done (2026-07-13)
  orgs 847p/11 BYPASSRLS-skips/0f        notifications 39p/0f;                     SA82 — done (2026-07-13)
  code fix verified live under gate      forms 0007 acceptance verified            SA80.3 (pg_dump) open,
SA83 — blog (86 RLS failures) open,                                                non-blocking
  no deps, unknown root cause                                                      SA81 — open, no deps
SA84 — CRM (67 RLS failures/20
  skipped) open, no deps, unknown
  root cause
SA85 — forms residual (33 RLS
  failures/8 skipped/10 errors)
  open, no deps, unknown root cause
SA86 — listings (6 RLS failures)
  open, no deps, unknown root cause
```


SA82 (Track 3) completed 2026-07-13 — the `orgs`/`notifications` quarantine entries are removed; the full gate rerun confirmed orgs (847 passed/11 BYPASSRLS-skips/0 failed) and notifications (39 passed/0 failed) clean. SA77 and SA79 are closed by this result. Track 1 is unblocked from SA82 with SA83–SA86 open; Track 2 is unblocked from SA82 with no further open items. The integration gate remains red due to separate independent findings (SA80.3, SA83–SA86) recorded below.

### Track 1 — Tenant-context surface

SA59 (umbrella, SA59.1–SA59.4) closed 2026-07-12 — see CHANGELOG.md. SA77 closed 2026-07-13 by SA82 — see below and CHANGELOG.md. Four independent restricted-role residuals in blog, CRM, forms, and listings are recorded as SA83–SA86 below.

- [x] **SA77 — Root-cause and fix orgs' restricted-role test failures.** `Tier 1 · Track 1 · deps: none → closed 2026-07-13`
  Code fix landed 2026-07-12 — full root-cause and fix detail (psycopg2→`connection.cursor()` conversion in two test helpers; 6 dynamic-DDL tests marked `@pytest.mark.bypass_rls`) is in [CHANGELOG.md](../../CHANGELOG.md)'s SA77 entry, not repeated here.

  *Acceptance:* the 3 helper-path restricted-role tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the 6 dynamic-DDL tests skip in restricted mode. The `scripts/test_integration.sh` quarantine entry was removed in SA82. The full `make test-integration` gate run (2026-07-13) confirmed orgs 847 passed/11 BYPASSRLS-skips/0 failed, 93.04% coverage. SA77 closed.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — Blog restricted-role RLS failures (`why →` CR-SA82-NT-002; discovered during SA82 full-gate rerun)

- [ ] **SA83 — Investigate and fix blog's 86 restricted-role RLS failures.** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate run with quarantine entries removed, blog's restricted-role suite showed 121 passed, 86 RLS failures. Root cause is unknown/unconfirmed — the failures are RLS policy violations under `quickscale_test_role` (NOBYPASSRLS), but the specific mechanism (missing org context, missing `operator_access`, or policy gap) has not been isolated.

  *Acceptance:* blog's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-002*)*

#### Finding — CRM restricted-role RLS failures (`why →` CR-SA82-NT-003; discovered during SA82 full-gate rerun)

- [ ] **SA84 — Investigate and fix CRM's 67 restricted-role RLS failures (plus 20 skipped).** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate run, CRM's restricted-role suite showed 195 passed, 67 RLS failures, 20 skipped. Root cause is unknown/unconfirmed — RLS policy violations under `quickscale_test_role`.

  *Acceptance:* CRM's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-003*)*

#### Finding — Forms residual restricted-role test failures (`why →` CR-SA82-NT-004; discovered during SA82 full-gate rerun)

- [ ] **SA85 — Investigate and fix forms' residual restricted-role test failures.** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate run, forms' restricted-role suite showed 140 passed, 33 RLS failures, 8 skipped, 10 errors. Root cause is unknown/unconfirmed — RLS policy violations and test-structural errors under `quickscale_test_role`.

  *Acceptance:* forms' restricted-role suite passes clean (0 failures, 0 errors) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-004*)*

#### Finding — Listings restricted-role RLS failures (`why →` CR-SA82-NT-005; discovered during SA82 full-gate rerun)

- [ ] **SA86 — Investigate and fix listings' 6 restricted-role RLS failures.** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate run, listings' restricted-role suite showed 128 passed, 6 RLS failures. Root cause is unknown/unconfirmed — RLS policy violations under `quickscale_test_role`.

  *Acceptance:* listings' restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-005*)*

### Track 2 — Module contracts & settings

SA79 closed 2026-07-13 by SA82 — see below and CHANGELOG.md.

- [x] **SA79 — Closeout verification/reconciliation.** `Tier 1 · Track 2 · deps: none → closed 2026-07-13`

  The full `make test-integration` gate run (SA82, 2026-07-13) confirmed notifications 39 passed/0 failed, 91.76% coverage — unquarantined, clean. Forms 0007 backfill acceptance verified under the full retained-role environment with the BYPASSRLS hatch closed and quarantine entries removed.

  SA80 (Track 3) resolved the local env gaps; SA82 removed the quarantine entries and confirmed both acceptance conditions under `make test-integration` itself rather than a narrower direct-pytest rerun. Audit/status docs refreshed in this pass.

  *Acceptance:* forms 0007 backfill passes under full retained-role env; notifications suite runs clean (unquarantined) under a full `make test-integration` gate run; audit/status docs reflect current state. **Achieved.** SA79 closed.

### Track 3 — Core/CLI plumbing

SA80 closed 2026-07-13 (venv re-provision + retained-role env wiring) — see CHANGELOG.md. SA82 completed 2026-07-13. SA80.3 and SA81 are open with no dependencies.

- [x] **SA82 — Remove the SA76 `orgs`/`notifications` quarantine entries and rerun the full `make test-integration` gate to prove SA77/SA79 clean.** `Tier 1 · Track 3 · deps: none → completed 2026-07-13`

  Removed `orgs` and `notifications` from `QUARANTINE_TICKETS` in `scripts/test_integration.sh` (passed `bash -n` syntax check). Ran `make test-integration` end-to-end — exit 1 (expected: separate findings remain). Target evidence: orgs 847 passed/11 BYPASSRLS-skips/0 failed, 93.04% coverage; notifications 39 passed/0 failed, 91.76% coverage. Overall mean coverage 92.95% passed.

  SA77 closed and SA79 closed by this result — their acceptance conditions are met under the full unquarantined gate. The four independent restricted-role findings surfaced by removing the quarantine are recorded as SA83 (blog, 86 RLS failures), SA84 (CRM, 67 RLS failures/20 skipped), SA85 (forms, 33 RLS failures/8 skipped/10 errors), and SA86 (listings, 6 RLS failures) — each open with no deps and unknown root cause in Track 1 above. Backups 275 passed/24 missing-`pg_dump` failures/2 skipped remain tracked by SA80.3 (non-blocking, existing).

  *Acceptance:* orgs and notifications both pass clean under the full unquarantined gate. **Achieved.** SA77 and SA79 closed.
  *(why →* 2026-07-13 roadmap closeout checkpoint, [CHANGELOG.md](../../CHANGELOG.md)*)*

#### Finding — PostgreSQL client tools missing locally (`why →` CR-SA82-NT-001; discovered during SA82 full-gate rerun)

- [ ] **SA80.3 — Install PostgreSQL 18 client tools locally.** `Tier 1 · Track 3 · deps: none`
  `backups` fails 24/301 tests locally on a missing `pg_dump` binary (275 passed, 24 failed, 2 skipped; all 24 failures due missing `pg_dump`). Install `postgresql-client-18` (PGDG apt repo), matching the guidance already printed in the `BackupError` message this raises. Not a blocker for SA77/SA79 or the shared gate rerun — only needed for a fully green local `make test-integration` run.

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
