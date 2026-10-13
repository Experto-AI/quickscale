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
([publish_procedure.md](publish_procedure.md)); the `v89` task tree passes `make release-gate`
with an isolated Poetry cache (evidence in the [technical audit](../others/tech-audit.md#11-watchlist-and-accepted-trade-offs)).
Two tickets are release requirements and land before the tag: SA269 (so the release gets its
hosted E2E run) and SA271 (the 2026-10-13 tech-audit S3s, all introduced since 0.88.0).
Publication remains a maintainer action.

Audit tickets name the [arch](../others/arch-audit.md), [tech](../others/tech-audit.md), or
[coherence](../others/coherence-audit.md) IDs they close; the audits keep the evidence. Coherence
tickets merge the matching coherence §6 rule into decisions with a harness detector.

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, acceptance, and each slice's tier; [CHANGELOG.md](../../CHANGELOG.md) preserves
history.

**Sizing.** Every slice carries an Adaptive tier
(Adaptive `docs/guides/operator-guide.md` § Planning and implementation):
Tier 1 is one bounded low-risk concern within direct context fit; Tier 2-fast is a specified
change with known targets, acceptance, and checks; Tier 2-full is one whose callers, mechanism,
or environment still need discovery. No slice is Tier 3: work that would be is split so that its
one-way or high-risk step stands alone behind the slices that prove it.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA269 | Make the release pipeline run hosted E2E and pin its Poetry retry | 1 | — | Required |
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | 1 | SA269, SA271 | Optional |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | 1 | SA275 | Optional |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191, SA204 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA271 | Stream disaster-recovery objects instead of spooling them | 2 | — | Required |
| SA275 | Derive gate wiring from the registry instead of holding copies equal | 2 | — | Optional |
| SA278 | Retire the gate-script frozen surfaces and scan `scripts/` for quality | 2 | — | Optional |
| SA273 | Harden the editor upload and the CLI's `pyproject.toml` write | 2 | — | Optional |
| SA282 | One organization-selector flag and a required contract-vintage id | 2 | — | Optional |
| SA280 | One source for the Stripe API version and the bundled manifests | 2 | SA275 | Optional |
| SA277 | Keep one project-upgrade mechanism and retire the other | 2 | SA191 | Optional |
| SA272 | Harden the notifications webhook and the orgs invite throttle | 3 | — | Optional |
| SA276 | Generate the theme's seam types from the manifest set | 3 | — | Optional |
| SA274 | Show real counts on the theme's CRM stat cards | 3 | — | Optional |
| SA283 | Manifest-read startup checks, one capability collector, one `--cov` form | 3 | SA272 | Optional |
| SA279 | Retire the conformance harness's frozen surfaces | 3 | SA278 | Optional |
| SA281 | Hand adapter hooks typed resolved options and delete the dataflow detector | 3 | SA279 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA269 ──► SA191 (repin, cutover) ∥ SA204 (a…g) ──► SA153 ──► SA154 (inventory)
Track 2: SA271 ──► SA275 ──► SA278 ──► SA273 ──► SA282 ──► SA280 ──► SA277
Track 3: SA272 ──► SA276 ──► SA274 ──► SA283 ──► SA279 ──► SA281
     release path:  SA269 + SA271 ──► publish 0.89.0 ──► SA191 repin
     critical path: SA275 ──► SA204 (c) ──► SA204 (g) ──► SA153 (a)
```

Arrows within a track are queue order; the table holds the dependency edges. Cross-track edges:
SA191 waits on Track 2's release fixes (through the 0.89.0 publication); SA204 waits on SA275 so
its freeze gate costs one registry row instead of about eight hand stations (arch audit §7);
SA279 waits on SA278, whose guard test it extends; SA277 waits on SA191's cutover, which decides
which upgrade mechanism proved itself.

**Parallel start.** SA269, SA204 (a), SA271, SA275, SA272, and SA276 have no unmet
dependency and touch disjoint files, so all three tracks start at once. SA204 (a), (b), (d), and
(e) do not wait on SA275; only (c) adds a gate row.

**Slices.** Large tickets list `Slices:` in their body. Each slice is one implementer session
with a fresh context, scoped to that slice's text and named surfaces, and ends with a short
handoff note (what landed, what is next, what to watch) committed with the work. A ticket closes
when its last slice lands; slices are not scheduled.

**Order.** Every change to a shipped module `0001_initial` lands before SA204 freezes
migration history, and SA204 lands before SA153 slice (a), whose schema work is `0002+` from the
start. None of the new tickets changes a module schema except SA270's additive reservation
attempt timestamps, which its Search-lag window reads; SA274's count endpoint and SA272's
status ranking are code-only. SA154 is an inventory, not work. SA191's agent work is done; its
remaining repin waits for the 0.89.0 publication, and SA204 proceeds alongside it. SA276 should
land before 0.89.0 is tagged if it fits, so `bap-web-new` adopts its step once at the repin
instead of on a live site (arch audit §7); it is not a release requirement.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA269 ∥ SA204 (a) | yes | no | yes | no | yes |
| 2 | SA271 | yes | yes | yes | no | yes |
| 3 | SA272 | yes | yes | yes | no | no |

### Ownership and merge coordination

- Track 1 owns the generated `urls.py.j2` and the theme's social seam
  pages, the parity oracles, the hosted workflow triggers (including `e2e.yml`'s tag pattern), the
  migration-history freeze gate, its hash manifest, and `decisions.md` § Clean-Break Migration
  History, the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation, and, for the conventions, module identities, models and their
  `0001_initial`, module READMEs, and module templates, static files, and template tags, with the
  module page templates and the generated `base.html`, and cross-module imports and settings reads,
  and the `services.py` public surface.
- Track 2 owns the gate registry and everything generated from it (`scripts/gate_registry.json`,
  `check_quality.sh`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`, `check_ci_locally.sh`'s
  gate arms, the Makefile gate help, the gate documentation
  table), `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package and the bundled-manifest build step, `ruff.toml`, the test-settings stubs, the
  gate-script parity families, the CLI apply/deploy/update commands, `utils/_dependency_write.py`,
  and `contract_vintage.py`, the module manifests' `contract_vintage` blocks and
  `project_contract.yml`, `contracts/module_options.py` and the `.env.example` template,
  `quickscale_core/dr_engine/`,
  and the billing module (`billing/services.py`, `billing/views.py`, `billing/adapter.py`,
  `_customers.py`, `_stripe_client.py`, its commands, and its docs), the split facades of the CLI
  commands, `dr_engine`, and billing with the tests that patch
  them, the blog and storage upload-path builders and the storage Markdownx upload, and, for the
  conventions, the manifest option schema and the CLI's `module_config`,
  module settings names, `is_enabled()`, and the per-module personal-data declarations with the
  orgs personal-data check, and the maintainer migration tools (`beta_migration/`) with their
  smoke gate, playbook, gap ledger, and the `showcase_react` design layer.
- Track 3 owns the orgs tenancy, purge, removal-obligation, invite-throttle, and boot path
  (`orgs/apps.py`, `orgs/removal.py`, `orgs/views.py`), the privileged-command and runtime-role
  stations, the
  `quickscale_core.runtime` settings facade, the generated settings templates (`base.py.j2`,
  `production.py.j2`, `local.py.j2`), the generator's Jinja environment, `auth/views.py`, the
  blog rate limiter, the generated `pyproject.toml.j2` `[build-system]` block, orgs'
  `quickscale_orgs_create_site_org` command, the notifications webhook (`_webhooks.py`), the
  CRM list API and the theme's CRM page, the generated theme seam types and the theme hooks that
  read them, and the frontend
  decisions in `frontend.md`, and, for the
  conventions, the `quickscale_core.runtime` helpers, module `checks.py` and `exceptions.py`,
  core's `CAPABILITIES`, the adapter hook signature,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, and the conformance harness with its registry row and its parity families, and the
  five `_anonymization.py` handlers with core's redaction helpers.
- **Cross-track edits.** SA204 (c) adds its gate row to the Track 2 registry; SA204 (d) and (e)
  edit Track 2's `dr_engine/recovery.py` and `update` command, with Track 2 review. SA269 (b)
  edits Track 2's `ci.yml` and `nightly-bypassrls.yml` outside their generated regions. SA282 (a)
  adds a harness clause and control to Track 3's harness; SA283 (a) edits Track 2's
  `billing/checks.py`; SA281 edits Track 2's option contract. All land through the serialized
  merge queue.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), the three audits,
  `project_contract.yml` (SA274, SA276, SA282), and [decisions.md](decisions.md). Each track
  resolves the shared set at its own merge, after the previous merge lands, then runs the
  consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Release requirements for 0.89.0

- [ ] **SA269 — Make the release pipeline run hosted E2E and pin its Poetry retry.**

  Closes tech `e2e-release-tag-trigger-never-matches` (S3, quick win) and
  `ci-poetry-retry-curl-pipe-python` (S4), the audit's pipeline batch.

  **Context:** `e2e.yml` triggers on `tags: ['v*']`, but release tags are `0.89.0`-style
  (`publish.yml` matches `"[0-9]*"`), so no release has had the hosted E2E run the workflow
  promises. The Poetry-install retry in `ci.yml` (three jobs) and `nightly-bypassrls.yml` pipes an
  unpinned `install.python-poetry.org` into `python3`, outside the SHA-pin contract.

  **Acceptance:** a release tag of the form `publish.yml` matches triggers `e2e.yml`, and an
  existing workflow test pins that the two tag patterns are equal (the audit's trigger-consistency
  tooling gap, held by a test, not a new gate). Every Poetry retry installs the pinned
  `poetry==2.4.1` through `pipx` or `pip`, and no workflow pipes a downloaded script into an
  interpreter. Generated workflow regions are untouched or regenerated by the sync.

  **Slices:**
  - [ ] (a) The `e2e.yml` tag pattern and its pinning test (Tier 1).
  - [ ] (b) The pinned Poetry retry in `ci.yml` and `nightly-bypassrls.yml` (Tier 1).

- [x] **SA270 — Keep checkout reconciliation fail-closed across Stripe Search lag.**

- [ ] **SA271 — Stream disaster-recovery objects instead of spooling them.**

  Closes tech `dr-private-remote-restore-whole-object-in-memory` (S3) and
  `dr-media-part-file-leak-on-publish-failure` (S4), the audit's DR batch.

  **Context:** `_materialize_private_remote_key` (`dr_engine/_remote.py:90–93`) copies through
  `S3Storage.open()`, which spools the whole object in memory (`AWS_S3_MAX_MEMORY_SIZE` is
  unbounded), so a dump larger than the container's memory OOM-kills the restore. It is the
  unfixed sibling of SA256's media fix. In `_media.py:153–179`, `chmod` and `replace` run outside
  the cleanup `try`, so a failure there leaves a `.part` file behind.

  **Acceptance:** the private-remote restore streams through the boto3 client's
  `download_fileobj`, the idiom `_media.py` uses, and a test proves the object is never read whole
  (a bounded-memory or chunked-read assertion). A failure in `chmod` or `replace` removes the
  `.part` file, with a test. A test or harness clause rejects `storage.open()` on a remote object
  in `dr_engine` (the audit's lint tooling gap), inside existing suites.

  **Slices:**
  - [ ] (a) Streaming private-remote restore with its bounded-read test and the `storage.open()`
    guard (Tier 2-fast).
  - [ ] (b) `.part` cleanup on publish failure, with its test (Tier 1).

### Track 1 — migration history and the property portal

- [ ] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

  Closes arch `clean-break-schema-no-data-path` (Finding 1, option 1 with the 2026-10-13
  addition) and retires tech watchlist `dr-restore-vintage-exact-match` and
  `initial-migration-edited-in-place`.

  **Context:** under [decisions.md](decisions.md) § Clean-Break Migration History, each
  model-bearing module ships one `0001_initial` that is rewritten in place every release, and the
  only supported upgrade is a fresh database. Every rewrite adds to the hand-written transform each
  deployed project needs on its next upgrade. SA191 reseeds `bap-web`, so the freeze is needed at
  SA153's go-live, where the first non-reseedable tenant data appears, and before any module schema
  change reaches that project. It is a one-way door (arch audit
  `clean-break-schema-no-data-path`, option 1). Every check that decides whether a database or a
  backup fits the installed code compares version labels today, and six modules' `0001` files
  differ under an equal label; the addition is that those checks compare **migration content
  identity** instead. SA204 is a release requirement for the release `bap-web` goes live on
  (SA153), not for 0.89.0.

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
  shallow CI clones and needs no tag). The same manifest is the content identity that restore and
  `quickscale update` compare: per module, the hashes of the applied migration files, recorded
  with every backup. Before merging, confirm no module schema change shipped
  between SA191's rebuild and the freeze, and prove on a restored `bap-web` copy that `migrate`
  from the frozen `0001` reproduces the FORCE-RLS parity baseline (the door is one-way). SA153's
  schema work is written as `0002+` migrations from the start. `test_module_migration_topology.py` changes from exactly
  one `0001_initial` to a `0001_initial` followed by an ordered chain, and its `0002` canary is
  inverted.

  The freeze extends to disaster recovery (arch audit `clean-break-schema-no-data-path`,
  recommendation): a backup taken at vintage N restores and migrates forward under N+1 instead of
  being refused by `dr_engine/recovery.py`'s exact-vintage match, a bare file that records no
  vintage is still refused (closing the fail-open `recorded_module_versions is None` branch at
  `recovery.py:287–288`), a backup recording an equal label but different migration hashes is
  refused, and a restore-forward test proves it. `quickscale update` likewise refuses a project
  whose applied migration hashes differ from the embedded files under an equal version label.

  **Slices** (in order; the one-way door is isolated in (g), behind the proof in (f)):
  - [ ] (a) Promote or replace `blog`'s `_BlogMediaAssetImageField` (Tier 1).
  - [ ] (b) The migration hash manifest: its generator, the checked-in manifest, and the helper
    that hashes a module's applied migrations; no gate yet (Tier 2-fast).
  - [ ] (c) The freeze gate as one registry row (after SA275), with controls for an in-place
    edit, a deletion, a new `0002`, and a `_`-symbol import, and the topology test's chain and
    inverted canary (Tier 2-fast).
  - [ ] (d) Restore-forward in `dr_engine/recovery.py` keyed on the hash manifest: forward
    migration from N to N+1, the bare-file refusal, and the equal-label hash-mismatch refusal,
    with tests (Tier 2-fast; Track 2 reviews).
  - [ ] (e) `quickscale update` compares applied migration hashes and refuses an equal-label
    mismatch, with tests (Tier 2-fast; Track 2 reviews).
  - [ ] (f) The restored-`bap-web` proof: `migrate` from the frozen `0001` reproduces the
    FORCE-RLS parity baseline, and no schema change shipped between SA191's rebuild and the freeze
    (Tier 2-full; environment-sensitive, read-mostly).
  - [ ] (g) The decision record lifting rule 1 and the freeze commit of the manifest, after (f)
    passes and with the maintainer's sign-off (Tier 2-fast; the one-way step, kept to docs and
    the manifest).

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port.**

  `bap-web-new` (at `/home/victor/code/bap-web-new`) is the ported recipient; the agent slices
  (a–e) are done and `scripts/cutover.sh` with `CUTOVER.md` rebuild, verify, and roll back,
  rehearsed on scratch. The cutover rebuilds a fresh database and reseeds the catalog under the
  restricted runtime role; billing stays disabled.

  **Remaining:** after 0.89.0 is published (its release requirements are SA269 and SA271), repin
  `bap-web-new` to it and re-run the rehearsal
  (agent); then the maintainer runs the Railway cutover, carries media, re-invites users, and
  archives the old repository. The pre-cutover database is retained until the reseeded site is
  verified. The production dump at `/home/victor/code/bap-web-prod.dump` holds real user data and
  stays out of every repository.


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


### Track 2 — gate derivation, upgrade path, and Track 2 hardening

- [ ] **SA275 — Derive gate wiring from the registry instead of holding copies equal.**

  Closes the gate part of arch `rules-held-by-parity-not-derivation` (Finding 3, option 1). The
  recommendation folded it into SA267 (a), which landed as a file split instead.

  **Context:** SA259 generated `gates.mk`, the workflow regions, and the docs table, but
  `sync_ci_gate_jobs.py` re-holds the registry by hand: `HOSTED_GATE_ORDER` (`:89–107`),
  `PUBLISH_GATE_ORDER` (`:273–290`), `HOSTED_JOB_CATALOG`, `PUBLISH_STEP_CATALOG`, and the help-text
  map, and it refuses to run unless they equal the registry. `check_ci_locally.sh` keeps a
  hand-written `case` arm per gate, and the `Makefile` help line names gates. A new gate costs
  about eight hand stations; SA204 (c) adds the next one.

  **Acceptance:** gate order and the hosted, publish, and help metadata are fields of
  `gate_registry.json`; the order tuples and catalogs are deleted, and the generator raises no
  copy-equality error. `check_ci_locally.sh`'s gate arms and the Makefile gate help are generated
  by the same sync (or read the registry at run time), and the existing "generated files are
  current" check covers them. A fixture gate added to the registry alone appears in every
  generated station: one hand station per gate. Emitted output is byte-identical for today's
  gates.

  **Slices:**
  - [ ] (a) Registry fields for order and hosted/publish/help metadata; delete the order tuples,
    catalogs, and equality refusals (Tier 2-fast).
  - [ ] (b) Generate `check_ci_locally.sh`'s gate arms and the Makefile gate help, with the
    one-station fixture test (Tier 2-fast).

- [ ] **SA278 — Retire the gate-script frozen surfaces and scan `scripts/` for quality.**

  Closes the SA267 part of arch `rules-held-by-parity-not-derivation` (Finding 3,
  recommendation: frozen name lists are deleted when a family's split closes; governance code
  meets the product bar).

  **Context:** SA267's slices split the gate scripts into facades plus private siblings and added
  a parity test per family whose `FROZEN_SURFACE` pins every module-level name the pre-split module
  published, private helpers included. SA267 has closed, so the lists now only tax refactors.
  `check_quality.sh` scans package `src/` only.

  **Acceptance:** every SA267 family's `FROZEN_SURFACE` name list is deleted; its exact-findings
  corpus stays as a behavioral test where one exists. `check_quality.sh` scans `scripts/` under
  the same thresholds, and the tree passes. A test fails when a `test_*_parity.py` holding a
  `FROZEN_SURFACE` exists under `scripts/` (SA279 extends it to the harness).

  **Slices:**
  - [ ] (a) Delete the gate-script frozen surfaces, keeping behavioral corpora, and add the
    no-frozen-surface test (Tier 2-fast).
  - [ ] (b) `check_quality.sh` scans `scripts/` (Tier 1).

- [ ] **SA273 — Harden the editor upload and the CLI's `pyproject.toml` write.**

  Closes tech `markdownx-upload-client-extension-and-content-type` and
  `pyproject-write-not-atomic` (S4, opportunistic batch).

  **Context:** the staff-only Markdownx upload (`storage/markdownx_urls.py:19–24`, vendor
  `markdownx/forms.py:52–57`) keeps the client's extension and content type, and GIF and SVG skip
  Pillow, so a staff account can store an HTML or SVG document in public media on the site's
  origin. `_write_validated_toml` (`quickscale_cli/utils/_dependency_write.py:65–74`) truncates
  and rewrites `pyproject.toml` in place.

  **Acceptance:** the upload stores the format-derived extension (the SA239 builder) and a
  content type derived from the decoded image; SVG is dropped from
  `MARKDOWNX_UPLOAD_CONTENT_TYPES`; tests reject an HTML file named `.png` and an SVG. The CLI
  writes a sibling temp file and `os.replace`s it, and a test proves an interrupted write leaves
  the original intact.

  **Slices:**
  - [ ] (a) The Markdownx upload wrapper and its tests (Tier 2-fast).
  - [ ] (b) The atomic `pyproject.toml` write and its test (Tier 1).

- [ ] **SA282 — One organization-selector flag and a required contract-vintage id.**

  Closes coherence `command-flag-conventions` (regressed) and `contract-vintage-identity`, and
  the tech coherence hand-off on `project_contract.yml:188`'s stale prose.

  **Context:** two commands take an organization selector and spell it two ways:
  `quickscale_billing_reconcile_checkouts --organization` and
  `quickscale_orgs_purge_organization --organization-id <uuid>`. `contract_vintage.id` is optional
  (`manifest/loader_sections.py:222`), and its presence picks the mechanism
  (`contract_vintage.py:108–110`): billing and orgs are tracked by adoption, while backups and
  social are compared by version and cannot be marked adopted.

  **Acceptance:** decisions rule 17 says an organization selector is `--organization-id <uuid>`,
  validated as a UUID, and harness rule 17 bans `--organization`, `--org`, and slug selectors with
  a fixture control; the billing command is renamed, with a release note for operator scripts.
  Decisions say every `contract_vintage` carries an `sa<NNN>-<slug>` `id`; the loader refuses a
  missing one with a control manifest; backups and social gain ids (new keys, so no persisted
  adoption key changes), and the CLI keeps one adoption mechanism. The stale step text at
  `project_contract.yml:188` describes the SA258 runtime seam.

  **Slices:**
  - [ ] (a) The `--organization-id` rename, the rule 17 clause, and the harness ban with its
    control (Tier 1).
  - [ ] (b) The required vintage `id`: the loader refusal and control, ids for backups and social,
    one CLI mechanism, the decision text, and the stale step prose (Tier 2-fast).

- [ ] **SA280 — One source for the Stripe API version and the bundled manifests.**

  Closes the product-copy part of arch `rules-held-by-parity-not-derivation` (Finding 3,
  option 1, remaining items).

  **Context:** the Stripe API version is held equal at five stations (`billing/_settings.py:32`,
  `billing/module.yml:115`, its bundled copy, `_finalize.py:276`, and `OPERATIONS.md.j2:115–131`).
  The bundled manifests under `quickscale_core/data/manifests/` are hand-copied and held equal by
  `check-manifest-sync`, and since SA264 a generated project's startup reads retired-setting
  refusals from that copy (`contracts/resolvers.py:28–42`), so the copy-pair now matters at run
  time.

  **Acceptance:** the Stripe API version has one authored constant; the manifest, the CLI
  finalizer, and the operations template read or render it, and no test compares copies. The
  bundled manifests are produced from the module manifests at wheel build time and are not
  tracked; `check-manifest-sync` and its registry row are deleted (one registry edit after
  SA275); an installed core wheel carries manifests equal to the modules' at build, proven by a
  build-and-inspect test; startup's retired-setting refusals still fire in a generated project.

  **Slices:**
  - [ ] (a) One Stripe API version constant across its five stations (Tier 2-fast).
  - [ ] (b) Bundled manifests built at wheel build time, and the sync gate retired (Tier 2-full;
    the build step and the installed-wheel check are environment-sensitive).

- [ ] **SA277 — Keep one project-upgrade mechanism and retire the other.**

  Closes the remaining recommendation of arch `generated-file-ownership-unmodeled` (Finding 2:
  "choose between keeping `beta_migration` and the prompt-driven port; retire the one SA191 did not
  use").

  **Context:** three upgrade mechanisms are maintained: prose adoption steps,
  `quickscale_devtools/beta_migration` (12.9k lines, its smoke gate, playbook, and gap ledger),
  and the prompt-driven port SA191 used (`MIGRATION_PROMPT.md`, `CUTOVER.md`). SA191's cutover is
  the evidence for which one works.

  **Acceptance:** decisions record the kept mechanism, its revocation trigger (a second long-lived
  project or a template security fix), and the steps-per-release count to watch, which should trend
  toward zero. The retired mechanism's code, gate row, docs, and ledger are deleted, and no gate or
  doc references it.

  **Slices:**
  - [ ] (a) The decision, after SA191's cutover (Tier 1).
  - [ ] (b) Delete the retired mechanism and its gate row and docs (Tier 2-fast).

### Track 3 — Track 3 hardening, theme seam types, and harness by construction

- [ ] **SA272 — Harden the notifications webhook and the orgs invite throttle.**

  Closes tech `notifications-webhook-status-regresses-out-of-order`,
  `notifications-webhook-secret-format-unchecked-at-startup`, and
  `orgs-invite-throttle-partial-charge` (S4).

  **Context:** `_apply_delivery_event` (`notifications/_webhooks.py`) overwrote the status
  with no ordering check and no row lock, so a late `email.sent` regressed a `delivered` or
  `bounced` row; slice (a) delivers the ranking and the row lock.
  `notifications/checks.py:62–71` (E003) refuses only an empty secret, so a malformed
  `whsec_` value passes startup and every webhook is then refused. In `orgs/views.py:184` and
  `OrgApiInviteView.post`, a per-org refusal after a passing per-sender check still costs the
  sender a token.

  **Acceptance:** delivery statuses are ranked and updated only forward under
  `select_for_update`, with an out-of-order test. E003 also refuses a value without the `whsec_`
  prefix or whose remainder is not valid base64, with tests. Both invite throttles are checked
  before either is charged, in the HTML and JSON views, with a test that a per-org refusal leaves
  the sender's bucket unchanged.

  **Slices:**
  - [x] (a) Forward-only delivery status under a row lock (Tier 2-fast). The
    reconciliation ranks the delivery statuses and applies an event only when it
    outranks the recorded one, re-reading the delivery under `select_for_update`;
    the out-of-order controls prove a late `email.sent` leaves delivered and
    bounced rows, their timestamps, and the parent message's derived status
    unchanged while the receipt is still recorded.
  - [ ] (b) The `whsec_` format check in E003 (Tier 1).
  - [ ] (c) Check-then-charge for both invite throttles (Tier 1).

- [ ] **SA276 — Generate the theme's seam types from the manifest set.**

  Closes the theme half of arch `generated-file-ownership-unmodeled` (Finding 2, option 2) and
  the arch coherence hand-off on `useModules.ts`.

  **Context:** SA258 and SA261 moved the Django side of the seam into the runtime, but
  `useModules.ts:1–27` still types 11 module names (`QuickScaleModules`), per-module path maps
  (`QuickScaleModulePaths`, `QuickScaleModuleApiPaths`), and a crm path parse in
  `inferCurrentOrgSlug`, in a user-owned file. Only `settings/modules.py` and `urls_modules.py` are
  managed (`project_state_hashes.py:34–37`), so every theme contract change becomes a hand-applied
  adoption step.

  **Acceptance:** generation and `update` emit a managed `quickscaleSeam.d.ts` from the manifest
  set, covered by the managed hash guard; `useModules.ts` and the other hooks import its types and
  name no module; `inferCurrentOrgSlug` reads the seam instead of parsing a crm path. The
  closed-world emission test extends to the theme: no user-owned emitted TS file names a module
  except the generated declaration. One `project_contract.yml` step covers the adoption. Land it
  before 0.89.0 is tagged if it fits (see **Order**).

  **Slices:**
  - [ ] (a) The generated, managed `quickscaleSeam.d.ts` and its hash-guard entry (Tier 2-fast).
  - [ ] (b) Hooks consume it, the theme emission test, and the adoption step (Tier 2-fast).

- [ ] **SA274 — Show real counts on the theme's CRM stat cards.**

  Closes tech `crm-theme-stats-always-zero` (S4) and its theme-to-API contract tooling gap.

  **Context:** `CrmPage.tsx:28–31` reads `.count`, then `.results.length`, but the CRM lists return
  a bare array (`runtime/drf.py:75–77`, `PlainListPagination`), so every card shows 0; even
  `.length` would count one page.

  **Acceptance:** the CRM API exposes totals (a count endpoint or a count header, chosen under
  rule 9's list shape and recorded in the CRM README), the theme reads them, and a test checks the
  theme's expected response shape against a rendered DRF response. One `project_contract.yml` step
  covers the theme change.

  **Tier:** 2-full (the count mechanism is the open decision; module API plus theme).

- [ ] **SA283 — Manifest-read startup checks, one capability collector, one `--cov` form.**

  Closes coherence `startup-checks-and-errors` (narrowed), `capability-collection` (narrowed), and
  `dependency-spec-sources`, with gaps 6 and the rule-6 literal scan from coherence §7.

  **Context:** the `checks.py` of analytics, billing, and notifications hand-list setting and
  secret names their manifests already project, so a rename is made twice. The orgs purge command
  walks `getattr(app_config, "invalidate_organization_cache", None)`
  (`quickscale_orgs_purge_organization.py:533`) outside `collect_capabilities`. auth and blog run
  `--cov=src/<pkg>` while the other ten run `--cov=<pkg>`.

  **Acceptance:** each slice merges its coherence §6 rule into decisions with a harness clause and
  a control. Startup checks read required names from the manifest projection, and harness rule 6
  flags a `<MODULE>_*` literal in `checks.py` (control: a fixture re-listing a setting). The
  invalidation hook is a listed `CAPABILITIES` name collected by `collect_capabilities`, and the
  harness bans `getattr(app_config, ...)` outside core (control: orgs' former walk). auth and blog
  use `--cov=<import package>`, and the harness compares each pyproject's `--cov` with the package
  name (control: a path form).

  **Slices:**
  - [ ] (a) Manifest-read startup checks in analytics, billing, and notifications, after SA272 (b)
    lands in the same `checks.py` (Tier 2-fast).
  - [ ] (b) The purge command's hook through `collect_capabilities` (Tier 1).
  - [ ] (c) The `--cov` form in auth and blog with its harness check (Tier 1).

- [ ] **SA279 — Retire the conformance harness's frozen surfaces.**

  Closes the SA268 part of arch `rules-held-by-parity-not-derivation` (Finding 3,
  recommendation).

  **Context:** SA268 split `rules_routes.py`, `rules_identity.py`, `rules_webhooks.py`, and
  `core.py` into facades plus siblings, each with a parity test whose `FROZEN_SURFACE` pins every
  published name. SA268 has closed.

  **Acceptance:** the harness families' `FROZEN_SURFACE` lists are deleted, keeping any
  exact-findings corpus as a behavioral test; SA278's no-frozen-surface test extends to the
  harness, so no `test_*_parity.py` with a frozen surface survives anywhere; all 43 covered rules
  still pass with their controls.

  **Tier:** 2-fast.

- [ ] **SA281 — Hand adapter hooks typed resolved options and delete the dataflow detector.**

  Closes the construction part of arch `rules-held-by-parity-not-derivation` (Finding 3,
  option 2, applied to SA263's hook signature).

  **Context:** SA263 made the engine validate, coerce, and default options, but hooks still
  receive a mutable settings dict holding the raw values, so "a hook never re-coerces or re-reads a
  raw option" is policed by a bounded inter-procedural dataflow analyzer (`adapter_flow.py` 697
  lines, `adapter_options.py` 353, `url_options.py` 99, and about 1.4k lines of controls).

  **Acceptance:** every adapter hook receives a frozen, typed resolved-options object and no raw
  option values; the 12 adapters are migrated; a hook that tries to read a raw option fails by
  construction (a type or attribute error under test). The dataflow detector, its controls, and
  their harness wiring are deleted, and the rule text says the boundary is structural. Generated
  settings are byte-identical for every module's fixture options.

  **Slices:**
  - [ ] (a) The resolved-options object in core's hook contract and the 12 adapters, with the
    byte-identical settings test (Tier 2-full; the object's shape and the hook signature are
    settled in planning, consumers enumerated).
  - [ ] (b) Delete the dataflow detector and its controls, and amend the rule (Tier 2-fast).

### Closed

- [x] **SA267 — Bring the gate scripts under the quality thresholds.**

- [x] **SA268 — Bring the conformance harness under the quality thresholds.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
