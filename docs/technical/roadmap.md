# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

`v88` is release-accepted (see [CHANGELOG.md](../../CHANGELOG.md)). The next goal is the first
useful property portal (SA153) in a project-owned extension, generalizing capabilities only after
that project proves their value. The portal is built on `bap-web`, the existing beta site, after
the verified migration tools move it onto current QuickScale (SA191).

**Release status — v0.88.0 packaged, not published.** The v0.88.0 release commit carries a
release-prepared public note; `v89` has since bumped the repository to `0.89.0`. No core tag,
split-branch republication, seal, or PyPI upload has happened. Outstanding before publication:
release-tier validation on the packaged bytes, the ordered phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. SA185 now declares
the `orgs` contract vintage that the 0.88 templates introduced; SA186 now requires a fast-forward
before the split-branch force-push that publication runs. The audits add a third recorded issue:
the packaged CLI generates an `.env.example` with no placeholder for the credential variables that
`storage` and `backups` declare (SA193), so a project generated from the published bytes with
either module enabled meets a configuration error naming a variable it was never shown.

The latest technical-audit pass adds more that the packaged bytes carry into every generated
project: the DR engine drops the database's TLS settings when it dumps and restores (SA198), the
account-deletion view makes a Stripe round trip inside a transaction holding organization row locks
(SA199), and the publishing workflow itself trusts mutable action refs on the path that would do
the uploading (SA202). Including any of these fixes in 0.88.0 means repackaging; publishing bytes
without one ships its recorded issue. Publication itself stays a maintainer decision; this planner
tracks only that it is owed.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance;
[CHANGELOG.md](../../CHANGELOG.md) preserves history and evidence.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA194 | Unblock in-place beta migration at the contract-vintage gate | post-v88 | 1 | — | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale with the fresh-first migration tool | post-v88 | 1 | SA194 | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA193 | Derive the generated `.env.example` credential contract from module manifests | post-v88 | 2 | — | Deferred |
| SA198 | Carry the database's TLS settings into the backup and restore commands | post-v88 | 2 | — | Deferred |
| SA202 | Pin the publishing supply chain and add the missing CI scanners | post-v88 | 2 | — | Deferred |
| SA195 | Share one module test-settings stub instead of copying it per module | post-v88 | 2 | — | Deferred |
| SA192 | Style the module-shipped Django pages with the shared design | post-v88 | 2 | SA195 | Deferred |
| SA199 | Keep external calls out of transactions and hold the webhook lock | post-v88 | 3 | — | Deferred |
| SA200 | Gate the proxy and correlation-id settings the generator emits | post-v88 | 3 | — | Deferred |
| SA196 | Fail hard on undefined generator template context | post-v88 | 3 | — | Deferred |
| SA201 | Give generated projects one throttling contract | post-v88 | 3 | — | Deferred |
| SA203 | Narrow the privileged-command exemption in the orgs boot path | post-v88 | 3 | — | Deferred |
| SA190 | Derive the purge plan and share organization-removal obligations | post-v88 | 3 | SA199 | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA194 ──► SA191 ──► SA153 ──► SA154 (inventory)   critical path: first portal
Track 2: SA193 ──► SA198 ──► SA202 ──► SA195 ──► SA192
Track 3: SA199 ──► SA200 ──► SA196 ──► SA201 ──► SA203 ──► SA190
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA194 → SA191 → SA153. The portal is built on the migrated `bap-web`, using the
verified migration tools for real, once the tool's in-place halt and its blind smoke gate are
cleared. Project-owned tenant tables no longer add a dependency to the portal. SA154 is an
inventory, not work. Every other ticket, including all six tickets the latest audits added, is off
the critical path.

**Ordering.**

- **Derived tenant tables support SA153 and SA177.** Project-owned tenant tables pass the generated
  project's `check_tenant_isolation` without module-source edits, and predicate verification covers
  them through the same derived tenant-model set.
- **SA194 precedes SA191, and SA191 precedes SA153.** `bap-web` is migrated with the maintainer
  tools only after SA152 proved them on isolated fixtures, and the portal is built on the migrated
  project rather than on a fresh one. SA194 is the new edge: the tool's in-place mode aborts
  mid-run at `quickscale apply` on exactly the recipients it was built for, and the smoke gate that
  claims to cover that path shims the CLI so it always exits 0. The `bap-web` migration uses
  fresh-first mode, which the halt does not reach, but it uses a tool whose gate is currently blind
  to the CLI it invokes; SA194 makes the gate observe it before the tool is trusted with the real
  site. SA191 redeploys through the fail-hard `deploy railway` path.
- **SA195 precedes SA192.** The SA192 precursor already minted three byte-identical test-settings
  stubs for the modules it restyled, while a sanctioned shared commons is imported by those same
  three suites. SA192 restyles five module surfaces on that pattern and SA154's inventory queues
  more, so the copy multiplies before it is removed unless the stub is shared first.
