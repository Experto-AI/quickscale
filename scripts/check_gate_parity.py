#!/usr/bin/env python3
"""
SA122a — Gate registry diagnostic parity checker.

Compares the declared gate registry (gate_registry.json) against every
execution context — Makefile, check_ci_locally.sh, ci.yml, publish.yml,
and e2e.yml — and reports structural gaps as deterministic JSONL records.

Exit codes
----------
0 — perfect parity: every declared gate is present in every required context.
1 — semantic diff: one or more gates missing from a required context.
    Output is JSONL (one JSON object per diagnostic) on stdout.
2 — malformed / unreadable / ambiguous input (registry or source parse error).
    One-line ERROR: prefix message on stderr, no traceback.

Output (exit 1)
---------------
One JSON object per line (JSONL).  Each diagnostic record carries:
  ``level``     — "missing"
  ``context``   — the context name
  ``gate_id``   — the gate identifier
  ``source``    — the source file path
  ``detail``    — human-readable explanation
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# YAML duplicate-key-rejecting constructor
# ---------------------------------------------------------------------------


class _DuplicateKeyYAMLError(ValueError):
    """Raised when a YAML mapping contains duplicate keys."""


def _no_duplicate_yaml_keys(loader: Any, node: Any) -> Any:
    """YAML constructor that rejects duplicate mapping keys."""
    from yaml.nodes import MappingNode

    if not isinstance(node, MappingNode):
        return loader.construct_scalar(node)
    mapping: dict[Any, Any] = {}
    seen: set[Any] = set()
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in seen:
            raise _DuplicateKeyYAMLError(f"Duplicate YAML key: {key!r}")
        seen.add(key)
        value = loader.construct_object(value_node, deep=False)
        mapping[key] = value
    return mapping


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Source files keyed by context name
_CONTEXT_SOURCES: dict[str, Path] = {
    "local-serial": _REPO_ROOT / "scripts" / "check_ci_locally.sh",
    "local-parallel": _REPO_ROOT / "scripts" / "check_ci_locally.sh",
    "hosted": _REPO_ROOT / ".github" / "workflows" / "ci.yml",
    "publish": _REPO_ROOT / ".github" / "workflows" / "publish.yml",
    "e2e-trigger": _REPO_ROOT / ".github" / "workflows" / "e2e.yml",
}

_REGISTRY_PATH = _REPO_ROOT / "scripts" / "gate_registry.json"
_MAKEFILE_PATH = _REPO_ROOT / "Makefile"


# ---------------------------------------------------------------------------
# Schema validation helpers
# ---------------------------------------------------------------------------


class SchemaValidationError(ValueError):
    """Structured validation error with source label and field path."""

    def __init__(self, source: str, path: str, message: str) -> None:
        self.source = source
        self.path = path
        self.message = message
        super().__init__(message)


def _is_strict_int(value: object) -> bool:
    """Return True if *value* is an ``int`` but not a ``bool``."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_registry(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Validate the registry JSON structure.

    Returns the validated gates list.  Raises ``SchemaValidationError`` on the
    first structural violation.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError("registry", "", "must be a JSON object")

    # --- Top-level required keys ---
    top_keys: frozenset[str] = frozenset({"schema_version", "description", "contexts", "gates"})
    top_unknown = set(data.keys()) - top_keys
    if top_unknown:
        raise SchemaValidationError(
            "registry",
            "",
            f"unknown top-level key(s): {', '.join(sorted(top_unknown))}",
        )
    top_missing = top_keys - set(data.keys())
    if top_missing:
        raise SchemaValidationError(
            "registry",
            "",
            f"missing required top-level key(s): {', '.join(sorted(top_missing))}",
        )

    # --- schema_version ---
    schema = data.get("schema_version")
    if not _is_strict_int(schema):
        raise SchemaValidationError(
            "registry",
            "schema_version",
            f"schema_version must be a non-boolean integer (got {type(schema).__name__})",
        )
    if schema != 1:
        raise SchemaValidationError(
            "registry",
            "schema_version",
            f"unsupported schema_version {schema} (expected 1)",
        )

    # --- description ---
    desc_top = data.get("description")
    if not isinstance(desc_top, str) or not desc_top:
        raise SchemaValidationError(
            "registry",
            "description",
            "description must be a non-empty string",
        )

    # --- contexts ---
    contexts = data.get("contexts")
    if not isinstance(contexts, dict):
        raise SchemaValidationError(
            "registry",
            "contexts",
            f"contexts must be a dict (got {type(contexts).__name__})",
        )

    known_contexts: set[str] = {
        "local-serial",
        "local-parallel",
        "hosted",
        "publish",
        "e2e-trigger",
    }
    declared_contexts = set(contexts.keys())
    unknown = declared_contexts - known_contexts
    if unknown:
        raise SchemaValidationError(
            "registry",
            "contexts",
            f"unknown context(s): {', '.join(sorted(unknown))}",
        )
    missing_contexts = known_contexts - declared_contexts
    if missing_contexts:
        raise SchemaValidationError(
            "registry",
            "contexts",
            f"incomplete contexts: missing {', '.join(sorted(missing_contexts))}",
        )

    for ctx_name, ctx_desc in contexts.items():
        if not isinstance(ctx_desc, str) or not ctx_desc:
            raise SchemaValidationError(
                "registry",
                f"contexts.{ctx_name}",
                f"context {ctx_name!r} description must be a non-empty string",
            )

    # --- gates ---
    gates = data.get("gates")
    if not isinstance(gates, list):
        raise SchemaValidationError(
            "registry",
            "gates",
            f"gates must be a list (got {type(gates).__name__})",
        )
    if not gates:
        raise SchemaValidationError(
            "registry",
            "gates",
            "gates must be a non-empty list",
        )

    # --- Gate-level validation ---
    gate_keys: frozenset[str] = frozenset(
        {
            "id",
            "description",
            "required_contexts",
            "bindings",
            "depends_on",
            "trigger_inputs",
        }
    )
    binding_keys: frozenset[str] = frozenset({"make_target", "ci_job", "local_ci_stage"})

    seen_ids: set[str] = set()
    seen_make_targets: dict[str, str] = {}  # make_target -> gate_id
    seen_ci_jobs: dict[str, str] = {}  # ci_job -> gate_id
    id_re = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    path_safe_re = re.compile(r"^(?!.*\.\.)[a-zA-Z0-9_./*-]+$")

    for i, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}]",
                f"gate at index {i} must be a JSON object (got {type(gate).__name__})",
            )

        # Unknown gate keys
        gate_unknown = set(gate.keys()) - gate_keys
        if gate_unknown:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}]",
                f"unknown key(s) in gate[{i}]: {', '.join(sorted(gate_unknown))}",
            )

        # Missing gate keys
        gate_missing = gate_keys - set(gate.keys())
        if gate_missing:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}]",
                f"missing required key(s) in gate[{i}]: {', '.join(sorted(gate_missing))}",
            )

        # --- id ---
        gid = gate.get("id")
        if not isinstance(gid, str) or not gid:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].id",
                f"gate[{i}].id must be a non-empty string",
            )
        if not id_re.match(gid):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].id",
                f"gate[{i}].id {gid!r} contains unsafe characters",
            )
        if gid in seen_ids:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].id",
                f"duplicate gate id: {gid!r}",
            )
        seen_ids.add(gid)

        # --- description ---
        desc = gate.get("description")
        if not isinstance(desc, str) or not desc:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].description",
                f"gate[{i}] ({gid}).description must be a non-empty string",
            )

        # --- required_contexts ---
        rc = gate.get("required_contexts")
        if not isinstance(rc, list):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].required_contexts",
                f"gate[{i}] ({gid}).required_contexts must be a list",
            )
        if not rc:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].required_contexts",
                f"gate[{i}] ({gid}).required_contexts must be a non-empty list",
            )
        seen_rc: set[str] = set()
        for ctx in rc:
            if not isinstance(ctx, str):
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].required_contexts",
                    f"gate[{i}] ({gid}).required_contexts contains non-string: {ctx!r}",
                )
            if ctx not in known_contexts:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].required_contexts",
                    f"gate[{i}] ({gid}).required_contexts contains unknown context: {ctx!r}",
                )
            if ctx in seen_rc:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].required_contexts",
                    f"gate[{i}] ({gid}).required_contexts contains duplicate context: {ctx!r}",
                )
            seen_rc.add(ctx)

        # --- bindings ---
        bindings = gate.get("bindings")
        if not isinstance(bindings, dict):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].bindings",
                f"gate[{i}] ({gid}).bindings must be a dict",
            )
        bind_unknown = set(bindings.keys()) - binding_keys
        if bind_unknown:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].bindings",
                f"gate[{i}] ({gid}).bindings contains unknown key(s): "
                f"{', '.join(sorted(bind_unknown))}",
            )

        for bkey in ("make_target", "ci_job"):
            bval = bindings.get(bkey)
            if bval is None:
                continue
            if not isinstance(bval, str):
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].bindings.{bkey}",
                    f"gate[{i}] ({gid}).bindings.{bkey} must be a string or null"
                    f" (got {type(bval).__name__})",
                )
            # Reject the string "null" — only JSON null is acceptable
            if bval == "null":
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].bindings.{bkey}",
                    f'gate[{i}] ({gid}).bindings.{bkey} must be JSON null, not the string "null"',
                )

        lcs = bindings.get("local_ci_stage")
        if lcs is not None and not _is_strict_int(lcs):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].bindings.local_ci_stage",
                f"gate[{i}] ({gid}).bindings.local_ci_stage must be an integer or null"
                f" (got {type(lcs).__name__})",
            )

        # --- Binding collision detection ---
        mt = bindings.get("make_target")
        if mt and isinstance(mt, str):
            if mt in seen_make_targets:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].bindings.make_target",
                    f"make_target {mt!r} already used by gate {seen_make_targets[mt]!r}",
                )
            seen_make_targets[mt] = gid

        cj = bindings.get("ci_job")
        if cj and isinstance(cj, str):
            if cj in seen_ci_jobs:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].bindings.ci_job",
                    f"ci_job {cj!r} already used by gate {seen_ci_jobs[cj]!r}",
                )
            seen_ci_jobs[cj] = gid

        # --- depends_on ---
        deps = gate.get("depends_on")
        if not isinstance(deps, list):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].depends_on",
                f"gate[{i}] ({gid}).depends_on must be a list",
            )
        for dep in deps:
            if not isinstance(dep, str) or not dep:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].depends_on",
                    f"gate[{i}] ({gid}).depends_on entry must be a non-empty string",
                )

        # --- trigger_inputs ---
        ti = gate.get("trigger_inputs")
        if not isinstance(ti, list):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].trigger_inputs",
                f"gate[{i}] ({gid}).trigger_inputs must be a list",
            )
        seen_ti: set[str] = set()
        for pidx, pp in enumerate(ti):
            if not isinstance(pp, str) or not pp:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].trigger_inputs[{pidx}]",
                    f"gate[{i}] ({gid}).trigger_inputs[{pidx}] must be a non-empty string",
                )
            if not path_safe_re.match(pp):
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].trigger_inputs[{pidx}]",
                    f"gate[{i}] ({gid}).trigger_inputs[{pidx}] {pp!r} contains unsafe characters",
                )
            if pp in seen_ti:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].trigger_inputs[{pidx}]",
                    f"gate[{i}] ({gid}).trigger_inputs contains duplicate path: {pp!r}",
                )
            seen_ti.add(pp)

    # --- Cross-gate dependency validation ---
    for gate in gates:
        gid = gate["id"]
        for dep in gate.get("depends_on", []):
            if dep == gid:
                raise SchemaValidationError(
                    "registry",
                    f"gates.{gid}.depends_on",
                    f"gate {gid!r} depends on itself",
                )
            if dep not in seen_ids:
                raise SchemaValidationError(
                    "registry",
                    f"gates.{gid}.depends_on",
                    f"gate {gid!r} depends on unknown gate {dep!r}",
                )

    # --- Direct-cycle detection ---
    for gate in gates:
        gid = gate["id"]
        for dep in gate.get("depends_on", []):
            # Find the dependency gate
            dep_gate = next((g for g in gates if g["id"] == dep), None)
            if dep_gate:
                for dep2 in dep_gate.get("depends_on", []):
                    if dep2 == gid and gid < dep:
                        # Mutual dependency between gid and dep
                        raise SchemaValidationError(
                            "registry",
                            f"gates.{gid}.depends_on",
                            f"circular dependency between {gid!r} and {dep!r}",
                        )

    return gates


