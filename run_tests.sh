#!/bin/bash
# Script to run tests with proper settings

set -eo pipefail

# Set environment variables for testing
export QUICKSCALE_TEST_MODE=1
export QUICKSCALE_NO_ANALYTICS=1

# Signal handler for proper cleanup on CTRL+C
cleanup_and_exit() {
    echo -e "\n\033[33mTest execution interrupted. Cleaning up...\033[0m"
    # Check for and cleanup test containers
    if docker ps -a | grep -E "test_project|real_test_project" > /dev/null; then
        echo "Stopping and removing test containers..."
        docker ps -a | grep -E "test_project|real_test_project" | awk '{print $1}' | xargs -r docker stop > /dev/null 2>&1 || true
        docker ps -a | grep -E "test_project|real_test_project" | awk '{print $1}' | xargs -r docker rm > /dev/null 2>&1 || true
    fi
    echo "Cleanup complete. Exiting."
    exit 1
}

# Set up trap for SIGINT (CTRL+C)
trap cleanup_and_exit SIGINT

# Functions for checking Docker
check_docker() {
    if [[ $QUIET -eq 0 ]]; then
        echo "Checking Docker availability..."
    fi
    
    # Check if docker command exists
    if ! command -v docker &> /dev/null; then
        echo -e "\033[31mERROR: Docker command not found!\033[0m"
        echo -e "\033[31mPlease install Docker before running these tests.\033[0m"
        echo -e "\033[31mTests will continue but may fail due to missing Docker dependency.\033[0m"
        return 1
    fi
    
    # Check if docker daemon is running
    if ! docker info &> /dev/null; then
        echo -e "\033[31mERROR: Docker daemon is not running!\033[0m"
        echo -e "\033[31mPlease start Docker service with one of these commands:\033[0m"
        echo -e "\033[31m  - sudo systemctl start docker    # for systemd systems\033[0m"
        echo -e "\033[31m  - sudo service docker start      # for init.d systems\033[0m"
        echo -e "\033[31mTests will continue but may fail due to Docker not running.\033[0m"
        return 1
    fi
    
    # Check Docker Compose availability and version
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | grep -oE "[0-9]+\.[0-9]+\.[0-9]+")
        if [[ $QUIET -eq 0 ]]; then
            echo "Using Docker Compose v1: $COMPOSE_VERSION"
        fi
        # Export the compose command for use in tests
        export DOCKER_COMPOSE_COMMAND="docker-compose"
    else
        # Check if docker compose (v2) is available
        if docker compose version &> /dev/null; then
            COMPOSE_VERSION=$(docker compose version | grep -oE "[0-9]+\.[0-9]+\.[0-9]+" | head -1)
            if [[ $QUIET -eq 0 ]]; then
                echo "Using Docker Compose v2: $COMPOSE_VERSION"
            fi
            # Export the compose command for use in tests
            export DOCKER_COMPOSE_COMMAND="docker compose"
        else
            echo -e "\033[31mERROR: Docker Compose not found!\033[0m"
            echo -e "\033[31mPlease install Docker Compose before running these tests.\033[0m"
            echo -e "\033[31mTests will continue but may fail due to missing Docker Compose dependency.\033[0m"
            return 1
        fi
    fi
    
    # Check Docker disk space
    DOCKER_INFO=$(docker info 2>/dev/null)
    if echo "$DOCKER_INFO" | grep -E "WARNING.*[lL]ow.*(space|memory)" > /dev/null; then
        echo -e "\033[33mWARNING: Docker is reporting low resources (disk space or memory).\033[0m"
        echo -e "\033[33mThis could cause test failures. Consider freeing up resources.\033[0m"
    fi
    
    if [[ $QUIET -eq 0 ]]; then
        echo "Docker is available and running."
    fi
    return 0
}

