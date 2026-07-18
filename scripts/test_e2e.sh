#!/usr/bin/env bash

#
# test_e2e.sh - Run full E2E tests locally
#
# This script sets up the complete E2E testing environment:
# - Starts PostgreSQL container
# - Installs Playwright browsers
# - Runs comprehensive E2E tests
# - Cleans up containers afterward
#
# Usage:
#   ./scripts/test_e2e.sh [OPTIONS]
#
# Options:
#   --headed          Run Playwright in headed mode (show browser)
#   --no-cleanup      Don't cleanup Docker containers (for debugging)
#   --full            Show full pytest output (per-file lines)
#   --verbose         Alias for --full
#   --help            Show this help message
#

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
HEADED=""
CLEANUP=true
SHOW_FULL_OUTPUT=false
PYTEST_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --headed)
            HEADED="--headed"
            shift
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --full|--verbose|-v)
            SHOW_FULL_OUTPUT=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --headed          Run Playwright in headed mode (show browser)"
            echo "  --no-cleanup      Don't cleanup Docker containers (for debugging)"
            echo "  --full            Show full pytest output (per-file lines)"
            echo "  --verbose, -v     Alias for --full"
            echo "  --help, -h        Show this help message"
            exit 0
            ;;
        *)
            PYTEST_ARGS="$PYTEST_ARGS $1"
            shift
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CORE_DIR="$PROJECT_ROOT/quickscale_core"
CLI_DIR="$PROJECT_ROOT/quickscale_cli"

# Every invocation gets an isolated Docker scope.  The process suffix keeps
# two otherwise-identical lanes independent, while QS_E2E_LANE makes the
# scope recognizable in concurrent worker logs and docker ps output.
sanitize_scope() {
    local value="$1"
    value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]_' '_')"
    value="${value#-}"
    value="${value%-}"
    printf '%s' "${value:-lane}"
}

E2E_LANE="$(sanitize_scope "${QS_E2E_LANE:-${QS_E2E_WORKER:-lane}}")"
E2E_CONTAINER_PREFIX_BASE="$(sanitize_scope "${QS_E2E_CONTAINER_PREFIX:-qs-e2e-${E2E_LANE}}")"
E2E_CONTAINER_PREFIX_BASE="${E2E_CONTAINER_PREFIX_BASE:0:35}"
E2E_CONTAINER_PREFIX="$(sanitize_scope "${E2E_CONTAINER_PREFIX_BASE}-${BASHPID}")"
# Docker Compose project names are limited to a portable, shell-safe subset;
# keep the generated scope short enough for container-name diagnostics too.
E2E_CONTAINER_PREFIX="${E2E_CONTAINER_PREFIX:0:50}"
if [ -n "${QS_E2E_COMPOSE_PROJECT_NAME:-}" ]; then
    E2E_COMPOSE_PROJECT_BASE="$(sanitize_scope "$QS_E2E_COMPOSE_PROJECT_NAME")"
    E2E_COMPOSE_PROJECT_BASE="${E2E_COMPOSE_PROJECT_BASE:0:35}"
    E2E_COMPOSE_PROJECT_NAME="$(sanitize_scope "${E2E_COMPOSE_PROJECT_BASE}-${BASHPID}")"
else
    E2E_COMPOSE_PROJECT_NAME="$E2E_CONTAINER_PREFIX"
fi
E2E_COMPOSE_PROJECT_NAME="${E2E_COMPOSE_PROJECT_NAME:0:50}"

find_free_port() {
    python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

if [ -n "${QS_E2E_APP_PORT:-}" ]; then
    case "$QS_E2E_APP_PORT" in
        *[!0-9]*|"")
            echo -e "${RED}Error: QS_E2E_APP_PORT must be a numeric host port${NC}"
            exit 1
            ;;
    esac
    E2E_APP_PORT="$QS_E2E_APP_PORT"
else
    E2E_APP_PORT="$(find_free_port)"
fi

