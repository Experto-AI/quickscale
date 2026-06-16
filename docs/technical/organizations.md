# QuickScale Organizations Module: Design Document

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Organizations Design**
> **Related docs**: [Roadmap](roadmap.md) | [Decisions](decisions.md) | [Tenancy Strategies](../legacy/tenancy-isolation-strategies.md) | [Railway Deployment](../deployment/railway.md)

## Purpose and Scope

The organizations module enables a QuickScale-generated app to be sold as a SaaS product to multiple paying clients. Each client is an **organization** — an isolated workspace with its own data, its own member roster, and its own role-based access control. The operator deploys a single Railway project, clients self-serve signup, subscribe, and invite their colleagues. This is the SaaS-parity milestone that completes the auth → billing → organizations foundation started in v0.84.0–v0.85.0.

QuickScale supports two deployment modes — **Solo** and **SaaS** — resolved at runtime via a single settings flag. Both modes use the same schema and codebase. Solo mode is a constrained configuration of the organization system, not a separate architecture.

**Current implementation note**: the repository currently ships the organizations foundation plus the server-rendered org-management Django surface: core org models/admin wiring, Solo/SaaS runtime branching, request-scoped org resolution, RBAC guards, self-service org creation, the org dashboard, member management, org settings, invite send/revoke on the org admin members surface, the slugless public invitation accept flow that resumes after auth and redeems only when the normalized email matches, and the current org-billing bridge (authoritative org billing ownership fields, canonical org-scoped billing pages/APIs with flat compatibility shims, migration/promote commands, and ORM-backed plan feature gating). Ordinary requests are still isolated in the application layer. PostgreSQL RLS activation, downstream tenant-table adoption, and the React org-management surface remain planned follow-on work unless a later section explicitly says otherwise.

---

## Deployment Mode: Solo vs SaaS-Organizations

### Overview

QuickScale supports two first-class deployment modes, switchable at runtime without code regeneration:

| Aspect | Solo mode | SaaS-Organizations mode |
|---|---|---|
| Target use case | Personal tools, internal apps, indie developers | Multi-tenant SaaS sold to paying clients |
| Organizations per user | 1 (personal org, auto-created) | Many (user may belong to multiple) |
| Org management UI | Hidden | Full (create, invite, settings, billing) |
| Org switcher | Not shown | Shown in sidebar |
| Invitations | Disabled | Enabled |
| URL structure | `/blog/`, `/crm/` (no slug) | `/orgs/<slug>/blog/`, `/orgs/<slug>/crm/` |
| Billing scope | Per-user (org has one member) | Per-org (team billing contact) |
| Isolation today | App-layer guards + middleware org context | App-layer guards + middleware org context |
| PostgreSQL RLS | Deferred until downstream tenant tables carry concrete `organization_id` columns | Deferred until downstream tenant tables carry concrete `organization_id` columns |

### Why Runtime Instead of Generation Time

The natural comparison is SaaS Pegasus, which resolves solo vs SaaS at **generation time** — it generates different code depending on your choice, producing a clean output with no dead code. QuickScale could do the same.

However, runtime resolution is preferable for QuickScale because:

1. **Start solo, scale to SaaS**: The most common trajectory is a developer who starts with a personal tool, gains traction, and wants to offer it as a multi-tenant SaaS. With generation-time resolution, that requires regenerating the project and migrating data. With runtime resolution, it is a one-line settings change plus a management command.
2. **One schema, one codebase**: The organizations foundation keeps a single org abstraction, request context, and runtime branching model across Solo and SaaS. Downstream modules still need concrete `organization` columns before database-level isolation can be enabled everywhere.
3. **Solo mode is a subset of SaaS mode**: Solo mode disables multi-org management — it does not require a different data model. An organization still exists; it just has one member and is never surfaced as a concept in the UI.

**The current tradeoff**: Solo mode already carries the same runtime org concepts as SaaS mode, but the database-hardening step is intentionally deferred. Until downstream modules add concrete `organization_id` columns, isolation for ordinary requests remains in the application layer.

### Runtime Switch

```python
# settings.py
QUICKSCALE_MODE = 'solo'   # or 'saas'
```

`TenantMiddleware` reads this setting and changes two behaviours:

- **URL resolution**: In solo mode, no `org_slug` appears in URLs; middleware auto-resolves the org from `request.user.personal_organization`. In SaaS mode, the slug is extracted from the URL.
- **Guard behaviour**: In solo mode, the post-signup guard auto-creates a personal org silently. In SaaS mode, it redirects the user to `/orgs/new/` to name their organization.

URL patterns are loaded conditionally:

```python
# urls.py
if settings.QUICKSCALE_MODE == 'saas':
    urlpatterns += [path('orgs/', include('quickscale_modules_orgs.urls.saas'))]
else:
    urlpatterns += [path('', include('quickscale_modules_orgs.urls.solo'))]
```

Views are identical in both modes. Only the URL kwargs differ (`org_slug` present or absent).

### Upgrade Path: Solo → SaaS

```bash
# 1. Change setting
QUICKSCALE_MODE = 'saas'

# 2. Run once after deploy
python manage.py promote_to_saas
```

`promote_to_saas` now ships as part of the current org/billing bridge. It keeps existing personal organizations, fills blank personal-org slugs from the owner username, suffixes collisions deterministically, and prints the required `QUICKSCALE_MODE = 'saas'` settings change instead of mutating settings files directly.

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

Each customer workspace (organization) has its own internal hierarchy. Today, ordinary organization requests are isolated by org membership checks, routing, and request-scoped org context. PostgreSQL RLS is a later hardening step once downstream tenant tables carry concrete `organization_id` columns.

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
    Acme Corp users      → org middleware + membership checks resolve Acme context
    Widget Co users      → org middleware + membership checks resolve Widget context
    Future DB hardening  → PostgreSQL RLS after downstream tenant tables expose organization_id
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

A user account is global (one email, one login). A user's role is org-scoped — the same person can be an Owner in one organization and a Member in another. A user may belong to multiple organizations simultaneously; an org switcher in the UI tracks the active context (SaaS mode only).

---

## Tenancy Strategy: Shared Deployment + staged PostgreSQL isolation

### Architecture

One Railway project: one application service and one PostgreSQL 18 service. All organizations share the same database and the same schema. The current foundation slice enforces org isolation for ordinary requests in middleware, URL resolution, and membership/role checks. `TenantMiddleware` already sets `app.current_org_id` for resolved org-scoped requests as the future database-policy hook, but PostgreSQL Row-Level Security (RLS) is not yet enabled because downstream business modules do not all carry concrete `organization_id` columns.

```
Railway project
├── app service (Django + Gunicorn)
│   └── TenantMiddleware → resolves request.org and sets app.current_org_id for org-scoped requests
└── postgres service (PostgreSQL 18)
    └── Future RLS policies only after downstream tenant tables expose organization_id
        USING (organization_id = current_setting('app.current_org_id', true)::uuid)
```

For the later RLS migration, the `true` second argument to `current_setting` will return `NULL` instead of raising an error when the setting is absent. That makes an unguarded query fail closed with an empty set, but only after the PostgreSQL policies are actually enabled.

### Why This Architecture

- **Cost**: 2 Railway services regardless of how many tenants exist. Railway bills by compute and memory, not by tenant count. At 100 tenants or 10 000, the bill changes only with actual usage.
- **Planned defence-in-depth**: the middleware-set org context gives a future RLS migration a fail-closed database hook. Until that activation work lands, views still rely on the application layer to enforce org scoping correctly.
- **Operational simplicity**: One backup covers all tenants. One migration covers all tenants. One deploy upgrades all tenants simultaneously.
- **Proven pattern**: Supabase, Stripe, and Slack all use shared-database isolation at scale. Detailed code examples are in [`docs/legacy/tenancy-isolation-strategies.md`](../legacy/tenancy-isolation-strategies.md) — that document is the reference implementation; this document does not duplicate it.

### Known Constraints

- **Operator access must stay explicit**: the current admin/operator surface is outside the tenant-scoped runtime path. If PostgreSQL RLS is activated later, operator access must be implemented deliberately rather than inferred from Django `is_superuser`.
- **Noisy neighbour**: One tenant running expensive queries slows response times for others. Acceptable at MVP scale; address with `statement_timeout` and rate limiting later.
- **Future RLS debugging**: when PostgreSQL policies are enabled later, policy failures will be silent (rows vanish; no exception is raised). Debugging will require checking `pg_policies` and PostgreSQL logs, not just Django stack traces.
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
def org_settings(request, org_slug):
    ...
