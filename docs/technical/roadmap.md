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
> - **Track 1** — mixed. SA59.4 remains **BLOCKED** on unresolved SA59.1 failures (orgs, forms migration 0007, notifications) — SA59.1 is still open (parked at a prior user-directed stop). Everything else on Track 1 is **unblocked and ready to start**: SA60 and SA70's pending decisions were both ratified 2026-07-12 (NOT DEFERRABLE composite-FK policy; raise-not-return-early refusal mechanism — see `decisions.md §Multi-tenant SaaS Architecture`), and two new items were added from tech-audit.md's 2026-07-11 pass that had never been roadmapped: SA74 (TA54, **S1 production defect** — org creation fails under the restricted runtime role when CRM is installed; fix this first, it's independent of the SA59.1 blockers) and SA76 (TA57 — quarantine the known integration-gate failures so the gate goes green while SA59.1 proceeds).
> - **Track 2** — clean. No open items remain after SA73's closeout.
> - **Track 3** — one open item, newly assigned: SA75 (TA56 — narrow a test fixture's overly-broad exception catch). Unblocked, parallel-safe, unrelated to the SA67 beta-site closeout (which itself remains closed; the outstanding manual check is tracked in `beta-site-migration.md`, not here).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA59 — drop bypassrls auto-prime       — clean / no open items —                 SA75 — narrow adapter-fixture
  (umbrella, split → SA59.1–SA59.4)                                                exception catch (TA56)
SA60 — composite-FK deferability
  policy + conformance gate
SA70 — orgs pre_delete receiver
  backstop (Finding 2 first step)
SA74 — prime CRM org-creation
  seeding context (TA54, S1)
SA76 — quarantine known
  integration-gate failures (TA57)
```

Track 2 is clean; Track 3 now carries one small, independent item (SA75). Track 1 carries the bulk of open work; within it, SA59.1, SA59.4, SA60, SA70, SA74, and SA76 touch disjoint files (SA59.1: `Makefile` + `scripts/test_unit.sh` + `ci.yml` + `publish.yml`; SA59.4: `docs/technical/decisions.md` + role reference docs; SA60: `orgs/tenancy.py` + forms migrations; SA70: `orgs/signals.py` + a new receiver test; SA74: `crm/services.py` + `orgs/tests/conftest.py`; SA76: `scripts/test_integration.sh`) and share only `decisions.md` (additive sections, not a real conflict — see the shared-closeout-files note below). SA59.2 and SA59.3 are complete (see CHANGELOG.md); SA59.4 depends on SA59.1, SA59.2, and SA59.3 (the latter two already satisfied). SA76's file overlaps SA59.1's territory in spirit (both touch the integration gate's failure set) but not in practice — coordinate manually if both are in flight. SA75 (Track 3) is fully independent of every Track 1 item. The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` remain the one universal merge-conflict exception across tracks.

### Track 1 — Tenant-context surface

Open items below. SA59 (umbrella) remains blocked/open via SA59.1–SA59.4; SA60 and SA70 remain active Track 1 work, both unblocked since their pending decisions were ratified 2026-07-12. SA74 and SA76 are new items added this pass from tech-audit.md's 2026-07-11 findings.

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 (umbrella) — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path — blocked (split into SA59.1–SA59.4).** `Tier 2 → split · Track 1 · deps: none`
  `Makefile:321-327` (`test-unit`) and `scripts/test_unit.sh:365-366` both blanket-export `QUICKSCALE_ALLOW_BYPASSRLS=1` for every module suite, which (a) disables the SA58 boot guard (now landed — checks both `rolbypassrls` and `rolsuper`) entirely during CI and local `make test-unit` runs and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests always running — contradicting the SA14.4 decision still documented at `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. No environment currently demonstrates the boot guard firing against a bypassing role.
  **Decision (2026-07-10, reaffirmed):** split release/CI validation into a DB-free unit gate plus a separate PostgreSQL integration gate, rather than threading a NOBYPASSRLS role through the existing combined `scripts/test_unit.sh` run (the alternative considered and rejected). The currently-combined script splits along its existing DB-need boundary: a fast path with no DB dependency, and an integration path that runs the DB-touching module suites against a NOBYPASSRLS role. The direct-connection role used by the integration path must be `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — the target role contract for the integration gate (the CI worktree's current `quickscale_test_role` omits `NOINHERIT`, tracked by F-SA59-ROLE-006) — so test suites can establish database connections under the restricted profile. The `CREATE ROLE ... NOBYPASSRLS NOINHERIT NOLOGIN` pattern from `scripts/test_isolation_conformance.sh:50` is a separate pattern for the isolation-conformance inner role (which exercises RLS isolation without needing a login-capable role); it does not apply to the direct-connection integration role. Both `ci.yml`'s `test` job and `publish.yml`'s `test` job gate on the integration path — `ci.yml:238-249`'s `test` job today also connects as the plain `postgres` superuser with no NOBYPASSRLS role (same gap tech-audit didn't separately flag but is in scope here), so it isn't just `publish.yml` that needs the new role. The SA59 aggregate was raised from Tier 1 to Tier 2 for the added script-split and two-workflow scope; the individual sub-slices are sized Tier 1–2.
  **Split (2026-07-11):** Per roadmap policy — a checklist item sized Tier 3 (7-item blocker ledger) must be split before implementation. Four sub-slices defined below, each Tier 1–2. The umbrella remains blocked until all four are complete.

  **Merged blocked-checkpoint state — SA59.1 merged to v87 (2026-07-11):** SA59.1 implementation artifacts have been merged to v87 as a blocked checkpoint per user direction. Open review findings and pre-existing integration failures remain unresolved (see still-open blockers under SA59.1 below). SA59.2–SA59.4 were not part of this merge and remained blocked at that point (SA59.2 has since been unblocked). Detail on the CI role setup, test-script split, and coverage wiring is in [CHANGELOG.md](../../CHANGELOG.md). *(Integration gate findings: the NOBYPASSRLS path exposed pre-existing RLS test failures — 15 in billing, 45 in social — plus 77.55% mean module coverage across the 12 integration suites. These are discovered blockers requiring separately scoped follow-up, not resolved by SA59 itself.)*

  ---

  - [ ] **SA59.1 — Validation harness + coverage plumbing (merged to v87 as blocked checkpoint; review findings remain open).** `Tier 1 · Track 1 · deps: none` *(user-directed stop 2026-07-11 — merged as-is with open blockers)*
    Implementation resolves three umbrella blockers (e2e exclusion, local CI parity, module coverage persistence) plus four review passes' operational and source-file corrections — detail in [CHANGELOG.md](../../CHANGELOG.md). No production code was changed.

    **Remaining blockers (SA59.1 not complete — must be resolved before closeout):**
    - **Orgs pre-existing failures (refined).** 3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py` persist. These depend on restricted-role `CREATE ROLE` behavior (SA59.3-style territory) and are not resolved by the Phase 3 test-only adaptations.
    - **Forms migration failure (newly discovered).** `quickscale_modules/forms/migrations/0007_new_organization_ownership.py` fails composite-FK validation on a fresh restricted-role DB. Discovered during this session's integration gate walk.
    - **Notifications duplicate-db issues (newly discovered).** Reruns hit `test_test_quickscale_notifications` ownership/duplicate-db problems. Discovered during this session's integration gate walk.
    - **Validated green:** billing (216 passed, 1 explicit bypass skip) was green on clean restricted-role rerun. Social (106/108 passed, 2 remaining boundary tests) ran clean but is not fully closed.

  - [ ] **SA59.4 — Docs + final closeout — BLOCKED (unresolved SA59.1 failures).** `Tier 1 · Track 1 · deps: SA59.1, SA59.2 (complete, see CHANGELOG.md), SA59.3 (complete, see CHANGELOG.md)`
    Correct documentation to match the adopted role shape, record the gate-split decision in decisions.md, and produce the final closeout checkpoint. Inherits two documentation fixes:
    - **F-SA59-DOC-002 / F-SA59-CMD-010** — Direct-connection role uses `LOGIN`, not `NOLOGIN`; correct matching docs and command matrix. Role descriptions in `Makefile` (help text) and scripts (`test_unit.sh`, `test_integration.sh`) still use `NOLOGIN`, but the CI `quickscale_test_role` requires `LOGIN` to establish test-database connections (CHANGELOG.md no longer carries the stale NOLOGIN wording). All documentation and the command matrix must reflect `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` consistently.
    - **Advisory: agent-handback provenance discrepancy (user accepted).** The previous implementation handback omitted `decisions.md` and `scripts/test_integration.sh` from its changed-files listing. Include these files in the closeout manifest.
    *Target files (SA59.4 share):* `docs/technical/decisions.md` (record the unit/integration gate split); role-description prose in scripts, workflow docs, CHANGELOG, and the test-command reference matrix.
    *Acceptance:* the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is removed from the unit-only path; the integration path runs module suites against a NOBYPASSRLS role in both `ci.yml` and `publish.yml`; developers set the SA14.4 hatch explicitly per-suite when they need it; `make test-unit` (and the new integration target) documents the split in its help text; decisions.md records the split.

  - **Blocked-checkpoint state:** SA59.1 — merged to v87 as blocked checkpoint (2026-07-11); resolved review findings (CR-SA59 series) are documented in [CHANGELOG.md](../../CHANGELOG.md). **Still unresolved:** pre-existing integration failures — orgs (3 test_models.py + 6 helper-path errors), forms (0007 migration composite-FK on restricted-role DB), notifications (duplicate-db/ownership). Billing was green on clean rerun; social (106/108 passed) ran clean but remains unreviewed and incomplete (2 remaining boundary tests). User chose to stop at the scope boundary rather than authorize expansion to fix newly-discovered pre-existing failures. SA59.1 remains open. SA59.2 and SA59.3 are complete (2026-07-11, see [CHANGELOG.md](../../CHANGELOG.md)). SA59.4 still waits on SA59.1 resolving.
  - **Stop-state (2026-07-12):** SA59.4 is the next ordered Track 1 task but remains blocked on the unresolved SA59.1 failures above. SA60's and SA70's pending decisions were ratified 2026-07-12 (see their entries below); both are now unblocked and available to work in parallel with SA59.1's resolution. SA74 (S1) and SA76 are also unblocked and available.
  - **Continuation note (2026-07-11):** Billing's canonical restricted-role suite is green (216 passed, 1 explicit bypass skip). Social test context work is unreviewed and incomplete (106/108 passed in the last restricted-role run); two social restricted-role boundary tests still need the direct-role adaptation pattern. The true cross-organization UPDATE test awaits an explicit decision between a single bypass-RLS mark, a production RLS-write expansion, or accepting a delete/create approximation.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `composite-fk-deferability-contract-diverged` (`why →` [tech-audit.md TA50](../others/tech-audit.md), [arch-audit.md Finding 4](../others/arch-audit.md) caution + Questions)

- [ ] **SA60 — Pick and enforce one composite-FK deferability policy.** `Tier 2 · Track 1 · deps: none`
  `6ea37301` silently flipped the Option C composite-FK helper (`orgs/tenancy.py:903`, `_ADD_COMPOSITE_FK_SQL`) from `DEFERRABLE INITIALLY DEFERRED` to `NOT DEFERRABLE`, with no decisions.md record and no test asserting the new behavior. This diverges from `forms/0007`'s own inlined `DEFERRABLE INITIALLY DEFERRED` SQL (and its `test_migrations.py:457-505` assertion) and from every *existing* database (fresh installs get `NOT DEFERRABLE`, existing ones keep `DEFERRABLE` — fleet drift with no aligning migration). Empirically verified this pass (PostgreSQL 18): `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so `NOT DEFERRABLE` is defensible on fail-fast grounds — but it needs to be the *documented*, uniformly-applied policy, not a one-module drift. Bundle in the second, cheaper doc gap arch-audit flagged in the same commit: `is_tenant_model()`'s `tenant_excluded`-marker-beats-manager/base-class precedence change (`tenancy.py:1548+`) also has no decision record.
  *Files:* `docs/technical/decisions.md` (two new entries: composite-FK deferability policy under the Option C child-table section; `tenant_excluded` precedence rule); `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:903` (helper SQL, if the decision changes it back) and `:1548+` (precedence — doc-only, no code change expected); `quickscale_modules/forms/src/quickscale_modules_forms/migrations/0007*.py` (align to the chosen policy); `quickscale_modules/forms/tests/test_migrations.py:457-505` and `quickscale_modules/crm/tests/test_migrations.py:1107,1158` (update assertions/stale comments to match); extend the SA35-style cross-module conformance gate to assert one deferability policy for all Option C composite FKs.
  *Acceptance:* decisions.md states the deferability policy (recommend keeping `NOT DEFERRABLE` given the empirical fail-fast verification, but ratify explicitly) and the `tenant_excluded` precedence rule; `forms/0007` and the `tenancy.py` helper emit the same deferability clause; a new conformance test fails if any Option C composite FK diverges; the two now-stale test comments (`crm/tests/test_migrations.py:1107,1158`) are corrected to reflect the no-op-on-NOT-DEFERRABLE behavior.
  **Decision ratified (2026-07-12):** NOT DEFERRABLE is the uniform policy for all Option C composite FKs — recorded in `decisions.md §Multi-tenant SaaS Architecture`. SA60 is unblocked; implementation (align `forms/0007` + its test assertions, correct the stale `crm` test comments, add the conformance test) can proceed.
  *(why →* [tech-audit.md TA50](../others/tech-audit.md)*,* [arch-audit.md Finding 4](../others/arch-audit.md)*)*

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

#### Finding — `integration-gate-red-at-merge` (`why →` [tech-audit.md TA57](../others/tech-audit.md))

- [ ] **SA76 — Quarantine SA59.1's known restricted-role integration failures so the gate goes green.** `Tier 1 · Track 1 · deps: soft dep on SA59.1's blocker list (same failures); independent of SA74`
  The integration gate merged red on `v87` (SA59.1's known failures: orgs 3 `test_models.py` + 6 helper-path errors, forms `0007` composite-FK, notifications duplicate-db; 77.55% mean coverage vs. the 90% threshold) — while red, `ci.yml`/`publish.yml`'s integration jobs catch no *new* module-suite regressions, and every day it stays red trains merging-over-red.
  *Files:* `scripts/test_integration.sh` (add an xfail-with-ticket marker or an explicit per-suite allowlist for the enumerated known failures, so everything else stays gated).
  *Acceptance:* the integration gate is green for every suite except the named, ticketed failures; a new module-suite regression outside the quarantine list still fails the gate; the quarantine is removed at SA59.4 closeout once the underlying failures are fixed.
  *(why →* [tech-audit.md TA57](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

**No open items.** Track 2 is clean — completed work lives in [CHANGELOG.md](../../CHANGELOG.md).

### Track 3 — Core/CLI plumbing

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work lives in [CHANGELOG.md](../../CHANGELOG.md).

One open item below, newly assigned to this track (2026-07-12) — it is core-level test-tooling, unrelated to tenant-context work, and parallel-safe against everything on Track 1.

#### Finding — `session-adapter-fixture-swallows-improperlyconfigured` (`why →` [tech-audit.md TA56](../others/tech-audit.md))

- [ ] **SA75 — Narrow `_session_managed_adapters`'s exception catch so a genuinely broken managed adapter fails the unit gate instead of skipping.** `Tier 1 · Track 3 · deps: none`
  `quickscale_core/tests/test_manifest_entry_point.py`'s `_session_managed_adapters` fixture (added in `fc3dc00c`, "SA73: fix quality gate failures") catches `ImproperlyConfigured` broadly and converts it to session-wide skips. `refresh_managed_adapters` only raises that exception when a module's manifest is present but its adapter is unimportable/malformed (AF7's fail-hard condition) — a truly absent module is silently deregistered without raising. In the monorepo/CI environment all module packages are always installed, so the fixture's defended case ("unit-only runs where packages aren't installed") doesn't exist in any gated environment; the catch currently converts real breakage into a green-with-skips gate.
  *Files:* `quickscale_core/tests/test_manifest_entry_point.py` (`_session_managed_adapters` — catch narrowly: re-raise unless `isinstance(exc.__cause__, ModuleNotFoundError)` and the missing module is the managed package itself; in CI, additionally assert the full adapter registry is populated).
  *Acceptance:* breaking a managed adapter's import (e.g. a syntax error in `quickscale_modules_billing.adapter`) fails the unit gate instead of producing skips; the genuine "package not installed" case (if it's ever exercised) still skips cleanly.
  *(why →* [tech-audit.md TA56](../others/tech-audit.md)*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
