# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Timeline & Tasks)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document tracks the active development timeline, versioned milestone scope, and archived pointers for recent QuickScale releases.

**Content Guidelines:**
- Organize work by versioned milestones with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

**What to Add Here:**
- New milestone planning and release-specific task tracking
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

**What NOT to Add Here:**
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- Technical specifications or architectural decisions (belongs in decisions.md)
- User documentation or getting started guides (belongs in README.md)
- Directory structures or scaffolding details (belongs in scaffolding.md)

## Broad Overview of the Roadmap

QuickScale's roadmap is milestone-led. It tracks shipped release pointers, the current implementation line, and the next versioned scopes already tied to concrete repository work. Older phase labels still appear in some historical notes, but they are not the active roadmap structure.

## Current Milestone Summary

This table is the single milestone summary for shipped history and the active forward roadmap.

| Version | Status | Milestone | Details |
|---------|--------|-----------|---------|
| v0.71.0 | ✅ Completed | Plan/Apply system | Terraform-style configuration system complete |
| v0.72.0 | ✅ Completed | Plan/Apply cleanup | Legacy commands removed after the Plan/Apply rollout |
| v0.73.0 | ✅ Released | CRM module | API-first Django CRM with 7 core models and CLI integration; archived in changelog |
| v0.74.0 | ✅ Completed | React default theme | React + shadcn/ui baseline shipped |
| v0.75.0 | ✅ Completed | Forms module | Generic form builder with DRF API, spam protection, and GDPR anonymization |
| v0.76.0 | ✅ Released | Storage module | Cloud file hosting plus CDN-ready media infrastructure; archived in release note and changelog |
| v0.77.0 | ✅ Internal baseline | Backups module | Private local and optional private remote workflows, guarded BackupPolicy-admin local restore, and CLI restore; changelog-only historical baseline |
| v0.78.0 | ✅ Released | Notifications module | Transactional email foundation with app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery; archived in release note and changelog |
| v0.79.0 | ✅ Released | Social and Link Tree module | Curated social links and embeds, backend-owned preview metadata, and React public pages for fresh `showcase_react` generations; older projects adopt them manually |
| v0.80.0 | ✅ Released | Analytics module | PostHog website analytics with flat mutable settings, service-style backend hooks, and fresh `showcase_react` starter support; existing projects adopt frontend snippets manually |
| v0.81.0 | ✅ Released | Beta-site migration maintainer tooling | Maintainer-only fresh-first and checkpoint-first in-place beta-site migration workflows; archived in release note and changelog |
| v0.82.0 | ✅ Released | Disaster recovery & environment promotion | Public `quickscale dr` capture/plan/execute/report workflows with `snapshot_id` lookup, resumable capture/execute, rollback pins, conservative env-var sync, and source-side media sync; archived in release note and changelog |
| v0.83.0 | ✅ Released | Hardening release | Repo-wide hardening release published; archived in the release note and changelog |
| v0.84.0 | ✅ Released | Backups hardening release | Backup lifecycle hardening and runtime/tooling refresh archived in the release note and changelog |
| v0.85.0 | ✅ Released | Billing module | Stripe-backed one-time credit purchases and recurring subscriptions, credits-first Django ledger, planner/apply readiness, module-owned pricing and dashboard pages, and starter-theme billing links; archived in release note and changelog |
| v0.86.0 | 📋 Planned | Organizations module | Multi-tenancy with Solo/SaaS runtime modes, an org-scoping foundation for future PostgreSQL RLS, org-scoped billing, credits + feature gates, and self-service onboarding |
| v0.87.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the hardening, billing, and organizations milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo or release-prepared, but not yet tagged/published
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.85.0 is the published release
- **Next planned milestone:** v0.86.0 organizations module after the billing milestone
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.86.0 - auth, billing, organizations modules complete on top of the notifications foundation

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Release doc layout:** [CHANGELOG.md](../../CHANGELOG.md) is the canonical history index; for each published release, `docs/releases/release-vX.XX.X.md` is the single official release note linked from the GitHub tag and release PR; the roadmap tracks active and unreleased release status until that note exists
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [Release Summary Template](./release_summary_template.md) for the single public release-note workflow

## ROADMAP
List of upcoming releases with detailed implementation tasks:

---

After release closeout, keep only a concise pointer in the roadmap. Put canonical history in [CHANGELOG.md](../../CHANGELOG.md), and for published releases add `docs/releases/release-vX.XX.X.md` as the single official release note linked from the GitHub tag and release PR. Keep unreleased closeout status in the roadmap until that release note exists.

