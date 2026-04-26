# QuickScale — User Manual (commands)

This short manual explains the commands QuickScale contributors and users run most often: how to bootstrap the repository, run the test suite and linters, and use the `quickscale` CLI to generate projects.

<!--
QuickScale User Manual (commands) — scope and disambiguation

This file is a short, practical user manual focusing on QuickScale developer/user commands: how to bootstrap the repository, run tests and linters, and use the `quickscale` CLI.

What belongs in this file:
- Practical step-by-step commands and examples users should run locally (bootstrap, tests, linters, quickscale CLI usage, short troubleshooting tips).

What does NOT belong in this file (and where to put it):
- Architectural decisions, implementation scope, and tie-breakers → `decisions.md` (authoritative).
- Long-term roadmap, release milestones, and planning → `roadmap.md`.
- Package and generator scaffolding details (templates, deep structure) → `scaffolding.md` and template files in `quickscale_core`.
- User-facing getting-started narrative and marketing material → top-level `README.md`.

Keep this doc short and actionable. When in doubt, link to the authoritative doc (decisions.md / roadmap.md / scaffolding.md) for details.
-->

## Installation Methods

QuickScale can be installed in two ways:

### Method 1: Install from PyPI (Recommended)

**Quick install:**
```bash
pip install quickscale
```

**Or with Poetry:**
```bash
poetry add quickscale
```

**Usage:**
```bash
quickscale plan myapp       # Direct command
cd myapp
quickscale apply
```

### Method 2: Install from Source

**For those who prefer building from source:**
```bash
git clone https://github.com/Experto-AI/quickscale.git
cd quickscale
make install
```

**What this does:**
1. Builds `quickscale_core` and `quickscale_cli` packages
2. Installs them to your system Python (via pip)
3. Makes `quickscale` command available globally

**Usage:**
```bash
quickscale plan myapp       # Direct command
cd myapp
quickscale apply
```

**Both methods use the same command syntax.**

---

### For Contributors

If you're contributing to QuickScale development (modifying source code), see the [Development Guide](./development.md) for setup instructions with `make bootstrap` and the shared repository workflows.

---

## Quick orientation

- The repository `Makefile` is the standard entrypoint for shared bootstrap, lint, test, CI, and version-check workflows. The `scripts/` directory contains lower-level helpers used by those targets.
- The primary CLI provided by this repository is the `quickscale` command (installed by the `quickscale_cli` package).
- For dependency management we recommend Poetry — see `docs/technical/poetry_user_manual.md` for full Poetry usage. This manual focuses on QuickScale commands, not Poetry details.

## 1) Bootstrap the repository

Purpose: get a development environment ready to run tests and use the CLI.

Recommended sequence:

```bash
# Ensure prerequisites are installed (Python 3.14+, Git, and Poetry)
make bootstrap

# If Poetry is already configured and you only need dependencies:
make setup
```

**Note**: QuickScale uses a monorepo with centralized dev dependencies. `make bootstrap` and `make setup` install all packages (core, cli, modules) plus shared dev tools (pytest, ruff, mypy) from the repository root.

Notes:
- Inspect `Makefile` or `scripts/bootstrap.sh` before running if you want to know exactly what the bootstrap path does on your system.
- If you configured Poetry to create an in-project virtualenv, the bootstrap step may create `.venv/` in the repo root.

## 2) Running tests (local)

Use the Makefile as the shared entrypoint for local test workflows:

```bash
# Run the full unit + integration suite
make test

# Run unit tests only
make test-unit

# Run unit tests for one module
make MODULE=blog test-unit -- --modules
```

For one-off debugging, run pytest directly through Poetry, for example:

```bash
poetry run pytest quickscale_core/tests/ -q
poetry run pytest quickscale_cli/tests/ -q
poetry run pytest <path/to/test_file.py> -q
```

### 2.1) End-to-End (E2E) Tests

E2E tests validate the complete project lifecycle with real PostgreSQL and browser automation. These tests are slower (5-10 minutes) and require Docker.

**Prerequisites**:
- Docker installed and running
- Playwright browsers installed (one-time setup below)

**First-time E2E setup**:
```bash
cd quickscale_core
poetry install --with dev

# Install Playwright Chromium browser (one-time)
poetry run playwright install chromium --with-deps
```

**Running E2E tests**:
```bash
# Run E2E tests only
make test-e2e

# Run the CI-parity release gate (includes E2E)
make ci-e2e

# Run E2E with visible browser (for debugging)
poetry run pytest -m e2e --headed

# Run all tests EXCEPT E2E (fast, for daily development)
poetry run pytest -m "not e2e"
```

**When to run E2E tests**:
- Pre-release validation
- After making generator template changes
- Before tagging a new version
- Manual testing of complete workflows

