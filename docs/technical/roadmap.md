# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[decisions.md § Module Conventions](decisions.md#module-conventions). `bap-web` is then ported
once, onto the standardized names (SA191), and carries the first property portal in a
project-owned extension (SA153). Capabilities are generalized only after that project proves
their value.

**Release status.** 0.88.0 is published and carries two S1 billing defects fixed on `v89` (with
real Stripe keys, every webhook and every checkout fails); the fix ships in 0.89.0, which is not
published yet ([publish_procedure.md](publish_procedure.md)). The webhook half and the checkout
relative-URL code repair are fixed — checkout and portal sessions now build absolute return URLs
(tech audit `billing-checkout-relative-redirect-urls`) — while the live Stripe test-mode checkout
record and SA251's remaining slices are outstanding; SA252 (a live credential sent to PostHog) is
also required, so 0.89.0 is not published until SA251 and SA252 land.

The 2026-10-08 audits ([arch](../others/arch-audit.md), [tech](../others/tech-audit.md),
[coherence](../others/coherence-audit.md)) are scheduled as SA251–SA266. Each ticket names the
audit IDs it closes; the audits keep the evidence. Coherence tickets merge the matching proposed
rule from coherence audit §6 into [decisions.md § Module Conventions](decisions.md#module-conventions)
with a harness detector, and the audits' watchlists stay unscheduled.

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA251 | Make Stripe checkout and payment outcomes complete and recoverable | 2 | — | Required |
| SA252 | Stop deriving the analytics distinct ID from the session key, and guard the dashboard | 3 | — | Required |
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | 1 | — | Optional |
| SA257 | Derive cross-row tenant equality for every tenant-to-tenant FK | 1 | — | Optional |
| SA266 | Sweep module models, templates, tests, and commands onto the written rules before the freeze | 1 | — | Optional |
| SA259 | Generate gate wiring from the registry instead of holding copies by parity | 2 | — | Optional |
| SA265 | Put cross-module vocabulary, capabilities, and private names in their owners | 3 | — | Optional |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | 1 | SA257, SA259, SA265, SA266 | Optional |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191, SA204 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA256 | Fix `deploy railway` environment writes and DR media streaming | 2 | — | Optional |
| SA253 | Make the generated project's CI, image, and healthcheck pass, and execute them in a gate | 2 | SA259 | Optional |
| SA255 | Accept Resend's real webhook signature in notifications | 2 | — | Optional |
| SA260 | One off switch and a closed-world manifest surface | 2 | — | Optional |
| SA263 | Adapters validate, coerce, and default only through the manifest | 2 | SA260 | Optional |
| SA254 | Harden self-registration: anonymize scope, invitation throttle, VIEW-AS scope | 3 | — | Optional |
| SA258 | Move the module↔project seam from user-owned generated files into the runtime | 3 | — | Optional |
| SA264 | One module error base, one HTTP mapping, and one startup-check order | 3 | — | Optional |
| SA262 | One JSON API contract: guards, 401, pagination, throttles, and DRF keys | 3 | SA252, SA264 | Optional |
| SA261 | One owner per URL prefix, and theme API bases from the seam | 3 | SA258 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191 ═╗ SA257 ──► SA266 ──► SA204 ──► SA153 ──► SA154 (inventory)
               (interleaves while SA191 waits on the maintainer)
Track 2: SA251 ──► SA256 ──► SA259 ──► SA253 ──► SA255 ──► SA260 ──► SA263
Track 3: SA252 ──► SA254 ──► SA265 ──► SA258 ──► SA264 ──► SA262 ──► SA261
     release path:  SA251 ∥ SA252 → publish 0.89.0
     critical path: SA191 → SA153, joined by SA259 (T2) and SA265 (T3) → SA204 → SA153
```

Arrows within a track are queue order; the table holds the actual dependency edges. Cross-track
edges: SA204 waits on SA259 (Track 2) and SA265 (Track 3); SA191's cutover slice (e) waits on
SA258 (Track 3) as an ordering rule, not a table edge, so slices (a)–(d) are not blocked.

**Slices.** Large tickets list `Slices:` in their body. Each slice is one implementer session
with a fresh context, scoped to that slice's text and named surfaces, and ends with a short
handoff note (what landed, what is next, what to watch) committed with the work. A ticket closes
when its last slice lands; slices are not scheduled.

**Order.** SA251 and SA252 go first: they gate the 0.89.0 publish. Every change to a shipped
module `0001_initial` (SA257's composite constraints, SA265's billing column on the tenant root,
SA266's model and constraint renames) lands before SA204 freezes migration history, and SA204
lands before SA153 slice (a), whose schema work is `0002+` from the start (arch audit §7).
SA259 lands before the new gates it cheapens (SA204's hash gate, SA253's rendered-artifact gate).
SA258 lands before SA191's cutover so `bap-web-new` starts on thin includes and pays one adoption
step instead of one per release. SA154 is an inventory, not work. SA191 runs slice (b) first;
slice (a) waits on the maintainer's production dump, and Track 1 takes SA257 and SA266 while it
waits.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191 | yes | no | yes | no | yes |
| 2 | SA251 | yes | yes | yes | **yes** | no |
| 3 | SA252 | yes | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the quality
  thresholds (`scripts/check_quality.sh`), the generated `urls.py.j2` and the theme's social seam
  pages, the parity oracles, the hosted workflow triggers, the migration-history freeze gate and `decisions.md` § Clean-Break Migration History, the `bap-web`
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
- **Audit-ticket transfers.** For SA259, Track 2 takes `scripts/gate_registry.json`,
  `scripts/check_quality.sh`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`, and the gate
  documentation table from Track 1, and keeps them after. For SA255, Track 2 takes the
  notifications webhook (`notifications/views.py`, `_webhooks.py`) from Track 3. For SA265,
  Track 3 takes cross-module imports from Track 1. For SA257, Track 1 adds its check to orgs'
  `checks.py`, and Track 3 reviews. SA253 edits `base.py.j2` (Track 3) only for the test-settings line it names.
- **Cross-track edits.** SA191 builds its recipient by the migration playbook of the completed
  SA214 tool; SA191 only reads it, and gate documentation (Track 1) owns the smoke-gate row's
  documentation. Both land through the serialized merge queue.
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

  **Acceptance:** decisions record that rule 1 of the clean-break decision is lifted from 0.89.0
  onward, the release the freeze lands in. Upgrades from earlier vintages, including 0.88.0,
  stay fresh-database-only. From 0.89.0 on, a schema change to a model-bearing module ships as a
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
  `dr-restore-vintage-exact-match`. The freeze lands on SA257's, SA265's, and SA266's `0001`
  edits, and the new gate is added through SA259's generated wiring (two stations, not twelve).

  **Surfaces:** decisions, the new gate with its hash manifest, registry row, and gate
  documentation, `quickscale_core/tests/test_module_migration_topology.py`,
  `dr_engine/recovery.py` (Track 2 reviews), and the arch audit.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port.**

  Migrate `bap-web` into a new repository at `/home/victor/code/bap-web-new`, once, without the
  fresh-first tool: a fresh `quickscale plan` + `apply` recipient, then a coding assistant ports the
  donor by following [bap-web-migration-prompt.md](../planning/bap-web-migration-prompt.md).
  Hardening the tool is SA214.

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
  rebuilds a fresh database. The `quickscale_orgs_create_site_org` command creates the site's
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
    rehearsed on the scratch database. Waits on SA258 so the recipient adopts the runtime seam
    before it goes live (arch audit §7).

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
    organization constraint that SA257's check requires.
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

- [ ] **SA251 — Make Stripe checkout and payment outcomes complete and recoverable.**

  **Context:** the 0.89.0 billing fix (SA209) repaired webhooks only. Checkout and portal sessions
  still pass relative `success_url`/`cancel_url`/`return_url`, which Stripe rejects, so every
  purchase fails with real keys in 0.87.0, 0.88.0, and HEAD (tech audit
  `billing-checkout-relative-redirect-urls`, S2). Two defects sit behind it on the same path: a
  failed checkout create leaves a reservation with an unknown provider outcome that blocks account
  deletion and purge forever (`billing-reservation-unknown-outcome-permanent`), and one-time
  purchases paid by a delayed method are never credited (`billing-async-payment-never-credited`).

  **Acceptance:** every URL handed to Stripe is absolute, built from the request or the configured
  site origin, and `StripeClient` refuses a relative one. One Stripe test-mode checkout from the
  API view completes at HEAD and is recorded. An unknown-outcome reservation resolves by a
  provider-side lookup (expire or adopt), and an operator reconciler clears rows already created;
  deletion and purge are no longer blocked by a resolvable reservation. `checkout.session.
  async_payment_succeeded` credits a one-time purchase exactly once and `async_payment_failed`
  releases it, on the existing event-dedup key. 0.89.0's release notes name the checkout fix.

  **Slices:**
  - [ ] (a) Absolute return URLs with the `StripeClient` guard and the test-mode record. The
    request-built absolute URLs and the client guard landed with tests; the live Stripe test-mode
    checkout record still needs test credentials and a running recipient.
  - [ ] (b) Unknown-outcome resolution and the operator reconciler.
  - [ ] (c) Delayed-payment webhook events.

  **Surfaces:** `billing/views.py`, `_checkout.py`, `_removal.py`, `_webhooks.py`,
  `_stripe_client.py`, their tests, the billing README, and the tech audit.

- [ ] **SA252 — Stop deriving the analytics distinct ID from the session key, and guard the dashboard.**

  **Context:** server-side analytics sends an identifier derived from the live session key to
  PostHog (tech audit `analytics-distinct-id-is-session-key`, S2; scenario in the private
  companion). The analytics overview page is the only module page with no guard
  (`analytics-dashboard-unauthenticated`, S4; coherence `tenant-authorization`, analytics half).

  **Acceptance:** the distinct ID is the user's stable non-secret ID when signed in and a random
  anonymous ID otherwise; no value derived from `session_key` reaches an outbound client or
  logger, and a conformance rule rejects it. The dashboard requires staff or the documented org
  role, with a test for the anonymous and under-privileged cases. The release notes tell each
  analytics-enabled deployment to invalidate sessions *after* upgrading and to purge or re-key
  PostHog persons.

  **Surfaces:** `analytics/services.py`, `analytics/views.py`, their tests, the analytics README,
  the conventions harness, and the tech audit.

- [ ] **SA253 — Make the generated project's CI, image, and healthcheck pass, and execute them in a gate.**

  **Context:** generated automation is only text-asserted, never run, and four defects live there
  (tech audit §9): the rendered CI cannot pass on a fresh project (`generated-ci-fails-out-of-box`),
  it uses mutable third-party action tags and no `permissions:` block
  (`generated-ci-mutable-action-tags`), the image `HEALTHCHECK` gets 400 under production settings
  (`docker-healthcheck-always-unhealthy`), and the frontend stage resolves npm dependencies
  unpinned when no lockfile exists (`frontend-image-floating-deps`). They share `ci.yml.j2` and
  `Dockerfile.j2`, so they land together.

  **Acceptance:** a fresh generated project's CI passes as rendered. The rendered workflow pins
  actions by SHA with a least-privilege `permissions:` block, and `check_workflow_security.py` and
  `make refresh-action-pins` cover `ci.yml.j2`. The `HEALTHCHECK` passes under production settings.
  The frontend image installs from a lockfile and fails without one. A registered gate generates a
  project offline and executes its CI test and migrate commands and the image healthcheck; it is
  added through SA259's generated wiring.

  **Surfaces:** `ci.yml.j2`, `Dockerfile.j2`, the test-settings line of `base.py.j2`,
  `scripts/check_workflow_security.py`, the new gate, and the tech audit.

- [ ] **SA254 — Harden self-registration: anonymize scope, invitation throttle, VIEW-AS scope.**

  **Context:** with the auth default `email_verification: none`, self-service removal rewrites
  other tenants' rows selected by an unverified address (tech audit
  `anonymize-matches-unverified-address`, S3). Any self-registered saas user can send unlimited
  invitation emails with chosen text (`org-invitation-email-unthrottled`, S3). A VIEW-AS
  organization replaces the URL's organization on management pages
  (`viewas-overrides-management-org`, S4).

  **Acceptance:** the orgs, notifications, and billing anonymization handlers select rows by the
  user's own keys or a verified address only, with a test where another tenant holds the same
  unverified address. Invitation sends are throttled per user and per organization through a
  rule 32 scope, and the free-text message is bounded and escaped. Management pages resolve the
  organization from the URL, never from VIEW-AS.

  **Surfaces:** the three `_anonymization.py` handlers, orgs `views.py`, `forms.py`,
  `middleware.py`, `_view_context.py`, their tests, and the tech audit.