# ---------------------------------------------------------------------------
# Registry loading (duplicate-key-rejecting via YAML BaseLoader)
# ---------------------------------------------------------------------------


class _DuplicateKeyError(ValueError):
    """Raised internally by ``json.loads`` when a duplicate mapping key is found."""


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """
    ``object_pairs_hook`` for ``json.loads`` that rejects duplicate keys.

    Python's ``json.loads`` silently keeps the last value for duplicate keys;
    this hook raises ``_DuplicateKeyError`` when duplicates occur.  Only
    valid JSON is accepted — no YAML constructs, no trailing commas, no
    unquoted keys (enforced by the stdlib parser).
    """
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise _DuplicateKeyError(f"Duplicate key: {key!r}")
        seen.add(key)
    return dict(pairs)


def _parse_json_strict(raw: str, label: str = "registry") -> dict[str, Any]:
    """Parse *raw* as strict JSON v1, rejecting duplicate mapping keys."""
    try:
        data = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except _DuplicateKeyError as exc:
        raise SchemaValidationError(label, "", f"Duplicate JSON key: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(label, "", f"JSON parse error: {exc}") from exc

    if not isinstance(data, dict):
        raise SchemaValidationError(label, "", "must be a JSON object")
    return data


def _load_registry(path: Path) -> list[dict[str, Any]]:
    """
    Load and validate the gate registry.

    Uses strict JSON parsing with explicit duplicate-key rejection.  Only
    valid JSON v1 is accepted — no YAML constructs, no trailing commas,
    no unquoted keys.
    """
    raw = path.read_text(encoding="utf-8")
    data = _parse_json_strict(raw, str(path))
    return _validate_registry(data)


# ---------------------------------------------------------------------------
# Source extraction helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# YAML safe loading with duplicate-key rejection
# ---------------------------------------------------------------------------


def _parse_yaml_strict(raw: str, label: str = "workflow") -> dict[str, Any]:
    """
    Parse *raw* as strict YAML, rejecting duplicate mapping keys.

    Uses ``yaml.BaseLoader`` to safely handle GitHub Actions ``on:`` key
    without interpreting it as Python boolean ``True``.
    """
    if _yaml is None:  # pragma: no cover
        raise SchemaValidationError(label, "", "PyYAML is not available")

    try:
        # Register the duplicate-key-rejecting constructor for mapping nodes
        _yaml.add_constructor(
            _yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            _no_duplicate_yaml_keys,
            Loader=_yaml.BaseLoader,
        )
        data = _yaml.load(raw, Loader=_yaml.BaseLoader)
    except _DuplicateKeyYAMLError as exc:
        raise SchemaValidationError(label, "", f"Duplicate YAML key: {exc}") from exc
    except _yaml.YAMLError as exc:
        raise SchemaValidationError(label, "", f"YAML parse error: {exc}") from exc

    if not isinstance(data, dict):
        raise SchemaValidationError(label, "", "must be a YAML mapping")
    return data


# ---------------------------------------------------------------------------
# Makefile target+recipe extraction
# ---------------------------------------------------------------------------


def _extract_makefile_targets(path: Path) -> set[str]:
    """
    Extract all Makefile target names that have an actual definition+recipe.

    Parses the Makefile looking for lines that match ``<target>:`` (optionally
    with prerequisites) on their own as a target definition line, where a
    subsequent line (non-comment, non-empty) provides a recipe.  Both explicit
    ``.PHONY`` targeting and bare target definitions count — a target is
    considered present when it appears as a defined target name with an actual
    recipe, regardless of ``.PHONY``.

    Raises ``SchemaValidationError`` when the Makefile cannot be parsed.
    """
    text = path.read_text(encoding="utf-8")

    # Find all target declaration lines and their recipe status.
    # A target line matches ``^<target>:`` (an identifier at the start of a line).
    # A target is considered to have a recipe when at least one subsequent line
    # that is not a comment, not empty, and not a variable assignment, provides
    # recipe content (starts with a tab or contains a shell command keyword).
    targets: set[str] = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Skip comments, empty, and variable assignments
        if not stripped or stripped.startswith("#") or "=" in stripped.split("#")[0]:
            i += 1
            continue
        # Check for target definition: line that starts with word-char and contains :
        # Must start in column 0 (no leading whitespace for a target definition)
        # But Make allows targets to start with non-whitespace only.
        # Pattern: ``target[: ...]`` at start of line or after tab.
        target_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_.\-]*)\s*:", stripped)
        if not target_match:
            # Could be a recipe line (starts with tab) — skip
            i += 1
            continue

        target_name = target_match.group(1)

        # Skip pattern rules (contain %)
        if "%" in target_name:
            i += 1
            continue

        # Skip .PHONY, .ONESHELL, .SILENT, .DEFAULT, .POSIX etc.
        if target_name.startswith("."):
            i += 1
            continue

        # Check if there is a recipe on a subsequent line (tab-indented)
        has_recipe = False
        j = i + 1
        while j < len(lines):
            next_line = lines[j]
            # A recipe line starts with a tab
            if next_line.startswith("\t") and next_line.strip():
                has_recipe = True
                break
            # A comment or blank line is a break — but some recipes have
            # blank-line / comment separators.  Check if the next line is
            # a new target definition instead.
            next_stripped = next_line.strip()
            if not next_stripped or next_stripped.startswith("#"):
                j += 1
                continue
            # If the next line is a new target at column 0, stop looking
            if re.match(r"^[a-zA-Z_]", next_stripped) and ":" in next_stripped.split("#")[0]:
                break
            # If the line is a variable assignment or include directive, skip
            if "=" in next_stripped.split("#")[0] or next_stripped.startswith("include"):
                j += 1
                continue
            # Anything else that's not tab-indented means no recipe
            if not next_line.startswith("\t"):
                break
            j += 1

        if has_recipe:
            targets.add(target_name)

        i += 1

    # NOTE: .PHONY declarations are intentionally NOT used as evidence of
    # target existence.  A gate's make_target must have an actual recipe
    # (tab-indented command lines) to be considered present.  .PHONY-only
    # targets without a recipe are treated as absent, which forces explicit
    # recipe definitions for every declared binding.

    return targets


