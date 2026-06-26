# Structural Autopsy: QuickScale (v87 / post–Track-1)

## Orientation

**What it is.** A creator-led Django *project generator* (`quickscale plan` → `quickscale apply`) plus a workspace of ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated projects via **git subtree** and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core` (core is Django-free by invariant).

**Near-term growth direction.** The dominant work of the last ~18 milestones is **retrofitting multi-tenant isolation** onto every module: a contextvar `TenantManager`, a NOT-NULL org FK contract, a `solo`→`saas` runtime mode, org-authoritative billing, and (Track 1, just merged) PostgreSQL FORCE RLS on all six tenant table-sets. The product is mid-pivot from a single-user scaffold into a multi-tenant SaaS substrate. Every finding below sits on the seam that pivot just stressed.

**Deployment context.** Generated apps run WSGI/Gunicorn (sync workers, `conn_max_age=600` persistent connections), single Railway project, shared Postgres. No existing users; the project's standing rule is **clean break — no back-compat, no migration path** (squash/rewrite migrations, delete dead paths).

**Prior autopsy status.** The previous round's Findings 1, 2, 4, 5 are recorded as resolved (CHANGELOG M12–M18). This is a fresh pass over the *post-RLS* shape. The headline: Track 1 made isolation a data-layer guarantee *in principle*, but the guarantee is now distributed across three mechanisms (Django manager + Postgres RLS + manual filters) that must all agree, and the operative one (RLS) is **opt-in via an env var that fails open**. That is the spine of Findings 1–2.

**Current autopsy resolution status (2026-06-26).** Finding 1 (RLS fails open) → resolved by T1.18 (boot guard in `QuickscaleOrgsConfig.ready()`). Finding 2 (two carriers + pervasive `all_objects`) → resolved by T1.19 (`org_scope()` unified primitive). Finding 4 (two routing models) → resolved by T1.20 (slug-routing fallback deleted). Finding 5 (static MODULE_CATALOG) → resolved by D2 (manifest-backed discovery canonical). **Finding 3 remains open** — request-scoped transaction/Stripe I/O coupling; tracked as D8 in roadmap (6–18 month horizon, production trigger required).

**Already acknowledged, not re-reported here.** The roadmap's Deferred/Monitor list already owns: no structured logging/correlation IDs, no versioned public API, no webhook payload-boundary validation, and the static `MODULE_CATALOG` tuple (kept below as the one tracked residual). Single-PR items (Stripe `api_version` pin, orphaned `apply-recovery.yml`, per-admin `select_related`) are out of scope by the autopsy's own rules. The module-upgrade story (subtree pull + "Module Extension Contract", `docs/technical/module-extension.md`) is a **deliberate, documented design** — excluded, not a load-bearing wrong decision.

---

## Open findings

| # | Finding | Horizon | Blast radius × likelihood |
|---|---------|---------|---------------------------|
| 3 | Request-scoped DB transaction couples connection-hold time to in-view external I/O (Stripe) | **6–18 mo** | Connection/lock exhaustion × medium-high under traffic |

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
