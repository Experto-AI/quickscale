# QuickScale Organizations Module: Design Document

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Organizations Design**
> **Related docs**: [Roadmap](roadmap.md) | [Decisions](decisions.md) | [Railway Deployment](../deployment/railway.md)

## Purpose and Scope

The organizations module enables a QuickScale-generated app to be sold as a SaaS product to multiple paying clients. Each client is an **organization** — an isolated workspace with its own data, its own member roster, and its own role-based access control. The operator deploys a single Railway project, clients self-serve signup, subscribe, and invite their colleagues. This is the SaaS-parity milestone that completes the auth → billing → organizations foundation.

QuickScale supports two deployment modes — **Solo** and **SaaS** — resolved at runtime via a single settings flag. Both modes use the same schema and codebase. Solo mode is a constrained configuration of the organization system, not a separate architecture.

**Current implementation note**: the repository currently ships the organizations foundation plus the server-rendered org-management Django surface: core org models/admin wiring, Solo/SaaS runtime branching, request-scoped org resolution, RBAC guards, self-service org creation, the org dashboard, member management, org settings, invite send/revoke on the org admin members surface, the slugless public invitation accept flow that resumes after auth and redeems only when the normalized email matches, the current org-billing bridge (authoritative org billing ownership fields, flat billing pages/APIs in both Solo and SaaS modes, migration/promote commands, and ORM-backed plan feature gating), and fresh `showcase_react` org pages for generated projects. The shipped tenant-table surface is registry-backed: **21 ENROLLED models** across CRM (7), Forms (4), Billing (3), Blog (4), Listings (1), and Social (2) each carry a direct `organization_id`, use the shared `TenantManager` / `TenantManager(super_scope=True)` contract, and ship with live FORCE-RLS policies. `TenantMiddleware` plus the execute-wrapper derive `app.current_org_id` from the request/session ContextVar path so tenant-scoped ORM and PostgreSQL enforcement stay aligned. Reviewed exclusions (org control-plane models, `Plan`, `WebhookEvent`, `AuthorProfile`, abstract bases, test-only models, auth `User`, backups operational models, and notifications operational models) remain outside the tenant-table contract by design. The authoritative human-readable overview of the shipped tenant-table surface is the marker-based derived registry view (:func:`get_derived_registry_overview` in ``quickscale_modules_orgs.tenancy``). The derived view is purely marker-driven — every excluded concrete model carries an explicit ``tenant_excluded`` class attribute. The literal ``TENANT_TABLE_REGISTRY`` is retained as a cross-check target for CI parity assertions.

---

## Deployment Mode: Solo vs SaaS-Organizations

### Overview

QuickScale supports two first-class deployment modes, switchable at runtime without code regeneration:

| Aspect | Solo mode | SaaS-Organizations mode |
|---|---|---|
| Target use case | Personal tools, internal apps, indie developers | Multi-tenant SaaS sold to paying clients |
| Organizations per user | 1 (personal org, auto-created) | 1 |
| Org management UI | Hidden | Full (create, invite, settings, billing) |
| Org switcher | Not shown | Not shown (VIEW-AS only for superusers) |
| Invitations | Disabled | Enabled |
| URL structure | Flat module routes such as `/blog/`, `/crm/dashboard/`, `/forms/`, `/listings/` (no tenant slug in content routes) | Org-management pages under `/orgs/...`; shipped server content routes stay flat, while fresh `showcase_react` SaaS pages keep org-slug blog/listings pages plus flat redirect shims |
| Billing scope | Per-org (the personal org is the billing owner) | Per-org (team billing contact) |
| Isolation today | `request.org` + ContextVar + FORCE-RLS on the enrolled tenant-table surface | `request.org` + ContextVar + FORCE-RLS on the enrolled tenant-table surface |
| PostgreSQL RLS | Active on all 21 enrolled tenant models; reviewed exclusions stay outside the tenant-table contract | Active on all 21 enrolled tenant models; reviewed exclusions stay outside the tenant-table contract |

### Why Runtime Instead of Generation Time

The natural comparison is SaaS Pegasus, which resolves solo vs SaaS at **generation time** — it generates different code depending on your choice, producing a clean output with no dead code. QuickScale could do the same.

However, runtime resolution is preferable for QuickScale because:

1. **Start solo, scale to SaaS**: The most common trajectory is a developer who starts with a personal tool, gains traction, and wants to offer it as a multi-tenant SaaS. With generation-time resolution, that requires regenerating the project and migrating data. With runtime resolution, it is a one-line settings change plus a management command.
2. **One schema, one codebase**: The organizations foundation keeps a single org abstraction, request context, and runtime branching model across Solo and SaaS. The shipped tenant-table surface already uses direct `organization_id` columns plus FORCE-RLS; reviewed exclusions stay out of that contract intentionally.
3. **Solo mode is a subset of SaaS mode**: Solo mode disables multi-org management — it does not require a different data model. An organization still exists; it just has one member and is never surfaced as a concept in the UI.

**The current tradeoff**: Solo mode already carries the same runtime org concepts as SaaS mode. That shared model is now fully hardened for the shipped enrolled tenant tables; the remaining distinction is contract scope, not a separate solo-only architecture.

### Runtime Switch

```python
# settings.py
QUICKSCALE_MODE = "solo"  # or 'saas'
```

`TenantMiddleware` reads this setting and changes two behaviours:

- **URL resolution**: In solo mode, middleware auto-resolves the org from the user's personal org. In SaaS mode, the org is resolved from the **session** (`ACTIVE_ORG_SESSION_KEY`), set at signup/org-creation and stable for the session lifetime. The org-management pages live under `/orgs/...`; the shipped module content routes are flat and rely on `request.org` / the current-org ContextVar rather than URL kwargs.
- **Guard behaviour**: In solo mode, the post-signup guard auto-creates a personal org silently. In SaaS mode, it redirects the user to `/orgs/new/` to name their organization.