---

### v0.86.0: `quickscale_modules.orgs` - Organizations / Multi-tenancy Module

**Status**: 📋 Planned

**Design document**: [`docs/technical/organizations.md`](organizations.md) — all architectural decisions, data models, and scope are recorded there. This section contains only the implementation task breakdown.

**Dependency note**: This milestone remains the SaaS-parity target after the v0.84.0 backups hardening release and the v0.85.0 billing milestone. The billing module's `Subscription`, `CreditBalance`, and `Plan` models are extended here.

**Architecture summary**: Single Railway deployment (1 app + 1 PostgreSQL 18). All tenants share one database; ordinary requests are still isolated by the org middleware and permission layer, while PostgreSQL RLS remains a future hardening step until downstream modules carry concrete `organization_id` columns. Runtime `QUICKSCALE_MODE` setting switches between Solo mode (personal org auto-created, flat URLs) and SaaS mode (multi-org, `/orgs/<slug>/` routing, invitations enabled). Platform owner access remains governed by Django/admin permissions in this slice; no database-level RLS bypass is assumed. Self-service signup → org creation → Stripe checkout. Plans differentiate by credit volume + feature gates; optional seat pricing designed in.

---

#### Phase 1 — Module scaffold + core models (4–6 h)

Create the `quickscale_modules_orgs` package and define all core models, the `OrganizationManager`, and the `TenantModel` abstract base.

**Files to create** (`quickscale_modules/orgs/src/quickscale_modules_orgs/`):
- [x] `__init__.py`
- [x] `apps.py` — `QuickscaleOrgsConfig` matching the billing/crm pattern
- [x] `managers.py` — `OrganizationManager.create_personal_for(user)`: creates `Organization(is_personal=True, slug=username)` + OWNER `OrganizationMembership`; idempotent (returns existing on second call)
- [x] `models.py` — `OrgRole` (TextChoices: VIEWER/MEMBER/ADMIN/OWNER), `Organization` (id UUID, name, slug, stripe_customer_id, is_personal BooleanField default False, created_at), `OrganizationMembership` (user FK, organization FK, role, invited_by nullable FK, joined_at; `unique_together = [('user', 'organization')]`), `OrganizationInvitation` (id UUID, organization FK, email, role, invited_by FK, token UUID unique, expires_at, accepted_at nullable), `TenantModel` (abstract: `organization = ForeignKey(..., db_index=True)`)
- [x] `admin.py` — register `Organization` (list: name, slug, is_personal, created_at; filter: is_personal), `OrganizationMembership` (list: user, organization, role, joined_at; filter: role, organization), `OrganizationInvitation` (list: email, organization, role, expires_at, accepted_at; filter: organization)
- [x] `migrations/__init__.py`
- [x] `migrations/0001_initial.py` — initial migration for all four models
- [x] `module.yml` skeleton — `name: orgs`, `version: "0.86.0"`, `django_apps: [quickscale_modules_orgs]`
- [x] `README.md` — one-paragraph module description

**Acceptance criteria**:
- [x] `python manage.py migrate` succeeds with no errors
- [x] `Organization`, `OrganizationMembership`, `OrganizationInvitation` appear in `/admin/` with correct columns and filters
- [x] `TenantModel` importable from `quickscale_modules_orgs.models`; its `organization` FK references `quickscale_modules_orgs.Organization`
- [x] `Organization.objects.create_personal_for(user)` creates org with `is_personal=True`, slug from `user.username`, OWNER membership — second call returns existing org without creating duplicates
- [x] `unique_together = [('user', 'organization')]` enforced at DB level (constraint present in migration)
- [x] `module.yml` passes `quickscale plan` validation

---

#### Phase 2 — QUICKSCALE_MODE + TenantMiddleware + RBAC + post-signup adapter (5–7 h)

Wire the `QUICKSCALE_MODE` setting, tenant context per request, role-based access control, and post-signup routing for both modes. This phase affects every subsequent request — test each branch explicitly.