def _iter_significant_lines(text: str, start: int, end: int) -> Iterator[str]:
    """Yield non-comment, non-echo, non-empty lines from *text[start:end]."""
    for line in text[start:end].splitlines(keepends=False):
        stripped = line.strip()
        # Skip empty, comments, and echo statements
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("echo"):
            continue
        if stripped.startswith('echo "'):
            continue
        yield stripped


def _find_function_body(
    text: str,
    func_name: str,
    label: str = "script",
) -> tuple[int, int]:
    """
    Locate the opening ``{`` and closing ``}`` of a bash function body.

    Returns ``(start, end)`` where *start* is the index of the character
    immediately after ``{`` and *end* is the index of the matching ``}``.

    Raises ``SchemaValidationError`` when the function is not found, appears
    multiple times, or has an unclosed brace (ambiguous/malformed).
    """
    # Find all occurrences to detect duplicates.
    # Require exact column-zero function header: ``func_name() {``
    matches = list(
        re.finditer(
            rf"^{func_name}\s*\(\s*\)\s*{{",
            text,
            re.MULTILINE,
        )
    )
    if not matches:
        raise SchemaValidationError(
            label,
            func_name,
            f"function {func_name}() not found in source",
        )
    if len(matches) > 1:
        raise SchemaValidationError(
            label,
            func_name,
            f"duplicate function definition: {func_name}() appears {len(matches)} times",
        )

    func_match = matches[0]
    # Verify column-zero header (no leading whitespace before func_name)
    header_line_start = text.rfind("\n", 0, func_match.start()) + 1
    if func_match.start() != header_line_start:
        raise SchemaValidationError(
            label,
            func_name,
            f"function {func_name}() header not at column 0 — ambiguous/malformed",
        )

    start = func_match.end()
    depth = 1
    end = start
    i = start
    while i < len(text):
        ch = text[i]
        # Skip ${...} variable expansions
        if ch == "$" and i + 1 < len(text) and text[i + 1] == "{":
            i += 2
            var_depth = 1
            while i < len(text) and var_depth > 0:
                if text[i] == "{":
                    var_depth += 1
                elif text[i] == "}":
                    var_depth -= 1
                i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # Verify the closing ``}`` is at column 0
                close_line_start = text.rfind("\n", 0, i) + 1
                if close_line_start != i:
                    raise SchemaValidationError(
                        label,
                        func_name,
                        f"closing brace of {func_name}() not at column 0 "
                        f"— ambiguous/malformed source",
                    )
                end = i
                break
        i += 1
    else:
        raise SchemaValidationError(
            label,
            func_name,
            f"unclosed brace in function {func_name}() — ambiguous/malformed source",
        )
    return start, end


