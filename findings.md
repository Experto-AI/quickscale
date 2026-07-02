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
| 1 | Tenant-isolation correctness is a hand-replicated per-model ritual; its only enforcement (the conformance gate) is scoped to `quickscale_modules_*` and does not reach the user-authored models that generated projects exist to host | now / 6–18mo | High | SA1.1–SA1.4 shipped; **SA1.5 open** (last task project-wide) |
| 2 | **CLOSED 2026-07-01.** The master isolation switch failed open: an unset `RUNTIME_DATABASE_URL` silently connected under a BYPASSRLS superuser role, and the boot guard that caught it was gated to `saas` + `DEBUG=False` | now (latent) | High | SA2.1, SA2.2 (both shipped, merged to `v87`) |
| 3 | **CLOSED 2026-07-01.** No single source of truth for the isolation contract — the two authoritative docs already described a weaker, different posture (and a different manager API) than the shipped code | now | High | SA3.1, SA3.2 (both shipped, merged to `v87`) |
| 4 | **CLOSED 2026-07-02.** DB tenant context was primed per-statement by a connection-layer wrapper that opened a transaction around every autocommit tenant query | 6–18mo | Medium | SA4.1, SA4.2 (both shipped); larger connection-checkout redesign deferred, no follow-on task |
| 5 | **CLOSED 2026-07-02.** Module integration was a high-arity coordination tax mid-migration between an imperative per-module path and an incomplete declarative manifest layer | 6–18mo | Medium | SA5.1, SA5.2 (both shipped); remaining per-module migrations left as unscheduled backlog |

---

## Two independent clusters (summary)

**Cluster A — the tenant-isolation contract has no single enforced source of truth (Findings 1, 2, 3, 4).** The isolation machinery is genuinely strong *inside the QuickScale repo* (FORCE-RLS on 21 models, composite FKs, restricted-role conformance proofs, an AF9 GUC-priming wrapper, a T1.18 boot guard). Findings 2, 3, and 4 are now closed; Finding 1 remains open pending SA1.5 (extending the enforcement gate into generated-project CI, so it reaches user-authored models — the one part of the contract that still has no backstop).

**Cluster B — module/generator integration coupling (Finding 5).** **CLOSED 2026-07-02.** The pilot (SA5.1) and freeze guardrail (SA5.2) shipped; the imperative surface can no longer grow. Remaining per-module migrations are left as unscheduled backlog rather than tracked roadmap work.

---

# Autopsy — 2026-06-30

This dated section is the full structural autopsy. Findings are ranked by blast radius × likelihood, most urgent first. The orientation summary above governs every severity and horizon call below.

**Read fully:** the orgs tenancy seam (`tenancy.py`, `current_org.py`, `managers.py`, `middleware.py`, `apps.py`), the conformance gate (`orgs/tests/test_tenant_table_conformance.py`), CRM/blog/listings model + admin layers, generated settings templates (`base.py.j2`, `production.py.j2`), and the authoritative docs (`decisions.md §multitenant`, `organizations.md`). **Sampled:** CLI module wiring (`module_config.py`, `module_commands.py`, `imperative_inventory.py`), DR engine boundary. **Skipped:** frontend theme source, analytics/notifications/storage internals, the test suites as test correctness (in scope only as architecture).

---

## Finding 1 — Tenant isolation is a hand-assembled per-model ritual, and its enforcement gate cannot see the user code that generated projects exist to host

**Status (2026-07-02):** SA1.1–SA1.4 shipped and merged to `v87` (CRM/blog migrated to `TenantModel`, generic conformance command, default-deny exclusion registry — see [CHANGELOG.md](CHANGELOG.md)). Only **SA1.5** (wiring the isolation gate into generated-project CI, the customer-extension backstop this finding is ultimately about) remains open — tracked in [roadmap.md](docs/technical/roadmap.md#structural-autopsy-remediation-opened-2026-06-30).

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

## Finding 2 — Closed 2026-07-01

Fully remediated: SA2.1 (always-on BYPASSRLS boot guard, `QUICKSCALE_ALLOW_BYPASSRLS=1` escape hatch) and SA2.2 (runtime DB-role default inverted to fail-closed — `RUNTIME_DATABASE_URL` required to serve, superuser `DATABASE_URL` now the named `migrate`-only exception) both shipped and merged to `v87`. Full autopsy detail (problem, evidence, alternatives) has been superseded by the shipped fix; see [CHANGELOG.md](CHANGELOG.md) (SA2.1, SA2.2 entries) for the implementation record.

---


## Finding 3 — Closed 2026-07-01

Fully remediated: SA3.1 (re-synced `decisions.md` and `organizations.md` with shipped reality — 21 ENROLLED FORCE-RLS models, `TenantManager(super_scope=…)` + `ContextVar` API, stale `TenantScopedManager`/`OperatorManager`/`.for_org()` framing removed) and SA3.2 (CI doc-consistency gate diffing both docs' machine-readable assertions against the `TENANT_TABLE_REGISTRY` SSOT) both shipped and merged to `v87`. Full autopsy detail (problem, evidence, alternatives) has been superseded by the shipped fix; see [CHANGELOG.md](CHANGELOG.md) (SA3.1, SA3.2 entries) for the implementation record.

---

## Finding 4 — Closed 2026-07-02

Remediated to the level the autopsy itself prescribed as the safe first cut: SA4.1 (statement-amplification measurement harness) and SA4.2 (per-transaction "already-primed" memo, skipping redundant `SET LOCAL` within a transaction) both shipped and merged to `v87`. The autopsy's preferred *structural* target — priming once per connection checkout — remains explicitly `wrong-for-now` per its own steelman ("should not be touched until load testing shows the round-trips matter") and is not currently load-tested; closed by maintainer decision (2026-07-02) with no follow-on task tracked. If traffic/tenant volume grows enough to justify a load test, re-open as a fresh finding rather than resuming this one. See [CHANGELOG.md](CHANGELOG.md) (SA4.1, SA4.2 entries) for the implementation record.

---

## Finding 5 — Closed 2026-07-02

Remediated to the level the autopsy prescribed as its safe phased path: SA5.1 (analytics derivation pilot — manifest-driven `module.yml` bridge replaces the imperative builder end to end) and SA5.2 (freeze guardrail — CI fails if a module outside the grandfathered `AUTHORIZED_IMPERATIVE_MODULES` set adds imperative wiring) both shipped and merged to `v87`. The pilot proves the declarative path works and the freeze stops the imperative surface from growing further, which was the urgent part; migrating the remaining ~9 modules off imperative wiring is left as unscheduled backlog rather than a tracked roadmap task, by maintainer decision (2026-07-02). See [CHANGELOG.md](CHANGELOG.md) (SA5.1, SA5.2 entries) for the implementation record.

---

_Lenses scanned with no qualifying finding: data-model integrity beyond tenancy (IDs are UUID/BigAuto by deliberate role), soft-delete semantics, observability architecture, API/contract versioning, concurrency beyond the tenant ContextVar (single-writer org creation is correctly guarded), supply-chain/build, and the DR engine boundary (recently extracted and cleanly adaptered)._
