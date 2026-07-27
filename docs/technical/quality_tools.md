# Code Quality Analysis Tools

QuickScale provides a comprehensive, baseline-aware quality gate that goes beyond basic linting and type checking. `make quality` runs the baseline monotonicity gate first, then preserves the raw findings in its report artifacts, and compares those findings against the tracked accepted-debt baseline in `scripts/quality_baseline.json`.

## Running Quality Analysis

```bash
make quality
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
- **Warning:** 500-799 lines
- **Critical:** >=800 lines

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
- Raw finding preservation, even when the gate passes against baseline

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
  "baseline": { ... },
  "regressions": { ... },
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

### Gate Status Output (.quickscale/quality_gate_status.json)

Compact machine-readable summary of the baseline gate result:
- Baseline load status and any baseline error
- Warning regression count
- Critical regression count
- Total regression count

## Exit Codes

- **0:** No warning or critical regressions beyond the tracked baseline; monotonicity gate passed
- **1:** Warning regressions found, the baseline file could not be loaded, or the baseline monotonicity gate failed (policy violation or prerequisite error)
- **2:** Critical regressions found

> **Note:** When the baseline monotonicity gate (SA121) fails, `make quality`
> exits 1 regardless of whether the helper reported exit 1 or exit 2.  The
> helper's detailed exit code is preserved in the diagnostic output.

## Integration with Existing Tools

The quality analysis script complements existing tools:

| Command | Purpose | When to Run |
|---------|---------|-------------|
| `make lint` | Format + basic linting (ruff) | Before every commit |
| `make ci` | Primary local development checks (lint + typecheck + unit tests; integration when PostgreSQL available) | Before push to GitHub |
| `make quality` | Deep quality analysis (dead code, complexity, duplication) + baseline monotonicity gate | Weekly / before major releases |

## Workflow Recommendations

1. **Daily development:** Use `make lint` for quick fixes
2. **Before push:** Run `make ci` to run primary local development checks before pushing
3. **Weekly health check:** Run `make quality` to catch technical debt early
4. **Before releases:** Review quality reports and address critical issues

## Interpreting Results

### When to Refactor

**Immediate action required:**
- Files >=800 lines
- Functions with CC >20
- Duplicate code in critical paths

**Plan for next sprint:**
- Files 500-799 lines
- Functions with CC 11-20
- Confirmed dead code (not framework-related)

**Monitor but don't block:**
- Dead code with <80% confidence
- Files approaching 500 lines
- Functions with CC 6-10

## Baseline Monotonicity Gate (SA121)

The quality baseline monotonicity gate enforces the shrink-only policy for
`scripts/quality_baseline.json`.  It runs as the first step inside
`make quality`, before any analyzer starts.

### How It Works

The helper (`scripts/check_quality_baseline_monotonicity.py`) compares every
ceiling in the current baseline file against the blob at the merge-base commit
in Git.  Any increase requires a matching structured waiver in
`scripts/quality_waivers.json` or the gate fails.

```bash
# Run standalone (used by make quality internally)
QUALITY_BASELINE_BASE_REF=v87 poetry run python scripts/check_quality_baseline_monotonicity.py

