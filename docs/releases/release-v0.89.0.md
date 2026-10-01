# QuickScale v0.89.0 — Development Maintenance

> **Release status:** prepared for the v0.89.0 development line, not published. No v0.89.0 tag,
> GitHub release, or package upload is implied by this note.

## Summary

Validation expectations now derive from their authoritative repository sources. Gate-parity tests
compute their counts from the gate registry and workflow declarations, while current-version tests
read the expected value from QuickScale package metadata. Adding a gate or bumping the repository
version therefore no longer requires a matching expectation-only patch.

Project-owned tenant models can now join classification and FORCE RLS policy refresh through the
marker-derived tenant contract. This keeps organization ownership and forced row-level security
requirements in place without requiring edits under embedded module source.

Organization purge now refuses to remove local data while a current Stripe-backed subscription, an
active subscription checkout reservation, or a preparing/open one-time purchase Checkout exists.
The command and its dry run reconcile hosted Checkout state and list live Stripe subscription IDs so
the operator can resolve provider state before retrying. Checkout, subscription, webhook, account
deletion, and purge provider transitions share an organization-scoped advisory mutex; local billing
row mutations also lock the organization row without placing Stripe calls in database transactions.

Purge coverage and dependency-sensitive child-before-parent order are now derived from the installed
tenant-model graph, including project-owned extension models. Each app declares the removal
obligations it owns on its own `AppConfig`, and purge and account deletion discharge the discovered
set through one shared coordinator that fails closed when a boundary skips a declared obligation; a
declared provider field refuses the purge while it carries a value unless the declaring module marks
it boundary-guarded and declares the guard, reconciliation, and provider-mutex hooks that decide its
liveness itself; an app-owned stage runs the declaring app's own hook; each removal boundary's owner
declares where its implementation lives; blog and CRM declare their purge-summary prefixes; and
account deletion records the data-removal steps it deliberately skips when an organization
survives.

Server-rendered auth, billing, blog, listings, and CRM pages now share the generated React theme's
design tokens and page shell. Their templates preserve Django-owned forms, URLs, sessions, and
module behavior while using the same colors, radii, controls, and light/dark state as the React
surface. DEBUG pages load `frontend/src/index.css` from Vite; non-DEBUG pages load the compiled
`static/frontend/assets/index.css`. The frontend architecture this depends on — the
`window.__QUICKSCALE__` seam, URL ownership between the React shell and module routes, the static
pipeline, and the template-inheritance rule — is documented in `docs/technical/frontend.md`.

## Adoption