- [ ] **SA255 — Accept Resend's real webhook signature in notifications.**

  **Context:** the notifications webhook accepts only a custom signing contract that Resend never
  sends, so delivery events never arrive (tech audit `notifications-webhook-rejects-resend`, S3).

  **Acceptance:** the webhook verifies Resend's Svix signature (`svix-id`, `svix-timestamp`,
  `svix-signature`, base64 secret with its `whsec_` prefix, timestamp tolerance) and keeps rule
  26's shape and replay key. A contract test is built from the vendor's documented payload and
  signature. The README documents the secret and endpoint.

  **Surfaces:** notifications `views.py`, `_webhooks.py`, their tests, the README, and the tech
  audit.

- [ ] **SA256 — Fix `deploy railway` environment writes and DR media streaming.**

  **Context:** `deploy railway` overwrites `DJANGO_SETTINGS_MODULE` with a value derived from the
  service name (tech audit `deploy-settings-module-from-service-name`, S3) and embeds a reused
  runtime password unquoted in a URL (`deploy-runtime-url-unquoted-password`, S4); both are in
  `_deploy_service_config.py`. DR media sync reads whole objects into memory
  (`dr-media-sync-whole-object-read`, S4).

  **Acceptance:** deploy writes the project's settings module from project state and leaves an
  existing value alone, and percent-encodes credentials in every URL it builds, with a test using
  a password containing `@:/%#`. Media sync streams objects in bounded chunks.

  **Surfaces:** `commands/_deploy_service_config.py`, `dr_engine/_media.py`, their tests, and the
  tech audit.

