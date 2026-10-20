# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[module_conventions.md](module_conventions.md#module-conventions). `bap-web` is then ported
once, onto the standardized names: the regenerated `bap-web-new` reaches visual parity (SA300)
and is cut over (SA191). It then carries the first property portal in a
project-owned extension (SA153). Capabilities are generalized only after that project proves
their value.

**Release status.** 0.89.0 fixes 0.88.0's S1 billing defects; a live 0.88.0 install moves to
0.89.0 on a fresh database. The local `0.89.0` tag is validated; SA191's cutover is the proof
before the operator's Phases 5–6 sealing and PyPI publication
([publish_procedure.md](publish_procedure.md)).

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
| SA300 | Extract the `bap-web` design system and reach visual parity with buenosairesproperties.com | 1 | — | Required |
| SA191 | Validate and cut over the regenerated `bap-web-new` | 1 | SA300 | Required |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 2 | SA191 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA300 (b, c) ──► SA191 (a, b) ──► SA153 (r, f) ──► SA154 (inventory)
Track 2: SA277 (a3) ──► SA277 (a2, after SA191)
Track 3: SA303 (done)
     release path:  SA300 ──► SA191 ──► operator publish 0.89.0
     critical path: SA300 ──► SA191 ──► SA153 (f)
```

Arrows within a track are queue order; the table holds the dependency edges. SA277 (a3) runs
now; (a2) waits on SA191's cutover evidence.

**Slices.** Each slice is one implementer session with a fresh context, scoped to its text and
named surfaces, and ends with a short handoff note committed with the work. A ticket closes when
its last slice lands; slices are not scheduled.

**Order.** Module migration history is frozen, so a module schema change ships as a new
migration. SA153's own tables live in the project-owned extension as `0002+` migrations.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA300 (b, browser harness) | yes | yes | yes | yes | yes |
| 2 | SA277 (a3) | yes | no | yes | no | no |
| 3 | — | no | yes | yes | yes | no |

### Ownership and merge coordination

- Track 1 owns the generated `urls.py.j2` and the theme's social seam pages, the parity oracles,
  the hosted workflow triggers (including `e2e.yml`'s tag pattern), the `bap-web-new` cutover,
  the property extension, public templates, and the portal's
  extension documentation, the `bap-web-new` salvage, the design-system
  extraction and the visual-parity harness, the managed CI-environment and operations-guide
  includes, and, for the conventions, module identities, models and their `0001_initial`,
  module READMEs, and module templates, static files, and template tags, with the module page templates and the generated
  `base.html`, cross-module imports and settings reads, and the `services.py` public surface.
- Track 2 owns the gate registry and everything generated from it (`scripts/gate_registry.json`,
  `check_quality.sh`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`, `check_ci_locally.sh`'s
  gate arms, the Makefile gate help, the gate documentation table), `.github/workflows/`,
  `scripts/publish_module.py`, the `[build-system]` blocks of every package, the core build
  target, the bundled-manifest build step and the publish-artifact check, `ruff.toml`, the
  test-settings base, stubs and conftest plugin, `scripts/security_suppressions.json`, the
  gate-script parity families, the CLI apply/deploy/update commands, `utils/_dependency_write.py`,
  and `contract_vintage.py`, the module manifests' `contract_vintage` blocks, `throttle_scopes`
  and `project_contract.yml`, `contracts/module_options.py` and the `.env.example` template,
  `quickscale_core/dr_engine/`, and the billing module (`billing/services.py`,
  `billing/views.py`, `billing/adapter.py`, `_customers.py`, `_stripe_client.py`, its commands,
  and its docs), the split facades of the CLI commands, `dr_engine`, and billing with the tests
  that patch them, the blog and storage upload-path builders and the storage Markdownx upload,
  and, for the conventions, the manifest option schema and the CLI's `module_config`, module
  settings names, `is_enabled()`, and the per-module personal-data declarations with the orgs
  personal-data check, and the maintainer migration tools (`beta_migration/`) with their smoke
  gate, playbook, gap ledger, and the `showcase_react` design layer.