# Function to verify health of containers
verify_container_health() {
    if [[ $QUIET -eq 0 ]]; then
        echo "Verifying container health..."
    fi
    
    # Check if any containers exist and if they are healthy
    CONTAINERS=$(docker ps -a --format "{{.Names}}" | grep -E "test_project|real_test_project")
    
    if [[ -z "$CONTAINERS" ]]; then
        if [[ $QUIET -eq 0 ]]; then
            echo "No test containers found to check health."
        fi
        return 0
    fi
    
    UNHEALTHY=0
    
    for CONTAINER in $CONTAINERS; do
        if [[ $QUIET -eq 0 ]]; then
            echo "Checking container: $CONTAINER"
        fi
        
        # Check container status
        STATUS=$(docker inspect --format="{{.State.Status}}" "$CONTAINER" 2>/dev/null)
        
        if [[ "$STATUS" != "running" ]]; then
            if [[ $QUIET -eq 0 ]]; then
                echo -e "\033[33mContainer $CONTAINER is not running (status: $STATUS).\033[0m"
            fi
            UNHEALTHY=1
            continue
        fi
        
        # Check if container has a health check
        if docker inspect --format="{{.State.Health}}" "$CONTAINER" 2>/dev/null | grep -q "Health"; then
            HEALTH=$(docker inspect --format="{{.State.Health.Status}}" "$CONTAINER" 2>/dev/null)
            
            if [[ "$HEALTH" != "healthy" ]]; then
                if [[ $QUIET -eq 0 ]]; then
                    echo -e "\033[33mContainer $CONTAINER health check: $HEALTH\033[0m"
                    docker inspect --format="{{.State.Health.Log}}" "$CONTAINER" | grep -v '\[\]' || true
                fi
                UNHEALTHY=1
            else
                if [[ $QUIET -eq 0 ]]; then
                    echo -e "\033[32mContainer $CONTAINER is healthy.\033[0m"
                fi
            fi
        else
            if [[ $QUIET -eq 0 ]]; then
                echo "Container $CONTAINER has no health check defined."
            fi
        fi
    done
    
    return $UNHEALTHY
}

# Function to free up Docker resources
free_docker_resources() {
    if [[ $QUIET -eq 0 ]]; then
        echo "Freeing up Docker resources..."
    fi
    
    # Remove unused containers
    if [[ $QUIET -eq 0 ]]; then
        echo "Removing unused containers..."
    fi
    docker container prune -f > /dev/null 2>&1
    
    # Remove unused images
    if [[ $QUIET -eq 0 ]]; then
        echo "Removing unused images..."
    fi
    docker image prune -f > /dev/null 2>&1
    
    # Remove unused volumes
    if [[ $QUIET -eq 0 ]]; then
        echo "Removing unused volumes..."
    fi
    docker volume prune -f > /dev/null 2>&1
    
    # Remove unused networks
    if [[ $QUIET -eq 0 ]]; then
        echo "Removing unused networks..."
    fi
    docker network prune -f > /dev/null 2>&1
    
    if [[ $QUIET -eq 0 ]]; then
        echo "Docker resources have been freed up."
    fi
}

# Function to clean up existing Docker containers
cleanup_test_containers() {
    if [[ $QUIET -eq 0 ]]; then
        echo "Checking for existing test containers..."
    fi
    
    # Check if any test containers are running
    if docker ps -a | grep -E "test_project|real_test_project" > /dev/null; then
        if [[ $QUIET -eq 0 ]]; then
            echo -e "\033[33mFound existing test containers. Cleaning up before running tests...\033[0m"
        fi
        
        # Stop and remove all containers matching our test patterns
        docker ps -a | grep -E "test_project|real_test_project" | awk '{print $1}' | xargs -r docker stop > /dev/null 2>&1 || true
        docker ps -a | grep -E "test_project|real_test_project" | awk '{print $1}' | xargs -r docker rm > /dev/null 2>&1 || true
        
        if [[ $QUIET -eq 0 ]]; then
            echo "Test containers have been stopped and removed."
        fi
    else
        if [[ $QUIET -eq 0 ]]; then
            echo "No existing test containers found."
        fi
    fi
    
    # Check for any dangling or unused volumes that could cause issues
    if docker volume ls -q -f dangling=true | grep -q .; then
        if [[ $QUIET -eq 0 ]]; then
            echo -e "\033[33mFound dangling Docker volumes. Cleaning up...\033[0m"
        fi
        
        docker volume prune -f > /dev/null 2>&1 || true
        
        if [[ $QUIET -eq 0 ]]; then
            echo "Dangling volumes have been removed."
        fi
    fi
    
    # Check for and remove any test networks
    if docker network ls | grep -E "test_project|real_test_project" > /dev/null; then
        if [[ $QUIET -eq 0 ]]; then
            echo -e "\033[33mFound test networks. Cleaning up...\033[0m"
        fi
        
        docker network ls | grep -E "test_project|real_test_project" | awk '{print $2}' | xargs -r docker network rm > /dev/null 2>&1 || true
        
        if [[ $QUIET -eq 0 ]]; then
            echo "Test networks have been removed."
        fi
    fi
}