- [ ] **SA257 — Derive cross-row tenant equality for every tenant-to-tenant FK.**

  **Context:** 6 of the 10 shipped intra-tenant FKs carry a composite `(fk, organization_id)`
  constraint, held by hand-listed tuples, and project FKs are covered by nothing. A seed, command,
  or project service that writes IDs can persist a cross-organization reference, which then lets
  one org's deletion cascade into another's rows or block its purge (arch audit
  `tenant-reference-equality-partial`, option 1). SA153 adds at least two such references.

  **Acceptance:** an orgs system check walks the marker-derived tenant models, finds every FK to
  another tenant model, and requires a composite constraint present in `pg_constraint` or a
  declared `tenant_reference_exemptions` entry; it runs in projects like W006, starts as a
  Warning, and replaces both hand-listed tuples. The four missing shipped composites land inside
  their module's `0001_initial`, before SA204. `module-extension.md` documents
  `add_composite_child_fk` for project-owned tenant tables.

  **Surfaces:** orgs `checks.py` (Track 3 reviews), the affected modules' models and
  `0001_initial`, `orgs/tests/test_tenant_table_conformance.py`, `module-extension.md`, and the
  arch audit.

- [ ] **SA258 — Move the module↔project seam from user-owned generated files into the runtime.**

  **Context:** module-facing contracts are emitted once into user-owned files (`urls.py`,
  `index.html`, `useApi`/`useModules`, `settings/base.py`, `start.sh`), so every module contract
  change becomes a hand-applied prose step per project, and three upgrade mechanisms are
  maintained while the one real upgrade goes by prompt (arch audit
  `generated-file-ownership-unmodeled`, regressed, option 2: extend SA206).

  **Acceptance:** the seam producer, module flags and paths, DRF composition, and error-shape
  parsing ship in `quickscale_core.runtime`: a template tag or context processor for
  `window.__QUICKSCALE__`, a `compose_rest_framework()` helper called from `settings/base.py`, and
  URL inclusion only through managed URLconfs. User-owned files hold a one-line include each. Each
  moved piece adds its last adoption step to `project_contract.yml`. A closed-world generator test
  fails when a Django-side user-owned emitted file contains a module name or module URL name.
  Lands before SA191's cutover; afterwards decide in decisions.md which upgrade mechanism
  (`beta_migration`, the vintage steps) is retired.

  **Slices:**
  - [ ] (a) `seam_module_flags` and `seam_module_paths` as a runtime template tag.
  - [ ] (b) `compose_rest_framework()` in `settings/base.py`.
  - [ ] (c) Managed URLconf inclusion and the emission test.

  **Surfaces:** `quickscale_core.runtime`, `generator/seam.py`, the settings templates, the
  generated `urls.py.j2` and theme hooks (Track 1 reviews), `project_contract.yml`, and the arch
  audit.

