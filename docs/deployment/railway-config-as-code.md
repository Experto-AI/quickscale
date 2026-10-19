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
- Delegates runtime startup to `./start.sh`
- Runs migrations automatically on deployment
- Collects static files during the Docker build
- Starts Gunicorn with environment-driven worker defaults
- Implements health checks via `/healthcheck/`
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
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/healthcheck/",
    "healthcheckTimeout": 100
  }
}
```

**Key Features**:
- **Automatic Migrations**: `./start.sh` runs on every deployment before Gunicorn starts
- **Static Files**: The Docker build runs `collectstatic`, so runtime startup stays focused on migrations and app boot
- **Low-Cost Baseline**: Generated projects default to one Gunicorn worker unless you set `GUNICORN_WORKERS` or `WEB_CONCURRENCY`
- **Worker Precedence**: `GUNICORN_WORKERS` overrides `WEB_CONCURRENCY`; if neither is set, the generated startup uses `1`
- **Health Checks**: Railway monitors `/healthcheck/` for service health
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
- `restartPolicyType`: `"ON_FAILURE"` (recommended), `"ALWAYS"`, or `"NEVER"`
- `restartPolicyMaxRetries`: Max restart attempts (default: 10)
- `healthcheckPath`: Health check endpoint (e.g., `"/health/"`)
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
# railway.json startCommand: ./start.sh runs migrations + gunicorn starts
```

**Phase 5: Runtime Role - Automated**
```bash
# Set in the Phase 3 batch: RUNTIME_DB_ROLE, RUNTIME_DB_PASSWORD, RUNTIME_DATABASE_URL.
# start.sh creates the role with the superuser DATABASE_URL before migrating.
```

**Benefits**:
- ✅ One command deployment: `quickscale deploy railway`
- ✅ No manual ALLOWED_HOSTS configuration
- ✅ No separate migration steps
- ✅ Automatic domain generation
- ✅ Config-as-code for build and deployment
- ✅ **Optimized deployments**: Only ONE deployment triggered for environment setup instead of 4+ deployments

#### Migration Strategies

**QuickScale Approach: In startCommand** ✅ Recommended
```json
{
  "deploy": {
    "startCommand": "./start.sh"
  }
}
```
- ✅ No separate migration step needed
- ✅ Runs in container environment (not locally)
- ✅ Migrations guaranteed to run before server starts
- ✅ Generated startup keeps the low-cost baseline at 1 Gunicorn worker unless `GUNICORN_WORKERS` or `WEB_CONCURRENCY` is set
- ✅ Handles redeployments automatically
- ⚠️  May delay server start for large migrations (acceptable for most use cases)

**Alternative: Separate railway run** (Manual control)
```json
{
  "deploy": {
    "startCommand": "gunicorn myapp.wsgi --bind 0.0.0.0:$PORT"
  }
}
```
Then run: `railway run --service myapp /bin/bash -c "QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL=\"\" python manage.py migrate --noinput"`
- ✅ Can monitor migration output directly
- ✅ Doesn't block server start
- ❌ Requires manual CLI command after each deployment
- ❌ Easy to forget migration step

**QuickScale uses the first approach** because it ensures migrations always run and eliminates manual steps.

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
