# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-09-17 · **Branch:** `v89` · **Range audited:** `b9e072f4..98b6c455`
>
> Live structural findings only. Findings are identified by their **slug**; ordinal numbering is
> pass-local and is not a stable identifier (see
> [decisions.md → Document Responsibilities](../technical/decisions.md)). Closed findings and
> prior-pass narratives live in [CHANGELOG.md](../../CHANGELOG.md).

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform** with a Click CLI,
a Django 6 project generator, and twelve shipped first-party modules embedded into generated
projects by `git subtree` and upgraded by `quickscale update`. Generated projects run PostgreSQL 18,
Vite/React, Docker and Railway; their public contracts are the CLI, `quickscale.yml` and applied
state, module manifests, the generated trees, and upgrade semantics. Persistence in generated
projects is PostgreSQL with dual-layer tenant isolation (`TenantManager` plus `FORCE RLS` under a
restricted runtime role). One maintainer, 3,688 reachable commits, one author. Governance is
deliberate: 13 registered gates, a closed hosted-job universe, AST and conformance gates, and
monotonic quality baselines.

**Commit delta** (`b9e072f4..98b6c455`, 34 commits: 12 merges, 22 non-merge). Every non-merge
commit carries a `v89:` testimony token, so the commit-testimony gate is holding. Classification:

- **Closeout (14):** `b217500d` (SA180 gate-parity counts), `d77576c1`/`d2359907`/`d06c85fa`
  (SA182 tenant enrollment), `6a9797e2` (SA187 Railway credentials), `9828ba86` (live-subscription
  purge refusal), `f334f087`/`81cec6c7` (SA177 RLS predicates), `882b5cf6` (SA185 contract
  vintage), `8a914f38` (SA186 split ancestry), `37987df9` (privileged-command contract),
  `adc753c6` (auth-header comparison), `f1a434a5`/`a97b5788` (SA152 beta-migration verification),
  `98b6c455` (SA189 runtime-role provisioning).
- **Housekeeping (5):** `d91cc85c`, `ca729ccc`, `2f264151`, `707ef1ed`, `fd6d7d40` — roadmap,
  user-manual, tenancy-doc and retired-ticket-context edits only.
- **Unlabeled-behavioral (3),** read at full depth:
  - `4a8fb649` "Refactor frontend templates" — despite the refactor-shaped message this is the
    **SA192 precursor**: it restyled the blog, crm and listings Django pages, added three
    per-module `<module>.css` static files, and minted **three byte-identical**
    `tests/templates/base.html` stubs (md5 `2902eaa7…`) plus three near-identical
    `test_templates.py` suites. Measured as probe A below.
  - `6a8e0189` "derive expected test versions" — test-only, replaces hardcoded version literals
    with derivation. Sound.
  - `adc753c6` "reject malformed authentication headers" — a real defect class, not a rename:
    `secrets.compare_digest`/`hmac.compare_digest` were called on `str`, which raises `TypeError`
    on non-ASCII input. Census: **2 of 2** hand-rolled shared-secret verifiers in the tree had the
    identical bug (`blog/views.py:351`, `notifications/services.py:752`); both fixed in this one
    commit. Billing's third verifier delegates to the Stripe library and was never affected.

**Growth direction (planning surface, authoritative).** `roadmap.md` scheduling table: the critical
path is **SA194 → SA191 → SA153** on track 1 — unblock the in-place migration gate, migrate
`bap-web` onto current QuickScale, then build the first property portal as a project-owned
extension. Track 2's next ticket is **SA202** (pin the publishing supply chain and add the missing CI
scanners); track 3's is **SA196** (fail hard on undefined generator template context). All three tracks
are "truly green". Completed SA190 removed project-owned tenant tables as a purge dependency by deriving the
purge plan from installed tenant metadata; the durable deletion coordinator remains deferred.

