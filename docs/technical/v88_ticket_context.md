# Ticket Context — Concepts and Implementation Notes

> **Terminal remediation status (2026-09-10):** SA160's generated CSRF transport and TA67's
> duplicate-cookie parity were corrected after the previously green release aggregate. That run is
> historical evidence for the prior bytes only. Fresh release-tier evidence must bind the corrected
> exact candidate before SA160 or TA67 is closed again; the corrections are not merge-ready on the
> historical verdict.

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Ticket Context**
> **Related docs**: [Roadmap](roadmap.md) | [Decisions](decisions.md) | [Validation Policy](validation_policy.md) | [Module Extension Contract](module-extension.md)

The [roadmap](roadmap.md) owns task scope, tracks, dependencies, scheduling, and acceptance.
This companion explains implementation rationale. Read the corresponding roadmap task first;
completed work and historical evidence belong in [CHANGELOG.md](../../CHANGELOG.md).

## SA152 — Exercise beta migration and check compatibility within each mode

The maintainer migration commands need a complete smoke exercise. Their flag and ownership
unit tests cannot establish that a donor project produces a working recipient. Reconcile the
workflow with the fresh-database upgrade contract, register the smoke in the gate layer, and
update the migration playbook to describe the actual `quickscale_devtools` implementation.
Missing template roots must fail the ownership conformance check instead of skipping it.

Launcher and settings compatibility is part of this exercise. `settings/production.py`,
`start.sh`, and `Dockerfile` participate in one privilege-selection contract, but the
`FRESH_FIRST_*` and `IN_PLACE_*` constants describe different migration modes. Comparing their
memberships as though they were one execution path does not prove incompatibility.

For each supported mode, trace which version of each file actually reaches the recipient and
define the resulting compatibility condition. Test that a compatible recipient works and that an
incompatible launcher/settings combination fails clearly. Preserve donor deployment settings
where the mode promises to preserve them; do not require identical file dispositions merely
because files participate in one contract. Ownership manifests and taxonomy redesign need
separate evidence of need.

## SA180 — Compute the gate-parity count oracles instead of pinning them

Several gate-parity assertions compare against hand-written integers: how many gates exist, how
many provisioning stations, how many hosted jobs. Each is a copy of a fact that lives somewhere
else, so every addition needs a matching hand edit, and a forgotten edit either fails loudly for
an unrelated reason or, worse, keeps passing against the stale number.

The written trigger for acting on this was more than two such edits. Historical review found that
two separate changes each crossed it, so the trigger has fired and the item is now owned work
rather than an observation. Correcting the surrounding documentation, as the command-set and
allowlist work did, does not discharge it.

Derive each count from the source it describes — the registry entries, the workflow job set, the
station list — so the assertion cannot drift from reality. Keep the closed-universe check, which
already makes an unregistered job loud, and keep the existing failure messages specific. A
regression that adds a gate and observes the derived count follow it is the evidence that closes
the watch item.

## SA177 — Verify RLS policy predicates

RLS enabled, RLS forced, and a row in `pg_policies` do not prove tenant isolation: a permissive
`USING (true)` policy can satisfy all three. The intended contract scopes writes to the current
organization and permits cross-tenant reads only with the operator flag. Operator access belongs
to a `FOR SELECT` policy so it cannot expand write or delete visibility.

Compare the database's `qual` and `with_check` expressions with the rendered policy contract for
every enrolled table, accounting for PostgreSQL's expression representation. Use a live database
and a negative control that weakens a predicate and is rejected. This checks policy meaning in
addition to SA172's accepted application and table-resolution behavior.

## SA153 — Launch the property portal through a project-owned extension

`listings` provides `AbstractListing`, but its shipped views, URLs, admin registration, and
filters target the concrete `Listing`. A property subclass therefore needs project-owned public
views, URLs, and filters under the documented [extension contract](module-extension.md).
Use that extension path to launch `buenosairesproperties.com` and let working project needs
inform later reusable module changes.

The launch needs property fields and galleries, explicit currency labels, attribute filtering
and keyword search, Spanish public pages, listing-linked inquiries into `crm`, and launch SEO
including metadata, sitemap, and robots guidance. Django templates provide one public presentation
path. Currency labels must not imply exchange-rate conversion, and Spanish launch coverage does
not require translating every QuickScale interface.

Every new child table, including gallery images, must carry its own `organization_id` and RLS
policy under the child-table decision in [decisions.md](decisions.md). Match the existing
`test_rls_boundary.py` coverage pattern and verify tenant isolation across public presentation
and inquiry handling.

A public JSON API and generic support requiring no project-owned views belong in the optional
inventory until a concrete consumer justifies them.

## SA154 — Evaluate optional property-portal capabilities

The inventory includes a public JSON API, reusable generalization of proven property-extension
and presentation code, maps and geocoding, saved searches and alerts, agent and office profiles,
syndication feeds, virtual tours, featured placement tied to billing credits, blog/listing links,
and PostgreSQL full-text search.

Promote a capability only with a concrete consumer, bounded acceptance criteria, and evidence
that it improves the working portal. Public API design and generic extension work should follow
the actual project contracts they need to support.