**Files to create**:
- [x] `middleware.py` — `TenantMiddleware`:
  - [x] `_resolve_org_slug(request, saas_mode)` — SaaS: reads `org_slug` from URL `resolve()` kwargs; Solo: queries user's personal org slug (no URL slug needed)
  - [x] No-membership guard: Solo mode calls `create_personal_for(request.user)`; SaaS mode redirects to `/orgs/new/` for all non-exempt paths (`/accounts/*`, `/orgs/new/`)
  - [x] Non-member requesting an org route → `HttpResponseForbidden()`
  - [x] Sets `SET LOCAL app.current_org_id = <uuid>` via `connection.cursor()`
  - [x] Sets `request.org` for all org-scoped requests; `None` for non-org routes
- [x] `permissions.py`:
  - [x] `ROLE_HIERARCHY = {OrgRole.VIEWER: 0, OrgRole.MEMBER: 1, OrgRole.ADMIN: 2, OrgRole.OWNER: 3}`
  - [x] `require_org_role(min_role)` decorator — resolves org from URL, checks membership + role, returns 403 on failure, sets `request.org`
  - [x] `OrgRoleMixin` — CBV equivalent of `require_org_role`
  - [x] `require_org_feature(feature_key)` decorator stub — reads `request.org.subscription.plan.features` (list); returns 402 when feature absent or no active subscription; fully wired in Phase 6
- [x] `adapters.py` — `OrgsAccountAdapter(DefaultAccountAdapter)`:
  - [x] Solo mode branch: calls `create_personal_for(request.user)`, returns `'/'`
  - [x] SaaS mode branch: returns `'/orgs/new/'` when no membership exists

**Files to modify**:
- [x] `module.yml` — add `middleware: [quickscale_modules_orgs.middleware.TenantMiddleware]`, `settings: {ACCOUNT_ADAPTER: quickscale_modules_orgs.adapters.OrgsAccountAdapter, QUICKSCALE_MODE: solo}`

**Acceptance criteria**:
- [x] **Solo mode**: new signup auto-creates personal org (`is_personal=True`); user lands at `/` without seeing org creation step
- [x] **SaaS mode**: new signup with no membership redirects to `/orgs/new/` for all non-exempt paths
- [x] Request to `/orgs/acme-corp/` by a non-member returns HTTP 403
- [x] `@require_org_role(min_role=OrgRole.ADMIN)` returns 403 for MEMBER, 403 for VIEWER, 200 for ADMIN, 200 for OWNER
- [x] `@require_org_role(min_role=OrgRole.OWNER)` returns 403 for ADMIN
- [x] `request.org` populated for org-scoped requests; `None` for non-org routes
- [x] `SET LOCAL app.current_org_id = <uuid>` confirmed via `SELECT current_setting('app.current_org_id', true)` in a test transaction
- [x] **Solo mode**: `_resolve_org_slug` returns personal org slug without reading from URL
- [x] Changing `QUICKSCALE_MODE` between `solo` and `saas` changes routing behaviour with no model changes

---

#### Phase 3 — Org RLS foundation + guarded activation prep (completed foundation slice)

Establish the runtime prerequisites for future PostgreSQL RLS without shipping unsafe database policies yet. This slice keeps ordinary request isolation in the application layer, ensures org context is set consistently for scoped requests, and records the hard prerequisites for the later PostgreSQL activation work.

**Files modified in the foundation slice**:
- [x] `middleware.py`
  - [x] Split bootstrap/exempt-path handling from org-scoped request handling so only scoped requests participate in org resolution and DB session setup
  - [x] Keep `SET LOCAL app.current_org_id = <uuid>` limited to resolved org-scoped requests, leaving non-org and exempt paths unset
  - [x] Preserve Solo and SaaS membership/slug resolution semantics while tightening the branch that future RLS will depend on
- [x] `tests/test_middleware.py`
  - [x] Expand caller-parity coverage for bootstrap/exempt paths versus org-scoped paths
  - [x] Verify the scoped branch sets `request.org` and the DB session org context only when an organization is actually resolved

**Deferred activation checklist**:
- [ ] Add concrete `organization_id` columns to downstream tenant tables before any RLS SQL ships
- [ ] Create a dedicated PostgreSQL migration that enables RLS only on tables proven to be org-scoped
- [ ] Add PostgreSQL-only integration tests for cross-org isolation and unset-context fail-safe behavior
- [x] Document the shipped application-layer superuser operator path explicitly without assuming Django `is_superuser` implies a database-level RLS bypass

