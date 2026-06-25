# Structural Autopsy: QuickScale

## Orientation

**What it is.** A creator-led Django *project generator* (`quickscale plan` → `quickscale apply`) plus a workspace of ~13 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Generated projects copy modules into a local `modules/` dir and become **user-owned code** ("no vendor lock-in"). The CLI/generator lives in `quickscale_cli` + `quickscale_core`.

**Near-term growth direction.** The dominant work of the last ~10 releases is **retrofitting multi-tenant isolation** (`F11.2`–`F11.13b`) onto every module, plus a `solo` → `saas` runtime mode (`v0.86.0` orgs) and org-authoritative billing (`F13/M9`). The product is mid-pivot from a single-user scaffold into a multi-tenant SaaS substrate. Every finding below sits on a seam that pivot just stressed.

The single most important structural fact: **the multi-tenant isolation that the whole recent roadmap is built on is enforced in application convention, not at the data layer — and the data-layer hook that implies otherwise is dead code.**

**Implementation notes:** no backward compatibility, no migration path, no existing users — every change is a clean break. Squash/rewrite migrations; drop dead paths outright.

**Findings 1, 2, and 4** are fully resolved via Track 1 (T1.1–T1.16 / M13–M18). **Finding 5** (DR) is resolved and archived to CHANGELOG (M12 / T3.1–T3.3). **Finding 3** is partially resolved — T2.3/T2.4 eliminated per-module CLI adapters (M14); the residual `MODULE_CATALOG` static tuple in core remains (tracked in roadmap Deferred/Monitor).

---

## Finding 1 — Tenant isolation is procedural; the RLS boundary does not exist

**STATUS: RESOLVED** — Contextvar `TenantManager` active across all modules (T1.2/M13); FORCE ROW LEVEL SECURITY active on all six tenant-table sets (T1.11–T1.16/M17–M18). See CHANGELOG M13, M15, M16, M17, M18.

**Time horizon: now** *(was)*

**Problem.** Cross-tenant data isolation is enforced by every callsite remembering to call `.for_org()` (or hand-write a `Q(organization_id=...)` filter). The default model manager returns *all* tenants' rows. The one piece of code that looks like a database-level guarantee — `SET LOCAL app.current_org_id` — is consumed by nothing.

