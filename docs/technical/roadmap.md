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
> - **Track 1** — SA74 and SA70 completed (2026-07-12). SA59.4 is now **unblocked** — SA76 (the ticketed quarantine it was waiting on) has now landed on Track 3 (2026-07-12). Everything else on Track 1 is unblocked and available to start now: SA77 (orgs' restricted-role `CREATE ROLE` failures, split out of SA59.1 as an independent, non-blocking follow-up). SA74 and SA77 are new items added this pass from tech-audit.md's 2026-07-11 findings and the 2026-07-12 SA59.1 closeout-path decision (Option B — see SA59.1's entry for the full rationale).
> - **Track 2** — SA60 (composite-FK deferability policy enforced as NOT DEFERRABLE, 2026-07-12) and SA78 (notifications' restricted-role duplicate-db rerun failures, 2026-07-12) are both delivered. SA78's fix surfaced a separate pre-existing forms 0007 backfill failure (26 tests) now tracked as **SA79** below. Track 2 is available for new work once SA79 is resolved.
> - **Track 3** — two completed items this pass: SA75 (narrow adapter-fixture exception, 2026-07-12) and **SA76** (ticketed quarantine for known integration-gate failures, 2026-07-12, moved from Track 1). Both are core-level test/CI-tooling work, parallel-safe, and unrelated to the SA67 beta-site closeout (whose outstanding manual check remains tracked in `beta-site-migration.md`, not here).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA59 — drop bypassrls auto-prime       SA60 — composite-FK deferability          SA75 — narrow adapter-fixture
  (umbrella, split → SA59.1–SA59.4)      policy + conformance gate (done)          exception catch (TA56, done)
SA70 — orgs pre_delete receiver        SA78 — fix notifications                 SA76 — quarantine known
  backstop (Finding 2 first step)        duplicate-db failures (done)              integration-gate failures (TA57) — closed 2026-07-12
SA74 — prime CRM org-creation
  seeding context (TA54, S1)
SA77 — fix orgs restricted-role
  CREATE ROLE failures
```

Track 2 delivered both items (SA60, moved from Track 1; SA78, split from SA59.1) with a new open follow-up (SA79) for the forms 0007 backfill bug SA78's fix surfaced. Track 3 carried two items (SA75, SA76) and both are now complete (SA75 closed 2026-07-12, SA76 closed 2026-07-12). Track 1 still carries the bulk of open work; within it, SA59.1 (closed via SA76 — see SA59.1 entry) and its sub-items, SA70, SA74, and SA77 touch disjoint files (SA70: `orgs/signals.py` + a new receiver test; SA74: `crm/services.py` + `orgs/tests/conftest.py`; SA77: orgs test files + possibly `scripts/provision_test_roles.sh`) and share only `decisions.md` (additive sections, not a real conflict — see the shared-closeout-files note below). SA59.4 is now unblocked (SA76 has landed — SA59.4's only remaining cross-track dependency). SA76 (Track 3) and SA77 (Track 1) both touch the integration gate's failure set (one quarantines, one fixes) — no file conflict. SA76 has landed (2026-07-12), unblocking SA59.4; SA77 will later remove its specific quarantine entry. SA60/SA78/SA79 (Track 2) and SA75/SA76 (Track 3) are fully independent of every Track 1 item. The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` remain the one universal merge-conflict exception across tracks.

### Track 1 — Tenant-context surface

**SA74 and SA70 completed (2026-07-12).** Open items below. SA59 (umbrella) remains blocked/open via SA59.1–SA59.4, but SA59.4's block narrowed to just SA76 landing and is now resolved (SA76 closed 2026-07-12 — see SA59.1's entry). SA77 remains open on Track 1. SA60 moved to Track 2 and SA76 moved to Track 3 this pass — see there.

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 (umbrella) — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path — blocked (split into SA59.1–SA59.4).** `Tier 2 → split · Track 1 · deps: none`
  `Makefile:321-327` (`test-unit`) and `scripts/test_unit.sh:365-366` both blanket-export `QUICKSCALE_ALLOW_BYPASSRLS=1` for every module suite, which (a) disables the SA58 boot guard (now landed — checks both `rolbypassrls` and `rolsuper`) entirely during CI and local `make test-unit` runs and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests always running — contradicting the SA14.4 decision still documented at `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. No environment currently demonstrates the boot guard firing against a bypassing role.
  **Decision (2026-07-10, reaffirmed):** split release/CI validation into a DB-free unit gate plus a separate PostgreSQL integration gate, rather than threading a NOBYPASSRLS role through the existing combined `scripts/test_unit.sh` run (the alternative considered and rejected). The currently-combined script splits along its existing DB-need boundary: a fast path with no DB dependency, and an integration path that runs the DB-touching module suites against a NOBYPASSRLS role. The direct-connection role used by the integration path must be `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — the target role contract for the integration gate (the CI worktree's current `quickscale_test_role` omits `NOINHERIT`, tracked by F-SA59-ROLE-006) — so test suites can establish database connections under the restricted profile. The `CREATE ROLE ... NOBYPASSRLS NOINHERIT NOLOGIN` pattern from `scripts/test_isolation_conformance.sh:50` is a separate pattern for the isolation-conformance inner role (which exercises RLS isolation without needing a login-capable role); it does not apply to the direct-connection integration role. Both `ci.yml`'s `test` job and `publish.yml`'s `test` job gate on the integration path — `ci.yml:238-249`'s `test` job today also connects as the plain `postgres` superuser with no NOBYPASSRLS role (same gap tech-audit didn't separately flag but is in scope here), so it isn't just `publish.yml` that needs the new role. The SA59 aggregate was raised from Tier 1 to Tier 2 for the added script-split and two-workflow scope; the individual sub-slices are sized Tier 1–2.
  **Split (2026-07-11):** Per roadmap policy — a checklist item sized Tier 3 (7-item blocker ledger) must be split before implementation. Four sub-slices defined below, each Tier 1–2. The umbrella remains blocked until all four are complete.

  **Merged blocked-checkpoint state — SA59.1 merged to v87 (2026-07-11):** SA59.1 implementation artifacts have been merged to v87 as a blocked checkpoint per user direction. Open review findings and pre-existing integration failures remain unresolved (see still-open blockers under SA59.1 below). SA59.2–SA59.4 were not part of this merge and remained blocked at that point (SA59.2 has since been unblocked). Detail on the CI role setup, test-script split, and coverage wiring is in [CHANGELOG.md](../../CHANGELOG.md). *(Integration gate findings: the NOBYPASSRLS path exposed pre-existing RLS test failures — 15 in billing, 45 in social — plus 77.55% mean module coverage across the 12 integration suites. These are discovered blockers requiring separately scoped follow-up, not resolved by SA59 itself.)*

  ---

  - [x] **SA59.1 — Validation harness + coverage plumbing (merged to v87 as blocked checkpoint; closed via SA76's quarantine — 2026-07-12).** `Tier 1 · Track 1 · deps: SA76 (closed)` *(closeout path decided 2026-07-12 — see below)*
    Implementation resolves three umbrella blockers (e2e exclusion, local CI parity, module coverage persistence) plus four review passes' operational and source-file corrections — detail in [CHANGELOG.md](../../CHANGELOG.md). No production code was changed.

    **Closeout path (decided 2026-07-12):** SA59.1's own deliverable — the unit/integration gate split — is mechanically complete; turning the integration gate on for the first time surfaced three pre-existing, unrelated module bugs it was never scoped to fix. Rather than holding SA59.1/SA59.4 open indefinitely on unbounded root-causing (the pattern that produced two prior stop points), SA59.1 closes once **SA76** (Track 3) lands (quarantines the known failures so the gate is green for everything else). The three discovered failures are spun out as independently tracked, non-blocking follow-ups:
    - **Orgs pre-existing failures.** 3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py`, tied to restricted-role `CREATE ROLE` behavior. Tracked as **SA77** (Track 1, below).
    - **Forms migration contract + backfill.** `quickscale_modules/forms/migrations/0007_new_organization_ownership.py` had two distinct issues: the composite-FK contract (`DEFERRABLE` → `NOT DEFERRABLE`, resolved by **SA60** on Track 2) and a data backfill bug where seeded FormField rows lack correct `organization_id` before `VALIDATE CONSTRAINT`. The backfill bug remains and is tracked as **SA79** (Track 2, below).
    - **Notifications duplicate-db issues.** Reruns hit `test_test_quickscale_notifications` ownership/duplicate-db problems. **Resolved by SA78** (Track 2, below).
    - **Validated green:** billing (216 passed, 1 explicit bypass skip) was green on clean restricted-role rerun. Social (106/108 passed, 2 remaining boundary tests) ran clean but is not fully closed.

  - [ ] **SA59.4 — Docs + final closeout — unblocked (SA76 has landed — 2026-07-12).** `Tier 1 · Track 1 · deps: SA59.1 (closed via SA76), SA76 (closed), SA59.2 (complete), SA59.3 (complete)`
    Correct documentation to match the adopted role shape, record the gate-split decision in decisions.md, and produce the final closeout checkpoint. Inherits two documentation fixes:
    - **F-SA59-DOC-002 / F-SA59-CMD-010** — Direct-connection role uses `LOGIN`, not `NOLOGIN`; correct matching docs and command matrix. Role descriptions in `Makefile` (help text) and scripts (`test_unit.sh`, `test_integration.sh`) still use `NOLOGIN`, but the CI `quickscale_test_role` requires `LOGIN` to establish test-database connections (CHANGELOG.md no longer carries the stale NOLOGIN wording). All documentation and the command matrix must reflect `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` consistently.
    - **Advisory: agent-handback provenance discrepancy (user accepted).** The previous implementation handback omitted `decisions.md` and `scripts/test_integration.sh` from its changed-files listing. Include these files in the closeout manifest.
    *Target files (SA59.4 share):* `docs/technical/decisions.md` (record the unit/integration gate split); role-description prose in scripts, workflow docs, CHANGELOG, and the test-command reference matrix.
    *Acceptance:* the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is removed from the unit-only path; the integration path runs module suites against a NOBYPASSRLS role in both `ci.yml` and `publish.yml`; developers set the SA14.4 hatch explicitly per-suite when they need it; `make test-unit` (and the new integration target) documents the split in its help text; decisions.md records the split.

  - **Blocked-checkpoint state:** SA59.1 — merged to v87 as blocked checkpoint (2026-07-11); resolved review findings (CR-SA59 series) are documented in [CHANGELOG.md](../../CHANGELOG.md). Billing was green on clean rerun; social (106/108 passed) ran clean but remains unreviewed and incomplete (2 remaining boundary tests). SA59.2 and SA59.3 are complete (2026-07-11, see [CHANGELOG.md](../../CHANGELOG.md)). **SA76 has now landed (2026-07-12), closing SA59.1 and unblocking SA59.4.** SA77 remains open; SA78 has since been delivered (see Track 2 entry) and its quarantine entry will be removed when SA78 lands on v87. SA77/SA78 will remove their quarantine entries independently as they land.
  - **Stop-state (2026-07-12), superseded by the closeout-path decision above:** SA59.4 was blocked on all three discovered failures being fixed. That's now narrowed to just SA76 landing — SA60 (Track 2) independently fixes the forms piece, and SA77/SA78 carry the orgs/notifications pieces as non-blocking follow-ups. SA70, SA74, SA77 are all unblocked and available on Track 1; SA60/SA78 on Track 2; **SA76 closed on Track 3 (2026-07-12).**
  - **Continuation note (2026-07-11):** Billing's canonical restricted-role suite is green (216 passed, 1 explicit bypass skip). Social test context work is unreviewed and incomplete (106/108 passed in the last restricted-role run); two social restricted-role boundary tests still need the direct-role adaptation pattern. The true cross-organization UPDATE test awaits an explicit decision between a single bypass-RLS mark, a production RLS-write expansion, or accepting a delete/create approximation.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `deletion-invariants-per-boundary-reimplementation`, first step (`why →` [arch-audit.md Finding 2](../others/arch-audit.md))

- [x] **SA70 — Add an orgs `pre_delete` receiver backstop for the last-owner invariant (2026-07-12).** `Tier 1 · Track 1 · deps: none`
  Implemented by adding ``_protect_last_owner_on_membership_delete`` to ``signals.py`` — a ``pre_delete`` receiver on ``OrganizationMembership`` that calls the existing ``is_last_owner_with_members()`` canonical check. Wired in ``QuickscaleOrgsConfig.ready()`` via ``pre_delete.connect()``, matching the connection pattern used by ``connection_created``. The receiver raises ``ValidationError`` with ``LAST_OWNER_REMOVAL_MESSAGE`` on cascade-driven deletions that would strand other members ownerless. New regression test (``test_user_delete_of_last_owner_in_multi_member_org_is_refused``) proves ``user.delete()`` is refused for a sole owner in a multi-member org. The deliberate sole-member self-removal behavior is unaffected (the receiver returns early when ``is_last_owner_with_members`` returns False). The four existing callsites are unaffected — this is a backstop, not a replacement.
  **Findings/blockers discovered:** none beyond the roadmap finding itself. The receiver does not acquire ``select_for_update`` (unlike the model ``delete()`` override), so under concurrent cascade paths a stale check could produce a fail-closed false positive — this is acceptable for a backstop; the model ``delete()`` override's locking handles the normal-path safety. Closes SA70.
  *(why →* [arch-audit.md Finding 2](../others/arch-audit.md)*)*

#### Finding — `org-creation-crm-seeding-fails-under-force-rls` (`why →` [tech-audit.md TA54](../others/tech-audit.md))

- [x] **SA74 — Prime tenant context for CRM's org-creation stage seeding; remove the orgs test-suite signal muting.** `Tier 1 · Track 1 · deps: none`
  **S1, production-path defect.** `crm/services.ensure_org_default_stages` (`quickscale_modules/crm/src/quickscale_modules_crm/services.py:39-85`) INSERTs `Stage` rows for a newly created organization, but the table is under FORCE RLS with a `WITH CHECK` clause requiring `app.current_org_id` to match. Neither dispatch site (`orgs/managers.py:207`, `orgs/forms.py:117`) nor the `organization_created` receiver (`crm/signals.py:16`) primes the new org's context before the write, so under the mandated NOBYPASSRLS production runtime role every org-creation path (signup, `/orgs/new/`, lazy personal-org creation) 500s. Currently invisible to CI because `orgs/tests/conftest.py:50-72`'s autouse fixture patches `organization_created.send` out globally (added in the SA59.1 checkpoint as a test-only workaround, not a blessed production behavior).
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/services.py` (wrap `_seed_default_stages`'s writes in `org_scope(organization)` or an equivalent `_tenant_context` call — CRM owns the seam since it owns the receiver; dispatch-site priming is the documented alternative if the project prefers "dispatcher guarantees context" as the receiver contract); `orgs/tests/conftest.py:50-72` (remove or invert the autouse `organization_created.send` muting once the fix lands, restoring the org-creation seam to real test coverage).
  *Acceptance:* `create_personal_for` with the ContextVar unset, run under the restricted role, seeds all 4 default stages without an RLS violation; the orgs test suite runs without muting `organization_created.send`; a new CRM regression test proves the seeding path under a restricted role with no ambient org context.
  **Closed (2026-07-12):** `ensure_org_default_stages` primes tenant ContextVar across the helper scope — so RLS policies see `app.current_org_id` for all reads and writes — and wraps `_seed_default_stages`'s INSERTs in `org_scope(organization)` for an explicit GUC guard on the write path. The CRM receiver is self-sufficient; callers no longer need to prime tenant context. The orgs conftest's autouse `_mock_org_created_signal` fixture is removed; replaced by a non-autouse opt-in `mock_org_created_signal` for tests that need to suppress the signal. New regression test (`test_seeds_without_ambient_org_context`) proves seeding succeeds with `reset_current_org_id()` (no ambient context). CRM focused restricted-role tests passed 14/14; orgs `test_crm_bootstrap.py` is blocked before execution by the pre-existing SA60 forms/0007 composite-FK migration failure under `quickscale_test_role` — recorded as a discovered validation blocker, not resolved by SA74 itself.

  **Follow-up (2026-07-12) — CR-SA74-001 resolved:** `ensure_org_default_stages` now restores the DB-side GUC (`app.current_org_id`) and clears the AF9 per-transaction priming memo on exit inside an active outer transaction. Without this fix, calling the function inside a surrounding `transaction.atomic()` would leave the transaction-scoped `SET LOCAL` from the AF9 execute wrapper in place after the function returned, so subsequent no-context queries in the same transaction inherited the seeded org UUID instead of seeing NULL (fail-closed). New regression test (`test_ensure_org_default_stages_restores_db_guc_in_outer_transaction`) proves the GUC is cleared on exit. Archived in [CHANGELOG.md](../../CHANGELOG.md).
  *(why →* [tech-audit.md TA54](../others/tech-audit.md)*,* [tech-audit.md TA55](../others/tech-audit.md)*)*

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, orgs restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA77 — Root-cause and fix orgs' restricted-role `CREATE ROLE`-dependent test failures.** `Tier 1 · Track 1 · deps: none`
  3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py` persist under the NOBYPASSRLS integration role. These depend on restricted-role `CREATE ROLE` behavior (SA59.3-style territory) and were not resolved by SA59.1's Phase 3 test-only adaptations or by SA59.3's create-then-use → assert-then-use conversion. Root cause not yet established — investigate whether these tests still attempt a `CREATE ROLE` call SA59.3 didn't cover, or exercise a role capability the shared `quickscale_test_role`/`quickscale_rls_test_role` contract doesn't grant.
  *Files:* `quickscale_modules/orgs/tests/test_tenant_table_conformance.py`, `quickscale_modules/orgs/tests/test_operator_access.py`, `quickscale_modules/orgs/tests/test_models.py` — plus `scripts/provision_test_roles.sh` if the fix is a role-contract gap rather than a test-helper gap.
  *Acceptance:* all 9 failing tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the corresponding `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

SA60 (composite-FK deferability policy enforced as NOT DEFERRABLE, 2026-07-12) and SA78 (notifications restricted-role duplicate-db rerun failures, 2026-07-12) are both delivered. SA78's fix surfaced a separate pre-existing forms 0007 backfill failure now tracked as **SA79** below. For completed-item detail, see below and [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `composite-fk-deferability-contract-diverged` (`why →` [tech-audit.md TA50](../others/tech-audit.md), [arch-audit.md Finding 4](../others/arch-audit.md) caution + Questions)

- [x] **SA60 — Enforce uniform NOT DEFERRABLE policy for all Option C composite FKs (2026-07-12).** `Tier 2 · Track 2 · deps: none`
  Implementation delta: aligned `forms/migrations/0007_new_organization_ownership.py`'s inlined SQL from `DEFERRABLE INITIALLY DEFERRED` to `NOT DEFERRABLE` (matching the shared helper in `orgs/tenancy.py:_ADD_COMPOSITE_FK_SQL`, which already emitted `NOT DEFERRABLE`); renamed and inverted the forms migration test (`test_0007_composite_fks_are_not_deferrable`) to assert `condeferrable=False`; corrected two stale CRM migration test comments to reflect the no-op-on-NOT-DEFERRABLE behavior; added a cross-module conformance gate (`orgs/tests/test_sa60_composite_fk_conformance.py`) that checks all six known composite FKs for `condeferrable=False`. The `tenant_excluded` precedence rule was already a doc-only ratification in `decisions.md` — no code change was needed. Closes SA60. **Also resolves the contract side of one of SA59.1's three remaining blockers** (forms `0007` composite-FK deferability); the separate data backfill bug in the same migration is tracked as SA79 — see the SA59.1 blocker note on Track 1.
  *(why →* [tech-audit.md TA50](../others/tech-audit.md)*,* [arch-audit.md Finding 4](../others/arch-audit.md)*)*

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, notifications restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [x] **SA78 — Fix notifications' duplicate-db/ownership failures on restricted-role reruns (2026-07-12).** `Tier 1 · Track 2 · deps: none`
  Root cause: Django's test runner tries to `DROP DATABASE` then `CREATE DATABASE` for `test_test_quickscale_notifications` on every run. A leftover test database owned by `postgres` (confirmed locally) cannot be dropped by `quickscale_test_role` — `must be owner of database` — and then cannot be created either — `DuplicateDatabase`. Two-part fix: (1) Added an explicit `TEST.NAME` in `settings.py` (`qs_notifications_test`) so a dedicated test database name is used, avoiding the orphaned `test_test_quickscale_notifications` entirely; (2) enabled pytest-django's `reuse_db` (`keepdb` equivalent) in `conftest.py` so the test database persists between runs and no DROP/CREATE is attempted on rerun. On the first run the new test database is created as `quickscale_test_role` (which has `CREATEDB`); on subsequent runs `reuse_db` skips the drop/recreate cycle entirely. **Also resolves one of SA59.1's three remaining blockers** (notifications duplicate-db/ownership failure) — see SA59.1's closeout-path decision on Track 1.
  *Files:* `quickscale_modules/notifications/tests/settings.py` (added `TEST.NAME` dict), `quickscale_modules/notifications/tests/conftest.py` (added `config.option.reuse_db = True` in `pytest_configure`).
  *Acceptance:* the duplicate-db/ownership rerun failure is resolved under the restricted role (verified on two consecutive runs: the duplicate-db failure is gone on both). The suite still encounters 26 pre-existing forms migration FK errors on each run — these are a separate issue documented in Findings/blockers below, not caused by nor addressable by the SA78 fix.
  **Findings/blockers discovered:**
  - **Pre-existing forms FK migration failure (26 tests) → SA79.** The forms module migration `0007_new_organization_ownership` contains a `VALIDATE CONSTRAINT` step for the composite FK `forms_formfield_form_org_fk` that fails on every test-database creation, even on a fresh database under the default (non-bypass) role. This is a pre-existing bug in the forms migration's backfill logic — the seeded FormField rows (from migration `0002_seed_forms`) do not have their `organization_id` correctly populated to match the parent Form's organization, causing the VALIDATE to reject the `(form_id, organization_id)` pairs. This failure is NOT caused by nor addressable by the SA78 fix. It surfaced only because the SA78 duplicate-database fix now allows the test suite to progress past the DB lifecycle stage. All 26 errors are identical with or without the SA78 changes (verified by baseline comparison). **Tracked as SA79 — see below.**
  - **SA76 quarantine entry — active.** notifications is quarantined in the SA76 map in `scripts/test_integration.sh` (tracked as SA78). Remove the quarantine entry once SA78 is verified clean under the restricted role on the merged v87.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `forms-0007-backfill-data-mismatch` (`why →` SA78 findings, notifications test suite)

- [ ] **SA79 — Fix forms migration 0007 backfill logic so seeded FormField rows match their parent Form's organization before VALIDATE CONSTRAINT.** `Tier 1 · Track 2 · deps: none`
  Migration `0007_new_organization_ownership` adds a composite FK `forms_formfield_form_org_fk` and runs `VALIDATE CONSTRAINT` against existing rows. The seeded FormField rows (from migration `0002_seed_forms`) do not have their `organization_id` correctly populated to match the parent Form's `organization_id`, causing the VALIDATE to reject the `(form_id, organization_id)` pairs. This pre-existing bug was surfaced when SA78's duplicate-database fix allowed the notifications test suite to progress past the DB lifecycle stage, revealing 26 FK validation failures across the notifications, forms, and social suites. Root cause: the backfill step in `0007_new_organization_ownership` needs to update orphaned FormField rows to reference the correct organization before VALIDATE CONSTRAINT runs.
  *Files:* `quickscale_modules/forms/migrations/0007_new_organization_ownership.py`
  *Acceptance:* a fresh test-database creation under the restricted role runs the notifications, forms, and social suites with 0 FK validation errors attributable to the forms 0007 backfill; SA76's quarantine entry for forms (if any) can be removed.
  *(why →* SA78 Findings/blockers discovered, notifications test suite*)*

### Track 3 — Core/CLI plumbing

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work lives in [CHANGELOG.md](../../CHANGELOG.md).

Both SA75 and SA76 are now complete (SA75 closed 2026-07-12, SA76 closed 2026-07-12), kept alongside each other for immediate merge-closeout traceability. Both are core-level test/CI-tooling changes, unrelated to tenant-context work, and parallel-safe against everything on Track 1 and each other (no file overlap: SA75 touches `quickscale_core/tests/test_manifest_entry_point.py`, SA76 touches `scripts/test_integration.sh`).

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

- [x] **SA76 — Quarantine SA59.1's known restricted-role integration failures so the gate goes green (2026-07-12).** `Tier 1 · Track 3 · deps: none`
  Implementation: added a ticketed quarantine map (`declare -A QUARANTINE_TICKETS`) to `scripts/test_integration.sh` mapping each known-failing module to its owning ticket. `run_pytest_stage` accepts a 4th positional parameter for the quarantine ticket; when set, stage failures return 0 (absorbed) with a clear `⚠ quarantined` message, and coverage is excluded from the mean. Each quarantine entry's ticket is printed during the run so removal is obvious. Current entries: `orgs` (SA77, 9 restricted-role failures) and `notifications` (SA78, duplicate-db rerun failures). Forms' `0007` composite-FK was already resolved by SA60 (2026-07-12) and is not quarantined. Non-quarantined module-suite regressions still fail the gate. Coverage threshold (90% mean) applies to non-quarantined modules only.
  *Files:* `scripts/test_integration.sh` (quarantine map + modified `run_pytest_stage` + annotated module loop + banner output).
  **Findings/blockers discovered:** none. Closes SA76.
  **Also closes SA59.1** (per the 2026-07-12 closeout-path decision) and **unblocks SA59.4**.
  *(why →* [tech-audit.md TA57](../others/tech-audit.md)*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
