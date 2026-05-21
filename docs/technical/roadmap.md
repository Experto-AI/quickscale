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
| v0.86.0 | 📋 Planned | Organizations module | Multi-tenancy with Solo/SaaS runtime modes, org-scoped billing, billing wiring fix + wiring regression guard, and self-service onboarding |
| v0.87.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the billing and organizations milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo or release-prepared, but not yet tagged/published
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.85.0 is the published release
- **Next planned milestone:** v0.86.0 organizations module after the billing milestone
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.86.0 - auth, billing, organizations modules complete on top of the notifications foundation
- **Billing wiring fix:** v0.86.0 - billing absent from generated wiring; `_billing_wiring` added to `MODULE_WIRING_BUILDERS`; wiring regression guard test added to `test_module_manifest_contract.py`

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

**Dependency note**: This milestone remains the SaaS-parity target after the v0.84.0 backups hardening release and the v0.85.0 billing milestone. The billing module's `Subscription`, `CreditBalance`, and `Plan` models are extended here, and the current maintainer-repo planner/apply contract now auto-materializes `orgs` whenever billing is selected so standalone billing is no longer advertised.

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
  - [x] `require_org_feature(feature_key)` decorator — resolves the current org's active subscription through the billing ORM and checks `Plan.features`; returns 402 when the feature is absent or when no active org subscription exists
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

Build the shipped invite-send -> email -> accept pipeline on top of the notifications module. This slice shipped independently of the still-open Phase 3 RLS activation work and the later Phase 6/7 billing and frontend follow-ons. **SaaS mode only** — Solo mode keeps invitation URLs hidden with HTTP 404, and ordinary SaaS no-membership traffic still goes to `/orgs/new/` unless a pending invitation is being continued.

**Files to modify** (`views.py`):
- [x] `InviteView` — requires ADMIN+; creates `OrganizationInvitation` (UUID token, 7-day expiry) from the org admin members surface and sends the invite through the notifications registry-backed `org_invitation` email
- [x] `RevokeInvitationView` — requires ADMIN+; revokes a pending invitation from the org admin members surface
- [x] `AcceptInvitationView` — public slugless accept path at `/orgs/invitations/<token>/accept/`; validates token, redirects unauthenticated users through auth, and completes redemption after auth only when the signed-in email matches the invitation email after normalization

**Files to create**:
- [x] `forms.py` additions — `InviteForm` (email + role; OWNER excluded from role choices)
- [x] `templates/quickscale_modules_orgs/members.html` — org members/admin surface with the invite form, pending invitations list, and revoke actions
- [x] `templates/quickscale_modules_orgs/org_invitation_accept.html` — invitation continuation plus confirmation/error states for invitation redemption
- [x] Notifications registry wiring — `org_invitation` email rendering and delivery moved through the notifications module registry instead of an org-owned template send path
- [x] Auth continuation storage — pending invitation continuation is carried through auth and redeemed back in `AcceptInvitationView`, so no separate signup signal handler is required for this shipped contract

**Edge cases — each requires a dedicated test**:
- [x] Expired token (`expires_at < now`, `accepted_at is None`) -> HTTP 410, message: "This invitation has expired. Ask an admin to send a new one."
- [x] Already-accepted token (`accepted_at is not None`) -> HTTP 410, message: "This invitation has already been used."
- [x] Revoked invitation token URL -> HTTP 404
- [x] Invitation email does not match the logged-in user's normalized email -> HTTP 403 before membership side effects
- [x] Invitation URL visited in Solo mode -> HTTP 404

