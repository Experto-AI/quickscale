# Structural Autopsy: QuickScale

> **Status: In progress.** See [CHANGELOG.md](CHANGELOG.md) for resolved work and [docs/technical/roadmap.md](docs/technical/roadmap.md) for locked decisions.

---

## Orientation

A creator-led Django **project generator** (`quickscale plan` → `quickscale apply`) plus ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated apps via git subtree and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core`.

**Deployment context.** Generated apps run WSGI/Gunicorn, single Railway project, shared Postgres 18. No existing users; clean-break rule (no back-compat, no migration path). Development via parallel worktree tracks (`wt-track1/2/3`).

---

## Ranked findings

Remediation plan: [roadmap.md → Structural Autopsy Remediation](docs/technical/roadmap.md#structural-autopsy-remediation-opened-2026-06-30). Each finding is decomposed into Adaptive Tier 1–2 tasks (`SAn.m`), dependency-ordered and assigned to parallel tracks 1/2/3.

| # | Finding | Horizon | Confidence | Remediation tasks |
|---|---------|---------|------------|-------------------|
| 1 | Tenant-isolation correctness is a hand-replicated per-model ritual; its only enforcement (the conformance gate) is scoped to `quickscale_modules_*` and does not reach the user-authored models that generated projects exist to host | now / 6–18mo | High | SA1.1, SA1.2, SA1.3, SA1.4, SA1.5 |
| 2 | The master isolation switch fails open: an unset `RUNTIME_DATABASE_URL` silently connects under a BYPASSRLS superuser role, and the boot guard that catches it is gated to `saas` + `DEBUG=False` | now (latent) | High | SA2.1, SA2.2 |
| 3 | No single source of truth for the isolation contract — the two authoritative docs already describe a weaker, different posture (and a different manager API) than the shipped code | now | High | SA3.1, SA3.2 |
| 4 | DB tenant context is primed per-statement by a connection-layer wrapper that opens a transaction around every autocommit tenant query | 6–18mo | Medium | SA4.1, SA4.2 |
| 5 | Module integration is a high-arity coordination tax mid-migration between an imperative per-module path and an incomplete declarative manifest layer | 6–18mo | Medium | SA5.1, SA5.2 |

---

## Two independent clusters (summary)

**Cluster A — the tenant-isolation contract has no single enforced source of truth (Findings 1, 2, 3, 4).** The isolation machinery is genuinely strong *inside the QuickScale repo* (FORCE-RLS on 21 models, composite FKs, restricted-role conformance proofs, an AF9 GUC-priming wrapper, a T1.18 boot guard). But the contract is defined and re-asserted in four unsynchronized places — prose in `decisions.md`, prose in `organizations.md`, the hardcoded `TENANT_TABLE_REGISTRY`, and a per-model copy-paste of the manager declarations — and the one mechanism that turns it from convention into invariant (the conformance gate) stops at QuickScale's own app prefix. The root is *where the contract lives*, not any single missing check.

**Cluster B — module/generator integration coupling (Finding 5).** Adding a module still re-pays a large, multi-file imperative wiring cost, while a declarative manifest/derivation layer is being built underneath it. The two coexist, and the migration is explicitly phased and partly deferred.

---

# Autopsy — 2026-06-30

This dated section is the full structural autopsy. Findings are ranked by blast radius × likelihood, most urgent first. The orientation summary above governs every severity and horizon call below.

**Read fully:** the orgs tenancy seam (`tenancy.py`, `current_org.py`, `managers.py`, `middleware.py`, `apps.py`), the conformance gate (`orgs/tests/test_tenant_table_conformance.py`), CRM/blog/listings model + admin layers, generated settings templates (`base.py.j2`, `production.py.j2`), and the authoritative docs (`decisions.md §multitenant`, `organizations.md`). **Sampled:** CLI module wiring (`module_config.py`, `module_commands.py`, `imperative_inventory.py`), DR engine boundary. **Skipped:** frontend theme source, analytics/notifications/storage internals, the test suites as test correctness (in scope only as architecture).

---

## Finding 1 — Tenant isolation is a hand-assembled per-model ritual, and its enforcement gate cannot see the user code that generated projects exist to host

**Rank rationale (blast radius × likelihood):** A miss is a silent cross-tenant data leak — the single failure the whole architecture is built to prevent — and the trigger (a customer adds a model to their generated app) is the *intended* extension workflow, not an edge case. Highest blast × high likelihood.

**Horizon:** `now` for first-party drift; `6–18 months` for the customer-extension leak once apps are sold and extended.

**Confidence:** High — verified directly in code (registry prefix filter, per-model declarations, subtree split scope).

**Context dependence:** `wrong-for-now` — dimension: *new domain / single→multi-tenant-product*. The product is being positioned (v0.86.0) as multi-tenant SaaS that customers extend; that is exactly when this bites.

**Problem:** The tenant-isolation contract for a model is a 6-to-10-artifact assembly (org FK, `objects`/`all_objects` managers, `base_manager_name`, an `enable_rls` migration, a `refresh_rls` migration, a composite-FK migration for child tables, a registry entry, an admin `get_queryset` override, serializer/service `all_objects` bypasses). A correct centralizing abstraction exists (`TenantModel`) but is not the enforced single way to declare a tenant model, and the conformance gate that backstops the copy-paste is scoped to QuickScale's own modules.

**Evidence:**
- `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:TenantModel` *does* centralize the whole contract correctly (org FK via `tenant_org_fk`, `objects = TenantManager()`, `all_objects = TenantManager(super_scope=True)`, `base_manager_name = "all_objects"`).
- But the two highest-churn content modules do **not** use it. `quickscale_modules/crm/.../models.py:29,67,95,…` are all `class X(models.Model)` re-declaring `organization`, `objects`, `all_objects`, `base_manager_name` by hand (lines 32–46, 70–87, …). `quickscale_modules/blog/.../models.py:115,159,230,278` likewise re-declare managers per model. CRM also bypasses the canonical `tenant_org_fk()` helper, hand-writing `models.ForeignKey(..., on_delete=models.PROTECT)`.
- The gate, `quickscale_modules/orgs/tests/test_tenant_table_conformance.py:37-43`, filters `apps.get_models()` to `QS_APP_PREFIX = "quickscale_modules_"`. `TENANT_TABLE_REGISTRY` (`tenancy.py:119-327`) is a hardcoded list of QuickScale's own 21 models.
- `.github/workflows/split-modules.yml` splits with `--prefix=quickscale_modules/<name>`, so the gate file *ships* into generated projects — but it asserts nothing about an app named `myproject.invoicing`.

**Why it compounds:** The architecture's stated justification for RLS is defense-in-depth: "a single missed filter leaks cross-tenant data" (`decisions.md §multitenant`), so the DB backstop catches app-layer mistakes. For first-party modules the gate makes that real. For **user-authored models** — the explicit "you own the code, extend it" path — there is no backstop and no gate: a customer who writes `class Invoice(models.Model)` with a default manager and no `enable_rls` migration gets a table with no RLS and an unscoped manager, and nothing fails. Every model the customer adds is an independent leak surface, and clean-break/no-migration means QuickScale cannot retrofit protection later.

**Correct shape:** Declaring a tenant-scoped model must be a *single* act that is impossible to do partially, and the invariant (org_id column + FORCE-RLS policy + scoped default manager + unfiltered base manager) must be verifiable by a check that is **generic over app label** and **runs in the generated project's own CI against the user's apps** — not a hardcoded list scoped to `quickscale_modules_*`.

**Trigger for urgency:** The first paying customer extends a generated app with their own tenant table — or a first-party module adds a model and someone forgets one of the migration steps (the CRM/blog hand-copy shows this is already the live pattern).

**Compounding factor:** Already built on top: 21 enrolled models across 6 modules, each carrying the hand-assembled contract; the admin layer (`crm/admin.py` ~15 `get_queryset` overrides), serializers, and services all manually route through `all_objects`. Any move to a single enforced seam must migrate all of them.

**Detection signal:** No signal today for user models — the leak is silent (RLS simply absent). Instrument: a generated-project CI check that walks *all* concrete models and fails if a tenant-scoped one lacks a FORCE-RLS policy in `pg_policies`; alert on any tenant table where `relforcerowsecurity = false`.

**Strongest counter-argument (steelman):** For first-party modules the gate is genuinely strong and the contract is consistent enough that the registry catches drift at PR time; QuickScale cannot run CI inside a customer's repo, so "no enforcement in user code" is arguably inherent to any generator. Don't fix if the product stays a thin starter customers rarely extend with new tenant tables. — The counter fails here precisely because the product's pitch *is* extension, and the architecture's own defense-in-depth claim is what's being voided for user code.

**Alternative solutions:**
1. **Make `TenantModel` the only way in + auto-managed RLS.** Mandate inheritance, and have a `post_migrate`/system-check + a shipped generic conformance check (auto-discovering tenant models by base class, not a hardcoded list) refuse to start / fail CI when a `TenantModel` subclass lacks its policy. *Effort: medium. Removes most compounding. Risk: requires migrating CRM/blog off hand-declarations.*
2. **Generic shipped conformance command.** Replace the QS-prefixed registry walk with a `manage.py check_tenant_isolation` that inspects every concrete model + `pg_policies` and ships as a generated-project CI gate. *Effort: medium-low. Catches user models. Doesn't stop the per-model ritual, only catches omissions.*
3. **Schema-level default deny.** A migration helper that enables FORCE-RLS on every table in the project's apps by default and requires explicit opt-out, inverting the "remember to add RLS" default. *Effort: high, most invasive, removes the most compounding; risk of breaking control-plane/system tables.*

**Preferred option + why:** (1)+(2) together. Mandatory `TenantModel` collapses the ritual to a single inheritance act for first-party and user code alike; a generic, base-class-driven conformance check that ships and runs in the generated project's CI is the backstop that makes the defense-in-depth claim true where it currently isn't. This fits the archetype (the contract travels with the code into user projects) and the maturity (first-party modules already mostly have the pieces).

**Migration path:** First cut — convert CRM and blog models to inherit `TenantModel` and delete the hand-copied manager/FK declarations, proving the base class can carry the full contract for the highest-churn modules before generalizing the gate.

---

## Finding 2 — The master isolation switch fails open: unset `RUNTIME_DATABASE_URL` silently runs under a BYPASSRLS superuser, and the boot guard is gated to `saas` + `DEBUG=False`

**Rank rationale (blast radius × likelihood):** Blast is total — every RLS policy across every module silently disables for all tenants at once. Likelihood is held down by the boot guard and the start.sh contract, but the guard has real coverage gaps, so this is high-blast × low-to-medium-likelihood.

**Horizon:** `now` (latent) — one misconfigured env var or `DEBUG=True` deploy away.

**Confidence:** High — the fallback and the guard's gating conditions are both verified in code/templates.

**Context dependence:** `wrong-regardless` for a shared-DB multi-tenant product; the fail-open direction on a security boundary is wrong independent of scale.

**Problem:** Isolation correctness hinges on the app connecting as a `NOBYPASSRLS` role, selected by an env var; the *absence* of that env var grants access (connects as the superuser `DATABASE_URL`, which has BYPASSRLS and silently voids all policies). The only structural catch fails open in solo mode, under `DEBUG=True`, and when `QUICKSCALE_MODE` is unset.

**Evidence:**
- `…/settings/production.py.j2:133-147` — `_runtime_db_url = config("RUNTIME_DATABASE_URL", default=None)`; only `if _runtime_db_url:` is `DATABASES["default"]` overridden to the restricted role. Unset → the superuser `DATABASE_URL` remains the default connection. `decisions.md §multitenant` states this plainly: "all RLS silently disables; fail open."
- `quickscale_modules/orgs/.../apps.py:_check_rls_role` returns early unless `QUICKSCALE_MODE == "saas"` (default `"solo"`) **and** `not settings.DEBUG`. A prod deploy with `DEBUG=True` both leaks *and* disables its own guard.

**Why it compounds:** Every module added to the isolation contract increases what this single switch protects, so the blast radius of a fail-open grows monotonically with adoption — the more successful the RLS rollout, the more catastrophic a silent bypass. The guard's mode/DEBUG gating means the protection does *not* grow with it.

**Correct shape:** The default connection role must be fail-closed: the app refuses to serve runtime traffic under a BYPASSRLS role regardless of `QUICKSCALE_MODE` or `DEBUG`, with `migrate` the single audited exemption. Access must require the restricted role's presence, not merely the absence of a misconfiguration.

**Trigger for urgency:** A Railway env var is dropped/renamed on redeploy, a staging box runs `DEBUG=True`, or a solo app is promoted to `saas` and the role swap is missed.

**Compounding factor:** All 21 enrolled models and their conformance proofs assume the restricted role at runtime; they all silently lose enforcement together under this fallback.

**Detection signal:** Add a startup assertion (independent of mode/DEBUG) that logs and refuses non-`migrate` boot when `rolbypassrls = true`; alert on any runtime process whose `current_user` has BYPASSRLS. Today there is no signal in solo/DEBUG paths.

**Strongest counter-argument (steelman):** The `start.sh` contract (set runtime URL for serving, unset only for `migrate`) is the real control, and solo mode is effectively single-tenant so a bypass there is low-stakes; gating the guard to `saas`+`DEBUG=False` avoids breaking local dev. — Reasonable, but "fail open when misconfigured" on the master switch is the wrong default for a security boundary, and `DEBUG=True`-in-prod is a common real incident.

**Alternative solutions:**
1. **Always-on boot guard** that fails closed on BYPASSRLS for every non-`migrate` start, with an explicit `QUICKSCALE_ALLOW_BYPASSRLS=1` escape hatch for intentional single-tenant ops. *Low effort, removes the gap, small risk of surprising local dev (mitigated by the escape hatch).*
2. **Require the restricted role explicitly** — make `RUNTIME_DATABASE_URL` mandatory in `saas` and raise on absence rather than falling back. *Low effort; shifts fail-open to fail-fast.*
3. **Single role with RLS, no superuser default** — provision the app's default connection as `NOBYPASSRLS` and use a separately-named privileged URL only for migrations. *Higher effort, best end state, removes the "absence grants access" shape entirely.*

**Preferred option + why:** (3) as the target, (1) immediately. Inverting so the privileged connection is the *named exception* rather than the default is the only shape where a missing env var fails closed; the always-on guard is the cheap stopgap that closes the DEBUG/solo holes now.

**Migration path:** First cut — drop the mode/`DEBUG` conditions in `apps.py:_check_rls_role` so the BYPASSRLS guard runs on every non-`migrate` boot.

---

## Finding 3 — The isolation contract has no single source of truth; the two authoritative docs already describe a weaker, different posture than the shipped code

**Rank rationale (blast radius × likelihood):** Blast is the whole contributor/module-author surface plus a maintenance tax on every future isolation change; likelihood is certain because the divergence already exists. High × high on a slower-moving axis than a live leak.

**Horizon:** `now` — the drift is present in the current tree.

**Confidence:** High — verified by direct comparison of docs vs. code.

**Context dependence:** `wrong-for-now` — dimension: *team / contributors*. With one author it's tolerable; the moment a second contributor or external module author follows the docs, it misleads.

**Problem:** The governing rule is "decisions.md is authoritative — always wins conflicts; update it first." But the isolation contract is specified in four unsynchronized places, and the two authoritative ones have diverged from reality on a security boundary, so the canonical guidance now describes a rejected/weaker design.

**Evidence:**
- `decisions.md §Multi-tenant SaaS Architecture` and `organizations.md` (lines 12, 31-32, 104, 169, 666-667) state RLS is "active for the **social module** (T1.15); others deferred." The code has **all 21 models** ENROLLED with live FORCE-RLS, composite FKs, and restricted-role proofs (`tenancy.py:119-327`, `test_tenant_table_conformance.py:984` asserts exactly 21).
- `organizations.md §F11.13b` documents a `TenantScopedManager` / `OperatorManager` / `.for_org(org_id)` API as the contract. The shipped API is `TenantManager(super_scope=bool)` auto-scoping via a `ContextVar` (`managers.py:15-48`); `.for_org()` does not exist, and `TenantScopedManager` survives only as a re-export alias in one module (`listings/managers.py:16`).
- `roadmap.md` "Open work" says *no open phases*, so the docs are presented as current, not mid-flight.

**Why it compounds:** Every future isolation change must be mirrored by hand across four artifacts (two prose docs, the registry, per-model code), and the drift demonstrates that mirroring is already failing. A new module author following `organizations.md` would build `.for_org()`-style app-layer scoping (the shipped managers auto-scope differently) or assume their module needn't enable RLS ("deferred"), reintroducing exactly the app-layer-only pattern `decisions.md` prohibits.

**Correct shape:** One artifact is authoritative and machine-checkable for the isolation contract (the registry + conformance gate are the natural candidate); prose docs reference/derive from it rather than restating it, so they cannot silently diverge.

**Trigger for urgency:** Second contributor or first external module author onboards; or an isolation change is made against the stale doc.

**Compounding factor:** Tied to Finding 1 — the same absence of a single enforced source is why both the gate's scope and the docs drifted. Fixing 1's "generic, base-class-driven gate as the contract" also gives 3 its single source.

**Detection signal:** A CI doc-lint that diffs the enrolled-model list / manager API names in `decisions.md`+`organizations.md` against `TENANT_TABLE_REGISTRY` and the actual manager classes, failing on mismatch.

**Strongest counter-argument (steelman):** This is "just stale docs" — editing prose is a ticket, not a structural change. — It rises above a ticket because the fix that *prevents recurrence* is structural: relocating the contract's source of truth so prose derives from code. Pure re-editing would drift again next release (it already has).

**Alternative solutions:**
1. **Generate the doc tables from the registry** (enrolled models, manager API) so prose can't diverge. *Medium effort; durable.*
2. **Demote the prose to pointers** — `decisions.md`/`organizations.md` link to the registry/gate as the contract and stop restating model lists. *Low effort; relies on discipline.*
3. **CI consistency gate** that fails when docs and registry disagree. *Low-medium; keeps prose but enforces sync.*

**Preferred option + why:** (1) with (3) as the guard. Generating the authoritative tables from the registry makes the code the single source of truth and matches the project's own "update the authoritative thing first" principle — except now "the authoritative thing" is executable.

**Migration path:** First cut — update `decisions.md §multitenant` and `organizations.md` to the shipped reality (21 models enrolled, `TenantManager`/`ContextVar` API), then wire the CI diff so they can't drift again.

---

## Finding 4 — DB tenant context is primed per-statement by a connection-layer wrapper that opens a transaction around every autocommit tenant query

**Rank rationale (blast radius × likelihood):** Blast is latency and connection-pool pressure across the shared DB (degrades all tenants together); likelihood scales with traffic and is real for the explicit shared-DB SaaS model, but the cost is overhead rather than incorrectness. Medium × medium.

**Horizon:** `6–18 months` — surfaces as the SaaS gains tenants and query volume.

**Confidence:** Medium — the code path is verified statically; the *magnitude* of overhead needs runtime confirmation (statement counts / pgbench under representative load).

**Context dependence:** `wrong-for-now` — dimension: *traffic / data volume*. Negligible at MVP scale, structural at SaaS scale.

**Problem:** Because the middleware (T1.20) deliberately no longer holds a request transaction or sets `SET LOCAL`, DB-level tenant context is established entirely by an execute-wrapper that, in autocommit mode, wraps **each** tenant statement in its own `transaction.atomic()` + `SET LOCAL`.

**Evidence:**
- `current_org.py:_make_priming_execute_wrapper` autocommit path (lines 474-482): `with transaction.atomic(using=conn.alias): _issue_set_local(...); return execute(...)` — a BEGIN / SET LOCAL / statement / COMMIT per query.
- `middleware.py:57-64` and module docstring: middleware "does NOT hold a request-long transaction or issue SET LOCAL."
- Generated settings set `conn_max_age=600` with **no `ATOMIC_REQUESTS`** (`production.py.j2:125,143`; absent in `base.py.j2`), so requests run in autocommit and hit the per-statement path.

**Why it compounds:** Every tenant ORM read becomes ≥2 statements plus a transaction round-trip; per-request query counts multiply directly into DB round-trips and short-lived transactions on a pooled, shared connection. The wrapper is installed on every `DatabaseWrapper` (`apps.py` via `connection_created`), so it is a connection-layer commitment that all modules inherit and that must be re-validated against RLS correctness if ever changed.

**Correct shape:** Tenant GUC priming should cost O(1) per transaction/connection-checkout, not O(statements) — primed once when context is established (e.g., at request scope or pool checkout) and reused, while preserving the fail-closed guarantee and avoiding request-long transactions.

**Trigger for urgency:** A latency-sensitive endpoint with many small queries (dashboards, list views with N related lookups) under real tenant concurrency; or moving to PgBouncer transaction pooling, which interacts with `SET LOCAL` semantics.

**Compounding factor:** The AF4 regression guard (no request-long transactions) and AF9/AF11 correctness proofs are all built on this per-statement model; changing it means re-proving RLS under the new priming point.

**Detection signal:** Per-request statement count ~2× query count; elevated `BEGIN`/`COMMIT` rate in `pg_stat_*`; transaction-per-statement visible in slow-query logs. Instrument statement counts per request in staging load tests.

**Strongest counter-argument (steelman):** `SET LOCAL` is an inline GUC assignment with negligible per-call cost, and the autocommit-atomic was the deliberate, correct fix to avoid request-long transactions (AF4); correctness beats micro-optimization at current scale. — Valid; this is explicitly `wrong-for-now`, and should not be touched until load testing shows the round-trips matter.

**Alternative solutions:**
1. **Prime once per connection checkout** via a pool checkout hook (session-level `SET`, reset on return) instead of per-statement. *Medium effort; biggest win; must handle pooling reset carefully.*
2. **Prime once per request** by re-introducing a request-scoped `tenant_context()` (single SET LOCAL per request transaction) for read paths, accepting a bounded transaction. *Lower effort; partially reverts the AF4 stance.*
3. **Per-transaction memo** in the wrapper (skip re-issuing SET LOCAL if already primed in the current transaction). *Lowest effort; only helps multi-statement transactions, not the autocommit-per-query case.*

**Preferred option + why:** (1) as the structural target — connection-checkout priming matches the `conn_max_age=600` persistent-connection model and removes the per-statement overhead without reintroducing long transactions; defer until load testing confirms the cost is real.

**Migration path:** First cut — add a per-transaction "already primed" memo (option 3) to remove the redundant SET LOCAL within multi-statement transactions, then evaluate checkout-time priming under load.

---

## Finding 5 — Module integration is a high-arity coordination tax, mid-migration between an imperative per-module path and an incomplete declarative manifest layer

**Rank rationale (blast radius × likelihood):** Blast is developer velocity and a two-places-to-edit hazard for every module; likelihood is medium and the team is actively, deliberately migrating. Medium × medium — real but managed.

**Horizon:** `6–18 months` — bites as the roadmap adds modules (teams) and vertical themes.

**Confidence:** Medium — verified the imperative inventory and file sizes; the *degree* of remaining duplication is inferred from the inventory's phase tags.

**Context dependence:** `wrong-for-now` — dimension: *new domain* (more modules/themes coming). Flat cost today; compounds as the module count grows.

**Problem:** Wiring a module spans a large, multi-file imperative surface (the Module Implementation Checklist enumerates ~30 steps), and a declarative manifest/derivation layer meant to replace it is half-built — so module knowledge currently lives in two parallel mechanisms that must be kept in sync.

**Evidence:**
- `quickscale_cli/.../commands/module_config.py` (2098 lines) + `module_commands.py` (1563 lines) carry imperative per-module configuration.
- `quickscale_core/.../contracts/imperative_inventory.py` catalogs per-module symbols (`_build_crm_derivation_schema`, `_build_billing_derivation_schema`, …) tagged by migration phase (`T2.3`/`T2.4`/`T2.5`/`deferred`) and by ownership (`declarative_target` = "should be YAML but isn't yet").
- `decisions.md §Module Derivation Schema` is explicit: the dataclasses exist but "No YAML loading from `module.yml` yet… No runtime derivation execution yet… No contract-file deletion yet."
- Mitigation already in place: module discovery is manifest-driven (`module_commands.py:65 AVAILABLE_MODULES = get_discovered_module_names()`) and the old `*_contract.py` source files are deleted (only stale `__pycache__` remains).

**Why it compounds:** Until the declarative path lands, each new module re-pays the imperative wiring cost *and* adds an entry to the inventory of things-to-migrate; the half-built `ModuleDerivationSchema` is a second definition site, so config knowledge can drift between the imperative builders and the manifest. The classic failure mode is the migration calcifying half-done — two mechanisms, permanently.

**Correct shape:** A module's configuration contract should have one declarative definition (`module.yml` + derivation schema) that the CLI consumes generically; adding a module should be "write the manifest," not "edit N CLI files."

**Trigger for urgency:** Implementing the `teams` module or a vertical theme, which forces another full pass through the imperative surface; or the Track 2 derivation migration stalling at a `deferred` phase.

**Compounding factor:** Every currently-shipped module (~10) has imperative wiring catalogued for migration; finishing the declarative path means migrating all of them, and leaving it half-done means maintaining both.

**Detection signal:** PR diffs for a new module touching `module_config.py` + `module_commands.py` + manifest + inventory simultaneously; `deferred`-tagged entries in `imperative_inventory.py` not decreasing release over release.

**Strongest counter-argument (steelman):** This is recognized, deliberately phased work with an explicit inventory and ownership matrix — discovery is already declarative and contract files are already deleted. It's managed debt, not a hidden beam. — Correct; the only structural risk is the migration stalling, so this is a "watch" more than an indictment.

**Alternative solutions:**
1. **Finish the declarative cutover one module at a time** (the planned path): land YAML loading + runtime derivation execution, then delete each module's imperative builder. *Medium-high effort; removes the duplication.*
2. **Freeze the imperative surface** behind a single adapter and forbid new imperative per-module code, forcing new modules through the manifest only. *Low effort; stops the bleed without finishing the migration.*
3. **Pilot-and-prove** on the analytics module (already named as the pilot), then templatize. *Low risk; validates the declarative path before broad migration.*

**Preferred option + why:** (3)→(1) with (2) as a guardrail. Prove the declarative path on one module, forbid new imperative wiring so the surface stops growing, then migrate the rest — matching the team's existing phased intent while preventing the stall that would leave two mechanisms permanently.

**Migration path:** First cut — implement `module.yml` `derivation:` loading + runtime execution for the analytics pilot and delete its imperative builder, proving one module can be fully manifest-driven end to end.

---

_Lenses scanned with no qualifying finding: data-model integrity beyond tenancy (IDs are UUID/BigAuto by deliberate role), soft-delete semantics, observability architecture, API/contract versioning, concurrency beyond the tenant ContextVar (single-writer org creation is correctly guarded), supply-chain/build, and the DR engine boundary (recently extracted and cleanly adaptered)._