- **SA193 is independent of the orgs work.** It touches generation-time wiring in `quickscale_cli`
  and `quickscale_core`; SA190's findings live in the `orgs` module, so the two run on different
  tracks with no shared file. One interaction, previously a watch item, has now fired: giving the
  `backups` remote-credential variables placeholders makes the DR path more exercised, and that
  path is the one SA198 fixes. SA193 is queued before SA198 for that reason, but the two edit
  disjoint files and carry no dependency edge.
- **SA198 and SA202 are queued on track 2 by what publication would ship.** SA198 is the only
  S2 defect in the packaged bytes that no other ticket touches, and SA202 hardens the workflow that
  performs the publication those bytes are waiting on. Neither blocks another ticket, so both are
  queue order rather than edges; both are placed ahead of the presentation work (SA195, SA192)
  because that work changes nothing a published artifact does.
- **SA199 precedes SA190, and this is a real edge.** Both rewrite the account-delete view. SA199
  splits it into an in-transaction guard and an out-of-transaction Stripe call; SA190 then designs
  the named obligations list that both boundaries consume. Designing that list against today's
  single atomic block would encode the defect into the contract, so SA199 lands first. It is also
  the reason SA190 moved off the head of track 3.
- **SA200 precedes SA201 in the queue, not by dependency.** Both edit the generator's settings
  templates, so serializing them avoids a self-inflicted conflict on `base.py.j2`, and SA200's
  `check --deploy` gate is the station SA201's throttle defaults are then observed by. SA201 is
  correct without SA200 and carries no edge.
- **SA203 is small and stands alone.** The `orgs.ready()` early return is boot-path code that no
  other ticket reads; it sits on track 3 because track 3 owns the orgs module and the
  privileged-command stations, and late in the queue because it is the least severe of them.
- **SA196 is queued early on track 3 but gates nothing.** Making the generator raise on an
  undefined context key protects the fresh recipient scaffold SA191 generates and the `base.html`
  rewrite SA192 performs, which is why it precedes SA190 in the queue. Neither ticket depends on
  it and both are correct without it, so it carries no dependency edge.
- **SA153 decides whether SA190's purge half stays real.** If the property tables ship as
  project-owned extension models, purge membership stays closed against them and the finding keeps
  its horizon; if they ship inside a first-party module, that half retires. SA190 is scheduled
  either way for the obligations half.
- **SA192 uses the enforced vintage boundary.** The module pages extend the generated,
  project-owned `base.html`, which `quickscale update` never rewrites, so a design change there is
  contract-bearing and existing projects adopt it through an enforced vintage move. SA192 is not
  an SA153 edge: the portal's
  React pages do not need the restyled Django pages to ship.

**Rebalance.** Track 1 carries the whole critical path: the migration-tool fixes (SA194), the
`bap-web` migration (SA191), and the portal (SA153), because each feeds the next and splitting them
across tracks would only add merge handoffs. Track 1 is saturated by that path, so none of the new
audit work was given to it — including the CI gates the tooling gaps call for, which would normally
follow Track 1's ownership of the gate registry. Track 2 takes those instead and coordinates the
registry entry with Track 1 at merge; the ownership list below records the transfer.

Tracks 2 and 3 split the rest by conflict surface, now along a sharper line than before: **Track 2
owns what the generator and the pipeline produce**, Track 3 owns **what the generated application
does at runtime**. Track 2 therefore takes the CLI apply/deploy/update, publication, DR engine,
module template and module test surfaces: the `.env.example` derivation (SA193), the backup TLS
contract (SA198), the supply-chain pinning and scanners (SA202), the shared test stub (SA195), and
the restyle (SA192). Track 3 takes orgs tenancy, purge, the settings and privileged/runtime-role
templates, the billing and auth transaction boundaries, and the generator's rendering strictness:
SA199, SA200, SA196, SA201, SA203, SA190.

Track 3 now carries six tickets to Track 2's five, but four of Track 3's are Small or Trivial by
the audit's own effort column, and its two substantial ones (SA196, SA190) were already scheduled.
Track 3 completed its independent RLS predicate work and privileged-command work, while Track 2
delivered SA186 and SA187.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA194 | yes | yes | yes | **yes** | **yes** |
| 2 | SA193 | yes | yes | yes | **yes** | no |
| 3 | SA199 | yes | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  `bap-web` migration, the property extension, public templates, and the portal's extension
  documentation.
- Track 2 owns `scripts/publish_module.py`, the module-shipped page templates and stylesheets, the
  module test-settings stubs and the shared test commons, the generated `base.html`, the CLI apply,
  deploy and update commands (`apply_command.py` with its env-sync steps, `deployment_commands.py`,
  `railway_utils.py`, `module_commands.py`, the vintage check), `contracts/module_options.py` with
  the `*_env_var` declarations in `module.yml` and the `.env.example` template, version
  expectations in tests, and the blog/notifications credential comparisons. It additionally owns,
  for the audit work, `quickscale_core/dr_engine/` (`primitives.py` command builders and their
  `orchestration.py` callers), `.github/workflows/`, the `[build-system]` blocks of every package,
  and `ruff.toml` — plus the new scanner and workflow-lint gates, whose `scripts/gate_registry.json`
  entries Track 2 writes and reconciles with Track 1 at merge.
