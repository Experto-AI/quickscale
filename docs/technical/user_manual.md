# QuickScale — User Manual (commands)

This short manual explains the commands QuickScale contributors and users run most often: how to bootstrap the repository, run the test suite and linters, and use the `quickscale` CLI to generate projects.

<!--
QuickScale User Manual (commands) — scope and disambiguation

This file is a short, practical user manual focusing on QuickScale developer/user commands: how to bootstrap the repository, run tests and linters, and use the `quickscale` CLI.

What belongs in this file:
- Practical step-by-step commands and examples users should run locally (bootstrap, tests, linters, quickscale CLI usage, short troubleshooting tips).

What does NOT belong in this file (and where to put it):
- Architectural decisions, MVP scope, and tie-breakers → `decisions.md` (authoritative).
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
./scripts/install_global.sh
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

If you're contributing to QuickScale development (modifying source code), see the [Development Guide](./development.md) for setup instructions with `./scripts/bootstrap.sh` and `poetry install`.

---

## Quick orientation

- Repository scripts are in `scripts/` (for example `./scripts/bootstrap.sh`, `./scripts/test_all.sh`, `./scripts/lint.sh`, `./scripts/publish_module.sh`). Inspect them if you need to confirm exact actions.
- The primary CLI provided by this repository is the `quickscale` command (installed by the `quickscale_cli` package).
- For dependency management we recommend Poetry — see `docs/technical/poetry_user_manual.md` for full Poetry usage. This manual focuses on QuickScale commands, not Poetry details.

## 1) Bootstrap the repository

Purpose: get a development environment ready to run tests and use the CLI.

Recommended sequence:

```bash
# 1. Ensure prerequisites are installed (Python 3.11+, Git, and Poetry)
# 2. Run the repository bootstrap script
./scripts/bootstrap.sh

# 3. Use Poetry to install all dependencies from repository root
poetry install
```

**Note**: QuickScale uses a monorepo with centralized dev dependencies. Running `poetry install` from the root installs all packages (core, cli, modules) plus shared dev tools (pytest, ruff, mypy).

Notes:
- Inspect `./scripts/bootstrap.sh` before running if you want to know exactly what it does on your system.
- If you configured Poetry to create an in-project virtualenv, the bootstrap step may create `.venv/` in the repo root.

## 2) Running tests (local)

You can run the full test suite using the repository script or Poetry:

```bash
# Run all tests (script)
./scripts/test_all.sh

# Or run pytest via Poetry
poetry run pytest

# Run package-specific tests
poetry run pytest quickscale_core/tests/
poetry run pytest quickscale_cli/tests/
```

If you prefer to run a single test file or test function, use pytest patterns, for example:

```bash
poetry run pytest tests/test_cli.py -q
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
pytest -m e2e

# Run E2E with visible browser (for debugging)
pytest -m e2e --headed

# Run all tests EXCEPT E2E (fast, for daily development)
pytest -m "not e2e"

# Use helper script
./scripts/test_e2e.sh              # Standard run
./scripts/test_e2e.sh --headed     # Show browser
./scripts/test_e2e.sh --verbose    # Detailed output
```

**When to run E2E tests**:
- Pre-release validation
- After making generator template changes
- Before tagging a new version
- Manual testing of complete workflows

E2E tests are excluded from fast CI and run separately on release workflows.

## 3) Linters and code quality checks

Use the repository lint script to run all code quality checks:

```bash
# Run lint script (includes ruff format, ruff check, and mypy)
./scripts/lint.sh
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
quickscale plan <project_name>

# Execute the configuration to generate a project
quickscale apply
```

**Theme Selection**:

QuickScale supports multiple frontend themes. Choose your theme during the `plan` wizard:

```bash
# Create configuration interactively
quickscale plan myapp
# → Select theme during wizard (showcase_html, showcase_htmx, showcase_react)
# → Generates quickscale.yml
```

**Available themes**:
- `showcase_html` - Pure HTML + CSS (default, production-ready)
- `showcase_htmx` - HTMX + Alpine.js (coming in v0.73.0)
- `showcase_react` - React + TypeScript SPA (coming in v0.74.0)

**Important**: Theme selection is one-time during project generation. Generated code is yours to own and customize - no updates or tracking after initialization.

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
quickscale logs web       # Web service only
quickscale logs db        # Database only
# Equivalent to: docker-compose logs [service]

# Check service status
quickscale ps
# Equivalent to: docker-compose ps
```

**Development Tools**:
```bash
# Interactive bash shell in web container
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
# ↑ Docker services auto-start here (if docker.start: true, the default)

# Services already running - check status:
quickscale ps                    # Check services
quickscale logs web              # View logs

# OR if you need to start manually:
# (e.g., after 'quickscale down' or if docker.start: false)
quickscale up

# Development
quickscale manage migrate        # Run migrations
quickscale manage createsuperuser  # Create admin user
quickscale shell                 # Access container shell
quickscale manage test           # Run tests

