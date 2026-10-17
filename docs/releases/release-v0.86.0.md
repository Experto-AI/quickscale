# Release v0.86.0 - Organizations Module

**Date:** 2026-05-22 · **Status:** ✅ Released

## Summary

v0.86.0 delivers the QuickScale organizations milestone and completes SaaS parity. The `quickscale_modules.orgs` module introduces multi-tenancy with a `QUICKSCALE_MODE` runtime switch between Solo mode (personal org auto-created, flat URLs) and SaaS mode (multi-org, `/orgs/<slug>/` routing, invitations). Billing models are extended with authoritative org ownership fields, plan-level feature gates gate downstream module access, and the billing wiring regression discovered during integration is permanently closed by a planner/apply guard test.

## Highlights

### Features

- **Organizations module (`quickscale_modules.orgs`)**: Ships `Organization`, `OrganizationMembership`, `OrganizationInvitation`, and the abstract `TenantModel` base. `OrganizationManager.create_personal_for(user)` is idempotent and used by Solo mode to auto-provision personal orgs on signup.
- **Solo and SaaS runtime modes**: `QUICKSCALE_MODE = 'solo'` (default) keeps flat routes with a personal org auto-created on signup. `QUICKSCALE_MODE = 'saas'` enables multi-org `/orgs/<slug>/` routing, org switcher, and self-service onboarding.
- **RBAC**: `require_org_role(min_role)` decorator and `OrgRoleMixin` enforce VIEWER/MEMBER/ADMIN/OWNER role hierarchy. `require_org_feature(feature_key)` gates downstream module access against `Plan.features` and returns 402 for absent features or missing subscriptions.
- **TenantMiddleware**: Resolves org context per request, sets `request.org`, and issues `SET LOCAL app.current_org_id = <uuid>` for future PostgreSQL RLS readiness. Exempt and non-org paths bypass the scoped branch.
- **Invitation flow**: ADMIN+ can invite by email with a 7-day UUID token. Accept path at `/orgs/invitations/<token>/accept/` handles auth continuation, normalized-email matching, expired/accepted/revoked token edge cases, and Solo-mode 404.
- **Billing bridge**: `Subscription`, `CreditBalance`, and `CreditTransaction` gain authoritative `organization` FK fields. `Plan.features` (JSONField) drives feature-gate checks. `migrate_billing_to_orgs` and `promote_to_saas` management commands handle existing-project migration.
- **React org pages**: Fresh `showcase_react` generations ship `OrgListPage`, `OrgCreatePage`, `OrgLayout`, `OrgDashboardPage`, `OrgMembersPage`, `OrgSettingsPage`, `OrgSwitcher`, and consolidated `useOrgs` hooks.

### Improvements

- **Billing wiring fix**: `_billing_wiring` was absent from `MODULE_WIRING_BUILDERS`, silently omitting billing from generated `INSTALLED_APPS`, settings, and URL wiring. Now fixed with a regression guard test.
- **Context processor fix**: `quickscale_core.context_processors.installed_modules` added to generated `settings/base.py` so `modules.billing.url` resolves correctly in `index.html`.
- **Last-owner invariant**: Enforced at both model save/delete time and view layer; the last OWNER cannot be demoted, removed, or have a second OWNER assigned without explicit transfer.
- **Superuser operator path**: Superusers can access org-scoped admin routes without a membership row; documented explicitly without assuming database-level RLS bypass.

## Breaking changes

- The `orgs` module is now auto-materialized alongside `billing` by the planner/apply pipeline; standalone billing projects should add `orgs` to their `quickscale.yml` module list.
- `Subscription.user` and `CreditBalance.user` are now nullable provenance-only fields; `organization` is the authoritative ownership field. Existing data is migrated by `python manage.py migrate_billing_to_orgs`.
- Org invitation URLs are slugless (`/orgs/invitations/<token>/accept/`) and Solo-mode returns 404 for all `/orgs/*` routes.

## Upgrade steps

1. Add the `orgs` module to `quickscale.yml` alongside `billing` and `auth`, then run `quickscale apply`.
2. Run `python manage.py migrate` to apply the billing org-ownership migration.
3. Run `python manage.py migrate_billing_to_orgs` to backfill authoritative org fields for existing billing rows.
4. To switch to SaaS mode, run `python manage.py promote_to_saas` to ensure all personal orgs have valid unique slugs, then set `QUICKSCALE_MODE = 'saas'` in your settings.