**Acceptance criteria**:
- [x] ADMIN sends invite -> email arrives with the slugless accept URL `/orgs/invitations/<token>/accept/`
- [x] Existing user (logged in) clicks accept -> `OrganizationMembership` created with the correct role; user lands on the org dashboard
- [x] Existing user (not logged in) clicks accept -> redirected through auth; membership created after login; user lands on the org dashboard
- [x] New user clicks accept -> auth continuation stores the pending token; `AcceptInvitationView` redeems it after signup/login when the normalized email matches; user lands on the org dashboard
- [x] Expired token -> HTTP 410 with a user-facing message (not 500, not 404)
- [x] Already-accepted token -> HTTP 410 with a user-facing message
- [x] Revoked invitation URL -> HTTP 404
- [x] Solo mode invitation URL -> HTTP 404
- [x] Shipping this slice did not require the still-open Phase 3 activation checklist or any Phase 6/7 billing/frontend work

**Focused validation notes**:
- [x] Validation stays scoped to invitation send/revoke, slugless accept continuation, auth redirect/resume, normalized-email redemption guards, and Solo-mode 404 behavior
- [x] Phase 5 closeout depends on targeted invitation-flow coverage rather than on deferred Phase 3 RLS activation or later Phase 6/7 integration work

---

#### Phase 6 — Billing bridge + plan feature gates (6–8 h)

Extend billing models to be org-scoped, ship plan-level feature gates, and provide migration commands for existing deployments. The authoritative org-billing ownership fields, migration/promote commands, canonical org-keyed billing routes, flat compatibility shims, and ORM-backed `require_org_feature` wiring are now shipped; optional seat-pricing fields remain follow-on work.

**Files to modify** (`quickscale_modules/billing/src/quickscale_modules_billing/models.py`):
- [x] `Subscription`: add authoritative `organization = ForeignKey('quickscale_modules_orgs.Organization', null=True, on_delete=SET_NULL, related_name='subscriptions')`; keep nullable `user` as provenance / compatibility only
- [x] `CreditBalance`: add authoritative `organization = OneToOneField('quickscale_modules_orgs.Organization', null=True, on_delete=CASCADE, related_name='credit_balance')`; keep nullable `user` as provenance / compatibility only
- [x] `CreditTransaction`: add authoritative `organization = ForeignKey('quickscale_modules_orgs.Organization', null=True, on_delete=SET_NULL, related_name='credit_transactions')` while keeping `user` as the acting org member / audit actor
- [x] `Plan`: add `features = JSONField(default=list)` (list of module key strings e.g. `["blog", "crm", "forms"]`)
- [ ] `Plan`: add `max_seats = IntegerField(default=0)` (0 = unlimited; UI-enforced only when seat billing ships)
- [ ] `Plan`: add `seat_price_id = CharField(blank=True)` (Stripe price ID for per-seat addon)

**Files to create** (`quickscale_modules/billing/src/quickscale_modules_billing/migrations/`):
- [x] `0003_org_authoritative_billing_contract.py` — authoritative `organization` ownership fields, org backfill rules, nullable provenance/compatibility retention for `Subscription.user` and `CreditBalance.user`, and `Plan.features`

**Files to create** (`quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/`):
- [x] `migrate_billing_to_orgs.py` — idempotent:
  - [x] Reuses the sole resolvable org when one already exists; otherwise creates a personal org and points authoritative billing rows to it
  - [x] Refuses ambiguous membership cases instead of guessing
  - [x] Prints per-user summary; exits 0 on success
- [x] `promote_to_saas.py` — idempotent:
  - [x] Ensures all `is_personal=True` orgs have a valid unique slug (fills from owner username if blank; appends `-2`, `-3` etc. on collision)
  - [x] Prints summary of orgs updated plus the required `QUICKSCALE_MODE = 'saas'` settings change (cannot mutate `settings.py` directly); exits 0 on success

**Wiring `require_org_feature`** (completed in the current Phase 6 slice):
- [x] Resolve the current org's active subscription through the billing ORM instead of trusting `request.org.subscription`
- [x] Check `Plan.features` as the sole entitlement source and return 402 when the feature is absent
- [x] Return 402 when the org has no active subscription (guard against silent feature leakage)
- [x] Update `Plan` admin to surface plan feature flags on the editable plan record
- [ ] Extend `Plan` admin for `max_seats` / `seat_price_id` when seat fields ship

