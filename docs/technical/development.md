# QuickScale Development Setup Guide

**Target**: New contributor can clone repository and run tests successfully in <15 minutes.

**Last Updated**: October 15, 2025  
**Tested On**: Ubuntu 22.04, Python 3.10-3.12

---

## Prerequisites

Before starting, ensure you have these tools installed:

### Required Tools

1. **Python 3.10 or higher**
   ```bash
   python3 --version
   # Should show 3.10.x, 3.11.x, or 3.12.x
   ```

2. **Git 2.25+**
   ```bash
   git --version
   # Should show 2.25.0 or higher
   ```

3. **Poetry 1.5+** (Python package manager)
   ```bash
   poetry --version
   # Should show 1.5.0 or higher
   ```

### Installing Prerequisites

**Ubuntu/Debian:**
```bash
# Python 3.10+ (if not already installed)
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# Git
sudo apt install git

# Poetry (recommended method)
curl -sSL https://install.python-poetry.org | python3 -
# Add Poetry to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```

**macOS:**
```bash
# Python 3.10+ via Homebrew
brew install python@3.10

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

### 1. Clone Repository (1 minute)
```bash
git clone https://github.com/Experto-AI/quickscale.git
cd quickscale
```

### 2. Bootstrap Development Environment (2-3 minutes)
```bash
# Run bootstrap script (sets up virtualenv, checks dependencies)
./scripts/bootstrap.sh

# Install all package dependencies
poetry install
```

**What bootstrap.sh does:**
- Checks Python version compatibility
- Verifies Poetry installation
- Configures Poetry to use in-project virtualenv (`.venv/`)
- Installs pre-commit hooks

### 3. Verify Installation (1-2 minutes)
```bash
# Check quickscale CLI is available
poetry run quickscale --version
# Should show version number (e.g., 0.56.2)

# List installed packages
poetry show
# Should show quickscale_core, quickscale_cli, and dependencies
```

### 4. Run Tests (3-5 minutes)
```bash
# Run all tests with coverage
./scripts/test-all.sh

# Or run with Poetry directly
poetry run pytest

# Expected output:
# =================== test session starts ====================
# quickscale_core: 96% coverage (target: >80%)
# quickscale_cli: 82% coverage (target: >75%)
# =================== XX passed in X.XXs ====================
```

### 5. Run Linters (1-2 minutes)
```bash
# Run all code quality checks
./scripts/lint.sh

# Expected output:
# ✓ ruff format --check (code formatting)
# ✓ ruff check (linting)
# ✓ mypy (type checking)
# All checks passed!
```

### 6. Generate Test Project (2-3 minutes)
```bash
# Create a test Django project
poetry run quickscale init testproject

# Verify generated project
cd testproject
poetry install
poetry run python manage.py migrate
poetry run pytest

# Expected: 5/5 tests passing
```

**Total time: some minutes** ✅

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
```bash
# All tests
poetry run pytest

# Specific package
poetry run pytest quickscale_core/tests/
poetry run pytest quickscale_cli/tests/

# Specific test file
poetry run pytest quickscale_core/tests/test_generator.py

# With verbose output
poetry run pytest -v

# With coverage report
poetry run pytest --cov=quickscale_core --cov=quickscale_cli
```

**Run linters:**
```bash
# All linters (via script)
./scripts/lint.sh

# Individual linters
poetry run ruff format --check .    # Check formatting
poetry run ruff format .             # Auto-format code
poetry run ruff check .              # Linting
poetry run mypy quickscale_core/ quickscale_cli/  # Type checking
```

**Pre-commit hooks:**
```bash
# Install hooks (one-time)
poetry run pre-commit install

# Run manually on all files
poetry run pre-commit run --all-files

# Hooks run automatically on 'git commit'
```

### Making Changes

**Typical workflow:**
1. Create feature branch: `git checkout -b feature/my-feature`
2. Make code changes in `quickscale_core/src/` or `quickscale_cli/src/`
3. Add tests in corresponding `tests/` directory
4. Run tests: `./scripts/test-all.sh`
5. Run linters: `./scripts/lint.sh`
6. Commit changes: `git commit -m "feat: description"`
7. Push and create PR: `git push origin feature/my-feature`

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

---

## Repository Structure

```
quickscale/
├── quickscale_core/          # Core package (scaffolding, templates)
│   ├── src/quickscale_core/  # Source code
│   ├── tests/                # Tests (NOT in src/)
│   └── pyproject.toml        # Package config
├── quickscale_cli/           # CLI package
│   ├── src/quickscale_cli/   # Source code
│   ├── tests/                # Tests
│   └── pyproject.toml        # Package config
├── docs/                     # Documentation
│   ├── technical/            # Technical specs
│   ├── contrib/              # Contributing guides
│   └── releases/             # Release notes
├── scripts/                  # Helper scripts
│   ├── bootstrap.sh          # Development setup
│   ├── test-all.sh           # Run all tests
│   └── lint.sh               # Run all linters
└── pyproject.toml            # Root workspace config
```

**Important locations:**
- Generated project templates: `quickscale_core/src/quickscale_core/generator/templates/`
- CLI command implementations: `quickscale_cli/src/quickscale_cli/commands/`
- Tests parallel source structure: `quickscale_core/tests/` mirrors `src/quickscale_core/`

---

## Common Issues & Solutions

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

**Cause**: System Python version doesn't match project requirements (3.10+)

**Solution:**
```bash
# Check current version
python3 --version

# Install specific version (Ubuntu)
sudo apt install python3.10 python3.10-venv

# Tell Poetry to use specific version
poetry env use python3.10

# Verify
poetry run python --version
```

---

## Advanced Topics

### Testing Generated Projects

**Full integration test:**
```bash
# Generate project
poetry run quickscale init integration_test

# Setup and test
cd integration_test
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
# Build wheels for both packages
cd quickscale_core && poetry build && cd ..
cd quickscale_cli && poetry build && cd ..

# Test installation from wheel
python -m venv test_venv
source test_venv/bin/activate
pip install quickscale_core/dist/*.whl
pip install quickscale_cli/dist/*.whl
quickscale --version
```

---

## Getting Help

**Documentation:**
- Technical decisions: [docs/technical/decisions.md](./decisions.md)
- User commands: [docs/technical/user_manual.md](./user_manual.md)
- Contributing workflow: [docs/contrib/contributing.md](../contrib/contributing.md)

**Commands Quick Reference:**
- Bootstrap: `./scripts/bootstrap.sh`
- Install: `poetry install`
- Tests: `./scripts/test-all.sh` or `poetry run pytest`
- Linters: `./scripts/lint.sh`
- CLI: `poetry run quickscale --help`

**Troubleshooting:**
- Check [Common Issues](#common-issues--solutions) section above
- Review test output for specific errors
- Check Poetry dependencies: `poetry show`
- Verify Python version: `poetry run python --version`

**Need more help?**
- GitHub Issues: https://github.com/Experto-AI/quickscale/issues
- See existing issues for similar problems
- Create new issue with environment details (OS, Python version, error output)

---

## Success Criteria

You have a working development environment when:

- ✅ `poetry run quickscale --version` shows version number
- ✅ `./scripts/test-all.sh` passes with >80% coverage
- ✅ `./scripts/lint.sh` passes all checks
- ✅ `quickscale init testproject` generates working Django project
- ✅ Can make changes, run tests, and see results in <2 minutes

**Target: Clone → working dev environment in <15 minutes** 🎯

If you completed this guide in <15 minutes, the setup is working as intended!
