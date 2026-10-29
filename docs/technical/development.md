# QuickScale Development Setup Guide

> **Related docs**: [Contributing](../contrib/contributing.md) | [User Manual](user_manual.md) | [Testing](../contrib/testing.md) | [Start Here](../../START_HERE.md)

**Target**: New contributor can clone repository and run tests successfully in <15 minutes.

**Tested On**: Ubuntu 22.04, Python 3.14

**Supported contributor hosts**: Linux x86_64/arm64, macOS Intel/Apple Silicon,
and Windows through WSL. Native Windows/Git Bash is not a supported execution
host. The mandatory dependency gate downloads the matching Trivy v0.74.0
release archive for each supported native OS/architecture, verifies the official
release-manifest SHA-256 before extraction, and fails explicitly on any other
host; it never silently skips a scan.

---

## Prerequisites

Before starting, ensure you have these tools installed:

### Required Tools

1. **Python 3.14** (the project pins `>=3.14,<3.15`)
   ```bash
   python3 --version
   # Should show 3.14.x
   ```
   3.13 and older are not supported — the sources use syntax (PEP 758
   unparenthesized `except`) that older interpreters cannot parse.

2. **Git 2.25+**
   ```bash
   git --version
   # Should show 2.25.0 or higher
   ```

3. **Poetry 2.0+** (Python package manager)
   ```bash
   poetry --version
   # Should show 2.0.0 or higher
   ```

### Installing Prerequisites

**Ubuntu/Debian:**
```bash
# Python 3.14 (if not already installed)
sudo apt update
sudo apt install python3.14 python3.14-venv python3-pip
# If your distro has no python3.14 package, `uv python install 3.14`
# or pyenv both provide it without touching the system interpreter.

# Git
sudo apt install git

# Poetry (recommended method)
curl -sSL https://install.python-poetry.org | python3 -
# Add Poetry to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```

**macOS:**
```bash
# Python 3.14 via Homebrew
brew install python@3.14

# Git (usually pre-installed)
brew install git

# Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

**Verify all prerequisites:**
```bash
python3 --version && git --version && poetry --version
# All three commands should succeed
```

---

## Quick Start (Clone → Test in <15 Minutes)

**For Contributors** (modifying QuickScale source code):

#### 1. Clone and Bootstrap (2-3 minutes)
```bash
git clone https://github.com/Experto-AI/quickscale.git
cd quickscale
./scripts/bootstrap.sh
poetry install
```

**What bootstrap.sh does:**
- Checks Python version compatibility
- Verifies Poetry installation
- Configures Poetry to use in-project virtualenv (`.venv/`)
- Installs pre-commit hooks

#### 2. Verify Installation (1 minute)
```bash
poetry run quickscale --version
# Prints the repository VERSION

poetry show
# Should show quickscale_core, quickscale_cli, and dependencies
```

#### 3. Run Tests (3-5 minutes)
```bash
make test-unit

# Expected output:
# =================== test session starts ====================
# quickscale_core: 96% coverage (target: >80%)
# quickscale_cli: 82% coverage (target: >80%)
# =================== XX passed in X.XXs ====================
```

#### 4. Run Linters (1-2 minutes)
```bash
make lint

# Prove the rendered showcase_react starter frontend without Docker
make frontend-proof

# Expected output:
# ✓ ruff format --check (code formatting)
# ✓ ruff check (linting)
# ✓ mypy (type checking)
# All checks passed!
```

See [validation_policy.md § Repository Command Reference](./validation_policy.md#repository-command-reference) for the full shared `make` entrypoint list.

#### 5. Generate Test Project (2-3 minutes)
```bash
poetry run quickscale plan testproject
cd testproject
poetry run quickscale apply
# Services auto-start (if docker.start: true)

# Verify services running:
poetry run quickscale ps

# OR use native Python (skip Docker):
poetry run quickscale apply --no-docker
poetry install
poetry run python manage.py migrate
poetry run pytest