The orgs module now ships a single URL module. The deployment mode changes request behavior, not which Django URL module is imported:

```python
urlpatterns += [path("", include("quickscale_modules_orgs.urls"))]
```

The same org views serve both modes. Org-management pages keep `org_slug` where needed (`/orgs/<slug>/...`), while tenant content routes do not use org-scoped URL kwargs. The active org is resolved from middleware-established context.

### Upgrade Path: Solo → SaaS

```bash
# 1. Change setting
QUICKSCALE_MODE = 'saas'

# 2. Run once after deploy
python manage.py promote_to_saas
```

`promote_to_saas` ships as part of the org/billing bridge. It keeps existing personal organizations, fills blank personal-org slugs from the owner username, suffixes collisions deterministically, and prints the required `QUICKSCALE_MODE = 'saas'` settings change instead of mutating settings files directly.

---

## Ownership Levels

The system has two distinct ownership tiers that must not be confused.

### Level 1: Platform Owner (Django Superuser)

The platform owner is the person or team who deploys and operates the QuickScale SaaS. They:

- Use `/admin/` as the primary operator surface, and in the shipped foundation slice can also access org-scoped runtime routes without membership as an application-layer operator path
- Hold `is_superuser=True` and `is_staff=True` in Django
- Are not represented by `OrganizationMembership`, even when using that shipped operator path
- Must not treat that shipped runtime access as proof of any future PostgreSQL RLS bypass; any DB-level operator access must still be designed explicitly
- Own the Stripe account that receives subscription payments from customers
- Deploy and upgrade the platform; enable or disable modules globally
- Are the only ones who can create or delete organizations via the admin panel in exceptional cases

The platform owner is **not** an organization member in the RBAC sense and does not appear in any `OrganizationMembership` record.

### Level 2: Organization Hierarchy (Customer Users)

Each customer workspace (organization) has its own internal hierarchy. Ordinary organization requests are isolated by org membership checks, routing, request-scoped org context, and PostgreSQL RLS on the shipped enrolled tenant-table surface.

```
Platform Owner (Django superuser)
└── /admin/ — operator surface, separate from org-scoped runtime
              ↓ operates
    QuickScale SaaS Platform
    (1 Railway: 1 app service + 1 PostgreSQL 18 service)
              ↓
    ┌─────────────────────┐   ┌─────────────────────┐
    │  Org: Acme Corp     │   │  Org: Widget Co      │  …N tenants
    │  slug: acme-corp    │   │  slug: widget-co     │
    │  stripe_customer_id │   │  stripe_customer_id  │
    └────────┬────────────┘   └──────────┬───────────┘
             │                           │
    alice@acme.com  OWNER       (same internal structure)
    bob@acme.com    ADMIN
    carol@acme.com  MEMBER
    dave@acme.com   VIEWER

Current request isolation:
    Acme Corp users       → org middleware + membership checks resolve Acme context
    Widget Co users       → org middleware + membership checks resolve Widget context
    Tenant ORM scoping    → `TenantManager` reads the current-org ContextVar and fails closed with `.none()` when unset
    Tenant DB hardening   → PostgreSQL FORCE RLS on all 21 enrolled models via `NULLIF(current_setting('app.current_org_id', true), '')::uuid`
```

### Capability Matrix

| Capability | Platform Owner | Org Owner | Org Admin | Org Member | Org Viewer |
|---|---|---|---|---|---|
| Access `/admin/` | ✅ | ❌ | ❌ | ❌ | ❌ |
| See all tenants' data | ✅ | ❌ | ❌ | ❌ | ❌ |
| Create / delete an org | ✅ (via admin) | ✅ (own org) | ❌ | ❌ | ❌ |
| Manage org billing | ✅ (via admin) | ✅ (own org) | ❌ | ❌ | ❌ |
| Invite org members | ✅ (via admin) | ✅ | ✅ | ❌ | ❌ |
| Remove org members | ✅ (via admin) | ✅ | ✅ | ❌ | ❌ |
| Change org settings | ✅ (via admin) | ✅ | ✅ | ❌ | ❌ |
| Transfer ownership | ✅ (via admin) | ✅ | ❌ | ❌ | ❌ |
| Use CRM / CMS / etc. | ✅ | ✅ | ✅ | ✅ | read-only |

In the current shipped foundation slice, that platform-owner `✅` for org-scoped runtime access comes from explicit application-layer superuser branches in org middleware and role guards. It is an operator path for today's runtime contract, not evidence that future PostgreSQL RLS policies would be bypassed automatically.

---

## Terminology

| Term | Definition |
|------|-----------|
| **Platform Owner** | The operator who deploys and runs the SaaS. Has Django `is_superuser`. Not an org member. |
| **Organization** | The paying client unit. Equivalent to "team", "workspace", or "tenant". |
| **Member** | An individual user who belongs to one or more organizations. |
| **Role** | The member's permission level within a specific organization. |
| **Org Owner** | The member who created the organization; the Stripe billing contact. |
| **Invitation** | A pending email-based request to join an organization before the recipient has a user account. |
| **Personal Org** | In Solo mode, the single organization auto-created for each user at signup. |

A user account is global (one email, one login). A user's role is org-scoped. Regular users belong to exactly one organization. The server session is the sole authority for org resolution — no org switcher in the user-facing UI. VIEW-AS (superuser-only) provides operator org-scope switching for debugging; see [decisions.md §Module & Theme Architecture](./decisions.md#module-theme-architecture).

---

## Tenancy Strategy: Shared Deployment + registry-backed PostgreSQL isolation

### Architecture