def _extract_check_ci_serial_gates(path: Path) -> set[str]:
    """
    Extract gate make targets from the serial path in check_ci_locally.sh.

    Looks for ``make <target>`` calls inside the ``run_static_gates_serial``
    function body.  Skips echo lines and comments so only actual gate
    invocations are counted.

    Raises ``SchemaValidationError`` when the function is missing, duplicated,
    or has an unclosed body.  An empty return means the function exists but
    contains no matching make invocations (valid absent membership).
    """
    text = path.read_text(encoding="utf-8")
    start, end = _find_function_body(text, "run_static_gates_serial", str(path))

    gates: set[str] = set()
    for sig_line in _iter_significant_lines(text, start, end):
        for m in re.finditer(r"\bmake\s+([a-z][a-z0-9_-]+)", sig_line):
            target = m.group(1)
            if target.startswith("check-") or target in ("frontend-proof", "smoke-install"):
                gates.add(target)
    return gates


def _extract_check_ci_parallel_gates(path: Path) -> set[str]:
    """
    Extract gate make targets from the parallel path in check_ci_locally.sh.

    Looks for ``launch_static_gate`` calls whose last arguments end with
    a ``make <target>`` pattern inside the ``run_static_gates_parallel``
    function body.  Comments and echo lines are skipped.

    Raises ``SchemaValidationError`` when the function is missing, duplicated,
    or has an unclosed body.  An empty return means the function exists but
    contains no matching make invocations (valid absent membership).
    """
    text = path.read_text(encoding="utf-8")
    start, end = _find_function_body(text, "run_static_gates_parallel", str(path))

    body_lines: list[str] = []
    for sig_line in _iter_significant_lines(text, start, end):
        body_lines.append(sig_line)
    body = "\n".join(body_lines)
    gates: set[str] = set()
    for m in re.finditer(
        r"launch_static_gate\s+[^)]+?\bmake\s+([a-z][a-z0-9_-]*)",
        body,
    ):
        target = m.group(1)
        if target.startswith("check-") or target in ("frontend-proof", "smoke-install"):
            gates.add(target)
    return gates


