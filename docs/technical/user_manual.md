# QuickScale — User Manual (commands)

This short manual explains the commands QuickScale contributors and users run most often: how to bootstrap the repository, run the test suite and linters, and use the `quickscale` CLI to generate projects.

<!--
QuickScale User Manual (commands) — scope and disambiguation

This file is a short, practical user manual focusing on QuickScale developer/user commands: how to bootstrap the repository, run tests and linters, and use the `quickscale` CLI (for example `quickscale init`).

What belongs in this file:
- Practical step-by-step commands and examples users should run locally (bootstrap, tests, linters, quickscale CLI usage, short troubleshooting tips).

What does NOT belong in this file (and where to put it):
- Architectural decisions, MVP scope, and tie-breakers → `decisions.md` (authoritative).
- Long-term roadmap, release milestones, and planning → `roadmap.md`.
- Package and generator scaffolding details (templates, deep structure) → `scaffolding.md` and template files in `quickscale_core`.
- User-facing getting-started narrative and marketing material → top-level `README.md`.

Keep this doc short and actionable. When in doubt, link to the authoritative doc (decisions.md / roadmap.md / scaffolding.md) for details.
-->

## Quick orientation

- Repository scripts are in `scripts/` (for example `./scripts/bootstrap.sh`, `./scripts/test-all.sh`, `./scripts/lint.sh`). Inspect them if you need to confirm exact actions.
- The primary CLI provided by this repository is the `quickscale` command (installed by the `quickscale_cli` package).
- For dependency management we recommend Poetry — see `docs/technical/poetry_user_manual.md` for full Poetry usage. This manual focuses on QuickScale commands, not Poetry details.

## 1) Bootstrap the repository

Purpose: get a development environment ready to run tests and use the CLI.

Recommended sequence:

```bash
# 1. Ensure prerequisites are installed (Python 3.10+, Git, and Poetry)
# 2. Run the repository bootstrap script
./scripts/bootstrap.sh

# 3. Use Poetry to install dependencies
poetry install
```

Notes:
- Inspect `./scripts/bootstrap.sh` before running if you want to know exactly what it does on your system.
- If you configured Poetry to create an in-project virtualenv, the bootstrap step may create `.venv/` in the repo root.

## 2) Running tests (local)

You can run the full test suite using the repository script or Poetry:

```bash
# Run all tests (script)
./scripts/test-all.sh

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

## 3) Linters and code quality checks

Use the repository lint script to run all code quality checks:

```bash
# Run lint script (includes ruff format, ruff check, and mypy)
./scripts/lint.sh
```

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

# Create a new Django project (primary MVP command)
quickscale init <project_name>
```

Typical flow to create and run a generated project:

```bash
quickscale init myapp
cd myapp
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
```

The generated project is meant to be fully owned by the user — templates and guidance are in `scaffolding.md` and generated README files.

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
- `./scripts/test-all.sh` — runs the full test matrix for the repo
- `./scripts/lint.sh` — runs configured linters and formatters

Run these scripts from the repository root.

## 6) Troubleshooting common issues

- Missing `quickscale` command after install: ensure you installed the `quickscale_cli` package (e.g., `poetry install` in repo root) and that your PATH points to the virtualenv bin directory or use `poetry run quickscale ...`.
- Poetry missing: install Poetry (https://python-poetry.org/docs/#installation) or run bootstrap script to learn what's required.
- Permission errors running scripts: check `chmod +x scripts/*.sh` and run scripts from the project root.
- Pre-commit failures: run `pre-commit run --all-files` to see failing hooks and fix code formatting/lint issues.

## 7) Commands quick reference

- Bootstrapping: `./scripts/bootstrap.sh`
- Install deps (Poetry): `poetry install`
- Tests: `./scripts/test-all.sh`
- Lint: `./scripts/lint.sh`
- CLI help: `quickscale --help`
- Create project: `quickscale init <name>`

## Poetry — quick commands

Minimal, project-focused Poetry commands you will use with this repo:

First-time / bootstrap
```bash
# From repo root (after ./scripts/bootstrap.sh)
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
# Add prod dep
poetry add <package>

# Add dev dep
poetry add --group dev <package>

# Update dependencies (refresh lock)
poetry update
```

Build & publish
```bash
cd quickscale_core
poetry build
poetry publish --build
```

## 8) Git Subtree Workflow (Advanced)

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