**Scope decision.** Three jobs: (1) re-verify both prior findings and all five watchlist triggers;
(2) close the prior pass's largest declared coverage gap — `beta_migration.py` (7,289 lines), which
SA191 is about to use for real, and `apply_command.py` (4,185 lines), both previously skipped or
sampled; (3) probe the two scheduled next changes.

**Measurements run (§3).** Churn × size over 12 months; defect gravity by directory; co-change
coupling across top-level areas with Jaccard; import fan-in; AST censuses of `_DELETE_SPECS`,
`INTENTIONALLY_UNMANAGED`, and every module-level literal table in `beta_migration.py`; a
manifest-vs-implementation census of `*_env_var` options. Co-change is healthy: the strongest pairs
are src↔tests within a package (`quickscale_cli` 0.60, `quickscale_core` 0.54); the only notable
cross-package pair is `quickscale_cli/src ↔ quickscale_core/src` (142 commits, 0.34), which is the
CLI-over-core layering working as designed. Modules barely co-change with each other, which is
evidence the subtree-split boundary is real.

**Read fully:** `beta_migration.py` structure and all 46 module-level literal tables, its runtime
compatibility validator (`:3630-3720`, `:5797-5940`) and copy-scope constants (`:68-171`);
`purge_organization.py`; `test_privileged_command_contract.py`; the three env-example triples in
`apply_command.py` (`:1459-1738`) and `apply/steps/env_sync.py`; `notifications/module.yml` and the
`.env.example.j2` template; `test_beta_migration_ownership_conformance.py`;
`generated_file_ownership.md`; `decisions.md` § Release scope safeguards; `roadmap.md`.

**Sampled:** `tenancy.py` public surface (1,994 lines — symbol map plus the classification and
policy-refresh sections); `apply_command.py` outside the env-sync band; `dr_engine/orchestration.py`
(header, layering contract, Protocol seams, backups credential validation at `:2144-2150`);
`provision_ci_postgres.sh`; `publish_module.py` split scope.

**Skipped:** `contracts/resolvers.py`, `manifest/` internals, `advisory_lock.py` and
`dr_engine/_lock.py` internals (watch item only, re-verified by size and count), frontend theme
internals, and the module test suites as tests.

**Coverage and residual risk.** The baseline is static analysis of source at `98b6c455`; nothing was
executed in that pass. SA190's affected source and regressions were re-read through `1270ed46` for
the reconciliation below. One baseline claim still wants runtime confirmation: that the beta-migration smoke gate keeps
`beta_migration.py`'s privileged-command copy honest (watchlist W1). The former rank-1 claim — a
generated project with `storage` or `backups` enabled shipping a `.env.example` with no placeholder
for its declared credential variables — was confirmed and closed by the credential-contract
derivation, whose conformance check now runs with the test suite. A reader must **not** conclude
from this document's silence that `contracts/resolvers.py`, the manifest resolver, or the dr_engine
internals are sound — they were not read at depth this pass, and no pass has read them yet.

## Enforcement census

