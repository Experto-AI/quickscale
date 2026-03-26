# QuickScale Makefile
# Cross-platform development commands
#
# Primary target: Linux/WSL
# Secondary: Windows (via WSL or Git Bash)
#
# Usage:
#   make bootstrap            - Full bootstrap (Python check + poetry install)
#   make setup                - Install Poetry dependencies only
#   make check                - Run all checks (lint, typecheck, test)
#   make test                 - Run all tests
#   make test-unit            - Run unit tests only
#   make lint -- --modules    - Run lint only for quickscale_modules/*
#   make test-unit -- -m      - Run unit tests only for quickscale_modules/*
#   make check -- --core      - Run checks only for quickscale_core
#   make MODULE=blog test -- --modules - Run tests only for quickscale_modules/blog
#   make test-unit SECTION=modules - Run unit tests only for quickscale_modules/*
#   make check SECTIONS="core modules" - Run checks for multiple sections without `--`
#   make test-cov             - Run tests with coverage
#   make test-e2e             - Run E2E tests (needs Docker + Playwright)
#   make test-agent           - Run agentic flow adapter tests
#   make lint                 - Run linting
#   make lint-fix             - Fix linting issues
#   make lint-frontend        - Lint React theme templates
#   make lint-agent           - Lint .agent adapter system
#   make typecheck            - Run type checking
#   make format               - Format code with ruff
#   make quality              - Run full code quality analysis
#   make ci                   - Run same checks as GitHub Actions CI
#   make ci-e2e               - Run CI checks including E2E tests
#   make docs                 - Compile contributing docs
#   make install              - Install QuickScale globally
#   make build                - Build all distribution packages
#   make publish-build        - Build packages only (no publish)
#   make publish-test         - Publish to TestPyPI
#   make publish-prod         - Publish to production PyPI
#   make publish-full         - Publish to TestPyPI then PyPI
#   make publish-module       - Publish module to split branch (MODULE=<name>)
#   make legacy-mount         - Mount legacy quickscale symlink
#   make legacy-unmount       - Unmount legacy quickscale symlink
#   make legacy-status        - Show legacy symlink status
#   make clean                - Remove build artifacts

.PHONY: setup bootstrap install \
        test test-unit test-cov test-e2e test-agent \
        lint lint-fix lint-frontend lint-agent typecheck format \
        quality check ci ci-e2e \
        docs \
        build clean \
        publish-build publish-test publish-prod publish-full publish-module \
        legacy-mount legacy-unmount legacy-status \
        version-check version-update bump-version \
        check-llm lint-llm typecheck-llm test-llm test-cov-llm \
        help

# Default Python command (uses root Poetry environment)
PYTHON ?= poetry run python
RUFF_CACHE_DIR ?= .ruff_cache/make

# Section flags must be passed after `--` so GNU make does not treat them as its
# own options, e.g. `make lint -- --modules` or `make test-unit -- -m`.
SECTION_FLAG_ARGS := $(filter --quickscale -q --core -c --cli -l --module --modules -m,$(MAKECMDGOALS))
ifneq ($(strip $(SECTION_FLAG_ARGS)),)
  $(eval $(SECTION_FLAG_ARGS):;@:)
endif

define map_section
$(if $(filter --quickscale -q,$(1)),quickscale,$(if $(filter --core -c,$(1)),core,$(if $(filter --cli -l,$(1)),cli,$(if $(filter --module --modules -m,$(1)),modules,))))
endef