def _extract_ci_job_names(path: Path) -> set[str]:
    """
    Extract top-level job names from a GitHub Actions workflow YAML.

    Uses structural YAML parsing with duplicate-key rejection (BaseLoader-safe
    for the ``on:`` key).  Returns only top-level keys under ``jobs:`` that
    have a ``steps:`` or ``runs-on:`` subkey (i.e. real jobs, not metadata).

    Raises ``SchemaValidationError`` when the file is malformed, unreadable,
    or contains duplicate YAML keys (caller should treat this as exit 2).
    """
    text = path.read_text(encoding="utf-8")
    data = _parse_yaml_strict(text, str(path))

    if not isinstance(data, dict):
        raise SchemaValidationError(str(path), "", "workflow must be a YAML mapping")

    if "jobs" not in data:
        raise SchemaValidationError(str(path), "", "workflow has no jobs section")

    jobs_raw = data["jobs"]
    if not isinstance(jobs_raw, dict):
        raise SchemaValidationError(str(path), "jobs", "jobs must be a mapping")

    # Metadata keys that appear at the same indentation level as jobs in GHA
    # workflows.  The GHA spec allows arbitrary job names, so we use a
    # known-metadata set to filter non-job entries.
    gha_meta = frozenset(
        {
            "on",
            "name",
            "env",
            "defaults",
            "concurrency",
            "permissions",
            "timeout-minutes",
            "continue-on-error",
        }
    )

    jobs: set[str] = set()
    for key, value in jobs_raw.items():
        if isinstance(key, str) and key not in gha_meta:
            # A job is a mapping with runs-on and/or steps
            if isinstance(value, dict) and ("runs-on" in value or "steps" in value):
                jobs.add(key)
            # A job can also be a template reference (uses/matrix/include)
            # but those are not gate jobs — skip.
    return jobs


