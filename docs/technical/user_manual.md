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

Use the repository lint script or run linters directly via Poetry:

```bash
# Run lint script (calls ruff format and ruff check)
./scripts/lint.sh

# Or run tools individually
poetry run ruff format --check .
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
- Tests: `./scripts/test-all.sh` or `poetry run pytest`
- Lint: `./scripts/lint.sh` or `poetry run ruff format --check .` / `poetry run ruff check .`
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

## 8) Where to find more information

- Technical decisions and authoritative feature scope: [decisions.md](./decisions.md)
- Scaffolding and generated project structure: [scaffolding.md](./scaffolding.md)
- Roadmap and release milestones: [roadmap.md](./roadmap.md)
- Generator templates (look under `quickscale_core/src/quickscale_core/scaffold/templates/`)
- Top-level README for newcomer guidance: [README.md](../../README.md)

---

If you'd like, I can now:
- Update generator README/template files to recommend Poetry-first commands (so generated starters show `poetry install` in their README), and/or
- Update `./scripts/bootstrap.sh` to explicitly call `poetry install` (if you want the bootstrap script to be Poetry-first).

