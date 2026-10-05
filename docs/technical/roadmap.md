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
published yet ([publish_procedure.md](publish_procedure.md)).

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA244 | Scope account anonymization to the person's records and bound its scans | 3 | — | Required |
| SA245 | Share one redaction matcher and one set of replacement values across anonymization handlers | 3 | SA244 | Required |
| SA246 | Declare personal data per module and check it where the project's models are installed | 2 | — | Optional |
| SA247 | Split the module-conventions checker and its tests into packages without changing behavior | 1 | — | Optional |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | 1 | — | Optional |
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | 1 | — | Optional |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191, SA246 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA214 | Harden the fresh-first migration tool into the standard upgrade path | 1 | — | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA247 ──► SA214 ──► SA191 ──► SA153 ──► SA204 ──► SA154 (inventory)
Track 2: SA246
Track 3: SA244 ──► SA245
     critical path: SA191 → SA153; release gate: SA244 → SA245 before 0.89.0
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Slices.** Large tickets list `Slices:` in their body. Each slice is one implementer session
with a fresh context, scoped to that slice's text and named surfaces, and ends with a short
handoff note (what landed, what is next, what to watch) committed with the work. A ticket closes
when its last slice lands; slices are not scheduled.

**Order.** SA247 runs first on Track 1 so later convention-rule edits (SA245, SA246) touch one rule module
instead of a 6,650-line file; it is a pure move. SA204 freezes migration history before any post-SA153 module schema change; SA154 is
an inventory, not work. SA214 runs on a pinned pre-SA191 `bap-web` donor. SA244 and SA245 share
the anonymization handler files and gate 0.89.0. SA246 touches `apps.py` capabilities and orgs'
checks, not handler bodies, and lands before SA153 so the portal's personal fields are classified
from the first migration.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA247 | yes | yes | yes | **yes** | yes |
| 2 | SA246 | yes | yes | yes | **yes** | no |
| 3 | SA244 | yes | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the quality
  thresholds (`scripts/check_quality.sh`), the generated `urls.py.j2` and the theme's social seam pages, the parity oracles, the hosted
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
  `quickscale_orgs_create_site_org` command, the personal-data inventory, and the frontend
  decisions in `frontend.md`, and, for the
  conventions, the `quickscale_core.runtime` helpers, module `checks.py` and `exceptions.py`,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, and the conformance harness with its registry row, and the five `_anonymization.py`
  handlers with core's redaction helpers (SA244, SA245).
- SA247 moves the conformance harness's files (`scripts/check_module_conventions.py`, its test, and
  the new packages) without changing rules; Tracks 2 and 3 rebase their rule edits onto the new
  layout after it merges.
- SA246 moves the personal-data inventory and its walk from Track 3 to Track 2: the per-module
  personal-data declarations, the orgs personal-data system check, and module-extension.md
  § removal.
- **Cross-track edits.** Outside the conventions, no queued ticket edits another track's surfaces;
  a ticket that does lands through the serialized merge queue.
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

- [ ] **SA244 — Scope account anonymization to the person's records and bound its scans.**

  **Context:** SA216(a) made notifications' `_scrub_messages` walk every `NotificationMessage` and
  redact the person's name and username wherever they appear as whole words, so one user's account
  removal rewrites unrelated text in every tenant's messages, including pending ones later sent
  (tech audit `notifications-anonymize-rewrites-all-messages`, S2). The same removal transaction,
  holding org row locks and provider advisory locks, also decodes every `django_session` row and
  walks every billing `WebhookEvent` payload; past gunicorn's 60 s timeout the worker dies after
  the Stripe cancellation and the compensation never runs (`anonymize-full-table-scans-under-locks`,
  S3). Neither has shipped; both block 0.89.0.

  **Acceptance:**
  - notifications redacts names and usernames only in messages linked to the person: those with a
    delivery to them, and those whose `context_json` records them as the actor through an
    `actor_user_id` key that `send_notification` callers (the orgs invitation send) now stamp.
    Pre-key invitation messages are covered by a one-time fallback that matches the person's
    unique email in `context_json`, never their name.
  - A test with a second user's message containing a common word and a person whose first name is
    that word leaves the unrelated message byte-identical; the shared-invitation test still passes.
  - auth deletes only sessions with `expire_date > now()`; billing pre-filters `WebhookEvent` rows
    in SQL on the person's email before the Python walk. No handler scans a whole table.
  - The dead `_account_username` helper is deleted (`notifications-account-username-dead`).

  **Surfaces:** `notifications/_anonymization.py` and its tests, the orgs invitation send call
  site, `auth/_anonymization.py`, `billing/_anonymization.py`, and the tech audit.

