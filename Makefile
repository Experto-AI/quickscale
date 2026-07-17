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
#   make check -- --core      - Run checks only for quickscale_core
#   make MODULE=blog test -- --modules - Run tests only for quickscale_modules/blog
#   make test-integration     - Run integration tests for all modules (full gate; for focused module reruns use `make MODULE=<name> test -- --modules`)
#   make check SECTIONS="core modules" - Run checks for multiple sections without `--`
#   make test-cov             - Run tests with coverage (aggregates DR-engine coverage from backups module when PostgreSQL is available)
#   make test-e2e             - Run E2E tests (needs Docker + Playwright)
#   make test-agent           - Run agentic flow adapter tests
#   make lint                 - Run linting
#   make lint-fix             - Fix linting issues
#   make lint-frontend        - Lint React theme templates
#   make frontend-proof       - Render showcase_react and run pnpm install/type-check/build
#   make lint-agent           - Lint .agent adapter system
#   make typecheck            - Run type checking
#   make format               - Format code with ruff
#   make quality              - Run full code quality analysis
#   make ci                   - Run primary local development checks (lint + typecheck + unit tests; integration when PostgreSQL available)
#   make ci-e2e               - Run CI checks including E2E tests
#   make docs                 - Compile contributing docs
#   make install              - Install QuickScale globally
#   make beta-migrate-fresh DONOR=/abs/path RECIPIENT=/abs/path - Run fresh-first beta migration on a throwaway recipient
#   make beta-migrate-in-place DONOR=/abs/path RECIPIENT=/abs/path - Run checkpoint-first in-place beta migration
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
        test test-unit test-integration test-cov test-cov-policy test-integration-worker-pool test-e2e test-agent \
        lint lint-fix lint-frontend frontend-proof lint-agent typecheck format \
        quality check ci ci-e2e \
        docs \
        build clean \
		beta-migrate-fresh beta-migrate-in-place \
        publish-build publish-test publish-prod publish-full publish-module \
        legacy-mount legacy-unmount legacy-status \
        version-check version-update bump-version \
        check-llm lint-llm typecheck-llm test-llm test-cov-llm \
        check-core-compat check-module-core-imports check-manifest-sync \
        check-org-context-primitives \
        check-csrf-exempt \
        help

# Default Python command (uses root Poetry environment)
PYTHON ?= poetry run python
RUFF_CACHE_DIR ?= .ruff_cache/make

# Section flags must be passed after `--` so GNU make does not treat them as its
# own options, e.g. `make lint -- --modules` or `make typecheck -- --core`.
SECTION_FLAG_ARGS := $(filter --quickscale -q --core -c --cli -l --devtools -d --module --modules -m,$(MAKECMDGOALS))
ifneq ($(strip $(SECTION_FLAG_ARGS)),)
  $(eval $(SECTION_FLAG_ARGS):;@:)
endif

define map_section
$(if $(filter --quickscale -q,$(1)),quickscale,$(if $(filter --core -c,$(1)),core,$(if $(filter --cli -l,$(1)),cli,$(if $(filter --devtools -d,$(1)),devtools,$(if $(filter --module --modules -m,$(1)),modules,)))))
endef

