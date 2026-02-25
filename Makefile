# QuickScale Makefile
# Cross-platform development commands
#
# Primary target: Linux/WSL
# Secondary: Windows (via WSL or Git Bash)
#
# Usage:
#   make setup                - Initialize Poetry environment and dependencies
#   make check                - Run all checks (lint, typecheck, test)
#   make test                 - Run all tests
#   make test-unit            - Run unit tests only (quickscale_core + quickscale_cli)
#   make test-cov             - Run tests with coverage
#   make lint                 - Run linting
#   make lint-fix             - Fix linting issues
#   make typecheck            - Run type checking
#   make format               - Format code with ruff
#   make build                - Build distribution packages
#   make clean                - Remove build artifacts

.PHONY: setup test test-unit test-cov lint lint-fix typecheck format check build clean help \
        version-check version-update bump-version \
        check-llm lint-llm typecheck-llm test-llm test-cov-llm

# Default Python command (uses root Poetry environment)
PYTHON ?= poetry run python

# Source directories for linting and type checking
SRC_DIRS := quickscale/src quickscale_core/src quickscale_cli/src

# Test directories
TEST_DIRS := quickscale_core/tests quickscale_cli/tests

help:
	@echo "QuickScale Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup                - Initialize Poetry environment and dependencies"
	@echo ""
	@echo "Quality Checks (via poetry run):"
	@echo "  make test                 - Run all tests"
	@echo "  make test-unit            - Run unit tests (core + cli only)"
	@echo "  make test-cov             - Run tests with coverage"
	@echo "  make lint                 - Check linting (no changes)"
	@echo "  make lint-fix             - Fix linting issues"
	@echo "  make typecheck            - Run type checking"
	@echo "  make format               - Format code with ruff"
	@echo "  make check                - Run all checks (lint, typecheck, test)"
	@echo ""
	@echo "LLM Optimized Checks (Quiet on success):"
	@echo "  make check-llm            - Run all checks quietly"
	@echo "  make test-cov-llm         - Run coverage quietly"
	@echo ""
	@echo "Build:"
	@echo "  make build                - Build all distribution packages"
	@echo "  make clean                - Remove build artifacts"
	@echo ""
	@echo "Version Management:"
	@echo "  make version-check        - Verify VERSION matches all pyproject.toml files"
	@echo "  make version-update       - Sync all pyproject.toml files from VERSION file"
	@echo "  make bump-version X.Y.Z   - Set new version and update all files"

# Setup development environment
setup:
	@poetry install
	@echo "✅ Dependencies installed!"

# Run all tests
test:
	@$(PYTHON) -m pytest $(TEST_DIRS) -v --tb=short

# Run unit tests only (core and cli packages)
test-unit:
	@$(PYTHON) -m pytest quickscale_core/tests quickscale_cli/tests -v --tb=short -m "not integration"

# Run tests with coverage (90% total, 80% per-file threshold)
test-cov:
	@$(PYTHON) -m pytest $(TEST_DIRS) -v \
		--cov=quickscale_core/src \
		--cov=quickscale_cli/src \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=json \
		--cov-fail-under=90
	@echo "📊 Coverage report: htmlcov/index.html"

# Run linting (check only, no changes)
lint:
	@$(PYTHON) -m ruff check $(SRC_DIRS)
	@$(PYTHON) -m ruff format --check $(SRC_DIRS)
	@echo "✅ Linting passed!"

# Run linting with auto-fix
lint-fix:
	@$(PYTHON) -m ruff check $(SRC_DIRS) --fix
	@$(PYTHON) -m ruff format $(SRC_DIRS)
	@echo "✅ Linting fixed!"

# Run type checking (uses mypy.ini config from project root)
typecheck:
	@$(PYTHON) -m mypy $(SRC_DIRS) --show-error-codes
	@echo "✅ Type checking passed!"

# Format code with ruff
format:
	@$(PYTHON) -m ruff format $(SRC_DIRS)
	@echo "✅ Formatting done!"

# Run all checks
check: lint typecheck test
	@echo ""
	@echo "🎉 All checks passed!"

# Build all distribution packages
build:
	@rm -rf quickscale/dist/ quickscale_core/dist/ quickscale_cli/dist/
	@cd quickscale && poetry build
	@cd quickscale_core && poetry build
	@cd quickscale_cli && poetry build
	@echo "✅ Build complete! See dist/ in each package."

# Clean build artifacts
clean:
	rm -rf quickscale/dist/ quickscale_core/dist/ quickscale_cli/dist/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.json
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned!"

# --- Version Management ---
# Single source of truth: VERSION file
# Delegates to scripts/version_tool.sh for multi-package sync
#
# Usage:
#   make version-check              - Verify VERSION matches all pyproject.toml files
#   make version-update             - Sync all pyproject.toml files from VERSION file
#   make bump-version 0.76.0        - Set new version and update all files

SUPPORTED_COMMANDS := bump-version
SUPPORTS_MAKE_ARGS := $(findstring $(firstword $(MAKECMDGOALS)), $(SUPPORTED_COMMANDS))
ifneq "$(SUPPORTS_MAKE_ARGS)" ""
  VERSION_ARG := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  $(eval $(VERSION_ARG):;@:)
endif

# Read version from VERSION file
VERSION := $(shell cat VERSION 2>/dev/null | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$$//')

version-check:
	@scripts/version_tool.sh check

version-update:
	@scripts/version_tool.sh sync --apply

bump-version:
	@if [ -z "$(VERSION_ARG)" ]; then echo "Error: version argument required (e.g. make bump-version 0.76.0)"; exit 1; fi
	@echo "$(VERSION_ARG)" > VERSION
	@echo "  UPDATED: VERSION"
	@scripts/version_tool.sh sync --apply
	@echo "✅ Version bumped to $(VERSION_ARG)"


# --- LLM Optimized Targets ---

lint-llm:
	@$(PYTHON) -m ruff check $(SRC_DIRS) --quiet
	@$(PYTHON) -m ruff format --check $(SRC_DIRS) --quiet

typecheck-llm:
	@$(PYTHON) -m mypy $(SRC_DIRS) --show-error-codes > mypy_log.txt 2>&1 || { cat mypy_log.txt; rm mypy_log.txt; exit 1; }
	@rm -f mypy_log.txt

test-llm:
	@$(PYTHON) -m pytest $(TEST_DIRS) -q --tb=short > pytest_log.txt 2>&1 || { cat pytest_log.txt; rm pytest_log.txt; exit 1; }
	@rm -f pytest_log.txt

test-cov-llm:
	@$(PYTHON) -m pytest $(TEST_DIRS) -q --tb=short \
		--cov=quickscale_core/src \
		--cov=quickscale_cli/src \
		--cov-report=term-missing \
		--cov-report=json \
		--cov-fail-under=90 > pytest_cov_log.txt 2>&1 || { cat pytest_cov_log.txt; rm pytest_cov_log.txt; exit 1; }
	@rm -f pytest_cov_log.txt

check-llm: lint-llm typecheck-llm test-llm
