# Railway Deployment Guide

## Overview

Railway.app is a modern platform-as-a-service (PaaS) that simplifies deploying Django applications with PostgreSQL databases. QuickScale-generated projects work seamlessly with Railway's infrastructure.

## Prerequisites

- Railway account ([railway.app](https://railway.app))
- Node.js/npm installed (for Railway CLI)
  - **Note**: QuickScale will automatically install/upgrade Railway CLI if needed
  - Railway CLI v4.0+ is required for multi-service project support
- QuickScale project generated via `quickscale init`
- Git repository for your project (recommended)

**Automated Setup**: The `quickscale deploy railway` command automatically:
- ✅ Checks if npm is installed (warns if missing)
- ✅ Installs Railway CLI if not present
- ✅ Upgrades Railway CLI if version < 4.0.0
- ✅ Handles authentication via browserless login if not authenticated
- ✅ Performs pre-flight checks (uncommitted changes, railway.json, Dockerfile, dependencies)

**Note**: Railway CLI v4+ is required for multi-service project support. Earlier versions may have API compatibility issues. QuickScale handles this automatically.

## Quick Start (CLI Automated)

**Recommended**: Use the QuickScale CLI command for fully automated deployment:

```bash
# 1. Generate QuickScale project
quickscale init myapp
cd myapp

# 2. Deploy with one command (everything is automated!)
quickscale deploy railway
```

**That's it!** The command handles everything automatically. You don't need to install Railway CLI, login manually, or configure anything - QuickScale does it all for you.

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
- ✅ Initializes Railway project (if needed) - interactive prompts let you create/select project
- ✅ Adds PostgreSQL 16 database service
- ✅ Creates application service
- ✅ Generates and sets SECRET_KEY securely
- ✅ Sets DEBUG=False for production
- ✅ Sets DJANGO_SETTINGS_MODULE
- ✅ **Auto-generates public domain** (e.g., myapp-production-abc123.up.railway.app)
- ✅ **Auto-configures ALLOWED_HOSTS** with detected domain
- ✅ Deploys using railway.json config (handles migrations + static files automatically)
- ✅ Provides deployment URL and next steps

**Config-First Approach**: QuickScale v0.60.0+ uses Railway's config-as-code (railway.json) for deployment. Migrations and static file collection run automatically on every deployment via the startCommand configuration.

**Note**: Railway projects support multiple services (your app + PostgreSQL). The CLI automatically handles service creation and configuration.

### CLI Command Options

```bash
# Specify project name (auto-detected from directory if omitted)
quickscale deploy railway --project-name myapp

# View all options
quickscale deploy railway --help
```

**Note**: Migrations and static file collection are handled automatically by railway.json on every deployment. The `--skip-migrations` and `--skip-collectstatic` flags have been removed in favor of the config-first approach.

## Manual Deployment (Alternative)

If you prefer manual control or need to customize the deployment process:

```bash
# 1. Generate QuickScale project
quickscale init myapp
cd myapp

# 2. Initialize Railway project
railway init

# 3. Add PostgreSQL database
railway add --database postgres

# 4. Create app service (Railway CLI v4+ required)
railway add --service myapp

# 5. Deploy to app service
railway up --service myapp

# 6. Configure environment variables
# IMPORTANT: Set all variables in ONE command to avoid multiple deployments!
railway variables --set \
  SECRET_KEY=your-secret-key \
  ALLOWED_HOSTS=myapp.railway.app \
  DEBUG=False \
  DJANGO_SETTINGS_MODULE=myapp.settings.production \
  --service myapp

# Alternative (NOT RECOMMENDED - triggers 4 deployments instead of 1):
# railway variables --set SECRET_KEY=your-secret-key --service myapp
# railway variables --set ALLOWED_HOSTS=myapp.railway.app --service myapp
# railway variables --set DEBUG=False --service myapp
# railway variables --set DJANGO_SETTINGS_MODULE=myapp.settings.production --service myapp

# 7. Run migrations
railway run --service myapp python manage.py migrate
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (generate a secure random string) | `django-insecure-...` |
| `DATABASE_URL` | PostgreSQL connection (auto-provided by Railway) | `postgresql://...` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `myapp.railway.app` |
| `DEBUG` | Debug mode (always False in production) | `False` |
| `DJANGO_SETTINGS_MODULE` | Django settings module | `myapp.settings.production` |

### Optional Configuration

- `RAILWAY_ENVIRONMENT` - Detected automatically by Railway
- `PORT` - Auto-assigned by Railway (default: 8000)

## Railway Multi-Service Architecture

Railway projects support multiple services within a single project. When you deploy a QuickScale application:

1. **PostgreSQL Service**: Created via `railway add --database postgres`
2. **Application Service**: Created via `railway add --service <app-name>` (Railway CLI v4+)

### Deployment Workflow

The `quickscale deploy railway` command follows this config-first workflow:

1. **Initialize Project** (interactive): Select or create Railway project
2. **Add PostgreSQL**: Provisions PostgreSQL 16 database service
3. **Create App Service**: Creates empty service container via `railway add --service <app-name>`
4. **Generate Public Domain**: Auto-generates Railway domain (e.g., myapp-production-abc123.up.railway.app)
5. **Configure Environment (Single Batch)**: Sets all variables in one command to trigger only ONE deployment
   - SECRET_KEY (auto-generated)
   - DEBUG=False
   - DJANGO_SETTINGS_MODULE
   - ALLOWED_HOSTS (using generated domain)
6. **Deploy Application**: Deploys using railway.json config via `railway up --service <app-name>`
   - railway.json defines Dockerfile builder
   - Dockerfile builds the image (collectstatic runs at build time)
   - startCommand runs migrations at runtime (when DATABASE_URL is available) + starts gunicorn
   - No separate migration or static file steps needed

**Important Notes**:
- Environment variables are service-specific. The CLI automatically targets the correct service for each operation.
- **Optimized Variable Setting**: QuickScale sets all environment variables in a single batch command to trigger only ONE deployment instead of multiple deployments.
- Railway CLI v4+ requires explicit service creation with `railway add --service` before deployment.
- **Config-as-Code**: railway.json is generated with every `quickscale init` and handles build/deploy configuration.
- **Automatic Migrations**: Migrations run on every deployment via startCommand (at runtime with DATABASE_URL available), eliminating manual migration steps.
- **DATABASE_URL Validation**: Production settings now validate DATABASE_URL is set and provide clear error messages if missing.

## Database Setup

Railway automatically provisions PostgreSQL and provides the `DATABASE_URL` environment variable. QuickScale's generated settings are pre-configured to use this.

## Static Files

QuickScale uses WhiteNoise for static file serving, which works out-of-the-box on Railway without additional CDN configuration.

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

### Option 3: Config as Code (railway.json) ✅ Implemented

**Status**: Implemented in v0.60.0

Railway supports infrastructure-as-code through `railway.json` or `railway.toml` configuration files. QuickScale-generated projects include a railway.json file that configures deployment settings.

All QuickScale projects generated with `quickscale init` include a railway.json file that:
- Uses Dockerfile for consistent builds
- Automatically runs migrations on deployment
- Collects static files automatically
- Starts Gunicorn with proper configuration
- Implements health checks via /admin/ endpoint
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
    "startCommand": "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn myapp.wsgi --bind 0.0.0.0:$PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/admin/",
    "healthcheckTimeout": 300
  }
}
```

**Key Features**:
- **Automatic Migrations**: Runs on every deployment before server starts
- **Static Files**: Collected automatically (even though WhiteNoise handles serving)
- **Proper Binding**: Gunicorn binds to Railway's PORT environment variable
- **Health Checks**: Railway monitors /admin/ endpoint for service health
- **Auto-Restart**: Restarts up to 10 times on failure

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
- `numReplicas`: Number of replicas (default: 1)

#### Configuration Priority

Railway applies configuration in this order (highest priority first):
1. **railway.json / railway.toml** (config-as-code)
2. Railway Dashboard settings
3. Railway defaults

**Important**: Config-as-code ALWAYS overrides dashboard settings.

#### QuickScale's Hybrid Deployment Approach ✅ Implemented

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

**Phase 3: Environment Setup (Batch) - Automated**
```bash
# All variables set in ONE command to trigger only ONE deployment
railway variables --set \
  SECRET_KEY=<generated> \
  DEBUG=False \
  DJANGO_SETTINGS_MODULE=myapp.settings.production \
  ALLOWED_HOSTS=<detected-url> \
  --service myapp
