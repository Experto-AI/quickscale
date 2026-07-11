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

> Completed and archived work lives in [CHANGELOG.md](../../CHANGELOG.md). Keep only active or blocked work here.
>
> **Track readiness (2026-07-11):**
> - **Track 1** — not clean as a whole, but no longer hard-blocked. SA59.1 is still open (parked at a prior user-directed stop on pre-existing test failures). SA59.2 has no blockers and can proceed. SA59.3's `F-SA59-ROLE-006` now has a decided design (2026-07-11: script/Docker-init role provisioning, no human administrator step — see SA59.3 below) and just needs implementing. SA59.4 still waits on SA59.1–SA59.3. SA60 and SA70 remain open and parallel-safe.
> - **Track 2** — clean. No open items remain after SA73's closeout.
> - **Track 3** — blocked. SA67 is the only remaining item and cannot proceed without external beta-site repository/deployment access.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA59 — drop bypassrls auto-prime       — clean / no open items —                 SA67 — verify + patch SA63 on the
  (umbrella, split → SA59.1–SA59.4)                                                  beta sites (blocked; external)
SA60 — composite-FK deferability
  policy + conformance gate
SA70 — orgs pre_delete receiver
  backstop (Finding 2 first step)
```

Open work no longer spans three active repo-local lanes. Track 1 is the only implementation lane with active in-repo work; Track 2 is clean; Track 3's only remaining item (SA67) is blocked on external beta-site access, so there is no repo-local parallel branch to run there until access exists. Within Track 1, SA59.1–SA59.4, SA60, and SA70 touch disjoint files (SA59.1: `Makefile` + `scripts/test_unit.sh` + `ci.yml` + `publish.yml`; SA59.2: backups module settings/manifests; SA59.3: test-database role setup + grant config; SA59.4: `docs/technical/decisions.md` + role reference docs; SA60: `orgs/tenancy.py` + forms migrations; SA70: `orgs/signals.py` + a new receiver test) and share only `decisions.md` (additive sections, not a real conflict — see the shared-closeout-files note below). SA59.3 carries soft deps on SA59.1 and SA59.2; SA59.4 depends on all three prior sub-slices. The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` remain the one universal merge-conflict exception across tracks.

### Track 1 — Tenant-context surface

