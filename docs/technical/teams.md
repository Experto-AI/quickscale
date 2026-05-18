# QuickScale Organizations Module: Design Document

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Organizations Design**
> **Related docs**: [Roadmap](roadmap.md) | [Decisions](decisions.md) | [Tenancy Strategies](../legacy/tenancy-isolation-strategies.md) | [Railway Deployment](../deployment/railway.md)

## Purpose and Scope

The organizations module enables a QuickScale-generated app to be sold as a SaaS product to multiple paying clients. Each client is an **organization** — an isolated workspace with its own data, its own member roster, and its own role-based access control. The operator deploys a single Railway project, clients self-serve signup, subscribe, and invite their colleagues. This is the SaaS-parity milestone that completes the auth → billing → organizations foundation started in v0.84.0–v0.85.0.

QuickScale supports two deployment modes — **Solo** and **SaaS** — resolved at runtime via a single settings flag. Both modes use the same schema and codebase. Solo mode is a constrained configuration of the organization system, not a separate architecture.

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
| RLS | Active (one org per user, still enforced) | Active (N orgs, strict isolation) |

### Why Runtime Instead of Generation Time

The natural comparison is SaaS Pegasus, which resolves solo vs SaaS at **generation time** — it generates different code depending on your choice, producing a clean output with no dead code. QuickScale could do the same.

However, runtime resolution is preferable for QuickScale because:

1. **Start solo, scale to SaaS**: The most common trajectory is a developer who starts with a personal tool, gains traction, and wants to offer it as a multi-tenant SaaS. With generation-time resolution, that requires regenerating the project and migrating data. With runtime resolution, it is a one-line settings change plus a management command.
2. **One schema, one codebase**: The `organization` FK is always present on tenant tables. There is no conditional base class, no dual migration path, no variant to maintain.
3. **Solo mode is a subset of SaaS mode**: Solo mode disables multi-org management — it does not require a different data model. An organization still exists; it just has one member and is never surfaced as a concept in the UI.

**The one tradeoff**: Solo mode carries the same schema overhead as SaaS mode (org FK on every tenant table, RLS policies active). For a personal blog this is invisible. If zero overhead is a hard requirement, generation-time resolution (as Pegasus does) remains a valid alternative.

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