**Acceptance criteria**:
- [x] Org-scoped requests continue to set `app.current_org_id` via middleware for future PostgreSQL policy activation
- [x] Bootstrap and exempt paths avoid the scoped branch and preserve caller parity across Solo and SaaS modes
- [x] The roadmap states clearly that current tenant isolation for ordinary requests is still enforced in the application layer
- [x] No PostgreSQL RLS migration ships in this slice because downstream business modules do not yet provide complete `organization_id` coverage
- [ ] Actual PostgreSQL RLS activation remains a later milestone once downstream tenant tables are ready

---

#### Phase 4 — Org management views + URL structure (Django) (4–6 h)

Build server-side views, forms, and the dual URL configuration. SaaS org management pages are only reachable in SaaS mode; Solo mode serves flat routes with no org slug.

**Files to create**:
- [x] `views.py`:
  - [x] `OrgListView` — lists all orgs the current user belongs to (SaaS only)
  - [x] `OrgCreateView` — creates org, redirects to billing pricing (SaaS only)
  - [x] `OrgDashboardView` — org home with thin dashboard context until the billing bridge lands
  - [x] `MemberListView` — lists `OrganizationMembership` rows; role change (ADMIN+); remove member (ADMIN+); blocks second-owner assignment without transfer and blocks demotion/removal of the last OWNER
  - [x] `OrgSettingsView` — updates org `name` and `slug` (ADMIN+); warns that slug changes break existing bookmarks
- [x] `forms.py`:
  - [x] `OrgCreateForm` — `name` field; auto-derives a unique `slug` server-side
  - [x] `OrgSettingsForm` — `name`, `slug` fields with normalization and uniqueness validation
  - [x] `RoleChangeForm` — `role` choices exclude OWNER when the acting user is not owner-like
- [x] `urls.py` — preserves the `quickscale_modules_orgs.urls` import target while serving solo `/` through the pre-home include and SaaS `/orgs/*` pages through the post-home include
- [x] `templates/quickscale_modules_orgs/`:
  - [x] `org_list.html`
  - [x] `org_create.html`
  - [x] `org_dashboard.html`
  - [x] `members.html`
  - [x] `settings.html`

**Files to modify**:
- [x] `module.yml` — runtime-mode routing metadata completed in the earlier Phase 1 wiring slice while preserving `quickscale_modules_orgs.urls`
- [x] Project `urls.py` template — pre-home vs post-home include behaviour completed in the earlier Phase 1 wiring slice

**Acceptance criteria**:
- [x] **SaaS mode**: `/orgs/` lists the user's orgs; empty state shows "Create your organization" CTA
- [x] **SaaS mode**: `/orgs/new/` creates an org and redirects to billing pricing
- [x] **SaaS mode**: `/orgs/<slug>/members/` — ADMIN can change roles; OWNER role cannot be assigned to a second member without transfer; the last OWNER cannot be removed or demoted
- [x] **SaaS mode**: `/orgs/<slug>/settings/` updates name/slug (ADMIN only); a MEMBER receives HTTP 403
- [x] **Solo mode**: `/` serves the org dashboard; downstream module pages remain flat and unslugged because `/orgs/*` stays hidden in solo mode
- [x] Non-existent org slug returns 404 (not 500) in both runtime modes

---

#### Phase 5 — Invitation flow (4–6 h)

Build the full invite-send → email → accept pipeline using the existing notifications module. **SaaS mode only** — all invitation views return HTTP 404 in Solo mode.

**Files to modify** (`views.py`):
- [ ] `InviteView` — requires ADMIN+; creates `OrganizationInvitation` (UUID token, 7-day expiry); sends email via notifications module
- [ ] `RevokeInvitationView` — requires ADMIN+; deletes `OrganizationInvitation` row
- [ ] `AcceptInvitationView` — public (no login required): validates token; existing user → creates `OrganizationMembership`; new user → stores token in session, redirects to signup

**Files to create**:
- [ ] `forms.py` additions — `InviteForm` (email + role; OWNER excluded from role choices)
- [ ] `templates/quickscale_modules_orgs/invite.html` — invite form + pending invitations list with revoke buttons
- [ ] `templates/quickscale_modules_orgs/accept.html` — confirmation page after membership created
- [ ] `templates/quickscale_modules_orgs/email/invite.html` — email body with accept URL; uses notifications `send_notification`
- [ ] `signals.py` — connects to django-allauth `user_signed_up` signal: if session contains invitation token, creates `OrganizationMembership` and clears token from session

