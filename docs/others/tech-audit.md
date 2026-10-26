# Technical Audit — Open Items

Audited: `82ff3e7d141cf943ab900eaae5f214c0edfc9e07` (v89) · 2026-10-24 · working tree dirty · repository public · prompt: deep-technical-audit v8

Source snapshot: HEAD `82ff3e7d` plus one unstaged change, `docs/others/arch-audit.md` (the companion
audit's uncommitted deliverable; excluded from the source basis, digest
`005a0098741f58eb06134459ee7324793b9d9d9dfa779835355d1fc04b52e58d`). No staged and no untracked
inputs. No drift between orientation and delivery. This file is the single source of truth for
defects that are found but not yet fixed. Cite a finding by its slug ID; section numbers are not
stable.

**Fix record (2026-10-24).** SA312 closes six findings recorded below; their entries keep the
audit evidence and now carry `status: fixed`:
`generated-compose-called-production-runs-debug`,
`generated-redis-cache-missing-client`, `dockerignore-bakes-local-backups`,
`generated-readme-examples-invalid`, `e2e-generated-ci-contract-stale-grep`, and
`publish-pypi-no-skip-existing`. The live ticket state is in
[the roadmap](../technical/roadmap.md).

**Fix record (2026-10-24).** SA317 closes three findings recorded below; their entries keep the
audit evidence and now carry `status: fixed`:
`cli-remove-accepts-path-traversal`, `cli-apply-force-never-forces`, and
`beta-migrate-existing-recipient-no-dirty-guard`.

**Fix record (2026-10-25).** SA322 (a) closes four findings recorded below; their entries keep the
audit evidence and now carry `status: fixed`:
`backups-restore-drops-own-artifact-row`, `backups-prune-no-keep-last`,
`backups-restore-not-atomic`, and `backups-creation-lock-expires-live`.

**Fix record (2026-10-25).** SA322 (b) closes the remaining S4 backup findings; their entries keep
the audit evidence and now carry `status: fixed`: `backups-validate-action-view-permission`,
`backups-dump-files-world-readable`, and `backups-filename-second-resolution-collision`.

**Fix record (2026-10-25).** SA322 (c) closes the arch `backup-restore-incoherent` recovery-point
finding: backups capture their media bytes with checksums, media sync restores that captured set,
and restore holds an advisory lock; a failed restore leaves the target database unchanged. It also
resolves the `media-sync-manifest-traversal` watchlist entry by rejecting a `..` segment at the
capture, sync and restore boundary.

**Fix record (2026-10-26).** SA310 closes two findings recorded below; their entries keep the
audit evidence and now carry `status: fixed`:
`billing-subscription-checkout-metadata-key-too-long` and
`billing-webhook-status-applied-out-of-order`. The subscription Checkout reference key is
`quickscale_sub_checkout_reference` (33 characters), and subscription and invoice webhooks read
the provider's current subscription under the organization's provider mutex before applying its
status.

**Fix record (2026-10-26).** SA311 closes four findings recorded below; their entries keep the
audit evidence and now carry `status: fixed`: `crm-deal-owner-cross-tenant`,
`media-s3-fixed-path-overwrite`, `orgs-admin-can-demote-owner`, and
`forms-null-optional-field-500`. A deal owner must be a member of the request organization and a
foreign owner's name is not serialized; a member mutation cannot target a role above the actor's;
cloud uploads allocate a unique key per save (with provider overwrite disabled as a second guard);
and a JSON `null` in an optional public form field is stored empty on both persistence branches.

## Orientation summary

QuickScale is a Python 3.14 / Django 6.0 **project generator and first-party module platform**: a CLI
(`quickscale_cli`) plans and applies projects, `quickscale_core` holds the generator templates,
manifest engine, runtime seams, and DR engine, and twelve Django modules (`quickscale_modules/*`)
ship as vendored runtime dependencies. There are **three deployment realities**: (a) **generated
projects**, internet-facing Django apps on Railway or self-hosted Docker, PostgreSQL 18 with FORCE
RLS through a `NOSUPERUSER`/`NOBYPASSRLS` runtime role; (b) **the maintainer toolchain**, run locally
and in GitHub Actions against this repository; and (c) the previously documented **self-hosted
Compose** "production" path, which was in fact the dev stack (finding
`generated-compose-called-production-runs-debug`, since corrected in the README). Repository
visibility: **public**
(`github.com/Experto-AI/quickscale`); there is no `SECURITY.md`, so the disclosure rule is applied.
Entry points: module HTTP/DRF views, Stripe and Svix webhooks, management commands with a `--trigger`
provenance, the CLI, the generator, and GitHub Actions. Actors: anonymous visitors, org members
(viewer/member/admin/owner), platform operators (superusers), schedulers, maintainers, and hostile
uploaded content. Crown jewels: cross-tenant data behind RLS, billing state and money movement,
credentials referenced by `*_env_var` options, backup/restore, and the release pipeline.
Configuration axes: per-module `enabled`, org mode `solo`/`saas`, `RUNTIME_DATABASE_URL` set/blank,
`QUICKSCALE_ALLOW_BYPASSRLS`, trusted-proxy settings, `REDIS_URL`, storage backend
(`local`/`s3`/`r2`), backups `target_mode`/`automation_enabled`, and replica count. Tooling baseline:
ruff, mypy, module-conventions harness, migration-freeze and coverage gates, actionlint (unwired),
Bandit/zizmor/Trivy scripts; no image-layer or IaC scanning in CI. Scope: full repository; depth on
generated-project templates, billing, orgs, backups, auth, CRM, storage/blog/forms, the CLI, the DR
engine, and the release pipeline. The generated-project surface has the largest blast radius because
users deploy it.

**Oracle list (declared invariants checked during the sweep).**

- Module Conventions: setting names, identity stems, public surfaces, tenant-model markers,
  authorization rules, command contracts (rules 1, 2, 4, 9, 19, 24, 26, 28, 31, 33, 41, 44).
- Orgs: the purge is atomic and fails closed on undischarged obligations; an organization always has
  an owner; RLS is FORCE-enabled for enrolled tenant tables.
- Notifications: forward-only delivery-status contract; Svix signature over the raw body.
- Forms: retention nulls the IP and clears the user agent; public submissions resolve the System org.
- Billing: Stripe API version `2026-06-24.dahlia`; webhook idempotency; one current subscription per
  organization; ownership-only checkout.
