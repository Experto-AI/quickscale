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
PARALLEL=0
INTEGRATION=1
UNIT=1
SKIP_DOCKER_CHECK=0
SKIP_CLEANUP=0
RUN_UNIT=0
RUN_INTEGRATION=0
RUN_E2E=0
QUIET=0
VERBOSE=0
FORCE_CLEAN=0
RETRY_E2E=0
EXITFIRST=0
MEMORY_LIMIT="4G"

print_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -c, --coverage     Run tests with coverage report"
    echo "  -p, --parallel     Run tests in parallel using pytest-xdist"
    echo "  -u, --unit         Run only unit tests (fast, no external dependencies)"
    echo "  -i, --integration  Run only integration tests (medium speed, some external dependencies)"
    echo "  -e, --e2e          Run only end-to-end tests (slow, full system tests with Docker)"
    echo "  -s, --skip-docker  Skip Docker availability check"
    echo "  -n, --no-cleanup   Skip Docker container cleanup"
    echo "  -f, --force-clean  Force Docker resource cleanup before running tests"
    echo "  -r, --retry        Retry e2e tests once if they fail"
    echo "  -m, --memory LIMIT Set Docker memory limit (default: 4G)"
    echo "  -q, --quiet        Run tests in quiet mode (less verbose output)"
    echo "  -v, --verbose      Run tests in verbose mode (more detailed output)"
    echo "  -x, --exitfirst    Exit on first test failure"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -u              # Run only unit tests"
    echo "  $0 -e              # Run only end-to-end tests"
    echo "  $0 -u -i           # Run both unit and integration tests"
    echo "  $0 -u -i -e        # Run all tests (unit, integration, and end-to-end)"
    echo "  $0 -c -p           # Run all tests with coverage in parallel"
    echo "  $0 -e -r           # Run e2e tests with retry on failure"
    echo "  $0 -e -f           # Run e2e tests with forced Docker cleanup"
    echo "  $0 -q              # Run tests in quiet mode"
    echo "  $0 -v              # Run tests in verbose mode"
    echo "  $0 -x              # Stop on first test failure"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--coverage)
            COVERAGE=1
            shift
            ;;
        -p|--parallel)
            PARALLEL=1
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
        -s|--skip-docker)
            SKIP_DOCKER_CHECK=1
            shift
            ;;
        -n|--no-cleanup)
            SKIP_CLEANUP=1
            shift
            ;;
        -f|--force-clean)
            FORCE_CLEAN=1
            shift
            ;;
        -r|--retry)
            RETRY_E2E=1
            shift
            ;;
        -m|--memory)
            MEMORY_LIMIT="$2"
            shift 2
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
        -h|--help)
            print_usage
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            ;;
    esac
done

# Run Docker check if not skipped and we're running integration or E2E tests
if [[ $SKIP_DOCKER_CHECK -eq 0 && ( $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 || $SELECTED_TESTS -eq 0 ) ]]; then
    if ! check_docker; then
        echo ""
        echo -e "\033[33mWARNING: Docker check failed but continuing with tests.\033[0m"
        echo -e "\033[33mAdd --skip-docker flag to suppress this check.\033[0m"
        echo ""
        # Give the user a chance to abort
        if [[ $QUIET -eq 0 ]]; then
            read -p "Press Enter to continue with tests, or Ctrl+C to abort..." 
        fi
    fi
fi

# Add test selection paths
test_paths=()
SELECTED_TESTS=0
if [[ $RUN_UNIT -eq 1 || $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 ]]; then
    SELECTED_TESTS=1
fi