E2E tests are excluded from fast CI and run separately on release workflows.

## 3) Linters and code quality checks

Use the repository Makefile targets for code quality checks:

```bash
# Lint and type-check with the shared repo configuration
make lint
make typecheck

# Apply formatting changes
make format

# Combined quality gate
make check
```

**Note**: Linting rules are centralized in `ruff.toml` and `mypy.ini` at the repository root. All packages share these configurations automatically.

Pre-commit hooks are configured in `.pre-commit-config.yaml`. After bootstrapping you may want to run:

```bash
pre-commit install
pre-commit run --all-files
```

## 4) QuickScale CLI (quickscale)

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

QuickScale supports multiple frontend themes. Choose your theme during the `plan` wizard:

```bash
# Create configuration interactively
quickscale plan myapp
# → Select theme during wizard (showcase_html, showcase_react)
# → Generates quickscale.yml
```

**Available themes**:
- `showcase_html` - Pure HTML + CSS; fresh v0.83.0 starter output does not scaffold public `/social` or `/social/embeds` pages
- `showcase_react` - React + TypeScript SPA (default); fresh generations auto-generate Django-owned public `/social` and `/social/embeds` pages

**Important**: Theme selection is one-time during project generation. Generated code is yours to own and customize - no updates or tracking after initialization. The backend-managed social transport remains theme-agnostic, but only fresh `showcase_react` auto-generates the public page files; existing projects and non-React themes must adopt those public pages manually if they want them.

**Typical flow** to create and run a generated project:

```bash
quickscale plan myapp
cd myapp             # Enter the created directory
quickscale apply     # Apply from within the project directory
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
```

The generated project is meant to be fully owned by the user — templates and guidance are in `scaffolding.md` and generated README files.

### 4.1) Development Commands (Shipped in v0.59.0)

> **Status**: ✅ Available (shipped in v0.59.0)
>
> The following commands will simplify Docker and Django operations, eliminating the need to remember complex docker-compose and docker exec syntax.

**Docker Service Management**:
```bash
# Start Docker services
quickscale up
# Equivalent to: docker-compose up -d

# Stop Docker services
quickscale down
# Equivalent to: docker-compose down

# View service logs
quickscale logs           # All services
quickscale logs backend       # Backend service only
quickscale logs db        # Database only
# Equivalent to: docker-compose logs [service]

# Check service status
quickscale ps
# Equivalent to: docker-compose ps
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

> **Status**: ✅ Available — `quickscale update` / `quickscale push --module <name>` shipped in v0.62.0, `quickscale status` in v0.70.0, and `quickscale remove <module>` in v0.71.0+
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

See [decisions.md: CLI Command Matrix](./decisions.md#cli-command-matrix) for the authoritative command list.

### 4.3) Plan/Apply Commands (Shipped in v0.68.0)

> **Status**: ✅ Available (shipped in v0.68.0)
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
1. **Theme selection**: Choose from available themes (showcase_html, showcase_react). Fresh `showcase_react` generations scaffold Django-owned public `/social` and `/social/embeds` pages; `showcase_html` does not scaffold those public pages in v0.83.0.
2. **Module selection**: Select optional modules to include. In the current implementation line, implemented first-party modules include analytics, auth, backups, blog, crm, forms, listings, notifications, social, and storage. The `billing` and `teams` directories remain placeholder inventory only; `quickscale plan`, `quickscale.yml` validation, `quickscale apply`, and generated starter output exclude them until those modules ship.
3. **Docker configuration**: Configure Docker build/start options and optional first-start superuser creation

**Generated `quickscale.yml` example**:
```yaml
version: "1"
project:
  slug: myapp
  package: myapp
  theme: showcase_html
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

In the current release line, `backups` is the admin/ops-first safety option in that set: private local artifacts are the default, optional private remote offload is supported, and generated local Docker and Railway PostgreSQL projects use PostgreSQL 18 custom dumps as the real backup/restore path. JSON artifacts are export-only rather than restore inputs, admin download and validate stay local-file-only in v1, and the BackupPolicy admin page exposes a guarded restore action only for row-backed local artifacts already present on disk. Exact filename confirmation and the existing environment gate remain required, admin restore never materializes remote-only artifacts, and CLI restore keeps its existing syntax.

If you enable `backups` in a generated PostgreSQL project, you can restore a row-backed local artifact from the BackupPolicy admin page under those same confirmation and environment guards, or use the CLI when you need artifact-id or operator-supplied file-path restore:

```bash
poetry run python manage.py backups_create
poetry run python manage.py backups_restore 12 --confirm BACKUP_FILENAME.dump --dry-run
poetry run python manage.py backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump --dry-run

export QUICKSCALE_BACKUPS_ALLOW_RESTORE=true
poetry run python manage.py backups_restore 12 --confirm BACKUP_FILENAME.dump
poetry run python manage.py backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump
```

