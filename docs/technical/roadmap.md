# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules (SA215): settings and identity names, how
a module reads its configuration, and how modules depend on and use each other, as recorded in
[decisions.md § Module Conventions](decisions.md#module-conventions). The migration and portal work (SA191, SA153, SA204, SA214) is
parked behind it, so `bap-web` is ported once, onto the standardized names. After that, the goal is
the first useful property portal (SA153) in a project-owned extension, built on `bap-web` after a
one-off port moves it onto current QuickScale (SA191). Capabilities are generalized only after that
project proves their value.

SA191 is the first QuickScale upgrade of a site holding real production state. That state is
**reseeded, not carried**, so SA204's migration-history freeze waits for SA153's go-live.

**Release status — v0.88.0 packaged, not published.** No core tag, split-branch republication,
seal, or PyPI upload has happened. Publication stays a maintainer decision; this planner tracks only
that it is owed: release-tier validation on the packaged bytes, the phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. The packaged bytes
predate fixes now on `v89` and carry two S1 billing defects: with billing enabled against real
Stripe keys, every webhook and every checkout fails. Shipping any `v89` fix in 0.88.0 means
repackaging.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA215 | Standardize conventions across modules | post-v88 | 1 | — | Deferred |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | post-v88 | 1 | SA215 | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | post-v88 | 1 | SA215 | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA214 | Harden the fresh-first migration tool into the standard upgrade path | post-v88 | 1 | SA215 | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA215 ──► SA191 ──► SA153 ──► SA204 ──► SA214 ──► SA154 (inventory)
Track 2: idle
Track 3: idle
                         critical path: SA215 → SA191 → SA153
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA215 fixes one convention across modules first, while renames are still
cheap: `bap-web` has not been ported onto the current names, and SA204 has not frozen the module
migration history that the app-label rename rewrites.
SA191 then migrates `bap-web` onto current QuickScale, rebuilds and reseeds its
database, and redeploys through `deploy railway`. SA153 builds the portal on it. SA204 freezes
module migration history before any post-SA153 module schema change. SA214 hardens the migration
tool off the critical path. SA154 is an inventory, not work.

**Off the critical path.** Tracks 2 and 3 are idle.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA215 | yes | yes | yes | **yes** | **yes** |
| 2 | — (idle) | — | — | — | **yes** | no |
| 3 | — (idle) | — | — | — | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  migration-history freeze gate and `decisions.md` § Clean-Break Migration History, the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation.
- Track 2 owns `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package, `ruff.toml`, the module page templates
  and test-settings stubs, the generated `base.html`, the CLI apply/deploy/update commands and
  `contract_vintage.py`, the module manifests' `contract_vintage` blocks,
  `contracts/module_options.py` and the `.env.example` template, `quickscale_core/dr_engine/`,
  and the billing module (`billing/services.py`, `billing/views.py`, `billing/adapter.py`, and its
  docs).
- Track 3 owns the orgs tenancy, purge, removal-obligation, and boot path (`orgs/apps.py`,
  `orgs/removal.py`), the privileged-command and runtime-role stations, the
  `quickscale_core.runtime` settings facade, the generated settings templates (`base.py.j2`,
  `production.py.j2`, `local.py.j2`), the generator's Jinja environment, `auth/views.py`, the
  blog rate limiter, and the generated `pyproject.toml.j2` `[build-system]` block.
- **Cross-track edits.** No queued ticket edits another track's surfaces; a ticket that does lands
  through the serialized merge queue.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), both audits, and
  [decisions.md](decisions.md) (SA204, SA153). Each track resolves the shared set at its
  own merge, after the previous merge lands, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [ ] **SA215 — Standardize conventions across modules.**

  **Context:** the twelve modules grew one at a time and follow different conventions, and neither
  audit checks cross-module consistency. The evidence is
  [module-conventions-inventory.md](../planning/module-conventions-inventory.md): two settings
  families (`QUICKSCALE_<MODULE>_*` and bare `<MODULE>_*`), three spellings of a boolean flag, eight
  independently written settings readers with defaults duplicated from the manifests, settings read
  but never declared, modules reading other modules' settings, an `auth ↔ orgs` import cycle, core
  reading `backups` settings, and URL, template, table, and management-command names that do not
  follow one stem. A second pass found URL prefixes set in three places, two API frameworks and
  error shapes, templates breaking the recorded base-template rule, four startup-check styles, no
  fixed file set, uneven tenant-isolation tests, and twelve README outlines. A third pass found option
checks in four places (including per-module validators in core and the CLI), three ways to build a
tenant model, uneven reverse names on shared models, receivers in `signals.py`, destructive commands
without `--dry-run`, and a placeholder module directory. A fourth pass (D22–D27) found tenant
modules authorizing with the site-wide `is_staff` instead of org roles, a second email sender in
forms, write side effects not tied to commit, feature events owned by analytics, and an
undeclared `services.py` surface. The rules are recorded in
  [decisions.md § Module Conventions](decisions.md#module-conventions); this ticket is the code.

  **Scope,** in module-sized slices through the serialized merge queue:
  - *Settings names.* Every first-party setting and option key follows rules 1 and 6 (the
    inventory's D1 table, including `QUICKSCALE_MODE` → `QUICKSCALE_ORGS_MODE`); every module gains
    `QUICKSCALE_<MODULE>_ENABLED`; undeclared settings are declared or removed.
  - *Identity names.* App labels become `quickscale_<module>`, so tables, migrations, content types,
    permissions, `AUTH_USER_MODEL`, and orgs' RLS table lists change; `db_table` overrides go; URL
    namespaces, template folders, and management commands take the same stem.
  - *Settings reading.* `apply` also writes `MODULE_SETTINGS_SCHEMA` into `settings/modules.py`;
    one generic startup check in `quickscale_core.runtime`, registered by each module, validates
    every declared setting; per-module readers and code defaults are removed.
  - *Dependencies.* `orgs` stops importing `auth` and `social`, `auth` stops importing `billing`,
    `blog` stops reading storage's setting, and `dr_engine` stops reading backups' settings,
    through `services.py` and `AppConfig` capabilities; `required_modules` covers every import.
  - *No legacy.* `apply` refuses retired option keys in `quickscale.yml` and state, and the startup
    check refuses retired settings, each naming the replacement. Generated templates, docs, and
    `.env.example` use only the new names.
  - *URLs.* Mounts move from `urls.py` and `adapter.py` into manifest `url_includes`; orgs gains an
    `app_name` and moves under `orgs/`; APIs to `<mount>api/`, webhooks to `<mount>webhooks/`;
    route names become snake_case without the module name.
  - *Templates and static.* One flat module base per module (orgs, analytics, forms gain one; orgs
    stops emitting `<html>`); emails under `email/`; static under `static/quickscale_<module>/`;
    template-tag libraries renamed `quickscale_<module>[_<purpose>]`.
  - *APIs.* blog's and listings' function-view APIs become DRF views; `OrgApiBaseView` is rebased
    on DRF's `APIView`; errors take the one QuickScale shape from a generic handler in `quickscale_core.runtime`
    (generated `REST_FRAMEWORK` block, DRF dependency in every module with an API, the theme's `useApi.ts` and
    orgs/social pages); blog's `BLOG_API_TOKENS`, its dual-auth exception in the JSON API Endpoint
    Base Contract, and its hand-written rate parser go. Signature-verified webhooks stay exempt.
  - *Checks and errors.* Hand-written `ready()` checks move to `checks.py`, run from `ready()` by
    one core helper that fails every process and also registers them as system checks, orgs' RLS
    boot guard included; analytics
    fails on invalid configuration and tolerates only an unreachable vendor; exceptions move to
    `exceptions.py` under one base; `register_backup_persistence` stays as the listed core port.
  - *Files, tests, docs.* Every module gains `services.py` with `is_enabled()` and `poetry.toml`;
    auth's `adapters.py` → `allauth_adapter.py`; one-off files fold in; missing required tests
    (`test_apps`, `test_services`, `test_migrations`, tenant isolation and RLS) are added;
    READMEs follow the rule 11 headings; the 15 literal tuple choice lists become `TextChoices`.
  - *Manifests and option checks (rule 12).* Every option gains `type`/`description`/`validation`
    as required, in the per-option `validation` block, which core starts reading (today it is
    parsed and ignored); listings' `derivation.validation_rules` moves there; the 25 one-to-one
    `derived_settings` entries that repeat an option's `django_setting` (analytics, billing, blog,
    crm, forms, listings), with their 10 repeated defaults, go; empty
    `immutable`/`dependencies` blocks are written out. Core's and the CLI's per-module option code
    goes — the `validate_/resolve_/normalize_/default_<module>_module_options` functions and
    `DEFAULT_*` / `LEGACY_*` constants in `quickscale_core.contracts.resolvers`,
    `contracts.module_options`, `schema.config_schema`, and the CLI's `module_config`, with the
    `contracts.imperative_inventory` that tracked them — and cross-option checks become the
    manifest's `required_when` / `any_of` keys, run by `plan`, `apply`, and the startup check.
  - *Models (rules 13–14).* billing, forms, listings (`AbstractListing`), and social
    (`BaseSocialItem`) models subclass `TenantModel` instead of `tenant_org_fk` plus hand-declared
    managers, every tenant `Meta` inherits the base's, and `organization` keeps the base's reverse
    name (`CreditBalance` alone overrides it, as a one-to-one); `is_tenant_model` recognizes
    inheritance only and an orgs check fails startup on a stray `TenantManager`; relations to other modules' models get
    `<module>_<name>` `related_name`s (crm's two `created_by` fields have none; backups, billing,
    blog, crm, forms, and orgs rename the rest, with their callers); `FormFieldValue` gains an
    ordering.
  - *Package root, signals, commands, tooling (rules 15–18).* `default_app_config` and storage's
    root re-export go; auth's and crm's `signals.py` become `receivers.py` and orgs' receivers move
    there; `backups_prune`, `forms_anonymize_submissions`, and `promote_to_saas` gain `--dry-run`,
    the retired `migrate_billing_to_orgs` is deleted with its recovery docs, and
    `check_tenant_isolation` raises
    `CommandError` instead of calling `sys.exit()`; orgs and social gain `[tool.mypy]` and
    fix what it reports; `quickscale_modules/teams/` is deleted (README to
    `docs/planning/teams.md`) with core's placeholder handling.
  - *Authorization, email, effects, events, service surface* (rules 19–24). blog, listings, crm,
    and forms authorize by org role through orgs' `permissions` (new DRF `HasOrgRole`); forms'
    fallback email sender goes and forms and orgs require notifications; write effects (forms'
    submission effects, orgs' invitation, crm's bootstrap receiver, social's cache purge) move to
    `transaction.on_commit` with a rollback test each; analytics keeps only `capture_event`, forms
    owns `forms_submitted` (release note: renames `form_submit`), and the unused
    `capture_social_link_click` goes; every `services.py`
    gains `__all__`, keyword-only signatures, and `<Module>Error` on failure; backups and blog gain
    `py.typed`; storage uses `timezone.now()`; social's cache keys become `quickscale_social:*`.
  - *Enforcement.* The rule 25 conformance test, covering rules 1–24, with a control case per rule.

  **Acceptance:** every inventory drift item (sections 1–26) is fixed or recorded as an accepted exception with
  its reason; the conformance test passes and rejects a violation of each rule; a project
  generated before SA215 fails `apply` and startup with messages naming each new name; a freshly
  generated project with all twelve modules passes `make ci-e2e`; the `auth ↔ orgs` cycle is gone;
  the release notes list every moved public URL with its operator step (Stripe and Resend webhook
  endpoints);
  decisions.md names quoted from the shipped state are updated; the inventory is marked resolved.

  **Surfaces:** every module (manifests and core manifest copies, `adapter.py`, settings reads, `AppConfig`,
  migrations, URLs, templates, static files, template tags, APIs, `checks.py`, `exceptions.py`,
  tests, READMEs); orgs' tenant classification (`tenancy.is_tenant_model`, a new stray-`TenantManager` check);
  `quickscale_core` (per-module option code in `contracts` and `schema` removed; placeholder
  handling in module discovery and the catalog; the startup check, capability helper, and API exception handler in `runtime`, the
  `dr_engine` backups call, generator settings including the `REST_FRAMEWORK` block, and theme
  templates including the React API client);
  `quickscale_cli` apply (schema writing, retired-key refusal) and `module_config` (per-module
  option checks removed; prompts read the manifest); `.env.example`; decisions,
  [module-extension.md](module-extension.md), [organizations.md](organizations.md) (tenant models,
  billing recovery section), railway.md, and user docs. It touches Track 2 (CLI apply,
  manifests' `contract_vintage` blocks, `.env.example`, `dr_engine`) and Track 3 (orgs, settings
  templates, `auth/views.py`) surfaces.

- [ ] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

  **Context:** under [decisions.md](decisions.md) § Clean-Break Migration History, each
  model-bearing module ships one `0001_initial` that is rewritten in place every release, and the
  only supported upgrade is a fresh database. Since `bap-web` was generated on 2026-03-05, all ten
  model-bearing modules' `0001_initial` were rewritten two to five times each. Every rewrite adds
  to the hand-written transform each deployed project needs on its next upgrade, and after SA153
  that transform must also assign `organization_id` under FORCE RLS. `bap-web`'s data is
  reseeded, so the freeze is needed only at SA153's go-live, where the first non-reseedable tenant
  data appears; it must land before any module schema change reaches that project. This is a one-way door: once a project applies a frozen `0001`, it can never be
  re-squashed under it (arch audit `clean-break-schema-no-data-path`, option 1).

  **Acceptance:** decisions record that rule 1 of the clean-break decision is lifted from 0.89.0
  onward, the release the freeze lands in. Upgrades from earlier vintages, including 0.88.0,
  stay fresh-database-only. From 0.89.0 on, a schema change to a model-bearing module ships as a
  new incremental migration under the existing migration-quality gates. A registered gate fails
  when an existing migration file of a model-bearing module changes or disappears, with controls
  proving that it rejects an in-place `0001` edit and accepts a new `0002`.

  The gate compares against a checked-in manifest of the frozen files' content hashes, not a git
  ref: no 0.89.0 tag exists yet, and a manifest also works in shallow CI clones. The freeze takes
  effect when SA204 merges, so any later `v89` change to a model-bearing module's models ships as
  a `0002`; confirm before merging that no module schema change shipped between SA191's rebuild
  and this freeze. The topology guard in `test_module_migration_topology.py` currently requires exactly one
  `0001_initial` and has a canary that rejects any `0002`; it changes to require a `0001_initial`
  followed by an ordered chain, and that canary is inverted.

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
  vendored `modules/forms`. It is 27 minor versions behind, and the tool's first iteration against
  it blocked at preflight (ledger G-001), so a judgement-driven port is cheaper for this one site.

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
  rebuilds a fresh database. A new idempotent `orgs` command, `create_site_org <slug> <name>`,
  creates the site's organization in the same privileged deploy step as `migrate`. The catalog is
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

  **Surfaces:** the new `bap-web-new` repository and its reseed step; the migration prompt; the
  `orgs` `create_site_org` command (a Track 3 surface, through the serialized merge queue); the
  `forms` module only for upstreamed customizations.

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

  This is the first real tenant data on a QuickScale site. From here on, module schema changes
  reach it only as incremental migrations on SA204's frozen history.

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
  decisions rule for the approved frontend stack. The marker-derived purge plan covers property
  rows without a vendored module edit. Every `*_id` field on a property model is classified through
  SA208's project-side declaration, and the SA208 system check passes in the project.

  **Surfaces:** the project-owned property extension, its API and React pages, and the project's
  prerender build and deploy step; listings/blog/forms/CRM seams only where needed; decisions;
  extension documentation.

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

  **Iterative loop.** Each iteration regenerates the recipient from scratch with `quickscale plan`
  and `quickscale apply` (same slug, `showcase_react`, the donor's modules), runs
  `make beta-migrate-fresh` with a read-only donor, verifies, and triages every gap into
  a gap ledger (tool fix, playbook step, project decision, or upstream to a module). Fixes land in
  QuickScale and the loop restarts. The recipient is never hand-edited before the final iteration.
  The ledger is the acceptance evidence.

  **Running an iteration.** The playbook's "Running a migration iteration" section is the
  procedure. Before the release, the recipient is built from the unreleased checkout: `make install`,
  an unpushed local annotated `0.89.0` tag on `HEAD` (the playbook gives the message format), a
  clean tree, `make publish-modules`, then
  `quickscale apply --split-refs-from-branches`; the tag is never pushed, because pushing it
  starts PyPI publication. `apply` writes into `<cwd>/<slug>`, so the recipient is generated in a
  staging directory and moved to the target path. A tool fix needs only `make install`; a module fix
  also needs a commit, a re-pointed tag, and `make publish-modules`. An iteration's check is the run
  report, the handoff prompt's remaining items, and the donor's pytest and Vitest suites in the
  recipient; live-site Playwright and screenshot parity run in the final iteration only.

  **Slice order.** Iteration zero comes first: one non-interactive `make beta-migrate-iterate`
  target (reads slug, theme, and modules from the donor's `quickscale.yml`; stages, regenerates,
  moves, migrates, and runs the iteration check) and its first run against a real donor, whose gaps
  seed the ledger; the open G-001 entry comes from the first `bap-web` run.
  Classification, functionality, and the design layer follow in ledger order.

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
    rendered prompt. Each remaining file item will also carry its diff once classification lands. A
    coding assistant completes the remainder from it. Work the assistant repeats every iteration is
    a tool-fix candidate, so the prompt shrinks across iterations.

  **Acceptance:**
  - A final iteration against the pinned `bap-web` donor runs clean: no unclassified files, every
    ledger entry closed (G-001 included), and the handoff prompt's remaining items recorded.
  - Tool tests cover each ledger fix with a fixture donor holding a project-owned app, customized
    tokens, a module edit, and a pre-facade `production.py`; the handoff prompt has a snapshot
    test; the beta-migration smoke gate passes; the playbook points at the tool instead of
    duplicating it as shell snippets.
  - A decision records who owns a pre-facade donor `production.py` (today donor-owned by policy
    and refused at preflight).

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, its tests and smoke gate; the migration
  playbook and gap ledger; the `showcase_react` theme, generator, and
  `generated_file_ownership.md` (design layer); decisions.

- [x] **SA212 — Keep the CI supply-chain pins fresh and scan the generated container.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Open questions: whether "regenerate and port" is the permanent upgrade model, and whether
`experto-ai-web` migrates too. Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