# If running e2e tests, set specific env variables
if [[ $RUN_E2E -eq 1 || ($SELECTED_TESTS -eq 0 && $RUN_INTEGRATION -eq 0 && $RUN_UNIT -eq 0) ]]; then
    if [[ $QUIET -eq 0 ]]; then
        echo "Setting up environment for E2E tests..."
    fi
    
    # Set environment variables for Docker memory limits
    export DOCKER_MEMORY_LIMIT=$MEMORY_LIMIT
    export DOCKER_BUILD_MEMORY=$MEMORY_LIMIT
    export DOCKER_OPTS="--memory=$MEMORY_LIMIT --memory-swap=$MEMORY_LIMIT"
    export PYTHONMALLOC=malloc
    export QUICKSCALE_TEST_BUILD=1
    export QUICKSCALE_SKIP_MIGRATIONS=1
    export QUICKSCALE_E2E_TEST=1
    export COMPOSE_HTTP_TIMEOUT=180
    
    # Extend Docker timeouts for better test stability
    export DOCKER_CLIENT_TIMEOUT=180
    
    # Use force cleanup if requested
    if [[ $FORCE_CLEAN -eq 1 ]]; then
        if [[ $QUIET -eq 0 ]]; then
            echo "Performing forced Docker resource cleanup..."
        fi
        free_docker_resources
    fi
    
    if [[ $QUIET -eq 0 ]]; then
        echo "E2E test environment configured with memory limit: $MEMORY_LIMIT"
    fi
fi

# Clean up existing Docker containers if we're running integration or E2E tests
if [[ $SKIP_CLEANUP -eq 0 && ( $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 || $SELECTED_TESTS -eq 0 ) ]]; then
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

# Add parallel option if requested
if [[ $PARALLEL -eq 1 ]]; then
    CMD="$CMD -n auto"
fi

# Add exitfirst option if requested
if [[ $EXITFIRST -eq 1 ]]; then
    CMD="$CMD --exitfirst"
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
else
    # Default: run unit, integration, and e2e tests
    test_paths+=("tests/unit/" "tests/integration/" "tests/e2e/")
fi

CMD="$CMD ${test_paths[@]}"

# Add pytest options to fix common issues
CMD="$CMD --no-header --tb=native"

# Show the command
if [[ $QUIET -eq 0 ]]; then
    echo "Running: $CMD"
fi

# Run the tests with special handling for E2E tests
set +e  # Allow script to continue if tests fail

if [[ $RUN_E2E -eq 1 && $RETRY_E2E -eq 1 && ($RUN_UNIT -eq 0 && $RUN_INTEGRATION -eq 0) ]]; then
    # Special case: Running only E2E tests with retry option
    if [[ $QUIET -eq 0 ]]; then
        echo "Running E2E tests with retry option..."
    fi
    
    # First attempt
    $CMD
    EXIT_CODE=$?
    
    # If failed, retry after cleanup
    if [[ $EXIT_CODE -ne 0 ]]; then
        if [[ $QUIET -eq 0 ]]; then
            echo -e "\033[33mE2E tests failed with exit code $EXIT_CODE. Retrying after cleanup...\033[0m"
            
            # Check container health to help diagnose issues
            echo "Checking container health before cleanup..."
            verify_container_health
        fi
        
        # Clean up Docker resources
        cleanup_test_containers
        free_docker_resources
        
        # Wait a moment for Docker to stabilize
        sleep 5
        
        if [[ $QUIET -eq 0 ]]; then
            echo "Running E2E tests (second attempt)..."
        fi
        
        # Second attempt
        $CMD
        EXIT_CODE=$?
    fi
else
    # Normal execution for other test types
    $CMD
    EXIT_CODE=$?
    
    # Check container health if e2e tests failed
    if [[ $EXIT_CODE -ne 0 && ($RUN_E2E -eq 1 || $SELECTED_TESTS -eq 0) && $QUIET -eq 0 ]]; then
        echo "Checking container health after test failure..."
        verify_container_health
    fi
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
    echo "  1. Run with forced cleanup:       $0 -e -f"
    echo "  2. Run with retry option:         $0 -e -r"
    echo "  3. Increase memory limit:         $0 -e -m 6G"
    echo "  4. Manual Docker cleanup:         docker system prune -a"
    echo "  5. Check Docker logs:             docker logs <container-id>"
    echo "  6. Verify Docker health:          docker inspect <container-id> | grep Health"
    echo "  7. Run only e2e tests:            $0 -e"
    echo "  8. Run tests with more verbose output: $0 -e -v"
    echo "  9. Stop on first failure:         $0 -e -x"
    echo "===================================================================="
    
    # Try to provide some diagnostic information
    echo "Docker info:"
    docker info 2>/dev/null | grep -E "containers|images|memory|space" || echo "Could not get Docker info"
    echo "===================================================================="
    echo -e "\033[0m"
fi

exit $EXIT_CODE