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
    `test_templates.py` suites. Measured as probe B below.
  - `6a8e0189` "derive expected test versions" — test-only, replaces hardcoded version literals
    with derivation. Sound.
  - `adc753c6` "reject malformed authentication headers" — a real defect class, not a rename:
    `secrets.compare_digest`/`hmac.compare_digest` were called on `str`, which raises `TypeError`
    on non-ASCII input. Census: **2 of 2** hand-rolled shared-secret verifiers in the tree had the
    identical bug (`blog/views.py:351`, `notifications/services.py:752`); both fixed in this one
    commit. Billing's third verifier delegates to the Stripe library and was never affected.

**Growth direction (planning surface, authoritative).** `roadmap.md` scheduling table: the critical
path is **SA191 → SA153** on track 1 — migrate `bap-web` onto current QuickScale with the verified
migration tooling, then build the first property portal as a project-owned extension. Track 2's next
ticket is **SA192** (style the module-shipped Django pages). Track 3's is **SA190** (derive the purge
plan and share organization-removal obligations). All three tracks are "truly green". Two changes
since the last pass matter for ranking: the roadmap now records that **"project-owned tenant tables
no longer add a dependency to the portal"**, decoupling SA153 from SA190; and every SA190-bearing
row carries release requirement **Deferred**.

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

**Coverage and residual risk.** This is static analysis of source at `98b6c455`; nothing was
executed. Three claims want runtime confirmation and are marked at their finding: that a generated
project with `storage` or `backups` enabled really does ship a `.env.example` with no placeholder
for its declared credential variables (rank 1); that purging an org owning a project-owned tenant
row still fails on `PROTECT` (rank 2); and that the beta-migration smoke gate is what actually keeps
`beta_migration.py`'s privileged-command copy honest (watchlist W1). A reader must **not** conclude
from this document's silence that `contracts/resolvers.py`, the manifest resolver, or the dr_engine
internals are sound — they were not read at depth this pass, and no pass has read them yet.

## Enforcement census

| Invariant | Enforcement | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural | unchanged |
| Tenant-model universe is classified, refreshed, and purged | Classification and FORCE-RLS refresh are marker-derived; 21-entry `_DELETE_SPECS` remains the purge membership list; `TENANT_TABLE_REGISTRY` is a parity oracle only | Classification/refresh structural; **purge closed to project-owned tenant models** | unchanged — re-verified 21 entries by AST; rank 2 |
| **Module-declared credential env vars reach the generated `.env.example`** | Three hand-written render/sync triples in `apply_command.py` + three named core steps | **Convention — 3 of 5 declaring modules covered** | **new row — rank 1** |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` boot guard; exemption set declared across fail-closed stations | Guard structural; duplicated declarations cross-checked | unchanged |
| Restricted runtime role exists with the right grants | `runtime_database.py` declares the role, attributes and grants; generator renders them into `db/init.sql.j2`, `start.sh.j2`, `OPERATIONS.md.j2`; Railway deploy imports the same name | Structural — one role name, one statement set | **strengthened** (`98b6c455` unified provisioning) |
| Privileged Django command set | Three `frozenset` stations + `start.sh.j2`, held equal by `test_privileged_command_contract.py`; a **fifth** copy in `beta_migration.py:3663` is outside that test but exercised by the smoke gate | Gated, exact-member | **set reduced to two members** (`37987df9`); **station count 4 → 5** — W1 |
| Template ↔ upgradable-code contract compatibility | `project_contract` in state plus declared module/CLI vintages; `status` reports gaps; `update`/`apply`/Railway deploy enforce them | Structural at mutation boundaries | unchanged |
| Every emitted path has a migration disposition | Generator-derived conformance test over a hand-authored taxonomy; bidirectional (no stale entries) | Membership gated both ways; **disposition choice and its documented rationale are not** | unchanged — **census: 117 emitted paths; 47 (40%) classified solely as `INTENTIONALLY_UNMANAGED`**; list shrank 87 → 78 — W5 |
| Cross-domain deletion obligations are discharged | Last-owner predicate + locked model delete + `pre_delete` receiver; live-subscription refusal in purge; remaining obligations inline per boundary | Last-owner and live-subscription refusal structural; **rest convention, split across two boundaries** | unchanged — rank 3 |
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
| 1 | `module-env-contract-hand-wired` | now | High | M | two-way door | The generated `.env.example` credential contract is hand-wired per module across four stations in two packages, although `module.yml` already declares the variable names — and two of the five declaring modules get nothing. |
| 2 | `org-model-universe-hand-enumerated` | deferred (SA190) | High | S | two-way door | Purge membership remains a literal `_DELETE_SPECS` list inside module source, closed to project-owned tenant tables even though classification and policy refresh are marker-derived. |
| 3 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months | High | M | two-way door | Two org-deletion boundaries exist and each discharges a different subset of the cross-domain obligations. |

Rank 1 leads because it is the only finding with a **live defect today** rather than a scheduled
trigger: `storage` and `backups` ship declared credential variables that never reach the generated
`.env.example`. Ranks 2 and 3 are both owned by SA190, whose roadmap release requirement is
**Deferred**; rank 2's horizon moves from `now` to `deferred` this pass because the roadmap
explicitly decoupled SA153 from project-owned tenant tables.

## Machine-readable finding index

```yaml
- id: module-env-contract-hand-wired
  title: Module-declared credential env vars are hand-wired into .env.example
  horizon: now
  confidence: high
  size: M
  reversibility: two-way-door
  status: open
  depends_on: []
