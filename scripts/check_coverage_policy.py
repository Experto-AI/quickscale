#!/usr/bin/env python3
r"""
Coverage policy checker for QuickScale.

Validates coverage data against the repository's dual-threshold policy:

  - **Package-aware equal-weight mean**: each recognised top-level package
    (``quickscale_core``, ``quickscale_cli``) is scored independently, then
    the two package percentages are averaged with equal weight.  A small
    package at low coverage cannot hide behind a large package at high
    coverage because the aggregation is per-package, not per-statement.
  - **Per-file minimum**: each measured file must reach 80%.

Accepts the ``coverage.json`` output from ``coverage json`` (or any
JSON file with the same schema) and optional threshold overrides.

Only files under recognised package trees (``quickscale_core/``,
``quickscale_cli/``) are accepted; any unrecognised file path causes a
hard error (exit 2).

Usage
-----
    poetry run python scripts/check_coverage_policy.py coverage.json
    poetry run python scripts/check_coverage_policy.py coverage.json \
        --mean-threshold 85 --per-file-threshold 75

Exit codes
----------
    0 - policy passes (both thresholds met)
    1 - policy fails (package-mean below threshold or any file below threshold)
    2 - configuration or data error (missing file, malformed JSON,
        missing required keys, empty file set, invalid file summary,
        unrecognised package path, non-finite numeric values)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# -- Package policy ------------------------------------------------------------
# Coverage files outside these trees cause a hard error.
KNOWN_PACKAGES: tuple[str, ...] = ("quickscale_core", "quickscale_cli")
PACKAGE_PREFIXES: tuple[str, ...] = tuple(p + "/" for p in KNOWN_PACKAGES)


def _classify_file(filepath: str) -> str | None:
    """
    Classify *filepath* into a known package, or return ``None``.

    Rejects non-canonical paths that contain parent traversal (``..``)
    or self-reference (``./``) components.  Pathlib normalises ``./``
    away from ``parts``, so we check the raw string first.
    """
    # Pathlib normalises the leading "./" away, so check before parsing.
    if filepath.startswith("./") or filepath.startswith(".\\"):
        return None
    parts = Path(filepath).parts
    if ".." in parts:
        return None
    if parts and parts[0] in KNOWN_PACKAGES:
        return parts[0]
    return None


# ---------------------------------------------------------------------------


def load_coverage_json(path: Path) -> dict[str, Any] | None:
    """
    Load and validate coverage JSON from *path*.

    Returns the parsed ``dict`` on success, or ``None`` on file-not-found,
    invalid JSON, or missing required top-level keys.  The expected
    schema is the ``coverage json`` output format.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"ERROR: Coverage JSON not found: {path}", file=sys.stderr)
        return None
    except (OSError, PermissionError) as exc:
        print(f"ERROR: Cannot read {path}: {exc}", file=sys.stderr)
        return None

    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        print(
            f"ERROR: Coverage JSON root is not a dict (got {type(data).__name__})",
            file=sys.stderr,
        )
        return None

    for key in ("files", "totals"):
        if key not in data:
            print(
                f"ERROR: Coverage JSON missing required key {key!r}",
                file=sys.stderr,
            )
            return None

    if not isinstance(data["files"], dict):
        print("ERROR: Coverage JSON 'files' key is not a dict", file=sys.stderr)
        return None

    if not isinstance(data["totals"], dict):
        print("ERROR: Coverage JSON 'totals' key is not a dict", file=sys.stderr)
        return None

    return data


def _validate_file_summary(
    summary: Any,
    filepath: str,
) -> tuple[int, int, float] | None:
    """
    Validate a single file's summary entry.

    Returns ``(covered_lines, num_statements, percent_covered)`` on
    success, or ``None`` (and prints an error) on failure.
    """
    if not isinstance(summary, dict):
        print(
            f"ERROR: Summary for {filepath} is not a dict",
            file=sys.stderr,
        )
        return None

    covered = summary.get("covered_lines")
    statements = summary.get("num_statements")
    percent = summary.get("percent_covered")

    for name, val in [
        ("covered_lines", covered),
        ("num_statements", statements),
        ("percent_covered", percent),
    ]:
        if val is None:
            print(
                f"ERROR: Missing {name} for {filepath}",
                file=sys.stderr,
            )
            return None
        if not isinstance(val, (int, float)):
            print(
                f"ERROR: Non-numeric {name}={val!r} for {filepath}",
                file=sys.stderr,
            )
            return None
        if not math.isfinite(val):
            print(
                f"ERROR: Non-finite {name}={val} for {filepath}",
                file=sys.stderr,
            )
            return None

    if statements < 0 or covered < 0:
        print(
            f"ERROR: Negative coverage values for {filepath} "
            f"(covered_lines={covered}, num_statements={statements})",
            file=sys.stderr,
        )
        return None

    if int(covered) > int(statements):
        print(
            f"ERROR: covered_lines ({int(covered)}) exceeds "
            f"num_statements ({int(statements)}) for {filepath}",
            file=sys.stderr,
        )
        return None

    return int(covered), int(statements), float(percent)