```

**Phase 4: Deploy with Config - Automated**
```bash
railway up --service myapp        # Uses railway.json automatically
# Dockerfile: collectstatic runs at build time
# railway.json startCommand: migrations run at runtime + gunicorn starts
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
    "startCommand": "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn myapp.wsgi --bind 0.0.0.0:$PORT"
  }
}
```
- ✅ No separate migration step needed
- ✅ Runs in container environment (not locally)
- ✅ Migrations guaranteed to run before server starts
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
Then run: `railway run --service myapp python manage.py migrate`
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

## Troubleshooting

### CLI Deployment Issues

**Railway CLI Not Installed**:
✅ **This is now automated!** QuickScale automatically installs Railway CLI via npm if not present.

If you see an npm error:
```
❌ Error: npm is not installed
```
**Solution**: Install Node.js/npm first:
- Download from: https://nodejs.org/
- Then run `quickscale deploy railway` again (QuickScale will auto-install Railway CLI)

**Manual Installation** (if needed):
```bash
# Node.js/npm (recommended - cross-platform)
npm install -g @railway/cli

# macOS Homebrew
brew install railway

# Windows Scoop
scoop install railway
```

**Railway CLI Outdated**:
✅ **This is now automated!** QuickScale automatically upgrades Railway CLI to v4+ if your version is older.

You'll see output like:
```
⚠️  Railway CLI version 3.x.x is outdated (need 4.0.0+)
📦 Upgrading Railway CLI via npm...
✅ Railway CLI upgraded to 4.x.x
```

**Not Authenticated**:
✅ **This is now automated!** QuickScale automatically initiates browserless authentication if you're not logged in.

You'll see output like:
```
⚠️  Not authenticated with Railway
🌐 Starting browserless authentication...
   You will receive a URL and pairing code
   Visit the URL in your browser and enter the code