if [ "$E2E_APP_PORT" -lt 1 ] || [ "$E2E_APP_PORT" -gt 65535 ]; then
    echo -e "${RED}Error: QS_E2E_APP_PORT must be between 1 and 65535${NC}"
    exit 1
fi

export QS_E2E_LANE="$E2E_LANE"
export QS_E2E_CONTAINER_PREFIX="$E2E_CONTAINER_PREFIX"
export QS_E2E_COMPOSE_PROJECT_NAME="$E2E_COMPOSE_PROJECT_NAME"
export QS_E2E_APP_PORT="$E2E_APP_PORT"
export COMPOSE_PROJECT_NAME="$E2E_COMPOSE_PROJECT_NAME"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   QuickScale E2E Test Runner           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
if [ "$SHOW_FULL_OUTPUT" = true ]; then
    echo "Output mode: full"
else
    echo "Output mode: dots"
fi
echo "Lane: $E2E_LANE"
echo "App host port: $E2E_APP_PORT"
echo "Docker scope: $E2E_COMPOSE_PROJECT_NAME"
echo ""

# Check if we're in the project root
if [ ! -d "$CORE_DIR" ]; then
    echo -e "${RED}Error: quickscale_core directory not found${NC}"
    echo "Please run this script from the project root or scripts directory"
    exit 1
fi

# Always run from project root using centralized poetry environment
cd "$PROJECT_ROOT"

cleanup_scoped_containers() {
    local container_ids

    # Compose labels cover pytest-docker and generated-project services.  The
    # name filter also catches generated services with explicit container_name
    # values, without ever touching another lane's containers.
    container_ids="$(docker ps -aq --filter "label=com.docker.compose.project=$E2E_COMPOSE_PROJECT_NAME" 2>/dev/null || true)"
    if [ -n "$container_ids" ]; then
        printf '%s\n' "$container_ids" | xargs -r docker rm -f 2>/dev/null || true
    fi
    container_ids="$(docker ps -aq --filter "name=$E2E_CONTAINER_PREFIX" 2>/dev/null || true)"
    if [ -n "$container_ids" ]; then
        printf '%s\n' "$container_ids" | xargs -r docker rm -f 2>/dev/null || true
    fi
}

