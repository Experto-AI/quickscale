#!/usr/bin/env bash
# QuickScale Code Quality Analysis Script
# Integrates: vulture (dead code), radon (complexity), pylint (duplication)
# Outputs: JSON (machine-readable) + Markdown (LLM-readable)
# Features: Auto-discovery of Python packages, configurable thresholds

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
BASELINE_FILE="${QUALITY_BASELINE_FILE:-$ROOT/scripts/quality_baseline.json}"
STATUS_OUTPUT="$OUTPUT_DIR/quality_gate_status.json"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#######################################
# ANALYSIS CONFIGURATION
#
# All thresholds are configurable below.
# To modify analysis behavior, update these variables.
#######################################

# Vulture (Dead Code Detection)
VULTURE_MIN_CONFIDENCE=80          # Minimum confidence percentage
VULTURE_SORT_BY_SIZE=true          # Sort results by code size

# Radon Complexity Thresholds
RADON_MIN_COMPLEXITY_GRADE="C"     # Minimum grade to report (A=1-5, B=6-10, C=11-20, D=21-30, E=31+)
RADON_HIGH_COMPLEXITY_CC=11        # Cyclomatic Complexity threshold for warnings
RADON_ERROR_COMPLEXITY_CC=21       # NEW: Cyclomatic Complexity threshold for errors
RADON_MIN_MI_GRADE="B"             # Maintainability Index minimum grade

# Large File Detection
LARGE_FILE_WARNING_LINES=500       # Line count to trigger warnings
LARGE_FILE_ERROR_LINES=800         # Line count to trigger errors (UPDATED from 1000)

# Code Duplication (pylint)
PYLINT_MIN_SIMILARITY_LINES=6      # Minimum similar lines to detect duplication

# Module Discovery
MODULE_DISCOVERY_ENABLED=true      # Enable auto-discovery of modules

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

discover_python_modules() {
    # Auto-discover Python packages with pyproject.toml and src/ directory
    # Returns: Space-separated list of src/ paths to analyze

    local modules=()

    # Find all directories with pyproject.toml (excluding root repo pyproject.toml)
    while IFS= read -r pyproject_file; do
        local package_dir=$(dirname "$pyproject_file")
        local src_dir="$package_dir/src"

        # Check if src/ directory exists
        if [ -d "$src_dir" ]; then
            # Exclude template directories
            if [[ ! "$src_dir" =~ /templates/ ]]; then
                modules+=("$src_dir")
            fi
        fi
    done < <(find "$ROOT" -name "pyproject.toml" -type f ! -path "$ROOT/pyproject.toml" 2>/dev/null)

    # Sort modules for consistent ordering
    IFS=$'\n' sorted_modules=($(sort <<<"${modules[*]}"))
    unset IFS

    # Return space-separated list
    echo "${sorted_modules[@]}"
}

get_module_paths() {
    # Returns module paths based on configuration
    # If auto-discovery is disabled, returns hardcoded fallback list

    if [ "$MODULE_DISCOVERY_ENABLED" = true ]; then
        local discovered=$(discover_python_modules)

        if [ -z "$discovered" ]; then
            print_warning "Auto-discovery found no modules, using fallback list"
            echo "quickscale_core/src quickscale_cli/src quickscale_modules/auth/src quickscale_modules/blog/src quickscale_modules/listings/src"
        else
            echo "$discovered"
        fi
    else
        # Fallback: hardcoded module list
        echo "quickscale_core/src quickscale_cli/src quickscale_modules/auth/src quickscale_modules/blog/src quickscale_modules/listings/src"
    fi
}

#######################################
# ANALYSIS FUNCTIONS
#######################################