**Acceptance criteria**:
- [x] `python manage.py migrate_billing_to_orgs` runs without error on a v0.85.0 fixture; authoritative subscription/balance ownership is migrated to organizations
- [x] Running `migrate_billing_to_orgs` twice produces no duplicate orgs or memberships
- [x] Stripe checkout creates `Subscription.organization` (assert `subscription.organization == request.org` in billing view test)
- [x] Org's `CreditBalance` is treated as authoritative on credit usage; `CreditBalance.user` remains nullable provenance / compatibility only
- [x] `CreditTransaction.user` continues to record the acting org member while `organization` carries authoritative scope
- [x] `@require_org_feature('crm')` returns 200 when `'crm' in plan.features`; returns 402 when not present
- [x] `@require_org_feature('crm')` returns 402 when org has no active subscription
- [x] `python manage.py promote_to_saas` runs idempotently; all personal orgs have valid unique slugs after run

---

#### Phase 7 — React frontend: org pages + org switcher (completed)

Fresh `showcase_react` generations now ship the org-aware React shell. The final URL-reservation slice landed the generated Django precedence needed to serve the `/orgs/*` shell ahead of overlapping module URLs while keeping billing, invitation, and social routes under Django ownership. The shipped starter also consolidated some earlier file-by-file roadmap guesses: invite + pending-invitation UI lives inside `OrgMembersPage.tsx`, and `useOrgs.ts` exports the single-org and members hooks instead of splitting them into separate files. The older `Team*` cleanup bullets were stale no-ops because those files do not exist in the current `showcase_react` template inventory.

**Files to modify** (`frontend/src/`):
- [x] `App.tsx` — SaaS mode adds the `/orgs/*` route tree, keeps the flat legacy redirects, and the generated Django `urls.py` now reserves the React shell ahead of overlapping module URLs; Solo mode keeps the flat route tree with no `/teams/*` routes
- [x] `components/layout/Sidebar.tsx` (or equivalent) — renders `OrgSwitcher` in SaaS mode and hides it in Solo mode

**Files to create** (`frontend/src/pages/orgs/`):
- [x] `OrgListPage.tsx` — user's org list with a "Create organization" CTA (SaaS only)
- [x] `OrgCreatePage.tsx` — name + server-derived slug flow with billing checkout redirect on submit (SaaS only)
- [x] `OrgLayout.tsx` — wrapper reading `orgSlug` from `useParams()` and rendering the shipped 403 page when the org fetch returns 403
- [x] `OrgDashboardPage.tsx` — org home with member count, plan tier, credit balance, and current org overview
- [x] `OrgMembersPage.tsx` — member list with role selector, remove controls, invite form, pending invitations list, revoke actions, and the last-owner guardrails
- [x] Invite + pending-invitation UI shipped inside `OrgMembersPage.tsx`; no separate `OrgInvitePage.tsx` is generated in the current starter
- [x] `OrgSettingsPage.tsx` — name/slug update form (ADMIN+)

**Files to create** (`frontend/src/components/orgs/`):
- [x] `OrgSwitcher.tsx` — dropdown with the active org, org list, and a "Create organization" link; navigates to `/orgs/:slug` on selection (SaaS only)

**Files to create** (`frontend/src/hooks/`):
- [x] `useOrgs.ts` — exports `useOrgs()`, `useOrg()`, `useOrgMembers()`, invite/revoke/remove mutations, settings updates, and org billing helpers from one consolidated hook module
- [x] No separate `useOrg.ts` file ships; `useOrg()` is exported from `useOrgs.ts`
- [x] No separate `useOrgMembers.ts` file ships; `useOrgMembers()` is exported from `useOrgs.ts`

**Files to remove**:
- [x] No `frontend/src/pages/teams/` directory exists in the current `showcase_react` starter; cleanup was a no-op
- [x] No `frontend/src/components/teams/TeamSwitcher.tsx` file exists in the current `showcase_react` starter; cleanup was a no-op
- [x] No `frontend/src/hooks/useTeams.ts`, `useTeam.ts`, or `useTeamMembers.ts` files exist in the current `showcase_react` starter; cleanup was a no-op