Open items below. SA59 (umbrella) remains blocked/open via SA59.1–SA59.4; SA60 and SA70 remain active Track 1 work.

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 (umbrella) — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path — blocked (split into SA59.1–SA59.4).** `Tier 2 → split · Track 1 · deps: none`
  `Makefile:321-327` (`test-unit`) and `scripts/test_unit.sh:365-366` both blanket-export `QUICKSCALE_ALLOW_BYPASSRLS=1` for every module suite, which (a) disables the SA58 boot guard (now landed — checks both `rolbypassrls` and `rolsuper`) entirely during CI and local `make test-unit` runs and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests always running — contradicting the SA14.4 decision still documented at `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. No environment currently demonstrates the boot guard firing against a bypassing role.
  **Decision (2026-07-10, reaffirmed):** split release/CI validation into a DB-free unit gate plus a separate PostgreSQL integration gate, rather than threading a NOBYPASSRLS role through the existing combined `scripts/test_unit.sh` run (the alternative considered and rejected). The currently-combined script splits along its existing DB-need boundary: a fast path with no DB dependency, and an integration path that runs the DB-touching module suites against a NOBYPASSRLS role. The direct-connection role used by the integration path must be `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — the target role contract for the integration gate (the CI worktree's current `quickscale_test_role` omits `NOINHERIT`, tracked by F-SA59-ROLE-006) — so test suites can establish database connections under the restricted profile. The `CREATE ROLE ... NOBYPASSRLS NOINHERIT NOLOGIN` pattern from `scripts/test_isolation_conformance.sh:50` is a separate pattern for the isolation-conformance inner role (which exercises RLS isolation without needing a login-capable role); it does not apply to the direct-connection integration role. Both `ci.yml`'s `test` job and `publish.yml`'s `test` job gate on the integration path — `ci.yml:238-249`'s `test` job today also connects as the plain `postgres` superuser with no NOBYPASSRLS role (same gap tech-audit didn't separately flag but is in scope here), so it isn't just `publish.yml` that needs the new role. The SA59 aggregate was raised from Tier 1 to Tier 2 for the added script-split and two-workflow scope; the individual sub-slices are sized Tier 1–2.
  **Split (2026-07-11):** Per roadmap policy — a checklist item sized Tier 3 (7-item blocker ledger) must be split before implementation. Four sub-slices defined below, each Tier 1–2. The umbrella remains blocked until all four are complete.

  **Merged blocked-checkpoint state — SA59.1 merged to v87 (2026-07-11):** SA59.1 implementation artifacts have been merged to v87 as a blocked checkpoint per user direction. Open review findings and pre-existing integration failures remain unresolved (see still-open blockers under SA59.1 below). SA59.2–SA59.4 are not part of this merge and remain blocked. Detail on the CI role setup, test-script split, and coverage wiring is in [CHANGELOG.md](../../CHANGELOG.md). *(Integration gate findings: the NOBYPASSRLS path exposed pre-existing RLS test failures — 15 in billing, 45 in social — plus 77.55% mean module coverage across the 12 integration suites. These are discovered blockers requiring separately scoped follow-up, not resolved by SA59 itself.)*

  ---

  - [ ] **SA59.1 — Validation harness + coverage plumbing (merged to v87 as blocked checkpoint; review findings remain open).** `Tier 1 · Track 1 · deps: none` *(user-directed stop 2026-07-11 — merged as-is with open blockers)*
    Implementation resolves three umbrella blockers (e2e exclusion, local CI parity, module coverage persistence) plus four review passes' operational and source-file corrections — detail in [CHANGELOG.md](../../CHANGELOG.md). No production code was changed.

    **Remaining blockers (SA59.1 not complete — must be resolved before closeout):**
    - **Orgs pre-existing failures (refined).** 3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py` persist. These depend on restricted-role `CREATE ROLE` behavior (SA59.3-style territory) and are not resolved by the Phase 3 test-only adaptations.
    - **Forms migration failure (newly discovered).** `quickscale_modules/forms/migrations/0007_new_organization_ownership.py` fails composite-FK validation on a fresh restricted-role DB. Discovered during this session's integration gate walk.
    - **Notifications duplicate-db issues (newly discovered).** Reruns hit `test_test_quickscale_notifications` ownership/duplicate-db problems. Discovered during this session's integration gate walk.
    - **Validated green:** billing (216 passed, 1 explicit bypass skip) and social (106/108 passed) were green on clean restricted-role rerun.

  - [ ] **SA59.2 — Backups PostgreSQL seam.** `Tier 1 · Track 1 · deps: none`
    Provide a proper PostgreSQL/RLS seam for the backups module so its integration suite exercises tenant-boundary safety under a restricted role. Inherits one blocker:
    - **F-SA59-DB-007** — Backups integration tests use SQLite and lack a `QS_BACKUPS_DB_*` PostgreSQL/RLS seam. Manifests/settings fall back to SQLite; no integration run exercises backups against a real PostgreSQL restricted role. Backups must connect as a restricted PostgreSQL role with RLS active before the integration gate validates tenant-boundary safety.

  - [ ] **SA59.3 — Retained-role contract conversion.** `Tier 2 · Track 1 · deps: SA59.1, SA59.2` — **unblocked design decided 2026-07-11; not yet implemented.**
    Remove runtime DDL from test helpers and execute the full restricted-role PostgreSQL 18 module gate end-to-end with coverage evidence. Inherits two blockers and the unmerged CI role work:
    - **F-SA59-ROLE-006 — design decided (2026-07-11), supersedes the prior "needs a database administrator" framing.** The original framing implied a human had to intervene out-of-band; that's wrong — CI's `postgres:18` service already runs with `POSTGRES_HOST_AUTH_METHOD: trust` and CI already uses that superuser access to `CREATE ROLE quickscale_test_role` (`ci.yml:340-345`). The fix is to reuse that *same* superuser step to also provision the inner RLS role Forms/Listings tests need, instead of letting the test suite create it itself (which is what currently forces `CREATEROLE` onto the restricted role and is the actual defect this finding is about). **Chosen design:**
      1. Write the inner-role provisioning SQL (`CREATE ROLE` + least-privilege schema/table grants) into one shared script/SQL file, not duplicated per module.
      2. **CI**: add a step in `ci.yml` (and `publish.yml`) right next to the existing `quickscale_test_role` creation step (`ci.yml:340-345`) that runs this same script against the trust-authenticated `postgres` superuser.
      3. **Local dev**: mount the same SQL as a `docker-entrypoint-initdb.d/*.sql` init script for the docker-compose Postgres service (or invoke the shared script from `scripts/bootstrap.sh`/`make bootstrap`) so local setup is one Docker-Compose-managed step, not a manual grant a developer has to run by hand.
      4. Forms/Listings test helpers change from *create-then-use* to *assert-then-use*: check `has_schema_privilege`/`has_table_privilege` for the pre-provisioned role and fail loudly with setup instructions if missing, instead of issuing `CREATE ROLE`/`GRANT` themselves.
      5. The outer test-connection role (`quickscale_test_role`) then genuinely gets `NOCREATEROLE`, making the old runtime-DDL path structurally impossible rather than just discouraged.
      6. Every test-database role creation path (CI and local) must assert `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` explicitly — the CI worktree's `quickscale_test_role` currently omits `NOINHERIT`.
      *Rejected alternative:* moving integration tests out of CI entirely (local-only) to sidestep the role question — rejected because it would silently undo SA58/SA59/SA14.4's whole point (CI must exercise RLS under a restricted role, or a real isolation regression could merge undetected — see tech-audit.md TA49).
      *Target files (new):* a shared SQL/script file for inner-role provisioning (exact path TBD at implementation time — candidates: `scripts/provision_test_roles.sh` or a `.sql` file under a new `db/init/` or similar, consumed by both `docker-entrypoint-initdb.d` and CI); `.github/workflows/ci.yml` (new step beside the existing role-creation step, `:340-345`); `.github/workflows/publish.yml` (same step); `docker-compose.yml` or local Postgres service config (mount the init script); Forms/Listings test setup helpers (switch to assert-only).
    - **F-SA59-VALID-003** — Execute full restricted-role PostgreSQL 18 module gate end-to-end with coverage evidence. The restricted-role integration pipeline has not been successfully executed through its full path. The ci.yml integration step provides partial signal, but the publish.yml restricted-role workflow remains unverified. A successful end-to-end run must produce per-module coverage artifacts and confirm the restricted role fired correctly across all suites.
    *Note — unmerged worktree role artifacts* (`quickscale_test_role` CI wiring, publish.yml role setup, decisions.md gate-split record) form the starting point for this sub-slice; they are now safe to build on since F-SA59-ROLE-006 has a decided, script/Docker-only path with no human-administrator step.

  - [ ] **SA59.4 — Docs + final closeout.** `Tier 1 · Track 1 · deps: SA59.1, SA59.2, SA59.3`
    Correct documentation to match the adopted role shape, record the gate-split decision in decisions.md, and produce the final closeout checkpoint. Inherits two documentation fixes:
    - **F-SA59-DOC-002 / F-SA59-CMD-010** — Direct-connection role uses `LOGIN`, not `NOLOGIN`; correct matching docs and command matrix. Role descriptions in `Makefile` (help text) and scripts (`test_unit.sh`, `test_integration.sh`) still use `NOLOGIN`, but the CI `quickscale_test_role` requires `LOGIN` to establish test-database connections (CHANGELOG.md no longer carries the stale NOLOGIN wording). All documentation and the command matrix must reflect `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` consistently.
    - **Advisory: agent-handback provenance discrepancy (user accepted).** The previous implementation handback omitted `decisions.md` and `scripts/test_integration.sh` from its changed-files listing. Include these files in the closeout manifest.
    *Target files (SA59.4 share):* `docs/technical/decisions.md` (record the unit/integration gate split); role-description prose in scripts, workflow docs, CHANGELOG, and the test-command reference matrix.
    *Acceptance:* the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is removed from the unit-only path; the integration path runs module suites against a NOBYPASSRLS role in both `ci.yml` and `publish.yml`; developers set the SA14.4 hatch explicitly per-suite when they need it; `make test-unit` (and the new integration target) documents the split in its help text; decisions.md records the split.

  - **Blocked-checkpoint state:** SA59.1 — merged to v87 as blocked checkpoint (2026-07-11); resolved review findings (CR-SA59 series) are documented in [CHANGELOG.md](../../CHANGELOG.md). **Still unresolved:** pre-existing integration failures — orgs (3 test_models.py + 6 helper-path errors), forms (0007 migration composite-FK on restricted-role DB), notifications (duplicate-db/ownership). Billing and social were green on clean rerun. User chose to stop at the scope boundary rather than authorize expansion to fix newly-discovered pre-existing failures. SA59.1 remains open. SA59.2 is unblocked and can proceed independently. SA59.3's F-SA59-ROLE-006 blocker is resolved at the design level (2026-07-11 — see SA59.3 above); SA59.4 still waits on SA59.1–SA59.3 completing.
  - **Continuation note (2026-07-11):** Billing's canonical restricted-role suite is green (216 passed, 1 explicit bypass skip). Social test context work is unreviewed and incomplete (106/108 passed in the last restricted-role run); two social restricted-role boundary tests still need the direct-role adaptation pattern. The true cross-organization UPDATE test awaits an explicit decision between a single bypass-RLS mark, a production RLS-write expansion, or accepting a delete/create approximation.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `composite-fk-deferability-contract-diverged` (`why →` [tech-audit.md TA50](../others/tech-audit.md), [arch-audit.md Finding 4](../others/arch-audit.md) caution + Questions)

- [ ] **SA60 — Pick and enforce one composite-FK deferability policy.** `Tier 2 · Track 1 · deps: none`
  `6ea37301` silently flipped the Option C composite-FK helper (`orgs/tenancy.py:903`, `_ADD_COMPOSITE_FK_SQL`) from `DEFERRABLE INITIALLY DEFERRED` to `NOT DEFERRABLE`, with no decisions.md record and no test asserting the new behavior. This diverges from `forms/0007`'s own inlined `DEFERRABLE INITIALLY DEFERRED` SQL (and its `test_migrations.py:457-505` assertion) and from every *existing* database (fresh installs get `NOT DEFERRABLE`, existing ones keep `DEFERRABLE` — fleet drift with no aligning migration). Empirically verified this pass (PostgreSQL 18): `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so `NOT DEFERRABLE` is defensible on fail-fast grounds — but it needs to be the *documented*, uniformly-applied policy, not a one-module drift. Bundle in the second, cheaper doc gap arch-audit flagged in the same commit: `is_tenant_model()`'s `tenant_excluded`-marker-beats-manager/base-class precedence change (`tenancy.py:1548+`) also has no decision record.
  *Files:* `docs/technical/decisions.md` (two new entries: composite-FK deferability policy under the Option C child-table section; `tenant_excluded` precedence rule); `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:903` (helper SQL, if the decision changes it back) and `:1548+` (precedence — doc-only, no code change expected); `quickscale_modules/forms/src/quickscale_modules_forms/migrations/0007*.py` (align to the chosen policy); `quickscale_modules/forms/tests/test_migrations.py:457-505` and `quickscale_modules/crm/tests/test_migrations.py:1107,1158` (update assertions/stale comments to match); extend the SA35-style cross-module conformance gate to assert one deferability policy for all Option C composite FKs.
  *Acceptance:* decisions.md states the deferability policy (recommend keeping `NOT DEFERRABLE` given the empirical fail-fast verification, but ratify explicitly) and the `tenant_excluded` precedence rule; `forms/0007` and the `tenancy.py` helper emit the same deferability clause; a new conformance test fails if any Option C composite FK diverges; the two now-stale test comments (`crm/tests/test_migrations.py:1107,1158`) are corrected to reflect the no-op-on-NOT-DEFERRABLE behavior.
  *(why →* [tech-audit.md TA50](../others/tech-audit.md)*,* [arch-audit.md Finding 4](../others/arch-audit.md)*)*

#### Finding — `deletion-invariants-per-boundary-reimplementation`, first step (`why →` [arch-audit.md Finding 2](../others/arch-audit.md))

- [ ] **SA70 — Add an orgs `pre_delete` receiver backstop for the last-owner invariant.** `Tier 1 · Track 1 · deps: none`
  Today the last-owner/personal-org invariant (`OrganizationMembership.is_last_owner_with_members()`, `orgs/models.py:165`) is enforced only at boundaries that choose to call it — `AccountDeleteView` and both orgs view callsites — so any deletion path that doesn't go through one of those four callsites (e.g. a future GDPR erasure command, or a direct ORM/admin delete) bypasses the rule entirely, since instance `delete()` overrides don't run under Django's deletion collector for cascades. Arch-audit's Finding 2 is `deferred` overall (full M-sized scope needs the teams build to justify a domain-owned deletion service), but explicitly flags this first step as "small enough to land as a general hardening item without waiting on teams."
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/signals.py` (new `pre_delete` receiver on the `User` model, calling the existing SA47 canonical check); `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py` (wire the receiver in `ready()` if not already using a signals-autodiscovery pattern — check the existing `ready()` for how other receivers are registered); a new regression test that deletes a last-owner `User` directly via the ORM (bypassing the view layer) and asserts the deletion is refused.
  *Acceptance:* a direct `user.delete()` ORM call on a sole owner of a multi-member org raises/refuses exactly like `AccountDeleteView` does today; the four existing callsites are unaffected (the receiver is a backstop, not a replacement); no change to the sole-member self-removal behavior documented as deliberate (SA47's orphaned-org watch item).
  *(why →* [arch-audit.md Finding 2](../others/arch-audit.md)*)*

### Track 2 — Module contracts & settings

**No open items.** Track 2 is clean — completed work lives in [CHANGELOG.md](../../CHANGELOG.md).

### Track 3 — Core/CLI plumbing

Only open item below: SA67 (blocked). Completed Track 3 work lives in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — SA63/SA68 beta-site rollout parity still unverified (`why →` [arch-audit.md Red flags](../others/arch-audit.md))

- [ ] **SA67 — Verify beta-site rollout parity for `experto-ai-web` and `bap-web`; patch by hand if needed.** `Tier 1 · Track 3 · deps: none — blocked on external access`
  The repo-local follow-up is already complete: SA66 classified `start.sh` correctly for beta migration, and SA68 closed the remaining launcher-contract work plus the Redis-dependent rollout guidance for donor-owned `settings/production.py`. The remaining work is now external verification only: inspect each beta site's deployed `start.sh`, current donor-owned `settings/production.py`, Redis state, and deploy outcome; if either site is missing the required env-pair bridge or rollout ordering, patch/redeploy by hand and record the evidence. This remains a red-flag-shaped external parity check, not an open repo-local tooling fix.
  *Files:* none in this repo except a note in `docs/planning/beta-site-migration.md` recording what was verified and whether a manual cherry-pick of the env-pair bridge into the existing donor-owned `settings/production.py` was required; the actual patch happens in the `experto-ai-web` and `bap-web` repos (external to this monorepo).
  *Acceptance:* for each beta site, confirm deployed launcher parity with the current templates, confirm Redis-present/Redis-absent rollout conditions, and where Redis is absent confirm the donor-owned `settings/production.py` already contains the SA63+SA68 env-pair bridge or receives the documented manual cherry-pick before redeploy. Record the check and outcome in `beta-site-migration.md` or a CHANGELOG entry.
  **Blocker (2026-07-11):** Deferred — no files, Redis state, deployment, patch, or redeploy were inspected or performed in `experto-ai-web` or `bap-web`. Both beta sites are external to this monorepo with no available repository or deployment access. Unblocking requires repository/deployment access (or equivalent current-file, Redis, and deploy evidence) for both sites. User-directed skip per decisions.md — SA67 is not reopened or implemented in this run.
  *(why →* [arch-audit.md Red flags](../others/arch-audit.md)*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
