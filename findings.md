# Structural Autopsy: QuickScale (v87 / post–Track-1)

## Orientation

**What it is.** A creator-led Django *project generator* (`quickscale plan` → `quickscale apply`) plus a workspace of ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated projects via **git subtree** and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core` (core is Django-free by invariant).

**Near-term growth direction.** The dominant work of the last ~18 milestones is **retrofitting multi-tenant isolation** onto every module: a contextvar `TenantManager`, a NOT-NULL org FK contract, a `solo`→`saas` runtime mode, org-authoritative billing, and (Track 1, just merged) PostgreSQL FORCE RLS on all six tenant table-sets. The product is mid-pivot from a single-user scaffold into a multi-tenant SaaS substrate. Every finding below sits on the seam that pivot just stressed.

**Deployment context.** Generated apps run WSGI/Gunicorn (sync workers, `conn_max_age=600` persistent connections), single Railway project, shared Postgres. No existing users; the project's standing rule is **clean break — no back-compat, no migration path** (squash/rewrite migrations, delete dead paths).

**Prior autopsy status.** The previous round's Findings 1, 2, 4, 5 are recorded as resolved (CHANGELOG M12–M18). This is a fresh pass over the *post-RLS* shape. The headline: Track 1 made isolation a data-layer guarantee *in principle*, but the guarantee is now distributed across three mechanisms (Django manager + Postgres RLS + manual filters) that must all agree, and the operative one (RLS) is **opt-in via an env var that fails open**. That is the spine of Findings 1–2.

**Current autopsy resolution status (2026-06-26).** Finding 1 (RLS fails open) → resolved by T1.18 (boot guard in `QuickscaleOrgsConfig.ready()`). Finding 2 (two carriers + pervasive `all_objects`) → resolved by T1.19 (`org_scope()` unified primitive). Finding 4 (two routing models) → resolved by T1.20 (slug-routing fallback deleted). Finding 5 (static MODULE_CATALOG) → resolved by D2 (manifest-backed discovery canonical). **Finding 3 remains open** — request-scoped transaction/Stripe I/O coupling; tracked as D8 in roadmap (6–18 month horizon, production trigger required).

**Already acknowledged, not re-reported here.** The roadmap's Deferred/Monitor list already owns: no structured logging/correlation IDs, no versioned public API, no webhook payload-boundary validation, and the static `MODULE_CATALOG` tuple (kept below as the one tracked residual). Single-PR items (Stripe `api_version` pin, orphaned `apply-recovery.yml`, per-admin `select_related`) are out of scope by the autopsy's own rules. The module-upgrade story (subtree pull + "Module Extension Contract", `docs/technical/module-extension.md`) is a **deliberate, documented design** — excluded, not a load-bearing wrong decision.

---

## Ranked findings

| # | Finding | Horizon | Blast radius × likelihood |
|---|---------|---------|---------------------------|
| 1 | RLS enforcement is opt-in via `RUNTIME_DATABASE_URL` and fails **open** | **now** | Cross-tenant data exposure × high (one env var, no boot guard) |
| 2 | Tenant isolation is re-implemented procedurally outside middleware (two carriers + pervasive `all_objects`) | **now** | Cross-tenant leak × high (already pervasive) |
| 3 | Request-scoped DB transaction couples connection-hold time to in-view external I/O (Stripe) | **6–18 mo** | Connection/lock exhaustion × medium-high under traffic |
| 4 | Two contradictory tenant-routing models, hardcoded as module frozensets, contradict the locked single-URL ADR | **6–18 mo** | Routing/auth confusion × medium |
| 5 | Static `MODULE_CATALOG` tuple is a second registry beside manifest discovery (tracked residual) | **2+ yr** | Coordination tax × low |

---

## Finding 1 — RLS, the new "structural" isolation guarantee, is opt-in via `RUNTIME_DATABASE_URL` and fails **open** when misconfigured

**Time horizon: now.**

**Problem.** Track 1's defense-in-depth (Postgres FORCE RLS) only enforces when the app connects as the restricted `NOSUPERUSER/NOBYPASSRLS` role; that role is selected solely by the presence of the `RUNTIME_DATABASE_URL` env var, and when it is absent the app silently falls back to the superuser `DATABASE_URL` (BYPASSRLS), disabling every RLS policy with no error.

**Why it compounds.** Each new tenant module adds an `0002_enable_rls.py` that *assumes* the connection role lacks BYPASSRLS. The more modules rely on RLS as their isolation floor, the larger the blast radius of the single misconfiguration that removes the floor for all of them at once. There is no per-module or per-table mitigation — it is one global on/off switch governed by an unset-able env var, and the failure mode is invisible (queries succeed, returning *all* tenants' rows).

**Evidence.**
- `quickscale_core/.../templates/project_name/settings/production.py.j2:120-135` and `settings/base.py.j2:100-117` — `RUNTIME_DATABASE_URL` is an *optional* override; comment: "When unset, `DATABASE_URL` is used instead (backward compatible)."
- `templates/start.sh.j2:33-35` — migrations deliberately run with `RUNTIME_DATABASE_URL=""` (superuser). The same unset that is correct for `migrate` is catastrophic for `runserver`/`gunicorn`.
- `templates/db/init.sql.j2:23-50` — creates the `NOBYPASSRLS` role and grants DML, but nothing *requires* the app to use it.
- `templates/OPERATIONS.md.j2:88-93` — the only verification is a **manual** `SELECT rolname, rolsuper, rolbypassrls` the operator is told to run. No code asserts it.
- Confirmed absence: no `AppConfig.ready()`, Django system check, or middleware guard anywhere in `quickscale_modules/*/src` asserts `current_setting`/`rolbypassrls` at boot.
- The RLS policy itself (`crm/.../migrations/0008_enable_rls.py:66-74`) uses `current_setting('app.current_org_id', true)::uuid` — the `true` (missing_ok) means an unset var yields NULL → fail-closed *only if RLS is active at all*. With BYPASSRLS, the predicate is never evaluated.

**Correct shape.** RLS enforcement should be a startup invariant, not a deployment convention. In `saas`/production mode the process should refuse to serve traffic unless the live connection role returns `rolbypassrls = false` and at least one expected policy is present — fail-fast at boot, not fail-open under traffic. The choice of role should be derived from mode, not from the accidental presence of an env var.

**Alternatives.**
- **(A — preferred) Boot-time invariant check.** Add an `AppConfig.ready()` / Django system check in the orgs module (or a generated settings guard) that, when `QUICKSCALE_MODE == "saas"` and `DEBUG is False`, runs `SHOW is_superuser` / `SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user` and raises on bypass. Cheapest, closes the exact gap, and turns a silent prod incident into a failed deploy. *Preferred because the failure is invisible and catastrophic, the check is ~15 lines, and it converts the worst-case (silent cross-tenant leak in production) into the best-case (deploy refuses to start).*
- **(B) Make `RUNTIME_DATABASE_URL` mandatory in saas/prod.** Raise in `production.py` if mode is saas and the var is unset. Simpler than A but weaker: it validates the var's *presence*, not that the role behind it actually lacks BYPASSRLS (a superuser URL pasted there still passes).
- **(C) Collapse to a single connection that is always the restricted role, and grant migration privileges out-of-band.** Removes the dual-URL switch entirely; migrations get a separate operator credential used only by `start.sh`. Most robust but largest change to the generated deploy contract.

**Trigger for urgency.** The first production deploy (or Railway environment copy) where `RUNTIME_DATABASE_URL` is not carried over — environment duplication is explicitly relied upon elsewhere (`production.py.j2:57-66`), so the unset-on-copy path is realistic.

**Compounding factor.** All six modules' RLS migrations, plus every `_billing_org_db_context` / serializer that *assumes* RLS backstops a missed filter, are built on the premise that the connection role enforces RLS. They inherit this single point of failure.

**Migration path.** Add the `ready()`-time `rolbypassrls` assertion to the orgs `AppConfig` first — it is the one place every generated saas project already installs.

**Detection signal.** Instrument a startup log line emitting `current_user` + `rolbypassrls`; alert if a saas/prod process ever reports `rolbypassrls = true`. Until then, the signal would be a support ticket reporting another tenant's data — i.e. no early signal exists today.

---

## Finding 2 — Tenant isolation is re-implemented procedurally everywhere outside the request path; the auto-scoping manager is routinely bypassed

**Time horizon: now.**

**Problem.** "Current org" has two independent carriers — the Python `ContextVar` (drives `TenantManager`) and the Postgres session var `app.current_org_id` (drives RLS) — that are only co-set inside `TenantMiddleware`; every non-middleware write path (serializers, services, webhooks, management commands) must re-establish both by hand, and the modules pervasively use `all_objects` (the manager-bypass) plus manual `organization_id=` filters, so the one structural guard in application code (`TenantManager.get_queryset`) protects almost nothing on the paths that matter.

**Why it compounds.** Every new serializer method, service function, or webhook handler is a fresh site that must remember to (a) set the contextvar, (b) open a transaction and `SET LOCAL` the DB var, and (c) re-apply the manual org filter when it reaches for `all_objects`. Miss any one and you either fail closed (annoying) or, when RLS is off (Finding 1), leak. The cost scales with query count, not module count — and CRM/billing already contain dozens of these callsites.

**Evidence.**
- Two carriers, set together only in middleware: `orgs/.../middleware.py:263-276` (`_call_with_org` sets contextvar + `SET LOCAL` inside one `transaction.atomic()`); the primitives live in `orgs/.../current_org.py:69-96` (contextvar) and `:104-123` (`set_db_current_org_id`).
- `TenantManager.get_queryset` (`orgs/.../managers.py:38-48`) is the lone structural filter — and `TenantModel` exposes `all_objects` right beside it (`orgs/.../models.py:356-357`).
- Pervasive bypass in CRM serializers: `crm/.../serializers.py` uses `Tag.all_objects`, `Contact.all_objects`, `Deal.all_objects` with hand-written `organization_id=org_id` at lines 104, 144-147, 265-269, 319-320, 417-418, 546-550 — each one a manual re-implementation of what the manager exists to do.
- Billing reintroduces the sync as a context manager because it has no request: `billing/.../services.py:911-947` (`_billing_org_db_context` sets contextvar + `SET LOCAL`), wrapped around every webhook handler (`:1075`, `:1173`, `:1325`, `:1461`); all billing reads/writes go through `Subscription.all_objects` / `CreditTransaction.all_objects` (`:585`, `:836`, `:870`, `:1572`).
- Serializers set only the contextvar, not the DB var (`crm/.../serializers.py:17-44`, `_request_org_id`) — relying on middleware having already `SET LOCAL`-ed for the request, an implicit ordering contract.

**Correct shape.** A single org-context primitive that sets *both* carriers atomically and is the *only* supported way to enter org scope (a `with org_scope(org):` context manager used uniformly by middleware, webhooks, and commands), combined with making `all_objects` genuinely rare — i.e. the default manager is trusted because RLS + contextvar are always coherent, so manual `organization_id=` filtering is deleted rather than duplicated.

**Alternatives.**
- **(A — preferred) One `org_scope()` context manager as the sole entry point; ban `all_objects` outside admin/operator code.** Middleware, `_billing_org_db_context`, and any command call the same primitive that sets contextvar + `SET LOCAL` together; serializer manual filters get deleted once the manager is trusted. *Preferred because it removes the "two carriers, set in two styles" divergence and shrinks the manual-filter surface that Finding 1 makes dangerous — it makes the structural guard actually load-bearing.*
- **(B) Keep `all_objects` but add a lint/CI rule** that forbids `.all_objects` outside an allowlist (admin, purge, migrations). Cheaper, but leaves the two-carrier sync problem and is enforcement-by-convention — the very thing Track 1 set out to kill.
- **(C) Drop the contextvar entirely and lean only on RLS.** The manager would query normally and RLS alone scopes. Simplest mental model, but couples *all* correctness to Finding 1 being fixed first, and breaks SQLite-based tests (RLS is a Postgres no-op), so the manager-level filter currently doubles as the test-time guard.

**Trigger for urgency.** The next module whose serializer/service author copies the CRM `all_objects + organization_id=` pattern and omits the filter on one method — or any background/management command that touches tenant tables without entering org scope.

**Compounding factor.** CRM serializers, billing services, and the social "managed views" path (which calls `set_db_current_org_id` directly) are already built on the manual two-carrier pattern; unifying it means touching all of them.

**Detection signal.** Add a test-suite assertion (Postgres CI) that any `all_objects` query without an explicit `organization_id` filter raises; in production, monitor for `CurrentOrgError` spikes (fail-closed misses) as the proxy for "a path forgot to enter org scope."

---

## Finding 3 — Wrapping the whole request in one transaction (to carry `SET LOCAL`) couples DB connection-hold time to in-view external I/O

**Time horizon: 6–18 months.**

**Problem.** Because `app.current_org_id` is set with `SET LOCAL`, which only survives inside a transaction, `TenantMiddleware._call_with_org` wraps the *entire* downstream view in a single `transaction.atomic()` — so every org-scoped request holds an open transaction (and its DB connection) for its full duration, including template rendering and any synchronous external API calls the view makes.

**Why it compounds.** The billing checkout/portal views make 2–4 sequential Stripe network calls *inside* that request transaction; the webhook handler holds `select_for_update` row locks across Stripe `retrieve_*` calls. As traffic grows and as more views add external calls (email, more Stripe, future providers), the number of connections sitting `idle in transaction` during third-party latency grows linearly, and Postgres `max_connections` (not CPU) becomes the ceiling. Row locks held across network calls also lengthen lock-wait chains on contended rows (credit balance, subscription).

**Evidence.**
- `orgs/.../middleware.py:270-273` — `with transaction.atomic(): self._set_current_org_id(...); return self.get_response(request)` wraps the whole view.
- `billing/.../services.py:489-539` (`create_checkout_session`) and `:542-688` (`create_subscription_checkout_session`) issue `retrieve_price` → `search_customers`/`create_customer` → `create_checkout_session` sequentially; these run under the request transaction because `/billing/` and `/api/billing/` are in `_SOLO_ROUTE_PREFIXES` (`middleware.py:66-75`) and thus go through `_call_with_org`.
- `billing/.../services.py:988-1037` — webhook handler holds `WebhookEvent.objects.select_for_update()` while calling `stripe_client.retrieve_subscription` / `retrieve_payment_intent` (`:1284`, `_retrieve_checkout_payment_intent_payload`).
- `production.py.j2:114-116` — `conn_max_age=600` (persistent connections), so each worker pins a connection that can sit idle-in-transaction.

**Correct shape.** Org context for reads should not require holding a transaction across view I/O. Set the tenant GUC per-checkout-out connection at acquisition (e.g. `SET` scoped to the connection lifecycle, or a `set_config(..., is_local := true)` re-applied at transaction start via a connection-init hook) so RLS is enforced without forcing a request-long transaction; external API calls should live *outside* any DB transaction, with DB writes committed before/after the network round-trip (or via an outbox), never around it.

**Alternatives.**
- **(A — preferred) Connection-init hook sets the GUC; views open short transactions only around writes.** Use Django's `connection_created`/wrapper or a thin pool that applies `SET app.current_org_id` when the org is resolved, decoupled from request-long `atomic()`. External calls run outside transactions. *Preferred because it keeps RLS enforcement while removing the structural "transaction = request" coupling that turns third-party latency into connection exhaustion.*
- **(B) Keep the request transaction but move all external I/O out of views** into pre/post hooks or async tasks (checkout session creation returns via a deferred flow). Smaller routing change, but pushes complexity into every external-calling view and doesn't help template-render hold time.
- **(C) Accept it; cap blast radius operationally** — aggressive statement/transaction timeouts (`idle_in_transaction_session_timeout`), PgBouncer in transaction mode, more workers. Buys headroom without a design change, but PgBouncer transaction pooling is itself incompatible with session-level `SET`, so this interacts badly with the very mechanism RLS depends on.

**Trigger for urgency.** A Stripe latency incident, a traffic step-change, or raising `WEB_CONCURRENCY` — any of which turns "connection held during network call" into pool/`max_connections` exhaustion and cascading 5xxs.

**Compounding factor.** Every billing view and webhook handler, plus any future module that calls an external service from within a request, is already written assuming the ambient request transaction.

**Detection signal.** Watch Postgres `state = 'idle in transaction'` connection count and `pg_stat_activity` transaction age; alert on idle-in-transaction duration p95 climbing with Stripe API latency.

---

## Finding 4 — Two contradictory tenant-routing models coexist, hardcoded as module-name frozensets, and contradict the locked single-URL decision

**Time horizon: 6–18 months.**

**Problem.** The locked architecture (Decision 4A) is "one URL tree: `/crm/...` for both solo and saas; no `/orgs/<slug>/crm/...`", yet the middleware still carries a full *second* slug-based routing model — hardcoded module name sets, slug resolution, and a fail-open "unknown segment ⇒ bypass org resolution" branch — and the generated React frontend still emits `/orgs/<slug>/crm` URLs in saas mode.

**Why it compounds.** The routing contract is encoded as literal module-name frozensets that every new routed module must be added to in two-or-three places; the "temporary until T1.5–T1.10" scaffolding has outlived its stated sunset (those tasks are marked complete) and is now permanent, untested-in-the-off-state code. Worse, the two models disagree about where org resolution happens, so a developer adding routes can pick the wrong contract and get either a 403 or a silent org-resolution bypass.

**Evidence.**
- Locked decision: `docs/technical/roadmap.md:69` (4A — "no `/orgs/<slug>/crm/...`") and D1 (`:76`, content URLs lose the slug). Tasks T1.5–T1.10 marked `[x]` complete (`:128-133`, M16 `:234`).
- Contradicting it, still shipped: `orgs/.../middleware.py:54-75` (`_DOWNSTREAM_ORG_SCOPED_MODULES`, `_SOLO_ROUTE_PREFIXES` frozensets), `:211-245` (`_resolve_org_from_path_slug`, Fallback A), `:165-190` (Fallbacks A/B/C).
- Fail-open branch: `middleware.py:324-334` — for `/orgs/<slug>/<unknown>` the comment says "Unknown segment — treat as management bypass (safe default)"; an unrecognized segment under a slug path **skips** org resolution entirely.
- Generated frontend still emits the forbidden shape: `templates/themes/showcase_react/templates/index.html.j2:83` — `crm: saas ? "/orgs/<slug>/crm" : "/crm"`, with `currentOrgSlug` plumbed at `:77`.

**Correct shape.** One routing contract, enforced structurally: saas resolves the active org from session only, all content lives under the flat tree, and the slug-resolution fallback + frozensets are deleted. "Which paths are org-scoped vs. management" should be derived from the modules' own manifests/URLConf ownership, not a hand-maintained name list in middleware, and the default for an unrecognized path must be fail-*closed* (resolve org or 403/redirect), never bypass.

**Alternatives.**
- **(A — preferred) Delete the slug model; finish 4A.** Remove `_resolve_org_from_path_slug`, the frozensets, and the slug branch in the generated frontend; make session-active-org the sole saas source; flip the unknown-segment default to fail-closed. *Preferred because the decision is already locked and the tasks are nominally "done" — this is closing real drift between the ADR and the code, and it removes a fail-open auth branch.*
- **(B) Keep both but make ownership manifest-driven.** Derive org-scoped vs management routing from each module's `module.yml`/URLConf instead of frozensets, so new modules don't edit middleware. Reduces the coordination tax but leaves the two contradictory URL shapes (and the frontend slug emission) alive.
- **(C) Standardize on slug routing instead.** Reverse 4A and make `/orgs/<slug>/...` canonical. Defensible for shareable/bookmarkable org URLs, but contradicts a locked decision and the whole flat-route migration already shipped — highest churn, least aligned.

**Trigger for urgency.** The teams module (`quickscale_modules/teams`, the stated v0.86.0 direction with `/teams/<slug>/` routing) landing on top of this — it will either add a *third* routing model or be forced to pick one of the two contradictory existing ones under pressure.

**Compounding factor.** The generated React theme, the middleware, and any module URLConf that still mounts under `/orgs/<slug>/` are built on the dual model; unwinding touches generator templates + middleware + per-module URLs together.

**Detection signal.** Instrument middleware to count requests resolved via the slug fallback vs. session; a non-decaying slug-fallback rate proves the "temporary" path is load-bearing in production. Also alert on any request that reaches a view with no `request.org` set under a non-exempt path (the fail-open branch firing).

---

## Finding 5 — Static `MODULE_CATALOG` tuple is a second authoritative registry beside manifest discovery (tracked residual)

**Time horizon: 2+ years.**

**Problem.** Module identity now has two sources of truth — the manifest-backed dynamic discovery (`module_discovery.py`, the intended authority) and a hand-edited `MODULE_CATALOG` tuple in core — so adding a module still requires editing the static tuple even though the CLI resolves modules generically.

**Why it compounds.** It is a small, bounded coordination tax (one extra edit per module add), but it is exactly the class of "manual registry beside the real one" that drifts: the static tuple can disagree with the manifests, and the disagreement surfaces as a module that "exists" in one inventory and not the other.

**Evidence.**
- `quickscale_core/src/quickscale_core/contracts/module_catalog.py` — static `MODULE_CATALOG` tuple still lists modules by name.
- `quickscale_core/src/quickscale_core/contracts/module_discovery.py` — manifest-backed discovery already exists and is intended as the sole authority.
- Tracked in `docs/technical/roadmap.md:196` (Deferred/Monitor — "Retire static MODULE_CATALOG tuple").
- Prior CLI-wiring half already resolved (M14 / T2.3–T2.4): per-module adapters, the implication-defaults ladder, and the CLI catalog shim are deleted.

**Correct shape.** `module_discovery.py` (reading each module's `module.yml`) is the single inventory; the static tuple is deleted and any callers read discovery.

**Alternatives.**
- **(A — preferred) Delete the tuple; route all callers through discovery.** *Preferred because the replacement already exists and is in use — this is removal of a redundant registry, not new infrastructure.*
- **(B) Generate the tuple from discovery at build time.** Keeps a static artifact for callers that want a frozen list, derived rather than hand-edited. Only worth it if a true compile-time constant is needed somewhere — otherwise it re-creates the drift surface.
- **(C) Leave as-is, lint for parity.** Add a test asserting tuple == discovery. Cheapest, but keeps two registries forever.

**Trigger for urgency.** The next module addition whose diff touches both a new `module.yml` and `contracts/module_catalog.py` — the redundant edit is the residual tax.

**Compounding factor.** Low — the CLI already ignores the tuple; only the catalog's direct callers in core remain.

**Migration path.** Replace the tuple's reads with `module_discovery` lookups one caller at a time, then delete the tuple.

**Detection signal.** A CI diff that modifies both `module.yml` (new module) and `module_catalog.py` in the same change.