**Acceptance criteria**:
- [x] **SaaS mode**: `/orgs` lists the user's orgs and the generated shell navigates to `/orgs/:slug`
- [x] **SaaS mode**: Org switcher appears in the sidebar; switching changes the URL slug and reloads org-scoped data
- [x] **SaaS mode**: `/orgs/new` creates an org and opens the billing checkout redirect
- [x] **SaaS mode**: `/orgs/:slug/members` lets admins manage roles, invite members, revoke invitations, and keeps the last OWNER guarded
- [x] **SaaS mode**: `/orgs/:slug/crm` runs inside the org-scoped shell, and non-members get the shipped 403 error page instead of a blank screen or crash
- [x] **Solo mode**: flat routes such as `/crm` and `/blog` continue to work, no org switcher is shown, and the `/orgs/*` shell stays inaccessible from the Solo route tree
- [x] The current `showcase_react` template inventory contains no `Team*` org-management files; only incidental copy such as `teammate@example.com` remains

---

#### Phase 8 — Tests + module.yml finalization (completed validation slice)

Complete the validation pass and reconcile the roadmap with the shipped orgs contract. The earlier Phase 8 checklist drifted from the repository: orgs coverage already lives across `test_adapters.py`, `test_admin.py`, `test_management_commands.py`, `test_middleware.py`, `test_models.py`, `test_permissions.py`, `test_views.py`, adjacent billing checkout tests, and CLI/core contract tests. This slice closes the remaining Phase 8 gaps without reopening deferred PostgreSQL RLS activation or seat-pricing work.

**Validated test inventory**:
- [x] `test_models.py` — `OrgRole` ordering, duplicate-membership DB constraint, personal-org idempotence, `Organization.is_personal` behavior, and the last-owner model guard
- [x] `test_permissions.py` — `require_org_role()` and `require_org_feature()` coverage across allowed and denied roles/states
- [x] `test_middleware.py` — solo personal-org bootstrap, SaaS no-membership redirect/403 behavior, `app.current_org_id` coverage in both runtime modes, and mode switching without model churn
- [x] `test_views.py` + `test_adapters.py` — signup routing, invitation flow, org management guardrails, and the last-owner view guard
- [x] `test_management_commands.py` + billing view/service coverage — org-authoritative billing bridge, org-scoped checkout routing, `migrate_billing_to_orgs`, and `promote_to_saas`
- [x] CLI/core contract tests — orgs module selectability, manifest/version alignment, and generated apply wiring

**Earlier pending items not required for this phase**:
- PostgreSQL RLS activation and cross-org queryset isolation remain a later milestone after downstream tenant tables gain concrete `organization_id` coverage
- Seat-pricing follow-ons (`Plan.max_seats`, `Plan.seat_price_id`, and related admin UI) remain Phase 6 follow-on work
- Cross-module migration dependency ordering remains a v0.86.0 release-note closeout task, not a blocker for this engineering validation slice

**`module.yml` shipped contract**:
```yaml
name: orgs
version: "0.86.0"
description: "Organizations and multi-tenant foundations with memberships and invitations"

config:
  mutable:
    mode:
      type: string
      default: "solo"
      django_setting: QUICKSCALE_MODE
      description: "Organization runtime mode (solo or saas)"
      validation:
        choices: ["solo", "saas"]
  immutable: {}

dependencies:
  - django-allauth>=65.14.1,<66.0.0

django_apps:
  - quickscale_modules_orgs

middleware:
  - quickscale_modules_orgs.middleware.TenantMiddleware

settings:
  ACCOUNT_ADAPTER: quickscale_modules_orgs.adapters.OrgsAccountAdapter
  QUICKSCALE_MODE: solo
```

