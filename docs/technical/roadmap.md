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
| v0.86.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.87.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the hardening, billing, and teams milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo or release-prepared, but not yet tagged/published
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.85.0 is the published release
- **Next planned milestone:** v0.86.0 teams module after the billing milestone
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.86.0 - auth, billing, teams modules complete on top of the notifications foundation

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

### v0.86.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

**Status**: 📋 Planned

**Design document**: [`docs/technical/teams.md`](teams.md) — all architectural decisions, data models, and scope are recorded there. This section contains only the implementation task breakdown.

**Dependency note**: This milestone remains the SaaS-parity target after the v0.84.0 backups hardening release and the v0.85.0 billing milestone.

**Architecture summary**: Single Railway deployment (1 app + 1 PostgreSQL 18). All tenants share one database; PostgreSQL RLS enforces isolation. URL-based team routing (`/teams/<slug>/crm/`). Platform owner (`is_superuser`) sees all tenants via `/admin/`. Self-service customer signup → team creation → Stripe checkout. Users may belong to multiple teams (team switcher in React UI).

---

#### Phase 1 — Module scaffold + core models (4–6 h)

Create the teams module package and define all three core models plus the `TenantModel` abstract base.

**Files to create** (`quickscale_modules/teams/src/quickscale_modules_teams/`):
- `__init__.py`
- `apps.py` — `QuickscaleTeamsConfig` matching the billing/crm pattern
- `models.py` — `TeamRole` (TextChoices), `Team`, `TeamMembership`, `TeamInvitation`, `TenantModel`
- `admin.py` — register `Team`, `TeamMembership`, `TeamInvitation`; add `team` column and list filter to each
- `migrations/__init__.py`
- `migrations/0001_initial.py` — initial migration for the three models
- `module.yml` — `name: teams`, `django_apps: [quickscale_modules_teams]`

**Acceptance criteria**:
- `python manage.py migrate` succeeds
- All three models appear in `/admin/` with correct list columns
- `TenantModel` is importable from `quickscale_modules_teams.models`
- `module.yml` passes `quickscale plan` validation

---

#### Phase 2 — TenantMiddleware + RBAC + post-signup adapter (4–6 h)

Wire the tenant context into every request and enforce role-based access control.

**Files to create**:
- `middleware.py` — `TenantMiddleware`: resolves `team_slug` from URL, sets `SET LOCAL app.current_team_id`, guards no-team users, returns 403 for non-members
- `permissions.py` — `ROLE_HIERARCHY` dict, `require_team_role(min_role)` decorator, `TeamRoleMixin` for CBVs
- `adapters.py` — `TeamsAccountAdapter(DefaultAccountAdapter)`: overrides `get_login_redirect_url` to redirect teamless users to `/teams/new/`

**Files to modify**:
- `module.yml` — add `middleware: [quickscale_modules_teams.middleware.TenantMiddleware]` and `settings: {ACCOUNT_ADAPTER: ...}`

**Acceptance criteria**:
- A new signup with no team redirects to `/teams/new/` — cannot reach any other page
- A request to `/teams/acme-corp/` by a non-member returns HTTP 403
- `@require_team_role(min_role=TeamRole.ADMIN)` returns 403 for a MEMBER and 200 for an ADMIN
- `request.team` is populated for all team-scoped requests
- `SET LOCAL app.current_team_id` is confirmed via `SELECT current_setting('app.current_team_id', true)` in a test

---

#### Phase 3 — PostgreSQL RLS migration (6–8 h)

Enable row-level security on all tenant tables and verify cross-tenant isolation end-to-end.

**Files to create**:
- `migrations/0002_rls_tenant_isolation.py` — `RunSQL` migration that:
  1. Enables RLS on each tenant table: `ALTER TABLE <table> ENABLE ROW LEVEL SECURITY`
  2. Creates isolation policies: `CREATE POLICY tenant_isolation ON <table> USING (team_id = current_setting('app.current_team_id', true)::uuid)`
  3. Tables covered: `quickscale_crm_*`, `quickscale_blog_*`, `quickscale_forms_*`, `quickscale_listings_*`, notifications, storage

**Tenant tables checklist** (confirm actual table names via `\dt` before writing SQL):
- CRM: contacts, companies, deals, activities, pipeline stages, tags
- Blog: posts, categories, comments
- Forms: forms, submissions, fields
- Listings: listings, listing images
- Notifications: notifications, notification preferences