def check_policy(
    coverage_path: str,
    mean_threshold: float = 90.0,
    file_threshold: float = 80.0,
) -> int:
    """
    Evaluate coverage policy and return an exit code.

    Parameters
    ----------
    coverage_path:
        Path to a ``coverage.json`` file as produced by ``coverage json``.
    mean_threshold:
        Minimum equal-weight package-mean coverage percentage
        (default: 90.0).
    file_threshold:
        Minimum coverage percentage per individual file (default: 80.0).

    Returns
    -------
    int
        0 if policy passes, 1 if it fails, 2 on data error.

    """
    data = load_coverage_json(Path(coverage_path))
    if data is None:
        return 2

    files: dict[str, Any] = data.get("files", {})

    if not files:
        print(
            "ERROR: No files found in coverage data - nothing to check.",
            file=sys.stderr,
        )
        return 2

    # Per-package accumulators: {pkg_name: (covered, statements)}
    pkg_covered: dict[str, int] = {}
    pkg_statements: dict[str, int] = {}
    file_results: list[tuple[str, float, int, int]] = []
    unknown_paths: list[str] = []

    for filepath in sorted(files):
        entry = files[filepath]
        if not isinstance(entry, dict):
            print(
                f"ERROR: File entry for {filepath!r} is not a dict (got {type(entry).__name__})",
                file=sys.stderr,
            )
            return 2

        summary = entry.get("summary")

        validated = _validate_file_summary(summary, filepath)
        if validated is None:
            return 2

        covered, statements, percent = validated

        # Classify into a known package
        pkg = _classify_file(filepath)
        if pkg is None:
            unknown_paths.append(filepath)
        else:
            pkg_covered[pkg] = pkg_covered.get(pkg, 0) + covered
            pkg_statements[pkg] = pkg_statements.get(pkg, 0) + statements
            file_results.append((filepath, percent, covered, statements))

    if unknown_paths:
        print(
            f"ERROR: Found files outside recognised package trees ({', '.join(KNOWN_PACKAGES)}):",
            file=sys.stderr,
        )
        for fp in unknown_paths:
            print(f"    {fp}", file=sys.stderr)
        return 2

    # -- Compute equal-weight package mean ----------------------------------
    # Each recognised package's percentage is calculated independently, then
    # the package percentages are averaged with equal weight (not weighted by
    # statement count).  This prevents a large high-coverage package from
    # masking a small low-coverage one.
    found_packages = sorted(pkg_covered.keys())
    if not found_packages:
        print(
            "ERROR: No recognised-package files found in coverage data.",
            file=sys.stderr,
        )
        return 2

    # -- Require both core and CLI -------------------------------------------
    missing: list[str] = [pkg for pkg in KNOWN_PACKAGES if pkg not in found_packages]
    if missing:
        print(
            "ERROR: Coverage data missing required package(s): "
            f"{', '.join(missing)}. "
            "Both quickscale_core and quickscale_cli must have measured files.",
            file=sys.stderr,
        )
        return 2

    pkg_percentages: dict[str, float] = {}
    for pkg in found_packages:
        stmts = pkg_statements[pkg]
        if stmts == 0:
            print(
                f"ERROR: Package {pkg!r} has 0 measurable statements.",
                file=sys.stderr,
            )
            return 2
        pct = (pkg_covered[pkg] / stmts) * 100.0
        pkg_percentages[pkg] = pct

    overall_mean = sum(pkg_percentages.values()) / len(pkg_percentages)

    # -- Header -------------------------------------------------------------
    print("Coverage Policy Check (equal-weight package mean)")
    print(f"  Mean threshold:       {mean_threshold:.1f}%")
    print(f"  Per-file threshold:   {file_threshold:.1f}%")
    print(f"  Files measured:       {len(file_results)}")
    print(f"  Packages found:       {len(found_packages)}")

    for pkg in found_packages:
        print(
            f"    {pkg}: {pkg_percentages[pkg]:.2f}%  "
            f"({pkg_covered[pkg]}/{pkg_statements[pkg]} stmts)"
        )

    print(f"  Equal-weight mean:    {overall_mean:.2f}%")

    # -- Mean check ---------------------------------------------------------
    policy_failed = False

    if overall_mean < mean_threshold:
        print(f"  FAIL - equal-weight mean {overall_mean:.2f}% is below {mean_threshold:.1f}%")
        policy_failed = True
    else:
        print(f"  Equal-weight mean {overall_mean:.2f}% meets {mean_threshold:.1f}% threshold")

    # -- Per-file check -----------------------------------------------------
    low_files = [
        (fp, pct, cov, stmts) for fp, pct, cov, stmts in file_results if pct < file_threshold
    ]

    if low_files:
        print(f"  FAIL - {len(low_files)} file(s) below {file_threshold:.1f}%:")
        for fp, pct, cov, stmts in low_files:
            print(f"      {fp}: {pct:.2f}% ({cov}/{stmts})")
        policy_failed = True
    else:
        print(f"  All {len(file_results)} files meet {file_threshold:.1f}% per-file threshold")

    return 1 if policy_failed else 0


def main(argv: list[str] | None = None) -> int:
    """Entry point: parse arguments, run policy check, return exit code."""
    parser = argparse.ArgumentParser(
        description="Check coverage data against the QuickScale "
        "dual-threshold policy (90% equal-weight package mean, "
        "80% per-file).",
    )
    parser.add_argument(
        "coverage_json",
        help="Path to a coverage.json file produced by `coverage json`.",
    )
    parser.add_argument(
        "--mean-threshold",
        type=float,
        default=90.0,
        help="Minimum equal-weight package-mean coverage (default: 90.0).",
    )
    parser.add_argument(
        "--per-file-threshold",
        type=float,
        default=80.0,
        help="Minimum per-file coverage percentage (default: 80.0).",
    )
    args = parser.parse_args(argv)

    return check_policy(
        args.coverage_json,
        mean_threshold=args.mean_threshold,
        file_threshold=args.per_file_threshold,
    )


if __name__ == "__main__":
    raise SystemExit(main())
