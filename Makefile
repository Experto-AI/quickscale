# QuickScale Makefile
# Cross-platform development commands
#
# Primary target: Linux/WSL
# Secondary: Windows (via WSL or Git Bash)
#
# Usage:
#   make bootstrap            - Full bootstrap (Python check + poetry install)
#   make setup                - Install Poetry dependencies only
#   make fix                  - Auto-format + auto-fix lint (write mode)
#   make check                - Fast pre-commit gate (lint + typecheck + unit + gates)
#   make check QUIET=1        - Same as `check`, quiet on success (LLM/agent mode)
#   make ci                   - Full local-CI parity (adds integration)
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
#   make test-ci-local-parallel - Run TP1 local-CI parallelism regression tests
#   make lint                 - Run linting
#   make lint-fix             - Fix linting issues
#   make lint-frontend        - Lint React theme templates
#   make frontend-proof       - Render showcase_react and run pnpm install/type-check/build
#   make smoke-install        - Build wheels, install into throwaway venv, run non-mutating CLI smoke tests
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

.PHONY: setup bootstrap smoke-install install \
        test test-unit test-integration test-cov test-cov-policy test-integration-worker-pool test-ci-local-parallel test-e2e test-agent \
        lint lint-fix lint-frontend frontend-proof lint-agent typecheck format \
        quality fix check ci ci-e2e \
        docs \
        build clean \
		beta-migrate-fresh beta-migrate-in-place \
        publish-build publish-test publish-prod publish-full publish-module \
        legacy-mount legacy-unmount legacy-status \
        version-check version-update bump-version \
        check-core-compat check-module-core-imports check-manifest-sync \
        check-org-context-primitives \
        check-csrf-exempt \
        help

# Default Python command (uses root Poetry environment)
PYTHON ?= poetry run python
RUFF_CACHE_DIR ?= .ruff_cache/make
# Unit-test worker count. Use ``0`` for a true serial run, ``auto`` for pytest's
# own CPU-count default, or an explicit integer (e.g. CI pins a fixed count).
#
# The default is computed dynamically: min(logical CPUs, available RAM in GB),
# capped at 16. Budgeting ~1 GB of headroom per worker means that when several
# worktrees run their suites at once the shared RAM shrinks MemAvailable, so
# each subsequent run picks fewer workers instead of oversubscribing into swap.
# On an idle machine this simply resolves to 16.
PYTEST_XDIST_WORKERS ?= $(shell \
	cpus=$$(nproc 2>/dev/null || echo 4); \
	memgb=$$(awk '/MemAvailable/{printf "%d", $$2/1024/1024}' /proc/meminfo 2>/dev/null || echo 8); \
	n=$$cpus; [ "$$memgb" -lt "$$n" ] && n=$$memgb; \
	[ "$$n" -gt 16 ] && n=16; [ "$$n" -lt 1 ] && n=1; echo $$n)
PYTEST_XDIST_ARGS := $(if $(filter 0 off serial none,$(PYTEST_XDIST_WORKERS)),,-n $(PYTEST_XDIST_WORKERS) --dist loadfile)

