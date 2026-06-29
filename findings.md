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

---

# Structural Autopsy — Fresh pass 2026-06-28 (post AF2/AF4 merge)

> New section appended per §9. Prior analysis above is retained unchanged. This pass
> re-examined the isolation seam after AF2 + AF4 landed on `v87` (commit `0a4cc943`,
> 2026-06-28) and verified the one remaining open carryover (AF3).

## Orientation (this pass)

Same system as the prior orientation: a Django **project generator** (`quickscale plan`/`apply`,
in `quickscale_core` + `quickscale_cli`) plus ~14 embeddable Django modules
(`quickscale_modules/*`) that become user-owned code in generated apps. The live pivot is still
**retrofitting multi-tenant isolation**: the isolation guarantee is assembled from three
mechanisms that must independently agree — (1) the Python contextvar `TenantManager`, (2) Postgres
FORCE-RLS policies, and (3) the `app.current_org_id` GUC the policies read. Deployment posture is
the documented secure one: WSGI/Gunicorn sync workers, `conn_max_age=600` **persistent**
connections (`production.py.j2:125,143`), a restricted **NOSUPERUSER/NOBYPASSRLS** runtime role fed
via `RUNTIME_DATABASE_URL` (`OPERATIONS.md.j2:12,19-20`), superuser `DATABASE_URL` used only for
`migrate`. No existing users; clean-break rule (no back-compat, no migration path).

**Read fully:** `orgs/{middleware,current_org,managers,apps,tenancy}.py`; the AF1 conformance gate
`orgs/tests/test_tenant_table_conformance.py`; `crm/tests/test_rls_boundary.py` + `crm/tests/settings.py`;
the generated `production.py.j2` DB block; `forms/views.py` public path; `.github/workflows/{ci,e2e}.yml`;
`Makefile` test targets. **Sampled:** billing/social explicit-transaction callers; the other five
`test_rls_boundary.py`. **Skipped:** generator/CLI cluster (AF5–AF8, all resolved last pass; no new
read).

**What this pass found.** The prior pass marked AF4 resolved — and it did fix the connection-hold
problem (Finding 4). But removing the request-long `transaction.atomic()` from the middleware also
removed the **only thing that set the RLS GUC on the normal authenticated request path**. The two
isolation layers are now wired to disagree in exactly the configuration FORCE-RLS exists for, and
the test matrix structurally cannot see it. Two new `now`-horizon findings (AF9, AF10) result; AF3
(operator seam) is re-confirmed still open and re-ranked below them.

## Ranked findings (this pass)

> **Update 2026-06-28 (b): two findings below (AF9, AF11) are now empirically reproduced**
> against a live PostgreSQL 18 server using the *exact* policy SQL from `tenancy.py` and the
> *exact* reset primitive from `current_org.py`, under a `NOSUPERUSER/NOBYPASSRLS` role (the
> documented runtime posture). Reproduction matrix:
>
> | GUC state (runtime role) | `current_setting('app.current_org_id', true)` | policy `SELECT` |
> |---|---|---|
> | never set (fresh pooled conn) | `NULL` | **0 rows** (clean fail-closed) |
> | after `RESET app.current_org_id` | `''` | **ERROR: `invalid input syntax for type uuid: ""`** |
> | after `SET LOCAL …` + txn end | `''` | **ERROR** (same) |
> | set to a valid org id | uuid | 1 row (correct) |
>
> Row 1 confirms AF9; rows 2–3 are the new AF11.