- Track 3 owns the isolation-conformance runner, `orgs/tenancy.py` and its checks, the orgs policy
  template/tests, `purge_organization.py` and the account-delete obligations, the privileged
  command and runtime-role stations (`orgs/apps.py`, `production.py.j2`, `start.sh.j2`,
  `db/init.sql.j2`, `development_commands.py`, the SA90 emission fixture), and the generator's
  Jinja environment. It additionally owns the generated settings templates as a whole
  (`base.py.j2`, `production.py.j2`, `local.py.j2`, including the `REST_FRAMEWORK` and logging
  middleware blocks), `billing/services.py` and `billing/views.py`, `auth/views.py`, and the blog
  rate limiter.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** The shared closeout set is this roadmap, [CHANGELOG.md](../../CHANGELOG.md),
  and the owning audit: the arch audit for SA193 and SA190, the tech audit for SA198, SA199, SA200,
  SA201, SA202, SA203, and the parts of SA190 it also records. SA191, SA153, SA192, SA195, SA194,
  and SA196 have no owning audit row; their evidence goes to the changelog, SA191's also to the
  migration playbook. All are Markdown with no generated consumer, but the tech audit is now a
  six-ticket shared file across two tracks, so its closeouts are the hottest merge surface in this
  cycle — each ticket edits only its own finding's entry.
  Code-adjacent overlaps that cross tracks: SA153 edits the extension and organizations
  documentation; SA192 restyles the `auth` account templates while SA190 and SA199 edit the
  account-delete view, so whichever lands second re-runs the auth tests; SA196 turns strict
  rendering on for every generator template, including the `.env.example` template SA193 rewrites,
  the settings templates SA200 and SA201 edit, and the generated `base.html` SA192 restyles, so its
  fixes may reach both other tracks' files and whichever lands second re-runs the generator tests
  and the SA90 emission fixture; and SA200's `check --deploy` station and SA202's workflow-lint
  gate both add rows to `scripts/gate_registry.json`, which Track 1 also owns. The serialized queue
  covers them: each track resolves the shared set at its own merge, after the previous merge lands,
  then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [x] **SA180 — Derive the gate-parity count oracles from the registry.**

- [x] **SA152 — Verify maintainer migration modes and their runtime compatibility.**

- [ ] **SA194 — Unblock in-place beta migration at the contract-vintage gate.**

  **Context:** SA185 made `quickscale apply` refuse a project whose recorded `project_contract` is
  below every installed module's declared minimum — now `0.89.0` for `orgs` — unless the
  acknowledgement flag is passed. The in-place beta migration shells out to a bare
  `quickscale apply` and nowhere mentions the contract vintage, so a beta site generated at 0.88.0
  or earlier, which is the only kind of recipient the mode exists for, halts at that step. By then
  four steps have already rewritten the recipient's working tree — managed infrastructure files,
  `pyproject.toml`, `frontend/package.json`, and `quickscale.yml` — and the run ends
  `in-place-partial` and `blocked`, skipping the React-surface copy and the verification stack. A
  stateless recipient does not escape it: an absent `project_contract` resolves as behind, and the
  only pre-apply step that touches recipient state never writes that key.

  The gap is invisible to CI because the beta-migration smoke gate shims `quickscale` so `apply`
  exits 0 unconditionally. The gate exercises the in-place path without ever observing the CLI that
  path invokes, so it is green today and would stay green through any refusal, gate, or regression
  in the real command. That blindness also explains why the fifth declaration of the privileged
  command set, the copy inside the migration tool that the cross-station contract test does not
  cover, is currently only assumed to be held honest by this gate.

  Fix the policy at the one callsite. A preflight that reads the recipient's recorded contract
  against the shipped manifests and refuses before any mutating step is the better shape than
  passing the acknowledgement, because it moves the refusal ahead of the damage; passing the
  acknowledgement is defensible only if the infrastructure-copy step genuinely performs all three
  `orgs` adoption steps, which must be checked against the manifest before choosing it.

  **Acceptance:** an in-place continuation against a recipient whose recorded contract is behind
  the shipped manifests either completes or refuses before the first mutating step, never aborts
  between them, and the refusal names the adoption steps; the chosen policy is recorded in the
  migration playbook, which currently documents the continuation order without mentioning the gate
  at all. The smoke gate runs the real `quickscale apply` on the in-place path instead of a shim
  that always succeeds, with the recipient fixture carrying a pre-`0.89.0` contract, and fails if
  the path regresses. With the real CLI in the loop, confirm the gate reaches the migration tool's
  own required-runtime-command validator, so the fifth privileged-command station is held honest by
  something observed rather than assumed. Fresh-first mode's behavior is unchanged. The latest
  tech-audit pass swept a different surface and no longer carries this finding or its smoke-gate
  tooling gap as live rows, so the evidence above is the ticket's own and the closeout goes to the
  changelog rather than to an audit entry.

  **Surfaces:** `quickscale_devtools/.../beta_migration.py` at its apply and in-place execution
  sites, `scripts/check_beta_migration_smoke.py`, the migration playbook, and the tech audit.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale with the fresh-first migration tool.**

  Use `make beta-migrate-fresh` with `bap-web` as donor and a fresh scaffold generated with the same
  slug as recipient, continuing manually only where the tool emits `pending_manual_actions`.

  **Context:** `bap-web` is the beta site behind the property portal. It already runs `listings`, `forms`, and a
  project-owned `properties` app with concrete models, a catalog seed command, a public
  `/api/properties/` endpoint, and React property pages. It was generated on an older QuickScale, so
  building the portal on it first requires catching it up to the current release.

  The fresh-first mode is the documented primary path: a fresh scaffold with the same slug receives
  the donor's custom content, so infrastructure files start correct instead of being merged. The
  migration is the first real run of the tools that SA152 verified on fixtures, which is why it
  waits for that verification and for SA194 — the tool's in-place mode aborts mid-run at the
  contract-vintage gate, and its smoke gate shims the CLI so it cannot observe that or any other
  real refusal. Manual continuation is expected where the tool stops safely; the value of
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
  restore, and listing, form, and user counts match before and after. Redeploy through
  `deploy railway`. No property-portal features,
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