# Expected: 5/5 tests passing
```

**Note**: If you're just using QuickScale (not contributing), install via `pip install quickscale` instead. See the [README](../../README.md) for user installation instructions.

---

## Troubleshooting

### `poetry install` fails with `[Errno 13] Permission denied: 'proxy.py'`

Root cause: your project `.venv/` was created as `root` (usually from running Poetry with `sudo`), so Poetry cannot delete or recreate files.

Use one of these fixes from project root:

```bash
# Preferred: keep existing env path, restore ownership
sudo chown -R "$USER:$USER" .venv

# Alternative: remove broken env and let Poetry recreate it
sudo rm -rf .venv
poetry install

# No-sudo workaround (if parent directory is writable):
mv .venv .venv.root-owned.backup.$(date +%Y%m%d-%H%M%S)
poetry install
```

Prevention:
- Never run `poetry` commands with `sudo` in this repository
- Use `./scripts/bootstrap.sh` (it detects and handles a root-owned `.venv`)

---

## Development Workflow

### Daily Commands

**Activate Poetry shell (optional):**
```bash
poetry shell
# Now you can run commands without 'poetry run' prefix
quickscale --version
pytest
```

**Run tests:**

Use `make test` / `make test-unit` (see [validation_policy.md § Repository Command Reference](./validation_policy.md#repository-command-reference)). For one-off debugging of a specific file, run pytest directly:
```bash
poetry run pytest quickscale_core/tests/test_generator.py -v
```

**Run linters:**

Use `make lint` / `make format` (see [validation_policy.md § Repository Command Reference](./validation_policy.md#repository-command-reference)). For a single tool:
```bash
poetry run ruff check .              # Linting only
poetry run mypy quickscale_core/ quickscale_cli/  # Type checking only
```

**Pre-commit hooks:**
```bash
# Install hooks (one-time; installs both the pre-commit and commit-msg hooks)
poetry run pre-commit install

# Run manually on all files
poetry run pre-commit run --all-files

# Hooks run automatically on 'git commit'
# Hooks use the root Poetry environment for Ruff and may rewrite files.
# If that happens, re-stage the changed files and run 'git commit' again.
```

### Making Changes

**Typical workflow:**
1. Create feature branch: `git checkout -b feature/my-feature`
2. Make code changes in `quickscale_core/src/` or `quickscale_cli/src/`
3. Add tests in corresponding `tests/` directory
4. Run tests: `make test-unit`
5. Run linters: `make lint` or `make lint-fix`; run `make typecheck` before commit
6. Commit changes: `git commit -m "feat: description"`
7. Push and create PR: `git push origin feature/my-feature`

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

**Behavioural control commits additionally require a `vNN` roadmap reference** — bare (`v88`) or dotted (`v0.88.0`) — anywhere in the message. This applies to commits touching a GitHub workflow, `scripts/gate_registry.json`, or a PostgreSQL provisioning station; a ticket id alone does not satisfy it. Merge commits are exempt: a merge carries someone else's protected change, not the merger's testimony.

Enforcement is at authorship: the `commit-msg` hook installed by `poetry run pre-commit install` rejects the commit against the staged surfaces, while rewording is still free. Hosted CI re-checks the whole range with `make check-commit-testimony`, which also runs on demand over any `--base-ref`/`--head-ref` range. See [validation policy](validation_policy.md).

### Fast feedback loop for AI-assisted / incremental development

When iterating on a focused change, use the narrowest validation target first and widen only when the narrower check passes. This keeps the cycle time short and avoids waiting on unrelated work.

**Iterate** — during active development:
```bash
# Re-run only the tests that failed last time
make retry

# Narrow to one test by name (drops the coverage gate for the scoped run)
make test-unit K=test_render_theme
make test-unit ARGS='-x --lf'

# Lint only the core package
make lint -- --core

# Type-check only the CLI package
make typecheck -- --cli

# Unit-test only the core package
make test-unit -- --core