# Parse arguments
COVERAGE=0
INTEGRATION=1
UNIT=1
RUN_UNIT=0
RUN_INTEGRATION=0
RUN_E2E=0
RUN_DJANGO_COMPONENTS=0
QUIET=0
VERBOSE=0
EXITFIRST=0
FAILURES_ONLY=0

print_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -c, --coverage     Run tests with coverage report"
    echo "  -u, --unit         Run only unit tests (fast, no external dependencies)"
    echo "  -i, --integration  Run only integration tests (medium speed, some external dependencies)"
    echo "  -e, --e2e          Run only end-to-end tests (slow, full system tests with Docker)"
    echo "  -d, --django       Run only Django component tests (models, views, utils)"
    echo "  -q, --quiet        Run tests in quiet mode (less verbose output)"
    echo "  -v, --verbose      Run tests in verbose mode (more detailed output)"
    echo "  -x, --exitfirst    Exit on first test failure"
    echo "  -f, --failures-only    Show only failed tests and warnings (LLM-optimized: suppresses passed tests for minimal context pollution)"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -u              # Run only unit tests"
    echo "  $0 -e              # Run only end-to-end tests"
    echo "  $0 -d              # Run only Django component tests"
    echo "  $0 -u -i           # Run both unit and integration tests"
    echo "  $0 -u -i -e        # Run all tests (unit, integration, and end-to-end)"
    echo "  $0 -u -i -d        # Run unit, integration and Django component tests"
    echo "  $0 -c              # Run all tests with coverage"
    echo "  $0 -q              # Run tests in quiet mode"
    echo "  $0 -v              # Run tests in verbose mode"
    echo "  $0 -x              # Stop on first test failure"
    echo "  $0 --failures-only # Show only failed tests and warnings (LLM-optimized output)"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--coverage)
            COVERAGE=1
            shift
            ;;
        -u|--unit)
            RUN_UNIT=1
            shift
            ;;
        -i|--integration)
            RUN_INTEGRATION=1
            shift
            ;;
        -e|--e2e)
            RUN_E2E=1
            shift
            ;;
        -d|--django)
            RUN_DJANGO_COMPONENTS=1
            shift
            ;;
        -q|--quiet)
            QUIET=1
            shift
            ;;
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -x|--exitfirst)
            EXITFIRST=1
            shift
            ;;
        -f|--failures-only)
            FAILURES_ONLY=1
            shift
            ;;
        -h|--help)
            print_usage
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            ;;
    esac
done

# Add test selection paths
test_paths=()
SELECTED_TESTS=0
if [[ $RUN_UNIT -eq 1 || $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 || $RUN_DJANGO_COMPONENTS -eq 1 ]]; then
    SELECTED_TESTS=1
fi

# If running e2e tests, set specific env variables
if [[ $RUN_E2E -eq 1 || ($SELECTED_TESTS -eq 0 && $RUN_INTEGRATION -eq 0 && $RUN_UNIT -eq 0 && $RUN_DJANGO_COMPONENTS -eq 0) ]]; then
    if [[ $QUIET -eq 0 ]]; then
        echo "Setting up environment for E2E tests..."
    fi
    
    # Set environment variables for E2E tests
    export PYTHONMALLOC=malloc
    export QUICKSCALE_TEST_BUILD=1
    export QUICKSCALE_SKIP_MIGRATIONS=1
    export QUICKSCALE_E2E_TEST=1
    export COMPOSE_HTTP_TIMEOUT=180
    
    # Extend Docker timeouts for better test stability
    export DOCKER_CLIENT_TIMEOUT=180
    
    if [[ $QUIET -eq 0 ]]; then
        echo "E2E test environment configured"
    fi
fi

# Clean up existing Docker containers if we're running integration or E2E tests
if [[ $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 || $SELECTED_TESTS -eq 0 ]]; then
    cleanup_test_containers
fi

# Build test command
CMD="python -m pytest"

# Add quiet mode if requested
if [[ $QUIET -eq 1 ]]; then
    # More comprehensive quiet flags: 
    # -q for less verbose
    # --no-header to hide pytest header
    # --no-summary to hide the summary
    # -o log_cli=false to suppress logging
    CMD="$CMD -q --no-header --no-summary -o log_cli=false"
fi

# Add verbose mode if requested (only if not in quiet mode)
if [[ $VERBOSE -eq 1 && $QUIET -eq 0 ]]; then
    # Extensive logging configuration for pytest:
    # -vv: very verbose output
    # --log-cli-level=DEBUG: show DEBUG level logs
    # -s: capture and show all output (including print statements)
    # --capture=tee-sys: capture and display both stdout and stderr
    CMD="$CMD -vv -s --log-cli-level=DEBUG --capture=tee-sys"