- [ ] **SA193 — Derive the generated `.env.example` credential contract from module manifests.**

  **Context:** `module.yml` already declares every credential variable a module needs, by name,
  with a type, default, Django setting, and description — and the manifest layer already projects
  declarations like these into generated wiring. `.env.example` escaped that. Its content is
  hand-written Python per module: a render function, a marker-splice implementation, and a wrapper
  in the apply command, plus a named core step re-exported through two `__init__` stations. Three
  modules have that treatment. `storage` and `backups` each declare two object-storage credential
  variables and have none, so a user enabling private-remote backups meets a configuration error
  naming a variable their generated `.env.example` never mentioned. The notifications variables
  appear a fourth time, hardcoded in the `.env.example` template under the same markers the apply
  step splices on.

  The cost is measured, not projected: adding one credential-bearing module option is an
  eight-station edit across two packages with no gate detecting omission, and the omission has
  already happened twice, silently, in shipped modules. The three splice implementations are the
  same algorithm copied verbatim, varying only in marker text, resolver, and log message, so any
  correctness fix to it — encoding, idempotency, a missing trailing newline — must be applied three
  times and will be applied to two.

  The steelman is real and shapes the fix rather than blocking it: the three implemented blocks
  carry bespoke prose that a type and a default cannot produce, and that guidance should not be
  lost or pushed into a config schema. Prose can hang off a derived set; it does not have to
  replace one.

  **Acceptance:** a conformance check fails when any `*_env_var` option declared in any `module.yml`
  has no placeholder in the generated `.env.example`, and it lands first, failing for `storage` and
  `backups` — that failing check is the specification for the rest. The managed blocks are then
  rendered from the declared option set in one place for every enabled module, under the existing
  marker convention, retiring the three hand-written triples and the static template copy;
  module-specific prose survives as manifest-hung text or one optional hook. Output is
  byte-identical to today's for the three covered modules, so existing projects see no spurious
  diff on their next `apply`, while `storage` and `backups` gain placeholders — a deliberate
  behavior change for existing projects, recorded as one. If the settled position is instead that
  `.env.example` is curated documentation rather than a derived contract, the ticket closes by
  recording that in `decisions.md` and the generated-file ownership doc with an explicit rationale
  for excluding `storage` and `backups`; silence is not an outcome. This closes the arch audit's
  highest-ranked finding, the only one with a live defect rather than a scheduled trigger.

  **Surfaces:** the apply command's env-sync render and splice functions, the named core env-sync
  step and its two re-export stations, `contracts/module_options.py`, the `.env.example` template,
  the five declaring `module.yml` files, the apply and env-sync tests, the generated-file ownership
  doc, and the arch audit.