**Why it compounds.** Isolation correctness is O(number of query sites). Every new view, serializer, admin action, management command, or signal handler is a fresh opportunity to forget the filter — and a miss is silent (returns a 200 with another tenant's rows). The F11 rollout is the evidence of the tax: `F11.10e` required a manual "same-org FK audit/fix cycle across `serializers.py` (225/225)" — a per-field human audit standing in for a structural invariant. Each new module re-pays that audit in full.

**Evidence.**
- `quickscale_modules/crm/src/quickscale_modules_crm/managers.py:44-45` — `TenantScopedManager.get_queryset()` returns an **unfiltered** `CrmQuerySet`. Docstring (lines 39-41): "Using `.all()` without `.for_org()` returns all rows." Identical unscoped default in `listings/managers.py:38-39`, and the same pattern in forms/social/blog.
- `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py:126-130` — `_set_current_org_id` emits `SET LOCAL app.current_org_id`. Nothing reads it: repo-wide grep for `CREATE POLICY` / `ROW LEVEL SECURITY` / `current_setting('app.current_org_id')` returns zero hits outside `quickscale_modules/orgs/tests/urls.py:23` (a test endpoint only).
- Isolation rides entirely on 49 explicit `.for_org(` callsites + per-view manual filters + ~10 admin `all_objects` overrides (`crm/admin.py:235-391`, `listings/admin.py:63-71`).

**Correct shape.** Two layers: (1) default manager auto-scopes via a `contextvar` set by middleware — `get_queryset()` reads the ambient org, `all_objects` is the audited escape hatch; (2) Postgres RLS policies keyed off `current_setting('app.current_org_id')` as the hard data-layer wall, so even a forgotten filter or `.raw()` call fails closed at the DB.

**Selected: Option C — default-scoped contextvar manager + Postgres RLS backstop.**
The contextvar manager inverts the footgun (scoped is default, unscoped is opt-in) and is testable without Postgres. RLS underneath catches anything that bypasses the ORM. Together they eliminate the "audit every callsite" tax permanently. The shared manager + contextvar live in `orgs` (not `quickscale_core` — core is Django-free by invariant); all six module `managers.py` files are deleted and replaced with imports from `orgs.tenancy`.

**Trigger for urgency.** The first real `QUICKSCALE_MODE=saas` deployment with two paying tenants. Solo mode made a forgotten filter invisible (one user = one org). SaaS mode shipped `v0.86.0`; the blast radius is now "Tenant B sees Tenant A's pipeline/invoices."

**Detection signal.** With `app.current_org_id` set, count rows a query returns whose `organization_id` differs from the session var. Any nonzero count is a live leak. Today nothing watches this. The RLS integration tests in Phase 3 (T1.11–T1.16) assert exactly this.

---

## Finding 2 — The org-ownership contract is inconsistent; NULL silently means "visible to everyone"

**STATUS: RESOLVED** — All six modules: NOT NULL/PROTECT org FK (T1.5–T1.10/M16); System org owns public content (T1.1/M13); teardown via `purge_organization` pending (T1.17, the only remaining Track 1 task). See CHANGELOG M13, M16.

**Time horizon: now** *(was)*

**Problem.** Each module made a different decision about the `organization` FK — nullability, `on_delete`, and whether `organization IS NULL` is a legal "global/flat" state — so there is no single answer to "who owns this row" or "what happens when a tenant is deleted."

**Why it compounds.** The divergence is load-bearing for queries: flat routes scope to `organization__isnull=True` and treat those rows as world-visible, while org routes scope to the active org. The *meaning of NULL* is a security-relevant value. Every cross-module feature (unified dashboard, global search, export) must re-learn each module's NULL semantics, and any code path that nulls an FK silently promotes a private row into the public bucket.

**Evidence.**
- CRM: `on_delete=models.PROTECT`, NOT NULL (`crm/models.py:32-36`).
- Billing: `on_delete=models.SET_NULL, null=True` (`billing/models.py:121-125, 170-174`).
- Blog / forms / listings / social: `on_delete=models.CASCADE, null=True` (`blog/models.py:118-122`, `forms/models.py:39-43`, `listings/models.py:21-25`, `social/models.py:33-37`).
- Deleting an org: **PROTECTs** in CRM, **CASCADE-deletes** blog/forms/listings/social, **SET_NULLs** billing rows — turning a tenant's subscription/credit-ledger rows into globally-visible NULL-org rows.
- CRM is NOT NULL yet its own views still union the NULL bucket: `Q(organization_id=org.id) | Q(organization_id__isnull=True)` at `crm/views.py:134, 241-255`.

**Correct shape.** Every owned row has a non-null org (NOT NULL + `PROTECT`). A single reserved `Organization(is_system=True)` row owns genuinely shared/public content. One teardown policy: `PROTECT` everywhere + an explicit `purge_organization` management command that deletes in FK-safe order.

**Selected: Option A + C — universal NOT NULL + reserved System org + standardized teardown.**
NULL stops being a security-relevant value. Flat routes disappear (every row has a real org). The `isnull=True` scoping in Finding 4 disappears as a side effect. The teardown policy is `on_delete=PROTECT` + `purge_organization` — GDPR-capable, no accidental cascade. Billing's `SET_NULL` must not ship to production multi-tenant: an org delete currently orphans the authoritative billing subject into the shared bucket.

**Trigger for urgency.** The first org deletion / tenant offboarding in SaaS mode, or the first GDPR "delete this customer's data" request — which today does five different things, including orphaning billing rows.

**Detection signal.** Alert on any owned-table row reaching `organization_id IS NULL` post-migration in a SaaS project. Today that's a normal "flat" value — it must become a DB constraint violation.

---

## Finding 3 — Adding a module requires coordinated edits across ~8 sites; T2.3/T2.4 resolved the CLI wiring bottleneck, but the module-catalog tuple remains hardcoded

**STATUS: PARTIAL** — T2.3/T2.4 (M14) deleted all per-module CLI adapters and the implication-defaults ladder; generic resolver is operational. Residual: `quickscale_core/src/quickscale_core/contracts/module_catalog.py` static `MODULE_CATALOG` tuple still hardcoded — tracked in roadmap Deferred/Monitor for retirement.

**Time horizon: <6 months** *(was)*

**Problem.** Module identity is not owned in one place — it's spread between the module's own source, the core catalog tuple, and the generator. T2.3/T2.4 eliminated the CLI's per-module Python adapters, the implication-defaults ladder, and the CLI catalog re-export shim, but the core module-catalog tuple still requires per-module edits.

**Why it compounds.** Each new module is a coordination tax: (1) `models.py` org FK + migration, (2) `managers.py` dual-manager, (3) dual-route `views.py`, (4) isolation tests, (5) a `pyproject.toml` dep, and (6) a hardcoded entry in the core `MODULE_CATALOG` tuple. The per-module CLI adapters, the implication-defaults ladder, and the CLI catalog shim have all been deleted — the CLI now resolves modules generically — but the core catalog still must be hand-edited.

**Evidence.**
- T2.3 deleted all 12 `quickscale_cli/src/quickscale_cli/*_manifest.py` adapter files; all callers now route through `quickscale_core.manifest.resolver`.
- T2.4 deleted the implication-defaults helper (`get_implied_module_default_configs`) and the `quickscale_cli.module_catalog` re-export shim.
- `quickscale_core/src/quickscale_core/contracts/module_catalog.py` still contains a hardcoded `MODULE_CATALOG` tuple listing all 13 modules by name, though it is now supplemented by manifest-backed dynamic discovery (`module_discovery.py`).

**Correct shape.** The CLI already resolves modules generically with zero per-module branches. The remaining gap is the hardcoded `MODULE_CATALOG` tuple in core — it should be retired in favor of the already-existing manifest-backed discovery as the sole authoritative inventory.

**Selected: T2.3/T2.4 completed the CLI-wiring half; the residual debt is the static catalog tuple.**
The per-module CLI Python adapters, the implication-defaults ladder, and the CLI catalog shim have been deleted. The `resolve_module_implications()` function and generic resolver are operational. What remains: `quickscale_core.contracts.module_catalog.MODULE_CATALOG` is still a hardcoded tuple — retire it and rely on dynamic discovery from `module.yml` files exclusively.

**Trigger for urgency.** The next module addition that requires both a new `module.yml` **and** a hand-edit to the static catalog tuple — a sign the catalog still acts as a manual registry.

**Detection signal.** A diff that touches both a new `module.yml` and `contracts/module_catalog.py` for the same logical module addition. That redundant edit is the residual tax.

---

## Finding 4 — The flat-route / org-route dual surface was a migration bridge that became permanent

**STATUS: RESOLVED** — All `/orgs/<slug:org_slug>/...` content routes deleted across CRM, Blog, Forms, Listings, Social, Billing (T1.5–T1.10/M16). Middleware always produces `request.org`; `_is_org_scoped_route()` eliminated everywhere. See CHANGELOG M15, M16.

**Time horizon: 6–18 months** *(was)*

**Problem.** Every isolated module serves the same content under two URL trees — flat `/crm/...` (scopes to `organization__isnull=True`) and `/orgs/<slug>/crm/...` (scopes to active org) — selected per-request by a `_is_org_scoped_route()` branch duplicated in each module, on top of a `solo` vs `saas` fork in `TenantMiddleware`.

**Why it compounds.** This doubles the surface to reason about for correctness and security permanently. Every new view in every module re-implements the branch. URL generation is also forked (`get_absolute_url` emits different URLs for NULL-org vs org-owned rows).

**Evidence.**
- `_is_org_scoped_route()` reimplemented in `crm/views.py:43`, `listings/views.py:36`, `blog/views.py:64`, `forms/views.py` — each copy with its own subtle scoping.
- `orgs/middleware.py:52-54` forks `_handle_saas_request` vs `_handle_solo_request`; the entire routing/scoping contract flips on one env var `QUICKSCALE_MODE`.
- `orgs/middleware.py:113-114` — solo mode calls `Organization.objects.create_personal_for(user)` (a get-or-create **write**) inside the request path on every authenticated request.

**Correct shape.** One URL tree. Middleware always resolves `request.org` (solo = the one implicit personal org; saas = session active-org). Views read `request.org` and never sniff the URL shape. "Solo" is "SaaS with exactly one implicit org," not a parallel routing universe.

**Selected: Option A — one URL tree, org always from middleware (D1).**
The `/orgs/<slug:org_slug>/...` content trees are deleted from every module. The `_is_org_scoped_route()` helper is deleted everywhere. Middleware always produces `request.org` — for solo this is the personal org, for saas it's read from `request.session[ACTIVE_ORG_SESSION_KEY]`. This depends on Finding 2A (System org must exist before NULL-org public rows can be rerouted): T1.1 is the lynchpin.

**Trigger for urgency.** When solo→saas promotion (`promote_to_saas`) becomes a routine customer operation — the two routing worlds must reconcile live data and live URLs, and the NULL-org rows need a home.

**Detection signal.** After collapsing to a single tree, any 404 on a previously flat URL is a stranded row that wasn't assigned to a real org.
