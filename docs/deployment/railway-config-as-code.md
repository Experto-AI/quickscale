# Railway Config as Code

> Railway guides: [deploy](railway.md) · [operations](railway-operations.md) · [config as code](railway-config-as-code.md) · [troubleshooting](railway-troubleshooting.md)

## Deployment Options

### Option 1: Docker Deployment (Recommended)

Railway auto-detects the `Dockerfile` in QuickScale projects and builds using Docker.

**Benefits**:
- Exact production environment matching local development
- Full control over dependencies and build process
- Consistent across all deployment platforms

### Option 2: Nixpacks Deployment

Railway can auto-detect Django projects and build using Nixpacks.

**Benefits**:
- Faster builds
- Automatic dependency detection
- Simpler configuration

### Option 3: Config as Code (railway.json)

Railway supports infrastructure-as-code through `railway.json` or `railway.toml` configuration files. QuickScale-generated projects include a railway.json file that configures deployment settings.

All QuickScale projects generated with `quickscale apply` include a railway.json file that:
- Uses Dockerfile for consistent builds
- Runs `./predeploy.sh` as the pre-deploy command (migrations + cache table)
- Delegates runtime startup to `./start.sh` (runtime role + Gunicorn)
- Collects static files during the Docker build
- Starts Gunicorn with environment-driven worker defaults
- Gates the deployment on readiness (`/ready/`); `/healthcheck/` stays DB-free liveness
- Configures restart policy for reliability

#### Benefits of Config as Code
- ✅ Version-controlled deployment configuration
- ✅ Consistent deployments across environments
- ✅ No manual migration or collectstatic steps
- ✅ Override Railway dashboard settings
- ✅ Easier CI/CD integration
- ✅ Team collaboration on deployment settings

#### QuickScale's railway.json Template

