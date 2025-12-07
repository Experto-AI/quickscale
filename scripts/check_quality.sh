#!/usr/bin/env bash
# QuickScale Code Quality Analysis Script
# Integrates: vulture (dead code), radon (complexity), pylint (duplication)
# Outputs: JSON (machine-readable) + Markdown (LLM-readable)

set -euo pipefail

#######################################
# CONFIGURATION
#######################################

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUTPUT_DIR="$ROOT/.quickscale"
JSON_OUTPUT="$OUTPUT_DIR/quality_report.json"
MD_OUTPUT="$OUTPUT_DIR/quality_report.md"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#######################################
# HELPER FUNCTIONS
#######################################

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_dependencies() {
    print_header "Checking Dependencies"

    local missing=0

    if ! poetry run vulture --version &>/dev/null; then
        print_error "vulture not installed"
        missing=1
    else
        print_success "vulture installed"
    fi

    if ! poetry run radon --version &>/dev/null; then
        print_error "radon not installed"
        missing=1
    else
        print_success "radon installed"
    fi

    if ! poetry run pylint --version &>/dev/null; then
        print_error "pylint not installed"
        missing=1
    else
        print_success "pylint installed"
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        print_error "Missing dependencies. Run: poetry install --with dev"
        exit 1
    fi
}

#######################################
# ANALYSIS FUNCTIONS
#######################################

analyze_dead_code() {
    print_header "Analyzing Dead Code (vulture)"

    # Run vulture and capture output
    local vulture_output
    vulture_output=$(poetry run vulture \
        quickscale_core/src \
        quickscale_cli/src \
        quickscale_modules/auth/src \
        quickscale_modules/blog/src \
        quickscale_modules/listings/src \
        --min-confidence 80 \
        --sort-by-size 2>&1 || true)

    # Count issues
    local dead_code_count
    dead_code_count=$(echo "$vulture_output" | grep -c "unused" || echo "0")

    if [ "$dead_code_count" -eq 0 ]; then
        print_success "No dead code found"
    else
        print_warning "Found $dead_code_count dead code issues"
    fi

    # Store results in temporary file for JSON aggregation
    echo "$vulture_output" > "$OUTPUT_DIR/vulture_raw.txt"
    echo "$dead_code_count" > "$OUTPUT_DIR/dead_code_count.txt"
}

analyze_complexity() {
    print_header "Analyzing Code Complexity (radon)"

    # Cyclomatic Complexity (CC)
    echo "Running cyclomatic complexity analysis..."
    local cc_output
    cc_output=$(poetry run radon cc \
        quickscale_core/src \
        quickscale_cli/src \
        quickscale_modules/auth/src \
        quickscale_modules/blog/src \
        quickscale_modules/listings/src \
        --min C \
        --show-complexity \
        --total-average \
        --json 2>&1 || echo "{}")

    # Save JSON output
    echo "$cc_output" > "$OUTPUT_DIR/complexity_cc.json"

    # Count high complexity functions (C and above)
    local high_complexity_count
    high_complexity_count=$(echo "$cc_output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    count = sum(len([f for f in funcs if f.get('complexity', 0) >= 11])
                for funcs in data.values() if isinstance(funcs, list))
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")

    echo "$high_complexity_count" > "$OUTPUT_DIR/high_complexity_count.txt"

    if [ "$high_complexity_count" -eq 0 ]; then
        print_success "No high complexity functions found"
    else
        print_warning "Found $high_complexity_count high complexity functions (CC >= 11)"
    fi

    # Maintainability Index (MI)
    echo "Running maintainability index analysis..."
    local mi_output
    mi_output=$(poetry run radon mi \
        quickscale_core/src \
        quickscale_cli/src \
        quickscale_modules/auth/src \
        quickscale_modules/blog/src \
        quickscale_modules/listings/src \
        --min B \
        --show \
        --json 2>&1 || echo "{}")

    echo "$mi_output" > "$OUTPUT_DIR/maintainability_mi.json"

    # Raw metrics (LOC, SLOC, comments)
    echo "Calculating raw metrics..."
    local raw_output
    raw_output=$(poetry run radon raw \
        quickscale_core/src \
        quickscale_cli/src \
        quickscale_modules/auth/src \
        quickscale_modules/blog/src \
        quickscale_modules/listings/src \
        --summary \
        --json 2>&1 || echo "{}")

    echo "$raw_output" > "$OUTPUT_DIR/raw_metrics.json"
}

