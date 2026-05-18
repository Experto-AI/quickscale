# QuickScale Teams Module: Design Document

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Teams Design**
> **Related docs**: [Roadmap](roadmap.md) | [Decisions](decisions.md) | [Tenancy Strategies](../legacy/tenancy-isolation-strategies.md) | [Railway Deployment](../deployment/railway.md)

## Purpose and Scope

The teams module enables a QuickScale-generated app to be sold as a SaaS product to multiple paying clients. Each client is a **team** — an isolated workspace with its own data, its own member roster, and its own role-based access control. The operator deploys a single Railway project, clients self-serve signup, subscribe, and invite their colleagues. This is the SaaS-parity milestone that completes the auth → billing → teams foundation started in v0.84.0–v0.85.0.

---

## Ownership Levels

The system has two distinct ownership tiers that must not be confused.

### Level 1: Platform Owner (Django Superuser)

The platform owner is the person or team who deploys and operates the QuickScale SaaS. They:

- Access only `/admin/` — they have no team-scoped dashboard
- Hold `is_superuser=True` and `is_staff=True` in Django
- See **all** tenants' data (PostgreSQL superuser bypasses RLS by design)
- Own the Stripe account that receives subscription payments from customers
- Deploy and upgrade the platform; enable or disable modules globally
- Are the only ones who can create or delete teams via the admin panel in exceptional cases

The platform owner is **not** a team member in the RBAC sense and does not appear in any `TeamMembership` record.

### Level 2: Team Hierarchy (Customer Users)

Each customer workspace (team) has its own internal hierarchy. All team users are isolated from other teams by PostgreSQL RLS.

```
Platform Owner (Django superuser)
└── /admin/ — sees all tenants, bypasses RLS
              ↓ operates
    QuickScale SaaS Platform
    (1 Railway: 1 app service + 1 PostgreSQL 18 service)
              ↓
    ┌─────────────────────┐   ┌─────────────────────┐
    │  Team: Acme Corp    │   │  Team: Widget Co     │  …N tenants
    │  slug: acme-corp    │   │  slug: widget-co     │
    │  stripe_customer_id │   │  stripe_customer_id  │
    └────────┬────────────┘   └──────────┬───────────┘
             │                           │
    alice@acme.com  OWNER       (same internal structure)
    bob@acme.com    ADMIN
    carol@acme.com  MEMBER
    dave@acme.com   VIEWER

PostgreSQL RLS:
  Acme Corp users  → only see rows WHERE team_id = 'acme-uuid'
  Widget Co users  → only see rows WHERE team_id = 'widget-uuid'
  Platform owner   → bypasses RLS, sees everything
```

### Capability Matrix

| Capability | Platform Owner | Team Owner | Team Admin | Team Member | Team Viewer |
|---|---|---|---|---|---|
| Access `/admin/` | ✅ | ❌ | ❌ | ❌ | ❌ |
| See all tenants' data | ✅ | ❌ | ❌ | ❌ | ❌ |
| Create / delete a team | ✅ (via admin) | ✅ (own team) | ❌ | ❌ | ❌ |
| Manage team billing | ✅ (via admin) | ✅ (own team) | ❌ | ❌ | ❌ |
| Invite team members | ✅ (via admin) | ✅ | ✅ | ❌ | ❌ |
| Remove team members | ✅ (via admin) | ✅ | ✅ | ❌ | ❌ |
| Change team settings | ✅ (via admin) | ✅ | ✅ | ❌ | ❌ |
| Transfer ownership | ✅ (via admin) | ✅ | ❌ | ❌ | ❌ |
| Use CRM / CMS / etc. | ✅ | ✅ | ✅ | ✅ | read-only |

---

## Terminology

| Term | Definition |
|------|-----------|
| **Platform Owner** | The operator who deploys and runs the SaaS. Has Django `is_superuser`. Not a team member. |
| **Team** | The paying client unit. Equivalent to "organization", "workspace", or "tenant". |
| **Member** | An individual user who belongs to one or more teams. |
| **Role** | The member's permission level within a specific team. |
| **Team Owner** | The member who created the team; the Stripe billing contact. |
| **Invitation** | A pending email-based request to join a team before the recipient has a user account. |