- [ ] **SA198 — Carry the database's TLS settings into the backup and restore commands.**

  **Context:** `_build_pg_dump_command` and `_build_pg_restore_command` destructure the Django
  `settings_dict` by hand and read only `HOST`, `PORT`, `USER`, `NAME` and `PASSWORD`. Everything
  `dj_database_url` puts in `OPTIONS` — `sslmode`, `sslrootcert`, `sslcert`, `sslkey`,
  `connect_timeout` — is discarded, so both commands fall back to libpq's default `sslmode=prefer`:
  TLS if the server offers it, plaintext if it does not, and no certificate verification either
  way. A deployment whose `DATABASE_URL` demands `sslmode=verify-full` has Django verifying the
  server certificate on every request while the one process that moves the entire database over the
  network verifies nothing. The audit confirmed empirically that the TLS parameters do land in
  `OPTIONS`, so this is a dropped value, not a missing one.

  Database dumps are the highest-value artifact this system produces, which is what lifts an
  omission to an S2. The precondition — a remote or managed PostgreSQL that accepts non-TLS
  connections — is the ordinary Railway case, not an exotic one.

  The audit also names the structural reason: connection parameters are destructured by hand in at
  least three places (both command builders and `start.sh.j2`'s psycopg2 connect), each picking a
  different subset, because nothing owns *how this system connects to its database*. The fix should
  leave one owner behind rather than a fourth hand-written subset.

  **Acceptance:** `pg_dump` and `pg_restore` run under the same TLS posture as the application's
  own connections — the relevant `OPTIONS` keys are translated into libpq environment variables
  (`PGSSLMODE`, `PGSSLROOTCERT`, `PGSSLCERT`, `PGSSLKEY`, `PGCONNECT_TIMEOUT`) alongside the
  existing `PGPASSWORD`, never into argv, so the standing no-secrets-in-argv rule is preserved. A
  regression asserts that a settings dict carrying `sslmode=verify-full` and an `sslrootcert` path
  produces a child environment demanding both, and that a dict with empty `OPTIONS` behaves exactly
  as today. The translation lives in one function that every connection-parameter consumer calls,
  and a test fails if a builder reads `settings_dict` fields directly instead. The deliberate
  behavior change is recorded as one: a deployment whose URL requests strict TLS will now fail its
  backup if the server cannot satisfy it, where it previously succeeded in plaintext — that is the
  point, and the release note says so. No change to backup contents, naming, or the DR gate's
  semantics.

  **Surfaces:** `quickscale_core/.../dr_engine/primitives.py` command builders, their
  `dr_engine/orchestration.py` callers, the DR tests, `start.sh.j2`'s connect if the shared owner
  absorbs it, the operations documentation, and the tech audit.

- [ ] **SA202 — Pin the publishing supply chain and add the missing CI scanners.**

  **Context:** `publish.yml` pins two third-party actions to `@release/v1`, which is a **branch**,
  not a tag: whoever can push to it changes what runs inside the job that holds the OIDC
  trusted-publishing identity. Poetry is installed unpinned in the same workflow, and every package
  in the monorepo declares `requires = ["poetry-core"]` with no upper bound, so the build backend is
  whatever resolves at build time. None of this is exploitable by a defect in this repository; all
  of it is trust extended to something outside it, on the exact path that would upload the release
  the project is currently holding.

  The audit reached no conclusion at all about CVE exposure, because no dependency scanner exists
  to run — that silence is a tooling gap, not a clean result. The same holds for secret scanning:
  the sweep found no committed secret, but that rests on greps. Both belong with the pinning work,
  because they are the same job's hygiene and because a workflow linter is what keeps the pinning
  caught rather than re-derived by the next audit.

  **Acceptance:** every third-party `uses:` in every workflow is pinned to a full commit SHA with
  the human-readable version in a trailing comment; Poetry is installed at a pinned version; every
  package's `[build-system]` declares a bounded `poetry-core` range. A workflow linter (`zizmor` or
  `actionlint`) runs as a registered gate and fails on an unpinned `uses:` ref and on a workflow
  missing a top-level `permissions:`, so the pinning cannot silently regress. Dependency scanning
  (`pip-audit` against `poetry.lock`) and secret scanning run in CI, each as a registered gate with
  its failure policy stated — including whether a new advisory fails the build or files a finding,
  which is decided here rather than left to the tool's default. Ruff's `S` rule set is selected and
  its findings are either fixed or per-line suppressed with a reason; `ASYNC` is selected only if
  the tree has async code to govern, and otherwise recorded as not applicable. The gate registry
  rows and the parity oracles they feed are updated in the same change and reconciled with Track 1
  at merge. Publication behavior is otherwise unchanged; this ticket publishes nothing.

  **Surfaces:** `.github/workflows/` (all four), the `[build-system]` block of every package,
  `ruff.toml`, `scripts/gate_registry.json` and the parity oracles, the publication procedure doc,
  and the tech audit.

- [ ] **SA195 — Share one module test-settings stub instead of copying it per module.**

  **Context:** The commit that restyled the blog, CRM, and listings Django pages also minted three
  byte-identical `tests/templates/base.html` stubs and three near-identical template-rendering
  suites. The argument that would justify per-module copies is that publication splits each module
  with its own prefix, so a module must stay self-contained — but those same three suites already
  import a repo-root shared test commons, so the modules' own imports contradict it. Whatever
  contract governs that commons today governs the stub too. SA192 restyles two further modules that
  carry their own divergent stubs, and the promotion inventory queues more behind them.

  The remaining three module stubs are not identical and predate the restyle; they are a separate
  question. This is presentation-free cleanup: no template output changes.

  **Acceptance:** the three byte-identical stubs resolve to one shared definition on the same terms
  as the existing shared test commons, or the copies are kept and a check asserts they stay
  identical, with the split constraint that forced them written down. Converge the three
  non-identical stubs only if the shared one renders their suites unchanged; otherwise leave them
  and record why. Module test suites pass unchanged, the publication split scope is unchanged, and
  the shared commons' portability contract is neither weakened nor newly claimed — if module tests
  are not in fact split-portable today, record that rather than fix it here. No styling, template,
  or rendering change; those belong to SA192.

  **Surfaces:** the blog, CRM, and listings test settings and template stubs, the shared test
  commons, and the affected module test suites.

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
  fails when a module page stops extending `base.html` or loses its module stylesheet. Each
  restyled module carries its own stylesheet, but its test-settings stub comes from the shared
  definition SA195 establishes rather than a new per-module copy. Django admin and notification
  emails are out of scope.

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

- [x] **SA197 — Run the hosted gate set on integration branches.**