def _extract_publish_gates(path: Path) -> set[str]:
    """
    Extract gate make_targets or ci_jobs referenced in publish.yml.

    Uses structural YAML parsing with duplicate-key rejection (BaseLoader-safe
    for the ``on:`` key).  Only counts canonical standalone ``make <target>``
    invocations inside job ``run:`` blocks and top-level job entry names.
    Deceptive/control/wrapper forms (``||``, ``&&``, shell control operators)
    raise ``SchemaValidationError``.  Comments and echo strings are excluded.

    Raises ``SchemaValidationError`` when the file is malformed, unreadable,
    contains duplicate YAML keys, or contains ambiguous control-flow make
    invocations.
    """
    text = path.read_text(encoding="utf-8")
    data = _parse_yaml_strict(text, str(path))

    if not isinstance(data, dict):
        raise SchemaValidationError(str(path), "", "workflow must be a YAML mapping")

    if "jobs" not in data:
        raise SchemaValidationError(str(path), "", "workflow has no jobs section")

    jobs_raw = data["jobs"]
    if not isinstance(jobs_raw, dict):
        raise SchemaValidationError(str(path), "jobs", "jobs must be a mapping")

    gha_meta = frozenset(
        {
            "on",
            "name",
            "env",
            "defaults",
            "concurrency",
            "permissions",
            "timeout-minutes",
            "continue-on-error",
        }
    )

    gates: set[str] = set()

    for job_name, job_value in jobs_raw.items():
        if not isinstance(job_name, str) or job_name in gha_meta:
            continue
        if not isinstance(job_value, dict):
            continue

        # Add top-level job name as a gate identifier
        gates.add(job_name)

        # Extract make <target> from steps[].run values
        steps = job_value.get("steps")
        if not isinstance(steps, list):
            continue

        for step in steps:
            if not isinstance(step, dict):
                continue
            run_value = step.get("run")
            if not isinstance(run_value, str):
                continue

            run_lines = run_value.splitlines()
            for line_idx, line in enumerate(run_lines):
                stripped = line.strip()
                # Skip empty, comments, and echo-only lines
                if not stripped or stripped.startswith("#") or stripped.startswith("echo"):
                    continue

                # Check for make invocations
                for m in re.finditer(r"\bmake\s+([a-z][a-z0-9_-]+)", stripped):
                    target = m.group(1)

                    # Deceptive/control/wrapper detection:
                    # A canonical standalone make line is:
                    #   @?make <target> [args...]
                    # with no shell control operators or conditional
                    # keywords on the line or immediately preceding line.
                    before_make = stripped[: m.start()].strip()
                    after_target = stripped[m.end() :].split("#")[0].strip()

                    # 1) Per-line check: shell control operators after
                    #    make target (not redirects like >& 2>&1).
                    if re.search(
                        r"\|\||&&|[^>];|;\s*$|\|\s+[a-z]|&(?!>)\s*$|`|\$\(|subshell",
                        after_target,
                    ):
                        raise SchemaValidationError(
                            str(path),
                            f"jobs.{job_name}",
                            f"Deceptive/control make invocation in publish.yml: {stripped!r}",
                        )

                    # 2) Per-line check: control/conditional keywords
                    #    before make (if/then/else/for/while/case/do).
                    if re.search(
                        r"\b(if|then|else|elif|for|while|case|do|done|esac|fi)\b",
                        before_make,
                    ):
                        raise SchemaValidationError(
                            str(path),
                            f"jobs.{job_name}",
                            f"Conditional/loop-wrapped make invocation: {stripped!r}",
                        )

                    # 3) Cross-line check: preceding line is part of a
                    #    control structure (ends with |, &&, ||, then, do,
                    #    else, or begins with if/for/while/case).
                    if line_idx > 0:
                        prev_line = run_lines[line_idx - 1].strip()
                        if re.search(
                            r"\b(if|for|while|case)\s",
                            prev_line.split("#")[0],
                        ) or prev_line.rstrip().endswith(
                            ("|", "&&", "||", "then", "do", "else", "elif")
                        ):
                            raise SchemaValidationError(
                                str(path),
                                f"jobs.{job_name}",
                                f"Make invocation inside control flow: "
                                f"{stripped!r} (preceded by {prev_line!r})",
                            )

                    # Only include if this looks like a gate target
                    if target.startswith("check-") or target in (
                        "frontend-proof",
                        "smoke-install",
                    ):
                        gates.add(target)

    return gates


def _extract_e2e_trigger_paths(path: Path) -> list[str]:
    """
    Extract the ordered path allowlist from e2e.yml (order preserved, duplicates allowed).

    Only extracts paths from the ``pull_request.paths:`` block.  Skips
    comments and non-path list entries.  Uses column-based indentation
    tracking to avoid false exits from child keys like ``branches:``.
    """
    text = path.read_text(encoding="utf-8")

    # Column (indent) of the pull_request: key
    pr_indent: int | None = None
    # Column of the paths: key
    paths_indent: int | None = None
    in_paths = False
    paths: list[str] = []

    for line in text.splitlines():
        # Compute the leading whitespace column
        raw_stripped = line.lstrip()
        col = len(line) - len(raw_stripped)
        stripped = raw_stripped

        if stripped.startswith("#"):
            continue

        if stripped == "pull_request:" and pr_indent is None:
            pr_indent = col
            in_paths = False
            continue

        if pr_indent is not None and paths_indent is None:
            if stripped == "paths:" and col > pr_indent:
                paths_indent = col
                in_paths = True
                continue
            # If we hit a key at the same indent as pull_request, we left the block
            if col <= pr_indent and ":" in stripped:
                pr_indent = None
                continue

        if in_paths:
            # Path items are indented deeper than paths:
            if stripped.startswith("- ") and col > paths_indent:
                path_entry = stripped[2:].strip().strip("'\"")
                if path_entry:
                    paths.append(path_entry)
            elif col <= paths_indent:
                # Left the paths block (line at or above paths: indent)
                in_paths = False
                # Also leave pull_request if at or above pr_indent
                if pr_indent is not None and col <= pr_indent:
                    pr_indent = None
    return paths


def _is_subsequence(needles: list[str], haystack: list[str]) -> bool:
    """Return True if *needles* appear in *haystack* as an order-preserving subsequence."""
    idx = 0
    for needle in needles:
        while idx < len(haystack) and haystack[idx] != needle:
            idx += 1
        if idx >= len(haystack):
            return False
        idx += 1
    return True


# ---------------------------------------------------------------------------
# Context extraction dispatch
# ---------------------------------------------------------------------------