**Files to create (tests)**:
- `tests/test_rls_isolation.py` — integration test: create two teams, create a CRM contact under team A, assert team B user's queryset is empty for that contact

**Acceptance criteria**:
- `python manage.py migrate` applies the RLS migration without errors
- Platform owner (`is_superuser`) sees all rows in all tables (RLS bypass confirmed)
- Team A user cannot read Team B's rows in any tenant table
- Empty queryset (not exception) is returned when `app.current_team_id` is not set

---

#### Phase 4 — Team management views + URLs (Django) (4–6 h)

Build the server-side views, forms, and URL routes for team lifecycle management.

**Files to create**:
- `views.py`:
  - `TeamListView` — lists all teams the current user belongs to
  - `TeamCreateView` — creates a team and redirects to Stripe checkout
  - `TeamDashboardView` — team home page (member count, recent activity)
  - `MemberListView` — lists `TeamMembership` rows; allows role change (ADMIN+) and removal (ADMIN+)
  - `TeamSettingsView` — update team `name` and `slug` (ADMIN+)
- `forms.py` — `TeamCreateForm` (name, slug with auto-slug), `TeamSettingsForm`, `RoleChangeForm`
- `urls.py` — all `/teams/` routes (see URL structure in design doc)
- `templates/quickscale_modules_teams/`:
  - `team_list.html`
  - `team_create.html`
  - `team_dashboard.html`
  - `members.html`
  - `settings.html`

**Files to modify**:
- `module.yml` — add `url_includes: [["teams/", "quickscale_modules_teams.urls"]]`

**Acceptance criteria**:
- `/teams/` lists a logged-in user's teams; empty state prompts to create one
- `/teams/new/` creates a team and redirects to Stripe pricing
- `/teams/<slug>/members/` shows the membership list; ADMIN can change roles; OWNER cannot be demoted
- `/teams/<slug>/settings/` updates team name/slug (ADMIN only)
- A MEMBER visiting `/teams/<slug>/settings/` receives HTTP 403

---

#### Phase 5 — Invitation flow (4–6 h)

Build the full invite-send → email → accept pipeline using the existing notifications module.

**Files to modify** (`views.py`):
- `InviteView` — ADMIN+: creates `TeamInvitation`, triggers notification email
- `AcceptInvitationView` — public: validates token, creates `TeamMembership` for existing user or redirects new user to signup with token in session

**Files to create**:
- `forms.py` additions — `InviteForm` (email, role)
- `templates/quickscale_modules_teams/invite.html` — invite form page
- `templates/quickscale_modules_teams/accept.html` — accept confirmation page
- `templates/quickscale_modules_teams/email/invite.html` — email body (uses notifications module `send_notification`)

**Edge cases to handle**:
- Expired token → HTTP 410 with clear message
- Already-accepted token → HTTP 410
- Revoke invitation → DELETE `TeamInvitation` row; token URL becomes 404
- Accept by new user → store token in session, complete membership on `user_signed_up` signal

**Acceptance criteria**:
- ADMIN sends invite → email arrives with correct accept URL
- Existing user clicks accept → `TeamMembership` created with correct role
- New user clicks accept → redirected to signup → membership created after account creation
- Expired token → 410 response with user-facing message
- Revoked invitation URL → 404

---

#### Phase 6 — Billing bridge (4–6 h)

Migrate billing models from user-scoped to team-scoped and provide a migration path for existing deployments.

**Files to modify** (`quickscale_modules/billing/src/quickscale_modules_billing/models.py`):
- `Subscription`: add `team = ForeignKey(Team, null=True, on_delete=SET_NULL, related_name='subscriptions')`
- `CreditBalance`: add `team = OneToOneField(Team, null=True, on_delete=CASCADE, related_name='credit_balance')`
- `CreditTransaction`: add `performed_by = ForeignKey(User, null=True, on_delete=SET_NULL, related_name='credit_actions')`

**Files to create** (`quickscale_modules/billing/src/quickscale_modules_billing/migrations/`):
- `0003_team_billing_bridge.py` — adds nullable `team` FK to Subscription and CreditBalance, adds `performed_by` to CreditTransaction