One Railway project: one application service and one PostgreSQL 18 service. All organizations share the same database and the same schema. `TenantMiddleware` resolves the active org, the execute-wrapper derives `app.current_org_id` from the current-org ContextVar, and the tenant registry marks the shipped repo surface explicitly. Today that surface contains **21 ENROLLED models** across CRM, Forms, Billing, Blog, Listings, and Social; each enrolled table has a direct `organization_id` column and a live FORCE-RLS policy. Reviewed exclusions (org control-plane models, system-wide billing metadata, `AuthorProfile`, abstract bases, test-only models, auth `User`, backups operational models, and notifications operational models) remain outside the tenant-table contract intentionally. The authoritative human-readable overview of the shipped tenant-table surface is the marker-based derived registry view (:func:`get_derived_registry_overview` in ``quickscale_modules_orgs.tenancy``). The derived view is purely marker-driven — every excluded concrete model carries an explicit ``tenant_excluded`` class attribute. The literal ``TENANT_TABLE_REGISTRY`` is retained as a cross-check target for CI parity assertions.

```
Railway project
├── app service (Django + Gunicorn)
│   └── TenantMiddleware + execute_wrapper
│       → resolves request.org, sets the current-org ContextVar, primes `app.current_org_id`
└── postgres service (PostgreSQL 18)
    └── Active RLS — all ENROLLED tenant tables:
        USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
```

The `true` second argument to `current_setting` returns `NULL` instead of raising when the setting is absent, and the shipped policy template wraps it in `NULLIF(..., '')::uuid`. That makes an unguarded query fail closed with an empty set across the enrolled tenant-table surface.

### Why This Architecture

- **Cost**: 2 Railway services regardless of how many tenants exist. Railway bills by compute and memory, not by tenant count. At 100 tenants or 10 000, the bill changes only with actual usage.
- **Defence-in-depth (active on the shipped tenant-table surface)**: the middleware-set org context gives RLS a fail-closed database hook. All 21 enrolled tenant tables now enforce database-level isolation on top of application-layer guards.
- **Operational simplicity**: One backup covers all tenants. One migration covers all tenants. One deploy upgrades all tenants simultaneously.
- **Proven pattern**: Supabase, Stripe, and Slack all use shared-database isolation at scale. The shipped implementation in `quickscale_modules/orgs/` is the reference for isolation code; see the Supabase comparison below for the structural argument.

### Supabase Architecture Comparison

QuickScale's isolation model is structurally equivalent to Supabase's. Both are shared-schema PostgreSQL with FORCE RLS.

| Dimension | Supabase | QuickScale |
|---|---|---|
| Isolation unit | User (`auth.uid()`) or custom JWT claim | Organization (`app.current_org_id`) |
| Context carrier | JWT claim, injected per-transaction by PostgREST | PostgreSQL GUC, derived from ContextVar by execute_wrapper |
| Policy syntax | `USING (auth.uid() = user_id)` | `USING (organization_id = NULLIF(current_setting('app.current_org_id',true),'')::uuid)` |
| Admin bypass | `service_role` (BYPASSRLS) | No shipped runtime BYPASSRLS admin path; admin/debug stays on the restricted runtime role via explicit org selection / VIEW-AS |
| Debug impersonation | Dashboard "Impersonate User" button | VIEW-AS feature (shipped) |
| Policy tester | Dashboard UI | `isolation-conformance` CI job |
| Deployment | Supabase managed cloud | Self-hosted Railway (one app + one Postgres service) |

The primary engineering difference is injection mechanism: Supabase's PostgREST sets the GUC from JWT claims before every query (automatic); QuickScale's shipped execute-wrapper derives the GUC from the ContextVar at every transaction start (equivalent guarantee, different wiring).

QuickScale adds the Solo/SaaS deployment mode distinction that Supabase (as a per-project service) does not need to model.

### Known Constraints

- **Operator access must stay explicit**: the current admin/operator surface is outside the tenant-scoped runtime path. With RLS active on the enrolled tenant-table surface, operator access is implemented deliberately per the per-org runtime-role admin contract — explicit per-org selection via the session, fail-closed when unresolved, with no `BYPASSRLS` or automatic cross-tenant bypass. Django `is_superuser` does not infer database-level access.
- **Noisy neighbour**: One tenant running expensive queries slows response times for others. Acceptable at MVP scale; address with `statement_timeout` and rate limiting later.
- **RLS debugging**: when PostgreSQL policies are active, policy failures are silent (rows vanish; no exception is raised). Debugging requires checking `pg_policies` and PostgreSQL logs, not just Django stack traces.
- **Migrations**: Migrations that add columns or change constraints on tenant tables run against all tenants at once. This is a feature (one migration), but large-table migrations need `CONCURRENTLY` indexes and zero-downtime patterns.
- **`SET LOCAL` vs `SET`**: `SET LOCAL` scopes the org context to the current transaction. `SET` (session-level) is needed for PgBouncer compatibility. Choose based on connection pooling setup; document this in the deployment guide.

---

## RBAC Design

### Role Hierarchy

Four roles in ascending permission order:

| Role | Can do |
|------|--------|
| `VIEWER` | Read org resources; cannot modify anything |
| `MEMBER` | Full read/write access to org resources |
| `ADMIN` | Member permissions + invite/remove members, manage org settings |
| `OWNER` | Admin permissions + delete org, transfer ownership, manage billing |

An organization has exactly one Owner at any time. Ownership can be transferred. An organization must always have an Owner — the last Owner cannot be demoted or removed.

### Why Not Django Groups

Django's permission groups are global — a user in the "Admin" group is an admin everywhere in the system. Org roles are org-scoped: the same user can be an Owner in one organization and a Viewer in another. An `OrganizationMembership` model with a `role` field is the correct primitive, not Django groups.

Django's `is_staff` and `is_superuser` flags continue to control access to the Django admin panel. They have no relationship to org roles.

### Permission Checking Pattern

Views check org membership and minimum role via a decorator or mixin:

```python
# Conceptual — not final implementation
@require_org_role(min_role=OrgRole.ADMIN)
def org_settings(request, org_slug): ...
```

The decorator resolves the current organization from the URL (`org_slug`), looks up the `OrganizationMembership` for `request.user`, and returns HTTP 403 if the user is not a member or their role is below the minimum. The organization is also stored on `request.org` for downstream use.