- [x] **SA181 — Derive expected versions in tests from the repository version.**

- [x] **SA184 — Make `quickscale deploy railway` re-runs read live state and fail hard.**

- [x] **SA185 — Enforce contract vintage when upgradable code meets an older project.**

- [x] **SA186 — Require a fast-forward before publication force-pushes a split branch.**

- [x] **SA187 — Reject non-ASCII tokens and signatures as authentication failures.**

- [x] **SA182 — Enroll marker-declared tenant models in classification and policy refresh.**

- [x] **SA183 — Refuse to purge an organization with a live Stripe subscription.**

- [x] **SA177 — Verify the predicates of enrolled RLS policies.**

- [x] **SA188 — Settle the privileged-command set behind one declaration.**

- [x] **SA189 — Provision the runtime database role in one place under one name.**

- [ ] **SA199 — Keep external calls out of transactions and hold the webhook lock.**

  **Context:** Two boundaries in the same payment path get the transaction/network relationship
  backwards, in opposite directions.

  Account deletion holds a transaction open across a Stripe round trip. `form_valid` opens
  `transaction.atomic()`, row-locks every organization the user owns, and then cancels the
  subscription over the network inside that block. A slow or hanging Stripe call holds the org row
  locks for its entire duration, and every other request touching those organizations queues behind
  a third party's latency. Billing's own service layer is careful about exactly this; `auth/views.py`
  is not, which is what the audit calls out as outbound-call discipline being re-derived per module
  rather than stated once.

  Webhook processing does the reverse: it takes `select_for_update()` on `WebhookEvent` inside an
  `atomic()` block that closes immediately after the `processed` check, so the lock is released
  before the handler runs. Two concurrent deliveries of the same event both take and release the
  lock, both see `processed == False`, and both run the handler; the loser of the subscription
  upsert race trips the unique index and is recorded `processed=False` with an error, so the row
  now lies about an event that was in fact processed. That violates the project's stated webhook
  idempotency invariant. The money path survives it — `credit_user` re-checks inside its own
  transaction and a partial unique index makes a double credit impossible — which is why this is a
  correctness and observability defect rather than a financial one.

  The comment defending the webhook slicing is right about its goal (keep Stripe round trips out of
  a long transaction) and silent about what replaces the lock as the idempotency mechanism during
  the unlocked window. Nothing does. The fix must honor both halves at once, which is why these two
  findings share a ticket: they are one rule — *hold the lock for the whole claim, make the network
  call outside it* — applied at two callsites that each got one half right.

  **Acceptance:** account deletion performs no network I/O inside `transaction.atomic()`; the
  atomic block does the guard check and collects what must be cancelled, and the Stripe call runs
  outside it, with the window this opens (a user deleted whose subscription cancellation then
  fails) handled explicitly rather than ignored — either by cancelling before committing the
  deletion or by recording the outstanding cancellation for retry, and the choice is written down.
  Webhook processing claims the event before releasing the lock: either the `atomic()` spans the
  whole handler, or the short atomic performs a conditional claim (`processed = false AND
  processing_started_at IS NULL`) and a zero-row result is treated as a duplicate, in which case a
  staleness timeout releases a claim whose worker died. A concurrency regression drives two
  `handle_stripe_event` calls for one event id from two threads against a real PostgreSQL
  connection and asserts the handler body runs exactly once and no row is left claiming a failure
  that did not occur. While in `billing/services.py`, `search_customers` stops building its Stripe
  Search Query Language string by unescaped f-string interpolation: references containing `'`, `\`
  or a newline are rejected or escaped, with a test, closing a query-injection sink that is safe
  today only by virtue of its two current callers. The last-owner backstop, the SA183 live-
  subscription purge refusal, and the existing idempotency constraints are unchanged.

  **Surfaces:** `auth/views.py` account deletion, `billing/services.py`
  (`handle_stripe_event`, `cancel_current_subscription`, `search_customers`), the billing
  cancellation seam, the auth and billing tests, and the tech audit.

- [ ] **SA200 — Gate the proxy and correlation-id settings the generator emits.**

  **Context:** Two independent defects in the generated settings templates, both trivial, both in
  the same two files, and both invisible to every test the repo runs because nothing ever checks a
  generated project's deployment posture.

  `production.py.j2` sets `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
  unconditionally, while the same file lets an operator set `USE_X_FORWARDED_FOR=False` for a
  single-host deployment — a combination the project's own contract explicitly invites. In that
  cell the app stops trusting `X-Forwarded-For` and keeps trusting `X-Forwarded-Proto` from anyone,
  so a client reaching the plaintext listener with `X-Forwarded-Proto: https` makes
  `request.is_secure()` true: the SSL redirect stops firing and Django sets `Secure` session and
  CSRF cookies on a plaintext response. `NUM_PROXIES` is already gated on the same flag; this
  assignment was not.

  `base.py.j2`'s `CorrelationIdMiddleware` accepts `X-Request-ID` verbatim with no length or
  character-class check, puts it in a `ContextVar`, and stamps it onto every log record the request
  emits and onto the response header. A 32 KB header multiplies the request's log footprint by its
  record count; a modest loop becomes a log-ingestion bill and, against a per-line cap, truncated
  lines exactly where the attacker's traffic is. Neither header injection nor log injection is
  reachable — Django rejects newlines in headers and the JSON formatter escapes the value — so what
  is left is purely unbounded size and cardinality, which nothing bounds.

  The shared cause is the tooling gap: nothing in CI boots or inspects a generated project's
  settings, so a deployment-posture regression in a template ships silently.

  **Acceptance:** the generated `production.py` leaves `SECURE_PROXY_SSL_HEADER` unset when
  `USE_X_FORWARDED_FOR` is false, with the assignment ordered after that flag's definition, and a
  rendered-template test asserts both cells. The correlation-id middleware accepts a client value
  only when it matches a bounded pattern (`^[A-Za-z0-9._-]{1,64}$`) and generates a UUID otherwise;
  a request carrying a 10 KB `X-Request-ID` is asserted to log a fresh UUID. CI runs
  `manage.py check --deploy` against a freshly generated project in both forwarding cells and fails
  on a new warning, as a registered gate — the station that would have caught the first defect and
  that guards the whole settings-template surface from here. The default proxied deployment's
  behavior is unchanged; a single-host operator who was relying on the spoofable header to suppress
  a redirect loop now gets the redirect, which is the correct behavior and is recorded as a
  deliberate change.

  **Surfaces:** `production.py.j2` and `base.py.j2` in the generator's settings templates, the
  rendered-template tests, `scripts/gate_registry.json` and the CI workflow for the deploy-check
  station, the deployment documentation, and the tech audit.

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