- [ ] **SA259 — Generate gate wiring from the registry instead of holding copies by parity.**

  **Context:** each rule is restated by hand in about 12 places with a parity gate keeping them
  equal; the split-facade scan covers 4 of 12 split packages; `check_quality.sh` excludes
  `scripts/` and falls back silently to a hardcoded path list when discovery finds nothing (arch
  audit `rules-held-by-parity-not-derivation`, option 1 plus option 3's budget;
  §11 `check_quality.sh:170–172` and `contracts/imperative_inventory.py`).

  **Acceptance:** `gate_registry.json` is the only gate list; the Makefile gate targets, the
  `check_ci_locally.sh` stage list, the `ci.yml`/`publish.yml`/e2e regions, and the docs table are
  generated from it, and `check_gate_parity.py` shrinks to "generated files are current". The
  split-facade scope is derived from layout, with a test that fails when a package with `_*.py`
  split files is outside it. `check_quality.sh` scans `scripts/` and fails when discovery is
  empty. The vestigial `contracts/imperative_inventory.py` is deleted. Decisions record the
  budget: no new gate or rule without retiring one. Adding a gate costs two stations.

  **Surfaces:** `scripts/gate_registry.json`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`,
  `check_split_facade_imports.py`, `check_quality.sh`, `check_ci_locally.sh` (respecting its
  parity-executed prefix), the workflows, the gate documentation, and the arch audit.

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
  mounting one prefix, the seam (from SA258) carries module API bases, and the harness rejects a
  `/<mount>/api` literal in the theme's TypeScript.

  **Surfaces:** blog and listings URLs, `module_wiring`, the theme's API clients, decisions, the
  harness, and the coherence audit.

- [ ] **SA262 — One JSON API contract: guards, 401, pagination, throttles, and DRF keys.**

  **Context:** coherence `tenant-authorization` (billing's `AllowAny` plus a hand-written check
  and no README role table), `unauthenticated-status-code` (401 in four modules, 403 in two),
  `http-api-shape` (list and body shapes; social's generated payload views are `JsonResponse`
  functions that echo `str(exc)`, tech `social-payload-echoes-exception-text`),
  `throttle-attachment` (two attachment styles; listings' publish API has no scope), and
  enforcement gap 13 (any module may replace any `REST_FRAMEWORK` key).

  **Acceptance:** coherence §6 proposals 7, 11, and 13 are merged and enforced: every view
  declares its guard and every README lists minimum roles; unauthenticated calls answer 401
  through core's one session authentication class; lists paginate through `PlainListPagination`
  with a `<THING>_PER_PAGE` setting; throttles attach by `throttle_scope` only and every
  vendor-calling or publishing write API has one; generated social payload views follow rule 9
  and return no exception text; `collect_wiring` admits only `DEFAULT_THROTTLE_RATES` from
  modules. The JSON API contract drops "the billing-module pattern".

  **Surfaces:** module views and READMEs, core's DRF helpers, `social_manifest.py`'s rendered
  views, `collect_wiring`, decisions, the harness, and the coherence audit.

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

- [ ] **SA264 — One module error base, one HTTP mapping, and one startup-check order.**

  **Context:** five ways a module error becomes an HTTP status, with `InsufficientCreditsError`
  answering 500 `billing_error` (coherence `module-error-http-mapping`), and five modules diverge
  on startup checks and error names (`startup-checks-and-errors`).

  **Acceptance:** coherence §6 proposal 5 is merged and enforced: `<Module>Error` uses the module
  name, derives from `Exception`, and API-visible subclasses set `status_code`/`default_code`
  that core's handler renders; no `APIException` in a module hierarchy; `retired_settings` lives
  in `module.yml`; the settings check registers before module checks and module checks do not
  re-list declared settings. Rule 10's detector checks the name and modules without
  `exceptions.py`.

  **Surfaces:** module `exceptions.py` and `checks.py`, core's exception handler, manifests,
  decisions, the harness, and the coherence audit.

- [ ] **SA265 — Put cross-module vocabulary, capabilities, and private names in their owners.**

  **Context:** lower layers hold higher layers' words: orgs' removal-obligation names,
  notifications' email-template keys, and `Organization.stripe_customer_id`, a billing column on
  the tenant root (coherence `upward-name-references`, regressed). Capabilities have two
  collectors and no list of names (`capability-collection`); private names are imported across
  modules (`module-dependency-direction`); required modules are guarded as optional, so forms
  reports `queued` when notifications is off (`optional-sender-guard`, tech
  `forms-notification-status-misreported`); session keys follow no namespace
  (`session-and-host-names`); core and the CLI keep per-module constants and branches
  (`core-cli-module-knowledge`, the convention side of arch watchlist
  `core-holds-module-vocabulary`).

  **Acceptance:** coherence §6 proposals 3, 4, 14, 15, and 17 are merged and enforced. Senders own
  and register their email templates and obligation names by capability; the Stripe customer ID
  moves to a billing-owned table inside billing's and orgs' `0001_initial` before SA204; core's
  `CAPABILITIES` lists every name and shape and `collect_capabilities` is the only collector; no
  module imports another's `_`-prefixed name; required modules are imported directly and asked
  `is_enabled()`, and forms reports `skipped` when no email is sent; session keys are
  `quickscale_<module>:<name>`. `module-extension.md` lists every core edit a new module needs,
  and the harness rejects any other per-module constant or `module_name == "<module>"` branch in
  core or the CLI.

  **Slices:**
  - [ ] (a) Schema: the billing customer column and orgs' removal names (before SA204).
  - [ ] (b) Capabilities, email-template ownership, and sender guards.
  - [ ] (c) Private-name imports, session keys, and core/CLI per-module knowledge.

  **Surfaces:** orgs, notifications, billing, forms, crm, blog, social models and services;
  core's capability helper and `contracts/module_options.py`; `module-extension.md`; decisions;
  the harness; and the coherence audit.

- [ ] **SA266 — Sweep module models, templates, tests, and commands onto the written rules before the freeze.**

  **Context:** tax-level drift across modules (coherence `model-basics`, `constraint-purpose-tokens`,
  `template-folder-depth`, `test-file-names`, `ticket-ids-in-shipped-source`,
  `command-flag-conventions`). The model and constraint renames rewrite `0001_initial`, so they
  land before SA204 or never cheaply.

  **Acceptance:** coherence §6 proposals 9, 6 (page depth), 10, and 12 and proposal 3's constraint
  tokens are merged and enforced: model basics hold with no `Meta.app_label`; constraint names use
  the lowercased model token, field-named purposes, and the `_unique` suffix; pages are flat under
  `quickscale_<module>/` and admin overrides under `admin/<label>/<model>/`; `tests/templates/`
  is allowed and no other non-test file; no ticket id appears in shipped source or `module.yml`;
  commands use `--json`, `--trigger {manual,scheduled}` defaulting to `manual`, and `--confirm
  <identifier>` for destructive runs. Release notes list moved template paths for host overrides.

  **Surfaces:** module models and `0001_initial`, templates, tests, management commands,
  decisions, the harness, and the coherence audit.

- [x] **SA214 — Harden the fresh-first migration tool into the standard upgrade path.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
