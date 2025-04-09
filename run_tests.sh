#!/bin/bash
# Script to run tests with proper settings

# Set environment variables for testing
export QUICKSCALE_TEST_MODE=1
export QUICKSCALE_NO_ANALYTICS=1

# Functions for checking Docker
check_docker() {
    echo "Checking Docker availability..."
    
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
    
    echo "Docker is available and running."
    return 0
}

# Function to clean up existing Docker containers
cleanup_test_containers() {
    echo "Checking for existing test containers..."
    
    # Check if any test containers are running
    if docker ps -a | grep -E "test_project|real_test_project" > /dev/null; then
        echo -e "\033[33mFound existing test containers. Cleaning up before running tests...\033[0m"
        
        # Stop and remove all containers matching our test patterns
        docker ps -a | grep -E "test_project|real_test_project" | awk '{print $1}' | xargs -r docker stop
        docker ps -a | grep -E "test_project|real_test_project" | awk '{print $1}' | xargs -r docker rm
        
        echo "Test containers have been stopped and removed."
    else
        echo "No existing test containers found."
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
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -u              # Run only unit tests"
    echo "  $0 -e              # Run only end-to-end tests"
    echo "  $0 -u -i           # Run both unit and integration tests"
    echo "  $0 -u -i -e        # Run all tests (unit, integration, and end-to-end)"
    echo "  $0 -c -p           # Run all tests with coverage in parallel"
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
if [[ $SKIP_DOCKER_CHECK -eq 0 && ( $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 ) ]]; then
    if ! check_docker; then
        echo ""
        echo -e "\033[33mWARNING: Docker check failed but continuing with tests.\033[0m"
        echo -e "\033[33mAdd --skip-docker flag to suppress this check.\033[0m"
        echo ""
        # Give the user a chance to abort
        read -p "Press Enter to continue with tests, or Ctrl+C to abort..." 
    fi
fi

# Clean up existing Docker containers if we're running integration or E2E tests
if [[ $SKIP_CLEANUP -eq 0 && ( $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 ) ]]; then
    cleanup_test_containers
fi

# Build test command
CMD="python -m pytest"

# Add coverage if requested
if [[ $COVERAGE -eq 1 ]]; then
    CMD="$CMD --cov=quickscale --cov-report=term --cov-report=html"
fi

# Add parallel option if requested
if [[ $PARALLEL -eq 1 ]]; then
    CMD="$CMD -n auto"
fi

# Add test selection paths
test_paths=()
SELECTED_TESTS=0
if [[ $RUN_UNIT -eq 1 || $RUN_INTEGRATION -eq 1 || $RUN_E2E -eq 1 ]]; then
    SELECTED_TESTS=1
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

# Show the command
echo "Running: $CMD"

# Run the tests
$CMD

# Capture exit code
EXIT_CODE=$?

# If coverage was generated, show the report location
if [[ $COVERAGE -eq 1 ]]; then
    echo "Coverage report generated in htmlcov/index.html"
fi

exit $EXIT_CODE