#!/usr/bin/env python3
"""
SA259 — Gate wiring currency checker.

``gate_registry.json`` is the only gate list.  The generated Make include
(``scripts/gates.mk``), the hosted-job regions and consumer ``needs`` lists in
``ci.yml``, the E2E allowlist in ``e2e.yml``, the publish workflow's
gate-step region, and the gate-roster table in
``docs/technical/validation_policy.md`` are all rendered from it by
``sync_ci_gate_jobs.py``.  This checker loads the registry through the
authoritative strict-JSON schema (duplicate-key rejection, binding collisions,
dependency-cycle detection) that the generator shares, then proves every
generated file is current.  It never re-derives a hand-written context.

The schema itself lives in the private sibling ``_gate_registry_schema``
(SA267) and is re-exported here; this facade keeps the loader, the drift
report, and the CLI.

Exit codes
----------
0 — all generated gate wiring is current.
1 — generated text differs from the checked-in file.
    One deterministic unified diff per stale file on stdout; no ERROR on
    stderr.
2 — malformed / unreadable / ambiguous input (registry or generated-source
    parse error).  One-line ERROR: prefix message on stderr, no traceback.

``trigger_inputs`` contract
---------------------------
The legacy field name does not mean that a matching change conditionally runs
or skips a gate.  It is each E2E-bound gate's ordered share of the
bidirectional partition of ``e2e.yml``'s pull-request path allowlist; the
generator renders the flattened registry sequence into the workflow, so the
two cannot drift.  If any execution context ever skips a gate on the basis of
``trigger_inputs``, that is the promotion trigger for renaming or redesigning
this contract rather than overloading the legacy name.
"""

from __future__ import annotations

import argparse
import difflib
import json as json
import re as re
import sys
from collections.abc import Iterator as Iterator
from pathlib import Path
from typing import Any

from _gate_registry_schema import (
    _TRIGGER_INPUTS_CONTRACT,
    SchemaValidationError,
    _canonical_input_path,
    _DuplicateKeyError,
    _is_strict_int,
    _no_duplicate_keys,
    _parse_json_strict,
    _validate_registry,
)

#: Every module-level name the pre-split checker published; the facade
#: re-exports the schema half from ``_gate_registry_schema``.  Per
#: decisions.md § Split-Facade Seams a facade re-exports public names only:
#: incidental imported bindings (``argparse``, ``json``, ``Path``, ...) stay
#: module attributes but are deliberately not part of the wildcard surface.
__all__ = [
    "SchemaValidationError",
    "_DuplicateKeyError",
    "_TRIGGER_INPUTS_CONTRACT",
    "_canonical_input_path",
    "_generated_drift",
    "_is_strict_int",
    "_load_registry",
    "_no_duplicate_keys",
    "_parse_args",
    "_parse_json_strict",
    "_print_error",
    "_validate_registry",
    "main",
]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

_REGISTRY_PATH = _REPO_ROOT / "scripts" / "gate_registry.json"


def _load_registry(path: Path) -> list[dict[str, Any]]:
    """
    Load and validate the gate registry.

    Uses strict JSON parsing with explicit duplicate-key rejection.  Only
    valid JSON v1 is accepted — no YAML constructs, no trailing commas,
    no unquoted keys.
    """
    canonical = _canonical_input_path(path, "registry")
    raw = canonical.read_text(encoding="utf-8")
    data = _parse_json_strict(raw, str(canonical))
    return _validate_registry(data)


# ---------------------------------------------------------------------------
# Generated-file currency
# ---------------------------------------------------------------------------


def _generated_drift(registry_path: Path) -> list[tuple[str, str, str]]:
    """
    Return one ``(label, current_text, expected_text)`` row per stale file.

    Every projection is owned by ``sync_ci_gate_jobs.py``; this checker never
    restates one.  The sibling import is deferred until call time because the
    generator imports this module's registry validator at its own module load.
    """
    import sync_ci_gate_jobs as generator

    surfaces: tuple[tuple[str, Path, Any], ...] = (
        ("ci.yml", generator.DEFAULT_WORKFLOW, generator.sync_workflow),
        ("e2e.yml", generator.DEFAULT_E2E_WORKFLOW, generator.sync_e2e_workflow),
        ("publish.yml", generator.DEFAULT_PUBLISH_WORKFLOW, generator.sync_publish_workflow),
        ("scripts/gates.mk", generator.DEFAULT_MAKE_INCLUDE, generator.sync_make_include),
        (
            "docs/technical/validation_policy.md",
            generator.DEFAULT_DOCS,
            generator.sync_docs_table,
        ),
    )
    drifted: list[tuple[str, str, str]] = []
    for label, path, render in surfaces:
        drift, expected = render(path, registry_path)
        if not drift:
            continue
        try:
            current = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = ""
        drifted.append((label, current, expected))
    return drifted


def _print_error(message: str, code: str = "INPUT_ERROR") -> None:
    """Print a stable one-line error on stderr, never a traceback or newline."""
    print(f"ERROR: [{code}] {' '.join(str(message).split())}", file=sys.stderr)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SA259 — generated gate wiring currency checker",
    )
    parser.add_argument(
        "--registry",
        help="Path to gate registry JSON (default: scripts/gate_registry.json)",
        default=None,
        type=str,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    Prove every generated gate-wiring file is current for the registry.

    Returns the exit code (0, 1, or 2).  Unexpected exceptions produce a
    deterministic stderr message and exit 2 without traceback.
    """
    args = _parse_args(argv)
    registry_path = Path(args.registry) if args.registry else _REGISTRY_PATH

    try:
        _load_registry(registry_path)
        drifted = _generated_drift(registry_path)
    except SchemaValidationError as exc:
        _print_error(f"{exc.source}:{exc.path}: {exc.message}", code="SCHEMA_ERROR")
        return 2
    except ValueError as exc:
        # GeneratorError subclasses ValueError: malformed generated sources,
        # mismatched marker pairs, and unsupported gate sets land here.
        _print_error(str(exc), code="INPUT_ERROR")
        return 2
    except FileNotFoundError as exc:
        _print_error(f"File not found: {exc}", code="FILE_NOT_FOUND")
        return 2
    except PermissionError as exc:
        _print_error(f"Permission denied: {exc}", code="PERMISSION_DENIED")
        return 2
    except Exception as exc:  # noqa: BLE001
        msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        _print_error(f"Unexpected error: {msg}", code="UNEXPECTED_ERROR")
        return 2

    if not drifted:
        print("All generated gate wiring is current.", file=sys.stderr)
        return 0

    for label, current, expected in drifted:
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=label,
            tofile=f"{label}.generated",
        )
        sys.stdout.write("".join(diff))
    return 1


if __name__ == "__main__":
    sys.exit(main())
