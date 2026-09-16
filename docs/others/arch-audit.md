# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-09-15 · **Branch:** `v89` · **Range audited:** `48e0a62a..b9e072f4` ·
> **Prior pass:** 2026-08-28 (reconciled through 2026-09-06)
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

**Scope decision.** Prior passes spent their depth on the governance/CI layer and on the
template/runtime boundary. This pass has three jobs:

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
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` boot guard; exemption set declared in four places | Guard structural; **set membership convention-only (4 declarations, 3 members, no cross-station gate)** | **weakened** — third member added in `b29d9a29` with no station test |
| **Restricted runtime role exists with the right grants** | `db/init.sql.j2` (role `{package}_app`), `start.sh.j2` Step 3 (role `quickscale_runtime`, adds `GRANT CONNECT`), `OPERATIONS.md.j2` manual SQL | **Convention: three implementations, two role names** | **new row** (seam minted in `461796ce`) |
| **Template ↔ upgradable-code contract compatibility across versions** | `project_contract` in state plus declared module/CLI vintages; `status` reports gaps and existing-project `update`, `apply`, and Railway deploy enforce them | **Structural at mutation boundaries, with explicit per-invocation acknowledgement** | **strengthened** — finding retired |
| Every emitted path has a migration disposition | Generator-derived conformance test over a hand-authored taxonomy | Membership gated; ownership hand-authored | unchanged; paid again for two new emitted paths (`31a93768`) |
| Cross-domain deletion obligations are discharged | Last-owner: one predicate, locked model delete, `pre_delete` receiver. Billing cancellation: account-delete view; live-subscription refusal plus row purge, cache invalidation, and tombstone: `purge_organization` | Last-owner and live-subscription refusal are structural; **remaining obligations convention, split across two boundaries** | **re-characterized** — rank 3 |
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
| 2 | `privileged-command-set-multi-owner` | now (fired) | High | M | Four independent declarations own the privileged-command set. It grew to three with no gate, and the frozen template copy rejects the new command in the projects that need it. |
| 3 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months | High | M | Two org-deletion boundaries already exist, and each discharges a different subset of cross-domain obligations. |

Promotions this pass: rank 1 remains now as the still-open SA190 purge-membership half; its
classification and policy-refresh halves are implemented by SA182. Rank 2 returns from the watchlist
because its trigger fired. Rank 3 moves from deferred to 6–18 months, because prior passes
mis-evaluated its trigger. The
rank-1 finding is narrowed rather than closed: SA190 still owns purge derivation.

---

## Fix-regression and delta audit

**Closeouts since the last pass.** Each was scored against the three §3 questions:

- **SA164** (`5d2c4ab5`): the guardrail now fails loud. The mechanism is fixed and the tuple
  stays literal; see the watchlist.
- **SA171** (`bf153e36`): stale-lock reclamation is atomic. The *same* correction had to be
  written into both lock implementations. That is not a relocation, but it is the watch item's
  compounding paid once more.
- **SA172 / `89d262bc`**: the FORCE-RLS refresh is idempotent. No new commitment was minted, but
  at that closeout the refresh still iterated the literal registry. That then-pre-existing gap
  became rank-1 evidence; SA182 later closed the refresh half.
- **SA173**: module presence is three-state, and identity stays derived. Sound.
- **SA160**: the template copy of `get_client_ip` was deleted in favour of the module resolver,
  plus a generated normalizing middleware. The mechanism is removed. The resolver still fails
  closed without the middleware (`current_org.py:598-603`), so the template/module split did not
  mint a skew hazard. Sound.
- **SA174**: the command-set docstring now says "none is a single source of truth." It landed and
  was then overtaken by `b29d9a29`.
- **SA167c**: a new gate. Its count-oracle cost is already recorded.

None relocated a prior finding's mechanism.

**Unlabeled-behavioral commits.** Three changed load-bearing semantics on the privilege/runtime-role
seam (`b29d9a29`, `461796ce`, `a85f29ff`), and one narrowed a gate (`2e2a932a`):

- `decisions.md` was updated for the first two.
- The prior pass's recorded maintainer answer (2026-08-31, "the two-command set is permanent") was
  not revisited.
- `b29d9a29` itself edited this file, changing a job count from 16 to 17, while leaving the
  privileged-command watch item marked "Not fired." That is decision-record drift in the §5.IX
  sense: plausibly correct behaviour, but the governing record now contradicts the code.

The testimony gate as narrowed accepts any `vNN` token, and every commit on a `vNN` branch
carries one, so it could not have flagged any of these. This is recorded, not promoted. Adding
properties to that gate is additive, and the better lever is the structural fixes below.

---

## Finding — Purge membership remains closed to project-owned tables

**ID:** `org-model-universe-hand-enumerated` · **Horizon:** now · **Confidence:** High ·
**Size:** S · **Context dependence:** `wrong-for-now` (new domain — first project-owned tenant tables)

**Rank rationale:** the remaining blast radius is org teardown for the first production portal.
Classification and policy refresh now accept project-owned tenant models; purge remains the
unresolved SA190 half. The trigger is certain because SA153 is the next ticket on the critical path.

**Trigger (restated):** a project-owned or module tenant model is scheduled. **Fired** — SA153's
acceptance requires new tenant-owned child tables with their own `organization_id` and forced RLS
(`roadmap.md`, SA153). The prior trigger ("teams adds a tenant model")
named the wrong growth vector.

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

## Finding — The privileged-command set has four owners and a frozen copy

**ID:** `privileged-command-set-multi-owner` · **Horizon:** now · **Confidence:** High · **Size:** M ·
**Context dependence:** `wrong-for-now` (a set that grows / generated projects in the field)

**Rank rationale:** the blast radius is the RLS privilege seam in every generated project. Every
divergence fails closed, so the cost is availability and operability rather than a leak. The
trigger has already fired.

**Trigger:** "a third sanctioned command, or any two declarations disagreeing." **Fired** by
`b29d9a29` (2026-09-13, "v88 fix: make ci-e2e fixes"), which added `migrate_billing_to_orgs`. The
decision this watch item was held under — the maintainer's 2026-08-31 answer that the two-command
set is permanent — has not been revisited.

**Problem:** Which one-shot commands may run under the superuser connection is declared
independently in four places:

- the module boot guard (`orgs/apps.py`);
- the generated production-settings validator (`production.py.j2`);
- the CLI producer (`development_commands.py`);
- the generated launcher (`start.sh.j2`).

Nothing derives or cross-checks them. Two of the four are frozen into every generated project at
generation time.

**Evidence** (re-verified and extended this pass):

- **The four declarations now:**
  - `production.py.j2:156`: `_KNOWN_PRIVILEGED_COMMANDS = frozenset({"migrate", "createcachetable", "migrate_billing_to_orgs"})`.
  - `orgs/apps.py:36`: `_PRIVILEGED_COMMANDS`.
  - `development_commands.py:44`: `_PRIVILEGED_DJANGO_COMMANDS`.
  - `start.sh.j2:11-20`: a *new declaration shape*, an argv dispatch branch for the third command.
    The first two members stay as inline env prefixes (`:115`, `:126`).
- **Station tests do not name the new member.** `createcachetable` appears in the generator's
  start.sh tests 26 times and in the boot-guard tests 7 times. `migrate_billing_to_orgs` appears
  in no generator, CLI, or boot-guard test; the only tests naming it are the command's own
  behaviour tests (`orgs/tests/test_management_commands.py`).
- **The frozen station rejects the command where it is needed.** The command's documented users
  are existing deployments with user-scoped billing (`release-v0.86.0.md:49,56`;
  `organizations.md:400`). Those projects were generated before 0.88.
  - Their `production.py` raises `ValueError("Unknown QUICKSCALE_PRIVILEGED_COMMAND value …")`.
  - Their `start.sh` has no one-shot branch.
  - An upgraded `orgs` module plus an upgraded CLI still cannot run it through the sanctioned
    path. The only route is the `QUICKSCALE_ALLOW_BYPASSRLS=1` escape hatch.
- **An adjacent seam was minted in the same release.** Runtime-role provisioning (`461796ce`) now
  has three implementations with two role names:
  - `db/init.sql.j2:23-50` creates `{package}_app` (`generator.py:507`) without `GRANT CONNECT`;
  - `start.sh.j2:56-104` creates `quickscale_runtime` with `GRANT CONNECT` (`:94`), and its
    default name duplicates `deployment_commands.py:37`;
  - `OPERATIONS.md.j2:55,71-85` gives the manual SQL.

  `decisions.md` records that provisioning "is not a fourth privileged Django command." That is
  correct for the guard, and it is still a fifth station on the same privilege seam.

**Counter-evidence:**

- **No derivation or cross-station gate.** Searched for a derivation, a cross-station equality
  test, and a `runtime_pins`-style shared constant for the command set; found none.
- **All four stations agree today**, and every miss fails closed. The module guard's independent
  check (run before the exemption) is intact.
- **No flat-cost counterpart.** Searched for evidence that the third member is a time-boxed
  exception; `decisions.md:908` now calls it "the three-command contract," with no retirement
  condition. The adjacent `NON_DB` contract still has a one-station change cost.

**Why it compounds:** the measured probe below is 8 edited stations over 2 commits (4 executable,
0 derived, 0 gated). Beyond that:

- **Member tests lag.** Each new member is tested at fewer stations than the last.
- **Declaration shapes multiply.** Each launcher mode introduces a new shape: env prefix, then
  argv branch.
- **Frozen copies block new members.** Each member added after a project is generated is
  un-runnable there without hand-editing emitted files.
- **Role provisioning repeats the pattern.** It is growing the same way (three implementations
  and two names within one release).

**Detection signal:** `Unknown QUICKSCALE_PRIVILEGED_COMMAND value` in deploy logs. Operators
reaching for `QUICKSCALE_ALLOW_BYPASSRLS=1` to run a data backfill. Password-authentication
failures for `quickscale_runtime` or `{package}_app` after a role-name mix-up.

**Steelman:** four fail-closed declarations are defence in depth. Settings validation, the module
guard, the CLI producer, and the launcher each refuse independently, and a single shared constant
would be a single point of trust. For a set that really does stay at two members, the duplication
cost is flat. Do not fix if `migrate_billing_to_orgs` is retired once the backfill window closes.

**Correct shape:** the sanctioned set is declared once, in a place that upgrades with the code that
adds members. Each enforcing station *reads* that declaration and keeps its own independent refusal.
Runtime-role provisioning has one implementation and one role-naming rule.

**Options:**

1. **Render-time single declaration.** A `runtime_pins`-style constant in `quickscale_core`,
   rendered into `production.py.j2` and `start.sh.j2`, and imported by the CLI and by the orgs
   guard (modules already depend on core). This fixes in-tree sync but not projects already in
   the field.
2. **Commands declare themselves.** A `requires_privileged_role = True` attribute on the Django
   command class. The guard and the launcher check the attribute; settings validate only that
   privileged mode was requested explicitly. The declaration then ships and upgrades with the
   command inside its module, which removes the frozen station for future members. It needs care,
   because settings import before commands load.
3. **Keep four declarations and add a cross-station equality test.** Cheapest, but it is a gate
   holding a copy-pair honest — the §0 fix-regression shape.

**Recommendation:** Option 2 if the answer to the question below is "permanent." It is the only
option under which a member added in a module release reaches already-generated projects. Choose
Option 1 if the third member is retired. In either case, fold role provisioning into one
implementation (the `start.sh` step, with `init.sql` delegating to the same SQL and one naming
rule). · **First step:** record whether `migrate_billing_to_orgs` is permanent, then collapse
role-name derivation to a single rule.

---

## Finding — Organization deletion obligations are split across two boundaries

**ID:** `deletion-invariants-per-boundary-reimplementation` · **Horizon:** 6–18 months ·
**Confidence:** High · **Size:** M · **Context dependence:** `wrong-for-now` (production tenants /
compliance)

**Rank rationale:** the blast radius is billing and data retention for real organizations, which
SA153 is the first to create. Likelihood is moderate: both boundaries exist today, but the
production volume does not yet.

**Trigger:** "another account/organization deletion boundary." **Mis-evaluated by prior passes.**
`purge_organization` has existed since `63a25b6e` (2026-06-26), before the last three passes, and
it is that second boundary. It re-promotes on SA153's production launch rather than on teams.

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

**Probe A — adding a third sanctioned privileged command, measured against the real addition.**
The prior pass predicted this on paper. `b29d9a29` plus `3923eb58` actually edited:

1. `production.py.j2`: the set at `:156` plus two comment blocks. Frozen in generated projects.
2. `start.sh.j2:11-20`: a new argv dispatch branch, a new declaration shape. Frozen.
3. `orgs/apps.py:36`: the set plus four docstrings.
4. `development_commands.py:44`: the set.
5. `decisions.md`: three sites.
6. `docs/deployment/railway.md`.
7. The SA90 emission fixture, regenerated across three variants. It was regenerated **twice**,
   because `3923eb58`'s reformat of line `:156` changed the emitted bytes again.
8. `CHANGELOG.md`.

Not edited though owed: station tests at 3 of the 4 executable stations, the `orgs`
`contract_vintage`, the settled-decision answer, and this document's watch item.

**Verdict: finding evidence** (rank 2): 8 stations over 2 commits, 4 executable, 0 derived, and
0 gated. Contrast `NON_DB`: one station.

**Probe B — SA153: add one project-owned tenant child table** (for example, a property gallery
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
- **Purge derivation pairs with rank 3:** the remaining rank-1/SA190 purge half and rank 3's
  coordinator touch the same command, so design them together.
- **SA177 is independent of all three findings,** but its "each enrolled table" scope inherits rank 1's
  closed universe. If rank 1 lands first, SA177 covers project tables for free.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed.** Ambient `TenantManager` scoping plus
  restricted-role `FORCE RLS`. A boot guard rejects a `rolbypassrls`/`rolsuper` runtime role, and
  `_check_quickscale_mode()` runs before the privileged exemption. Marker-derived membership and
  the W003/W004 isolation checks are what make SA182's runtime shape safe; keep them while SA190
  derives purge membership.
- **Last-owner safety is a model/signal backstop, not a view check.** One predicate serves six
  callsites, plus a `pre_delete` receiver that catches direct ORM deletes. Rank 3's coordinator
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

- **`privileged-command-set-multi-owner`:** is `migrate_billing_to_orgs` a permanent third member,
  reversing the 2026-08-31 answer, or a one-shot to retire once pre-org billing data is
  backfilled? A dated retirement demotes this back to the watchlist; permanence confirms Option 2.
*The prior answer from 2026-08-31 ("permanent two commands") has since been contradicted by
`b29d9a29`; its earlier effect is recorded in the reconciliation log.*

## Red flags (out of scope — fix now)

- *(Dismissed, retained so it is not re-raised)* `except ValueError, AttributeError:` at
  `purge_organization.py:337` is valid PEP 758 syntax on the pinned Python 3.14.6.

## Reconciliation log

- 2026-08-28 — `ci-environment-hand-replicated`: **resolved** and archived; the full fix-regression
  narrative is in [CHANGELOG.md](../../CHANGELOG.md). Only its residue stays live here — the two
  hand-pinned literals on the watchlist, restated by SA174 after it absorbed SA178.
- 2026-08-28 — `privileged-command-set-multi-owner`: **new**, promoted from the prior watchlist item
  "privileged-command template/runtime pair", whose trigger ("a third sanctioned command, or a mismatch")
  **fired** — not as a value mismatch but as a third and fourth *owner*. `3523f9f8` (2026-08-18, labeled
  `test:`) added the CLI decider without reconciling the SSOT claim at `apps.py:52`.
- 2026-08-28 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, deferred. All six
  callsites re-verified. Trigger not fired; `teams` remains README-only.
- 2026-08-28 — `org-model-universe-hand-enumerated`: **still-open**, deferred. Anchors re-verified and the
  spec count re-derived by AST rather than transcribed: **21**, matching the prior pass. Trigger not fired.
- 2026-08-28 — Fix-regression audit of the delta's two behavioral commits (`990f660f`, `48e0a62a`):
  compounding **removed, not relocated**. Literal ticket IDs, merge positions, dependency edges, dates and
  prose deleted from the planning conformance gate and replaced with roadmap-derived counts plus a red
  canary; structural invariants (no checked entries, dependency validity, position uniqueness, no
  schedulable restatement) all survive with their own canaries. No invariant weakened, no station minted.
- 2026-08-28 — Prior watchlist reconciled: *module universe in environment lists* **not fired** (and its
  parent finding resolved); *SA92 migration-squash tuple* **not fired**, still SA164's; *frontend runtime
  module keys* **not fired** (universe unchanged at twelve); *privileged-command pair* **fired — promoted**;
  *`trigger_inputs` name drift* **not fired**, verified against `check_gate_parity.py:498-524`. Two items
  added from the fix-regression audit; one added for the count-pinned oracles.
- 2026-08-28 — Prior red flags: none were open at the last pass and none opened this pass.
- 2026-09-05 — **Watchlist ownership split, no finding changed.** SA164 was carrying one executable
  repair plus two documentation obligations. The repair — making the SA92 guardrail's `_migdir()`
  fail loudly and re-anchoring its `v87` backstop — stays with **SA164**. The `trigger_inputs` naming
  correction and the restatement of the three not-fired items moved to **SA178** at this checkpoint;
  the consolidation below supersedes that assignment. No item was closed, promoted, demoted, or had
  its trigger altered; the ranked findings and their deferrals are untouched.
- 2026-09-05 — **SA164 guardrail repair completed.** The SA92 tripwire now raises on a missing
  conventional migration directory instead of skipping the module, its regression proves the scan
  cannot pass by absence, and its backstop wording points at the current regenerated migration
  baseline rather than retired `v87`. The watch item remains open with its trigger unchanged and
  future restatement now owned by SA174; no ranked finding changed.
- 2026-09-05 — **Planning consolidation, no finding changed.** SA174 absorbs SA178's
  documentation-only semantics correction and watchlist reconciliation. Post-v88 SA152 absorbs
  SA175 as mode-aware migration compatibility smoke verification; the prior assertion-only
  acceptance is superseded, not discharged. Current dependencies and tracks live only in the
  [roadmap](../technical/roadmap.md). No product work or release verification occurred in this edit.
- 2026-09-06 — **SA174 documentation candidate reconciled the watchlist.** The false command-set
  SSOT instruction is corrected, `privileged-command-set-multi-owner` is demoted under the settled
  two-command decision, and every watch trigger remains armed. Retained `trigger_inputs` semantics
  describe the exact bidirectional E2E allowlist partition without changing behavior. The historical
  count-oracle trigger is confirmed fired and promoted to a separately owned gate-parity follow-up;
  deriving those oracles is independent of this documentation correction. No watch item is closed.
- 2026-09-06 — **The fired count-oracle follow-up is ticketed as SA180.** The promotion was carried
  as an unassigned note with an owner role but no planner entry; it now has a post-v88 ticket, an
  acceptance condition (derive each count from the source it describes and prove it with a
  gate-addition regression), and a track. The watch item, its trigger, and its severity are
  unchanged, and no other finding is touched. Closed-ticket release narrative for SA166, SA167c,
  SA167d, SA170, SA171, and SA176 was removed from the orientation section above; all of it is
  archived in [CHANGELOG.md](../../CHANGELOG.md) and none of it constrained an open finding.
- 2026-09-06 — **SA174 closed; no finding retired.** The command-set and gate-input documentation
  corrections were already integrated on `v88`, and their validation is now green: the gate-parity
  check reported *All gates present in all required contexts.* (exit 0), `scripts/test_gate_parity.py`
  passed **238 tests**, and Ruff check and format were clean on `check_gate_parity.py`,
  `test_gate_parity.py`, and `orgs/apps.py`. The `privileged-command-set-multi-owner` demotion and
  the watchlist restatement stand as recorded; every watch item above keeps its live status and
  trigger. The fired count-oracle trigger remains owned by SA180. Evidence is archived in
  [CHANGELOG.md](../../CHANGELOG.md).
- 2026-09-15 — **Commit delta `48e0a62a..b9e072f4` reconstructed.** 759 commits: 109 merges, 472
  synthetic subtree-split commits (excluded), 178 monorepo commits (99 docs-only, 32 tests-only, 29
  ticket-labelled closeouts, 18 unlabeled-behavioral, all read at depth). Every prior anchor was
  re-resolved against current code. Moved anchors: `beta_migration.py` is now 2,716 lines, with
  collections at `:55`/`:86`/`:108`/`:123`, `_execute_copy_selected_django_files` at `:1842`, and
  in-place targets at `:121`/`:125`/`:128`; the closed-universe check is at
  `sync_ci_gate_jobs.py:381-387`.
- 2026-09-15 — `org-model-universe-hand-enumerated`: **still-open, promoted deferred → now.** It
  was re-scoped from purge ordering to the root: classification, policy refresh, and purge are
  literal module-source lists closed to project-owned tenant tables. The trigger was restated from
  "teams" to SA153, which fires it. The spec count was re-derived by AST at 21.
- 2026-09-15 — `privileged-command-set-multi-owner`: **watchlist → finding (trigger fired).** A
  third member was added in all four declarations by `b29d9a29` ("v88 fix: make ci-e2e fixes"),
  contradicting the 2026-08-31 "permanent two" answer. The same commit edited this document
  without re-evaluating the trigger. Evidence was extended with the frozen-station
  un-runnability and the three-implementation runtime-role seam (`461796ce`).
- 2026-09-15 — `deletion-invariants-per-boundary-reimplementation`: **still-open, promoted deferred
  → 6–18 months.** Prior passes mis-evaluated the trigger: `purge_organization` (since 2026-06-26)
  is a second boundary, and a census shows the two boundaries discharge disjoint obligation
  subsets. Size re-estimated S → M.
- 2026-09-15 — Fix-regression audit of the delta's closeouts (SA160, SA164, SA167c, SA171,
  SA172/`89d262bc`, SA173, SA174): **no mechanism relocated.** SA171 applied one correction to both
  lock implementations, which is recorded under that watch item. SA160 removed a template/module
  copy-pair and is recorded as a sound decision.
- 2026-09-15 — Prior watchlist reconciled:
  - *Two lock implementations*: **not fired** (SA171 note added).
  - *Provisioning hand-pinned literals* and *second PostgreSQL major*: **merged into one item**,
    both **not fired**.
  - *Count-pinned oracles*: **fired (prior), SA180 open**, population re-verified at 8.
  - *SA92 tuple*: **not fired** (10 = 10).
  - *`trigger_inputs`*: **not fired**.
  - *`privileged-command-set-multi-owner`*: **fired — promoted to finding**.
- 2026-09-15 — Prior red flags: none were open. **One opened:** `purge_organization` orphaning
  live Stripe subscriptions.
- 2026-09-15 — Prior questions: both were answered 2026-08-31. The first answer is now contradicted
  by code (see above), and the second's scope ("no updater for users") was found not to cover
  `quickscale update` and `deploy`. Three new questions were added.
- 2026-09-15 — Census: two rows added (runtime-role provisioning; template ↔ upgradable-code
  vintage), three re-characterized (tenant-model universe, privileged set, deletion obligations),
  and one narrowed (commit testimony, `2e2a932a`).
- 2026-09-15 — **SA182 Phase A narrowed `org-model-universe-hand-enumerated` to its SA190
  purge-membership half.** Classification and FORCE-RLS refresh now use the marker-derived tenant
  set, with project-owned fixture regressions and live-policy validation; `_DELETE_SPECS` remains
  the open purge seam. No purge implementation, status, or release surface changed.
- 2026-09-15 — **The count-pinned gate-parity oracle watch item is retired.** Registry-bound
  expectations now derive from the gate registry, workflow station counts derive from the station
  contract, and a gate-addition regression proves the derived counts follow their source. No ranked
  finding or other watch item changed.
- 2026-09-16 — **The `purge_organization` live-Stripe red flag is retired.** The command and dry
  run refuse before deletion, list current Stripe subscription IDs, and preserve local rows until
  the operator cancels them. Rank 3 remains open for the broader shared-obligation work.
- 2026-09-16 — **`generated-file-ownership-unmodeled` is retired.** The `orgs` manifest and
  Railway runtime-role command declare the 0.88 contract boundary, while existing-project
  `quickscale update`, `quickscale apply`, and `quickscale deploy railway` refuse old or unknown
  contracts before mutation. The refusal names the owner, minimum, and manual adoption steps; a
  dedicated acknowledgement resumes one invocation without pretending to update generated files.

*Lenses scanned with no qualifying finding this pass: observability, API/contract stability of
the CLI surface, performance and scalability, concurrency and state isolation (beyond the lock
watch item), build/release and supply chain (single lockfile, exact lockstep pin — both sound),
and the library archetype lens. Trust and authorization, data/state model, design conflicts,
governance, and the code-generator archetype lens produced the ranked findings above.*

Closed findings, retired watch items, historical option records, and cross-reference migrations are
archived in [CHANGELOG.md](../../CHANGELOG.md) and version control rather than repeated here.