RAW_SECTION_VARS := $(strip $(SECTIONS) $(SECTION))
SECTION_VARS := $(foreach section,$(RAW_SECTION_VARS),$(if $(filter module,$(section)),modules,$(section)))
SELECTED_SECTIONS := $(strip $(foreach arg,$(SECTION_FLAG_ARGS),$(call map_section,$(arg))))
ACTIVE_SECTIONS := $(if $(SECTION_VARS),$(SECTION_VARS),$(if $(SELECTED_SECTIONS),$(SELECTED_SECTIONS),quickscale core cli modules))
MODULE_DIRS := $(if $(MODULE),quickscale_modules/$(MODULE),$(wildcard quickscale_modules/*))

# Source directories for linting and type checking
SRC_DIRS := quickscale/src quickscale_core/src quickscale_cli/src

# Test directories
TEST_DIRS := quickscale_core/tests quickscale_cli/tests

help:
	@echo "QuickScale Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup                - Install Poetry dependencies only"
	@echo "  make bootstrap            - Full bootstrap (Python check + poetry install)"
	@echo "  make install              - Install QuickScale CLI globally"
	@echo ""
	@echo "Testing:"
	@echo "  make test                 - Run all unit + integration tests"
	@echo "  make test-unit            - Run unit tests only (no integration)"
	@echo "  make test -- --modules    - Run tests only for quickscale_modules/*"
	@echo "  make test-unit -- --core  - Run unit tests only for quickscale_core"
	@echo "  make test-unit SECTION=modules - Run unit tests only for quickscale_modules/*"
	@echo "  make test-cov             - Run tests with coverage report"
	@echo "  make test-e2e             - Run E2E tests (needs Docker + Playwright)"
	@echo "  make test-agent           - Run agentic flow adapter tests"
	@echo ""
	@echo "Quality Checks:"
	@echo "  make lint                 - Check linting (no changes)"
	@echo "  make lint-fix             - Fix linting issues"
	@echo "  make lint-frontend        - Lint React theme templates (ESLint + TypeScript)"
	@echo "  make lint-agent           - Lint .agent adapter shell scripts"
	@echo "  make typecheck            - Run mypy type checking"
	@echo "  make format               - Format code with ruff"
	@echo "  make quality              - Full quality analysis (dead code, complexity, duplication)"
	@echo "  make check                - Run all checks (lint, typecheck, test)"
	@echo "  make ci                   - Run same checks as GitHub Actions"
	@echo "  make ci-e2e               - Run CI checks including E2E tests"
	@echo ""
	@echo "Section Flags:"
	@echo "  Pass flags after \`--\`: --quickscale/-q, --core/-c, --cli/-l, --modules/-m"
	@echo "  Examples: make lint -- -m | make typecheck -- --core | make check -- --cli --modules"
	@echo "  Variable alternative: SECTION=modules or SECTIONS=\"core modules\""
	@echo "  Optional: MODULE=blog limits the modules scope to one module"
	@echo "  Example: make MODULE=blog test-unit -- --modules"
	@echo ""
	@echo "Docs:"
	@echo "  make docs                 - Compile contributing docs from docs/contrib/"
	@echo ""
	@echo "Build & Publish:"
	@echo "  make build                - Build all distribution packages"
	@echo "  make publish-build        - Build packages only (no publish)"
	@echo "  make publish-test         - Publish to TestPyPI"
	@echo "  make publish-prod         - Publish to production PyPI"
	@echo "  make publish-full         - Publish TestPyPI → verify → PyPI"
	@echo "  make publish-module       - Publish module to split branch (MODULE=<name>)"
	@echo "  make clean                - Remove build artifacts"
	@echo ""
	@echo "Legacy:"
	@echo "  make legacy-mount         - Create symlink to ../quickscale-legacy"
	@echo "  make legacy-unmount       - Remove legacy symlink"
	@echo "  make legacy-status        - Show legacy symlink status"
	@echo ""
	@echo "LLM Optimized Checks (Quiet on success):"
	@echo "  make check-llm            - Run all checks quietly"
	@echo "  make test-cov-llm         - Run coverage quietly"
	@echo ""
	@echo "Version Management:"
	@echo "  make version-check        - Verify VERSION matches all pyproject.toml files"
	@echo "  make version-update       - Update all versioned files from VERSION"
	@echo "  make bump-version X.Y.Z   - Set new version and update all files"

# --- Setup ---

# Bootstrap full development environment (Python check + poetry install)
bootstrap:
	@scripts/bootstrap.sh

# Setup development environment (alias kept for familiarity)
setup:
	@poetry install
	@echo "✅ Dependencies installed!"

# Install QuickScale CLI globally
install:
	@scripts/install_global.sh

# --- Testing ---

# Run all tests
test:
	@set -e; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "ℹ️ quickscale has no test suite to run."; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Testing quickscale_core..."; \
		$(PYTHON) -m pytest quickscale_core/tests -v --tb=short -m "not e2e"; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Testing quickscale_cli..."; \
		$(PYTHON) -m pytest quickscale_cli/tests -v --tb=short -m "not e2e" --cov=quickscale_cli --cov-report=term-missing --cov-report=html --cov-fail-under=90; \
	fi; \
	if [ -n "$(filter modules,$(ACTIVE_SECTIONS))" ]; then \
		if [ -n "$(MODULE)" ] && [ ! -d "quickscale_modules/$(MODULE)" ]; then \
			echo "Error: MODULE=$(MODULE) does not exist."; \
			exit 1; \
		fi; \
		mod_found=0; \
		for mod in $(MODULE_DIRS); do \
			if [ -d "$$mod/tests" ]; then \
				mod_found=1; \
				mod_name=$$(basename "$$mod"); \
				echo "📦 Testing module: $$mod_name..."; \
				PYTHONPATH="$$mod:$$mod/src" $(PYTHON) -m pytest "$$mod/tests/" -v --tb=short -o "addopts=" -m "not e2e" -p pytest_django --ds=tests.settings; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No module test suites matched the current filters."; \
		fi; \
	fi

# Run unit tests only (selected sections, no integration)
test-unit:
	@set -e; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "ℹ️ quickscale has no test suite to run."; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Unit testing quickscale_core..."; \
		$(PYTHON) -m pytest quickscale_core/tests -v --tb=short -m "not integration and not e2e"; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Unit testing quickscale_cli..."; \
		$(PYTHON) -m pytest quickscale_cli/tests -v --tb=short -m "not integration and not e2e" --cov=quickscale_cli --cov-report=term-missing --cov-report=html --cov-fail-under=90; \
	fi; \
	if [ -n "$(filter modules,$(ACTIVE_SECTIONS))" ]; then \
		if [ -n "$(MODULE)" ] && [ ! -d "quickscale_modules/$(MODULE)" ]; then \
			echo "Error: MODULE=$(MODULE) does not exist."; \
			exit 1; \
		fi; \
		mod_found=0; \
		for mod in $(MODULE_DIRS); do \
			if [ -d "$$mod/tests" ]; then \
				mod_found=1; \
				mod_name=$$(basename "$$mod"); \
				echo "📦 Unit testing module: $$mod_name..."; \
				PYTHONPATH="$$mod:$$mod/src" $(PYTHON) -m pytest "$$mod/tests/" -v --tb=short -o "addopts=" -m "not integration and not e2e" -p pytest_django --ds=tests.settings; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No module test suites matched the current filters."; \
		fi; \
	fi

# Run E2E tests (starts PostgreSQL container, installs Playwright browsers)
test-e2e:
	@scripts/test_e2e.sh

# Run agentic flow adapter tests only
test-agent:
	@scripts/test_agentic_flow.sh

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

# --- Lint / Format ---

# Run linting (check only, no changes)
lint:
	@set -e; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Linting quickscale..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale/src; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) --check quickscale/src; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Linting quickscale_core..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale_core/src quickscale_core/tests; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) --check quickscale_core/src quickscale_core/tests; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Linting quickscale_cli..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale_cli/src quickscale_cli/tests; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) --check quickscale_cli/src quickscale_cli/tests; \
	fi; \
	if [ -n "$(filter modules,$(ACTIVE_SECTIONS))" ]; then \
		if [ -n "$(MODULE)" ] && [ ! -d "quickscale_modules/$(MODULE)" ]; then \
			echo "Error: MODULE=$(MODULE) does not exist."; \
			exit 1; \
		fi; \
		mod_found=0; \
		for mod in $(MODULE_DIRS); do \
			if [ -d "$$mod/src" ]; then \
				mod_found=1; \
				mod_name=$$(basename "$$mod"); \
				echo "📦 Linting module: $$mod_name..."; \
				lint_args="$$mod/src"; \
				if [ -d "$$mod/tests" ]; then \
					lint_args="$$lint_args $$mod/tests"; \
				fi; \
				$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) $$lint_args; \
				$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) --check $$lint_args; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No modules matched the current filters."; \
		fi; \
	fi
	@echo "✅ Linting passed!"

# Run linting with auto-fix
lint-fix:
	@set -e; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Lint-fixing quickscale..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale/src --fix; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale/src; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Lint-fixing quickscale_core..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale_core/src quickscale_core/tests --fix; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale_core/src quickscale_core/tests; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Lint-fixing quickscale_cli..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale_cli/src quickscale_cli/tests --fix; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale_cli/src quickscale_cli/tests; \
	fi; \
	if [ -n "$(filter modules,$(ACTIVE_SECTIONS))" ]; then \
		if [ -n "$(MODULE)" ] && [ ! -d "quickscale_modules/$(MODULE)" ]; then \
			echo "Error: MODULE=$(MODULE) does not exist."; \
			exit 1; \
		fi; \
		mod_found=0; \
		for mod in $(MODULE_DIRS); do \
			if [ -d "$$mod/src" ]; then \
				mod_found=1; \
				mod_name=$$(basename "$$mod"); \
				echo "📦 Lint-fixing module: $$mod_name..."; \
				lint_args="$$mod/src"; \
				if [ -d "$$mod/tests" ]; then \
					lint_args="$$lint_args $$mod/tests"; \
				fi; \
				$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) $$lint_args --fix; \
				$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) $$lint_args; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No modules matched the current filters."; \
		fi; \
	fi
	@echo "✅ Linting fixed!"

# Run type checking (uses mypy.ini config from project root)
typecheck:
	@set -e; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Type checking quickscale..."; \
		$(PYTHON) -m mypy quickscale/src --show-error-codes; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Type checking quickscale_core..."; \
		$(PYTHON) -m mypy quickscale_core/src --show-error-codes; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Type checking quickscale_cli..."; \
		$(PYTHON) -m mypy quickscale_cli/src --show-error-codes; \
	fi; \
	if [ -n "$(filter modules,$(ACTIVE_SECTIONS))" ]; then \
		if [ -n "$(MODULE)" ] && [ ! -d "quickscale_modules/$(MODULE)" ]; then \
			echo "Error: MODULE=$(MODULE) does not exist."; \
			exit 1; \
		fi; \
		mod_found=0; \
		for mod in $(MODULE_DIRS); do \
			if [ -d "$$mod/src" ]; then \
				mod_found=1; \
				mod_name=$$(basename "$$mod"); \
				echo "📦 Type checking module: $$mod_name..."; \
				$(PYTHON) -m mypy "$$mod/src" --show-error-codes; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No modules matched the current filters."; \
		fi; \
	fi
	@echo "✅ Type checking passed!"

# Lint React theme templates (renders to tmp dir, runs ESLint + TypeScript check)
lint-frontend:
	@scripts/lint_frontend.sh

# Lint .agent adapter shell scripts for syntax errors
lint-agent:
	@scripts/lint_agentic_flow.sh

# Format code with ruff
format:
	@set -e; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Formatting quickscale..."; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale/src; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Formatting quickscale_core..."; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale_core/src quickscale_core/tests; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Formatting quickscale_cli..."; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale_cli/src quickscale_cli/tests; \
	fi; \
	if [ -n "$(filter modules,$(ACTIVE_SECTIONS))" ]; then \
		if [ -n "$(MODULE)" ] && [ ! -d "quickscale_modules/$(MODULE)" ]; then \
			echo "Error: MODULE=$(MODULE) does not exist."; \
			exit 1; \
		fi; \
		mod_found=0; \
		for mod in $(MODULE_DIRS); do \
			if [ -d "$$mod/src" ]; then \
				mod_found=1; \
				mod_name=$$(basename "$$mod"); \
				echo "📦 Formatting module: $$mod_name..."; \
				format_args="$$mod/src"; \
				if [ -d "$$mod/tests" ]; then \
					format_args="$$format_args $$mod/tests"; \
				fi; \
				$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) $$format_args; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No modules matched the current filters."; \
		fi; \
	fi
	@echo "✅ Formatting done!"

# --- Combined Checks ---

# Run all checks (lint + typecheck + test)
check: lint typecheck test
	@echo ""
	@echo "🎉 All checks passed!"

# Full code quality analysis: dead code (vulture), complexity (radon), duplication (pylint)
# Reports saved to .quickscale/quality_report.{json,md}
quality:
	@scripts/check_quality.sh

# Run the same checks as GitHub Actions CI (lint + typecheck + unit tests)
ci:
	@scripts/check_ci_locally.sh

# Run full CI including E2E tests (slow — needs Docker + Playwright)
ci-e2e:
	@scripts/check_ci_locally.sh --e2e

# --- Docs ---

# Compile docs/contrib/ into contributing.md and .cursor/rules/
docs:
	@scripts/compile_docs.sh

# --- Build & Publish ---

# Build all distribution packages
build:
	@rm -rf quickscale/dist/ quickscale_core/dist/ quickscale_cli/dist/
	@cd quickscale && poetry build
	@cd quickscale_core && poetry build
	@cd quickscale_cli && poetry build
	@echo "✅ Build complete! See dist/ in each package."

# Build packages only (no upload)
publish-build:
	@scripts/publish.sh build

# Publish to TestPyPI
publish-test:
	@scripts/publish.sh test

# Publish to production PyPI
publish-prod:
	@scripts/publish.sh prod

# Publish to TestPyPI, verify, then production PyPI
publish-full:
	@scripts/publish.sh full

# Publish module changes to its split branch (e.g. make publish-module MODULE=auth)
publish-module:
	@if [ -z "$(MODULE)" ]; then echo "Error: MODULE is required (e.g. make publish-module MODULE=auth)"; exit 1; fi
	@scripts/publish_module.sh $(MODULE)

# Clean build artifacts
clean:
	rm -rf quickscale/dist/ quickscale_core/dist/ quickscale_cli/dist/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.json
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned!"

# --- Legacy Symlink ---

# Mount symlink pointing to ../quickscale-legacy
legacy-mount:
	@scripts/quickscale_legacy_symlink.sh mount

# Remove legacy symlink
legacy-unmount:
	@scripts/quickscale_legacy_symlink.sh unmount

# Show legacy symlink status
legacy-status:
	@scripts/quickscale_legacy_symlink.sh status

# --- Version Management ---
# Single source of truth: VERSION file
# Delegates to scripts/version_tool.sh for multi-package sync
#
# Usage:
#   make version-check              - Verify VERSION matches all pyproject.toml files
#   make version-update             - Update all versioned files from VERSION (pyproject.toml, dependencies, _version.py, docs)
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
	@scripts/version_tool.sh update

bump-version:
	@if [ -z "$(VERSION_ARG)" ]; then echo "Error: version argument required (e.g. make bump-version 0.76.0)"; exit 1; fi
	@echo "$(VERSION_ARG)" > VERSION
	@echo "  UPDATED: VERSION"
	@scripts/version_tool.sh update
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
