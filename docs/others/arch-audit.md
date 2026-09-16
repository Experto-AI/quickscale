# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-09-15 · **Branch:** `v89` · **Range audited:** `48e0a62a..b9e072f4`
>
> Live structural findings only. Findings are identified by their **slug**; ordinal numbering is
> pass-local and is not a stable identifier (see
> [decisions.md → Document Responsibilities](../technical/decisions.md)). Closed findings and
> prior-pass narratives live in [CHANGELOG.md](../../CHANGELOG.md).

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**. It has a Click
CLI, a Django 6 project generator with 119 template files (39 of them `.j2`), and twelve shipped
first-party modules (`teams` is still a README-only placeholder). Modules are embedded into
generated projects by `git subtree` and upgraded in place by the public `quickscale update`
command. Generated projects run PostgreSQL 18, Vite/React, Docker, and Railway. Their public
contracts are the CLI, `quickscale.yml` and the applied state, module manifests, the generated
trees, and upgrade semantics. Persistence in generated projects is PostgreSQL with dual-layer
tenant isolation (`TenantManager` plus `FORCE RLS` under a restricted runtime role). The
repository has one maintainer (3,654 reachable commits, one author across two emails) and a
deliberate governance layer: 12 registered gates, a closed hosted-job universe, AST and
conformance gates, and monotonic quality baselines.

**Commit delta** (`48e0a62a..b9e072f4`, 759 commits). This breaks down as:

- **109 merges.**
- **472 synthetic commits.** These are subtree-split module histories imported by the v0.88
  release's eleven `git subtree split --rejoin` merges (`publish_module.py:1035`). They are not
  monorepo changes and were excluded.
- **178 real monorepo commits:**
  - **Housekeeping:** 99 touch only docs or planning; 32 touch only tests.
  - **Closeout:** 29 production-touching commits carry ticket labels (SA160, SA164, SA165,
    SA167c/d, SA170–SA173, SA176). Each maps to a closed roadmap ticket.
  - **Unlabeled-behavioral:** 18 production-touching commits carry release- or docs-shaped
    messages. All were read at full depth:
    - `b29d9a29` "v88 fix: make ci-e2e fixes" adds a **third sanctioned privileged command**
      across all four declarations, which fires a watch trigger. It also moves the BYPASSRLS lane
      into `ci.yml` as a reusable workflow and widens the parity extractors to `uses:` jobs.
    - `461796ce` "v0.88.0: QuickScale 0.88.0" adds **runtime-role provisioning** to the generated
      `start.sh` and to `quickscale deploy railway`.
    - `a85f29ff` "v0.88.0" changes the generated **`Dockerfile` CMD to `./start.sh`**.
    - `2e2a932a` "docs: …" **narrows the commit-testimony gate** to a `vNN` token only.
    - `74d18f48` "docs: …" strengthens the lockstep-pin gate from a floor check to an exact match.
    - `d73155d1` "v0.88.0" retires the second lockfile.
    - `f4cb7964` "v0.88.0" drops the nightly BYPASSRLS cron; the lane now runs on every CI run
      via `workflow_call`.
    - The rest: `b8ca6283`, `3923eb58`, `54aea5ab`, `296afa0e`, `5a6d1f4f`, `18d6084a`,
      `e0a92fdb`, `0e79113c`, `335e51dd`, and the version stamps `a960d4e9` and `b9e072f4`
      (55 files each).

**Growth direction (planning surface, authoritative).** `v88` is release-accepted, and
**v0.88.0 is packaged but not published**. Publication is recorded as owed (`roadmap.md:12-16`).
The critical path is **SA153: the first production property portal
(`buenosairesproperties.com`) built as a *project-owned extension*** on `bap-web`, after SA152
verifies the migration tooling and SA191 migrates that site onto current QuickScale.
Its acceptance requires that "every new tenant-owned child table has its own `organization_id`,
forced RLS, and boundary tests". SA177 (verify RLS policy predicates) is off the critical path. The standing decisions still stand: no `teams` work and no third
generated-project updater. SA153 is not a teams trigger, so the teams tie-breaker
(`decisions.md:151`) does not govern the promotions below.

**Scope decision.** This pass has three jobs:

1. Reconstruct the large delta, and re-verify every prior anchor and watchlist trigger.
2. Run the **change-cost probe against SA153**, the growth direction that is actually scheduled.
   That probe led to the tenancy registry, purge, and deletion boundaries.
3. Follow the v0.88 release commits into the **privilege/runtime-role seam**. They changed it
   under release-shaped messages.

**Read fully:**
- The 18 unlabeled-behavioral diffs.
- `orgs/tenancy.py` classification (`:1160-1460`) and policy refresh (`:587-640`).
- `orgs/checks.py`, `purge_organization.py`, and the head of `check_tenant_isolation.py`.
- The generated `start.sh.j2` (`:1-130`), the privilege section of `production.py.j2`, and
  `db/init.sql.j2`.
- The runtime-role section of `deployment_commands.py`, `module_commands.update`, and the
  account-delete view.
- `roadmap.md`, the SA153 ticket context, the header of `check_commit_testimony.py`, and the SA92
  guardrail.

**Sampled:**
- `beta_migration.py` (anchor re-verification only).
- The SA160 client-identity diffs.
- The structure of `test_generated_project_runtime.py`.
- The closed-universe check in `sync_ci_gate_jobs.py`.
- `module_discovery.py`.

**Skipped:** `apply_command.py` (4,122 lines), the internals of the `module_config.py` wiring
drain, frontend theme internals, and dr_engine internals beyond the lock files.

## Enforcement census

