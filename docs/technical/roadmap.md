# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[decisions.md § Module Conventions](decisions.md#module-conventions). `bap-web` is then ported
once, onto the standardized names (SA191), and carries the first property portal in a
project-owned extension (SA153). Capabilities are generalized only after that project proves
their value.

**Release status.** 0.88.0 is published with S1 billing defects (with real Stripe keys, every
webhook and every checkout fails). The fixes are on `v89` and ship in 0.89.0
([publish_procedure.md](publish_procedure.md)); 0.89.0 is publish-ready.

Audit tickets name the [arch](../others/arch-audit.md), [tech](../others/tech-audit.md), or
[coherence](../others/coherence-audit.md) IDs they close; the audits keep the evidence. Coherence
tickets merge the matching coherence §6 rule into decisions with a harness detector.

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | 1 | — | Optional |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | 1 | — | Optional |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191, SA204 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA260 | One off switch and a closed-world manifest surface | 2 | — | Optional |
| SA263 | Adapters validate, coerce, and default only through the manifest | 2 | SA260 | Optional |
| SA267 | Bring `scripts/` under the quality thresholds without gating it | 2 | — | Optional |
| SA261 | One owner per URL prefix, and theme API bases from the seam | 3 | — | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191 (cutover) ∥ SA204 ──► SA153 ──► SA154 (inventory)
Track 2: SA260 ──► SA263 ──► SA267
Track 3: SA261
     release path:  publish 0.89.0
     critical path: SA191 → SA204 → SA153