```python
ROLE_HIERARCHY = {
    OrgRole.VIEWER: 0,
    OrgRole.MEMBER: 1,
    OrgRole.ADMIN: 2,
    OrgRole.OWNER: 3,
}
```

---

## Data Model

### Core Models

```
Organization
  id            UUID (PK, default uuid4)
  name          CharField(max_length=100)
  slug          SlugField(unique=True)              # URL identifier, e.g. "acme-corp"
  stripe_customer_id  CharField(blank=True)         # Stripe customer tied to the org
  is_personal   BooleanField(default=False)         # True for Solo-mode auto-created orgs
  created_at    DateTimeField(auto_now_add)

OrganizationMembership
  id            BigAutoField (PK)
  user          FK → User (on_delete=CASCADE)
  organization  FK → Organization (on_delete=CASCADE)
  role          CharField(choices=OWNER|ADMIN|MEMBER|VIEWER)
  invited_by    FK → User (nullable, on_delete=SET_NULL)
  joined_at     DateTimeField(auto_now_add)

  class Meta:
      unique_together = [('user', 'organization')]
      # One org per regular user. The unique_together constraint prevents accidental
      # duplicates. Multi-org membership for a single user is possible at the DB level
      # but is not exposed in the regular UI — VIEW-AS handles operator debug needs.

OrganizationInvitation
  id            UUID (PK)
  organization  FK → Organization (on_delete=CASCADE)
  email         EmailField
  role          CharField(choices=ADMIN|MEMBER|VIEWER, default=MEMBER)
  invited_by    FK → User (on_delete=CASCADE)
  token         UUIDField(unique=True, default=uuid4)
  expires_at    DateTimeField
  accepted_at   DateTimeField(nullable)

  # A pending invitation is: accepted_at is None AND expires_at > now
```

### TenantModel Abstract Base

The organizations module ships a `TenantModel` abstract base class. Any module that stores tenant-scoped data inherits from it to get the canonical `organization` FK, the shared manager contract, and the base-manager wiring in one place.

```python
class TenantModel(models.Model):
    organization = tenant_org_fk(
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
```

The shipped repo-enrolled surface currently covers CRM, blog, forms, listings, billing, and social. Cross-module migration dependency ordering must be documented in the organizations release note when new tenant tables join the contract.

---

**Historical design note**: some headings below preserve rollout-era phase labels, but the current shipped contract already includes the org-billing bridge, enrolled-table PostgreSQL RLS, VIEW-AS, and generated React org pages. Only sections explicitly labeled future-ready or deferred should be read as not-yet-shipped work.

---

## Billing Integration

### The Gap

The billing module binds subscriptions and credit balances to individual users:

```
Subscription.user  → FK → User
CreditBalance.user → FK → User (OneToOne)
```

This is wrong for a team SaaS. Clients pay for their organization; individual members consume credits on behalf of the organization. The billing contact is the Org Owner, not an arbitrary user account.

### Resolution

Phase 6 now makes the organization the authoritative billing owner while retaining a narrow user-level provenance bridge for compatibility during the cutover:

```
Subscription.organization  → FK → Organization (authoritative owner)
Subscription.user          → nullable FK → User (provenance / compatibility only)
CreditBalance.organization → OneToOneField → Organization (authoritative balance owner)
CreditBalance.user         → nullable OneToOneField → User (provenance / compatibility only)
CreditTransaction.organization → FK → Organization (authoritative ledger scope)
CreditTransaction.user     → nullable FK → User (acting org member provenance / audit actor)
Plan.features             → JSONField(default=list) (sole entitlement source)
```

`Organization.stripe_customer_id` is the Stripe customer identifier. The Org Owner's email is the Stripe billing email. When the Owner transfers ownership, the Stripe customer record stays with the organization (not the departing user).

Credit transactions stay attributed to the acting user (`CreditTransaction.user`) while debiting the authoritative organization balance, and that user link now nulls cleanly on deletion so the org ledger row remains intact.

The billing tenant tables (`Subscription`, `CreditBalance`, `CreditTransaction`) are part of the enrolled tenant-table surface and therefore follow the same `organization_id` + `TenantManager` + FORCE-RLS contract as the other shipped tenant-owned models. `Plan` and `WebhookEvent` remain reviewed exclusions because they are system-wide metadata, not tenant-owned rows.

### Hybrid Billing Model: Credits + Feature Gates + Optional Seats