| Invariant | Enforcement | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural | unchanged |
| **Tenant-model universe is classified (and refreshed, and purged)** | Marker-derived tenant classification and FORCE-RLS refresh; 21-entry `_DELETE_SPECS` remains the purge membership list. The shipped `TENANT_TABLE_REGISTRY` is a parity oracle only | **Classification and refresh are marker-derived; purge remains closed to project-owned tenant models** | **narrowed to SA190 purge membership** — rank 1 |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` boot guard; exemption set declared in four places and checked by exact-member station regressions | Guard structural; **two-member set duplicated across four fail-closed stations and cross-checked** | **strengthened** — recovery backfill excluded and declaration drift gated |
| **Restricted runtime role exists with the right grants** | `db/init.sql.j2` (role `{package}_app`), `start.sh.j2` Step 3 (role `quickscale_runtime`, adds `GRANT CONNECT`), `OPERATIONS.md.j2` manual SQL | **Convention: three implementations, two role names** | **new row** (seam minted in `461796ce`) |
| **Template ↔ upgradable-code contract compatibility across versions** | `project_contract` in state plus declared module/CLI vintages; `status` reports gaps and existing-project `update`, `apply`, and Railway deploy enforce them | **Structural at mutation boundaries, with explicit per-invocation acknowledgement** | **strengthened** — compatibility boundary enforced |
| Every emitted path has a migration disposition | Generator-derived conformance test over a hand-authored taxonomy | Membership gated; ownership hand-authored | unchanged; paid again for two new emitted paths (`31a93768`) |
| Cross-domain deletion obligations are discharged | Last-owner: one predicate, locked model delete, `pre_delete` receiver. Billing cancellation: account-delete view; live-subscription refusal plus row purge, cache invalidation, and tombstone: `purge_organization` | Last-owner and live-subscription refusal are structural; **remaining obligations convention, split across two boundaries** | **re-characterized** — rank 2 |
| CSRF-exempt endpoints have alternate integrity checks | AST gate plus sanctioned endpoint bases | Structural and gated | unchanged |
| Core/module dependency direction and lockstep pin | Import-compatibility and reverse-import gates; exact `>=X.Y.0,<X.(Y+1).0` pin derived from `VERSION` | Gated | strengthened (floor → exact, `74d18f48`) |
| Module identity (the twelve-module universe) | `module_discovery.py --list-modules`, consumed fail-hard (`provision_ci_postgres.sh:81`, `check_sa117_scope.py:57`, `version_tool.sh:34`) | Structural and derived | unchanged (SA173 three-state presence added behind the same shim) |
| CI runtime environment and closed hosted-job set | `provision_ci_postgres.sh` (five profiles); `sync_ci_gate_jobs.py:381-387` (`UNOWNED ∪ registry-bound` == 17 jobs) | Structural and gated | unchanged; parity extractors now also count reusable-workflow `uses:` jobs |
| Behavioural-control commits carry testimony | `check_commit_testimony.py` — a `vNN` token in the message | Gated, token-shaped | **narrowed** (`2e2a932a`, labelled `docs:`, dropped the SA-ticket and CHANGELOG forms) |
| Generated emission is byte-identical to the recorded manifest | SA90 fixture hash/mode comparison, `_HOST_DEPENDENT_PATHS` exception | Gated, one exception entry | unchanged (still 1 — monotonic) |
| Complexity maxima never ratchet upward | Merge-base monotonicity gate plus waiver ledger | Gated | unchanged (baseline shrank by 24 lines) |
| Gate-suite self-tests, planning-count derivation, runtime pins, installed-wheel lifecycle E2E | `check-gate-suites`, ticket-context consistency test, `runtime_pins.py`, `smoke-install` | Gated / structural | unchanged — re-verified present |

## Summary table

| Rank | ID | Horizon | Confidence | Size | Problem in one line |
|---:|---|---|---|---|---|
| 1 | `org-model-universe-hand-enumerated` | now (SA190) | High | S | Purge membership remains a literal `_DELETE_SPECS` list inside the orgs module, closed to project-owned tenant tables even though classification and policy refresh are marker-derived. |
| 2 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months | High | M | Two org-deletion boundaries already exist, and each discharges a different subset of cross-domain obligations. |

Rank 1 is the still-open SA190 purge-membership half; classification and policy refresh are
marker-derived, while SA190 still owns purge derivation. The permanent two-command contract is
cross-checked across all four enforcing stations, whose duplication remains a watch item. Rank 2
is scheduled at the 6–18 month horizon.

---

## Finding — Purge membership remains closed to project-owned tables

**ID:** `org-model-universe-hand-enumerated` · **Horizon:** now · **Confidence:** High ·
**Size:** S · **Context dependence:** `wrong-for-now` (new domain — first project-owned tenant tables)

**Rank rationale:** the remaining blast radius is org teardown for the first production portal.
Classification and policy refresh now accept project-owned tenant models; purge remains the
unresolved SA190 half. The trigger is certain because SA153 is the next ticket on the critical path.

**Trigger:** a project-owned or module tenant model is scheduled. **Fired** — SA153's
acceptance requires new tenant-owned child tables with their own `organization_id` and forced RLS
(`roadmap.md`, SA153).

**Problem:** The organization purge plan still treats the set of tenant models as a literal list
inside the orgs module's source and has no project-side extension seam. The documented extension
model forbids editing module source, and SA153 is required to ship exactly the kind of table this
list cannot see.

**Evidence** (all anchors established or re-verified this pass):

- **Classification and policy refresh are now marker-derived.** `is_tenant_model()` and
  `get_tenant_models()` identify installed concrete project models, while
  `is_classified_in_registry()` uses the marker-only classifier. W003/W004 and
  `check_tenant_isolation` therefore cover project-owned models without a literal registry entry.
  `refresh_force_rls_policies()` binds each existing table to its unique live `FOR ALL` policy
  from `pg_policies` before performing the revert/apply cycle. The shipped literal remains only a
  parity oracle.
- **SA153's model is a tenant model by construction.** `AbstractListing` carries `tenant_org_fk()`
  and `objects = TenantManager()` (`listings/models.py:12,22,124-125`), so any property subclass
  with the dual-manager contract is one. The Phase A project fixture proves classification,
  command output, live policy refresh, and missing-policy fail-closed behavior without a literal
  registry entry.
- **Purge is closed and order-dependent.**
  - `_DELETE_SPECS` (`purge_organization.py:64`, **21 entries**, re-derived by AST) is the whole
    purge universe (`_resolve_models`, `:215`).
  - The organization row is removed with `_raw_delete` (`:448`), and `tenant_org_fk` is `PROTECT`
    (`tenancy.py:450-476`).
  - Purging any org that owns a project-owned tenant row therefore fails on the database FK.
- **The remaining fix belongs to SA190.** `implementation_contract.md:355` requires projects to
  extend modules "through a project-owned extension app … never by editing module source
  directly." Adding project-owned purge membership to `_DELETE_SPECS` would violate that
  boundary and would have to survive every later `quickscale update` subtree pull.

**Counter-evidence:**

- **The project-side marker hook now exists.** The module extension and organizations contracts
  document the dual-manager/marker path; the shipped parity literal remains separate.
- **Isolation stays guarded without the literal.** W003/W004 and `check_tenant_isolation` require
  `organization_id` and FORCE RLS for every marker-derived `TenantManager` model.
- **Purge fails loud.** No silent partial teardown is possible.

Those last two points are what keep this a registration/extension problem rather than an
isolation leak.

Runtime confirmation: generate a project with `listings`, add an extension model subclassing
`AbstractListing`, and run `manage.py check_tenant_isolation --format json`. Classification and
policy refresh should include the model; purging an organization that owns its row still fails
until SA190 derives purge membership.

**Why it compounds:**

- Every project-owned tenant table still needs a purge-membership seam, currently a hand-chosen
  `_DELETE_SPECS` position in module source.
- That edit must be carried through every later module update.
- Purge ordering remains manual, while classification and policy refresh now see the table.
- SA154's inventory (saved searches, favorites, agent/office profiles, tours) is a list of more
  tenant tables built on the same pattern.

**Detection signal:** a generated project's `purge_organization` raising `IntegrityError` or
`ProtectedError` while a project-owned tenant row exists. Hand edits appearing under
`quickscale_modules_orgs/` in a generated project's git history remain evidence of the wrong
extension shape, not a requirement for classification or policy refresh.

**Steelman:** a closed purge list is default-deny. Nothing is deleted unless a maintainer reviewed
its ordering, and `_DELETE_SPECS` protects against accidental cross-domain deletion. Do not fix if
SA153 is re-scoped to ship its tables inside a first-party module.

**Correct shape:** purge membership is derived from the same marker-derived tenant-model set used
by classification and policy refresh, with explicit ordering from installed FK metadata and
documented overrides where needed. Any literal list is a monorepo-side cross-check over shipped
modules, never the runtime authority in a generated project.

**Options:**

1. **Open `_DELETE_SPECS`.** Merge a project-declared list (a setting or AppConfig hook) into the
   purge plan. This is small and keeps default-deny, but adds another hand-maintained station per
   table and leaves purge ordering manual.
2. **Derive purge membership from markers.** Drive purge membership from `get_tenant_models()` and
   order it topologically from installed FK metadata with explicit overrides. Keep the shipped
   literal only as a monorepo parity test. This removes the remaining compounding.
3. **Keep purge closed and require first-party modules for tenant tables.** This contradicts
   SA153's scope and the extension contract.

**Recommendation:** Option 2. SA182 has aligned classification and policy refresh with the
marker-derived set. SA190 should now derive purge membership from `get_tenant_models()`, preserving
the existing ordered deletion and last-owner safeguards while proving a non-module tenant row can
be purged safely.

---

## Finding — Organization deletion obligations are split across two boundaries

**ID:** `deletion-invariants-per-boundary-reimplementation` · **Horizon:** 6–18 months ·
**Confidence:** High · **Size:** M · **Context dependence:** `wrong-for-now` (production tenants /
compliance)

**Rank rationale:** the blast radius is billing and data retention for real organizations, which
SA153 is the first to create. Likelihood is moderate: both boundaries exist today, but the
production volume does not yet.

**Trigger:** another account/organization deletion boundary. **Fired:** `purge_organization` is
the second boundary, and SA153's production launch makes the split obligations operationally
relevant.

**Problem:** Last-owner safety is structural, but the other cross-domain obligations of removing
an organization — cancelling billing, deleting tenant rows, invalidating caches, writing a
tombstone — are orchestrated inline by whichever boundary happens to run. The two existing
boundaries discharge disjoint subsets.

**Evidence (census of org-lifecycle deletion boundaries):**

| Obligation | Account-delete view (`AccountDeleteView`, `auth/views.py:56-240`) | `purge_organization` |
|---|---|---|
| Last-owner guard | ✅ `:164` via the one predicate | n/a (whole org) |
| Cancel Stripe subscription | ✅ `_cancel_personal_org_subscriptions`, `:172-240` | Refuses current Stripe-backed subscriptions before deletion; cancellation remains out of band |
| Delete tenant rows | ❌ personal org and its rows survive (membership `CASCADE`, `orgs/models.py:116-120`) | ✅ `_delete_owned_rows`, `:514` |
| Invalidate social caches | ❌ | ✅ `_clear_social_cache`, `:538` |
| Tombstone | ❌ | ✅ `:452` |

`cancel_current_subscription` has exactly two callers: `billing/views.py:311` and
`auth/views.py:225`. The six last-owner callsites were re-verified (`orgs/models.py:165,329`;
`signals.py:66`; `orgs/views.py:808,1161`; `auth/views.py:164`).

**Counter-evidence:**

- **No billing delete hooks.** Searched billing for `pre_delete`/`post_delete` receivers or
  model-level `delete()` hooks; found none.
- **The live-subscription precondition is now enforced and documented.** The purge and dry-run
  paths list current Stripe subscription IDs and refuse before deletion. This closes the money-path
  red flag without unifying the remaining cross-domain obligations.
- **Last-owner safety is sound**, so this finding is scoped to cross-domain obligations.

**Why it compounds:**

- **Each new domain obligation** (SA153's property galleries in media storage, CRM inquiries,
  SA154's saved searches and alerts) must be added to whichever boundaries its author remembers.
- **Each new boundary** — bulk admin, GDPR erasure, or `teams` — copies a subset.
- **The subsets have already diverged.**

**Detection signal:** a new organization-deletion boundary that omits the live-subscription
refusal, memberless personal organizations still holding tenant rows, or stale `social` cache
entries after account deletion.

**Steelman:** the two boundaries have different intents. Account deletion removes a *person* and
deliberately retains organization data. Purge is an operator's hard teardown. Network calls
inside Django signals would be worse than explicit orchestration, and a coordinator built before
a real tenant exists is premature.

**Correct shape:** the obligations for removing an organization — and those for removing a person
from one — are declared once, each by the domain that owns it. Every boundary discharges the same
set, idempotently.

**Options:**

1. **An explicit organization-removal coordinator** with idempotent domain contributors (billing
   cancel, row purge, cache invalidation, tombstone). Both the account view and purge call it.
2. **Domain-local safeguards:** billing refuses deletion of a row with a live Stripe id; an outbox
   record reconciles. Stronger against bypass, but network effects complicate transactions.
3. **Deletion as a durable job.** Strongest recovery; excessive before multi-store erasure exists.

**Recommendation:** Option 1. Design it together with rank 1's purge derivation, so that purge
membership and obligations come from one place. Preserve the last-owner model/signal backstop.
· **First step:** fold the shipped live-subscription refusal and the remaining purge obligations
into a named list shared with the account view; the purge-plan work owns that consolidation.

---

## Change-cost probe

**Probe — SA153: add one project-owned tenant child table** (for example, a property gallery
image). SA182 now covers the classification and policy-refresh stations. The remaining SA190
purge-membership probe is:

1. The project model: `tenant_org_fk()` plus `TenantManager()` and `TenantManager(super_scope=True)`.
2. A project migration calling `apply_force_rls()`, plus `add_composite_child_fk()` for the parent
   equality.
3. A child boundary test on the `test_rls_boundary.py` pattern.
4. **Module source:** a `_DELETE_SPECS` entry at a hand-chosen FK position. Without it, purging any
   org that owns the row fails on `PROTECT`.
5. Carry the purge-membership change through every later `quickscale update` of `orgs`.

**Verdict: finding evidence** (rank 1): 5 stations remain in the SA190 half. The project model,
migration, child-boundary, classification, and refresh behaviours now have an extension path and
Phase A regression coverage; purge membership remains in vendored module source.

---

## Fix order and interactions

- **SA182's rank-1 classification/refresh half is complete:** it unblocks SA153's first migration
  and keeps the shipped literal as parity-only evidence.
- **Purge derivation pairs with rank 2:** the remaining rank-1/SA190 purge half and rank 2's
  coordinator touch the same command, so design them together.
- **SA177 is independent of both findings,** but its "each enrolled table" scope inherits rank 1's
  closed universe. If rank 1 lands first, SA177 covers project tables for free.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed.** Ambient `TenantManager` scoping plus
  restricted-role `FORCE RLS`. A boot guard rejects a `rolbypassrls`/`rolsuper` runtime role, and
  `_check_quickscale_mode()` runs before the privileged exemption. Marker-derived membership and
  the W003/W004 isolation checks are what make SA182's runtime shape safe; keep them while SA190
  derives purge membership.
- **Last-owner safety is a model/signal backstop, not a view check.** One predicate serves six
  callsites, plus a `pre_delete` receiver that catches direct ORM deletes. Rank 2's coordinator
  must not replace it.
- **Single-declaration derivation seams work where they are used.** Module identity is shelled out
  to `module_discovery.py --list-modules` by every consumer. `runtime_pins.py` renders Python,
  Django, and PostgreSQL pins into templates. The lockstep pin is now derived exactly from
  `VERSION` (`74d18f48`). These are the precedent for ranks 1–2.
- **The PostgreSQL CI environment is one contract with five profiles.** `provision_ci_postgres.sh`
  derives its module list and hard-fails on drift, and parity tests assert that the old
  hand-rolled shell is absent. `b29d9a29` also stopped the BYPASSRLS authorization leaking into
  `GITHUB_ENV` (`provision_ci_postgres.sh:439-444`), which strengthens it.
- **Contract-bearing generated files now have an enforced compatibility boundary.** Existing-project
  update, apply, and Railway deploy compare the recorded project contract with declared module or
  command vintages before mutation, while fresh generation remains unaffected.

## Watchlist

- **Privileged-command set has four independent enforcing stations.** The permanent sanctioned set
  is the ``migrate``/``createcachetable`` pair, each station has an exact-member regression, and a
  cross-station test rejects divergence. *Doesn't qualify:* the two-member duplication is flat-cost
  defence in depth and every miss fails closed. **Trigger:** a third sanctioned command, a second
  launcher declaration shape, or any declaration/test mismatch. **Not fired.**
- **Two independent filesystem-lock implementations** (`advisory_lock.py`, 514 lines;
  `dr_engine/_lock.py`, 298 lines). *Doesn't qualify:* both public contracts are preserved and
  the fix is release-accepted. **Trigger:** a third implementation, divergent behaviour or
  platform support, or the contracts no longer preservable independently. **Not fired**, but note
  that SA171 (`bf153e36`) had to write one atomic-reclamation correction into both.
- **Hand-pinned residue inside the provisioning derivation** (merged from two prior items).
  `provision_ci_postgres.sh:96` (`== 12`) and `:93` (`!= teams`) re-pin a count and a name;
  `:15` `POSTGRES_MAJOR=18` duplicates `runtime_pins.py:30`. *Doesn't qualify:* all of them fail
  loudly, and the two PostgreSQL values are arguably separate owners. **Trigger:** a thirteenth
  module, `teams` graduating, or the backups DR `pg_dump`/`pg_restore` contract depending on the
  two majors agreeing. **Not fired:** the universe is 12 and the DR contract is unchanged.
- **SA92 migration-squash discovery tuple** (`test_sa92_migration_squash_guardrail.py:83-100`).
  *Doesn't qualify:* it is a bounded tripwire, and `_migdir()` now fails loud. **Trigger:** another
  migration-bearing module, or the tuple omitting one. **Not fired:** the census shows 10 names and
  10 modules with migrations.
- **`trigger_inputs` is a legacy name for an exact E2E allowlist partition.** *Doesn't qualify:*
  the check is exact, and the contract is now spelled out in every diagnostic (`e0a92fdb`).
  **Trigger:** any context skipping a gate on the basis of `trigger_inputs`. **Not fired.**

## Questions that would change the ranking

No open question changes the current ranking. The privileged-command permanence question was
settled by the permanent two-command contract.

*Lenses scanned with no qualifying finding this pass: observability, API/contract stability of
the CLI surface, performance and scalability, concurrency and state isolation (beyond the lock
watch item), build/release and supply chain (single lockfile, exact lockstep pin — both sound),
and the library archetype lens. Trust and authorization, data/state model, design conflicts,
governance, and the code-generator archetype lens produced the ranked findings above.*

Closed findings, retired watch items, historical option records, and cross-reference migrations are
archived in [CHANGELOG.md](../../CHANGELOG.md) and version control rather than repeated here.
