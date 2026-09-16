# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

`v88` is release-accepted (see [CHANGELOG.md](../../CHANGELOG.md)). The next goal is the first
useful property portal (SA153) in a project-owned extension, generalizing capabilities only after
that project proves their value. The portal is built on `bap-web`, the existing beta site, after
the verified migration tools (SA152) move it onto current QuickScale (SA191).

**Release status — v0.88.0 packaged, not published.** The v0.88.0 release commit carries a
release-prepared public note; `v89` has since bumped the repository to `0.89.0`. No core tag,
split-branch republication, seal, or PyPI upload has happened. Outstanding before publication:
release-tier validation on the packaged bytes, the ordered phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. Two scheduled fixes
bear on what gets published: SA186 guards the split-branch force-push that publication runs, and
SA185 declares the `orgs` contract vintage that the 0.88 templates introduced. Landing either in
0.88.0 means repackaging; publishing without them ships the recorded issues. Publication itself
stays a maintainer decision; this planner tracks only that it is owed.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance;
[CHANGELOG.md](../../CHANGELOG.md) preserves history and evidence.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA152 | Verify maintainer migration modes and their runtime compatibility | post-v88 | 1 | — | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale with the fresh-first migration tool | post-v88 | 1 | SA152 | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA184 | Make `quickscale deploy railway` re-runs read live state and fail hard | post-v88 | 2 | — | Deferred |
| SA185 | Enforce contract vintage when upgradable code meets an older project | post-v88 | 2 | SA184 | Deferred |
| SA186 | Require a fast-forward before publication force-pushes a split branch | post-v88 | 2 | — | Deferred |
| SA187 | Reject non-ASCII tokens and signatures as authentication failures | post-v88 | 2 | — | Deferred |
| SA192 | Style the module-shipped Django pages with the shared design | post-v88 | 2 | SA185 | Deferred |
| SA177 | Verify the predicates of enrolled RLS policies | post-v88 | 3 | — | Deferred |
| SA188 | Settle the privileged-command set behind one declaration | post-v88 | 3 | SA185 | Deferred |
| SA189 | Provision the runtime database role in one place under one name | post-v88 | 3 | SA188 | Deferred |
| SA190 | Derive the purge plan and share organization-removal obligations | post-v88 | 3 | — | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA152 ──► SA191 ──► SA153 ──► SA154 (inventory)   critical path: first property portal
Track 2: SA184 ──► SA185 ──► SA186 ──► SA187 ──► SA192
Track 3: SA177 ──► SA188 ──► SA189 ──► SA190

Cross-track dependencies:  SA185 ──► SA188
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA152 → SA191 → SA153. The portal is built on the migrated `bap-web`, so the
migration tools are verified first and then used for real. Project-owned tenant tables no longer add
a dependency to the portal. SA154 is an inventory, not work. Every other ticket is off the critical
path.

**Ordering.**

- **Derived tenant tables support SA153 and SA177.** Project-owned tenant tables pass the generated
  project's `check_tenant_isolation` without module-source edits, and predicate verification covers
  them through the same derived tenant-model set.
- **SA184 precedes SA185.** Both edit `deployment_commands.py`, and the deploy-time vintage check
  should read Railway state through the fail-hard path.
- **SA185 precedes SA188, and SA188 precedes SA189.** SA188 changes contract-bearing templates and
  is the first real use of an enforced vintage move. SA188 and SA189 both edit `start.sh.j2` and
  regenerate the SA90 emission fixture; settle the command set before collapsing role provisioning
  around it.
- **SA152 precedes SA191, and SA191 precedes SA153.** `bap-web` is migrated with the maintainer
  tools only after SA152 has proven them on isolated fixtures, and the portal is built on the
  migrated project rather than on a fresh one. SA184 is not an edge: SA191 redeploys through
  `deploy railway` only if SA184 has landed, and otherwise deploys manually.
- **SA185 precedes SA192.** The module pages extend the generated, project-owned `base.html`, which
  `quickscale update` never rewrites, so a design change there is contract-bearing and existing
  projects adopt it through an enforced vintage move. SA192 is not an SA153 edge: the portal's
  React pages do not need the restyled Django pages to ship.
