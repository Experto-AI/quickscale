# Technical Audit — Open Items

Audited: `39d455efb17c156ac0ced7d3a3ee260573ca0724` (v89) · 2026-10-20 · working tree dirty · repository public · prompt: deep-technical-audit v8

Source snapshot: HEAD `39d455ef` plus one unstaged change, `docs/others/arch-audit.md` (the companion
audit's deliverable; not product code and not read as evidence). No other staged, unstaged, or
untracked inputs. No drift between orientation and delivery.

This file is the single source of truth for defects that are found but not yet fixed. Cite a
finding only by its slug ID; section numbers are not stable.

## Orientation summary

QuickScale is a Python 3.12 / Django code generator and module platform: a CLI (`quickscale_cli`)
that plans and applies projects, a core (`quickscale_core`) that holds the generator templates,
manifest engine, and runtime seams, a set of Django modules (`quickscale_modules/*`: auth, orgs,
billing, forms, notifications, backups, crm, blog, listings, social, storage, analytics), and
maintainer-only tooling (`quickscale_devtools`, `scripts/`). There are two deployment realities:
**generated projects**, internet-facing Django apps on Railway/Docker (gunicorn, one worker by
default, more through `GUNICORN_WORKERS`/`WEB_CONCURRENCY`, PostgreSQL with FORCE RLS through a
NOBYPASSRLS runtime role); and **the maintainer toolchain**, which runs locally against operator
checkouts. The repository is public and has no `SECURITY.md`. Entry points: module HTTP/DRF views,
inbound webhooks (notifications/Svix, billing/Stripe), management commands with a `--trigger`
provenance, the CLI, and the beta-migration devtool. Actors: anonymous visitors, org members,
platform operators (superusers), schedulers, and the maintainer/operator. Crown jewels: cross-tenant
data behind RLS, credentials referenced by `*_env_var` options, billing state, backups/restore, and
the release pipeline. Configuration axes: per-module `enabled` switches, `QUICKSCALE_ALLOW_BYPASSRLS`,
`RUNTIME_DATABASE_URL` set or blank, trusted-proxy settings, worker count, and live or console email
delivery. Tooling baseline: ruff, mypy, the module-conventions harness, the migration-freeze and
coverage gates, CI. There is no image-layer or IaC scanning.

**Re-run mode.** The prior pass was at `30b0b6b1` (2026-10-16), in the older compact format. The delta
`30b0b6b1..HEAD` has 334 non-merge and 118 merge commits. About 40 % of the non-merge commits are
synthetic subtree-split replays of mainline commits, so the delta was taken as the net tree diff:
343 files, +15 417/−3 279, most of it `scripts/` harness code and tests.

**Delta classification.** Most commits are review-tracked (`v89: SAnnn` with validation trails).
Housekeeping-labelled commits that touched non-doc files were read in full: `99465fd6`, `84ff7ee9`,
and `272295eb` changed only comments, doc paths, `.cursor` rules, and Makefile help text. No
unreviewed behavioral change was found. The 118 merge commits are subtree-split merges and were not
read individually.

**Oracle list (used).** These are the declared invariants checked during the sweep:

- rule 17: commands own no transaction, and there is one scheduled-off refusal;
- rule 24: operator access is audit-logged with its identity;
- rule 44: one `is_platform_operator` helper, and the command-only operator entry stays in `management/commands/`;
- notifications: the forward-only delivery-status contract;
- forms: retention nulls IP and clears the user agent;
- orgs: the purge is atomic and fails closed on undischarged obligations.

**Data sensitivity.** The system handles personal data: form submissions with IP and user agent,
email recipients, and account data. It also holds tenant-scoped business data and references to
provider credentials, but never the credential values themselves.

**Guarantees and platforms.** RLS tenant isolation; purge atomicity, with a tombstone and
post-commit cache invalidation; once-only, forward-only webhook reconciliation (a unique idempotency
key plus a row lock); retention anonymization. Platform: PostgreSQL 18, Django 5.x, Python 3.12.

**Hotspot measurements.** The delta replaced the churn ranking. Fix density was not recomputed,
because split replays dominate the history (see memory note on synthetic commits).

### Coverage and residual risk

- **Read in full:**
  - the `current_org.py` operator-access change and its callers (forms views, `_presets.py`, `_retention.py`, account-removal discovery);
  - the purge transaction move (`_purge_support.py`, the purge command, `RemovalCoordinator.discharge_stage`/`finish`);
  - the `_scheduled_off.py` guard and its three callers;
  - the notifications adapter refactor and its manifest validation;
  - `_webhooks._record_delivery_event` and `_delivery._refresh_message_status`;
  - the orgs invite-throttle check-then-charge;
  - generator `ci_environment.py` and the head of `operations_page.py`;
  - `_railway_cli.is_railway_project_initialized`;
  - the beta-migration `--existing-recipient` path (`cca2eac9`).
- **Sampled:** backups command changes, and the housekeeping commits' code hunks.
- **Skipped:**
  - the `scripts/module_conventions` harness (+5 k lines, gate code, not shipped);
  - `loader_sections.py`, `conventions.py`, `seam.py`, `_settings_supplied.py`, `apply_support.py`, `_config.py`, `module_wiring_manager.py`;
  - forms `_presets.py` write paths beyond the operator-entry call.
- **Empirical check (§1e, trusted repo, pure function):** `notifications_runtime_email_backend` was
  called with 6 crafted option sets: placeholder sender, case-variant placeholder, padded
  placeholder, blank sender name, URL-shaped domain, and a valid configuration. All 5 invalid sets
  chose the console backend and the valid set chose Resend. This refuted the regression candidate.
- **Category activation:** active: I, II, III, IV, VI, IX, X (generator, CLI/devtool, multi-tenant,
  service/webhook) · inert this pass: V (no hot-path change in the delta), VII (no dependency or
  pipeline change read), VIII (test diffs not reviewed) · produced: II, IX, X.
- **§3b scenarios:**
  - *committed, reply lost*: traced for webhooks; the idempotency key plus the lock holds;
  - *interrupted between steps*: traced for the purge; atomic, and the cache step heals by tombstone retry;
  - the other four scenarios were not traced this pass.
- **Matrix:** partial. Only the delta's new or changed rows were filled (below). Unchanged
  populations carry the prior pass's verification.
- **What this silence does not cover:** the skipped files above, runtime behavior under multiple
  workers, Railway platform controls, and any test weakening in the delta.

## Machine-readable index

```yaml
schema: tech-audit/v6
audited: 39d455efb17c156ac0ced7d3a3ee260573ca0724
items:
  - {id: beta-migrate-existing-recipient-no-dirty-guard, status: open, severity: S4, category: X,
     title: "--existing-recipient overwrites a git-tracked recipient with no dirty-tree check",
     effort: Small, confidence: High, reality: maintainer-toolchain,
     anchors: [quickscale_devtools/src/quickscale_devtools/beta_migration/execution.py],
     first_seen: 2026-10-20, last_verified: 2026-10-20}
  - {id: notifications-message-status-aggregate-race, status: open, severity: S4, category: II,
     title: "Concurrent webhooks for sibling deliveries leave the message aggregate stale",
     effort: Trivial, confidence: Medium, reality: generated-project,
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/_delivery.py],
     first_seen: 2026-10-20, last_verified: 2026-10-20}
  - {id: forms-retention-skips-null-ip-rows, status: open, severity: S4, category: IX,
     title: "Retention never clears user_agent on submissions stored without an IP",
     effort: Trivial, confidence: High, reality: generated-project,
     anchors: [quickscale_modules/forms/src/quickscale_modules_forms/management/commands/_retention.py],
     first_seen: 2026-10-20, last_verified: 2026-10-20}
  - {id: orgs-role-mixin-checks-request-org, status: watchlist}
  - {id: backups-upload-restore-by-model-permission, status: watchlist}
  - {id: allow-bypassrls-serving-undetected, status: watchlist}
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
```

## Summary table

| ID | Sev | Cat | Title | Effort | Conf | Since |
|---|---|---|---|---|---|---|
| `beta-migrate-existing-recipient-no-dirty-guard` | S4 | X | `--existing-recipient` overwrites a git-tracked recipient with no dirty-tree check | Small | High | new |
| `notifications-message-status-aggregate-race` | S4 | II | Concurrent sibling-delivery webhooks leave the message aggregate stale | Trivial | Medium | new |
| `forms-retention-skips-null-ip-rows` | S4 | IX | Retention never clears `user_agent` on rows stored without an IP | Trivial | High | new |

No S1–S3 findings.

## Findings

### S4

- `beta-migrate-existing-recipient-no-dirty-guard` · `beta_migration/execution.py:80` `_copy_path`
  (→ `model.py:333` `_remove_path`), reached through `_run_beta_migration_iterate`
  (`execution.py:753`) when `BASELINE=1` is set.
  - **Defect.** Fresh-first runs `rmtree`/`unlink` and then copies over recipient paths. Since
    `cca2eac9` (today) the recipient can be the operator's persistent, git-tracked baseline, and
    nothing checks for uncommitted changes. Uncommitted edits in the baseline are destroyed without
    a warning; committed history survives. Before this commit the recipient was always freshly
    regenerated, so there was nothing to lose.
  - **Fix.** In `_validate_existing_recipient`, block when `git -C <recipient> status --porcelain`
    is non-empty, with a message telling the operator to commit or stash first.
- `notifications-message-status-aggregate-race` · `_delivery.py:248` `_refresh_message_status`, called
  from `_webhooks.py:271` under a lock on the delivery row only.
  - **Defect.** Two Svix events for different deliveries of one message commit concurrently. Each
    reads its sibling's pre-commit status (READ COMMITTED), and the last `message.save` keeps a
    stale aggregate, for example `sent` after every delivery is `delivered`. It stays that way until
    another event arrives. It needs more than one worker (`WEB_CONCURRENCY`, a supported mode) and a
    multi-recipient message. Only admin and operations views read the field. The SA272 (a) commit
    message names this as known, but it is tracked nowhere.
  - **Fix.** Before re-aggregating, lock the parent row with
    `NotificationMessage.objects.select_for_update().get(pk=...)`.
- `forms-retention-skips-null-ip-rows` · `_retention.py:74` and `:92`, `.exclude(ip_address=None)`.
  - **Defect.** A submission saved with a blank `REMOTE_ADDR` stores `ip_address=NULL`
    (`get_client_ip` returns `""`, and `GenericIPAddressField` stores NULL) but keeps its
    `user_agent`. Retention filters on a non-null IP, so that user agent is never cleared, which
    breaks the documented "nulls IP and clears user_agent" contract (README:127, release v0.75.0).
  - **Fix.** Select rows with `Q(ip_address__isnull=False) | ~Q(user_agent="")` in both the read and
    the update.

## Safeguard matrix (delta rows only)

| Population member | AuthZ / gate | Audit | Atomicity / idempotency | Notes |
|---|---|---|---|---|
| `operator_access(user=…)` (forms views) | `is_platform_operator` inside the CM, refusal logged before the GUC changes | rule 24 `user_id` + reason | `transaction.atomic()` at caller | verified |
| `operator_access_for_command` (forms presets/retention) | command-only (rule 44 harness) | `command` + reason | caller-owned atomic | verified |
| account-removal discovery seam | internal (no user) | reason only | atomic | unchanged by design |
| purge `_execute_purge_transaction` | `--confirm` under row lock, reserved-org guard | discharge bookkeeping post-commit | single atomic; `finish()` post-commit as before | verified |
| scheduled `--trigger` commands (backups create/prune, forms anonymize) | `require_scheduled_module_enabled`, default False | CommandError names the setting | n/a | verified, fails loud |
| notifications webhook ingest | Svix signature (unchanged) | event row | idempotency key + delivery row lock; message row unlocked | `notifications-message-status-aggregate-race` |
| invite throttles (HTML + API) | check-all-then-charge | n/a | cache get/set race inherent to DRF | verified |
| beta-migrate `--existing-recipient` | baseline/donor equivalence check | report | no dirty-tree guard | `beta-migrate-existing-recipient-no-dirty-guard` |
| generated `.github/quickscale-ci-env` | names reject `=`/whitespace/newline; values from shipped manifests | n/a | n/a | verified |

## Fix order and batching

The three findings are independent and each is a one-file change. If they are batched, land the two
module fixes (notifications, forms) together, each with a regression test. The devtool guard
`beta-migrate-existing-recipient-no-dirty-guard` remains open; SA299 (f) ran against a clean
baseline.

## Per-subsystem verdicts

- orgs operator access and purge (delta): clean, read in full.
- notifications adapter and live-delivery predicate: clean, empirically probed.
- notifications webhooks: `notifications-message-status-aggregate-race`.
- forms retention: `forms-retention-skips-null-ip-rows`.
- generator CI-env and operations page: clean (operations page head read only).
- CLI Railway link detection: clean, and it fails closed on every ambiguous state.
- devtools beta migration: `beta-migrate-existing-recipient-no-dirty-guard`.

## Clean sweeps and rejected candidates

- **`operator_access` signature change breaks callers.** Killed: every non-test caller passes
  `user=`, and the commands use the `_for_command` variant.
- **Purge discharge moved post-commit, so a routing error now lands after the delete.** Killed:
  `discharge_stage` is static bookkeeping that is deterministic per boundary and covered by tests,
  and `finish()` was already post-commit at `30b0b6b1`.
- **Shared scheduled-off guard defaults a missing `QUICKSCALE_FORMS_ENABLED` to False and blocks
  retention.** Killed: forms has declared the setting since `3420fbc8` (0.89), it projects into
  `settings/modules.py`, and the refusal is a loud CommandError.
- **Notifications predicate lost the case-insensitive placeholder check, blank-name check, or domain
  shape check.** Killed by the empirical probe; manifest `excludes`/`not_empty`/`pattern` cover all of
  them.
- **Invite check-then-charge opens a new race.** Killed: the window equals DRF's own get/set race.
- **CI-env file injection through an env-var name.** Killed: `=`, whitespace, and newline are
  rejected, and the values are manifest constants.
- **`99465fd6`/`84ff7ee9` docs-labelled commits change behavior.** Killed: comments, doc paths, and
  help text only.

## Structural smells

- No typed Stripe provider-adapter seam.
- Session-level advisory locks fail silently under transaction pooling.
- Outbound timeout policy is implicit.
- `start.sh` has a second database-connection constructor.
- `TenantMiddleware` declares path ownership twice.

## Tooling gaps

- No image-layer or broader IaC scanning.
- No test exercises two concurrent webhook ingests for one message under PostgreSQL, which would
  have caught `notifications-message-status-aggregate-race`.

## Watchlist and accepted trade-offs

Every trigger was evaluated this pass. All were **not fired**.

| ID | Concern | Trigger | This pass |
|---|---|---|---|
| `orgs-role-mixin-checks-request-org` | `OrgRoleMixin.dispatch` checks `resolve_request_org()`, while `get_organization()` prefers the URL slug | a path sets `request.org` on `/orgs/<slug>/` for a non-superuser | not fired: the only setters are `current_org.py:49/59` and `_api_views.py:95` (2026-10-02, predates the prior pass) |
| `backups-upload-restore-by-model-permission` | uploaded-dump restore needs only `change_backuppolicy` + `QUICKSCALE_BACKUPS_ALLOW_RESTORE=true` | that permission granted to non-superuser staff while restore is enabled | not fired: the restore change in the delta is help text only |
| `allow-bypassrls-serving-undetected` | `QUICKSCALE_ALLOW_BYPASSRLS=1` + blank `RUNTIME_DATABASE_URL` silently disables RLS | any tooling or docs set it outside dev | not fired: only the nightly test workflow, test Makefile targets, and docs that call it non-serving |
| `single-sync-worker-vendor-calls` | one sync worker plus Stripe's 80 s default stalls all requests | more than one concurrent request in prod, or a vendor latency incident | not fired: `start.sh` still defaults to 1 worker |
| `migrate-runs-per-replica` | `start.sh` migrates on every boot | more than one replica | not fired |
| `social-config-error-served-200` | DRF payload views return 200 with `str(exc)` | a new raise of `SocialConfigurationError` | not fired: 0 raises at both SHAs |
| `account-deletion-hook-exception-text` | undeclared reconcile hooks flash `str(exc)` | a documented host extension point for that hook | not fired: `module-extension.md:224` documents module declarations, text from 2026-09-24 |
| `deploy-existing-settings-module-never-corrected` | deploy keeps an existing `DJANGO_SETTINGS_MODULE` | an older Railway service fails to boot | not fired |
| `generated-project-automation-local-only` | the generated-automation gate is local only | a generated-artifact regression reaches a release | not fired |
| `orgs-provider-id-check-blocks-migrate` | the conformance ERROR blocks `check`/`migrate` (deliberate) | a contract-vintage step that does not list it | not fired |
| `crm-stage-seed-lost-on-commit-failure` | an `on_commit` seed failure leaves an org without stages | a report of an org without stages | not fired |
| `development-workflow-intermittent-root-500` | one unreproduced 500 on `/` in E2E | a recurrence with a traceback | not fired |
| `core-e2e-poetry-cache-install-candidates` | Poetry "Unable to find installation candidates" | a recurrence with a fresh cache | not fired |

## Questions that would change severity

- Do production generated projects run with `WEB_CONCURRENCY` > 1? A yes moves
  `notifications-message-status-aggregate-race` from Rare toward Common, and it also fires
  `single-sync-worker-vendor-calls`.
- Can a generated deployment receive requests with an empty `REMOTE_ADDR`, for example over a unix
  socket or a proxy setup? A no makes `forms-retention-skips-null-ip-rows` unreachable.

## Reconciliation log

- 2026-10-20 — prior pass `30b0b6b1` recorded no open findings; regenerated in the v8 format.
- 2026-10-20 — `beta-migrate-existing-recipient-no-dirty-guard`: new (introduced by `cca2eac9`).
- 2026-10-20 — `notifications-message-status-aggregate-race`: new (pre-existing; noted in the SA272 (a) commit message, previously untracked).
- 2026-10-20 — `forms-retention-skips-null-ip-rows`: new (long-standing).
- 2026-10-20 — all 13 watchlist items: carried (trigger not fired; evidence in the table).
