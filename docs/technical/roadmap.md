# QuickScale Development Roadmap

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
with an isolated Poetry cache (evidence in the [technical audit](../others/tech-audit.md#watchlist-latent-act-only-when-the-trigger-fires)).
SA284, 0.89.0's one release requirement, has landed: the release build content-checks the wheel
it uploads for the bundled manifests (arch `rules-held-by-parity-not-derivation`).
Upgrading a live 0.88.0 install is not supported (maintainer decision, 2026-10-16): 0.88.0 and earlier move to 0.89.0 on a fresh database, the 0.89.0 release
notes say so, and `initial-migration-edited-in-place` stays a watch item. Publication remains a
maintainer action.

Audit tickets name the [arch](../others/arch-audit.md), [tech](../others/tech-audit.md), or
[coherence](../others/coherence-audit.md) IDs they close; the audits keep the evidence. Coherence
tickets merge the matching coherence proposal into decisions with a harness detector, or record a
review-only clause without one.

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
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | 1 | — | Optional |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | 1 | — | Optional |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA277 | Define the upgrade path as `beta_migration` code plus a prompt for the remainder | 2 | SA191 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191 (repin on v89) ──► SA153 (a…e) ──► SA204 (j) ──► SA153 (f, go-live) ──► SA154 (inventory)
Track 2: SA277
Track 3: — (SA296 landed)
     release path:  publish 0.89.0 ──► SA191 cutover ──► SA153 (f)
     critical path: SA191 repin ──► SA153 (a…e) ──► SA204 (j) ──► SA153 (f)
```

Arrows within a track are queue order; the table holds the dependency edges. Cross-track edges:
SA191's cutover (not its repin) waits on the 0.89.0 publication, and SA153 (f) waits on the cutover; SA296 waited on SA292, which has landed (both rewrite harness rule 17);
SA277 waits on SA191's cutover, whose evidence draws the line between what `beta_migration`
automates and what the prompt handles. Inside Track 1, SA204 (j) and SA153 (f) are interleaved
slices of two tickets: the freeze lands after SA153's build slices and before its go-live.

**Parallel start.** Each track takes one at a time,
in queue order. SA286 landed ahead
of SA191 in Track 1's queue because every adoption step it removed before the repin is applied
once, offline, instead of on a live site.

**Slices.** Large tickets list `Slices:` in their body. Each slice is one implementer session
with a fresh context, scoped to that slice's text and named surfaces, and ends with a short
handoff note (what landed, what is next, what to watch) committed with the work. A ticket closes
when its last slice lands; slices are not scheduled.

**Order.** Every change to a shipped module `0001_initial` lands before SA204 freezes
migration history. The freeze (SA204 (j)) waits until SA153's go-live (maintainer decision,
2026-10-16), keeping `0001` editable while the portal is built, and lands before SA153 (f) puts
non-reseedable tenant data on `bap-web`. SA153's own tables live in the project-owned extension,
whose migrations are `0002+` from the start either way. Any module `0001` edit made before the
freeze is applied to `bap-web` by hand or by a reseed. No open ticket changes a module schema.
SA154 is an inventory, not work. SA191's repin pins the unpublished `v89` tree and does not wait for 0.89.0; its cutover does, and SA204's remaining slice (j) waits for SA153 (e). SA276 has
landed, so `bap-web-new` adopts its steps once at the repin instead of on a live site;
it is not a release requirement.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191 | yes | no | yes | no | yes |
| 2 | SA277 | no | no | yes | no | no |
| 3 | — (SA296 landed) | yes | yes | yes | yes | no |

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
- **New surfaces.** Track 1 also owns the managed CI-environment and operations-guide includes
  (SA286). Track 2 also owns the core build target and the publish-artifact check (SA284,
  SA285), `scripts/security_suppressions.json` (SA295), the manifest `throttle_scopes`
  projection (SA291), and the shared test-settings base and conftest plugin (SA293). Track 3
  also owns the generated `REST_FRAMEWORK` renderer and parser defaults (SA288), the core
  scheduled-off refusal helper (SA292), `is_platform_operator` and the gated `operator_access`
  (SA290, SA297), and `module-extension.md`'s authoring checklist (SA296).
- **Cross-track edits.** SA204 (c) adds its gate row to the Track 2 registry; SA204 (d), (e),
  and (g) edit Track 2's `dr_engine/recovery.py` and `update` command, with Track 2 review. SA282 (a)
  adds a harness clause and control to Track 3's harness; SA283 (a) edits Track 2's
  `billing/checks.py`; SA281 edits Track 2's option contract. Every coherence ticket adds its
  detector and control to Track 3's harness, or records a review-only clause without one (SA294).
  SA288 (b) drops pins in Track 2's billing views;
  SA291 edits Track 3's `compose_rest_framework` and three module `checks.py`; SA292 (b) and
  SA293 (c) edit Track 1's module READMEs and module tooling sections. All land through the
  serialized merge queue.
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

  The gate compares against a checked-in manifest of the frozen files' content hashes, append-only
  against the manifest the latest release tag carries (from SA204 (h): a shallow CI clone has the
  gate fetch that one tag; a tag predating the manifest passes with a notice). The same manifest
  is the content identity that restore and `quickscale update` compare: per module, the hashes of
  the applied migration files, recorded with every backup. Before merging, confirm no module
  schema change shipped
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
  whose applied migration hashes differ from the embedded files — under an equal version label,
  and on every pull from the freeze vintage on.

  **Slices** (in order; the one-way door is isolated in (j), behind the proofs in (f) and (i)):
  - [x] (a), (b), (d): landed (`BlogMediaAssetImageField` public; `quickscale_core.migration_hashes`
    with `scripts/migration_hashes.json`; hash-keyed restore-forward in `recovery.py`).
  - [x] (c): landed as `scripts/check_migration_freeze.py`, one registry row (`check-migration-freeze`)
    with controls for an in-place edit, a deletion, a new `0002`, and a `_`-symbol reference; the
    topology guard accepts an ordered chain and its `0002` canary is inverted. (j) is next.
  - [x] (d) Restore-forward in `dr_engine/recovery.py` keyed on the hash manifest: forward
    migration from N to N+1, the bare-file refusal, and the equal-label hash-mismatch refusal,
    with tests (Tier 2-fast; Track 2 reviews). Landed as per-module `migration_hashes` recorded
    in every backup's metadata and content-identity checks in recovery.py: a restore proceeds
    when the recorded migration files are still installed byte-identical (newer installed
    migrations apply forward), and refuses a changed, missing, or unrecorded identity. (c) is
    unblocked now that SA275 has landed.
  - [x] (e) `quickscale update` refuses a same-label rewrite of an applied migration file and
    restores the pre-update content; an added migration file still applies forward, and a
    version-label change keeps the upgrade path.
  - [x] (f): landed as a rehearsal on a bap-web copy carrying the frozen content, migrated into a
    fresh database (`bap_freeze_proof`) on the retained scratch PostgreSQL: `migrate` exit 0
    (`--skip-checks`: the copy's Oct-9 project admin predates SA266's listings field rename); the
    FORCE-RLS surface 6 tables / 12 policies (5 / 10 module-only, the delta being
    `properties_propertylisting`'s canonical pair); tenant isolation 6/6, no `W004`/`W007`, only the
    two known `W006` properties warnings — matching the SA191 baseline; no carried module's
    migration changed since the rebuild (SA270's billing and SA204(a)'s blog are not carried).
    (j) is next.
  The 2026-10-16 arch pass found two branches that still key on labels or authorship (arch `clean-break-schema-no-data-path`): `quickscale update` compares content only under an equal
  label (`_module_update.py:286–297`, `:365`), so the cross-release update the freeze exists to
  make safe is the one path left unverified; and `sync_migration_hashes.py --write` re-freezes an
  edited `0001` in the same commit that edits it, so the gate catches drift, not intent. Both
  close before the one-way step, which then verifies them instead of only recording the manifest.

  - [x] (g): landed as `quickscale_core.migration_hashes.MIGRATION_FREEZE_VINTAGE` (still unset;
    SA204 (j) sets it to the release the freeze lands in) and its `is_frozen_vintage` predicate,
    which the update guard keys every pull on: an applied migration file stays byte-identical, an
    equal version label compares as before, new files apply forward, an unidentifiable applied
    identity refuses a frozen pull instead of silently authorizing it, and a vintage before the
    freeze keeps the fresh-database path. Tests: a label change plus a changed applied file is
    refused and rolled back — through a real subtree pull too — a removal is refused, an added
    `0002` applies forward, and the pre-freeze label-change path is unchanged. (j) is next.
  - [x] (h): landed as the freeze gate's append-only comparison against the latest release
    tag: a value that release recorded may not change or disappear, even after `--write`
    re-froze the manifest, while unreleased additions stay legal; the release being tagged is
    never its own baseline, and a shallow clone refreshes the newest eligible tag from `origin`
    on every run (an unreachable remote fails closed; a non-shallow clone stays local). A tag
    predating the manifest, or no baseline other than the checked-out release, passes with a
    notice. Controls cover the re-frozen `0001` edit, a removal, an addition, the
    highest-release-version selection, the checked-out-release exclusion, the shallow-clone
    fetch, the newer-release refresh, both notices, a malformed released manifest, and an
    uninspectable Git root. (j) is next.
  - [x] (i): landed as the (f) rehearsal re-run on a bap-web copy repinned to the frozen content,
    adding the cross-release `update` path from (g) through real local subtree pulls, with the
    freeze vintage pinned in-process at the applied `0.88.0` (SA204 (j) sets the shipped
    constant): a same-label and a cross-release pull that rewrites an applied `0001` are both
    refused and rolled back, a pre-freeze vintage keeps the fresh-database path, and a pull
    adding `0002_add_listing_display_order` is accepted and applies forward on the scratch
    PostgreSQL (exit 0); the FORCE-RLS baseline still holds (6 tables / 12 policies, tenant
    isolation 6/6, the two known `W006` warnings). (j) is next.
  - [ ] (j) The decision record lifting rule 1, the freeze commit of the manifest, and
    `MIGRATION_FREEZE_VINTAGE` set to the release this step lands in, after (g),
    (h), and (i) pass, scheduled after SA153 (e) and before SA153 (f)'s go-live, with the
    maintainer's sign-off (Tier 2-fast; the one-way step, kept to docs, the manifest, and that
    one constant). If a module `0001` changed after (i), (i) is re-run first.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port.**

  `bap-web-new` (at `/home/victor/code/bap-web-new`) is the ported recipient; the agent slices
  (a–e) are done and `scripts/cutover.sh` with `CUTOVER.md` rebuild, verify, and roll back,
  rehearsed on scratch. The cutover rebuilds a fresh database and reseeds the catalog under the
  restricted runtime role; billing stays disabled.

  **Remaining:** (1) repin (agent, no publication needed): pin `bap-web-new` to the `v89` tree
  and re-run the rehearsal; SA153 (a…e) builds on this pin, re-pinned at each `v89` merge that
  touches modules, with any module `0001` change applied by a reseed. Slice 1 landed (bap-web-new
  `cecc0fe`, 2026-10-17): the Oct-9 frozen core wheel pin is now a path pin on the checkout's
  `quickscale_core` (`develop = true`); a git rev pin was probed and refuted — an installed clone
  carries no bundled manifests and no monorepo manifest path, so every manifest read fails. The
  rehearsal re-ran green on a reset `bap_cutover_rehearsal`: exit 0 twice, catalog 3/12/48/60 and
  the six service forms in the System org scope, unscoped reads 0, tenant isolation 6/6, only the
  two known `W006` warnings (runbook port 32768). Slice 2 landed (bap-web-new `0061215`,
  2026-10-17): the split branches were refreshed from a locally tagged v89 HEAD
  (`make publish-modules`), the six modules re-embedded from them, and the 16 pending contract
  steps adopted and recorded — including the managed URLconf that restores the SPA shell and
  `storage`, which the v89 listings requires. Project suite 57/0 (coverage 93.94%), frontend 387
  tests and its coverage gate green, rehearsal exit 0 twice on a reset `bap_cutover_rehearsal`.
  (2) cutover: after 0.89.0 is published, swap the pin to `0.89.0` and
  re-run the rehearsal, so the unpublished pin never reaches production; then the maintainer runs
  the Railway cutover, carries media, re-invites users, and archives the old repository. The
  pre-cutover database is retained until the reseeded site is verified. The production dump at
  `/home/victor/code/bap-web-prod.dump` holds real user data and stays out of every repository.

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

  Module-coupled data on new pages comes through seam-declared hooks in managed files, so pages
  consume hooks rather than endpoints (arch `generated-file-ownership-unmodeled`, option 2's
  theme part, scheduled "as SA153 adds pages").

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
  - [x] (a, b): landed on `bap-web-new` as the explicit `currency` label (seeded, API `currency`
    + `currencyLabel`) and the `PropertyImage`/`PropertyFeature` children as tenant-owned tables
    (own `organization_id`, forced RLS, composite `(property_id, organization_id)` FKs)
    backfilled and RLS-proven on a `bap_cutover_rehearsal` clone, with a tenant-scoped
    `PropertyListing.objects` and API-level organization-isolation tests; `manage.py check`
    reports zero findings, `check_tenant_isolation` passes on the three property tables, and the
    suite is 68/0 at 93.94%. (c, d, e) is next; inquiry → listing lands with it under the same
    composite-FK rule.
  - [ ] (c, d, e) Frontend, one session: React catalog and detail pages in Spanish on the app's
    design; listing inquiry into a CRM record with a listing reference, and the search → detail
    → inquiry journey; prerender or server render, Open Graph tags, sitemap, and `robots.txt`,
    with the crawler test and rendered-page isolation (Tier 2-full: the prerender mechanism
    needs discovery).
  - [ ] (f) Go-live on `buenosairesproperties.com`, after SA204 (j) freezes migration history:
    the release `bap-web` goes live on carries the frozen manifest, and the search → detail →
    inquiry journey is re-proved on the deployed site (Tier 2-full; production deploy, maintainer
    action).

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

- [x] **SA286 — Render module-owned CI environment and operations text into managed includes.**

### Track 2 — gate derivation, release integrity, upgrade path, and manifest conventions

- [x] **SA275 — Derive gate wiring from the registry instead of holding copies equal.**

- [x] **SA278 — Retire the gate-script frozen surfaces and scan `scripts/` for quality.**

- [x] **SA273 — Harden the editor upload and the CLI's `pyproject.toml` write.**

- [x] **SA282 — One organization-selector flag and a required contract-vintage id.**

- [x] **SA280 — One source for the Stripe API version and the bundled manifests.**

- [ ] **SA277 — Define the upgrade path as `beta_migration` code plus a prompt for the remainder.**

  Answers the remaining recommendation of arch `generated-file-ownership-unmodeled` (Finding 1,
  option 4: "choose one upgrade mechanism"). Maintainer decision, 2026-10-16: keep both, as one
  path in two stages, rather than retire one. `beta_migration` is the code stage and does what it
  can do mechanically; the prompt-driven port handles what the code stage reports it could not.

  **Context:** three upgrade mechanisms are maintained: prose adoption steps,
  `quickscale_devtools/beta_migration` (12.9k lines, its smoke gate, playbook, and gap ledger),
  and the prompt-driven port SA191 used (`MIGRATION_PROMPT.md`, `CUTOVER.md`). SA191's cutover is
  the evidence for which one works.

  **Acceptance:** decisions record the two-stage path: `beta_migration` runs first, and its gap
  ledger is the handoff list the prompt (`MIGRATION_PROMPT.md`) takes as input, so neither stage
  repeats the other's work. They also record the boundary rule (a gap that recurs across
  releases moves into code; a one-off stays in the prompt), the revocation trigger (a second
  long-lived project or a template security fix), and the steps-per-release count to watch,
  which should trend toward zero (recorded beside this watch: 50 declared project-contract
  steps at SA286's close, 2026-10-16). Prose adoption steps that either stage now covers are not
  duplicated in the operator docs. The arch audit records option 4 as answered by this hybrid.

  **Slices:**
  - [ ] (a) The decision record and boundary rule, drawn from SA191's cutover evidence (which
    steps `beta_migration` covered and which the port did by hand), and the wired handoff:
    `beta_migration` emits its unresolved gaps in the form the prompt reads, the prompt and
    `CUTOVER.md` move into the maintained tree beside it, and a smoke test proves the handoff
    file is produced (Tier 2-full: the gap ledger's handoff format needs discovery).

- [x] **SA284 — Content-check the core wheel that `publish.yml` uploads.**

- [x] **SA285 — Derive the gate inventory in tests and build the core wheel through one target.**

- [x] **SA295 — Review the security suppressions and stagger their expiry.**

- [x] **SA293 — One test-settings base, one pyproject template, no ticket ids in tests or manifests.**

- [x] **SA291 — The manifest owns option validation and throttle rates.**

- [x] **SA287 — The CLI reaches module behaviour through manifest fields and hooks.**

### Track 3 — Track 3 hardening, API and theme conventions, and harness by construction

- [x] **SA276 — Generate the theme's seam types from the manifest set.**

- [x] **SA274 — Show real counts on the theme's CRM stat cards.**

- [x] **SA283 — Manifest-read startup checks, one capability collector, one `--cov` form.**

- [x] **SA279 — Retire the conformance harness's frozen surfaces.**

- [x] **SA281 — Hand adapter hooks typed resolved options and delete the dataflow detector.**

- [x] **SA288 — JSON-only module APIs through the generated `REST_FRAMEWORK` defaults.**

- [x] **SA289 — Theme requests go through `apiRequest` and parse one error shape.**

- [x] **SA290 — One named platform-operator check.**

- [x] **SA297 — `operator_access` checks the platform operator itself.**

- [x] **SA292 — One command off-refusal helper, service-owned transactions, complete README flags.**

- [x] **SA294 — Record the structured-log-field convention.**

- [x] **SA296 — Close the rule-audit enforcement gaps the 2026-10-16 census found.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

**Unscheduled — React-theme browser coverage.** No test drives `showcase_react` in a real
browser against a real backend. jsdom route tests (`src/test/*.tsx`) already cover route mounting.
The repo's Playwright E2E asserts only status 200, the title and the first stylesheet. The
generated `e2e/home.spec.ts.j2` is stale and no CI runs it. Order when scheduled: (1) fix the
stub and add `pnpm test:e2e` to `ci.yml.j2`; (2) write the named user journeys; (3) a depth-capped
link crawler in `test_e2e_full_workflow.py`; (4) full journey E2E against the Docker stack, only
if it fits the E2E time budget in validation_policy.md.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