- **Independent.** SA186 and SA187 have no edges and sit by severity. SA152 shares no files with
  SA188/SA189, but all three touch the privilege/runtime contract of generated `settings/production.py`
  and `start.sh`; whichever lands second re-runs the others' fixtures.

**Rebalance.** Track 1 carries the whole critical path: the migration-tool verification (SA152),
the `bap-web` migration (SA191), and the portal (SA153), because each feeds the next and
splitting them across tracks would only add merge handoffs. Tracks 2 and 3 split the audit work by
conflict surface. Track 2 takes the CLI deploy/update, publication, and test surfaces, which are
mostly trivial or small. Track 3 takes orgs tenancy, purge, and the privileged/runtime-role
templates, which carry the medium tickets. SA177 sits ahead of SA188 so Track 3 keeps working while
Track 2 delivers SA185. SA186 and SA187 could move to Track 3's tail without a conflict, but would
only lengthen that track.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA152 | yes | yes | yes | **yes** | **yes** |
| 2 | SA184 | yes | yes | yes | **yes** | no |
| 3 | SA177 | yes | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the maintainer
  migration tools and playbook, the `bap-web` migration, the property extension, public templates,
  and the portal's extension documentation.
- Track 2 owns `scripts/publish_module.py`, the module-shipped page templates and stylesheets, the
  generated `base.html`, the CLI deploy and update commands
  (`deployment_commands.py`, `railway_utils.py`, `module_commands.py`, the vintage check), version
  expectations in tests, and the blog/notifications credential comparisons.
- Track 3 owns the isolation-conformance runner, `orgs/tenancy.py` and its checks, the orgs policy
  template/tests, `purge_organization.py` and the account-delete obligations, and the privileged
  command and runtime-role stations (`orgs/apps.py`, `production.py.j2`, `start.sh.j2`,
  `db/init.sql.j2`, `development_commands.py`, the SA90 emission fixture).
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** The shared closeout set is this roadmap, [CHANGELOG.md](../../CHANGELOG.md),
  and the owning audit: the arch audit for SA152, SA185, SA188, SA189, and SA190; the tech audit
  for SA177, SA184, SA186, and
  SA187 (SA190 also closes arch-audit items). SA191, SA153, and SA192 have no owning
  audit; their evidence goes to the changelog, and SA191's also to the migration playbook. All are
  Markdown with no generated consumer.
  Three code-adjacent overlaps cross tracks: SA153 edits the extension and organizations
  documentation; SA192 restyles the `auth` account templates
  while SA190 edits the account-delete view, so whichever lands second re-runs the auth tests; and
  SA189 edits `deployment_commands.py` after Track 2's deploy work has merged through its
  dependency chain. The serialized queue covers them:
  each track resolves the shared set at its own merge, after the previous merge lands, then runs the
  consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [x] **SA180 — Derive the gate-parity count oracles from the registry.**

