# Cutover and rollback runbook — bap-web

SA191 rebuilds `bap-web` on current QuickScale with a **fresh production
database**. The production data cannot move by backup and restore: the v0.62
migration ledger is inconsistent with the current migration graph (recorded in
`MIGRATION_PROMPT.md`, SA191 slice (a)). This runbook is the executed
procedure. The steps are scripted, rehearsed on the SA191 scratch PostgreSQL 18
(recorded in `MIGRATION_PROMPT.md`, SA191 slice (e)), and leave the previous
deployment and its database untouched so they remain the rollback.

## What the cutover does

`scripts/cutover.sh` works on a fresh database:

1. checks that `DATABASE_URL` and `RUNTIME_DATABASE_URL` address the same
   database and that the runtime connection is NOSUPERUSER/NOBYPASSRLS,
2. applies migrations under the superuser privileged-command contract,
3. creates the site organization (`quickscale_orgs_create_site_org`),
4. reseeds the properties catalog through `scripts/reseed_catalog.sh` under the
   restricted `quickscale_runtime` role, never under BYPASSRLS,
5. reseeds the six service inquiry forms behind the contact page through
   `scripts/reseed_service_forms.sh` under the same role,
6. verifies the result (no unapplied migrations, system checks, catalog counts
   and the six service form schemas in the System org scope, RLS fail-closed
   probes, tenant-isolation conformance).

Every step is idempotent; re-running the script is safe. Users are re-invited
and media is carried separately; form submissions and other transactional rows
are not carried.

## Prerequisites

- Deploy the recipient service first (`quickscale deploy railway` or the target
  Railway project). On boot, `start.sh` creates the runtime role and applies
  migrations; the cutover script re-checks both and repeats the migration step
  idempotently.
- Export the variables in the environment that runs the script (never bake
  them into files):

  | Variable | Meaning |
  |---|---|
  | `DATABASE_URL` | superuser connection to the target database |
  | `RUNTIME_DATABASE_URL` | restricted runtime-role connection to the same database |
  | `SITE_ORG_SLUG` / `SITE_ORG_NAME` | the site organization to create, e.g. `bap-web` / `Buenos Aires Properties` |
  | `SITE_FORM_NOTIFY_EMAILS` | optional; notification addresses for the service forms — the live site used `info@buenosairesproperties.com`; unset seeds none |
  | `DJANGO_SETTINGS_MODULE` | `bap_web.settings.production` on the deployment |

- For a non-live rehearsal, also set the generated CI's placeholder credentials
  (`QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET`, `RESEND_API_KEY`,
  `POSTHOG_API_KEY`) so the enabled modules' startup checks pass. The
  notifications module refuses a malformed signing secret, so the webhook
  secret must be a `whsec_`-prefixed value whose remainder is valid base64 —
  the same value the managed `.github/quickscale-ci-env` carries.

## Running