# Per-test timeout (seconds) for the UNIT lane only. A unit test that runs
# longer than this is a hang, not a slow test, so we kill it and fail with a
# thread dump naming the culprit instead of silently wedging the whole run.
# Set to 0/empty to disable. E2E/integration lanes are intentionally exempt.
PYTEST_TIMEOUT ?= 120
PYTEST_TIMEOUT_ARGS := $(if $(filter 0 off none,$(PYTEST_TIMEOUT)),,--timeout=$(PYTEST_TIMEOUT) --timeout-method=thread)

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
	@echo "Inner loop (fast, while coding):"
	@echo "  make fix                  - Auto-format + auto-fix lint (write mode)"
	@echo "  make lint                 - Check linting, no changes"
	@echo "  make typecheck            - Run mypy type checking"
	@echo "  make format               - Format code with ruff"
	@echo "  make test-unit            - Run DB-free unit tests only (core + CLI)"
	@echo ""
	@echo "Before you push (gates):"
	@echo "  make check                - Fast gate: lint + typecheck + unit tests + repo gates"
	@echo "  make check QUIET=1        - Same as check, quiet on success (LLM/agent mode)"
	@echo "  make ci                   - Full local-CI parity (adds integration when PostgreSQL available)"
	@echo "  make ci-e2e               - Full local CI including E2E (slow — Docker + Playwright)"
	@echo ""
	@echo "Deep / occasional:"
	@echo "  make test                 - Run all tests (unit + integration)"
	@echo "  make test-integration     - Integration tests for quickscale_modules/* (requires PostgreSQL)"
	@echo "  make test-cov             - Tests with coverage report (aggregates backups DR-engine coverage when PostgreSQL is available)"
	@echo "  make test-e2e             - E2E tests (needs Docker + Playwright)"
	@echo "  make test-agent           - Agentic flow adapter tests"
	@echo "  make quality              - Full quality analysis (dead code, complexity, duplication)"
	@echo "  make lint-frontend        - Lint React theme templates (ESLint + TypeScript)"
	@echo "  make frontend-proof       - Render showcase_react and run pnpm install/type-check/build"
	@echo "  make smoke-install        - Build wheels, install into throwaway venv, run CLI smoke tests"
	@echo "  make lint-agent           - Lint .agent adapter shell scripts"
	@echo "  make test-integration-worker-pool - Worker pool harness tests (fast, no PostgreSQL)"
	@echo "  make test-ci-local-parallel - TP1 local-CI parallelism regression tests"
	@echo ""
	@echo "Modifiers (apply to most check/test targets — not commands on their own):"
	@echo "  Section flags (after \`--\`): --quickscale/-q, --core/-c, --cli/-l, --devtools/-d, --modules/-m"
	@echo "    e.g. make lint -- --core | make typecheck -- --cli --modules"
	@echo "    Variable form: SECTION=modules or SECTIONS=\"core modules\""
	@echo "  MODULE=blog               - Limit the modules scope to one module (e.g. make MODULE=blog test -- --modules)"
	@echo "  QUIET=1                   - Quiet-on-success output for \`make check\` / \`make test-cov\` (LLM/agent mode)"
	@echo "  PYTEST_XDIST_WORKERS=0|N  - Serial run (0) or pinned worker count (default: auto)"
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
	@echo "Repository gates (auto-run by \`make check\` — run solo only to debug drift):"
	@echo "  make check-core-compat            - Module quickscale_core imports resolve against current core API"
	@echo "  make check-module-core-imports    - Module code imports only from quickscale_core.runtime"
	@echo "  make check-manifest-sync          - Module-owned module.yml files match their core snapshots"
	@echo "  make manifest-sync                - Resync snapshots after intentional manifest changes"
	@echo "  make check-org-context-primitives - No external use of privatized org-context primitives"
	@echo "  make check-csrf-exempt            - Every csrf_exempt callsite is paired with CSRF/signature enforcement"
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
			$(PYTEST_XDIST_ARGS) $(PYTEST_TIMEOUT_ARGS) \
			--cov=quickscale_core --cov-report=xml:quickscale_core/coverage.xml; \
	fi; \
	if [ -n "$(filter cli,$(ACTIVE_SECTIONS))" ]; then \
		echo "📦 Unit testing quickscale_cli..."; \
		$(PYTHON) -m pytest quickscale_cli/tests -q --tb=short -m "not integration and not e2e" \
			$(PYTEST_XDIST_ARGS) $(PYTEST_TIMEOUT_ARGS) \
			--cov=quickscale_cli --cov-report=term-missing --cov-report=html \
			--cov-report=xml:quickscale_cli/coverage.xml --cov-fail-under=90; \
	fi; \
	if [ -n "$(filter modules,$(SECTION_VARS) $(SELECTED_SECTIONS))" ]; then \
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
	if [ -n "$(QUIET)" ]; then \
		$(PYTHON) -m pytest $(TEST_DIRS) -q --tb=short \
			--cov=quickscale_core/src --cov=quickscale_cli/src \
			--cov-report=term-missing --cov-report=json --cov-fail-under=90 \
			> pytest_cov_log.txt 2>&1 || { cat pytest_cov_log.txt; rm -f pytest_cov_log.txt; exit 1; }; \
		rm -f pytest_cov_log.txt; \
		exit 0; \
	fi; \
	overall_exit=0; \
	coverage_dir=$$(mktemp -d "$${TMPDIR:-/tmp}/quickscale-test-cov.XXXXXX"); \
	phase1_file="$$coverage_dir/combined.phase1"; \
	phase2_file="$$coverage_dir/combined.phase2"; \
	combined_file="$$coverage_dir/combined"; \
	cleanup_coverage() { rm -rf "$$coverage_dir"; }; \
	record_failure() { \
		failure_exit="$$1"; \
		if [ "$$overall_exit" -eq 0 ]; then \
			overall_exit="$$failure_exit"; \
		fi; \
	}; \
	trap cleanup_coverage EXIT; \
	trap 'exit 130' INT; \
	trap 'exit 143' TERM; \
	trap 'exit 129' HUP; \
	echo "📦 Phase 1 — Running core + CLI unit tests with coverage..."; \
	set +e; \
	COVERAGE_FILE="$$phase1_file" $(PYTHON) -m pytest $(TEST_DIRS) -q --tb=short -m "not e2e" \
		$(PYTEST_XDIST_ARGS) \
		--cov=quickscale_core \
		--cov=quickscale_cli \
		--cov-report= \
		--cov-fail-under=0; \
	phase1_exit=$$?; \
	set -e; \
	if [ $$phase1_exit -ne 0 ]; then \
		echo "⚠️  Phase 1 — Core/CLI tests had failures (exit $$phase1_exit) — coverage data still captured"; \
		record_failure "$$phase1_exit"; \
	fi; \
	phase1_missing=false; \
	if [ ! -f "$$phase1_file" ]; then \
		echo "❌ Phase 1 — Expected coverage data file is missing: $$phase1_file"; \
		record_failure 1; \
		phase1_missing=true; \
	fi; \
	backups_required=false; \
	if [ -n "$(REQUIRE_BACKUPS_COVERAGE)" ]; then backups_required=true; fi; \
	required_backups_missing=false; \
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
		echo "📦 Phase 2 — Running backups-module tests with isolated coverage..."; \
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
		PYTHONPATH="$$module_pythonpath" COVERAGE_FILE="$$phase2_file" $(PYTHON) -m pytest "$$mod/tests/" \
			-q --tb=short -o "addopts=" -m "not e2e" -p pytest_django --ds=tests.settings \
			$(PYTEST_XDIST_ARGS) \
			--cov=quickscale_core \
			--cov-report= \
			--cov-fail-under=0; \
		phase2_exit=$$?; \
		set -e; \
		if [ $$phase2_exit -ne 0 ]; then \
			echo "⚠️  Phase 2 — Backups-module tests had failures (exit $$phase2_exit) — coverage data still captured"; \
			record_failure "$$phase2_exit"; \
		fi; \
		if [ ! -f "$$phase2_file" ]; then \
			echo "❌ Phase 2 — Expected coverage data file is missing: $$phase2_file"; \
			if [ $$phase2_exit -eq 0 ]; then record_failure 1; fi; \
			if [ "$$backups_required" = true ]; then required_backups_missing=true; fi; \
		fi; \
	else \
		if [ -n "$(REQUIRE_BACKUPS_COVERAGE)" ]; then \
			echo "❌ REQUIRE_BACKUPS_COVERAGE is set but PostgreSQL or DR toolchain is not available."; \
			echo "   Ensure PostgreSQL 18 is running on localhost:5432 and the QS_BACKUPS_DB_*"; \
			echo "   environment variables point to a valid LOGIN CREATEDB NOINHERIT NOBYPASSRLS role."; \
			record_failure 1; \
			required_backups_missing=true; \
		fi; \
		echo "ℹ️ Phase 2 — PostgreSQL or DR toolchain not available — skipping module coverage (backups)"; \
	fi; \
	if [ "$$phase1_missing" = false ] && [ "$$required_backups_missing" = false ]; then \
		echo "📊 Phase 3 — Combining isolated coverage data and generating report (threshold deferred to Phase 4)..."; \
		set +e; \
		$(PYTHON) -m coverage combine --data-file="$$combined_file" "$$coverage_dir"; \
		combine_exit=$$?; \
		set -e; \
		if [ $$combine_exit -ne 0 ]; then \
			echo "⚠️  Phase 3 — Coverage combine failed (exit $$combine_exit)"; \
			record_failure "$$combine_exit"; \
		elif [ ! -f "$$combined_file" ]; then \
			echo "❌ Phase 3 — Coverage combine did not create the expected data file: $$combined_file"; \
			record_failure 1; \
		else \
			set +e; \
			$(PYTHON) -m coverage html --data-file="$$combined_file"; \
			html_exit=$$?; \
			$(PYTHON) -m coverage report --data-file="$$combined_file" --fail-under=0; \
			report_exit=$$?; \
			$(PYTHON) -m coverage json --data-file="$$combined_file"; \
			json_exit=$$?; \
			set -e; \
			if [ $$html_exit -ne 0 ]; then \
				echo "⚠️  Phase 3 — Coverage HTML report failed (exit $$html_exit)"; \
				record_failure "$$html_exit"; \
			fi; \
			if [ $$report_exit -ne 0 ]; then \
				echo "⚠️  Phase 3 — Coverage report failed (exit $$report_exit)"; \
				record_failure "$$report_exit"; \
			fi; \
			if [ $$json_exit -ne 0 ] || [ ! -f coverage.json ]; then \
				if [ $$json_exit -ne 0 ]; then \
					echo "⚠️  Phase 3 — Coverage JSON report failed (exit $$json_exit)"; \
				else \
					echo "❌ Phase 3 — Coverage JSON report did not create coverage.json"; \
				fi; \
				if [ $$json_exit -ne 0 ]; then record_failure "$$json_exit"; else record_failure 1; fi; \
			else \
				echo "🔍 Phase 4 — Checking coverage policy (90% equal-weight package mean, 80% per-file)..."; \
				set +e; \
				$(PYTHON) scripts/check_coverage_policy.py coverage.json; \
				policy_exit=$$?; \
				set -e; \
				if [ $$policy_exit -ne 0 ]; then \
					echo "⚠️  Phase 4 — Coverage policy check failed (exit $$policy_exit)"; \
					record_failure "$$policy_exit"; \
				fi; \
			fi; \
		fi; \
	else \
		echo "⚠️  Phase 3 — Skipping coverage combine because required coverage inputs are missing"; \
	fi; \
	if [ -f coverage.json ]; then echo "📊 Coverage report: htmlcov/index.html"; fi; \
	exit $$overall_exit