# Shutdown
quickscale down                  # Stop services
```

**Note on Docker auto-start:**
- First `quickscale apply` with `docker.start: true` (default) → services start automatically
- After `quickscale down` → must run `quickscale up` manually
- Incremental applies (adding modules) → services keep running, no restart

See [Roadmap v0.59.0](./roadmap.md#v0590-cli-development-commands--railway-deployment-) for complete implementation details.

### 4.2) Git Subtree Commands (Shipped in v0.62.0)

> **Status**: ✅ Available (shipped in v0.62.0)
>
> These commands simplify complex manual git subtree operations with simple CLI wrappers.

```bash
# Pull QuickScale updates
quickscale update
# Equivalent to: git subtree pull --prefix=quickscale_core <remote> main --squash

# Push improvements back to QuickScale
quickscale push
# Equivalent to: git subtree push --prefix=quickscale_core <remote> feature-branch
```

**Note**: Module embedding is now handled by the `quickscale plan` + `quickscale apply` workflow.

See [Roadmap v0.60.0](./roadmap.md#v0600-cli-git-subtree-wrappers--update-workflow-validation) for complete implementation details.

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
1. **Theme selection**: Choose from available themes (showcase_html, showcase_htmx, showcase_react)
2. **Module selection**: Select optional modules to include (blog, listings, billing, teams)
3. **Docker configuration**: Configure Docker build and startup options

**Generated `quickscale.yml` example**:
```yaml
version: 0.74.0
project:
  name: myapp
  theme: showcase_html
modules:
  - name: blog
  - name: listings
docker:
  build: true
  start: true
```

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
5. Embed selected modules (via git subtree)
6. Install Poetry dependencies
7. Run Django migrations
8. Start Docker services (if configured)

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
quickscale up
quickscale manage migrate
quickscale manage createsuperuser
```

**Benefits over `init`**:
- ✅ Declarative: Configuration is version-controllable
- ✅ Reproducible: Same config produces same project
- ✅ Reviewable: Preview before execution
- ✅ Modular: Includes module embedding in one step

### Docker deployment

Generated projects include Docker support for both development and production. After generating a project:

```bash
# Development with Docker Compose
cd myapp
cp .env.example .env  # Configure environment variables
docker-compose up --build
docker-compose exec web python manage.py migrate

# Production Docker build
docker build -t myapp:latest .
docker run -p 8000:8000 \
  -e SECRET_KEY=your-secret \
  -e ALLOWED_HOSTS=yourdomain.com \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  myapp:latest
```

The `Dockerfile` uses multi-stage builds (builder + runtime) for production efficiency. The `docker-compose.yml` includes PostgreSQL and is configured for local development.

## 5) Development helper scripts

- `./scripts/bootstrap.sh` — initial environment/setup steps (inspect to confirm behavior)
- `./scripts/test_all.sh` — runs the full test matrix for the repo
- `./scripts/lint.sh` — runs configured linters and formatters
- `./scripts/publish_module.sh` — publishes module changes to split branches

Run these scripts from the repository root.

## 6) Troubleshooting common issues

- Missing `quickscale` command after install: ensure you installed the `quickscale_cli` package (e.g., `poetry install` in repo root) and that your PATH points to the virtualenv bin directory or use `poetry run quickscale ...`.
- Poetry missing: install Poetry (https://python-poetry.org/docs/#installation) or run bootstrap script to learn what's required.
- Permission errors running scripts: check `chmod +x scripts/*.sh` and run scripts from the project root.
- Pre-commit failures: run `pre-commit run --all-files` to see failing hooks and fix code formatting/lint issues.

## 7) Commands quick reference

**Repository Commands**:
- Bootstrapping: `./scripts/bootstrap.sh`
- Install deps (Poetry): `poetry install`
- Tests: `./scripts/test_all.sh`
- E2E tests: `pytest -m e2e`
- Lint: `./scripts/lint.sh`

**CLI Commands (Current)**:
- CLI help: `quickscale --help`
- Create config: `quickscale plan <name>`
- Apply config: `quickscale apply [config.yml]`

**CLI Commands (Development)**:
- Start services: `quickscale up`
- Stop services: `quickscale down`
- View logs: `quickscale logs [service]`
- Service status: `quickscale ps`
- Container shell: `quickscale shell`
- Django commands: `quickscale manage <cmd>`

**CLI Commands (Modules)**:
- Update core: `quickscale update`
- Push changes: `quickscale push`
- Remove module: `quickscale remove <module>`
- Project status: `quickscale status`

## Poetry — quick commands

Minimal, project-focused Poetry commands you will use with this repo:

First-time / bootstrap
```bash
# From repo root (after ./scripts/bootstrap.sh)
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

> **Note**: CLI wrapper commands (`quickscale update`, `quickscale push`) now ship with QuickScale. Module embedding is handled via `quickscale plan` + `quickscale apply`. See [section 4.2](#42-git-subtree-commands-shipped-in-v0620) for the simplified commands.
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
