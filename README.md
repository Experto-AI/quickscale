# QuickScale Organizations Module

Foundational multi-tenant data model for organization records, memberships, invitations, and
shared tenant ownership, giving later phases a stable base for Solo/SaaS runtime modes,
PostgreSQL row-level security, and org-scoped billing.

## Overview

- **Models**: `Organization`, `OrganizationMembership`, `OrganizationInvitation`,
  `OrganizationTombstone`, and the abstract `TenantModel` base that every organization-scoped
  model inherits.
- **Runtime modes**: `solo` (single-tenant; each user gets a personal organization
  automatically) and `saas` (explicit organizations with a selected active organization).
- **Tenant scoping**: `TenantManager` filters by the current organization and fails closed when
  no organization context is set; `all_objects` is the operator super-scope.
- **URL surfaces**: a flat, prefix-less URLconf with organization pages, debug VIEW-AS routes,
  and a DRF JSON organization/membership API that answers the shared
  `{"error": {"code", "message", "fields"}}` error shape.
- **Removal machinery**: organization purge and account deletion discharge declared removal
  obligations through one shared coordinator.
- `orgs` requires `auth`; QuickScale does not support a standalone orgs install.

## Configuration

The module declares the option below in `module.yml`; `quickscale plan` and `quickscale apply`
write it to the generated settings, and `quickscale.yml` carries the desired value.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_ORGS_ENABLED` | Mount the module's organization pages and API. Off keeps the app, its data, the tenant middleware, and the admin installed but mounts none of its organization URLs in either mode; an installed module that lists `orgs` in `required_modules` (auth, billing, blog, crm, listings, social) makes `apply` refuse the switch. |
| `mode` | string | `solo` | `QUICKSCALE_ORGS_MODE` | Organization runtime mode: `solo` or `saas`. |

In `solo` mode the module creates and serves each user's personal organization; the
organization API and the leaf organization pages answer `404`. In `saas` mode organizations are
explicit, the middleware resolves the active organization from the session, and the API and
organization pages are served. The module's manifest mounts it at `orgs/`: in solo mode before the
project's home route, in saas mode after it.

## Public surface

### Models and managers

- `Organization`, `OrganizationMembership`, `OrganizationInvitation`, and
  `OrganizationTombstone`.
- `TenantModel`, the abstract base that owns the `organization` foreign key, the
  `objects` / `all_objects` `TenantManager` pair, and `base_manager_name`.
- `TenantManager` fails closed (`none()`) when no organization is in context;
  `OrganizationManager` provides the System-organization helpers.

### Permissions

`permissions.py` publishes the role guards and the request-organization resolver used by
org-scoped views and APIs:

- `user_has_org_role(user, organization, min_role)`.
- `require_org_role(min_role)`, a decorator for function views.
- `OrgRoleMixin`, a class-based-view mixin with a configurable `min_org_role`.
- `HasOrgRole(min_role)`, the DRF permission class for JSON endpoints; it resolves the request's
  organization the same way and delegates to `user_has_org_role`, refusing a request with no
  organization context. Superusers pass as the operator path, matching `user_has_org_role`.
- `resolve_request_org(request, route_kwargs)`, which returns the request's organization from
  the active context or the routed `org_slug`.

### Tenancy helpers

`tenancy.py` publishes the migration and runtime helpers tenant modules use:
`tenant_org_fk()`, `apply_force_rls()`, `revert_force_rls()`, `refresh_force_rls_policies()`,
and `get_tenant_models()`. The module also installs the always-on RLS boot guard through its
`checks.py`; the shipped-module parity registry `TENANT_TABLE_REGISTRY` is test-owned
(Module Conventions rule 34).

### Current organization

`current_org.py` publishes the execution-context surface:

- `org_scope()` and `operator_access()` context managers.
- `get_current_org()` / `get_current_org_id()` / `set_current_org_id()`.
- `get_client_ip()` and `ClientIPThrottleMixin`, used by module throttles.

### Other public surfaces

- `sanitization.py` publishes `sanitize_href()` and `sanitize_rendered_html()`; blog and
  listings render user-authored links through them.
- `public_context.py` publishes `PublicSystemOrgReadMixin` for public reads that resolve the
  System organization.
- `views.py` publishes `OrgApiBaseView`, the sanctioned organization-role JSON API base: a DRF
  `APIView` with session authentication (CSRF enforced), `min_org_role` access gating, and
  JSON-only rendering, so every org API error answers the one QuickScale shape and anonymous
  callers keep their `401` challenge.
- `signals.py` sends `organization_created` when an organization is created.
- `middleware.py` installs `TenantMiddleware`, which resolves `request.org` per request,
  redirects users without an active organization in saas mode, and skips the org-management
  paths.
- Template tags: `{% load quickscale_orgs_debug %}` exposes the superuser-only
  `debug_as_active` tag for VIEW-AS sessions.
- Admin: `OrganizationAdmin` (with its VIEW-AS entry points), `OrganizationMembershipAdmin`,
  and `OrganizationInvitationAdmin`, plus the reusable `TenantModelAdmin` base other modules
  register their tenant models on.
- `removal.py` publishes the removal contract: `RemovalAction`, `RemovalBoundary`,
  `RemovalCoordinator`, `OrganizationRemovalObligation`, and `ExternalProviderField`, with the
  declaration helpers each owning app uses.
- `apps.py` declares orgs' own capabilities (Module Conventions rule 4): the organization-aware
  post-login and post-signup redirect hooks auth's allauth adapter collects, and the
  `social-cache-state` obligation executor, which clears the organization-scoped cache keys
  installed modules declare through `organization_cache_keys`.
- `services.py` re-exports `OrgsError` and `CurrentOrgError`, the module's error surface
  (Module Conventions rules 4 and 23); the org lifecycle operations stay in the module's own
  views and forms.

## URLs

The module's mount (`orgs/`) lives only in the manifest's `url_includes` wiring projection, and
every route name is snake_case under the `quickscale_orgs` namespace. The `api` slug is reserved
for the module's API: creating or renaming an organization to it is refused.

| Route name | Path | Purpose |
|------------|------|---------|
| `quickscale_orgs:index` | `orgs/` | Organization list (saas only) |
| `quickscale_orgs:new` | `orgs/new/` | Create an organization (saas only) |
| `quickscale_orgs:invitation_accept` | `orgs/invitations/<uuid:token>/accept/` | Accept an invitation |
| `quickscale_orgs:detail` | `orgs/<slug>/` | Organization dashboard (saas only) |
| `quickscale_orgs:members` | `orgs/<slug>/members/` | Member list (saas only) |
| `quickscale_orgs:members_invite` | `orgs/<slug>/members/invite/` | Invite a member (saas only) |
| `quickscale_orgs:members_invitation_revoke` | `orgs/<slug>/members/invitations/<uuid>/revoke/` | Revoke an invitation (saas only) |
| `quickscale_orgs:settings` | `orgs/<slug>/settings/` | Organization settings (saas only) |
| `quickscale_orgs:debug_view_as` | `orgs/<slug>/debug/view-as/` | Superuser VIEW-AS entry |
| `quickscale_orgs:debug_exit` | `orgs/<slug>/debug/exit/` | Exit VIEW-AS |
| `quickscale_orgs:debug_exit_root` | `orgs/debug/exit/` | Exit VIEW-AS from the root |
| `quickscale_orgs:api_list_create` | `orgs/api/` | Organization list/create API (saas only) |
| `quickscale_orgs:api_detail` | `orgs/api/<slug>/` | Organization detail API (saas only) |
| `quickscale_orgs:api_members` | `orgs/api/<slug>/members/` | Member list API (saas only) |
| `quickscale_orgs:api_members_invite` | `orgs/api/<slug>/members/invite/` | Invite API (saas only) |
| `quickscale_orgs:api_members_role` | `orgs/api/<slug>/members/<int>/role/` | Change a member role (saas only) |
| `quickscale_orgs:api_members_remove` | `orgs/api/<slug>/members/<int>/remove/` | Remove a member (saas only) |
| `quickscale_orgs:api_members_invitation_revoke` | `orgs/api/<slug>/members/invitations/<uuid>/revoke/` | Revoke an invitation (saas only) |
| `quickscale_orgs:api_settings` | `orgs/api/<slug>/settings/` | Organization settings API (saas only) |

## Management commands

- `quickscale_orgs_purge_organization` — purge an organization and all owned rows across all
  modules. Use `--organization-id <uuid>` for destructive execution and `--slug <slug>` for a
  non-destructive preflight; destructive execution and `--dry-run` are refused while a current
  Stripe-backed subscription, a pending subscription checkout, or a preparing/open one-time
  purchase checkout exists.
- `quickscale_orgs_promote_to_saas` — normalize every personal organization to a valid unique
  slug and print the required `QUICKSCALE_ORGS_MODE` SaaS setting change.
- `quickscale_orgs_check_tenant_isolation` — discover tenant models by `TenantModel`
  inheritance across all installed apps and verify each has `organization_id` plus conformant
  FORCE RLS policies.

## Operations

### Organization purge

`quickscale_orgs_purge_organization` refuses both destructive execution and `--dry-run` while
the organization has a current Stripe-backed subscription, a pending subscription checkout, or
a preparing/open one-time purchase checkout. Before opening the purge transaction it asks
billing to reconcile hosted checkouts with Stripe: only a provider-confirmed expired session
becomes purgeable, while a completed or open session remains blocked and a purchase whose
creation outcome is unknown requires provider reconciliation. Dry-run inspects provider state
without persisting it; destructive execution persists reconciliation before purge. Billing
provider operations and purge share an organization-keyed PostgreSQL advisory mutex; local
billing writes separately lock the organization row, and Stripe calls remain outside database
transactions.

The command derives its tenant-row coverage and child-before-parent deletion order from
installed tenant-model and foreign-key metadata, with explicit overrides available for
relationships metadata cannot express. Each app declares the removal obligations it owns on its
own `AppConfig` — billing's provider state, orgs' tenant-row, social-cache, and tombstone
obligations — and both purge and account deletion discharge the discovered set through one
shared coordinator that fails closed when a boundary finishes without discharging a declared
obligation. A declared provider field refuses the purge while it carries a value unless the
declaring module marks that field boundary-guarded and decides liveness itself; an app-owned
stage (cache invalidation, provider reconciliation) runs the declaring app's own hook, and a
declaration without its executor hook fails the orgs system check. Account deletion reconciles
billing outside its database transaction and records the data-removal obligations deliberately
skipped when organization data is retained.

### Tenant isolation

Run `quickscale_orgs_check_tenant_isolation` in CI or before a release: it fails when a tenant
model lacks `organization_id` or its FORCE RLS policies deviate from the tenant-write and
operator-read contract. The orgs RLS boot guard refuses a superuser or BYPASSRLS database
connection except for the guarded one-shot `migrate` command; serve under a restricted role
(NOSUPERUSER, NOBYPASSRLS).

### Mode changes

Promote a solo project to saas with `quickscale_orgs_promote_to_saas`, then set
`QUICKSCALE_ORGS_MODE` to `saas` as the command's output directs. Purging an organization is the
supported removal path; organization data cannot be silently dropped.

## Extending

- A project-owned tenant model subclasses `TenantModel` (directly or through a module abstract
  base), ships its own FORCE RLS migration through `apply_force_rls`, and classifies every
  non-relational `*_id` field in `provider_id_classification` (`provider-backed` or
  `not-provider-backed`). The purge refuses while any row of the organization carries a value
  in a provider-backed field, naming the field, and the orgs system check fails on any `*_id`
  field that neither a declared obligation nor its model classifies. See
  [module-extension.md](../../docs/technical/module-extension.md#project-owned-tenant-models).
- An app that owns organization-scoped data declares its removal obligations on its
  `AppConfig` so purge and account deletion discharge them without orgs knowing the app. A
  module that owns organization-scoped cache state also declares its keys through the
  `organization_cache_keys` capability, so the purge clears them without orgs knowing the key
  shapes.