**Edge cases — each requires a dedicated test**:
- [ ] Expired token (`expires_at < now`, `accepted_at is None`) → HTTP 410, message: "This invitation has expired. Ask an admin to send a new one."
- [ ] Already-accepted token (`accepted_at is not None`) → HTTP 410, message: "This invitation has already been used."
- [ ] Revoked invitation token URL → HTTP 404
- [ ] Invitation email does not match logged-in user's email → HTTP 403
- [ ] Invitation URL visited in Solo mode → HTTP 404

**Acceptance criteria**:
- [ ] ADMIN sends invite → email arrives with accept URL containing UUID token
- [ ] Existing user (logged in) clicks accept → `OrganizationMembership` created with correct role; user lands on org dashboard
- [ ] Existing user (not logged in) clicks accept → redirected to login; membership created after login; user lands on org dashboard
- [ ] New user clicks accept → session stores token; signup completes; `user_signed_up` signal creates membership; user lands on org dashboard
- [ ] Expired token → HTTP 410 with user-facing message (not 500, not 404)
- [ ] Already-accepted token → HTTP 410 with user-facing message
- [ ] Revoked invitation URL → HTTP 404
- [ ] Solo mode invitation URL → HTTP 404

---

#### Phase 6 — Billing bridge + plan feature gates (6–8 h)

Extend billing models to be org-scoped, add plan-level feature gates and seat fields, and provide migration commands for existing deployments.

**Files to modify** (`quickscale_modules/billing/src/quickscale_modules_billing/models.py`):
- [ ] `Subscription`: add `organization = ForeignKey('quickscale_modules_orgs.Organization', null=True, on_delete=SET_NULL, related_name='subscriptions')`
- [ ] `CreditBalance`: add `organization = OneToOneField('quickscale_modules_orgs.Organization', null=True, on_delete=CASCADE, related_name='credit_balance')`
- [ ] `CreditTransaction`: add `performed_by = ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=SET_NULL, related_name='credit_actions')`
- [ ] `Plan`: add `features = JSONField(default=list)` (list of module key strings e.g. `["blog", "crm", "forms"]`), `max_seats = IntegerField(default=0)` (0 = unlimited; UI-enforced only in v0.86.0 — add `# TODO: enforce at DB layer` comment), `seat_price_id = CharField(blank=True)` (Stripe price ID for per-seat addon)

**Files to create** (`quickscale_modules/billing/src/quickscale_modules_billing/migrations/`):
- [ ] `0003_org_billing_bridge.py` — nullable `organization` FK on Subscription and CreditBalance; `performed_by` on CreditTransaction; `features`, `max_seats`, `seat_price_id` on Plan

**Files to create** (`quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/`):
- [ ] `migrate_billing_to_orgs.py` — idempotent:
  - [ ] For each User with a Subscription or CreditBalance but no OrganizationMembership: call `create_personal_for(user)`, point Subscription/CreditBalance to new org
  - [ ] Skips users who already have OrganizationMembership
  - [ ] Prints per-user summary; exits 0 on success
- [ ] `promote_to_saas.py` — idempotent:
  - [ ] Ensures all `is_personal=True` orgs have a valid unique slug (fills from owner username if blank; appends `-2`, `-3` etc. on collision)
  - [ ] Prints summary of orgs updated; prints the required `QUICKSCALE_MODE = 'saas'` settings change (cannot mutate `settings.py` directly); exits 0 on success

**Wiring `require_org_feature`** (stubbed in Phase 2 — complete here):
- [ ] Read `request.org.subscription.plan.features` (list); return 402 when feature absent
- [ ] Return 402 when `request.org` has no active subscription (guard against silent feature leakage)
- [ ] Update `Plan` admin to show `features` as an editable JSON field, `max_seats`, `seat_price_id`

**Acceptance criteria**:
- [ ] `python manage.py migrate_billing_to_orgs` runs without error on a v0.85.0 fixture; all Subscriptions have non-null `organization` after run
- [ ] Running `migrate_billing_to_orgs` twice produces no duplicate orgs or memberships
- [ ] Stripe checkout creates `Subscription.organization` (assert `subscription.organization == request.org` in billing view test)
- [ ] Org's `CreditBalance` debited on credit usage; no change to any user-level balance field
- [ ] `CreditTransaction.performed_by` records the acting org member
- [ ] `@require_org_feature('crm')` returns 200 when `'crm' in plan.features`; returns 402 when not present
- [ ] `@require_org_feature('crm')` returns 402 when org has no active subscription
- [ ] `python manage.py promote_to_saas` runs idempotently; all personal orgs have valid unique slugs after run

