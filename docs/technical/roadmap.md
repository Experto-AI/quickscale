# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

Cut over the regenerated `bap-web` at visual parity (SA191d), then deliver the first
property portal in a project-owned extension (SA153), following
[module conventions](module_conventions.md#module-conventions). Generalize capabilities only
after that project proves their value. Alongside, close the 2026-10-23 audits' findings, starting
with the defects that block publication.

**Release status.** 0.89.0 fixes 0.88.0's S1 billing defects; a live 0.88.0 install moves to
0.89.0 on a fresh database. The 2026-10-23 technical audit found a new S1
(`billing-subscription-checkout-metadata-key-too-long`) and eight S2s in the unpublished tag, so
0.89.0 re-enters the release loop: SA310 and SA311 land, the tag is re-cut and
re-validated, and then the operator's Phases 5–6 sealing and PyPI publication follow SA191d
([publish_procedure.md](publish_procedure.md)).

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
| SA191d | Cut over production to the regenerated `bap-web` in place (delegated, operator-gated) | 2 | — | Required |
| SA310 | Fix the subscription Checkout S1 and order billing webhooks | 2 | — | Required |
| SA311 | Close the S2 tenant-boundary defects in CRM, orgs, storage and forms | 2 | — | Required |
| SA314 | Make billing credits, Checkout and gates idempotent and tenant-correct | 2 | SA310 | Optional |
| SA315 | Close orgs and auth lifecycle defects | 2 | SA311 | Optional |
| SA316 | Extend the contract-vintage gate to runtime and managed outputs | 3 | — | Optional |
| SA317 | Give apply state one owner; close CLI command defects | 3 | — | Optional |
| SA318 | Run generated tenant-isolation tests under the runtime role | 1 | — | Optional |
| SA319 | Update modules as one sealed-tag transaction | 3 | SA317 | Optional |
| SA320 | Deliver module resource contracts through managed hooks | 1 | SA316 | Optional |
| SA321 | Make the generated production deployment contract an artifact | 1 | — | Optional |
| SA322 | Make backup restore safe and its recovery point coherent | 3 | — | Optional |
| SA323 | Harden module upload, form, export and notification paths | 2 | SA311 | Optional |
| SA324 | Make tenant contract evidence and write services coherent | 2 | SA311 | Optional |
| SA325 | Make module settings, defaults, messages and READMEs follow one contract | 3 | — | Optional |
| SA326 | Wire the unwired release and security gates | 3 | — | Optional |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191d, SA318, SA320 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 3 | SA191d | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA153 (h) ─► SA318 ─► [SA316] SA320 (a) ─► SA153 (j) ─► [SA191d (production)] SA153 (f)
         ─► SA320 (b → c) ─► SA321 ─► SA154
Track 2: SA191d (re-proof) ─► SA310 ─► SA311 ─► SA191d (production → retire, operator-gated)
         ─► SA314 (a → b) ─► SA315 (a, b) ─► SA323 ─► SA324 (a, b)
Track 3: SA316 ─► SA317 (a, b) ─► SA319 (a → b) ─► SA322 (a → b → c)
         ─► SA325 ─► SA326 ─► [SA191d (production)] SA277
     release path: SA310, SA311 ─► re-cut 0.89.0 ─► SA191d ─► publication
     portal path:  SA316 ─► SA320 (a) ─► SA153 (j); SA191d (production) ─► SA153 (f)
```

Arrows are queue order; table dependencies gate ticket completion, with slice exceptions below.
SA153 (h) can ship any time; SA153 (j) needs SA318 and SA320 (a) only, and (f) needs
SA191d (production); SA320 (b/c) may finish after SA153 (j). SA277 waits for SA191d (production).
SA191d's operator gates are idle time on Track 2, filled with SA310/SA311 and then the Optional
module tickets. SA191d (retire) closes the ticket; (re-proof) owns the `develop` deployment and its
checks. Operator publication of 0.89.0 follows SA191d and the re-cut tag. Each slice ships with
its own checks and handoff.

**Order.** Module migration history is frozen, so a module schema change (SA310's optional
version column, SA314's debit reference) ships as a new migration. SA153's own tables live in the
project-owned extension as `0002+` migrations. Arch fix order holds: SA316 before SA320, SA317
before SA319, SA318 before SA153 (j).

### Track states

| Track | Next ticket / slice | Can start | Can finish | Can merge |
|---|---|---|---|---|
| 1 | SA153 (h) | yes | no: SA191d (production) for SA153 (f); SA316 for SA320 | yes: SA153 (h), SA318 |
| 2 | SA191d (re-proof) | yes | no: SA191d operator gates | yes: SA191d (re-proof), SA310, SA311 |
| 3 | SA316 | yes | no: SA191d (production) for SA277 | yes: SA316, SA317 |

**Clearing blockers.** Track 1: SA316 (Track 3) clears SA320; SA191d (production) clears SA153 (f).
Track 2: the operator's SA191d publication, production-switch and retirement approvals. Track 3:
SA191d (production) clears SA277.

### Ownership and merge coordination

- Track 1: generated-project templates (README, Compose, Docker, CI, Makefile, settings), the
  theme and its managed hooks, release workflows, the project-owned property extension, React
  pages, crawler views and journey checks.
- Track 2: `bap-web` cutover (SA191d), with joint publication and deployment; dependency
  manifests, locks and advisory disposition; module runtime code and tests in billing, CRM, orgs,
  auth, storage, forms, listings and notifications.
- Track 3: `beta_migration/`, apply/update state and CLI commands, the contract-vintage gate,
  backups and `dr_engine`, module manifests/READMEs for SA325, repository gates, supported-version
  fixtures, versioned upgrade prompt, and upgrade decision/operator guidance.
- One delivery candidate per track; serialize merges into `v89`.
- **Conflict surface:** this roadmap, CHANGELOG, the three audits, `project_contract.yml`,
  `decisions.md`, `README.md.j2` (SA320 (c), SA321), `settings/base.py.j2` (SA320 (c),
  SA321), billing `_settings.py` (SA310, SA314), module manifests (SA320 (c), SA325),
  `bap-web`'s dependency lock, and `bap-web`'s frontend tests and routes
  (`App.test.tsx`, `AppRoutes.test.tsx`; SA153 adds pages).
  Reconcile after each merge and run the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Track 1 — generated project and property portal

- [x] **SA312 — Close the generated-project and release-workflow safety defects before publication.**

- [ ] **SA318 — Run generated tenant-isolation tests under the restricted runtime role.**

  Closes arch `generated-isolation-unverified` (option 1). Generated CI gains a lane that migrates
  once, creates a `NOSUPERUSER NOBYPASSRLS` runtime role, and runs a two-organization isolation test
  template; production refuses `QUICKSCALE_ALLOW_BYPASSRLS=1` while serving. Lands before SA153 (j)
  so the portal's tenant views are enrolled from the start.

  **Acceptance:** removing an organization filter from a sample project-owned view fails the
  generated isolation lane; the lane fails, not skips, when the role is absent (Tier 2-full).

- [ ] **SA320 — Deliver module resource contracts to user-owned pages through managed hooks.**

  Closes arch `generated-file-ownership-unmodeled` (options 1 + 2) and coherence
  `generated-module-branches` and `notifications-anymail-wiring-split` (proposals 1–2, gaps 22 and
  26). Waits for SA316 so every new managed output is watched from its first release.

  **Slices:**
  - [ ] (a) Generate `quickscaleSeam.hooks` plus payload types per installed module from its
    manifest; move `CrmPage.tsx`'s section paths and `CrmStats` into it; extend the closed-world
    check to reject a module resource subpath or payload type in a user-owned file, with the
    managed hook as its passing control. Changing a module endpoint subpath then produces no
    `project_contract.yml` step and no user-owned diff (Tier 2-full).
  - [ ] (b) After (a), move the remaining theme pages' module paths and types onto the generated
    hooks; the closed-world check passes over the full theme (Tier 2-full).
  - [ ] (c) Move the per-module branches in core templates (admin index, CI/Makefile, Compose,
    base settings, the notifications `ANYMAIL` block) into module-declared manifest blocks or a
    managed generic block; the rule 37 scan catches single-name branches and the rule 30 scan reads
    core templates, each with its fixture controls (Tier 2-full).

- [ ] **SA321 — Make the generated production deployment contract an artifact.**

  Closes arch `generated-deploy-topology-unmodeled`. Default is option 2 — Railway is the supported
  production path — unless the operator declares self-hosted Compose supported, in which case
  option 1 adds a production Compose profile. Either way, decisions record the choice; migrations
  run as a pre-deploy step, not at boot; readiness and liveness are separate; and production
  refuses `FileSystemStorage` media unless an explicit dev flag is set.

  **Acceptance:** a generated deployment test boots production settings and fails on local media
  without the flag; the rendered Railway config runs migrations pre-deploy; README and decisions
  name one production path (Tier 2-full).

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API under the [extension contract](module-extension.md), building on the React pages
  and `/api/properties/` the port carried over. No public API in `listings`, no generic property
  behavior in generated projects. Module-coupled data on new pages comes through the managed hooks
  SA320 (a) generates (arch `generated-file-ownership-unmodeled`), and project-owned tenant views
  run in SA318's isolation lane.

  **Acceptance:** the served documents (per-request head and crawler summary), the sitemap and
  robots views, and the search → detail → inquiry journey with organization isolation pass on the
  deployed site, and the extension/tenant declarations pass in `manage.py check`.

  **Slices:**
  - [ ] (h) Close only served-head, crawler-summary, sitemap and robots gaps in the
    project; request-level crawler tests pass with the existing React build (Tier 2-full).
  - [ ] (j) After (h), SA318 and SA320 (a), close search → detail → inquiry gaps; test organization
    isolation under the restricted role and the extension declarations, with module data accessed
    through managed hooks (Tier 2-full).
  - [ ] (f) After (j) and SA191d (production), deploy and re-prove that journey on the live site
    with operator approval and a tested deploy-revert path (Tier 2-full).

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Tier 1 inventory review only: promote reusable property/React pages, translations, maps,
  saved searches, profiles, syndication, media, paid placement, cross-links or full-text search
  only for a concrete consumer, with bounded acceptance, dependencies and a track. Otherwise
  drop the item. Tenant schema changes use incremental migrations on the frozen history.

### Track 2 — cutover and module runtime defects

**SA191d context.** Old `bap-web` (`~/code/bap-web-old`) serves production on Railway project
`bap-web` with no users and no production submissions. The regenerated `bap-web` (`~/code/bap-web`)
declares `auth`, `listings`, `forms`, `analytics`, `notifications`, `orgs`, and `storage`, the
`properties` app, and the six BAP forms. The cutover runs **in place**: per environment, a new
PostgreSQL 18 service restored from `~/bap-cutover/new-2026-10-22.dump`, new variables, and a
force-push over the unrelated history (kept as `legacy-main`, `legacy-develop`, `v-legacy`); the
old PostgreSQL 17 service stays as the rollback until acceptance, and DNS is never touched.
`develop` already runs it. The procedure and its run record are `bap-web/CUTOVER.md`. Secrets
live in `~/bap-cutover/` (mode 600), never printed or committed. After Railway's 2026-10-21
incident every old variable is exposed: none is carried, and the old PostgreSQL 17 credentials
are retired after the cutover. A QuickScale defect follows the release re-entry loop; a project
defect is fixed in `bap-web`. The module fixes below reach `bap-web` through its next ordinary
update; the cutover does not wait for them.

- [x] **SA327 — Raise module dependency floors past open Dependabot advisories.**

- [ ] **SA191d — Cut over production to the regenerated `bap-web` in place (delegated, operator-gated).**

  One slice per session, each ending with a handoff note in `bap-web/docs/`. Every push, Railway
  change, and restore is an operator gate. **Production acceptance:** on `https://buenosairesproperties.com`,
  `/healthcheck/` prints `OK`, `/` and `/contact` render, a form submitted logged in and
  anonymously reaches `info@buenosairesproperties.com` through Resend, `/admin/` lists it, and
  the old PostgreSQL 17 service and legacy refs exist for rollback. Ticket completion also
  requires (retire), after which the dump and legacy refs remain as recovery artifacts.

  **Slices:**
  - [ ] (re-proof) Push the updated `bap-web` to `develop` and re-pass the acceptance there with
    CI green and both dependency audits clean apart from the recorded dev-only exception
    (Tier 2-fast).
  - [ ] (production) After re-proof and operator approval, execute `CUTOVER.md` § S4 steps 1–5;
    pass the production acceptance above, retaining the old database and legacy refs.
    **Tier 3: plan review required** — the production database/credential switch can lose data
    or expose credentials; review restore validation and rollback before execution.
  - [ ] (retire) After production acceptance and a separate operator gate, execute § S4 step 6:
    delete the develop Resend webhook and old PostgreSQL 17 service, retire exposed credentials,
    then rename the new service/volume after 48 hours; verify health and the retained dump/refs.
    **Tier 3: plan review required** — deleting the old database irreversibly removes live rollback.

- [ ] **SA310 — Fix the subscription Checkout S1 and apply billing webhooks in provider order.**

  Closes tech `billing-subscription-checkout-metadata-key-too-long` (S1) and
  `billing-webhook-status-applied-out-of-order`. Ordering strategy (re-fetch the provider object,
  or a version column needing a new migration on the frozen history) is settled in planning; both
  share `_settings.py` and the webhook tests.

  **Acceptance:** every constant used as a Stripe metadata key is ≤40 characters by test; a
  subscription Checkout succeeds against a Stripe test-mode contract test when credentials exist;
  replaying an older subscription or invoice event after a newer one leaves the newer status
  (Tier 2-full).

- [ ] **SA311 — Close the S2 tenant-boundary defects in CRM, orgs, storage and forms.**

  Closes tech `crm-deal-owner-cross-tenant`, `orgs-admin-can-demote-owner`,
  `media-s3-fixed-path-overwrite`, and `forms-null-optional-field-500`. Each fix tightens an
  existing boundary along the audit's stated fix; none widens access.

  **Acceptance:** a deal owner from another organization is rejected and its name never
  serialized; an ADMIN cannot demote or remove an OWNER through the form or the API; two
  organizations uploading the same filename to a fake S3 backend get distinct keys; a JSON `null`
  in an optional public form field is stored empty or rejected with 400, never 500 (Tier 2-full).

- [ ] **SA314 — Make billing credits, Checkout and gates idempotent and tenant-correct.**

  Closes tech `billing-invoice-payment-failed-unscoped`, `billing-zero-credit-plan-webhook-loop`,
  `billing-credit-services-missing-org-scope`, `billing-debit-not-idempotent`,
  `billing-checkout-double-submit`, and coherence `billing-feature-gate` and
  `billing-admin-org-filter` (proposals 4–5, gap 25).

  **Slices:**
  - [ ] (a) Webhooks and credits: guard failed invoices by billing reason and subscription id;
    end the zero-credit `invoice.paid` retry; wrap `credit_user`/`debit_user` in `org_scope`; add a
    debit reference with a unique constraint in a new migration. Tests cover a no-context thread
    and a retried debit (Tier 2-full).
  - [ ] (b) After (a), reuse the open purchase reservation on a repeated POST;
    `require_org_feature` returns the QuickScale error shape with a stable code; billing's tenant
    admins show the organization column and filter; detectors carry the audit's controls
    (Tier 2-full).

- [ ] **SA315 — Close orgs and auth lifecycle defects.**

  Closes tech `orgs-bulk-delete-leaves-zero-owners`, `orgs-admin-org-delete-blocked`,
  `orgs-slug-new-shadows-route`, `auth-profile-email-change-desync`, `auth-deletion-logs-pii`, and
  coherence `orgs-invitation-notification-failure` (proposal 15). Q2 default: best-effort — the
  invitation stays, and the send failure is logged and surfaced, never a 500.

  **Slices:**
  - [ ] (a) Orgs: bulk deletion cannot leave an organization ownerless; admin organization
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

- [x] **SA313 — Run backup dump and restore under the backup role, not the runtime role.**

- [ ] **SA316 — Extend the contract-vintage gate to the runtime surface and managed outputs.**

  Closes arch `contract-vintage-boundary-blind` (option 1, with option 2 deciding what counts as a
  step). The watched set derives from the emission mapping plus `quickscale_core.runtime`'s public
  modules, and every `quickscale_managed` output is hashed or declared unmanaged.

  **Acceptance:** a change shaped like `936b8d0b` fails without a step; an internal refactor
  passes; a local edit under `quickscale_managed/` appears in `status` (Tier 2-full).

- [ ] **SA317 — Give apply state one owner and close the CLI command defects.**

  Closes arch `apply-state-dual-owner` (option 1) and tech `cli-remove-accepts-path-traversal`,
  `cli-apply-force-never-forces`, and `beta-migrate-existing-recipient-no-dirty-guard`.

  **Slices:**
  - [ ] (a) The recovery ledger keeps the checkpoint and resume pointer only; resume reads
    `state.yml`. A fault-injection test kills after step 4, resumes, and asserts `managed_files`
    and contract steps survive and an edited managed file is still detected (Tier 2-full).
  - [ ] (b) `remove` validates the module name against state and asserts the target is inside
    `modules/`; `apply --force` stages and swaps or the flag is removed; `--existing-recipient`
    refuses a dirty tracked recipient (Tier 2-fast).

- [ ] **SA319 — Update modules as one sealed-tag transaction.**

  Closes arch `module-upgrade-no-reconciler` (option 1, option 2 as the transition guard). Needs
  SA317's single state owner so the journal is not a third writer.

  **Slices:**
  - [ ] (a) Update resolves and verifies the sealed `splits/<module>/<version>` tag before the
    first pull and refreshes `poetry.lock`; a release gate asserts each split branch tip and sealed
    tag share a tree (Tier 2-full).
  - [ ] (b) After (a), an update journal commits the module set once with one state write; a test
    that kills between modules resumes to one coherent set (Tier 2-full).

- [ ] **SA322 — Make backup restore safe and its recovery point coherent.**

  Closes tech `backups-restore-drops-own-artifact-row`, `backups-prune-no-keep-last`,
  `backups-restore-not-atomic`, `backups-creation-lock-expires-live`,
  `backups-validate-action-view-permission`, `backups-dump-files-world-readable`,
  `backups-filename-second-resolution-collision`, and arch `backup-restore-incoherent` (option 1).
  The one-way artifact-format choice is made once in (b), behind a manifest version; later format
  changes are version bumps.

  **Slices:**
  - [ ] (a) Restore safety: the artifact row survives a restore and a metadata failure is
    visible; prune always keeps the newest valid snapshot; restore runs in one transaction or
    behind a pre-restore safety dump; the create lock stays held for the run, proven by a
    long-backup test (Tier 2-full).
  - [ ] (b) After (a), decisions record the artifact format; the manifest carries a version and
    project-app migration hashes; restore refuses an unknown version or a hash mismatch; the S4
    permission, file-mode and filename fixes ride along (Tier 2-full).
  - [ ] (c) After (b), capture media or an immutable media manifest per the recorded format, and
    hold a restore advisory lock; a DB + media + project-schema drill restores the captured set,
    and a killed restore leaves no partial database (Tier 2-full).

- [ ] **SA325 — Make module settings, defaults, messages and READMEs follow one contract.**

  Closes coherence `manifest-declared-surface`, `duplicated-default-constants`,
  `stale-version-error-strings`, and `readme-extending-contract` (proposals 3, 9, 12, 14; gaps 24,
  27, 30–31). Q1 default: `storage.private_media_enabled` is rejected as not supported until
  private-media authorization exists. Q3 default: the five Extending items are mandatory.

  **Acceptance:** every accepted manifest option has a live consumer; code constants derive from
  manifest defaults; no module source message names a release; all twelve READMEs answer the five
  Extending questions; each detector carries the audit's fixture controls (Tier 2-full).

- [ ] **SA326 — Wire the unwired release and security gates.**

  Closes the tech audit's tooling gaps for gate wiring and coherence gap 21: register
  `security-negative-probes`; run `check-module-seals` and `sync_migration_hashes.py --check` in CI;
  wire `check_generated_workflow_lint.py`; remove the coverage `QUIET` bypasses so CI and `make`
  share commands; reject a class-level `csrf_exempt` dispatch and the `from … import current_org`
  form in their gates; scan git history for secrets with justified, expiring suppressions; make
  rule 17's destructive duty key on computed operations.

  **Acceptance:** each newly wired gate runs in CI and `make check`, and each tightened gate fails
  its fixture control (Tier 2-full).

- [ ] **SA277 — Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt.**

  Addresses the upgrade-path part of arch `generated-file-ownership-unmodeled`; managed
  resource hooks are SA320's and SA153's scope. One path in two stages:
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

**Unscheduled — React-theme browser coverage (Track 1, Tier 2-full per ordered slice).**
When activated: (A) wire `pnpm test:e2e` into generated CI and prove the existing smoke;
(B) add named journeys with passing browser checks; (C) add a depth-capped link crawler with
bounded traversal tests; (D) run the journeys on Docker within the E2E budget. Each consumes
its predecessor; no open-ended full-site crawl.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
