# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

Ship 0.89.0 to production. The re-cut 0.89.0 is proven on `bap-web` `develop` (SA191d) and
the orgs pins are fixed (SA328); re-prove the ship candidate on `develop` and review the
cutover plan (SA329), cut over production (SA330),
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
| SA329 | Prepare and review the production cutover plan | 2 | — | Required |
| SA330 | Cut over production to the regenerated `bap-web` in place (operator-gated) | 2 | SA329 | Required |
| SA331 | Publish 0.89.0 to PyPI | 2 | SA330 | Required |
| SA332 | Retire the old production database and exposed credentials | 2 | SA330 | Required |
| SA277 | Define the upgrade path for newer projects as `website_migration` code plus a maintained prompt | 3 | SA330 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: — (portal deferred)
Track 2: SA328 (pins) ─► SA329 (plan) ─► SA330 (production) ─► SA331 (publish) ─► SA332 (retire)
Track 3: SA277 (a) done ─► [SA330] ─► SA277 (b)
     portal (deferred): publication ─► SA153 ─► SA154
```

Arrows are queue order; table dependencies gate ticket completion. SA277 (a) is complete; only
(b) remains, waiting for SA330. SA330 ships exactly the bytes SA191d (re-proof) and SA328 proved; a
defect found there follows the release re-entry loop (fix, re-cut, re-proof). Module migration
history is frozen: a module schema change ships as a new migration, and SA153's tables live in
the project-owned extension as `0002+` migrations.

### Track states

| Track | Next ticket / slice | Can start | Can finish | Can merge |
|---|---|---|---|---|
| 1 | — (portal deferred) | no: nothing queued | no: nothing queued | yes |
| 2 | SA329 (§ S3b develop re-proof; ship frozen) | yes: SA328 sealed and bap-web updated | no: operator gates 3–5 (push, deploy, acceptance), then plan approval | yes |
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
`develop` already runs the regenerated stack (rehearsed 2026-10-23). The procedure and its run record are `bap-web/CUTOVER.md`. Secrets
live in `~/bap-cutover/` (mode 600), never printed or committed. After Railway's 2026-10-21
incident every old variable is exposed: none is carried, and the old PostgreSQL 17 credentials
are retired after the cutover. A QuickScale defect follows the release re-entry loop; a project
defect is fixed in `bap-web`. `bap-web` keeps SA153 (h) (public property head, crawler summary,
sitemap, robots). **Operator decisions (2026-10-30):** production stores media on local disk
(`QUICKSCALE_ALLOW_LOCAL_MEDIA=1`, ephemeral across redeploys; revisit when real uploads start);
acceptance proves anonymous submissions only (a logged-in admin resolves its own organization,
which owns no forms); F-004 is fixed before publication.

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

- [ ] **SA329 — Prepare and review the production cutover plan.**

  Revised 2026-10-31 and reviewed against the develop evidence (the Tier 3 plan review; four
  review rounds, clean): `bap-web/CUTOVER.md` § S4 + Rollback now carry the `predeploy.sh`
  (migrate, cache table) + `start.sh` (runtime role, forms seed, Gunicorn) + `/ready/` contract
  with stop conditions from the develop deploy logs; the production variables table rebuilt
  from the develop service's names, with `QUICKSCALE_ALLOW_LOCAL_MEDIA=1` and the production
  `ALLOWED_HOSTS`; a step 0 submission check plus a fresh `old-<date>.dump` rollback copy; the
  lease re-verified (`782b11c3` is still `origin/main`); step 5 aligned with SA330's
  anonymous-only acceptance; and the Rollback `dumpdata` label (`quickscale_forms`) and stale
  `hashFiles` note corrected. Handoff: `bap-web/docs/sa329-cutover-plan.md`.

  **Production-shaped develop re-proof (operator decision 2026-10-31).** Production ships only
  a tree `develop` has run the way production will. `CUTOVER.md` § S3b now freezes `main` as
  `SHIP_SHA`, checks develop/production variable-name parity, deploys it to `develop` (operator
  gates) and passes the develop acceptance; § S4 then ships `$SHIP_SHA` (must equal
  `origin/develop`). The S3b + S4 ship-commit delta review ran two rounds and stopped clean;
  `SHIP_SHA` is frozen at `86ba951b` and the parity check passed (develop = the S4 table;
  production differs only by the known S4 step 2 sets). Remaining: operator gates 3–5
  (develop push, deploy, acceptance), then operator approval, then SA330 (Tier 2-full).

- [ ] **SA330 — Cut over production to the regenerated `bap-web` in place.**

  **Production acceptance:** on `https://buenosairesproperties.com`,
  `/healthcheck/` prints `OK`, `/ready/` passes, `/` and `/contact` render, the six form schemas
  answer, an anonymous submission (private window) reaches `info@buenosairesproperties.com`
  through Resend with `email.sent` and `email.delivered` webhook events, `/admin/` lists it under
  the System organization, and the old PostgreSQL 17 service and legacy refs exist for rollback.

  After SA329 is approved, execute the revised `CUTOVER.md` § S4 steps
  0–5 exactly, each operator gate approved separately; pass the production acceptance,
  retaining the old database and legacy refs. A failed stop condition goes to Rollback, not
  improvisation. **Tier 3: plan review required** (done in SA329) — the production
  database/credential switch can lose data or expose credentials.

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
