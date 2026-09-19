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

Organization purge now refuses to remove local data while a current Stripe-backed subscription
still exists. The command and its dry run list the live Stripe subscription IDs so the operator can
cancel them before retrying.

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
stylesheet, build assets before starting Vite, and wait for the stylesheet before starting the
backend. Run `pnpm dev` for DEBUG pages and run
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
option; cancelled subscriptions and current rows without a Stripe subscription ID remain purgeable.

The shared-design change is an existing-project generated-file compatibility boundary, not only a
template-override change. Module Python APIs, URLs, form fields, sessions, and settings consumed by
the modules are unchanged, but DEBUG pages now require the generated shell, local Vite port/origin
settings, Vite static routing, and Compose frontend workflow described under Adoption. Contract
vintage enforcement blocks old or unknown projects before mutation; passing
`--acknowledge-contract-vintage` confirms that the operator completed every listed manual step and
does not update those files automatically.

This maintenance release adds maintainer-only beta-migration compatibility validation and
mode-specific runtime provenance to report output; incompatible launcher, settings, and package
combinations now fail before recipient mutation, and fresh-first identity changes reconcile raw
and derived slug/package values across the generated scaffold. It does not change
generated-project output, public package APIs, or upgrade requirements.

## Validation

The task-tier and release-tier validation commands for this prepared capability are:

```text
make check QUIET=1
make ci-e2e
make release-gate
```

The task-tier gate includes the registered beta-migration generated-project smoke check, its CLI
regression suite, and repository gate-parity checks. This note does not claim completed
release-tier validation, publication, or a v0.89.0 tag.

## Deferred scope

Derived purge membership and shared account-deletion obligations remain deferred. The live Stripe
subscription refusal is implemented independently of those broader changes.
