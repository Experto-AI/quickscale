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

Server-rendered module pages share one page shell. The blog, listings, and CRM base templates
extend the project's `base.html` rather than emitting their own HTML document, so those pages
inherit the site topbar, messages, and footer instead of restating a shell each. The frontend
architecture this depends on — the `window.__QUICKSCALE__` seam, URL ownership between the React
shell and module routes, the static pipeline, and the template-inheritance rule — is now written
down in `docs/technical/frontend.md`.

## Adoption

A project-owned model declares the tenant-manager contract and calls `apply_force_rls()` from its
initial migration to install the exact pair required by isolation checks: one tenant-only `FOR ALL`
policy and its `<base>_select` operator-read `FOR SELECT` policy. A project-owned `AbstractListing`
subclass declares both the tenant-scoped and super-scope managers before running those checks.

A project that has **overridden** `quickscale_modules_blog/blog/*.html`,
`quickscale_modules_listings/listings/*.html`, or `quickscale_modules_crm/crm/*.html` renames the
content block in its override to the module block — `blog_content`, `listings_content`, or
`crm_content`. An override left on `{% block content %}` renders empty, because the module base
template now occupies that block itself. A project that overrode a module *base* template keeps
its standalone document and is unaffected until it adopts the new base.

New server-rendered module surfaces extend `base.html` and use only the blocks it already defines
(`title`, `extra_css`, `content`, `extra_js`), so they render correctly in projects generated
before this release. They wrap their page content in a `<div class="<module>-content">` and scope
the module stylesheet's spacing rules to it, because `base.html` applies a reset that zeroes
default margins.

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

The shared-shell change is **breaking for template overrides only**, in the way described under
Adoption; module Python APIs, URLs, and settings are unchanged. Blog and listings stylesheets keep
their existing rules; CRM page styling moved from an inline `<style>` block to
`quickscale_modules_crm/crm.css`, so a project that copied those inline rules keeps its copy and
takes no action.

This maintenance release adds maintainer-only beta-migration compatibility validation and
mode-specific runtime provenance to report output; incompatible launcher, settings, and package
combinations now fail before recipient mutation, and fresh-first identity changes reconcile raw
and derived slug/package values across the generated scaffold. It does not change
generated-project output, public package APIs, or upgrade requirements.

## Validation

The task-tier validation command for this prepared capability is:

```text
make check QUIET=1
```

This task-tier gate includes the registered beta-migration generated-project smoke check, its CLI
regression suite, and repository gate-parity checks. This note does not claim release-tier
validation, publication, or a v0.89.0 tag.