- Backups: PostgreSQL-18 custom dumps are the recovery path; restore is guarded by exact filename
  confirmation and the environment gate; capture is one coherent recovery point (the architectural
  audit's F6 states the stricter promise).
- Generated projects: `production.py` fails closed on SECRET_KEY, DB URL, hosts, cookies, and proxy
  trust; `start.sh` is the deployment command; `Dockerfile` is non-root.
- Module conventions and the generated-project contract are enforced by repository gates, not by
  prose alone.

**Data sensitivity.** Personal data: form submissions (IP, user agent, field values), account and
org-member identity, billing customer details and Stripe webhook payloads, email recipients, and
author/avatar data. Tenant business data: CRM contacts/deals, listings, blog content, credit ledgers.
Credentials are referenced by environment-variable name (Stripe, Resend/Svix, AWS, backups private
remote), never stored as values in first-party code; generated `db/init.sql` and `.env.example` carry
a fixed local runtime-role password (see the Compose finding). Backups contain the full database.
Severity calls for leak-shaped findings use this context.

**Guarantees and supported platforms.** RLS tenant isolation under a `NOSUPERUSER`/`NOBYPASSRLS`
role; atomic org purge with a tombstone; once-only webhook processing per Stripe event id; forward-only
notification delivery status; retention anonymization; PostgreSQL 18 custom-format backup/restore with
migration-content compatibility; Python 3.14, Django 6.0, PostgreSQL 18; `WEB_CONCURRENCY`/`GUNICORN_WORKERS`
may exceed one (supported mode). Unknowns: production `WEB_CONCURRENCY`, whether the live generated
project uses the backups engine, and whether self-hosted Compose is a supported production path; these
are named in the Questions section.

**Hotspot measurements.** The 12-month churn query returned 3,787 non-merge commits and 681
fix-message commits. After filtering merges, subtree-split replays, lockfiles, generated output, and
docs, the top files are still docs (`docs/technical/roadmap.md` 251, `decisions.md` 62), tests, and
`pyproject.toml`; production source is diffuse. Subtree-split replays and docs-heavy history make
fix-density unreliable in this repository, so the §2f delta replaced the churn ranking. The global
defect-gravity query was run over the delta only for candidate seeding; its output is not used as a
finding.

**Delta classification.** `39d455ef..HEAD` contains 94 commits: 46 `v89: SAnnn` review-tracked
tickets, 17 `docs:` commits, 4 roadmap commits, and 27 subtree-split replays and merges.
No housekeeping-labelled commit changed first-party production semantics. The dependency-pin refresh
(SA308) is review-tracked. Test hunks were diffed: assertions increased (218 added vs 19 removed in
test files); no deleted test file, no new unlinked `skip`/`xfail`, and no inverted expectation found.
The one release-pipeline regression the sweep found (`e2e-generated-ci-contract-stale-grep`) predates
the delta (SA253, 2026-10-10); it is not an unreviewed delta change.

### Coverage and residual risk

- **Read in full (unit-level, by the main agent and the delegated units):** all source of
  `quickscale_modules/billing` (35 files), `orgs` (57), `backups` (source, commands, persistence,
  admin), `auth`, `crm`, `forms`, `storage`, `blog` (storage/upload paths), `notifications` (webhook
  path), `social`/`listings`/`analytics` (status paths), `quickscale_cli/commands`, the generator
  (`generator.py`, emission mapping, manifests, templates), `quickscale_core/runtime`, and the DR
  engine; generated settings, Dockerfile, Compose, `start.sh`, README/OPERATIONS, CI templates;
  `.github/workflows/*.yml`; the security/quality gate scripts named in the tooling section.
- **Sampled:** the React theme UI, `quickscale_devtools` outside the beta-migration path, the
  `scripts/module_conventions` harness, migrations beyond constraints/RLS targets, and the docs tree.
- **Skipped:** `bap-web` (external deployment), real Stripe/S3/Railway services, the full test suite,
  Playwright/E2E, the frontend bundle, and a fresh dependency audit. The prior accepted postcss
  advisory was re-read, not re-run.
- **Audit tools:** no dependency auditor was run this pass. The Python lockfile changed in the
  review-tracked SA308 refresh, so the prior "no new advisories" claim is **not** re-established
  here; the JS lockfile still carries the accepted postcss dev-only exception. A fresh `pnpm audit`
  / `pip-audit` is residual risk. `ruff`/`mypy` were not run because the sweep is read-only and the
  repository's gates are not the audit's subject. `git grep`,
  `git log/blame`, and read-only AST inspection were used. Empirical checks: (1) a scratch
  PostgreSQL 18.6 container created and destroyed by the audit proved `pg_dump` fails on a FORCE-RLS
  table as a `NOBYPASSRLS` non-owner (`query would be affected by row-level security policy`) and
  `pg_restore --clean` fails as a non-owner (`must be owner of table`), confirming
  the backup-role finding (resolved as SA313); (2) `get_generator_emission_mapping()` in a read-only Python
  process proved the generator emits both `.env` and `.env.example`; (3) length checks proved the
  Stripe metadata key is 42 characters; (4) source reads confirmed the S3 overwrite default and the
  allauth email lookup. No repository code was executed except the read-only mapping call in a
  trusted checkout.
- **Category activation:** active: I, II, III, IV, V, VI, VII, VIII, IX, X · inert: none (the ML/LLM,
  firmware, and native/FFI blocks were marked inert because §2 found no such surface) · archetypes:
  code/config generator, CLI, library, service/webhook, multi-tenant, data-ish pipeline.
- **§3b scenarios:** *committed, reply lost* — traced for billing checkout/debit and Stripe/Svix
  webhooks; findings `billing-checkout-double-submit`, `billing-debit-not-idempotent`; *interrupted
  between steps* — traced for backup restore and apply; findings `backups-restore-not-atomic`,
  `backups-restore-drops-own-artifact-row`, `cli-apply-force-never-forces`; *old work resumes* —
  traced for webhook ordering and the backup lease; findings `billing-webhook-status-applied-out-of-order`,
  `backups-creation-lock-expires-live`; *authority or data withdrawn* — traced for org roles, email
  change, and purge; findings `orgs-admin-can-demote-owner`, `auth-profile-email-change-desync`;
  *dependency slow or unavailable* — not traced in depth; the prior `single-sync-worker-vendor-calls`
  watchlist remains, and the synchronous Stripe webhook path is now noted in the chain of the ordering
  finding; *versions or environments differ* — traced for Redis (`generated-redis-cache-missing-client`),
  PostgreSQL tooling (backup finding), and module split/vintage (prior watchlist).
- **What this silence does not cover:** real Railway/Firebase/Stripe/S3 behavior, production
  environment values (`WEB_CONCURRENCY`, `REDIS_URL`, whether backups run), browser/UI behavior,
  Docker image scanning, dependency advisories beyond the carried exception, and the skipped
  subsystems above. A clean category here is not evidence of a clean deployment.

## Machine-readable index

```yaml
schema: tech-audit/v6
audited: 82ff3e7d141cf943ab900eaae5f214c0edfc9e07
items:
  - {id: billing-subscription-checkout-metadata-key-too-long, status: fixed, severity: S1, category: IX,
     title: "Subscription Checkout metadata key exceeds Stripe's 40-character limit", effort: Trivial,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_settings.py,
               quickscale_modules/billing/src/quickscale_modules_billing/_subscription_checkout_steps.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: crm-deal-owner-cross-tenant, status: fixed, severity: S2, category: III,
     title: "Deal owner accepts a foreign-tenant user id and the list serializes that user's name",
     effort: Small, confidence: High, reality: generated-project,
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/serializers.py,
               quickscale_modules/crm/src/quickscale_modules_crm/views.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: media-s3-fixed-path-overwrite, status: fixed, severity: S2, category: III,
     title: "Fixed upload paths plus S3 overwrite replace another user's or tenant's media", effort: Small,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/storage/src/quickscale_modules_storage/adapter.py,
               quickscale_modules/listings/src/quickscale_modules_listings/models.py,
               quickscale_modules/blog/src/quickscale_modules_blog/models.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: orgs-admin-can-demote-owner, status: fixed, severity: S2, category: III,
     title: "An org ADMIN can demote or remove an OWNER through the member API", effort: Small,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/_view_org_management.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/forms.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/_api_views.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: generated-compose-called-production-runs-debug, status: fixed, severity: S2, category: X,
     title: "The generated README calls the dev Compose stack production; it runs runserver with DEBUG=True",
     effort: Small, confidence: High, reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/README.md.j2,
               quickscale_core/src/quickscale_core/generator/templates/docker-compose.yml.j2,
               quickscale_core/src/quickscale_core/generator/templates/project_name/settings/local.py.j2],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: generated-redis-cache-missing-client, status: fixed, severity: S2, category: VI,
     title: "Selecting the recommended Redis cache fails at first use: the redis client is not a project dependency",
     effort: Trivial, confidence: High, reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/project_name/settings/production.py.j2,
               quickscale_core/src/quickscale_core/generator/templates/pyproject.toml.j2],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: forms-null-optional-field-500, status: fixed, severity: S2, category: I,
     title: "A JSON null in an optional public form field raises IntegrityError and 500", effort: Trivial,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/forms/src/quickscale_modules_forms/serializers.py,
               quickscale_modules/forms/src/quickscale_modules_forms/views.py,
               quickscale_modules/forms/src/quickscale_modules_forms/models.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: billing-webhook-status-applied-out-of-order, status: fixed, severity: S2, category: II,
     title: "Subscription and invoice webhooks apply payload status without provider ordering", effort: Medium,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_subscription_events.py,
               quickscale_modules/billing/src/quickscale_modules_billing/_webhooks_invoice.py,
               quickscale_modules/billing/src/quickscale_modules_billing/models.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: billing-invoice-payment-failed-unscoped, status: open, severity: S3, category: IX,
     title: "invoice.payment_failed with no subscription id marks the customer's current subscription past due",
     effort: Trivial, confidence: High, reality: generated-project,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_webhooks_invoice.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: billing-credit-services-missing-org-scope, status: open, severity: S3, category: III,
     title: "credit_user/debit_user fail under FORCE RLS outside a request context", effort: Small,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_credits.py,
               quickscale_modules/billing/README.md],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: billing-debit-not-idempotent, status: open, severity: S3, category: II,
     title: "A retried usage debit double-spends credits", effort: Medium, confidence: High,
     reality: generated-project,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_credits.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: billing-checkout-double-submit, status: open, severity: S3, category: II,
     title: "A second purchase Checkout POST creates a second payable session", effort: Small,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_checkout.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: backups-restore-drops-own-artifact-row, status: fixed, severity: S3, category: IX,
     title: "A successful restore removes the artifact row for the backup it restored and leaves the snapshot PENDING",
     effort: Medium, confidence: High, reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_capture.py,
               quickscale_modules/backups/src/quickscale_modules_backups/persistence.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: backups-prune-no-keep-last, status: fixed, severity: S3, category: IX,
     title: "Retention can delete the last remaining recovery point", effort: Trivial, confidence: High,
     reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_prune.py,
               quickscale_modules/backups/src/quickscale_modules_backups/persistence.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: backups-restore-not-atomic, status: fixed, severity: S3, category: IV,
     title: "pg_restore --clean has no single-transaction or pre-restore safety dump", effort: Medium,
     confidence: High, reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/primitives.py,
               quickscale_core/src/quickscale_core/dr_engine/recovery.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: backups-creation-lock-expires-live, status: fixed, severity: S3, category: II,
     title: "The backup-create lock is a 300 s mtime lease and expires under a live backup", effort: Small,
     confidence: High, reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_lock.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: auth-profile-email-change-desync, status: open, severity: S3, category: III,
     title: "Profile email change updates User.email but not allauth EmailAddress", effort: Small,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/auth/src/quickscale_modules_auth/forms.py,
               quickscale_modules/auth/src/quickscale_modules_auth/_profile_views.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: cli-remove-accepts-path-traversal, status: fixed, severity: S3, category: X,
     title: "quickscale remove joins an unvalidated module argument into modules/ and rmtree()s it",
     effort: Trivial, confidence: High, reality: maintainer-toolchain,
     anchors: [quickscale_cli/src/quickscale_cli/commands/remove_command.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: dockerignore-bakes-local-backups, status: fixed, severity: S3, category: III,
     title: "Generated .dockerignore omits .quickscale/backups, so local DB dumps enter the image",
     effort: Trivial, confidence: High, reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/.dockerignore.j2,
               quickscale_core/src/quickscale_core/generator/templates/Dockerfile.j2],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: cli-apply-force-never-forces, status: fixed, severity: S3, category: I,
     title: "apply --force still aborts on a non-empty directory without quickscale.yml", effort: Small,
     confidence: High, reality: maintainer-toolchain,
     anchors: [quickscale_cli/src/quickscale_cli/commands/_generation.py,
               quickscale_core/src/quickscale_core/generator/generator.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: e2e-generated-ci-contract-stale-grep, status: fixed, severity: S3, category: VII,
     title: "The E2E workflow greps for mutable action tags that the generated workflow no longer contains",
     effort: Trivial, confidence: High, reality: maintainer-toolchain,
     anchors: [.github/workflows/e2e.yml,
               quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: publish-pypi-no-skip-existing, status: fixed, severity: S3, category: VII,
     title: "A partial PyPI publish cannot be resumed", effort: Trivial, confidence: High,
     reality: maintainer-toolchain,
     anchors: [.github/workflows/publish.yml], depends_on: [], chain: [],
     first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: media-image-decode-before-dimension-cap, status: open, severity: S3, category: IV,
     title: "Upload validation decodes the full image before checking its dimensions", effort: Small,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/storage/src/quickscale_modules_storage/_helpers.py,
               quickscale_modules/blog/src/quickscale_modules_blog/services.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: orgs-bulk-delete-leaves-zero-owners, status: open, severity: S3, category: II,
     title: "Bulk deletion of co-owners passes per-row checks and leaves the org ownerless", effort: Medium,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/receivers.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/models.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: orgs-admin-org-delete-blocked, status: open, severity: S4, category: II,
     title: "Admin deletion of an organization with a sole owner and other members is blocked",
     effort: Small, confidence: High, reality: generated-project,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/receivers.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/admin.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: orgs-slug-new-shadows-route, status: open, severity: S4, category: I,
     title: "An org with slug new cannot reach its dashboard", effort: Trivial, confidence: High,
     reality: generated-project,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/_constants.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/urls.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: backups-validate-action-view-permission, status: fixed, severity: S4, category: III,
     title: "The Validate selected backups admin action lacks change permission", effort: Trivial,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/backups/src/quickscale_modules_backups/_admin_artifact.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: backups-dump-files-world-readable, status: fixed, severity: S4, category: IX,
     title: "Dump and sidecar files inherit the process umask", effort: Trivial, confidence: High,
     reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_paths.py,
               quickscale_core/src/quickscale_core/dr_engine/_capture.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: backups-filename-second-resolution-collision, status: fixed, severity: S4, category: II,
     title: "Unique backup filenames have one-second resolution", effort: Trivial, confidence: High,
     reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_paths.py,
               quickscale_modules/backups/src/quickscale_modules_backups/models.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: forms-csv-export-materializes-all-values, status: open, severity: S4, category: V,
     title: "CSV export builds the whole field-value table in memory", effort: Small, confidence: High,
     reality: generated-project,
     anchors: [quickscale_modules/forms/src/quickscale_modules_forms/views.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: forms-option-values-not-validated, status: open, severity: S4, category: IX,
     title: "Select/radio/checkbox values are not checked against options", effort: Trivial,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/forms/src/quickscale_modules_forms/serializers.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: generated-readme-examples-invalid, status: fixed, severity: S4, category: X,
     title: "Generated README examples use invalid YAML, clobber the generated .env, and miss the Vite output in .gitignore",
     effort: Small, confidence: High, reality: generated-project,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/README.md.j2,
               quickscale_core/src/quickscale_core/generator/templates/.env.example.j2,
               quickscale_core/src/quickscale_core/generator/templates/.gitignore.j2],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: billing-zero-credit-plan-webhook-loop, status: open, severity: S4, category: I,
     title: "A zero-credit plan makes invoice.paid fail and retry forever", effort: Trivial,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_webhooks_invoice.py,
               quickscale_modules/billing/src/quickscale_modules_billing/_credits.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: auth-deletion-logs-pii, status: open, severity: S4, category: IX,
     title: "Account-deletion failure paths log the user's name and org names", effort: Trivial,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/auth/src/quickscale_modules_auth/views.py,
               quickscale_modules/auth/src/quickscale_modules_auth/_account_deletion_providers.py],
     depends_on: [], chain: [], first_seen: 2026-10-24, last_verified: 2026-10-24}
  - {id: beta-migrate-existing-recipient-no-dirty-guard, status: fixed, severity: S4, category: X,
     title: "--existing-recipient overwrites a git-tracked recipient with no dirty-tree check",
     effort: Small, confidence: High, reality: maintainer-toolchain,
     anchors: [quickscale_devtools/src/quickscale_devtools/beta_migration/execution.py],
     depends_on: [], chain: [], first_seen: 2026-10-20, last_verified: 2026-10-24}
  - {id: notifications-message-status-aggregate-race, status: open, severity: S4, category: II,
     title: "Concurrent sibling-delivery webhooks leave the message aggregate stale", effort: Trivial,
     confidence: Medium, reality: generated-project,
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/_delivery.py],
     depends_on: [], chain: [], first_seen: 2026-10-20, last_verified: 2026-10-24}
  - {id: forms-retention-skips-null-ip-rows, status: open, severity: S4, category: IX,
     title: "Retention never clears user_agent on submissions stored without an IP", effort: Trivial,
     confidence: High, reality: generated-project,
     anchors: [quickscale_modules/forms/src/quickscale_modules_forms/management/commands/_retention.py],
     depends_on: [], chain: [], first_seen: 2026-10-20, last_verified: 2026-10-24}
  - {id: orgs-role-mixin-checks-request-org, status: watchlist}
  - {id: backups-upload-restore-by-model-permission, status: watchlist}
  - {id: single-sync-worker-vendor-calls, status: watchlist}
  - {id: migrate-runs-per-replica, status: watchlist}
  - {id: social-config-error-served-200, status: watchlist}
  - {id: account-deletion-hook-exception-text, status: watchlist}
  - {id: deploy-existing-settings-module-never-corrected, status: watchlist}
  - {id: generated-project-automation-local-only, status: watchlist}
  - {id: orgs-provider-id-check-blocks-migrate, status: watchlist}
  - {id: crm-stage-seed-lost-on-commit-failure, status: watchlist}
  - {id: development-workflow-intermittent-root-500, status: watchlist}
  - {id: core-e2e-poetry-cache-install-candidates, status: watchlist}
  - {id: orgs-contextvar-leak-on-db-error, status: watchlist}
  - {id: orgs-personal-membership-not-owner, status: watchlist}
  - {id: orgs-purge-unclassified-models, status: watchlist}
  - {id: tenant-admin-org-selector, status: watchlist}
  - {id: billing-webhook-payload-retention, status: watchlist}
  - {id: billing-provider-erasure, status: watchlist}
  - {id: billing-refunds-disputes, status: watchlist}
  - {id: auth-email-verification-none, status: watchlist}
  - {id: auth-account-deletion-no-reauth, status: watchlist}
  - {id: templates-local-media-production, status: watchlist}
  - {id: templates-healthcheck-liveness, status: watchlist}
  - {id: notifications-pre-signature-db-read, status: watchlist}
  - {id: media-storage-orphans, status: watchlist}
  - {id: backups-artifact-path-trust, status: watchlist}
  - {id: social-cache-bulk-invalidation, status: watchlist}
  - {id: postcss-selector-parser-build-time-advisory, status: accepted}
```

## Summary table

Rows record audit-time severity; current status is in the machine-readable index above.

| ID | Sev | Cat | Title | Effort | Conf | Since |
|---|---|---|---|---|---|---|
| `billing-subscription-checkout-metadata-key-too-long` | S1 | IX | Subscription Checkout metadata key exceeds Stripe's 40-character limit | Trivial | High | new |
| `crm-deal-owner-cross-tenant` | S2 | III | Deal owner accepts a foreign-tenant user id and leaks the name | Small | High | new |
| `media-s3-fixed-path-overwrite` | S2 | III | Fixed upload paths plus S3 overwrite replace another tenant's media | Small | High | new |
| `orgs-admin-can-demote-owner` | S2 | III | An org ADMIN can demote or remove an OWNER | Small | High | new |
| `generated-compose-called-production-runs-debug` | S2 | X | The README calls the dev Compose stack production; it runs DEBUG | Small | High | new |
| `generated-redis-cache-missing-client` | S2 | VI | Redis cache selected without the redis client dependency | Trivial | High | new |
| `forms-null-optional-field-500` | S2 | I | JSON null in an optional public form field raises IntegrityError and 500 | Trivial | High | new |
| `billing-webhook-status-applied-out-of-order` | S2 | II | Webhooks apply payload status without provider ordering | Medium | High | new |
| `billing-invoice-payment-failed-unscoped` | S3 | IX | invoice.payment_failed with no subscription id marks the current subscription past due | Trivial | High | new |
| `billing-credit-services-missing-org-scope` | S3 | III | credit_user/debit_user fail under FORCE RLS outside a request | Small | High | new |
| `billing-debit-not-idempotent` | S3 | II | A retried usage debit double-spends credits | Medium | High | new |
| `billing-checkout-double-submit` | S3 | II | A second purchase Checkout POST creates a second payable session | Small | High | new |
| `backups-restore-drops-own-artifact-row` | S3 | IX | A restore removes the artifact row for the backup it restored | Medium | High | new |
| `backups-prune-no-keep-last` | S3 | IX | Retention can delete the last remaining recovery point | Trivial | High | new |
| `backups-restore-not-atomic` | S3 | IV | pg_restore --clean has no single transaction or pre-restore dump | Medium | High | new |
| `backups-creation-lock-expires-live` | S3 | II | The backup-create lock is a 300 s mtime lease | Small | High | new |
| `auth-profile-email-change-desync` | S3 | III | Profile email change leaves the old allauth address usable | Small | High | new |
| `cli-remove-accepts-path-traversal` | S3 | X | quickscale remove joins an unvalidated module argument and rmtree()s it | Trivial | High | new |
| `dockerignore-bakes-local-backups` | S3 | III | .dockerignore omits .quickscale/backups | Trivial | High | new |
| `cli-apply-force-never-forces` | S3 | I | apply --force still aborts on a non-empty directory | Small | High | new |
| `e2e-generated-ci-contract-stale-grep` | S3 | VII | The E2E workflow greps for tags the generated CI no longer uses | Trivial | High | new |
| `publish-pypi-no-skip-existing` | S3 | VII | A partial PyPI publish cannot be resumed | Trivial | High | new |
| `media-image-decode-before-dimension-cap` | S3 | IV | Upload validation decodes before checking dimensions | Small | High | new |
| `orgs-bulk-delete-leaves-zero-owners` | S3 | II | Bulk deletion of co-owners leaves the org ownerless | Medium | High | new |
| `orgs-admin-org-delete-blocked` | S4 | II | Admin org deletion is blocked by the last-owner receiver | Small | High | new |
| `orgs-slug-new-shadows-route` | S4 | I | An org with slug `new` cannot reach its dashboard | Trivial | High | new |
| `backups-validate-action-view-permission` | S4 | III | The Validate selected backups action lacks change permission | Trivial | High | new |
| `backups-dump-files-world-readable` | S4 | IX | Dump and sidecar files inherit the process umask | Trivial | High | new |
| `backups-filename-second-resolution-collision` | S4 | II | Unique backup filenames have one-second resolution | Trivial | High | new |
| `forms-csv-export-materializes-all-values` | S4 | V | CSV export builds the whole field-value table in memory | Small | High | new |
| `forms-option-values-not-validated` | S4 | IX | Select/radio/checkbox values are not checked against options | Trivial | High | new |
| `generated-readme-examples-invalid` | S4 | X | Generated README examples use invalid YAML and clobber generated files | Small | High | new |
| `billing-zero-credit-plan-webhook-loop` | S4 | I | A zero-credit plan makes invoice.paid retry forever | Trivial | High | new |
| `auth-deletion-logs-pii` | S4 | IX | Account-deletion failure paths log names | Trivial | High | new |
| `beta-migrate-existing-recipient-no-dirty-guard` | S4 | X | --existing-recipient overwrites a tracked recipient | Small | High | carried |
| `notifications-message-status-aggregate-race` | S4 | II | Concurrent sibling webhooks leave the aggregate stale | Trivial | Medium | carried |
| `forms-retention-skips-null-ip-rows` | S4 | IX | Retention skips rows stored without an IP | Trivial | High | carried |

Quick wins (Trivial effort, open S2/S3): `billing-invoice-payment-failed-unscoped`.

## Findings

Findings marked `status: fixed` in the machine-readable index keep the audit-time evidence
below; their `Fix:` text records what the fix required, not outstanding work.

### S1

#### Finding 1: Subscription Checkout metadata key exceeds Stripe's 40-character limit

- **ID:** `billing-subscription-checkout-metadata-key-too-long`
- **Severity:** S1 · **High × Direct** (a paying owner cannot start a subscription; no
  precondition beyond a valid plan/customer) · deployment reality: generated project with billing
  on · oracle: Stripe's documented metadata-key limit; billing's only subscription-start path · no
  unverified assumption.
- **Category:** IX (provider-contract drift; a wrong value at a boundary).
- **Confidence:** High — the key was measured at 42 characters, passed verbatim to the installed
  `stripe 15.3.1` SDK, and Stripe's primary documentation states keys are up to 40 characters.
- **Location:** `quickscale_modules/billing/src/quickscale_modules_billing/_settings.py:61-63`;
  `_subscription_checkout_steps.py:190-193`; `_stripe_client.py:154-163`.
- **Defect:** `_SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY` is
  `"quickscale_subscription_checkout_reference"` (42 characters), and the same dict is passed as
  both the Checkout Session `metadata` and the Subscription `subscription_data.metadata`. Stripe
  rejects keys longer than 40 characters.
- **Failure scenario:** Any org OWNER posts to `/billing/api/subscription/checkout/` with a valid
  `plan_slug`. `_create_and_persist_checkout_session` builds the metadata and calls
  `checkout.Session.create`; Stripe returns an `InvalidRequestError`; the wrapper raises
  `BillingError` and the API answers 500. The authoritative-error path closes the blank reservation,
  and a retry re-creates it and fails again. Purchase checkouts are unaffected (their key is 38
  characters), so a mixed smoke test that only buys credits misses it.
- **Evidence:** `_SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY = ("quickscale_subscription_checkout_reference")`
  (42 chars) and `"metadata": dict(session_metadata), "subscription_data": {"metadata": dict(subscription_metadata)}`.
  Stripe's Metadata reference: "You can specify up to 50 keys, with key names up to 40 characters long".
- **Refutation:** Searched for a local key-length validator, a manifest `max_length`, a serializer
  field, and a startup check; none exists. The Stripe SDK does not pre-validate metadata key length.
  The tests use a fake `create` function and assert metadata contents, never provider validation.
  A grep for a second subscription-create path found none.
- **Fix:** Rename the key to a <=40-character name (for example
  `quickscale_sub_checkout_reference`, 33 chars) in `_settings.py`, and add a tiny assertion/test that
  every constant used as a Stripe metadata key is <=40 characters. **Effort:** Trivial.
- **Fix files:** `_settings.py`; tests that assert the metadata key.
- **Depends on:** none.
- **Verification:** A test that builds the subscription-session metadata and asserts all keys are
  <=40 characters; a Stripe test-mode contract test if the project has credentials.
- **Fix risk:** Low — the key is internal; changing it also changes any stored event metadata, but
  the module reads the reservation from its own database, not from the key. Existing Sessions created
  before the fix do not exist (every create failed), so there is no migration.
- **Detection signal:** `BillingError`/500 on every `POST /billing/api/subscription/checkout/`;
  Stripe Dashboard event log shows no `checkout.session.created`; application logs show the Stripe
  `InvalidRequestError` for the metadata key.
- **Deliberate?** No comment or suppression; introduced 2026-10-02 in `3cfa290e` (billing services
  split). **Age:** 3 weeks; a regression introduced by the split, so a rename is safe.

### S2

#### Finding 3: Deal owner accepts a foreign-tenant user id and leaks that user's name

- **ID:** `crm-deal-owner-cross-tenant`
- **Severity:** S2 · **High × Common** (any org MEMBER can create a deal; the target id is a
  sequential integer) · deployment reality: generated project with CRM · oracle: the serializer's
  own foreign-org validation; the module's tenant contract · no unverified assumption.
- **Category:** III (object-level authorization / cross-tenant data exposure).
- **Confidence:** High — the write path, serializer fields, validation, and read renderer were read
  end to end; no owner guard exists.
- **Location:** `quickscale_modules/crm/src/quickscale_modules_crm/serializers.py:585` (`owner` in
  `DealDetailSerializer.Meta.fields`), `:611-680` (`validate`), `:527-531` (`get_owner_name`);
  `views.py:424-441`.
- **Defect:** Cross-tenant object-authorization gap in the deal-owner write/read path. Details are
  held in the private companion.
- **Failure scenario:** **Held in the private companion.**
- **Evidence:** **Held in the private companion.**
- **Refutation:** **Held in the private companion.**
- **Chain:** **Held in the private companion.**
- **Fix:** Validate `owner` against an active `OrganizationMembership` in the request org (or reject
  any owner who is not a current member), and make `owner_name` return `""` for a foreign user.
  Apply the same rule to `DealDetailSerializer` and `DealListSerializer`. **Effort:** Small.
- **Fix files:** `serializers.py`; CRM serializer/view tests.
- **Depends on:** none.
- **Verification:** A test that POSTs a deal with the pk of a user outside the active org and asserts
  a 400 / no cross-user name in the list.
- **Fix risk:** Low — projects may currently assign a global user who is not an org member; the
  validation will start rejecting those writes, which is the intended contract. A data migration is
  not needed for existing rows; the read filter hides the name.
- **Detection signal:** Deal list rows whose `owner_name` is a user with no membership in the
  request org; support reports of a strange owner name.
- **Deliberate?** No comment or test pinning a foreign owner; the serializer's docstring says it
  rejects foreign-org related IDs. Long-standing (since the CRM tenant contract, `b8d6ff60`,
  2026-06-24). **Age:** 4 months.

#### Finding 4: Fixed upload paths plus S3 overwrite replace another tenant's media

- **ID:** `media-s3-fixed-path-overwrite`
- **Severity:** S2 · **High × Common** (a member upload; common filenames; the cloud backend is the
  recommended production cell) · deployment reality: generated project with the storage module on
  `s3`/`r2` · oracle: the storage module's upload-path uniqueness intent; tenant isolation of
  content · no unverified assumption beyond the shared-bucket configuration, which is the documented
  one.
- **Category:** III (cross-tenant data integrity), secondary IX.
- **Confidence:** High on the mechanics (default read from installed django-storages 1.14.6);
  Medium on targeting (the attacker needs a known/common filename and the same bucket).
- **Location:** `quickscale_modules/listings/src/quickscale_modules_listings/models.py:43-45`;
  `quickscale_modules/blog/src/quickscale_modules_blog/models.py:263-268,344-349`;
  `quickscale_modules/storage/src/quickscale_modules_storage/adapter.py:33-47`.
- **Defect:** Cross-tenant media-integrity gap in the fixed-path cloud upload path. Details are
  held in the private companion.
- **Failure scenario:** **Held in the private companion.**
- **Evidence:** **Held in the private companion.**
- **Refutation:** **Held in the private companion.**
- **Chain:** **Held in the private companion.**
- **Fix:** Set `"file_overwrite": False` in the cloud `STORAGES` options (and document the equivalent
  `AWS_S3_FILE_OVERWRITE=False` for custom configs), and/or give each `upload_to` a per-user/per-org
  UUID path. A storage-level setting is the contained fix; per-org paths are the defense in depth.
  **Effort:** Small.
- **Fix files:** `storage/adapter.py` (plus tests); optionally `blog/models.py`,
  `listings/models.py` for per-tenant paths.
- **Depends on:** none.
- **Verification:** A test that uploads two files with the same name and asserts distinct stored
  names (with `file_overwrite=False`); a storage test with the S3 backend mocked at the
  `get_available_name` boundary.
- **Fix risk:** Low for new uploads; existing keys remain. Projects that deliberately rely on
  overwriting a key (unlikely for media) would need a manual delete. Local `FileSystemStorage`
  already auto-renames, so local tests must not be the only coverage.
- **Detection signal:** A public media URL changing to a different image after another user's upload;
  the S3 object's `LastModified` moving without the owning row changing.
- **Deliberate?** No comment; the local backend's auto-rename made the divergence invisible in tests.
  Long-standing. **Age:** blog/listings media since their first releases.

#### Finding 5: An org ADMIN can demote or remove an OWNER

- **ID:** `orgs-admin-can-demote-owner`
- **Severity:** S2 · **High × Common** (any org ADMIN; no extra precondition) · deployment reality:
  generated project in SaaS mode · oracle: the capability matrix reserves ownership transfer to
  owners; the members template hides the role form for owners · no unverified assumption.
- **Category:** III (privilege escalation / broken object-level authorization).
- **Confidence:** High — both the HTML and JSON member-management paths use the same form and lack
  an actor-rank check.
- **Location:** `quickscale_modules/orgs/src/quickscale_modules_orgs/_view_org_management.py:140`,
  `:158-182`; `forms.py:294-358`; `_api_views.py:182-216`, `:219-251`;
  `templates/quickscale_orgs/members.html:92-106`.
- **Defect:** Privilege-escalation gap in the member role/remove path (actor rank is not compared
  with the target's). Details are held in the private companion.
- **Failure scenario:** **Held in the private companion.**
- **Evidence:** **Held in the private companion.**
- **Refutation:** **Held in the private companion.**
- **Chain:** **Held in the private companion.**
- **Fix:** In `RoleChangeForm.clean_role` and both remove paths, reject any mutation where the
  target's role rank is greater than the actor's (superuser excepted), and reject owner removal by a
  non-owner. Add the same rule to the JSON API and a test for ADMIN→OWNER demotion/removal.
  **Effort:** Small.
- **Fix files:** `forms.py`, `_view_org_management.py`, `_api_views.py`, tests.
- **Depends on:** none.
- **Verification:** A test with owners O1/O2 and admin X that asserts X receives a validation error
  for a role change or removal targeting O1.
- **Fix risk:** Low — the UI already hides the action, so no legitimate UI flow breaks; a project
  with an admin-managed owner would need an owner to perform the change, which is the documented
  contract.
- **Detection signal:** The org audit log (if enabled) records an ADMIN actor changing an OWNER's
  role; a sudden loss of owner-only access for an owner.
- **Deliberate?** The template's owner-only guard is evidence that the server check is the omission,
  not a chosen policy. Long-standing. **Age:** since the member-management views.

#### Finding 6: The generated README calls the dev Compose stack production

- **ID:** `generated-compose-called-production-runs-debug`
- **Severity:** S2 · **High × Common** (the README is the first deployment instruction a user
  follows; no extra precondition) · deployment reality: self-hosted generated project · oracle: the
  generated production settings and `start.sh` contract · no unverified assumption; the Compose
  override is explicit.
- **Category:** X (code/config generator), secondary VI (insecure defaults).
- **Confidence:** High — the README text, Compose override, and `local.py` forcing `DEBUG=True` were
  read end to end; the Dockerfile's correct `CMD ["./start.sh"]` is overridden by Compose.
- **Location:** `quickscale_core/src/quickscale_core/generator/templates/README.md.j2:338-347`;
  `docker-compose.yml.j2:70`, `:78`, `:95`; `project_name/settings/local.py.j2:24`, `:118`.
- **Defect:** The documented self-hosted "production" path is the development Compose stack.
  Details are held in the private companion.
- **Failure scenario:** **Held in the private companion.**
- **Evidence:** **Held in the private companion.**
- **Refutation:** **Held in the private companion.**
- **Chain:** **Held in the private companion.**
- **Fix:** Either remove the production claim and label Compose as local development, or add a
  production Compose profile/override that runs the built image's `start.sh` with
  `DJANGO_SETTINGS_MODULE=<package>.settings.production`, no source bind mount, no dev
  dependencies, and explicit `DEBUG=False`. The smallest safe fix is the docs correction plus a
  startup assertion that refuses `DEBUG=True` when `QUICKSCALE_ENVIRONMENT=production`. **Effort:**
  Small.
- **Fix files:** `README.md.j2`, `OPERATIONS.md.j2`, optionally `docker-compose.yml.j2` and
  `start.sh.j2`.
- **Depends on:** none (the docs correction can land alone; the production profile is a follow-up).
- **Verification:** A rendered-README test that asserts the production instructions do not use
  `settings.local`/`runserver`; an E2E test that boots the production profile with `DEBUG=False`.
- **Fix risk:** Low for the docs; a production profile is a larger surface but still contained. Users
  who rely on the dev Compose for local work are unaffected.
- **Detection signal:** `docker compose up` logs the Django development server banner; a debug
  traceback reachable from the internet; `settings.DEBUG` true in the running container.
- **Deliberate?** The Compose file is deliberately a dev stack; the *claim* is the defect. The
  architectural audit's F4 (`generated-deploy-topology-unmodeled`) records the structural version.
  Long-standing (`03413ebc`, 2025-10-17). **Age:** ~1 year.

#### Finding 7: Selecting the Redis cache fails because the redis client is not a project dependency

- **ID:** `generated-redis-cache-missing-client`
- **Severity:** S2 · **High × Common** (the README/production settings call Redis the recommended
  shared cache; setting `REDIS_URL` is a supported configuration cell) · deployment reality:
  generated production deployment with Redis · oracle: the production settings' own cache contract;
  a cache backend must be importable · no unverified assumption.
- **Category:** VI (unusable fallback), secondary IV.
- **Confidence:** High — the generated `pyproject.toml.j2` has no `redis` dependency, the
  `quickscale-core` dependency does not include it, and Django's `RedisCache` imports `redis`.
- **Location:** `project_name/settings/production.py.j2:234-247`;
  `pyproject.toml.j2:14-21`.
- **Defect:** When `REDIS_URL` is set, `CACHES["default"]["BACKEND"]` becomes Django's
  `django.core.cache.backends.redis.RedisCache`, but the generated project never installs the
  `redis` package (the `django-stubs[redis]` extra is a dev-only stub extra and is not installed in
  the production image). The first cache access raises `ModuleNotFoundError`/`ImproperlyConfigured`;
  the DB-free healthcheck stays green.
- **Failure scenario:** A user follows the recommended production setup, adds a Redis service, sets
  `REDIS_URL`, and deploys. The first request that touches a DRF throttle or any cache call raises
  `ImportError: No module named 'redis'`; the request 500s. The healthcheck returns 200 because it
  never touches the cache, so the platform keeps routing traffic.
- **Evidence:** `_redis_url = config("REDIS_URL", default=None)` then
  `"BACKEND": "django.core.cache.backends.redis.RedisCache"`; `pyproject.toml.j2` dependencies are
  Django, quickscale-core, psycopg2-binary, decouple, whitenoise, gunicorn, dj-database-url (no
  redis). The composed DRF settings install throttles by default.
- **Refutation:** Searched for a transitive `redis` dependency in `quickscale-core` and the module
  pyprojects; none. The repository's own `poetry.lock` has `redis = ["redis", "types-redis"]` only
  as a `django-stubs` optional extra; the generated project does not install that extra. A startup
  check does not import the cache. The database cache fallback is only selected when `REDIS_URL` is
  unset, so the Redis cell is exactly the broken one.
- **Fix:** Add `redis = "^6.4.0"` (or the current supported floor) to the generated
  `[tool.poetry.dependencies]`, and add a startup check that imports the configured cache backend
  and reports a clear `ImproperlyConfigured` at boot rather than at first request. **Effort:**
  Trivial.
- **Fix files:** `pyproject.toml.j2`; optionally `production.py.j2` and the generated CI.
- **Depends on:** none.
- **Verification:** Render the project, install the generated dependencies in a scratch venv, set
  `REDIS_URL`, and import/instantiate `CACHES["default"]`; or a unit test that asserts the `redis`
  package appears in the rendered dependency list when the Redis backend is selected.
- **Fix risk:** Low — adds one dependency; the version must stay compatible with Django 6.0.
- **Detection signal:** `ModuleNotFoundError: No module named 'redis'` on the first throttled
  request; 500s on login/registration; a green healthcheck while the site is down.
- **Deliberate?** No comment; the settings recommend Redis without the client. Long-standing.
  **Age:** since the Redis backend branch.

#### Finding 8: A JSON null in an optional public form field raises IntegrityError and 500

- **ID:** `forms-null-optional-field-500`
- **Severity:** S2 · **Moderate × Direct** (unauthenticated public endpoint; a real client that
  serializes an empty optional input as `null` triggers it) · deployment reality: generated project
  with forms · oracle: the public submit contract should return a validation error, not a 500 ·
  no unverified assumption.
- **Category:** I (correctness), secondary IX.
- **Confidence:** High — the serializer accepts `None` for optional fields and the persistence path
  writes the raw value into a non-null `TextField`; the honeypot path bypasses the serializer.
- **Location:** `quickscale_modules/forms/src/quickscale_modules_forms/serializers.py:179-199`;
  `views.py:309-320`, `:338-346`, `:365-379`; `models.py:193`.
- **Defect:** The dynamic serializer's `validate` treats `None` as an empty optional value and
  continues, but `_create_field_values` writes `data.get(field.name, "")` without converting `None`
  to a string. `FormFieldValue.value` is a non-null `TextField`, so the insert violates NOT NULL and
  raises `IntegrityError`. The honeypot fast path skips validation entirely and has the same write.
- **Failure scenario:** An unauthenticated client posts
  `{"full_name":"x","email":null,"rating":"5","message":"hi"}` to the public submit route of a seeded
  Feedback form (optional `email`/`full_name`). Validation passes; the transaction inserts
  `value=None`; PostgreSQL raises `IntegrityError`; the view returns 500 and the transaction rolls
  back. A bot can repeat this on every form; a legitimate frontend that sends `null` for an empty
  optional field cannot submit.
- **Evidence:** `if submitted_value is None: ... continue`; then
  `FormFieldValue.objects.create(..., value=submitted_value)`; `value = models.TextField()` (no
  `null=True`). The existing tests only send `None` with a required field, so validation aborts
  before the write.
- **Refutation:** Checked the serializer's `to_internal_value` (returns the raw dict), the honeypot
  branch (writes before validation), the model field, and the migration; all confirm the path.
  Checked for a model `save`/`clean` normalization; none. The public endpoint is throttled at
  `5/hour` per IP, so the DoS is bounded but the 500 is still reachable.
- **Fix:** Normalize optional `None` to `""` at the persistence boundary (or reject it with a clear
  field error), and apply the same normalization in the honeypot path. **Effort:** Trivial.
- **Fix files:** `serializers.py`/`views.py`; tests.
- **Depends on:** none.
- **Verification:** A public-submit test with an optional field set to `null` asserts 201 (if
  normalized) or 400 (if rejected), never 500; a honeypot test with `null` values.
- **Fix risk:** Low — normalizing to `""` matches the existing empty-string semantics; no schema
  change.
- **Detection signal:** `IntegrityError`/`null value in column "value"` in the forms log; 500s on
  `/forms/api/<slug>/submit/`; a spike in form error logs with `null`.
- **Deliberate?** No; the `None` branch was added for optional fields but the write was not updated.
  Long-standing. **Age:** since the dynamic serializer.

#### Finding 9: Subscription and invoice webhooks apply payload status without provider ordering

- **ID:** `billing-webhook-status-applied-out-of-order`
- **Severity:** S2 · **High × Common** (Stripe redelivery is ordinary operation; the docs say order
  is not guaranteed; no extra config) · deployment reality: generated project with billing and a
  Stripe webhook · oracle: billing's own idempotency/current-subscription contract; Stripe's event
  ordering guidance · no unverified assumption.
- **Category:** II (stale/out-of-order writes), secondary IX.
- **Confidence:** High that no ordering or provider-object check exists; High that Stripe can
  deliver distinct events out of order (primary documentation).
- **Location:** `quickscale_modules/billing/src/quickscale_modules_billing/_subscription_events.py:191-205`;
  `_webhooks_invoice.py:490-530`; `_webhooks.py:69-120`; `models.py:367-389`.
- **Defect:** Out-of-order provider-event handling in the subscription/invoice webhook path.
  Details are held in the private companion.
- **Failure scenario:** **Held in the private companion.**
- **Evidence:** **Held in the private companion.**
- **Refutation:** **Held in the private companion.**
- **Chain:** **Held in the private companion.**
- **Fix:** Before applying a subscription or invoice event, retrieve the current object from Stripe
  (the handler already has a `stripe_client` and processes provider I/O outside the DB transaction)
  and apply the authoritative state, or store a provider version/updated timestamp and reject older
  writes. Do not rely on `event.created` alone (Stripe explicitly warns that it is not an ordering
  key). **Effort:** Medium.
- **Fix files:** `_subscription_events.py`, `_webhooks_invoice.py`, `models.py` + migration if a
  version column is chosen; tests with out-of-order fixtures.
- **Depends on:** none.
- **Verification:** A test that delivers `customer.subscription.deleted` then an older
  `customer.subscription.updated` and asserts the row stays canceled; the inverse for a late
  `invoice.payment_failed`.
- **Fix risk:** Medium — a provider read on every event adds latency and a new failure mode; do it
  outside the transaction and fail closed or retry. A version column needs a migration and handling
  of old rows.
- **Detection signal:** A subscription row that flips back to `active` after a cancellation; a
  `past_due` row after a successful invoice; Stripe event deliveries marked delivered but local
  state disagreeing with the Dashboard.
- **Deliberate?** No comment; tests assert last-write-wins, not ordering. Long-standing. **Age:**
  since the billing webhook handlers.

### S3

- `billing-invoice-payment-failed-unscoped` · **S3 (High × Rare)** · `_webhooks_invoice.py:419-438`,
  `:512-552` · The failed-invoice handler has no `billing_reason`/subscription-id guard: an
  unrelated failed invoice for the same Stripe customer resolves the current subscription by
  customer and marks it `past_due`, or creates a phantom `past_due` row. Reachability is Rare
  because it needs Stripe Invoicing/one-off invoices on the same customer; the paid handler already
  has the guard. Fix: share the paid handler's billing-reason filter and require a non-empty
  subscription id. Effort Trivial. Confidence High. `depends_on: none`.
- `billing-credit-services-missing-org-scope` · **S3 (High × Rare)** · `_credits.py:49-57,101-114`;
  `README.md:268-273` · `credit_user`/`debit_user` require an `organization` but never enter
  `org_scope`, so a documented production shell/background call (runtime role, no request ContextVar)
  sees no rows and fails RLS; webhook callers happen to wrap them. Fix: wrap both public services in
  `org_scope(organization)` (save/restore the prior scope) and add a test that calls them from a
  no-context thread. Effort Small. Confidence High. `depends_on: none`.
- `billing-debit-not-idempotent` · **S3 (High × Rare)** · `_credits.py:101-131` · `debit_user` has no
  caller-supplied idempotency key or unique reference; a commit whose response is lost and retried
  debits again. Fix: add an optional `reference`/`stripe_object_id` and a unique constraint on
  `(organization, reference, transaction_type)`, mirroring `credit_user`'s dedup. Effort Medium.
  Confidence High. `depends_on: none`.
- `billing-checkout-double-submit` · **S3 (High × Rare)** · `_checkout.py:124-147`;
  `serializers.py:63-65` · Purchase Checkout reuses only a `PREPARING` reservation; once the first is
  `OPEN`, a double-click/HTTP retry creates a second reservation and a second payable Stripe session
  (different idempotency keys). Fix: reuse the latest `OPEN` reservation per user/org/plan or accept
  a client idempotency key; the throttles and advisory lock serialize but do not deduplicate.
  Effort Small. Confidence High. `depends_on: none`.
- `backups-restore-drops-own-artifact-row` · **S3 (High × Rare)** · `_capture.py:521-533,605-626`;
  `persistence.py:299-334` · The snapshot row is created before the dump; the artifact row is created
  after it. A successful restore therefore restores a DB without the artifact row, and the
  post-restore update matches 0 rows and only warns; the snapshot remains `PENDING` with no
  authoritative dump, and a later prune can delete its root. Fix: create/relink the artifact row after
  restore (or create it before the dump with placeholders and update it), and fail the restore
  metadata step visibly instead of a success warning. Effort Medium. Confidence High. `depends_on:
  none`.
- `backups-prune-no-keep-last` · **S3 (High × Rare)** · `_prune.py:63-140`;
  `persistence.py:404-410` · Retention deletes every expired snapshot/artifact with no keep-last
  floor. If backup creation fails for `retention_days`, the scheduled prune deletes the only
  remaining recovery point. Fix: always retain the newest valid snapshot (and skip its artifacts),
  or refuse to prune the last one. Effort Trivial. Confidence High. `depends_on: none`.
- `backups-restore-not-atomic` · **S3 (High × Rare)** · `primitives.py:345-364`;
  `recovery.py:786-791` · `pg_restore --clean --if-exists` has no `--single-transaction` and no
  pre-restore dump; a mid-restore failure leaves the live DB partially dropped/restored. Fix: add
  `--single-transaction` where supported and a pre-restore safety dump (or refuse without one);
  document the maintenance window. Effort Medium. Confidence High. `depends_on: none`.
- `backups-creation-lock-expires-live` · **S3 (Moderate × Common)** · `_lock.py:28-29,82-126,140-179`
  · The create lock is a file whose mtime is set once; the fd is closed after acquisition, so the
  `flock` does not stay held. A backup longer than 300 s is declared stale and a second run starts.
  Fix: keep the descriptor open for the context (flock protects against process death) or refresh
  the mtime with a heartbeat; add a long-backup test. Effort Small. Confidence High. `depends_on:
  none`.
- `auth-profile-email-change-desync` · **S3 (High × Rare)** · `auth/forms.py:44-67`;
  `_profile_views.py:34-52` · `ProfileUpdateForm` writes `User.email` directly and never updates
  allauth's `EmailAddress`; the old verified address remains a login and password-reset identifier,
  while the new address is unverified. Fix: use allauth's email-management flow (add/verify the new
  address, remove/mark the old one) or reject direct email edits; add a regression test that resets
  the password via the old address after a profile email change. Effort Small. Confidence High.
  `depends_on: none`.
- `cli-remove-accepts-path-traversal` · **S3 (High × Rare)** · `remove_command.py:453-465,696-700`;
  `_check_module_exists:520-535` · `quickscale remove <module>` joins the positional argument into
  `project_path / "modules" / module_name` and `shutil.rmtree()`s it. `..` or an absolute path
  resolves outside `modules/` and, after the ordinary confirmation, deletes that directory (for
  example `quickscale remove ..` deletes the project root). Fix: validate the module name against the
  known module-name pattern and the state/manifest list before any path join; reject `..`, `/`, and
  names not in `state.modules`; resolve and assert the target is inside `modules/`. Effort Trivial.
  Confidence High. `depends_on: none`.
- `dockerignore-bakes-local-backups` · **S3 (High × Rare)** · `.dockerignore.j2` (no `.quickscale`
  entry); `Dockerfile.j2` `COPY . .` · The default backup directory is `.quickscale/backups` and is
  gitignored, but the Docker build context includes it; the runtime image copies the whole project,
  so a local DB dump with tenant data is baked into the image and its layers. Fix: add
  `.quickscale/` (or `.quickscale/backups/`) to `.dockerignore`, and add a rendered-Dockerfile test.
  Effort Trivial. Confidence High. `depends_on: none`.
- `cli-apply-force-never-forces` · **S3 (Moderate × Common)** · `_generation.py:97-129,131-150`;
  `_steps.py:63-67`; `generator.py:464-510` · `_check_output_directory` accepts `--force` and warns
  that it will overwrite, but `_generate_new_project` with an existing non-empty directory and no
  `quickscale.yml` calls `ProjectGenerator.generate`, which raises `FileExistsError`. The user is
  told to use the flag they already supplied and the apply aborts. Fix: stage into a temp directory
  and swap (the existing `_generate_with_existing_config` path) or remove the misleading flag from
  this branch. Effort Small. Confidence High. `depends_on: none`.
- `e2e-generated-ci-contract-stale-grep` · **S3 (Moderate × Common)** ·
  `.github/workflows/e2e.yml:162-174`; `ci.yml.j2` · The E2E workflow renders a project and greps for
  `actions/checkout@v6` and `actions/setup-python@v6`, but the generated template has pinned those
  actions by SHA since SA253. The release-triggered E2E job fails at the contract step; the
  generated workflow is correct. Fix: grep for the pinned SHA or, better, assert the parsed `uses:`
  pin shape; run the same check in the generator tests. Effort Trivial. Confidence High.
  `depends_on: none`.
- `publish-pypi-no-skip-existing` · **S3 (High × Rare)** · `.github/workflows/publish.yml:343-361` ·
  The production PyPI publish action has no `skip-existing`; a partial upload (network failure after
  one package) makes a re-run of the same tag fail on the already-present file, and a new version is
  needed to recover. The TestPyPI job already sets `skip-existing: true`. Fix: add `skip-existing:
  true` to the production step (the artifact is the same tested build) or publish each distribution
  with a resumable strategy. Effort Trivial. Confidence High. `depends_on: none`. Fix risk: it can
  mask a version mismatch; keep the VERSION check.
- `media-image-decode-before-dimension-cap` · **S3 (Moderate × Common)** ·
  `storage/_helpers.py:344-365`; `blog/services.py:96-180` · Both upload validators call
  `Image.open(...).load()` before checking `width`/`height`; Pillow's bomb warning at 89 MP is not an
  error, so a highly compressed 100 MP image decodes (~300 MB RGB) before the configured dimension
  cap rejects it. A member can OOM the default single gunicorn worker (5/hour throttle). Fix: read
  `image.size` and reject before `load()`; set `Image.MAX_IMAGE_PIXELS` to the configured cap; keep
  the existing `DecompressionBombError` handling. Effort Small. Confidence High. `depends_on: none`.
- `orgs-bulk-delete-leaves-zero-owners` · **S3 (Moderate × Rare)** · `receivers.py:21-85`;
  `models.py:179-223` · Django's collector sends all `pre_delete` signals before any delete; the
  last-owner receiver checks each row independently, so deleting two co-owners in one admin/ORM bulk
  operation passes both checks and leaves the org with members but no owner. The model-level guard
  only covers single-row `delete()`. Fix: add a `post_delete` invariant check (raise to roll back the
  collector) or lock the org and count owners at the start of a bulk delete; add a `delete_selected`
  test. Effort Medium. Confidence High. `depends_on: none`.

### S4

- `orgs-admin-org-delete-blocked` · `receivers.py:21-85`; `admin.py:48` · Deleting an organization
  with a sole owner and another member through `OrganizationAdmin` raises the last-owner
  `ValidationError` for the cascaded membership, so the documented admin delete fails. Fix: exempt
  memberships whose organization is being deleted (detect the cascade) or route admin deletion
  through the purge command. Effort Small.
- `orgs-slug-new-shadows-route` · `_constants.py:17`; `urls.py:35,91`; `forms.py:61-81` · `new` is
  not reserved and the `new/` route precedes `<slug>/`, so an org named "New" cannot reach
  `/orgs/new/` (it renders the create form). Fix: add `new` (and the other one-segment utility
  names) to `RESERVED_ORG_SLUGS`. Effort Trivial.
- `backups-validate-action-view-permission` · `_admin_artifact.py:486-505`; `admin.py:158` · The
  `validate_selected_backups` action has no `permissions=["change"]`; a staff user with only view
  permission can run it, and `validate_backup_artifact` writes `status`/`validated_at` without a
  RESTORING/DELETED guard. Fix: add the change permission to the action and a status guard. Effort
  Trivial.
- `backups-dump-files-world-readable` · `_paths.py:51-60`; `_capture.py:506-520`;
  `_metadata.py:190-195` · Backup directories/files use the process umask (typically 0755/0644);
  only the lock is 0600. On a shared host/volume, another local user can read full DB dumps. Fix:
  create the directory 0700 and the files 0600 (or chmod after creation), and make the policy
  private. Effort Trivial.
- `backups-filename-second-resolution-collision` · `_paths.py:31-48`; `models.py:108`;
  `_capture.py:605-626` · The filename embeds only seconds and is globally unique in the DB;
  concurrent creates on different replicas/lock directories in the same second make the second
  `create_artifact` raise an uncaught `IntegrityError` after a successful dump. Fix: add a short
  random suffix or retry with a new name. Effort Trivial.
- `forms-csv-export-materializes-all-values` · `views.py:523-562` · The "stream" export first
  materializes every `FormFieldValue` for the form into a list and builds a `StringIO`; on a large
  form the admin request holds the whole table in memory. Fix: iterate values with `iterator()` and
  stream the CSV response. Effort Small.
- `forms-option-values-not-validated` · `serializers.py:179-220` · The dynamic serializer checks
  type/required/email/regex but never checks a select/radio/checkbox value against the field's
  `options`, so arbitrary strings enter the submission ledger. Fix: validate `field_type`-specific
  option membership. Effort Trivial.
- `generated-readme-examples-invalid` · `README.md.j2:26,82,285-295`; `.env.example.j2:17`;
  `.gitignore.j2` · Three generated-doc defects in one class: `cp .env.example .env` overwrites the
  generated `.env` (and its host UID) with `DOCKER_UID=1000`, so non-1000 hosts cannot write the
  Compose bind mounts; the S3 `quickscale.yml` example uses tab indentation, which PyYAML rejects;
  and `.gitignore` misses `static/frontend`, so a Vite build leaves untracked files that block
  `quickscale apply` module embedding. Fix: use the generated `.env`, space-indent the YAML, and
  ignore the Vite output. Effort Small.
- `billing-zero-credit-plan-webhook-loop` · `_webhooks_invoice.py:407-416`; `_credits.py:49-50`;
  `models.py:67-72` · `Plan.credits_per_period` allows 0, but `credit_user` rejects `amount <= 0`; a
  paid zero-credit plan activates the subscription and then fails the credit step, rolling back the
  activation and retrying the webhook forever. Fix: skip the credit call when the plan grants 0
  credits, or constrain the plan to positive credits. Effort Trivial.
- `auth-deletion-logs-pii` · `auth/views.py:166-184,255-262`;
  `_account_deletion_providers.py:263-272` · Deletion failure paths log `str(user)` (full name or
  username) and organization names; the success path logs retained org names at INFO. The generated
  JSON/file logging retains them after the scrub. Fix: log the pk and a redacted correlation id, not
  the name; use the core redaction helpers. Effort Trivial.
- `beta-migrate-existing-recipient-no-dirty-guard` · `quickscale_devtools/.../execution.py:759-772`
  · Prior S4 still open: `--existing-recipient` rmtree/copies over a git-tracked recipient with no
  dirty-tree check. Fix: run `git status --porcelain` and block. Effort Small.
- `notifications-message-status-aggregate-race` · `_delivery.py:248-270` · Prior S4 still open: two
  sibling-delivery webhooks recompute and save the message aggregate without locking the parent,
  leaving a stale status. Needs multiple workers and a multi-recipient message. Fix: lock the
  `NotificationMessage` row before re-aggregating. Effort Trivial.
- `forms-retention-skips-null-ip-rows` · `_retention.py:74,92` · Prior S4 still open: the retention
  query `.exclude(ip_address=None)` skips submissions stored with a NULL IP but a non-empty user
  agent, so the UA is never cleared. Fix: select `Q(ip_address__isnull=False) | ~Q(user_agent="")` in
  both the read and the update. Effort Trivial.

## Safeguard matrix

Compact; each cell names the layer that supplies the safeguard, the finding ID for a gap, or
`unknown`/`n/a` with the reason. The matrix is a reading aid, not a second findings list.

| Population | Authentication | Authorization / scope | Input & limits | Durability / atomicity | Notes |
|---|---|---|---|---|---|
| Generated boot (`start.sh`, Dockerfile) | n/a | non-root image, `SECRET_KEY` guard, runtime-role split | healthcheck is liveness only | migrations at every boot (watchlist) | compose debug |
| Generated HTTP (base/production settings) | Django session | `ALLOWED_HOSTS`, CSRF, secure cookies, HSTS, conditional proxy trust | no request-size tuning | n/a | verified; no readiness probe |
| Module content APIs (CRM/blog/listings/forms/orgs) | session + allauth | org role + RLS + object filters | DRF serializers, throttles | transactions on writes | `crm-deal-owner-cross-tenant`; `orgs-admin-can-demote-owner` |
| Public endpoints (forms submit, blog/listing public, social) | anonymous by design | System-org scope / published filter | forms 5/hour, blog/listing 5/hour | atomic submission | `forms-null-optional-field-500`; `forms-option-values-not-validated` |
| Webhooks (Stripe, Svix) | signature over raw body | event-type allowlist | no throttle on Svix | event-id dedup + advisory lock | `billing-webhook-status-applied-out-of-order`; `notifications-pre-signature-db-read` |
| Admin surfaces | staff + model perms | superuser policy for org data | n/a | restore CAS | `backups-validate-action-view-permission`; `tenant-admin-org-selector` |
| Management commands | operator | `--confirm`/env gate, scheduled-off | dry-run on prune/restore | command-owned transactions | `backups-restore-not-atomic` |
| CLI | local operator | confirmation + advisory lock | n/a | apply backup/rollback | `cli-remove-accepts-path-traversal`; `cli-apply-force-never-forces` |
| Uploads (blog/listings/storage) | session + member | org-scoped rows; public media by design | size/format/dimension, bomb error | object storage | `media-s3-fixed-path-overwrite`; `media-image-decode-before-dimension-cap` |
| Tenant ORM/RLS | n/a | `TenantManager` + FORCE RLS | n/a | GUC per scope | `billing-credit-services-missing-org-scope`; `orgs-contextvar-leak-on-db-error` |
| Caches / throttles | n/a | per-user/anon scopes | DRF rates | shared cache required | `social-cache-bulk-invalidation` |
| Release pipeline | GitHub OIDC / tokens | least privilege, SHA pins | n/a | artifact promotion | none open |
| Dependencies | n/a | lockfiles/pins | n/a | n/a | accepted postcss advisory; no fresh audit |
| Backups | n/a | operator/admin gate | checksum/format/migration identity | dump+sidecar | `backups-*` findings; F6 structural context |

## Fix order and batching

**S1/S2 batch is closed.** The two billing findings are fixed by SA310, and
`crm-deal-owner-cross-tenant`, `media-s3-fixed-path-overwrite`,
`orgs-admin-can-demote-owner` and `forms-null-optional-field-500` are fixed by SA311 (see the
machine-readable index above); no S1/S2 finding remains open.

**Then (S3), in three batches:**

- **Billing batch:** `billing-invoice-payment-failed-unscoped`,
  `billing-credit-services-missing-org-scope`, `billing-debit-not-idempotent`,
  `billing-checkout-double-submit`, `billing-zero-credit-plan-webhook-loop`. The webhook-ordering
  fix has landed (SA310); the credit/idempotency changes touch `_credits.py` and need a migration
  for the reference constraint.
- **Backups batch:** `backups-restore-drops-own-artifact-row`, `backups-prune-no-keep-last`,
  `backups-restore-not-atomic`, `backups-creation-lock-expires-live`, plus the S4 backup items.
  These share `_capture.py`/`_restore.py`/`_prune.py`/`_lock.py`; the runtime-role fix has landed,
  and the restore-metadata fix still lands before the prune change.
- **Generator/CLI/release batch:** `media-image-decode-before-dimension-cap`,
  `auth-profile-email-change-desync`. The README, `.dockerignore`, E2E-contract,
  publish-resumability, remove-traversal, apply-force and dirty-recipient fixes are closed; the
  rest ride with the next generator release.

**S4 tail:** batch by file (orgs receivers, backups admin/perms, forms export/options, auth logging,
three prior S4s). No ordering constraint beyond “restore-metadata before prune”.

Parallelizable: the billing, orgs, CRM, media, generator-docs, and release-workflow batches touch
disjoint files. The backup batch and the generator batch both touch `quickscale_core` but different
subtrees; run them in parallel if the branch strategy allows. Conflicts: `_settings.py` (billing key
+ RLS) and `_capture.py` (artifact row + perms) are the shared-file hotspots; coordinate
reviewers.

## Per-subsystem verdicts

- **Generated-project templates:** four findings, fixed since the audit
  (`generated-compose-called-production-runs-debug`, `generated-redis-cache-missing-client`,
  `dockerignore-bakes-local-backups`, `generated-readme-examples-invalid`); otherwise read in full,
  secure defaults verified (secret guard, non-root, cookies/HSTS, conditional proxy trust).
- **Billing:** findings 1 and 9 are fixed, five S3/S4 remain; webhook signature/raw body, price
  parity, RLS targets, and the current-subscription constraint verified. Metadata-key and ordering
  regressions run against a fake provider; the real test-mode subscription Checkout is
  credential-gated in `test_stripe_contract.py`.
- **Orgs:** `orgs-admin-can-demote-owner` is fixed; `orgs-bulk-delete-leaves-zero-owners`, two S4s,
  and four watchlist items remain; RLS predicate, purge atomicity, `TenantManager`, invitation
  throttle, and content-route roles verified.
- **Backups/DR:** five human-scale S3/S4s; checksum/migration identity, admin upload trusted
  match, and the environment gate verified. The RLS/runtime-role path was reproduced (resolved as
  SA313).
- **Auth:** `auth-profile-email-change-desync` and `auth-deletion-logs-pii`; allauth config,
  account-deletion guard, session rotation, and email-verification default (watchlist) verified.
- **CRM:** `crm-deal-owner-cross-tenant` is fixed; org-scoped reads, contact/stage/tag/owner
  validation, bulk stage filters, and CSV-free exports verified.
- **Storage/blog/forms/listings:** `media-s3-fixed-path-overwrite` and
  `forms-null-optional-field-500` are fixed; `media-image-decode-before-dimension-cap` and three S4s
  remain; extension-from-format, SVG exclusion, public/private media split, CSV formula
  neutralization, and retention (prior S4) verified.
- **CLI:** `cli-remove-accepts-path-traversal`, `cli-apply-force-never-forces`; argv-list subprocess,
  advisory locks, theme preflight, and apply checkpoint/rollback verified.
- **Core generator/DR:** the restore/prune/lock items and the fixed S4 README/ignore items;
  emission mapping, Jinja autoescape rationale, and runtime settings fail-closed paths verified.
- **Scripts/CI/publish:** two findings, fixed since the audit
  (`e2e-generated-ci-contract-stale-grep`, `publish-pypi-no-skip-existing`); action SHA pins,
  least-privilege permissions, and the gate registry verified. The manual/unwired gates are in the
  Tooling gaps section.
- **Notifications/social/listings/analytics:** no new defect beyond the carried notifications race
  and watchlist items; Svix raw-body verification, delivery-status contract, public filters, and
  analytics escaping verified.
- **Devtools:** the prior `beta-migrate-existing-recipient-no-dirty-guard` is fixed by SA317; the
  rest was sampled.

## Clean sweeps and rejected candidates

- **Billing:** purchase metadata key is 38 chars (within Stripe's limit); purchase/subscription
  create/response-loss recovery and idempotency keys verified; Stripe signature over the raw body,
  API-version gate, customer/subscription identity checks, price parity, and RLS on billing tables
  verified. Refuted: “the purchase path has the same metadata-key defect” (38 chars).
- **Orgs:** FORCE-RLS policy predicate and `TenantManager` fail-closed behavior verified; purge is
  atomic and tombstoned; invitation acceptance is token + normalized email; content routes require
  membership; single-row last-owner guards verified. Refuted: “non-superuser org users can reach
  `/admin/` tenant data” (the documented policy is superuser-only staff; `TenantModelAdmin` remains
  a watchlist).
- **Auth:** allauth 65.18 email lookup searches both `EmailAddress` and `User.email`; the deletion
  flow's transaction and last-owner guard verified; session cookie age setting is read at startup.
  Refuted: “`ProfileUpdateForm` lets a user change their role” (no role field).
- **Backups:** checksum validation, archive magic/list, migration identity, exact-filename
  confirmation, environment gate, remote-key containment in the normal artifact path, and admin
  upload trusted-match verified. Refuted: “the media sync path is used by first-party uploads”
  (keys are UUID/format-derived; the `..` case remains a watchlist).
- **Templates:** SECRET_KEY placeholder rejected in production; HSTS/cookies; proxy trust is
  conditional on `USE_X_FORWARDED_FOR`; non-root image; healthcheck is intentionally DB-free
  (watchlist as readiness). Refuted: “the Dockerfile runs as root” (it creates and switches to
  `django`).
- **Storage:** `DecompressionBombError` is translated to a validation error; the stored extension
  comes from Pillow's detected format, not the client name; SVG is excluded from Markdownx.
  Refuted: “a client can store an `.html` extension” (format map).
- **Forms:** public schema/submit resolve the System org and only active forms; CSV cells are
  formula-neutralized; the honeypot path marks spam without revealing detection; per-IP throttle
  exists. Refuted: “public submission leaks another org's form” (System-org query).
- **CRM:** org-scoped querysets, foreign contact/stage/tag rejection, and bulk stage/mark filters
  verified. Refuted: “contact/stage foreign-org ids are writable” (serializer validates them).
- **Notifications:** Svix signature is verified over the raw body before parsing; event id is the
  replay key; the forward-only status contract is implemented. Prior race carried.
- **CLI:** subprocess calls use argv lists with `shell` disabled; apply/update acquire advisory
  locks; theme preflight runs before mutation; removal snapshots and rolls back. Refuted: “apply
  writes outside the project through `package`” (config schema requires a lowercase identifier).
- **Scripts/CI:** Actions are SHA-pinned, top-level permissions are `contents: read`, publish uses
  OIDC, and the gate registry/Makefile wiring was checked. Refuted: “the publish workflow trusts a
  fork's code with write secrets” (tag-triggered, no `pull_request_target`).
- **Scanner hits dismissed:** no committed credential was found in HEAD (the matches are documented
  placeholders/test fixture strings); `gitleaks` was not run and history scanning is a tooling gap,
  not a finding. No dependency hit was re-verified; the carried postcss advisory is the only
  exception.

## Structural smells

- **Generated production topology is prose, not an artifact** (arch F4): media is container-local
  by default and schema changes at boot. The README's production claim is corrected; the structural
  form is arch `generated-deploy-topology-unmodeled`.
- **Backups hold a coherent recovery point** (arch F6, closed by SA322): media is captured into the
  versioned snapshot and restored from it, project migration identity is enforced, and a restore
  lease serializes destructive runs.
- **Billing webhooks reconcile with the provider** (SA310): subscription and invoice handlers
  retrieve the current subscription under the organization's provider mutex before applying its
  status, so a late delivery cannot overwrite newer provider state. Remaining: a failed invoice
  with no subscription id still resolves the customer's current subscription
  (`billing-invoice-payment-failed-unscoped`, SA314).
- **Media ownership/lifecycle is still not modeled** (SA311 closes the overwrite vector): cloud
  uploads never replace an existing key, but fixed upload paths carry no organization or user
  segment and row/tenant deletion has no generic cleanup. The structural fix is a media-asset
  owner/key model.
- **Org hierarchy authorization has one rank rule but no single policy seam** (SA311):
  `role_outranks_actor` guards member role changes and removals; other owner/admin checks stay per
  view and form.
- **The generator's Jinja environment disables autoescape for every template, including HTML**: it
  is safe only while every rendered value is validated; a future project-name/module field rendered
  into HTML would be an injection sink. No live injection found.
- **`start.sh` carries a second database-connection constructor** (prior arch observation); the
  runtime-role split is sound, and the backup path resolves its own privileged connection without a
  third launcher mode.
- **`TenantModelAdmin` uses a request-supplied org selector** while content routes use the session
  authority (prior arch/coherence watchlist); the documented superuser-only staff policy is the only
  guard.

## Tooling gaps

- **Stripe test-mode contract coverage is credential-gated**: `test_stripe_contract.py` creates a
  real subscription Checkout when `STRIPE_TEST_SECRET_KEY` is set and enumerates every
  metadata-key constant against Stripe's 40-character limit; the late subscription and invoice
  replays live in `tests/test_subscriptions.py`, and the live case skips without credentials.
- **S3 overwrite coverage is fake-backend only**: `test_manifest_adapter.py` runs the module
  backend's name allocator against a recording connection and proves two sequential and two
  barrier-forced concurrent same-filename uploads get distinct keys; no live-bucket upload is
  exercised.
- **No image dimension-before-decode test**: add a compressed high-pixel fixture and assert
  rejection before `Image.load()`.
- **CRM owner coverage is serializer- and view-level**: a foreign owner is a 400 on create and its
  name is hidden from the list; a live membership-removal round trip is not exercised.
- **Secret scanning is working-tree-only (fixed 2026-10-25)**: `check_secret_scanning.py` now runs
  `gitleaks dir` and `gitleaks git` over every commit reachable from `HEAD`, so a deleted credential
  stays visible. Value-level exemptions moved out of `gitleaks.toml` into
  `scripts/secret_scan_suppressions.json`, where each finding fingerprint carries an owner, a
  rationale, a decision reference, and an expiry; an expired or unused entry fails the gate, and a
  shallow clone fails closed.
- **Unwired or weak gates (fixed 2026-10-25)**: `security-negative-probes` is registered in all four
  executable contexts (`make check-security-negative-probes`, alias `make security-negative-probes`);
  `check-module-seals` is registry-bound in the publish context and still reachable manually as
  `make check-module-seals`; `sync_migration_hashes.py --check` is the registered
  `check-migration-hashes` gate; `check_generated_workflow_lint.py` is registered and acquires the
  pinned actionlint release when absent; the coverage QUIET modes now capture output around the
  same commands instead of bypassing the policy; the CSRF gate rejects a class-level `csrf_exempt`
  dispatch and checks only the named per-handler exemption; the org-context gate refuses
  `from ... import current_org` and every attribute use through a bound `current_org` module object;
  rule 17 treats a computed adapter dispatch as destructive by construction. Each tightened gate
  has a fixture control.
- **Gate parity (fixed 2026-10-25)**: CI and the local `make` lanes now share the coverage, secret
  scanning, and security-probe commands; `QUIET` no longer changes which command runs.

## Watchlist and accepted trade-offs

Every prior trigger was re-evaluated this pass; all are **not fired** unless stated. New watchlist
items are near-findings that fail a §0 gate today or deliberate behaviors with a named promotion
trigger. The chain pass reads this list.

| ID | Concern | Trigger that would promote/revoke | This pass |
|---|---|---|---|
| `orgs-role-mixin-checks-request-org` | `OrgRoleMixin.dispatch` checks `resolve_request_org()` while `get_organization()` prefers the URL slug | a new path sets `request.org` on `/orgs/<slug>/` for a non-superuser | not fired: the only setters remain `current_org.py`/`_api_views.py` (unchanged in the delta) |
| `backups-upload-restore-by-model-permission` | uploaded-dump restore needs `change_backuppolicy` + `QUICKSCALE_BACKUPS_ALLOW_RESTORE=true` | that permission granted to non-superuser staff while restore is enabled | not fired: no permission change in the delta; with the runtime-role fix, revisit the trust model |
| `single-sync-worker-vendor-calls` | one sync worker plus Stripe's default stalls all requests | `WEB_CONCURRENCY` > 1 in production or a vendor latency incident | not fired: `start.sh` still defaults to 1; it now amplifies `billing-webhook-status-applied-out-of-order` |
| `migrate-runs-per-replica` | `start.sh` migrates on every boot | more than one replica | not fired: still the single-replica path |
| `social-config-error-served-200` | DRF payload views return 200 with `str(exc)` | a new raise of `SocialConfigurationError` | not fired: 0 raises |
| `account-deletion-hook-exception-text` | undeclared reconcile hooks flash `str(exc)` | a documented host extension point for that hook | not fired: module-extension.md still limits it to module declarations |
| `deploy-existing-settings-module-never-corrected` | deploy keeps an existing `DJANGO_SETTINGS_MODULE` | an older Railway service fails to boot | not fired: unchanged |
| `generated-project-automation-local-only` | the generated-automation gate is local only | a generated-artifact regression reaches a release | not fired: unchanged; the E2E grep regression is a separate gap |
| `orgs-provider-id-check-blocks-migrate` | the conformance ERROR blocks `check`/`migrate` (deliberate) | a contract-vintage step that does not list it | not fired: deliberate |
| `crm-stage-seed-lost-on-commit-failure` | an `on_commit` seed failure leaves an org without stages | a report of an org without stages | not fired: unchanged |
| `development-workflow-intermittent-root-500` | one unreproduced 500 on `/` in E2E | a recurrence with a traceback | not fired: no new evidence |
| `core-e2e-poetry-cache-install-candidates` | Poetry “Unable to find installation candidates” | a recurrence with a fresh cache | not fired: no new evidence |
| `orgs-contextvar-leak-on-db-error` | `org_scope` restores the DB GUC inside the atomic before restoring the ContextVar; a DB error in the body can skip the ContextVar restore | a caller catches a DB error inside `org_scope` and continues | not fired: request middleware resets at the boundary; a background loop would promote it |
| `orgs-personal-membership-not-owner` | any membership in an `is_personal` org is treated as the user's personal org | an invitee in a personal org plus a switch back to solo mode | not fired: the documented path is one-way promote-to-SaaS; no current reproducer |
| `orgs-purge-unclassified-models` | the purge plan covers marker-derived tenant models; a plain `organization_id` project model survives | a project adds such a model and the CI isolation check is bypassed | not fired: the generated CI check fails on unclassified models; W005 is warning-only at runtime |
| `tenant-admin-org-selector` | `TenantModelAdmin` trusts a POST/GET org UUID; superuser-only staff is a policy, not a server check | a non-superuser staff account is created | not fired: documented policy is superuser-only; keep it in mind for operator training |
| `billing-webhook-payload-retention` | `WebhookEvent.payload` stores full Stripe customer/invoice PII; the org purge declares `SKIP` and account anonymization scrubs only email/name | a customer erasure/retention policy covers webhook payloads | not fired: the module declares the SKIP treatment; add a retention job instead of silently deleting an audit log |
| `billing-provider-erasure` | no Stripe Customer/invoice deletion or anonymization after account/org removal | a privacy policy or contract requires provider-side erasure | not fired: accounting retention may be intentional; decide explicitly |
| `billing-refunds-disputes` | `charge.refunded`, `charge.dispute.created`, `invoice.voided` are ignored; credits are not reversed | the product adds refunds/disputes to the billing contract | not fired: refunds are an explicit non-goal; the `REFUND` enum is unused |
| `auth-email-verification-none` | the auth module ships `ACCOUNT_EMAIL_VERIFICATION="none"` with open registration | a capability is granted on an unverified email match | not fired: default is explicit and configurable; org invites require the token as a second secret |
| `auth-account-deletion-no-reauth` | the account-delete POST needs only the session + CSRF (empty `Form`) | a threat model requires elevation for irreversible self-service deletion | not fired: the confirmation page is deliberate; password/MFA re-auth is a policy choice |
| `templates-local-media-production` | production defaults to `FileSystemStorage` under the ephemeral container; `/media/` is not served outside DEBUG | a media-bearing project deploys without the storage module | not fired: the operations doc warns and blog/listings require `storage`; the storage module's default backend is still `local` |
| `templates-healthcheck-liveness` | the healthcheck is DB-free; a broken DB still reports healthy | a deployment with a misconfigured runtime URL is routed traffic | not fired: liveness vs readiness is a deliberate choice; add a readiness probe |
| `notifications-pre-signature-db-read` | `ingest_webhook_event` loads the settings snapshot (DB) before verifying the Svix signature | sustained unauthenticated traffic to the webhook endpoint | not fired: one cheap `exists()` per request; add a throttle or verify the signature before the read |
| `media-storage-orphans` | blog/listing media and avatars are deleted with the row only; no storage cleanup | an erasure/retention obligation covers media objects | not fired: the public-media contract defers this; add a cleanup job |
| `backups-artifact-path-trust` | download/restore/purge treat a restored row's `local_path`/`snapshot.local_root_path` as authoritative | a crafted/restored DB row reaches the backup admin | not fired: the trusted-match upload path is the intended boundary; treat post-restore rows as data |
| `social-cache-bulk-invalidation` | Django admin bulk delete does not invalidate the social public payload cache | a bulk delete is used on published social links | not fired: no bulk-delete workflow documented; add a post-delete signal |
| `postcss-selector-parser-build-time-advisory` | **accepted** `GHSA-rj75-hqrm-r3gf` / `postcss-selector-parser@6.1.4`, dev-only build-time, owner Track 2, expires 2026-11-22 | a dependency/lockfile or exposure change; before expiry | carried: the current JS lock still resolves 6.1.4; the acceptance evidence was not re-run. Re-check `pnpm audit` and `pnpm audit --prod` on the next dependency change |

The accepted advisory's evidence and recheck rule are the prior record: the dependency is a
dev-only build-time path in the React starter (`tailwindcss` → `postcss-selector-parser@6.1.4`);
both runtime images copy only `static/frontend/assets` and `favicon.svg`, never `node_modules`;
`pnpm audit --prod` was clean at acceptance. A finding with no matching accepted entry blocks
release.

## Questions that would change severity

- **Does any generated project run `quickscale_backups_create` rather than a manual `pg_dump`?** A no
  makes the backup findings latent for that deployment (S4 watchlist) but does not fix the shipped
  engine; a yes keeps S2.
- **Is self-hosted Compose a supported production path, or only a dev convenience?** This decides
  the generated production deployment artifact: a supported path needs a production Compose profile;
  a dev-only path needs one documented production path (architectural audit F4).
- **Does the project use Stripe Invoicing or one-off invoices on the same customer?** A no demotes
  `billing-invoice-payment-failed-unscoped` to S4; a yes keeps S3.
- **Are all `/admin/` staff accounts superusers, with no tenant user ever granted `is_staff`?** A yes
  keeps `tenant-admin-org-selector` a policy watchlist; a no promotes it toward a finding.

## Coherence hand-offs

- `tenant-admin-org-selector`: `TenantModelAdmin` resolves the org from a request POST/GET value
  while content routes resolve it from the session; the population of admin classes does not agree
  on the authority. For the coherence audit (also arch watchlist `admin-tenant-authority`).
- `notifications-pre-signature-db-read`: the public Svix webhook has no throttle while the public
  forms/listing/blog endpoints do; the public-endpoint population diverges. For the coherence audit.

## Reconciliation log

- 2026-10-20 — prior pass `30b0b6b1` recorded no open findings; regenerated in the v8 format.
- 2026-10-20 — `beta-migrate-existing-recipient-no-dirty-guard`: new (introduced by `cca2eac9`).
- 2026-10-20 — `notifications-message-status-aggregate-race`: new (pre-existing; noted in the SA272
  (a) commit message, previously untracked).
- 2026-10-20 — `forms-retention-skips-null-ip-rows`: new (long-standing).
- 2026-10-20 — all 13 watchlist items: carried (trigger not fired; evidence in the table).
- 2026-10-23 — `postcss-selector-parser-build-time-advisory`: **accepted** (dev-only build-time
  advisory in QuickScale's React starter and `bap-web`; production audits clean; owner Track 2;
  expires 2026-11-22).
- 2026-10-23 — `braces-build-time-advisory`: **withdrawn** (GHSA-vfj7-8cjw-p6xm withdrawn
  2026-10-23; both full audits no longer report it, so no exception is recorded).
- 2026-10-24 — `cli-remove-accepts-path-traversal`: fixed by SA317 (bare-slug validation plus an
  inside-`modules/` containment assertion before any deletion).
- 2026-10-24 — `cli-apply-force-never-forces`: fixed by SA317 (the force path stages a generation
  and swaps it in with rollback).
- 2026-10-24 — `beta-migrate-existing-recipient-no-dirty-guard`: fixed by SA317 (the in-place path
  refuses a recipient with uncommitted tracked changes).
- 2026-10-24 — `notifications-message-status-aggregate-race`: still-open (S4; no parent lock added).
- 2026-10-24 — `forms-retention-skips-null-ip-rows`: still-open (S4; still `.exclude(ip_address=None)`).
- 2026-10-24 — `postcss-selector-parser-build-time-advisory`: accepted, carried (the current JS lock
  still resolves 6.1.4; the acceptance evidence was not re-run; a fresh `pnpm audit` is residual risk).
- 2026-10-24 — 13 prior watchlist items: carried (all triggers not fired; evidence in the table).
- 2026-10-24 — `orgs-role-mixin-checks-request-org`: carried (no new `request.org` setter).
- 2026-10-24 — `backups-upload-restore-by-model-permission`: carried (no permission change).
- 2026-10-24 — `allow-bypassrls-serving-undetected`: **resolved** (SA318: generated production
  serving refuses the flag; the generated isolation lane runs under the restricted runtime role).
  This also closes the "Generated-project CI never exercises RLS under the runtime role" tooling-gap
  entry, which is removed.
- 2026-10-24 — `single-sync-worker-vendor-calls`: carried (default worker count still 1).
- 2026-10-24 — `migrate-runs-per-replica`: carried (single-replica path).
- 2026-10-24 — `social-config-error-served-200`: carried (0 raises).
- 2026-10-24 — `account-deletion-hook-exception-text`: carried (no host extension point).
- 2026-10-24 — `deploy-existing-settings-module-never-corrected`: carried.
- 2026-10-24 — `generated-project-automation-local-only`: carried (E2E grep is a separate gap).
- 2026-10-24 — `orgs-provider-id-check-blocks-migrate`: carried (deliberate).
- 2026-10-24 — `crm-stage-seed-lost-on-commit-failure`: carried.
- 2026-10-24 — `development-workflow-intermittent-root-500`: carried.
- 2026-10-24 — `core-e2e-poetry-cache-install-candidates`: carried.
- 2026-10-24 — **new open:** `billing-subscription-checkout-metadata-key-too-long`,
  `backups-run-under-runtime-role`, `crm-deal-owner-cross-tenant`,
  `media-s3-fixed-path-overwrite`, `orgs-admin-can-demote-owner`,
  `generated-compose-called-production-runs-debug`, `generated-redis-cache-missing-client`,
  `forms-null-optional-field-500`, `billing-webhook-status-applied-out-of-order`,
  `billing-invoice-payment-failed-unscoped`, `billing-credit-services-missing-org-scope`,
  `billing-debit-not-idempotent`, `billing-checkout-double-submit`,
  `backups-restore-drops-own-artifact-row`, `backups-prune-no-keep-last`,
  `backups-restore-not-atomic`, `backups-creation-lock-expires-live`,
  `auth-profile-email-change-desync`, `cli-remove-accepts-path-traversal`,
  `dockerignore-bakes-local-backups`, `cli-apply-force-never-forces`,
  `e2e-generated-ci-contract-stale-grep`, `publish-pypi-no-skip-existing`,
  `media-image-decode-before-dimension-cap`, `orgs-bulk-delete-leaves-zero-owners`,
  `orgs-admin-org-delete-blocked`, `orgs-slug-new-shadows-route`,
  `backups-validate-action-view-permission`, `backups-dump-files-world-readable`,
  `backups-filename-second-resolution-collision`, `forms-csv-export-materializes-all-values`,
  `forms-option-values-not-validated`, `generated-readme-examples-invalid`,
  `billing-zero-credit-plan-webhook-loop`, `auth-deletion-logs-pii`.
- 2026-10-24 — **new watchlist:** `orgs-contextvar-leak-on-db-error`,
  `orgs-personal-membership-not-owner`, `orgs-purge-unclassified-models`,
  `tenant-admin-org-selector`, `billing-webhook-payload-retention`,
  `billing-provider-erasure`, `billing-refunds-disputes`, `auth-email-verification-none`,
  `auth-account-deletion-no-reauth`, `templates-local-media-production`,
  `templates-healthcheck-liveness`, `notifications-pre-signature-db-read`,
  `media-storage-orphans`, `media-sync-manifest-traversal`, `backups-artifact-path-trust`,
  `social-cache-bulk-invalidation`.
- 2026-10-24 — reconciliation counts: prior still-open **3**; carried watchlist **13**; accepted
  **1**; resolved **1**; regressed **0**; withdrawn **0**; superseded **0**; new open **35**; new
  watchlist **16**. Total open **37** (S1 1 · S2 7 · S3 16 · S4 13).
- 2026-10-24 — `backups-run-under-runtime-role`: **resolved** (SA313: dump and restore resolve
  `QUICKSCALE_BACKUP_DATABASE_URL` or `DATABASE_URL` for the one command, refuse a `NOBYPASSRLS`
  role against FORCE-RLS tables, and a scratch PostgreSQL test dumps and restores every row).
- 2026-10-25 — `backups-restore-drops-own-artifact-row`, `backups-prune-no-keep-last`,
  `backups-restore-not-atomic`, `backups-creation-lock-expires-live`: **resolved** (SA322 (a):
  restore recreates and relinks its artifact/snapshot rows and fails visibly on a metadata failure,
  prune retains the newest complete snapshot and newest live artifact, `pg_restore` runs in one transaction, and the
  create lock is held for the whole run).
- 2026-10-25 — `backups-validate-action-view-permission`, `backups-dump-files-world-readable`,
  `backups-filename-second-resolution-collision`: **resolved** (SA322 (b): the validate action
  requires change permission and refuses a restoring or deleted artifact, backup directories and
  files are created owner-only, and filenames carry a random token).
- 2026-10-26 — `billing-subscription-checkout-metadata-key-too-long`: **resolved** (SA310: the
  subscription Checkout reference metadata key is 33 characters and a test enumerates every
  metadata-key constant and the rendered Checkout metadata against Stripe's 40-character limit;
  a credential-gated test-mode contract test exercises the real subscription Checkout).
- 2026-10-26 — `billing-webhook-status-applied-out-of-order`: **resolved** (SA310: subscription
  and invoice handlers retrieve the provider's current subscription under the organization's
  provider mutex and apply its status, so a late delivery cannot overwrite a newer provider
  status; tests replay a late update after deletion and a late failure after payment).

- 2026-10-26 — `crm-deal-owner-cross-tenant`: **resolved** (SA311: `DealDetailSerializer` rejects
  an owner with no membership in the request organization, and `DealListSerializer` returns an
  empty `owner_name` for a foreign user; regression tests cover create rejection, same-org
  acceptance, and the read filter).
- 2026-10-26 — `media-s3-fixed-path-overwrite`: **resolved** (SA311: the generated settings use the
  module-owned `quickscale_modules_storage._backends.UniqueKeyS3Storage`, which adds a random token
  to the allocated key within the field's `max_length`; a field too short for the token keeps the
  stock allocation. `file_overwrite: False` stays as a second guard. A fake-connection test
  stores two same-filename uploads, and a barrier-forced concurrent pair, under distinct keys with
  both payloads preserved; the storage README documents the custom-config equivalent).
- 2026-10-26 — `orgs-admin-can-demote-owner`: **resolved** (SA311: `role_outranks_actor` refuses a
  member mutation whose target role outranks the actor, wired through `RoleChangeForm.clean_role`
  and both removal paths with platform operators exempt; HTML and JSON tests target an OWNER).
- 2026-10-26 — `forms-null-optional-field-500`: **resolved** (SA311: `_create_field_values`
  normalizes a JSON `null` to the empty string on both the accepted and honeypot persistence
  branches; regression tests assert 201 and an empty stored value, never 500).
