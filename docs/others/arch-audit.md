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
deliberate governance layer: 13 registered gates, a closed hosted-job universe, AST and
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
**v0.88.0 is packaged but not published**. Publication is recorded as owed (`roadmap.md:13-20`).
The critical path is **SA153: the first production property portal
(`buenosairesproperties.com`) built as a *project-owned extension*** on `bap-web`, after the
verified migration tooling is used by SA191 to move that site onto current QuickScale.
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
- `orgs/tenancy.py` classification (`:1357-1740`) and policy refresh (`:713`).
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
| **Tenant-model universe is classified (and refreshed, and purged)** | Marker-derived tenant classification, FORCE-RLS refresh, and FK-ordered purge membership; the shipped `TENANT_TABLE_REGISTRY` is a parity oracle only | **Structural and open to installed project-owned tenant models** | **strengthened** — purge no longer hand-enumerates the model universe |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` boot guard; exemption set declared in four places and checked by exact-member station regressions | Guard structural; **two-member set duplicated across four fail-closed stations and cross-checked** | **strengthened** — recovery backfill excluded and declaration drift gated |
| **Restricted runtime role exists with the right grants** | `runtime_database.py` declares `quickscale_runtime`, its attributes, and the canonical grants; generator context renders that contract into `db/init.sql.j2`, `start.sh.j2`, and `OPERATIONS.md.j2`, while Railway deploy imports the same role name | **Structural: one role name and one statement set feed local, Railway, and manual paths** | **strengthened** — naming and `GRANT CONNECT` drift gated |
| **Template ↔ upgradable-code contract compatibility across versions** | `project_contract` in state plus declared module/CLI vintages; `status` reports gaps and existing-project `update`, `apply`, and Railway deploy enforce them | **Structural at mutation boundaries, with explicit per-invocation acknowledgement** | **strengthened** — compatibility boundary enforced |
| Every emitted path has a migration disposition | Generator-derived conformance test over a hand-authored taxonomy | Membership gated; ownership hand-authored | unchanged; paid again for two new emitted paths (`31a93768`) |
| Cross-domain deletion obligations are discharged | Last-owner: one predicate, locked model delete, `pre_delete` receiver. One named obligation contract classifies billing reconciliation, row purge, cache invalidation, and tombstone handling across account deletion and `purge_organization` | Last-owner, live-subscription refusal, and obligation classification are structural; **execution remains split across two boundaries** | **strengthened** — shared contract added; durable coordinator remains deferred — rank 1 |
| CSRF-exempt endpoints have alternate integrity checks | AST gate plus sanctioned endpoint bases | Structural and gated | unchanged |
| Core/module dependency direction and lockstep pin | Import-compatibility and reverse-import gates; exact `>=X.Y.0,<X.(Y+1).0` pin derived from `VERSION` | Gated | strengthened (floor → exact, `74d18f48`) |
| Module identity (the twelve-module universe) | `module_discovery.py --list-modules`, consumed fail-hard (`provision_ci_postgres.sh:81`, `check_sa117_scope.py:57`, `version_tool.sh:34`) | Structural and derived | unchanged (SA173 three-state presence added behind the same shim) |
| CI runtime environment and closed hosted-job set | `provision_ci_postgres.sh` (five profiles); `sync_ci_gate_jobs.py:386-392` (`UNOWNED ∪ registry-bound` == 18 jobs) | Structural and gated | strengthened by the registered migration smoke job; parity extractors also count reusable-workflow `uses:` jobs |
| Behavioural-control commits carry testimony | `check_commit_testimony.py` — a `vNN` token in the message | Gated, token-shaped | **narrowed** (`2e2a932a`, labelled `docs:`, dropped the SA-ticket and CHANGELOG forms) |
| Generated emission is byte-identical to the recorded manifest | SA90 fixture hash/mode comparison, `_HOST_DEPENDENT_PATHS` exception | Gated, one exception entry | unchanged (still 1 — monotonic) |
| Complexity maxima never ratchet upward | Merge-base monotonicity gate plus waiver ledger | Gated | unchanged (baseline shrank by 24 lines) |
| Gate-suite self-tests, planning-count derivation, runtime pins, installed-wheel lifecycle E2E | `check-gate-suites`, ticket-context consistency test, `runtime_pins.py`, `smoke-install` | Gated / structural | unchanged — re-verified present |

## Summary table

| Rank | ID | Horizon | Confidence | Size | Problem in one line |
|---:|---|---|---|---|---|
| 1 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months | High | M | Two org-deletion boundaries share one obligation contract but still execute different subsets without a durable coordinator. |

The remaining finding is scheduled at the 6–18 month horizon. The permanent two-command privilege
contract is cross-checked across all four enforcing stations, whose duplication remains a watch item.

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

**Problem:** Last-owner safety and the cross-domain obligation inventory are structural, but the
actions for removing an organization — reconciling billing, deleting tenant rows, invalidating
caches, and writing a tombstone — are still orchestrated by whichever boundary runs. The two
existing boundaries intentionally discharge different subsets without a durable coordinator.

**Evidence (census of org-lifecycle deletion boundaries):**

| Obligation | Account-delete view (`auth/views.py::AccountDeleteView`) | `purge_organization` |
|---|---|---|
| Last-owner guard | ✅ `AccountDeleteView._get_blocking_orgs_for_deletion` via the one predicate | n/a (whole org) |
| Reconcile Stripe subscription | ✅ outside the deletion transaction | Refuses current Stripe-backed subscriptions and active checkout reservations under the organization-keyed provider advisory mutex; elapsed reservations are reconciled with Stripe before the transaction, local finalization uses the organization-row lock, and only provider-confirmed expiry is purgeable |
| Delete tenant rows | Deliberate skip recorded because the organization survives | ✅ marker-derived `_delete_owned_rows` |
| Invalidate social caches | Deliberate skip recorded because the organization survives | ✅ `_clear_social_cache` |
| Tombstone | Deliberate skip recorded because the organization survives | ✅ after the organization row is removed |

`cancel_current_subscription` has exactly two callers:
`billing/views.py::CancelSubscriptionView.post` and
`auth/views.py::AccountDeleteView._cancel_personal_org_subscriptions`. The six last-owner
callsites were re-verified (`orgs/models.py:165,329`; `signals.py:66`;
`orgs/views.py:808,1161`; `auth/views.py::AccountDeleteView._get_blocking_orgs_for_deletion`).

**Counter-evidence:**

- **No billing delete hooks.** Searched billing for `pre_delete`/`post_delete` receivers or
  model-level `delete()` hooks; found none.
- **The live-subscription precondition is enforced and documented.** The purge and dry-run paths
  list current Stripe subscription IDs and refuse before deletion.
- **The obligation inventory is now shared.** `ORGANIZATION_REMOVAL_OBLIGATIONS` classifies all four
  actions, both boundaries consume it, and account deletion records its deliberate retention skips.
  Provider-ID conformance rejects a purged external ID with no refusal/reconciliation rule.
- **Last-owner safety is sound**, so this finding is scoped to cross-domain obligations.

**Why it compounds:**

- **Each new domain obligation** must extend the shared declaration and each boundary's handler.
- **Each new boundary** — bulk admin, GDPR erasure, or `teams` — still needs orchestration code.
- **The subsets intentionally differ**, but the shared contract now makes those differences visible.

**Detection signal:** a new organization-deletion boundary that does not consume the shared
obligation contract, a provider ID without a refusal/reconciliation declaration, or a durable
erasure requirement that cannot tolerate boundary-local execution.

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

**Recommendation:** Keep the completed shared obligation contract and last-owner model/signal
backstop. Adopt option 1 when another destructive boundary or durable-erasure requirement fires the
coordinator trigger; use option 3 only when recovery across multiple external stores is required.

---

## Change-cost probe

**Probe — SA153: add one project-owned tenant child table** (for example, a property gallery
image). Marker-derived classification, policy refresh, and purge membership now cover the runtime
stations:

1. The project model: `tenant_org_fk()` plus `TenantManager()` and `TenantManager(super_scope=True)`.
2. A project migration calling `apply_force_rls()`, plus `add_composite_child_fk()` for the parent
   equality.
3. A child boundary test on the `test_rls_boundary.py` pattern.
4. Purge discovers the model automatically and orders it before its protected parent from installed
   FK metadata; no module-source edit is required.

**Verdict: resolved:** the project model, migration, boundary test, classification, policy refresh,
and purge all have an extension path without vendored module edits.

---

## Fix order and interactions

- **Marker-derived classification, refresh, and purge are complete:** SA153 can add project-owned
  child tables without a vendored module edit.
- **The remaining deletion-coordinator finding is deferred:** its first step, the shared obligation
  inventory, is complete; preserve that contract if a later trigger justifies a coordinator.
- **SA152's completed maintainer verification** does not conflict with the remaining finding.
- **SA177 is independent:** its "each enrolled table" scope already covers project tables.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed.** Ambient `TenantManager` scoping plus
  restricted-role `FORCE RLS`. A boot guard rejects a `rolbypassrls`/`rolsuper` runtime role, and
  `_check_quickscale_mode()` runs before the privileged exemption. Marker-derived membership and
  the W003/W004 isolation checks and marker-derived purge are what keep project-owned tables safe.
- **Last-owner safety is a model/signal backstop, not a view check.** One predicate serves six
  callsites, plus a `pre_delete` receiver that catches direct ORM deletes. Rank 2's coordinator
  must not replace it.
- **Single-declaration derivation seams work where they are used.** Tenant classification, policy
  refresh, and purge share the installed marker-derived model set. Module identity is shelled out
  to `module_discovery.py --list-modules` by every consumer. `runtime_pins.py` renders Python,
  Django, and PostgreSQL pins into templates. The lockstep pin is now derived exactly from
  `VERSION` (`74d18f48`). These are the precedent for the remaining deletion-boundary work.
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