A user account is global (one email, one login). A user's role is team-scoped — the same person can be an Owner in one team and a Member in another. A user may belong to multiple teams simultaneously; a team switcher in the UI tracks the active context.

---

## Tenancy Strategy: Shared Deployment + PostgreSQL RLS

### Architecture

One Railway project: one application service and one PostgreSQL 18 service. All teams share the same database and the same schema. Every tenant-scoped table carries a `team` foreign key. PostgreSQL Row-Level Security (RLS) policies enforce that each database connection can only read and write rows belonging to the current team, as set by middleware at request time.

```
Railway project
├── app service (Django + Gunicorn)
│   └── TenantMiddleware → SET app.current_team_id per request (extracted from URL)
└── postgres service (PostgreSQL 18)
    └── RLS policies on every tenant table
        USING (team_id = current_setting('app.current_team_id', true)::uuid)
```

The `true` second argument to `current_setting` returns `NULL` instead of raising an error when the setting is absent. This means an unguarded query returns an empty set rather than raising an exception — fail-safe, but requires the middleware to always set the context for tenant routes.

### Why This Architecture

- **Cost**: 2 Railway services regardless of how many tenants exist. Railway bills by compute and memory, not by tenant count. At 100 tenants or 10 000, the bill changes only with actual usage.
- **Defence-in-depth**: RLS is enforced by the database engine, not by application code. A view that accidentally omits `.filter(team=...)` returns an empty set instead of leaking another tenant's data.
- **Operational simplicity**: One backup covers all tenants. One migration covers all tenants. One deploy upgrades all tenants simultaneously.
- **Proven pattern**: Supabase, Stripe, and Slack all use shared-database isolation at scale. Detailed code examples are in [`docs/legacy/tenancy-isolation-strategies.md`](../legacy/tenancy-isolation-strategies.md) — that document is the reference implementation; this document does not duplicate it.

### Known Constraints