---

#### Phase 7 — React frontend: org pages + org switcher (6–8 h)

Add all org management pages, wire Solo and SaaS route trees, and remove all legacy `Team*` components.

**Files to modify** (`frontend/src/`):
- [ ] `App.tsx` — SaaS mode: add `/orgs/*` route tree, move `/crm`/`/blog`/`/forms`/`/listings` under `/orgs/:slug/*`; Solo mode: keep flat routes; remove all `/teams/*` routes
- [ ] `components/layout/Sidebar.tsx` (or equivalent) — render `OrgSwitcher` in SaaS mode; hide in Solo mode

**Files to create** (`frontend/src/pages/orgs/`):
- [ ] `OrgListPage.tsx` — user's org list; "Create organization" CTA (SaaS only)
- [ ] `OrgCreatePage.tsx` — name + auto-slug form; Stripe checkout redirect on submit (SaaS only)
- [ ] `OrgLayout.tsx` — wrapper reading `orgSlug` from `useParams()`; renders 403 page if org fetch returns 403
- [ ] `OrgDashboardPage.tsx` — org home: member count, plan tier, credit balance, recent activity feed
- [ ] `OrgMembersPage.tsx` — member list with role selector (ADMIN+); remove button (ADMIN+); last OWNER's controls disabled with tooltip
- [ ] `OrgInvitePage.tsx` — invite form (email + role) + pending invitations list with revoke button (SaaS only)
- [ ] `OrgSettingsPage.tsx` — name/slug update form (ADMIN+)

**Files to create** (`frontend/src/components/orgs/`):
- [ ] `OrgSwitcher.tsx` — dropdown: active org name, all user orgs, "Create organization" link; navigates to `/orgs/:slug` on selection (SaaS only)

**Files to create** (`frontend/src/hooks/`):
- [ ] `useOrgs.ts` — `GET /api/orgs/` → user's org list
- [ ] `useOrg.ts` — `GET /api/orgs/:slug/` → single org detail + plan + credit balance
- [ ] `useOrgMembers.ts` — `GET /api/orgs/:slug/members/`

**Files to remove**:
- [ ] `frontend/src/pages/teams/` — entire directory removed
- [ ] `frontend/src/components/teams/TeamSwitcher.tsx` — removed
- [ ] `frontend/src/hooks/useTeams.ts`, `useTeam.ts`, `useTeamMembers.ts` — removed

**Acceptance criteria**:
- [ ] **SaaS mode**: `/orgs` lists user's orgs; clicking navigates to `/orgs/:slug`
- [ ] **SaaS mode**: Org switcher in sidebar; switching changes URL slug and reloads all org-scoped data
- [ ] **SaaS mode**: `/orgs/new` creates org; Stripe checkout opens
- [ ] **SaaS mode**: `/orgs/:slug/members` — ADMIN can change roles; last OWNER's role selector is disabled
- [ ] **SaaS mode**: `/orgs/:slug/crm` loads CRM scoped to that org; non-member navigating there sees 403 error page (not blank page, not crash)
- [ ] **Solo mode**: flat routes `/crm`, `/blog` etc. work; no org switcher shown; `/orgs/*` routes not accessible
- [ ] `grep -r "Team" frontend/src/pages frontend/src/components frontend/src/hooks` returns no matches related to org management (only incidental string matches acceptable)

---

#### Phase 8 — Tests + module.yml finalization (4–6 h)

Complete the test suite and finalize the module manifest. All tests involving RLS require a real PostgreSQL connection — mark with `@pytest.mark.django_db(transaction=True)`.

**Test files to create** (`quickscale_modules/orgs/tests/`):
- [ ] `test_models.py`:
  - [ ] `OrgRole` hierarchy values ordered correctly (VIEWER < MEMBER < ADMIN < OWNER)
  - [ ] `unique_together = [('user', 'organization')]` raises `IntegrityError` on duplicate membership
  - [ ] Last OWNER cannot be removed (test both model guard and view guard)
  - [ ] `create_personal_for(user)` idempotent — second call returns existing org, no duplicate created
  - [ ] `Organization.is_personal` set correctly; `is_personal=False` for user-named orgs