Local, inside the project environment (the `poetry run` wrapper supplies the
interpreter for the script's `python` calls):

```bash
poetry run bash scripts/cutover.sh
```

On the Railway service, inside the container so the private database hostnames
resolve:

```bash
railway ssh --service <service> bash scripts/cutover.sh
```

None of the scripts print credentials. Both reseed scripts can also run on their
own to refresh content later (`scripts/reseed_catalog.sh`,
`scripts/reseed_service_forms.sh`); each refuses to write through anything but
a NOSUPERUSER/NOBYPASSRLS role. The service forms seed from
`SITE_FORM_NOTIFY_EMAILS` on their first creation (an explicit
`--notify-emails` argument wins over the variable); to change the addresses
later, edit the forms in the Django admin, or re-seed with
`scripts/reseed_service_forms.sh --overwrite --notify-emails <addresses>`
before users are invited (that deletes and recreates each form).

## Verification

`scripts/cutover.sh` ends with `Cutover steps complete.` only when:

- `migrate --check` reports no unapplied migrations,
- `manage.py check` passes (the two `quickscale_orgs.W006` personal-data
  warnings for the `properties` app remain until SA153 declares them),
- the seeded catalog matches the bundled JSON in the System org scope
  (3 agents / 12 properties / 48 images / 60 features), the six service forms
  exist, are active, and carry the live payload schema (`full_name`, `email`,
  `subject`, `project_context`, `gdpr_consent`), and unscoped reads return zero
  rows under RLS,
- `quickscale_orgs_check_tenant_isolation --postgres-only` passes (6 models).

Afterwards, smoke the public surfaces:

```bash
curl -fsS "https://<host>/healthcheck/"
curl -fsS "https://<host>/api/properties/" | head -c 200   # JSON with "count": 12
```

## Rehearsal (repeatable)

The rehearsal target is the SA191 scratch PostgreSQL 18 container
(`qs-bap-prod-scratch-pg`, `127.0.0.1:32768`), on a database of its own — never
the retained production-dump copy (`bap_prod_scratch`). The setup below resets
the rehearsal database and role first so the run reproduces the
rebuilt-from-empty path:

```bash
docker exec qs-bap-prod-scratch-pg psql -U postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS bap_cutover_rehearsal" \
  -c "DROP ROLE IF EXISTS quickscale_runtime"
docker exec qs-bap-prod-scratch-pg psql -U postgres -v ON_ERROR_STOP=1 \
  -c "CREATE ROLE quickscale_runtime WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD '<scratch-password>'"
docker exec qs-bap-prod-scratch-pg psql -U postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE bap_cutover_rehearsal"
docker exec qs-bap-prod-scratch-pg psql -U postgres -d bap_cutover_rehearsal -v ON_ERROR_STOP=1 \
  -c "GRANT CONNECT ON DATABASE bap_cutover_rehearsal TO quickscale_runtime" \
  -c "GRANT USAGE ON SCHEMA public TO quickscale_runtime" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO quickscale_runtime" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO quickscale_runtime"
```

Then export the variables for that database and run the script:

```bash
export DJANGO_SETTINGS_MODULE=bap_web.settings.production
export DATABASE_URL='postgresql://postgres:<scratch-password>@127.0.0.1:32768/bap_cutover_rehearsal'
export RUNTIME_DATABASE_URL='postgresql://quickscale_runtime:<scratch-password>@127.0.0.1:32768/bap_cutover_rehearsal'
export SITE_ORG_SLUG='bap-web' SITE_ORG_NAME='Buenos Aires Properties'
export SITE_FORM_NOTIFY_EMAILS='info@buenosairesproperties.com'
export QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET='whsec_YWFhYWFhYWFhYWFhYWFhYQ==' \
       RESEND_API_KEY=rehearsal-placeholder POSTHOG_API_KEY=rehearsal-placeholder
poetry run bash scripts/cutover.sh
```

Repeat the run to confirm idempotency (the organization becomes a no-op and
both seeds report unchanged content), serve the recipient against the fresh
database, and repeat the public smoke above. Re-run this rehearsal after the
pre-cutover repin to the sealed release.

## Rollback

Rollback restores the previous deployment **and** its database. The cutover
never writes to the pre-cutover database; the rehearsal proves the retained
copy's row-count fingerprint and migration-ledger hash are identical before and
after.

Retain before cutover, until the reseeded site is verified:

- the old repository and its Railway service, and the current deployment ID,
- the old PostgreSQL service and its database (do not migrate, rename, or
  delete it),
- the media originals at their current location.

To roll back:

1. Redeploy the previous service deployment from the Railway dashboard: open
   the service's **Deployments** tab, select the deployment recorded before the
   cutover, and choose **Redeploy**. The CLI's `railway redeploy` only
   redeploys the most recent deployment, so it is not a rollback.
2. Confirm its environment still references the retained pre-cutover database
   and media location.
3. Smoke the old site (home, contact, admin) and confirm listings remain hidden
   as before.
4. Keep the new site's database for inspection. Rows written on the new site
   since cutover are not carried back; transactional rows are not carried by
   design, and users are re-invited after the cutover is verified.
