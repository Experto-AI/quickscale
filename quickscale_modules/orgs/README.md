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
  and a JSON organization/membership API.
- **Removal machinery**: organization purge and account deletion discharge declared removal
  obligations through one shared coordinator.
- `orgs` requires `auth`; QuickScale does not support a standalone orgs install.

## Configuration

The module declares the option below in `module.yml`; `quickscale plan` and `quickscale apply`
write it to the generated settings, and `quickscale.yml` carries the desired value.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `mode` | string | `solo` | `QUICKSCALE_MODE` | Organization runtime mode: `solo` or `saas`. |

In `solo` mode the module creates and serves each user's personal organization; the
organization API and the leaf organization pages answer `404`. In `saas` mode organizations are
explicit, the middleware resolves the active organization from the session, and the API and
organization pages are served. The generated project mounts the module at the root: in solo
mode before the home route, in saas mode after it.

## Public surface

### Models and managers

- `Organization`, `OrganizationMembership`, `OrganizationInvitation`, and
  `OrganizationTombstone`.
- `TenantModel`, the abstract base that owns the `organization` foreign key, the
  `objects` / `all_objects` `TenantManager` pair, and `base_manager_name`.
- `TenantManager` fails closed (`none()`) when no organization is in context;
  `OrganizationManager` provides the System-organization helpers.

### Permissions

`permissions.py` publishes the role guards used by org-scoped views and APIs:

- `user_has_org_role(user, organization, min_role)`.
- `require_org_role(min_role)`, a decorator for function views.
- `OrgRoleMixin`, a class-based-view mixin with a configurable `min_org_role`.
- `require_org_feature(feature_key)`, which returns `402` when the organization's active
  billing plan lacks the feature key.

### Tenancy helpers

`tenancy.py` publishes the migration and runtime helpers tenant modules use:
`tenant_org_fk()`, `apply_force_rls()`, `revert_force_rls()`, `refresh_force_rls_policies()`,
`get_tenant_models()`, and the `TENANT_TABLE_REGISTRY`. The module also installs the
always-on RLS boot guard through its `checks.py`.

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

## URLs

The module has no `app_name`; its route names are global and it is mounted at the project root.

| Route name | Path | Purpose |
|------------|------|---------|
| `org-home` | `` (root) | Organization dashboard; served in both modes |
| `org-index` | `orgs/` | Organization list (saas only) |
| `org-new` | `orgs/new/` | Create an organization (saas only) |
| `org-invitation-accept` | `orgs/invitations/<uuid:token>/accept/` | Accept an invitation |
| `org-detail` | `orgs/<slug>/` | Organization dashboard (saas only) |
| `org-members` | `orgs/<slug>/members/` | Member list (saas only) |
| `org-members-invite` | `orgs/<slug>/members/invite/` | Invite a member (saas only) |
| `org-members-invitation-revoke` | `orgs/<slug>/members/invitations/<uuid>/revoke/` | Revoke an invitation (saas only) |
| `org-settings` | `orgs/<slug>/settings/` | Organization settings (saas only) |
| `org-debug-view-as` | `orgs/<slug>/debug/view-as/` | Superuser VIEW-AS entry |
| `org-debug-exit` | `orgs/<slug>/debug/exit/` | Exit VIEW-AS |
| `org-debug-exit-root` | `debug/exit/` | Exit VIEW-AS from the root |
| `org-api-list-create` | `api/orgs/` | Organization list/create API (saas only) |
| `org-api-detail` | `api/orgs/<slug>/` | Organization detail API (saas only) |
| `org-api-members` | `api/orgs/<slug>/members/` | Member list API (saas only) |
| `org-api-members-invite` | `api/orgs/<slug>/members/invite/` | Invite API (saas only) |
| `org-api-members-role` | `api/orgs/<slug>/members/<int>/role/` | Change a member role (saas only) |
| `org-api-members-remove` | `api/orgs/<slug>/members/<int>/remove/` | Remove a member (saas only) |
| `org-api-members-invitation-revoke` | `api/orgs/<slug>/members/invitations/<uuid>/revoke/` | Revoke an invitation (saas only) |
| `org-api-settings` | `api/orgs/<slug>/settings/` | Organization settings API (saas only) |

## Management commands

- `quickscale_orgs_purge_organization` — purge an organization and all owned rows across all
  modules. Use `--organization-id <uuid>` for destructive execution and `--slug <slug>` for a
  non-destructive preflight; destructive execution and `--dry-run` are refused while a current
  Stripe-backed subscription, a pending subscription checkout, or a preparing/open one-time
  purchase checkout exists.
- `quickscale_orgs_promote_to_saas` — normalize every personal organization to a valid unique
  slug and print the required `QUICKSCALE_MODE` SaaS setting change.
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
`QUICKSCALE_MODE` to `saas` as the command's output directs. Purging an organization is the
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
  `AppConfig` so purge and account deletion discharge them without orgs knowing the app.