- [ ] **SA196 — Fail hard on undefined generator template context.**

  **Context:** The generator's Jinja environment uses the default undefined behavior, so a missing
  or renamed context key renders as empty text with no error — confirmed for plain substitution,
  loops, and filters alike. SA189 moved the runtime role's attributes and grant statements out of
  template literals and into context variables, which means a rename now silently emits a role
  creation statement with no `NOSUPERUSER`, no `NOBYPASSRLS`, and no grants. The only thing
  standing between that and a generated project is a content assertion in one test file.

  The rest of the system applies the fail-hard principle to every configuration error, missing
  dependency, and invalid runtime state. The generator's own rendering is the station where it was
  never applied, and SA189 made that station load-bearing for the privilege contract.

  **Acceptance:** the generator's Jinja environment raises on an undefined context key instead of
  emitting empty text, and a regression test renders a template with a missing key and asserts the
  failure. Generation still succeeds for every shipped template and module combination, and the
  emission fixture stays byte-identical; any template that relied on undefined-renders-empty is
  fixed by supplying or removing the key, never by restoring a permissive default. Fixes may reach
  templates other tracks own, and they are in scope here. Additionally close the tech audit's
  generated-project smoke-boot gap: CI generates a project, runs its `start.sh`, and hits
  `/healthcheck/`, so a template regression that survives strict rendering is still caught by the
  artifact refusing to boot. The repo has extensive rendered-template assertions and nothing that
  boots the result, and strict rendering is the half of that gap this ticket already owns.

  **Surfaces:** the generator's Jinja environment, any template rendering an undefined key,
  generator and emission-fixture tests, the CI smoke-boot station, and the tech audit.

- [ ] **SA201 — Give generated projects one throttling contract.**

  **Context:** Rate limiting in this system is per-module folklore. `forms` uses a DRF
  `ScopedRateThrottle`; `blog` hand-rolls a cache-counter limiter with its own IP normalization;
  everything else has nothing. The generated `REST_FRAMEWORK` block defines
  `DEFAULT_PERMISSION_CLASSES` and `NUM_PROXIES` but no `DEFAULT_THROTTLE_CLASSES` or
  `DEFAULT_THROTTLE_RATES`, and no billing view declares `throttle_classes` — so any authenticated
  org owner can POST `/billing/checkout/` in a loop, and each request makes one or two outbound
  Stripe calls. The failure is fleet-wide, not per-tenant: Stripe rate-limit exhaustion takes every
  other tenant's checkout and webhook processing down with it. `production.py.j2` tunes
  `NUM_PROXIES` with a comment explaining it is "so that DRF throttles are enforced consistently",
  which reads as though throttles are configured. They are not.

  `blog`'s limiter has its own two defects. It relies on `cache.add` plus `cache.incr` being
  atomic, which holds on Redis and not on `DatabaseCache` — and production without `REDIS_URL` is a
  configuration the template explicitly supports and `start.sh.j2` provisions a cache table for. In
  that cell concurrent requests read the same counter and write back the same increment, so the
  effective limit is far above the configured one, and the fallback branch has the same
  read-modify-write shape. Separately, its cache key replaces both `":"` and `"."` with `"_"`, so
  an IPv4 address and an IPv6 fragment can normalize into the same bucket — two unrelated clients
  sharing a budget, or one evading it.

  There is a structural obstacle worth naming up front: `base.py.j2` **replaces** the whole
  `REST_FRAMEWORK` dict after `MODULE_SETTINGS`, so a module cannot contribute DRF configuration at
  all, even though the settings-composition system exists to let modules contribute settings. The
  natural fix for the throttle defaults is exactly to make that block composable. The audit records
  the clobber as a watch item precisely because no module ships a `REST_FRAMEWORK` key today; this
  ticket is the one that would make one, so it fires the trigger and owns it.

  **Acceptance:** the generated settings declare `DEFAULT_THROTTLE_CLASSES` and
  `DEFAULT_THROTTLE_RATES` with conservative `user` and `anon` scopes, documented as defaults an
  operator raises; the checkout and billing-portal views carry an explicit tighter `throttle_scope`,
  and a test posts past the rate and asserts a 429. The `REST_FRAMEWORK` composition stops
  clobbering module-supplied DRF configuration — modules merge into it on the same terms as every
  other settings key — and a test proves a module-contributed throttle rate survives composition.
  `blog`'s limiter either requires a backend with atomic `incr` and fails closed on boot when one
  is absent, or moves its counter to a single atomic `UPDATE ... RETURNING`; a regression drives it
  from N threads against a `DatabaseCache`-configured settings module and asserts the observed
  count never exceeds the limit — the runtime confirmation the audit marks this as needing. The
  throttle identity is hashed rather than character-substituted, so no two distinct client
  identifiers share a bucket. The rate defaults must not break legitimate polling clients, and the
  numbers chosen are written down with the reasoning.

  **Surfaces:** the `REST_FRAMEWORK` block and settings composition in `base.py.j2`, the
  `NUM_PROXIES` comment in `production.py.j2`, `billing/views.py`, `blog/views.py` and its cache
  key helper, `forms/throttles.py` if a shared scope absorbs it, the module settings-composition
  tests, and the tech audit.