- [ ] `test_permissions.py`:
  - [ ] `require_org_role(ADMIN)`: 200 for ADMIN, 200 for OWNER, 403 for MEMBER, 403 for VIEWER, 403 for non-member
  - [ ] `require_org_role(OWNER)`: 200 for OWNER only; 403 for all other roles
  - [ ] `require_org_feature('crm')`: 200 when feature in plan, 402 when not present, 402 when no active subscription
- [ ] `test_middleware.py`:
  - [ ] **Solo mode**: new user auto-gets personal org; `request.org` set from personal org without URL slug
  - [ ] **SaaS mode**: new user (no membership) redirected to `/orgs/new/`
  - [ ] **SaaS mode**: authenticated non-member requesting `/orgs/acme-corp/` returns 403
  - [ ] `app.current_org_id` set correctly in both modes
  - [ ] `QUICKSCALE_MODE` switch changes behaviour with no model changes
- [ ] `test_rls_isolation.py` (PostgreSQL + `transaction=True`):
  - [ ] Org A user queryset for Org B contact is empty (not exception)
- [ ] Platform owner query behavior follows the explicitly implemented operator policy for the RLS rollout; do not assume Django `is_superuser` bypasses PostgreSQL policies automatically
  - [ ] Unset `app.current_org_id` → empty queryset (not exception)
  - [ ] Solo mode: user sees only their personal org's rows
- [ ] `test_invitation_flow.py`:
  - [ ] Full cycle: invite → email sent (mocked) → existing user accepts → membership created with correct role
  - [ ] Full cycle: new user accepts → signup → `user_signed_up` signal → membership created
  - [ ] Expired token → 410 with user-facing message
  - [ ] Already-accepted token → 410 with user-facing message
  - [ ] Revoke → token URL becomes 404
  - [ ] Email mismatch (logged-in user email ≠ invitation email) → 403
  - [ ] Solo mode invitation URL → 404
- [ ] `test_billing_bridge.py`:
  - [ ] `CreditBalance.organization` debited on credit usage; user-level balance unchanged
  - [ ] `Subscription.organization` set on Stripe checkout completion
  - [ ] `CreditTransaction.performed_by` records acting user
  - [ ] `migrate_billing_to_orgs` idempotent on v0.85.0 fixture
  - [ ] `promote_to_saas` idempotent; all personal orgs have valid slugs after run
- [ ] `test_mode_switch.py`:
  - [ ] `QUICKSCALE_MODE = 'solo'`: flat routes work; `/orgs/new/` returns 404
  - [ ] `QUICKSCALE_MODE = 'saas'`: `/orgs/new/` reachable; org management pages render; invitation URLs active
  - [ ] After `promote_to_saas`: all personal orgs have slugs; invitation system operational

**`module.yml` final**:
```yaml
name: orgs
version: "0.86.0"
description: "Multi-tenant organizations with PostgreSQL RLS, RBAC, Solo/SaaS runtime mode, and self-service onboarding"
dependencies:
  - django-allauth>=0.63.0
django_apps:
  - quickscale_modules_orgs
middleware:
  - quickscale_modules_orgs.middleware.TenantMiddleware
settings:
  ACCOUNT_ADAPTER: quickscale_modules_orgs.adapters.OrgsAccountAdapter
  QUICKSCALE_MODE: solo
url_includes:
  - conditional: QUICKSCALE_MODE
    saas: ["orgs/", "quickscale_modules_orgs.urls.saas"]
    solo: ["", "quickscale_modules_orgs.urls.solo"]
```

**Acceptance criteria**:
- [ ] `python manage.py test quickscale_modules_orgs` passes — all test files, PostgreSQL backend
- [ ] `quickscale plan` lists `orgs` as a selectable module with correct metadata
- [ ] `quickscale apply` injects `TenantMiddleware`, `ACCOUNT_ADAPTER`, `QUICKSCALE_MODE = 'solo'` (default), and conditional URL includes into the generated project
- [ ] **Solo end-to-end**: signup → personal org auto-created → org dashboard at `/` reachable — no org creation step shown
- [ ] **SaaS end-to-end**: signup → `/orgs/new/` → org created → Stripe checkout → org dashboard at `/orgs/<slug>/`
- [ ] Cross-module migration dependency ordering documented in v0.86.0 release note: `quickscale_modules_orgs` must migrate before CRM, blog, forms, listings, notifications apply RLS policies

---

### v0.87.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack. Any blocking HTML contract corrections discovered in v0.83.0 belong to the hardening release; this later milestone is for optional polish after the shipped contract is stable again.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---