def _extract_gates_for_context(
    context: str,
    registry_gates: list[dict[str, Any]],
    source_text: str | None = None,
) -> set[str]:
    """
    Extract the set of gate IDs that are present in a given context.

    Uses the registry's binding metadata to map between gate IDs and the
    concrete target names found in source files.
    """
    _ = source_text  # Reserved for future use

    # Build a mapping from make_target -> gate_id and ci_job -> gate_id
    target_to_gate: dict[str, str] = {}
    job_to_gate: dict[str, str] = {}

    for gate in registry_gates:
        gid = gate["id"]
        bindings = gate.get("bindings", {})
        mt = bindings.get("make_target")
        if mt and isinstance(mt, str):
            target_to_gate[mt] = gid
        cj = bindings.get("ci_job")
        if cj and isinstance(cj, str) and cj != "null":
            job_to_gate[cj] = gid

    source = _CONTEXT_SOURCES.get(context)
    if not source or not source.exists():
        return set()

    if context in ("local-serial",):
        make_targets = _extract_check_ci_serial_gates(source)
        return {target_to_gate[t] for t in make_targets if t in target_to_gate}

    if context in ("local-parallel",):
        make_targets = _extract_check_ci_parallel_gates(source)
        return {target_to_gate[t] for t in make_targets if t in target_to_gate}

    if context == "hosted":
        job_names = _extract_ci_job_names(source)
        return {job_to_gate[j] for j in job_names if j in job_to_gate}

    if context == "publish":
        make_targets = _extract_publish_gates(source)
        return {target_to_gate[t] for t in make_targets if t in target_to_gate}

    if context == "e2e-trigger":
        # For e2e-trigger, match each gate's trigger_inputs against the
        # ordered e2e path allowlist.  A gate is "present" iff every one
        # of its trigger_inputs appears in the e2e path list as an
        # order-preserving subsequence.
        e2e_paths = _extract_e2e_trigger_paths(source)
        found: set[str] = set()
        for gate in registry_gates:
            ti = gate.get("trigger_inputs", [])
            if ti and _is_subsequence(ti, e2e_paths):
                found.add(gate["id"])
        return found

    return set()


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

_Diagnostic = dict[str, Any]


def _compare(
    registry_gates: list[dict[str, Any]],
) -> list[_Diagnostic]:
    """
    Compare declared required contexts against extracted presence.

    Returns a list of diagnostic records (empty = perfect parity).
    """
    diagnostics: list[_Diagnostic] = []

    # --- Makefile target validation -----------------------------------------
    # Every gate's make_target must exist as a defined Makefile target with
    # an actual recipe (tab-indented commands) or be declared in .PHONY.
    makefile_targets = _extract_makefile_targets(_MAKEFILE_PATH)
    for gate in registry_gates:
        gid = gate["id"]
        bindings = gate.get("bindings", {})
        mt = bindings.get("make_target")
        if mt and isinstance(mt, str) and mt not in makefile_targets:
            diagnostics.append(
                {
                    "level": "missing",
                    "context": "makefile",
                    "gate_id": gid,
                    "source": "Makefile",
                    "detail": (
                        f"Gate {gid!r} declares make_target {mt!r} "
                        f"but that target is not defined with a recipe in the Makefile"
                    ),
                }
            )

    for gate in registry_gates:
        gid = gate["id"]
        required = set(gate.get("required_contexts", []))

        for context in sorted(required):
            source = _CONTEXT_SOURCES.get(context)
            source_label = str(source.relative_to(_REPO_ROOT)) if source else context

            present = _extract_gates_for_context(context, registry_gates)
            if gid not in present:
                diagnostics.append(
                    {
                        "level": "missing",
                        "context": context,
                        "gate_id": gid,
                        "source": source_label,
                        "detail": (
                            f"Gate {gid!r} is required in context {context!r} "
                            f"but was not found in {source_label}"
                        ),
                    }
                )

    # --- e2e-trigger aggregate path comparison (exact sequence) -------------
    # Only compare when at least one gate requires e2e-trigger context, so
    # test registries that only reference other contexts stay hermetic.
    e2e_source = _CONTEXT_SOURCES.get("e2e-trigger")
    has_e2e_requirement = any(
        "e2e-trigger" in gate.get("required_contexts", []) for gate in registry_gates
    )
    if e2e_source and e2e_source.exists() and has_e2e_requirement:
        e2e_paths_actual = _extract_e2e_trigger_paths(e2e_source)
        # Collect all trigger_inputs from all gates in registration order
        registry_paths: list[str] = []
        for gate in registry_gates:
            ti = gate.get("trigger_inputs", [])
            if isinstance(ti, list):
                registry_paths.extend(ti)

        # --- Exact sequence comparison (duplicate-aware) --------------------
        # 1. Missing: paths in registry aggregate but not in e2e.yml (by value).
        seen_in_e2e = set(e2e_paths_actual)
        registry_missing = [p for p in registry_paths if p not in seen_in_e2e]
        if registry_missing:
            diagnostics.append(
                {
                    "level": "missing",
                    "context": "e2e-trigger",
                    "gate_id": "**aggregate**",
                    "source": str(e2e_source.relative_to(_REPO_ROOT)),
                    "detail": (
                        f"{len(registry_missing)} path(s) declared in registry "
                        f"trigger_inputs but not found in e2e.yml: "
                        f"{registry_missing}"
                    ),
                }
            )

        # 2. Extra: in e2e.yml but not in any gate's trigger_inputs
        seen_in_registry = set(registry_paths)
        extra_paths = [p for p in e2e_paths_actual if p not in seen_in_registry]
        if extra_paths:
            diagnostics.append(
                {
                    "level": "extra",
                    "context": "e2e-trigger",
                    "gate_id": "**aggregate**",
                    "source": str(e2e_source.relative_to(_REPO_ROOT)),
                    "detail": (
                        f"{len(extra_paths)} path(s) in e2e.yml but not declared "
                        f"in any gate's trigger_inputs: {extra_paths}"
                    ),
                }
            )

        # 3. Exact sequence comparison (duplicate-aware).
        # Compare the full ordered sequence of the union of paths.
        # This catches: reorder, interior swap, missing position, extra position,
        # and duplicate-count mismatches.
        if not registry_missing and not extra_paths:
            # Same set — compare exact sequences
            if registry_paths != e2e_paths_actual:
                # Find first position of divergence
                min_len = min(len(registry_paths), len(e2e_paths_actual))
                for i in range(min_len):
                    if registry_paths[i] != e2e_paths_actual[i]:
                        diagnostics.append(
                            {
                                "level": "order",
                                "context": "e2e-trigger",
                                "gate_id": "**aggregate**",
                                "source": str(e2e_source.relative_to(_REPO_ROOT)),
                                "detail": (
                                    f"Exact sequence mismatch at position {i}: "
                                    f"registry expects {registry_paths[i]!r} "
                                    f"but e2e.yml has {e2e_paths_actual[i]!r}"
                                ),
                            }
                        )
                        break
                else:
                    # One is longer than the other (cardinality mismatch on same set)
                    diagnostics.append(
                        {
                            "level": "order",
                            "context": "e2e-trigger",
                            "gate_id": "**aggregate**",
                            "source": str(e2e_source.relative_to(_REPO_ROOT)),
                            "detail": (
                                f"Exact sequence length mismatch: "
                                f"registry has {len(registry_paths)} paths, "
                                f"e2e.yml has {len(e2e_paths_actual)} paths"
                            ),
                        }
                    )
        elif not registry_missing:
            # Only extra paths exist — check if ordering matches for what's in common
            _add_common_order_diagnostic(registry_paths, e2e_paths_actual, e2e_source, diagnostics)
        elif not extra_paths:
            # Only missing paths — check common order
            _add_common_order_diagnostic(registry_paths, e2e_paths_actual, e2e_source, diagnostics)

        # --- e2e-trigger ownership collision detection ----------------------
        # The e2e path list is a single ordered aggregate allowlist, not
        # partitioned per gate.  When two (or more) gates' trigger_inputs
        # match overlapping subsequences of the e2e path list, ownership
        # is ambiguous — neither can claim unique presence.
        # Report overlapping path ownership as a diagnostic.
        gate_path_sets: dict[str, frozenset[str]] = {}
        for gate in registry_gates:
            if "e2e-trigger" in gate.get("required_contexts", []):
                ti = gate.get("trigger_inputs", [])
                if isinstance(ti, list) and ti:
                    gate_path_sets[gate["id"]] = frozenset(ti)

        for gid_a, paths_a in gate_path_sets.items():
            for gid_b, paths_b in gate_path_sets.items():
                if gid_a < gid_b and paths_a & paths_b:
                    # Overlapping path sets — ambiguous ownership
                    overlap = sorted(paths_a & paths_b)
                    diagnostics.append(
                        {
                            "level": "ambiguous",
                            "context": "e2e-trigger",
                            "gate_id": "**ownership**",
                            "source": str(e2e_source.relative_to(_REPO_ROOT)),
                            "detail": (
                                f"e2e-trigger path ownership collision: "
                                f"gates {gid_a!r} and {gid_b!r} both claim "
                                f"{len(overlap)} overlapping path(s): {overlap}"
                            ),
                        }
                    )

    return diagnostics


