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
> - **Track 1** — blocked. SA77 code fix implemented 2026-07-12. Whether the fix is actually correct under a real restricted-role rerun is still unconfirmed — the 2026-07-13 rerun never reached orgs' RLS-relevant tests due to the venv staleness issue above. Nothing further to do on Track 1 until SA80 (Track 3) lands and SA79 unblocks.
> - **Track 2** — blocked. SA79's own quarantined suite (notifications) also never reached its described forms-0007 code path in the 2026-07-13 rerun — it crashed earlier on the same role-wiring gap affecting 6 other modules. CR-PLAN-SA79-004 cannot be meaningfully re-attempted until SA80 (Track 3) lands.
> - **Track 3** — **SA80 implementation verified** (SA80.1 + SA80.2 + verified 2026-07-13). `scripts/test_integration.sh` now exports the same `QS_*_DB_USER=quickscale_test_role` vars that CI does, and the local `quickscale_core` venv has been re-provisioned to pick up the `runtime` package. Verified rerun: orgs (847 passed, 11 BYPASSRLS-skips) and notifications (39 passed) now reach their intended code paths instead of crashing at app-ready. SA80.3 (pg_dump) remains a non-blocking follow-up. SA80 is independent of Track 1/2 — its completion unblocks them for verification.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — fix orgs restricted-role        SA79 — reopened/blocked                    SA80 — re-provision local
  test failures                          (CR-PLAN-SA79-004: retained-role           dev env (venv + role wiring)
  ◐ code fix landed 2026-07-12;          rerun still owed — sole remaining          ✓ SA80.1+SA80.2 done; verified
    verification blocked on SA80          blocker; CR-PLAN-SA79-005 resolved)          2026-07-13: orgs/notifications
    (Track 3) + Track 2                                                              reach real code paths
```

SA77 (Track 1) code fix landed 2026-07-12; full detail in CHANGELOG.md. SA80 (Track 3) implementation and verification is now complete — SA80.1 (quickscale_core venv re-provision) and SA80.2 (retained-role env wiring in scripts/test_integration.sh) are both done and verified. The 2026-07-13 live rerun confirms both SA77 and SA79 tests reach their intended code paths. SA80 had no dependencies and was a clean hand-off candidate.

### Track 1 — Tenant-context surface

SA59 (umbrella, SA59.1–SA59.4) closed 2026-07-12 — see CHANGELOG.md. SA77 code fix implemented 2026-07-12; final DB verification blocked by SA79 (see below).

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, orgs restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA77 — Root-cause and fix orgs' restricted-role test failures.** `Tier 1 · Track 1 · deps: code fix landed 2026-07-12; final verification depends on SA79 (blocked)`
  Code fix landed 2026-07-12 — full root-cause and fix detail (psycopg2→`connection.cursor()` conversion in two test helpers; 6 dynamic-DDL tests marked `@pytest.mark.bypass_rls`) is in [CHANGELOG.md](../../CHANGELOG.md)'s SA77 entry, not repeated here.

  *Acceptance:* the 3 helper-path restricted-role tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the 6 dynamic-DDL tests skip in restricted mode and pass only when `QUICKSCALE_ALLOW_BYPASSRLS` is explicitly enabled. The corresponding `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  **Blocked:** the restricted-role rerun currently aborts in forms 0007 FK validation before reaching the orgs seam (Track 2 SA79, CR-PLAN-SA79-004). Full acceptance cannot be confirmed until SA79 unblocks and the orgs suite passes under the retained-role environment (direct pytest commands or full `make test-integration`).
  **2026-07-13 rerun note:** the attempted verification didn't reach this code path either — orgs' local suite instead hit an unrelated `ModuleNotFoundError` from a stale local `quickscale-core` venv install (environment-only, not a code defect), which the SA76 quarantine absorbed under this ticket anyway. Full detail in [CHANGELOG.md](../../CHANGELOG.md). **SA80 (Track 3, completed 2026-07-13)** resolved both the stale venv issue (SA80.1) and the retained-role env wiring gap (SA80.2) — the local environment blocker is no longer present. The remaining blocker is SA79's forms 0007 FK validation path, which must be resolved before a live SA77 rerun can produce real signal.
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

  **SA80 (Track 3, completed 2026-07-13):** The local env re-provisioning that CR-PLAN-SA79-004's next step described is now done — `quickscale_core` has been editable-reinstalled (SA80.1, operational fix) and `scripts/test_integration.sh` now exports the full `QS_*_DB_USER=quickscale_test_role` set matching CI (SA80.2). **Verified 2026-07-13:** Notifications (39 passed, 0 failed) reaches the forms-0007 code path and passes clean under retained-role env. CR-PLAN-SA79-004 can now produce real SA79-relevant signal (notifications' quarantine entry is SA79's own forms-0007 FK path that passes under retained-role env).

  *Acceptance:* forms 0007 backfill passes under full retained-role env; notifications suite runs clean (unquarantined); audit/status docs reflect current state.