# Run the coverage policy helper test suite independently.
# This verifies the helper's arithmetic, validation, and fail-closed
# behaviour before the main test-cov pipeline uses it.
test-cov-policy:
	@$(PYTHON) -m pytest scripts/test_ci_coverage_policy.py -q --tb=short

# Run the worker-pool and concurrent E2E lane harness tests.
# These are fast, self-contained, and do not require PostgreSQL or Docker.
test-integration-worker-pool:
	@$(PYTHON) -m pytest scripts/test_integration_worker_pool.py scripts/test_e2e_parallel.py -q --tb=short

# Run TP1 local-CI fan-out, signal-lifecycle, and serial/post-static tests.
# The test fixture replaces make/poetry, so this target is safe as a prerequisite
# of ci and cannot recurse through the real ci target.
test-ci-local-parallel:
	@$(PYTHON) -m pytest scripts/test_ci_local_parallel.py -q --tb=short

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

# Build wheels, install into throwaway venv outside source tree, and run
# non-mutating CLI smoke tests (SA110 installed-artifact smoke gate).
# Must run from the repository root with Poetry and a compatible Python.
smoke-install:
	@scripts/smoke_install.sh

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

# Auto-format and auto-fix lint across the active sections (write mode).
fix: format lint-fix
	@echo "✨ Formatted and lint-fixed!"