def _add_common_order_diagnostic(
    registry_paths: list[str],
    e2e_paths_actual: list[str],
    e2e_source: Path,
    diagnostics: list[_Diagnostic],
) -> None:
    """Emit an order diagnostic when common paths diverge in sequence."""
    common_set = set(registry_paths) & set(e2e_paths_actual)
    common_registry = [p for p in registry_paths if p in common_set]
    common_e2e = [p for p in e2e_paths_actual if p in common_set]
    if common_registry and common_registry != common_e2e:
        for i, (rp, ep) in enumerate(zip(common_registry, common_e2e)):
            if rp != ep:
                diagnostics.append(
                    {
                        "level": "order",
                        "context": "e2e-trigger",
                        "gate_id": "**aggregate**",
                        "source": str(e2e_source.relative_to(_REPO_ROOT)),
                        "detail": (
                            f"Common-path order mismatch at position {i}: "
                            f"registry expects {rp!r} but e2e.yml has {ep!r}"
                        ),
                    }
                )
                break


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _print_error(message: str, code: str = "INPUT_ERROR") -> None:
    """Print a stable one-line error on stderr."""
    print(f"ERROR: [{code}] {message}", file=sys.stderr)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SA122a — gate registry diagnostic parity checker",
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
    Execute the gate parity check.

    Returns the exit code (0, 1, or 2).  Unexpected exceptions produce a
    deterministic stderr message and exit 2 without traceback.
    """
    args = _parse_args(argv)
    registry_path = Path(args.registry) if args.registry else _REGISTRY_PATH

    try:
        registry_gates = _load_registry(registry_path)

        diagnostics = _compare(registry_gates)

        if not diagnostics:
            print("All gates present in all required contexts.", file=sys.stderr)
            return 0

        # Exit 1: emit JSONL on stdout
        for d in diagnostics:
            print(json.dumps(d, sort_keys=True))
        return 1

    except SchemaValidationError as exc:
        _print_error(f"{exc.source}:{exc.path}: {exc.message}", code="SCHEMA_ERROR")
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


if __name__ == "__main__":
    sys.exit(main())