- **Admin bypass (intentional)**: PostgreSQL superuser connections bypass RLS. The platform owner's `/admin/` session sees all tenants' data by design — this is the intended operator view, not a bug. See [Decisions → Admin Panel Contract](#decisions).
- **Noisy neighbour**: One tenant running expensive queries slows response times for others. Acceptable at MVP scale; address with `statement_timeout` and rate limiting later.
- **Debugging**: RLS policy failures are silent (rows vanish; no exception is raised). Debugging requires checking `pg_policies` and PostgreSQL logs, not just Django stack traces.
- **Migrations**: Migrations that add columns or change constraints on tenant tables run against all tenants at once. This is a feature (one migration), but large-table migrations need `CONCURRENTLY` indexes and zero-downtime patterns.
- **`SET LOCAL` vs `SET`**: `SET LOCAL` scopes the team context to the current transaction. `SET` (session-level) is needed for PgBouncer compatibility. Choose based on connection pooling setup; document this in the deployment guide.

---

## RBAC Design

### Role Hierarchy

Four roles in ascending permission order:

| Role | Can do |
|------|--------|
| `VIEWER` | Read team resources; cannot modify anything |
| `MEMBER` | Full read/write access to team resources |
| `ADMIN` | Member permissions + invite/remove members, manage team settings |
| `OWNER` | Admin permissions + delete team, transfer ownership, manage billing |

A team has exactly one Owner at any time. Ownership can be transferred. A team must always have an Owner — the last Owner cannot be demoted or removed.

### Why Not Django Groups

Django's permission groups are global — a user in the "Admin" group is an admin everywhere in the system. Team roles are team-scoped: the same user can be an Owner in one team and a Viewer in another. A `TeamMembership` model with a `role` field is the correct primitive, not Django groups.

Django's `is_staff` and `is_superuser` flags continue to control access to the Django admin panel. They have no relationship to team roles.

### Permission Checking Pattern

Views check team membership and minimum role via a decorator or mixin:

```python
# Conceptual — not final implementation
@require_team_role(min_role=TeamRole.ADMIN)
def team_settings(request, team_slug):
    ...
```

The decorator resolves the current team from the URL (`team_slug`), looks up the `TeamMembership` for `request.user`, and returns HTTP 403 if the user is not a member or their role is below the minimum. The team is also stored on `request.team` for downstream use.

```python
ROLE_HIERARCHY = {
    TeamRole.VIEWER: 0,
    TeamRole.MEMBER: 1,
    TeamRole.ADMIN:  2,
    TeamRole.OWNER:  3,
}
```

---

## Data Model

### Core Models

```
Team
  id            UUID (PK, default uuid4)
  name          CharField(max_length=100)
  slug          SlugField(unique=True)        # URL identifier, e.g. "acme-corp"
  stripe_customer_id  CharField(blank=True)   # Stripe customer tied to the team
  created_at    DateTimeField(auto_now_add)

TeamMembership
  id            BigAutoField (PK)
  user          FK → User (on_delete=CASCADE)
  team          FK → Team (on_delete=CASCADE)
  role          CharField(choices=OWNER|ADMIN|MEMBER|VIEWER)
  invited_by    FK → User (nullable, on_delete=SET_NULL)
  joined_at     DateTimeField(auto_now_add)

  class Meta:
      unique_together = [('user', 'team')]
      # A user may belong to multiple teams. unique_together is (user, team),
      # NOT just (user). A team switcher in the UI tracks the active context.

TeamInvitation
  id            UUID (PK)
  team          FK → Team (on_delete=CASCADE)
  email         EmailField
  role          CharField(choices=ADMIN|MEMBER|VIEWER, default=MEMBER)
  invited_by    FK → User (on_delete=CASCADE)
  token         UUIDField(unique=True, default=uuid4)
  expires_at    DateTimeField
  accepted_at   DateTimeField(nullable)

  # A pending invitation is: accepted_at is None AND expires_at > now
```

### TenantModel Abstract Base

The teams module ships a `TenantModel` abstract base class. Any module that stores tenant-scoped data inherits from it to get the `team` FK, the RLS-required index, and shared queryset utilities in one place.

```python
class TenantModel(models.Model):
    team = models.ForeignKey(
        'quickscale_modules_teams.Team',
        on_delete=models.CASCADE,
        db_index=True,
    )

    class Meta:
        abstract = True
```

Modules affected: CRM, blog, forms, listings, storage, notifications. Cross-module migration dependency ordering must be documented in the teams release note.

---

## Billing Integration

### The Gap

The v0.85.0 billing module binds subscriptions and credit balances to individual users:

```
Subscription.user  → FK → User
CreditBalance.user → FK → User (OneToOne)
```

This is wrong for a team SaaS. Clients pay for their team; individual members consume credits on behalf of the team. The billing contact is the Team Owner, not an arbitrary user account.

### Resolution

Add team-scoped fields to billing models:

```
Subscription.team  → FK → Team (nullable; required after migration)
CreditBalance.team → OneToOneField → Team (replaces per-user balance)
CreditTransaction.performed_by → FK → User (who acted within the team)
```

`Team.stripe_customer_id` is the Stripe customer identifier. The Team Owner's email is the Stripe billing email. When the Owner transfers ownership, the Stripe customer record stays with the team (not the departing user).

Credit transactions (`CreditTransaction`) are attributed to the acting user (`performed_by`) but deducted from the team's balance.

### Migration Path from v0.85.0

For deployments already using v0.85.0 user-scoped billing: a management command `migrate_billing_to_teams` auto-creates a personal team (name: `"{username}'s Team"`, slug: `"{username}"`) for each existing user and migrates their `Subscription` and `CreditBalance` to that team. The command is idempotent and must be run once after deploying the teams module.

### Module Access

All modules (CRM, blog, forms, listings, etc.) are available to all teams equally. Plans differentiate by credit volume, not by feature gating. This keeps the billing model simple and avoids per-team feature flags in every module view.

| Plan tier | Monthly credits | All modules |
|-----------|----------------|-------------|
| Starter   | 500            | ✅ |
| Growth    | 2 000          | ✅ |
| Pro       | Unlimited      | ✅ |

### Seat Pricing (Deferred)

Per-seat billing (charging per `TeamMembership` count) is not in v0.86.0 scope.

---

## Customer Onboarding Flow

Customers self-provision without platform owner intervention:

```
1. /accounts/signup/      → customer creates a global user account (django-allauth)
2. Redirect → /teams/new/ → customer creates their team (name, slug)
3. Stripe checkout        → customer subscribes to a plan
4. Redirect → /teams/<slug>/  → team dashboard, ready to use
```

**Post-signup guard**: Authenticated users with no `TeamMembership` are redirected to `/teams/new/` by `TenantMiddleware` for every request except `/accounts/*` and `/teams/new/` itself. This is enforced via a django-allauth adapter override:

```python
class TeamsAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        if not TeamMembership.objects.filter(user=request.user).exists():
            return '/teams/new/'
        return super().get_login_redirect_url(request)
```

Wired via `ACCOUNT_ADAPTER = 'quickscale_modules_teams.adapters.TeamsAccountAdapter'` in module settings.

---

## Invitation Flow

1. An Admin or Owner submits an invite form with an email address and role.
2. The system creates a `TeamInvitation` record with a UUID token and a 7-day expiry.
3. The notifications module sends the invite email: `teams/email/invite.html` with the accept URL.
4. Accept URL: `GET /teams/<team_slug>/invite/<token>/accept/`
   - If the email has an existing account: log in (or confirm login) and create `TeamMembership`.
   - If the email is new: redirect to signup, then complete membership creation on account creation.
5. Expired or already-accepted tokens return HTTP 410 with a user-facing message.
6. Revoking an invitation deletes the `TeamInvitation` row; the token URL becomes 404.

---

## URL Structure

Path routing (not subdomain). The team slug appears in every URL so the active team is always explicit, bookmarkable, and shareable.

```
/teams/                                    # List teams the current user belongs to
/teams/new/                                # Create a new team + Stripe checkout
/teams/<slug>/                             # Team dashboard
/teams/<slug>/members/                     # Member list and role management
/teams/<slug>/invite/                      # Send invitations
/teams/<slug>/invite/<token>/accept/       # Accept an invitation
/teams/<slug>/settings/                    # Team settings (name, slug)
/teams/<slug>/billing/                     # Team billing (delegates to billing module)

# All module routes are nested under the team slug:
/teams/<slug>/crm/                         # CRM for this team
/teams/<slug>/blog/                        # Blog for this team
/teams/<slug>/forms/                       # Forms for this team
/teams/<slug>/listings/                    # Listings for this team

# API equivalents:
/api/teams/<slug>/crm/                     # CRM API for this team
/api/billing/...                           # Billing API (team resolved from session/auth)
```

The module wiring layer nests all `MODULE_URLPATTERNS` under `teams/<slug>/` when the teams module is active. The `TenantMiddleware` extracts the slug from the URL and sets `app.current_team_id` before any view runs.

**React frontend routes** mirror the Django URL structure:

```
/teams                   → TeamListPage
/teams/new               → TeamCreatePage
/teams/:slug             → TeamDashboardPage  (rendered inside TeamLayout)
/teams/:slug/members     → TeamMembersPage
/teams/:slug/invite      → TeamInvitePage
/teams/:slug/settings    → TeamSettingsPage
/teams/:slug/billing     → BillingPage (reuses existing billing components)
/teams/:slug/crm         → CrmPage (reuses existing CRM components)
/teams/:slug/blog        → BlogPage
/teams/:slug/forms       → FormsPage
/teams/:slug/listings    → ListingsPage
```

`TeamLayout` is a React wrapper that injects `teamSlug` from `useParams()` into all nested pages. A team switcher in the sidebar shows the active team and lets the user navigate to another by changing the slug in the URL.

Subdomain routing (`acme.myapp.com`) is not in v0.86.0 scope.

---

## TenantMiddleware

```python
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Guard: authenticated non-staff user with no team → /teams/new/
        if request.user.is_authenticated and not request.user.is_staff:
            exempt = request.path.startswith('/accounts') or \
                     request.path.startswith('/teams/new')
            if not exempt and not TeamMembership.objects.filter(user=request.user).exists():
                return redirect('/teams/new/')

        # Extract team from URL and set RLS context
        try:
            match = resolve(request.path)
            team_slug = match.kwargs.get('team_slug')
        except Resolver404:
            team_slug = None

        request.team = None
        if team_slug and request.user.is_authenticated:
            team = get_object_or_404(Team, slug=team_slug)
            if not request.user.is_staff:
                if not TeamMembership.objects.filter(user=request.user, team=team).exists():
                    return HttpResponseForbidden()
            request.team = team
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_team_id = %s", [str(team.id)])

        return self.get_response(request)
```

**Connection pooling note**: `SET LOCAL` scopes the value to the current transaction. With PgBouncer in transaction-pooling mode, use `SET` (session-level) instead, combined with connection checkout/return hooks that reset the value. Document the chosen approach in `docs/deployment/railway.md`.

---

## Admin Panel Contract

The platform owner's Django `/admin/` session connects as a PostgreSQL superuser. PostgreSQL superusers bypass RLS by default — no `SET ROLE` or policy exception is needed.

**Intended behaviour**: The platform owner sees all tenants' data in all list views. This is correct — `/admin/` is an operator tool, not a tenant-facing interface. All admin list views for tenant models (CRM contacts, blog posts, etc.) expose a `team` column and a `team` list filter so the operator can focus on a specific client when needed.

**No tenant should ever have `is_staff=True`.** Team-scoped administration happens through the team settings pages at `/teams/<slug>/settings/`, not through Django admin.

---

## Decisions

All open questions from the original design were resolved before implementation began.

| Question | Decision | Rationale |
|----------|----------|-----------|
| Multi-team membership? | **Yes** — user may belong to multiple teams | Supports consultants and agencies working across clients; team switcher in UI handles context |
| `Team` model location? | **`quickscale_modules_teams`** | Auth stays minimal and standalone; teams depends on auth, not the reverse |
| Billing migration path? | **Auto-create personal team per user** | Management command `migrate_billing_to_teams`; idempotent; zero manual operator work |
| Admin panel isolation? | **Platform owner sees all** | Superuser bypasses RLS by design; `/admin/` is the operator control plane, not a tenant interface |
| Active team routing? | **URL-based** — slug in every URL | Bookmarkable, shareable, no hidden session state; `/teams/<slug>/crm/` is always unambiguous |
| Post-signup flow? | **Force `/teams/new/`** | Users cannot access the app without a team; allauth adapter redirects; middleware guards all routes |
| Module access per plan? | **All modules for all teams** | Differentiate by credit volume only; no per-team feature flags |
| Team provisioning? | **Self-service** | Customer signs up, creates team, pays Stripe — no manual platform owner action required |

---

## v0.86.0 Implementation Scope

| Deliverable | Included |
|-------------|---------|
| `Team`, `TeamMembership`, `TeamInvitation` models | ✅ |
| `TenantModel` abstract base class with `team` FK | ✅ |
| PostgreSQL RLS migration for all tenant tables | ✅ |
| `TenantMiddleware` (sets `app.current_team_id` from URL slug) | ✅ |
| `require_team_role` decorator + `TeamRoleMixin` | ✅ |
| Post-signup redirect via allauth adapter | ✅ |
| Self-service team creation flow + Stripe checkout | ✅ |
| Invitation flow via notifications module | ✅ |
| Billing bridge: `Subscription.team`, `CreditBalance.team`, `CreditTransaction.performed_by` | ✅ |
| Management command: `migrate_billing_to_teams` | ✅ |
| Django admin: Team, TeamMembership, TeamInvitation registration | ✅ |
| React: team list, create, dashboard, members, invite, settings pages | ✅ |
| React: `TeamLayout` + team switcher in sidebar | ✅ |
| React: module routes moved under `/teams/:slug/` | ✅ |
| HTML theme: team management pages | ✅ |
| Unit + integration tests for isolation and permissions | ✅ |
| Subdomain routing | ❌ deferred |
| Seat-based pricing | ❌ deferred |
| Per-tenant analytics | ❌ deferred |
| Module-level feature gating per plan | ❌ deferred |
| Cross-team admin tooling beyond basic `/admin/` | ❌ deferred |

---

## References

- [`docs/legacy/tenancy-isolation-strategies.md`](../legacy/tenancy-isolation-strategies.md) — full RLS code examples, cost matrix, and real-world company comparisons
- [`docs/deployment/railway.md`](../deployment/railway.md) — Railway deployment contract (connection pooling notes)
- [`docs/technical/decisions.md`](decisions.md) — architecture decision log
- [`quickscale_modules/billing/`](../../quickscale_modules/billing/) — billing models to extend
- [`quickscale_modules/auth/`](../../quickscale_modules/auth/) — User model base
- [`quickscale_modules/teams/README.md`](../../quickscale_modules/teams/README.md) — module placeholder
