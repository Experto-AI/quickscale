#!/bin/bash
# LLM-friendly test runner that outputs only failures to a file
# Usage: ./run_tests_llm.sh [test-options]

set -eo pipefail

# Create output directory
mkdir -p test_results

# Get timestamp for unique filenames
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FAILURES_FILE="test_results/test_failures_${TIMESTAMP}.txt"
SUMMARY_FILE="test_results/test_summary_${TIMESTAMP}.txt"

echo "Running tests with LLM-friendly output..."
echo "Failures will be written to: $FAILURES_FILE"
echo "Summary will be written to: $SUMMARY_FILE"

# Run tests with failures-only flag and capture output
./run_tests.sh --failures-only "$@" 2>&1 | tee "$FAILURES_FILE"

# Create a summary
{
    echo "=== TEST EXECUTION SUMMARY ==="
    echo "Timestamp: $(date)"
    echo "Command: ./run_tests.sh --failures-only $*"
    echo ""
    
    # Count failures
    FAILURE_COUNT=$(grep -c "FAILED" "$FAILURES_FILE" 2>/dev/null || echo "0")
    echo "Total failures: $FAILURE_COUNT"
    
    if [[ $FAILURE_COUNT -gt 0 ]]; then
        echo ""
        echo "=== FAILED TESTS ==="
        grep "FAILED" "$FAILURES_FILE" || true
    fi
    
    echo ""
    echo "=== FULL OUTPUT ==="
    cat "$FAILURES_FILE"
} > "$SUMMARY_FILE"

# Show summary
echo ""
echo "=== LLM ANALYSIS READY ==="
echo "Copy this file content for LLM analysis:"
echo "cat $SUMMARY_FILE"

# Exit with the same code as the test run
if [[ $FAILURE_COUNT -gt 0 ]]; then
    exit 1
else
    exit 0
fi