- [ ] **SA152 — Verify maintainer migration modes and their runtime compatibility.**

  **Context:** The maintainer migration commands need a complete smoke exercise. Their flag and ownership
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

  **Acceptance:** for each migration mode (fresh-first, in-place), derive which version of
  `settings/production.py`, `start.sh`, and `Dockerfile` reaches the recipient, preserving donor
  precedence. In isolated fixtures on a generated donor/recipient pair, prove a compatible combination
  works and an unsupported privileged-command/runtime combination fails for the intended reason; run
  the fresh-first dry-run and in-place checkpoint-only workflows without touching a real project or
  database. Make a missing template root fail instead of `pytest.skip()`. Register the smoke gate,
  keep gate parity green, and correct the migration playbook's version/location claims.

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, CLI migration tests, gate registry and
  parity wiring, Make/CI entrypoints as needed, the migration playbook. No public updater, typed
  ownership framework, or changed file precedence.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale with the fresh-first migration tool.**

  Use `make beta-migrate-fresh` with `bap-web` as donor and a fresh scaffold generated with the same
  slug as recipient, continuing manually only where the tool emits `pending_manual_actions`.

  **Context:** `bap-web` is the beta site behind the property portal. It already runs `listings`, `forms`, and a
  project-owned `properties` app with concrete models, a catalog seed command, a public
  `/api/properties/` endpoint, and React property pages. It was generated on an older QuickScale, so
  building the portal on it first requires catching it up to the current release.

  The fresh-first mode is the documented primary path: a fresh scaffold with the same slug receives
  the donor's custom content, so infrastructure files start correct instead of being merged. The
  migration is the first real run of the tools that SA152 verifies on fixtures, which is why it waits
  for that verification. Manual continuation is expected where the tool stops safely; the value of
  this ticket is that every such stop becomes either a playbook step or a deterministic tool fix.

  The migration preserves behavior, including the existing React and JSON API property surface that
  the portal then builds on.

  **Acceptance:** the migrated project records the current QuickScale version in `quickscale.yml`
  and its lock, and passes its own test suite and local verification stack. The project-owned
  `properties` app, its migrations and catalog seed, forms and contact customizations, content,
  and frontend pages carry over and behave as before; `.git`, `media/`, `.env`, and `poetry.lock`
  are not copied between the two trees. Every manual step the tool did not automate is recorded in
  the migration report and fed back into the playbook, or into a tool fix when it is deterministic.
  The migrated project replaces the old repository and deploys, with a written rollback to the
  previous deploy. The production database and media are carried over by a verified backup and
  restore, and listing, form, and user counts match before and after. Redeploying through
  `deploy railway` requires SA184; otherwise the deploy is manual. No property-portal features,
  frontend stack change, or module-source edits.

  **Surfaces:** the `bap-web` repository; the migration playbook and, for deterministic gaps found,
  `quickscale_devtools/.../beta_migration.py` and its tests.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API, using the documented project-owned extension pattern for property models,
  serializers, API views, URLs, and filters. Build on the React pages and `/api/properties/` that
  SA191 carries over instead of replacing them. No Django-rendered property pages, public API in the
  reusable `listings` module, or generic property behavior in every generated project.

  **Context:** `listings` provides `AbstractListing`, but its shipped views, URLs, admin registration, and
  filters target the concrete `Listing`. A property subclass therefore needs a project-owned read
  API, URLs, and filters under the documented [extension contract](module-extension.md).
  Use that extension path to launch `buenosairesproperties.com` and let working project needs
  inform later reusable module changes.

  **Frontend direction.** React is the standard frontend for new application and public pages.
  Django keeps the flows where its ready-made behavior is the point: `auth` (allauth login, signup,
  reset, profile) and `billing` (pricing and status around Stripe's hosted checkout) stay
  Django-rendered and adopt the shared visual design instead of being rebuilt. The module pages that
  are already Django-rendered — blog, generic listings, the CRM dashboard — keep that rendering on
  the same design until a concrete consumer promotes a React replacement, and Django admin stays as
  shipped. The deciding costs were rebuilding security-sensitive flows against
  an API for little user-visible gain; the look comes from the shared Tailwind design, not from
  the rendering technology. `bap-web` already follows this shape, so the portal extends its React
  pages and `/api/properties/` rather than replacing them.

  A client-rendered page gives crawlers and link-preview bots an empty document, so catalog and
  detail pages must be prerendered or server-rendered for Open Graph and indexing. Choosing that
  mechanism adds to the approved frontend stack and needs its decision entry.

  The launch needs property fields and galleries, explicit currency labels, attribute filtering
  and keyword search applied by the API, Spanish public pages, listing-linked inquiries into `crm`,
  and launch SEO including metadata, sitemap, and robots guidance. Currency labels must not imply
  exchange-rate conversion, and Spanish launch coverage does not require translating every
  QuickScale interface.

  Every new child table, including gallery images, must carry its own `organization_id` and RLS
  policy under the child-table decision in [decisions.md](decisions.md). Match the existing
  `test_rls_boundary.py` coverage pattern and verify tenant isolation across the API, the rendered
  pages, and inquiry handling. These tables join the tenant universe through the marker-derived
  classification of SA182, never through edits to the vendored `orgs` source.

  A public read API inside the reusable `listings` module, and generic support requiring no
  project-owned code, belong in the optional inventory until a second consumer justifies them.

  **Acceptance:** first record in decisions that React is the standard frontend for new application
  and public pages; `auth` and `billing` stay Django-rendered on the shared design (SA192); the
  existing module-shipped Django pages (blog, listings, CRM dashboard) stay Django-rendered on that
  design until an SA154 item promotes a React replacement; Django admin stays as shipped. Then the
  `bap-web` project migrated by SA191 serves an organization-scoped React property catalog and
  detail page with ordered image galleries; bedrooms, bathrooms, area, property type, sale/rent,
  and explicitly labeled currency fields; keyword and attribute filters that the API applies
  server-side. Property pages use the React app's visual design and render in Spanish. A listing
  inquiry creates a CRM record with a listing reference. Catalog and detail pages are prerendered or
  server-rendered so a crawler that runs no JavaScript receives the content and Open Graph tags; the
  site has a sitemap and `robots.txt` generated from published listings. The API exposes only
  published listings of the requested organization. Every new tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests,
  and passes the generated project's `check_tenant_isolation` through marker-derived enrollment, with no
  edit under vendored module source. Prove the search → detail → inquiry journey and isolation
  between organizations through both the API and the rendered pages. Correct reusable-module feature
  claims that the module does not provide. Adding a frontend dependency for prerendering follows the
  decisions rule for the approved frontend stack. Purging an organization that owns property rows
  is SA190's.

  **Surfaces:** the project-owned property extension, its API and React pages, and the project's
  prerender build and deploy step; listings/blog/forms/CRM seams only where needed; decisions;
  extension documentation.

- [ ] **SA192 — Style the module-shipped Django pages with the shared design.**

  **Context:** After the frontend direction, a user moves between React screens and Django-rendered module pages:
  `auth` account pages, `billing` pricing and status, and the blog, generic listings, and CRM
  dashboard pages. Those pages use their own plainer styling, which reads as a different product.
  The fix is presentation only.

  Two layers produce a module page's look, and they update differently. The module's own templates
  and static files (for example `quickscale_modules_auth/base.html` and its `auth.css`) live under
  `modules/<name>/`, so `quickscale update` delivers changes to them. Those templates extend the
  generated `base.html`, which is project-owned and never rewritten. Module-specific styling therefore
  belongs in the module, where updates reach existing projects; the shell's tokens and header belong
  in the generated `base.html`, which fresh projects receive and existing projects adopt through the
  vintage rule from SA185.

  The styling must not rely on project-level overrides. Django resolves a project `templates/` copy
  before the module's, so an override would freeze that page at generation time and hide every later
  module fix. It also cannot assume Tailwind utility classes are available: the project's Tailwind
  build scans only `frontend/src`, so classes used only in module templates are never emitted. A
  module stylesheet expressed in the shared design tokens avoids both traps.

  Behavior stays exactly as tested. Allauth flows, form handling, CSRF and session semantics, and
  the Stripe hosted checkout hand-off must not change, which is why existing tests should pass
  without behavior edits.

  **Acceptance:** every user-facing page template shipped by `auth` (account pages), `billing`
  (pricing, dashboard, checkout and portal return pages), `blog`, `listings`, and the `crm`
  dashboard uses the same design tokens (colors, radius, typography) and component look as
  `showcase_react`, so moving between the React app and these pages shows no visual break. The
  tokens are the shadcn/ui CSS variables (`--primary`, `--radius`, …) defined once for the project
  and loaded by both the React app and `base.html`, so changing a token restyles React and Django
  pages together; module styles read those variables instead of hard-coded colors. The
  module-specific styling ships inside each module — its templates and a module stylesheet built
  from the shared tokens — not as project-level `templates/` overrides, so `quickscale update`
  delivers it and later design fixes; a generated project contains no copy of a module template.
  The page shell stays the generated, project-owned `base.html`: fresh generations get the shared
  tokens and header there, and the change moves the owning vintage through SA185 with manual
  adoption steps for existing projects. Styling must not depend on Tailwind classes that the
  project's frontend build does not emit, since that build scans only `frontend/src`. Flow logic,
  URLs, forms, CSRF and session handling, allauth behavior, and the Stripe hosted checkout hand-off
  are unchanged, and existing module tests pass without behavior edits. A generated-project check
  fails when a module page stops extending `base.html` or loses its module stylesheet. Django admin
  and notification emails are out of scope.

  **Surfaces:** `auth`, `billing`, `blog`, `listings`, and `crm` templates and static styles; the
  generated `base.html` template; the module vintage declarations; generator tests; the theme
  documentation; and the user manual's update-ownership section.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or prerender step into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Items that add tenant tables (saved searches, favorites, profiles,
  tours) build on marker-derived enrollment and SA190's purge derivation, not on module-source edits. Close
  when every item is promoted or dropped with rationale.

  **Context:** The inventory includes reusable generalization of the proven property API, React pages, and
  prerender step; React pages for the blog, generic listings, and CRM dashboard; React `auth` and
  `billing` flows; maps and geocoding, saved searches and alerts, agent and office profiles,
  syndication feeds, virtual tours, featured placement tied to billing credits, blog/listing links,
  and PostgreSQL full-text search.

  Promote a capability only with a concrete consumer, bounded acceptance criteria, and evidence
  that it improves the working portal. Public API design and generic extension work should follow
  the actual project contracts they need to support.

