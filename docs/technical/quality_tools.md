# Code Quality Analysis Tools

QuickScale provides a comprehensive quality gate that goes beyond basic linting and type checking. `make quality` runs four analyzers, preserves the raw findings in its report artifacts, and applies fixed fail/warn thresholds with no accepted-debt baseline, no waiver ledger, and no monotonicity helper.

## Running Quality Analysis

```bash
make quality
```

## What Gets Analyzed

Every metric has exactly two bands: a **fail** column that exits non-zero and a **warn** band that prints and still exits 0. Fail-column findings are named with their function, file, or block and value.

| Metric | Fails (non-zero exit) | Warns only |
|---|---|---|
| Dead code (vulture) | 100% confidence | 80-99% confidence |
| Cyclomatic complexity (radon) | CC >= 21 | CC 11-20 |
| File length | >= 800 lines | 500-799 lines |
| Duplication (pylint R0801) | a block of >= 20 similar lines | blocks of 6-19 lines |

### 1. Dead Code Detection (vulture)

Identifies unused imports, functions, methods, classes, variables, and function parameters at 80% confidence or higher.

**Thresholds:**
- Fail: any finding at 100% confidence
- Warn: findings at 80-99% confidence
- Excludes: Django framework patterns (Meta classes, migrations)

**Example findings:**
```
quickscale_cli/src/utils/helpers.py:42: unused function 'format_date' (80% confidence)
quickscale_core/src/models.py:15: unused import 'datetime' (100% confidence)
```

A 100% dead-code finding is code that can never run, so it fails the gate. The lower band is advisory.

### 2. Complexity Metrics (radon)

**Cyclomatic Complexity (CC):**
- Measures code complexity based on decision points
- Grades:
  - **A (1-5):** Simple
  - **B (6-10):** Moderate
  - **C (11-20):** High — warning band
  - **D (21-30):** Very high — failure band
  - **E (31+):** Extremely high — failure band

Functions at CC >= 21 are reported as failures naming the function and its value. The CC 11-20 tier stays a warning. Nested functions are included through Radon's closure reporting; Radon class aggregates are not functions and are not part of the failure count. Radon does not report methods of classes declared inside functions, so those methods remain outside this measurement by analyzer limitation.

**Maintainability Index (MI):**
- Composite metric combining complexity, LOC, and Halstead volume
- Grades:
  - **A (20-100):** Highly maintainable
  - **B (10-19):** Moderately maintainable
  - **C (0-9):** Difficult to maintain

MI is collected in the report but has no gate threshold (it is out of scope for the fixed-threshold lane).

**Example finding:**
```json
{
  "quickscale_cli/commands/module_commands.py": [
    {
      "name": "install_module",
      "complexity": 15,
      "lineno": 150,
      "rank": "C"
    }
  ]
}
```

### 3. Large File Detection

- **Fail:** >= 800 lines
- **Warn:** 500-799 lines

A file at or above 800 lines is reported as a failure naming the file and its line count. Line counts include a final physical line that has no trailing newline, so an exactly-800-line file without a terminal newline cannot slip past the gate.

**Example findings:**
```
1065    quickscale_cli/src/commands/module_commands.py
725     quickscale_cli/src/utils/railway_utils.py
```

### 4. Code Duplication (pylint)

Detects similar code blocks across files, ignoring comments, docstrings, and imports.

- **Fail:** a block of >= 20 similar lines
- **Warn:** blocks of 6-19 similar lines

The gate runs pylint's `duplicate-code` checker twice, with `--min-similarity-lines` set one below each inclusive floor because pylint compares strictly greater: option 5 for the 6-line warn floor and option 19 for the 20-line fail line. Fail-column blocks are exactly the blocks pylint reports at 19 (>= 20 similar lines); every other block observed at 5 (>= 6 similar lines) is a warning. Each reported block is named by its participating locations and source span, in one-based inclusive source lines (pylint's message ranges are zero-based and end-exclusive). The 20-line bar follows the block-size practice of CPD-style tools.

**Example finding** (`quality_report.json`):
```json
{
  "message-id": "R0801",
  "message": "Similar lines in 2 files\n==pkg.a:[10:31]\n==pkg.b:[44:65]\n...",
  "path": "pkg/a.py",
  "line": 10,
  "endLine": 30
}
```

## Output Formats

### JSON Output (.quickscale/quality_report.json)

Machine-readable report for CI/CD integration, automated tooling, trend analysis, and raw finding preservation:

