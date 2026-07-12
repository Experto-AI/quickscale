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
> **Track readiness (2026-07-12):**
> - **Track 1** — mostly unblocked. SA59.4 remains **BLOCKED**, but narrowly — waiting only on **SA76** (a small, scoped quarantine PR, now on Track 3), not on any of the underlying bugs being fixed. Everything else on Track 1 is unblocked and available to start now: SA70 (decision ratified), SA74 (TA54, **S1 production defect** — fix this first), and SA77 (orgs' restricted-role `CREATE ROLE` failures, split out of SA59.1 as an independent, non-blocking follow-up). SA74/SA77 are new items added this pass from tech-audit.md's 2026-07-11 findings and the 2026-07-12 SA59.1 closeout-path decision (Option B — see SA59.1's entry for the full rationale).
> - **Track 2** — one item completed (SA60, composite-FK deferability policy enforced as NOT DEFERRABLE, 2026-07-12), one item open and unblocked: SA78 (notifications' restricted-role duplicate-db failures, split out of SA59.1 as a module-owned test-database issue). Track 2 stays busy on its own — no reassignment needed here.
> - **Track 3** — one just-completed item (SA75, closed in this change) and one open, unblocked item (**SA76**, moved from Track 1 to keep this track from going idle after SA75). Both are core-level test/CI-tooling work, parallel-safe, and unrelated to the SA67 beta-site closeout (whose outstanding manual check remains tracked in `beta-site-migration.md`, not here).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA59 — drop bypassrls auto-prime       SA60 — composite-FK deferability          SA75 — narrow adapter-fixture
  (umbrella, split → SA59.1–SA59.4)      policy + conformance gate                 exception catch (TA56)
SA70 — orgs pre_delete receiver        SA78 — fix notifications                 SA76 — quarantine known
  backstop (Finding 2 first step)        duplicate-db failures                    integration-gate failures (TA57)
SA74 — prime CRM org-creation
  seeding context (TA54, S1)
SA77 — fix orgs restricted-role
  CREATE ROLE failures
```

Track 2 carries two items (SA60, moved from Track 1; SA78, split from SA59.1); Track 3 now carries two items (SA75; SA76, moved from Track 1 this pass to keep the track from going idle). Track 1 still carries the bulk of open work; within it, SA59.1, SA59.4, SA70, SA74, and SA77 touch disjoint files (SA59.1/SA59.4: `Makefile` + `scripts/test_unit.sh` + `ci.yml` + `publish.yml` + `docs/technical/decisions.md`; SA70: `orgs/signals.py` + a new receiver test; SA74: `crm/services.py` + `orgs/tests/conftest.py`; SA77: orgs test files + possibly `scripts/provision_test_roles.sh`) and share only `decisions.md` (additive sections, not a real conflict — see the shared-closeout-files note below). SA59.2 and SA59.3 are complete (see CHANGELOG.md); SA59.4 now depends only on SA76 (Track 3) landing (not on SA77/SA78/SA60 — see SA59.1's closeout-path decision) — a cross-track dependency, which is fine since tracks parallelize independent *work*, not the dependency graph. SA76 (Track 3) and SA77 (Track 1) both touch the integration gate's failure set (one quarantines, one fixes) — no file conflict, but coordinate the order (SA76 first unblocks SA59.4 immediately; SA77 later removes its specific quarantine entry). SA60/SA78 (Track 2) and SA75/SA76 (Track 3) are fully independent of every Track 1 item. The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` remain the one universal merge-conflict exception across tracks.

### Track 1 — Tenant-context surface

Open items below. SA59 (umbrella) remains blocked/open via SA59.1–SA59.4, but SA59.4's block narrowed to just SA76 landing (2026-07-12 closeout-path decision — see SA59.1's entry). SA70 remains active Track 1 work, unblocked since its pending decision was ratified 2026-07-12. SA74 and SA77 are new items added this pass (SA74 from tech-audit.md's 2026-07-11 findings; SA77 split out of SA59.1's blocker list). SA60 moved to Track 2 and SA76 moved to Track 3 this pass — see there.

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 (umbrella) — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path — blocked (split into SA59.1–SA59.4).** `Tier 2 → split · Track 1 · deps: none`
  `Makefile:321-327` (`test-unit`) and `scripts/test_unit.sh:365-366` both blanket-export `QUICKSCALE_ALLOW_BYPASSRLS=1` for every module suite, which (a) disables the SA58 boot guard (now landed — checks both `rolbypassrls` and `rolsuper`) entirely during CI and local `make test-unit` runs and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests always running — contradicting the SA14.4 decision still documented at `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. No environment currently demonstrates the boot guard firing against a bypassing role.
  **Decision (2026-07-10, reaffirmed):** split release/CI validation into a DB-free unit gate plus a separate PostgreSQL integration gate, rather than threading a NOBYPASSRLS role through the existing combined `scripts/test_unit.sh` run (the alternative considered and rejected). The currently-combined script splits along its existing DB-need boundary: a fast path with no DB dependency, and an integration path that runs the DB-touching module suites against a NOBYPASSRLS role. The direct-connection role used by the integration path must be `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — the target role contract for the integration gate (the CI worktree's current `quickscale_test_role` omits `NOINHERIT`, tracked by F-SA59-ROLE-006) — so test suites can establish database connections under the restricted profile. The `CREATE ROLE ... NOBYPASSRLS NOINHERIT NOLOGIN` pattern from `scripts/test_isolation_conformance.sh:50` is a separate pattern for the isolation-conformance inner role (which exercises RLS isolation without needing a login-capable role); it does not apply to the direct-connection integration role. Both `ci.yml`'s `test` job and `publish.yml`'s `test` job gate on the integration path — `ci.yml:238-249`'s `test` job today also connects as the plain `postgres` superuser with no NOBYPASSRLS role (same gap tech-audit didn't separately flag but is in scope here), so it isn't just `publish.yml` that needs the new role. The SA59 aggregate was raised from Tier 1 to Tier 2 for the added script-split and two-workflow scope; the individual sub-slices are sized Tier 1–2.
  **Split (2026-07-11):** Per roadmap policy — a checklist item sized Tier 3 (7-item blocker ledger) must be split before implementation. Four sub-slices defined below, each Tier 1–2. The umbrella remains blocked until all four are complete.

  **Merged blocked-checkpoint state — SA59.1 merged to v87 (2026-07-11):** SA59.1 implementation artifacts have been merged to v87 as a blocked checkpoint per user direction. Open review findings and pre-existing integration failures remain unresolved (see still-open blockers under SA59.1 below). SA59.2–SA59.4 were not part of this merge and remained blocked at that point (SA59.2 has since been unblocked). Detail on the CI role setup, test-script split, and coverage wiring is in [CHANGELOG.md](../../CHANGELOG.md). *(Integration gate findings: the NOBYPASSRLS path exposed pre-existing RLS test failures — 15 in billing, 45 in social — plus 77.55% mean module coverage across the 12 integration suites. These are discovered blockers requiring separately scoped follow-up, not resolved by SA59 itself.)*

  ---

  - [ ] **SA59.1 — Validation harness + coverage plumbing (merged to v87 as blocked checkpoint; closes via SA76's quarantine, not a full fix of every discovered failure).** `Tier 1 · Track 1 · deps: SA76 (Track 3, cross-track)` *(closeout path decided 2026-07-12 — see below)*
    Implementation resolves three umbrella blockers (e2e exclusion, local CI parity, module coverage persistence) plus four review passes' operational and source-file corrections — detail in [CHANGELOG.md](../../CHANGELOG.md). No production code was changed.

    **Closeout path (decided 2026-07-12):** SA59.1's own deliverable — the unit/integration gate split — is mechanically complete; turning the integration gate on for the first time surfaced three pre-existing, unrelated module bugs it was never scoped to fix. Rather than holding SA59.1/SA59.4 open indefinitely on unbounded root-causing (the pattern that produced two prior stop points), SA59.1 closes once **SA76** (Track 3) lands (quarantines the known failures so the gate is green for everything else). The three discovered failures are spun out as independently tracked, non-blocking follow-ups:
    - **Orgs pre-existing failures.** 3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py`, tied to restricted-role `CREATE ROLE` behavior. Tracked as **SA77** (Track 1, below).
    - **Forms migration failure.** `quickscale_modules/forms/migrations/0007_new_organization_ownership.py` fails composite-FK validation on a fresh restricted-role DB. **Resolved by SA60** (Track 2, unblocked 2026-07-12) — no separate ticket needed.
    - **Notifications duplicate-db issues.** Reruns hit `test_test_quickscale_notifications` ownership/duplicate-db problems. Tracked as **SA78** (Track 2, below).
    - **Validated green:** billing (216 passed, 1 explicit bypass skip) was green on clean restricted-role rerun. Social (106/108 passed, 2 remaining boundary tests) ran clean but is not fully closed.

  - [ ] **SA59.4 — Docs + final closeout — BLOCKED (waiting on SA76's quarantine, not on SA77/SA78/full fixes).** `Tier 1 · Track 1 · deps: SA59.1, SA76 (Track 3, cross-track), SA59.2 (complete, see CHANGELOG.md), SA59.3 (complete, see CHANGELOG.md)`
    Correct documentation to match the adopted role shape, record the gate-split decision in decisions.md, and produce the final closeout checkpoint. Inherits two documentation fixes:
    - **F-SA59-DOC-002 / F-SA59-CMD-010** — Direct-connection role uses `LOGIN`, not `NOLOGIN`; correct matching docs and command matrix. Role descriptions in `Makefile` (help text) and scripts (`test_unit.sh`, `test_integration.sh`) still use `NOLOGIN`, but the CI `quickscale_test_role` requires `LOGIN` to establish test-database connections (CHANGELOG.md no longer carries the stale NOLOGIN wording). All documentation and the command matrix must reflect `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` consistently.
    - **Advisory: agent-handback provenance discrepancy (user accepted).** The previous implementation handback omitted `decisions.md` and `scripts/test_integration.sh` from its changed-files listing. Include these files in the closeout manifest.
    *Target files (SA59.4 share):* `docs/technical/decisions.md` (record the unit/integration gate split); role-description prose in scripts, workflow docs, CHANGELOG, and the test-command reference matrix.
    *Acceptance:* the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is removed from the unit-only path; the integration path runs module suites against a NOBYPASSRLS role in both `ci.yml` and `publish.yml`; developers set the SA14.4 hatch explicitly per-suite when they need it; `make test-unit` (and the new integration target) documents the split in its help text; decisions.md records the split.

  - **Blocked-checkpoint state:** SA59.1 — merged to v87 as blocked checkpoint (2026-07-11); resolved review findings (CR-SA59 series) are documented in [CHANGELOG.md](../../CHANGELOG.md). Billing was green on clean rerun; social (106/108 passed) ran clean but remains unreviewed and incomplete (2 remaining boundary tests). SA59.2 and SA59.3 are complete (2026-07-11, see [CHANGELOG.md](../../CHANGELOG.md)). SA59.4 waits on SA76 (quarantine, Track 3), not on SA77/SA78/SA60 landing.
  - **Stop-state (2026-07-12), superseded by the closeout-path decision above:** SA59.4 was blocked on all three discovered failures being fixed. That's now narrowed to just SA76 landing — SA60 (Track 2) independently fixes the forms piece, and SA77/SA78 carry the orgs/notifications pieces as non-blocking follow-ups. SA70, SA74, SA77 are all unblocked and available on Track 1; SA60/SA78 on Track 2; SA76 on Track 3.
  - **Continuation note (2026-07-11):** Billing's canonical restricted-role suite is green (216 passed, 1 explicit bypass skip). Social test context work is unreviewed and incomplete (106/108 passed in the last restricted-role run); two social restricted-role boundary tests still need the direct-role adaptation pattern. The true cross-organization UPDATE test awaits an explicit decision between a single bypass-RLS mark, a production RLS-write expansion, or accepting a delete/create approximation.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `deletion-invariants-per-boundary-reimplementation`, first step (`why →` [arch-audit.md Finding 2](../others/arch-audit.md))

- [ ] **SA70 — Add an orgs `pre_delete` receiver backstop for the last-owner invariant.** `Tier 1 · Track 1 · deps: none`
  Today the last-owner/personal-org invariant (`OrganizationMembership.is_last_owner_with_members()`, `orgs/models.py:165`) is enforced only at boundaries that choose to call it — `AccountDeleteView` and both orgs view callsites — so any deletion path that doesn't go through one of those four callsites (e.g. a future GDPR erasure command, or a direct ORM/admin delete) bypasses the rule entirely, since instance `delete()` overrides don't run under Django's deletion collector for cascades. Arch-audit's Finding 2 is `deferred` overall (full M-sized scope needs the teams build to justify a domain-owned deletion service), but explicitly flags this first step as "small enough to land as a general hardening item without waiting on teams."
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/signals.py` (new `pre_delete` receiver on the `User` model, calling the existing SA47 canonical check); `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py` (wire the receiver in `ready()` if not already using a signals-autodiscovery pattern — check the existing `ready()` for how other receivers are registered); a new regression test that deletes a last-owner `User` directly via the ORM (bypassing the view layer) and asserts the deletion is refused.
  *Acceptance:* a direct `user.delete()` ORM call on a sole owner of a multi-member org raises/refuses exactly like `AccountDeleteView` does today; the four existing callsites are unaffected (the receiver is a backstop, not a replacement); no change to the sole-member self-removal behavior documented as deliberate (SA47's orphaned-org watch item).
  **Decision ratified (2026-07-12):** the receiver raises (does not return early / silently no-op) — recorded in `decisions.md §Multi-tenant SaaS Architecture`. SA70 is unblocked; implementation can proceed.
  *(why →* [arch-audit.md Finding 2](../others/arch-audit.md)*)*

#### Finding — `org-creation-crm-seeding-fails-under-force-rls` (`why →` [tech-audit.md TA54](../others/tech-audit.md))

- [ ] **SA74 — Prime tenant context for CRM's org-creation stage seeding; remove the orgs test-suite signal muting.** `Tier 1 · Track 1 · deps: none`
  **S1, production-path defect.** `crm/services.ensure_org_default_stages` (`quickscale_modules/crm/src/quickscale_modules_crm/services.py:39-85`) INSERTs `Stage` rows for a newly created organization, but the table is under FORCE RLS with a `WITH CHECK` clause requiring `app.current_org_id` to match. Neither dispatch site (`orgs/managers.py:207`, `orgs/forms.py:117`) nor the `organization_created` receiver (`crm/signals.py:16`) primes the new org's context before the write, so under the mandated NOBYPASSRLS production runtime role every org-creation path (signup, `/orgs/new/`, lazy personal-org creation) 500s. Currently invisible to CI because `orgs/tests/conftest.py:50-72`'s autouse fixture patches `organization_created.send` out globally (added in the SA59.1 checkpoint as a test-only workaround, not a blessed production behavior).
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/services.py` (wrap `_seed_default_stages`'s writes in `org_scope(organization)` or an equivalent `_tenant_context` call — CRM owns the seam since it owns the receiver; dispatch-site priming is the documented alternative if the project prefers "dispatcher guarantees context" as the receiver contract); `orgs/tests/conftest.py:50-72` (remove or invert the autouse `organization_created.send` muting once the fix lands, restoring the org-creation seam to real test coverage).
  *Acceptance:* `create_personal_for` with the ContextVar unset, run under the restricted role, seeds all 4 default stages without an RLS violation; the orgs test suite runs without muting `organization_created.send`; a new CRM regression test proves the seeding path under a restricted role with no ambient org context.
  *(why →* [tech-audit.md TA54](../others/tech-audit.md)*,* [tech-audit.md TA55](../others/tech-audit.md)*)*

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, orgs restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA77 — Root-cause and fix orgs' restricted-role `CREATE ROLE`-dependent test failures.** `Tier 1 · Track 1 · deps: none`
  3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py` persist under the NOBYPASSRLS integration role. These depend on restricted-role `CREATE ROLE` behavior (SA59.3-style territory) and were not resolved by SA59.1's Phase 3 test-only adaptations or by SA59.3's create-then-use → assert-then-use conversion. Root cause not yet established — investigate whether these tests still attempt a `CREATE ROLE` call SA59.3 didn't cover, or exercise a role capability the shared `quickscale_test_role`/`quickscale_rls_test_role` contract doesn't grant.
  *Files:* `quickscale_modules/orgs/tests/test_tenant_table_conformance.py`, `quickscale_modules/orgs/tests/test_operator_access.py`, `quickscale_modules/orgs/tests/test_models.py` — plus `scripts/provision_test_roles.sh` if the fix is a role-contract gap rather than a test-helper gap.
  *Acceptance:* all 9 failing tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the corresponding `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

SA60 completed 2026-07-12 (composite-FK deferability policy enforced as NOT DEFERRABLE). One remaining open item: SA78 (notifications' restricted-role duplicate-db failures, split out of SA59.1). SA60 moved from Track 1 earlier this pass; SA78 is new, split out of SA59.1's blocker list (2026-07-12 closeout-path decision) as a module-owned test-database issue. Neither has any file overlap with Track 1 or Track 3.

#### Finding — `composite-fk-deferability-contract-diverged` (`why →` [tech-audit.md TA50](../others/tech-audit.md), [arch-audit.md Finding 4](../others/arch-audit.md) caution + Questions)

- [x] **SA60 — Enforce uniform NOT DEFERRABLE policy for all Option C composite FKs (2026-07-12).** `Tier 2 · Track 2 · deps: none`
  Implementation delta: aligned `forms/migrations/0007_new_organization_ownership.py`'s inlined SQL from `DEFERRABLE INITIALLY DEFERRED` to `NOT DEFERRABLE` (matching the shared helper in `orgs/tenancy.py:_ADD_COMPOSITE_FK_SQL`, which already emitted `NOT DEFERRABLE`); renamed and inverted the forms migration test (`test_0007_composite_fks_are_not_deferrable`) to assert `condeferrable=False`; corrected two stale CRM migration test comments to reflect the no-op-on-NOT-DEFERRABLE behavior; added a cross-module conformance gate (`orgs/tests/test_sa60_composite_fk_conformance.py`) that checks all six known composite FKs for `condeferrable=False`. The `tenant_excluded` precedence rule was already a doc-only ratification in `decisions.md` — no code change was needed. Closes SA60. **Also resolves one of SA59.1's three remaining blockers** (forms `0007` fails composite-FK validation on a fresh restricted-role DB) — see the SA59.1 blocker note on Track 1.
  *(why →* [tech-audit.md TA50](../others/tech-audit.md)*,* [arch-audit.md Finding 4](../others/arch-audit.md)*)*

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, notifications restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA78 — Fix notifications' duplicate-db/ownership failures on restricted-role reruns.** `Tier 1 · Track 2 · deps: none`
  Reruns of the notifications module suite under the restricted `quickscale_test_role` hit `test_test_quickscale_notifications` ownership/duplicate-db problems — discovered during SA59.1's integration gate walk, not yet root-caused. Assigned to Track 2 (not Track 1) because it's a module-owned test-database setup issue (matches the shape of SA59.2's backups PostgreSQL seam fix), not tenant-context machinery — no ContextVar/`org_scope`/RLS-policy involvement.
  *Files:* `quickscale_modules/notifications/tests/settings.py` and/or the notifications test suite's database-creation/teardown fixtures — likely a test-database naming or ownership collision on rerun, similar in shape to what SA59.2 fixed for backups.
  *Acceptance:* the notifications suite passes cleanly on a rerun (not just a fresh run) under the restricted role; the corresponding `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 3 — Core/CLI plumbing

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work lives in [CHANGELOG.md](../../CHANGELOG.md).

One open item remains below (SA76), and the just-completed SA75 entry is kept alongside it for immediate merge-closeout traceability. Both are core-level test/CI-tooling changes, unrelated to tenant-context work, and parallel-safe against everything on Track 1 and each other (no file overlap: SA75 touches `quickscale_core/tests/test_manifest_entry_point.py`, SA76 touches `scripts/test_integration.sh`).

#### Finding — `session-adapter-fixture-swallows-improperlyconfigured` (`why →` [tech-audit.md TA56](../others/tech-audit.md))

- [x] **SA75 — Narrow `_session_managed_adapters`'s exception catch so a genuinely broken managed adapter fails the unit gate instead of skipping.** `Tier 1 · Track 3 · deps: none` *(closed 2026-07-12)*
  `quickscale_core/tests/test_manifest_entry_point.py`'s `_session_managed_adapters` fixture (added in `fc3dc00c`, "SA73: fix quality gate failures") catches `ImproperlyConfigured` broadly and converts it to session-wide skips. `refresh_managed_adapters` only raises that exception when a module's manifest is present but its adapter is unimportable/malformed (AF7's fail-hard condition) — a truly absent module is silently deregistered without raising. In the monorepo/CI environment all module packages are always installed, so the fixture's defended case ("unit-only runs where packages aren't installed") doesn't exist in any gated environment; the catch currently converts real breakage into a green-with-skips gate.
  *Files:* `quickscale_core/tests/test_manifest_entry_point.py` (`_session_managed_adapters` — catch narrowly: re-raise unless the missing import target is the managed package root itself, whether reported directly or via the immediate cause; in CI, additionally assert the full adapter registry is populated).
  *Acceptance:* breaking a managed adapter's import (e.g. a syntax error in `quickscale_modules_billing.adapter`) fails the unit gate instead of producing skips; the genuine "package not installed" case (if it's ever exercised) still skips cleanly.
  **Closeout (2026-07-12):** `_session_managed_adapters` now swallows only a genuine missing managed-package root import, re-raises broken adapter import failures, and asserts the full manifest-adapter registry in CI. Added regression coverage for the nongated skip path, fail-hard broken-import path, and the CI registry guard. **Findings/blockers discovered:** none beyond the roadmap finding itself. Closes SA75.
    **Follow-up (CR-SA75-REV-001, 2026-07-12):** `_refresh_session_managed_adapters()` now processes each managed module independently with deterministic sorted iteration, so one tolerated missing package does not prevent later managed adapters from being refreshed and a shipped-but-broken module cannot be masked. Two regression tests cover the coexistence scenario. Closes CR-SA75-REV-001.
    **Follow-up (CR-SA75-REV-002, 2026-07-12):** Fixed a correctness gap in the root-package-missing detection: the handler checked only `exc.__cause__` for `ModuleNotFoundError`, but a genuinely missing managed package root raises `ModuleNotFoundError` directly (with no `__cause__`), so the tolerated case was never recognised. The check now examines both the exception itself and its cause. Updated the regression test that implicitly relied on the bug. Closes CR-SA75-REV-002.
  *(why →* [tech-audit.md TA56](../others/tech-audit.md)*)*

#### Finding — `integration-gate-red-at-merge` (`why →` [tech-audit.md TA57](../others/tech-audit.md))

- [ ] **SA76 — Quarantine SA59.1's known restricted-role integration failures so the gate goes green.** `Tier 1 · Track 3 · deps: none`
  The integration gate merged red on `v87` (SA59.1's known failures: orgs 3 `test_models.py` + 6 helper-path errors, forms `0007` composite-FK, notifications duplicate-db; 77.55% mean coverage vs. the 90% threshold) — while red, `ci.yml`/`publish.yml`'s integration jobs catch no *new* module-suite regressions, and every day it stays red trains merging-over-red. **Decided 2026-07-12 (Option B):** this is now SA59.1's actual closeout path, not a stopgap alongside a fuller fix — SA59.1 closes once this lands, and the quarantined failures are removed one at a time as SA60 (forms), SA77 (orgs), and SA78 (notifications) land independently. **Moved from Track 1 (2026-07-12):** the diff is a CI script edit (xfail markers), no tenant-context code — fits Track 3's "core/CLI plumbing" charter, same shape as SA75; frees Track 1 to focus purely on tenant-context work (SA70/SA74/SA77) while this proceeds in parallel.
  *Files:* `scripts/test_integration.sh` (add an xfail-with-ticket marker or an explicit per-suite allowlist for the enumerated known failures, so everything else stays gated).
  *Acceptance:* the integration gate is green for every suite except the named, ticketed failures; a new module-suite regression outside the quarantine list still fails the gate; each quarantine entry is removed independently as its owning ticket (SA60/SA77/SA78) lands — not held for a single simultaneous closeout.
  *(why →* [tech-audit.md TA57](../others/tech-audit.md)*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