```

**Manual Login** (if needed):
```bash
# Standard login (opens browser)
railway login

# Browserless login (for SSH/remote/headless systems)
railway login --browserless
```
This displays a pairing code and URL you can use from any device.

**Pre-flight Check Failures**:

**Missing railway.json**:
```
❌ Error: railway.json not found in project root
```
**Solution**: Regenerate your project with `quickscale init` or create railway.json manually.

**Missing Dockerfile**:
```
❌ Error: Dockerfile not found in project root
```
**Solution**: Regenerate your project with `quickscale init` or create Dockerfile manually.

**Missing Dependencies**:
```
⚠️  Warning: Missing required Railway dependencies:
   - psycopg2-binary
   - dj-database-url
```
**Solution**: Add missing dependencies to pyproject.toml and run `poetry install`.

**Project Initialization Failed**:
```
❌ Error: Failed to initialize Railway project
Problem processing request
```
**Solution**:
- The CLI runs `railway init` interactively - follow the prompts to create/select a project
- Check your Railway account has available projects (free tier limit: 2 projects)
- Verify network connectivity
- Ensure you're authenticated: `railway whoami`
- Try manual initialization: `railway init`

**Deployment Timeout**:
- Large projects may take longer than expected (first deploy: 5-10 minutes)
- Check deployment status: `railway status`
- View build logs: `railway logs --service <app-name>`
- Migrations run automatically via railway.json startCommand

**Migration Failures**:

**Error: FileNotFoundError for logs directory (v0.59.0 and earlier)**:
```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/myapp/logs/django_error.log'
ValueError: Unable to configure handler 'error_file'
```

**Problem**: In older versions, `railway run` executed commands in your LOCAL environment, not the Railway container. The logs directory didn't exist locally.

**Solution for v0.60.0+ Users**:
✅ **This is now fixed!** Migrations run automatically via railway.json's startCommand in the Railway container, not locally. You shouldn't encounter this error.

**If Using Manual Deployment**:
Wait for deployment to complete, then run migrations in the container:
```bash
# Check deployment status first
railway status --service <app-name>

# Once deployed, run migrations in the Railway container
railway run --service <app-name> python manage.py migrate
```

**Best Practice (QuickScale Default)**:
Configure migrations in railway.json to run automatically:
```json
{
  "deploy": {
    "startCommand": "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn myapp.wsgi --bind 0.0.0.0:$PORT"
  }
}
```
This is the default in QuickScale v0.60.0+ projects.

**Other migration issues**:
- Verify DATABASE_URL is set correctly (Railway auto-provides this)
- Check migration files for syntax errors
- Review database logs in Railway dashboard
- Ensure PostgreSQL service is running: `railway service`
- Check deployment logs: `railway logs --service <app-name>`

### General Railway Issues

**Database Connection Errors**:

**Error: `connection to server at "localhost" failed`**:
```
django.db.utils.OperationalError: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

**Problem**: Django is trying to connect to `localhost:5432` instead of Railway's PostgreSQL service. This typically means `DATABASE_URL` environment variable is not set or not linked properly.

**Solution**:
1. Verify DATABASE_URL is linked to your app service:
   ```bash
   railway variables --service <app-name>
   ```
   You should see `DATABASE_URL` in the list. If not, it means the PostgreSQL service is not linked.

