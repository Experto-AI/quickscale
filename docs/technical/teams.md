# QuickScale Teams Module: Design Document

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Teams Design**
> **Related docs**: [Roadmap](roadmap.md) | [Decisions](decisions.md) | [Tenancy Strategies](../legacy/tenancy-isolation-strategies.md) | [Railway Deployment](../deployment/railway.md)

## Purpose and Scope

The teams module enables a QuickScale-generated app to be sold as a SaaS product to multiple paying clients. Each client is a **team** — an isolated workspace with its own data, its own member roster, and its own role-based access control. The operator deploys a single Railway project, clients self-serve signup, subscribe, and invite their colleagues. This is the SaaS-parity milestone that completes the auth → billing → teams foundation started in v0.84.0–v0.85.0.

---

## Terminology

| Term | Definition |
|------|-----------|
| **Team** | The paying client unit. Equivalent to "organization", "workspace", or "tenant". |
| **Member** | An individual user who belongs to one or more teams. |
| **Role** | The member's permission level within a specific team. |
| **Team Owner** | The member who created the team; the Stripe billing contact. |
| **Invitation** | A pending email-based request to join a team before the recipient has a user account. |

A user account is global (one email, one login). A user's role is team-scoped — the same person can be an Owner in one team and a Member in another.

---

## Tenancy Strategy: Shared Deployment + PostgreSQL RLS

### Architecture

One Railway project: one application service and one PostgreSQL 18 service. All teams share the same database and the same schema. Every tenant-scoped table carries a `team` foreign key. PostgreSQL Row-Level Security (RLS) policies enforce that each database connection can only read and write rows belonging to the current team, as set by middleware at request time.

```
Railway project
├── app service (Django + Gunicorn)
│   └── TenantMiddleware → SET app.current_team_id per request
└── postgres service (PostgreSQL 18)
    └── RLS policies on every tenant table
        USING (team_id = current_setting('app.current_team_id')::uuid)
```

### Why This Architecture

- **Cost**: 2 Railway services regardless of how many tenants exist. Railway bills by compute and memory, not by tenant count. At 100 tenants or 10 000, the bill changes only with actual usage.
- **Defence-in-depth**: RLS is enforced by the database engine, not by application code. A view that accidentally omits `.filter(team=...)` returns an empty set instead of leaking another tenant's data.
- **Operational simplicity**: One backup covers all tenants. One migration covers all tenants. One deploy upgrades all tenants simultaneously.
- **Proven pattern**: Supabase, Stripe, and Slack all use shared-database isolation at scale. Detailed code examples are in [`docs/legacy/tenancy-isolation-strategies.md`](../legacy/tenancy-isolation-strategies.md) — that document is the reference implementation; this document does not duplicate it.

### Known Constraints

- **Admin bypass**: PostgreSQL superuser connections and Django's `is_staff` admin bypass RLS. The Django admin panel must either use a restricted database role (`SET ROLE tenant_app_user`) or apply explicit `.filter(team=...)` on all admin querysets. This is non-negotiable — failure to address it creates a full data leak in the admin panel.
- **Noisy neighbour**: One tenant running expensive queries slows response times for others. Acceptable at MVP scale; address with query timeouts (`statement_timeout`) and rate limiting if needed later.
- **Debugging**: RLS policy failures are silent (rows vanish; no exception is raised). Debugging requires checking `pg_policies` and PostgreSQL logs, not just Django stack traces.
- **Migrations**: Migrations that add columns or change constraints on tenant tables run against all tenants at once. This is a feature (one migration), but large-table migrations need `CONCURRENTLY` indexes and zero-downtime patterns.

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

---

## Data Model

### Core Models

