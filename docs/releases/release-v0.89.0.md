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
tenant-model graph, including project-owned extension models. Purge and account deletion consume
one named removal-obligation contract for billing reconciliation, tenant rows, social caches, and
tombstones; account deletion records the data-removal steps it deliberately skips when an
organization survives.

Server-rendered auth, billing, blog, listings, and CRM pages now share the generated React theme's
design tokens and page shell. Their templates preserve Django-owned forms, URLs, sessions, and
module behavior while using the same colors, radii, controls, and light/dark state as the React
surface. DEBUG pages load `frontend/src/index.css` from Vite; non-DEBUG pages load the compiled
`static/frontend/assets/index.css`. The frontend architecture this depends on — the
`window.__QUICKSCALE__` seam, URL ownership between the React shell and module routes, the static
pipeline, and the template-inheritance rule — is documented in `docs/technical/frontend.md`.

## Adoption

A project-owned model declares the tenant-manager contract and calls `apply_force_rls()` from its
initial migration to install the exact pair required by isolation checks: one tenant-only `FOR ALL`
policy and its `<base>_select` operator-read `FOR SELECT` policy. A project-owned `AbstractListing`
subclass declares both the tenant-scoped and super-scope managers before running those checks.

Existing projects that install or update auth, billing, blog, listings, or CRM must manually adopt
the current generated `templates/base.html`, `templates/index.html`, generated
`templates/social/*.html` files, `frontend/vite.config.ts`, `<package>/settings/local.py`, and
`docker-compose.yml` before acknowledging the v0.89.0 contract vintage. Together those files load
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
existing organization ownership and FORCE RLS requirements in place without changing package APIs
or upgrade requirements. Organization purge adds a fail-closed precondition but no new command-line
option; cancelled subscriptions remain purgeable, while any current row without a Stripe
subscription ID blocks purge and dry run until reconciled. An incomplete subscription or one-time
purchase Checkout reservation must reach provider-confirmed expiry first. Reconciliation runs
outside database transactions; completed subscription sessions retain their subscription identity
and block, while completed purchases block until their webhook has synchronized the local credit
ledger.
Project-owned tenant children no longer require vendored purge-command edits: their tenant marker
enrolls them, and installed FK metadata determines deletion order for both cascading and blocking
relationships.

The shared-design change is an existing-project generated-file compatibility boundary, not only a
template-override change. Module Python APIs, URLs, form fields, sessions, and settings consumed by
the modules are unchanged, but DEBUG pages now require the generated shell, local Vite port/origin
settings, Vite static routing, and Compose frontend workflow described under Adoption. Contract
vintage enforcement blocks old or unknown projects before mutation; passing
`--acknowledge-contract-vintage` confirms that the operator completed every listed manual step and
does not update those files automatically. `QUICKSCALE_FRONTEND_HOST_PORT` must be a canonical
decimal from 1 through 65535. A configured `QUICKSCALE_FRONTEND_ORIGIN` must be a
canonical HTTP(S) origin; malformed values fail startup. When it is blank, Django and Vite derive
`http://localhost:<QUICKSCALE_FRONTEND_HOST_PORT>`; Vite accepts only the effective origin's exact
Host in either case.

This maintenance release also adds maintainer-only beta-migration compatibility validation and
mode-specific runtime provenance to report output; incompatible launcher, settings, and package
combinations now fail before recipient mutation, and fresh-first identity changes reconcile raw
and derived slug/package values across the generated scaffold. Those beta-migration-only additions
do not themselves change generated-project output, public package APIs, or upgrade requirements;
the shared-design generated-file boundary is described above.

## Delivery provenance

The SA195/SA192 delivery was synchronized with `v89` at
`6e8b24036bb26a74b585aa78cd9e53d54cd29e88`. It changes the shared module-test shell; the auth,
billing, blog, CRM, and listings templates and stylesheets; the generated React/Django shell,
frontend-origin settings, Vite proxy, and Compose workflow; their source/embedded module manifests;
the exact-emission fixture; focused contract and E2E coverage; and the corresponding changelog,
roadmap, frontend architecture, and user-manual documentation. No dependency was added.

The exact-emission hashes below apply identically to `react_default`, `react_empty`, and
`react_selected`; all paths not listed remain unchanged in those manifests.

| Generated path | SHA-256 |
|---|---|
| `.env` | `04da07b92d64dc5c800229b93b2dfc9904e0a529d9e403fafe4a00a25fe79d9b` |
| `.env.example` | `e7ec92216acad33ac5d3ce7d4eb1d445fe7cdcb60780e391225c859dec3b4fc1` |
| `README.md` | `1e1778dec8bd438dd06573df0204b20b63776bbfaf8bf587504e8ad697c57387` |
| `docker-compose.yml` | `d5aa48c237cb4148e87a6fa0bfc8e0395160be18c4f0b9da1d512d58dc24dfc3` |
| `frontend/src/test/viteAssetRouting.test.ts` | `c51b723eda4a3c84d70db43a6886c55a1fd5439ca08159b736af8e472124e016` |
| `frontend/vite.config.ts` | `f658677187822a51078f405f690a313a83900ffc654ad062e2be1763e176c82e` |
| `templates/base.html` | `dbc8e9669c906fab12f46cdc572e7e1bb0f6ec80ec040b22bba6ddcfcb7e2668` |
| `templates/index.html` | `c1023de5db28e87a76cb48635f4f03a05332f946e5541a785134fb24a33a34f0` |
| `templates/social/embeds.html` | `72c05317c6a7c507412b7a942ecc19abc1a0ae5272952aba0a4d03fe99e71f82` |
| `templates/social/link_tree.html` | `2c716821493cf08bf136438475979a0b1b122b340a67ecc7870b899df02577cb` |
| `testproject/settings/local.py` | `cb15c6d4bf76805285683dfa552843b62fb2d534e17ed2e8f1c94ece8f8189c9` |

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