**Acceptance criteria**:
- [x] The current orgs module test suite passes in the maintainer repo (`poetry run pytest -o addopts='' tests` in `quickscale_modules/orgs`)
- [x] The last-owner invariant is covered at both the model and view layers
- [x] `app.current_org_id` is asserted in both Solo and SaaS runtime coverage where middleware sets org context
- [x] Org-scoped recurring checkout success is covered alongside the existing org purchase checkout flow
- [x] Org module catalog, manifest alignment, and generated apply wiring contract tests pass in the maintainer repo (`poetry run pytest -o addopts='' quickscale_cli/tests/test_orgs_contract.py quickscale_cli/tests/test_module_manifest_contract.py quickscale_core/tests/test_module_wiring.py`)
- [x] The shipped `module.yml` remains authoritative; runtime-mode routing is validated by planner/apply wiring tests rather than a separate manifest `url_includes` block
- [x] Phase 8 closes without implementing deferred PostgreSQL RLS activation, seat-pricing fields, or release-note dependency-ordering work


#### Phase 9 — Billing wiring fix + regression guard

Harden the plan/apply pipeline against silent module omissions discovered during the v0.85.0 + v0.86.0 integration.

**Root causes (both fixed)**:
1. `_billing_wiring` was absent from `MODULE_WIRING_BUILDERS`, causing every project generated with billing selected to silently omit `quickscale_modules_billing` from `INSTALLED_APPS`, billing settings, and URL wiring. Both themes gate billing nav on `'quickscale_modules_billing' in settings.INSTALLED_APPS`, so billing links were hidden everywhere.
2. `quickscale_core.context_processors.installed_modules` was missing from `TEMPLATES.context_processors` in the generated `settings/base.py`. Without it, `modules.billing.url` in `index.html` rendered as `""`, which overrode the React default `/billing/pricing/` path, causing the billing link to navigate to `/` instead.

**Files modified**:
- [x] `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py` — added `_billing_wiring()` and registered `"billing": _billing_wiring` in `MODULE_WIRING_BUILDERS`
- [x] `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2` — added `quickscale_core.context_processors.installed_modules` to `TEMPLATES` context_processors so that `modules.billing.url` resolves in `index.html`
- [x] `quickscale_cli/tests/test_module_manifest_contract.py` — added `test_all_catalog_modules_have_wiring_builder()` regression guard: asserts every catalog module is either present in `MODULE_WIRING_BUILDERS` or has a documented special-case handler (currently only `social`)
- [x] `quickscale_core/tests/test_react_theme_integration.py` — added `test_generated_settings_registers_installed_modules_context_processor()` to `TestReactThemeBaseTemplate`

**Still open**:
- [ ] `quickscale_cli/src/quickscale_cli/commands/apply_command.py` — add `_sync_billing_env_example` alongside the existing notifications/analytics env-example sync (`STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `QUICKSCALE_BILLING_WEBHOOK_SECRET`)
- [ ] `quickscale_cli/tests/commands/test_module_wiring_specs_billing.py` (create) — unit tests for `_billing_wiring`: default settings, env-var normalization, app list, URL include prefix

**Acceptance criteria**:
- [x] `quickscale_modules_billing` appears in `MODULE_INSTALLED_APPS` of generated `settings/modules.py` when billing is selected
- [x] `test_all_catalog_modules_have_wiring_builder` added and passes — any future module added to the catalog without a wiring builder will fail this test immediately
- [x] `quickscale_core.context_processors.installed_modules` registered in generated `settings/base.py` — `test_generated_settings_registers_installed_modules_context_processor` added and passes
- [ ] Billing env-example block (`STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `QUICKSCALE_BILLING_WEBHOOK_SECRET`) present in generated `.env.example` after `quickscale apply`
- [ ] `_billing_wiring` unit tests pass

---

### v0.87.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack. Any blocking HTML contract corrections discovered in v0.83.0 belong to the hardening release; this later milestone is for optional polish after the shipped contract is stable again.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---