**Files to create** (`quickscale_modules/teams/src/quickscale_modules_teams/management/commands/`):
- `migrate_billing_to_teams.py` — idempotent command:
  1. For each `User` with a `Subscription` or `CreditBalance` but no `TeamMembership`
  2. Create `Team(name=f"{user.username}'s Team", slug=user.username)`
  3. Create `TeamMembership(user, team, role=OWNER)`
  4. Point `Subscription.team` and `CreditBalance.team` to the new team

**Acceptance criteria**:
- `python manage.py migrate_billing_to_teams` runs without error on a v0.85.0 dataset
- After migration, every `Subscription` has a non-null `team`
- Stripe checkout creates `Subscription.team` (verified in billing view)
- Team's credit balance is debited on credit usage (not the individual user's balance)
- `CreditTransaction.performed_by` records which team member spent the credits

---

#### Phase 7 — React frontend: team pages + team switcher (6–8 h)

Add all team management pages to the React SPA and move existing module routes under the team slug.

**Files to modify** (`frontend/src/`):
- `App.tsx` — add `/teams/*` route tree; move `/crm`, `/blog`, `/forms`, `/listings` to `/teams/:slug/*`
- `components/layout/Sidebar.tsx` (or equivalent) — add team switcher component

**Files to create** (`frontend/src/pages/teams/`):
- `TeamListPage.tsx` — lists user's teams; "Create team" CTA
- `TeamCreatePage.tsx` — name + slug form; on submit → Stripe checkout redirect
- `TeamLayout.tsx` — wrapper that injects `teamSlug` from `useParams()` into nested pages
- `TeamDashboardPage.tsx` — team home; member count, plan status
- `TeamMembersPage.tsx` — member list, role selector (ADMIN+), remove button
- `TeamInvitePage.tsx` — invite form (email + role)
- `TeamSettingsPage.tsx` — name/slug update form

**Files to create** (`frontend/src/components/teams/`):
- `TeamSwitcher.tsx` — dropdown showing active team; lists all user teams; "Create team" link; navigates by changing slug in URL

**Files to create** (`frontend/src/hooks/`):
- `useTeams.ts` — `GET /api/teams/` → list user's teams
- `useTeam.ts` — `GET /api/teams/:slug/` → single team detail
- `useTeamMembers.ts` — `GET /api/teams/:slug/members/`

**Acceptance criteria**:
- `/teams` lists the user's teams; clicking navigates to `/teams/:slug`
- Team switcher dropdown appears in sidebar; switching changes the URL and reloads data
- `/teams/new` creates a team; Stripe checkout opens
- `/teams/:slug/members` shows all members; ADMIN can change roles
- `/teams/:slug/crm` loads CRM data scoped to that team
- Navigating directly to `/teams/other-team/crm` as a non-member shows an error

---

#### Phase 8 — Tests + module.yml finalization (4–6 h)

Complete the test suite and finalize the module manifest for `quickscale plan` integration.

**Test files to create** (`quickscale_modules/teams/tests/`):
- `test_models.py` — role hierarchy constants, `unique_together` enforcement, last-owner protection
- `test_permissions.py` — `require_team_role` returns 403/200 for each role at each threshold
- `test_middleware.py` — team context set correctly; no-team user redirected; non-member returns 403
- `test_rls_isolation.py` — two teams; team A data invisible to team B user
- `test_invitation_flow.py` — full invite → email → accept cycle; expired token 410; revoke 404
- `test_billing_bridge.py` — `CreditBalance.team` debited on usage; `Subscription.team` populated on checkout

**`module.yml` final fields**:
```yaml
name: teams
version: "0.86.0"
description: "Multi-tenant teams with PostgreSQL RLS, RBAC, and self-service onboarding"
dependencies:
  - django-allauth>=0.63.0   # already required by auth module
django_apps:
  - quickscale_modules_teams
middleware:
  - quickscale_modules_teams.middleware.TenantMiddleware
settings:
  ACCOUNT_ADAPTER: quickscale_modules_teams.adapters.TeamsAccountAdapter
url_includes:
  - ["teams/", "quickscale_modules_teams.urls"]
```

**Acceptance criteria**:
- `python manage.py test quickscale_modules_teams` passes
- `quickscale plan` lists `teams` as a selectable module
- `quickscale apply` adds the middleware, adapter setting, and URL include to the generated project
- All 10 verification items from the design doc pass on a fresh generated project

---

### v0.87.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack. Any blocking HTML contract corrections discovered in v0.83.0 belong to the hardening release; this later milestone is for optional polish after the shipped contract is stable again.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---
