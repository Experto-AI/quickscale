#!/usr/bin/env bash
# QuickScale Code Quality Analysis Script
# Integrates: vulture (dead code), radon (complexity), pylint (duplication)
# Outputs: JSON (machine-readable) + Markdown (LLM-readable)
# Gate: fixed fail/warn thresholds, no baseline and no waivers (SA243).
#   - vulture:  100% confidence fails; 80-99% warns
#   - radon CC: >= 21 fails; 11-20 warns
#   - file size: >= 800 lines fails; 500-799 warns
#   - pylint duplication: blocks of >= 20 similar lines fail; 6-19 lines warn
# A warn-column finding prints and still exits 0; a fail-column finding exits 1.

set -euo pipefail

#######################################
# CONFIGURATION
#######################################

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUTPUT_DIR="${QUALITY_OUTPUT_DIR:-$ROOT/.quickscale}"
export QUALITY_OUTPUT_DIR="$OUTPUT_DIR"
JSON_OUTPUT="$OUTPUT_DIR/quality_report.json"
MD_OUTPUT="$OUTPUT_DIR/quality_report.md"
STATUS_OUTPUT="$OUTPUT_DIR/quality_gate_status.json"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# A verdict from a previous run must never survive into a failed run: clear
# the report and status artifacts before any analysis starts.  A successful
# run regenerates them below.
rm -f "$JSON_OUTPUT" "$MD_OUTPUT" "$STATUS_OUTPUT"

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
VULTURE_MIN_CONFIDENCE=80           # Minimum confidence percentage to report
VULTURE_ERROR_CONFIDENCE=100        # 100% confidence findings fail the gate
VULTURE_SORT_BY_SIZE=true           # Sort results by code size

# Radon Complexity Thresholds
RADON_MIN_COMPLEXITY_GRADE="C"     # Minimum grade to report (A=1-5, B=6-10, C=11-20, D=21-30, E=31+)
RADON_HIGH_COMPLEXITY_CC=11        # Cyclomatic Complexity threshold for warnings
RADON_ERROR_COMPLEXITY_CC=21       # Cyclomatic Complexity threshold for failures
RADON_MIN_MI_GRADE="B"             # Maintainability Index minimum grade

# Large File Detection
LARGE_FILE_WARNING_LINES=500       # Line count to trigger warnings
LARGE_FILE_ERROR_LINES=800         # Line count to trigger failures

# Code Duplication (pylint).  The policy bands are inclusive — a block of
# exactly 6 similar lines warns, a block of exactly 20 fails — but pylint's
# --min-similarity-lines option is exclusive (it reports blocks strictly
# longer than the option value).  The option values are the inclusive floors
# minus one so the policy holds at the boundaries.
PYLINT_WARN_MIN_LINES=6            # Warn band floor: blocks of >= 6 similar lines
PYLINT_FAIL_MIN_LINES=20           # Fail line: blocks of >= 20 similar lines
PYLINT_WARN_OPTION_LINES=$((PYLINT_WARN_MIN_LINES - 1))
PYLINT_FAIL_OPTION_LINES=$((PYLINT_FAIL_MIN_LINES - 1))

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

    # Run vulture and capture output.  Exit 3 means findings, 0 means none;
    # any other status is an analyzer failure that must not read as clean.
    local vulture_status=0
    local vulture_output
    vulture_output=$(poetry run vulture \
        $module_paths \
        $vulture_args 2>&1) || vulture_status=$?

    if [ "$vulture_status" -ne 0 ] && [ "$vulture_status" -ne 3 ]; then
        print_error "vulture scan failed (exit $vulture_status)"
        exit 1
    fi

    # Store raw output for the report step
    echo "$vulture_output" > "$OUTPUT_DIR/vulture_raw.txt"

    # Split findings by confidence: >= 100% fails, 80-99% warns.  A non-empty
    # line that is not a finding is an analyzer diagnostic; the run must fail
    # closed instead of counting it as zero findings.
    if ! python3 - "$OUTPUT_DIR" "$VULTURE_ERROR_CONFIDENCE" <<'PY'
import re
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
error_confidence = int(sys.argv[2])
raw = (output_dir / "vulture_raw.txt").read_text()
pattern = re.compile(
    r"^(?P<location>.+?): (?P<message>.+) \((?P<confidence>\d+)% confidence.*\)$"
)

fail_lines: list[str] = []
warn_lines: list[str] = []
for line in raw.splitlines():
    stripped = line.strip()
    if not stripped:
        continue
    match = pattern.match(stripped)
    if match is None:
        raise SystemExit(f"unrecognized vulture output line: {stripped}")
    if int(match.group("confidence")) >= error_confidence:
        fail_lines.append(stripped)
    else:
        warn_lines.append(stripped)