### Track 3 — Core/CLI plumbing

SA80 implementation verified (SA80.1 + SA80.2, verified 2026-07-13). Orgs (847 passed, 11 BYPASSRLS-skips) and notifications (39 passed) now reach real code paths instead of crashing at app-ready. SA80.3 (pg_dump) remains as non-blocking follow-up. Track 3 is otherwise available for new work.

#### Finding — Local dev environment gaps blocking the SA79 retained-role rerun (`why →` [CHANGELOG.md](../../CHANGELOG.md)'s "CR-PLAN-SA79-004 rerun attempted, blocked checkpoint (2026-07-13)" entry)

- [x] **SA80 — Re-provision the local dev environment so a retained-role `make test-integration` rerun produces real signal for SA77/SA79.** `Tier 1 · Track 3 · deps: none`
  The 2026-07-13 rerun attempt was blocked by two environment gaps before it reached either SA77's or SA79's actual code paths. This ticket had no dependencies on Track 1 or Track 2 — closing it is what lets *them* produce real verification signal. Implementation complete (SA80.1+SA80.2) and verified (2026-07-13): orgs (847 passed, 11 BYPASSRLS-skips) and notifications (39 passed) now reach real code paths.

  - [x] **SA80.1 — Editable-reinstall `quickscale_core`.** The local `.venv` had `quickscale-core` installed non-editable at a stale `0.86.0` build, missing the `runtime` package added by SA9.3. Fixed operationally in this session via `poetry install` from repo root. Confirmed: `poetry run pip show quickscale-core` reports version `0.87.0` with editable project location, and `poetry run python -c "import quickscale_core.runtime"` succeeds.
  - [x] **SA80.2 — Fix retained-role env wiring for 7 modules locally.** `scripts/test_integration.sh` now exports all 12 `QS_*_DB_USER` vars defaulting to `quickscale_test_role`, matching `.github/workflows/ci.yml` (lines 399-410) and `publish.yml` (160-171). Each var uses `${VAR:-quickscale_test_role}` so callers can pre-export to override individual modules. The fix is in the script itself, so both direct invocation and callers like `scripts/check_ci_locally.sh` inherit the correct environment. No changes needed to `scripts/check_ci_locally.sh`, `Makefile`, or `scripts/provision_test_roles.sh`.
  - [ ] **SA80.3 — (lower priority, unrelated to SA77/SA79) Install PostgreSQL 18 client tools locally.** `backups` fails 23/299 tests locally on a missing `pg_dump` binary. Install `postgresql-client-18` (PGDG apt repo), matching the guidance already printed in the `BackupError` message this raises. Not a blocker for SA77/SA79 — only needed for a fully green local `make test-integration` run.

  *Acceptance:* the orgs and notifications suites reach — and produce real pass/fail signal for — their respective SA77 and SA79 acceptance criteria, instead of crashing earlier on environment issues. Verified via direct retained-role pytest commands: orgs 847 passed / 11 BYPASSRLS-skips / 93.04% coverage; notifications 39 passed / 91.76% coverage. SA80 itself closes on SA80.1+SA80.2 (SA80.3 is a nice-to-have, trackable independently).
  *(why →* [CHANGELOG.md](../../CHANGELOG.md)'s 2026-07-13 CR-PLAN-SA79-004 rerun checkpoint*)*

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
