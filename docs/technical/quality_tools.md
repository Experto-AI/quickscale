# Code Quality Analysis Tools

QuickScale provides a comprehensive code quality analysis script that goes beyond basic linting and type checking.

## Running Quality Analysis

```bash
./scripts/check_quality.sh
```

## What Gets Analyzed

### 1. Dead Code Detection (vulture)

Identifies unused:
- Imports
- Functions and methods
- Classes
- Variables and attributes
- Function parameters

**Thresholds:**
- Minimum confidence: 80% (high confidence findings only)
- Excludes: Django framework patterns (Meta classes, migrations)

**Example findings:**
```
quickscale_cli/src/utils/helpers.py:42: unused function 'format_date' (80% confidence)
quickscale_core/src/models.py:15: unused import 'datetime' (100% confidence)
```

### 2. Complexity Metrics (radon)

**Cyclomatic Complexity (CC):**
- Measures code complexity based on decision points
- Thresholds:
  - **A (1-5):** Simple - no action needed
  - **B (6-10):** Moderate - acceptable
  - **C (11-20):** High - consider refactoring
  - **D (21-30):** Very high - refactor recommended
  - **E (31+):** Extremely high - refactor required

**Maintainability Index (MI):**
- Composite metric combining complexity, LOC, and Halstead volume
- Grades:
  - **A (20-100):** Highly maintainable
  - **B (10-19):** Moderately maintainable
  - **C (0-9):** Difficult to maintain

**Example findings:**
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

Identifies files that may benefit from splitting:
- **Warning:** 500-1000 lines
- **Critical:** >1000 lines

**Why it matters:**
- Large files are harder to understand and navigate
- Indicates potential Single Responsibility Principle violations
- Makes code review more difficult

**Example findings:**
```
1065    quickscale_cli/src/commands/module_commands.py
725     quickscale_cli/src/utils/railway_utils.py
```

### 4. Code Duplication (pylint)

Detects similar code blocks across files:
- Minimum: 6 similar lines
- Ignores: comments, docstrings, imports

**Why it matters:**
- Violates DRY (Don't Repeat Yourself) principle
- Increases maintenance burden
- Bugs must be fixed in multiple places

**Example findings:**
```json
{
  "message": "Similar lines in 2 files",
  "locations": [
    {"path": "file1.py", "line": 42},
    {"path": "file2.py", "line": 156}
  ]
}
```

## Output Formats

### JSON Output (.quickscale/quality_report.json)

Machine-readable format for:
- CI/CD integration
- Automated tooling
- Trend analysis over time

```json
{
  "timestamp": "2025-12-07T...",
  "summary": {
    "dead_code_issues": 5,
    "high_complexity_functions": 3,
    "large_files_warning": 2,
    "large_files_error": 1,
    "duplication_blocks": 4,
    "total_issues": 15
  },
  "dead_code": { ... },
  "complexity": { ... },
  "large_files": { ... },
  "duplication": { ... }
}
```

### Markdown Output (.quickscale/quality_report.md)

Human-readable format optimized for:
- LLM consumption (Claude, GPT)
- Code review discussions
- Documentation

Contains:
- Executive summary table
- Detailed findings per category
- Actionable recommendations
- Priority-ranked action items

## Exit Codes

- **0:** All quality checks passed
- **1:** Warnings found (review recommended)
- **2:** Critical issues found (action required - files >1000 lines)

## Integration with Existing Tools

The quality analysis script complements existing tools:

| Tool | Purpose | When to Run |
|------|---------|-------------|
| `./scripts/lint.sh` | Format + basic linting (ruff) | Before every commit |
| `./scripts/check_ci_locally.sh` | Full CI checks (lint + type + test) | Before push to GitHub |
| `./scripts/check_quality.sh` | Deep quality analysis | Weekly / before major releases |

## Workflow Recommendations

1. **Daily development:** Use `lint.sh` for quick fixes
2. **Before push:** Run `check_ci_locally.sh` to ensure CI will pass
3. **Weekly health check:** Run `check_quality.sh` to catch technical debt early
4. **Before releases:** Review quality reports and address critical issues

## Interpreting Results

### When to Refactor

**Immediate action required:**
- Files >1000 lines
- Functions with CC >20
- Duplicate code in critical paths

**Plan for next sprint:**
- Files 500-1000 lines
- Functions with CC 11-20
- Confirmed dead code (not framework-related)

**Monitor but don't block:**
- Dead code with <80% confidence
- Files approaching 500 lines
- Functions with CC 6-10

## Configuration

All tools are configured in root-level files:

- **vulture:** `.vulture.toml`
- **pylint:** `pyproject.toml` (tool.pylint sections)
- **radon:** CLI arguments in script (no config file)

Adjust thresholds based on team preferences and project maturity.

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