(output_dir / "dead_code_fail.txt").write_text(
    "\n".join(fail_lines) + ("\n" if fail_lines else "")
)
(output_dir / "dead_code_warning.txt").write_text(
    "\n".join(warn_lines) + ("\n" if warn_lines else "")
)
(output_dir / "dead_code_fail_count.txt").write_text(f"{len(fail_lines)}\n")
(output_dir / "dead_code_warning_count.txt").write_text(f"{len(warn_lines)}\n")
PY
    then
        print_error "vulture output is not a valid finding list — refusing to treat it as zero findings"
        exit 1
    fi

    local fail_count=$(cat "$OUTPUT_DIR/dead_code_fail_count.txt")
    local warn_count=$(cat "$OUTPUT_DIR/dead_code_warning_count.txt")

    if [ "$fail_count" -gt 0 ]; then
        print_error "Found $fail_count dead code findings at 100% confidence"
        while IFS= read -r dead_line; do
            if [ -n "$dead_line" ]; then
                print_error "  $dead_line"
            fi
        done < "$OUTPUT_DIR/dead_code_fail.txt"
    fi
    if [ "$warn_count" -gt 0 ]; then
        print_warning "Found $warn_count dead code findings at 80-99% confidence"
    fi
    if [ "$fail_count" -eq 0 ] && [ "$warn_count" -eq 0 ]; then
        print_success "No dead code found"
    fi
}

analyze_complexity() {
    print_header "Analyzing Code Complexity (radon)"

    # Get module paths
    local module_paths=$(get_module_paths)

    # Cyclomatic Complexity (CC)
    echo "Running cyclomatic complexity analysis..."
    local cc_status=0
    local cc_output
    cc_output=$(poetry run radon cc \
        $module_paths \
        --min $RADON_MIN_COMPLEXITY_GRADE \
        --show-complexity \
        --show-closures \
        --total-average \
        --json 2>/dev/null) || cc_status=$?

    # A non-zero status or a document whose values are not finding lists is
    # an analyzer failure that must not read as zero findings.  Radon reports
    # a per-file error object (``{"error": ...}``) for an unparsable file with
    # status 0, so value shapes are validated too.
    if [ "$cc_status" -ne 0 ] || ! echo "$cc_output" | python3 -c "
import json
import sys

data = json.load(sys.stdin)
valid = isinstance(data, dict) and all(
    isinstance(entries, list)
    and all(isinstance(entry, dict) for entry in entries)
    for entries in data.values()
)
if not valid:
    raise SystemExit(1)
" 2>/dev/null; then
        print_error "radon complexity output is not a valid JSON object — refusing to treat it as zero findings"
        exit 1
    fi

    # Save JSON output
    echo "$cc_output" > "$OUTPUT_DIR/complexity_cc.json"

    # Count high complexity functions (C and above)
    local high_complexity_count
    high_complexity_count=$(echo "$cc_output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    count = sum(len([f for f in funcs
                     if f.get('complexity', 0) >= $RADON_HIGH_COMPLEXITY_CC
                     and f.get('type') != 'class'])
                for funcs in data.values() if isinstance(funcs, list))
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")
    echo "$high_complexity_count" > "$OUTPUT_DIR/high_complexity_count.txt"

    # Count failure-level complexity functions
    local error_complexity_count
    error_complexity_count=$(echo "$cc_output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    count = sum(len([f for f in funcs
                     if f.get('complexity', 0) >= $RADON_ERROR_COMPLEXITY_CC
                     and f.get('type') != 'class'])
                for funcs in data.values() if isinstance(funcs, list))
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")
    echo "$error_complexity_count" > "$OUTPUT_DIR/error_complexity_count.txt"

    # SA242: name every failure-column function so the gate reports it, not
    # just a count. The warning-column file backs the warn-naming in reports.
    # Radon class aggregates are not functions and are excluded from the fail
    # column; nested functions are included through --show-closures.
    echo "$cc_output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    data = {}

def function_name(entry):
    name = entry.get('name', '?')
    classname = entry.get('classname')
    return f'{classname}.{name}' if classname else name

error_rows = []
warn_rows = []
for file_path, funcs in data.items():
    if not isinstance(funcs, list):
        continue
    for entry in funcs:
        if entry.get('type') == 'class':
            continue
        complexity = entry.get('complexity', 0)
        if complexity >= $RADON_ERROR_COMPLEXITY_CC:
            error_rows.append((complexity, file_path, function_name(entry)))
        elif complexity >= $RADON_HIGH_COMPLEXITY_CC:
            warn_rows.append((complexity, file_path, function_name(entry)))