`promote_to_saas` assigns a slug to each personal organization (derived from the owner's username), enables invitations, and migrates billing to org-scoped records. The command is idempotent.

---

## Ownership Levels

The system has two distinct ownership tiers that must not be confused.

### Level 1: Platform Owner (Django Superuser)

The platform owner is the person or team who deploys and operates the QuickScale SaaS. They:

- Access only `/admin/` — they have no organization-scoped dashboard
- Hold `is_superuser=True` and `is_staff=True` in Django
- See **all** tenants' data (PostgreSQL superuser bypasses RLS by design)
- Own the Stripe account that receives subscription payments from customers
- Deploy and upgrade the platform; enable or disable modules globally
- Are the only ones who can create or delete organizations via the admin panel in exceptional cases

The platform owner is **not** an organization member in the RBAC sense and does not appear in any `OrganizationMembership` record.

### Level 2: Organization Hierarchy (Customer Users)

Each customer workspace (organization) has its own internal hierarchy. All organization users are isolated from other organizations by PostgreSQL RLS.

```
Platform Owner (Django superuser)
└── /admin/ — sees all tenants, bypasses RLS
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

PostgreSQL RLS:
  Acme Corp users  → only see rows WHERE org_id = 'acme-uuid'
  Widget Co users  → only see rows WHERE org_id = 'widget-uuid'
  Platform owner   → bypasses RLS, sees everything
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

## Tenancy Strategy: Shared Deployment + PostgreSQL RLS

### Architecture

One Railway project: one application service and one PostgreSQL 18 service. All organizations share the same database and the same schema. Every tenant-scoped table carries an `organization` foreign key. PostgreSQL Row-Level Security (RLS) policies enforce that each database connection can only read and write rows belonging to the current organization, as set by middleware at request time.

```
Railway project
├── app service (Django + Gunicorn)
│   └── TenantMiddleware → SET app.current_org_id per request (extracted from URL or user)
└── postgres service (PostgreSQL 18)
    └── RLS policies on every tenant table
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
```

The `true` second argument to `current_setting` returns `NULL` instead of raising an error when the setting is absent. This means an unguarded query returns an empty set rather than raising an exception — fail-safe, but requires the middleware to always set the context for tenant routes.

### Why This Architecture

- **Cost**: 2 Railway services regardless of how many tenants exist. Railway bills by compute and memory, not by tenant count. At 100 tenants or 10 000, the bill changes only with actual usage.
- **Defence-in-depth**: RLS is enforced by the database engine, not by application code. A view that accidentally omits `.filter(organization=...)` returns an empty set instead of leaking another tenant's data.
- **Operational simplicity**: One backup covers all tenants. One migration covers all tenants. One deploy upgrades all tenants simultaneously.
- **Proven pattern**: Supabase, Stripe, and Slack all use shared-database isolation at scale. Detailed code examples are in [`docs/legacy/tenancy-isolation-strategies.md`](../legacy/tenancy-isolation-strategies.md) — that document is the reference implementation; this document does not duplicate it.

### Known Constraints

- **Admin bypass (intentional)**: PostgreSQL superuser connections bypass RLS. The platform owner's `/admin/` session sees all tenants' data by design — this is the intended operator view, not a bug. See [Decisions → Admin Panel Contract](#decisions).
- **Noisy neighbour**: One tenant running expensive queries slows response times for others. Acceptable at MVP scale; address with `statement_timeout` and rate limiting later.
- **Debugging**: RLS policy failures are silent (rows vanish; no exception is raised). Debugging requires checking `pg_policies` and PostgreSQL logs, not just Django stack traces.
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

## Billing Integration

### The Gap

The v0.85.0 billing module binds subscriptions and credit balances to individual users:

```
Subscription.user  → FK → User
CreditBalance.user → FK → User (OneToOne)
```

This is wrong for a team SaaS. Clients pay for their organization; individual members consume credits on behalf of the organization. The billing contact is the Org Owner, not an arbitrary user account.

### Resolution

Add org-scoped fields to billing models:

```
Subscription.organization  → FK → Organization (nullable; required after migration)
CreditBalance.organization → OneToOneField → Organization (replaces per-user balance)
CreditTransaction.performed_by → FK → User (who acted within the org)
```

`Organization.stripe_customer_id` is the Stripe customer identifier. The Org Owner's email is the Stripe billing email. When the Owner transfers ownership, the Stripe customer record stays with the organization (not the departing user).

Credit transactions (`CreditTransaction`) are attributed to the acting user (`performed_by`) but deducted from the organization's balance.

### Hybrid Billing Model: Credits + Feature Gates + Optional Seats

QuickScale combines the credit-pool model (QuickScale's core mechanic) with plan-level feature gating and optional seat pricing (both proven by SaaS Pegasus). These are complementary, not alternatives.

**Credits** measure consumption — AI operations, API calls, or any metered action. Every plan includes a monthly credit allocation. Credits do not expire within the billing period and roll over at the operator's discretion.

**Feature gates** control which modules are available at each plan tier. This gives operators a tool to upsell without requiring a custom per-org flag system.

**Seat pricing** (optional) charges per `OrganizationMembership` count. It is additive on top of the base plan price. Operators may enable it via a settings flag; it is not required.

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

This decorator checks `request.org.subscription.plan.features` and returns HTTP 402 with an upgrade prompt if the feature is not in the plan.

### Migration Path from v0.85.0

For deployments already using v0.85.0 user-scoped billing: a management command `migrate_billing_to_orgs` auto-creates a personal organization (name: `"{username}'s Org"`, slug: `"{username}"`, `is_personal=True`) for each existing user and migrates their `Subscription` and `CreditBalance` to that organization. The command is idempotent and must be run once after deploying the organizations module.

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

**Post-signup guard**: Authenticated users with no `OrganizationMembership` are redirected to `/orgs/new/` by `TenantMiddleware` for every request except `/accounts/*` and `/orgs/new/` itself.

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

Invitations are only active in SaaS mode. In Solo mode the invitation views return HTTP 404.

1. An Admin or Owner submits an invite form with an email address and role.
2. The system creates an `OrganizationInvitation` record with a UUID token and a 7-day expiry.
3. The notifications module sends the invite email: `orgs/email/invite.html` with the accept URL.
4. Accept URL: `GET /orgs/<org_slug>/invite/<token>/accept/`
   - If the email has an existing account: log in (or confirm login) and create `OrganizationMembership`.
   - If the email is new: redirect to signup, then complete membership creation on account creation.
5. Expired or already-accepted tokens return HTTP 410 with a user-facing message.
6. Revoking an invitation deletes the `OrganizationInvitation` row; the token URL becomes 404.

---

## URL Structure

### SaaS Mode

Path routing (not subdomain). The org slug appears in every URL so the active organization is always explicit, bookmarkable, and shareable.

```
/orgs/                                     # List orgs the current user belongs to
/orgs/new/                                 # Create a new org + Stripe checkout
/orgs/<slug>/                              # Org dashboard
/orgs/<slug>/members/                      # Member list and role management
/orgs/<slug>/invite/                       # Send invitations
/orgs/<slug>/invite/<token>/accept/        # Accept an invitation
/orgs/<slug>/settings/                     # Org settings (name, slug)
/orgs/<slug>/billing/                      # Org billing (delegates to billing module)

# All module routes are nested under the org slug:
/orgs/<slug>/crm/                          # CRM for this org
/orgs/<slug>/blog/                         # Blog for this org
/orgs/<slug>/forms/                        # Forms for this org
/orgs/<slug>/listings/                     # Listings for this org

# API equivalents:
/api/orgs/<slug>/crm/                      # CRM API for this org
/api/billing/...                           # Billing API (org resolved from session/auth)
```

### Solo Mode

```
/                      # Dashboard (org resolved silently from user's personal org)
/blog/                 # Blog
/crm/                  # CRM
/forms/                # Forms
/listings/             # Listings
/billing/              # Billing
/account/settings/     # User settings
```

No org management pages are exposed in solo mode.

### React Frontend Routes

#### SaaS mode

```
/orgs                   → OrgListPage
/orgs/new               → OrgCreatePage
/orgs/:slug             → OrgDashboardPage  (rendered inside OrgLayout)
/orgs/:slug/members     → OrgMembersPage
/orgs/:slug/invite      → OrgInvitePage
/orgs/:slug/settings    → OrgSettingsPage
/orgs/:slug/billing     → BillingPage (reuses existing billing components)
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
/billing                → BillingPage
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
                         request.path.startswith('/orgs/new')
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

The platform owner's Django `/admin/` session connects as a PostgreSQL superuser. PostgreSQL superusers bypass RLS by default — no `SET ROLE` or policy exception is needed.

**Intended behaviour**: The platform owner sees all tenants' data in all list views. This is correct — `/admin/` is an operator tool, not a tenant-facing interface. All admin list views for tenant models (CRM contacts, blog posts, etc.) expose an `organization` column and an `organization` list filter so the operator can focus on a specific client when needed.

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
| Admin panel isolation? | **Platform owner sees all** | Superuser bypasses RLS by design; `/admin/` is the operator control plane, not a tenant interface |
| Active org routing? | **URL-based in SaaS; transparent in Solo** | SaaS: bookmarkable, shareable, no hidden state. Solo: no slug needed, org resolved from user |
| Post-signup flow? | **SaaS: force `/orgs/new/`. Solo: auto-create personal org** | SaaS users must name their workspace; solo users should not see org concepts |
| Module access per plan? | **Feature gates + credits** | Credits for consumption metering; feature gates for upsell leverage; no per-org custom flags |
| Seat pricing? | **Optional, designed in** | Operator-configurable; enforced at UI/API layer in v0.86.0; hard DB enforcement deferred |
| Subdomain routing? | **Future-ready** | Middleware decoupled from slug source; only `_resolve_org_slug` changes |
| Org provisioning? | **Self-service** | Customer signs up, creates org, pays Stripe — no manual platform owner action required |

---

## v0.86.0 Implementation Scope

| Deliverable | Included |
|-------------|---------|
| `Organization`, `OrganizationMembership`, `OrganizationInvitation` models | ✅ |
| `TenantModel` abstract base class with `organization` FK | ✅ |
| PostgreSQL RLS migration for all tenant tables | ✅ |
| `TenantMiddleware` (sets `app.current_org_id`; Solo and SaaS branches) | ✅ |
| `require_org_role` decorator + `OrgRoleMixin` | ✅ |
| `require_org_feature` decorator (plan feature gate checks) | ✅ |
| `QUICKSCALE_MODE` setting with Solo / SaaS behaviour | ✅ |
| Post-signup: auto-create personal org (Solo) or redirect to `/orgs/new/` (SaaS) | ✅ |
| Self-service org creation flow + Stripe checkout | ✅ |
| Invitation flow via notifications module (SaaS only) | ✅ |
| Billing bridge: `Subscription.organization`, `CreditBalance.organization`, `CreditTransaction.performed_by` | ✅ |
| `Plan.features` (JSONField for feature gates) + `Plan.max_seats` | ✅ |
| Management command: `migrate_billing_to_orgs` | ✅ |
| Management command: `promote_to_saas` (Solo → SaaS upgrade) | ✅ |
| Django admin: Organization, OrganizationMembership, OrganizationInvitation registration | ✅ |
| React: org list, create, dashboard, members, invite, settings pages (SaaS mode) | ✅ |
| React: `OrgLayout` + org switcher in sidebar (SaaS mode) | ✅ |
| React: module routes under `/orgs/:slug/` (SaaS) or flat (Solo) | ✅ |
| HTML theme: org management pages | ✅ |
| Unit + integration tests for isolation and permissions | ✅ |
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