JSON artifacts remain export-only, not restore inputs. Existing generated projects must manually adopt later Docker/CI/E2E PostgreSQL 18 tooling updates because `quickscale apply` does not rewrite those user-owned files.

### 4.4) Disaster Recovery and Environment Promotion Commands

> **Status**: ✅ Released in v0.82.0
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
# Development with Docker Compose
cd myapp
cp .env.example .env  # Configure environment variables
docker-compose up --build
docker-compose exec backend python manage.py migrate

# Production Docker build
docker build -t myapp:latest .
docker run -p 8000:8000 \
  -e SECRET_KEY=your-secret \
  -e ALLOWED_HOSTS=yourdomain.com \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  myapp:latest
```

The `Dockerfile` uses multi-stage builds (builder + runtime) for production efficiency. The `docker-compose.yml` includes PostgreSQL and is configured for local development.

## 5) Repository Make Targets

Use these from the repository root:

- `make bootstrap` — bootstrap checks plus dependency install
- `make setup` — dependency install only
- `make test` / `make test-unit` — shared test entrypoints
- `make test-e2e` / `make ci-e2e` — E2E and release-gate validation
- `make lint` / `make format` / `make typecheck` — shared quality checks
- `make publish-module MODULE=<name>` — publish module changes to split branches
- `make version-check` — verify `VERSION` alignment across packages

Lower-level helpers still live in `scripts/` if you need to inspect the underlying implementation.

## 6) Troubleshooting common issues

- Missing `quickscale` command after install: ensure you installed the `quickscale_cli` package (e.g., `poetry install` in repo root) and that your PATH points to the virtualenv bin directory or use `poetry run quickscale ...`.
- Poetry missing: install Poetry (https://python-poetry.org/docs/#installation) or run bootstrap script to learn what's required.
- Permission errors from Makefile-backed helpers: check `chmod +x scripts/*.sh`, since some repository targets shell out to scripts in that directory.
- Pre-commit failures: run `pre-commit run --all-files` to see failing hooks and fix code formatting/lint issues.

## 7) Commands quick reference

**Repository Commands**:
- Bootstrapping: `make bootstrap`
- Install deps only: `make setup`
- Tests: `make test`
- Unit tests only: `make test-unit`
- E2E tests: `make test-e2e`
- CI parity + E2E: `make ci-e2e`
- Lint: `make lint`
- Format: `make format`
- Version parity: `make version-check`

**CLI Commands (Current)**:
- CLI help: `quickscale --help`
- Create config: `quickscale plan <project-slug>`
- Apply config: `quickscale apply [config.yml]`

**CLI Commands (Development)**:
- Start services: `quickscale up`
- Stop services: `quickscale down`
- View logs: `quickscale logs [service]`
- Service status: `quickscale ps`
- Container shell: `quickscale shell`
- Django commands: `quickscale manage <cmd>`

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

## Poetry — quick commands

Minimal, project-focused Poetry commands you will use with this repo:

First-time / bootstrap
```bash
# From repo root (after make bootstrap or make setup)
# Installs all packages + centralized dev dependencies
poetry install
```

Daily / project commands
```bash
# Activate shell (optional)
poetry shell

# Run tests
poetry run pytest

# Run CLI from package
poetry run quickscale --help

# Run linters / formatters
poetry run ruff format --check .
poetry run ruff check .
```

Dependency management
```bash
# Add dev dependency (centralized at root)
cd /path/to/quickscale
poetry add --group dev <package>

# Add production dependency (package-specific)
cd quickscale_core  # or quickscale_cli, etc.
poetry add <package>

# Update dependencies
poetry lock --no-update
poetry install
```

Build & publish
```bash
cd quickscale_core
poetry build
poetry publish --build
```

## 8) Git Subtree Workflow (Advanced)

> **Note**: CLI wrapper commands (`quickscale update`, `quickscale push --module <name>`) now ship with QuickScale. Module embedding is handled by running `quickscale plan`, entering the generated directory, and then running `quickscale apply`. See [section 4.2](#42-module-management-commands) for the simplified commands.
>
> The manual commands documented below will continue to work and are useful for understanding how git subtree works under the hood.

QuickScale supports embedding `quickscale_core` into your project using git subtree for advanced workflows. This section documents when and how to use this feature.

### When to Use Git Subtree

**Use subtree embedding when:**

1. **Personal Monorepo with Multiple Client Projects**
   - You maintain 3+ client projects and want shared improvements
   - Example: Agency with 5 Django projects all using QuickScale
   - Benefit: Bug fixes flow to all projects with one `git subtree pull`

2. **Sharing Improvements Back to Core**
   - You enhance QuickScale and want to contribute back
   - Example: Better error handling, new template features
   - Benefit: Use `git subtree push` to create PRs upstream

3. **Module Extraction Workflow (Advanced)**
   - You've built the same feature 2-3 times across projects
   - Example: Custom auth pattern worth extracting
   - Benefit: Extract to `quickscale_modules/` for reuse

4. **Custom Core Modifications with Upstream Sync**
   - You need custom modifications but want upstream security fixes
   - Example: Agency-specific templates with upstream updates
   - Benefit: Merge upstream changes while keeping customizations

**Don't use subtree when:**
- ❌ You have only 1-2 projects (overhead not worth it)
- ❌ You never plan to update or contribute back (just use generated project)
- ❌ You're unfamiliar with git advanced features (stick to basics first)

### Prerequisites

**Required:**
- Git 2.25+ (earlier versions have subtree bugs)
- Understanding of git remotes and branches
- Comfortable with merge conflict resolution
- Backup strategy (subtree can't be easily undone)

**Verify prerequisites:**
```bash
# Check git version
git --version
# Should show 2.25.0 or higher

# Test git subtree availability
git subtree --help
# Should show help text (not an error)
```

### Git Subtree Commands

**Basic Commands:**
```bash
# Embed core (first time)
git subtree add --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# Pull updates from upstream
git subtree pull --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# Push improvements back (requires write access or fork)
git subtree push --prefix=quickscale https://github.com/Experto-AI/quickscale.git feature-branch
```

**Validation after each command:**
```bash
# After 'git subtree add'
ls quickscale/quickscale_core  # Should show core package
git log --oneline -5            # Should show merge commit

# After 'git subtree pull'
git log quickscale/ --oneline -5  # Should show new upstream commits

# After 'git subtree push'
git ls-remote --heads https://github.com/Experto-AI/quickscale.git
# Should show your feature-branch
```

### Common Issues & Solutions

**Issue 1: Merge conflicts during subtree pull**

**Symptom:**
```
CONFLICT (content): Merge conflict in quickscale/quickscale_core/...
Automatic merge failed; fix conflicts and then commit the result.
```

**Solution:**
```bash
# 1. Check which files have conflicts
git status

# 2. Manually resolve conflicts in each file
#    (edit files, remove <<<< ==== >>>> markers)

# 3. Stage resolved files
git add quickscale/

# 4. Complete the merge
git commit -m "Merge upstream changes, resolved conflicts"
```

**Prevention:** Pull upstream changes frequently (weekly) to minimize conflict scope.

---

**Issue 2: "Already exists" error on subtree add**

**Symptom:**
```
fatal: prefix 'quickscale' already exists.
```

**Solution - Clean slate approach:**
```bash
# Option A: Use different prefix
git subtree add --prefix=quickscale-core https://github.com/...

# Option B: Remove existing directory first (DANGER: loses local changes)
rm -rf quickscale/
git subtree add --prefix=quickscale https://github.com/...
```

**Solution - Existing prefix approach:**
```bash
# If directory exists and you want to convert it to subtree
git rm -r quickscale/
git commit -m "Remove old quickscale directory"
git subtree add --prefix=quickscale https://github.com/... main --squash
```

---

**Issue 3: Push failures to read-only remotes**

**Symptom:**
```
ERROR: Permission to Experto-AI/quickscale.git denied to user.
fatal: Could not read from remote repository.
```

**Solution - Fork-first workflow:**
```bash
# 1. Fork Experto-AI/quickscale on GitHub to your-username/quickscale

# 2. Add your fork as a remote
git remote add my-fork https://github.com/your-username/quickscale.git

# 3. Push to your fork
git subtree push --prefix=quickscale my-fork feature-branch

# 4. Create PR from your-username/quickscale:feature-branch → Experto-AI/quickscale:main
```

---

**Issue 4: Branch mismatch errors**

**Symptom:**
```
fatal: ambiguous argument 'main': unknown revision or path not in the working tree.
```

**Solution - Explicit branch flag:**
```bash
# Check available branches on remote
git ls-remote --heads https://github.com/Experto-AI/quickscale.git

# Use explicit branch name (might be 'master' or 'develop')
git subtree pull --prefix=quickscale https://github.com/Experto-AI/quickscale.git master --squash

# Or fetch first to see branches
git fetch https://github.com/Experto-AI/quickscale.git
git branch -r  # Shows remote branches
```

---

## 9) Where to find more information

- Technical decisions and authoritative feature scope: [decisions.md](./decisions.md)
- Scaffolding and generated project structure: [scaffolding.md](./scaffolding.md)
- Roadmap and release milestones: [roadmap.md](./roadmap.md)
- Generator templates (look under `quickscale_core/src/quickscale_core/scaffold/templates/`)
- Top-level README for newcomer guidance: [README.md](../../README.md)
