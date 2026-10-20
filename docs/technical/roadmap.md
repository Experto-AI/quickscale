# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[module_conventions.md](module_conventions.md#module-conventions). `bap-web` is then ported
once, onto the standardized names: regenerated as `bap-web-new` (SA299), brought to visual and
functional parity (SA300, SA301), and cut over (SA191). It then carries the first property portal in a
project-owned extension (SA153). Capabilities are generalized only after that project proves
their value.

**Release status.** 0.88.0 ships S1 billing defects; the fixes ship in 0.89.0; SA191 now supplies the
local-candidate validation and cutover required before PyPI publication. A live 0.88.0 install moves to 0.89.0 on a fresh database. Part 1 is green on
the SA298 tip and the Phase 4b pre-linked live check passed there; the local `0.89.0` tag is
re-pointed at the roadmap-only close commit whose product bytes match that tip. The operator's
Phases 5–6 sealing and publication remain, in [publish_procedure.md](publish_procedure.md).
For this release, the operator's chosen order is: regenerate `bap-web-new` from the local 0.89.0
candidate (SA299), reach design parity and port custom features (SA300; SA301 landed), validate
and cut over (SA191), then publish to PyPI; publication does not block SA191.

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
| SA303 | Make `quickscale` help show every command, subcommand, and option it reaches | 2 | — | Optional |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 2 | SA191 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA299 (regenerate, landed) ──► SA300 (design parity) ──► SA191 (cutover)
         ──► SA153 (f, go-live) ──► SA154 (inventory)
Track 2: SA277 (a2, a3), SA303 (CLI help)
Track 3: — (SA302 landed)
     release path:  SA299 (landed) ──► SA300 ──► SA191 (validation + cutover) ──► operator publish 0.89.0
     critical path: SA299 (landed) ──► SA300 ──► SA191 ──► SA153 (f)