for rows, filename in ((error_rows, 'error_complexity_functions.txt'), (warn_rows, 'high_complexity_functions.txt')):
    rows.sort(reverse=True)
    with open('$OUTPUT_DIR/' + filename, 'w') as handle:
        for complexity, file_path, name in rows:
            handle.write(f'{complexity}\t{file_path}\t{name}\n')
" 2>/dev/null || true

    if [ "$high_complexity_count" -eq 0 ] && [ "$error_complexity_count" -eq 0 ]; then
        print_success "No high complexity functions found"
    else
        if [ "$error_complexity_count" -gt 0 ]; then
            print_error "Found $error_complexity_count critical complexity functions (CC >= $RADON_ERROR_COMPLEXITY_CC)"
            while IFS=$'\t' read -r function_complexity function_path function_name; do
                if [ -n "$function_complexity" ]; then
                    print_error "  $function_path: $function_name is $function_complexity"
                fi
            done < "$OUTPUT_DIR/error_complexity_functions.txt"
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

    # Find files >= warning threshold.  ``grep -c ""`` counts a final
    # physical line that has no trailing newline; ``wc -l`` would undercount
    # it, so a valid 800-line file without a terminal newline could slip past
    # the gate.
    local large_files_output
    large_files_output=$(find \
        $module_paths \
        -type f -name "*.py" -exec sh -c '
            for python_file do
                line_count=$(grep -c "" "$python_file" 2>/dev/null || true)
                line_count=${line_count:-0}
                printf "%s\t%s\n" "$line_count" "$python_file"
            done
        ' sh {} + 2>/dev/null | \
        awk -v warn="$LARGE_FILE_WARNING_LINES" '$1 >= warn {print $1 "\t" $2}' | \
        sort -rn || echo "")

    echo "$large_files_output" > "$OUTPUT_DIR/large_files.txt"

    local warning_count
    warning_count=$(printf '%s\n' "$large_files_output" | \
        awk -v warn="$LARGE_FILE_WARNING_LINES" -v err="$LARGE_FILE_ERROR_LINES" \
        '$1 >= warn && $1 < err {count++} END {print count+0}')

    local error_count
    error_count=$(printf '%s\n' "$large_files_output" | \
        awk -v err="$LARGE_FILE_ERROR_LINES" '$1 >= err {count++} END {print count+0}')

    echo "$warning_count" > "$OUTPUT_DIR/large_files_warning_count.txt"
    echo "$error_count" > "$OUTPUT_DIR/large_files_error_count.txt"

    if [ "$error_count" -gt 0 ]; then
        print_error "Found $error_count very large files (>= $LARGE_FILE_ERROR_LINES lines)"
        while IFS=$'\t' read -r file_line_count file_path; do
            if [ -n "$file_line_count" ] && [ "$file_line_count" -ge "$LARGE_FILE_ERROR_LINES" ]; then
                print_error "  $file_path has $file_line_count lines"
            fi
        done <<< "$large_files_output"
    fi
    if [ "$warning_count" -gt 0 ]; then
        print_warning "Found $warning_count large files (>$LARGE_FILE_WARNING_LINES lines)"
    fi
    if [ "$error_count" -eq 0 ] && [ "$warning_count" -eq 0 ]; then
        print_success "No large files found"
    fi
}