# Fast pre-commit gate: lint + typecheck + UNIT tests + repository gates.
# (Integration/E2E live in `make ci` / `make ci-e2e`.)
#
#   make check           - full output, respects section flags (-- --core, MODULE=…)
#   make check QUIET=1    - quiet on success for LLM/agent use (flat SRC/TEST dirs,
#                           ruff/mypy --quiet, pytest output shown only on failure)
check:
	@set -e; \
	if [ -n "$(QUIET)" ]; then \
		$(PYTHON) -m ruff check $(SRC_DIRS) --quiet; \
		$(PYTHON) -m ruff format --check $(SRC_DIRS) --quiet; \
		$(PYTHON) -m mypy $(SRC_DIRS) --show-error-codes > mypy_log.txt 2>&1 || { cat mypy_log.txt; rm -f mypy_log.txt; exit 1; }; \
		rm -f mypy_log.txt; \
		$(PYTHON) -m pytest $(TEST_DIRS) -q --tb=short $(PYTEST_XDIST_ARGS) > pytest_log.txt 2>&1 || { cat pytest_log.txt; rm -f pytest_log.txt; exit 1; }; \
		rm -f pytest_log.txt; \
	else \
		$(MAKE) lint typecheck SECTIONS="$(ACTIVE_SECTIONS)" MODULE="$(MODULE)"; \
		$(MAKE) test-unit SECTIONS="$(filter-out modules,$(ACTIVE_SECTIONS))" MODULE="$(MODULE)"; \
	fi; \
	$(MAKE) check-core-compat check-module-core-imports check-manifest-sync check-org-context-primitives check-csrf-exempt
	@if [ -z "$(QUIET)" ]; then \
		if command -v node >/dev/null 2>&1 && command -v pnpm >/dev/null 2>&1; then \
			echo "📦 Linting rendered frontend..."; \
			$(MAKE) lint-frontend; \
		else \
			echo "ℹ️ Skipping rendered frontend lint (node and pnpm are required)."; \
		fi; \
		echo ""; \
		echo "🎉 All checks passed!"; \
	fi

# Full code quality analysis: dead code (vulture), complexity (radon), duplication (pylint)
# Reports saved to .quickscale/quality_report.{json,md}
quality:
	@scripts/check_quality.sh

# Run primary local development checks (lint + typecheck + unit tests; integration when PostgreSQL available)
ci: test-ci-local-parallel
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