```

Arrows within a track are queue order; the table holds the dependency edges. Track 1's queue
head is SA300 (b): SA299 (a)–(f) salvaged, inventoried, deleted, regenerated `bap-web-new`
as a clean baseline, and migrated the donor into it in place; SA300 (a) has extracted and
applied its design system, and SA301 has landed the donor's custom forms and features. SA300
(b)–(c) continues on the regenerated project, and SA191 validates and cuts over after it. PyPI
publication follows successful validation and cutover. SA153 (e3–e4) have landed, so the reverted
contract step never ships. SA153 (f) waits on SA191's cutover, with
the migration freeze it also waited on landed. SA277 (a1) has landed; SA277 (a3) can
start now, and (a2) waits on the cutover, whose evidence confirms the line between what `beta_migration` automates and what the
prompt handles.

**Slices.** Each slice is one implementer session with a fresh context, scoped to its text and
named surfaces, and ends with a short handoff note committed with the work. A ticket closes when
its last slice lands; slices are not scheduled.

**Order.** SA204 (j) froze migration history before SA153 (f) puts non-reseedable tenant data on
`bap-web`, and no module `0001` edit was outstanding, so `bap-web` needs no reseed. SA153's own
tables live in the project-owned extension as `0002+` migrations. No open ticket changes a module
schema; a schema change from the freeze release on ships as a new migration. SA153 (a…e) builds on
the `v89` pin, re-pinned at each `v89` merge that touches modules.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA300 (b, browser harness) | yes | no | yes | no | yes |
| 2 | SA277 (a3) | yes | no | yes | no | no |
| 3 | — | yes | yes | yes | yes | no |

### Ownership and merge coordination

- Track 1 owns the generated `urls.py.j2` and the theme's social seam pages, the parity oracles,
  the hosted workflow triggers (including `e2e.yml`'s tag pattern), the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation, the `bap-web-new` regeneration and its salvage, the design-system
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
  page, the port of `bap-web`'s custom forms and features into `bap-web-new`, the generated
  theme seam types and the theme hooks that read them, and the frontend decisions in
  `frontend.md`, and, for the conventions, the `quickscale_core.runtime` helpers, module `checks.py` and `exceptions.py`, core's `CAPABILITIES`, the adapter hook signature,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, the conformance harness with its registry row, parity families and
  `module-extension.md`'s authoring checklist, the five `_anonymization.py` handlers with
  core's redaction helpers, and the migration-history freeze gate, its hash manifest, and
  `decisions.md` § Clean-Break Migration History.
- **Cross-track edits.** SA301 edits public templates Track 1 owns only after SA300 (a)'s
  design system lands, with Track 1 review. SA153 (e3) reverts Track 3's `publicPage` seam
  type, with Track 3 review, and lands through the serialized merge queue.
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

### Track 1 — migration history and the property portal

- [x] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

- [x] **SA292 — Fix `quickscale deploy railway` re-initializing a linked directory, and correct the manual-deploy docs.**

- [x] **SA298 — Complete 0.89.0 final release validation and live deployment proof.**

- [x] **SA299 — Regenerate `bap-web-new` from local 0.89.0 with the deployed `bap-web` module set.**

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
  - [x] (a) Extract the coding styles of the current `bap-web` (tokens, typography, spacing,
    components) into a design system in the regenerated project's theme, and apply it (Tier 2-full).
    Landed in `bap-web-new` (design system at `ffa3c738`, review fixes at `7891405`):
    `frontend/design/` is the single token source, the shell/module contract tokens are restored,
    and `frontend/src/test/designSystem.test.ts` pins it.
  - [ ] (b) Browser harness: fix the stale `e2e/home.spec.ts.j2`, crawl the live menu to fix the
    required page list, and add the page-by-page comparison above of the local `bap-web-new`
    deployment against the live site. The local side runs `quickscale up` in `bap-web-new`
    (its `start.sh` migrates and seeds the forms presets), then
    `quickscale manage properties_seed_catalog` to load the catalog; the harness documents both
    steps and runs against that stack (Tier 2-full).
  - [ ] (c) Iterate until every required page meets the parity bar. Spotted improvements are
    recorded as a separate list and do not block parity (Tier 2-fast).

- [ ] **SA191 — Validate and cut over the regenerated `bap-web-new`.**

  Targets the project SA299 regenerated, with SA300's parity and SA301's features in place.
  A fresh stack's first `migrate` prints no `quickscale_orgs.W004`/`W007` for schema its own
  migrations are about to install, and `manage check` after migrations reports none.
  `scripts/cutover.sh` and `CUTOVER.md` are re-ported from SA299 (a)'s salvage; they rebuild a
  fresh database, reseed the catalog under the restricted runtime role (billing disabled),
  verify, and roll back, and are rehearsed on scratch again. The modules the donor did not run
  (`orgs`, `storage`, `analytics`, `notifications`) are added as SA299 (b) requires, and their
  production settings (analytics key, email provider and sender, storage backend, the site
  organization) are configured and verified here.

  **Remaining (Tier 2-full):** validate and cut over using the local 0.89.0 candidate; PyPI
  publication is not a prerequisite. An assistant records the exact QuickScale source commit,
  local installation method and module refs, and ensures the deployed build can install the same
  candidate without relying on the developer's filesystem or unpublished PyPI packages. Re-run
  the rehearsal and verification in `bap-web-new`, then stage the production run (exact commands,
  media manifest, invite list, rollback). The operator must explicitly authorize the Railway
  cutover against production, the media carry, the user re-invites, and the old repository's archive.
  Retain the pre-cutover database until the reseeded site is verified. Close SA191 only after its
  validation, cutover, and remaining acceptance complete; sealing alone does not close it.
  Successful `bap-web-new` validation and cutover are the operator's proof before publishing
  0.89.0 to PyPI. Any QuickScale defect found follows the release re-entry loop; revalidate the
  final candidate before publication. Switching the recipient to published packages can follow
  publication. The production dump is absent from the documented path
  (`/home/victor/code/bap-web-prod.dump`); the operator confirmed the production data is
  backed up elsewhere and stays out of every repository.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API under the [extension contract](module-extension.md), building on the React pages
  and `/api/properties/` the port carried over. No public API in `listings`, no generic property
  behavior in generated projects. Module-coupled data on new pages comes through seam-declared
  hooks in managed files (arch `generated-file-ownership-unmodeled`, Next (b)).

  **Landed (a)–(e4)** on `bap-web-new`: explicit per-listing currency labels, the tenant-owned
  `PropertyImage`/`PropertyFeature`/`PropertyInquiry` tables (own `organization_id`, forced RLS,
  composite FKs, boundary tests), the listing inquiry filing a CRM record with the listing
  reference, and (e4)'s per-request fill: Django writes the catalog and detail documents' head
  and a plain-HTML crawler summary from the live published listings, `sitemap.xml` and
  `robots.txt` are Django views over the same data, and the build-time prerender path is gone.

  Because SA299 regenerates `bap-web-new`, the (a)–(e4) work is re-applied from SA299 (a)'s
  salvage (`~/code/bap-web-new-salvage/`) onto the regenerated project before (f), and its acceptance is re-proved there.

  **Acceptance (remaining):** the deployed site (f). The served documents, the sitemap and robots
  views, and the search → detail → inquiry journey with organization isolation pass in the
  project, and the SA208 and SA246 declarations pass in `manage.py check`.

  **Slices** (in order; (e1) and (e2) built a build-time prerender from a committed snapshot that
  (e3)–(e4) replaced with Decision 2's per-request fill):
  - [x] (e3): landed on QuickScale as the revert: the theme's `publicPage` seam carries the social
    shapes only, `main.tsx` mounts with `createRoot` (no hydration), the static-location render is
    gone, the prerender contract step is retired (replaced by `sa153e3-public-page-prerender-reverted`
    — the contract gate requires a fresh id on a template change), its CHANGELOG bullet is out, and
    frontend.md matches Decision 2.
  - [x] (e4): landed on `bap-web-new`: the catalog and detail routes' Django view fills the SPA
    document's head and a crawler summary per request from the published, organization-scoped
    listings; `sitemap.xml` and `robots.txt` are Django views over the same data; the prerender
    build step, the snapshot command, the committed artifacts, and the reverted contract step's
    project-side traces are gone; the no-JavaScript crawler test, rendered-document organization
    isolation, and the journey test pass (Tier 2-fast).
  - [ ] (f) Go-live on `buenosairesproperties.com` after SA191's cutover and the migration
    freeze; re-prove the journey on the deployed site (Tier 2-full; production deploy,
    maintainer action).

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or crawler fill into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with
  a concrete consumer, bounded acceptance, and a fresh dependency and track. Tenant tables build
  on marker-derived enrollment and purge; schema changes ship incremental migrations on SA204's
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
  - [x] (a1) The wired handoff: the completed prompt names every recorded unresolved gap in its
    remaining-work form — the pre-port surfaces and the donor's module divergences (older copies
    the current module content supersedes, and local edits to upstream or re-express), each with
    paths and a governing rule — and the smoke gate's gap-handoff case proves the handoff file
    carries them. The working prompt and `CUTOVER.md` lived in `bap-web-new` only; SA299 (a)
    preserves them in `~/code/bap-web-new-salvage/`. This slice's handoff note carries the decision-record and boundary-rule draft:
    `docs/planning/migration-upgrade-path-draft.md`. Next: (a2), after the cutover.
  - [ ] (a2) After SA191's cutover: the decision record and boundary rule in decisions, the
    (a1) draft confirmed or amended against the cutover evidence, and the operator docs pruned of
    steps either stage covers (Tier 2-fast).
  - [ ] (a3) The supported source-version range, test projects generated at each version in it
    with `beta_migration` smoke runs against them, and the prompt moved into the QuickScale
    repository as a versioned artifact (Tier 2-full).

- [ ] **SA303 — Make `quickscale` help show every command, subcommand, and option it reaches.**

  `quickscale` and `quickscale --help` list only the 15 top-level command names with a one-line
  summary, so nothing below them can be found from the top: `deploy railway`; `dr capture`,
  `execute`, `plan`, `report`; and the options of `apply`, `plan`, `up`, `down`, `logs`, `push`,
  `remove`, `shell`, `status`, `update`. The pass-through command `manage` shows a bare usage line
  and never lists the Django commands it forwards (`check`, `migrate`, the modules' own commands).

  A walk of the Click tree (2026-10-20: 15 commands, 5 subcommands, 69 parameters, none hidden)
  also found help that exists but says nothing:
  - all 24 `dr` options (`capture`, `plan`, `execute`, `report`) have no help text, and the four
    `dr` subcommands have no examples; `deploy` and `dr` show no examples either;
  - positional arguments are named but never described: `apply [CONFIG]`, `remove MODULE_NAME`
    (valid module names not listed), `logs [SERVICE]`, `manage [ARGS]`;
  - `plan`'s usage shows `PROJECT_SLUG` as required although it is optional (`plan --add`,
    `plan --reconfigure` run without it);
  - `logs --tail` takes `TEXT` instead of an integer (or `all`);
  - `apply`'s help prints reST double backquotes literally, and `remove`'s numbered list is misindented.

  **Acceptance:** `quickscale` and `quickscale --help` show the full command tree, every group's
  subcommands and every command's options (or a documented `--all`/`help <command>` that does);
  each group with no subcommand given shows its subcommands; `quickscale manage` (with or without
  `--help`) lists the project's Django management commands, grouped by app, through `manage.py
  help` in the backend container, with a clear message when the stack is down; `quickscale logs
  --help` names the valid `SERVICE` values (`backend`, `frontend`, `db`, read from the project's compose file); every option and
  argument has help text, every command and subcommand an example, usage marks optional
  arguments as optional, and `--tail` validates its value; a test walks the Click command
  tree so a new command, option, or argument cannot be missing from the help or lack help text
  (Tier 2-fast).

### Track 3 — custom features and tenancy

- [x] **SA301 — Inventory and port `bap-web`'s custom forms and features.**

- [x] **SA302 — Keep the orgs tenancy checks quiet on tables whose migrations are not applied yet.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

**Unscheduled — React-theme browser coverage.** No test drives `showcase_react` in a real
browser against a real backend. The repo's Playwright E2E asserts only status 200, the title and
the first stylesheet. SA300 (b) fixes the stale `e2e/home.spec.ts.j2` stub and adds the
screenshot harness. Remaining order when scheduled: (1) add `pnpm test:e2e` to `ci.yml.j2`;
(2) the named user journeys; (3) a depth-capped link crawler in `test_e2e_full_workflow.py`;
(4) full journey E2E against the Docker stack, only if it fits the E2E time budget in
validation_policy.md.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