RAW_SECTION_VARS := $(strip $(SECTIONS) $(SECTION))
SECTION_VARS := $(foreach section,$(RAW_SECTION_VARS),$(if $(filter module,$(section)),modules,$(section)))
SELECTED_SECTIONS := $(strip $(foreach arg,$(SECTION_FLAG_ARGS),$(call map_section,$(arg))))
DEFAULT_SECTIONS := quickscale core cli devtools modules
ACTIVE_SECTIONS := $(if $(SECTION_VARS),$(SECTION_VARS),$(if $(SELECTED_SECTIONS),$(SELECTED_SECTIONS),$(DEFAULT_SECTIONS)))
MODULE_DIRS := $(if $(MODULE),quickscale_modules/$(MODULE),$(wildcard quickscale_modules/*))

# Source directories for linting and type checking
SRC_DIRS := quickscale/src quickscale_core/src quickscale_cli/src quickscale_devtools/src

# Test directories
TEST_DIRS := quickscale_core/tests quickscale_cli/tests

help:
	@echo "QuickScale Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup                - Install Poetry dependencies only"
	@echo "  make bootstrap            - Full bootstrap (Python check + poetry install)"
	@echo "  make install              - Install QuickScale CLI globally"
	@echo "  make beta-migrate-fresh DONOR=/abs/path RECIPIENT=/abs/path - Run fresh-first on a throwaway recipient"
	@echo "                             Default: mutate recipient + local verification; DRY_RUN=1 plans only"
	@echo "  make beta-migrate-in-place DONOR=/abs/path RECIPIENT=/abs/path - Run checkpoint-first in-place beta migration"
	@echo "                             Default stays checkpoint-only; add CONTINUE=1 to run copy/apply/verification"
	@echo "                             Optional: REPORT=/abs/path/report.json"
	@echo ""
	@echo "Testing:"
	@echo "  make test                 - Run all tests (unit + integration)"
	@echo "  make test-unit            - Run DB-free unit tests only (core + CLI)"
	@echo "  make test -- --modules    - Run tests only for quickscale_modules/*"
	@echo "  make test-unit -- --core  - Run unit tests only for quickscale_core"
	@echo "  make test-integration     - Run integration tests for quickscale_modules/* (requires PostgreSQL)"
	@echo "  make test-cov             - Run tests with coverage report (aggregates DR-engine coverage from backups module when PostgreSQL is available)"
	@echo "  make test-e2e             - Run E2E tests (needs Docker + Playwright)"
	@echo "  make test-agent           - Run agentic flow adapter tests"
	@echo "  make test-integration-worker-pool - Run worker pool harness tests (fast, no PostgreSQL needed)"
	@echo ""
	@echo "Quality Checks:"
	@echo "  make lint                 - Check linting (no changes)"
	@echo "  make lint-fix             - Fix linting issues"
	@echo "  make lint-frontend        - Lint React theme templates (ESLint + TypeScript)"
	@echo "  make frontend-proof       - Render showcase_react and run pnpm install/type-check/build"
	@echo "  make lint-agent           - Lint .agent adapter shell scripts"
	@echo "  make typecheck            - Run mypy type checking"
	@echo "  make format               - Format code with ruff"
	@echo "  make quality              - Full quality analysis (dead code, complexity, duplication)"
	@echo "  make check                - Run all checks (lint, typecheck, test)"
	@echo "  make ci                   - Run primary local CI checks (lint + typecheck + unit tests; integration when PostgreSQL available)"
	@echo "  make ci-e2e               - Run CI checks including E2E tests"
	@echo ""
	@echo "Section Flags:"
	@echo "  Pass flags after \`--\`: --quickscale/-q, --core/-c, --cli/-l, --devtools/-d, --modules/-m"
	@echo "  Examples: make lint -- -m | make typecheck -- --core | make check -- --cli --modules"
	@echo "  Variable alternative: SECTION=modules or SECTIONS=\"core modules\""
	@echo "  Optional: MODULE=blog limits the modules scope to one module"
	@echo "  Example: make MODULE=blog test -- --modules"
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
	@echo "  make publish-module-status - Show split-branch status for all modules"
	@echo "  make publish-modules-outdated - Publish modules with missing or outdated branches"
	@echo "  make clean                - Remove build artifacts"
	@echo ""
	@echo "Legacy:"
	@echo "  make legacy-mount         - Create symlink to ../quickscale-legacy"
	@echo "  make legacy-unmount       - Remove legacy symlink"
	@echo "  make legacy-status        - Show legacy symlink status"
	@echo ""
	@echo "Repository Gates:"
	@echo "  make check-core-compat    - Verify each module's quickscale_core imports"
	@echo "                               resolve against the current core API"
	@echo "  make check-module-core-imports - Verify module code imports only from"
	@echo "                               quickscale_core.runtime (with per-module"
	@echo "                               legacy exceptions for billing/crm adapters)"
	@echo "  make check-manifest-sync  - Verify all module-owned module.yml files"
	@echo "                               match their core snapshots"
	@echo "  make manifest-sync        - Copy source manifests to snapshot paths"
	@echo "  make check-org-context-primitives - Hard-fail gate for direct external use"
	@echo "                               of the three privatized org-context primitives"
	@echo "                               (_tenant_context, _set_current_org_for_context,"
	@echo "                               _set_db_current_org_id). Exits 1 on any"
	@echo "                               violation. Existing migrations are complete."
	@echo "                               None-path hardening remains deferred"
	@echo "                               (see roadmap.md)."
	@echo "  make check-csrf-exempt      - Hard-fail gate pairing every csrf_exempt"
	@echo "                               callsite with _enforce_csrf or cryptographic"
	@echo "                               signature verification. Exits 1 on any"
	@echo "                               unprotected csrf_exempt usage."
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
	@scripts/bootstrap.sh
	@poetry install
	@echo "✅ Dependencies and system checks complete!"
install:
	@scripts/install_global.sh

# Run beta-site migration using the fresh-first workflow on a throwaway recipient.
beta-migrate-fresh:
	@set -e; \
	if [ -z "$(DONOR)" ] || [ -z "$(RECIPIENT)" ]; then \
		echo "Error: DONOR and RECIPIENT are required absolute paths (optional: DRY_RUN=1 REPORT=/abs/path/report.json)."; \
		exit 1; \
	fi; \
	dry_run_args=""; \
	if [ "$(DRY_RUN)" = "1" ] || [ "$(DRY_RUN)" = "true" ] || [ "$(DRY_RUN)" = "yes" ]; then \
		dry_run_args="--dry-run"; \
	fi; \
	if [ -n "$(REPORT)" ]; then \
		poetry run python scripts/beta_migrate.py fresh-first \
			--donor "$(DONOR)" \
			--recipient "$(RECIPIENT)" \
			$$dry_run_args \
			--report-path "$(REPORT)"; \
	else \
		poetry run python scripts/beta_migrate.py fresh-first \
			--donor "$(DONOR)" \
			--recipient "$(RECIPIENT)" \
			$$dry_run_args; \
	fi

# Emit the baseline in-place checkpoint report without copy/apply/verification execution.
beta-migrate-in-place:
	@set -e; \
	if [ -z "$(DONOR)" ] || [ -z "$(RECIPIENT)" ]; then \
		echo "Error: DONOR and RECIPIENT are required absolute paths (optional: DRY_RUN=1 CONTINUE=1 REPORT=/abs/path/report.json)."; \
		exit 1; \
	fi; \
	dry_run_args=""; \
	continue_args=""; \
	if [ "$(DRY_RUN)" = "1" ] || [ "$(DRY_RUN)" = "true" ] || [ "$(DRY_RUN)" = "yes" ]; then \
		dry_run_args="--dry-run"; \
	fi; \
	if [ "$(CONTINUE)" = "1" ] || [ "$(CONTINUE)" = "true" ] || [ "$(CONTINUE)" = "yes" ]; then \
		continue_args="--continue-after-checkpoint"; \
	fi; \
	if [ -n "$(REPORT)" ]; then \
		poetry run python scripts/beta_migrate.py in-place \
			--donor "$(DONOR)" \
			--recipient "$(RECIPIENT)" \
			$$dry_run_args \
			$$continue_args \
			--report-path "$(REPORT)"; \
	else \
		poetry run python scripts/beta_migrate.py in-place \
			--donor "$(DONOR)" \
			--recipient "$(RECIPIENT)" \
			$$dry_run_args \
			$$continue_args; \
	fi

# --- Testing ---

# Run all tests
test:
	@set -e; \
	if [ "$(strip $(ACTIVE_SECTIONS))" = "$(strip $(DEFAULT_SECTIONS))" ] && [ -z "$(MODULE)" ]; then \
		$(MAKE) test-unit && $(MAKE) test-integration; \
		exit 0; \
	fi; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "ℹ️ quickscale has no test suite to run."; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Testing quickscale_core..."; \
		$(PYTHON) -m pytest quickscale_core/tests -q --tb=short -m "not e2e"; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Testing quickscale_cli..."; \
		$(PYTHON) -m pytest quickscale_cli/tests -q --tb=short -m "not e2e" --cov=quickscale_cli --cov-report=term-missing --cov-report=html --cov-fail-under=90; \
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
				module_pythonpath="$$mod:."; \
				if [ -d "$$mod/src" ]; then \
					module_pythonpath="$$module_pythonpath:$$mod/src"; \
				fi; \
				for sibling in quickscale_modules/*; do \
					if [ "$$sibling" != "$$mod" ] && [ -d "$$sibling/src" ]; then \
						module_pythonpath="$$module_pythonpath:$$sibling/src"; \
					fi; \
				done; \
				if [ -n "$$PYTHONPATH" ]; then \
					module_pythonpath="$$module_pythonpath:$$PYTHONPATH"; \
				fi; \
				PYTHONPATH="$$module_pythonpath" $(PYTHON) -m pytest "$$mod/tests/" -q --tb=short -o "addopts=" -m "not e2e" -p pytest_django --ds=tests.settings; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No module test suites matched the current filters."; \
		fi; \
	fi

# Run DB-free unit tests only (core + CLI, no modules — use test-integration for modules)
test-unit:
	@set -e; \
	if [ -n "$(filter quickscale,$(ACTIVE_SECTIONS))" ]; then \
		echo "ℹ️ quickscale has no test suite to run."; \
	fi; \
	if [ -n "$(filter core,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Unit testing quickscale_core..."; \
		$(PYTHON) -m pytest quickscale_core/tests -q --tb=short -m "not integration and not e2e" \
			--cov=quickscale_core --cov-report=xml:quickscale_core/coverage.xml; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Unit testing quickscale_cli..."; \
		$(PYTHON) -m pytest quickscale_cli/tests -q --tb=short -m "not integration and not e2e" \
			--cov=quickscale_cli --cov-report=term-missing --cov-report=html \
			--cov-report=xml:quickscale_cli/coverage.xml --cov-fail-under=90; \
	fi; \
	if [ -n "$(filter modules,$(ACTIVE_SECTIONS))" ]; then \
		echo ""; \
		echo "❌ Module test suites have moved from test-unit to test-integration."; \
		echo ""; \
		echo "   To run module integration tests (requires PostgreSQL), use:"; \
		echo "     make test-integration"; \
		echo ""; \
		echo "   Or use the 'test' target for mixed unit + integration runs:"; \
		echo "     make MODULE=<name> test -- --modules"; \
		echo ""; \
		exit 1; \
	fi

# Run integration tests (module suites — requires PostgreSQL 18 with a
# LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER role).  Sets QUICKSCALE_ALLOW_BYPASSRLS=0
# by default so the SA58 boot guard stays active against the restricted role.
# Override explicitly per-suite (SA14.4 hatch) for tests that need BYPASSRLS.
test-integration:
	@scripts/test_integration.sh

# Run E2E tests (starts PostgreSQL container, installs Playwright browsers)
test-e2e:
	@scripts/test_e2e.sh

# Run agentic flow adapter tests only
test-agent:
	@scripts/test_agentic_flow.sh

# Run tests with coverage (90% equal-weight package mean, 80% per-file threshold)
#
# Phase 1: Core + CLI unit tests (threshold deferred via --cov-fail-under=0)
# Phase 2: Backups-module tests (when PostgreSQL is available) — aggregates
#          legitimate DR-engine exercise into the combined coverage measurement.
#          Set REQUIRE_BACKUPS_COVERAGE=1 to fail when PostgreSQL or the DR
#          toolchain is not available (instead of silently skipping).
# Phase 3: Combined coverage report (threshold deferred via --fail-under=0).
# Phase 4: Explicit dual-threshold policy check via check_coverage_policy.py
#          (90% equal-weight package mean + 80% per-file minimum).
# Phase 5: Final exit code (test failures are captured but coverage is always reported).
#
# Usage:
#   make test-cov                          — standalone (backups optional)
#   make test-cov REQUIRE_BACKUPS_COVERAGE=1 — CI mode (backups required)
test-cov:
	@set -e; \
	overall_exit=0; \
	rm -f .coverage; \
	echo "📦 Phase 1 — Running core + CLI unit tests with coverage..."; \
	set +e; \
	$(PYTHON) -m pytest $(TEST_DIRS) -q --tb=short -m "not e2e" \
		--cov=quickscale_core \
		--cov=quickscale_cli \
		--cov-report= \
		--cov-fail-under=0; \
	phase1_exit=$$?; \
	set -e; \
	if [ $$phase1_exit -ne 0 ]; then \
		echo "⚠️  Phase 1 — Core/CLI tests had failures (exit $$phase1_exit) — coverage data still captured"; \
		overall_exit=$$phase1_exit; \
	fi; \
	pg_available=false; \
	dr_tools_missing=false; \
	for tool in pg_dump pg_restore; do \
		if ! command -v "$$tool" >/dev/null 2>&1; then \
			echo "ℹ️  Required DR tool '$$tool' not found in PATH"; \
			dr_tools_missing=true; \
		fi; \
	done; \
	if [ "$$dr_tools_missing" = false ] && $(PYTHON) -c "import psycopg2; conn = psycopg2.connect(\
		host='$${QS_BACKUPS_DB_HOST:-localhost}',\
		port='$${QS_BACKUPS_DB_PORT:-5432}',\
		dbname='postgres',\
		user='$${QS_BACKUPS_DB_USER:-postgres}',\
		password='$${QS_BACKUPS_DB_PASSWORD:-}'\
	); conn.close()" >/dev/null 2>&1; then \
		pg_available=true; \
	fi; \
	if [ "$$pg_available" = true ]; then \
		echo "📦 Phase 2 — Running backups-module tests with coverage append..."; \
		mod="quickscale_modules/backups"; \
		module_pythonpath="$$mod:."; \
		if [ -d "$$mod/src" ]; then \
			module_pythonpath="$$module_pythonpath:$$mod/src"; \
		fi; \
		for sibling in quickscale_modules/*; do \
			if [ "$$sibling" != "$$mod" ] && [ -d "$$sibling/src" ]; then \
				module_pythonpath="$$module_pythonpath:$$sibling/src"; \
			fi; \
		done; \
		set +e; \
		PYTHONPATH="$$module_pythonpath" $(PYTHON) -m pytest "$$mod/tests/" \
			-q --tb=short -o "addopts=" -m "not e2e" -p pytest_django --ds=tests.settings \
			--cov=quickscale_core --cov-append \
			--cov-report=; \
		phase2_exit=$$?; \
		set -e; \
		if [ $$phase2_exit -ne 0 ]; then \
			echo "⚠️  Phase 2 — Backups-module tests had failures (exit $$phase2_exit) — coverage data still captured"; \
			[ $$overall_exit -eq 0 ] && overall_exit=$$phase2_exit; \
		fi; \
	else \
		if [ -n "$(REQUIRE_BACKUPS_COVERAGE)" ]; then \
			echo "❌ REQUIRE_BACKUPS_COVERAGE is set but PostgreSQL or DR toolchain is not available."; \
			echo "   Ensure PostgreSQL 18 is running on localhost:5432 and the QS_BACKUPS_DB_*"; \
			echo "   environment variables point to a valid LOGIN CREATEDB NOINHERIT NOBYPASSRLS role."; \
			exit 1; \
		fi; \
		echo "ℹ️ Phase 2 — PostgreSQL or DR toolchain not available — skipping module coverage append (backups)"; \
	fi; \
	echo "📊 Phase 3 — Generating combined coverage report (threshold deferred to Phase 4)..."; \
	$(PYTHON) -m coverage html; \
	$(PYTHON) -m coverage report --fail-under=0; \
	$(PYTHON) -m coverage json; \
	echo "🔍 Phase 4 — Checking coverage policy (90% equal-weight package mean, 80% per-file)..."; \
	$(PYTHON) scripts/check_coverage_policy.py coverage.json; \
	policy_exit=$$?; \
	if [ $$policy_exit -ne 0 ]; then \
		echo "⚠️  Phase 4 — Coverage policy check failed (exit $$policy_exit)"; \
		[ $$overall_exit -eq 0 ] && overall_exit=$$policy_exit; \
	fi; \
	echo "📊 Coverage report: htmlcov/index.html"; \
	exit $$overall_exit

# Run the coverage policy helper test suite independently.
# This verifies the helper's arithmetic, validation, and fail-closed
# behaviour before the main test-cov pipeline uses it.
test-cov-policy:
	@$(PYTHON) -m pytest scripts/test_ci_coverage_policy.py -q --tb=short

# Run the QS_INTEGRATION_JOBS validation and worker-pool harness tests.
# These are fast, self-contained, and do not require PostgreSQL.
test-integration-worker-pool:
	@$(PYTHON) -m pytest scripts/test_integration_worker_pool.py -q --tb=short

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
	if [ -n "$(filter devtools,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Linting quickscale_devtools..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale_devtools/src; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) --check quickscale_devtools/src; \
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
	if [ -n "$(filter devtools,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Lint-fixing quickscale_devtools..."; \
		$(PYTHON) -m ruff check --cache-dir $(RUFF_CACHE_DIR) quickscale_devtools/src --fix; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale_devtools/src; \
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
	if [ -n "$(filter devtools,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Type checking quickscale_devtools..."; \
		$(PYTHON) -m mypy quickscale_devtools/src --show-error-codes; \
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
				module_mypypath="$$mod:."; \
				if [ -d "$$mod/src" ]; then \
					module_mypypath="$$module_mypypath:$$mod/src"; \
				fi; \
				for sibling in quickscale_modules/*; do \
					if [ "$$sibling" != "$$mod" ] && [ -d "$$sibling/src" ]; then \
						module_mypypath="$$module_mypypath:$$sibling/src"; \
					fi; \
				done; \
				if [ -n "$$MYPYPATH" ]; then \
					module_mypypath="$$module_mypypath:$$MYPYPATH"; \
				fi; \
				MYPYPATH="$$module_mypypath" $(PYTHON) -m mypy "$$mod/src" --show-error-codes; \
			fi; \
		done; \
		if [ "$$mod_found" -eq 0 ]; then \
			echo "ℹ️ No modules matched the current filters."; \
		fi; \
	fi
	@echo "✅ Type checking passed!"

# Lint React theme templates (renders to tmp dir, runs ESLint + TypeScript check)
lint-frontend:
	@poetry run scripts/lint_frontend.sh

# Render showcase_react and prove the generated frontend toolchain without Docker
frontend-proof:
	@scripts/frontend_proof.sh

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
	if [ -n "$(filter devtools,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Formatting quickscale_devtools..."; \
		$(PYTHON) -m ruff format --cache-dir $(RUFF_CACHE_DIR) quickscale_devtools/src; \
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

# --- Core Compatibility Check ---

# Check each module's quickscale_core imports against the current core API.
# This verifies that every import from quickscale_core in a module's source
# resolves to an existing symbol, and that the module's claimed minimum core
# version is <= the repository's current core version.
check-core-compat:
	@$(PYTHON) scripts/check_module_core_compatibility.py

# --- Module-Core Import Linter ---

# Check that module code only imports from quickscale_core.runtime
# (not from internal subpackages like dr_engine, contracts, manifest, etc.).
# Per-module legacy exceptions exist for billing/crm adapter seams only.
check-module-core-imports:
	@$(PYTHON) scripts/check_module_core_imports.py

# --- Manifest Sync Gate (SA16.1) ---

# Verify that every module-owned module.yml matches its core snapshot.
# Fails CI if drift is introduced.  Run ``make manifest-sync`` to
# resync snapshots after intentionally updating a module manifest.
check-manifest-sync:
	@$(PYTHON) scripts/sync_module_manifests.py

manifest-sync:
	@$(PYTHON) scripts/sync_module_manifests.py --sync

# --- Org-Context Primitives Gate (SA13.4) ---

# Hard-fail lint gate for direct external use of the three privatized
# org-context primitives.  Exits 1 on any violation — all SA13.2/SA13.3
# migrations are complete.  AF9 None-path hardening deferred;
# compatibility aliases remain but trigger the gate.
check-org-context-primitives:
	@$(PYTHON) scripts/check_org_context_primitives.py

# --- CSRF-Exempt Gate (SA46) ---

# Hard-fail AST gate that requires every csrf_exempt callsite to pair
# with _enforce_csrf or cryptographic signature verification.
# Exits 1 on any unprotected csrf_exempt usage.
check-csrf-exempt:
	@$(PYTHON) scripts/check_csrf_exempt_gate.py

# --- Combined Checks ---

# Run all checks (lint + typecheck + test + core-compat + import-linter + manifest-sync + gates)
check: lint typecheck test check-core-compat check-module-core-imports check-manifest-sync check-org-context-primitives check-csrf-exempt
	@echo ""
	@echo "🎉 All checks passed!"

# Full code quality analysis: dead code (vulture), complexity (radon), duplication (pylint)
# Reports saved to .quickscale/quality_report.{json,md}
quality:
	@scripts/check_quality.sh

# Run primary local development checks (lint + typecheck + unit tests; integration when PostgreSQL available)
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
	@scripts/publish_module.sh $(MODULE) $(if $(CLEAN),--clean,)

# Show split-branch status for all modules
publish-module-status:
	@scripts/publish_module.sh --status

# Publish modules whose split branches are missing or outdated
publish-modules-outdated:
	@scripts/publish_module.sh --publish-outdated $(if $(CLEAN),--clean,)

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