- Track 3 owns the orgs tenancy, purge, removal-obligation, invite-throttle, and boot path
  (`orgs/apps.py`, `orgs/removal.py`, `orgs/views.py`), the privileged-command and runtime-role
  stations, `is_platform_operator` and `operator_access`, the `quickscale_core.runtime`
  settings facade and its scheduled-off refusal helper, the generated settings templates
  (`base.py.j2`, `production.py.j2`, `local.py.j2`) with the generated `REST_FRAMEWORK`
  defaults, the generator's Jinja environment, `auth/views.py`, the blog rate limiter, the
  generated `pyproject.toml.j2` `[build-system]` block, orgs' `quickscale_orgs_create_site_org`
  command, the notifications webhook (`_webhooks.py`), the CRM list API and the theme's CRM
  page, the CLI help, the generated
  theme seam types and the theme hooks that read them, and the frontend decisions in
  `frontend.md`, and, for the conventions, the `quickscale_core.runtime` helpers, module `checks.py` and `exceptions.py`, core's `CAPABILITIES`, the adapter hook signature,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, the conformance harness with its registry row, parity families and
  `module-extension.md`'s authoring checklist, the five `_anonymization.py` handlers with
  core's redaction helpers, and the migration-history freeze gate, its hash manifest, and
  `decisions.md` § Clean-Break Migration History.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), the three audits,
  `project_contract.yml`, and [decisions.md](decisions.md). Each track resolves the shared set at
  its own merge, after the previous merge lands, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Track 1 — parity, cutover, and the property portal

- [ ] **SA300 — Extract the `bap-web` design system and reach visual parity with buenosairesproperties.com.**

  The live buenosairesproperties.com is the reference, read through a browser, so parity does
  not depend on the local `bap-web` checkout matching the deployed commit.

  **Page list.** Required: the home page and every page reachable from a menu item. Any other
  page is listed in (b)'s handoff and the operator decides whether it joins the required set.

  **Parity bar.** A required page has no differences when, at desktop (1280×720) and mobile
  (390×844) viewports, against the live page:
  - the screenshot pixel diff is at most 1% of the page area, with an anti-aliasing tolerance
    (`pixelmatch` threshold 0.1) and with data-driven regions masked (listing photos, prices,
    counts, and dates, since the catalog is reseeded);
  - the visible static text, the menu items and their targets, and the fields of every form
    are identical;
  - computed fonts, colors, and spacing of the header, footer, menu, buttons, and form controls
    match;
  - the page shows no console errors and no broken links or images the live page lacks.
  A difference the operator accepts as an improvement is recorded as such, not as a failure.

  **Slices:**
  - [x] (a) Design system: `bap-web-new`'s `frontend/design/` is the single token source.
  - [ ] (b) Browser harness: fix the stale `e2e/home.spec.ts.j2`, crawl the live menu to fix the
    required page list, and add the page-by-page comparison above of the local `bap-web-new`
    deployment against the live site. The local side runs `quickscale up` in `bap-web-new`
    (its `start.sh` migrates and seeds the forms presets), then
    `quickscale manage properties_seed_catalog` to load the catalog; the harness documents both
    steps and runs against that stack (Tier 2-full).
  - [ ] (c) Iterate until every required page meets the parity bar. Spotted improvements are
    recorded as a separate list and do not block parity (Tier 2-fast).