- [ ] **SA245 — Share one redaction matcher and one set of replacement values across anonymization handlers.**

  **Context:** billing and notifications carry byte-identical copies of the address helpers that
  have already diverged: billing still matches the name as a bare substring and rewrites payload
  keys, so an account named `Bill` turns `billing_details` into `[redacted]ing_details` (tech
  audit `billing-anonymize-name-substring`; coherence audit
  `anonymize-redaction-helper-copies`). The same field kind, an address inside a stored provider
  payload, becomes `deleted-<pk>@invalid` in notifications and `[redacted]` in billing, with the
  tokens spelled in five places (`anonymize-replacement-values`). auth's private entry point is
  `scrub_account` while the other four are `anonymize_account`, and its file also holds the
  cross-module collector (`anonymize-executor-naming`).

  **Acceptance:**
  - `quickscale_core.runtime` exposes the redaction helpers (`replace_address`, `redact_names`)
    and the `DELETED_ADDRESS(pk)` and `REDACTED` values; one core test table pins namesake,
    overlapping address, quoted address, and untouched-key cases. HTML-entity spellings stay an
    opt-in of notifications.
  - billing and notifications use them, with word-bounded name and username matching and no key
    rewrite; every email address becomes `DELETED_ADDRESS(pk)`, every name or username `REDACTED`
    (option A of the coherence audit), and wholesale-replaced provider prose keeps `REDACTED`.
  - auth's handler entry point is `_anonymization.anonymize_account`, and the collector moves to
    auth's `_anonymize_boundary.py`.
  - decisions.md § Module Conventions records rules 47 (redaction) and 48 (replacement values and
    entry-point name); the harness enforces both with control cases (billing's current
    `_redact_string` and `REDACTED = "[redacted]"`), and the coherence audit's three items close.

  **Surfaces:** `quickscale_core.runtime`, the five `_anonymization.py` handlers, auth's new
  boundary file, decisions, the conformance harness, and the coherence audit.

- [ ] **SA246 — Declare personal data per module and check it where the project's models are installed.**

  **Context:** whether every personal field has an anonymization treatment is checked only by a
  test in orgs over shipped models (`orgs/tests/_personal_data_inventory.py`), which skips project
  apps by design and ties the recorded treatment to no handler. A project-owned field such as an
  SA153 contact email on a user-referencing model is detected by nothing (arch audit
  `personal-data-coverage-shipped-only`). Eight modules' rows also live in orgs' tests, which the
  authoring guide never mentions (coherence audit `personal-data-inventory-ownership`).

  **Acceptance:**
  - Each module declares the treatment of its own user-linked fields beside its handler, collected
    through `collect_capabilities` like `anonymize_handlers`; orgs' file keeps only orgs, contrib,
    and third-party rows. The closed-world inventory test reads the collected declarations and
    keeps its three control cases.
  - `walk_candidate_fields` and `candidate_kinds` move into `quickscale_modules_orgs` as a
    warning-level system check over installed apps, on the `check_model_classification` (W005)
    pattern; a control proves a project-app `EmailField` on a user-referencing model fails it.
  - Each module's anonymization test asserts its declared treatments on a populated user.
  - decisions.md records rule 49 (personal-data declarations); module-extension.md § removal
    documents the declaration and the check and replaces "account-deletion collector" with the
    anonymize boundary's name.

  **Surfaces:** each module's `apps.py` capability, `orgs/checks.py`, orgs' personal-data inventory
  and its test, module-extension.md, decisions, and the arch and coherence audits.

