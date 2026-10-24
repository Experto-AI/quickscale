# QuickScale — User Manual (CLI)

How to use the `quickscale` CLI with worked examples. Installation: [README.md](../../README.md#installation).
Repository commands for contributors (bootstrap, tests, lint, E2E, Poetry): [development.md](development.md).
The authoritative command list is [implementation_contract.md § CLI Commands](implementation_contract.md#cli-command-matrix).

## QuickScale CLI

The CLI entry point is `quickscale`. After you install the package (via Poetry or an editable install), the following commands are available:

```bash
# Show general help and version
quickscale --help
quickscale --version

# Create a project configuration (interactive wizard)
quickscale plan <project_slug>
# Optional explicit Python package name
quickscale plan <project_slug> --package <python_package>

# Execute the configuration to generate a project
quickscale apply
```

**Theme Selection**:

QuickScale uses the `showcase_react` React + TypeScript SPA as its sole theme. The former `showcase_html` (pure HTML + CSS) secondary option has been removed. Plans created before the removal that specified `showcase_html` will fail closed on apply; switch to `showcase_react` or create a fresh configuration.

```bash
# Create configuration - theme is always showcase_react
quickscale plan myapp
# → Generates quickscale.yml with theme: showcase_react
```

**Important**: Theme selection is one-time during project generation. Generated code is yours to own and customize - no updates or tracking after initialization, except the QuickScale-managed files (`<package>/settings/modules.py`, `<package>/urls_modules.py`, `frontend/src/quickscaleSeam.d.ts`, `frontend/src/quickscaleSeam.keys.ts`, `.github/quickscale-ci-env`, and `quickscale-operations.md`), which apply, update, and remove regenerate. The backend-managed social transport remains theme-agnostic, but only fresh `showcase_react` auto-generates the public page files; existing projects must adopt those public pages manually if they want them.

**Typical flow** to create and run a generated project:

```bash
quickscale plan myapp
cd myapp             # Enter the created directory
quickscale apply     # Apply from within the project directory
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
```

The generated project is meant to be fully owned by the user — templates and guidance are in `generated_project_structure.md` and generated README files.

### 4.1) Development Commands

> **Status**: ✅ Available
>
> The following commands simplify Docker and Django operations, eliminating the need to remember complex `docker compose` and `docker exec` syntax.

Generated projects keep the `docker-compose.yml` file name, but QuickScale and this repo's guidance use the Docker Compose v2 plugin command syntax: `docker compose`.

**Docker Service Management**:
```bash
# Start Docker services
quickscale up
# Equivalent to: docker compose up -d

# Stop Docker services
quickscale down
# Equivalent to: docker compose down

# View service logs
quickscale logs           # All services
quickscale logs backend       # Backend service only
quickscale logs db        # Database only
# Equivalent to: docker compose logs [service]

# Check service status
quickscale ps
# Equivalent to: docker compose ps
```

**Development Tools**:
```bash
# Interactive bash shell in backend container
quickscale shell
# Equivalent to: docker exec -it <container> /bin/bash

# Run Django management commands
quickscale manage migrate
quickscale manage createsuperuser
quickscale manage collectstatic
# Equivalent to: docker exec <container> python manage.py <command>
```

**Typical Development Workflow**:
```bash
# Create new project
quickscale plan myapp
cd myapp
quickscale apply
# ↑ If docker.start: true (the default) and you did not pass --no-docker,
#   apply runs Docker startup here

# Services already running - check status:
quickscale ps                    # Check services
quickscale logs backend              # View logs

# OR if you need to start manually:
# (e.g., after 'quickscale down', on a fresh project with docker.start: false,
#  or after --no-docker)
quickscale up
# ↑ Use this when Docker was not auto-started or needs a restart

# If apply did not already run migrations for your path:
quickscale manage migrate

# Development
quickscale manage createsuperuser  # Create admin user
quickscale shell                 # Access container shell
quickscale manage test           # Run tests

# Shutdown
quickscale down                  # Stop services
```

**Note on Docker auto-start:**
- Any `quickscale apply` with `docker.start: true` and no `--no-docker` flag → QuickScale runs Docker startup and then migrations in the backend container
- Existing-project `quickscale apply` with `docker.start: false` → QuickScale skips Docker startup but still runs local migrations after dependency refresh
- Fresh-project `quickscale apply` with `docker.start: false`, and any `quickscale apply --no-docker` run, leave startup as a manual step
- After `quickscale down`, services stay stopped until you run `quickscale up` or another qualifying `quickscale apply`

See [roadmap.md](./roadmap.md) for historical implementation context and follow-on enhancements.

### 4.2) Module Management Commands

> **Status**: ✅ Available — `quickscale update`, `quickscale push --module <name>`, `quickscale status`, and `quickscale remove <module>`
>
> These commands manage installed modules while keeping manual `git subtree` flows available for advanced recovery scenarios.

```bash
# Check installed modules and project status
quickscale status

# Update installed modules
quickscale update

# Remove an installed module
quickscale remove blog

# Push improvements for a specific module back upstream
quickscale push --module blog
```

**Note**: Initial module embedding is handled by running `quickscale plan`, entering the generated directory, and then running `quickscale apply`. Manual `git subtree` commands remain useful for advanced debugging and recovery.

See [decisions.md: CLI Command Matrix](./implementation_contract.md#cli-command-matrix) for the authoritative command list.

#### What `quickscale update` changes, and what stays yours

`quickscale update` pulls module code into `modules/<name>/` through `git subtree` and regenerates
the QuickScale-managed files. It never rewrites the rest of what generation copied into your
project. Before pulling, it compares each `modules/<name>/` tree with the split commit recorded in
`.quickscale/state.yml` (the `pyproject.toml` dependency rewrite the embed path applies is
allowed). If a file was added, changed, or removed, the update stops before any pull and lists the
changed paths; restore the recorded content by reverting the edit before a normal update, or pass
`--allow-local-changes` to proceed. A change you want to keep must be published upstream and
brought in by that allowed update, since upstreaming alone does not move the recorded baseline.
`quickscale status` reports the same drift. The check needs the recorded split commit in the
project's history; when it is
unavailable, status reports the check as unverifiable rather than clean and the update refuses the
module unless `--allow-local-changes` is passed. An update also refuses to replace an applied
migration file while the module's version label is unchanged, and on every pull once the project's
applied vintage is at or after the migration-freeze release: from that release on, the applied
migration files are the database's schema identity, so replacing one would leave it unidentified
and an update refuses to proceed while that identity cannot be established from the embedded
module. A refused update restores the pre-update content, and a migration file the pull adds is
applied forward on the next `migrate`.

| Project part | Changed by `quickscale update`? | Notes |
| --- | --- | --- |
| `modules/<name>/` — module code, including its Django templates and static files | Yes | Local edits are unsupported; `quickscale update` refuses and lists them unless `--allow-local-changes` is passed. |
| Managed wiring and generated pages — `<package>/settings/modules.py`, `<package>/urls_modules.py`, `frontend/src/quickscaleSeam.d.ts`, `frontend/src/quickscaleSeam.keys.ts`, `.github/quickscale-ci-env`, and `quickscale-operations.md` | Yes | QuickScale-owned; never edit them. |
| `frontend/` — the React app | Never, except the managed `frontend/src/quickscaleSeam.d.ts` and `frontend/src/quickscaleSeam.keys.ts` above | Copied once at generation. New theme features reach existing projects only by manual adoption or migration. |
| `templates/` — generated `base.html`, error pages, and any overrides of module templates | Never | Module pages extend your `base.html`, which loads the token source from Vite in DEBUG and the compiled React stylesheet otherwise; shell changes in new releases arrive as manual adoption steps. An override hides every later change to the module template it replaces. |
| Other generated files (`settings/base.py`, `Dockerfile`, `start.sh`, CI) | Never | Changes arrive as documented adoption steps; `quickscale status` reports contract-vintage gaps. |
| Project-owned apps (for example a `properties` app) | Never | Yours entirely. |

**Contract-vintage enforcement.** Before `quickscale update`, an existing-project `quickscale
apply`, or `quickscale deploy railway` can combine current code with generated files, QuickScale
compares the adopted contract steps recorded in `.quickscale/state.yml` with the current
generated-project declaration and each installed module's declared step id. An old or
unknown legacy project stops before mutation and names each outstanding generated-project step and
each incompatible module or command, with its minimum and manual adoption steps. Fresh projects
without state keep the normal generation flow.

After completing every named adoption step, repeat the command with
`--confirm-contract-adoption` to record the adopted vintage in `.quickscale/state.yml`, or with
`--acknowledge-contract-vintage` to proceed for that invocation only. Neither flag rewrites the
user-owned generated files an adoption step names, but for `quickscale update` and `quickscale
apply` the confirming option also regenerates the QuickScale-managed files (`<package>/settings/modules.py`,
`<package>/urls_modules.py`, `frontend/src/quickscaleSeam.d.ts`, `frontend/src/quickscaleSeam.keys.ts`,
`.github/quickscale-ci-env`, and `quickscale-operations.md`) from the installed modules — which is how an adoption step whose
deliverable is managed wiring, such as the SA217 settings schema, completes. Such a step therefore
runs in this order: make and commit the manual edit (`quickscale update` refuses a dirty tree),
then run `quickscale update --confirm-contract-adoption`, which updates the embedded modules,
regenerates the wiring, and records the adoption; a confirmed no-delta `quickscale apply`
regenerates the wiring the same way. Only the recording option advances `project_contract`, and
once it does, the project needs no flag again until a later vintage increase.

For the shared-design step declared in the project-level contract, adopt all of the following
project-owned generated-file changes before recording adoption or using
`--acknowledge-contract-vintage`:

1. Compare and adopt the current `templates/base.html`, `templates/index.html`, and generated
   `templates/social/*.html` files. Together they select the live DEBUG Vite token source or the
   production `frontend/assets/index.css` build without letting a child host override the shell's
   choice; `base.html` also restores the persisted theme before paint.
2. Compare and adopt the current `frontend/vite.config.ts` static proxy and exact-Host rules. Vite
   must serve `/static/frontend/` itself while forwarding other Django-owned `/static` paths to
   Django. It derives `http://localhost:<QUICKSCALE_FRONTEND_HOST_PORT>` when the full origin is
   blank, rejects a missing Host, and rejects every differing HTTP/WebSocket Host, including Vite's
   normal localhost and IP exceptions.
3. Compare and adopt the current `<package>/settings/local.py` definitions of
   `QUICKSCALE_FRONTEND_HOST_PORT` and `QUICKSCALE_FRONTEND_ORIGIN`. Django uses the full
   browser-visible Vite origin when it renders the DEBUG stylesheet URL for both React and module
   pages, and rejects a non-canonical value instead of rendering a broken URL.
4. Compare and adopt the current `docker-compose.yml` frontend workflow. It runs `pnpm build`
   before `pnpm dev`, publishes `${QUICKSCALE_FRONTEND_HOST_PORT:-5173}:5173`, passes the port and
   optional full origin to Vite and Django, probes Vite with the effective origin's Host, and waits
   for the Vite-served stylesheet before the backend starts.
5. With DEBUG enabled, run `pnpm dev` in `frontend/`. For non-DEBUG deployments, run `pnpm build`
   so `static/frontend/assets/index.css` exists.

For the design-layer step declared in the project-level contract, adopt all of the following
project-owned changes before recording adoption or using `--acknowledge-contract-vintage`:

1. Create `frontend/design/` and move the current design source into it: `tokens.css` receives the
   current `frontend/src/index.css` content (Tailwind directives plus the `:root`/`.dark` custom
   properties), and `tailwind.preset.js` receives the current `frontend/tailwind.config.js`
   `darkMode`, `theme`, and `plugins` values. Add `fonts/` for project webfonts and `brand/` for
   brand assets when you need them.
2. Reduce `frontend/src/index.css` to `@import "../design/tokens.css";` and `frontend/tailwind.config.js`
   to a config whose `presets` consume `./design/tailwind.preset.js` while its `content` globs stay
   in the entry config.
3. Preserve relative references while moving the design. A `url()` or `@import` target that was
   relative to `frontend/src/` resolves one directory off after the move, so rebase it to the
   equivalent `../src/...` path (or move the referenced file into `frontend/design/`), and rebase
   relative JavaScript module specifiers in the Tailwind config the same way. Do not rebase
   Tailwind `content` globs: they resolve against the `frontend/` working directory, so rewriting
   them would break content scanning. The maintainer migration blocks and names any reference it
   cannot preserve instead of silently dropping a design resource.
4. Keep future color, radius, font, and brand changes in `frontend/design/`: nothing overwrites
   that folder on an upgrade or `quickscale apply` run, so it is the one design source for the
   React host and the Django-rendered shell.

Both stylesheet paths originate from the project-owned `frontend/design/tokens.css`: change colors and
radii there once, then keep Vite running for local development or rebuild for deployment. Module
styles consume those variables and do not require Tailwind to scan module templates. The default
browser-facing Vite port remains 5173; set `QUICKSCALE_FRONTEND_HOST_PORT` to a canonical decimal
from 1 through 65535 when Docker must publish a different host port. With a blank
`QUICKSCALE_FRONTEND_ORIGIN`, both servers derive
`http://localhost:<QUICKSCALE_FRONTEND_HOST_PORT>` and accept only that exact Host. Set the full
origin when the browser reaches Vite through another hostname or an HTTPS development tunnel. Use
a canonical HTTP(S) origin with no path, query, fragment, or user information.

**Keeping the frontend separate from updates.** It already is: `frontend/` is your code and no
QuickScale command rewrites it, except the managed `frontend/src/quickscaleSeam.d.ts` and
`frontend/src/quickscaleSeam.keys.ts` that apply,
update, and remove regenerate. What can still change under it is the backend it calls — module API
responses such as `/orgs/api/`, `/forms/api/<slug>/`, and the CRM API, and the page configuration
Django passes to the React bundle through `window.__QUICKSCALE__`. Keep the frontend in the same
repository and deploy: the Dockerfile builds it into `static/frontend/` and Django serves it on the
same domain, so session cookies and CSRF work without configuration. Moving it to a separate
repository or host adds CORS, cookie-domain, and `CSRF_TRUSTED_ORIGINS` configuration and a second
deploy to coordinate, and it does not remove the dependency on module APIs.

**Customizing a module template.** Prefer module settings and documented extension surfaces first
(see [module-extension.md](./module-extension.md)). When you do need a template override, copy the
module template into the project's `templates/` directory at the same relative path — for example,
`modules/auth/.../templates/account/login.html` becomes `templates/account/login.html`. Django
searches `templates/` before module templates, so your copy wins. The cost is drift: your copy no
longer receives the module's fixes to that template, including security and accessibility fixes,
and nothing warns you. Override as few templates as possible, keep a list of them, and do not
override a template only to restyle it. Module pages extend your `base.html`, so change shared
colors and radii in `frontend/design/tokens.css`, change shell structure in `base.html`, run `pnpm dev`
for DEBUG development or rebuild for deployment, and leave each page's own styling to the module
so updates keep delivering it.

When you override a module *page* template, copy its block structure exactly. A module page fills a
module-named block — `auth_content`, `billing_content`, `blog_content`, `listings_content`,
`crm_content`, `orgs_content`, `analytics_content`, or `forms_content` — not `content`, which the
module's own base template occupies. An override left on `{% block content %}` parses without error
and renders nothing.

**After every update:**

1. Run the project's test suite, including frontend tests.
2. Exercise the React pages that call module APIs (orgs, forms, CRM, and any project API).
3. For each overridden template, compare your copy with the updated module version
   (`git diff <commit-before-update> -- modules/<name>/templates/` shows what changed) and port
   relevant changes.
4. Check `quickscale status` for contract-vintage warnings and follow any adoption steps it names.

### 4.3) Plan/Apply Commands

> **Status**: ✅ Available
>
> These commands provide a Terraform-style declarative workflow for project generation, replacing the imperative `init` command.

**The `plan` command** creates a `quickscale.yml` configuration file through an interactive wizard:

```bash
# Create configuration interactively
quickscale plan myapp

# Save to custom location
quickscale plan myapp --output ./configs/myapp.yml

# Overwrite existing config
quickscale plan myapp --overwrite
```

The wizard guides you through:
1. **Theme selection**: The sole theme is `showcase_react` (the former `showcase_html` option has been removed). Fresh `showcase_react` generations scaffold Django-owned public `/social` and `/social/embeds` pages.
2. **Module selection**: Select optional modules to include. In the current implementation line, implemented first-party modules include analytics, auth, backups, billing, blog, crm, forms, listings, notifications, social, and storage. Billing now participates in public `quickscale plan`, `quickscale.yml`, and `quickscale apply` flows, and fresh starter output links into the billing module's Django-owned `/billing/pricing/` (public) and `/billing/dashboard/` (authenticated) pages without generating a starter-owned billing React page. `quickscale apply` requires `auth` whenever billing is selected.
3. **Docker configuration**: Configure Docker build/start options and optional first-start superuser creation

**Generated `quickscale.yml` example**:
```yaml
version: "1"
project:
  slug: myapp
  package: myapp
  theme: showcase_react
modules:
  blog: {}
  listings: {}
docker:
  build: true
  start: true
  create_superuser: false
```

`version` is the plan/apply schema version string, not the CLI release number.
Use `"1"` in `quickscale.yml`.

For `auth`, `quickscale.yml` accepts only the canonical desired-config keys
`registration_enabled`, `email_verification`, `authentication_method`, and
optional `session_cookie_age`. Legacy keys such as `allow_registration` and
`social_providers` are rejected during desired-config validation.

For `notifications`, local development keeps the default placeholder sender
`noreply@example.com` on the console email backend. If you set
`modules.notifications.resend_domain`, also set a real sender email plus the
API-key env-var reference before re-running `quickscale apply`; otherwise apply
stops instead of leaving a live-delivery target on the console backend.

In the current release line, `backups` is the admin/ops-first safety option in that set: private local artifacts are the default, optional private remote offload is supported, and generated local Docker and Railway PostgreSQL projects use PostgreSQL 18 custom dumps as the real backup/restore path. JSON artifacts are export-only rather than restore inputs, admin download and validate stay local-file-only in v1, and the BackupPolicy admin page exposes a guarded restore action only for row-backed local artifacts already present on disk. Exact filename confirmation and the existing environment gate remain required, admin restore never materializes remote-only artifacts, and CLI restore keeps its existing syntax. Restore compatibility uses the recorded migration content identity, not a version label: every capture records the hashes of each installed module's applied migration files, a recorded artifact whose migration file is missing or has changed content — or that records no identity — is refused before `pg_restore` runs, and a backup that is behind the installed modules restores and migrates forward through the DR snapshot route because the direct restore surfaces do not run migrations. Backup and restore connect under the active Django connection's TLS settings — `sslmode`, `sslrootcert`, `sslcert`, `sslkey`, and `connect_timeout` reach `pg_dump` and `pg_restore` as libpq environment variables — so a deployment that requires verified TLS fails its backup instead of silently completing it in plaintext; when serving, that is the `RUNTIME_DATABASE_URL` role connection, so TLS parameters must be carried there rather than only on `DATABASE_URL`, and on a CLI-managed Railway service that URL must be re-checked after `quickscale deploy railway`, which rewrites it without query parameters.

If you enable `backups` in a generated PostgreSQL project, you can restore a row-backed local artifact from the BackupPolicy admin page under those same confirmation and environment guards, or use the CLI when you need a stored artifact id restore:

```bash
poetry run python manage.py backups_create
poetry run python manage.py backups_restore 12 --confirm BACKUP_FILENAME.dump --dry-run

export QUICKSCALE_BACKUPS_ALLOW_RESTORE=true
poetry run python manage.py backups_restore 12 --confirm BACKUP_FILENAME.dump
```

JSON artifacts remain export-only, not restore inputs. Existing generated projects must manually adopt later Docker/CI/E2E PostgreSQL 18 tooling updates because `quickscale apply` does not rewrite those user-owned files.

### 4.4) Disaster Recovery and Environment Promotion Commands

> **Status**: ✅ Available
>
> QuickScale uses one `quickscale dr` command group for two related but separate operator jobs:
> - **Environment promotion** moves a validated source environment forward, such as local → Railway develop or Railway develop → Railway production.
> - **Disaster recovery / rehearsal** restores a stored snapshot into a recovery target, such as Railway production → Railway develop.
>
> In both cases, QuickScale keeps `database`, `media`, and `env_vars` as separate operational surfaces instead of one opaque full-environment action.

QuickScale exposes one top-level DR group:

```bash
quickscale dr --help
```

Supported route labels are fixed:

```text
local-to-railway-develop
railway-develop-to-railway-production
railway-production-to-railway-develop
```

For Railway-backed routes, pass explicit service names instead of relying on guessed naming:

```bash
# Capture a local source snapshot for later promotion into Railway develop
quickscale dr capture \
  --route local-to-railway-develop

# Capture from a Railway source service
quickscale dr capture \
  --route railway-develop-to-railway-production \
  --source-service myapp-develop

# Resume an interrupted capture on the same stored snapshot
quickscale dr capture \
  --route railway-develop-to-railway-production \
  --source-service myapp-develop \
  --resume <snapshot_id>
```

Build and persist a dry-run plan for a stored snapshot:

```bash
quickscale dr plan \
  --route railway-develop-to-railway-production \
  --snapshot-id <snapshot_id> \
  --source-service myapp-develop \
  --target-service myapp-production
```

`quickscale dr plan` evaluates three separate operational surfaces:

- `env_vars`: only a conservative allowlist of portable variables is eligible for automatic sync
- `database`: validates the stored authoritative dump against the target environment through `manage.py backups_restore --dry-run`
- `media`: validates source-side media sync using the stored media manifest and target runtime overrides

Provider-owned, secret, storage, host, and other environment-specific variables are surfaced as manual actions instead of being copied automatically.

Execute one or more surfaces explicitly:

```bash
quickscale dr execute \
  --route railway-develop-to-railway-production \
  --snapshot-id <snapshot_id> \
  --source-service myapp-develop \
  --target-service myapp-production \
  --database \
  --media \
  --env-vars \
  --rollback-pin-hours 24 \
  --rollback-pin-reason "pre-production cutover"
```

Resume the latest partial execute record for the same route and snapshot:

```bash
quickscale dr execute \
  --route railway-develop-to-railway-production \
  --snapshot-id <snapshot_id> \
  --source-service myapp-develop \
  --target-service myapp-production \
  --resume
```

Execution rules to remember:

- Choose at least one surface: `--database`, `--media`, or `--env-vars`, unless you use `--resume`, which retries only the surfaces from the latest execute record that still need follow-up
- Routes that involve Railway production require both `--rollback-pin-hours` and `--rollback-pin-reason` before first execution
- `snapshot_id` is the public stored-snapshot locator for DR workflows
- Database restore and media sync remain separate operational surfaces
- Media sync is source-side rather than a second restore path
- `quickscale dr execute --resume` uses stored verification records to skip completed work and retry only incomplete, failed, partial, or manual-required surfaces
- Railway-target `--media` requires the `storage` module backed by external object storage; Railway container disk is not a durable media target
- Raw secret values are never persisted into snapshot sidecars

Review the latest stored plan and execute records for one route:

```bash
quickscale dr report \
  --route railway-develop-to-railway-production \
  --snapshot-id <snapshot_id> \
  --source-service myapp-develop
```

Use `--json` on `capture`, `plan`, `execute`, and `report` when you need structured output for automation.

**The `apply` command** executes a configuration file to generate the project:

```bash
# Apply configuration (looks for quickscale.yml in current directory)
quickscale apply

# Apply specific configuration file
quickscale apply myconfig.yml

# Skip Docker operations
quickscale apply --no-docker

# Skip module embedding
quickscale apply --no-modules

# Force overwrite existing project directory
quickscale apply --force

# Continue an existing project after manually adopting every named contract step
quickscale apply --acknowledge-contract-vintage
```

**Apply execution order**:
1. Validate configuration file
2. Generate project from theme
3. Initialize git repository
4. Create initial commit
5. Auto-commit pending `quickscale.yml` / `.quickscale/` changes in existing projects so git subtree embed runs from a clean tree
6. Embed selected modules (via git subtree)
7. Refresh the Poetry lockfile and install dependencies
8. If this is an existing project and `docker.start: false`, run local migrations after the dependency refresh
9. If Docker auto-start is enabled (`docker.start: true` and not `--no-docker`), start Docker services and run migrations in the backend container
10. Otherwise leave startup as a manual next step; fresh projects without Docker auto-start and `--no-docker` applies also keep migrations as operator-managed steps

For existing projects, that pre-embed auto-commit is limited to QuickScale-managed config/state files. User-owned code changes are not swept into the commit.

**Installed module version tracking**:
- After embedding, QuickScale reads each installed module version from the embedded `modules/<name>/module.yml` file.
- `.quickscale/state.yml` records that canonical manifest version, and `.quickscale/config.yml` mirrors the same normalized value for legacy update/push compatibility.
- If a packaged module also exposes a package version string, treat `module.yml` as authoritative and expect the package metadata to match it.

**Typical Plan/Apply Workflow**:
```bash
# Step 1: Create configuration
quickscale plan myapp
# → Interactive wizard runs
# → Creates myapp/ directory with quickscale.yml inside

# Step 2: Enter project directory
cd myapp

# Step 3: Review configuration (optional)
cat quickscale.yml

# Step 4: Apply configuration
quickscale apply

# Step 5: Start development
quickscale ps                    # If Docker auto-start was enabled
quickscale manage createsuperuser

# If Docker auto-start was disabled on a fresh project, or you used --no-docker:
quickscale up
quickscale manage migrate
# or: poetry run python manage.py migrate

# Existing-project apply with docker.start: false already ran local migrations;
# use quickscale up only if you want Docker services running afterward.
```

**Benefits over `init`**:
- ✅ Declarative: Configuration is version-controllable
- ✅ Reproducible: Same config produces same project
- ✅ Reviewable: Preview before execution
- ✅ Modular: Includes module embedding in one step

### 4.5) Module Reconfiguration Lifecycle (Remove → Re-add)

Use this workflow when you need to change immutable module options or fully refresh a module embed.

**Step-by-step runbook**:

```bash
# 1) Remove module from current project
quickscale remove <module>

# 2) Re-add module through plan wizard (can update options)
quickscale plan --add <module>

# 3) Re-apply desired state (re-embeds module and reconciles state/wiring)
quickscale apply
```

**Do you need `quickscale apply` after remove?**
- **Yes** when you re-add a module or want QuickScale to reconcile desired/applied state and managed wiring.
- **Recommended** even after remove-only operations to ensure no config drift remains.

**Do you need `quickscale down` / `quickscale up`?**
- **Usually no manual restart step is required.** Existing-project `quickscale apply` still honors `docker.start`: it reruns Docker startup when `docker.start: true`, or runs local migrations when `docker.start: false`.
- Use `quickscale down` + `quickscale up` only if:
  - you already stopped services,
  - you changed Docker/runtime settings and want a clean restart,
  - or you need to verify startup from a clean container state.

**Database note**:
- `quickscale remove` removes module code and state references, but does not automatically drop module tables.
- If you need full data removal, run reverse migrations before/after removal as appropriate for your module.

**Quick decision guide**:
- Change mutable options only → `quickscale plan --reconfigure` + `quickscale apply`
- Change immutable options → `quickscale remove <module>` + `quickscale plan --add <module>` + `quickscale apply`
- Update embedded module code from upstream split branch → `quickscale update`

### Docker deployment

Generated projects include Docker support for both development and production. After generating a project:

```bash
# Development with Docker Compose v2
cd myapp
# The generator wrote .env with your host UID/GID. A fresh clone has none,
# so create it from .env.example and set DOCKER_UID/DOCKER_GID to your host IDs.
docker compose up --build
docker compose exec backend python manage.py migrate

# Production Docker build
docker build -t myapp:latest .
docker run -p 8000:8000 \
  -e SECRET_KEY=your-secret \
  -e ALLOWED_HOSTS=yourdomain.com \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  myapp:latest
```

The `Dockerfile` uses multi-stage builds (builder + runtime) for production efficiency. The generated project keeps the `docker-compose.yml` file name, and that file includes PostgreSQL for local development.

## Commands quick reference

**CLI Commands (Current)**:
- CLI help: `quickscale --help` (the full command tree, with every option and argument)
- Create config: `quickscale plan <project-slug>`
- Apply config: `quickscale apply [config.yml]`

**CLI Commands (Development)**:
- Start services: `quickscale up`
- Stop services: `quickscale down`
- View logs: `quickscale logs [service]`
- Service status: `quickscale ps`
- Container shell: `quickscale shell`
- Django commands: `quickscale manage <cmd>`; `quickscale manage --help` lists them by app
- Logs: `quickscale logs [service]`, where `service` is declared in `docker-compose.yml`

**CLI Commands (Modules)**:
- Update installed modules: `quickscale update`
- Push module changes: `quickscale push --module <name>`
- Remove module: `quickscale remove <module>`
- Project status: `quickscale status`

**CLI Commands (Disaster Recovery & Promotion)**:
- Capture a route source snapshot: `quickscale dr capture --route <label> [--resume <snapshot_id>]`
- Build a DR plan: `quickscale dr plan --route <label> --snapshot-id <snapshot_id>`
- Execute selected or retryable DR surfaces: `quickscale dr execute --route <label> --snapshot-id <snapshot_id> [--database] [--media] [--env-vars] [--resume]`
- Review stored route reports: `quickscale dr report --route <label> --snapshot-id <snapshot_id>`

## Git subtree

`quickscale plan`/`apply`, `quickscale update` and `quickscale push --module <name>` wrap the git-subtree mechanics; running `git subtree` by hand is unsupported for module management. Distribution model: [decisions.md § Module & Theme Architecture](decisions.md#module-theme-architecture).

## Where to find more information

- Technical decisions and authoritative feature scope: [decisions.md](./decisions.md)
- Scaffolding and generated project structure: [generated_project_structure.md](./generated_project_structure.md)
- Roadmap and release milestones: [roadmap.md](./roadmap.md)
- Generator templates (look under `quickscale_core/src/quickscale_core/generator/templates/`)
- Top-level README for newcomer guidance: [README.md](../../README.md)