# Or with an explicit ref
poetry run python scripts/check_quality_baseline_monotonicity.py --base-ref v87
```

### Comparison Scope

Every increase in the following values requires a waiver:

| Section | Key | Compared value |
|---------|-----|----------------|
| `dead_code` | Per normalized message | Occurrence count (multiplicity) |
| `complexity` | Per `path::symbol` key | `max_complexity` |
| `large_files` | Per file path | `max_lines` |
| `duplication` | Global | `allowed_blocks` |

A missing base key is treated as 0 (any current value > 0 is an increase).
Deleted, reduced, or unchanged entries pass without action.  A rename is
modelled as delete plus new-exemption: the old key disappears (pass) and the
new key appears as an increase (requires a waiver if > 0).

### Baseline File Schema

`scripts/quality_baseline.json` must satisfy this exact schema.  Every field is
required unless marked optional; extra fields are tolerated but ignored.

```json
{
  "schema_version": 1,
  "dead_code": {
    "allowed_messages": ["string", "..."]
  },
  "complexity": {
    "allowed_functions": {
      "file::symbol": {
        "file": "canonical/repo/relative/path.py",
        "symbol": "function_or_method_name",
        "type": "function|method|class",
        "max_complexity": 11
      }
    }
  },
  "large_files": {
    "allowed_files": {
      "canonical/repo/relative/path.py": {
        "max_lines": 500
      }
    }
  },
  "duplication": {
    "allowed_blocks": 0,
    "allowed_block_identities": ["optional, length equals allowed_blocks"]
  }
}
```

Field-level rules:

- **`schema_version`** — strict non-bool `int`, exactly `1`.  A `bool` value is
  rejected (Python `bool` subclasses `int` but is explicitly excluded).
- **`dead_code.allowed_messages`** — list of non-empty strings.  Multiplicity
  (occurrence count of each distinct message) is the compared value.  Empty
  strings are rejected; duplicates are valid and simply raise multiplicity.
- **`complexity.allowed_functions`** — dict mapping canonical `file::symbol`
  keys to records with `file` (non-empty repo-relative POSIX path), `symbol`
  (non-empty), `type` (`function`/`method`/`class`), and `max_complexity`
  (strict non-negative non-bool `int`).  Paths are validated by a strict
  canonical-path checker that rejects absolute paths, Windows
  backslashes/drive letters, empty/dot/dotdot segments, repeated separators,
  leading/trailing whitespace, and surrogate/control characters.
- **`large_files.allowed_files`** — dict mapping repo-relative POSIX paths
  (same strict path validation) to records with `max_lines` (strict
  non-negative non-bool `int`).
- **`duplication.allowed_blocks`** — strict non-negative non-bool `int`.
- **`duplication.allowed_block_identities`** — optional; when present, a list
  of non-empty strings whose length exactly equals `allowed_blocks`.

The helper builds validated ceiling indexes (`dict[str, int]` keyed by
canonical key) from the merge-base and current baselines after structural
validation, and compares those indexes directly.  It never applies
`.get(..., 0)` to malformed input — a value that fails strict type/range
validation exits 2 with a `SCHEMA_ERROR` envelope rather than defaulting.

### Base-Ref Precedence

The merge-base is resolved in this order (first match wins):

1. `--base-ref` CLI argument — explicit manual override
2. `QUALITY_BASELINE_BASE_REF` environment variable — local CI / ad-hoc
3. `GITHUB_BASE_REF` environment variable — GitHub Actions PR context (tries
   `origin/<branch>` first, then local `<branch>`)
4. Local `v87` tag — fallback for local development

### Required History

The helper reads the base baseline from the local Git object store.  The
repository must have the necessary history and tags (v87) available.  There
is **no automatic fetch** and **no fallback** to `HEAD^` — if the merge-base
commit does not contain `scripts/quality_baseline.json`, the gate fails with
exit 2.  A missing *waiver* file is tolerated and treated as an empty ledger
(initial-rollout allowance only).

`QUALITY_BASELINE_FILE` may override the current-baseline file path, but the
merge-base side of the comparison always reads the canonical
`scripts/quality_baseline.json` path from the Git tree.

### Waiver Schema & Lifecycle

Waivers are stored in `scripts/quality_waivers.json`:

```json
{
  "schema_version": 1,
  "waivers": [
    {
      "waiver_id": "W001",
      "entry_key": "complexity:path/to/file.py::function_name",
      "base_ceiling": 12,
      "ceiling": 13,
      "owner": "user@example.com",
      "reason": "Brief justification",
      "expires_on": "YYYY-MM-DD",
      "decision_ref": "quality-baseline-monotonicity"
    }
  ]
}
```

Each waiver must use the exact canonical `entry_key` format matching the
monotonicity diagnostic key.  The helper's ``_parse_entry_key`` rejects any
key that does not match its section's strict canonical syntax:

- ``dead_code:allowed_messages:<nonempty-msg>:multiplicity`` — the message
  between the prefix and ``:multiplicity`` suffix must be non-empty.
- ``complexity:<safe-repo-path>::<nonempty-symbol>`` — exactly one ``::``
  separator between a validated repo-relative path and a non-empty symbol.
  Extra or missing separators are rejected.  The path component is validated
  by the same ``_validate_repo_relative_path`` used during baseline loading.
- ``large_files:<safe-repo-path>`` — a validated repo-relative path with no
  extra ``:`` characters.
- ``duplication:allowed_blocks`` — exact literal match only.

Waivers whose ``entry_key`` fails parsing are assigned the ``malformed``
state before any lifecycle matching (orphan/stale/active) is attempted.

Key fields:

- **`base_ceiling`** — the value at the merge-base (used for stale-waiver
  detection: a mismatch is a hard failure and the violation remains unresolved)
- **`ceiling`** — the maximum allowed current value; if the observed value
  exceeds this ceiling, the waiver does not resolve the violation
- **`expires_on`** — strict ASCII YYYY-MM-DD UTC date
  (``[0-9]{4}-[0-9]{2}-[0-9]{2}``, validated with `fullmatch` before
  ``date.fromisoformat``); Unicode digit characters (e.g. fullwidth
  ``２０２６-０１-０１``) are rejected.  Expired waivers
  (``expires_on < today in UTC``) are assigned the ``expired`` state and do
  not resolve violations
- **`decision_ref`** — exact Markdown heading anchor (`{#anchor-name}`) or
  HTML anchor (`<a id="anchor-name">`) in `docs/technical/decisions.md`;
  substring text matching is not accepted

### Waiver Lifecycle States

State precedence for each ledger row (first match wins):

1. **malformed** — per-row schema validation failure (missing fields, invalid types, unresolved `decision_ref`)
2. **duplicate** — `waiver_id` or `entry_key` appears more than once; all copies are disqualified
3. **expired** — `expires_on < today` (UTC date comparison)
4. **orphan** — `entry_key` has no corresponding increase (no-op)
5. **stale_base** — `base_ceiling` does not match the merge-base value
6. **over_ceiling** — current value exceeds the waiver's `ceiling`
7. **active** — all checks pass; waiver covers the increase

| State | Meaning | Gate Impact |
|-------|---------|-------------|
| `active` | Waiver is valid and covers the increase | Non-blocking |
| `stale_base` | `base_ceiling` does not match the merge-base value — violation remains unresolved | Hard fail — verdict is `violation` |
| `over_ceiling` | Current value exceeds `ceiling` — violation remains unresolved | Hard fail — verdict is `violation` |
| `malformed` | Missing required fields, invalid types, or invalid `decision_ref` — violation remains unresolved | Hard fail — verdict is `violation` |
| `expired` | `expires_on` has passed (UTC date < today) — violation remains unresolved | Hard fail — verdict is `violation` |
| `orphan` | Waiver's `entry_key` has no corresponding violation (no-op) | Hard fail — verdict is `violation` |
| `duplicate` | Duplicate `waiver_id` or `entry_key` — all copies are disqualified from matching violations | Hard fail — verdict is `violation` |

All non-`active` states are blocking.  Every ledger row produces exactly one
evaluation; `active` is the only non-blocking outcome.

### Error Envelope

When a schema or prerequisite error prevents the comparison, the helper writes
a deterministic error envelope to ``.quickscale/quality_baseline_policy.json``:

```json
{
  "schema_version": 1,
  "verdict": "error",
  "error": {
    "code": "SCHEMA_ERROR",
    "source": "current_baseline",
    "path": "dead_code.allowed_messages",
    "message": "dead_code.allowed_messages must be a list of strings"
  },
  "diagnostics": []
}
```

Canonical source labels:
- ``merge_base_baseline`` — the blob from the merge-base commit
- ``current_baseline`` — the live baseline file
- ``waiver_ledger`` — the waiver file
- ``git`` — Git resolution failure (merge-base resolution)
- ``main`` — unexpected handler error

The helper prints a single `ERROR:` line to stderr (no Python traceback) and
exits 2.  The shell script maps exit 2 to `make quality` exit 1.

### Canonical Diagnostic Record

The authoritative diagnostic feed is the ``diagnostics`` list in
``quality_baseline_policy.json``.  Every diagnostic entry carries the exact
13-key canonical set: ``error_code``, ``section``, ``canonical_key``,
``old_value``, ``new_value``, ``waiver_id``, ``waiver_status``,
``waiver_base_ceiling``, ``waiver_ceiling``, ``waiver_file``,
``decision_ref``, ``waiver_index``, ``duplicate_kinds``.

All 13 keys are always present.  Unavailable values are ``null`` and
``duplicate_kinds`` is a deterministic list (empty when no duplicate
dimensions exist).  This list is sorted and identical across all four
consumers:

1. ``quality_baseline_policy.json`` — ``diagnostics``
2. ``quality_report.json`` — ``monotonicity.diagnostics``
3. ``quality_gate_status.json`` — ``monotonicity_diagnostics``
4. ``quality_report.md`` — fenced JSON block after ``### Diagnostics``

The shell failure summary (printed to stdout when the monotonicity gate fails)
also reads from ``diagnostics`` — the same canonical 13-key records.  No raw
``waiver_evaluations`` dicts are serialised to stdout or the policy artifact.
Waiver lifecycle entries appear as canonical diagnostic records with
``waiver_id`` and ``waiver_status`` fields alongside the standard 13-key set.

``violations`` and ``unresolved`` are compatibility subsets of the same
canonical records (same shape, same keys), filtered to include only entries
with actual increase data (``error_code`` is not null).

### UTC Boundary

All expiry comparisons use ``datetime.now(UTC).date()``.  The waiver
``expires_on`` date is compared against today's **UTC** date — not local time.
A waiver whose ``expires_on == today`` remains active even when the system
timezone offset would place the local date on the following or previous day.

### Shell Cleanup on Failure

When the helper exits non-zero (exit 1 or exit 2), ``check_quality.sh``:

1. Preserves ``.quickscale/quality_baseline_policy.json`` (policy artifact)
2. Removes stale success artifacts: ``quality_report.json``,
   ``quality_report.md``, ``quality_gate_status.json``
3. Aborts without running analyzers (no ``Analyzing …`` output)
4. Exits 1 (the shell's exit code is always 1 regardless of the helper's
   more detailed exit 1 vs exit 2 distinction)

### Exit Codes

Integrated into `make quality`:

| Helper exit | `make quality` exit | Behavior |
|-------------|-------------------|----------|
| 0 (pass) | Normal exit (0/1/2) | Proceeds with full analysis; monotonicity verdict added to reports |
| 1 (violation) | 1 | Prints diagnostic summary, preserves policy artifact, clears stale success reports, aborts without running analyzers |
| 2 (error) | 1 | Same as exit 1 — prerequisite failure (missing ref, bad baseline, git error) |

When the gate passes, the verdict and merge-base metadata are included in the
generated reports:

- **`quality_report.json`** — top-level `"monotonicity"` key with full verdict,
  violation list, waiver evaluations, and summary
- **`quality_gate_status.json`** — additive fields `monotonicity_verdict`,
  `monotonicity_merge_base`, `monotonicity_base_ref`,
  `monotonicity_waiver_count` (existing keys and readers are unaffected)
- **`quality_report.md`** — "Baseline Monotonicity Gate (SA121)" section with
  verdict, merge-base, waiver count, and violation details

### Remediation

If the gate reports unresolved violations:

1. **Check the merge-base ref** — verify `QUALITY_BASELINE_BASE_REF` or
   `--base-ref` points to the intended baseline
2. **Identify the increased ceiling** — the diagnostic names the key, old
   value, new value, and affected section
3. **Reduce the ceiling** — if the increase is accidental, revert the baseline
   edit and re-run
4. **Add a waiver** — if the increase is intentional (e.g. a known refactor),
   create a waiver in `scripts/quality_waivers.json` with the correct
   `entry_key`, `base_ceiling`, and `ceiling`
5. **Re-run** — with the waiver in place, the gate should pass

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