QuickScale generates this railway.json configuration automatically:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "./start.sh",
    "preDeployCommand": ["./predeploy.sh"],
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/ready/",
    "healthcheckTimeout": 100
  }
}
```

**Key Features**:
- **Pre-Deploy Migrations**: `./predeploy.sh` runs before the new deployment starts; a failure aborts promotion and leaves the previous deployment live, so migrations must stay backward-compatible
- **Static Files**: The Docker build runs `collectstatic`, so runtime startup stays focused on role provisioning and app boot
- **Low-Cost Baseline**: Generated projects default to one Gunicorn worker unless you set `GUNICORN_WORKERS` or `WEB_CONCURRENCY`
- **Worker Precedence**: `GUNICORN_WORKERS` overrides `WEB_CONCURRENCY`; if neither is set, the generated startup uses `1`
- **Readiness Gate**: Railway monitors `/ready/`, which answers 200 only while the database is reached and no migrations are pending; `/healthcheck/` remains a DB-free liveness probe
- **Auto-Restart**: Restarts up to 10 times on failure

`numReplicas` is a separate Railway platform setting. If you add it later, it changes how many containers Railway runs, not how many Gunicorn workers each container starts.

#### Available Configuration Fields

**Build Configuration**:
- `builder`: `"DOCKERFILE"` (recommended), `"RAILPACK"`, or `"NIXPACKS"` (deprecated)
- `dockerfilePath`: Path to Dockerfile (default: `"Dockerfile"`)
- `buildCommand`: Custom build command
- `watchPatterns`: Files to watch for rebuilds

**Deploy Configuration**:
- `startCommand`: Command to start your service
- `preDeployCommand`: Command(s) to run after build and before the new deployment starts (QuickScale runs `./predeploy.sh` for migrations and the cache table)
- `restartPolicyType`: `"ON_FAILURE"` (recommended), `"ALWAYS"`, or `"NEVER"`
- `restartPolicyMaxRetries`: Max restart attempts (default: 10)
- `healthcheckPath`: Readiness endpoint (QuickScale uses `"/ready/"`; `/healthcheck/` is liveness)
- `healthcheckTimeout`: Health check timeout in seconds
- `numReplicas`: Number of replicas (default: 1). QuickScale does not generate this field today; replicas scale container count and are separate from Gunicorn worker count inside each container.

#### Configuration Priority

Railway applies configuration in this order (highest priority first):
1. **railway.json / railway.toml** (config-as-code)
2. Railway Dashboard settings
3. Railway defaults

**Important**: Config-as-code ALWAYS overrides dashboard settings.

#### QuickScale's Hybrid Deployment Approach

QuickScale uses a hybrid approach that combines CLI automation with config-as-code:

**Phase 1: Initial Setup (CLI) - Automated by `quickscale deploy railway`**
```bash
railway init                      # Create project (interactive)
railway add --database postgres   # Add PostgreSQL
railway add --service myapp       # Create app service
```

**Phase 2: Domain Generation - Automated**
```bash
railway domain --service myapp    # Generate public domain
```

**Phase 3: Environment Setup (per-variable stdin) - Automated**
```bash
# One write per variable: the value travels through stdin, never argv, and
# --skip-deploys triggers no deployment on its own.
printf '%s' '<value>' | railway variable set SECRET_KEY --stdin --service myapp --skip-deploys
printf '%s' '<value>' | railway variable set DEBUG --stdin --service myapp --skip-deploys
# ... SECRET_KEY, DEBUG, DJANGO_SETTINGS_MODULE, ALLOWED_HOSTS,
#     RUNTIME_DB_ROLE, RUNTIME_DB_PASSWORD, RUNTIME_DATABASE_URL
```

**Phase 4: Deploy with Config - Automated**
```bash
railway up --service myapp        # Uses railway.json automatically
# Dockerfile: collectstatic runs at build time
# railway.json preDeployCommand: ./predeploy.sh runs migrations + cache table
# railway.json startCommand: ./start.sh provisions the runtime role + gunicorn starts
```

**Phase 5: Runtime Role - Automated**
```bash
# Set in the Phase 3 batch: RUNTIME_DB_ROLE, RUNTIME_DB_PASSWORD, RUNTIME_DATABASE_URL.
# predeploy.sh applies the schema first; start.sh creates the role at boot.
```

**Benefits**:
- ✅ One command deployment: `quickscale deploy railway`
- ✅ No manual ALLOWED_HOSTS configuration
- ✅ No separate migration steps
- ✅ Automatic domain generation
- ✅ Config-as-code for build and deployment
- ✅ **Optimized deployments**: Only ONE deployment triggered for environment setup instead of 4+ deployments

#### Migration Strategies

**QuickScale Approach: In preDeployCommand** ✅ Recommended
```json
{
  "deploy": {
    "preDeployCommand": ["./predeploy.sh"],
    "startCommand": "./start.sh"
  }
}
```
- ✅ Runs after the image is built and before the new deployment is promoted
- ✅ Runs in the deployment environment with `DATABASE_URL` available
- ✅ A failed migration aborts promotion and leaves the previous deployment serving; migrations must stay backward-compatible because the shared schema may already be ahead
- ✅ Keeps schema changes out of the container boot path, so a restarted or replaced container does not replay migrations; rolling back the database is a separate, explicit operation
- ✅ Generated startup keeps the low-cost baseline at 1 Gunicorn worker unless `GUNICORN_WORKERS` or `WEB_CONCURRENCY` is set
- ✅ Handles redeployments automatically
- ⚠️  Holds the deployment (not serving traffic) while a large migration runs

**Alternative: In startCommand** ❌ Not used
```json
{
  "deploy": {
    "startCommand": "QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL=\"\" python manage.py migrate --noinput && ./start.sh"
  }
}
```
- ❌ Every boot mutates the schema, including restarts and rollbacks
- ❌ A failed migration crash-loops the service instead of preserving the previous deployment
- ❌ Multiple replicas race the same migration

**QuickScale uses the first approach** because it makes the schema transition an explicit deployment
step with a promotion boundary. It does not provide a database rollback: migrations must remain
backward-compatible until the new deployment is accepted.

**Readiness gate:** the deployment's `healthcheckPath` is `/ready/`. It answers 200 only while the
database is reached and no migrations are pending, so a deployment that skipped or failed the
pre-deploy step is never promoted. `/healthcheck/` stays a DB-free liveness probe.

#### Public Domain Generation

Generate Railway-provided public domain:
```bash
railway domain --service myapp

# With custom port
railway domain --service myapp --port 8000

# JSON output (for automation)
railway domain --service myapp --json
```

This generates a URL like `myapp-production-abc123.up.railway.app`.

#### Current Limitations
- Cannot configure environment variables via config file (use CLI or dashboard)
- Cannot manage services/databases via config (use CLI)
- File path must be absolute in Railway dashboard settings
- JSON syntax errors prevent deployment

#### References
- [Railway Config as Code Docs](https://docs.railway.com/reference/config-as-code)
- [Railway JSON Schema](https://railway.app/railway.schema.json)
- [Railway Django Template](https://github.com/railwayapp-templates/django)

## CI/CD Integration

Railway can deploy automatically from GitHub:

1. Connect your GitHub repository in Railway dashboard
2. Configure branch-based deployments (e.g., `main` → production)
3. Every push to main triggers automatic deployment
4. Use GitHub Actions for testing before Railway deployment