# Run a single module's test suite. Tenant module suites default to the
# restricted role; QS_<MODULE>_DB_USER overrides it.
make MODULE=orgs test -- --modules
```

**Pre-merge** — before committing:
```bash
# All unit tests (core + CLI) with xdist parallelism
make test-unit

# Full lint and type-check
make lint
make typecheck

# Bounded integration concurrency — limit to N concurrent module workers:
QS_INTEGRATION_JOBS=2 make test-integration
```

**Re-verifying one CI stage** — while fixing what a full `make ci` surfaced:
```bash
make ci ONLY=integration     # run just that stage
make ci FROM=coverage        # resume from a stage onward
make ci SKIP_INSTALL=1       # skip the dependency install stage
```

These print `PARTIAL CI — NOT a full pass` and list what they skipped. They
shorten the fix cycle; they never replace the full run the tier owes. Both these
and the `K=`/`ARGS=` scoping variables are documented in
[validation_policy.md § Scoping and Rerun Variables](./validation_policy.md#scoping-and-rerun-variables).

**E2E-last** — before merging to a release branch:
```bash
# Full local CI pipeline (lint + typecheck + unit + integration)
make ci

# E2E release gate (requires Docker + Playwright)
make ci-e2e
```

Concurrency, memory-guard, and progress-reporting environment variables for these
runners — plus how to tell a stuck lane from an out-of-date checkout during a long
E2E run — are documented in
[validation_policy.md § Runner Tuning Knobs](./validation_policy.md#runner-tuning-knobs).

---

Repository layout: [repository_layout.md](repository_layout.md).

---

## Common Issues & Solutions

### Issue: "TempliteSyntaxError: Don't understand tag" or "coverage" version errors

**Cause**: Stale `.venv` directories in sub-packages with outdated dependencies

**Solution:**
```bash
# Delete all sub-package venvs
rm -rf quickscale_core/.venv quickscale_cli/.venv quickscale/.venv
rm -rf quickscale_modules/*/.venv

# Reinstall from root
cd /path/to/quickscale  # repository root
poetry install
```

**Prevention**: Sub-packages that could be independently invoked have `poetry.toml` with `virtualenvs.create = false` to prevent accidental local venvs. The CI will fail if stale sub-package `.venv` directories are detected.

---

### Issue: "quickscale: command not found"

**Cause**: CLI package not installed or not in PATH

**Solution:**
```bash
# Ensure packages are installed
poetry install

# Use full path
poetry run quickscale --version

# Or activate Poetry shell
poetry shell
quickscale --version
```

---

### Issue: "ModuleNotFoundError: No module named 'quickscale_core'"

**Cause**: Source packages not installed in editable mode

**Solution:**
```bash
# Reinstall in editable mode
poetry install

# Verify installation
poetry show | grep quickscale
# Should show quickscale-core and quickscale-cli
```

---

### Issue: Tests fail with "permission denied" on generated projects

**Cause**: Tests running in source directory instead of isolated filesystem

**Solution:**
- This is a test isolation bug (should use `tmp_path` fixture)
- Report in GitHub issues with test file name
- Workaround: `chmod -R u+w quickscale_core/tests/test_data/`

---

### Issue: Pre-commit hooks fail on existing code

**Cause**: Code doesn't meet formatting/linting standards

**Solution:**
```bash
# Auto-fix formatting issues
poetry run ruff format .

# Auto-fix some linting issues
poetry run ruff check --fix .

# Re-run pre-commit
poetry run pre-commit run --all-files
```

---

### Issue: Poetry takes a long time to resolve dependencies

**Cause**: Poetry's dependency resolver is thorough but slow

**Solution:**
```bash
# Use cached dependencies (faster)
poetry install --no-root

# Update lockfile if needed
poetry lock --no-update

# Clear cache if corrupted
poetry cache clear . --all
rm poetry.lock
poetry install
```

---

### Issue: Python version mismatch

**Cause**: System Python version doesn't match project requirements (`>=3.14,<3.15`)

**Solution:**
```bash
# Check current version
python3 --version

# Install specific version (Ubuntu)
sudo apt install python3.14 python3.14-venv
# ...or, without touching the system interpreter:
#   uv python install 3.14

# Tell Poetry to use specific version
poetry env use python3.14

# Verify
poetry run python --version
```

---

## Advanced Topics

### Testing Generated Projects

**Full integration test:**
```bash
# Generate project configuration
poetry run quickscale plan integration_test
# Accept defaults

# Apply configuration
cd integration_test
poetry run quickscale apply

# Setup and test
poetry install
poetry run pytest
poetry run python manage.py check

# Cleanup
cd ..
rm -rf integration_test
```

### Running Specific Test Categories

```bash
# Unit tests only
poetry run pytest -m unit

# Integration tests only
poetry run pytest -m integration

# Tests matching pattern
poetry run pytest -k "generator"
```

### Debugging Tests

```bash
# Drop into debugger on failure
poetry run pytest --pdb

# Show print statements
poetry run pytest -s

# Very verbose
poetry run pytest -vv
```

### Building Distribution Packages

```bash
# Build every distribution package (materializes the bundled module manifests)
make build

# Test installation from wheel
python -m venv test_venv
source test_venv/bin/activate
pip install quickscale_core/dist/*.whl
pip install quickscale_cli/dist/*.whl
quickscale --version
```

### E2E prerequisites

E2E runs need Docker and the Playwright Chromium browser (one-time install from the repo root):

```bash
poetry run playwright install chromium --with-deps
poetry run pytest -m e2e --headed   # visible browser for debugging
```

### Dependency management

```bash
poetry add --group dev <package>     # shared dev dependency (repo root)
poetry lock --no-update && poetry install
```

A package's runtime dependency goes in that package's `pyproject.toml`; the root
`pyproject.toml` resolves everything into one `poetry.lock`
([decisions.md § Package Structure](decisions.md#package-structure)).

### Local wheelhouse resolution

QuickScale can replace the generated project's published `quickscale-core`
dependency range with an exact local wheel during development and
installed-wheel acceptance testing. The dependency synchronizer applies this
seam to both the direct project dependency update and the embedded module
`pyproject.toml` path-repair pass. Published third-party dependencies keep the specs
declared in the module `pyproject.toml`; the wheelhouse is not a replacement package
index.

#### Wheelhouse selection

The `QUICKSCALE_LOCAL_WHEELHOUSE` environment variable is an explicit override.
When it is set, it must contain an absolute path to an existing directory; an
empty value is invalid.
For a dependency named `quickscale-core`, the synchronizer searches that
directory for exactly one wheel matching the normalized pattern
`quickscale_core-*.whl`.

When the variable is unset, an installed CLI may implicitly use
`sys.prefix/quickscale_wheels`, the wheelhouse staged by the global-install
workflow. If that implicit wheelhouse has no matching wheel, the synchronizer
keeps the canonical published `quickscale-core` lockstep pin; this preserves the
normal fallback for locally installed builds whose wheelhouse is incomplete. An
unset variable with no staged wheelhouse also keeps the canonical lockstep pin.

#### Failure modes

- A non-absolute or nonexistent explicit path raises `DependencySyncError` and
  names the required environment-variable contract.
- An explicit directory with no matching `quickscale-core` wheel raises
  `DependencySyncError`.
  The error names `QUICKSCALE_LOCAL_WHEELHOUSE`, the searched directory, the
  attempted normalized glob pattern, and the wheels that were available, so an
  acceptance run cannot silently test a published artifact instead.
- More than one matching wheel raises `DependencySyncError` because the local
  artifact is ambiguous.
- With no explicit wheelhouse, no staged wheelhouse, or an unmatched implicit
  wheelhouse, the canonical published `quickscale-core` lockstep pin remains
  authoritative.

To use local resolution, build or copy one matching `.whl` into the explicit
directory and rerun the command. To use the published dependency range, unset
`QUICKSCALE_LOCAL_WHEELHOUSE`.