A project-owned model inherits `TenantModel` (directly or through a module's abstract base) and
calls `apply_force_rls()` from its initial migration to install the exact pair required by
isolation checks: one tenant-only `FOR ALL` policy and its `<base>_select` operator-read
`FOR SELECT` policy. A `TenantManager` on a model that does not inherit `TenantModel` fails
startup.

Existing projects must manually adopt the current generated `templates/base.html`,
`templates/index.html`, generated
`templates/social/*.html` files, `frontend/vite.config.ts`, `<package>/settings/local.py`, and
`docker-compose.yml` before recording or acknowledging the v0.89.0 contract vintage. Together those files load
the canonical token stylesheet, keep Django-owned static paths on Django, expose the browser-facing
Vite port and optional full origin to Django, make React and module pages use the same live DEBUG
stylesheet, reject malformed origins and requests outside the exact Host derived from the host port
or configured origin, build assets before starting Vite, and probe that Host before starting the
backend. Run `pnpm dev` for DEBUG
pages and run
`pnpm build` before serving non-DEBUG pages. `quickscale update` and existing-project
`quickscale apply` do not rewrite these project-owned files.

A project that has overridden module page templates must also retain the current module block
structure — including `auth_content`, `billing_content`, `blog_content`, `listings_content`, or
`crm_content` where applicable — and compare each override with the current module template. An
override left on the wrong block can parse without error and render no page content.

## Compatibility

The validation-source changes affect repository tests only. The tenant-enrollment capability keeps
existing organization ownership and FORCE RLS requirements in place, but this release does rename
model-facing names: every organization-scoped model now inherits `TenantModel` (a `TenantManager` on
a model that does not inherit it fails startup), cross-module reverse accessors take the
`quickscale_<module>_<name>` form, and model choice constants become `TextChoices` members. A
project that reads an old reverse accessor or choice constant updates to the new name. Organization purge adds a fail-closed precondition but no new command-line
option; cancelled subscriptions remain purgeable, while any current row without a Stripe
subscription ID blocks purge and dry run until reconciled. An incomplete subscription or one-time
purchase Checkout reservation must reach provider-confirmed expiry first. Reconciliation runs
outside database transactions; completed subscription sessions retain their subscription identity
and block, while completed purchases block until their webhook has synchronized the local credit
ledger.
Project-owned tenant children no longer require vendored purge-command edits: their tenant marker
enrolls them, and installed FK metadata determines deletion order for both cascading and blocking
relationships. Removal obligations now declare on each app's `AppConfig`, so the module-level
`ORGANIZATION_REMOVAL_OBLIGATIONS` tuple and the `require_removal_action` /
`skipped_removal_obligations` helpers are replaced by the coordinator's stage discharge; a boundary
that finishes without discharging a declared obligation fails closed.

The shared-design change is an existing-project generated-file compatibility boundary, not only a
template-override change. Module Python APIs, URLs, form fields, sessions, and settings consumed by
the modules are unchanged, but DEBUG pages now require the generated shell, local Vite port/origin
settings, Vite static routing, and Compose frontend workflow described under Adoption. Contract
vintage enforcement blocks old or unknown projects before mutation and names the outstanding
generated-project steps; `--confirm-contract-adoption` records the adopted vintage in
`.quickscale/state.yml`, while `--acknowledge-contract-vintage` confirms completion for that
invocation only. Neither updates those files automatically.
`QUICKSCALE_FRONTEND_HOST_PORT` must be a canonical
decimal from 1 through 65535. A configured `QUICKSCALE_FRONTEND_ORIGIN` must be a
canonical HTTP(S) origin; malformed values fail startup. When it is blank, Django and Vite derive
`http://localhost:<QUICKSCALE_FRONTEND_HOST_PORT>`; Vite accepts only the effective origin's exact
Host in either case.

Managed module credential blocks in `.env.example` change on this line: an existing project that
enables `storage` or `backups` gains their credential placeholders on its next `apply`, while the
blocks for notifications, analytics, and billing keep their exact previous bytes so no spurious
diff appears for those. Fresh generations no longer carry a module-managed block until `apply`
writes it, and user-authored lines outside the managed markers are never rewritten.

Backup and restore commands now run under the TLS posture of the Django connection they actually
use: that connection's `sslmode`, `sslrootcert`, `sslcert`, `sslkey`, and `connect_timeout` reach
`pg_dump` and `pg_restore` as libpq environment variables instead of being dropped. This is a
deliberate behavior change — a deployment whose active connection requests strict TLS (the
`RUNTIME_DATABASE_URL` role connection while serving) will now fail its backup if the server cannot
satisfy that request, where it previously completed in plaintext. Operators who require verified TLS
must carry those parameters on `RUNTIME_DATABASE_URL`, not only on `DATABASE_URL`, and re-check that
URL after `quickscale deploy railway`, which rewrites the runtime URL on services it manages.

This maintenance release also adds maintainer-only beta-migration compatibility validation and
effective runtime provenance to report output; incompatible launcher, settings, and package
combinations now fail before recipient mutation, fresh-first identity changes reconcile raw and
derived slug/package values across the generated scaffold, and a run that completes its
verification stack writes a report-derived `MIGRATION_PROMPT.md` handoff into the recipient. Those
beta-migration-only additions do not themselves change generated-project output, public package
APIs, or upgrade requirements; the shared-design generated-file boundary is described above.

**Moved URLs.** The organizations module now serves its JSON API under its mount: `/api/orgs/...`
moves to `/orgs/api/...` (organization list/create at `/orgs/api/`, org-scoped endpoints under
`/orgs/api/<slug>/...`), and the slugless VIEW-AS exit moves from `/debug/exit/` to
`/orgs/debug/exit/`. The operator step is to update custom frontend code that calls
`/api/orgs/...`, any saved link or form that posted to `/debug/exit/`, and project-owned template
overrides that reverse the retired global orgs route names (`org-members-invite`,
`org-members-invitation-revoke`, `org-debug-exit`), which become the namespaced snake_case names
(`quickscale_orgs:members_invite`, `quickscale_orgs:members_invitation_revoke`,
`quickscale_orgs:debug_exit`). The module's HTML routes (org dashboard, members, settings,
invitation accept) keep their existing `/orgs/...` URLs, and no provider webhook endpoint changes.
The root dashboard route is removed, so the site root belongs to the project and the module's pages
live under `/orgs/`; the module now reserves the `api` slug, so an existing organization with that
slug must be renamed.

**Billing URLs.** The billing module's JSON API moves under its mount: `/api/billing/...` becomes
`/billing/api/...` (for example, `/api/billing/plans/` becomes `/billing/api/plans/`). The Stripe
webhook stays at `/billing/webhooks/stripe/` and the module's Django pages keep their existing
`/billing/...` URLs. The operator step is to update custom frontend code that calls
`/api/billing/...`, and to rename project-owned template overrides that reverse the retired
kebab-case billing route names (`billing-dashboard`, `pricing-page`, `stripe-webhook`, and the
rest), which become the namespaced snake_case names under `quickscale_billing:` (`dashboard`,
`pricing_page`, `stripe_webhook`, and the rest).

**CRM and forms URLs.** The crm module declares its `crm/` mount in its manifest and every route
name becomes snake_case under `quickscale_crm:` (`api_root`, `tag_list`, `contact_notes`,
`deal_bulk_update_stage`, and the rest); its Django page and JSON API keep their existing
`/crm/dashboard/` and `/crm/api/...` URLs. The forms module declares its `forms/` mount in its
manifest and its JSON API moves under it, path for path:

| Retired path | New path |
|---|---|
| `/api/forms/<slug>/` | `/forms/api/<slug>/` |
| `/api/forms/<slug>/submit/` | `/forms/api/<slug>/submit/` |
| `/api/admin/forms/` | `/forms/api/admin/forms/` |
| `/api/admin/forms/<id>/submissions/` | `/forms/api/admin/forms/<id>/submissions/` |
| `/api/admin/forms/<id>/submissions/<sub_id>/` | `/forms/api/admin/forms/<id>/submissions/<sub_id>/` |
| `/api/admin/forms/<id>/submissions/export/` | `/forms/api/admin/forms/<id>/submissions/export/` |

Its HTML pages keep their existing `/forms/...` URLs. The analytics dashboard route name also
becomes `quickscale_analytics:dashboard` (the retired `analytics-dashboard`), with the
`/analytics/` URL unchanged. The operator step is to update custom frontend code that calls the
retired `/api/forms/...` and `/api/admin/forms/...` paths, and to rename project-owned Django
templates and Python code that reverse the retired kebab-case crm, forms, and analytics route
names (`quickscale_crm:api-root`, `quickscale_crm:tag-list`, `quickscale_forms:form-submit`,
`quickscale_forms:admin-submission-export`, `quickscale_analytics:analytics-dashboard`, and the
rest) to their snake_case forms under `quickscale_crm:`, `quickscale_forms:`, and
`quickscale_analytics:`.

**Moved Python surface.** `require_org_feature` moves from `quickscale_modules_orgs.permissions`
to `quickscale_modules_billing.services`; project code that imports the decorator updates its
import path. `quickscale_modules_orgs.permissions.resolve_request_org` is the public name of the
request-organization resolver the gate uses, replacing the private `_resolve_request_org`.

## Delivery provenance

The SA195/SA192 delivery was synchronized with `v89` at
`6e8b24036bb26a74b585aa78cd9e53d54cd29e88`. It changes the shared module-test shell; the auth,
billing, blog, CRM, and listings templates and stylesheets; the generated React/Django shell,
frontend-origin settings, Vite proxy, and Compose workflow; their source/embedded module manifests;
the exact-emission fixture; focused contract and E2E coverage; and the corresponding changelog,
roadmap, frontend architecture, and user-manual documentation. No dependency was added.

The credential-contract derivation followed on the same line: the generated `.env.example` now
renders one managed block per enabled credential-bearing module from that module's declared
environment-variable options, the static notifications block left the template, and enabling
`storage` or `backups` adds their credential placeholders on the next `apply`. That changes the
fresh-generation `.env.example` bytes for every variant, so the hash row below is the current
emission; the other rows are the SA195/SA192 delivery's.

The frontend-startup resilience change followed later on the same line: the generated
`docker-compose.yml` frontend service now passes `--config.fetch-retries=5` to its `pnpm install`,
so a single stalled registry request does not abort the dev install and leave `quickscale up` with
a failed-to-start frontend. That changes the fresh-generation `docker-compose.yml` bytes for every
variant, so its hash row is also the current emission.

The exact-emission hashes below apply identically to `react_default`, `react_empty`, and
`react_selected`; all paths not listed remain unchanged in those manifests.

| Generated path | SHA-256 |
|---|---|
| `.env.example` | `e81448025b9c55d84a0770a205235ec004a2a15516da742474e63443dda3e265` |
| `README.md` | `1e1778dec8bd438dd06573df0204b20b63776bbfaf8bf587504e8ad697c57387` |
| `docker-compose.yml` | `147671e902ac3123931e8b9be1ccff80247db08f8a83211ed904a81519329148` |
| `frontend/src/test/viteAssetRouting.test.ts` | `c51b723eda4a3c84d70db43a6886c55a1fd5439ca08159b736af8e472124e016` |
| `frontend/vite.config.ts` | `f658677187822a51078f405f690a313a83900ffc654ad062e2be1763e176c82e` |
| `templates/base.html` | `dbc8e9669c906fab12f46cdc572e7e1bb0f6ec80ec040b22bba6ddcfcb7e2668` |
| `templates/index.html` | `c1023de5db28e87a76cb48635f4f03a05332f946e5541a785134fb24a33a34f0` |
| `templates/social/embeds.html` | `72c05317c6a7c507412b7a942ecc19abc1a0ae5272952aba0a4d03fe99e71f82` |
| `templates/social/link_tree.html` | `2c716821493cf08bf136438475979a0b1b122b340a67ecc7870b899df02577cb` |
| `testproject/settings/local.py` | `cb15c6d4bf76805285683dfa552843b62fb2d534e17ed2e8f1c94ece8f8189c9` |

`.env` is excluded from the hash table: it embeds the invoking host's `DOCKER_UID`/`DOCKER_GID`,
so the emission fixture pins only its presence and mode.

## Validation

The task-tier and release-tier validation commands for this prepared capability are:

```text
make check QUIET=1
make ci-e2e
make release-gate
```

This task-tier gate includes the registered beta-migration generated-project smoke check, its CLI
regression suite, and repository gate-parity checks. This note does not claim release-tier
validation, publication, or a v0.89.0 tag.