# Cleanup function
cleanup() {
    if [ "$CLEANUP" = true ]; then
        echo -e "\n${YELLOW}Cleaning up Docker containers (pytest-docker handles this)...${NC}"
        # Use the lane's Compose project and container prefix only.
        (cd "$CORE_DIR/tests" && docker compose -f docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true)
        cleanup_scoped_containers

        echo -e "${GREEN}✓ Cleanup complete${NC}"
    else
        echo -e "\n${YELLOW}Skipping cleanup (--no-cleanup specified)${NC}"
        echo -e "${BLUE}To manually cleanup this lane, run:${NC}"
        echo "  docker ps -aq --filter label=com.docker.compose.project=$E2E_COMPOSE_PROJECT_NAME | xargs -r docker rm -f"
        echo "  docker ps -aq --filter name=$E2E_CONTAINER_PREFIX | xargs -r docker rm -f"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Step 1: Check Docker is running
echo -e "${BLUE}[1/5] Checking Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Step 1b: Pre-cleanup - remove only this lane's stale containers
echo -e "${BLUE}[1b/5] Cleaning up any orphaned test containers...${NC}"
cleanup_scoped_containers
# Keep the existing short stabilization delay for single-lane teardown.
sleep 1
echo -e "${GREEN}✓ Pre-cleanup complete${NC}"
echo ""

# Step 2: Install Playwright browsers
echo -e "${BLUE}[2/4] Installing Playwright browsers...${NC}"
echo -e "${YELLOW}Note: This may prompt for sudo password to install system dependencies${NC}"
if ! poetry run playwright install chromium; then
    echo -e "${YELLOW}Warning: Playwright browser installation had issues${NC}"
    echo "Continuing anyway..."
fi
echo -e "${GREEN}✓ Playwright browsers ready${NC}"
echo ""

# Step 3: Run Core E2E tests (pytest-docker will manage PostgreSQL)
echo -e "${BLUE}[3/4] Running Core E2E tests...${NC}"
echo -e "${YELLOW}Note: pytest-docker will automatically start PostgreSQL${NC}"
echo -e "${YELLOW}This may take some minutes (includes installing project dependencies)...${NC}"
echo ""

# Build pytest command - run from root with PYTHONPATH for centralized venv
# Using --rootdir to ensure pytest finds the correct conftest.py
# Clear addopts to disable coverage thresholds (E2E tests don't need full coverage)
PYTEST_CMD="PYTHONPATH=\"$CORE_DIR:$CORE_DIR/src\" poetry run pytest $CORE_DIR/tests/ -m e2e --rootdir=$CORE_DIR -o \"addopts=\" --tb=long -ra"

if [ "$SHOW_FULL_OUTPUT" = false ]; then
    PYTEST_CMD="$PYTEST_CMD -q"
fi

if [ -n "$HEADED" ]; then
    PYTEST_CMD="$PYTEST_CMD $HEADED"
fi

if [ -n "$PYTEST_ARGS" ]; then
    PYTEST_CMD="$PYTEST_CMD $PYTEST_ARGS"
fi

# Run Core E2E tests
echo -e "${BLUE}Command: $PYTEST_CMD${NC}"
echo ""

CORE_TESTS_PASSED=false
if eval "$PYTEST_CMD"; then
    echo -e "${GREEN}✓ Core E2E tests passed${NC}"
    CORE_TESTS_PASSED=true
else
    echo -e "${RED}✗ Core E2E tests failed${NC}"
fi

echo ""

# Cleanup core test containers before running CLI tests
echo -e "${BLUE}Cleaning up Core E2E test containers...${NC}"
# Remove only the current lane's Compose services and explicit-name services.
cleanup_scoped_containers
# Wait for ports to be released
sleep 2
echo -e "${GREEN}✓ Core test containers cleaned up${NC}"
echo ""

# Step 4: Run CLI E2E tests
echo -e "${BLUE}[4/4] Running CLI E2E tests...${NC}"
echo -e "${YELLOW}Testing development commands with real Docker containers...${NC}"
echo ""

# Build CLI pytest command - run from root with PYTHONPATH for centralized venv
# Clear addopts to disable coverage thresholds (E2E tests don't need full coverage)
CLI_PYTEST_CMD="PYTHONPATH=\"$CLI_DIR:$CLI_DIR/src\" poetry run pytest $CLI_DIR/tests/ -m e2e --rootdir=$CLI_DIR -o \"addopts=\" --tb=long -ra"

if [ "$SHOW_FULL_OUTPUT" = false ]; then
    CLI_PYTEST_CMD="$CLI_PYTEST_CMD -q"
fi

if [ -n "$PYTEST_ARGS" ]; then
    CLI_PYTEST_CMD="$CLI_PYTEST_CMD $PYTEST_ARGS"
fi

echo -e "${BLUE}Command: $CLI_PYTEST_CMD${NC}"
echo ""

CLI_TESTS_PASSED=false
if eval "$CLI_PYTEST_CMD"; then
    echo -e "${GREEN}✓ CLI E2E tests passed${NC}"
    CLI_TESTS_PASSED=true
else
    echo -e "${RED}✗ CLI E2E tests failed${NC}"
fi

echo ""

# Final results
if [ "$CORE_TESTS_PASSED" = true ] && [ "$CLI_TESTS_PASSED" = true ]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✓ All E2E Tests Passed!              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ✗ E2E Tests Failed                   ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Debugging tips:${NC}"
    echo "  • Run with --headed to see browser actions (Core tests)"
    echo "  • Run with --full for detailed output"
    echo "  • Run with --no-cleanup to inspect containers"
    echo "  • Check screenshots in failed test output"
    echo "  • Ensure Docker is running and accessible"
    exit 1
fi