| Invariant | Enforcement | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural | unchanged |
| **Tenant-model universe is classified (and refreshed, and purged)** | Marker-derived tenant classification, FORCE-RLS refresh, and FK-ordered purge membership; the shipped `TENANT_TABLE_REGISTRY` is a parity oracle only | **Structural and open to installed project-owned tenant models** | **strengthened** — purge no longer hand-enumerates the model universe |
| **Module-declared credential env vars reach the generated `.env.example`** | One declaration-driven renderer for every enabled credential-bearing module, plus a manifest-coverage conformance check | **Structural and gated** | **closed — rank 1 resolved; `storage` and `backups` gain placeholders on the next `apply`** |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` boot guard; exemption set declared across fail-closed stations | Guard structural; duplicated declarations cross-checked | unchanged |
| Restricted runtime role exists with the right grants | `runtime_database.py` declares the role, attributes and grants; generator renders them into `db/init.sql.j2`, `start.sh.j2`, `OPERATIONS.md.j2`; Railway deploy imports the same name | Structural — one role name, one statement set | **strengthened** (`98b6c455` unified provisioning) |
| Privileged Django command set | Three `frozenset` stations + `start.sh.j2`, held equal by `test_privileged_command_contract.py`; a **fifth** copy in `beta_migration.py:3663` is outside that test but exercised by the smoke gate | Gated, exact-member | **set reduced to two members** (`37987df9`); **station count 4 → 5** — W1 |
| Template ↔ upgradable-code contract compatibility | `project_contract` in state plus declared module/CLI vintages; `status` reports gaps; `update`/`apply`/Railway deploy enforce them | Structural at mutation boundaries | unchanged |
| Every emitted path has a migration disposition | Generator-derived conformance test over a hand-authored taxonomy; bidirectional (no stale entries) | Membership gated both ways; **disposition choice and its documented rationale are not** | unchanged — **census: 117 emitted paths; 47 (40%) classified solely as `INTENTIONALLY_UNMANAGED`**; list shrank 87 → 78 — W5 |
| Cross-domain deletion obligations are discharged | Last-owner predicate + locked model delete + `pre_delete` receiver; one named contract classifies billing reconciliation, row purge, cache invalidation, and tombstone handling across account deletion and `purge_organization` | Last-owner, live-subscription refusal, and obligation classification structural; **execution remains split across two boundaries** | **strengthened** — shared contract added; durable coordinator remains deferred — rank 1 |
| Shared-secret comparison at module API boundaries | Per-module hand-rolled `compare_digest` calls (2), plus Stripe's library verifier (1) | Convention | **both hand-rolled callsites carried the same `str`-vs-`bytes` defect; both fixed** (`adc753c6`) |
| CSRF-exempt endpoints have alternate integrity checks | AST gate plus sanctioned endpoint bases | Structural and gated | unchanged |
| Core/module dependency direction and lockstep pin | Import-compatibility and reverse-import gates; exact `>=X.Y.0,<X.(Y+1).0` pin derived from `VERSION` | Gated | unchanged |
| Module identity (the twelve-module universe) | `module_discovery.py --list-modules`, consumed fail-hard | Structural and derived | unchanged — universe still 12 |
| CI runtime environment and closed hosted-job set | `provision_ci_postgres.sh`; `sync_ci_gate_jobs.py` parity | Structural and gated | **strengthened** — `check-beta-migration-smoke` registered (`f1a434a5`), registry now 13 gates |
| Behavioural commits carry testimony | `check_commit_testimony.py` — a `vNN` token | Gated, token-shaped | unchanged — all 22 non-merge commits complied |
| Generated emission is byte-identical to the recorded manifest | SA90 fixture hash/mode comparison, `_HOST_DEPENDENT_PATHS` exception | Gated, one exception entry | unchanged (still 1 — monotonic) |
| Complexity maxima never ratchet upward | Merge-base monotonicity gate plus waiver ledger | Gated | unchanged |

## Summary table

| Rank | ID | Horizon | Confidence | Size | Reversibility | Problem in one line |
|---:|---|---|---|---|---|---|
| 1 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months | High | M | two-way door | Two org-deletion boundaries share one obligation contract but still execute different subsets without a durable coordinator. |

The former rank-1 finding closed: module-declared credential variables now reach the generated
`.env.example` through one declaration-driven renderer, and a conformance check fails when a
declaration has no placeholder. The remaining finding takes rank 1 at the 6–18 month horizon:
SA190 completed its shared declaration and marker-derived purge prerequisites, while a durable
coordinator is still deferred until another destructive boundary or durable-erasure requirement
fires the trigger.

## Machine-readable finding index

```yaml
- id: deletion-invariants-per-boundary-reimplementation
  title: Organization deletion obligations are split across two boundaries
  horizon: 6-18-months
  confidence: high
  size: M
  reversibility: two-way-door
  status: open
  depends_on: []