2. Link the PostgreSQL service to your app in Railway dashboard:
   - Go to your Railway project dashboard
   - Click on your app service
   - Go to "Variables" tab
   - Ensure "PostgreSQL" appears as a "Reference" variable source
   - If not, click "New Variable" → "Add Reference" → Select PostgreSQL service

3. Redeploy after linking:
   ```bash
   railway up --service <app-name> --detach
   ```

4. Check deployment logs to verify DATABASE_URL is available:
   ```bash
   railway logs --service <app-name>
   ```

**Error: `DATABASE_URL environment variable is not set`**:
```
ValueError: DATABASE_URL environment variable is not set.
Railway requires DATABASE_URL to connect to PostgreSQL.
```

**Problem**: QuickScale's production settings (v0.60.1+) validate DATABASE_URL is set and provide clear error messages.

**Solution**: Follow the steps above to link PostgreSQL service to your app service.

**Note**: `collectstatic` during Docker build doesn't need DATABASE_URL (it uses a dummy connection). The error only occurs when running migrations or starting the server.

**Other database issues**:
- Verify `DATABASE_URL` environment variable is set (Railway auto-provides this when linked)
- Check Railway PostgreSQL service is running: `railway service`
- Review connection logs in Railway dashboard
- Ensure the PostgreSQL service is in the same Railway project

**Static Files Not Loading**:
- WhiteNoise handles static files automatically
- No CDN or separate static file server needed
- Verify `STATIC_ROOT` is configured correctly

**502 Bad Gateway**:
- Verify application is listening on Railway's `PORT` env var (auto-provided)
- Check application logs for startup errors: `railway logs`
- Ensure Gunicorn is configured correctly in `Dockerfile`

**Build Failures**:
- Check `Dockerfile` syntax
- Verify all dependencies in `pyproject.toml`
- Review Railway build logs for specific errors
- Try rebuilding: `railway up --detach`

**ALLOWED_HOSTS Errors**:
```
ERROR Invalid HTTP_HOST header: 'myapp-production-abc123.up.railway.app'.
You may need to add 'myapp-production-abc123.up.railway.app' to ALLOWED_HOSTS.
```

**Problem**: Railway auto-generates a public URL, but Django blocks requests from unknown hosts.

**Solution for v0.60.0+ Users**:
✅ **This is now automated!** The `quickscale deploy railway` command auto-generates the domain and sets ALLOWED_HOSTS automatically. You shouldn't see this error if using the CLI deployment command.

**Manual Solution (if needed)**:
1. Get your deployment URL:
   ```bash
   # Check Railway logs for the actual URL
   railway logs --service <app-name>

   # Or generate a public domain if it doesn't exist
   railway domain --service <app-name>
   ```

2. The URL will be in format: `<app-name>-production-<hash>.up.railway.app`

3. Set ALLOWED_HOSTS with the detected URL:
   ```bash
   railway variables --set ALLOWED_HOSTS=myapp-production-abc123.up.railway.app --service <app-name>
   ```

4. For multiple domains (including custom domains):
   ```bash
   railway variables --set ALLOWED_HOSTS=myapp-production-abc123.up.railway.app,myapp.com,www.myapp.com --service <app-name>
   ```

**Note**: Setting environment variables triggers a redeployment. Wait for the new deployment to complete before testing.

**Multi-Service Issues**:

If you see "Multiple services found" errors:
- Railway CLI v4+ uses `--service` flag for multi-service projects
- Update Railway CLI: `npm update -g @railway/cli`
- Specify service explicitly: `railway logs --service myapp`
- The QuickScale CLI automatically handles service selection

If environment variables aren't taking effect:
- Verify variables are set for the correct service: `railway variables --service <app-name>`
- Environment changes require redeployment: `railway up --service <app-name>`
- Check service name matches your project directory name

**Getting Deployment URL**:

Railway auto-generates a public domain for your service. To find it:

**Method 1: Check logs**
```bash
railway logs --service <app-name>
```
Look for the URL in log errors (e.g., ALLOWED_HOSTS errors show the URL).

**Method 2: Generate public domain**
```bash
railway domain --service <app-name>
```
This creates a public domain if it doesn't exist and returns the URL.

