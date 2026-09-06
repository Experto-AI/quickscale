# Ticket Context — Concepts and Implementation Notes

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Ticket Context**
> **Related docs**: [Roadmap](roadmap.md) | [Decisions](decisions.md) | [Validation Policy](validation_policy.md) | [Module Extension Contract](module-extension.md)

The [roadmap](roadmap.md) owns task scope, tracks, dependencies, scheduling, and acceptance.
This companion explains implementation rationale. Read the corresponding roadmap task first;
completed work and historical evidence belong in [CHANGELOG.md](../../CHANGELOG.md).

## SA165 — Validate the audit corrections and record their closeout

The product concerns are corrupt or non-mapping YAML reaching state writes, overly broad
empty-parameter isolation skips, unexplained host-dependent emission exceptions, and generated
operations guidance that permits predictable credentials in shared environments. State loading
must fail before writing, skip authorization must name the intended test identities, exceptions
must state their rationale and growth trigger, and credential guidance must distinguish local
development from shared deployments.

A release verdict describes exact product bytes. The five-file product candidate must include
the emission fixture with the operations template it pins: reviewing the template alone hides
the evidence that its generated output was rebaselined. Independent review and release validation
must cover the same settled product candidate under the [validation policy](validation_policy.md).

Recording that verdict is the final step of this task. Audit notes, status documents, and the
changelog record the result after it exists; they are outside the frozen product set so recording
a review cannot invalidate that review. Retire the four action-bearing notes only after the
required evidence is green. Documentation closeout does not reopen accepted product behavior.

## SA160 — Repair generated CSRF handling and remove dead settings helpers

The React theme repeats a cookie parser in `useApi.ts` and `FormRenderer.tsx`. Splitting on
`"; csrftoken="` and accepting exactly two parts returns an empty token when the browser has
multiple cookies of that name at different domain scopes. Reads still work, while Django rejects
mutating requests without `X-CSRFToken`.

Use one shared helper under `src/lib/`: iterate cookie entries, match the name exactly, and decode
the selected value. Both request paths should import it. Cover duplicate token cookies, unrelated
cookies, one token, and an empty cookie string; verify both consumers use the helper.

The generated base and production settings also define unused lowercase `get_client_ip` helpers.
Django exposes uppercase settings, and the live implementation is
`quickscale_modules_orgs.current_org.get_client_ip`, which reads `USE_X_FORWARDED_FOR` and
`TRUSTED_PROXY_COUNT`. Remove the dead definitions and the misleading comment about production
rebinding. Preserve the uppercase configuration and `REST_FRAMEWORK["NUM_PROXIES"]`
recomputation, and verify proxy-aware resolution retains its behavior.

These edits affect generated output. Review them together with one emission-fixture rebaseline,
keeping per-file rationale and separate CSRF and proxy regression evidence.

## SA172 — Make RLS application repeatable and resolve actual table names

`apply_force_rls` must be safe to invoke twice. PostgreSQL policy creation requires the forward
SQL to drop the named policies with `DROP POLICY IF EXISTS` before recreating them; otherwise
the second invocation raises `duplicate_object`. Prove repeatability by applying twice.

`refresh_force_rls_policies` must obtain each enrolled model's table name through
`apps.get_model(...)._meta.db_table`. Guessing the default Django name silently misses models
with a custom `db_table`. Resolution failures must be explicit because an omitted policy refresh
cannot be treated as success. Preserve the module's independent fail-closed role guard.

Predicate-content enforcement has a different purpose and is explained under SA177.

## SA174 — Correct contract comments and audit watchlist explanations

The sanctioned privileged commands are `migrate` and `createcachetable`. Production settings
validate the role selection, the `orgs` app supplies an independent boot guard, and the CLI
produces the environment value. A template test transcribes the settings declaration, while
`start.sh` contains invocation literals. The `orgs` frozenset is therefore one declaration in a
shared contract, not its sole authority.

Correct the comment to name the participating declarations and retain the independent
fail-closed guard. Record a third sanctioned command or disagreement between declarations as
the trigger for revisiting consolidation. This requires no generated-output change.

The gate registry's `trigger_inputs` field describes a bidirectional partition of the
`e2e.yml` path allowlist; it is not a promise about when a gate can be skipped. Explain that
meaning in its docstring and schema description, retaining the field name and behavior. Using
it to skip execution is the trigger for reconsidering those semantics.

Restate the architectural watchlist from the actual implementation, preserving the triggers for
the provisioning script's module-name and module-count literals, its separately pinned PostgreSQL
major, and count-pinned gate-parity oracles. Accurate watchlist wording preserves deferred
questions without claiming that documentation has resolved their underlying structures.

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

## SA177 — Verify RLS policy predicates

RLS enabled, RLS forced, and a row in `pg_policies` do not prove tenant isolation: a permissive
`USING (true)` policy can satisfy all three. The intended contract scopes writes to the current
organization and permits cross-tenant reads only with the operator flag. Operator access belongs
to a `FOR SELECT` policy so it cannot expand write or delete visibility.

Compare the database's `qual` and `with_check` expressions with the rendered policy contract for
every enrolled table, accounting for PostgreSQL's expression representation. Use a live database
and a negative control that weakens a predicate and is rejected. This checks policy meaning in
addition to the application and table-resolution behavior covered by SA172.

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