```

---

## Finding — Organization deletion obligations are split across two boundaries

**ID:** `deletion-invariants-per-boundary-reimplementation` · **Horizon:** 6–18 months ·
**Confidence:** High · **Size:** M · **Context dependence:** `wrong-for-now` (production tenants /
compliance)

**Rank rationale:** blast radius is billing and data retention for real organizations, which SA153
is the first to create. Likelihood is moderate — both boundaries exist today, the production volume
does not.

**Trigger:** another destructive organization-removal boundary or a durable-erasure requirement.
**Not fired after SA190:** the two current boundaries share one declared obligation inventory, and
their different actions are deliberate; no durable coordinator or cross-store erasure job exists.

**Problem:** Last-owner safety and the cross-domain obligation inventory are structural, but the
actions for removing an organization — reconciling billing, deleting tenant rows, invalidating
caches, and writing a tombstone — are still orchestrated by whichever boundary runs. The two
existing boundaries intentionally discharge different subsets without a durable coordinator.

**Evidence (census of org-lifecycle deletion boundaries, re-verified this pass):**

| Obligation | Account-delete view (`auth/views.py::AccountDeleteView`) | `purge_organization` |
|---|---|---|
| Last-owner guard | ✅ `AccountDeleteView._get_blocking_orgs_for_deletion` via the one predicate | n/a (whole org) |
| Reconcile Stripe subscription | ✅ outside the deletion transaction | Refuses current Stripe-backed subscriptions and active checkout reservations under the organization-keyed provider advisory mutex; elapsed reservations are reconciled with Stripe before the transaction, local finalization uses the organization-row lock, and only provider-confirmed expiry is purgeable |
| Delete tenant rows | Deliberate skip recorded because the organization survives | ✅ marker-derived `_delete_owned_rows` |
| Invalidate social caches | Deliberate skip recorded because the organization survives | ✅ `_clear_social_cache` |
| Tombstone | Deliberate skip recorded because the organization survives | ✅ after the organization row is removed |

`cancel_current_subscription` has exactly two callers:
`billing/views.py::CancelSubscriptionView.post` and
`auth/views.py::AccountDeleteView._cancel_personal_org_subscriptions`. The last-owner predicate is
defined once and consumed at five callsites: the locked model delete, the `pre_delete` receiver, two
organization views, and `AccountDeleteView._get_blocking_orgs_for_deletion`.

**Counter-evidence:**

- **No billing delete hooks.** Searched billing for `pre_delete`/`post_delete` receivers or
  model-level `delete()` hooks; found none.
- **The live-subscription precondition is enforced and documented.** The purge and dry-run paths
  refuse current Stripe subscriptions and active checkout reservations before deletion.
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

**Steelman:** the two boundaries have genuinely different intents — account deletion removes a
*person* and deliberately retains organization data, while purge is an operator's hard teardown.
Network calls inside Django signals would be worse than explicit orchestration, and a coordinator
built before a real tenant exists is premature.

**Correct shape:** the obligations for removing an organization — and for removing a person from one
— are declared once, each by the domain that owns it, and every boundary discharges the same set
idempotently.

**Do-nothing cost:** bounded until real tenants exist; after SA153 the first divergence is a
retention or billing incident on a real customer, diagnosed by hand.

**Options:**

1. **An explicit organization-removal coordinator** with idempotent domain contributors (billing
   cancel, row purge, cache invalidation, tombstone), called by both the account view and purge.
2. **Domain-local safeguards:** billing refuses deletion of a row with a live Stripe id, with an
   outbox record reconciling. Stronger against bypass; network effects complicate transactions.
3. **Deletion as a durable job.** Strongest recovery; excessive before multi-store erasure exists.

**Recommendation:** Keep the completed shared obligation contract and last-owner model/signal
backstop. Adopt option 1 when another destructive boundary or durable-erasure requirement fires the
coordinator trigger; use option 3 only when recovery across multiple external stores is required.
· **Size:** `M` · **Reversibility:** `two-way door` — the coordinator is an internal seam; both
callers can be reverted to inline orchestration without transforming state.

---

## Change-cost probe

**Probe A — SA192: style one more module's Django pages**, measured against `4a8fb649`, which did
exactly this for three modules:

1. `src/.../static/<module>/<module>.css` — new stylesheet.
2. `src/.../templates/<module>/base.html` — restyled base.
3. Each leaf template's `extends`/block edits (2–4 files).
4. `tests/templates/base.html` — a stub base for the test settings.
5. `tests/test_templates.py` — a per-module rendering suite (~75–80 lines).

**Verdict: exonerates the architecture, flags a cleanup.** The per-module cost is real but
*correctly* module-local: `publish_module.py` splits with `--prefix=quickscale_modules/<name>`, so
each module must carry its own styling and its own tests to remain self-contained after the split.
What is not justified by that constraint is that the three `tests/templates/base.html` stubs are
**byte-identical** (md5 `2902eaa7…`) while a sanctioned commons already exists and is already used
by module tests — `tests_shared/` is imported by six module suites (`blog`, `crm`, `social`,
`forms`, `listings`, `orgs`), including the three this commit touched. So the subtree-split argument
that would justify the copies is contradicted by the modules' own existing imports. This is
ticket-shaped (extract the stub, point three test settings at it) and therefore not a finding, but
SA192 will replicate the copy nine more times if it is not done first.

**Probe B — add one project-owned tenant child table** (re-measured after SA190):

1. The project model: `tenant_org_fk()` plus `TenantManager()` and `TenantManager(super_scope=True)`.
2. A project migration calling `apply_force_rls()`, plus `add_composite_child_fk()`.
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
- **One interaction now live:** the closed credential-contract derivation touches the backups
  credential variables that `dr_engine/orchestration.py:2144-2150` validates, and watch item W3
  notes the DR `pg_dump`/`pg_restore` contract's dependence on two independently-pinned PostgreSQL
  majors. Closing rank 1 made the backups credential path more exercised, which makes W3's trigger
  more likely to fire.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed.** Ambient `TenantManager` scoping plus
  restricted-role `FORCE RLS`. A boot guard rejects a `rolbypassrls`/`rolsuper` runtime role, and
  `_check_quickscale_mode()` runs before the privileged exemption. Marker-derived membership and
  the W003/W004 isolation checks and marker-derived purge are what keep project-owned tables safe.
- **Last-owner safety is a model/signal backstop, not a view check.** One predicate serves five
  callsites, plus a `pre_delete` receiver that catches direct ORM deletes. The future coordinator
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
- **The privileged-command contract is now exact, minimal and cross-checked.** `37987df9` retired
  the third sanctioned command, leaving `{migrate, createcachetable}` declared in three frozensets
  plus the launcher, held equal by `test_privileged_command_contract.py`, with a regression proving
  `start.sh` refuses the retired argv. Reducing a sanctioned set and gating the reduction is the
  right direction of travel.
- **Runtime role provisioning is one contract with many renderings.** `98b6c455` made
  `runtime_database.py` the single declaration of the `quickscale_runtime` role name, attributes
  and grants, rendered into `db/init.sql.j2`, `start.sh.j2` and `OPERATIONS.md.j2` and imported by
  Railway deploy. This is the precedent the credential-contract derivation followed.
- **Module identity and the CI environment are derived, not pinned.** Every consumer shells out to
  `module_discovery.py --list-modules` and hard-fails on drift; `provision_ci_postgres.sh` derives
  its module list. Co-change measurement supports this: modules barely change together, so the
  subtree boundary is real rather than nominal.

## Watchlist

- **W1 — The privileged-command set now has five declaration stations, and the cross-station test
  covers four.** `beta_migration.py:3663` declares `_REQUIRED_RUNTIME_COMMANDS` with its own
  `frozenset({"migrate", "createcachetable"})` and asserts at `:3636-3644` that an effective
  project's `_KNOWN_PRIVILEGED_COMMANDS` equals it exactly; `test_privileged_command_contract.py`
  lists only `orgs/apps.py`, `development_commands.py` and `production.py.j2`, plus `start.sh.j2`.
  *Doesn't qualify:* the copy is held honest indirectly — `check-beta-migration-smoke` generates a
  current-vintage project and runs the validator over it, so a template-side change to the set
  fails that gate. Every station fails closed. **Trigger:** a sixth station, a third sanctioned
  command, or a donor vintage whose sanctioned set legitimately differs from the monorepo's — the
  exact-equality assertion would block that migration. **Partially fired** (station count 4 → 5);
  carried rather than promoted because the smoke gate contains it. *Needs runtime confirmation that
  the smoke gate reaches this validator.*
- **W2 — Two independent filesystem-lock implementations** (`advisory_lock.py`, 514 lines;
  `dr_engine/_lock.py`, 298 lines; re-verified unchanged, and no third `fcntl`/`flock`/`O_EXCL`
  implementation exists). *Doesn't qualify:* both public contracts are preserved and the split is
  release-accepted. **Trigger:** a third implementation, divergent behaviour or platform support, or
  the contracts no longer preservable independently. **Not fired** — neither file changed this pass.
- **W3 — Hand-pinned residue inside derived provisioning** (merged with the former SA92 item, which
  has the same shape). `provision_ci_postgres.sh:96` re-pins `== 12`, `:93` re-pins `!= teams`, and
  `:15` `POSTGRES_MAJOR=18` duplicates the generator's `runtime_pins.py`; the SA92 guardrail's
  discovery tuple names 10 migration-bearing modules. *Doesn't qualify:* all fail loudly, and the
  two PostgreSQL values are arguably separate owners. **Trigger:** a thirteenth module, `teams`
  graduating, another migration-bearing module, or the backups DR `pg_dump`/`pg_restore` contract
  depending on the two majors agreeing. **Not fired** — census re-run this pass: the universe is 12,
  and the tuple's 10 names match the 10 modules with migration directories exactly.
- **W4 — `trigger_inputs` is a legacy name for an exact E2E allowlist partition**
  (`check_gate_parity.py:326,512-518`). *Doesn't qualify:* the check is exact and the contract is
  spelled out in every diagnostic. **Trigger:** any context skipping a gate on the basis of
  `trigger_inputs`. **Not fired.**
- **W5 — The beta-migration ownership taxonomy is hand-authored, and only its membership is
  gated.** 46 module-level literal tables totalling 308 entries in `beta_migration.py` encode the
  shape of generated artifacts the generator itself owns; `test_taxonomy_classifies_every_emitted_template`
  enforces that all 117 emitted paths are classified and the reverse test forbids stale entries, but
  nothing checks that the *disposition chosen* is right, and 47 paths (40%) are classified solely as
  `INTENTIONALLY_UNMANAGED` — the cheapest way to satisfy the gate.
  `test_intentionally_unmanaged_entries_have_documented_rationale` asserts only that the tuple is
  non-empty while its own docstring states the real obligation (a rationale in `decisions.md`), and
  the doc mirror has already drifted by one entry (`frontend/src/test/validateQuickScaleSeam.test.ts`
  is in the tuple but in no category of `generated_file_ownership.md`). *Doesn't qualify:*
  `decisions.md` § Release scope safeguards **explicitly withholds authorization** for "typed
  disposition metadata, ownership-manifest generation, taxonomy derivation, or changes to existing
  file dispositions", so this is a recorded deferral rather than an unrecognised commitment; the
  list is also shrinking (87 → 78), and the measured cost of adding an emitted path is only two
  stations (`31a93768`). **Trigger:** the decision record being lifted; a second drift between the
  tuple and `generated_file_ownership.md`; or SA191 discovering that a disposition was wrong in
  practice rather than merely unverified.

## Reconciliation log

- 2026-09-23 — `module-env-contract-hand-wired`: **closed**. The generated `.env.example`
  contract renders from each module's declared `*_env_var` options in one place; the static
  template copy and the three hand-written render/splice triples are retired, and a conformance
  check fails when a declaration has no placeholder. `storage` and `backups` gain placeholders on
  the next `apply` — a deliberate behavior change. With rank 1 closed,
  `deletion-invariants-per-boundary-reimplementation` is the only live finding and takes rank 1;
  closure archived in CHANGELOG.
- 2026-09-18 — `deletion-invariants-per-boundary-reimplementation`: **still-open**. SA190 made the
  obligation inventory structural and completed marker-derived, FK-ordered purge, retiring the
  former purge-membership dependency whose closure is archived in CHANGELOG. Boundary-local
  execution remains; horizon stays 6–18 months and rank is now 2.
- 2026-09-17 — `module-env-contract-hand-wired`: **new**. Opened at rank 1; the only finding with a
  live defect rather than a scheduled trigger.
- 2026-09-17 — Prior watch item *"Privileged-command set has four independent enforcing stations"*:
  carried as **W1**, trigger **partially fired** — a fifth declaration
  (`beta_migration.py:3663`) exists outside the cross-station test. Not promoted: the
  beta-migration smoke gate contains the drift. Separately, `37987df9` **resolved** the prior
  pass's noted third sanctioned command by retiring it, and gated the retirement.
- 2026-09-17 — Prior watch item *"Two independent filesystem-lock implementations"*: carried as
  **W2**, trigger **not fired** — neither file changed; no third implementation exists.
- 2026-09-17 — Prior watch items *"Hand-pinned residue inside the provisioning derivation"* and
  *"SA92 migration-squash discovery tuple"*: **merged** into **W3** (same shape: hand-pinned
  residue that fails loud). Both triggers **not fired** — census re-run: 12 modules, and the SA92
  tuple's 10 names match the 10 modules with migration directories.
- 2026-09-17 — Prior watch item *"`trigger_inputs` is a legacy name"*: carried as **W4**, trigger
  **not fired**.
- 2026-09-17 — New watch item **W5** opened for the beta-migration ownership taxonomy, explicitly
  bounded by `decisions.md` § Release scope safeguards.
- 2026-09-17 — Prior *"Questions that would change the ranking"* recorded no open question. Two new
  questions opened this pass.
- 2026-09-17 — No red flags this pass: no committed credential, unauthenticated surface, injection
  path or imminent data-loss condition was encountered. The `str`-vs-`bytes` `compare_digest`
  defect that would have qualified was found already **fixed** in this delta (`adc753c6`), and its
  census (2 of 2 hand-rolled verifiers affected, both corrected) is recorded in the enforcement
  census instead.

*Lenses scanned with no qualifying finding this pass: observability and operability; API/contract
stability of the CLI surface; performance and scalability; concurrency and state isolation (beyond
W2); build, release and supply chain, including the build-as-trust-boundary lens (single lockfile,
exact lockstep pin, maintainer-only devtools excluded from the publish list — all sound); failure
domains and recovery; cost and resource economics (no metered per-unit cost driver — the generator
runs on the maintainer's and user's own machines); data lifecycle, privacy and residency (no
regulatory obligation is declared in-repo, and generated projects own their own data); change
safety and rollout (the contract-vintage boundary shipped this pass is the right shape); and
contributor model and cognitive load (single maintainer — the lens is inert, and bus-factor 1 is a
property of the project, not a fixable structural decision). Data/state model, trust and
authorization, module cohesion, design conflicts, governance and gate architecture, and the
code-generator archetype lens produced the ranked findings above.*

Closed findings, retired watch items, historical option records, and cross-reference migrations are
archived in [CHANGELOG.md](../../CHANGELOG.md) and version control rather than repeated here.
