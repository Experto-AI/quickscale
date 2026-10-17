# Technical Audit — Open Items

Last verified at `30b0b6b1` (2026-10-16). This file is the single source of truth for defects
that are found but not yet fixed. Open items only: resolved items and pass history are in git
history. IDs are slugs. Never cite them from code, tests or other docs.

## Open findings

None (S1–S4: 0).

## Open question

- Is upgrading a live 0.88.0 install to 0.89.0 a supported path? If yes,
  `initial-migration-edited-in-place` becomes an S2 data-loss finding. Answer before 0.89.0 is
  published.

## Watchlist (latent; act only when the trigger fires)

| ID | Concern | Trigger |
|---|---|---|
| `initial-migration-edited-in-place` | billing/orgs/blog `0001_initial` were edited in place pre-1.0 with no data copy (for example `BillingCustomer` replaced `orgs.stripe_customer_id`). The freeze gate now blocks further edits | any supported upgrade from a live 0.88.0 install |
| `orgs-role-mixin-checks-request-org` | `OrgRoleMixin.dispatch` checks the role on `resolve_request_org()` (prefers `request.org`), while `get_organization()` prefers the URL slug. Fix: check on `get_organization()`, as `OrgApiBaseView.initial` does | a code path sets `request.org` on `/orgs/<slug>/` for a non-superuser |
| `backups-upload-restore-by-model-permission` | uploaded-dump restore needs only `change_backuppolicy` plus `QUICKSCALE_BACKUPS_ALLOW_RESTORE=true`, and a dump can write `auth_user` | that permission granted to non-superuser staff while restore is enabled |
| `allow-bypassrls-serving-undetected` | `QUICKSCALE_ALLOW_BYPASSRLS=1` plus a blank `RUNTIME_DATABASE_URL` silently disables RLS, and nothing flags it at startup | any tooling or docs setting it outside dev |
| `single-sync-worker-vendor-calls` | one sync gunicorn worker (60 s) and Stripe's 80 s SDK default: one slow vendor call stalls every request | more than one concurrent request in production, or a vendor latency incident |
| `migrate-runs-per-replica` | `start.sh` runs `migrate` on every boot, so concurrent replicas race | more than one replica |
| `social-config-error-served-200` | DRF payload views return 200 with `str(exc)` for `status=error` | any new raise of `SocialConfigurationError` |
| `account-deletion-hook-exception-text` | undeclared `reconcile_account_deletion_provider_state` hooks flash `str(exc)` to the user | a documented host extension point for that hook |
| `deploy-existing-settings-module-never-corrected` | deploy keeps an existing `DJANGO_SETTINGS_MODULE`, so a value derived wrongly before SA256 persists | a pre-SA256 Railway service fails to boot |
| `generated-project-automation-local-only` | the SA253 generated-automation gate runs locally only (no hosted PostgreSQL) | a generated-artifact regression reaches a release |
| `orgs-provider-id-check-blocks-migrate` | the orgs provider-id system check blocks `migrate` (deliberate) | a contract-vintage step that does not list it |
| `crm-stage-seed-lost-on-commit-failure` | the crm stage seed in `receivers.py` is lost if the surrounding commit fails | a report of an org without stages |
| `development-workflow-intermittent-root-500` | one unreproduced HTTP 500 on `/` in the development-workflow E2E | a recurrence with a retained backend traceback |
| `core-e2e-poetry-cache-install-candidates` | core E2E Poetry installs once failed with "Unable to find installation candidates" | a recurrence with a fresh isolated cache |

## Structural smells (no defect yet)

- No typed Stripe provider-adapter seam.
- Session-level advisory locks fail silently under transaction pooling.
- Outbound timeout policy is implicit.
- `start.sh` has a second database-connection constructor.
- `TenantMiddleware` declares path ownership twice.

## Tooling gaps

- No image-layer or broader IaC scanning.