```
Team
  id            UUID (PK, default uuid4)
  name          CharField(max_length=100)
  slug          SlugField(unique=True)        # URL identifier, e.g. "acme-corp"
  stripe_customer_id  CharField(nullable)     # Stripe customer tied to the team
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

### Tenant FK on Existing Models

Every model that holds tenant-scoped data gains a `team` foreign key:

```python
# Added to CRM, blog, forms, listings, storage, notifications, etc.
team = models.ForeignKey(
    'quickscale_modules_teams.Team',
    on_delete=models.CASCADE,
    db_index=True,
)
```

The teams module ships a `TenantModel` abstract base class that modules can inherit to get this field, the RLS index, and any shared queryset utilities in one place. Cross-module migration dependency ordering must be documented in the teams release note.

---

## Billing Integration

### The Gap

The v0.85.0 billing module binds subscriptions and credit balances to individual users:

```
Subscription.user  → FK → User
CreditBalance.user → FK → User (OneToOne)
```

This is wrong for a team SaaS. Clients pay for their team; individual members consume credits on behalf of the team. The billing contact is the team Owner, not an arbitrary user account.

### Resolution

Add team-scoped fields to billing models:

```
Subscription.team  → FK → Team (replaces .user for team billing context)
CreditBalance.team → FK → Team (OneToOne, replaces per-user balance)
```

`Team.stripe_customer_id` is the Stripe customer identifier. The team Owner's email is the Stripe billing email. When the Owner transfers ownership, the Stripe customer record stays with the team (not the departing user).

Credit transactions (`CreditTransaction`) are attributed to the acting user (`CreditTransaction.performed_by → User`) but deducted from the team's balance.

**Migration note**: Existing deployments using the v0.85.0 billing module have user-scoped subscriptions. The teams migration must handle this: either convert existing subscriptions to a new team created from that user, or keep user-scoped billing as a legacy path and add team-scoped billing as an additive field. The migration strategy must be decided before implementation begins.

### Seat Pricing (Deferred)

Per-seat billing (charging per `TeamMembership` count) is not in v0.86.0 scope. The billing module already supports recurring subscriptions with credits; teams will use that surface.

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

Path routing (not subdomain). The team slug appears in the URL:

```
/teams/                          # List teams the current user belongs to
/teams/new/                      # Create a new team
/teams/<slug>/                   # Team dashboard
/teams/<slug>/members/           # Member list and role management
/teams/<slug>/invite/            # Send invitations
/teams/<slug>/invite/<token>/accept/  # Accept an invitation
/teams/<slug>/settings/          # Team settings (name, slug)
/teams/<slug>/billing/           # Team billing (delegates to billing module)

# API equivalents under /api/teams/<slug>/...
```

Subdomain routing (`acme.myapp.com`) is not in v0.86.0 scope. It requires DNS configuration that the operator must handle and is not automatable inside a Railway project without custom proxy infrastructure.

---

## Open Questions

These must be resolved before implementation begins. They are recorded here, not in the roadmap, so they survive the roadmap closeout.

1. **Multi-team membership**: Can a single user belong to more than one team? The data model above allows it (`unique_together` is `(user, team)`, not `user`). If yes, the UI needs an "active team" selector (session variable or URL-based). If no, the constraint becomes a `OneToOneField(User)` on `TeamMembership`, which simplifies routing but limits use cases like consultants.

2. **Team model location**: Should `Team` live in `quickscale_modules_teams` or in `quickscale_modules_auth`? The auth module already owns user identity; a case can be made that teams are an identity concern. The counter-argument is that auth should remain a standalone minimal module and teams should depend on auth, not the reverse.

3. **Billing migration path**: How do apps currently using v0.85.0 user-scoped billing migrate to team-scoped billing? Options: (a) auto-create a personal team for each existing user and migrate their subscription there; (b) treat solo users as a "team of one" transparently; (c) break compatibility and require operators to run a migration script.

4. **Admin panel isolation**: The Django admin panel runs as `is_staff` which bypasses RLS. What is the explicit contract for how the admin panel accesses multi-tenant data? Options: (a) admin always sees all tenants (intended for the SaaS operator, not tenants); (b) use `SET ROLE` to enforce RLS even in admin; (c) disable per-tenant models in admin entirely.

---

## v0.86.0 Implementation Scope

| Deliverable | Included |
|-------------|---------|
| `Team`, `TeamMembership`, `TeamInvitation` models | ✅ |
| `TenantModel` abstract base class with `team` FK | ✅ |
| PostgreSQL RLS migration for all tenant tables | ✅ |
| `TenantMiddleware` (sets `app.current_team_id`) | ✅ |
| `require_team_role` decorator | ✅ |
| Invitation flow via notifications module | ✅ |
| Billing bridge: `Subscription.team`, `CreditBalance.team` | ✅ |
| React theme: dashboard, members, invite, settings pages | ✅ |
| HTML theme: same pages | ✅ |
| Unit + integration tests for isolation and permissions | ✅ |
| Subdomain routing | ❌ deferred |
| Seat-based pricing | ❌ deferred |
| Per-tenant analytics | ❌ deferred |
| Cross-team admin tooling | ❌ deferred |

---

## References

- [`docs/legacy/tenancy-isolation-strategies.md`](../legacy/tenancy-isolation-strategies.md) — full RLS code examples, cost matrix, and real-world company comparisons
- [`docs/deployment/railway.md`](../deployment/railway.md) — Railway deployment contract
- [`docs/technical/decisions.md`](decisions.md) — architecture decision log
- [`quickscale_modules/billing/`](../../quickscale_modules/billing/) — billing models to extend
- [`quickscale_modules/auth/`](../../quickscale_modules/auth/) — User model base
- [`quickscale_modules/teams/README.md`](../../quickscale_modules/teams/README.md) — module placeholder
