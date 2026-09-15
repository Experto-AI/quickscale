# Ticket Context — Concepts and Implementation Notes

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

## SA184 — Treat the live Railway environment as the source of truth

`quickscale deploy railway` is designed to be re-run, and the Railway guide recommends re-running
it. The runtime-role work made the database password survive re-runs, but `SECRET_KEY` is still
regenerated each time, which logs everyone out and invalidates signed links. The same step turns an
unreadable variable listing into an empty mapping, and an ambiguous Postgres service listing into
a guessed name. Both violate Fail-Hard: a transient CLI failure becomes a rotated database
credential that breaks the still-serving deployment when its pooled connections recycle.

The shared cause is that deploy reconstructs configuration instead of reconciling with state it
has read successfully. Read first, refuse when the read fails, and generate a secret only when the
live environment genuinely has none.

## SA185 — Make the recorded contract vintage binding

Some runtime contracts are split: one half is an emitted file frozen at generation
(`settings/production.py`, `start.sh`, the `Dockerfile`), and the other half ships in code that users
upgrade — CLI releases and module subtree pulls through `quickscale update`. v0.88 changed two such
contracts in a skew-unsafe way: the privileged-command set and the runtime role that `deploy
railway` now expects `start.sh` to create. A pre-0.88 project that updates `orgs` or deploys with
the new CLI breaks.

The machinery to detect this already exists: `project_contract` is recorded at apply, and manifests
may declare `contract_vintage`. Only `quickscale status` reads it, and `orgs` declares none. Declare
the vintage the 0.88 templates need, and make the paths that apply upgradable code consult the same
check and refuse unless acknowledged. The client-identity resolver, which fails closed without its
generated middleware, is the skew-safe shape to point future contract changes toward. This is an
enforcement check, not a template updater.

## SA186 — A lease is only safe against a tip someone actually reviewed

Force-with-lease prevents overwriting a remote commit nobody observed. `--publish-all` observes the
remote tip and immediately feeds it to the lease, so the lease only guards the moment between
observation and push. Publishing from an older worktree then force-overwrites newer split branches
with older bytes, and consumers verifying module code from split refs get stale modules. Because
`git subtree split` is deterministic, a legitimate republish always fast-forwards; an ancestry check
costs nothing on the happy path and stops exactly the overwrite the lease was meant to prevent.

## SA187 — Constant-time comparisons reject non-ASCII strings

`secrets.compare_digest` and `hmac.compare_digest` raise `TypeError` when given `str` values containing
non-ASCII characters. Header values reaching the blog API token check and the notifications webhook
signature check are attacker-controlled, so malformed input produces a 500 and a logged traceback
instead of an authentication failure. Comparing encoded bytes keeps the constant-time property and
turns the input into an ordinary mismatch.

## SA182 — Let project-owned tenant tables join the tenant universe

The tenant-isolation gate classifies models only through the literal `TENANT_TABLE_REGISTRY`, the
exclusion marker, or M2M inference. A model that uses `tenant_org_fk()` and `TenantManager` but lives
in a project app is unclassified, and every generated project's CI fails on it. The remediation
hint points at module source, which the extension contract forbids editing and which the next
`quickscale update` would overwrite. The property portal needs exactly such tables: any
`AbstractListing` subclass is a tenant model by construction.

A marker-derived classifier already exists and the documentation calls its overview authoritative,
while the source calls the literal the single source of truth. Make the gate and the policy refresh
use the derived set. Isolation stays default-deny in substance, because W003/W004 and the isolation
check still demand `organization_id` and FORCE RLS for every tenant model, whether or not the literal
lists it. The literal stays useful as a monorepo cross-check that shipped modules did not lose their
markers.

## SA183 — Destructive teardown must not strand a live external obligation

`purge_organization` deletes billing rows of every status and then the organization row holding
the Stripe customer id, without cancelling or refusing. Stripe keeps charging, and renewal webhooks
can no longer resolve an organization. Refusing is the smallest correct behavior: it keeps network
effects out of the purge transaction, preserves the local handle until billing is resolved, and
leaves the explicit teardown decision intact for everything already cancelled.

## SA188 — One owner for which commands may bypass the runtime role

Four stations independently declare which one-shot commands may run under the superuser connection:
the orgs boot guard, generated production settings, the CLI, and the generated launcher, which
added a second declaration shape. Adding `migrate_billing_to_orgs` edited eight places with no
cross-station test. The two frozen template copies also reject the command in exactly the
pre-0.88 projects that would need it.

The first decision is whether the third member stays. The command is documented for existing
deployments with user-scoped billing, yet `organization_id` is `NOT NULL` on every current install.
If it is retired, the set returns to two and the duplication cost stays flat. If it stays, the
declaration should live on the command itself, so it ships and upgrades with its module; settings
import before commands load, so settings can only validate that privileged mode was requested
explicitly. Each station keeps an independent refusal either way; the goal is one declaration, not
one check.

## SA189 — Runtime-role provisioning has three implementations

The same release that introduced runtime-role provisioning left three implementations with two
role names. Local `init.sql` creates `<package>_app` without `GRANT CONNECT`, while `start.sh` creates
`quickscale_runtime` with it and duplicates the CLI's default name; the operations guide gives
manual SQL. A role-name mix-up surfaces as password-authentication failures. Choose one naming rule
and one statement set, and have the other paths render or delegate to it. The DDL-password logging
and concurrent `CREATE ROLE` notes in the technical audit are not promoted and stay out of scope.

## SA190 — Purge membership and removal obligations from one place

After SA182, a project-owned tenant table is classified and refreshed, but purge still enumerates
its own literal `_DELETE_SPECS`. Because tenant foreign keys are `PROTECT`, an organization that owns
an unlisted row cannot be purged at all. Derive membership from the same tenant set, and order it
topologically from installed foreign keys, with overrides where the graph is not enough.

Organization removal also has two boundaries that discharge disjoint obligations. The account-delete
view cancels Stripe but leaves the personal organization's rows; purge deletes rows, clears caches,
and writes a tombstone, but does not touch Stripe. Account deletion removes a person and may keep
organization data on purpose, so the goal is not identical behavior. It is one named list of
obligations, where each boundary either discharges an item or states that it deliberately skips it.
Design the list together with the derived purge plan, keep network effects out of transactions, and
leave the last-owner model/signal backstop in place.

## SA191 — Migrate the property site before building the portal on it

`bap-web` is the beta site behind the property portal. It already runs `listings`, `forms`, and a
project-owned `properties` app with concrete models, a catalog seed command, a public
`/api/properties/` endpoint, and React property pages. It was generated on an older QuickScale, so
building the portal on it first requires catching it up to the current release.

The fresh-first mode is the documented primary path: a fresh scaffold with the same slug receives
the donor's custom content, so infrastructure files start correct instead of being merged. The
migration is the first real run of the tools that SA152 verifies on fixtures, which is why it waits
for that verification. Manual continuation is expected where the tool stops safely; the value of
this ticket is that every such stop becomes either a playbook step or a deterministic tool fix.

The migration preserves behavior, including the existing React and JSON API property surface.
Whether the portal keeps that surface or moves to Django-rendered pages is decided for the portal,
not here.

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
and inquiry handling. These tables join the tenant universe through the marker-derived
classification of SA182, never through edits to the vendored `orgs` source.

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