- id: org-model-universe-hand-enumerated
  title: Purge membership remains closed to project-owned tables
  horizon: deferred
  confidence: high
  size: S
  reversibility: two-way-door
  status: open
  depends_on: []
- id: deletion-invariants-per-boundary-reimplementation
  title: Organization deletion obligations are split across two boundaries
  horizon: 6-18-months
  confidence: high
  size: M
  reversibility: two-way-door
  status: open
  depends_on: [org-model-universe-hand-enumerated]
```

---

## Finding — Module-declared credential env vars are hand-wired into `.env.example`

**ID:** `module-env-contract-hand-wired` · **Horizon:** now · **Confidence:** High ·
**Size:** M · **Context dependence:** `wrong-regardless`

**Rank rationale:** blast radius is the credential-setup surface of every generated project that
enables a credential-bearing module, times the coordination tax on every future one. Likelihood is
not a forecast — the trigger has already fired twice, silently, in shipped modules.

**Problem:** `.env.example` content is treated as bespoke Python per module rather than as a
projection of the module manifest, even though `module.yml` already declares each credential
variable by name and the manifest layer already has a derivation mechanism for exactly this kind of
wiring.

**Evidence** (all anchors established this pass):

- **The manifest already declares the contract.** `notifications/module.yml` declares
  `resend_api_key_env_var` (default `RESEND_API_KEY`) and `webhook_secret_env_var`, each with a
  type, default, `django_setting` and description, alongside a `derivation.wiring_projections`
  block that derives Django app wiring generically.
- **Census — modules declaring `*_env_var` options vs. modules with an `.env.example` sync:**

  | Module | `*_env_var` options declared | Managed `.env.example` block |
  |---|---:|---|
  | analytics | 4 | ✅ `_sync_analytics_env_example` |
  | billing | 6 | ✅ `_sync_billing_env_example` |
  | notifications | 2 | ✅ `_sync_notifications_env_example` |
  | **storage** | **2** (`access_key_id_env_var`, `secret_access_key_env_var`) | **❌ none** |
  | **backups** | **2** (`remote_access_key_id_env_var`, `remote_secret_access_key_env_var`) | **❌ none** |

  The two uncovered modules are precisely the two whose variables are object-storage credentials.
- **Four stations per covered module, across two packages.** `apply_command.py:1459/1498/1540`
  (notifications), `:1553/1592/1637` (analytics), `:1650/1694/1725` (billing) — a
  `_render_*_block`, a `_sync_*_impl`, and a thin wrapper each; plus a named core step
  (`apply/steps/env_sync.py:60,92,124`) re-exported through `apply/steps/__init__.py` and
  `apply/__init__.py`. The three `_sync_*_impl` bodies are the same marker-splice algorithm —
  read, split on a start/end marker pair, replace-or-append, write — copied verbatim three times,
  varying only in marker text, resolver, and log message.
- **A fourth copy of the same knowledge.** `.env.example.j2:49-53` statically hardcodes
  `RESEND_API_KEY=` and `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=` under the same markers the
  apply step splices on — so notifications' variable names exist in the manifest, in
  `module_options.py` `DEFAULT_*` constants, in the template, and in the render function.
- **The gap is load-bearing, not cosmetic.** `dr_engine/orchestration.py:2144-2150` *requires*
  `remote_access_key_id_env_var` and `remote_secret_access_key_env_var` when
  `target_mode is private_remote`, and `module_options.py:73-76,221` carries their `DEFAULT_*`
  constants. A user enabling private-remote backups therefore hits a validation error naming a
  variable their generated `.env.example` never mentioned.

**Counter-evidence:** searched for any other writer of `.env.example` across
`quickscale_cli/src`, `quickscale_core/src` and the template tree — there is none besides the three
triples and the static template block. Searched `quickscale_core/tests`, `quickscale_cli/tests` and
`scripts/` for a gate asserting that every declared `*_env_var` option reaches `.env.example`;
the suites that touch env sync (`test_apply_deps_and_env_sync.py`, `test_apply_step.py`,
`test_apply_command_extended.py`) exercise the three implemented steps and do not assert coverage
over the manifest set. Checked whether storage/backups reach `.env.example` through the manifest
renderer, `module_wiring_manager`, or a module-owned template — they do not. Checked
`decisions.md` § Release scope safeguards for a recorded decision deferring this, as there is for
taxonomy derivation; there is none, so this is a gap rather than an accepted trade-off.

*Runtime confirmation:* generate a project with `storage` and `backups` enabled, run
`quickscale apply`, and grep the resulting `.env.example` for `AWS_ACCESS_KEY_ID` and the backups
remote key variables.

**Why it compounds:**

- Every future credential-bearing module needs a fourth-station triple plus two re-export edits, or
  it silently ships without placeholders — measured at **8 stations** in probe A below.
- The marker-splice algorithm is copied three times, so any fix to it (encoding, idempotency,
  CRLF, a missing trailing newline) must be applied three times and will be applied to two.
- Already built on top: `analytics`, `billing` and `notifications` depend on the current block
  shape and its markers; `storage` and `backups` have shipped without it, so closing the gap is
  also a behaviour change for existing generated projects on their next `apply`.
- SA154's promotion inventory is a list of further module capabilities built on this pattern.

**Detection signal:** a generated project whose `.env.example` lacks a variable that the module's
`module.yml` declares — assert this in CI over the manifest set. Today the operator-visible
signal is a `BackupConfigurationError` naming `remote_access_key_id_env_var` on a project whose
`.env.example` never mentioned it.

**Steelman:** the three implemented blocks carry genuinely bespoke prose — notifications explains
Resend domain verification, billing explains Stripe key handling — and that guidance is not
derivable from a type and a default. Rendering it generically would either lose the guidance or
push prose into `module.yml`, which is a config schema and not a docs surface. `storage` and
`backups` may also have been judged not to need placeholders because their variables are AWS
conventional names that users already set. Do not fix this if the maintainer's position is that
`.env.example` is curated documentation rather than a derived contract — but in that case the two
uncovered modules still need a deliberate decision recorded, not silence.

**Correct shape:** the set of environment variables a generated project must define is derived from
the module manifests that declare them, in one place, so that a module cannot declare a credential
variable and have it silently absent from the generated project's environment contract.
Module-specific prose, if kept, hangs off that derived set rather than replacing it.

**Do-nothing cost (next ~12 months):** two shipped modules keep handing users a runtime error
instead of a placeholder; every new credential-bearing module is an ~8-station edit across two
packages with a coin-flip chance of being skipped, as it was twice; and the triplicated splice
algorithm means any correctness fix to it is applied inconsistently.

**Options:**

1. **Derive the block from the manifest.** One generic renderer consumes the declared
   `*_env_var` options for every enabled module, emitting one managed block per module under the
   existing marker convention; optional per-module prose comes from a manifest `description` or a
   single optional hook. Removes the compounding and closes the storage/backups gap in the same
   change. Largest edit, but it deletes three triples and four re-export stations.
2. **Keep the triples, add a coverage gate.** Leave the hand-written blocks and add a conformance
   test asserting that every `*_env_var` option declared in any `module.yml` appears in the
   generated `.env.example`. Small and safe; it converts a silent gap into a loud one, but leaves
   the 8-station tax and the triplicated algorithm in place — a gate that holds a copy honest
   rather than removing the copy.
3. **Accept and document.** Record in `decisions.md` that `.env.example` is curated prose, not a
   derived contract, and that `storage` and `backups` are deliberately excluded; add the rationale
   to `generated_file_ownership.md`. Revoked the moment a module ships a non-conventional
   credential variable name.

**Recommendation:** **Option 1**, with option 2's gate landing first as a cheap tripwire. The
manifest already carries the declarations and `derivation.wiring_projections` is the precedent for
projecting them, so this is the system's own stated architecture applied to a surface that escaped
it — not a new abstraction. Doing option 2 alone leaves the tax that caused the gap.
· **Size:** `M` (one seam plus migration of three callers).
· **Reversibility:** `two-way door` — the change is confined to generation-time rendering under an
existing marker convention; a bad render is fixed by the next `apply`, and no user data or public
contract is transformed. The one edge to verify before shipping is that the new block is
byte-identical to the current output for the three covered modules, so existing projects see no
spurious diff.
· **First step:** add the coverage assertion over the manifest `*_env_var` set and let it fail for
`storage` and `backups` — that failing test is the specification for the renderer.

---

## Finding — Purge membership remains closed to project-owned tables

**ID:** `org-model-universe-hand-enumerated` · **Horizon:** deferred (SA190) · **Confidence:** High ·
**Size:** S · **Context dependence:** `wrong-for-now` (new domain — first project-owned tenant tables)

**Rank rationale:** blast radius is org teardown for the first production portal. Likelihood has
**fallen** this pass: the roadmap now records that project-owned tenant tables no longer gate SA153,
and SA190 carries release requirement Deferred, so the trigger is real but unscheduled.

**Trigger:** a project-owned or module tenant model is scheduled. **Still real, now deferred** —
SA153's acceptance still requires tenant-owned child tables with their own `organization_id` and
forced RLS, but `roadmap.md` § Ordering now states that project-owned tenant tables "no longer add
a dependency to the portal".

**Problem:** The organization purge plan treats the set of tenant models as a literal list inside
the orgs module's source and has no project-side extension seam, while the documented extension
model forbids editing module source.

**Evidence** (re-verified this pass unless noted):

- **`_DELETE_SPECS` is unchanged at 21 entries**, re-counted by AST at
  `purge_organization.py:65`, and is the whole purge universe via `_resolve_models` (`:216`).
  Only one commit touched the file since the last pass (`9828ba86`), and it added the
  live-subscription guard, not membership derivation.
- **Classification and policy refresh remain marker-derived** and therefore already see
  project-owned models: `tenancy.py` exposes `is_tenant_model`, `get_tenant_models`,
  `is_classified_in_registry` and `get_derived_registry_overview`, with the comment at `:1492`
  confirming `TENANT_TABLE_REGISTRY` "remains only as a parity-oracle target". `37987df9` rewrote
  the registry header to say runtime classification is marker-derived.
- **Purge is closed and order-dependent.** The organization row is removed with `_raw_delete`
  (`:452`) and `tenant_org_fk` is `PROTECT`, so purging an org that owns a project-owned tenant row
  fails on the database FK. Deletion order is the literal entry order (`:60-64` comment).
- **The extension boundary forbids the obvious workaround.** `implementation_contract.md` requires
  projects to extend modules through a project-owned extension app, never by editing module source,
  and any `_DELETE_SPECS` edit would have to survive every later `quickscale update` subtree pull.

**Counter-evidence:** re-searched `tenancy.py`, `checks.py` and `check_tenant_isolation.py` for a
project-side purge-membership hook added by the SA182/SA177 work — classification, policy refresh
and predicate verification all now accept project-owned models, but none of them feed purge.
Verified that isolation itself stays guarded without the literal (W003/W004 plus
`check_tenant_isolation` require `organization_id` and FORCE RLS for every marker-derived
`TenantManager` model), and that purge fails loudly rather than partially — which is what keeps
this a registration problem rather than an isolation leak.

*Runtime confirmation:* generate a project with `listings`, add an extension model subclassing
`AbstractListing`, and run `manage.py check_tenant_isolation --format json`; classification and
policy refresh should include it, while purging an organization that owns its row still fails.

**Why it compounds:** every project-owned tenant table needs a hand-chosen `_DELETE_SPECS` position
in module source, carried through every later module update, while classification and refresh see
the table for free — and SA154's inventory (saved searches, favorites, agent/office profiles,
tours) is a list of more tables on the same pattern. Probe C below measures 5 remaining stations.

**Detection signal:** `purge_organization` raising `IntegrityError` or `ProtectedError` while a
project-owned tenant row exists; hand edits under `quickscale_modules_orgs/` in a generated
project's git history.

**Steelman:** a closed purge list is default-deny — nothing is deleted unless a maintainer reviewed
its ordering, which is a real safeguard on a destructive operator command. With SA153 now decoupled,
deferring is a defensible scheduling call rather than an oversight. Do not fix if SA153 ships its
tables inside a first-party module.

**Correct shape:** purge membership is derived from the same marker-derived tenant-model set used by
classification and policy refresh, ordered from installed FK metadata, with documented overrides.
Any literal list is a monorepo-side cross-check over shipped modules, never the runtime authority.

**Do-nothing cost:** bounded while no project-owned tenant table exists; the day one ships, org
teardown is broken in production with a database-level error and the only in-contract fix is a
module release.

**Options:**

1. **Open `_DELETE_SPECS`** to a project-declared list merged in via a setting or AppConfig hook —
   small, keeps default-deny, but adds a hand-maintained station per table and leaves ordering manual.
2. **Derive purge membership from markers** — drive it from `get_tenant_models()`, order
   topologically from installed FK metadata with explicit overrides, and keep the literal as a
   monorepo parity test. Removes the compounding.
3. **Keep purge closed and require first-party modules for tenant tables** — contradicts the
   extension contract.

**Recommendation:** **Option 2**, as SA190 already scopes it. Preserve the ordered deletion and
last-owner safeguards, and prove a non-module tenant row can be purged safely.
· **Size:** `S` · **Reversibility:** `two-way door` — derivation can be reverted to the literal
without transforming any state, provided the literal is retained as the parity oracle.
· **First step:** make the literal the parity oracle in a monorepo test and let
`get_tenant_models()` feed the runtime plan.

---

## Finding — Organization deletion obligations are split across two boundaries

**ID:** `deletion-invariants-per-boundary-reimplementation` · **Horizon:** 6–18 months ·
**Confidence:** High · **Size:** M · **Context dependence:** `wrong-for-now` (production tenants /
compliance)

**Rank rationale:** blast radius is billing and data retention for real organizations, which SA153
is the first to create. Likelihood is moderate — both boundaries exist today, the production volume
does not.

**Trigger:** another account/organization deletion boundary. **Fired:** `purge_organization` is the
second boundary; SA190's roadmap title now explicitly pairs "derive the purge plan" with "share
organization-removal obligations", so the team has recognised it.

**Problem:** Last-owner safety is structural, but the other cross-domain obligations of removing an
organization — cancelling billing, deleting tenant rows, invalidating caches, writing a tombstone —
are orchestrated inline by whichever boundary happens to run, and the two boundaries discharge
disjoint subsets.

**Evidence (census of org-lifecycle deletion boundaries, re-verified this pass):**

| Obligation | Account-delete view (`auth/views.py:56-240`) | `purge_organization` |
|---|---|---|
| Last-owner guard | ✅ `:164` via the one predicate | n/a (whole org) |
| Cancel Stripe subscription | ✅ `_cancel_personal_org_subscriptions`, `:172-240` | Refuses current Stripe-backed subscriptions (`:570`); cancellation stays out of band |
| Delete tenant rows | ❌ personal org and its rows survive (membership `CASCADE`, `orgs/models.py:118-122`) | ✅ `_delete_owned_rows`, `:518` |
| Invalidate social caches | ❌ | ✅ `_clear_social_cache`, `:542` |
| Tombstone | ❌ | ✅ `:452` |

The last-owner predicate is defined once at `orgs/models.py:169` and consumed at five callsites
(`orgs/models.py:329`; `orgs/signals.py:66`; `orgs/views.py:808,1161`; `auth/views.py:164`) —
anchors re-resolved this pass; the prior pass's `models.py:165` is now `:169`.
`cancel_current_subscription` is defined at `billing/services.py:736` and has exactly two callers
(`billing/views.py:311`, `auth/views.py:225`).

**Counter-evidence:** re-searched billing for `pre_delete`/`post_delete` receivers or model-level
`delete()` hooks that would discharge cancellation structurally — there are none. Confirmed the
live-subscription precondition is now enforced and documented in both the purge and dry-run paths,
which closes the money-path exposure without unifying the remaining obligations. Confirmed
last-owner safety is a model/signal backstop rather than a view check, so this finding is scoped to
cross-domain obligations only.

**Why it compounds:** each new domain obligation (SA153's property galleries in media storage, CRM
inquiries, SA154's saved searches and alerts) must be added to whichever boundaries its author
remembers; each new boundary — bulk admin, GDPR erasure, `teams` — copies a subset; and the subsets
have already diverged.

**Detection signal:** a new organization-deletion boundary that omits the live-subscription refusal;
memberless personal organizations still holding tenant rows; stale `social` cache entries after
account deletion.

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

**Recommendation:** **Option 1**, designed together with rank 2's purge derivation so membership and
obligations come from one place. Preserve the last-owner model/signal backstop — it must not be
replaced by the coordinator.
· **Size:** `M` · **Reversibility:** `two-way door` — the coordinator is an internal seam; both
callers can be reverted to inline orchestration without transforming state.
· **First step:** fold the shipped live-subscription refusal and the remaining purge obligations
into a named list shared with the account view.

---

## Change-cost probe

**Probe A — add one credential-bearing module option that needs an `.env.example` placeholder**
(the shape `storage` and `backups` already have, and the shape SA154 promotions will have):

1. `module.yml` — declare the `*_env_var` option.
2. `contracts/module_options.py` — `DEFAULT_*` constant, resolver entry, `__all__`.
3. `apply/steps/env_sync.py` — `step_<module>_env_sync` plus `__all__`.
4. `apply/steps/__init__.py` — import and `__all__`.
5. `apply/__init__.py` — re-export and `__all__`.
6. `apply_command.py` — `_render_<module>_env_example_block`.
7. `apply_command.py` — `_sync_<module>_env_example_impl` (the copied marker-splice body).
8. `apply_command.py` — `_sync_<module>_env_example` wrapper and its call site.

**Verdict: finding evidence** (rank 1). Eight stations across two packages for a declaration the
manifest already carries, with no gate detecting omission — and the omission has already happened
twice.

**Probe B — SA192: style one more module's Django pages**, measured against `4a8fb649`, which did
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

**Probe C — SA190: add one project-owned tenant child table** (carried, re-measured):

1. The project model: `tenant_org_fk()` plus `TenantManager()` and `TenantManager(super_scope=True)`.
2. A project migration calling `apply_force_rls()`, plus `add_composite_child_fk()`.
3. A child boundary test on the `test_rls_boundary.py` pattern.
4. **Module source:** a `_DELETE_SPECS` entry at a hand-chosen FK position.
5. Carry that change through every later `quickscale update` of `orgs`.

**Verdict: finding evidence** (rank 2), unchanged at 5 stations. Classification, policy refresh and
predicate verification now have an extension path; purge membership remains in vendored module
source.

## Fix order and interactions

Rank 1 is **independent** of ranks 2 and 3 — it touches generation-time wiring in
`quickscale_cli`/`quickscale_core`, while the others live in the `orgs` module — so it can run in
parallel on a different track. That matters because ranks 2 and 3 are both owned by SA190 on
track 3, and rank 1 naturally belongs to whichever track holds the CLI apply surface.

Ranks 2 and 3 must be designed together and land in that order: the coordinator (rank 3) needs a
membership set to iterate, and deriving that set is rank 2. Fixing rank 3 first would harden a
coordinator around the closed literal and force rework. Rank 3's `depends_on` records this.

One interaction to watch: rank 1's fix touches the backups credential variables that
`dr_engine/orchestration.py:2144-2150` validates, and watch item W3 notes the DR `pg_dump`/
`pg_restore` contract's dependence on two independently-pinned PostgreSQL majors. Closing rank 1
makes the backups credential path more exercised, which makes W3's trigger more likely to fire.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed.** Ambient `TenantManager` scoping plus
  restricted-role `FORCE RLS`, with a boot guard rejecting a `rolbypassrls`/`rolsuper` runtime role
  and `_check_quickscale_mode()` running before the privileged exemption. Marker-derived membership
  and the W003/W004 checks are what make project-owned models safe; keep them while SA190 derives
  purge membership.
- **Last-owner safety is a model/signal backstop, not a view check.** One predicate
  (`orgs/models.py:169`) serves five callsites, plus a `pre_delete` receiver catching direct ORM
  deletes. Rank 3's coordinator must not replace it.
- **The privileged-command contract is now exact, minimal and cross-checked.** `37987df9` retired
  the third sanctioned command, leaving `{migrate, createcachetable}` declared in three frozensets
  plus the launcher, held equal by `test_privileged_command_contract.py`, with a regression proving
  `start.sh` refuses the retired argv. Reducing a sanctioned set and gating the reduction is the
  right direction of travel.
- **Runtime role provisioning is one contract with many renderings.** `98b6c455` made
  `runtime_database.py` the single declaration of the `quickscale_runtime` role name, attributes
  and grants, rendered into `db/init.sql.j2`, `start.sh.j2` and `OPERATIONS.md.j2` and imported by
  Railway deploy. This is the precedent rank 1 should follow.
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

## Questions that would change the ranking

- **`module-env-contract-hand-wired`** — is `.env.example` intended as a *derived contract* or as
  *curated documentation*? If the latter is the maintainer's settled position, rank 1 collapses to
  option 3 (accept and document) plus a deliberate decision about `storage` and `backups`, and the
  finding leaves the list.
- **`org-model-universe-hand-enumerated`** — will `bap-web`'s property tables ship as
  project-owned extension models, or inside a first-party module? The second answer retires the
  finding outright; the first restores its `now` horizon.

## Reconciliation log

- 2026-09-17 — `org-model-universe-hand-enumerated`: **still-open**. Evidence re-verified
  (`_DELETE_SPECS` unchanged at 21 entries by AST). Horizon **downgraded `now` → `deferred`**:
  `roadmap.md` § Ordering now records that project-owned tenant tables no longer gate SA153, and
  SA190 carries release requirement Deferred. Rank moved 1 → 2.
- 2026-09-17 — `deletion-invariants-per-boundary-reimplementation`: **still-open**. Anchors
  re-resolved (`orgs/models.py:165` → `:169`; membership `CASCADE` `:116-120` → `:118-122`;
  purge helpers now at `:518`, `:542`, `:570`). Now co-scheduled with rank 2 under SA190. Rank
  moved 2 → 3.
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