```json
{
  "timestamp": "2026-10-05T...",
  "thresholds": {
    "vulture": {"warn_min_confidence": 80, "fail_min_confidence": 100},
    "complexity": {"warn_min_cc": 11, "fail_min_cc": 21},
    "large_files": {"warn_min_lines": 500, "fail_min_lines": 800},
    "duplication": {"warn_min_similar_lines": 6, "fail_min_similar_lines": 20}
  },
  "summary": {
    "dead_code_fail": 0,
    "dead_code_warning": 4,
    "complexity_fail": 0,
    "complexity_warning": 12,
    "large_files_fail": 0,
    "large_files_warning": 5,
    "duplication_fail": 0,
    "duplication_warning": 18,
    "fail_total": 0,
    "warning_total": 39
  },
  "fail_findings": {
    "dead_code": [],
    "complexity": [],
    "large_files": [],
    "duplication": []
  },
  "warnings": { "...": "same shape as fail_findings" },
  "dead_code": {"raw_output": "..."},
  "complexity": {"cyclomatic": {}, "maintainability": {}, "raw_metrics": {}},
  "large_files": {"files": "..."},
  "duplication": {"observed": [], "fail_blocks": [], "warning_blocks": []}
}
```

### Markdown Output (.quickscale/quality_report.md)

Human-readable report optimized for review discussions and LLM consumption. Contains the thresholds, a per-metric summary table, the failing findings and warnings lists, and the raw analyzer output per category.

### Gate Status Output (.quickscale/quality_gate_status.json)

Compact machine-readable gate result:

```json
{
  "fail_count": 0,
  "warning_count": 39,
  "exit_code": 0,
  "dead_code_fail": 0,
  "dead_code_warning": 4,
  "complexity_fail": 0,
  "complexity_warning": 12,
  "large_files_fail": 0,
  "large_files_warning": 5,
  "duplication_fail": 0,
  "duplication_warning": 18
}
```

## Exit Codes

- **0:** No fail-column finding; warn-column findings may be present and are printed
- **1:** At least one fail-column finding, missing analyzer dependencies, or unparseable analyzer output

## Quality Thresholds Gate {#quality-thresholds-gate}

`make quality` is a fixed-threshold gate. It never reads a baseline file, never consults a waiver, and never compares against Git history. The rules are:

1. Each analyzer runs once per invocation; the report artifacts are written only after all four complete.
2. A finding in a fail column exits 1 and is named in stdout, the Markdown report, and `quality_gate_status.json`.
3. A finding in a warn band prints and leaves the exit code at 0.
4. An analyzer failure is a hard failure, never zero findings: a non-zero analyzer status beyond "findings present", unparseable output, or an analyzer diagnostic object aborts the run with exit 1 and no fresh verdict artifacts.
5. The only way to clear a fail-column finding is to fix it. There is no allowlist and no inline waiver.

The duplication checker is the one analyzer run twice: the 5-option pass feeds the warn band (and the `duplication.observed` list in the report), and the 19-option pass defines the fail column. A block reported by the fail pass fails; the remaining observed blocks warn. Both boundaries are inclusive in policy — exactly 6 similar lines warns, exactly 20 fails — while pylint's option is exclusive, hence the option values being one below each floor.

## Integration with Existing Tools

| Command | Purpose | When to Run |
|---------|---------|-------------|
| `make lint` | Format + basic linting (ruff) | Before every commit |
| `make ci` | Primary local development checks (lint + typecheck + unit tests; integration when PostgreSQL available) | Before push to GitHub |
| `make quality` | Deep quality analysis (dead code, complexity, duplication, file length) with the fixed thresholds; a registered gate in `make ci` | Every local CI run, or directly for a quality-only pass |

## Workflow Recommendations

1. **Daily development:** Use `make lint` for quick fixes
2. **Before push:** Run `make ci` to run primary local development checks before pushing
3. **Quality-only pass:** Run `make quality` to check the thresholds without the rest of local CI
4. **Before releases:** Review quality reports and address failing findings

## Interpreting Results

**Immediate action required (fail column):**
- Functions with CC >= 21
- Files at or above 800 lines
- Duplication blocks of 20 or more similar lines
- Dead code at 100% confidence

**Plan for next sprint (warn band):**
- Functions with CC 11-20
- Files of 500-799 lines
- Duplication blocks of 6-19 similar lines
- Dead code at 80-99% confidence

## Configuration

All tools are configured in root-level files:

- **vulture:** `.vulture.toml`
- **pylint:** `pyproject.toml` (tool.pylint sections)
- **radon:** CLI arguments in script (no config file)

Thresholds live in `scripts/check_quality.sh` at the top of the file. `QUALITY_OUTPUT_DIR` overrides the artifact directory (default `.quickscale/`). The test suite points each run at a temporary directory, so tests never write repository artifacts.

## Excluding Files

To exclude specific files from analysis, update:

```toml
# .vulture.toml
exclude = [
    "**/tests/",
    "**/migrations/",
    "path/to/legacy/code.py",
]
```

```toml
# pyproject.toml
[tool.pylint.main]
ignore = ["tests", "migrations", "legacy_module"]
```
