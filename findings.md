# Structural Autopsy: QuickScale

## Orientation

**What it is.** A creator-led Django *project generator* (`quickscale plan` → `quickscale apply`) plus a workspace of ~13 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Generated projects copy modules into a local `modules/` dir and become **user-owned code** ("no vendor lock-in"). The CLI/generator lives in `quickscale_cli` + `quickscale_core`.

**Near-term growth direction.** The dominant work of the last ~10 releases is **retrofitting multi-tenant isolation** (`F11.2`–`F11.13b`) onto every module, plus a `solo` → `saas` runtime mode (`v0.86.0` orgs) and org-authoritative billing (`F13/M9`). The product is mid-pivot from a single-user scaffold into a multi-tenant SaaS substrate. Every finding below sits on a seam that pivot just stressed.

The single most important structural fact: **the multi-tenant isolation that the whole recent roadmap is built on is enforced in application convention, not at the data layer — and the data-layer hook that implies otherwise is dead code.**

**Implementation notes:** no backward compatibility, no migration path, no existing users — every change is a clean break. Squash/rewrite migrations; drop dead paths outright.

**Findings 1, 2, and 4 are three faces of one decision** — tenant isolation was added as an application-layer convention layered onto a single-user scaffold, rather than as a data-layer invariant. Finding 3 is independent. Finding 5 (DR) is resolved — implemented as M12 (T3.1–T3.3, 2026-06-23); see CHANGELOG.

---

## Finding 1 — Tenant isolation is procedural; the RLS boundary does not exist

**Time horizon: now**

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

**Time horizon: now**

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

## Finding 3 — Adding a module requires coordinated edits across ~8 sites; the CLI hardcodes every module by name

**Time horizon: 6–18 months**

**Problem.** Module identity is not owned in one place — it's spread between the module's own source and the generator/CLI, which carries hand-maintained per-module knowledge (a manifest file each, a catalog, and a hardcoded dependency-implication function).

**Why it compounds.** Each new module is a coordination tax: (1) `models.py` org FK + migration, (2) `managers.py` dual-manager, (3) dual-route `views.py`, (4) isolation tests, (5) a `<name>_manifest.py` in `quickscale_cli`, (6) a `MODULE_CATALOG` entry, (7) a hardcoded branch in `get_implied_module_default_configs`, (8) a `pyproject.toml` dep. Miss one and the module is silently mis-wired. The CLI must be edited for every module it claims to merely "compose."

**Evidence.**
- 13 separate `*_manifest.py` files in `quickscale_cli/src/quickscale_cli/` (one per module, each a ~200-line Python config adapter).
- `quickscale_cli/src/quickscale_cli/commands/implied_module_defaults.py:16-29` — dependency implications are a literal `if "billing"…`, `if "crm"…`, `if "social"…`, `if "orgs"…` ladder. The `SOCIAL-CR-002` changelog entry is exactly this edit made by hand.
- `module_catalog.py` is a re-export shim pointing at `quickscale_core.contracts.module_catalog` — the catalog already had to be relocated ("Phase 0 moved the catalog out of the CLI"), evidence the ownership seam is unsettled.
- `quickscale_core/src/quickscale_core/contracts/module_catalog.py` — hardcoded `MODULE_CATALOG` tuple listing all 13 modules by name.

**Correct shape.** Each module declares its own contract in one `module.yml` (name, `implies`, config rules, isolation policy). The CLI resolves them generically — zero per-module branches. The manifest schema (`quickscale_core/manifest/`) already exists and is half-built; this finishes it.

**Selected: Option A — self-describing manifests + generic resolver.**
Add an `implies` field to `module.yml`; write a `resolve_module_implications()` function that reads it and computes the transitive closure (replaces the `if`-ladder). Move config normalization/validation/derivation rules from the 13 Python adapters into `module.yml` config sections. Delete the `*_manifest.py` files, the `if`-ladder, the catalog shim, and the hardcoded `MODULE_CATALOG` tuple (replaced by dynamic discovery from `module.yml` files).

**Trigger for urgency.** The next wave of `AbstractListing` verticals — the moment a new module is added and the CLI silently doesn't know about it.

**Detection signal.** Count diffs that touch ≥4 of the 8 wiring sites for a single logical "add module" change. That fan-out is the tax made visible.

---

## Finding 4 — The flat-route / org-route dual surface was a migration bridge that became permanent

**Time horizon: 6–18 months**

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

---

## Finding 5 — ~~The backups/DR module has a 3,677-line god-file and two parallel operation protocols~~

**Resolved 2026-06-23 (M12 / T3.1–T3.3).** Legacy env-var protocol deleted; all 8 management commands route through `dr_engine.adapter`; `services.py` reduced to 205 LOC thin re-exports; `dr_engine/orchestration.py` owns all DR logic. See CHANGELOG for implementation history.
