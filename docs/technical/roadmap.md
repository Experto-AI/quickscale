# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

Fixes first, release on `develop`, ship 0.89.0 to production. Close every 2026-10-23 audit
ticket, re-cut 0.89.0, update `bap-web` to that tag, prove the release on its `develop`
environment, then cut over production to the same tag (SA191d) and publish 0.89.0 to PyPI. The
property portal (SA153, SA154) is deferred: it starts only after all hardening tickets close,
production runs 0.89.0, and 0.89.0 is on PyPI (see
[Deferred — property portal](#deferred-property-portal)).

**Release status.** 0.89.0 is unpublished; a live 0.88.0 install moves to it on a fresh
database. All hardening tickets (SA315, SA320, SA321, SA323, SA324) land,
the tag is re-cut, `bap-web` adopts it, SA191d (re-proof) is the release's final validation on
`develop`, SA191d (production) ships the same tag, and the operator's Phases 5–6 sealing and PyPI
publication follow ([publish_procedure.md](publish_procedure.md)).

Audit tickets name the [arch](../others/arch-audit.md), [tech](../others/tech-audit.md), or
[coherence](../others/coherence-audit.md) IDs they close; the audits keep the evidence and fix
detail. Coherence tickets merge the matching coherence proposal into decisions with a harness
detector (the audit's enforcement gap, with its fixture controls), or record a review-only clause
without one. Where an audit leaves an operator question open, the ticket states the default it
ships unless the operator decides otherwise.

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, acceptance, and each slice's tier; [CHANGELOG.md](../../CHANGELOG.md) preserves
history.

**Sizing.** Every slice carries an Adaptive tier
(Adaptive `docs/guides/operator-guide.md` § Planning and implementation):
Tier 1 is one bounded low-risk concern within direct context fit; Tier 2-fast is a specified
change with known targets, acceptance, and checks; Tier 2-full is one whose callers, mechanism,
or environment still need discovery, or that carries an open strategic choice. Audit work is
sliced to Tier 2 — preferably Tier 2-full, which holds a related batch in one delivery. Only
SA191d's production switch and retirement stay Tier 3 with plan review: their risk is the
irreversible operation itself, which slicing cannot remove; preparation ships separately.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA191d | Prove 0.89.0 on `bap-web` `develop`, then cut over production to it in place (delegated, operator-gated) | 2 | SA315, SA321, SA323, SA324 | Required |
| SA315 | Close orgs and auth lifecycle defects | 2 | — | Required |
| SA321 | Make the generated production deployment contract an artifact | 1 | — | Required |
| SA323 | Harden module upload, form, export and notification paths | 2 | — | Required |
| SA324 | Make tenant contract evidence and write services coherent | 2 | — | Required |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 3 | SA191d | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA321
Track 2: SA315 (a, b) ─► SA323 ─► SA324 (a, b)
         ─► SA191d (re-proof → production → retire, operator-gated)
Track 3: [SA191d (production)] SA277
     release path: all hardening ─► re-cut 0.89.0 ─► bap-web adopts it ─► SA191d (re-proof on develop)
                   ─► SA191d (production, same tag) ─► publication ─► SA191d (retire)
     portal (deferred): all hardening closed + publication ─► SA153 ─► SA154
```

Arrows are queue order; table dependencies gate ticket completion, with slice exceptions below.
SA277 waits for SA191d (production).
SA191d (re-proof) owns the `develop` deployment and the release's final checks; (production) ships
exactly the tag re-proof passed; a defect found there follows the release re-entry loop (fix,
re-cut, re-proof). Operator publication of 0.89.0 follows SA191d (production); SA191d (retire)
closes the ticket. Each slice ships with
its own checks and handoff.

**Order.** Module migration history is frozen, so a module schema change (SA314's debit
reference) ships as a new migration. When resumed, SA153's own tables
live in the project-owned extension as `0002+` migrations.

### Track states

| Track | Next ticket / slice | Can start | Can finish | Can merge |
|---|---|---|---|---|
| 1 | SA321 | yes | yes | yes: SA321 |
| 2 | SA315 (b) | yes | yes | yes: SA315, SA323, SA324 |
| 3 | SA277 | no: SA191d (production) for SA277 | no: SA191d (production) for SA277 | yes: SA326 |

**Clearing blockers.** Track 1: none. Track 2: SA191d waits for all hardening and the re-cut tag,
then the operator's `develop` push, production-switch, publication and retirement approvals. Track 3:
SA191d (production) clears SA277.

### Ownership and merge coordination

- Track 1: generated-project templates (README, Compose, Docker, CI, Makefile, settings), the
  theme and its managed hooks, and release workflows. The property extension, React pages,
  crawler views and journey checks return with the deferred portal.
- Track 2: `bap-web` cutover (SA191d), with joint publication and deployment; dependency
  manifests, locks and advisory disposition; module runtime code and tests in billing, CRM, orgs,
  auth, storage, forms, listings and notifications.
- Track 3: `beta_migration/`, apply/update state and CLI commands, the contract-vintage gate,
  backups and `dr_engine`, module manifests/READMEs, repository gates, supported-version
  fixtures, versioned upgrade prompt, and upgrade decision/operator guidance.
- One delivery candidate per track; serialize merges into `v89`.
- **Conflict surface:** this roadmap, CHANGELOG, the three audits, `project_contract.yml`,
  `decisions.md`, `README.md.j2` (SA320 (c), SA321), `settings/base.py.j2` (SA320 (c),
  SA321), billing `_settings.py`, module manifests (SA320 (c)),
  `bap-web`'s dependency lock, and `bap-web`'s frontend tests and routes
  (`App.test.tsx`, `AppRoutes.test.tsx`).
  Reconcile after each merge and run the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Track 1 — generated project

- [x] **SA320 — Deliver module resource contracts to user-owned pages through managed hooks.**

- [ ] **SA321 — Make the generated production deployment contract an artifact.**

  Closes arch `generated-deploy-topology-unmodeled`. Default is option 2 — Railway is the supported
  production path — unless the operator declares self-hosted Compose supported, in which case
  option 1 adds a production Compose profile. Either way, decisions record the choice; migrations
  run as a pre-deploy step, not at boot; readiness and liveness are separate; and production
  refuses `FileSystemStorage` media unless an explicit dev flag is set.

  **Acceptance:** a generated deployment test boots production settings and fails on local media
  without the flag; the rendered Railway config runs migrations pre-deploy; README and decisions
  name one production path (Tier 2-full).

### Track 2 — cutover and module runtime defects

**SA191d context.** Old `bap-web` (`~/code/bap-web-old`) serves production on Railway project
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
defect is fixed in `bap-web`. The module fixes below reach `bap-web` as one update to the re-cut
0.89.0 tag before re-proof; the cutover waits for all of them. `bap-web` keeps SA153 (h) (public
property head, crawler summary, sitemap, robots); its `properties` models must be classified in
the tenant contract, since the 2026-10-26 `develop` CI run failed the tenant isolation
conformance check on `properties.PropertyAgent` and siblings.

- [ ] **SA191d — Cut over production to the regenerated `bap-web` in place (delegated, operator-gated).**

  One slice per session, each ending with a handoff note in `bap-web/docs/`. Every push, Railway
  change, and restore is an operator gate. **Production acceptance:** on `https://buenosairesproperties.com`,
  `/healthcheck/` prints `OK`, `/` and `/contact` render, a form submitted logged in and
  anonymously reaches `info@buenosairesproperties.com` through Resend, `/admin/` lists it, and
  the old PostgreSQL 17 service and legacy refs exist for rollback. Ticket completion also
  requires (retire), after which the dump and legacy refs remain as recovery artifacts.

  **Slices:**
  - [ ] (re-proof) After all hardening and the re-cut, update `bap-web` to the 0.89.0 tag, push
    it to `develop`, and pass the acceptance there as the release's final validation, with CI
    green (tenant conformance included) and both dependency audits clean apart from the recorded
    dev-only exception (Tier 2-full).
  - [ ] (production) After re-proof and operator approval, ship the same commit and tag: execute `CUTOVER.md` § S4 steps 1–5;
    pass the production acceptance above, retaining the old database and legacy refs.
    **Tier 3: plan review required** — the production database/credential switch can lose data
    or expose credentials; review restore validation and rollback before execution.
  - [ ] (retire) After production acceptance and a separate operator gate, execute § S4 step 6:
    delete the develop Resend webhook and old PostgreSQL 17 service, retire exposed credentials,
    then rename the new service/volume after 48 hours; verify health and the retained dump/refs.
    **Tier 3: plan review required** — deleting the old database irreversibly removes live rollback.

- [x] **SA310 — Fix the subscription Checkout S1 and apply billing webhooks in provider order.**

- [x] **SA311 — Close the S2 tenant-boundary defects in CRM, orgs, storage and forms.**

- [x] **SA314 — Make billing credits, Checkout and gates idempotent and tenant-correct.**

- [ ] **SA315 — Close orgs and auth lifecycle defects.**

  Closes tech `orgs-bulk-delete-leaves-zero-owners`, `orgs-admin-org-delete-blocked`,
  `orgs-slug-new-shadows-route`, `auth-profile-email-change-desync`, `auth-deletion-logs-pii`, and
  coherence `orgs-invitation-notification-failure` (proposal 15). Q2 default: best-effort — the
  invitation stays, and the send failure is logged and surfaced, never a 500.

  **Slices:**
  - [x] (a) Orgs: bulk deletion cannot leave an organization ownerless; admin organization
    deletion passes the last-owner receiver; slug `new` is reserved; the invitation send-failure
    policy is recorded and tested (Tier 2-full).
  - [ ] (b) Auth: a profile email change goes through allauth's address flow, and a password reset
    through the old address fails by test; deletion-failure logs carry no names (Tier 2-full).

- [ ] **SA323 — Harden module upload, form, export and notification paths.**

  Closes tech `media-image-decode-before-dimension-cap`, `forms-option-values-not-validated`,
  `forms-csv-export-materializes-all-values`, `forms-retention-skips-null-ip-rows`, and
  `notifications-message-status-aggregate-race`.

  **Acceptance:** a compressed high-pixel image is rejected before decode; a select, radio or
  checkbox value outside its options is a 400; CSV export streams with bounded memory; retention
  removes rows stored without an IP; concurrent sibling webhooks leave a correct aggregate status
  (Tier 2-full).

- [ ] **SA324 — Make tenant contract evidence and write services coherent.**

  Closes coherence `forms-tenant-isolation-evidence`, `tenant-suite-default-role`,
  `stale-isolation-narratives`, `listings-publish-org-fallback`, `public-read-marker-mixins`, and
  `crm-null-org-legacy` (proposals 6–8, 10–11, 13; gaps 23, 28–29). Q4 default: every tenant suite
  defaults to the restricted role; an environment variable may override.

  **Slices:**
  - [ ] (a) Evidence: forms' RLS boundary covers all four tenant tables with matching,
    non-matching and unset context plus a regular-member view; the three suites default
    restricted; the two narratives describe the current contract; the rule 11 detector requires
    all three (Tier 2-full).
  - [ ] (b) Services: listings' publish service requires an explicit organization; both
    public-read mixins prime public context or are documented no-DB markers; CRM's NULL-organization
    branch is removed with its test; detectors for rules 19 and 23 carry their controls
    (Tier 2-full).

### Track 3 — upgrade path, generator state and backups

- [x] **SA319 — Update modules as one sealed-tag transaction.**

- [x] **SA322 — Make backup restore safe and its recovery point coherent.**

- [x] **SA325 — Make module settings, defaults, messages and READMEs follow one contract.**

- [x] **SA326 — Wire the unwired release and security gates.**

- [ ] **SA277 — Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt.**

  Addresses the upgrade-path part of arch `generated-file-ownership-unmodeled`; managed
  resource hooks are SA320's scope (and the deferred SA153's). One path in two stages:
  `beta_migration` does what it can mechanically; the prompt-driven port (`MIGRATION_PROMPT.md`,
  `CUTOVER.md`) handles what it reports it could not.

  **Acceptance:** decisions record the two-stage path (the gap ledger is the prompt's input, so
  neither stage repeats the other), the boundary rule (a gap that recurs across releases moves
  into code; a one-off stays in the prompt), the revocation trigger (a second long-lived project
  or a template security fix), and the steps-per-release count to watch, trending toward zero
  (58 declared steps on 2026-10-23). Operator docs do not duplicate steps either stage covers.
  Decisions say that supporting further projects meets the "second long-lived project"
  revocation trigger.

  After SA191d (production), record the two-stage boundary and revocation triggers against the
  cutover evidence; confirm/amend the upgrade-path draft and remove duplicate operator steps
  (Tier 2-fast). Validate links and smoke instructions.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

<a id="deferred-property-portal"></a>

### Deferred — property portal (Track 1)

Not scheduled. Resumes only when SA315, SA320, SA321, SA323 and SA324 are
closed, SA191d (production) has passed, and 0.89.0 is published; it is then re-added to the
scheduling table on top of the deployed `bap-web`.

**SA153 — Deliver the first property portal using project-owned extensions.**

Target `buenosairesproperties.com` with one React public property surface over a project-owned
JSON read API under the [extension contract](module-extension.md), building on the React pages
and `/api/properties/` the port carried over. No public API in `listings`, no generic property
behavior in generated projects. Module-coupled data on new pages comes through the generated managed
hooks (arch `generated-file-ownership-unmodeled`), and project-owned tenant views
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