| # | Finding | Horizon | Blast radius × likelihood | Plan |
|---|---------|---------|---------------------------|------|
| **AF9** | After AF4, nothing sets `app.current_org_id` on the authenticated/admin path; under the NOBYPASSRLS runtime role, FORCE-RLS **fail-closes every authenticated + admin tenant read/write to zero rows** *(reproduced)* | **now** | App-wide data outage in secure posture × certain once `RUNTIME_DATABASE_URL` is set | **Phase A / Track 1** — execute_wrapper derives GUC from ContextVar |
| **AF11** | The RLS policy casts `current_setting(...,true)::uuid` with **no empty-string guard**; a pooled connection rests at `''` (not NULL) after *any* `SET LOCAL`/`RESET`, so the policy **throws a 500 instead of failing closed** — and this *also* falsifies the boundary test's "unset ⇒ 0 rows" assertion *(reproduced)* | **now** | Non-deterministic 500s across the whole tenant surface × high (every mixed anon+auth traffic pattern) | **Phase A / Track 2** — `NULLIF` guard in `_FORCE_RLS_FORWARD_SQL` + sweep migration |
| **AF10** | The entire DB-level isolation layer (RLS policies, restricted-role boundary, AF1 gate's catalog checks) is **`skipif(not postgres)` and never provisioned in CI** — green CI certifies only the SQLite-visible Python wiring | **now** | Every isolation regression ships green × certain (it already has — AF9 *and* AF11) | **Phase A / Track 3** — AF13 (Postgres-only test settings) → dedicated `isolation-conformance` CI job |
| **AF3** | Operator escape hatch is a **dual, ambient, unaudited bypass** (`all_objects` + the connected role's `BYPASSRLS`) with no single authorized seam | **6–18 mo** | Silent cross-tenant operator leak × medium | **Phase B / Track 1** — `operator_access(reason=...)` seam; gated on AF9+AF11+AF10 |
| **AF12** | DB-level child-parent `organization_id` equality is enforced by a trigger on the **child only**; a parent `organization_id` mutation silently orphans children with no re-validation | **6–18 mo** | Cross-tenant child rows after a parent org-move × low–medium | **Phase A / Track 2** — composite FK `(parent_id, org_id)` after AF11 |
| **AF13** | Every module `tests/settings.py` defaults to SQLite, violating the Postgres-only policy — **structural root cause of AF10** | **now** | Every module's test suite silently targets the wrong DB × certain | **Phase A / Track 3 (first)** — delete SQLite fallback from all 11 settings files |

AF9, AF10, AF11, and AF13 share one structural root (**isolation correctness is asserted on SQLite/the
happy path and never validated against the real two-layer postgres+restricted-role runtime**) but
are kept separate because the fixes touch different seams: AF9 is a runtime-wiring defect (GUC never
set on the auth path), AF11 is a policy-SQL defect (not empty-string-safe) that bites even when the
GUC *is* managed, AF13 is the code-level cause of AF10 (test settings select the wrong DB), and AF10
is the CI-provisioning gap that hides all of the above. AF12 is independent (a trigger-coverage
asymmetry, not a GUC problem). The plan tracks all six in `roadmap.md §Open work — v87 structural
findings` with Phase A (Tracks 1–3 parallel) and Phase B (AF3 after Phase A merges).

---

## Finding AF9 — The contextvar manager and FORCE-RLS desynchronized: the authenticated path sets the ContextVar but never the GUC, so RLS fail-closes the app under the runtime role

**Horizon: now.** **Confidence: High — empirically reproduced** (live PG18, exact policy SQL,
NOBYPASSRLS role: a never-set GUC ⇒ `current_setting` returns NULL ⇒ policy `NULL::uuid = org_id`
⇒ **0 rows**; the reproduction matrix is in the update note above). **Context dependence:
wrong-for-now**, dimension = *single→secure-multitenant deployment* (it bites the moment the app
runs under the documented NOBYPASSRLS runtime role with FORCE-RLS migrations applied).

**Problem.** Tenant isolation depends on the Python `TenantManager` (reads `organization_id` from a
ContextVar) and the Postgres FORCE-RLS policy (reads the `app.current_org_id` GUC) agreeing. AF4
made the middleware set **only the ContextVar** and pushed GUC-setting onto individual callers
"where DB-level org scope is required." But the normal authenticated path — every CRM/listings/blog
view reading through the default `objects` manager — is not one of those callers. So under the
runtime role (`NOBYPASSRLS`, which the boot guard *requires* in saas-prod), every such query runs
with `current_setting('app.current_org_id', true)` = NULL, the policy `NULL::uuid = organization_id`
evaluates to false, and the read returns **zero rows** (and an INSERT/UPDATE violates `WITH CHECK`).
The Python manager says "give me org X's rows"; RLS says "you have no org context, nothing." The two
layers are wired to contradict each other on the hottest path in the app.

**Evidence.**
- Middleware sets ContextVar only, no transaction, no GUC: `orgs/middleware.py:171-182`
  (`_call_with_org` → `set_current_org_id(organization.pk)`; the wrapping `transaction.atomic()`
  that AF4 removed is gone — see the class docstring `middleware.py:57-64`).
- The GUC is *only* ever set via transaction-scoped `SET LOCAL`, never connection/session-wide:
  `current_org.py:106-125` (`set_db_current_org_id`), `current_org.py:177-230` (`tenant_context`),
  `org_scope` `current_org.py:238-302`. A repo-wide search found **no** `connection_created` hook,
  no `ATOMIC_REQUESTS`, no custom DB backend, and no session-level `SET` anywhere in modules **or**
  generator templates.
- The policy reads the GUC and fail-closes on NULL: `orgs/tenancy.py:395-403`
  (`USING (current_setting('app.current_org_id', true)::uuid = organization_id)` + identical
  `WITH CHECK`).
- The runtime role is `NOBYPASSRLS` by construction: `OPERATIONS.md.j2:12,19-20`,
  `production.py.j2:133-146`; boot guard *enforces* it fail-closed in saas-prod
  (`orgs/apps.py:38-62`). Persistent connections: `production.py.j2:125,143` (`conn_max_age=600`).
- The asymmetry is explicit in the code: the **anonymous** paths that have no middleware ContextVar
  *do* set the GUC — `forms/views.py:163-171` opens `transaction.atomic()` + `tenant_context()` and
  its docstring states "the middleware no longer holds a request-long atomic (Phase 3)." So the GUC
  is set exactly where the Python manager is bypassed (`Form.all_objects`, `forms/views.py:176`) and
  unset exactly where the Python manager is relied on (authenticated `objects` reads).

**Why it compounds.** Every new authenticated module view added to the system inherits the broken
wiring for free: it works in unit tests (SQLite, RLS no-op) and in e2e (superuser, RLS bypassed),
then returns empty results the instant it runs under the real runtime role. The number of paths
that must "remember" to open an atomic + `tenant_context()` grows with every feature, and the
failure is invisible until the secure posture is switched on — at which point it is not one bug but
an app-wide data outage. Conversely, the only posture in which the authenticated path *works* today
is running as a BYPASSRLS/superuser role — in which FORCE-RLS provides **zero** backstop, defeating
the entire AF1 investment. There is no configuration in which the authenticated path both works and
is backstopped by RLS.

**Correct shape.** On any path that touches a tenant table under the runtime role, the ContextVar
and the GUC must be set **together, from one source, by a mechanism callers cannot forget** — not
split between middleware (ContextVar) and per-caller discipline (GUC). The invariant: "if the Python
manager would scope a query to org X, the DB session evaluating that query has `app.current_org_id`
= X," enforced structurally.

**Trigger for urgency.** Turning on the documented secure posture: setting `RUNTIME_DATABASE_URL`
to the restricted role (which `docker-compose.yml.j2:58` already does by default) or promoting to
saas in production. The first authenticated page load returns an empty list; the first create raises
`new row violates row-level security policy`.

**Compounding factor.** Already built on top of the broken wiring:
- Every authenticated read/write in crm, listings, blog, social, and billing dashboards.
- **The entire Django admin operator surface.** `/admin/` is an `EXEMPT_PATH_PREFIX`
  (`middleware.py:45`), so the middleware sets *neither* ContextVar nor GUC there, and every module
  admin overrides `get_queryset()` to return `all_objects.all()` (e.g. `blog/admin.py:226-228`,
  `billing/admin.py:100-101,120-121,145-146`, `listings/admin.py:62-71`, `forms/admin.py:19-22`).
  Under the runtime role those reads bypass the Python filter but RLS still applies with the GUC
  unset/`''` ⇒ admin changelists return **0 rows or 500s** (AF11). The operator UI is as broken as
  the tenant UI.
- **The AF2 base-manager hole now rests on a backstop that isn't there.** AF2 deliberately set
  `base_manager_name = "all_objects"` (unfiltered) so `refresh_from_db()` and forward-FK traversal
  bypass tenant scoping in Python — the conformance gate even *asserts* the base manager is
  super-scoped (`test_tenant_table_conformance.py:252-274`). That hole was justified on the premise
  that RLS covers it. AF9 + AF11 show RLS is inert/broken on exactly those paths, so any
  Django-internal `_base_manager` access (FK descriptors, `refresh_from_db`, serializer `.get()`)
  is unscoped in **both** layers under the runtime role — an IDOR surface (§XI) with no backstop.

**Detection signal.** Today: none (AF10 is why). Instrument: a postgres CI job under the restricted
role that asserts a normal authenticated list view returns the owner's rows (it will currently
return zero). In prod: alert on `row-level security policy` errors and on authenticated list
endpoints returning empty for users who own data.

**Strongest counter-argument (steelman).** "RLS is intended as a defense-in-depth backstop, not the
runtime read path; the Python manager is primary, and we accept running the app as a role that
bypasses RLS." This fails on its own artifacts: the boot guard (`apps.py:38-62`) *forbids* a
BYPASSRLS role in saas-prod, and OPERATIONS/production templates build the NOBYPASSRLS role
specifically so RLS *is* enforced at runtime. You would only decline to fix this if you reverted
AF1 and the boot guard and demoted RLS to a migration-time-only artifact — which contradicts the
locked decision (roadmap "Decisions locked", Finding 1 = C).

**Alternatives.**
- **(A) Restore a per-request scope that sets both layers, but scope the atomic to DB work only.**
  Reintroduce a middleware/`org_scope`-style wrapper that sets ContextVar + `SET LOCAL`, but open
  the atomic lazily around the view's DB access rather than the whole request, keeping Stripe/HTTP
  I/O outside it. Removes the desync; must be careful not to reintroduce the AF4 connection-hold.
- **(B — preferred) Derive the GUC from the ContextVar at the connection layer.** A
  `connection_created` signal + a `connection.execute_wrapper` (or a thin custom backend) that, on
  the first statement of each transaction, issues `SET LOCAL app.current_org_id` from
  `get_current_org_id()`. One source of truth (the ContextVar), zero per-caller discipline, the two
  layers can never disagree, and the transaction stays per-DB-operation so AF4's fix is preserved.
- **(C) Demote RLS to operator/migration-time only; run runtime under a BYPASSRLS role; make the
  Python manager the sole runtime enforcement.** Smallest change, but abandons the DB backstop and
  contradicts AF1 + the boot guard — reintroduces exactly the procedural-isolation risk AF1 closed.

**Preferred option + why.** **(B).** It satisfies the invariant by construction (the GUC is a pure
function of the ContextVar the manager already trusts), needs no edits to any view, cannot be
forgotten by future module authors, and keeps AF4's connection-hold fix intact. (A) is a viable
fallback if a connection-layer hook proves awkward under sync workers; (C) is rejected as a
regression of the locked design.

**Migration path.** First cut: add the postgres-under-restricted-role CI assertion from AF10 that
drives a normal authenticated list view — it goes red immediately and pins the defect — *then* wire
the `execute_wrapper` so ContextVar and GUC share one source.

---

## Finding AF11 — The RLS policy casts the GUC to `uuid` with no empty-string guard, so a pooled connection that has served any `SET LOCAL` request fails *crash* (500) instead of *closed*

**Horizon: now.** **Confidence: High — empirically reproduced** (live PG18, exact policy template,
NOBYPASSRLS role). **Context dependence: wrong-regardless** (the policy is unsafe on any Postgres;
the persistent-connection deployment just makes the bad state the steady state).

**Problem.** Every tenant table shares one policy template (`tenancy.py:395-403`):
`USING (current_setting('app.current_org_id', true)::uuid = organization_id)`. The `true`
(`missing_ok`) argument was chosen so a missing GUC yields `NULL` and the row is hidden
(fail-closed). But `current_setting(...,true)` only returns `NULL` while the GUC has **never been
referenced** on the connection. The moment any statement does `SET LOCAL app.current_org_id = …`
(every explicit `tenant_context()` path — public forms, social public views, billing webhooks) or
`RESET app.current_org_id` (`reset_db_current_org_id`, `current_org.py:143`), the connection's
resting value for that GUC becomes the **empty string `''`**, not unset. And `''::uuid` does not
evaluate to NULL — it **raises `invalid input syntax for type uuid: ""`**, turning the query into a
500. With `conn_max_age=600` persistent connections, `''` is the *steady state* of any connection
that has served even one `SET LOCAL` request, so the fail-closed guarantee is silently replaced by a
fail-crash that recurs on every reused connection.

**Evidence.**
- Policy template with the unguarded cast: `orgs/tenancy.py:395-403` (`_FORCE_RLS_FORWARD_SQL`),
  emitted to every tenant table by `apply_force_rls` (`tenancy.py:412-432`).
- The two primitives that flip the connection to `''`: `current_org.py:124-125`
  (`SET LOCAL app.current_org_id`) and `current_org.py:142-143` (`RESET app.current_org_id`).
- Persistent connections that keep `''` alive across requests: `production.py.j2:125,143`
  (`conn_max_age=600`). Sync Gunicorn workers reuse one connection across many requests.
- **Empirical matrix** (above): `RESET` ⇒ `''` ⇒ ERROR; `SET LOCAL`+txn-end ⇒ `''` ⇒ ERROR; only
  the truly-untouched connection returns NULL ⇒ 0 rows. Script:
  `scratchpad/af9_repro.py` (exact policy SQL, throwaway table + NOBYPASSRLS role, cleaned up).

**Why it compounds.** The defect lives in a single shared template that is *copied into every tenant
table's policy* by migration, so the same bug is uniform across crm/blog/listings/forms/social/
billing and every future module — fixing it means rewriting the template **and re-emitting every
policy** (a migration touching all enrolled tables). Each new tenant table widens the blast radius.
Because the failure mode is per-connection and traffic-dependent (a connection is only poisoned after
it serves a `SET LOCAL` request), it presents as flapping, unreproducible 500s that are maximally
expensive to diagnose — and it interacts with AF9 to make "what does an unscoped query do?"
genuinely undefined (0 rows on a fresh connection, 500 on a recycled one).

**Correct shape.** The policy must treat "no/blank tenant context" identically and safely
(fail-closed to zero rows), regardless of whether the GUC is unset or `''`. The cast must be
empty-string-safe — e.g. `organization_id = NULLIF(current_setting('app.current_org_id', true),'')::uuid`
— and that one expression must be the single source every policy is generated from.

**Trigger for urgency.** Any production traffic that mixes anonymous `SET LOCAL` paths (public form
submit, social public pages, Stripe webhooks) with authenticated/admin reads on the same worker —
i.e., normal traffic. The first poisoned connection turns a tenant page into a 500.

**Compounding factor.** Every enrolled policy already embeds the unguarded cast; the AF1 conformance
gate asserts the policy *exists* but not that it is empty-safe, so the gate passes a broken policy.

**Detection signal.** `invalid input syntax for type uuid: ""` in app logs / Postgres logs; 500-rate
on tenant endpoints correlated with worker/connection age. Add a boundary test asserting both
`NULL`-GUC and `''`-GUC return zero rows (it currently asserts only a `RESET` path it never runs).

**Strongest counter-argument (steelman).** "If AF9 is fixed so the GUC is always a valid uuid on
every request, the `''` state is never observed at query time, so this is moot." Partly true for the
authenticated path — but it does not cover the **exempt admin/operator paths** (no GUC by design) or
any management/console query on a pooled connection, and it leaves a latent fail-crash one refactor
away from re-exposure. The policy should be correct independent of whether callers remember the GUC;
that is the whole point of a DB backstop. You would skip the fix only if you also abandoned RLS as a
runtime backstop (contradicting AF1).

**Alternatives.**
- **(A — preferred) Make the policy empty-string-safe at the source** (`NULLIF(...,'')::uuid`) and
  re-emit every policy via the shared `apply_force_rls` template; extend the conformance gate to
  assert empty-GUC ⇒ 0 rows. One template change, one sweep migration, permanent fix.
- **(B) Set a real typed default for the GUC** (`ALTER DATABASE … SET app.current_org_id = '00000000-…'`
  / a sentinel) so it is never `''`. Avoids the cast error but introduces a magic sentinel and still
  relies on every connection inheriting the default; weaker than fixing the policy.
- **(C) Stop using `RESET`/bare `SET`; only ever `SET LOCAL` inside a transaction and never touch the
  session value.** Reduces how often `''` appears but does not eliminate it (txn-end still reverts to
  `''`), and depends on caller discipline — exactly what a backstop should not require.

**Preferred option + why.** **(A).** It fixes the defect where it lives (the policy), is immune to
caller behavior, and is verifiable by a one-line conformance assertion. (B)/(C) only narrow the
window.

**Migration path.** First cut: change `_FORCE_RLS_FORWARD_SQL` to `NULLIF(current_setting(...),'')::uuid`,
add a conformance assertion that a `''` GUC returns zero rows, and ship one migration that drops and
recreates every enrolled policy from the corrected template.

---

## Finding AF10 — The isolation layer's own conformance and boundary tests are gated behind a database CI never provisions, so green CI certifies only the Python wiring

**Horizon: now.** **Confidence: High** (CI workflows and test skip-guards read directly).
**Context dependence: wrong-regardless** for a product whose headline guarantee is DB-enforced
tenant isolation.

**Problem.** The tests that prove the DB-level isolation layer — the AF1 conformance gate's catalog
assertions and every module's `test_rls_boundary.py` — are all `@pytest.mark.skipif(not _is_postgres)`,
and the CI job that runs the suite uses the SQLite module settings. So the assertions that would
certify "FORCE-RLS is live, policies exist, a restricted role sees only its org" are **skipped on
every CI run**. The one job with a Postgres service (e2e) connects as a **superuser**, which
bypasses RLS entirely. The net: no CI job ever exercises the application under the NOBYPASSRLS
runtime role against FORCE-RLS tables — the exact configuration the whole isolation effort exists
for, and the one in which AF9 manifests.

**Evidence.**
- RLS assertions are postgres-gated and skipped on the default DB: conformance gate
  `orgs/tests/test_tenant_table_conformance.py:503-515` (`test_enrolled_model_has_force_rls_policy`,
  `skipif not _is_postgres`) and `:601-605` (equality-trigger check); module boundary tests
  `crm/tests/test_rls_boundary.py:85-88` (`_skip_if_not_postgres`).
- The default test DB is SQLite and the suite runs against it: `crm/tests/settings.py:28-33`
  (`sqlite3 :memory:`), invoked via `--ds=tests.settings` in the module test loop
  (`Makefile:269,314`).
- The unit/integration CI job provisions **no** Postgres server (`.github/workflows/ci.yml`, "Run
  Tests" job at line 95 — only `postgresql-client-18` binaries for the backups pg_dump contract, no
  `services: postgres`).
- The only Postgres-backed job runs as a superuser: `.github/workflows/e2e.yml:36-44`
  (`services.postgres`, `POSTGRES_USER: test_user` — a superuser in the official image, which
  bypasses RLS). It sets no `RUNTIME_DATABASE_URL` and creates no restricted role.
- What *does* run in CI from the gate is real but SQLite-bounded: registry coverage, manager-type,
  and `base_manager_name` assertions (`test_tenant_table_conformance.py:72-274`) — they prove the
  Python wiring and bookkeeping, not that RLS engages.

**Why it compounds.** This is the meta-instance of the QA thread the prior pass itself identified:
the property tests built to certify isolation are run in a configuration where the mechanism they
test is inert, so they pass for the wrong reason. Every future RLS/tenant change ships green with
its DB-level behavior unobserved; the gap widens with each module. It has *already* compounded — AF9
is an app-wide defect that a single restricted-role postgres run would have caught at the moment AF4
landed. **Worse than "not run": the skipped tests encode a *false* belief.**
`crm/tests/test_rls_boundary.py:215-244` (`test_unset_org_context_returns_zero_rows_contacts`)
does `RESET app.current_org_id` and asserts `count == 0` — but the empirical matrix above shows
`RESET` leaves the GUC at `''`, and `''::uuid` *raises* rather than returning zero rows (AF11). The
suite's author model of "unset ⇒ fail-closed to zero rows" is wrong, and because the test never
runs, nobody found out. A green build is certifying a fail-closed property the database does not
actually provide.

**Correct shape.** The isolation property tests must run in the configuration they assert about: a
CI job with a real Postgres server, migrations applied (FORCE-RLS live), exercising the app under a
NOSUPERUSER/NOBYPASSRLS role — so that "isolation passes" cannot be true while the DB layer is inert.

**Trigger for urgency.** Already triggered (AF9). Independently: any compliance posture that requires
evidence the tenant boundary is tested, or the first isolation regression that the SQLite suite
waves through.

**Compounding factor.** Six `test_rls_boundary.py` suites, the conformance gate's catalog half, and
any future `tenant_context`/GUC wiring all currently sit in the skipped set.

**Detection signal.** Count of `skipped` postgres-gated isolation tests in the CI summary (currently
≈ all of them). Instrument a CI assertion that *fails* if the isolation tests are skipped rather than
run.

**Strongest counter-argument (steelman).** "RLS behavior is Postgres's, not ours, so unit-testing it
on SQLite is pointless and the boundary tests are there for local/manual postgres runs." Partly fair
for the *policy semantics* — but the thing that breaks (AF9) is **our wiring** (which role, which
GUC, set by whom), which only manifests in the integrated postgres+restricted-role config. You would
decline to fix this only if isolation were not a product guarantee — but it is the headline of the
current pivot.

**Alternatives.**
- **(A) Add a Postgres service + restricted runtime role to the main test job** so all existing
  `skipif(postgres)` tests actually run. Lowest new surface; makes the suite honest immediately.
- **(B — preferred) A dedicated `isolation-conformance` CI job:** Postgres service, migrate, create
  the NOBYPASSRLS role, run the conformance gate + all `test_rls_boundary.py` **and** one full
  authenticated-request integration test under that role. Isolates slow DB tests from the fast unit
  job and is the job that catches AF9.
- **(C) Make the conformance gate hard-fail (not skip) for tenant tables when run on a DB that can't
  express RLS** — i.e., refuse to certify isolation on SQLite. Cheapest signal, but doesn't actually
  exercise RLS; best combined with (A)/(B).

**Preferred option + why.** **(B)**, optionally plus **(C)** as a guard so the gate can never again
"pass" by skipping. (B) directly re-creates the missing configuration and is the single job that
would have turned AF9 red on the AF4 commit.

**Migration path.** First cut: stand up the Postgres + NOBYPASSRLS-role CI job and point the
existing (already-written) `test_rls_boundary.py` + conformance catalog tests at it — no new test
code, just the environment they were written for; the AF9 read-returns-zero-rows assertion is the
next line added.

---

## Finding AF3 — Operator escape hatch is a dual, ambient, unaudited bypass (re-confirmed open)

**Horizon: 6–18 months.** **Confidence: High.** **Context dependence: wrong-for-now**, dimension =
*compliance / operator-surface growth*. Unchanged in substance from the prior pass; carried forward
because the roadmap still lists AF3 as the only open isolation task and this pass confirmed it.

**Problem.** Crossing the tenant boundary as an operator is governed by two independent, ambient,
unlogged switches: the per-model `all_objects = TenantManager(super_scope=True)`
(`orgs/managers.py:34-48`, declared on every tenant model) and the identity of the DB role the
process is connected as (`BYPASSRLS` for migrate/superuser vs `NOBYPASSRLS` at runtime). There is no
single authorized, audited "operator access" seam.

**New nuance from this pass.** AF9's mechanics make the operator surface *doubly* inconsistent:
under the runtime `NOBYPASSRLS` role, `all_objects` does **not** actually bypass isolation — it
bypasses only the Python filter, while RLS (GUC unset) still fail-closes the read to zero rows. So
the same `all_objects` call is an unconditional cross-tenant read when run under a `BYPASSRLS`
connection and a zero-row no-op when run under the runtime role. Operator code that "works" today
does so only because operator tooling runs under the superuser `DATABASE_URL`. This makes the case
for collapsing both switches into one explicit, logged `operator_access(reason=...)` seam stronger,
not weaker.

**Evidence / correct shape / alternatives / migration:** unchanged — see **Finding 3** above
(`orgs/managers.py:34-48`; role-level bypass `orgs/apps.py:20-62`; scattered `all_objects` in
`*/admin.py`, `*/services.py`, management commands). Preferred remains a single audited
`operator_access()` boundary that owns both the unfiltered queryset and the privileged connection.

**Sequencing note.** AF3 should land **after** AF9/AF10: the audited seam should be built against a
runtime where the GUC/role wiring is correct and CI-verified, otherwise the seam's own cross-tenant
reads inherit AF9's zero-row behavior and can't be tested.

---

## Finding AF12 — DB-level child-parent org equality is enforced on the child only, so a parent org-move silently orphans children across the tenant boundary

**Horizon: 6–18 months.** **Confidence: High** (trigger SQL read directly). **Context dependence:
wrong-for-now**, dimension = *operator/data-migration surface* (runtime RLS makes a parent org-move
nearly impossible; the gap opens at the operator/`all_objects`/migration level).

**Problem.** AF1's child-table contract is enforced in the DB by a trigger
(`tenancy.py:_EQUALITY_TRIGGER_SQL`) installed `BEFORE INSERT OR UPDATE ON {child_table}` — it
validates, on every *child* write, that `child.organization_id = parent.organization_id`
(`tenancy.py:538-548`). There is **no corresponding trigger on the parent table.** So if a parent
row's `organization_id` is changed (an operator action, an `all_objects` update, a data migration,
or any path that reaches the parent under a BYPASSRLS connection), the children are not
re-validated and are left pointing at the parent's old org — the exact `child.org != parent.org`
state the trigger exists to forbid, now silently present and undetected.

