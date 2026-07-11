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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA21.2 (2026-07-07), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA41 (2026-07-07), SA42 (2026-07-07), SA43 (2026-07-07), SA44 (2026-07-07), SA45 (2026-07-06), SA46 (2026-07-07), SA47 (2026-07-07), SA48 (2026-07-07), SA49 (2026-07-07), SA50 (2026-07-07), SA51 (2026-07-07), SA52 (2026-07-07), SA53 (2026-07-08), SA54 (2026-07-08), SA55 (2026-07-07), SA56 (2026-07-08), SA57 (2026-07-10), SA58 (2026-07-10), SA61 (2026-07-10), SA62 (2026-07-10), SA63 (2026-07-10), SA64 (2026-07-10), SA66 (2026-07-10), SA69 (2026-07-10). All closed per template rule — detail lives in CHANGELOG.md.
>
> **Origin note:** SA34–SA47 trace to the 2026-07-06 triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5), each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred and remain tracked in arch-audit.md itself).
>
> **Origin note (2026-07-07, fix-plan pass):** SA48–SA56 trace to the 2026-07-07 delta-pass findings in [tech-audit.md](../others/tech-audit.md) (TA42–TA46) and [arch-audit.md](../others/arch-audit.md) (Finding 1's red flags and CR-SA44-REV-001 blocker, Finding 4's coverage-boundary sub-item, Finding 5's two remaining Option 1 pieces plus the billing migration promoted from "long tail" to scheduled work per user decision — no idiom is grandfathered as permanent legacy), each sized Tier 1–2. Every item fit Tier 1–2 without splitting; the two items large enough to flag (SA50, the `OrgApiBaseView` fold; SA56, the billing DRF migration) are Tier 2, not Tier 3.

> **Origin note (2026-07-10, fix-plan pass):** SA57–SA64 trace to the 2026-07-09/10 findings in [tech-audit.md](../others/tech-audit.md) (TA47–TA52, all opened by the unreviewed `6ea37301`/`198a1951` "fix: make check"/"fix: some make ci" commits) and [arch-audit.md](../others/arch-audit.md) (the Red flags section's DR-media/social-admin/createcachetable/TOML-splice/test-artifact items — several of which are the same defects tech-audit found independently and are merged into one task below — plus Finding 6's recommended first step and Finding 4's doc-only decision-record sub-item). Findings 1, 2 and 4's *remaining* structural work (the persistence port, the `pre_delete` backstop, the purge-order derivation) stay in arch-audit.md — each is sized M. Findings 2 and 4 are `deferred`: teams is decided **not next, not planned** (brainstormed placeholder only, no committed timeline — see [decisions.md §Teams module status](../technical/decisions.md#multitenant-saas-architecture)), so their teams-driven horizon no longer applies and there is no near-term trigger pulling them into this batch. Finding 1 Option 2 (the persistence port) is independent of teams' timeline but still M-sized and scheduled for its own next planning cycle rather than this fix-plan pass. Pulling any of the three into this batch as full structural rewrites would be Tier 3. Every item below fit Tier 1–2 without splitting; SA60 (composite-FK policy + conformance gate) and SA63 (Finding 6's launcher-contract first step) are Tier 2, the rest are Tier 1.

> **Origin note (2026-07-10, second fix-plan pass, HEAD `ae8c386e`):** SA65–SA70 trace to the V2-prompt re-run of both audits. From [tech-audit.md](../others/tech-audit.md): TA53 (`apply-subprocess-env-pythonpath-pollution`, opened this pass from the side-channel commit `628c7d28`). From [arch-audit.md](../others/arch-audit.md): Finding 7's recommended first step (`generated-file-ownership-unmodeled`, new this pass — the conformance gate, Option 1), Finding 6's recommendation to finish the migrate-path deciders (`db-privilege-mode-procedural`, narrowed `now`→`6–18 months` but still open scope), the two Red flags (SA63's unverified beta-site rollout; the undocumented `ImproperlyConfigured` re-homing), and Finding 2's recommendation to land the `pre_delete` receiver backstop as opportunistic hardening independent of teams' timeline (`deletion-invariants-per-boundary-reimplementation` — only the receiver-backstop first step, not the full M-sized finding). Finding 1 (persistence port) and Finding 4's purge-order derivation (Option 2, needs teams as a real second consumer) are excluded from this batch per the same Tier-3-avoidance rule as the prior pass — both stay open in arch-audit.md. Every item below fits Tier 1–2: SA66 (Finding 7's gate) and SA68 (Finding 6's migrate-path finish) are Tier 2; SA65, SA67, SA69, SA70 are Tier 1.

> **Track status (2026-07-11, SA65–SA70/SA59.1–SA59.4 opened; SA63/SA69 closed; SA67 blocked; SA59.1 merged as blocked checkpoint):**
> Track 1 — **6 open items** (SA59.1–SA59.4, SA60, SA70). SA59.1 implementation artifacts exist (e2e exclusion, local CI parity wiring, per-module coverage XML persistence, CI/publish coverage upload parity) but open review findings block closeout: CR-SA59-001 (coverage uploads incomplete — CI/publish upload references core/CLI XML artifacts not persisted by the `test-unit` entrypoint), CR-SA59-002 (local `make ci` overclaims GitHub Actions parity when PostgreSQL is absent — it warns explicitly but still exits success). CR-SA59-003 (NOLOGIN/LOGIN wording inconsistency) remains advisory, deferred to SA59.4. Pre-existing integration test failures (forms, notifications, orgs) also remain after local PostgreSQL bootstrap. SA59.2–SA59.4 remain open. SA59 has been split per roadmap policy (Tier 3 with 7-item blocker checklist → 4 Tier 1–2 sub-slices); the first sub-slice has been merged to v87 as a blocked checkpoint per user direction, but it is not closed. SA59.2–SA59.3 remain blocked by the unresolved role-grant path. SA59's publish.yml blocker is resolved via the 2026-07-10 unit/integration gate-split decision.
> Track 2 — **0 open items** (SA73 closed).
> Track 3 — **1 open item** (SA67 blocked). SA65 is complete. SA66 is complete — the conformance gate passes (zero unclassified gaps). CR-SA66-005 remains low/advisory. SA67 is blocked — no repo or deployment access to the external beta sites (`experto-ai-web`, `bap-web`) to perform the required verification. SA68 is complete — the migrate-path launcher env-pair contract is finished; `start.sh.j2`/`production.py.j2` use the bridge exclusively; `orgs/apps.py` no longer inspects `sys.argv`. CR-SA68-004 (rollout-guidance for Redis-absent createcachetable) remains as accepted blocking follow-up — see SA68 entry below.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA59 — drop bypassrls auto-prime       SA73 — make quality commands pass          SA67 — verify + patch SA63 on the
  (umbrella, split → SA59.1–SA59.4)                                                  beta sites (urgent, do first)
SA60 — composite-FK deferability                                                    SA65 — stop propagating the CLI's
  policy + conformance gate                                                         PYTHONPATH env to foreign
SA70 — orgs pre_delete receiver                                                     subprocesses (quick win)
  backstop (Finding 2 first step)                                                   SA66 — generated-file ownership
                                                                                     conformance gate (Finding 7)

```

All three tracks run fully in parallel — no hard cross-track implementation dependencies exist; every task below touches files no other open task touches, with two exceptions noted where they occur. Within Track 1, SA59.1–SA59.4, SA60, and SA70 touch disjoint files (SA59.1: `Makefile`+`scripts/test_unit.sh`+`ci.yml`+`publish.yml`; SA59.2: backups module settings/manifests; SA59.3: test-database role setup + grant config; SA59.4: `docs/technical/decisions.md`+role reference docs; SA60: `orgs/tenancy.py`+forms migrations; SA70: `orgs/signals.py`+a new receiver test) and share only `decisions.md` (additive sections, not a real conflict — see the shared-closeout-files note below). SA59.3 carries soft deps on SA59.1 and SA59.2; SA59.4 depends on all three prior sub-slices. Within Track 3, SA65/SA66/SA67/SA68 touch disjoint source files and share only `decisions.md`; run them in this order within the track: **SA67 first** (it's the urgent red flag — arch-audit explicitly says it "shouldn't wait for the gate"), then SA65 (independent quick win), then SA66, then SA68. **Soft cross-track dependency:** SA68 deletes `orgs/apps.py`'s `_is_migrate_command()` (a Track 1 file) and its fix is only *demonstrably* exercised in CI once SA59 has removed the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` test-harness export — arch-audit's fix-order note recommends bundling them "in the same batch, so the guard is demonstrably exercised the week the contract completes." This is a timing recommendation, not a file or merge blocker: SA68 is correct on its own regardless of merge order, but prefer landing SA59 first (or the same week) so the CI signal is real. (The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` are the one universal cross-track exception — every track touches them during closeout, managed by the merge procedure above.)

### Track 1 — Tenant-context surface

SA47, SA48, SA49, SA50, SA58 are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). SA59 (umbrella) is **blocked** — SA59.1 merged as blocked checkpoint; SA59.2–SA59.4 remain open. The approved continuation plan splits SA59 into four sub-slices (SA59.1–SA59.4) below. SA50 folded the `JsonApiMixin`/`JsonOrganizationAccessMixin` stack into one `OrgApiBaseView` as part of the `json-api-boundary-idiom-fragmentation` finding (see [arch-audit.md Finding 5](../others/arch-audit.md)). Open: SA59 umbrella (blocked, split into SA59.1–SA59.4), SA60 (carried from the prior pass), SA70 (new this pass), below.

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 (umbrella) — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path — blocked (split into SA59.1–SA59.4).** `Tier 2 → split · Track 1 · deps: none`
  `Makefile:321-327` (`test-unit`) and `scripts/test_unit.sh:365-366` both blanket-export `QUICKSCALE_ALLOW_BYPASSRLS=1` for every module suite, which (a) disables the SA58 boot guard (now landed — checks both `rolbypassrls` and `rolsuper`) entirely during CI and local `make test-unit` runs and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests always running — contradicting the SA14.4 decision still documented at `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. No environment currently demonstrates the boot guard firing against a bypassing role.
  **Decision (2026-07-10, reaffirmed):** split release/CI validation into a DB-free unit gate plus a separate PostgreSQL integration gate, rather than threading a NOBYPASSRLS role through the existing combined `scripts/test_unit.sh` run (the alternative considered and rejected). The currently-combined script splits along its existing DB-need boundary: a fast path with no DB dependency, and an integration path that runs the DB-touching module suites against a NOBYPASSRLS role. The direct-connection role used by the integration path must be `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — the target role contract for the integration gate (the CI worktree's current `quickscale_test_role` omits `NOINHERIT`, tracked by F-SA59-ROLE-006) — so test suites can establish database connections under the restricted profile. The `CREATE ROLE ... NOBYPASSRLS NOINHERIT NOLOGIN` pattern from `scripts/test_isolation_conformance.sh:50` is a separate pattern for the isolation-conformance inner role (which exercises RLS isolation without needing a login-capable role); it does not apply to the direct-connection integration role. Both `ci.yml`'s `test` job and `publish.yml`'s `test` job gate on the integration path — `ci.yml:238-249`'s `test` job today also connects as the plain `postgres` superuser with no NOBYPASSRLS role (same gap tech-audit didn't separately flag but is in scope here), so it isn't just `publish.yml` that needs the new role. The SA59 aggregate was raised from Tier 1 to Tier 2 for the added script-split and two-workflow scope; the individual sub-slices are sized Tier 1–2.
  **Split (2026-07-11):** Per roadmap policy — a checklist item sized Tier 3 (7-item blocker ledger) must be split before implementation. Four sub-slices defined below, each Tier 1–2. The umbrella remains blocked until all four are complete.

  - [x] **Investigation and planning (completed 2026-07-10):** The initial blanket-removal draft was rolled back before landing; the unit/integration gate-split decision above was adopted as the path forward. Confirmed that `publish.yml` invokes `scripts/test_unit.sh` without a PostgreSQL service or a NOBYPASSRLS/NOSUPERUSER role; removing the blanket export would fail the publish workflow. Implementation artifacts were retained for SA59.1.

  **Merged blocked-checkpoint state — SA59.1 merged to v87 (2026-07-11):** SA59.1 implementation artifacts have been merged to v87 as a blocked checkpoint per user direction. Open review findings and pre-existing integration failures remain unresolved (see still-open blockers under SA59.1 below). SA59.2–SA59.4 are not part of this merge and remain blocked.

  - CI `quickscale_test_role` (LOGIN CREATEDB NOBYPASSRLS NOSUPERUSER) added to ci.yml's `test` job, wired through every module's QS_*_DB_USER env var, with database ownership + public schema grants on 11 module test databases. `QUICKSCALE_ALLOW_BYPASSRLS=0` prevents the hatch from being overridden. *(Publish.yml role setup and decisions.md gate-split record are deferred to SA59.3 and SA59.4 respectively.)*
  - Blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` removed from Makefile `test-unit` target and `scripts/test_unit.sh`. Module test suites stripped from `test-unit` (now DB-free core + CLI only). `scripts/test_integration.sh` created. `make test-integration` target added. `make test` updated to run both unit and integration. ci.yml `test` job split into separate unit/integration steps. Gate-split decision record still pending — deferred to SA59.4.
    *(Validation findings from integration gate: the integration gate runs under NOBYPASSRLS and exposes pre-existing RLS test failures — 15 in billing (quickscale_modules/billing) and 45 in social (quickscale_modules/social) — plus 77.55% mean module coverage across the 12 integration suites. These are discovered blockers requiring separately scoped follow-up; they are not resolved by SA59 itself.)*

  ---

  - [ ] **SA59.1 — Validation harness + coverage plumbing (merged to v87 as blocked checkpoint; review findings remain open).** `Tier 1 · Track 1 · deps: none` *(user-directed stop 2026-07-11 — merged as-is with open blockers)*
    Implementation artifacts exist covering three blockers from the umbrella ledger:
    - **F-SA59-E2E-008** — Integration runner must exclude e2e tests from normal CI. `scripts/test_integration.sh` now passes `-m "not e2e"` to pytest for every module suite, preventing Playwright-based end-to-end tests from running in the CI integration gate.
    - **F-SA59-PARITY-009** — `make ci` / local validation parity. `scripts/check_ci_locally.sh` now runs `./scripts/test_integration.sh` after unit tests when PostgreSQL is available (checked via `pg_isready`). When PostgreSQL is not available, the script prints an explicit warning that integration tests were skipped and full CI parity requires PostgreSQL. CR-SA59-002 remains open — local `make ci` overclaims parity because it still exits success when PostgreSQL is absent, so CI-equivalent integration steps are silently missed despite the explicit warning (see still-open blockers below).
    - **F-SA59-COV-004** — Module coverage artifacts not persisted; upload parity incomplete. `scripts/test_integration.sh` now persists per-module coverage XML to `quickscale_modules/<name>/coverage.xml` via a new `persist_module_coverage_xml()` function. `ci.yml`'s upload step includes `./quickscale_modules/*/coverage.xml`. `publish.yml`'s `test` job now includes an equivalent coverage upload step.
    *Target files touched:* `scripts/test_integration.sh` (e2e exclusion + module coverage persistence); `scripts/check_ci_locally.sh` (prerequisite-aware integration gate); `.github/workflows/ci.yml` (module coverage upload glob); `.github/workflows/publish.yml` (new coverage upload step); `docs/technical/roadmap.md` (status update); `CHANGELOG.md` (entry).

    **Still-open blockers (SA59.1 not complete — must be resolved before closeout):**
    - **CR-SA59-001 — Coverage uploads incomplete.** CI/publish.yml upload steps reference core/CLI coverage XML artifacts (`coverage.xml`), but the current `test-unit` entrypoint does not persist those artifacts. Upload paths exist but source data is not reliably produced.
    - **CR-SA59-002 — Local CI parity overclaim.** `make ci` (`scripts/check_ci_locally.sh`) warns explicitly when PostgreSQL is absent but still exits success, so CI-equivalent integration steps are silently missed despite the warning.
    - **Pre-existing integration failures.** After local PostgreSQL bootstrap, pre-existing integration test failures exist in forms, notifications, and orgs modules. These are not regressions from SA59.1 work but block clean integration gate signal and must be resolved for a valid SA59 closeout.

  - [ ] **SA59.2 — Backups PostgreSQL seam.** `Tier 1 · Track 1 · deps: none`
    Provide a proper PostgreSQL/RLS seam for the backups module so its integration suite exercises tenant-boundary safety under a restricted role. Inherits one blocker:
    - **F-SA59-DB-007** — Backups integration tests use SQLite and lack a `QS_BACKUPS_DB_*` PostgreSQL/RLS seam. Manifests/settings fall back to SQLite; no integration run exercises backups against a real PostgreSQL restricted role. Backups must connect as a restricted PostgreSQL role with RLS active before the integration gate validates tenant-boundary safety.

  - [ ] **SA59.3 — Retained-role contract conversion.** `Tier 2 · Track 1 · deps: SA59.1, SA59.2`
    Complete the administrator-side role grants, remove runtime DDL from test helpers, and execute the full restricted-role PostgreSQL 18 module gate end-to-end with coverage evidence. Inherits two blockers and the unmerged CI role work:
    - **F-SA59-ROLE-006** — Administrator-side least-privilege schema/table grants required; Forms and Listings test helpers create/grant inner RLS role via runtime DDL. This runtime role DDL must be removed — the inner role must be pre-provisioned by the database administrator using explicit least-privilege schema/table grants plus `has_schema_privilege`/`has_table_privilege` assertions in each test-database setup path. The outer test connection role must retain `NOCREATEROLE` so the runtime DDL path is structurally impossible. Additionally, every test-database role creation path must assert `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` explicitly. The CI worktree `quickscale_test_role` currently uses `LOGIN CREATEDB NOBYPASSRLS NOSUPERUSER` but does not explicitly assert `NOINHERIT`.
    - **F-SA59-VALID-003** — Execute full restricted-role PostgreSQL 18 module gate end-to-end with coverage evidence. The restricted-role integration pipeline has not been successfully executed through its full path. The ci.yml integration step provides partial signal, but the publish.yml restricted-role workflow remains unverified. A successful end-to-end run must produce per-module coverage artifacts and confirm the restricted role fired correctly across all suites.
    *Note — unmerged worktree role artifacts* (`quickscale_test_role` CI wiring, publish.yml role setup, decisions.md gate-split record) form the starting point for this sub-slice but need the F-SA59-ROLE-006 administrative grant path resolved before they are safe to merge. User selected stop rather than authorize the required administrator-side grant path for F-SA59-ROLE-006.

  - [ ] **SA59.4 — Docs + final closeout.** `Tier 1 · Track 1 · deps: SA59.1, SA59.2, SA59.3`
    Correct documentation to match the adopted role shape, record the gate-split decision in decisions.md, and produce the final closeout checkpoint. Inherits two documentation fixes:
    - **F-SA59-DOC-002 / F-SA59-CMD-010** — Direct-connection role uses `LOGIN`, not `NOLOGIN`; correct matching docs and command matrix. Role descriptions in `Makefile` (help text) and scripts (`test_unit.sh`, `test_integration.sh`) still use `NOLOGIN`, but the CI `quickscale_test_role` requires `LOGIN` to establish test-database connections (CHANGELOG.md no longer carries the stale NOLOGIN wording). All documentation and the command matrix must reflect `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` consistently.
    - **Advisory: agent-handback provenance discrepancy (user accepted).** The previous implementation handback omitted `decisions.md` and `scripts/test_integration.sh` from its changed-files listing. Include these files in the closeout manifest.
    *Target files (SA59.4 share):* `docs/technical/decisions.md` (record the unit/integration gate split); role-description prose in scripts, workflow docs, CHANGELOG, and the test-command reference matrix.
    *Acceptance:* the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is removed from the unit-only path; the integration path runs module suites against a NOBYPASSRLS role in both `ci.yml` and `publish.yml`; developers set the SA14.4 hatch explicitly per-suite when they need it; `make test-unit` (and the new integration target) documents the split in its help text; decisions.md records the split.

  - **Blocked-checkpoint state:** SA59.1 — merged to v87 as blocked checkpoint (2026-07-11) with open review findings and pre-existing integration failures unresolved. SA59.2–SA59.4 remain blocked without the unresolved role-grant path for F-SA59-ROLE-006 (SA59.3). Open review findings on SA59.1 (CR-SA59-001, CR-SA59-002) and pre-existing integration failures (forms, notifications, orgs) must be resolved before SA59.1 closeout. CR-SA59-003 (NOLOGIN/LOGIN wording inconsistency) remains advisory, deferred to SA59.4.
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

SA21.2, SA37, SA38, SA40, SA43, SA51, SA52, SA53, SA54, SA57, SA64, SA69, SA73, plus its earlier share of the SA19–SA33 batch, are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). The `backups-dispatch-fail-open-robustness` finding (SA52/SA53, `why →` [tech-audit.md TA47](../others/tech-audit.md)), the `social-admin-perorgadminmixin-prototype` finding (SA64, `why →` [arch-audit.md Red flags](../others/arch-audit.md)), the `ImproperlyConfigured` re-homing decision-record gap (SA69, `why →` [arch-audit.md Red flags](../others/arch-audit.md)), and the `make-quality-commands-failing` finding (SA73, below) are fully closed.

#### Finding — `make-quality-commands-failing`

- [x] **SA73 — Fix `make lint`, `make typecheck`, `make format`, and `make test-unit` to all pass.** `Tier 1 · Track 2 · deps: none`
  `make lint` and `make format` pass cleanly. `make typecheck` fails with 4 errors: 3× `import-not-found` for `quickscale_modules_backups.models` (`quickscale_core/dr_engine` modules import the backups module package, which mypy cannot resolve because module packages are not on the mypy path) and 1× `unused-ignore` at `orchestration.py:646` (suppressed because the unresolvable import makes the target `Any`). `make test-unit` fails at collection time: `test_manifest_entry_point.py:52` calls `refresh_managed_adapters()` at module level, which iterates all known managed adapters and raises `ImproperlyConfigured` when any module package is not importable (observed: `quickscale_modules_crm`, `quickscale_modules_billing` depending on iteration order). Root cause: the quickscale_core mypy path and test environment are not configured to resolve cross-module references to installed module packages, and the `refresh_managed_adapters()` call at import time assumes every managed module is installed.
  *Target files:* `mypy.ini` (add `ignore_missing_imports = True` to `[mypy-quickscale_modules_backups.*]` — it exists but lacks this flag while other section patterns have it — or add an explicit `paths` entry); `quickscale_core/src/quickscale_core/dr_engine/orchestration.py:646` (update the `# type: ignore[attr-defined]` with a clarifying comment — previously unused it is now a needed ignore on a Django reverse relation once imports resolve, retained not removed); `quickscale_core/tests/test_manifest_entry_point.py:52` (move `refresh_managed_adapters()` from module level into a session-scoped fixture that catches `ImproperlyConfigured` for unimportable modules); `Makefile` (add `MYPYPATH` construction for module mypy runs so each module's `src` and its siblings are resolvable).
  *Acceptance:* `make lint && make typecheck && make format && make test-unit` all exit 0.

### Track 3 — Core/CLI plumbing

SA44 (Finding 1 stage 1, `dr-engine-module-circular-lattice`), SA56 (Finding 5, `json-api-boundary-idiom-fragmentation`, now fully closed), SA61 (test artifacts untracked, gitignore patterns added, blog test media pointed at tmp_path), SA62 (module pyproject TOML splice routed through the validated writer), SA63 (createcachetable/boot-guard collision fix, launcher-owned env contract first step), SA65, and SA66 (conformance gate — passes with zero unclassified gaps; CR-SA66-005 advisory recorded below) are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). Open this pass: SA67 (blocked), SA68 (complete with accepted follow-up — see CR-SA68-004 below).

#### Finding — SA63 beta-site rollout unverified (`why →` [arch-audit.md Red flags](../others/arch-audit.md))

- [ ] **SA67 — Verify SA63 reached `experto-ai-web` and `bap-web`; patch by hand if not.** `Tier 1 · Track 3 · deps: none — do this first, urgent`
  SA63 changed two generator templates (`start.sh.j2`, `production.py.j2`). Arch-audit's Finding 7 independently discovered that the maintainer's beta-site upgrade tooling (`quickscale_devtools/beta_migration.py`) **misses both of these files by construction**: `IN_PLACE_INFRASTRUCTURE_TARGETS` (`beta_migration.py:96–108`) does not include `start.sh`, so the in-place migration path never delivers the createcachetable env-pair fix; and `FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES` (`:43–48`) copies the **donor's** `settings/production.py` onto the fresh scaffold, so the fresh-first path keeps the beta site's old production settings and misses SA63's env-pair bridge (`production.py.j2:172–184`). Each of SA63's two changed files is missed by exactly one of the two migration paths — meaning at least one of the two production deployments is silently running without the fix it needs, most likely for its no-Redis boot path. This is flagged as a red flag "out of scope — fix now," independent of Finding 7's structural fix (SA66, below), and should not wait for it.
  *Files:* none in this repo except a note in `docs/planning/beta-site-migration.md` recording that this manual check was performed and its outcome; the actual patch happens in the `experto-ai-web` and `bap-web` repos (external to this monorepo).
  *Acceptance:* diff each beta site's deployed `start.sh` and `settings/production.py` against this repo's current templates; where either site is missing SA63's changes, patch by hand and redeploy; record the check (and whether Redis is present on either site, which determines how urgent the `start.sh` gap actually is — see arch-audit's open Question on this) in `beta-site-migration.md` or a CHANGELOG entry.
  **Blocker (2026-07-11):** Deferred — no files, Redis state, deployment, patch, or redeploy were inspected or performed in `experto-ai-web` or `bap-web`. Both beta sites are external to this monorepo with no available repository or deployment access. Unblocking requires repository/deployment access (or equivalent current-file, Redis, and deploy evidence) for both sites.
  *(why →* [arch-audit.md Red flags](../others/arch-audit.md)*)*

#### Finding — `apply-subprocess-env-pythonpath-pollution` (`why →` [tech-audit.md TA53](../others/tech-audit.md))

- [x] **SA65 — Stop propagating the CLI's dev-context `PYTHONPATH` to foreign subprocesses.** `Tier 1 · Track 3 · deps: none`
  `apply_command.py`'s module-level `_QUICKSCALE_SUBPROCESS_ENV` (built once at import time by `_build_quickscale_env()`, `apply_command.py:212–254`) was passed unconditionally by `_run_command` and `_start_docker_impl` to **every** apply subprocess — not just the two nested `sys.executable -m quickscale_cli.main` invocations it existed for. The dev-context `PYTHONPATH` is now built on-demand via `_build_quickscale_env()` and passed only to the two nested CLI invocations (`_run_migrations_in_docker_impl`, `_start_docker_impl`). The module-level `_QUICKSCALE_SUBPROCESS_ENV` cache is removed; `_run_command` now defaults to `env=None` (inherit parent env). The docstring is corrected to describe the narrow scoping. Regression tests prove that foreign subprocess calls (`_run_command` default) receive no injected `PYTHONPATH` while nested CLI calls do.
  *Files:* `quickscale_cli/src/quickscale_cli/commands/apply_command.py` (`_build_quickscale_env`, `_run_command`, `_run_migrations_in_docker_impl`, `_start_docker_impl`); `quickscale_cli/tests/test_apply_command_extended.py` (new `TestSA65SubprocessEnvScoping`).
  *Acceptance:* foreign subprocesses (`_run_command` default) receive `env=None` (inherit parent env); controlled dev-path delivery is asserted for every nested CLI call via `TestSA65SubprocessEnvScoping`; QG lint/tests passed (1944 passed, 28 deselected); four known pre-existing `module_config.py:38` MyPy errors remain out of scope.
  *Findings:* CR-SA65-001 (test-gap — injected dev PYTHONPATH not proven by regression tests), CR-SA65-002 (premature closure wording — completion status predates independent review). Both resolved in review pass 2. Closes SA65.
  *(why →* [tech-audit.md TA53](../others/tech-audit.md)*)*

#### Finding — `generated-file-ownership-unmodeled`, first step (`why →` [arch-audit.md Finding 7](../others/arch-audit.md))

- [x] **SA66 — Add a conformance gate deriving the beta-migration file taxonomy from the template tree.** `Tier 2 · Track 3 · deps: none`
  *Revise (2026-07-10 pass 2):* The initial gate was rejected by change review with four blocking findings (CR-SA66-001..004). This pass resolves all four and delivers a passing gate.
  *Corrections applied:*
  - CR-SA66-001 (identity substitution): `start.sh` is now in `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS` so the in-place copy path replaces donor package/slug references with the recipient's. Regression test added using different donor/recipient package names.
  - CR-SA66-002 (inventory completeness): the conformance test now also enumerates non-Jinja theme files copied as-is by the generator (`src/lib/utils.ts`, `src/lib/analytics.ts`, `src/posthog-js.d.ts`). The inventory correctly models generator behavior across both themes and optional/conditional file gating.
  - CR-SA66-003 (per-path disposition): the classification system now tracks per-taxonomy-tuple dispositions via `_build_classified_map()` (returns `dict[str, list[str]]` instead of flat `set[str]`). Directory-level matching is supported. `INTENTIONALLY_UNMANAGED` is populated with all user-owned generated files across 15 documented categories. The conflict gate prevents the same path from appearing in both managed and unmanaged tuples.
  - CR-SA66-004 (truthful documentation): roadmap/changelog status updated to reflect SA66 is open (not closed). `decisions.md` expanded with full category rationales.
  *Acceptance:* the conformance gate passes — every known emitted file is classified by at least one taxonomy tuple. Failed to 84 gaps before; zero gaps now. The gate stays wired into the `quickscale_cli/tests/` suite.
  *Advisory — CR-SA66-005 (low):* prose lists both common and mode-specific required specs as classification sources, but the conformance test iterates only mode-specific specs; the rationale test does not inspect decisions.md. Manual parity verified on both dimensions — no gate gap, but a follow-up could automate the prose-inventory cross-check.
  *(why →* [arch-audit.md Finding 7](../others/arch-audit.md)*)*

#### Finding — `db-privilege-mode-procedural`, remainder (`why →` [arch-audit.md Finding 6](../others/arch-audit.md))

- [x] **SA68 — Finish the launcher env-pair contract for the `migrate` path; delete the last argv deciders.** `Tier 2 · Track 3 · deps: soft — pair with SA59 for CI verification (see Dependency overview above)` — **Complete.**
  SA63 landed the launcher-owned `RUNTIME_DATABASE_URL`/`QUICKSCALE_ALLOW_BYPASSRLS` env-pair contract for `createcachetable` and deleted `local.py.j2`'s argv ladder, and arch-audit's Probe B confirmed a *new* privileged command now costs exactly one station under that contract. The `migrate` path, however, still had three independent deciders left over from before the contract existed: `start.sh.j2:49` unsets `RUNTIME_DATABASE_URL` for migrate but does **not** set `QUICKSCALE_ALLOW_BYPASSRLS=1`; `production.py.j2:185` has a separate `elif "migrate" in sys.argv` branch (membership, any position) that selects the superuser URL without going through the env-pair bridge at `:172`; and `orgs/apps.py`'s `_is_migrate_command()` (`:32–51`, positional `sys.argv[1] == "migrate"`) is the boot guard's independent migrate exemption (`apps.py:155`). Three deciders, three slightly different idioms, for the same "is this a migrate invocation" question. Additionally, the same `QUICKSCALE_ALLOW_BYPASSRLS` bit is overloaded across per-command production sanction (SA63's bridge), per-environment dev opt-out, and blanket test-harness convenience (SA59's target) — arch-audit suggests considering a second, distinct flag for launcher sanction if that's still muddy after this task.
  **Final design:** The explicit two-signal one-shot command contract uses `QUICKSCALE_PRIVILEGED_COMMAND` and `QUICKSCALE_NON_DB_COMMAND` env vars — not the old single-flag/argv wording. All three argv deciders are deleted; `start.sh.j2` and `production.py.j2` route every privileged command through the env-pair bridge; `orgs/apps.py` no longer inspects `sys.argv`.
  *Files modified:* `quickscale_core/src/quickscale_core/generator/templates/start.sh.j2:49`, `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/production.py.j2:185,195`, `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`, `test_generated_project_runtime.py`, `docs/technical/decisions.md`. Closeout docs (Phase 4): `docs/planning/beta-site-migration.md`, `docs/technical/roadmap.md` (this file), `CHANGELOG.md`.
  *Acceptance:* `start.sh.j2`'s migrate line carries the same env pair as its createcachetable line; `production.py.j2` has exactly one code path selecting the superuser URL (the `:172` bridge) plus the fail-closed default — no argv inspection remains; `orgs/apps.py` no longer inspects `sys.argv`; the boot smoke test suite demonstrates the guard firing and passing correctly on the migrate path; decisions.md's deploy-time-configuration paragraph is written, retiring that arch-audit watchlist item.
  *Accepted remaining blocking follow-up — CR-SA68-004 (medium, blocking):*
  `docs/planning/beta-site-migration.md` still recommends launcher-first rollout
  too broadly. For Redis-absent sites whose donor-owned settings predate the
  `createcachetable` bridge, launcher-first rollout is unsafe — the new launcher
  emits the env-pair signal for `createcachetable`, but an older
  `settings/production.py` does not recognise it. Manual transplant of the new
  `production.py` without paired launcher/doc updates is unsafe in all cases.
  The beta-site-migration rollout-order guidance must document the Redis-present
  vs Redis-absent conditions explicitly. *(Accepted remaining follow-up per
  user checkpoint decision.)*
  Non-blocking: orgs module tests require module-local pytest context for direct
  module runs; runtime smoke e2e remains explicitly marked and opt-in.
  *(why →* [arch-audit.md Finding 6](../others/arch-audit.md)*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
