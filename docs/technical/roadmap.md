# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[decisions.md § Module Conventions](decisions.md#module-conventions): the convention tickets deliver
it across all three tracks and SA215's conformance test closes it. `bap-web` is then ported once, onto the
standardized names (SA191), and carries the first property portal in a project-owned extension
(SA153). Capabilities are generalized only after that project proves their value.

**Release status.** 0.88.0 is published and carries two S1 billing defects fixed on `v89` (with
real Stripe keys, every webhook and every checkout fails); the fix ships in 0.89.0, which is not
published yet ([publish_procedure.md](publish_procedure.md)).

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA235 | Declare module UI paths in manifests and render host routes from discovery | post-v88 | 1 | — | Deferred |
| SA237 | One org-role check and root-only type-stub exemptions | post-v88 | 2 | — | Deferred |
| SA238 | Split-facade conventions: log channels, re-exports, and view discovery by content | post-v88 | 3 | — | Deferred |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | post-v88 | 1 | — | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | post-v88 | 1 | SA235, SA237, SA238 | Deferred |
| SA241 | Record the React-frontend and public-page prerender decisions for SA153 | post-v88 | 2 | — | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191, SA241 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA214 | Harden the fresh-first migration tool into the standard upgrade path | post-v88 | 1 | — | Deferred |
| SA216 | Disable and anonymize accounts instead of deleting the user row | post-v88 | 3 | — | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA235 ──► SA191 ──► SA153 ──► SA204 ──► SA214 ──► SA154 (inventory)
Track 2: SA237 ──► SA241
Track 3: SA238 ──► SA216
     critical path: SA238 → SA191 → SA153
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Slices.** Large tickets list `Slices:` in their body. Each slice is one implementer session
with a fresh context, scoped to that slice's text and named surfaces, and ends with a short
handoff note (what landed, what is next, what to watch) committed with the work. A ticket closes
when its last slice lands; slices are not scheduled. A slice becomes its own ticket only when it
can start earlier or on another track (SA240, SA241, SA242).

**Critical path.** The conventions land while renames are still cheap: `bap-web` is not yet
ported, and SA204 has not frozen the migration history. SA234 untangled the split facades
before SA191 edits `apply`, and SA238's re-export rule follows SA234's contract, so the facade work
runs ahead of SA191. SA204 freezes migration history before any post-SA153 module schema change.
SA154 is an inventory, not work.