fi

# Add coverage if requested
if [[ $COVERAGE -eq 1 ]]; then
    CMD="$CMD --cov=quickscale --cov-report=term --cov-report=html"
fi

# Add exitfirst option if requested
if [[ $EXITFIRST -eq 1 ]]; then
    CMD="$CMD --exitfirst"
fi

# Configure output based on flags
if [[ $FAILURES_ONLY -eq 1 ]]; then
    # LLM-optimized failures-only mode: show ONLY failures and warnings, suppress passed tests
    # This minimizes context pollution for LLM analysis while preserving critical error information
    if [[ $EXITFIRST -eq 1 ]]; then
        # Single failure mode: stop on first failure for focused debugging, do not shows warnings
        CMD="$CMD --tb=short -q --disable-warnings -o log_cli=false"
        # Note: --exitfirst is already added above, no need to duplicate
    else
        # Multiple failures mode: show up to 5 failures for broader context and all warnings
        CMD="$CMD --tb=short -q -o log_cli=false --maxfail=5"
    fi
    
    # Add a note about LLM optimization
    if [[ $QUIET -eq 0 ]]; then
        if [[ $EXITFIRST -eq 1 ]]; then
            echo "Failures-only mode: Stopping on first failure for focused LLM analysis."
        else
            echo "Failures-only mode: Showing up to 5 failures for LLM context efficiency. Combine with -x for single-failure mode."
        fi
    fi
else
    # Standard mode: show failed tests with moderate detail
    CMD="$CMD -rf --tb=short"
fi

if [[ $SELECTED_TESTS -eq 1 ]]; then
    # User selected specific tests
    if [[ $RUN_UNIT -eq 1 ]]; then
        test_paths+=("tests/unit/")
    fi
    if [[ $RUN_INTEGRATION -eq 1 ]]; then
        test_paths+=("tests/integration/")
    fi
    if [[ $RUN_E2E -eq 1 ]]; then
        test_paths+=("tests/e2e/")
    fi
    if [[ $RUN_DJANGO_COMPONENTS -eq 1 ]]; then
        test_paths+=("tests/unit/django_components/" "tests/integration/django_apps/" "tests/e2e/django_workflows/")
    fi
else
    # Default: run unit, integration, and e2e tests (template validation is optional)
    test_paths+=("tests/unit/" "tests/integration/" "tests/e2e/")
fi

CMD="$CMD ${test_paths[@]}"

# Add pytest options to fix common issues (unless in failures-only mode)
if [[ $FAILURES_ONLY -eq 0 ]]; then
    CMD="$CMD --no-header --tb=native"
fi

# Show the command
if [[ $QUIET -eq 0 ]]; then
    echo "Running: $CMD"
fi

# Run the tests
set +e  # Allow script to continue if tests fail

$CMD
EXIT_CODE=$?

# Check container health if e2e tests failed
if [[ $EXIT_CODE -ne 0 && ($RUN_E2E -eq 1 || $SELECTED_TESTS -eq 0) && $QUIET -eq 0 ]]; then
    echo "Checking container health after test failure..."
    verify_container_health
fi

set -e

# If coverage was generated, show the report location
if [[ $COVERAGE -eq 1 && $QUIET -eq 0 ]]; then
    echo "Coverage report generated in htmlcov/index.html"
fi

# Print a helpful message for E2E test failures
if [[ $EXIT_CODE -ne 0 && ($RUN_E2E -eq 1 || $SELECTED_TESTS -eq 0) ]]; then
    echo -e "\033[33m"
    echo "===================================================================="
    echo "   E2E Test Failure - Troubleshooting Tips"
    echo "===================================================================="
    echo " Try the following for more reliable tests:"
    echo "  1. Manual Docker cleanup:         docker system prune -a"
    echo "  2. Check Docker logs:             docker logs <container-id>"
    echo "  3. Verify Docker health:          docker inspect <container-id> | grep Health"
    echo "  4. Run only e2e tests:            $0 -e"
    echo "  5. Run tests with more verbose output: $0 -e -v"
    echo "  6. Stop on first failure:         $0 -e -x"
    echo "===================================================================="
    
    # Try to provide some diagnostic information
    echo "Docker info:"
    docker info 2>/dev/null | grep -E "containers|images|memory|space" || echo "Could not get Docker info"
    echo "===================================================================="
    echo -e "\033[0m"
fi

exit $EXIT_CODE