- [ ] **SA203 — Narrow the privileged-command exemption in the orgs boot path.**

  **Context:** `QuickscaleOrgsConfig.ready()` opens with `if _is_privileged_command(): return`,
  which exits `ready()` entirely and so skips three installations that come after it: the AF9 GUC
  priming wrapper with its `connection_created` signal, the SA70 `pre_delete` last-owner backstop
  receiver, and the SA1.3 tenant-isolation system check registration. The intent — skip the
  BYPASSRLS boot guard during `migrate` — is served by `_check_rls_role()` alone. The asymmetry is
  the tell: the *other* exemption, `QUICKSCALE_ALLOW_BYPASSRLS=1`, returns from inside
  `_check_rls_role` and leaves the rest of `ready()` intact. The block's comment explains why the
  guard is exempted and says nothing about the other three, which reads as a consequence of
  `return` rather than a decision.

  Concretely: a data migration that deletes `OrganizationMembership` rows under
  `QUICKSCALE_PRIVILEGED_COMMAND=migrate` runs with the last-owner invariant unenforced and can
  leave an organization with members and no owner — a state the application's own guard exists to
  prevent and cannot repair afterwards. The priming wrapper's absence is harmless in this window
  because the privileged role bypasses RLS anyway, and `check_tenant_isolation` is invoked
  explicitly by the Makefile, which is what keeps this below the backstop's own severity.

  This is the fifth item in the privileged-command lineage after SA188 and SA189, and it is the
  one about what the exemption *reaches* rather than what it contains.

  **Acceptance:** `ready()` skips only `_check_rls_role()` under a privileged command; the priming
  wrapper, the `pre_delete` receiver, and the system check registration install unconditionally. A
  test sets `QUICKSCALE_PRIVILEGED_COMMAND=migrate`, re-runs `ready()`, and asserts the last-owner
  receiver is connected to `pre_delete`. Existing migrations are checked before landing for one
  that legitimately deletes owner memberships — if one exists it gets an explicit, named bypass
  rather than the backstop being weakened. The BYPASSRLS guard's own exemption semantics, the
  `QUICKSCALE_ALLOW_BYPASSRLS` path, and the privileged-command contract test are unchanged.

  **Surfaces:** `orgs/apps.py` `ready()`, the orgs boot tests, and the tech audit.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings and their growth triggers. Items they record without scheduling — the watchlists
and watch notes, the beta-migration ownership taxonomy whose derivation `decisions.md` § Release
scope safeguards explicitly withholds authorization for, and the later deletion-coordinator options
— stay there until a trigger fires. Three are no longer among them, because a ticket now carries
each: the external-provider conformance gap is in SA190's acceptance; the dependency-scan, secret-
scan and workflow-lint gaps are SA202's; and the generated-project smoke-boot gap is SA196's. Two
watch notes are deliberately fired rather than carried: the `REST_FRAMEWORK` clobber, which SA201
resolves because SA201 is the change that would otherwise trigger it, and the DR
`pg_dump`/`pg_restore` dependence that SA193 makes live and SA198 fixes. The remaining watch
notes — persistent `QUICKSCALE_PRIVILEGED_COMMAND`, the analytics single-quote escape, the
`BackupError` host echo, `set_railway_variable`'s swallowed reason, and future-dated notification
timestamps — stay unscheduled with their triggers intact. The standing
no-`teams`/no-third-updater scope, internal-only devtools, presence contracts, and resource
safeguards live in
[decisions](decisions.md) and [validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