- [x] **SA181 — Derive expected versions in tests from the repository version.**

- [ ] **SA184 — Make `quickscale deploy railway` re-runs read live state and fail hard.**

  **Context:** `quickscale deploy railway` is designed to be re-run, and the Railway guide recommends re-running
  it. The runtime-role work made the database password survive re-runs, but `SECRET_KEY` is still
  regenerated each time, which logs everyone out and invalidates signed links. The same step turns an
  unreadable variable listing into an empty mapping, and an ambiguous Postgres service listing into
  a guessed name. Both violate Fail-Hard: a transient CLI failure becomes a rotated database
  credential that breaks the still-serving deployment when its pooled connections recycle.

  The shared cause is that deploy reconstructs configuration instead of reconciling with state it
  has read successfully. Read first, refuse when the read fails, and generate a secret only when the
  live environment genuinely has none.

  **Acceptance:** a re-run reuses the service's existing `SECRET_KEY` and generates one only on first
  deploy, mirroring the `RUNTIME_DB_PASSWORD` reuse rule. When Railway variables cannot be read —
  an exception or a `None` result — the command raises `click.ClickException` instead of treating
  state as empty, so it never regenerates the runtime password or overwrites an operator-managed
  `RUNTIME_DATABASE_URL`. `_setup_postgres_step` fails when listing fails or when anything other than
  exactly one database service matches, preferring Railway's service type to a name substring when
  the JSON exposes it. Regressions cover key reuse, the unreadable-state refusal, and zero or several
  Postgres matches. This retires TA74 and TA75.

  **Surfaces:** `deployment_commands.py`, the `railway_utils.py` variable helpers, CLI deploy tests,
  `docs/deployment/railway.md`, and the technical audit.

