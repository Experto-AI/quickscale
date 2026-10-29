# Railway Deployment Guide

> Railway guides: [deploy](railway.md) · [operations](railway-operations.md) · [config as code](railway-config-as-code.md) · [troubleshooting](railway-troubleshooting.md)

## Overview

Railway.app is a modern platform-as-a-service (PaaS) that simplifies deploying Django applications with PostgreSQL databases. QuickScale-generated projects work with Railway's infrastructure.

**Important**: QuickScale's RLS boot guard requires a dedicated PostgreSQL runtime role with
``NOSUPERUSER``/``NOBYPASSRLS`` for production serving. ``quickscale deploy railway`` provisions it:
it sets the role's credentials as Railway variables, ``predeploy.sh`` applies migrations before the
new deployment starts, and the generated ``start.sh`` creates the role at boot (see
[Runtime Role Setup](#runtime-role-setup)).

## Prerequisites

- Railway account ([railway.app](https://railway.app))
- Node.js/npm installed (for Railway CLI)
  - **Note**: QuickScale will automatically install/upgrade Railway CLI if needed
  - Railway CLI v4.0+ is required for multi-service project support
- QuickScale project generated via `quickscale plan` + `quickscale apply`
- Git repository for your project (recommended)
- For **manual** deployments only: a PostgreSQL runtime role with ``NOSUPERUSER``/``NOBYPASSRLS``
  and ``RUNTIME_DATABASE_URL`` pointing to it (the CLI deploy provisions both)

**Automated Setup**: The `quickscale deploy railway` command automatically handles
Railway project setup, including the restricted runtime database role. Before that it:
- ✅ Checks if npm is installed (warns if missing)
- ✅ Installs Railway CLI if not present
- ✅ Upgrades Railway CLI if version < 4.0.0
- ✅ Handles authentication via browserless login if not authenticated
- ✅ Performs pre-flight checks (uncommitted changes, railway.json, Dockerfile, dependencies)

**Note**: Railway CLI v4+ is required for multi-service project support. Earlier versions may have API compatibility issues. QuickScale handles this automatically.

## Quick Start (CLI Automated)

**Recommended**: Use the QuickScale CLI command for the initial Railway setup:

```bash
# 1. Generate QuickScale project
quickscale plan myapp
quickscale apply
cd myapp

# 2. Deploy with one command (handles Railway project setup, PostgreSQL,
#    env configuration, and deployment)
quickscale deploy railway
```

The CLI command handles Railway project creation, PostgreSQL provisioning, env configuration,
the restricted runtime database role, and the initial deploy.

### What Gets Automated

The `quickscale deploy railway` command automatically:

**Pre-flight Checks:**
- ✅ Checks for uncommitted Git changes (warns but allows continuation)
- ✅ Verifies railway.json exists and is valid JSON
- ✅ Verifies Dockerfile exists
- ✅ Checks for required Railway dependencies (gunicorn, psycopg2-binary, dj-database-url, whitenoise)

**Railway CLI Management:**
- ✅ Checks if npm is installed (warns with instructions if missing)
- ✅ Installs Railway CLI via npm if not present
- ✅ Upgrades Railway CLI if version < 4.0.0
- ✅ Authenticates via browserless login if not logged in (shows pairing code)

**Deployment Setup:**
- ✅ Initializes Railway project (if needed) - reuses a linked directory and creates a project only when none is linked
- ✅ Adds PostgreSQL 18 database service
- ✅ Creates application service
- ✅ Retries `DATABASE_URL` reference linking while PostgreSQL finishes provisioning
- ✅ Reuses the service's SECRET_KEY, generating one only on the first deploy
- ✅ Sets DEBUG=False for production
- ✅ Sets DJANGO_SETTINGS_MODULE
- ✅ **Auto-generates public domain** (e.g., myapp-production-abc123.up.railway.app)
- ✅ **Auto-configures ALLOWED_HOSTS** with detected domain
- ✅ Deploys using railway.json config (pre-deploy migrations + static files handled automatically)
- ✅ Provides deployment URL and next steps

- ✅ Provisions the restricted runtime database role: sets ``RUNTIME_DB_ROLE``,
  ``RUNTIME_DB_PASSWORD``, and ``RUNTIME_DATABASE_URL``; ``predeploy.sh`` migrates before the new
  deployment starts and ``start.sh`` creates the role at boot

**Config-First Approach**: QuickScale uses Railway's config-as-code (railway.json) for deployment.
Generated projects delegate startup to `./start.sh` and schema work to `./predeploy.sh`
(`deploy.preDeployCommand`), which runs migrations and the cache table before the new deployment is
promoted; static files are collected during the Docker build.

**Note**: Railway projects support multiple services (your app + PostgreSQL). The CLI automatically handles service creation and configuration.

### CLI Command Options

```bash
# Specify project name (auto-detected from directory if omitted)
quickscale deploy railway --project-name myapp

# Continue only after adopting the generated-file changes named by the refusal
quickscale deploy railway --acknowledge-contract-vintage

# Record the adopted contract so later commands no longer need a flag
quickscale deploy railway --confirm-contract-adoption

# View all options
quickscale deploy railway --help
```

**Note**: Migrations and static file collection are handled automatically: the Railway pre-deploy
command runs `./predeploy.sh`, and the Docker build collects static files. The `--skip-migrations`
and `--skip-collectstatic` flags have been removed in favor of the config-first approach.

For an existing generated project, deploy checks the recorded `project_contract` before any
Railway preflight or remote operation. Projects older than the CLI's runtime-role contract stop and
name the required `settings/production.py`, `settings/base.py`, `db/init.sql`, `.env.example`,
`docker-compose.yml`, `start.sh`, `Dockerfile`, and `OPERATIONS.md` adoption work. For an existing
local database, run the role/grant SQL from `OPERATIONS.md` with `<password>` set to the password in
the adopted local `RUNTIME_DATABASE_URL`, or reset the disposable Compose database volume before
starting services. After manually adopting every named surface, use
`--acknowledge-contract-vintage` for that invocation, or `--confirm-contract-adoption` to record
the adoption in `.quickscale/state.yml`. Neither flag updates those files, and only the recording
option advances the recorded contract so later commands no longer need a flag.

## Manual Deployment (Alternative)

If you prefer manual control or need to customize the deployment process:

```bash
# 1. Generate QuickScale project
quickscale plan myapp
quickscale apply
cd myapp

# 2. Initialize Railway project
railway init

# 3. Add PostgreSQL database
railway add --database postgres

# 4. Create app service (Railway CLI v4+ required)
railway add --service myapp

# 5. Configure environment variables, one write per variable.
#    --skip-deploys keeps each write from starting a deployment of its own;
#    the single deploy below picks up every value.
railway variable set 'SECRET_KEY=your-secret-key' --service myapp --skip-deploys
railway variable set 'ALLOWED_HOSTS=myapp.railway.app' --service myapp --skip-deploys
railway variable set 'DEBUG=False' --service myapp --skip-deploys
railway variable set 'DJANGO_SETTINGS_MODULE=myapp.settings.production' --service myapp --skip-deploys
railway variable set 'RUNTIME_DATABASE_URL=postgresql://quickscale_runtime:password@host:port/db' --service myapp --skip-deploys

# 6. Deploy to app service
#    railway.json's deploy.preDeployCommand runs ./predeploy.sh, then the
#    platform starts ./start.sh.
railway up --service myapp
```

If the pre-deploy command fails, Railway does not promote the new deployment; the previous version
stays live. The shared database may already be ahead, so migrations must remain backward-compatible
until the new deployment is accepted. Run the bootstrap manually only when you deploy outside Railway's pre-deploy path:

```bash
railway run --service myapp ./predeploy.sh
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (generate a secure random string) | `django-insecure-...` |
| `DATABASE_URL` | PostgreSQL connection (auto-provided by Railway) | `postgresql://...` |
| `RUNTIME_DATABASE_URL` | PostgreSQL connection for the restricted runtime role (``NOSUPERUSER``/``NOBYPASSRLS``) — the production settings fail closed without this, using the superuser ``DATABASE_URL`` only for privileged one-shot commands. Set by the CLI deploy | `postgresql://quickscale_runtime:...@${{<selected-postgres-service>.PGHOST}}:...` |
| `RUNTIME_DB_ROLE` / `RUNTIME_DB_PASSWORD` | Credentials ``start.sh`` uses to create or update the runtime role. Set by the CLI deploy; leave unset for a hand-managed role | `quickscale_runtime` / `<generated>` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `myapp.railway.app` |
| `DEBUG` | Debug mode (always False in production) | `False` |
| `DJANGO_SETTINGS_MODULE` | Django settings module | `myapp.settings.production` |

### Module Vendor Credentials

The CLI deploy's environment batch covers only the core variables above. A project whose selected
modules gate startup on a vendor credential fails its module startup checks (and its migrations
step) until the credential is present on the service:

| Module | Variables |
|--------|-----------|
| `billing` | `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `QUICKSCALE_BILLING_WEBHOOK_SECRET` |
| `notifications` | `RESEND_API_KEY`, `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET` |
| `analytics` | `POSTHOG_API_KEY` |

Set each value through stdin so it never appears in process arguments, for example:

```bash
printf '%s' "$STRIPE_SECRET_KEY" | railway variable set STRIPE_SECRET_KEY --stdin --service myapp --skip-deploys
```

`--skip-deploys` leaves the running deployment alone; the value is live for the next boot, so set
credentials before the first deploy, or redeploy after setting them. The names above are the module
defaults; a project that configured its own ``*_env_var`` names reads the configured names instead.

### Optional Configuration

- `RAILWAY_ENVIRONMENT` - Detected automatically by Railway
- `PORT` - Auto-assigned by Railway (default: 8000)
- `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` - Client-IP forwarding trust for proxied
  deployments (production defaults: `True` / `1`). Set `USE_X_FORWARDED_FOR=False` only for a
  single-host deployment that terminates TLS itself; the generated production settings then also
  stop trusting `X-Forwarded-Proto`, so a direct plaintext client can neither suppress the HTTPS
  redirect nor make Django set secure cookies on a plaintext response. This is deliberate: the
  header used to be trusted unconditionally, which let a spoofed `X-Forwarded-Proto: https` mark a
  plaintext request secure.
- `QUICKSCALE_ALLOW_LOCAL_MEDIA` - Development and test only. Production serving refuses
  `FileSystemStorage` uploads by default because a redeploy replaces the container and loses them.
  Configure the storage module with S3-compatible object storage instead of setting this flag on a
  production service.

## Railway Multi-Service Architecture

Railway projects support multiple services within a single project. When you deploy a QuickScale application:

1. **PostgreSQL Service**: Created via `railway add --database postgres`
2. **Application Service**: Created via `railway add --service <app-name>` (Railway CLI v4+)

### Deployment Workflow

The `quickscale deploy railway` command follows this config-first workflow:

1. **Initialize Project**: Reuses the linked Railway project, and creates one only when the directory is not linked (see **Project Initialization** under Important Notes)
2. **Add PostgreSQL**: Provisions PostgreSQL 18 database service
3. **Create App Service**: Creates empty service container via `railway add --service <app-name>`
4. **Link DATABASE_URL Reference**: Links app `DATABASE_URL` to PostgreSQL with retry/backoff
5. **Generate Public Domain**: Auto-generates Railway domain (e.g., myapp-production-abc123.up.railway.app)
6. **Configure Environment (per-variable stdin)**: Writes each variable with `railway variable set KEY --stdin --skip-deploys` — values never reach process arguments, and earlier writes remain when a later one fails — so no deployment starts until step 7
   - SECRET_KEY (generated once, reused on re-deploy)
   - DEBUG=False
   - DJANGO_SETTINGS_MODULE
   - ALLOWED_HOSTS (using generated domain)
   - RUNTIME_DB_ROLE, RUNTIME_DB_PASSWORD (generated once, reused on re-deploy), RUNTIME_DATABASE_URL
     (see [Runtime Role Setup](#runtime-role-setup))
7. **Deploy Application**: Deploys using railway.json config via `railway up --service <app-name>`
   - railway.json defines Dockerfile builder
   - Dockerfile builds the image (collectstatic runs at build time via an inline
     ``QUICKSCALE_NON_DB_COMMAND=collectstatic`` prefix — a one-shot command-mode
     env var, never persistent environment configuration)
   - railway.json runs ``./predeploy.sh`` as ``deploy.preDeployCommand`` before the new
     deployment starts; it applies migrations and creates the cache table under the superuser
     ``DATABASE_URL`` with the one-shot      ``QUICKSCALE_PRIVILEGED_COMMAND`` prefix. A failed pre-deploy step aborts promotion and leaves
     the previous deployment serving, but the schema may already be ahead, so migrations must
     remain backward-compatible until the new deployment is accepted.
   - ``start.sh`` then creates or updates the runtime role and starts Gunicorn
   - Railway gates the deployment on ``/ready/`` (database reached, no pending migrations);
     ``/healthcheck/`` stays a DB-free liveness probe
   - Gunicorn defaults to 1 worker for the low-cost baseline unless ``GUNICORN_WORKERS`` or ``WEB_CONCURRENCY`` is set
   - No separate migration or static file steps needed

**Important Notes**:
- Environment variables are service-specific. The CLI automatically targets the correct service for each operation.
- **Optimized Variable Setting**: QuickScale writes each variable with `railway variable set KEY --stdin --skip-deploys` (values stay out of process arguments) and triggers one deployment after the writes succeed, so environment setup never causes multiple deployments.
- **Module Vendor Credentials**: the CLI's environment configuration writes the core variables only. Set any credentials the selected modules require (see [Module Vendor Credentials](#module-vendor-credentials)) on the service before the first boot, or the deployment fails its module startup checks.
- **Project Initialization**: the command checks the live link state with `railway status --json` and runs `railway init` only when the directory is not linked. Railway CLI 5.x keeps directory links in ``~/.railway/config.json`` and writes no ``.railway`` marker, so pre-creating or pre-linking the project with `railway init`/`railway link` is safe: the deploy reuses that link instead of creating a second project (the application service still takes the directory slug as its name). If the link state cannot be read, the command aborts rather than initializing again.
- Railway CLI v4+ requires explicit service creation with `railway add --service` before deployment.
- **Config-as-Code**: railway.json is generated with every `quickscale apply` and handles build/deploy configuration.
- **Automatic Migrations**: The generated `./predeploy.sh` runs before the new deployment starts via `deploy.preDeployCommand`, so migrations happen in the deployment environment with `DATABASE_URL` available and a failed migration never reaches serving. Migrations use the one-shot `QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL=""` inline prefix so the superuser `DATABASE_URL` is used (the runtime role has NOSUPERUSER/NOBYPASSRLS and cannot run DDL).
- **RUNTIME_DATABASE_URL Required**: Production serving fails closed without it. The CLI deploy sets it together with the role credentials; manual deployments must follow [Runtime Role Setup](#runtime-role-setup).
- **Live State Required**: Re-deploys abort when Railway variables or services cannot be read. The CLI never treats an unreadable environment as empty, and it requires exactly one PostgreSQL service before writing configuration.
- **DATABASE_URL Validation**: Production settings now validate DATABASE_URL is set and provide clear error messages if missing.
- **Default Scaling Baseline**: Generated projects start with one Railway replica and one Gunicorn worker. Increase replicas in Railway if you want more containers; set `GUNICORN_WORKERS` or `WEB_CONCURRENCY` if you want more workers inside each container. These controls are independent.

## Runtime Role Setup

QuickScale production settings require two database connections:

1. **``DATABASE_URL``** — the superuser connection (auto-provided by Railway). Used only for one-shot privileged work: ``predeploy.sh`` runs ``migrate`` and ``createcachetable``, and ``start.sh`` creates the runtime role.
2. **``RUNTIME_DATABASE_URL``** — a restricted runtime role with ``NOSUPERUSER``/``NOBYPASSRLS`` for production serving. This is the connection Django uses for web requests, background workers, and all normal database operations.

### Automatic (``quickscale deploy railway``)

The deploy sets three variables on the app service:

| Variable | Value |
|---|---|
| ``RUNTIME_DB_ROLE`` | ``quickscale_runtime`` |
| ``RUNTIME_DB_PASSWORD`` | a generated 48-character hex password |
| ``RUNTIME_DATABASE_URL`` | ``postgresql://quickscale_runtime:<password>@${{<selected-postgres-service>.PGHOST}}:${{<selected-postgres-service>.PGPORT}}/${{<selected-postgres-service>.PGDATABASE}}`` |

Host, port, and database are Railway reference variables on the PostgreSQL service, resolved at
deploy time. The pre-deploy bootstrap applies the schema first; on boot, when ``RUNTIME_DB_PASSWORD``
is set, ``start.sh`` connects with the superuser ``DATABASE_URL`` and creates the role, or updates
its password and attributes if it already exists, then grants DML on the ``public`` schema. The log
line is ``✅ Runtime role 'quickscale_runtime' created`` (or ``updated``).

Re-running the deploy reuses the existing ``RUNTIME_DB_PASSWORD``, so the container still serving
traffic keeps authenticating during the rollover. If the service has ``RUNTIME_DATABASE_URL`` but no
``RUNTIME_DB_PASSWORD``, the role is treated as operator-managed and none of the three variables is
written. ``start.sh`` refuses a ``RUNTIME_DB_ROLE`` that is the ``DATABASE_URL`` login itself or an
existing superuser, instead of demoting it.

The same re-run reuses the service's existing ``SECRET_KEY``, preserving sessions and signed links;
a new key is generated only when the live environment has none. If the CLI cannot read the live
variables, it stops without changing credentials or an operator-managed ``RUNTIME_DATABASE_URL``.

### Manual

Skip this when you used the CLI deploy. For a manual deployment, or to manage the role yourself,
leave ``RUNTIME_DB_PASSWORD`` unset (``start.sh`` then skips role creation) and:

1. Generate a URL-safe password and open psql on the Railway database:
   ```bash
   RUNTIME_DB_PASSWORD=$(openssl rand -hex 24)
   echo "$RUNTIME_DB_PASSWORD"
   railway connect primary-db
   ```
   ```sql
   CREATE ROLE quickscale_runtime WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD '<password>';
   GRANT CONNECT ON DATABASE railway TO quickscale_runtime;
   GRANT USAGE ON SCHEMA public TO quickscale_runtime;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO quickscale_runtime;
   GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO quickscale_runtime;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO quickscale_runtime;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO quickscale_runtime;
   ```
2. Set only ``RUNTIME_DATABASE_URL`` on the app service, in the same shell:
   ```bash
   railway variable set \
     "RUNTIME_DATABASE_URL=postgresql://quickscale_runtime:${RUNTIME_DB_PASSWORD}"'@${{primary-db.PGHOST}}:${{primary-db.PGPORT}}/${{primary-db.PGDATABASE}}' \
     --service myapp --skip-deploys
   ```
   Replace ``primary-db`` in both commands with the exact PostgreSQL service name shown by
   ``railway service list``. The double-quoted half expands your shell variable; the single-quoted
   half passes ``${{...}}`` to Railway literally.
3. Redeploy: ``railway up --service myapp --detach``.

**Why this is necessary**: The RLS boot guard in the orgs module raises ``ImproperlyConfigured`` at startup if the connected role has ``BYPASSRLS`` or ``SUPERUSER`` — both of which the default Railway superuser role has. Setting ``RUNTIME_DATABASE_URL`` to a restricted role satisfies the guard and keeps RLS enforcement active during production serving.

## Database Setup

Railway automatically provisions PostgreSQL and provides the `DATABASE_URL` environment variable. QuickScale's generated settings are pre-configured to use this.

## Static Files

QuickScale uses WhiteNoise for static file serving, which works out-of-the-box on Railway without additional CDN configuration.

## Additional Resources

- [Railway Documentation](https://docs.railway.app/)
- [Railway Django Template](https://railway.app/template/django)
- [Railway CLI Reference](https://docs.railway.app/develop/cli)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