**Method 3: Check Railway status** (doesn't support --service flag)
```bash
railway status
```
Note: In Railway CLI v4, `railway status` does not accept the `--service` flag.

**Method 4: Railway Dashboard**
1. Open https://railway.app
2. Navigate to your project
3. Click on your service
4. Look for "Deployments" tab
5. The URL will be shown under the deployment

The generated URL format is: `<service-name>-<environment>-<hash>.up.railway.app`

## Deployment Checklist

### CLI Method (Recommended) ✅ v0.60.0+
- [ ] Generate project: `quickscale init myapp`
- [ ] Initialize git repository (optional but recommended)
- [ ] Login to Railway: `railway login` or `railway login --browserless`
- [ ] Deploy with automation: `quickscale deploy railway`
  - ✅ Interactive project creation/selection
  - ✅ PostgreSQL database added
  - ✅ App service created
  - ✅ Environment variables configured (SECRET_KEY, DEBUG, DJANGO_SETTINGS_MODULE)
  - ✅ Public domain auto-generated
  - ✅ ALLOWED_HOSTS auto-configured
  - ✅ Deployment via railway.json (migrations + static files run automatically)
- [ ] Wait for deployment to complete (5-10 minutes for first deploy)
- [ ] Create superuser: `railway run --service myapp python manage.py createsuperuser`
- [ ] Verify site is accessible at provided URL (should load without errors)
- [ ] Test all critical functionality
- [ ] Configure custom domain (optional): Railway dashboard

**That's it!** The entire deployment is automated. No manual ALLOWED_HOSTS setup, no separate migration steps.

### Manual Method (Advanced Users)
- [ ] Generate project: `quickscale init myapp` (includes railway.json)
- [ ] Initialize git repository (optional)
- [ ] Create Railway project: `railway init`
- [ ] Add PostgreSQL database: `railway add --database postgres`
- [ ] Create app service: `railway add --service myapp`
- [ ] Configure environment variables:
  - `railway variables --set SECRET_KEY=<generated-key> --service myapp`
  - `railway variables --set DEBUG=False --service myapp`
  - `railway variables --set DJANGO_SETTINGS_MODULE=myapp.settings.production --service myapp`
- [ ] Generate public domain: `railway domain --service myapp`
- [ ] Set ALLOWED_HOSTS with domain: `railway variables --set ALLOWED_HOSTS=<domain> --service myapp`
- [ ] Deploy to Railway: `railway up --service myapp`
  - ✅ railway.json automatically runs migrations + collectstatic + gunicorn
- [ ] Wait for deployment to complete (5-10 minutes)
- [ ] Create superuser account: `railway run --service myapp python manage.py createsuperuser`
- [ ] Verify site is accessible (should load without errors)
- [ ] Test all critical functionality
- [ ] Configure custom domain (optional): Railway dashboard

**Note**: The automated CLI method is recommended as it eliminates manual steps and potential errors.

## Real-World Validation

✅ **Validated**: Railway deployment with config-first approach tested and validated in v0.60.0.

**Test Results**:
- ✅ Automated deployment flow works end-to-end
- ✅ PostgreSQL 16 provisioning successful
- ✅ railway.json config-as-code working correctly
- ✅ Automatic domain generation functional
- ✅ Auto-ALLOWED_HOSTS configuration working
- ✅ Environment variable management functional
- ✅ Database migrations execute automatically via railway.json startCommand
- ✅ Static files collected and served via WhiteNoise without issues
- ✅ SSL/HTTPS auto-provisioned by Railway
- ✅ Deployment completes in ~5-10 minutes for first deploy
- ✅ Multi-service architecture (PostgreSQL + App) working correctly

**v0.60.0 Enhancements**:
- Config-first deployment using railway.json (no manual migration steps)
- Automatic public domain generation
- Automatic ALLOWED_HOSTS configuration
- Eliminates ALLOWED_HOSTS errors completely
- Streamlined workflow: init → login → deploy → done

## Additional Resources

- [Railway Documentation](https://docs.railway.app/)
- [Railway Django Template](https://railway.app/template/django)
- [Railway CLI Reference](https://docs.railway.app/develop/cli)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)

## Deployment Helper Script

QuickScale projects include a deployment helper script:

```bash
./scripts/deploy_railway.sh
```

This script:
- Validates environment variables are set
- Runs database migrations
- Collects static files
- Provides deployment checklist
- Tests database connectivity

## Next Steps

After successful deployment:

1. **Monitor Application**: Use Railway's built-in logging and metrics
2. **Set Up Custom Domain**: Configure DNS and SSL certificates
3. **Enable Backups**: Configure automated PostgreSQL backups
4. **Scale Resources**: Adjust Railway resources based on traffic
5. **CI/CD Pipeline**: Automate deployments with GitHub Actions

## Support

For Railway-specific issues:
- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Railway Documentation: [docs.railway.app](https://docs.railway.app)

For QuickScale deployment questions:
- GitHub Issues: Check project documentation for support links
- User Manual: [user_manual.md](../technical/user_manual.md)

---

**Note**: This guide is based on QuickScale's generated project structure and Railway's best practices. The workflow has been validated with QuickScale-generated projects.
