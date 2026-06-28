# Structural Autopsy: QuickScale (v87 / post–Track-1 RLS)

## Orientation

**What it is.** A creator-led Django *project generator* (`quickscale plan` → `quickscale apply`) plus a workspace of ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated projects via **git subtree** and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core` (core is Django-free by invariant).

**Near-term growth direction.** The dominant work of the last ~18 milestones is **retrofitting multi-tenant isolation** onto every module: a contextvar-backed `TenantManager`, a NOT-NULL `PROTECT` org FK contract (`tenant_org_fk`), a `solo`→`saas` runtime mode, org-authoritative billing, and (Track 1) PostgreSQL FORCE RLS rolled out module-by-module. The product is mid-pivot from a single-user scaffold into a multi-tenant SaaS substrate. Every finding below sits on the seam that pivot is stressing right now.

**Deployment context.** Generated apps run WSGI/Gunicorn (sync workers, `conn_max_age=600` persistent connections — `production.py.j2:114,132`), single Railway project, shared Postgres 18. No existing users; the standing rule is **clean break — no back-compat, no migration path** (squash/rewrite migrations, delete dead paths). Development is run as parallel worktree tracks (`wt-track1/2/3`), i.e. several isolation tasks land concurrently against the same seams.

**Prior autopsy status (carried forward).** The previous round recorded Findings 1, 2, 4, 5 as resolved:
- F1 (RLS fails open) → T1.18 boot guard (`orgs/apps.py:38-62`, fail-closed for non-`migrate` startup).
- F2 (two carriers + pervasive `all_objects`) → T1.19/T1.7–T1.9 unified the **manager** to a single shared `TenantManager`.
- F4 (two routing models) → T1.20 deleted slug-routing fallback; middleware is now session-only (`orgs/middleware.py`).
- F5 (static `MODULE_CATALOG`) → D2 manifest-backed discovery.

**What this pass found.** Track 1 made isolation a *data-layer* guarantee in principle, but the guarantee was assembled from three mechanisms that must independently agree — the Django `TenantManager`, the Postgres FORCE-RLS policy, and a hand-set `app.current_org_id` GUC — and the structural glue was missing. Findings 1 (AF1 ✅), 2 (AF2 ✅), and 4 (AF4 ✅) are resolved. **Finding 3 (AF3)** — the unaudited operator-access seam — is the one remaining open item.

**Already acknowledged, not re-reported.** The roadmap's Deferred/Monitor list owns: no structured logging/correlation IDs (D9a is a baseline only), no versioned public API, no webhook payload-boundary validation. The module-upgrade story (subtree pull + "Module Extension Contract", `docs/technical/module-extension.md`) is **deliberate, documented design** — excluded. Single-PR items (Stripe `api_version` pin, per-admin `select_related`, the personal-org-create-per-request micro-cost) are out of scope by the autopsy's own rules.

---

## Ranked findings

| # | Finding | Horizon | Blast radius × likelihood |
|---|---------|---------|---------------------------|
| 1 | Tenant-table isolation is per-table hand-written SQL with **no conformance gate**; child tables without `organization_id` sit outside *both* isolation layers | **now** (dev) → **6–18 mo** (first cross-tenant prod leak) | Cross-tenant data leak × high (recurs every model/table added) |
| 2 | The auto-scoping contextvar `TenantManager` is the **default *and* base manager**, so every non-request code path must re-establish ambient org context — already re-implemented 3× | **RESOLVED** | AF2, 2026-06-28 — see CHANGELOG |
| 3 | The operator escape hatch is a **dual, ambient, unaudited bypass** (`all_objects` *and* the connected DB role's `BYPASSRLS`) with no single authorized seam | **6–18 mo** | Silent cross-tenant operator leak × medium |
| 4 | Wrapping the whole request in one transaction (to carry `SET LOCAL`) couples DB connection-hold time to in-view external I/O (Stripe) — *carryover, broadened by T1.20* | **RESOLVED** | AF4, 2026-06-28 — see CHANGELOG |
| 5 | `quickscale apply` step checkpointing + fault-injection harness | **RESOLVED** | AF5, 2026-06-27 — see CHANGELOG |
| 6 | God files fighting parallel-worktree workflow | **RESOLVED** | AF6, 2026-06-27 — see CHANGELOG |
| 7 | Rich-module adapters living in core instead of module packages | **RESOLVED** | AF7, 2026-06-28 — see CHANGELOG |
| 8 | Silent fallbacks in module-path discovery and Railway project-name inference | **RESOLVED** | AF8, 2026-06-28 — see CHANGELOG |

**These findings span two distinct domains.** Findings 1–4 sit on the **runtime multi-tenant isolation** seam (the `quickscale_modules/*` + `orgs` machinery that runs inside a generated app). Findings 5–8 sit on the **generator/CLI** seam (`quickscale_core` + `quickscale_cli` — the `plan`/`apply` engine itself) and were surfaced specifically by broadening the autopsy past the isolation pivot. The two domains share almost no files, which is what makes them parallelizable (see the roadmap track assignment). Findings 5–8 are fully resolved — see CHANGELOG.md.

Sections of the autopsy template with **nothing new to report** for this codebase: VI (Observability — already on the Deferred list), VII (external API/Contract versioning — already owned). They are omitted rather than padded.

---

## Finding 1 — Tenant isolation is a per-table, hand-maintained guarantee with no conformance gate, and child tables fall through it

**Time horizon: now (development-time) → 6–18 months (first cross-tenant production leak).**

**Problem.** "Database-level isolation" is not a property of the schema; it is six independently hand-written `enable_rls` migrations, each carrying a copy-pasted policy SQL string and a hardcoded list of table names — and any tenant-owned table that lacks a literal `organization_id` column (every child/detail table) is silently outside *both* the Python `TenantManager` and the RLS policy. There is no structural assertion that "every org-owned table has FORCE RLS + a policy," so coverage is whatever the last author remembered.

**Why it compounds.** The isolation guarantee scales by hand, not by construction:
- **Every new tenant table** requires authoring a fresh RLS migration with the right table name and the right policy SQL. Forget it, and the Python manager still scopes reads in the happy path, so tests pass and the gap is invisible — until an `all_objects` query, a raw report, a DR restore, or a direct child-table endpoint returns another tenant's rows.
- **Every new child table** (notes, line items, attachments, comments) inherits the `ContactNote`/`DealNote` shape: no `organization_id`, plain `objects`, no RLS. The DB backstop that FORCE RLS was *supposed* to provide — catching the app when it forgets to filter — does not exist for these tables. The only thing protecting them is the application remembering to join through the parent.
- **Changing the policy formula** (GUC name, fail-closed semantics, adding a `WITH CHECK` variant) means editing six near-identical migration files in lockstep. Drift between them is undetectable without reading all six.

**Evidence.**
- Six duplicated migrations, each with its own copy of the forward/reverse SQL and a hardcoded `_*_RLS_TARGETS` tuple: `crm/.../migrations/0008_enable_rls.py:54-74`, plus `blog`, `listings`, `forms`, `social`, `billing` `…/migrations/000*_enable_rls.py` (identical `_FORWARD_SQL` body).
- Child-table gap, stated explicitly in the migration itself: `crm/.../migrations/0008_enable_rls.py:18-21` — "ContactNote and DealNote have no direct `organization_id` column … FORCE RLS on those tables is therefore not applied here." The models confirm it: `crm/.../models.py:260-317` (`ContactNote`/`DealNote` are plain `models.Model`, default `objects`, no org FK). `billing/.../migrations/0002_enable_rls.py:7` similarly excludes `Plan` and `WebhookEvent`.
- No conformance test. The only shared isolation helper, `tests_shared/isolation.py:19-57`, asserts a **response-level** property ("this HTTP endpoint returned only my org's names"); it does not enumerate `pg_policies` or model `_meta` to prove table coverage. Each module's `test_rls_boundary.py` exercises whatever paths its author chose.
- The canonical FK helper exists (`orgs/.../tenancy.py:12-38`, NOT NULL + `PROTECT`) but adoption is by convention — `crm`/`blog` inline their own `ForeignKey(..., on_delete=PROTECT)` instead of calling it, so even the column contract is copy-discipline, not a single definition.

**Correct shape.** Tenant-table membership should be **declarative and enumerable**, and RLS + the conformance check should derive from that one declaration. A model is tenant-owned by inheriting one `TenantModel` base (or being registered in a tenant-table registry); a single migration operation (`EnableTenantRLS(model)`) emits the policy from one source string; and a CI conformance test walks `apps.get_models()`, selects everything carrying the tenant marker, and asserts each has (a) an `organization_id` column and (b) a live FORCE-RLS policy in `pg_policies`. Every tenant-owned table — including child/detail tables — must carry `organization_id` directly; parent-join RLS policies are not an accepted substitute. Child tables are never an implicit "the app will remember to join" — they are promoted to full tenant tables with a DB constraint keeping `child.organization_id = parent.organization_id`.

**Alternatives.**
- **(A) Declarative tenant-table registry + generated RLS + CI conformance test.** One `TenantModel`/registry marker is the single source of truth; a reusable `EnableTenantRLS` migration operation generates the policy; a conformance test fails the build when any registered table lacks a direct-column policy. *This is the implementation vehicle — the registry and conformance gate are how Option C is enforced at scale.*
- **(B) Keep per-module migrations, add only the conformance test.** Smallest change; catches missing coverage at CI. But it leaves the duplicated policy SQL and the manual table lists, so the *write* tax and drift risk remain.
- **(C — decided) Add `organization_id` to every child table (denormalize the FK down); every tenant table uses a uniform direct-column RLS policy.** Makes every tenant table uniformly RLS-able with the same policy shape, no parent-derived special case. Strong isolation story; DB constraint/trigger keeps child `organization_id` equal to the parent's. **This is the locked project default for child-table policy** — see roadmap.md "Decisions locked." The registry and conformance gate from (A) are the enforcement mechanism; (C) is the schema contract they enforce.

**Trigger for urgency.** Onboarding the **first real multi-tenant customer** (two paying orgs sharing the DB), or shipping any cross-tenant reporting / data-export / DR-restore path that reads child tables directly. Either turns the invisible gap into a disclosure.

**Compounding factor.** Six modules already encode the per-table pattern; `crm` already ships two unprotected child tables; the admin/operator and DR/backups paths already read via `all_objects`. Every one of these is a place a missing or drifted policy surfaces.

**Migration path.** First cut: add the CI conformance test (walk models, diff against `pg_policies`) — it is read-only, lands in one PR, and immediately surfaces today's true coverage including the `ContactNote`/`DealNote` gap; then introduce `EnableTenantRLS` and migrate the six modules onto it.

**Detection signal.** Today there is no signal — that *is* the finding. Instrument: the conformance test in CI (build-time), plus a periodic prod job that counts org-owned tables whose `relrowsecurity`/`relforcerowsecurity` is false in `pg_class`, alerting if >0.

---

## Finding 2 — The auto-scoping contextvar manager is wired as the *base* manager, so every non-request code path silently depends on an ambient org context

**Status: RESOLVED — AF2 implemented 2026-06-28.** `TenantModel.base_manager_name` set to `"all_objects"`; duplicate context wrappers (`_billing_org_db_context`, social admin `_org_db_context`) deleted; request-scoped callers converged on `orgs.current_org.tenant_context()`. Regression tests added for FK traversal and `refresh_from_db()` under no org context. See [CHANGELOG.md](../../CHANGELOG.md).

---

## Finding 3 — The operator escape hatch is a dual, ambient, unaudited bypass

**Time horizon: 6–18 months.**

**Problem.** Crossing tenant boundaries as an operator is governed by two *independent* switches that must both be reasoned about and neither of which is audited: the Python-level `all_objects = TenantManager(super_scope=True)` declared on every model, and the **identity of the DB role the process happens to be connected as** (the runtime role is `NOBYPASSRLS` per the boot guard, but migrations, management commands run with the superuser `DATABASE_URL`, and the DR/backups engine all operate with `BYPASSRLS`). There is no single, explicit, logged "operator access" seam — cross-tenant reach is an emergent property of which manager attribute you typed and which connection string your shell inherited.

**Why it compounds.** As the operator surface grows (admin actions, management commands, DR/restore, backups, future cross-tenant analytics), the number of places that can read across tenants grows, and each one's safety depends on an invisible combination: `all_objects` + the ambient role + (per Finding 1) whether the table even has RLS. For a child table with no policy, `all_objects` is an unconditional cross-tenant read regardless of role. None of these accesses leaves an audit trail tying "operator X read org Y's rows" to a reason — so a future SOC2/GDPR posture has no record to point at, and a compromised or buggy operator script is indistinguishable from legitimate maintenance.

**Evidence.**
- Per-model Python bypass: `objects`/`all_objects` pairs on every tenant model (e.g. `crm/.../models.py:41-42`, `blog/.../models.py:265-266`, `billing/.../models.py`), backed by `TenantManager(super_scope=True)` returning the unfiltered queryset (`orgs/.../managers.py:34-48`).
- Role-level bypass is environment-selected: `orgs/apps.py:20-62` documents that `manage.py migrate` (and only it) runs under the superuser `DATABASE_URL` with `BYPASSRLS` because `start.sh` unsets `RUNTIME_DATABASE_URL`; the runtime role is fail-closed `NOBYPASSRLS`. The DR engine (`quickscale_core/.../generator` DR paths, `docs/technical/dr_engine_migration.md`) operates at the DB level entirely outside RLS.
- Operator reads via `all_objects` are spread across `*/admin.py`, `*/services.py`, `*/views.py`, and management commands (`forms_anonymize_submissions`, `purge_organization`, `migrate_billing_to_orgs`) with no shared audit point.

**Correct shape.** A single, explicit, authorized operator-escalation seam: cross-tenant access is reachable only through one API — e.g. `with operator_access(reason=...) as scope:` — that is the *only* code permitted to use the unfiltered queryset / `BYPASSRLS` path, emits a structured audit record (who, which orgs, why), and is the thing tests and reviews can grep for. `all_objects` stops being a free attribute on every model; the privileged role is reached through a named, logged boundary rather than an ambient connection string.

**Alternatives.**
- **(A — preferred) One `operator_access()` boundary that owns both the unfiltered queryset and the privileged-role connection, and audits every use.** Replace scattered `all_objects` with calls routed through this seam; make the `BYPASSRLS` connection reachable only inside it. *Preferred: it collapses two ambient switches into one authorized, logged decision, gives compliance a real audit trail, and makes "where can we cross tenants?" a finite, reviewable list instead of an emergent property.*
- **(B) Keep `all_objects`, add structured audit logging + a lint/review rule.** Lower effort; every `all_objects` use logs an operator-access event and is flagged in review. Buys observability and a paper trail without restructuring, but leaves two bypass switches and relies on discipline to keep them aligned — the dual-switch ambiguity remains.
- **(C) Drop `all_objects` entirely; operators get cross-tenant reach only by connecting as the `BYPASSRLS` role.** Makes the DB role the single switch (no Python bypass). Conceptually clean, but pushes all operator tooling onto a privileged connection and removes the in-process, per-query escape that admin/inlines currently rely on — a larger rewrite of the admin/operator surface for less ergonomic gain than (A).

**Trigger for urgency.** A compliance commitment (SOC2/GDPR data-access audit), the first incident requiring "prove no operator read tenant X's data," or the first cross-tenant analytics/back-office feature — any of which needs an audited boundary that does not exist today.

**Compounding factor.** Every current `all_objects` callsite, every management command, and the DR/backups engine assume ambient operator reach; consolidating onto one seam means routing all of them through it.

**Migration path.** First cut: introduce `operator_access()` as a thin wrapper that today just logs + yields the unfiltered path, and convert the handful of management commands to it — establishing the audited seam before tightening `all_objects` out of the models.

**Detection signal.** Count distinct `all_objects`/privileged-connection entrypoints (should trend to one). Operationally, once the seam exists, alert on operator-access events that name more than one org in a single scope, or that run under the `BYPASSRLS` role outside `migrate`.

---

## Finding 4 — Wrapping the whole request in one transaction (to carry `SET LOCAL`) couples DB connection-hold time to in-view external I/O *(carryover, broadened by T1.20)*

**Status: RESOLVED — AF4 implemented 2026-06-28.** `TenantMiddleware._call_with_org` no longer opens a request-long `transaction.atomic()`; middleware sets `request.org` + ContextVar only. Public forms, generated social views, and billing webhooks open explicit short `transaction.atomic()` + `tenant_context()` windows only where DB-level org scope is required. Stripe retrieval/backfill runs outside local mutation transactions. `production.py.j2` documents `CONN_MAX_AGE`, `CONN_HEALTH_CHECKS`, and the `RUNTIME_DATABASE_URL` runtime-role pattern. See [CHANGELOG.md](../../CHANGELOG.md).

---

## Finding 5 — `quickscale apply` is a 16-step, all-irreversible, cross-system mutation with no rollback and convention-based "idempotent-rerun" as the sole recovery

**Status: RESOLVED — AF5 implemented 2026-06-27.** Per-step `is_satisfied()`/`apply()` contract, `ResumeCheckpoint`/`RecoveryLedger` post-step checkpointing, fault-injection harness, and destructive-phase confirmation gate. See CHANGELOG.md.

---

## Finding 6 — The generator's hottest logic is concentrated in god files that fight the project's own parallel-worktree workflow

**Status: RESOLVED — AF6 implemented 2026-06-27.** `apply_command.py` 16 step bodies extracted to `quickscale_core/apply/steps/*.py`; `dr_engine/orchestration.py` split into `_lock.py`, `_paths.py`, `_sidecar.py`. See CHANGELOG.md.

---

## Finding 7 — "Self-describing modules" only half-landed: rich modules carry hand-written adapters inside core

**Status: RESOLVED (AF7, 2026-06-28).** Module-owned adapters shipped for social, billing, CRM; core fallbacks deleted; `refresh_managed_adapters()` now raises `ImproperlyConfigured` on missing adapters. See [CHANGELOG.md](../../CHANGELOG.md).

---

## Finding 8 — Fail-hard violations in module-path discovery, managed-adapter resolution, and Railway project-name inference

**Status: RESOLVED (AF7-CR-003 + AF8, 2026-06-28).** All three violations closed: managed-adapter fallbacks deleted (AF7); `get_modules_base_path()` raises `ImproperlyConfigured` on missing path; `get_app_service_name()` raises `ValueError` on missing project name (AF8). See [CHANGELOG.md](../../CHANGELOG.md).

---

## Cross-finding note for roadmap planning

The eight findings form **two independent clusters** that share almost no files:

- **Runtime isolation cluster (Findings 1–4)** — Findings 1 ✅ (AF1), 2 ✅ (AF2), 4 ✅ (AF4) resolved. **Finding 3 (AF3) is the only remaining open item** — single audited operator-access seam on `wt-track1`.
- **Generator cluster (Findings 5–8)** — all touch `quickscale_core`/`quickscale_cli`. **All resolved.** AF5 ✅ AF6 ✅ AF7 ✅ AF8 ✅ — see [CHANGELOG.md](../../CHANGELOG.md).

---

## Cross-cutting QA / testing thread

Three structural findings shared a common failure mode: the test suite exercises the happy request path — the one path on which the broken mechanism still appears to work — so coverage gaps, ambient-context breakage, and non-idempotent steps all pass silently and give false confidence. The fix in each case is a **property / conformance test (enumerate-and-assert or fault-inject-and-assert)**, not another example-path test.

| Finding | Property test | Status |
|---|---|---|
| **1** | Walk `apps.get_models()`, select tenant tables, assert each has a live FORCE-RLS policy in `pg_policies` (conformance gate) | **complete — AF1 ✅** |
| **2** | Regression test: forward-FK traversal + `refresh_from_db()` with **no** org context set must succeed | **complete — AF2 ✅** |
| **5** | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) | **complete — AF5 ✅** |