- [ ] **SA185 — Enforce contract vintage when upgradable code meets an older project.**

  **Context:** Some runtime contracts are split: one half is an emitted file frozen at generation
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

  **Acceptance:** `orgs` declares `contract_vintage.minimum: 0.88.0` with manual adoption steps for
  `settings/production.py`, `start.sh`, and the `Dockerfile`, and the CLI declares the same minimum
  for the runtime-role variables `deploy railway` writes. `quickscale update`, `apply`, and
  `deploy railway` run the vintage check that `quickscale status` already computes and refuse when
  the project's recorded contract is behind, unless the operator explicitly acknowledges it; the
  refusal names the module or command, the minimum, and the adoption steps. Regressions prove an
  old-vintage project is refused, and that acknowledged and current projects proceed. Document the
  rule that a change to a contract-bearing emitted file moves the owning vintage. No template
  updater; deriving vintages from the SA90 fixture is out of scope.

  **Surfaces:** the `orgs` manifest, the manifest loader and `status_command.py` vintage check (reuse),
  `module_commands.py` update, `apply_command.py`, `deployment_commands.py`, CLI tests, upgrade
  documentation, and the architecture audit.

- [ ] **SA186 — Require a fast-forward before publication force-pushes a split branch.**

  **Context:** Force-with-lease prevents overwriting a remote commit nobody observed. `--publish-all` observes the
  remote tip and immediately feeds it to the lease, so the lease only guards the moment between
  observation and push. Publishing from an older worktree then force-overwrites newer split branches
  with older bytes, and consumers verifying module code from split refs get stale modules. Because
  `git subtree split` is deterministic, a legitimate republish always fast-forwards; an ancestry check
  costs nothing on the happy path and stops exactly the overwrite the lease was meant to prevent.

  **Acceptance:** before each push, `--publish-all` (and single-module publication, which relies on
  the same lease) requires the observed remote tip to be an ancestor of the local split. On
  divergence the batch stops before any further push and names the module. A regression with a
  non-ancestor remote tip refuses; a fast-forward republish proceeds. This retires TA77.

  **Surfaces:** `scripts/publish_module.py`, its tests, the publish procedure where it describes the
  lease, and the technical audit.