```

The decorator resolves the current organization from the URL (`org_slug`), looks up the `OrganizationMembership` for `request.user`, and returns HTTP 403 if the user is not a member or their role is below the minimum. The organization is also stored on `request.org` for downstream use.

```python
ROLE_HIERARCHY = {
    OrgRole.VIEWER: 0,
    OrgRole.MEMBER: 1,
    OrgRole.ADMIN:  2,
    OrgRole.OWNER:  3,
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
      # A user may belong to multiple organizations. unique_together is (user, organization),
      # NOT just (user). An org switcher in the UI tracks the active context.

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

The organizations module ships a `TenantModel` abstract base class. Any module that stores tenant-scoped data inherits from it to get the `organization` FK, the RLS-required index, and shared queryset utilities in one place.

```python
class TenantModel(models.Model):
    organization = models.ForeignKey(
        'quickscale_modules_orgs.Organization',
        on_delete=models.CASCADE,
        db_index=True,
    )

    class Meta:
        abstract = True
```

Modules affected: CRM, blog, forms, listings, storage, notifications. Cross-module migration dependency ordering must be documented in the organizations release note.

---

**Planned follow-on design note**: the remaining sections mix the shipped server-rendered contract with later v0.86.0 follow-on design. Billing bridge, React org-management, and PostgreSQL RLS activation remain planned follow-on work; the invitation flow and org URL notes below call out the current shipped contract where relevant.

---

## Billing Integration

### The Gap

The v0.85.0 billing module binds subscriptions and credit balances to individual users:

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

PostgreSQL RLS activation is still deferred. The org-billing bridge ships first at the ORM/application layer; later DB hardening still depends on downstream tenant tables carrying concrete `organization_id` columns.

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

Seat limits and module gates are advisory in v0.86.0 — enforced in the UI and API, but not at the database layer. Hard enforcement (database constraints on membership count) is deferred.

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
@require_org_feature('crm')
def crm_index(request, org_slug):
    ...
```

This decorator resolves the current organization's active subscription through the billing ORM, selects its `Plan`, and checks `Plan.features` as the sole entitlement source. It returns HTTP 402 when the org has no active subscription or when the feature key is absent.

### Migration Path from v0.85.0

For deployments already using v0.85.0 user-scoped billing, `migrate_billing_to_orgs` ships as the idempotent bridge command. It reuses a sole existing organization when one is already resolvable for the billing user; otherwise it creates a personal org via the standard helper, migrates authoritative `Subscription`, `CreditBalance`, and `CreditTransaction` ownership to that organization, syncs a sole Stripe customer id when safe, and aborts ambiguous cases instead of guessing. Run it once after deploying the organizations module.

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
            if settings.QUICKSCALE_MODE == 'solo':
                Organization.objects.create_personal_for(request.user)
                return '/'
            return '/orgs/new/'
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
- Shipping this slice did not require the deferred Phase 3 PostgreSQL RLS activation work or the later Phase 7 React org-management work.

---

## URL Structure

### SaaS Mode

Path routing (not subdomain). The org slug appears in every URL so the active organization is always explicit, bookmarkable, and shareable.

```
/orgs/                                     # List orgs the current user belongs to
/orgs/new/                                 # Create a new org + Stripe checkout
/orgs/<slug>/                              # Org dashboard
/orgs/<slug>/members/                      # Member list, role management, invite send/revoke
/orgs/invitations/<token>/accept/          # Public invitation accept / continuation
/orgs/<slug>/settings/                     # Org settings (name, slug)
/orgs/<slug>/billing/dashboard/            # Canonical authenticated billing dashboard
/orgs/<slug>/billing/pricing/              # Canonical org-scoped pricing page

# All module routes are nested under the org slug:
/orgs/<slug>/crm/                          # CRM for this org
/orgs/<slug>/blog/                         # Blog for this org
/orgs/<slug>/forms/                        # Forms for this org
/orgs/<slug>/listings/                     # Listings for this org

# API equivalents:
/orgs/<slug>/crm/api/                    # CRM API for this org
/orgs/<slug>/api/billing/...               # Canonical org-scoped billing API surface

Flat authenticated billing routes (`/billing/dashboard/`, `/api/billing/...`) remain compatibility shims for Solo mode and for older non-org callers while SaaS callers move to the canonical org-scoped paths above.
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
/orgs/:slug/members     → OrgMembersPage (member list, role changes, invite send/revoke)
/orgs/:slug/settings    → OrgSettingsPage
/orgs/:slug/billing/dashboard → BillingPage (reuses existing billing components)
/orgs/:slug/crm         → CrmPage (reuses existing CRM components)
/orgs/:slug/blog        → BlogPage
/orgs/:slug/forms       → FormsPage
/orgs/:slug/listings    → ListingsPage
```

`OrgLayout` is a React wrapper that injects `orgSlug` from `useParams()` into all nested pages. An org switcher in the sidebar shows the active organization and lets the user navigate to another by changing the slug in the URL.

#### Solo mode

```
/                       → DashboardPage
/blog                   → BlogPage
/crm                    → CrmPage
/forms                  → FormsPage
/listings               → ListingsPage
/billing/dashboard      → BillingPage
/billing/pricing        → PricingPage
```

No `OrgLayout` or org switcher is rendered.

### Subdomain Routing (Future-Ready)

Subdomain routing (`acme.myapp.com`) is not in v0.86.0 scope, but the architecture is designed to support it with no changes to views or models.

`TenantMiddleware` currently extracts the org slug from the URL. To support subdomains, only the slug-extraction logic changes:

```python
# Current (path-based):
org_slug = match.kwargs.get('org_slug')

# Future (subdomain-based):
host = request.get_host()
org_slug = host.split('.')[0] if host.count('.') >= 2 else None
```

Everything downstream (RLS context, `request.org`, permission checks) is identical. DNS wildcard and NGINX configuration changes are documented in `docs/deployment/railway.md` when the feature is implemented.

---

## TenantMiddleware

```python
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        saas_mode = settings.QUICKSCALE_MODE == 'saas'

        # Guard: authenticated non-staff user with no org membership
        if request.user.is_authenticated and not request.user.is_staff:
            has_membership = OrganizationMembership.objects.filter(user=request.user).exists()
            if not has_membership:
                exempt = request.path.startswith('/accounts') or \
                         request.path.startswith('/orgs/new') or \
                         (request.path.startswith('/orgs/invitations/') and request.path.endswith('/accept/'))
                if saas_mode and not exempt:
                    return redirect('/orgs/new/')
                elif not saas_mode:
                    Organization.objects.create_personal_for(request.user)

        # Extract org and set RLS context
        request.org = None
        org_slug = self._resolve_org_slug(request, saas_mode)

        if org_slug and request.user.is_authenticated:
            org = get_object_or_404(Organization, slug=org_slug)
            if not request.user.is_staff:
                if not OrganizationMembership.objects.filter(user=request.user, organization=org).exists():
                    return HttpResponseForbidden()
            request.org = org
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_org_id = %s", [str(org.id)])

        return self.get_response(request)

    def _resolve_org_slug(self, request, saas_mode):
        if saas_mode:
            try:
                match = resolve(request.path)
                return match.kwargs.get('org_slug')
            except Resolver404:
                return None
        else:
            # Solo mode: resolve from user's personal org
            if request.user.is_authenticated:
                personal = OrganizationMembership.objects.filter(
                    user=request.user, organization__is_personal=True
                ).select_related('organization').first()
                return personal.organization.slug if personal else None
            return None
```

**Connection pooling note**: `SET LOCAL` scopes the value to the current transaction. With PgBouncer in transaction-pooling mode, use `SET` (session-level) instead, combined with connection checkout/return hooks that reset the value. Document the chosen approach in `docs/deployment/railway.md`.

---

## Admin Panel Contract

The current organizations foundation keeps Django `/admin/` as the primary operator surface. The shipped foundation slice also allows Django superusers through org-scoped runtime middleware and role guards without membership, but that remains an application-layer operator path. Today that means admin visibility comes from standard Django ORM/admin behaviour in the app-layer model, not from a special PostgreSQL bypass.

**Future RLS note**: if PostgreSQL RLS is activated later, operator access must be implemented explicitly, for example with dedicated policies or a distinct database role. Do **not** assume Django `is_superuser` or `is_staff` automatically bypasses database policies.

**Operator expectation**: admin list views for org-aware models should expose an `organization` column and an `organization` list filter so the operator can focus on a specific client when needed. Any later RLS rollout must re-verify those admin query paths before claiming all-tenant visibility.

**No tenant should ever have `is_staff=True`.** Organization-scoped administration happens through the org settings pages at `/orgs/<slug>/settings/`, not through Django admin.

---

## Decisions

All open questions from the original design were resolved before implementation began.

| Question | Decision | Rationale |
|----------|----------|-----------|
| Multi-org membership? | **Yes** — user may belong to multiple orgs (SaaS mode) | Supports consultants and agencies working across clients; org switcher in UI handles context |
| `Organization` model location? | **`quickscale_modules_orgs`** | Auth stays minimal and standalone; orgs depends on auth, not the reverse |
| Solo vs SaaS resolution? | **Runtime** — `QUICKSCALE_MODE` setting | Start solo, scale to SaaS without code regeneration; one schema, one codebase |
| Billing migration path? | **Auto-create personal org per user** | Management command `migrate_billing_to_orgs`; idempotent; zero manual operator work |
| Admin panel isolation? | **Operator access is explicit and separate from tenant runtime** | The current slice is app-layer guarded, and any future RLS-era operator access must be designed explicitly rather than inferred from Django flags |
| Active org routing? | **URL-based in SaaS; transparent in Solo** | SaaS: bookmarkable, shareable, no hidden state. Solo: no slug needed, org resolved from user |
| Post-signup flow? | **SaaS: force `/orgs/new/`. Solo: auto-create personal org** | SaaS users must name their workspace; solo users should not see org concepts |
| Module access per plan? | **Feature gates + credits** | Credits for consumption metering; feature gates for upsell leverage; no per-org custom flags |
| Seat pricing? | **Optional, designed in** | Operator-configurable; enforced at UI/API layer in v0.86.0; hard DB enforcement deferred |
| Subdomain routing? | **Future-ready** | Middleware decoupled from slug source; only `_resolve_org_slug` changes |
| Org provisioning? | **Self-service** | Customer signs up, creates org, pays Stripe — no manual platform owner action required |

---

## v0.86.0 Implementation Scope

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
| PostgreSQL RLS migration for downstream tenant tables | ❌ deferred until those tables carry concrete `organization_id` columns |
| PostgreSQL cross-org isolation test suite | ❌ deferred with the RLS migration; requires real PostgreSQL |
| Server-rendered self-service org creation, dashboard, members, settings, and import-compatible org URL surfaces | ✅ implemented |
| Server-rendered invitation flow: invite send/revoke on org admin surfaces, notifications registry-backed email, and slugless public accept continuation under `/orgs` | ✅ implemented |
| Org-authoritative billing bridge (organization ownership fields, canonical org billing routes, flat compatibility shims, and ORM-backed feature gating) | ✅ implemented |
| `migrate_billing_to_orgs` / `promote_to_saas` management commands | ✅ implemented |
| React org-management UI surfaces | ❌ planned follow-on work |
| Subdomain routing | ❌ future-ready (middleware decoupled; DNS/NGINX config deferred) |
| Hard seat-count enforcement at DB layer | ❌ deferred |
| Per-tenant analytics | ❌ deferred |
| Cross-org admin tooling beyond basic `/admin/` | ❌ deferred |

---

## References

- [`docs/legacy/tenancy-isolation-strategies.md`](../legacy/tenancy-isolation-strategies.md) — full RLS code examples, cost matrix, and real-world company comparisons
- [`docs/deployment/railway.md`](../deployment/railway.md) — Railway deployment contract (connection pooling notes, future subdomain config)
- [`docs/technical/decisions.md`](decisions.md) — architecture decision log
- [`quickscale_modules/billing/`](../../quickscale_modules/billing/) — billing models to extend
- [`quickscale_modules/auth/`](../../quickscale_modules/auth/) — User model base
- [`quickscale_modules/orgs/README.md`](../../quickscale_modules/orgs/README.md) — module placeholder