analyze_duplication() {
    print_header "Analyzing Code Duplication (pylint)"

    # Get module paths
    local module_paths=$(get_module_paths)

    # pylint exits 8 when it reports refactor findings (which includes every
    # R0801 block) and 0 when there are none; any other status is an analyzer
    # failure.  stdout is the JSON document; stderr stays out of it.
    local pylint_common="--disable=all --enable=duplicate-code --ignore-comments=yes --ignore-docstrings=yes --ignore-imports=yes --output-format=json"

    # Warn pass: every block of >= 6 similar lines (the option value is one
    # below the inclusive floor because pylint compares strictly greater).
    local warn_status=0
    local warn_output
    warn_output=$(poetry run pylint \
        $module_paths \
        $pylint_common \
        --min-similarity-lines=$PYLINT_WARN_OPTION_LINES 2>/dev/null) || warn_status=$?
    echo "$warn_output" > "$OUTPUT_DIR/duplication.json"

    # Fail pass: only blocks of >= 20 similar lines, by pylint's own count.
    local error_status=0
    local error_output
    error_output=$(poetry run pylint \
        $module_paths \
        $pylint_common \
        --min-similarity-lines=$PYLINT_FAIL_OPTION_LINES 2>/dev/null) || error_status=$?
    echo "$error_output" > "$OUTPUT_DIR/duplication_error.json"

    if { [ "$warn_status" -ne 0 ] && [ "$warn_status" -ne 8 ]; } || \
       { [ "$error_status" -ne 0 ] && [ "$error_status" -ne 8 ]; }; then
        print_error "pylint duplication scan failed (exit $warn_status/$error_status)"
        exit 1
    fi

    # Classify the two runs.  Unparseable output, a non-object entry, or a
    # non-R0801 analyzer diagnostic is a gate error, never zero findings.  A
    # block reported by the fail pass fails; every other block observed by
    # the warn pass warns.
    if ! python3 - "$OUTPUT_DIR" <<'PY'
import json
import re
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
header_pattern = re.compile(r"==([^\s:]+):\[(\d+):(\d+)\]")


def load_blocks(filename: str) -> list[dict]:
    raw = (output_dir / filename).read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{filename} is not valid JSON: {exc}") from None
    if not isinstance(data, list):
        raise SystemExit(f"{filename} must be a JSON list")
    blocks = []
    for entry in data:
        if not isinstance(entry, dict):
            raise SystemExit(f"{filename} contains a non-object entry")
        message_id = entry.get("message-id")
        if message_id != "R0801":
            raise SystemExit(
                f"{filename} carries analyzer diagnostic {message_id}: "
                f"{entry.get('message', '')}"
            )
        blocks.append(entry)
    return blocks


def identity(entry: dict) -> tuple[str, ...]:
    headers = tuple(header_pattern.findall(str(entry.get("message", ""))))
    if headers:
        return headers
    return (json.dumps(entry, sort_keys=True),)


fail_blocks = load_blocks("duplication_error.json")
fail_identities = {identity(entry) for entry in fail_blocks}
warn_blocks = [
    entry for entry in load_blocks("duplication.json") if identity(entry) not in fail_identities
]

(output_dir / "duplication_fail.json").write_text(json.dumps(fail_blocks, indent=2) + "\n")
(output_dir / "duplication_warning.json").write_text(json.dumps(warn_blocks, indent=2) + "\n")
(output_dir / "duplication_count.txt").write_text(f"{len(fail_blocks) + len(warn_blocks)}\n")
(output_dir / "duplication_fail_count.txt").write_text(f"{len(fail_blocks)}\n")
(output_dir / "duplication_warning_count.txt").write_text(f"{len(warn_blocks)}\n")
PY
    then
        print_error "pylint duplication output is not a valid finding list — refusing to treat it as zero findings"
        exit 1
    fi

    local fail_count=$(cat "$OUTPUT_DIR/duplication_fail_count.txt")
    local warn_count=$(cat "$OUTPUT_DIR/duplication_warning_count.txt")

    if [ "$fail_count" -gt 0 ]; then
        print_error "Found $fail_count duplication blocks of >= $PYLINT_FAIL_MIN_LINES similar lines"
        python3 - "$OUTPUT_DIR/duplication_fail.json" <<'PY'
import json
import re
import sys
from pathlib import Path

header_pattern = re.compile(r"==([^\s:]+):\[(\d+):(\d+)\]")
for entry in json.loads(Path(sys.argv[1]).read_text()):
    ranges = header_pattern.findall(str(entry.get("message", "")))
    if ranges:
        for name, start, end in ranges:
            # Pylint headers are zero-based and end-exclusive; display
            # one-based inclusive source lines.
            start_line = int(start) + 1
            end_line = int(end)
            span = end_line - start_line + 1
            print(f"  {name} source lines {start_line}-{end_line} (span {span} lines)")
    else:
        print(f"  {entry.get('path', 'unknown-path')}")
PY
    fi
    if [ "$warn_count" -gt 0 ]; then
        print_warning "Found $warn_count duplication blocks of $PYLINT_WARN_MIN_LINES-$((PYLINT_FAIL_MIN_LINES - 1)) similar lines"
    fi
    if [ "$fail_count" -eq 0 ] && [ "$warn_count" -eq 0 ]; then
        print_success "No code duplication found"
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
    export QS_RADON_HIGH_COMPLEXITY_CC="$RADON_HIGH_COMPLEXITY_CC"
    export QS_RADON_ERROR_COMPLEXITY_CC="$RADON_ERROR_COMPLEXITY_CC"
    export QS_LARGE_FILE_WARNING_LINES="$LARGE_FILE_WARNING_LINES"
    export QS_LARGE_FILE_ERROR_LINES="$LARGE_FILE_ERROR_LINES"
    export QS_VULTURE_MIN_CONFIDENCE="$VULTURE_MIN_CONFIDENCE"
    export QS_VULTURE_ERROR_CONFIDENCE="$VULTURE_ERROR_CONFIDENCE"
    export QS_PYLINT_WARN_MIN_LINES="$PYLINT_WARN_MIN_LINES"
    export QS_PYLINT_FAIL_MIN_LINES="$PYLINT_FAIL_MIN_LINES"

    python3 <<'PY'
from pathlib import Path
import json
import os
import re

root = Path(os.environ["QS_ROOT"]).resolve()
output_dir = Path(os.environ["QS_OUTPUT_DIR"])
json_output = Path(os.environ["QS_JSON_OUTPUT"])
status_output = Path(os.environ["QS_STATUS_OUTPUT"])
timestamp = os.environ["QS_TIMESTAMP"]

high_complexity_threshold = int(os.environ["QS_RADON_HIGH_COMPLEXITY_CC"])
error_complexity_threshold = int(os.environ["QS_RADON_ERROR_COMPLEXITY_CC"])
large_file_warning_threshold = int(os.environ["QS_LARGE_FILE_WARNING_LINES"])
large_file_error_threshold = int(os.environ["QS_LARGE_FILE_ERROR_LINES"])
vulture_min_confidence = int(os.environ["QS_VULTURE_MIN_CONFIDENCE"])
vulture_error_confidence = int(os.environ["QS_VULTURE_ERROR_CONFIDENCE"])
pylint_min_lines = int(os.environ["QS_PYLINT_WARN_MIN_LINES"])
pylint_error_lines = int(os.environ["QS_PYLINT_FAIL_MIN_LINES"])


def read_text_safe(filename: str) -> str:
    try:
        return (output_dir / filename).read_text()
    except OSError:
        return ""


def read_json_safe(filename: str, default):
    try:
        return json.loads((output_dir / filename).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def relative_path(path_value: str) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


# --- Dead code -----------------------------------------------------------
dead_code_fail = [line for line in read_text_safe("dead_code_fail.txt").splitlines() if line.strip()]
dead_code_warning = [
    line for line in read_text_safe("dead_code_warning.txt").splitlines() if line.strip()
]

# --- Complexity ----------------------------------------------------------
cyclomatic = read_json_safe("complexity_cc.json", {})
maintainability = read_json_safe("maintainability_mi.json", {})
raw_metrics = read_json_safe("raw_metrics.json", {})


def parse_complexity_rows(filename: str) -> list[dict]:
    rows = []
    for line in read_text_safe(filename).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        complexity, file_path, name = parts
        try:
            value = int(complexity)
        except ValueError:
            continue
        rows.append(
            {
                "module": name,
                "complexity": value,
                "file": relative_path(file_path),
            }
        )
    return rows


critical_functions = parse_complexity_rows("error_complexity_functions.txt")
high_functions = parse_complexity_rows("high_complexity_functions.txt")
high_complexity_count = sum(
    1
    for entries in cyclomatic.values()
    if isinstance(entries, list)
    for entry in entries
    if isinstance(entry, dict)
    and isinstance(entry.get("complexity"), (int, float))
    and not isinstance(entry.get("complexity"), bool)
    and entry.get("complexity", 0) >= high_complexity_threshold
    and entry.get("type") != "class"
)
error_complexity_count = len(critical_functions)

# --- Large files ---------------------------------------------------------
large_files_raw = read_text_safe("large_files.txt")
large_files_fail = []
large_files_warning = []
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
    entry = {"file": relative_path(parts[1].strip()), "lines": line_count}
    if line_count >= large_file_error_threshold:
        large_files_fail.append(entry)
    elif line_count >= large_file_warning_threshold:
        large_files_warning.append(entry)
large_files_fail.sort(key=lambda item: (-item["lines"], item["file"]))
large_files_warning.sort(key=lambda item: (-item["lines"], item["file"]))

# --- Duplication ---------------------------------------------------------
duplication_header_pattern = re.compile(r"==([^\s:]+):\[(\d+):(\d+)\]")


def describe_duplication(entry: dict) -> None:
    """Name the block's locations and its source span from the message headers.

    Pylint headers are zero-based and end-exclusive (``[0:20]`` is the first
    20 lines), so the displayed coordinates are converted to one-based
    inclusive source lines.
    """
    ranges = duplication_header_pattern.findall(str(entry.get("message", "")))
    entry["block_locations"] = [
        f"{name} source lines {int(start) + 1}-{end}" for name, start, end in ranges
    ]
    spans = [int(end) - int(start) for _, start, end in ranges]
    entry["span_lines"] = max(spans) if spans else None


observed_blocks = [
    entry
    for entry in read_json_safe("duplication.json", [])
    if isinstance(entry, dict) and entry.get("message-id") == "R0801"
]
fail_blocks = [
    entry
    for entry in read_json_safe("duplication_fail.json", [])
    if isinstance(entry, dict)
]
warn_blocks = [
    entry
    for entry in read_json_safe("duplication_warning.json", [])
    if isinstance(entry, dict)
]
for entry in (*fail_blocks, *warn_blocks, *observed_blocks):
    if isinstance(entry.get("path"), str):
        entry["path"] = relative_path(entry["path"])
    raw_locations = entry.get("locations")
    if isinstance(raw_locations, list):
        for location in raw_locations:
            if isinstance(location, dict) and isinstance(location.get("path"), str):
                location["path"] = relative_path(location["path"])
    describe_duplication(entry)

# --- Aggregation ---------------------------------------------------------
fail_count = (
    len(dead_code_fail)
    + len(critical_functions)
    + len(large_files_fail)
    + len(fail_blocks)
)
warning_count = (
    len(dead_code_warning)
    + len(high_functions)
    + len(large_files_warning)
    + len(warn_blocks)
)
exit_code = 1 if fail_count > 0 else 0

report = {
    "timestamp": timestamp,
    "thresholds": {
        "vulture": {
            "warn_min_confidence": vulture_min_confidence,
            "fail_min_confidence": vulture_error_confidence,
        },
        "complexity": {
            "warn_min_cc": high_complexity_threshold,
            "fail_min_cc": error_complexity_threshold,
        },
        "large_files": {
            "warn_min_lines": large_file_warning_threshold,
            "fail_min_lines": large_file_error_threshold,
        },
        "duplication": {
            "warn_min_similar_lines": pylint_min_lines,
            "fail_min_similar_lines": pylint_error_lines,
        },
    },
    "summary": {
        "dead_code_fail": len(dead_code_fail),
        "dead_code_warning": len(dead_code_warning),
        "complexity_fail": len(critical_functions),
        "complexity_warning": len(high_functions),
        "large_files_fail": len(large_files_fail),
        "large_files_warning": len(large_files_warning),
        "duplication_fail": len(fail_blocks),
        "duplication_warning": len(warn_blocks),
        "fail_total": fail_count,
        "warning_total": warning_count,
    },
    "fail_findings": {
        "dead_code": dead_code_fail,
        "complexity": critical_functions,
        "large_files": large_files_fail,
        "duplication": fail_blocks,
    },
    "warnings": {
        "dead_code": dead_code_warning,
        "complexity": high_functions,
        "large_files": large_files_warning,
        "duplication": warn_blocks,
    },
    "dead_code": {
        "raw_output": read_text_safe("vulture_raw.txt"),
    },
    "complexity": {
        "cyclomatic": cyclomatic,
        "maintainability": maintainability,
        "raw_metrics": raw_metrics,
    },
    "large_files": {
        "files": large_files_raw,
    },
    "duplication": {
        "observed": observed_blocks,
        "fail_blocks": fail_blocks,
        "warning_blocks": warn_blocks,
    },
}

status_payload = {
    "fail_count": fail_count,
    "warning_count": warning_count,
    "exit_code": exit_code,
    "dead_code_fail": len(dead_code_fail),
    "dead_code_warning": len(dead_code_warning),
    "complexity_fail": len(critical_functions),
    "complexity_warning": len(high_functions),
    "large_files_fail": len(large_files_fail),
    "large_files_warning": len(large_files_warning),
    "duplication_fail": len(fail_blocks),
    "duplication_warning": len(warn_blocks),
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
    export QS_VULTURE_MIN_CONFIDENCE="$VULTURE_MIN_CONFIDENCE"
    export QS_VULTURE_ERROR_CONFIDENCE="$VULTURE_ERROR_CONFIDENCE"
    export QS_PYLINT_WARN_MIN_LINES="$PYLINT_WARN_MIN_LINES"
    export QS_PYLINT_FAIL_MIN_LINES="$PYLINT_FAIL_MIN_LINES"

    python3 <<'PY'
from pathlib import Path
import json
import os

report = json.loads(Path(os.environ["QS_JSON_OUTPUT"]).read_text())
md_output = Path(os.environ["QS_MD_OUTPUT"])

high_complexity_threshold = int(os.environ["QS_RADON_HIGH_COMPLEXITY_CC"])
error_complexity_threshold = int(os.environ["QS_RADON_ERROR_COMPLEXITY_CC"])
large_file_warning_threshold = int(os.environ["QS_LARGE_FILE_WARNING_LINES"])
large_file_error_threshold = int(os.environ["QS_LARGE_FILE_ERROR_LINES"])
vulture_min_confidence = int(os.environ["QS_VULTURE_MIN_CONFIDENCE"])
vulture_error_confidence = int(os.environ["QS_VULTURE_ERROR_CONFIDENCE"])
pylint_similarity_lines = int(os.environ["QS_PYLINT_WARN_MIN_LINES"])
pylint_error_lines = int(os.environ["QS_PYLINT_FAIL_MIN_LINES"])

summary = report["summary"]
failures = report["fail_findings"]
warnings = report["warnings"]
fail_total = summary["fail_total"]
warning_total = summary["warning_total"]


def code_block(language: str, content: str) -> str:
    body = content.rstrip() if content else ""
    if not body:
        body = "[]" if language == "json" else "No findings."
    return f"```{language}\n{body}\n```"


def json_block(value) -> str:
    return code_block("json", json.dumps(value, indent=2))


def overall_verdict() -> str:
    if fail_total > 0:
        return "✗ Failing findings"
    if warning_total > 0:
        return "✓ Pass (warnings only)"
    return "✓ Pass"


def duplication_locations(entry: dict) -> str:
    locations = list(entry.get("block_locations") or [])
    if not locations:
        raw_locations = entry.get("locations")
        if isinstance(raw_locations, list):
            for location in raw_locations:
                if not isinstance(location, dict):
                    continue
                path = location.get("path", "unknown-path")
                line = location.get("line")
                locations.append(f"{path}:{line}" if line else str(path))
    if not locations:
        path = entry.get("path", "unknown-path")
        line = entry.get("line")
        locations.append(f"{path}:{line}" if line else str(path))
    return ", ".join(locations)


lines = [
    "# QuickScale Code Quality Report",
    "",
    f"**Generated:** {report['timestamp']}",
    "",
    "**Thresholds:** "
    f"CC >= {error_complexity_threshold} fails / {high_complexity_threshold}-{error_complexity_threshold - 1} warns; "
    f"files >= {large_file_error_threshold} lines fail / {large_file_warning_threshold}-{large_file_error_threshold - 1} warn; "
    f"duplication >= {pylint_error_lines} similar lines fails / {pylint_similarity_lines}-{pylint_error_lines - 1} warn; "
    f"vulture {vulture_error_confidence}% fails / {vulture_min_confidence}-{vulture_error_confidence - 1}% warns.",
    "",
    "## Summary",
    "",
    "| Metric | Findings | Threshold | Gate impact |",
    "|--------|----------|-----------|-------------|",
    f"| Dead code (>= {vulture_error_confidence}% confidence) | {summary['dead_code_fail']} | fails | {summary['dead_code_fail']} failing |",
    f"| Dead code ({vulture_min_confidence}-{vulture_error_confidence - 1}% confidence) | {summary['dead_code_warning']} | warns | advisory |",
    f"| Critical complexity (CC >= {error_complexity_threshold}) | {summary['complexity_fail']} | fails | {summary['complexity_fail']} failing |",
    f"| High complexity (CC {high_complexity_threshold}-{error_complexity_threshold - 1}) | {summary['complexity_warning']} | warns | advisory |",
    f"| Very large files (>= {large_file_error_threshold} lines) | {summary['large_files_fail']} | fails | {summary['large_files_fail']} failing |",
    f"| Large files ({large_file_warning_threshold}-{large_file_error_threshold - 1} lines) | {summary['large_files_warning']} | warns | advisory |",
    f"| Duplication (>= {pylint_error_lines} similar lines) | {summary['duplication_fail']} | fails | {summary['duplication_fail']} failing |",
    f"| Duplication ({pylint_similarity_lines}-{pylint_error_lines - 1} similar lines) | {summary['duplication_warning']} | warns | advisory |",
    f"| **Total** | **{fail_total + warning_total}** | | **{overall_verdict()}** |",
    "",
    "---",
    "",
    f"## Failing Findings ({fail_total})",
    "",
]

if fail_total == 0:
    lines.append("✓ None.")
else:
    for entry in failures["dead_code"]:
        lines.append(f"- [dead code] {entry}")
    for entry in failures["complexity"]:
        lines.append(
            f"- [complexity] {entry['module']} is {entry['complexity']} ({entry['file']})"
        )
    for entry in failures["large_files"]:
        lines.append(
            f"- [large file] {entry['file']} has {entry['lines']} lines"
        )
    for entry in failures["duplication"]:
        span = entry.get("span_lines")
        span_note = f" (span {span} lines)" if span else ""
        lines.append(
            f"- [duplication] {duplication_locations(entry)}{span_note} "
            f"{entry.get('message', 'duplicate-code').splitlines()[0]}"
        )

lines.extend(
    [
        "",
        "---",
        "",
        f"## Warnings ({warning_total})",
        "",
    ]
)

if warning_total == 0:
    lines.append("✓ None.")
else:
    for entry in warnings["dead_code"]:
        lines.append(f"- [dead code] {entry}")
    for entry in warnings["complexity"]:
        lines.append(
            f"- [complexity] {entry['module']} is {entry['complexity']} ({entry['file']})"
        )
    for entry in warnings["large_files"]:
        lines.append(
            f"- [large file] {entry['file']} has {entry['lines']} lines"
        )
    for entry in warnings["duplication"]:
        span = entry.get("span_lines")
        span_note = f" (span {span} lines)" if span else ""
        lines.append(
            f"- [duplication] {duplication_locations(entry)}{span_note} "
            f"{entry.get('message', 'duplicate-code').splitlines()[0]}"
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
        json_block(report["duplication"]["observed"]),
        "",
        "---",
        "",
        "## Tool Details",
        "",
        "- vulture: Dead code detection",
        f"- radon: Complexity metrics (CC >= {high_complexity_threshold} warning, CC >= {error_complexity_threshold} failure)",
        f"- pylint: Code duplication (minimum {pylint_similarity_lines} similar lines; >= {pylint_error_lines} fails)",
        f"- Custom: Large file detection ({large_file_warning_threshold}+ warning, {large_file_error_threshold}+ failure)",
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
    local dead_code_fail=$(cat "$OUTPUT_DIR/dead_code_fail_count.txt" 2>/dev/null || echo "0")
    local dead_code_warning=$(cat "$OUTPUT_DIR/dead_code_warning_count.txt" 2>/dev/null || echo "0")
    local error_complexity_count=$(cat "$OUTPUT_DIR/error_complexity_count.txt" 2>/dev/null || echo "0")
    local high_complexity_count=$(cat "$OUTPUT_DIR/high_complexity_count.txt" 2>/dev/null || echo "0")
    local large_files_warning=$(cat "$OUTPUT_DIR/large_files_warning_count.txt" 2>/dev/null || echo "0")
    local large_files_error=$(cat "$OUTPUT_DIR/large_files_error_count.txt" 2>/dev/null || echo "0")
    local duplication_fail=$(cat "$OUTPUT_DIR/duplication_fail_count.txt" 2>/dev/null || echo "0")
    local duplication_warning=$(cat "$OUTPUT_DIR/duplication_warning_count.txt" 2>/dev/null || echo "0")

    eval "$(
        python3 - "$STATUS_OUTPUT" <<'PY'
import json
import shlex
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
for key in ("fail_count", "warning_count", "exit_code"):
    print(f"{key.upper()}={shlex.quote(str(data.get(key, '')))}")
PY
    )"

    echo ""
    echo "Summary:"
    echo "  - Dead code (100% confidence): $dead_code_fail"
    echo "  - Dead code (80-99% confidence): $dead_code_warning"
    echo "  - High complexity (CC >= $RADON_HIGH_COMPLEXITY_CC): $high_complexity_count"
    echo "  - Critical complexity (CC >= $RADON_ERROR_COMPLEXITY_CC): $error_complexity_count"
    echo "  - Large files ($LARGE_FILE_WARNING_LINES-$((LARGE_FILE_ERROR_LINES - 1)) lines): $large_files_warning"
    echo "  - Very large files (>= $LARGE_FILE_ERROR_LINES lines): $large_files_error"
    echo "  - Duplication blocks (fail): $duplication_fail"
    echo "  - Duplication blocks (warn): $duplication_warning"
    echo ""
    echo "Reports generated:"
    echo "  - JSON: $JSON_OUTPUT"
    echo "  - Markdown: $MD_OUTPUT"
    echo "  - Gate status: $STATUS_OUTPUT"
    echo ""

    if [ "$FAIL_COUNT" -gt 0 ]; then
        print_error "Quality gate FAILED: $FAIL_COUNT fail-column findings must be fixed."
        exit 1
    fi

    if [ "$WARNING_COUNT" -gt 0 ]; then
        print_warning "Quality gate passed with $WARNING_COUNT warn-column findings (advisory)."
    else
        print_success "Quality gate passed with no findings."
    fi
    exit 0
}

# Run main function
main "$@"
