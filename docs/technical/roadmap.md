# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[module_conventions.md](module_conventions.md#module-conventions). `bap-web` is then ported
once, onto the standardized names: the regenerated `bap-web`, already at visual parity, is
cut over (SA191d) and then carries the first property portal in a project-owned extension
(SA153). Capabilities are generalized only after that project proves
their value.

**Release status.** 0.89.0 fixes 0.88.0's S1 billing defects; a live 0.88.0 install moves to
0.89.0 on a fresh database. The local `0.89.0` tag is validated; SA191d's cutover is the proof
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
| SA191d | Cut over production to the regenerated `bap-web` in place (delegated, operator-gated) | 1 | — | Required |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191d | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA306 | Make the generated `ci.yml` start on GitHub and pass on `bap-web` | 1 | — | Required |
| SA307 | Make System-org public content reachable for logged-in staff in forms and the admin | 1 | — | Required |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 3 | SA191d | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191d (build ──► swap ──► develop ──► production) ∥ SA153 (r) ──► SA153 (f) ──► SA154 (inventory) ∥ SA306 ∥ SA307
Track 3: SA277 (a3) ──► SA277 (a2, after SA191d)
     release path:  SA191d ──► operator publish 0.89.0
     critical path: SA191d ──► SA153 (f)
```

Arrows within a track are queue order; the table holds the dependency edges. SA191d is
delegated, with every production write operator-gated; SA153 (r) and SA277 (a3) need nothing from it and run now. SA153 (f)
and SA277 (a2) wait on SA191d.

**Slices.** Each slice is one implementer session with a fresh context, scoped to its text and
named surfaces, and ends with a short handoff note committed with the work. A ticket closes when
its last slice lands; slices are not scheduled.

**Order.** Module migration history is frozen, so a module schema change ships as a new
migration. SA153's own tables live in the project-owned extension as `0002+` migrations.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191d (production); SA153 (r); SA306; SA307 | yes | no | yes | no | yes |
| 2 | — | yes | yes | yes | yes | no |
| 3 | SA277 (a3) | yes | no | yes | no | no |

### Ownership and merge coordination

- Track 1 owns the generated `urls.py.j2` and the theme's social seam pages, the parity oracles,
  the hosted workflow triggers (including `e2e.yml`'s tag pattern), the `bap-web` cutover,
  the property extension, public templates, and the portal's
  extension documentation, the `bap-web` forms import, the design-system
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
  personal-data check, and the `showcase_react` design layer.
- Track 3 owns the orgs tenancy, purge,
  removal-obligation, invite-throttle, and boot path (`orgs/apps.py`, `orgs/removal.py`, `orgs/views.py`), the privileged-command and runtime-role
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
  `decisions.md` § Clean-Break Migration History, and the maintainer migration tools
  (`beta_migration/`) with their smoke gate, playbook, gap ledger, and the upgrade prompt.
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

### Track 1 — cutover and the property portal

**SA191d context.** Old `bap-web` (`~/code/bap-web-old`) serves production on Railway with no
users, only form submissions and configuration. The regenerated `bap-web` (`~/code/bap-web`,
formerly `bap-web-new`) already declares every module (`auth`, `listings`, `forms`, `analytics`,
`notifications`, `orgs`, `storage`), carries
the `properties` app with `/api/properties/` and `properties_seed_catalog`, and recreates the six
BAP form definitions (`compradores`, `vendedores`, `alquiler-propietario`,
`alquiler-inquilino`, `reubicacion`, `consulta-general`) in
`client_extensions/.../forms_seed_presets.py`.
The cutover runs **in place** on Railway project `bap-web`, which has two environments, each an
app service fed by GitHub `VictorRocco/BAP-web` plus a PostgreSQL 17 service: `develop` (branch
`develop`, `bap-web-develop.up.railway.app`, 14 test submissions) and `production` (branch
`main`, `buenosairesproperties.com`, 0 submissions). The custom domain and DNS are never touched.
The new code replaces the old by force-push (the histories are unrelated); the old history stays
as `legacy-main`, `legacy-develop`, and the `v-legacy` tag. The project targets PostgreSQL 18, so
each environment gets a **new PostgreSQL 18 service** restored from a locally built database and
the app's `DATABASE_URL` is repointed to it; the old PostgreSQL 17 service stays untouched as the
rollback. `develop` is the rehearsal; `production` repeats it. Downtime is accepted.

Measured on 2026-10-22, before the (build) slice: rollback copies (production `pg_dump`, both environments'
variables) are in `~/bap-cutover/` (mode 700, outside every repository). Old mail goes through
Resend's SMTP relay (`smtp.resend.com:2587`, the same `re_…` key in both environments as
`EMAIL_HOST_PASSWORD`); the new project uses the Resend API with that key as `RESEND_API_KEY`,
plus a webhook signing secret. All ten old forms notify `info@buenosairesproperties.com`; four
(`contact`, `feedback`, `newsletter`, `support`) are not recreated and have no production
submissions. Operator decisions: sender, reply-to, and notification address
`info@buenosairesproperties.com`; analytics stays on with `POSTHOG_API_KEY`, because the shipped
apply rule refuses switching `analytics` off while `forms` requires it; the `develop` test
submissions are not carried. The (build) dump is `~/bap-cutover/new-2026-10-22.dump`.
`railway ssh` needs an operator SSH key (re-registered 2026-10-23 after the incident reset); exports otherwise read the database directly
(`DATABASE_PUBLIC_URL` of the PostgreSQL service). Secrets staged in `~/bap-cutover/` (mode
600): `resend-api-key`, `posthog-key`, `resend-webhook-secret-develop`, and
`resend-webhook-secret-production`; the last three were never stored in Railway.

**Railway security incident (2026-10-21).** Railway disclosed a platform incident, recommends
revoking every variable stored in Railway, invalidated API tokens and OAuth sessions, and
re-enabled builds by plan tier (Enterprise, Pro, then Hobby, Free, Trial). Every value in the
old variables is treated as exposed: the Resend key is rotated before use; the old
`SECRET_KEY` and `DJANGO_SUPERUSER_*` are not carried; the old PostgreSQL 17 credentials are
rollback-only (rotate or retire after the cutover). Values generated after the incident (the
new PostgreSQL 18 service, runtime role, `SECRET_KEY`) are clean.

The (swap) slice made `~/code/bap-web` the new project and `~/code/bap-web-old` the old one. The
procedure is `bap-web/CUTOVER.md`; the (build) slice rewrote it to this strategy. A QuickScale
defect follows the release re-entry loop (never patch an embedded module in a project; republish
and update); a project defect is fixed in `bap-web`, project-specific behavior in its
`client_extensions`.

- [ ] **SA191d — Cut over production to the regenerated `bap-web` in place (delegated, operator-gated).**

  Delegated to an AI assistant, one slice per session, each ending with a handoff note in the
  project's `docs/`. Every push, every Railway variable or service change, and every restore is
  an operator gate; the operator runs `createsuperuser` and the admin and inbox reviews. Secrets
  are read from `~/bap-cutover/` or Railway, never printed or committed.

  **Acceptance:** on `https://buenosairesproperties.com`, `/healthcheck/` prints `OK`, `/` and
  `/contact` (six forms) render, a submitted form reaches `info@buenosairesproperties.com` through
  Resend, and `/admin/` shows it; the old PostgreSQL 17 service and the legacy refs exist for
  rollback.

  **Slices:**
  - [x] (build) Local database build.
  - [x] (swap) Repository swap.
  - [x] (develop) Rehearsal on Railway `develop` (`bap-web` `CUTOVER.md` § S3 record).
  - [ ] (production) Switch on Railway `production` (Tier 2-full; the one-way step stands alone),
    following `CUTOVER.md` § S4 as rewritten by (develop): automatic deploys off and an SSH key
    registered first; restore inside the new service over `railway ssh` (no TCP proxy); delete
    `DJANGO_SUPERUSER_*`, `EMAIL_*`, and `DEFAULT_FROM_EMAIL` before the new code first boots
    (`start.sh` creates a superuser from them); `railway variable` flags after the subcommand;
    `resend-webhook-secret-production`; force-push `main` to `main` with the lease on `782b11c`;
    acceptance on the domain, with the browser check from a private window (a logged-in admin
    gets 404 on public forms). After it passes, the operator deletes the develop Resend webhook,
    the old PostgreSQL 17 service, and, 48 hours later (Railway reserves deleted names), renames
    the new service and volume to `Postgres` / `postgres-volume`, as on `develop`. Rollback: repoint `DATABASE_URL` to the old PostgreSQL 17 service, restore
    the variables from `~/bap-cutover/old-variables.json` (their Resend key is revoked), and
    deploy `legacy-main`.

