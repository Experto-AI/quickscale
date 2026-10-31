# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

Ship 0.89.0 to production. The re-cut 0.89.0 is proven on `bap-web` `develop` (SA191d), the
orgs pins are fixed (SA328), and the cutover plan is approved (SA329); cut over production
(SA330) at `SHIP_SHA` `86ba951b`,
publish 0.89.0 to PyPI (SA331, [publish_procedure.md](publish_procedure.md)), and retire the
old database (SA332). 0.89.0 is unpublished; a live 0.88.0 install moves
to it on a fresh database. The property portal (SA153, SA154) starts only after production runs
0.89.0 and it is on PyPI (see [Deferred — property portal](#deferred-property-portal)).

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, acceptance, and each slice's tier; [CHANGELOG.md](../../CHANGELOG.md) preserves
history.

**Sizing.** Every slice carries an Adaptive tier
(Adaptive `docs/guides/operator-guide.md` § Planning and implementation):
Tier 1 is one bounded low-risk concern within direct context fit; Tier 2-fast is a specified
change with known targets, acceptance, and checks; Tier 2-full is one whose callers, mechanism,
or environment still need discovery, or that carries an open strategic choice. Audit work is
sliced to Tier 2, preferably Tier 2-full. Only SA330 (production) and SA332 (retire) stay Tier 3 with
plan review: their risk is the irreversible operation itself.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA330 | Cut over production to the regenerated `bap-web` in place (operator-gated) | 2 | — | Required |
| SA331 | Publish 0.89.0 to PyPI | 2 | SA330 | Required |
| SA332 | Retire the old production database and exposed credentials | 2 | SA330 | Required |
| SA277 | Define the upgrade path for newer projects as `website_migration` code plus a maintained prompt | 3 | SA330 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: — (portal deferred)
Track 2: SA330 (production) ─► SA331 (publish) ─► SA332 (retire)
Track 3: SA277 (a) done ─► [SA330] ─► SA277 (b)
     portal (deferred): publication ─► SA153 ─► SA154
```

Arrows are queue order; table dependencies gate ticket completion. SA277 (a) is complete; only
(b) remains, waiting for SA330. SA330 ships exactly `SHIP_SHA` `86ba951b`, the tree § S3b proved
on `develop` (including the SA328 pin refresh and the listings-off gate); a defect found there
follows the release re-entry loop (fix, re-cut, re-proof). Module migration
history is frozen: a module schema change ships as a new migration, and SA153's tables live in
the project-owned extension as `0002+` migrations.

### Track states

| Track | Next ticket / slice | Can start | Can finish | Can merge |
|---|---|---|---|---|
| 1 | — (portal deferred) | no: nothing queued | no: nothing queued | yes |
| 2 | SA330 | yes: SA329 approved; ship frozen at 86ba951b | no: production acceptance | yes |
| 3 | SA277 (b) | no: SA330 | no: SA330 | yes |

### Ownership and merge coordination

- Track 1: generated-project templates, the theme and managed hooks, release workflows, and
  the deferred portal.
- Track 2: `bap-web` cutover and 0.89.0 publication (SA328–SA332), with joint publication and deployment; dependency
  manifests, locks and advisory disposition; module runtime code and tests in billing, CRM, orgs,
  auth, storage, forms, listings and notifications.
- Track 3: `website_migration/`, apply/update state and CLI commands, the contract-vintage gate,
  backups and `dr_engine`, module manifests/READMEs, repository gates, supported-version
  fixtures, versioned upgrade prompt, and upgrade decision/operator guidance.
- One delivery candidate per track; serialize merges into `v89`.
- **Conflict surface:** this roadmap, CHANGELOG, the three audits, `project_contract.yml`,
  `decisions.md`, and `bap-web`'s dependency lock.
  Reconcile after each merge and run the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Track 2 — cutover

**Cutover context (SA328–SA332).** Old `bap-web` (`~/code/bap-web-old`) serves production on Railway project
`bap-web` with no users and no production submissions. The regenerated `bap-web` (`~/code/bap-web`)
declares `auth`, `listings`, `forms`, `analytics`, `notifications`, `orgs`, and `storage`, the
`properties` app, and the six BAP forms. The cutover runs **in place**: per environment, a new
PostgreSQL 18 service restored from `~/bap-cutover/new-2026-10-22.dump`, new variables, and a
force-push over the unrelated history (kept as `legacy-main`, `legacy-develop`, `v-legacy`); the
old PostgreSQL 17 service stays as the rollback until acceptance, and DNS is never touched.
`develop` runs `86ba951b` with public listings off (rehearsed 2026-10-23; re-proved 2026-10-31).
The procedure and its run record are `bap-web/CUTOVER.md`. Secrets
live in `~/bap-cutover/` (mode 600), never printed or committed. After Railway's 2026-10-21
incident every old variable is exposed: none is carried, and the old PostgreSQL 17 credentials
are retired after the cutover. A QuickScale defect follows the release re-entry loop; a project
defect is fixed in `bap-web`. `bap-web` keeps SA153 (h) (public property head, crawler summary,
sitemap, robots). **Operator decisions (2026-10-30, extended 2026-10-31):** production stores
media on local disk (`QUICKSCALE_ALLOW_LOCAL_MEDIA=1`, ephemeral across redeploys; revisit when
real uploads start); acceptance proves anonymous submissions only (public requests resolve the
System organization regardless of session state; use a private window); public listings stay off
(`PUBLIC_LISTINGS_ENABLED=False`, variable only; the static `/properties/` sitemap entry is an
accepted exception); F-004 is fixed before publication.

**Execution model.** Each ticket is handed to an AI session from a cold context; the human only
approves operator gates (every push, tag push, Railway change, restore, deletion, and PyPI
upload). Each session starts by measuring state (branches, tags, `origin/develop`,
`origin/main`, Railway deployment) rather than trusting this text, and ends with a handoff
note in `bap-web/docs/` and an update to its ticket here.

- [x] **SA191d — Prove 0.89.0 on `bap-web` `develop` (re-proof).**

  `bap-web` adopted the re-cut splits and pushed `main` `34551d4f`
  to `develop` (operator gate); CI `41103839564` passed the test, frontend-lint and
  tenant-isolation jobs, and the develop acceptance passed. The 2026-10-30 advisory
  refresh required `89da9a17` (`zod` 4.6.7, dev `undici` and
  `postcss-selector-parser` patched); CI `41108598169` passed, the audits are clean
  (the hosted CI has no audit jobs), and the acceptance re-passed with no W007.
  `develop` runs `89da9a17` (Tier 2-full).

- [x] **SA328 — Fix the stale orgs-module action pins (F-004) before publication.**

- [x] **SA329 — Prepare and review the production cutover plan.**

  Operator-approved 2026-10-31 at `SHIP_SHA` `86ba951b`. Handoff:
  `bap-web/docs/sa329-cutover-plan.md`.

- [ ] **SA330 — Cut over production to the regenerated `bap-web` in place.**

  **Ship exactly `SHIP_SHA` `86ba951b88e8db64d32c270f3d9282b2dac36493`; it must equal
  `origin/develop`.** It is the tree `develop` proved in § S3b with the production-shaped
  deploy and acceptance.

  **bap-web docs.** The local-only docs commits after `86ba951b`, up to `4e559dc6`, are never
  pushed to `main` before acceptance; they can follow later as a docs-only descendant.

  **Production variables.** Use the 13-name § S4 step 2 table, including
  `PUBLIC_LISTINGS_ENABLED=False`; delete the 10 legacy names (`EMAIL_*`,
  `DEFAULT_FROM_EMAIL`, `DJANGO_SUPERUSER_*`).

  **Acceptance.** The § S4 step 5 list, including the listings-off checks: the home seam
  `publicListingsEnabled: false`, `/api/properties/` 404, no `/properties/<slug>/` sitemap
  details (the static `/properties/` entry is an accepted exception), and no "Propiedades"
  nav. `/healthcheck/` and `/ready/` `OK`; `/` and `/contact` render; the six form schemas
  answer; an anonymous `consulta-general` submission (private window) reaches
  `info@buenosairesproperties.com` through Resend with `email.sent` and `email.delivered`;
  `/admin/` lists it under the System organization; the old PostgreSQL 17 service and legacy
  refs exist for rollback.

  **Lease.** `origin/main` must be `782b11c316b9255151596439fe6ce677c15d7680`.

  Execute `CUTOVER.md` § S4 step 0 first, then each operator gate separately; a failed stop
  condition goes to Rollback. Retain the old database and legacy refs. **Tier 3: plan review
  approved in SA329** — the production database/credential switch can lose data or expose
  credentials.

- [ ] **SA331 — Publish 0.89.0 to PyPI.**

  After production acceptance, publish 0.89.0 per
  [publish_procedure.md](publish_procedure.md) Phases 6–7 from the sealed state production
  runs: confirm the `0.89.0` tag is at `HEAD` and matches the shipped wheel, finalize the
  CHANGELOG line, push the tag (operator gate; this triggers PyPI), verify the PyPI release
  and a clean install, then close out (merge `v89` to `main`). PyPI publication is
  irreversible (Tier 2-full).

- [ ] **SA332 — Retire the old production database and exposed credentials.**

  After SA330 acceptance and a separate operator gate, execute § S4 step 6:
  delete the develop Resend webhook and old PostgreSQL 17 service, retire exposed credentials,
  then rename the new service/volume after 48 hours; verify health and the retained dump/refs.
  **Tier 3: plan review required** — deleting the old database irreversibly removes live rollback.

### Track 3 — upgrade path

- [ ] **SA277 — Define the upgrade path for newer projects as `website_migration` code plus a maintained prompt.**

  One upgrade path in two stages:
  `website_migration` does what it can mechanically; the prompt-driven port (`MIGRATION_PROMPT.md`,
  `CUTOVER.md`) handles what it reports it could not.

  **Acceptance:** decisions record the two-stage path (the gap ledger is the prompt's input, so
  neither stage repeats the other), the boundary rule (a gap that recurs across releases moves
  into code; a one-off stays in the prompt), the revocation trigger (a second long-lived project
  or a template security fix), and the steps-per-release count to watch, trending toward zero
  (58 declared steps on 2026-10-23). Operator docs do not duplicate steps either stage covers.
  Decisions say that supporting further projects meets the "second long-lived project"
  revocation trigger. "Website migration" is the name throughout (the `website_migration`
  package, CLI commands, docs and tests).

  **Slices:**
  - [x] (a) Renamed "beta migration" to "website migration" (`website_migration` in code, CLI,
    docs and tests); recorded the two-stage path, boundary rule and revocation triggers in
    decisions; removed operator steps either stage covers (Tier 2-fast).
  - [ ] (b) After SA330, confirm them and the steps count against the cutover
    evidence; validate links and smoke instructions (Tier 1).

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

### Deferred — bap-web post-cutover follow-ups

Project-owned follow-ups after SA330 acceptance; they are not QuickScale tickets.

- Omit the static `/properties/` sitemap entry while public listings are disabled; it currently
  serves a not-found page with HTTP 200.
- Delete the 12 demo listings from the production database (operator-gated).

<a id="deferred-property-portal"></a>

### Deferred — property portal (Track 1)

Not scheduled. Resumes only when SA330 has passed and 0.89.0 is published; it is then re-added to the
scheduling table on top of the deployed `bap-web`.

**SA153 — Deliver the first property portal using project-owned extensions.**

Target `buenosairesproperties.com` with one React public property surface over a project-owned
JSON read API under the [extension contract](module-extension.md), building on the React pages
and `/api/properties/` the port carried over. No public API in `listings`, no generic property
behavior in generated projects. Module-coupled data on new pages comes through the generated managed
hooks, and project-owned tenant views
run in the generated isolation lane.

**Acceptance:** the served documents (per-request head and crawler summary), the sitemap and
robots views, and the search → detail → inquiry journey with organization isolation pass on the
deployed site, and the extension/tenant declarations pass in `manage.py check`.

**Slices:**
- (j) Close search → detail → inquiry gaps; test organization isolation
  under the restricted role and the extension declarations, with module data accessed through
  the managed hooks (Tier 2-full).
- (f) After (j), deploy and re-prove that journey on the live site
  with operator approval and a tested deploy-revert path (Tier 2-full).

**SA154 — Property-portal capabilities to promote when a project needs them (after SA153).**

Tier 1 inventory review only: promote reusable property/React pages, translations, maps,
saved searches, profiles, syndication, media, paid placement, cross-links or full-text search
only for a concrete consumer, with bounded acceptance, dependencies and a track. Otherwise
drop the item. Tenant schema changes use incremental migrations on the frozen history.

**Unscheduled — React-theme browser coverage (Track 1, Tier 2-full per ordered slice).**
When activated: (A) wire `pnpm test:e2e` into generated CI and prove the existing smoke;
(B) add named journeys with passing browser checks; (C) add a depth-capped link crawler with
bounded traversal tests; (D) run the journeys on Docker within the E2E budget. Each consumes
its predecessor; no open-ended full-site crawl.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
