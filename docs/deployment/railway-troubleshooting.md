# Railway Troubleshooting

> Railway guides: [deploy](railway.md) · [operations](railway-operations.md) · [config as code](railway-config-as-code.md) · [troubleshooting](railway-troubleshooting.md)

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

**Error: `bad substitution` when setting DATABASE_URL manually**:
```bash
bash: DATABASE_URL=${{primary-db.DATABASE_URL}}: bad substitution
```
**Cause**: Bash interprets `${{...}}` when double quotes are used.

**Solution**: Use single quotes so Railway receives the literal reference syntax:
```bash
railway variable set 'DATABASE_URL=${{primary-db.DATABASE_URL}}' --service <app-name>
```
Replace ``primary-db`` with the exact PostgreSQL service name shown by
``railway service list``.

**Pre-flight Check Failures**:

**Missing railway.json**:
```
❌ Error: railway.json not found in project root
```
**Solution**: Regenerate your project with `quickscale plan` + `quickscale apply` or create railway.json manually.

**Missing Dockerfile**:
```
❌ Error: Dockerfile not found in project root
```
**Solution**: Regenerate your project with `quickscale plan` + `quickscale apply` or create Dockerfile manually.

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
- The CLI runs `railway init` and creates the project; follow its prompts for the workspace and project name
- Check your Railway account has available projects (free tier limit: 2 projects)
- Verify network connectivity
- Ensure you're authenticated: `railway whoami`
- Prefer re-running `quickscale deploy railway`; it reuses a directory already linked with `railway link` (see **Project Initialization**)

**Deployment Timeout**:
- Large projects may take longer than expected (first deploy: 5-10 minutes)
- Check deployment status: `railway status`
- View build logs: `railway logs --service <app-name>`
- Migrations run automatically through railway.json's `deploy.preDeployCommand` (`./predeploy.sh`)

**Migration Failures**:

**Pre-deploy command**: migrations run in the pre-deploy container through `./predeploy.sh`
before the new deployment starts. A failure aborts the deployment and leaves the previous version
serving; check the deployment logs for the failed step. To run migrations by hand against the
deployed environment:

```bash
# Check deployment status first
railway status --service <app-name>

# Run the bootstrap command with the deployment's environment
# Use the one-shot env-pair prefix so the superuser DATABASE_URL is used
# (the runtime role has NOSUPERUSER/NOBYPASSRLS and cannot run DDL).
railway run --service <app-name> ./predeploy.sh
```

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

2. Link the PostgreSQL service to your app (CLI or dashboard):
   ```bash
   railway variable set 'DATABASE_URL=${{primary-db.DATABASE_URL}}' --service <app-name>
   ```
   Replace ``primary-db`` with the exact PostgreSQL service name shown by
   ``railway service list``.
   Or use dashboard linking:
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

**Problem**: QuickScale's production settings validate DATABASE_URL is set and provide clear error messages.

**Solution**: Follow the steps above to link PostgreSQL service to your app service.

**Note**: ``collectstatic`` during Docker build doesn't need ``DATABASE_URL``. The
Dockerfile invokes it with ``QUICKSCALE_NON_DB_COMMAND=collectstatic`` (a one-shot
inline prefix — never persistent environment configuration), and the production
settings seam supplies a dummy ``postgresql://`` connection when the real
``DATABASE_URL`` is absent. The ``DATABASE_URL``-required error only occurs when
running migrations or serving requests.

**Error: `ImproperlyConfigured: The connected PostgreSQL role has BYPASSRLS...`**:
This error from the RLS boot guard means ``RUNTIME_DATABASE_URL`` is either unset
or points to a superuser role. The production settings select ``RUNTIME_DATABASE_URL``
when serving requests; if it is missing or points to the superuser role, the boot
guard in the orgs module raises ``ImproperlyConfigured``.

**Solution**: Re-run ``quickscale deploy railway``, which sets the runtime role variables, or follow
[Runtime Role Setup — Manual](railway.md#manual) for a hand-managed role. If the log shows the runtime role
step failing, check that ``DATABASE_URL`` is linked to the superuser PostgreSQL service. The guard has two narrow
exemptions:
1. ``QUICKSCALE_PRIVILEGED_COMMAND`` set to a sanctioned DB command (``migrate``,
   ``createcachetable``) — used by ``predeploy.sh`` for one-shot privileged operations.
2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` — non-serving escape hatch for development/test only. It must
   never be set persistently or used while serving production requests.

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

`quickscale deploy railway` generates the domain and sets ALLOWED_HOSTS; this error occurs only with manual deployment.

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
   railway variable set ALLOWED_HOSTS=myapp-production-abc123.up.railway.app --service <app-name>
   ```

4. For multiple domains (including custom domains):
   ```bash
   railway variable set ALLOWED_HOSTS=myapp-production-abc123.up.railway.app,myapp.com,www.myapp.com --service <app-name>
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