- [ ] **SA306 — Make the generated `ci.yml` start on GitHub and pass on `bap-web`.**

  `ci.yml.j2:133` gates `frontend-lint` with a job-level `if: hashFiles(...)`; GitHub rejects the
  workflow, so every generated project's push shows a 0-second failure with no jobs (seen on
  `bap-web` `develop`, run 39920079023). Fix the template (step-level guard or an always-run job),
  add an `actionlint` check over the generated workflows, ship through the release re-entry loop,
  update `bap-web`, and iterate until its CI is green on `develop` (Tier 2-full).

- [ ] **SA307 — Make System-org public content reachable for logged-in staff in forms and the admin.**

  Public forms and their submissions live in the System org, but a staff session resolves its
  personal org: on `bap-web` `develop` the public submit returns 404 to a logged-in admin, and the
  admin lists show no forms or submissions with no visible way to pick an org (only
  `?organization__id__exact=<id>` works). Public form resolution must not depend on the visitor's
  session org, and the admin must offer an org selector that includes the System org. Ship
  through the release re-entry loop and re-prove both on `bap-web` (Tier 2-full).

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
  - [ ] (r) Audit the portal work already in `bap-web` (`~/code/bap-web`; the `properties` app, its API, and
    the React pages) against this acceptance, list what is missing, and close the gaps with
    tests in the project (Tier 2-full).
  - [ ] (f) Go-live on `buenosairesproperties.com` after SA191d's cutover; re-prove the journey on
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

### Track 2 — module provenance

- [x] **SA305 — Detect hand edits to an embedded module before `quickscale update`.**

### Track 3 — upgrade path

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
  - [ ] (a2) After SA191d's cutover: the decision record and boundary rule in decisions, the
    draft (`docs/planning/migration-upgrade-path-draft.md`) confirmed or amended against the cutover evidence, and the operator docs pruned of
    steps either stage covers (Tier 2-fast).
  - [ ] (a3) The supported source-version range, test projects generated at each version in it
    with `beta_migration` smoke runs against them, and the prompt moved into the QuickScale
    repository as a versioned artifact (Tier 2-full).

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

**Unscheduled — React-theme browser coverage.** The generated Playwright E2E now asserts the
current dashboard heading against the Django-served origin, and `bap-web` (`~/code/bap-web`) has
a live-site screenshot harness; the repository still has no full journey suite. Remaining
order when scheduled: (1) add `pnpm test:e2e` to `ci.yml.j2`;
(2) the named user journeys; (3) a depth-capped link crawler in `test_e2e_full_workflow.py`;
(4) full journey E2E against the Docker stack, only if it fits the E2E time budget in
validation_policy.md.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