```

Arrows within a track are queue order; the table holds the dependency edges. There are no
cross-track edges.

**Slices.** Large tickets list `Slices:` in their body. Each slice is one implementer session
with a fresh context, scoped to that slice's text and named surfaces, and ends with a short
handoff note (what landed, what is next, what to watch) committed with the work. A ticket closes
when its last slice lands; slices are not scheduled.

**Order.** Every change to a shipped module `0001_initial` lands before SA204 freezes
migration history, and SA204 lands before SA153 slice (a), whose schema work is `0002+` from the
start. SA154 is an inventory, not work. SA191's agent work is done and it closes at the
maintainer's cutover, so SA204 proceeds alongside it.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191 | yes | no | yes | no | yes |
| 2 | SA260 | yes | yes | yes | **yes** | no |
| 3 | SA261 | yes | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns the generated `urls.py.j2` and the theme's social seam
  pages, the parity oracles, the hosted workflow triggers, the migration-history freeze gate and `decisions.md` § Clean-Break Migration History, the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation, and, for the conventions, module identities, models and their
  `0001_initial`, module READMEs, and module templates, static files, and template tags, with the
  module page templates and the generated `base.html`, and cross-module imports and settings reads,
  and the `services.py` public surface.
- Track 2 owns the gate registry and everything generated from it (`scripts/gate_registry.json`,
  `check_quality.sh`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`, the gate documentation
  table), `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package, `ruff.toml`, the test-settings stubs, the CLI apply/deploy/update commands and
  `contract_vintage.py`, the module manifests' `contract_vintage` blocks,
  `contracts/module_options.py` and the `.env.example` template, `quickscale_core/dr_engine/`,
  and the billing module (`billing/services.py`, `billing/views.py`, `billing/adapter.py`, and its
  docs), the split facades of the CLI commands, `dr_engine`, and billing with the tests that patch
  them, the blog and storage upload-path builders, and, for the conventions, the manifest option schema and the CLI's `module_config`,
  module settings names, `is_enabled()`, and the per-module personal-data declarations with the
  orgs personal-data check, and the maintainer migration tools (`beta_migration/`) with their
  smoke gate, playbook, gap ledger, and the `showcase_react` design layer.
- Track 3 owns the orgs tenancy, purge, removal-obligation, and boot path (`orgs/apps.py`,
  `orgs/removal.py`), the privileged-command and runtime-role stations, the
  `quickscale_core.runtime` settings facade, the generated settings templates (`base.py.j2`,
  `production.py.j2`, `local.py.j2`), the generator's Jinja environment, `auth/views.py`, the
  blog rate limiter, the generated `pyproject.toml.j2` `[build-system]` block, orgs'
  `quickscale_orgs_create_site_org` command, and the frontend
  decisions in `frontend.md`, and, for the
  conventions, the `quickscale_core.runtime` helpers, module `checks.py` and `exceptions.py`,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, and the conformance harness with its registry row, and the five `_anonymization.py`
  handlers with core's redaction helpers.
- **Cross-track edits.** SA204 adds its gate row to the Track 2 registry. All land through
  the serialized merge queue.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), both audits, and
  [decisions.md](decisions.md). Each track resolves the shared set at its
  own merge, after the previous merge lands, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [ ] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

  **Context:** under [decisions.md](decisions.md) § Clean-Break Migration History, each
  model-bearing module ships one `0001_initial` that is rewritten in place every release, and the
  only supported upgrade is a fresh database. Every rewrite adds to the hand-written transform each
  deployed project needs on its next upgrade. SA191 reseeds `bap-web`, so the freeze is needed at
  SA153's go-live, where the first non-reseedable tenant data appears, and before any module schema
  change reaches that project. It is a one-way door (arch audit
  `clean-break-schema-no-data-path`, option 1).

  **Acceptance:** decisions record that rule 1 of the clean-break decision is lifted from the
  release the freeze lands in. Upgrades from earlier vintages stay fresh-database-only. From that
  release on, a schema change to a model-bearing module ships as a
  new incremental migration under the existing migration-quality gates. A registered gate fails
  when an existing migration file of a model-bearing module changes or disappears, with controls
  proving that it rejects an in-place `0001` edit and accepts a new `0002`.

  The same gate fails when a frozen migration imports a `_`-prefixed module symbol; before the
  freeze, `blog`'s `_BlogMediaAssetImageField` (pinned into `0001_initial` by `6e0ac9da`) is
  promoted to a public, documented field or replaced, so frozen history names only symbols with a
  stability promise (arch audit `clean-break-schema-no-data-path`, guard).

  The gate compares against a checked-in manifest of the frozen files' content hashes (it works in
  shallow CI clones and needs no tag). Before merging, confirm no module schema change shipped
  between SA191's rebuild and the freeze, and prove on a restored `bap-web` copy that `migrate`
  from the frozen `0001` reproduces the FORCE-RLS parity baseline (the door is one-way). SA153's
  schema work is written as `0002+` migrations from the start. `test_module_migration_topology.py` changes from exactly
  one `0001_initial` to a `0001_initial` followed by an ordered chain, and its `0002` canary is
  inverted.

  The freeze extends to disaster recovery (arch audit `clean-break-schema-no-data-path`,
  recommendation): a backup taken at vintage N restores and migrates forward under N+1 instead of
  being refused by `dr_engine/recovery.py`'s exact-vintage match, a bare file that records no
  vintage is still refused, and a restore-forward test proves it. This also retires tech watchlist
  `dr-restore-vintage-exact-match`.

  **Surfaces:** decisions, the new gate with its hash manifest, registry row, and gate
  documentation, `quickscale_core/tests/test_module_migration_topology.py`,
  `dr_engine/recovery.py` (Track 2 reviews), and the arch audit.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port.**

  Migrate `bap-web` into a new repository at `/home/victor/code/bap-web-new`: a fresh `quickscale plan` + `apply` recipient, then a coding assistant ports the
  donor by following [bap-web-migration-prompt.md](../planning/bap-web-migration-prompt.md).

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
  organization FK (`migrate --plan` on a restored dump fails with `InconsistentMigrationHistory`),
  so the cutover rebuilds a fresh database. The `quickscale_orgs_create_site_org` command creates the site's
  organization in the same deploy step as `migrate`. The catalog is
  then reseeded through `bap-web`'s own seed command, tenant-scoped to that organization under the
  restricted runtime role — never under BYPASSRLS. Users are
  re-invited; form submissions and other transactional rows are not carried. Media is carried over
  separately and verified.

  **Dependencies and ownership:** Billing stays disabled. An agent delivers everything up to a
  deploy-ready recipient and a rehearsed cutover script, and takes the production dump read-only
  by slice (a)'s steps. The maintainer logs in to Railway, creates and archives the repositories, runs the Railway cutover, carries media, and
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
    specs that submit forms or write data run only against the recipient, and every form mock
    intercepts both the recipient's `/forms/api/*` and the donor's `/api/forms/*` submit
    endpoints, so no spec can submit into production. The live site keeps public listings hidden
    on purpose (maintainer decision, 2026-10-10): home and contact are screenshot-diffed
    recipient-vs-live at desktop and mobile widths with animations off, under 1% of pixels, the
    recipient rendered flag-off and every mask recorded; the live baselines are captured and kept
    in `bap-web-new` before cutover, because the cutover replaces that site. The recipient ships
    with public listings enabled, proven by recipient-only specs over the 12 seeded listings
    (`/api/properties/`, `/properties`, `/properties/:slug`, and the home property actions and
    featured section); catalog and detail use the design system of home and contact — shell,
    typography, color, spacing, and components — with kept recipient screenshots and an
    automated computed-style check.
  - The carried `properties` models pass SA208's provider-ID system check. The FORCE-RLS table and
    policy counts equal a fresh project's with the same modules, and `check_tenant_isolation` passes.
  - `bap-web-new` becomes a new repository and redeploys through `deploy railway`; the old
    repository is archived. The pre-cutover database is retained until the reseeded site is verified,
    and the written rollback restores the previous deploy *and* that database.
  - No property-portal features (SA153) and no frontend stack change.

  **Remaining:** agent work (slices a–e) is done; `scripts/cutover.sh` and `CUTOVER.md` in
  `bap-web-new` rebuild, verify, and roll back, rehearsed on scratch. After 0.89.0 is published:
  repin `bap-web-new` to it and re-run the rehearsal (agent), then the maintainer runs the Railway
  cutover, carries media, re-invites users, and archives the old repository. The production dump
  at `/home/victor/code/bap-web-prod.dump` holds real user data and stays out of every repository.

  **Surfaces:** the new `bap-web-new` repository and its reseed step; the migration prompt; the
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
  detail pages must be prerendered or server-rendered for Open Graph and indexing, by the mechanism
  [frontend.md](frontend.md) records.

  The launch needs property fields and galleries, explicit currency labels, attribute filtering
  and keyword search applied by the API, Spanish public pages, listing-linked inquiries into `crm`,
  and launch SEO including metadata, sitemap, and robots guidance. Currency labels must not imply
  exchange-rate conversion, and Spanish launch coverage does not require translating every
  QuickScale interface.

  New child tables, including gallery images, follow the child-table decision in
  [decisions.md](decisions.md) and the `test_rls_boundary.py` coverage pattern.

  **Acceptance:** under frontend.md's decisions, the `bap-web` project migrated by SA191 serves an organization-scoped React property catalog and
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
  claims that the module does not provide. The
  marker-derived purge plan covers property rows without a vendored module edit. Every `*_id` field on a property model is classified through
  SA208's project-side declaration, and the SA208 system check passes in the project. Every
  personal field on a project-owned model carries a personal-data declaration and passes SA246's
  check.

  **Slices:**
  - [ ] (a) Models: property fields, currency labels, and ordered gallery child tables, with
    forced RLS, boundary tests, SA208 classification, and purge coverage, as `0002+` migrations.
    Every tenant-to-tenant FK (gallery → property, inquiry → listing) carries the composite
    organization constraint that orgs' composite-FK check requires.
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

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or prerender step into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Items that add tenant tables build on marker-derived enrollment
  and purge, not on module-source edits, and items that change a module schema ship an incremental
  migration on SA204's frozen history. Close when every item is promoted or dropped with rationale.

- [x] **SA253 — Make the generated project's CI, image, and healthcheck pass, and execute them in a gate.**

- [x] **SA255 — Accept Resend's real webhook signature in notifications.**

- [ ] **SA260 — One off switch and a closed-world manifest surface.**

  **Context:** five mechanisms say "installed but off"; switching analytics off removes its app,
  so a template following the README's `{% load quickscale_analytics %}` raises
  `TemplateSyntaxError` (coherence `module-enabled-switch`, defect). The manifest loader ignores
  unknown keys, so orgs' `middleware:`/`settings:` load silently, and `apps`/`middleware` literals
  in adapters are unchecked (`manifest-declared-surface`). Dependency specs come from two files in
  two dialects (`dependency-spec-sources`).

  **Acceptance:** coherence §6 proposals 1 and 18 are merged into decisions and enforced: off
  keeps apps, middleware, settings, admin, and template tags and drops only public `url_includes`
  and `spa_routes`; scheduled commands refuse only `--trigger scheduled`; `.env.example` blocks
  are kept. `load_manifest` rejects unknown top-level keys; `apps` and `middleware` come only from
  `wiring_projections`; `required_modules` and `dependencies` are always present, `dependencies`
  lists names with specs in `pyproject.toml`, and every module declares `quickscale-core`.

  **Surfaces:** the five diverging adapters, `manifest` loader, `env_sync`, module manifests and
  `pyproject.toml`s, the checklist, decisions, the harness, and the coherence audit.

- [ ] **SA261 — One owner per URL prefix, and theme API bases from the seam.**

  **Context:** blog and listings both mount `markdownx/`, so listings' editor uploads land under
  `blog/markdownx/` (coherence `markdownx-shared-mount`, collision); the theme writes module API
  paths as literals in four of five API clients (`mount-path-copies`); and the two
  `markdownx_urls.py` files differ only in the module name (arch audit §14).

  **Acceptance:** coherence §6 proposal 16 is merged and enforced: a shared third-party URLconf is
  mounted once by the lowest-layer module that needs it, `collect_wiring` fails on two modules
  mounting one prefix, the runtime seam carries module API bases, and the harness rejects a
  `/<mount>/api` literal in the theme's TypeScript.

  **Surfaces:** blog and listings URLs, `module_wiring`, the theme's API clients, decisions, the
  harness, and the coherence audit.

- [ ] **SA263 — Adapters validate, coerce, and default only through the manifest.**

  **Context:** all 12 adapters validate, coerce, and default options differently
  (coherence `option-schema-and-validation`); core's resolver step 5 validates against rule lists
  the loader refuses (gap 14); a blank `__QS_ENV__:` marker renders as a literal string (gap 15);
  backups' remote credentials break rule 1's naming (`secret-env-var-names`).

  **Acceptance:** coherence §6 proposals 2 and 8 are merged and enforced: the generic path
  validates, types, and projects `_ENV_VAR` options (blank → `""`), post-hooks compute only
  settings no single option maps to, and the harness rejects re-validation, coercion,
  `.get(<option>, <default>)`, and value checks in `adapter.py`. The dead resolver step is
  removed, a blank secret marker renders `""`, and backups' private-remote credentials are a
  listed rule 1 exception.

  **Surfaces:** the 12 adapters, `resolver.py`, `module_wiring.py`, decisions, the harness, and
  the coherence audit.
- [ ] **SA267 — Bring `scripts/` under the quality thresholds without gating it.**

  **Context:** `check_quality.sh` scans only packages, and `scripts/` misses its fixed lines:
  about 65 functions at CC >= 21, 9 non-test files >= 800 lines, and 8 vulture 100%-confidence
  findings (arch audit `rules-held-by-parity-not-derivation`).

  **Acceptance:** `scripts/` has no finding on the gate's fail lines: radon CC >= 21, files
  >= 800 lines, and vulture at 100% confidence. Prefer deleting dead or redundant governance
  code over splitting it. Behavior of every gate is unchanged, and their tests pass. `make
  quality` and `check_quality.sh` discovery are not changed.

  **Slices:** one per script family, largest debt first; each lands green on its own.

  **Surfaces:** `scripts/` and their tests, and the arch audit.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
