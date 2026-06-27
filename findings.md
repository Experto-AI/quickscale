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

**What this pass found.** Track 1 made isolation a *data-layer* guarantee in principle, but the guarantee is assembled from three mechanisms that must independently agree — the Django `TenantManager`, the Postgres FORCE-RLS policy, and a hand-set `app.current_org_id` GUC — and **the structural glue that would keep them in sync does not exist**. There is no conformance gate proving every tenant table is actually covered; the auto-scoping manager is wired as Django's *base* manager so all ORM graph traversal silently depends on an ambient contextvar; and the operator escape hatch is a dual, ambient bypass with no audited seam. The previous round's open carryover (request-long transaction around external I/O) is re-confirmed and has **broadened** since T1.20 removed the per-route gating.

**Already acknowledged, not re-reported.** The roadmap's Deferred/Monitor list owns: no structured logging/correlation IDs (D9a is a baseline only), no versioned public API, no webhook payload-boundary validation. The module-upgrade story (subtree pull + "Module Extension Contract", `docs/technical/module-extension.md`) is **deliberate, documented design** — excluded. Single-PR items (Stripe `api_version` pin, per-admin `select_related`, the personal-org-create-per-request micro-cost) are out of scope by the autopsy's own rules.

---

## Ranked findings

| # | Finding | Horizon | Blast radius × likelihood |
|---|---------|---------|---------------------------|
| 1 | Tenant-table isolation is per-table hand-written SQL with **no conformance gate**; child tables without `organization_id` sit outside *both* isolation layers | **now** (dev) → **6–18 mo** (first cross-tenant prod leak) | Cross-tenant data leak × high (recurs every model/table added) |
| 2 | The auto-scoping contextvar `TenantManager` is the **default *and* base manager**, so every non-request code path must re-establish ambient org context — already re-implemented 3× | **now** | Broken operator/job paths + leak-via-bypass × high |
| 3 | The operator escape hatch is a **dual, ambient, unaudited bypass** (`all_objects` *and* the connected DB role's `BYPASSRLS`) with no single authorized seam | **6–18 mo** | Silent cross-tenant operator leak × medium |
| 4 | Wrapping the whole request in one transaction (to carry `SET LOCAL`) couples DB connection-hold time to in-view external I/O (Stripe) — *carryover, broadened by T1.20* | **6–18 mo** | Connection/lock exhaustion × medium-high under traffic |
| 5 | `quickscale apply` is a 16-step, **all-irreversible**, cross-system mutation (git + FS + Docker + DB migrations + **remote Railway deploy**) whose only recovery is convention-based "idempotent-rerun" — no rollback, no compensation, no per-step verification | **6–18 mo** | Half-applied project / failed remote deploy × medium |
| 6 | The generator's hottest logic is concentrated in **god files** (`apply_command.py` 3.1k, `dr_engine/orchestration.py` 3.7k, `module_config.py` 2.1k, `resolvers.py` 1.9k, `entry_point.py` 1.6k) — serial merge chokepoints that directly fight the documented 3-worktree parallel workflow | **now** (dev) | Merge conflicts / Tier-3 risk concentration × high |
| 7 | The "self-describing module" decision (D3) only half-landed: rich modules (billing, crm, social) still carry **hand-written imperative adapters keyed by module name inside `quickscale_core`** (`MANIFEST_ADAPTER_REGISTRY`), so adding a non-trivial module means editing core, not just shipping a module | **6–18 mo** | Per-module coordination tax × medium |

**These findings span two distinct domains.** Findings 1–4 sit on the **runtime multi-tenant isolation** seam (the `quickscale_modules/*` + `orgs` machinery that runs inside a generated app). Findings 5–7 sit on the **generator/CLI** seam (`quickscale_core` + `quickscale_cli` — the `plan`/`apply` engine itself) and were surfaced specifically by broadening the autopsy past the isolation pivot. The two domains share almost no files, which is what makes them parallelizable (see the roadmap track assignment).

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

**Time horizon: now (already causing pain).**

**Problem.** Every tenant model declares `objects = TenantManager()` first and sets no `Meta.base_manager_name`. `TenantManager.get_queryset()` filters on a request-scoped `ContextVar` and returns `.none()` when it is unset. Because the first-declared manager is also Django's `_base_manager`, **forward-FK access, `refresh_from_db()`, the cascade-delete collector, admin inlines, and serializer relations all traverse the object graph through the auto-scoping manager** — so any code running outside the request cycle (management commands, the Stripe webhook, admin, DR/backups, signals, shell) gets empty results or `DoesNotExist` unless it first re-establishes the ambient context by hand.

**Why it compounds.** The "ambient context" requirement leaks into every surface that isn't an ordinary request, and each surface re-solves it locally:
- There are already **three independent re-implementations** of "set the contextvar + `SET LOCAL` for non-middleware code": `orgs.current_org.set_current_org_for_context` (T1.17), billing's `_billing_org_db_context` (`billing/.../services.py:912`, used at `:1075,:1173,:1325,:1461`), and social admin's `_org_db_context` (`social/.../admin.py`, wraps *every* admin view in `atomic()` + `SET LOCAL`). Each is the same capture-set-restore dance, written three times.
- The escape hatch doesn't escape: `all_objects` bypasses scoping on the *queried* model, but related-object traversal still goes through the *related* model's base manager. So `deal.contact` under no context raises `DoesNotExist` even when fetched via `all_objects` — which is exactly why `crm/.../models.py:282-298` (`ContactNote.save`) has to reach for `Contact.all_objects.filter(...).update(...)` with a comment explaining the contextvar is unset on operator/inline paths.
- Every new management command, async job, webhook, or admin surface must independently remember to wrap itself in org context (and, if it spans orgs, loop and re-set per org) — the precise "every callsite must remember" procedural burden that the contextvar manager was introduced to remove. The burden simply moved from "remember to filter" to "remember to set context."

**Evidence.**
- `orgs/.../managers.py:38-48` — `TenantManager.get_queryset()` reads the contextvar and returns `qs.none()` when `org_id is None`.
- No `base_manager_name`/`default_manager_name` anywhere under `quickscale_modules/*/src` (grep returns nothing), so `objects = TenantManager()` (declared first on every tenant model, e.g. `crm/.../models.py:41-42`, `blog/.../models.py:127-128`) is the `_base_manager`.
- The three duplicated context wrappers cited above; the `ContactNote.save` workaround at `crm/.../models.py:282-298`.
- `_resolve_active_org` (the *read* side of the same missing boundary) is itself re-implemented per module: `crm/.../views.py:43-74`, `blog/.../views.py`, `billing/.../services.py`, `social/.../admin.py` — each with its own personal-org fallback.

**Correct shape.** There should be exactly one owned "tenant context" boundary, and the auto-scoping manager must **not** be the base manager. Concretely: set `Meta.base_manager_name = "all_objects"` (or an unfiltered base) so Django internals never silently scope; expose a single `tenant_context(org_id)` context manager (the one already half-built as `set_current_org_for_context`) that all non-request callers use; and — to remove the burden entirely — apply the GUC at the connection level (a `connection_created`/checkout hook keyed to the resolved org) so RLS is satisfied without each surface re-deriving it. The contextvar manager stays as the *default* (`objects`) for ergonomic request-time scoping, but it stops governing the framework's own graph traversal.

**Alternatives.**
- **(A — preferred) Demote the scoping manager from base + one shared `tenant_context()` used everywhere.** Set `base_manager_name` to an unfiltered manager on `TenantModel`; collapse the three wrappers into the single `orgs` primitive; keep `objects` auto-scoping for views. *Preferred: it removes the silent `DoesNotExist`/empty-result class of bugs from all framework-internal paths at once, deletes duplicated context code, and is a contained change (one base class + delete two wrappers) because the shared primitive already exists.*
- **(B) Stop auto-scoping in the manager; require explicit `.for_org()` + lean entirely on RLS.** Matches what `organizations.md` §F11.13b actually documents (a `.for_org()` contract that the code no longer implements). Makes scoping explicit and removes the ambient-context dependency from Django internals. But it surrenders the "manager catches a forgotten filter" safety at the Python layer and makes RLS the *sole* guard — which is only safe once Finding 1's coverage gate exists, so this should follow (A), not replace it.
- **(C) Connection-level GUC via a pool/checkout hook; leave managers as-is.** Apply `app.current_org_id` when a connection is checked out for a resolved org, so RLS is satisfied without per-surface wrappers. Solves the *DB* half cleanly (and dovetails with Finding 4), but the Python base-manager traversal still scopes on the contextvar, so it must be combined with (A) to fix the `DoesNotExist` class.

**Trigger for urgency.** The next batch operation that touches tenant data across orgs — a billing reconciliation command, a DR restore, an analytics rollup, or any Celery/Django-Q job the roadmap adds — will either silently no-op (contextvar unset → `.none()`) or be written with a fourth copy of the context wrapper. It is already biting at admin/inline/webhook scope today.

**Compounding factor.** Billing services, social admin, the `orgs` helper, every `all_objects` callsite, and `purge_organization`/`migrate_billing_to_orgs` are all written against the current ambient-context assumption and will be touched when the base manager is corrected.

**Detection signal.** Grep-able proxy now: count of `all_objects` references and of bespoke `*_db_context`/`set_current_org_*` wrappers (rising = the tax compounding). Runtime: log `CurrentOrgError` and unexpected `RelatedObjectDoesNotExist` from non-request entrypoints (management commands, webhook handlers) — a nonzero rate there is this finding firing.

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

**Time horizon: 6–18 months.**

**Problem.** Because `app.current_org_id` is set with `SET LOCAL`, which only survives inside a transaction, `TenantMiddleware._call_with_org` wraps the *entire* downstream view in a single `transaction.atomic()` — so every org-scoped request holds an open transaction (and its DB connection) for its full duration, including template rendering and any synchronous external API calls the view makes. Since T1.20 removed the per-route gating (`_SOLO_ROUTE_PREFIXES` no longer exists), this now applies to **every authenticated org-scoped request**, not just billing routes.

**Why it compounds.** Billing checkout/portal views make 2–4 sequential Stripe calls *inside* that request transaction; the webhook path holds its own transaction across Stripe `retrieve_*` calls via `_billing_org_db_context`. As traffic grows and as more views add external calls (email, more Stripe, future providers), the number of connections sitting `idle in transaction` during third-party latency grows linearly, and Postgres `max_connections` (not CPU) becomes the ceiling. Row locks held across network calls also lengthen lock-wait chains on contended rows (credit balance, subscription).

**Evidence.**
- `orgs/.../middleware.py:171-177` — `try: with transaction.atomic(): self._set_current_org_id(...); return self.get_response(request)` wraps the whole view; reached by every authenticated, non-exempt request (`EXEMPT_PATH_PREFIXES` is only `/accounts/`, `/admin/`, `/healthcheck/` — `middleware.py:43`), so `/billing/...` is included.
- `billing/.../services.py:511,525` (`create_checkout_session`) and `:564` (`create_subscription_checkout_session`) issue `retrieve_price` → `create_checkout_session` sequentially inside the request transaction.
- `billing/.../services.py:912` (`_billing_org_db_context`) wraps webhook handling in `atomic()` + `SET LOCAL`, holding it across `retrieve_subscription` (`:1284`) / `retrieve_payment_intent` (`:1788`).
- `production.py.j2:114,132` — `conn_max_age=600` (persistent connections), so each worker pins a connection that can sit idle-in-transaction.

**Correct shape.** Org context for reads should not require holding a transaction across view I/O. Set the tenant GUC at connection acquisition (a `connection_created`/checkout hook re-applying `set_config(..., is_local := true)` at transaction start — the same hook Finding 2(C) wants) so RLS is enforced without a request-long transaction; external API calls live *outside* any DB transaction, with DB writes committed before/after the network round-trip (or via an outbox), never around it.

**Alternatives.**
- **(A — preferred) Connection-init hook sets the GUC; views open short transactions only around writes.** A thin pool/`connection_created` hook applies `app.current_org_id` when the org is resolved, decoupled from request-long `atomic()`; external calls run outside transactions. *Preferred: it keeps RLS enforcement while removing the structural "transaction = request" coupling that turns third-party latency into connection exhaustion — and it is the same seam Finding 2 needs, so the two findings share one fix.*
- **(B) Keep the request transaction but move all external I/O out of views** into pre/post hooks or deferred/async flows. Smaller routing change, but pushes complexity into every external-calling view and does nothing for template-render hold time.
- **(C) Accept it; cap blast radius operationally** — `idle_in_transaction_session_timeout`, PgBouncer, more workers. Buys headroom without a design change, but PgBouncer *transaction* pooling is incompatible with session-level `SET`, so it interacts badly with the very mechanism RLS depends on.

**Trigger for urgency.** A Stripe latency incident, a traffic step-change, or raising `WEB_CONCURRENCY` — any of which turns "connection held during network call" into pool/`max_connections` exhaustion and cascading 5xxs.

**Compounding factor.** Every billing view and webhook handler, plus any future module that calls an external service from within a request, is already written assuming the ambient request transaction.

**Detection signal.** Watch Postgres `state = 'idle in transaction'` connection count and `pg_stat_activity` transaction age; alert on idle-in-transaction duration p95 climbing with Stripe API latency.

---

---

## Finding 5 — `quickscale apply` is a 16-step, all-irreversible, cross-system mutation with no rollback and convention-based "idempotent-rerun" as the sole recovery

**Time horizon: 6–18 months.**

**Problem.** The apply pipeline executes 16 ordered steps, **every one tagged `reversible=False`**, that mutate five independent systems in sequence — git (subtree embedding makes commits), the filesystem (template generation), env files, Docker (`docker startup`), the **database (`database migrations`)**, and a **remote Railway deploy** — and only then writes authoritative state. There is no rollback and no compensation; the only recovery mechanism is that each step is *asserted by convention* to be idempotent on rerun, gated purely by the presence of an `apply-recovery.yml` file.

**Why it compounds.** The pipeline reaches further into irreversible and *remote* territory as it grows, while the recovery model stays "rerun the whole thing and trust every step is idempotent":
- A crash between the post-embed snapshot (step 2) and authoritative state persistence (step 15) leaves git commits, generated files, a started container, applied DB migrations, and possibly a *triggered Railway deploy* on disk/remote that the canonical `state.yml` does not record — reconciliation depends entirely on every intervening step being correctly re-runnable.
- Idempotency is a per-step property maintained by hand with no enforcing harness: there is no test that injects a failure at step N and asserts a clean rerun converges. Each new step (the registry already grew to 16) adds another hand-verified idempotency obligation.
- The destructive/remote steps (DB migrations, Railway deploy) sit *inside* the same linear script as cheap local steps, so a transient failure in a late step re-runs early irreversible steps' idempotency logic every retry.

**Evidence.**
- `quickscale_core/.../apply/step.py:64-193` — `APPLY_STEPS`, 16 entries, **all `reversible=False`**; the docstring (`:39-46`) states "There is no rollback today; all irreversible steps use `idempotent-rerun`."
- Cross-system steps: `step.py` step 12 `docker startup`, step 13 `database migrations`, step 14 `railway deploy`, step 15 `authoritative state persistence` (state written *after* all mutations).
- Railway deploy is in-pipeline, gated only on link presence: `apply_command.py:2982-3012` (`if (ctx.output_path / ".railway").is_dir(): … failed_step=_FAILED_STEP["railway deploy"]`).
- Recovery is presence-gated and explicitly diagnostic-only: `apply/ledger.py:10-19` ("Resume gating is driven purely by whether the ledger file *exists* … `step_progress` … must never be used as a resume gate").

**Correct shape.** Apply should be a step framework with an explicit per-step contract — `is_satisfied()` (already-done check), `apply()`, and `compensate()`/forward-fix — and a checkpoint written *after each* step, not only at the end, so recovery is "resume at the first unsatisfied step" rather than "rerun all 16 and hope." Remote/destructive steps (Railway deploy, migrations) should be the last, separately-confirmable phase, fenced off from local scaffolding, so a failure in cheap local steps never risks a half-finished remote.

**Alternatives.**
- **(A — preferred) Promote the implicit step list into an executor with per-step `is_satisfied()` + post-step checkpointing + a fault-injection test harness.** Keep "no rollback" for genuinely irreparable steps, but make "resume at first unsatisfied step" structural and *tested*. *Preferred: it keeps the team's deliberate idempotent-rerun philosophy while removing its weakest assumption (untested, all-or-nothing rerun) and makes adding step 17 a matter of implementing a contract, not extending a 3k-line script.*
- **(B) Split apply into two phases: local scaffolding (idempotent, safe to rerun) and a separate `deploy` phase (Railway/migrations) the operator runs explicitly.** Removes the remote/destructive steps from the auto-run pipeline — smaller blast radius per `apply` — but changes the one-command UX and doesn't fix per-step recovery for the local phase.
- **(C) Leave the pipeline; add only the fault-injection test suite that proves rerun-convergence for each step.** Lowest effort, real confidence gain, but it's the additive-only option the autopsy explicitly discounts — it documents the current shape's safety without changing the all-or-nothing recovery model.

**Trigger for urgency.** The first `quickscale apply` that fails mid-`railway deploy` or mid-`migrations` on a real linked project — leaving a half-deployed remote with no recorded state — or adding apply steps 17+ that reach a new external system (e.g. DNS, object storage).

**Compounding factor.** The recovery ledger, the 16-step registry, the `_FAILED_STEP` sentinels, and every existing step's ad-hoc idempotency logic are all built on the current linear-script shape.

**Migration path.** First cut: add the fault-injection harness (run apply, kill after step N, rerun, assert convergence) for the existing 16 steps — it's read-mostly, surfaces which steps are *not* actually idempotent today, and is the evidence base for introducing the per-step `is_satisfied()` contract.

**Detection signal.** Count `quickscale apply` invocations that re-enter via the recovery ledger (resume rate) and the rate of applies that abort with a `_FAILED_STEP` sentinel at steps 12–14; a rising resume/abort rate at the remote/destructive steps is this finding firing.

---

## Finding 6 — The generator's hottest logic is concentrated in god files that fight the project's own parallel-worktree workflow

**Time horizon: now (development-time friction).**

**Problem.** The decision-dense core of the generator lives in a handful of multi-thousand-line files — `apply_command.py` (3,136), `dr_engine/orchestration.py` (3,682), `module_config.py` (2,098), `contracts/resolvers.py` (1,903), `manifest/entry_point.py` (1,564) — each owning many unrelated concerns. The project's stated development model is three git worktrees developing *in parallel* and merging to `v87`, but the work that milestones actually require routes through these same few files, making them serial chokepoints.

**Why it compounds.** This is "wrong for where the team is now": the team has explicitly committed to a parallel-track workflow (`roadmap.md:17-43`, the `wt-track1/2/3` merge dance), so the cost of the monolith is paid as merge conflicts and coordination overhead on *every* milestone that touches apply, manifest resolution, or DR — which is most of them. As more modules and apply steps are added, these files grow, more tracks need them simultaneously, and the conflict surface widens. The roadmap's own "keep tasks out of Tier 3" discipline (`roadmap.md:68-70`) is undermined when the single-concern task still has to edit a 3k-line shared file.

**Evidence.**
- File sizes (lines, non-migration): `dr_engine/orchestration.py` 3,682; `apply_command.py` 3,136; `cli/.../module_config.py` 2,098; `core/.../contracts/resolvers.py` 1,903; `manifest/entry_point.py` 1,564; `cli/.../module_commands.py` 1,563.
- `dr_engine/orchestration.py` mixes ~20+ top-level classes/protocols (`_RemoteUploader`, `StagedAdminRestoreUpload`, lock errors, backend selection, …) in one module.
- The already-open roadmap task (D1) lists scope across generator templates **+** `orgs` **+** `billing` simultaneously — a concrete instance of one task fanning across files multiple tracks share.

**Correct shape.** The apply pipeline, the manifest/adapter resolution, and the DR engine should each be a package of small single-responsibility modules behind a thin orchestrator — so a given milestone's change lands in a leaf file owned by one concern, and two tracks editing "apply" usually edit different leaves. The orchestrator stays small and changes rarely; the volume lives in independently-evolvable parts.

**Alternatives.**
- **(A — preferred) Extract the step bodies of `apply_command.py` into a `quickscale_core/apply/steps/` package (one module per step), leaving a thin CLI orchestrator; do the same split for `dr_engine/orchestration.py` by concern (locking, upload, restore, verification).** *Preferred: it directly converts the merge chokepoint into per-concern leaf files that map onto the step registry that already exists (`apply/step.py`), so the decomposition has a ready-made seam and pairs naturally with Finding 5's executor.*
- **(B) Leave file structure; enforce module ownership via CODEOWNERS + assign each god file to a single track per milestone.** Process fix, zero code risk — but it serializes work by fiat (only one track may touch apply per milestone), which throttles the parallelism the worktree model exists to provide.
- **(C) Split only the worst offender (`dr_engine/orchestration.py`) now, defer the rest.** Pragmatic triage; reduces the single largest conflict surface. But it leaves `apply_command.py`/`entry_point.py` as chokepoints exactly where Findings 5 and 7 are about to add work.

**Trigger for urgency.** Already active: any milestone where two tracks both need apply or manifest changes (the isolation work in Findings 1–4 touches module wiring while generator work in Findings 5/7 touches the same apply/manifest core). The next multi-track milestone pays this in merge conflicts.

**Compounding factor.** Findings 5 (apply executor) and 7 (adapter registry) both land in these exact files; doing them without decomposition deepens the monolith.

**Migration path.** First cut: extract `apply_command.py`'s 16 step bodies into `apply/steps/<step>.py` modules called by a thin loop — mechanical, behaviour-preserving, and it creates the per-step seam Finding 5 needs.

**Detection signal.** Track merge-conflict frequency per file across the `wt-track*` merges (git can report conflict hotspots); a small set of files dominating conflict resolution time is the measurable symptom.

---

## Finding 7 — "Self-describing modules" only half-landed: rich modules still carry hand-written adapters keyed by name inside core

**Time horizon: 6–18 months.**

**Problem.** Decision D3 chose "self-describing manifests + a generic resolver; delete the `if`-ladder" (`roadmap.md:53`). In practice the `if`-ladder became a `MANIFEST_ADAPTER_REGISTRY` of **hand-written, per-module imperative adapter functions living in `quickscale_core`** (`_billing_manifest_adapter`, `_crm_manifest_adapter`, `_social_manifest_adapter`), plus a whole module-specific file (`manifest/social_manifest.py`). So a module is only "self-describing" if its needs fit the manifest schema; the moment it needs real wiring, the logic goes back into core, keyed by the module's name.

**Why it compounds.** The generator's core value proposition is "add a module." But adding a *non-trivial* one is an N-place coordinated edit in core, not a self-contained module drop: a `module.yml`, a `ModuleCatalogEntry` in `contracts/module_catalog.py`, discovery in `contracts/module_discovery.py`, and — for anything beyond the schema — a bespoke adapter function registered in the 1,564-line `entry_point.py`. Every new rich module grows `entry_point.py` and re-couples core to that module's specifics, eroding the "generic resolver" the decision was meant to buy. It also means a module's behavior is split across two repos-worth of mental model (the module package *and* its core adapter), so the subtree-distributed module is not actually the whole module.

**Evidence.**
- `manifest/entry_point.py` — `MANIFEST_ADAPTER_REGISTRY["billing"]` (`:307`), `["crm"]` (`:483`), `["social"]` (`:1511`); 110 occurrences of concrete module names in a "generic" resolver.
- `manifest/social_manifest.py` — an entire module-specific adapter module inside the generic `manifest/` package (provider catalog, URL helpers, renderers for social only).
- Module-add touch points spread across `contracts/module_catalog.py`, `contracts/module_discovery.py`, `manifest/entry_point.py` — the catalog still ships a static `MODULE_CATALOG` tuple for UX labels alongside manifest discovery.

**Correct shape.** Whatever a module needs to wire itself should be expressible *by the module* — either declaratively in its `module.yml`/manifest schema, or via an adapter that ships *inside the module package* and is discovered (entry-point / registered hook), not hand-written into core keyed by name. Core owns the generic resolver and the contract; modules own their own wiring. Adding a module then touches zero core files.

**Alternatives.**
- **(A — preferred) Move each module's adapter into the module package and discover adapters via the manifest/entry-point mechanism (core holds only the protocol).** Relocate `_billing/_crm/_social` adapters and `social_manifest.py` next to their modules; core's registry is populated by discovery, not literals. *Preferred: it finishes the D3 decision the code drifted from, makes a module genuinely self-contained for subtree distribution, and removes core edits from the "add a module" path.*
- **(B) Extend the manifest *schema* until billing/crm/social fit it declaratively, deleting the adapters.** The purest "data-driven" end state. But the three modules need imperative behavior (OAuth provider URL building, Stripe wiring) that is awkward-to-impossible to express as static data, so this risks an over-rich, leaky schema — partial at best.
- **(C) Accept core-side adapters; just relocate them out of `entry_point.py` into one file per module under `manifest/adapters/`.** Improves the god-file problem (Finding 6) and readability without changing the boundary. Lowest risk, but core still changes whenever a rich module is added — the coordination tax remains.

**Trigger for urgency.** The next rich first-party module (the `teams` placeholder is already stubbed, or any client-specific module an agency wants to add) forces another core adapter and another `entry_point.py` growth spurt; a third-party/client module that "should" be droppable cannot be, because its wiring must live in core.

**Compounding factor.** The three existing adapters, `social_manifest.py`, the static `MODULE_CATALOG`, and `entry_point.py`'s size are all built on the core-owns-module-wiring assumption.

**Migration path.** First cut: relocate one adapter (`_social_manifest_adapter` + `social_manifest.py`) into the social module package and have core discover it — proving the entry-point discovery path before moving billing/crm.

**Detection signal.** Count concrete module-name literals in `quickscale_core` (grep) and `entry_point.py` line count over time; both should fall, not rise, as modules are added.

---

## Cross-finding note for roadmap planning

The seven findings form **two independent clusters** that share almost no files, plus one internal dependency chain:

- **Runtime isolation cluster (Findings 1–4)** — all touch `orgs/` + the tenant modules. They are *not* freely parallel among themselves: **Finding 1's conformance gate + `TenantModel` base is the prerequisite**, after which **Findings 2 and 4 share a single fix** (a connection-level GUC hook that both lets the base manager stop governing graph traversal *and* removes the request-long transaction), and **Finding 3** (operator seam) lands last on the hardened base. Sequence: **1 → (2 + 4) → 3.**
- **Generator cluster (Findings 5–7)** — all touch `quickscale_core`/`quickscale_cli`. **Finding 6 (decompose the god files) is the enabler**: doing it first creates the per-step/per-adapter seams that **Finding 5 (apply executor)** and **Finding 7 (push adapters into modules)** then land on cleanly. Sequence: **6 → (5, 7).**

Because the two clusters touch disjoint file sets, they parallelize across worktrees with no merge contention. The roadmap below assigns the isolation cluster to track 1 (foundation) + track 2 (shared-fix seam) and the entire generator cluster to track 3.

---

## Cross-cutting QA / testing thread

The autopsy folded template **Section VIII (Testing)** into the findings rather than reporting it separately, because the testing gap is not a standalone weakness — it is the *mechanism* by which three of the structural findings stay invisible. They share one failure mode:

**The test suite exercises the happy request path — which is exactly the path on which the broken mechanism still appears to work.** A forgotten RLS migration still scopes reads in the Python happy path (Finding 1); the ambient-context base manager still resolves FKs inside a request (Finding 2); a non-idempotent apply step still succeeds on a clean first run (Finding 5). So example-based, happy-path tests pass and give *false confidence*; the defect only surfaces off the tested path — an `all_objects`/operator read, a management command, a non-request webhook, or a mid-pipeline crash.

The structural remedy in each case is the same shape — a **property / conformance test (enumerate-and-assert or fault-inject-and-assert)**, not another example-path test:

| Finding | Today's test reality | The property test that closes it |
|---|---|---|
| **1** | `tests_shared/isolation.py:19-57` asserts a *response-level* property for chosen endpoints only — no table-level coverage check | Walk `apps.get_models()`, select tenant tables, assert each has a live FORCE-RLS policy in `pg_policies` (build-time conformance gate) |
| **2** | Request-path scoping is covered; non-request FK traversal is not | Regression test: forward-FK traversal + `refresh_from_db()` with **no** org context set must succeed (not raise `DoesNotExist`) |
| **5** | Idempotent-rerun is asserted by convention (`apply/ledger.py:10-19`), with no enforcing test | Fault-injection harness: kill after step N, rerun, assert convergence for all 16 steps |

These map to roadmap tasks **AF1** (conformance gate), **AF2** (no-context FK regression test), and **AF5** (fault-injection harness) — split across tracks 1 and 3, but one QA-hardening spine. Tracked together, they convert a silently-passing happy-path suite into a build that *fails* when the structural guarantee is actually absent. Land **AF1's conformance gate first**: it is read-only, surfaces today's true RLS coverage (including the `ContactNote`/`DealNote` child-table gap), and is the evidence base the others build on.