- [ ] **SA187 — Reject non-ASCII tokens and signatures as authentication failures.**

  **Context:** `secrets.compare_digest` and `hmac.compare_digest` raise `TypeError` when given `str` values containing
  non-ASCII characters. Header values reaching the blog API token check and the notifications webhook
  signature check are attacker-controlled, so malformed input produces a 500 and a logged traceback
  instead of an authentication failure. Comparing encoded bytes keeps the constant-time property and
  turns the input into an ordinary mismatch.

  **Acceptance:** the blog API token check and the notifications webhook signature check compare
  bytes, or reject non-ASCII input first, so a non-ASCII `Authorization` token or signature header
  gets 401/403 instead of a 500 traceback. Each path has a regression. This retires TA78.

  **Surfaces:** `blog/views.py`, `notifications/services.py`, their tests, and the technical audit.

- [x] **SA182 — Enroll marker-declared tenant models in classification and policy refresh.**

- [x] **SA183 — Refuse to purge an organization with a live Stripe subscription.**

- [ ] **SA177 — Verify the predicates of enrolled RLS policies.**

  **Context:** RLS enabled, RLS forced, and a row in `pg_policies` do not prove tenant isolation: a permissive
  `USING (true)` policy can satisfy all three. The intended contract scopes writes to the current
  organization and permits cross-tenant reads only with the operator flag. Operator access belongs
  to a `FOR SELECT` policy so it cannot expand write or delete visibility.

  Compare the database's `qual` and `with_check` expressions with the rendered policy contract for
  every enrolled table, accounting for PostgreSQL's expression representation. Use a live database
  and a negative control that weakens a predicate and is rejected. This checks policy meaning in
  addition to SA172's accepted application and table-resolution behavior.

  **Acceptance:** for each enrolled table — including marker-declared project tables, through
  the derived set — compare both policies' `qual` and `with_check` in `pg_policies` against the
  rendered expected policies, normalized for PostgreSQL's catalog representation. A deliberately
  weakened predicate fails for the intended reason and the exact policy is restored afterward. Then
  retire the tech audit's predicate-conformance tooling gap and structural smell.

  **Surfaces:** isolation-conformance runner, orgs policy template/tests, technical audit.

- [ ] **SA188 — Settle the privileged-command set behind one declaration.**

  **Context:** Four stations independently declare which one-shot commands may run under the superuser connection:
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

  **Acceptance:** first record in decisions whether `migrate_billing_to_orgs` is a permanent member
  or is retired; this answers the architecture audit's open question and supersedes the 2026-08-31
  "permanent two" answer. If retired, remove it from the orgs guard, `production.py.j2`,
  `development_commands.py`, and the `start.sh.j2` argv branch, and return the item to the
  watchlist with a dated retirement. If permanent, a privileged command declares itself on its
  command class; the orgs guard and the launcher read that declaration, settings validate only that
  privileged mode was requested explicitly, and every station keeps its own fail-closed refusal.
  Either way, each executable station has a regression naming every member, the SA90 emission
  fixture is regenerated once, and the template change moves the `orgs` vintage through SA185.

  **Surfaces:** `orgs/apps.py`, `migrate_billing_to_orgs.py`, `production.py.j2`, `start.sh.j2`,
  `development_commands.py`, generator/CLI/boot-guard tests, the SA90 fixture, decisions,
  `docs/deployment/railway.md`, and the architecture audit.