analyze_dead_code() {
    print_header "Analyzing Dead Code (vulture)"

    # Get module paths
    local module_paths=$(get_module_paths)

    # Build vulture arguments
    local vulture_args="--min-confidence $VULTURE_MIN_CONFIDENCE"

    if [ "$VULTURE_SORT_BY_SIZE" = true ]; then
        vulture_args="$vulture_args --sort-by-size"
    fi

    # Run vulture and capture output
    local vulture_output
    vulture_output=$(poetry run vulture \
        $module_paths \
        $vulture_args 2>&1 || true)

    # Count issues
    local dead_code_count
    if [ -z "$vulture_output" ]; then
        dead_code_count=0
    else
        dead_code_count=$(echo "$vulture_output" | grep -c "unused" 2>/dev/null || echo "0")
        # Ensure count is a single integer (trim whitespace)
        dead_code_count=$(echo "$dead_code_count" | tr -d '[:space:]')
        dead_code_count=${dead_code_count:-0}
    fi

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

    # Get module paths
    local module_paths=$(get_module_paths)

    # Cyclomatic Complexity (CC)
    echo "Running cyclomatic complexity analysis..."
    local cc_output
    cc_output=$(poetry run radon cc \
        $module_paths \
        --min $RADON_MIN_COMPLEXITY_GRADE \
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
    count = sum(len([f for f in funcs if f.get('complexity', 0) >= $RADON_HIGH_COMPLEXITY_CC])
                for funcs in data.values() if isinstance(funcs, list))
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")

    echo "$high_complexity_count" > "$OUTPUT_DIR/high_complexity_count.txt"

    # Count error-level complexity functions (NEW)
    local error_complexity_count
    error_complexity_count=$(echo "$cc_output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    count = sum(len([f for f in funcs if f.get('complexity', 0) >= $RADON_ERROR_COMPLEXITY_CC])
                for funcs in data.values() if isinstance(funcs, list))
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")

    echo "$error_complexity_count" > "$OUTPUT_DIR/error_complexity_count.txt"

    if [ "$high_complexity_count" -eq 0 ] && [ "$error_complexity_count" -eq 0 ]; then
        print_success "No high complexity functions found"
    else
        if [ "$error_complexity_count" -gt 0 ]; then
            print_error "Found $error_complexity_count critical complexity functions (CC >= $RADON_ERROR_COMPLEXITY_CC)"
        fi
        if [ "$high_complexity_count" -gt 0 ]; then
            print_warning "Found $high_complexity_count high complexity functions (CC >= $RADON_HIGH_COMPLEXITY_CC)"
        fi
    fi

    # Maintainability Index (MI)
    echo "Running maintainability index analysis..."
    local mi_output
    mi_output=$(poetry run radon mi \
        $module_paths \
        --min $RADON_MIN_MI_GRADE \
        --show \
        --json 2>&1 || echo "{}")

    echo "$mi_output" > "$OUTPUT_DIR/maintainability_mi.json"

    # Raw metrics (LOC, SLOC, comments)
    echo "Calculating raw metrics..."
    local raw_output
    raw_output=$(poetry run radon raw \
        $module_paths \
        --summary \
        --json 2>&1 || echo "{}")

    echo "$raw_output" > "$OUTPUT_DIR/raw_metrics.json"
}

analyze_large_files() {
    print_header "Analyzing Large Files"

    # Get module paths
    local module_paths=$(get_module_paths)

    # Find files >= warning threshold
    # Filter out the "total" line from wc -l output
    local large_files_output
    large_files_output=$(find \
        $module_paths \
        -type f -name "*.py" -exec wc -l {} + 2>/dev/null | \
        grep -v " total$" | \
        awk -v warn="$LARGE_FILE_WARNING_LINES" '$1 >= warn {print $1 "\t" $2}' | \
        sort -rn || echo "")

    echo "$large_files_output" > "$OUTPUT_DIR/large_files.txt"

    local warning_count
    warning_count=$(echo "$large_files_output" | grep -v "^$" | \
        awk -v warn="$LARGE_FILE_WARNING_LINES" -v err="$LARGE_FILE_ERROR_LINES" \
        '$1 >= warn && $1 < err' | wc -l)

    local error_count
    error_count=$(echo "$large_files_output" | grep -v "^$" | \
        awk -v err="$LARGE_FILE_ERROR_LINES" '$1 >= err' | wc -l)

    echo "$warning_count" > "$OUTPUT_DIR/large_files_warning_count.txt"
    echo "$error_count" > "$OUTPUT_DIR/large_files_error_count.txt"

    if [ "$error_count" -eq 0 ] && [ "$warning_count" -eq 0 ]; then
        print_success "No large files found"
    else
        print_warning "Found $warning_count files >$LARGE_FILE_WARNING_LINES lines, $error_count files >$LARGE_FILE_ERROR_LINES lines"
    fi
}

analyze_duplication() {
    print_header "Analyzing Code Duplication (pylint)"

    # Get module paths
    local module_paths=$(get_module_paths)

    # Run pylint with only duplicate-code check enabled
    local pylint_output
    pylint_output=$(poetry run pylint \
        $module_paths \
        --disable=all \
        --enable=duplicate-code \
        --min-similarity-lines=$PYLINT_MIN_SIMILARITY_LINES \
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

    export QS_ROOT="$ROOT"
    export QS_TIMESTAMP="$TIMESTAMP"
    export QS_OUTPUT_DIR="$OUTPUT_DIR"
    export QS_JSON_OUTPUT="$JSON_OUTPUT"
    export QS_STATUS_OUTPUT="$STATUS_OUTPUT"
    export QS_BASELINE_FILE="$BASELINE_FILE"
    export QS_RADON_HIGH_COMPLEXITY_CC="$RADON_HIGH_COMPLEXITY_CC"
    export QS_RADON_ERROR_COMPLEXITY_CC="$RADON_ERROR_COMPLEXITY_CC"
    export QS_LARGE_FILE_WARNING_LINES="$LARGE_FILE_WARNING_LINES"
    export QS_LARGE_FILE_ERROR_LINES="$LARGE_FILE_ERROR_LINES"

    python3 <<'PY'
from collections import Counter
import json
import os
import re
from pathlib import Path

root = Path(os.environ["QS_ROOT"]).resolve()
output_dir = Path(os.environ["QS_OUTPUT_DIR"])
json_output = Path(os.environ["QS_JSON_OUTPUT"])
status_output = Path(os.environ["QS_STATUS_OUTPUT"])
timestamp = os.environ["QS_TIMESTAMP"]
baseline_file_value = os.environ["QS_BASELINE_FILE"]
baseline_path = Path(baseline_file_value)
if not baseline_path.is_absolute():
    baseline_path = (Path.cwd() / baseline_path).resolve()

high_complexity_threshold = int(os.environ["QS_RADON_HIGH_COMPLEXITY_CC"])
error_complexity_threshold = int(os.environ["QS_RADON_ERROR_COMPLEXITY_CC"])
large_file_warning_threshold = int(os.environ["QS_LARGE_FILE_WARNING_LINES"])
large_file_error_threshold = int(os.environ["QS_LARGE_FILE_ERROR_LINES"])

confidence_suffix = re.compile(r"\s+\(\d+% confidence, .*\)$")
dead_code_identity = re.compile(r"^(?P<file>.+?):\d+: (?P<message>.+)$")


def read_text_safe(filename):
    try:
        return (output_dir / filename).read_text()
    except OSError:
        return ""


def read_json_safe(filename, default):
    try:
        return json.loads((output_dir / filename).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def relative_path(path_value):
    if not path_value:
        return ""

    path = Path(path_value)
    if not path.is_absolute():
        return path.as_posix()

    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def require_mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_string(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def require_non_negative_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def normalize_dead_code(line):
    stripped = confidence_suffix.sub("", line.strip())
    match = dead_code_identity.match(stripped)
    if not match:
        return stripped
    return f"{match.group('file')}: {match.group('message')}"


def normalize_duplication_message(message):
    if not isinstance(message, str):
        return ""
    return " ".join(message.split())


def normalize_duplication_location(location):
    if not isinstance(location, dict):
        return ""

    path = relative_path(str(location.get("path", "")).strip())
    line = location.get("line")
    end_line = location.get("endLine")
    location_parts = [path]
    if isinstance(line, int):
        location_parts.append(str(line))
    if isinstance(end_line, int):
        location_parts.append(str(end_line))
    return ":".join(part for part in location_parts if part)


def normalize_duplication_identity(entry):
    normalized_message = normalize_duplication_message(entry.get("message"))
    normalized_locations = []
    raw_locations = entry.get("locations")
    if isinstance(raw_locations, list):
        normalized_locations = sorted(
            location
            for location in (
                normalize_duplication_location(location)
                for location in raw_locations
            )
            if location
        )

    if not normalized_locations:
        primary_location = normalize_duplication_location(
            {
                "path": entry.get("path", ""),
                "line": entry.get("line"),
                "endLine": entry.get("endLine"),
            }
        )
        if primary_location:
            normalized_locations = [primary_location]

    identity_parts = [normalized_message, *normalized_locations]
    normalized_identity = " | ".join(part for part in identity_parts if part)
    if normalized_identity:
        return normalized_identity
    return json.dumps(entry, sort_keys=True)


def validate_baseline(data):
    baseline = require_mapping(data, "baseline")
    schema_version = require_non_negative_int(baseline.get("schema_version"), "schema_version")
    if schema_version != 1:
        raise ValueError("schema_version must equal 1")

    dead_code = require_mapping(baseline.get("dead_code"), "dead_code")
    allowed_messages = dead_code.get("allowed_messages")
    if not isinstance(allowed_messages, list) or any(
        not isinstance(item, str) or not item for item in allowed_messages
    ):
        raise ValueError("dead_code.allowed_messages must be a list of non-empty strings")

    complexity = require_mapping(baseline.get("complexity"), "complexity")
    allowed_functions_raw = require_mapping(
        complexity.get("allowed_functions"),
        "complexity.allowed_functions",
    )
    allowed_functions = {}
    for key, entry in allowed_functions_raw.items():
        require_string(key, "complexity.allowed_functions key")
        item = require_mapping(entry, f"complexity.allowed_functions[{key}]")
        file_path = require_string(item.get("file"), f"complexity.allowed_functions[{key}].file")
        symbol = require_string(item.get("symbol"), f"complexity.allowed_functions[{key}].symbol")
        entry_type = require_string(item.get("type"), f"complexity.allowed_functions[{key}].type")
        max_complexity = require_non_negative_int(
            item.get("max_complexity"),
            f"complexity.allowed_functions[{key}].max_complexity",
        )
        expected_key = f"{file_path}::{symbol}"
        if key != expected_key:
            raise ValueError(
                f"complexity.allowed_functions[{key}] must match file::symbol ({expected_key})"
            )
        allowed_functions[key] = {
            "file": file_path,
            "symbol": symbol,
            "type": entry_type,
            "max_complexity": max_complexity,
        }

    large_files = require_mapping(baseline.get("large_files"), "large_files")
    allowed_files_raw = require_mapping(
        large_files.get("allowed_files"),
        "large_files.allowed_files",
    )
    allowed_files = {}
    for key, entry in allowed_files_raw.items():
        file_path = require_string(key, "large_files.allowed_files key")
        item = require_mapping(entry, f"large_files.allowed_files[{key}]")
        max_lines = require_non_negative_int(
            item.get("max_lines"),
            f"large_files.allowed_files[{key}].max_lines",
        )
        allowed_files[file_path] = {"max_lines": max_lines}

    duplication = require_mapping(baseline.get("duplication"), "duplication")
    allowed_blocks = require_non_negative_int(
        duplication.get("allowed_blocks"),
        "duplication.allowed_blocks",
    )
    allowed_block_identities = duplication.get("allowed_block_identities", [])
    if not isinstance(allowed_block_identities, list) or any(
        not isinstance(item, str) or not item for item in allowed_block_identities
    ):
        raise ValueError(
            "duplication.allowed_block_identities must be a list of non-empty strings"
        )
    if len(allowed_block_identities) != allowed_blocks:
        raise ValueError(
            "duplication.allowed_block_identities must list each allowed duplication block"
        )

    return {
        "schema_version": schema_version,
        "dead_code": {"allowed_messages": allowed_messages},
        "complexity": {"allowed_functions": allowed_functions},
        "large_files": {"allowed_files": allowed_files},
        "duplication": {
            "allowed_blocks": allowed_blocks,
            "allowed_block_identities": allowed_block_identities,
        },
    }


def regression_sort_key(item):
    severity_order = {"critical": 0, "warning": 1}
    return (
        severity_order.get(item.get("severity"), 2),
        item.get("file", ""),
        item.get("symbol", ""),
        item.get("message", ""),
    )


dead_code_raw = read_text_safe("vulture_raw.txt")
normalized_dead_code = sorted(
    normalize_dead_code(line)
    for line in dead_code_raw.splitlines()
    if line.strip()
)

cyclomatic = read_json_safe("complexity_cc.json", {})
maintainability = read_json_safe("maintainability_mi.json", {})
raw_metrics = read_json_safe("raw_metrics.json", {})

actual_complexity = {}
for file_path, entries in cyclomatic.items():
    if not isinstance(entries, list):
        continue
    rel_file = relative_path(file_path)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        complexity_value = entry.get("complexity")
        if isinstance(complexity_value, bool) or not isinstance(complexity_value, int):
            continue
        class_name = entry.get("classname")
        symbol = f"{class_name}.{name}" if class_name else name
        key = f"{rel_file}::{symbol}"
        actual_complexity[key] = {
            "key": key,
            "file": rel_file,
            "symbol": symbol,
            "type": entry.get("type", "function"),
            "complexity": complexity_value,
            "rank": entry.get("rank"),
            "lineno": entry.get("lineno"),
            "endline": entry.get("endline"),
        }

large_files_raw = read_text_safe("large_files.txt")
actual_large_files = {}
for raw_line in large_files_raw.splitlines():
    line = raw_line.strip()
    if not line:
        continue
    parts = line.split("\t", 1)
    if len(parts) != 2:
        continue
    try:
        line_count = int(parts[0].strip())
    except ValueError:
        continue
    rel_file = relative_path(parts[1].strip())
    actual_large_files[rel_file] = {
        "file": rel_file,
        "lines": line_count,
    }

duplication_raw = read_json_safe("duplication.json", [])
matching_duplication_blocks = []
for entry in duplication_raw:
    if not isinstance(entry, dict) or entry.get("message-id") != "R0801":
        continue
    normalized_entry = dict(entry)
    if isinstance(normalized_entry.get("path"), str):
        normalized_entry["path"] = relative_path(normalized_entry["path"])
    raw_locations = normalized_entry.get("locations")
    if isinstance(raw_locations, list):
        normalized_locations = []
        for location in raw_locations:
            if not isinstance(location, dict):
                continue
            normalized_location = dict(location)
            if isinstance(normalized_location.get("path"), str):
                normalized_location["path"] = relative_path(
                    normalized_location["path"]
                )
            normalized_locations.append(normalized_location)
        normalized_entry["locations"] = normalized_locations
    normalized_entry["identity"] = normalize_duplication_identity(normalized_entry)
    matching_duplication_blocks.append(normalized_entry)

high_complexity_count = sum(
    1 for entry in actual_complexity.values() if entry["complexity"] >= high_complexity_threshold
)
error_complexity_count = sum(
    1 for entry in actual_complexity.values() if entry["complexity"] >= error_complexity_threshold
)
large_files_warning_count = sum(
    1
    for entry in actual_large_files.values()
    if large_file_warning_threshold <= entry["lines"] < large_file_error_threshold
)
large_files_error_count = sum(
    1 for entry in actual_large_files.values() if entry["lines"] >= large_file_error_threshold
)
duplication_count = len(matching_duplication_blocks)

summary = {
    "dead_code_issues": len(normalized_dead_code),
    "high_complexity_functions": high_complexity_count,
    "error_complexity_functions": error_complexity_count,
    "large_files_warning": large_files_warning_count,
    "large_files_error": large_files_error_count,
    "duplication_blocks": duplication_count,
    "total_issues": len(normalized_dead_code)
    + high_complexity_count
    + large_files_warning_count
    + large_files_error_count
    + duplication_count,
}

baseline_payload = {
    "file": str(baseline_path),
    "status": "error",
    "error": "Baseline comparison not evaluated",
}
regressions = {
    "status": "not_evaluated",
    "warning_count": 0,
    "critical_count": 0,
    "total_count": 0,
    "has_regressions": False,
    "dead_code": {
        "count": 0,
        "new_messages": [],
        "resolved_messages": [],
    },
    "complexity": {
        "warning_count": 0,
        "critical_count": 0,
        "new_or_worse": [],
        "resolved": [],
    },
    "large_files": {
        "warning_count": 0,
        "critical_count": 0,
        "new_or_grown": [],
        "resolved": [],
    },
    "duplication": {
        "allowed_blocks": 0,
        "observed_blocks": duplication_count,
        "count": 0,
        "new_blocks": [],
    },
}

baseline_data = None
try:
    baseline_data = validate_baseline(json.loads(baseline_path.read_text()))
except FileNotFoundError:
    baseline_payload["error"] = f"Baseline file not found: {baseline_path}"
except json.JSONDecodeError as exc:
    baseline_payload["error"] = (
        f"Baseline file is not valid JSON: {baseline_path}: {exc.msg} "
        f"at line {exc.lineno}, column {exc.colno}"
    )
except ValueError as exc:
    baseline_payload["error"] = f"Baseline file is invalid: {exc}"

if baseline_data is not None:
    allowed_messages = Counter(baseline_data["dead_code"]["allowed_messages"])
    actual_messages = Counter(normalized_dead_code)
    new_dead_code = []
    for message in sorted(actual_messages):
        delta = actual_messages[message] - allowed_messages.get(message, 0)
        for _ in range(max(0, delta)):
            new_dead_code.append({"message": message, "severity": "warning"})

    resolved_dead_code = []
    for message in sorted(allowed_messages):
        delta = allowed_messages[message] - actual_messages.get(message, 0)
        for _ in range(max(0, delta)):
            resolved_dead_code.append(message)

    complexity_regressions = []
    for key, actual_entry in actual_complexity.items():
        baseline_entry = baseline_data["complexity"]["allowed_functions"].get(key)
        if baseline_entry is None:
            allowed_max = None
            regression_type = "new"
        elif actual_entry["complexity"] > baseline_entry["max_complexity"]:
            allowed_max = baseline_entry["max_complexity"]
            regression_type = "increased"
        else:
            continue

        regression = dict(actual_entry)
        regression["severity"] = (
            "critical"
            if actual_entry["complexity"] >= error_complexity_threshold
            else "warning"
        )
        regression["regression_type"] = regression_type
        regression["allowed_max_complexity"] = allowed_max
        if allowed_max is not None:
            regression["delta"] = actual_entry["complexity"] - allowed_max
        complexity_regressions.append(regression)

    complexity_resolved = []
    for key, baseline_entry in baseline_data["complexity"]["allowed_functions"].items():
        if key in actual_complexity:
            continue
        resolved_entry = dict(baseline_entry)
        resolved_entry["key"] = key
        complexity_resolved.append(resolved_entry)

    large_file_regressions = []
    for file_path, actual_entry in actual_large_files.items():
        baseline_entry = baseline_data["large_files"]["allowed_files"].get(file_path)
        if baseline_entry is None:
            allowed_max_lines = None
            regression_type = "new"
        elif actual_entry["lines"] > baseline_entry["max_lines"]:
            allowed_max_lines = baseline_entry["max_lines"]
            regression_type = "grown"
        else:
            continue

        regression = dict(actual_entry)
        regression["severity"] = (
            "critical"
            if actual_entry["lines"] >= large_file_error_threshold
            else "warning"
        )
        regression["regression_type"] = regression_type
        regression["allowed_max_lines"] = allowed_max_lines
        if allowed_max_lines is not None:
            regression["delta"] = actual_entry["lines"] - allowed_max_lines
        large_file_regressions.append(regression)

    large_files_resolved = []
    for file_path, baseline_entry in baseline_data["large_files"]["allowed_files"].items():
        if file_path in actual_large_files:
            continue
        large_files_resolved.append(
            {
                "file": file_path,
                "max_lines": baseline_entry["max_lines"],
            }
        )

    allowed_duplication_blocks = baseline_data["duplication"]["allowed_blocks"]
    remaining_allowed_duplication_blocks = Counter(
        baseline_data["duplication"]["allowed_block_identities"]
    )
    duplication_regressions = []
    for block in matching_duplication_blocks:
        identity = str(block.get("identity", "")).strip()
        if remaining_allowed_duplication_blocks.get(identity, 0) > 0:
            remaining_allowed_duplication_blocks[identity] -= 1
            continue

        regression = dict(block)
        regression["severity"] = "warning"
        duplication_regressions.append(regression)

    complexity_regressions.sort(key=regression_sort_key)
    large_file_regressions.sort(key=regression_sort_key)

    warning_regressions = (
        len(new_dead_code)
        + sum(1 for entry in complexity_regressions if entry["severity"] == "warning")
        + sum(1 for entry in large_file_regressions if entry["severity"] == "warning")
        + len(duplication_regressions)
    )
    critical_regressions = sum(
        1 for entry in complexity_regressions if entry["severity"] == "critical"
    ) + sum(1 for entry in large_file_regressions if entry["severity"] == "critical")

    baseline_payload = {
        "file": str(baseline_path),
        "status": "loaded",
        "schema_version": baseline_data["schema_version"],
        "accepted": {
            "dead_code_messages": len(baseline_data["dead_code"]["allowed_messages"]),
            "high_complexity_functions": len(baseline_data["complexity"]["allowed_functions"]),
            "critical_complexity_functions": sum(
                1
                for entry in baseline_data["complexity"]["allowed_functions"].values()
                if entry["max_complexity"] >= error_complexity_threshold
            ),
            "large_files_warning": sum(
                1
                for entry in baseline_data["large_files"]["allowed_files"].values()
                if large_file_warning_threshold <= entry["max_lines"] < large_file_error_threshold
            ),
            "large_files_error": sum(
                1
                for entry in baseline_data["large_files"]["allowed_files"].values()
                if entry["max_lines"] >= large_file_error_threshold
            ),
            "duplication_blocks": allowed_duplication_blocks,
        },
    }
    regressions = {
        "status": "evaluated",
        "warning_count": warning_regressions,
        "critical_count": critical_regressions,
        "total_count": warning_regressions + critical_regressions,
        "has_regressions": (warning_regressions + critical_regressions) > 0,
        "dead_code": {
            "count": len(new_dead_code),
            "new_messages": new_dead_code,
            "resolved_messages": resolved_dead_code,
        },
        "complexity": {
            "warning_count": sum(
                1 for entry in complexity_regressions if entry["severity"] == "warning"
            ),
            "critical_count": sum(
                1 for entry in complexity_regressions if entry["severity"] == "critical"
            ),
            "new_or_worse": complexity_regressions,
            "resolved": sorted(complexity_resolved, key=lambda entry: entry["key"]),
        },
        "large_files": {
            "warning_count": sum(
                1 for entry in large_file_regressions if entry["severity"] == "warning"
            ),
            "critical_count": sum(
                1 for entry in large_file_regressions if entry["severity"] == "critical"
            ),
            "new_or_grown": large_file_regressions,
            "resolved": sorted(large_files_resolved, key=lambda entry: entry["file"]),
        },
        "duplication": {
            "allowed_blocks": allowed_duplication_blocks,
            "observed_blocks": duplication_count,
            "count": len(duplication_regressions),
            "new_blocks": duplication_regressions,
        },
    }

report = {
    "timestamp": timestamp,
    "summary": summary,
    "baseline": baseline_payload,
    "regressions": regressions,
    "dead_code": {
        "raw_output": dead_code_raw,
        "normalized_messages": normalized_dead_code,
    },
    "complexity": {
        "cyclomatic": cyclomatic,
        "normalized_entries": sorted(actual_complexity.values(), key=lambda entry: entry["key"]),
        "maintainability": maintainability,
        "raw_metrics": raw_metrics,
    },
    "large_files": {
        "files": large_files_raw,
        "normalized_entries": sorted(
            actual_large_files.values(),
            key=lambda entry: (-entry["lines"], entry["file"]),
        ),
    },
    "duplication": duplication_raw,
}

status_payload = {
    "baseline_status": baseline_payload["status"],
    "baseline_error": baseline_payload.get("error", ""),
    "warning_regressions": regressions["warning_count"],
    "critical_regressions": regressions["critical_count"],
    "total_regressions": regressions["total_count"],
}

json_output.write_text(json.dumps(report, indent=2) + "\n")
status_output.write_text(json.dumps(status_payload, indent=2) + "\n")
PY

    print_success "JSON report saved to: $JSON_OUTPUT"
    print_success "Gate status saved to: $STATUS_OUTPUT"
}

generate_markdown_report() {
    print_header "Generating Markdown Report"

    export QS_JSON_OUTPUT="$JSON_OUTPUT"
    export QS_MD_OUTPUT="$MD_OUTPUT"
    export QS_RADON_HIGH_COMPLEXITY_CC="$RADON_HIGH_COMPLEXITY_CC"
    export QS_RADON_ERROR_COMPLEXITY_CC="$RADON_ERROR_COMPLEXITY_CC"
    export QS_LARGE_FILE_WARNING_LINES="$LARGE_FILE_WARNING_LINES"
    export QS_LARGE_FILE_ERROR_LINES="$LARGE_FILE_ERROR_LINES"
    export QS_PYLINT_MIN_SIMILARITY_LINES="$PYLINT_MIN_SIMILARITY_LINES"

    python3 <<'PY'
import json
import os
from pathlib import Path

report = json.loads(Path(os.environ["QS_JSON_OUTPUT"]).read_text())
md_output = Path(os.environ["QS_MD_OUTPUT"])

high_complexity_threshold = int(os.environ["QS_RADON_HIGH_COMPLEXITY_CC"])
error_complexity_threshold = int(os.environ["QS_RADON_ERROR_COMPLEXITY_CC"])
large_file_warning_threshold = int(os.environ["QS_LARGE_FILE_WARNING_LINES"])
large_file_error_threshold = int(os.environ["QS_LARGE_FILE_ERROR_LINES"])
pylint_similarity_lines = int(os.environ["QS_PYLINT_MIN_SIMILARITY_LINES"])

summary = report["summary"]
baseline = report["baseline"]
regressions = report["regressions"]


def pluralize(count, singular, plural=None):
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural or singular + 's'}"


def code_block(language, content):
    body = content.rstrip() if content else ""
    if not body:
        body = "[]" if language == "json" else "No findings."
    return f"```{language}\n{body}\n```"


def json_block(value):
    return code_block("json", json.dumps(value, indent=2))


def regression_cell(count, label):
    return f"{count} {label}" if baseline["status"] == "loaded" else "baseline error"


lines = [
    "# QuickScale Code Quality Report",
    "",
    f"**Generated:** {report['timestamp']}",
    f"**Baseline file:** {baseline['file']}",
    "",
    "## Summary",
    "",
    "| Metric | Raw Count | Gate Impact |",
    "|--------|-----------|-------------|",
    f"| Dead Code Issues | {summary['dead_code_issues']} | {regression_cell(regressions['dead_code']['count'], 'new vs baseline')} |",
    f"| High Complexity Functions (CC >= {high_complexity_threshold}) | {summary['high_complexity_functions']} | {regression_cell(regressions['complexity']['warning_count'], 'warning regressions')} |",
    f"| Critical Complexity Functions (CC >= {error_complexity_threshold}) | {summary['error_complexity_functions']} | {regression_cell(regressions['complexity']['critical_count'], 'critical regressions')} |",
    f"| Large Files ({large_file_warning_threshold}-{large_file_error_threshold - 1} lines) | {summary['large_files_warning']} | {regression_cell(regressions['large_files']['warning_count'], 'warning regressions')} |",
    f"| Very Large Files (>= {large_file_error_threshold} lines) | {summary['large_files_error']} | {regression_cell(regressions['large_files']['critical_count'], 'critical regressions')} |",
    f"| Code Duplication Blocks | {summary['duplication_blocks']} | {regression_cell(regressions['duplication']['count'], 'new vs baseline')} |",
    f"| **Total Raw Issues** | **{summary['total_issues']}** | **{'✓ Pass' if baseline['status'] == 'loaded' and regressions['total_count'] == 0 else '✗ Action required' if baseline['status'] == 'loaded' else '✗ Baseline error'}** |",
    "",
    "---",
    "",
    "## Baseline Gate",
    "",
]

if baseline["status"] != "loaded":
    lines.extend(
        [
            f"✗ Baseline configuration error: {baseline['error']}",
            "",
            "Baseline comparison was not evaluated. Raw findings below are still preserved for inspection.",
        ]
    )
else:
    accepted = baseline["accepted"]
    lines.extend(
        [
            "✓ Baseline loaded successfully.",
            "",
            "Accepted debt snapshot:",
            f"- {accepted['dead_code_messages']} dead-code messages",
            f"- {accepted['high_complexity_functions']} high-complexity functions ({accepted['critical_complexity_functions']} critical)",
            f"- {accepted['large_files_warning']} warning large files and {accepted['large_files_error']} critical large files",
            f"- {accepted['duplication_blocks']} allowed duplication blocks",
            "",
        ]
    )

    if regressions["total_count"] == 0:
        lines.extend(
            [
                "Regression result: ✓ No new or worsened findings relative to the accepted baseline.",
                "",
                "### New or Worse Findings",
                "",
                "✓ None.",
            ]
        )
    else:
        lines.extend(
            [
                f"Regression result: ✗ {regressions['critical_count']} critical and {regressions['warning_count']} warning regressions detected.",
                "",
                "### New or Worse Findings",
                "",
            ]
        )
        for entry in regressions["dead_code"]["new_messages"]:
            lines.append(f"- [warning] Dead code: {entry['message']}")
        for entry in regressions["complexity"]["new_or_worse"]:
            if entry["allowed_max_complexity"] is None:
                lines.append(
                    f"- [{entry['severity']}] Complexity: {entry['file']}::{entry['symbol']} is {entry['complexity']} (new above threshold)"
                )
            else:
                lines.append(
                    f"- [{entry['severity']}] Complexity: {entry['file']}::{entry['symbol']} is {entry['complexity']} (baseline {entry['allowed_max_complexity']})"
                )
        for entry in regressions["large_files"]["new_or_grown"]:
            if entry["allowed_max_lines"] is None:
                lines.append(
                    f"- [{entry['severity']}] Large file: {entry['file']} is {entry['lines']} lines (new above threshold)"
                )
            else:
                lines.append(
                    f"- [{entry['severity']}] Large file: {entry['file']} is {entry['lines']} lines (baseline {entry['allowed_max_lines']})"
                )
        for entry in regressions["duplication"]["new_blocks"]:
            path = entry.get("path") or "unknown-path"
            line = entry.get("line")
            location = f"{path}:{line}" if line else path
            lines.append(
                f"- [warning] Duplication: {location} {entry.get('message', 'duplicate-code')}"
            )

    lines.extend(
        [
            "",
            "### Resolved Since Baseline",
            "",
            f"- Dead code resolved: {len(regressions['dead_code']['resolved_messages'])}",
            f"- Complexity entries resolved: {len(regressions['complexity']['resolved'])}",
            f"- Large files resolved: {len(regressions['large_files']['resolved'])}",
        ]
    )

lines.extend(
    [
        "",
        "---",
        "",
        "## Detailed Findings",
        "",
        "### Dead Code (vulture)",
        "",
        code_block("text", report["dead_code"]["raw_output"]),
        "",
        "### Cyclomatic Complexity (radon)",
        "",
        json_block(report["complexity"]["cyclomatic"]),
        "",
        "### Maintainability Index (radon)",
        "",
        json_block(report["complexity"]["maintainability"]),
        "",
        "### Large Files",
        "",
        code_block("text", report["large_files"]["files"]),
        "",
        "### Code Duplication (pylint)",
        "",
        json_block(report["duplication"]),
        "",
        "---",
        "",
        "## Tool Details",
        "",
        "- vulture: Dead code detection",
        f"- radon: Complexity metrics (CC >= {high_complexity_threshold} warning, CC >= {error_complexity_threshold} critical)",
        f"- pylint: Code duplication (minimum {pylint_similarity_lines} similar lines)",
        f"- Custom: Large file detection ({large_file_warning_threshold}+ warning, {large_file_error_threshold}+ critical)",
        "",
        f"Full JSON report: {os.environ['QS_JSON_OUTPUT']}",
    ]
)

md_output.write_text("\n".join(lines).rstrip() + "\n")
PY

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
    local error_complexity_count=$(cat "$OUTPUT_DIR/error_complexity_count.txt" 2>/dev/null || echo "0")
    local large_files_warning=$(cat "$OUTPUT_DIR/large_files_warning_count.txt" 2>/dev/null || echo "0")
    local large_files_error=$(cat "$OUTPUT_DIR/large_files_error_count.txt" 2>/dev/null || echo "0")
    local dup_count=$(cat "$OUTPUT_DIR/duplication_count.txt" 2>/dev/null || echo "0")

    eval "$(
        python3 - "$STATUS_OUTPUT" <<'PY'
import json
import shlex
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
for key in (
    "baseline_status",
    "baseline_error",
    "warning_regressions",
    "critical_regressions",
    "total_regressions",
):
    print(f"{key.upper()}={shlex.quote(str(data.get(key, '')))}")
PY
    )"

    echo ""
    echo "Summary:"
    echo "  - Baseline file: $BASELINE_FILE"
    echo "  - Dead code: $dead_code_count"
    echo "  - High complexity (CC >= $RADON_HIGH_COMPLEXITY_CC): $high_complexity_count"
    echo "  - Critical complexity (CC >= $RADON_ERROR_COMPLEXITY_CC): $error_complexity_count"
    echo "  - Large files ($LARGE_FILE_WARNING_LINES-$((LARGE_FILE_ERROR_LINES - 1)) lines): $large_files_warning"
    echo "  - Very large files (>= $LARGE_FILE_ERROR_LINES lines): $large_files_error"
    echo "  - Duplication blocks: $dup_count"
    echo "  - Baseline regressions (warning): $WARNING_REGRESSIONS"
    echo "  - Baseline regressions (critical): $CRITICAL_REGRESSIONS"
    echo ""
    echo "Reports generated:"
    echo "  - JSON: $JSON_OUTPUT"
    echo "  - Markdown: $MD_OUTPUT"
    echo "  - Gate status: $STATUS_OUTPUT"
    echo ""

    # Exit codes
    if [ "$BASELINE_STATUS" != "loaded" ]; then
        print_error "Baseline configuration error: $BASELINE_ERROR"
        exit 1
    fi

    if [ "$CRITICAL_REGRESSIONS" -gt 0 ]; then
        print_error "CRITICAL regressions detected against baseline"
        exit 2
    elif [ "$WARNING_REGRESSIONS" -gt 0 ]; then
        print_warning "Regressions detected against baseline - review reports"
        exit 1
    else
        print_success "Quality baseline gate passed with no regressions"
        exit 0
    fi
}

# Run main function
main "$@"