**Evidence.**
- Trigger is child-side only: `tenancy.py:_EQUALITY_TRIGGER_SQL` (`CREATE TRIGGER … BEFORE INSERT OR
  UPDATE ON {child_table}`) and the function body raising only on child writes
  (`tenancy.py:538-548`). No `enable_*` helper installs a parent-side trigger; the enrolled set is
  child tables (`test_tenant_table_conformance.py:592-598`).
- The invariant the trigger claims to guarantee is the AF1 child-table contract (roadmap "Decisions
  locked", AF1 = C): "DB constraint/trigger keeps child `organization_id` equal to the parent's."
  That guarantee holds for child writes and breaks for parent writes.

**Why it compounds.** Every new child/detail table promoted to ENROLLED installs another child-only
trigger and inherits the same one-directional guarantee; the set of tables whose invariant can be
broken by a parent org-move grows with the schema. Once cross-org child rows exist, they are
invisible to the conformance gate (which checks trigger *presence*, not row consistency) and, under
AF9/AF11, also invisible to RLS on the read path — so the corruption is silent and unbounded.

**Correct shape.** The equality invariant must be enforced symmetrically: either a parent-side
`AFTER UPDATE OF organization_id` trigger that cascades/rejects (so the parent cannot move while it
has children, or its children move with it), or a composite FK `(id, organization_id)` →
`(parent_id, organization_id)` so the database itself makes a divergent pair unrepresentable.

**Trigger for urgency.** The first feature or operator workflow that re-parents or migrates an org's
data (org merge, tenant split, GDPR re-assignment) — or any `purge_organization`/migration that
touches a parent's `organization_id`.

**Compounding factor.** The five enrolled child tables (crm notes ×2, forms field/submission/
field-value) each rely on the one-directional trigger today.

**Detection signal.** A periodic consistency query joining each child to its parent on the FK and
asserting `child.organization_id = parent.organization_id`; alert on any mismatch.

**Strongest counter-argument (steelman).** "At runtime, RLS `WITH CHECK` + `USING` make a parent
org-move essentially impossible (you cannot satisfy both the old-org `USING` and new-org `WITH CHECK`
in one GUC value), so the only way to trigger this is an operator with a privileged connection — a
narrow surface." Fair: this is why it is ranked last and `6–18 mo`. But the whole point of the
trigger is to be the backstop for exactly the privileged/operator path that RLS does not cover, and
it only covers half of it.

**Alternatives.**
- **(A — preferred) Composite FK `(parent_id, organization_id)` referencing `(parent.id, parent.organization_id)`.**
  Makes a divergent pair structurally impossible, enforced by the FK with no trigger logic; requires
  a unique constraint on `(id, organization_id)` on the parent. Strongest and simplest to reason
  about.
- **(B) Add a parent-side `AFTER UPDATE OF organization_id` trigger** that either rejects the move
  when children exist or cascades the new org to children. Symmetric with the existing approach;
  more trigger code to maintain.
- **(C) Leave it; rely on the operational consistency check (detection signal) + RLS-makes-it-rare.**
  Lowest effort, accepts silent corruption between checks.

**Preferred option + why.** **(A)** — it converts the invariant from "enforced by two triggers that
must both exist and agree" into a single declarative FK the database cannot violate, which is the
same "make it unrepresentable" philosophy AF1 chose for the column itself.

**Migration path.** First cut: add a unique constraint on `(id, organization_id)` to each enrolled
parent table, then redefine each child's parent FK as the composite `(parent_id, organization_id)`
FK and drop the child-only equality trigger.

---

---

## Finding AF13 — Every module test-settings file defaults to SQLite, violating the PostgreSQL-only policy and serving as the structural root cause of AF10

**Horizon: now.** **Confidence: High** (all 11 module test settings files read directly).
**Context dependence: wrong-regardless** — this is a policy violation independent of deployment
posture.

**Problem.** `decisions.md §Database Policy` prohibits SQLite for any purpose, including tests.
Every first-party module's `tests/settings.py` defaults to `django.db.backends.sqlite3` `:memory:`,
with PostgreSQL reachable only by setting the `QUICKSCALE_TEST_DB=postgres` environment variable.
Since CI never sets that variable, every module's test run executes against SQLite. This is the
**structural root cause of AF10**: the isolation tests skip because the test settings select a
database that cannot run them, and no CI job forces Postgres unconditionally.

**Violation inventory.** All 11 module test settings files:
- `quickscale_modules/orgs/tests/settings.py:80-85` — SQLite `:memory:` default, Postgres behind env-var guard
- `quickscale_modules/crm/tests/settings.py:28-33`
- `quickscale_modules/billing/tests/settings.py:49` (same pattern)
- `quickscale_modules/blog/tests/settings.py:59`
- `quickscale_modules/listings/tests/settings.py:62`
- `quickscale_modules/forms/tests/settings.py:32`
- `quickscale_modules/social/tests/settings.py:75`
- `quickscale_modules/auth/tests/settings.py:21`
- `quickscale_modules/notifications/tests/settings.py:59`
- `quickscale_modules/storage/tests/settings.py:15`
- `quickscale_modules/analytics/tests/settings.py:44`

**Additional violations:**
- `quickscale_core/tests/test_generated_project_runtime.py:123-133` — writes a SQLite settings file
  into the generated project for a "no-Docker-required" smoke test; rationale is understandable but
  still policy-violating and should be replaced with a Postgres-backed smoke test job.
- `quickscale_modules/crm/src/quickscale_modules_crm/migrations/0005_tag_owner_bucket_unique.py:11`
  and `0007_stage_terminal_semantic_bucket_unique.py:12` — inline comments justify a migration
  design choice as "portable across SQLite (test) and PostgreSQL"; this portability concern is
  obsolete once tests are Postgres-only.

**Note:** `test_dr_engine_primitives.py` tests the `_database_engine_family` routing function by
passing the string `"django.db.backends.sqlite3"` — this is testing router logic, not using SQLite
as a DB, and is not a violation.

**Why it compounds.**
- Every new module added to the repo inherits the same SQLite-default template from the module
  checklist (`decisions.md §Module Implementation Checklist`). The checklist itself is the vector
  that reproduces this violation.
- Migrations designed for SQLite portability (`partial-index approach is portable across SQLite
  (test) and PostgreSQL`) create weaker schema choices; with Postgres-only testing those constraints
  dissolve and the optimal Postgres-native approach can be used directly.
- The `QUICKSCALE_TEST_DB` escape hatch gives the illusion of optionality, making the violation
  invisible during routine code review.

**Correct shape.** Every `tests/settings.py` must unconditionally configure `django.db.backends.postgresql`
with connection parameters from environment variables (sensible CI-friendly defaults). The
`QUICKSCALE_TEST_DB` env-var branch and the SQLite fallback block must be deleted. The Module
Implementation Checklist must be updated so new modules start with a Postgres-only test settings
file. The generator smoke test must be reworked to provision a real Postgres container in CI.

**Relationship to AF10.** AF10 is the CI infrastructure gap (no Postgres service in the test job,
isolation tests skipped). AF13 is the code-level cause: test settings files that make SQLite the
default ensure the tests skip even if the developer means to run them locally. Fixing AF10 (adding a
Postgres CI service) without fixing AF13 still requires every developer to remember `QUICKSCALE_TEST_DB=postgres`.
Fix AF13 first so that Postgres is the unconditional baseline, then AF10's CI job fix is just adding
the `services: postgres` block.

**Migration path.** Delete the `else` branch (SQLite fallback) from all 11 `tests/settings.py`
files; replace with a single unconditional Postgres block reading `QS_*_DB_*` env vars with sensible
defaults (`localhost:5432`). Update the module checklist's `tests/settings.py` template. Then land
the AF10 CI job fix.

**Detection signal.** Grep for `sqlite3` in any `tests/settings.py` — currently returns 11 hits and
must trend to zero. Add to CI a step that fails if the pattern appears.

---

*Lenses scanned with no new qualifying finding this pass: III (module cohesion — generator god-files
resolved AF6), V (webhook idempotency — billing `handle_stripe_event` correctly records + locks +
dedups on `stripe_event_id`, `services.py:911-998` — verified, not a finding), VI (observability —
`CorrelationIdMiddleware` now present in generated `base.py.j2`, narrowing the prior Deferred note),
VII (API/contract versioning — already owned/deferred), XIII (build/release — generator cluster
resolved AF5–AF8).*
