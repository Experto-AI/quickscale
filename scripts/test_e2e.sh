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
#   --verbose         Verbose pytest output
#   --help            Show this help message
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
HEADED=""
CLEANUP=true
VERBOSE=""
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
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --headed          Run Playwright in headed mode (show browser)"
            echo "  --no-cleanup      Don't cleanup Docker containers (for debugging)"
            echo "  --verbose, -v     Verbose pytest output"
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

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   QuickScale E2E Test Runner           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the project root
if [ ! -d "$CORE_DIR" ]; then
    echo -e "${RED}Error: quickscale_core directory not found${NC}"
    echo "Please run this script from the project root or scripts directory"
    exit 1
fi

# Always run from project root using centralized poetry environment
cd "$PROJECT_ROOT"

# Cleanup function
cleanup() {
    if [ "$CLEANUP" = true ]; then
        echo -e "\n${YELLOW}Cleaning up Docker containers (pytest-docker handles this)...${NC}"
        # pytest-docker automatically cleans up containers, but we'll ensure any orphaned containers are removed
        cd "$CORE_DIR/tests"
        docker compose -f docker-compose.test.yml down -v 2>/dev/null || true

        # Cleanup any test containers that might be lingering
        docker ps -a | grep -E '(test|e2e_cli_test).*_(db|web|postgres)' | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true

        # Stop containers on test ports
        docker ps | grep -E ':(8000|5432)->' | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true
        docker ps -a | grep -E ':(8000|5432)->' | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true

        echo -e "${GREEN}✓ Cleanup complete${NC}"

        # Return to project root
        cd "$PROJECT_ROOT"
    else
        echo -e "\n${YELLOW}Skipping cleanup (--no-cleanup specified)${NC}"
        echo -e "${BLUE}To manually cleanup, run:${NC}"
        echo "  docker ps -a | grep pytest | awk '{print \$1}' | xargs docker rm -f"
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

# Step 1b: Pre-cleanup - stop any existing test containers to free ports
echo -e "${BLUE}[1b/5] Cleaning up any orphaned test containers...${NC}"
# Stop and remove any pytest containers that might be lingering from previous runs
docker ps -a --filter "name=pytest" --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true
# Stop containers on commonly used test ports
docker ps --format "{{.ID}} {{.Ports}}" | grep -E ':(5432|5433|8000)->' | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true
docker ps -a --format "{{.ID}} {{.Ports}}" | grep -E ':(5432|5433|8000)->' | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true
# Also cleanup test containers by name pattern
docker ps -a | grep -E '(test|e2e_cli_test).*_(db|web|postgres)' | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true
# Wait briefly for ports to be released
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
PYTEST_CMD="PYTHONPATH=\"$CORE_DIR:$CORE_DIR/src\" poetry run pytest $CORE_DIR/tests/ -m e2e --rootdir=$CORE_DIR"

if [ -n "$VERBOSE" ]; then
    PYTEST_CMD="$PYTEST_CMD $VERBOSE"
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
# Stop any containers from core E2E tests (pytest-docker containers)
docker ps -a | grep -E 'test.*_(db|web|postgres)' | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true
# Also stop any containers on ports 8000 and 5432
docker ps | grep -E ':(8000|5432)->' | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true
docker ps -a | grep -E ':(8000|5432)->' | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true
# Wait for ports to be released
sleep 2
echo -e "${GREEN}✓ Core test containers cleaned up${NC}"
echo ""

# Step 4: Run CLI E2E tests
echo -e "${BLUE}[4/4] Running CLI E2E tests...${NC}"
echo -e "${YELLOW}Testing development commands with real Docker containers...${NC}"
echo ""

# Build CLI pytest command - run from root with PYTHONPATH for centralized venv
CLI_PYTEST_CMD="PYTHONPATH=\"$CLI_DIR:$CLI_DIR/src\" poetry run pytest $CLI_DIR/tests/ -m e2e --rootdir=$CLI_DIR"

if [ -n "$VERBOSE" ]; then
    CLI_PYTEST_CMD="$CLI_PYTEST_CMD $VERBOSE"
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
    echo "  • Run with --verbose for detailed output"
    echo "  • Run with --no-cleanup to inspect containers"
    echo "  • Check screenshots in failed test output"
    echo "  • Ensure Docker is running and accessible"
    exit 1
fi