analyze_large_files() {
    print_header "Analyzing Large Files"

    # Find files > 500 lines (warning) and > 1000 lines (error)
    local large_files_output
    large_files_output=$(find \
        quickscale_core/src \
        quickscale_cli/src \
        quickscale_modules/auth/src \
        quickscale_modules/blog/src \
        quickscale_modules/listings/src \
        -type f -name "*.py" -exec wc -l {} + 2>/dev/null | \
        awk '$1 >= 500 {print $1 "\t" $2}' | \
        sort -rn || echo "")

    echo "$large_files_output" > "$OUTPUT_DIR/large_files.txt"

    local warning_count
    warning_count=$(echo "$large_files_output" | awk '$1 >= 500 && $1 < 1000' | wc -l)

    local error_count
    error_count=$(echo "$large_files_output" | awk '$1 >= 1000' | wc -l)

    echo "$warning_count" > "$OUTPUT_DIR/large_files_warning_count.txt"
    echo "$error_count" > "$OUTPUT_DIR/large_files_error_count.txt"

    if [ "$error_count" -eq 0 ] && [ "$warning_count" -eq 0 ]; then
        print_success "No large files found"
    else
        print_warning "Found $warning_count files >500 lines, $error_count files >1000 lines"
    fi
}

analyze_duplication() {
    print_header "Analyzing Code Duplication (pylint)"

    # Run pylint with only duplicate-code check enabled
    local pylint_output
    pylint_output=$(poetry run pylint \
        quickscale_core/src \
        quickscale_cli/src \
        quickscale_modules/auth/src \
        quickscale_modules/blog/src \
        quickscale_modules/listings/src \
        --disable=all \
        --enable=duplicate-code \
        --min-similarity-lines=6 \
        --ignore-comments=yes \
        --ignore-docstrings=yes \
        --ignore-imports=yes \
        --output-format=json 2>&1 || echo "[]")

    echo "$pylint_output" > "$OUTPUT_DIR/duplication.json"

    # Count duplication blocks
    local dup_count
    dup_count=$(echo "$pylint_output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # Filter for R0801 (duplicate-code)
    count = len([d for d in data if d.get('message-id') == 'R0801'])
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")

    echo "$dup_count" > "$OUTPUT_DIR/duplication_count.txt"

    if [ "$dup_count" -eq 0 ]; then
        print_success "No code duplication found"
    else
        print_warning "Found $dup_count duplication blocks"
    fi
}

#######################################
# OUTPUT GENERATION
#######################################

generate_json_report() {
    print_header "Generating JSON Report"

    # Read all counts
    local dead_code_count=$(cat "$OUTPUT_DIR/dead_code_count.txt" 2>/dev/null || echo "0")
    local high_complexity_count=$(cat "$OUTPUT_DIR/high_complexity_count.txt" 2>/dev/null || echo "0")
    local large_files_warning=$(cat "$OUTPUT_DIR/large_files_warning_count.txt" 2>/dev/null || echo "0")
    local large_files_error=$(cat "$OUTPUT_DIR/large_files_error_count.txt" 2>/dev/null || echo "0")
    local dup_count=$(cat "$OUTPUT_DIR/duplication_count.txt" 2>/dev/null || echo "0")

    # Generate JSON report using Python for proper JSON formatting
    python3 <<EOF > "$JSON_OUTPUT"
import json
from pathlib import Path

# Read raw data
output_dir = Path("$OUTPUT_DIR")

def read_json_safe(filename):
    try:
        with open(output_dir / filename) as f:
            return json.load(f)
    except:
        return {}

def read_text_safe(filename):
    try:
        with open(output_dir / filename) as f:
            return f.read()
    except:
        return ""

report = {
    "timestamp": "$TIMESTAMP",
    "summary": {
        "dead_code_issues": int("$dead_code_count"),
        "high_complexity_functions": int("$high_complexity_count"),
        "large_files_warning": int("$large_files_warning"),
        "large_files_error": int("$large_files_error"),
        "duplication_blocks": int("$dup_count"),
        "total_issues": int("$dead_code_count") + int("$high_complexity_count") +
                       int("$large_files_warning") + int("$large_files_error") + int("$dup_count")
    },
    "dead_code": {
        "raw_output": read_text_safe("vulture_raw.txt")
    },
    "complexity": {
        "cyclomatic": read_json_safe("complexity_cc.json"),
        "maintainability": read_json_safe("maintainability_mi.json"),
        "raw_metrics": read_json_safe("raw_metrics.json")
    },
    "large_files": {
        "files": read_text_safe("large_files.txt")
    },
    "duplication": read_json_safe("duplication.json")
}

print(json.dumps(report, indent=2))
EOF

    print_success "JSON report saved to: $JSON_OUTPUT"
}

generate_markdown_report() {
    print_header "Generating Markdown Report"

    # Read counts
    local dead_code_count=$(cat "$OUTPUT_DIR/dead_code_count.txt" 2>/dev/null || echo "0")
    local high_complexity_count=$(cat "$OUTPUT_DIR/high_complexity_count.txt" 2>/dev/null || echo "0")
    local large_files_warning=$(cat "$OUTPUT_DIR/large_files_warning_count.txt" 2>/dev/null || echo "0")
    local large_files_error=$(cat "$OUTPUT_DIR/large_files_error_count.txt" 2>/dev/null || echo "0")
    local dup_count=$(cat "$OUTPUT_DIR/duplication_count.txt" 2>/dev/null || echo "0")
    local total_issues=$((dead_code_count + high_complexity_count + large_files_warning + large_files_error + dup_count))

    # Generate Markdown report
    cat > "$MD_OUTPUT" <<MDEOF
# QuickScale Code Quality Report

**Generated:** $TIMESTAMP

## Summary

| Metric | Count | Status |
|--------|-------|--------|
| Dead Code Issues | $dead_code_count | $([ "$dead_code_count" -eq 0 ] && echo "✓ Good" || echo "⚠ Needs attention") |
| High Complexity Functions | $high_complexity_count | $([ "$high_complexity_count" -eq 0 ] && echo "✓ Good" || echo "⚠ Needs attention") |
| Large Files (500-1000 lines) | $large_files_warning | $([ "$large_files_warning" -eq 0 ] && echo "✓ Good" || echo "⚠ Warning") |
| Very Large Files (>1000 lines) | $large_files_error | $([ "$large_files_error" -eq 0 ] && echo "✓ Good" || echo "✗ Critical") |
| Code Duplication Blocks | $dup_count | $([ "$dup_count" -eq 0 ] && echo "✓ Good" || echo "⚠ Needs attention") |
| **Total Issues** | **$total_issues** | $([ "$total_issues" -eq 0 ] && echo "**✓ Excellent**" || echo "**⚠ Action Required**") |

---

## Detailed Findings

### 1. Dead Code Analysis (vulture)

$(if [ "$dead_code_count" -eq 0 ]; then
    echo "✓ No dead code detected. All imports, functions, classes, and variables appear to be in use."
else
    echo "⚠ Found $dead_code_count potential dead code issues:"
    echo '```'
    cat "$OUTPUT_DIR/vulture_raw.txt" 2>/dev/null || echo "No details available"
    echo '```'
    echo ""
    echo "**Recommended Actions:**"
    echo "1. Review each flagged item to confirm it's truly unused"
    echo "2. Remove confirmed dead code or add comments explaining why it's kept"
    echo "3. Consider using \`# type: ignore[vulture]\` for intentional unused code"
fi)

---

### 2. Complexity Analysis (radon)

#### Cyclomatic Complexity

$(if [ "$high_complexity_count" -eq 0 ]; then
    echo "✓ All functions have acceptable complexity (CC < 11)."
else
    echo "⚠ Found $high_complexity_count functions with high complexity (CC >= 11):"
    echo '```json'
    cat "$OUTPUT_DIR/complexity_cc.json" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "{}"
    echo '```'
    echo ""
    echo "**Complexity Thresholds:**"
    echo "- **A (1-5):** Simple - no action needed"
    echo "- **B (6-10):** Moderate - acceptable"
    echo "- **C (11-20):** High - consider refactoring"
    echo "- **D (21-30):** Very high - refactor recommended"
    echo "- **E (31+):** Extremely high - refactor required"
    echo ""
    echo "**Recommended Actions:**"
    echo "1. Extract complex logic into smaller, focused functions"
    echo "2. Reduce nested conditionals and loops"
    echo "3. Apply SOLID principles (especially Single Responsibility)"
fi)

#### Maintainability Index

\`\`\`json
$(cat "$OUTPUT_DIR/maintainability_mi.json" 2>/dev/null | python3 -m json.tool 2>/dev/null | head -50 || echo "{}")
\`\`\`

**Maintainability Grades:**
- **A (20-100):** Highly maintainable
- **B (10-19):** Moderately maintainable
- **C (0-9):** Difficult to maintain - needs attention

---

### 3. Large Files Analysis

$(if [ "$large_files_error" -eq 0 ] && [ "$large_files_warning" -eq 0 ]; then
    echo "✓ No files exceed 500 lines. Good modularity!"
else
    echo "Files exceeding recommended size limits:"
    echo '```'
    cat "$OUTPUT_DIR/large_files.txt" 2>/dev/null || echo "No details available"
    echo '```'
    echo ""
    echo "**Size Thresholds:**"
    echo "- **< 500 lines:** Good"
    echo "- **500-1000 lines:** Warning - consider splitting"
    echo "- **> 1000 lines:** Critical - refactor required"
    echo ""
    echo "**Recommended Actions:**"
    echo "1. Split large files into multiple modules"
    echo "2. Extract related functions into separate files"
    echo "3. Consider breaking down large classes"
fi)

---

### 4. Code Duplication Analysis (pylint)

$(if [ "$dup_count" -eq 0 ]; then
    echo "✓ No significant code duplication detected (minimum 6 similar lines)."
else
    echo "⚠ Found $dup_count duplication blocks:"
    echo '```json'
    cat "$OUTPUT_DIR/duplication.json" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "[]"
    echo '```'
    echo ""
    echo "**Recommended Actions:**"
    echo "1. Extract duplicated code into shared utility functions"
    echo "2. Create base classes for common functionality"
    echo "3. Apply DRY (Don't Repeat Yourself) principle"
    echo "4. Consider using inheritance or composition patterns"
fi)

---

## Overall Recommendations

$(if [ "$total_issues" -eq 0 ]; then
    echo "🎉 **Excellent Code Quality!** No issues detected across all analyzed metrics."
    echo ""
    echo "Continue maintaining these practices:"
    echo "- Keep functions small and focused"
    echo "- Maintain good modularity"
    echo "- Follow DRY principles"
    echo "- Remove unused code promptly"
else
    echo "### Priority Actions:"
    echo ""
    if [ "$large_files_error" -gt 0 ]; then
        echo "1. **CRITICAL:** Refactor $large_files_error files exceeding 1000 lines"
    fi
    if [ "$high_complexity_count" -gt 0 ]; then
        echo "2. **HIGH:** Reduce complexity in $high_complexity_count functions (CC >= 11)"
    fi
    if [ "$dup_count" -gt 0 ]; then
        echo "3. **MEDIUM:** Eliminate $dup_count code duplication blocks"
    fi
    if [ "$dead_code_count" -gt 0 ]; then
        echo "4. **LOW:** Remove $dead_code_count dead code instances"
    fi
    if [ "$large_files_warning" -gt 0 ]; then
        echo "5. **LOW:** Consider splitting $large_files_warning files (500-1000 lines)"
    fi
    echo ""
    echo "### General Best Practices:"
    echo "- Apply SOLID principles during refactoring"
    echo "- Write unit tests for refactored code"
    echo "- Review changes with team before committing"
    echo "- Run this script regularly to track improvements"
fi)

---

## Tool Details

- **vulture:** Dead code detection (min confidence: 80%)
- **radon:** Complexity metrics (CC, MI, raw LOC)
- **pylint:** Code duplication (min 6 similar lines)
- **Custom:** Large file detection (>500 lines warning, >1000 error)

**Full JSON report:** \`$JSON_OUTPUT\`

MDEOF

    print_success "Markdown report saved to: $MD_OUTPUT"
}

#######################################
# MAIN EXECUTION
#######################################

main() {
    print_header "QuickScale Code Quality Analysis"
    echo "Timestamp: $TIMESTAMP"

    # Check all dependencies are installed
    check_dependencies

    # Run all analyses
    analyze_dead_code
    analyze_complexity
    analyze_large_files
    analyze_duplication

    # Generate reports
    generate_json_report
    generate_markdown_report

    print_header "Analysis Complete"

    # Read summary counts for exit code determination
    local dead_code_count=$(cat "$OUTPUT_DIR/dead_code_count.txt" 2>/dev/null || echo "0")
    local high_complexity_count=$(cat "$OUTPUT_DIR/high_complexity_count.txt" 2>/dev/null || echo "0")
    local large_files_error=$(cat "$OUTPUT_DIR/large_files_error_count.txt" 2>/dev/null || echo "0")
    local dup_count=$(cat "$OUTPUT_DIR/duplication_count.txt" 2>/dev/null || echo "0")
    local total_issues=$((dead_code_count + high_complexity_count + large_files_error + dup_count))

    echo ""
    echo "Summary:"
    echo "  - Dead code: $dead_code_count"
    echo "  - High complexity: $high_complexity_count"
    echo "  - Large files (>1000 lines): $large_files_error"
    echo "  - Duplication blocks: $dup_count"
    echo ""
    echo "Reports generated:"
    echo "  - JSON: $JSON_OUTPUT"
    echo "  - Markdown: $MD_OUTPUT"
    echo ""

    # Exit codes
    if [ "$large_files_error" -gt 0 ]; then
        print_error "CRITICAL: Files exceeding 1000 lines found"
        exit 2
    elif [ "$total_issues" -gt 0 ]; then
        print_warning "Warnings found - review reports"
        exit 1
    else
        print_success "All quality checks passed!"
        exit 0
    fi
}

# Run main function
main "$@"