QuickScale currently combines the credit-pool model (QuickScale's core mechanic) with plan-level feature gating. Optional seat pricing remains future design work; the current Phase 6 contract does not yet ship `max_seats` or seat-addon Stripe prices.

**Credits** measure consumption — AI operations, API calls, or any metered action. Every plan includes a monthly credit allocation. Credits do not expire within the billing period and roll over at the operator's discretion.

**Feature gates** control which modules are available at each plan tier. This gives operators a tool to upsell without requiring a custom per-org flag system.

**Seat pricing** remains optional follow-on work. The design below stays as a future-ready reference, but the current shipped bridge does not yet expose seat fields or seat billing enforcement.

| Plan tier | Monthly credits | Modules included | Max seats (optional) |
|-----------|-----------------|-----------------|----------------------|
| Starter   | 500             | Blog, Forms | 3 |
| Growth    | 2 000           | All modules | 10 |
| Pro       | Unlimited       | All modules | Unlimited |

Seat limits and module gates are advisory — enforced in the UI and API, but not at the database layer. Hard enforcement (database constraints on membership count) is deferred.

### Plan Feature Gate Implementation

Feature gates are stored as a list of module keys on the `Plan` model:

```
Plan
  name            CharField
  stripe_price_id CharField
  credits_per_month  IntegerField (0 = unlimited)
  features        JSONField(default=list)   # e.g. ["blog", "forms", "crm", "listings"]
  max_seats       IntegerField (0 = unlimited)
  seat_price_id   CharField(blank=True)     # Stripe price for per-seat addon (optional)
```

Views check feature access via a decorator:

```python
@require_org_feature("crm")
def crm_index(request): ...
```

This decorator resolves the current organization's active subscription through the billing ORM, selects its `Plan`, and checks `Plan.features` as the sole entitlement source. It returns HTTP 402 when the org has no active subscription or when the feature key is absent.

### Migration Path from User-Scoped Billing

For deployments already using user-scoped billing, `migrate_billing_to_orgs` ships as the idempotent bridge command. It reuses a sole existing organization when one is already resolvable for the billing user; otherwise it creates a personal org via the standard helper, migrates authoritative `Subscription`, `CreditBalance`, and `CreditTransaction` ownership to that organization, syncs a sole Stripe customer id when safe, and aborts ambiguous cases instead of guessing. Run it once after deploying the organizations module.

---

## Customer Onboarding Flow

### SaaS Mode

Customers self-provision without platform owner intervention:

```
1. /accounts/signup/      → customer creates a global user account (django-allauth)
2. Redirect → /orgs/new/ → customer creates their organization (name, slug)
3. Stripe checkout        → customer subscribes to a plan
4. Redirect → /orgs/<slug>/  → org dashboard, ready to use
```

**Post-signup guard**: Authenticated users with no `OrganizationMembership` are redirected to `/orgs/new/` by `TenantMiddleware` for ordinary requests. The shipped carveout is the slugless invitation continuation path under `/orgs/invitations/<token>/accept/`, which stays reachable so a pending invite can resume after auth instead of being forced through org creation.

### Solo Mode

```
1. /accounts/signup/  → customer creates a global user account (django-allauth)
2. TenantMiddleware auto-creates a personal Organization (is_personal=True, slug=username)
3. Redirect → /       → dashboard, ready to use (no org creation step shown)
```

The allauth adapter handles both modes:

```python
class OrgsAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        if not OrganizationMembership.objects.filter(user=request.user).exists():
            if settings.QUICKSCALE_MODE == "solo":
                Organization.objects.create_personal_for(request.user)
                return "/"
            return "/orgs/new/"
        return super().get_login_redirect_url(request)
```

Wired via `ACCOUNT_ADAPTER = 'quickscale_modules_orgs.adapters.OrgsAccountAdapter'` in module settings.

---

## Invitation Flow

Invitations are active only in SaaS mode. In Solo mode the invitation views stay hidden behind HTTP 404.

1. An Admin or Owner opens the org members/admin surface and submits an invite form with an email address and role.
2. The system creates an `OrganizationInvitation` record with a UUID token and a 7-day expiry.
3. The notifications module renders and sends the registry-backed `org_invitation` email with the public accept URL.
4. Accept URL: `GET /orgs/invitations/<token>/accept/`
    - The URL is intentionally slugless so invite redemption can continue before org membership resolution exists.
    - Unauthenticated visitors are redirected through auth and then resumed back into `AcceptInvitationView`.
    - Redemption happens in `AcceptInvitationView` after auth, and membership side effects run only when the signed-in email matches the invitation email after normalization.
    - New users can complete signup first; the same accept view resumes and redeems the invite after auth succeeds.
5. Expired or already-accepted tokens return HTTP 410 with a user-facing message.
6. Revoking an invitation deletes the `OrganizationInvitation` row; the token URL becomes HTTP 404.
7. Ordinary SaaS no-membership traffic still goes to `/orgs/new/`; the public invitation accept path is the narrow bootstrap carveout for pending invite continuation.

### Focused Validation Notes

- Coverage stays focused on invite send/revoke, the slugless accept continuation path, auth redirect/resume behavior, normalized-email redemption guards, and Solo-mode 404 handling.
- This slice now sits on top of the shipped enrolled-table RLS surface and coexists with the generated React org pages; neither changes the invitation contract itself.

---

## URL Structure

### SaaS Mode

Path routing (not subdomain). The org slug is part of the org-management surface; the shipped module content routes are now flat and resolve the active organization from `request.org` / the current-org ContextVar rather than from a content-route slug.

```
/orgs/                                     # List orgs the current user belongs to
/orgs/new/                                 # Create a new org + Stripe checkout
/orgs/<slug>/                              # Org dashboard
/orgs/<slug>/members/                      # Member list, role management, invite send/revoke
/orgs/invitations/<token>/accept/          # Public invitation accept / continuation
/orgs/<slug>/settings/                     # Org settings (name, slug)

# Module routes (all flat in the shipped server-rendered surface):
/blog/                                     # Blog index
/blog/post/<slug>/                         # Blog detail
/crm/dashboard/                            # CRM dashboard
/forms/                                    # Forms index
/forms/<slug>/                             # Form detail
/listings/                                 # Listings index
/billing/dashboard/                        # Authenticated billing dashboard
/billing/pricing/                          # Public pricing

**Note**: The billing module uses flat routes exclusively in both modes (`/billing/dashboard/`, `/billing/pricing/`, `/api/billing/...`). No org-scoped billing URL tree exists — the org is resolved from `request.org` (set by middleware from session or personal-org fallback), not from a URL slug.

**Note**: CRM, blog, forms, listings, and billing all use flat server routes in the shipped contract. The active organization is resolved from `request.org` / the current-org ContextVar, not from a URL slug.
```

### Solo Mode

```
/                      # Dashboard (org resolved silently from user's personal org)
/blog/                 # Blog
/crm/                  # CRM
/forms/                # Forms
/listings/             # Listings
/billing/pricing/      # Public pricing
/billing/dashboard/    # Authenticated billing dashboard
/account/settings/     # User settings
```

No org management pages are exposed in solo mode.

### React Frontend Routes

#### SaaS mode

```
/orgs                   → OrgListPage
/orgs/new               → OrgCreatePage
/orgs/:slug             → OrgDashboardPage  (rendered inside OrgLayout)
/orgs/:slug/blog        → BlogPage (SaaS org-context page; `/blog` redirects here)
/orgs/:slug/listings    → ListingsPage (SaaS org-context page; `/listings` redirects here)
/orgs/:slug/members     → OrgMembersPage (member list, role changes, invite send/revoke)
/orgs/:slug/settings    → OrgSettingsPage
/crm                    → CrmPage (flat route)
/forms                  → FormsPage (flat route)
/forms/:slug            → FormsPage (flat route)
```

**Note:** The generated `showcase_react` SaaS surface keeps org-management pages under `/orgs/:orgSlug/...`, serves CRM and forms at flat routes, and uses legacy redirect shims (`/blog`, `/listings`, `/settings`) to land the user on the active-org route when needed. Billing remains Django-page navigation (`/billing/dashboard/`, `/billing/pricing/`) rather than a generated React billing page.

`OrgLayout` is a React wrapper that injects `orgSlug` from `useParams()` into the generated org pages. No org switcher is rendered in the user-facing UI — regular users belong to exactly one org. VIEW-AS (superuser-only) provides the debug path for operators; see [decisions.md §Module & Theme Architecture](./decisions.md#module-theme-architecture).

#### Solo mode

```
/                       → DashboardPage
/blog                   → BlogPage
/crm                    → CrmPage
/forms                  → FormsPage
/listings               → ListingsPage
```

No `OrgLayout` or org switcher is rendered. Billing remains Django-page navigation rather than a generated React billing page.

### Subdomain Routing (Future-Ready)

Subdomain routing (`acme.myapp.com`) is not in scope, but the architecture is designed to support it with no changes to views or models.

`TenantMiddleware` currently resolves the org from the session (`ACTIVE_ORG_SESSION_KEY`) in SaaS mode and from the authenticated user's personal org in Solo mode; the middleware carries no content-route slug fallback. To support subdomains, only the initial SaaS resolution step changes — instead of reading the session first, the middleware would read the subdomain from `request.get_host()`:

```python
# Current (session-based SaaS resolution):
org_id = request.session.get(ACTIVE_ORG_SESSION_KEY)

# Future (subdomain-based):
host = request.get_host()
slug = host.split(".")[0] if host.count(".") >= 2 else None
if slug:
    org = Organization.objects.get(slug=slug)
    # then set request.org and the current-org ContextVar as today
```

Everything downstream (`request.org`, the current-org ContextVar, permission checks, and any caller-managed RLS priming) is identical. DNS wildcard and NGINX configuration changes are documented in `docs/deployment/railway.md` when the feature is implemented.

---

## TenantMiddleware

The middleware uses **session-based org resolution** for SaaS mode and personal-org resolution for Solo mode. It populates `request.org` plus the current-org ContextVar, but it does **not** hold a request-long transaction or issue `SET LOCAL` directly.

The middleware carries no slug/fallback resolution paths for content routes: org-management URLs (`/orgs/...` and `/api/orgs/...`) bypass tenant resolution so the orgs views can own access control, while all other SaaS requests either resolve an active session org or fail closed.

Key behaviours (current):
- **SaaS mode + active session org** → resolves the org from the session key, validates membership, and sets `request.org` + the current-org ContextVar.
- **SaaS mode + no active session org** → redirects to `/orgs/` for non-exempt, non-org-management paths.
- **Solo mode** → resolves the personal org from the authenticated user's membership.
- **VIEW-AS debug override** → a superuser debug session org takes priority over the normal Solo/SaaS branch.
- **Org-management path bypass** → `/orgs/...` and `/api/orgs/...` requests owned by the orgs module bypass middleware tenant resolution so the views can own access control.

**Connection/RLS note**: DB-level `app.current_org_id` priming is now caller-managed (`tenant_context(...)`, `org_scope(...)`, or the execute-wrapper path where applicable). When deployment topology requires session-level `SET` instead of transaction-local `SET LOCAL`, document that explicitly in `docs/deployment/railway.md`.

---

## Admin Panel Contract

The current organizations foundation keeps Django `/admin/` as the primary operator surface. With RLS now active on the enrolled tenant-table surface, the per-org runtime-role admin contract applies: org-aware admin flows operate through explicit per-org request selection → session persistence → fail-closed behavior under the app runtime role. No `BYPASSRLS` role or automatic cross-tenant operator bypass was introduced. Django superusers on the runtime-role connection see only the rows their session org selects, matching the contract enforced for ordinary users.

**RLS note**: operator access is implemented deliberately per the per-org runtime-role contract. Do **not** assume Django `is_superuser` or `is_staff` automatically bypasses database policies — they do not, and no operator bypass policy was deployed.

**Operator expectation**: admin list views for org-aware models should expose an `organization` column and an `organization` list filter so the operator can focus on a specific client when needed. Any later registry or admin-query-path change must re-verify those caller-parity paths before claiming all-tenant visibility.

**No tenant should ever have `is_staff=True`.** Organization-scoped administration happens through the org settings pages at `/orgs/<slug>/settings/`, not through Django admin.

---

## Operator Debug Mode (View-As)

**Status: implemented.**

Supabase ships a dashboard "Impersonate User" button so operators can see the app exactly as a specific user sees it — essential for debugging silent RLS row-filtering. QuickScale now ships the equivalent "view app as this org" feature for Django superusers.

### How It Works

1. In Django Admin (`/admin/`), an operator uses the VIEW-AS entry point for an `Organization` row.
2. The action sets the session key `quickscale_modules_orgs.debug_as_org_id` to the org's UUID and redirects to `/`.
3. `TenantMiddleware` detects the session key (superusers only) and resolves the org from it instead of the normal Solo/SaaS path.
4. A persistent debug banner renders at the top of every page:
   `⚠ DEBUG MODE — viewing as org "Acme Corp" [Exit debug mode]`
5. The operator uses the app normally; all RLS policies and tenant filters apply exactly as they would for an Acme Corp member — no BYPASSRLS.
6. Clicking "Exit debug mode" clears the session key and restores normal resolution.

### Security Properties

- Only `is_superuser=True` users can set the session key; the middleware ignores it for non-superusers.
- The debug session uses the same restricted runtime role (`NOBYPASSRLS`) as all other tenant paths — RLS remains fully enforced. The operator sees exactly what an Acme Corp member sees.
- Every debug activation is audit-logged: who activated it, which org, when, from which path.
- Depends on the shipped GUC/ContextVar wiring so the debug session sees the same restricted-role row set as an ordinary tenant request.

### Implementation Scope

| File | Change |
|---|---|
| `orgs/middleware.py` | Add `_resolve_debug_org()` called before Solo/SaaS path |
| `orgs/admin.py` | Add `view_as_org` and `exit_debug_mode` actions to `OrganizationAdmin` |
| `orgs/views.py` | Add `DebugAsOrgView`, `ExitDebugModeView` (superuser-only) |
| `orgs/urls.py` | Two new URL patterns for activate/exit |
| Base template | Debug banner conditional on session key + `is_superuser` |

---

## Decisions

All open questions from the original design were resolved before implementation began.

| Question | Decision | Rationale |
|----------|----------|-----------|
| Multi-org membership? | **No** — regular SaaS users belong to exactly one org | Eliminates the dual-source-of-truth problem (session is sole authority); removes need for explicit-org API contract. Multi-org membership at the DB level is not precluded but is not exposed in the UI. VIEW-AS handles operator debug needs. |
| `Organization` model location? | **`quickscale_modules_orgs`** | Auth stays minimal and standalone; orgs depends on auth, not the reverse |
| Solo vs SaaS resolution? | **Runtime** — `QUICKSCALE_MODE` setting | Start solo, scale to SaaS without code regeneration; one schema, one codebase |
| Billing migration path? | **Auto-create personal org per user** | Management command `migrate_billing_to_orgs`; idempotent; zero manual operator work |
| Admin panel isolation? | **Operator access is explicit and separate from tenant runtime** | The enrolled tenant-table surface now runs under the per-org runtime-role admin contract (explicit per-org selection → session → fail-closed); no operator bypass or `BYPASSRLS` deployed |
| Active org routing? | **Session-based in SaaS; personal-org resolution in Solo** | Org-management pages stay under `/orgs/...`; shipped server content routes are flat for CRM, blog, forms, listings, and billing; fresh `showcase_react` SaaS pages keep org-slug blog/listings routes with flat redirect shims. Solo mode resolves the personal org transparently. |
| Post-signup flow? | **SaaS: force `/orgs/new/`. Solo: auto-create personal org** | SaaS users must name their workspace; solo users should not see org concepts |
| Module access per plan? | **Feature gates + credits** | Credits for consumption metering; feature gates for upsell leverage; no per-org custom flags |
| Seat pricing? | **Optional, designed in** | Operator-configurable; enforced at UI/API layer; hard DB enforcement deferred |
| Subdomain routing? | **Future-ready** | Middleware decoupled from org source (session today); subdomain support swaps the session read for a host-based lookup, everything downstream unchanged |
| Org provisioning? | **Self-service** | Customer signs up, creates org, pays Stripe — no manual platform owner action required |

---

## Current Implementation Scope

This section records the current repository slice, not the eventual end-state design.

| Deliverable | Status |
|-------------|--------|
| `Organization`, `OrganizationMembership`, `OrganizationInvitation` models | ✅ implemented |
| Django admin registration for core org models | ✅ implemented |
| `TenantModel` abstract base class with `organization` FK | ✅ implemented |
| `QUICKSCALE_MODE` setting with Solo / SaaS behaviour | ✅ implemented |
| `TenantMiddleware` (Solo/SaaS org resolution, `request.org`, `app.current_org_id`) | ✅ implemented |
| Middleware caller-parity coverage for bootstrap/exempt vs org-scoped paths | ✅ implemented |
| `require_org_role` decorator + `OrgRoleMixin` | ✅ implemented |
| `require_org_feature` decorator | ✅ implemented with ORM-backed active-subscription lookup and `Plan.features` entitlement checks |
| Post-signup: auto-create personal org (Solo) or redirect to `/orgs/new/` (SaaS) | ✅ implemented |
| PostgreSQL RLS migration for downstream tenant tables | ✅ implemented for the shipped repo surface — 21 enrolled tenant models across CRM, Forms, Billing, Blog, Listings, and Social |
| PostgreSQL cross-org isolation test suite | ✅ implemented — restricted-role proofs plus the `isolation-conformance` CI job cover the enrolled tenant-table surface on PostgreSQL |
| Server-rendered self-service org creation, dashboard, members, settings, and import-compatible org URL surfaces | ✅ implemented |
| Server-rendered invitation flow: invite send/revoke on org admin surfaces, notifications registry-backed email, and slugless public accept continuation under `/orgs` | ✅ implemented |
| Org-authoritative billing bridge (organization ownership fields, canonical org billing routes, flat compatibility shims, and ORM-backed feature gating) | ✅ implemented |
| `migrate_billing_to_orgs` / `promote_to_saas` management commands | ✅ implemented |
| React org-management UI surfaces | ✅ implemented for fresh `showcase_react` generations (`OrgListPage`, `OrgCreatePage`, `OrgLayout`, `OrgDashboardPage`, `OrgMembersPage`, `OrgSettingsPage`) |
| Subdomain routing | ❌ future-ready (middleware decoupled; DNS/NGINX config deferred) |
| Hard seat-count enforcement at DB layer | ❌ deferred |
| Per-tenant analytics | ❌ deferred |
| Operator debug mode: "view app as this org" (VIEW-AS) | ✅ implemented — superuser session-scoped impersonation with debug banner and audit trail |
| Cross-org admin tooling beyond VIEW-AS | ❌ deferred |

---

## F11.13b — Structural Isolation Rollout: Adoption Path for Existing Projects

Already-generated QuickScale projects that add the organizations module (or upgrade to a release that includes structural multi-tenant isolation) must adopt the shared `TenantManager` + ContextVar contract to maintain correct tenant scoping across all code paths.

### Dual-Manager Contract Summary

Every tenant-scoped model (one that inherits from `TenantModel` or carries an `organization` FK) ships two managers:

| Manager | Class | Purpose | Use in |
|---------|-------|---------|--------|
| `objects` | `TenantManager()` | Default manager; reads the current organization from the shared ContextVar and auto-filters querysets to that org. When no org context is set, it fails closed with `.none()`. | Views, services, tenant-facing request code, scoped background work |
| `all_objects` | `TenantManager(super_scope=True)` | Operator escape hatch; removes Python-side tenant auto-filtering. It does **not** by itself bypass PostgreSQL RLS. | Admin `get_queryset()`, audited commands, explicit operator/superuser paths |

The authoritative tenant-facing API is **ambient scoping**, not `.for_org(...)` chaining.

### Tenant-Scoped: ambient `TenantManager`

Use the default `objects` manager only after the current org has been established:

- **Views and services** — request-scoped paths rely on `TenantMiddleware` to resolve the org, set `request.org`, and populate the ContextVar that `TenantManager` reads:
  ```python
  def listing_index(request):
      posts = Post.objects.filter(published=True)
      ...
  ```
- **Manual shell / one-off queries** — establish org scope explicitly before using the default manager:
  ```python
  from quickscale_modules_orgs.current_org import org_scope
  from quickscale_modules_orgs.models import Organization

  org = Organization.objects.get(slug="acme-corp")
  with org_scope(org):
      posts = Post.objects.filter(published=True)
  ```

### Operator Path: `all_objects`

Use `Model.all_objects.all()` in:

- **Admin classes** — subclass `TenantModelAdmin` (from `quickscale_modules_orgs.admin`) instead of `admin.ModelAdmin` for tenant-scoped models. `TenantModelAdmin` resolves the active org from the VIEW-AS session, explicit request selection, or session persistence (fail-closed) and automatically scopes `get_queryset` to that org via `_org_db_context`. All standard admin views (`changelist_view`, `add_view`, `change_view`, `delete_view`, `history_view`) are wrapped in `org_scope()` so the Python ContextVar and PostgreSQL GUC are set correctly for RLS. Add an `organization` column and list filter so the operator can focus on a specific client when needed.
- **Management commands** — cross-tenant commands should run under `operator_access(reason=...)` and use `all_objects` only when they truly need an unfiltered queryset:
  ```python
  from django.db import transaction

  with transaction.atomic():
      with operator_access(reason="nightly-maintenance"):
          for form in Form.all_objects.all():
              ...
  ```
  ``operator_access`` requires an active ``transaction.atomic()`` block because the underlying ``SET LOCAL`` is transaction-scoped. It **only grants cross-tenant read visibility** — the PostgreSQL RLS policy template splits operator elevation into a separate ``FOR SELECT`` sub-policy (``{policy_name}_select``), so write and delete operations remain scoped to the current organization even when operator_access is active. Callers must verify ``user.is_superuser`` before entering the context manager.
- **Operator/superuser shell work** — any ad-hoc query that legitimately needs the unfiltered ORM queryset, subject to the active DB-role / RLS contract.

### Adoption Steps

For a generated project that already exists and is adding structural isolation:

1. **Add `quickscale_modules_orgs` to `INSTALLED_APPS`** and run its migrations.
2. **Add `TenantMiddleware`** to the middleware stack and configure `QUICKSCALE_MODE` (see [Deployment Mode](#deployment-mode-solo-vs-saas-organizations) above).
3. **Wire URL routing** — load org-scoped or solo URL patterns conditionally based on `QUICKSCALE_MODE`.
4. **Add the shared manager contract** to every tenant-scoped model that does not already have it — `objects = TenantManager()` and `all_objects = TenantManager(super_scope=True)` (or inherit from `TenantModel`, which provides that contract).
5. **Backfill `organization_id`** on existing rows — the FK is required for new rows; existing rows may need a data migration to assign an org.
6. **Switch views and services** — remove `.for_org(...)` chaining and rely on middleware-established org context for request paths; for non-request paths, enter scope explicitly with `org_scope(...)` / `tenant_context(...)` / `set_current_org_for_context(...)` before using `objects`.
7. **Switch admin classes** — change parent class from `admin.ModelAdmin` to `TenantModelAdmin` (from `quickscale_modules_orgs.admin`). `TenantModelAdmin` auto-scopes querysets to the resolved org and wraps all standard views in org context. Add an `organization` column and list filter for org-aware filtering.
8. **Switch management commands** — audited cross-tenant commands use `operator_access(reason=...)` and `all_objects`; tenant-scoped commands establish org scope explicitly before using the default manager.

### Async Jobs

QuickScale does not currently ship async job infrastructure for generated projects. When async jobs (Celery, Django Q, or similar) are added later, they must follow the same rule:

- **Tenant-scoped jobs** — enter org scope explicitly (`org_scope(...)`, `tenant_context(...)`, or an equivalent helper), then use the default `objects` manager.
- **Admin/operator jobs** — use `Model.all_objects.all()` when the job crosses org boundaries (e.g., a nightly maintenance task that touches every tenant's data), ideally under the same audited operator-access contract as management commands.

No async job path should use the default tenant manager without first establishing org context, and no operator path should rely on hidden bypass behavior.

---

## References

- [`quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`](../../quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py) — shipped RLS and org-context implementation
- [`docs/deployment/railway.md`](../deployment/railway.md) — Railway deployment contract (connection pooling notes, future subdomain config)
- [`docs/technical/decisions.md`](decisions.md) — architecture decision log
- [`quickscale_modules/billing/`](../../quickscale_modules/billing/) — billing models to extend
- [`quickscale_modules/auth/`](../../quickscale_modules/auth/) — User model base
- [`quickscale_modules/orgs/README.md`](../../quickscale_modules/orgs/README.md) — module placeholder