- [ ] **SA191 — Validate and cut over the regenerated `bap-web-new`.**

  Targets the regenerated project with SA300's parity in place. A fresh stack's first `migrate` prints no `quickscale_orgs.W004`/`W007` for schema its own
  migrations are about to install, and `manage check` after migrations reports none.
  `scripts/cutover.sh` and `CUTOVER.md` are re-ported from the salvage; they rebuild a
  fresh database, reseed the catalog under the restricted runtime role (billing disabled),
  verify, and roll back, and are rehearsed on scratch again. The modules the donor did not run
  (`orgs`, `storage`, `analytics`, `notifications`) are added, and their
  production settings (analytics key, email provider and sender, storage backend, the site
  organization) are configured and verified here.

  The deployed build installs the local 0.89.0 candidate (source commit, install method, and
  module refs recorded) without the developer's filesystem or unpublished PyPI packages. A
  QuickScale defect found follows the release re-entry loop. Production data is backed up outside
  every repository; the pre-cutover database is retained until the reseeded site is verified.

  **Slices:**
  - [ ] (a) Rehearse and verify in `bap-web-new` on scratch, then stage the production run:
    exact commands, media manifest, invite list, rollback (Tier 2-full).
  - [ ] (b) Production cutover on Railway, media carry, user re-invites, old repository archived;
    each step explicitly operator-authorized. Tier 3: plan review required — one irreversible
    production data replacement.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API under the [extension contract](module-extension.md), building on the React pages
  and `/api/properties/` the port carried over. No public API in `listings`, no generic property
  behavior in generated projects. Module-coupled data on new pages comes through seam-declared
  hooks in managed files (arch `generated-file-ownership-unmodeled`, Next (b)).

  **Acceptance:** the served documents (per-request head and crawler summary), the sitemap and
  robots views, and the search → detail → inquiry journey with organization isolation pass on the
  deployed site, and the SA208 and SA246 declarations pass in `manage.py check`.

  **Slices:**
  - [ ] (r) Re-apply the landed (a)–(e4) work from `~/code/bap-web-new-salvage/` onto the
    regenerated project and re-prove its tests there (Tier 2-full).
  - [ ] (f) Go-live on `buenosairesproperties.com` after SA191's cutover; re-prove the journey on
    the deployed site (Tier 2-full; production deploy, maintainer action).

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or crawler fill into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with
  a concrete consumer, bounded acceptance, and a fresh dependency and track. Tenant tables build
  on marker-derived enrollment and purge; schema changes ship incremental migrations on the
  frozen history. Close when every item is promoted or dropped with rationale.

### Track 2 — upgrade path

- [ ] **SA277 — Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt.**

  Closes arch `generated-file-ownership-unmodeled` Next (a). One path in two stages:
  `beta_migration` does what it can mechanically; the prompt-driven port (`MIGRATION_PROMPT.md`,
  `CUTOVER.md`) handles what it reports it could not.

  **Acceptance:** decisions record the two-stage path (the gap ledger is the prompt's input, so
  neither stage repeats the other), the boundary rule (a gap that recurs across releases moves
  into code; a one-off stays in the prompt), the revocation trigger (a second long-lived project
  or a template security fix), and the steps-per-release count to watch, trending toward zero
  (50 declared steps on 2026-10-16). Operator docs do not duplicate steps either stage covers.
  `bap-web` is an old project; the path must also serve "not so old" ones: a declared supported
  source-version range, `beta_migration` proven against projects generated at each version in
  it, and the AI-assistant prompt kept and versioned in the QuickScale repository rather than only
  in a recipient. Supporting further projects meets the "second long-lived project" revocation
  trigger, and decisions say so.

  **Slices:**
  - [x] (a1) The handoff names every recorded gap; draft decision record in
    `docs/planning/migration-upgrade-path-draft.md`.
  - [ ] (a2) After SA191's cutover: the decision record and boundary rule in decisions, the
    (a1) draft confirmed or amended against the cutover evidence, and the operator docs pruned of
    steps either stage covers (Tier 2-fast).
  - [ ] (a3) The supported source-version range, test projects generated at each version in it
    with `beta_migration` smoke runs against them, and the prompt moved into the QuickScale
    repository as a versioned artifact (Tier 2-full).

### Track 3 — CLI help

- [x] **SA303 — Make `quickscale` help show every command, subcommand, and option it reaches.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

**Unscheduled — React-theme browser coverage.** No test drives `showcase_react` in a real
browser against a real backend beyond SA300 (b)'s screenshot harness. Remaining order when scheduled: (1) add `pnpm test:e2e` to `ci.yml.j2`;
(2) the named user journeys; (3) a depth-capped link crawler in `test_e2e_full_workflow.py`;
(4) full journey E2E against the Docker stack, only if it fits the E2E time budget in
validation_policy.md.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