**Parallel start.** SA235 (Track 1) and SA237 (Track 2) can start now; SA238 (Track 3) starts
now that its dependencies have landed, and SA216 follows it. SA241 (Track 2) follows
SA237 and must land before SA153. SA215's closing pass landed and closed inventory sections 1–41
(the two cells the seventh pass corrected are carried by SA235). The coherence audit's
seventh pass (sections 42–47, D43–D48) is carried by SA235, SA237, and SA238 (SA236 closed rules
42–43). Each begins by recording its decision (proposed rules 41 and 44–46 in the
[inventory](../planning/module-conventions-inventory.md#rules-proposed-seventh-pass)) and closes
its own item, harness clause, and inventory section, and SA191 waits for all of them.

**Off the critical path.** SA216 follows SA215 because both change auth's views, orgs' removal
path, and the user-referencing models.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA235 | yes | yes | yes | **yes** | **yes** |
| 2 | SA237 | yes | yes | yes | **yes** | no |
| 3 | SA238 | yes | yes | yes | **yes** | **yes** |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the quality ratchet
  (`scripts/check_quality.sh`, `quality_baseline.json`, `quality_waivers.json`, and the
  monotonicity check), the generated `urls.py.j2` and the theme's social seam pages, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  migration-history freeze gate and `decisions.md` § Clean-Break Migration History, the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation, and, for the conventions, module identities, models and their
  `0001_initial`, module READMEs, and module templates, static files, and template tags, with the
  module page templates and the generated `base.html`, and cross-module imports and settings reads,
  and the `services.py` public surface.
- Track 2 owns `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package, `ruff.toml`, the test-settings stubs, the CLI apply/deploy/update commands and
  `contract_vintage.py`, the module manifests' `contract_vintage` blocks,
  `contracts/module_options.py` and the `.env.example` template, `quickscale_core/dr_engine/`,
  and the billing module (`billing/services.py`, `billing/views.py`, `billing/adapter.py`, and its
  docs), the split facades of the CLI commands, `dr_engine`, and billing with the tests that patch
  them, the blog and storage upload-path builders, and, for the conventions, the manifest option schema and the CLI's `module_config`,
  module settings names, and `is_enabled()`.
- Track 3 owns the orgs tenancy, purge, removal-obligation, and boot path (`orgs/apps.py`,
  `orgs/removal.py`), the privileged-command and runtime-role stations, the
  `quickscale_core.runtime` settings facade, the generated settings templates (`base.py.j2`,
  `production.py.j2`, `local.py.j2`), the generator's Jinja environment, `auth/views.py`, the
  blog rate limiter, the generated `pyproject.toml.j2` `[build-system]` block, orgs'
  `quickscale_orgs_create_site_org` command (SA240), and the personal-data inventory (SA242), and, for the
  conventions, the `quickscale_core.runtime` helpers, module `checks.py` and `exceptions.py`,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, and the conformance harness with its registry row (SA215).
- **Cross-track edits.** Outside the conventions, no queued ticket edits another track's surfaces;
  a ticket that does lands through the serialized merge queue. SA215 touches every module and crosses every
  track, so it lands in module-sized slices through that queue, merging `v89` before each slice.
  The seventh-pass convention tickets (SA235–SA238) also cross tracks: each adds its own harness
  clause (a Track 3 surface), and SA235 touches orgs' `TenantMiddleware`. They land through the
  same queue.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), both audits, and
  [decisions.md](decisions.md) (SA204, SA153, and SA215, which update the names it
  quotes from the shipped state). Each track resolves the shared set at its
  own merge, after the previous merge lands, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [x] **SA233 — Key the quality ratchet by qualified name and retire the rename waivers.**

- [x] **SA234 — Retarget test patches to defining modules and remove facade back-imports.**

- [ ] **SA235 — Declare module UI paths in manifests and render host routes from discovery.**

  **Context:** the generated `urls.py.j2` puts React shell routes for `blog/`, `listings/`,
  `forms/`, and `crm/` before the modules' own mounts. As a result, `reverse("quickscale_blog:post_list")`
  and `reverse("quickscale_listings:listing_list")` resolve to the shell, and the routes ignore each
  module's `_ENABLED` switch. Module paths are also repeated as literals in the generator
  templates, the theme's social pages (which hand-write the seam), `base.html.j2`, and orgs'
  `TenantMiddleware` (coherence D43 `mount-path-copies`, with prior items `theme-module-presence`
  and `module-lists-outside-members`; tech audit §9). Once `bap-web` ports, a URL move becomes a
  one-way door, so this lands before SA191.

  **Scope:** record rule 41 (D43, recommended option A) after the maintainer decides whether the
  modules' server-rendered indexes stay reachable. Each module with a React surface declares
  `spa_routes` in its manifest. The generator renders them after the module's own includes, and
  only for installed and enabled modules. Project-namespace route names become
  `quickscale_<module>:<name>`. The social seam pages render through `generator/seam.py`.
  `TenantMiddleware` reads its prefixes from orgs' URL names. Rule 40's detectors for rules 7, 31,
  and 37 read `generator/templates/**/*.j2` too (enforcement gap 13).

  **Acceptance:** a generated-project test proves that every module root URL name resolves to its
  own view, and a `^blog/?$` shell control fails it. No module path literal remains in the
  generator or theme templates or in another module, and the harness rejects one in a `.j2` file.
  `frontend.md` § URL ownership matches the code. The release notes give the user-owned `urls.py`
  step for each moved route.

  **Surfaces:** module manifests (`spa_routes`); `urls.py.j2`, the social seam pages,
  `base.html.j2`, `generator/seam.py`; orgs' `TenantMiddleware`; the harness; `frontend.md`;
  decisions.

  **Progress (SA235).** Rule 41 is recorded with option A (the module indexes stay reachable).
  The three flat modules (blog, listings, crm) declare `spa_routes`, which `apply` renders after
  the module includes and each adapter drops when its module is off; their shadowing shell
  reservations left `urls.py.j2`. The seam, both public social pages, `base.html.j2`, and
  `TenantMiddleware` read routes or paths by name; the harness's rules 7, 31, and 37 now read
  `generator/templates/**/*.j2` with controls; a generated-project test proves the module root
  URL names resolve to their own views. Remaining: social's and orgs' React surfaces do not yet
  declare manifest `spa_routes` (orgs' mode-inverted `/orgs*` reservations stay host-rendered and
  social's public pages stay host routes), forms' entrypoint renders only an inert mount-point div
  so its shallow paths keep a host reservation and it declares no `spa_routes`, and billing's
  `/billing/...` copies in `context_processors.py.j2` remain.

- [x] **SA236 — Make settings snapshots private and guard optional senders on `is_enabled()`.**

- [ ] **SA237 — One org-role check and root-only type-stub exemptions.**

  **Context:** billing's post-lock re-check (`_subscription_mutations.py`) re-implements orgs' role
  check with the string `"owner"` and an extra `is_active` test. Ten module `pyproject.toml` files
  carry `[[tool.mypy.overrides]]` blocks that CI never reads. Their coverage is uneven (anymail is
  missing from the root `mypy.ini`), and the harness exempts them with no listed exception
  (coherence D46 `org-role-check-copies`, D47 `mypy-overrides-unread`).

  **Scope:** record rules 44 and 45 (recommended option A for each). Billing calls
  `user_has_org_role(user, org, OrgRole.OWNER)` and keeps `is_active` at the call site. Delete the
  module overrides blocks, add any stub exemption the root needs, and remove the harness's
  `overrides` skip.

  **Acceptance:** the harness rejects an `OrganizationMembership` `role=` query outside orgs and
  any `[tool.mypy]` table in a module, each with a control case. The root mypy run passes.

  **Surfaces:** billing `_subscription_mutations.py`; module `pyproject.toml` files; root
  `mypy.ini`; the harness (Track 3, through the queue); decisions.

- [ ] **SA238 — Split-facade conventions: log channels, re-exports, and view discovery by content.**

  **Context:** module splits (auth, backups, billing, notifications, orgs) name their private files
  in three different forms, follow two re-export policies, and handle loggers two ways. Billing's
  logger moved silently from `…billing.services` to `…billing._subscription_mutations`. Rule 19's
  scan finds views by file name, so a third naming form would escape it (coherence D48
  `split-facade-conventions`). SA234 sets the re-export contract this ticket applies to modules.

  **Scope:** record rule 46. Private files in a split module log on the facade's channel. Module
  facades re-export public names only, under SA234's decision, and their tests patch the defining
  module. Rule 19 finds view code by content: a Django or DRF view subclass, or a function that
  takes `request`.

  **Acceptance:** the harness rejects `getLogger(__name__)` in a `_<name>.py` that has a facade, and
  a view class in an unscanned file name, each with a control case. No module facade re-exports a
  private name. The release notes list every log channel that moved since 0.88.0.

  **Slices:**
  - [ ] (a) Rule 46 decision entry and log channels: private files log on the facade's channel,
    the rule 28 clause, and the release-note list of moved channels.
  - [ ] (b) Re-exports: trim module facades to public names and retarget their tests' patches.
  - [ ] (c) Rule 19 finds view code by content, with its control case.

  **Surfaces:** loggers and facades in auth, backups, billing (Track 2), notifications, and orgs,
  with their tests; harness rule 19 and rule 28; release notes; decisions.

- [x] **SA239 — Derive blog and storage upload extensions from the validated image format.**

- [x] **SA215 — Enforce the remaining module conventions and close the inventory.**

- [x] **SA231 — Split long files and complex functions in batches, then make the quality gate fail.**

- [x] **SA232 — Split the long CLI command, `dr_engine`, and billing files.**

- [ ] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

  **Context:** under [decisions.md](decisions.md) § Clean-Break Migration History, each
  model-bearing module ships one `0001_initial` that is rewritten in place every release, and the
  only supported upgrade is a fresh database. Every rewrite adds to the hand-written transform each
  deployed project needs on its next upgrade. SA191 reseeds `bap-web`, so the freeze is needed at
  SA153's go-live, where the first non-reseedable tenant data appears, and before any module schema
  change reaches that project. It is a one-way door (arch audit
  `clean-break-schema-no-data-path`, option 1).

  **Acceptance:** decisions record that rule 1 of the clean-break decision is lifted from 0.89.0
  onward, the release the freeze lands in. Upgrades from earlier vintages, including 0.88.0,
  stay fresh-database-only. From 0.89.0 on, a schema change to a model-bearing module ships as a
  new incremental migration under the existing migration-quality gates. A registered gate fails
  when an existing migration file of a model-bearing module changes or disappears, with controls
  proving that it rejects an in-place `0001` edit and accepts a new `0002`.

  The gate compares against a checked-in manifest of the frozen files' content hashes (it works in
  shallow CI clones and needs no tag). Before merging, confirm no module schema change shipped
  between SA191's rebuild and the freeze, and prove on a restored `bap-web` copy that `migrate`
  from the frozen `0001` reproduces the FORCE-RLS parity baseline (the door is one-way). SA153's
  schema work is written as `0002+` migrations from the start. `test_module_migration_topology.py` changes from exactly
  one `0001_initial` to a `0001_initial` followed by an ordered chain, and its `0002` canary is
  inverted.

  **Surfaces:** decisions, the new gate with its hash manifest, registry row, and gate
  documentation, `quickscale_core/tests/test_module_migration_topology.py`, and the arch audit.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port.**

  Migrate `bap-web` into a new repository at `/home/victor/code/bap-web-new`, once, without the
  fresh-first tool: a fresh `quickscale plan` + `apply` recipient, then a coding assistant ports the
  donor by following [bap-web-migration-prompt.md](../planning/bap-web-migration-prompt.md).
  Hardening the tool is SA214. `experto-ai-web` is out of scope.

  **Context:** `bap-web` is the beta site behind the property portal, generated 2026-03-05 on
  v0.62.0 with the `showcase_react` theme and `auth`, `listings`, and `forms`. It carries a
  project-owned `properties` app (models on `AbstractListing`, a catalog seed command, a public
  `/api/properties/` endpoint), a heavily customized React design, and in-place edits under the
  vendored `modules/forms`.

  **Recipient.** Built as the playbook's "Running a migration iteration" section describes: before
  the release, from the unreleased checkout with modules embedded by
  `quickscale apply --split-refs-from-branches`; it repins to the sealed release before cutover.
  The donor stays read-only; every in-place `modules/forms` customization is re-expressed as
  project-owned configuration or extension, or reported as an upstream candidate.

  **Data.** It cannot move by backup and restore. The production database records `listings`
  0001–0003, `forms` 0001–0003, and `auth` 0001–0002 as applied and has no `orgs`, while current
  `listings` and `forms` ship a rewritten `0001_initial` that depends on `orgs` and a NOT NULL
  organization FK. Rehearse first: restore a production dump into a scratch PostgreSQL 18 and
  confirm the history inconsistency with `migrate --plan` against the recipient. The cutover
  rebuilds a fresh database. SA240's `quickscale_orgs_create_site_org` command creates the site's
  organization in the same deploy step as `migrate`. The catalog is
  then reseeded through `bap-web`'s own seed command, tenant-scoped to that organization under the
  restricted runtime role — never under BYPASSRLS. Users are
  re-invited; form submissions and other transactional rows are not carried. Media is carried over
  separately and verified.

  **Dependencies and ownership:** Billing stays disabled. An agent delivers everything up to a
  deploy-ready recipient and a rehearsed cutover script. The maintainer supplies the production
  dump, creates and archives the repositories, runs the Railway cutover, carries media, and
  re-invites users.

  **Acceptance:**
  - The prompt's done criteria pass and its report is recorded, including every adapted or
    excluded donor test with its reason and every upstream candidate.
  - `bap-web-new` records the current QuickScale version in `quickscale.yml` and its lock, imports
    the SA206 facade, hand-patches no QuickScale-owned contract, and has no edits under `modules/`.
    `.git`, `media/`, `.env`, and `poetry.lock` are not copied between trees.
  - Automated parity, no manual QA: the donor's pytest and Vitest suites pass in the recipient.
    The "old" side of every comparison is the live site, `https://buenosairesproperties.com` on
    Railway; the donor is not deployed locally. The donor's Playwright e2e suite passes against
    the live site and the local recipient, but only its read-only specs run against production;
    specs that submit forms or write data run only against the recipient. Screenshot diffs of home,
    catalog, detail, and contact differ by under 1% of pixels at desktop and mobile widths, with
    animations off. The recipient is seeded to show the same listings as the live catalog, and
    regions that show content the two sites don't share are masked, with each mask recorded. The
    live baseline screenshots are captured and kept before cutover, because the cutover replaces
    that site.
  - The carried `properties` models pass SA208's provider-ID system check. The FORCE-RLS table and
    policy counts equal a fresh project's with the same modules, and `check_tenant_isolation` passes.
  - `bap-web-new` becomes a new repository and redeploys through `deploy railway`; the old
    repository is archived. The pre-cutover database is retained until the reseeded site is verified,
    and the written rollback restores the previous deploy *and* that database.
  - No property-portal features (SA153) and no frontend stack change.

  **Slices:**
  - [ ] (a) Rehearsal: restore the production dump into scratch PostgreSQL 18 and record the
    `migrate --plan` inconsistency against a fresh recipient.
  - [ ] (b) Recipient and code port: generate the recipient, port the donor by the migration
    prompt, re-express the `modules/forms` edits, and record upstream candidates.
  - [ ] (c) Test parity: the donor's pytest and Vitest suites, SA208's check, FORCE-RLS counts,
    and `check_tenant_isolation`.
  - [ ] (d) Live parity: Playwright e2e and screenshot diffs, with the live baselines captured and
    kept.
  - [ ] (e) Cutover: reseed step under the runtime role, cutover script, and written rollback,
    rehearsed on the scratch database.

  **Surfaces:** the new `bap-web-new` repository and its reseed step; the migration prompt; the
  `forms` module only for upstreamed customizations.

- [x] **SA240 — Add the idempotent `quickscale_orgs_create_site_org` command for SA191's cutover.**

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

  A client-rendered page gives crawlers and link-preview bots an empty document, so catalog and
  detail pages must be prerendered or server-rendered for Open Graph and indexing. SA241 chooses
  that mechanism and records it, with the React-frontend decision, before this ticket starts.

  The launch needs property fields and galleries, explicit currency labels, attribute filtering
  and keyword search applied by the API, Spanish public pages, listing-linked inquiries into `crm`,
  and launch SEO including metadata, sitemap, and robots guidance. Currency labels must not imply
  exchange-rate conversion, and Spanish launch coverage does not require translating every
  QuickScale interface.

  New child tables, including gallery images, follow the child-table decision in
  [decisions.md](decisions.md) and the `test_rls_boundary.py` coverage pattern.

  **Acceptance:** under SA241's decisions, the `bap-web` project migrated by SA191 serves an organization-scoped React property catalog and
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
  claims that the module does not provide. Prerendering uses the mechanism SA241 approved. The
  marker-derived purge plan covers property rows without a vendored module edit. Every `*_id` field on a property model is classified through
  SA208's project-side declaration, and the SA208 system check passes in the project.

  **Slices:**
  - [ ] (a) Models: property fields, currency labels, and ordered gallery child tables, with
    forced RLS, boundary tests, SA208 classification, and purge coverage, as `0002+` migrations.
  - [ ] (b) Read API: published listings of the requested organization, with server-side keyword
    and attribute filters, and API-level isolation tests.
  - [ ] (c) React catalog and detail pages in Spanish on the app's design.
  - [ ] (d) Listing inquiry into a CRM record with a listing reference, and the search → detail
    → inquiry journey.
  - [ ] (e) Prerender or server render, Open Graph tags, sitemap, and `robots.txt`, with the
    crawler test and rendered-page isolation.

  **Surfaces:** the project-owned property extension, its API and React pages, and the project's
  prerender build and deploy step; listings/blog/forms/CRM seams only where needed; extension
  documentation.

- [ ] **SA241 — Record the React-frontend and public-page prerender decisions for SA153.**

  **Context:** SA153 needs two decisions before any code: which pages are React, and how React
  public pages reach crawlers that run no JavaScript. Split out of SA153 so they are settled while
  SA191 is in flight.

  **Acceptance:** decisions record that React is the standard frontend for new application and
  public pages; `auth` and `billing` stay Django-rendered on the shared design (SA192); the
  existing module-shipped Django pages (blog, listings, CRM dashboard) stay Django-rendered on that
  design until an SA154 item promotes a React replacement; Django admin stays as shipped. A second
  entry chooses the prerender or server-render mechanism for catalog and detail pages, compares the
  options considered, and adds any new frontend dependency under the approved-stack rule.

  **Surfaces:** decisions; `frontend.md` where it states the frontend split (SA235 also edits it,
  so whichever lands second resolves it at merge).

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or prerender step into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Items that add tenant tables build on marker-derived enrollment
  and purge, not on module-source edits, and items that change a module schema ship an incremental
  migration on SA204's frozen history. Close when every item is promoted or dropped with rationale.

- [ ] **SA214 — Harden the fresh-first migration tool into the standard upgrade path.**

  Make `make beta-migrate-fresh` the standard way to move a QuickScale project onto the current
  release, so the next beta-site upgrade needs no one-off prompt. Donors: `bap-web` as it stood
  before SA191 (a pinned copy or commit, read-only) and fixture donors; not a live repository.

  **Iterative loop.** The playbook's "Running a migration iteration" section is the procedure:
  each iteration regenerates the recipient, runs `make beta-migrate-fresh` with a read-only donor,
  and triages every gap into the gap ledger (tool fix, playbook step, project decision, or upstream
  to a module); fixes land in QuickScale and the loop restarts. The recipient is never hand-edited
  before the final iteration. The first slice is one non-interactive `make beta-migrate-iterate`
  target that reads slug, theme, and modules from the donor's `quickscale.yml` and runs one
  iteration; the rest follows ledger order, starting with G-001.

  **Tool scope.** The tool migrates everything that can be done deterministically:
  - *Classification.* Every donor file lands in exactly one class — generated-untouched,
    generated-customized, project-owned, module-edited, or build artifact. An unclassified file is a
    blocker, never a silent drop.
  - *Functionality.* Project-owned Django apps are detected, copied, registered, and URL-mounted
    without hand-patching QuickScale-owned settings; their migrations are regenerated against the
    current `AbstractListing`. Donor-added frontend dependencies merge, with conflicts reported.
  - *Design system.* The `showcase_react` theme gains a project-owned design layer: one folder
    holding the tokens CSS, Tailwind preset, fonts, and brand assets. It is declared
    never-overwritten in [generated_file_ownership.md](generated_file_ownership.md), and a test
    proves an upgrade leaves it untouched. The tool ports the donor's design into it. The SA192
    Django-rendered pages import the same tokens file.
  - *Handoff prompt.* The final phase writes `MIGRATION_PROMPT.md` into the recipient, generated
    from the report: what was migrated, the remaining manual actions with their paths and the
    applicable rule, the hard constraints, and the exact done criteria; a snapshot test pins the
    rendered prompt. A coding assistant completes the remainder from it.

  **Acceptance:**
  - A final iteration against the pinned `bap-web` donor runs clean: no unclassified files, every
    ledger entry closed (G-001 included), and the handoff prompt's remaining items recorded.
  - Tool tests cover each ledger fix with a fixture donor holding a project-owned app, customized
    tokens, a module edit, and a pre-facade `production.py`; the handoff prompt has a snapshot
    test; the beta-migration smoke gate passes; the playbook points at the tool instead of
    duplicating it as shell snippets.
  - A decision records who owns a pre-facade donor `production.py` (today donor-owned by policy
    and refused at preflight).

  **Slices:**
  - [ ] (a) `make beta-migrate-iterate`: one non-interactive iteration driven by the donor's
    `quickscale.yml`.
  - [ ] (b) Classification of every donor file, with unclassified files as blockers.
  - [ ] (c) Project-owned apps (copy, register, mount, regenerate migrations) and frontend
    dependency merge.
  - [ ] (d) The `showcase_react` design layer, its ownership entry and upgrade test, and the
    donor design port.
  - [ ] (e) The generated `MIGRATION_PROMPT.md` and its snapshot test.
  - [ ] (f) Ledger iterations to a clean final run, the playbook rewrite, and the pre-facade
    `production.py` decision.

  **Surfaces:** `quickscale_devtools/.../beta_migration/`, its tests and smoke gate; the migration
  playbook and gap ledger; the `showcase_react` theme, generator, and
  `generated_file_ownership.md` (design layer); decisions.

- [ ] **SA216 — Disable and anonymize accounts instead of deleting the user row.**

  **Context:** "Delete my account" (auth's `AccountDeleteView`) deletes the `User` row today. Every
  record the person made for an organization loses its author ([Module Conventions](decisions.md#module-conventions) rule 27 makes
  those links `SET_NULL`), and the deletion needs cross-organization machinery: orgs'
  `account_deletion_user_reference_organization_ids()` lookup, the `RemovalCoordinator`'s
  `ACCOUNT_DELETE` boundary, and billing reconciliation before the row can go. Deleting the row is
  also what erasure requests are assumed to need. They need the personal data gone, not the row.
  This ticket keeps the row, disables it, and scrubs the personal data at once, so records stay
  attributed to "Deleted user #<id>" (as Django admin shows it).

  **Personal data about a user today** (from the models on `v89`; the first slice confirms it,
  including third-party tables):

  | Where | What | Proposed treatment |
  |---|---|---|
  | auth `User` | `username`, `email`, `first_name`, `last_name`, password, `last_login` | scrub: `deleted-<id>` / `deleted-<id>@invalid`, blank names, unusable password, `is_active = False` |
  | django-allauth `EmailAddress` | the person's email addresses and their verified state | delete (rows exist only for login) |
  | Django sessions | active logins | delete |
  | blog `AuthorProfile` | `bio`, `avatar` file | blank the bio; delete the file through storage |
  | orgs `OrganizationMembership` | membership, role; `invited_by` on surviving rows | delete the person's memberships (the last-owner guard still applies); surviving rows keep the inviter link |
  | orgs `OrganizationInvitation` | invitations *sent* (`invited_by`); the recipient `email` on pending, accepted, and expired invitations | pending invitations withdrawn; accepted and expired rows keep the sender link and have the address scrubbed |
  | notifications `NotificationMessage` / `NotificationDelivery` / `NotificationDeliveryEvent` | `recipient_email`, rendered subject, text, and context sent to them, provider failure text, and the stored provider payload (matched by address; there is no user link) | scrub the address, the rendered body, and provider-carried text; keep status for delivery statistics |
  | billing `Subscription`, `CreditBalance`, `CreditTransaction`, `PurchaseCheckout`, `WebhookEvent` | the user as actor; customer email and name inside the stored Stripe event payload | keep the link; scrub customer email and name from the webhook payload; the organization's Stripe customer email belongs to the org owner and changes only with ownership |
  | crm `ContactNote` / `DealNote`, `Deal.owner`, forms `Form.created_by`, blog `Post.author` / `BlogMediaAsset.uploaded_by`, backups actor | the user as actor | keep the link; nothing to scrub on the row |
  | analytics (PostHog) | events under the user's `distinct_id` | outside the database: documented as the operator's deletion step |

  Out of scope: data about people who are *not* users (crm `Contact`, forms submissions with their
  IP and user agent), which belong to the organization; a restore grace period; a data export.

  **Scope:**
  - *Inventory first.* SA242 delivers the table above as a checked list; this ticket's handlers
    are written against it.
  - *Anonymize capability.* Each module that holds personal data about a user declares an
    anonymize handler on its `AppConfig` (Module Conventions rule 4's capability mechanism, extending
    the removal obligations in orgs' `removal.py` with an `ANONYMIZE` `RemovalAction`); auth
    collects and runs them in one transaction. File deletion runs on commit (Module Conventions
    rule 21).
  - *auth.* `AccountDeleteView` disables and scrubs instead of calling `delete()`; the last-owner
    guard and billing's checks before deletion stay. The person can sign up again with the same email.
  - *Simplify.* The cross-organization null-out lookup
    (`account_deletion_user_reference_organization_ids`, in orgs' `current_org` and billing) is
    called only by auth's delete view; it goes if nothing else deletes users through self-service,
    and the `ACCOUNT_DELETE` removal boundary becomes the anonymize boundary. Operator hard delete
    (Django admin) keeps working under Module Conventions rule 27.
  - *Docs.* decisions.md records the account-removal model; organizations.md's account deletion
    section and auth's README change with it.

  **Acceptance:**
  - After account removal, no table (module or third-party) holds the person's email, name, or
    free text written about them as a user, as a test that walks the inventory proves; files are gone
    from storage.
  - Their posts, deals, notes, and billing records remain, attributed to "Deleted user", and each
    organization's data is otherwise untouched.
  - The same email can register again; the old account cannot sign in.
  - A rolled-back removal leaves no effect (Module Conventions rule 21); operator hard delete still passes the user-FK conformance gate.

  **Surfaces:** auth (`views.py`, `AppConfig`, README); orgs (`removal.py`, the
  account-deletion lookup, memberships, invitations); blog, notifications, billing, crm, forms,
  backups (anonymize handlers where the inventory lists them); decisions.md and [organizations.md](organizations.md). These are Track 3 surfaces
  (`auth/views.py`, orgs' removal path) plus module code that SA215 also edited (the dependency edge
  closed with SA215);
  billing is a Track 2 surface, so SA216 lands through the serialized merge queue.

  **Slices:**
  - [ ] (a) The `ANONYMIZE` removal action and auth's collector, with each module's handler and
    its tests.
  - [ ] (b) `AccountDeleteView` disables and scrubs; re-registration and sign-in tests; the
    rollback test.
  - [ ] (c) Remove the account-deletion lookup and turn `ACCOUNT_DELETE` into the anonymize
    boundary; decisions, organizations.md, and auth's README.

- [x] **SA242 — Inventory every personal-data field about a user behind a failing test.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Open questions: whether "regenerate and port" is the permanent upgrade model, and whether
`experto-ai-web` migrates too. Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