- [ ] **SA189 — Provision the runtime database role in one place under one name.**

  **Context:** The same release that introduced runtime-role provisioning left three implementations with two
  role names. Local `init.sql` creates `<package>_app` without `GRANT CONNECT`, while `start.sh` creates
  `quickscale_runtime` with it and duplicates the CLI's default name; the operations guide gives
  manual SQL. A role-name mix-up surfaces as password-authentication failures. Choose one naming rule
  and one statement set, and have the other paths render or delegate to it. The DDL-password logging
  and concurrent `CREATE ROLE` notes in the technical audit are not promoted and stay out of scope.

  **Acceptance:** `db/init.sql.j2`, the `start.sh.j2` provisioning step, the `deploy railway` default
  role, and `OPERATIONS.md.j2` share one role-naming rule and one provisioning statement set,
  including `GRANT CONNECT`. A generated project's local and Railway paths produce the same role name
  and grants, and a regression fails when they diverge. The template change moves the `orgs`
  vintage through SA185. The boot guard and the privileged-command set are unchanged.

  **Surfaces:** `db/init.sql.j2`, `start.sh.j2`, the generator's role-name context,
  `deployment_commands.py`, `OPERATIONS.md.j2`, generator tests, the SA90 fixture, and the
  architecture audit.

- [ ] **SA190 — Derive the purge plan and share organization-removal obligations.**

  **Context:** Marker-derived tenant discovery classifies and refreshes project-owned tenant tables,
  but purge still enumerates its own literal `_DELETE_SPECS`. Because tenant foreign keys are
  `PROTECT`, an organization that owns an unlisted row cannot be purged at all. Derive membership
  from the same tenant set, and order it topologically from installed foreign keys, with overrides
  where the graph is not enough.

  Organization removal also has two boundaries that discharge disjoint obligations. The account-delete
  view cancels Stripe but leaves the personal organization's rows; purge deletes rows, clears caches,
  and writes a tombstone, but does not touch Stripe. Account deletion removes a person and may keep
  organization data on purpose, so the goal is not identical behavior. It is one named list of
  obligations, where each boundary either discharges an item or states that it deliberately skips it.
  Design the list together with the derived purge plan, keep network effects out of transactions, and
  leave the last-owner model/signal backstop in place.

  **Acceptance:** `purge_organization` takes its membership from the derived tenant-model set and
  its deletion order from installed FK metadata, with explicit overrides, so purging an organization
  that owns project-owned tenant rows succeeds without a `_DELETE_SPECS` edit. The obligations of
  removing an organization — the SA183 billing refusal, owned-row purge, social cache invalidation,
  and tombstone — are one named list that both `purge_organization` and the account-delete view
  consume; the view records which obligations it deliberately skips (retained organization data)
  instead of omitting them. The last-owner model/signal backstop is unchanged. Regressions purge a
  non-module tenant model with a child row cleanly, and a conformance test fails when a purged model
  carries an external provider id with no refuse-or-reconcile obligation. This retires the purge
  half of `org-model-universe-hand-enumerated`, the first step of
  `deletion-invariants-per-boundary-reimplementation`, and the tech audit's teardown tooling gap. No
  durable deletion job or outbox.

  **Surfaces:** `purge_organization.py`, `auth/views.py` account deletion, the billing cancellation
  seam, orgs and auth tests, `organizations.md`, and both audits.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings and their growth triggers. Items they record without scheduling — the watchlists
and watch notes, the generated-project dependency-scan tooling gap, and the later
deletion-coordinator options — stay there until a trigger fires. The standing
no-`teams`/no-third-updater scope, internal-only devtools, presence contracts, and resource
safeguards live in
[decisions](decisions.md) and [validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