- [ ] **SA247 — Split the module-conventions checker and its tests into packages without changing behavior.**

  **Context:** `scripts/check_module_conventions.py` (~6,650 lines) and
  `scripts/test_check_module_conventions.py` (~7,300 lines) are too large to read whole; an agent
  session ran out of output after reading both. No source file should exceed ~1,500 lines, so a
  rule edit needs only that rule's module plus core. Pure move: no renames, no rule logic edits, no
  "while I'm here" fixes.

  **Scope:**
  - `scripts/module_conventions/`: `core.py` (`Corpus`, `AuthorityError`, `_read_tree` and corpus
    loading, AST helpers shared by more than one rule — bindings, scoping,
    terminate/reachability); `rules_*.py` grouped by theme (identity/naming,
    dependencies/imports, routes/views, models/settings, docs/README, analytics); `rule_44.py` for
    the rule-44 lexical scanner and its `_rule_44_*` helpers; one ordered registry preserving the
    current execution and output order. Single-rule helpers move with their rule, not into core.
  - `scripts/check_module_conventions.py` stays a thin entry point (`main(argv)` plus re-exports of
    every name tests or other scripts import today, found by grepping the repo), so the Makefile
    target (Makefile:1115), CI, and `gate_registry.json` stay unchanged.
  - The test file splits the same way into `scripts/tests_module_conventions/` or
    `test_module_conventions_*.py`, whichever the pytest configuration discovers, with shared
    fixtures in a conftest or helper module.

  **Acceptance:**
  - `pytest --collect-only -q` reports the same test count before and after; the suite and the
    `make` target that runs the checker pass; no test logic changes.
  - The checker's output on the real repo is byte-identical before and after (saved and diffed).
  - `wc -l`: no new file exceeds ~1,500 lines.
  - `scripts/README.md` and the Makefile:1112 comment point at the new layout, and
    `scripts/adaptive.rules.md` mentions the per-rule layout if it documents where rules live.
  - The delivery summary lists helpers seen duplicated across other `check_*.py` scripts as
    candidates for a later pass; a shared library for them is out of scope.

  **Surfaces:** `scripts/check_module_conventions.py`, its test, the new `scripts/module_conventions/`
  and test packages, `scripts/README.md`, the Makefile comment, and `scripts/adaptive.rules.md`.

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
    rehearsed on the scratch database.

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
  - A decision records who owns a pre-facade donor `production.py`: the migration rewrites a
    recognized pre-facade database block onto the facade while the donor stays read-only
    ([decisions.md § Generated-File Ownership](decisions.md#generated-file-ownership-taxonomy)).

  **Slices:**
  - [x] (a) `make beta-migrate-iterate`: one non-interactive iteration driven by the donor's
    `quickscale.yml`. Handoff: the target reads slug, package, theme, and modules from the donor
    config, regenerates through a staging directory and `quickscale apply --split-refs-from-branches`,
    then runs fresh-first; next are G-001 and slices (b)–(f); watch the apply confirmation input and
    the fail-closed recipient and stage guards.
  - [x] (b) Classification of every donor file, with unclassified files as blockers. Handoff: the
    audit classifies donor files against the fresh recipient (identity-normalized) and the generator
    emission inventory, records the inventory in the report and stdout, and blocks before mutation on
    an unclassified or unreadable file; next are slices (c)–(f), starting with G-001; watch the
    recognized-root allowlist — a new donor root blocks until the maintainer classifies it.
  - [x] (c) Project-owned apps (copy, register, mount, regenerate migrations) and frontend
    dependency merge.
  - [x] (d) The `showcase_react` design layer, its ownership entry and upgrade test, and the
    donor design port. Handoff: the theme emits `frontend/design/` (tokens.css,
    tailwind.preset.js, fonts/, brand/), the React entry imports it and Django-rendered pages
    resolve the same tokens, the layer is declared never-overwritten in
    generated_file_ownership.md with an apply-upgrade test, and the tool's `port-donor-design`
    step validates and copies the donor layer or its legacy index.css/tailwind.config.js sources;
    next are (e)–(f); watch the design-layer recipient preflight and the regenerated
    exact-emission fixture.
  - [x] (e) The generated `MIGRATION_PROMPT.md` and its snapshot test. Handoff: delivered by
    `1e628dd5` and kept green through slices (b)–(d) — the fresh-first and iterate flows write
    `MIGRATION_PROMPT.md` from the report (what was migrated, remaining manual actions with their
    paths and governing rules, hard constraints, done criteria) only after the verification stack
    completes, via a symlink-safe atomic replace; the `handoff_prompt.md` fixture pins the
    document and the smoke gate asserts it; next is (f), starting with G-001; watch prompt
    stability as the report schema grows.
  - [ ] (f) Ledger iterations to a clean final run, the playbook rewrite, and the pre-facade
    `production.py` decision. Handoff: the tool now rewrites a recognized pre-facade
    `production.py` onto the facade (G-001), carries non-regenerable project-owned-app migration
    operations into appended migrations with fail-closed safe-carry boundaries (G-002), and
    classifies donor root documentation and tooling paths (G-003); the pinned-donor dry run is clean
    with zero unclassified files and both carries planned; next is the full execution iteration on
    PostgreSQL 18 with modules from `--split-refs-from-branches` (repinning to published splits is
    SA191's cutover step); watch the rewrite's recognized-shape boundary and the carry planner's
    same-app dependency chain.

  **Surfaces:** `quickscale_devtools/.../beta_migration/`, its tests and smoke gate; the migration
  playbook and gap ledger; the `showcase_react` theme, generator, and
  `generated_file_ownership.md` (design layer); decisions.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Open questions: whether "regenerate and port" is the permanent upgrade model, and whether
`experto-ai-web` migrates too. Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
