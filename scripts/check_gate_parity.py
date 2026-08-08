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

SA128a
------
The Makefile context is observed through GNU Make's own semantics instead of
regex text extraction: ``make -qp`` supplies the resolved target/recipe
database and ``make --dry-run`` proves pure-delegation / check-aggregation
targets.  Observation runs in a controlled environment with a hard timeout,
an output byte bound, and process-group cleanup; a malformed Makefile fails
hard (exit 2).

Check-gate membership is derived through the real ``check`` target: the
``make -qp`` database is walked from ``check`` through resolved prerequisites
and ``$(MAKE)`` recipe goals, so a standalone recipe-owning gate that is
removed from ``check`` no longer satisfies the registry — global target
effectiveness is not check aggregation.  Missing or malformed ``include``
files fail hard with the named file (exit 2).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

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


def _canonical_input_path(path: Path, source_kind: str) -> Path:
    """
    Accept one trusted, canonical, regular file inside the repository.

    The checker treats repository inputs as trusted and assumes no concurrent
    writer replaces a validated path.  This boundary deliberately does not
    claim atomic inode identity, descriptor identity, race freedom, or
    sandboxing of repository content.

    Relative paths are interpreted from the current working directory.  They
    are accepted when that spelling is already the canonical spelling of an
    in-repository path; lexical ``..`` aliases and every symlink component are
    rejected before the source can be observed.
    """
    candidate = path if path.is_absolute() else Path.cwd() / path
    if any(part == ".." for part in candidate.parts):
        raise SchemaValidationError(
            str(path), "", f"{source_kind} must use a canonical path (.. aliases are not allowed)"
        )

    current = Path(candidate.anchor)
    for component in candidate.parts[1:]:
        current /= component
        if current.is_symlink():
            raise SchemaValidationError(
                str(path), "", f"{source_kind} must not contain symlink components"
            )

    if not candidate.is_relative_to(_REPO_ROOT):
        raise SchemaValidationError(
            str(path), "", f"{source_kind} must reside inside the repository"
        )

    try:
        canonical = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise FileNotFoundError(path) from None

    if candidate != canonical:
        raise SchemaValidationError(
            str(path), "", f"{source_kind} must use its canonical path spelling"
        )
    if not canonical.is_file():
        raise SchemaValidationError(str(path), "", f"{source_kind} is not a regular file")
    return canonical


def _observation_input_path(path: Path, source_kind: str) -> Path:
    """
    Resolve a direct fixture input without weakening the CLI boundary.

    Public checker inputs are validated by ``_canonical_input_path`` before
    they reach observation.  The low-level observation functions are also
    intentionally usable with temporary fixture files in focused tests, so
    they only require a real, non-symlink file here.
    """
    if path.is_symlink():
        raise SchemaValidationError(str(path), "", f"{source_kind} must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise SchemaValidationError(str(path), "", f"{source_kind} not found") from None
    if not resolved.is_file():
        raise SchemaValidationError(str(path), "", f"{source_kind} is not a regular file")
    return resolved


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

    # --- Dependency-cycle detection ----------------------------------------
    # Use an explicit DFS stack rather than recursion so the registry can
    # contain arbitrarily long dependency chains without depending on Python's
    # recursion limit.  The traversal order and reported cycle are canonical:
    # gate IDs and adjacency entries are visited lexicographically, and the
    # cycle is rotated to begin at its lexicographically smallest member.
    dependencies = {gate["id"]: tuple(sorted(gate.get("depends_on", []))) for gate in gates}
    gate_ids = tuple(sorted(seen_ids))
    state: dict[str, int] = {gid: 0 for gid in gate_ids}  # 0=unseen, 1=active, 2=done
    cycle: tuple[str, ...] | None = None

    for start in gate_ids:
        if state[start] != 0:
            continue

        state[start] = 1
        path: list[str] = [start]
        path_positions: dict[str, int] = {start: 0}
        stack: list[tuple[str, Iterator[str]]] = [(start, iter(dependencies[start]))]

        while stack and cycle is None:
            current, successors = stack[-1]
            try:
                successor = next(successors)
            except StopIteration:
                state[current] = 2
                stack.pop()
                path_positions.pop(current)
                path.pop()
                continue

            if state[successor] == 0:
                state[successor] = 1
                path_positions[successor] = len(path)
                path.append(successor)
                stack.append((successor, iter(dependencies[successor])))
            elif state[successor] == 1:
                cycle = tuple(path[path_positions[successor] :])
                break

        if cycle is not None:
            break

    if cycle is not None:
        cycle_start = min(cycle)
        start_index = cycle.index(cycle_start)
        ordered_cycle = cycle[start_index:] + cycle[:start_index]
        cycle_members = ", ".join(repr(gid) for gid in sorted(cycle))
        cycle_path = " -> ".join((*ordered_cycle, cycle_start))
        if len(cycle) == 2:
            # Keep the Phase 1 diagnostic wording for the existing two-node
            # case while making its member order deterministic.
            ordered_members = sorted(cycle)
            detail = (
                f"circular dependency between {ordered_members[0]!r} and {ordered_members[1]!r}"
            )
        else:
            detail = f"circular dependency among gates: {cycle_members} ({cycle_path})"
        raise SchemaValidationError(
            "registry",
            f"gates.{cycle_start}.depends_on",
            detail,
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
    canonical = _canonical_input_path(path, "registry")
    raw = canonical.read_text(encoding="utf-8")
    data = _parse_json_strict(raw, str(canonical))
    return _validate_registry(data)


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
# Makefile semantic observation (SA128a)
# ---------------------------------------------------------------------------
#
# Gate make_target presence is derived from GNU Make's own semantics instead
# of regex-parsing Makefile text:
#
#   * ``make -qp`` prints the authoritative target database with every
#     variable-composed target name already resolved and every recipe
#     attributed to its owner.
#   * ``make --dry-run <target>`` prints the commands that would actually run
#     for a target, which proves pure-delegation / check-aggregation targets
#     (no recipe of their own) are effective.
#   * Check-gate membership is derived through the real ``check`` target:
#     the database is walked from ``check`` through resolved prerequisites
#     and ``$(MAKE)`` recipe goals.  A standalone recipe-owning gate that is
#     removed from ``check`` is absent — global target effectiveness is not
#     check aggregation.  ``include`` resolution is part of the same
#     observation: included files' targets appear in the database, and a
#     missing or malformed include makes GNU make exit 2 (fail hard, named).
#
# Observation is bounded: a controlled environment (no inherited
# MAKEFLAGS/jobserver), a hard timeout, an output byte bound, and process-
# group cleanup keep the observation deterministic.  GNU make exit codes
# discriminate malformed input (>= 2) from a valid database (0/1), and a
# malformed Makefile fails hard with ``SchemaValidationError`` (exit 2).

_MAKE_TIMEOUT_SECONDS = 30.0
_MAKE_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_MAKE_ERROR_DETAIL_BYTES = 400

_MAKE_VARIABLES_HEADER = "\n# Variables"
_MAKE_VARIABLE_LINE_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*(:=|=|\?=|\+=|!=|::=)\s*(.*)$")
_MAKE_VAR_REF_RE = re.compile(r"(?<!\$)\$\(([^()]+)\)|(?<!\$)\$\{([^{}]+)\}")
_MAKE_RECURSIVE_MAKE_RE = re.compile(r"(?<!\$)\$\(MAKE\)|(?<!\$)\$\{MAKE\}")
_MAKE_REPORTED_FILE_RE = re.compile(r"^Reading makefile '([^']+)'")
# Shell metacharacters that end a goal run on a ``$(MAKE)`` recipe line.
# ``$`` and ``(``/``)`` are deliberately absent: make variable references
# such as ``$(GATES)`` legitimately contain them and resolve to goal text.
_MAKE_GOAL_STOP_RE = re.compile(r'[|&;<>{}`"\'#=:!?*\[\]~\\]')
# GNU make options that consume a following argument (defensive goal parsing).
_MAKE_ARG_TAKING_OPTIONS: frozenset[str] = frozenset(
    {
        "-C",
        "-f",
        "-I",
        "-o",
        "-W",
        "--directory",
        "--file",
        "--include-dir",
        "--old-file",
        "--assume-old",
        "--new-file",
        "--assume-new",
    }
)
_MAKE_EXPANSION_PASSES = 10


class _MakeOutputError(RuntimeError):
    """GNU make produced more output than the observation bound allows."""


class _MakeTargetRecord:
    """One target record parsed from the ``make -qp`` database."""

    __slots__ = ("has_commands", "prereqs", "recipe_lines")

    def __init__(self, prereqs: str) -> None:
        self.has_commands = False
        self.prereqs = prereqs
        self.recipe_lines: list[str] = []


class _MakeResult(NamedTuple):
    """Bounded GNU make subprocess result (raw bytes)."""

    returncode: int
    stdout: bytes
    stderr: bytes


def _make_observation_env() -> dict[str, str]:
    """
    Return the controlled environment for GNU make observation.

    Only the variables GNU make needs to parse the Makefile are passed.
    ``MAKEFLAGS``/``MFLAGS``/``MAKELEVEL``/``GNUMAKEFLAGS`` from an enclosing
    ``make`` run are deliberately not inherited, so the observed make cannot
    join a parent jobserver or pick up parent flags — observation is
    deterministic.
    """
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "LANG": "C",
        "LC_ALL": "C",
    }


def _kill_make_process_group(
    proc: subprocess.Popen[bytes], process_group_id: int | None = None
) -> dict[int, str]:
    """
    Kill an observed process group and return any members left behind.

    ``start_new_session=True`` binds the process group at spawn time.  Keep
    that ID rather than looking it up after the process has been cleaned up:
    the latter is both racy and can accidentally observe a reused group ID.
    The helper is retained under its historical name because Make and Bash
    share this cleanup contract.
    """
    return _terminate_process_group(proc, process_group_id or proc.pid)


def _communicate_bounded(
    proc: subprocess.Popen[bytes],
    max_bytes: int,
    timeout: float,
    watched_file_bytes: Callable[[], int] | None = None,
) -> tuple[bytes, bytes]:
    """
    Read both pipes with a combined byte bound and a hard deadline.

    ``watched_file_bytes`` supplies the current size of file-backed observation
    channels.  When present, pipe bytes and those file bytes share *max_bytes*;
    the callback is sampled while the process runs and once more before the
    function returns.  Sampling sizes rather than reading files keeps a fast
    producer from turning a later parser into an unbounded read.

    Raises ``subprocess.TimeoutExpired`` when the process outlives *timeout*
    and ``_MakeOutputError`` when combined output exceeds *max_bytes*.
    """
    assert proc.stdout is not None and proc.stderr is not None
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    out_sink = bytearray()
    err_sink = bytearray()
    selector.register(proc.stdout, selectors.EVENT_READ, out_sink)
    selector.register(proc.stderr, selectors.EVENT_READ, err_sink)
    total = 0

    def check_total_bound() -> int:
        file_total = watched_file_bytes() if watched_file_bytes is not None else 0
        if total + file_total > max_bytes:
            raise _MakeOutputError(
                f"GNU make exceeded the {max_bytes} byte observation output bound"
            )
        return file_total

    def drain(key: selectors.SelectorKey) -> None:
        nonlocal total
        sink: bytearray = key.data
        fileobj = key.fileobj
        while True:
            file_total = check_total_bound()
            available = max_bytes - total - file_total
            if available <= 0:
                raise _MakeOutputError(
                    f"GNU make exceeded the {max_bytes} byte observation output bound"
                )
            fd = fileobj if isinstance(fileobj, int) else fileobj.fileno()
            try:
                chunk = os.read(fd, min(65536, available))
            except BlockingIOError:
                # A ready pipe is not necessarily readable for a second
                # immediate read.  Non-blocking descriptors prevent a child
                # that inherited the pipe from defeating the deadline.
                return
            if not chunk:
                selector.unregister(fileobj)
                return
            sink.extend(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise _MakeOutputError(
                    f"GNU make exceeded the {max_bytes} byte observation output bound"
                )
            check_total_bound()

    for stream in (proc.stdout, proc.stderr):
        os.set_blocking(stream.fileno(), False)

    try:
        check_total_bound()
        while selector.get_map():
            if proc.poll() is not None:
                # The direct process may have exited while a descendant still
                # owns a pipe.  Continue draining only within the same hard
                # deadline; EOF is required for successful completion.
                for key in tuple(selector.get_map().values()):
                    drain(key)
                if not selector.get_map():
                    break
            check_total_bound()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            for key, _ in selector.select(
                timeout=min(remaining, _BOUNDED_COMMUNICATION_POLL_SECONDS)
            ):
                drain(key)

        # EOF on both captured streams is not sufficient: the direct observer
        # may have closed both descriptors and still be alive.  Preserve the
        # original deadline while waiting for that process to exit rather than
        # returning to a caller that would need an unbounded wait.
        while proc.poll() is None:
            check_total_bound()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            try:
                proc.wait(timeout=min(remaining, _BOUNDED_COMMUNICATION_POLL_SECONDS))
            except subprocess.TimeoutExpired:
                continue
        check_total_bound()
    finally:
        selector.close()
    return bytes(out_sink), bytes(err_sink)


def _observation_returncode(
    proc: subprocess.Popen[bytes], process_group_id: int, label: str
) -> int:
    """Return an already-reaped observer status or fail closed."""
    returncode = proc.poll()
    if returncode is not None:
        return returncode
    cleanup = _kill_make_process_group(proc, process_group_id)
    raise SchemaValidationError(
        label,
        "",
        f"observation process remained alive after bounded communication; "
        f"{_cleanup_detail(cleanup)}",
    )


def _run_make(args: list[str], cwd: Path, label: str) -> _MakeResult:
    """
    Run GNU make with a controlled environment and hard observation bounds.

    Raises ``SchemaValidationError`` when make cannot be started, exceeds the
    timeout or output bound, or exits with a GNU make error code (>= 2) —
    which for a query/dry-run invocation means the Makefile is malformed.
    Exit codes 0 and 1 are valid database output (``-q`` returns 1 when the
    default goal would need updating).
    """
    process_group_id: int
    try:
        proc = subprocess.Popen(
            ["make", *args],
            cwd=str(cwd),
            env=_make_observation_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        # start_new_session makes the child PID its process-group ID.  Capture
        # it immediately, before any failure-path cleanup can reap the child.
        process_group_id = proc.pid
    except FileNotFoundError:
        raise SchemaValidationError(label, "", "GNU make executable not found on PATH") from None
    except OSError as exc:
        raise SchemaValidationError(label, "", f"failed to start GNU make: {exc}") from None

    try:
        stdout, stderr = _communicate_bounded(proc, _MAKE_MAX_OUTPUT_BYTES, _MAKE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        cleanup = _kill_make_process_group(proc, process_group_id)
        detail = _cleanup_detail(cleanup)
        raise SchemaValidationError(
            label,
            "",
            f"GNU make exceeded the {_MAKE_TIMEOUT_SECONDS:g}s observation timeout; {detail}",
        ) from None
    except _MakeOutputError as exc:
        cleanup = _kill_make_process_group(proc, process_group_id)
        detail = _cleanup_detail(cleanup)
        raise SchemaValidationError(label, "", f"{exc}; {detail}") from None

    returncode = _observation_returncode(proc, process_group_id, label)
    if returncode not in (0, 1):
        detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
        if detail:
            detail = detail[:_MAKE_ERROR_DETAIL_BYTES]
            message = f"GNU make exited with status {returncode}: {detail}"
        else:
            message = f"GNU make exited with status {returncode}"
        cleanup = _kill_make_process_group(proc, process_group_id)
        raise SchemaValidationError(label, "", f"{message}; {_cleanup_detail(cleanup)}")
    cleanup = _kill_make_process_group(proc, process_group_id)
    if cleanup:
        residual_ids = ", ".join(str(pid) for pid in sorted(cleanup))
        raise SchemaValidationError(
            label,
            "",
            f"GNU make observation left live process-group members {residual_ids}; "
            f"{_cleanup_detail(cleanup)}",
        )
    return _MakeResult(returncode, stdout, stderr)


def _validate_make_consumed_sources(output: bytes, makefile: Path) -> None:
    """Validate every source GNU Make reports as consumed during observation."""
    reported: set[Path] = set()
    text = output.decode("utf-8", errors="replace")
    for line in text.splitlines():
        match = _MAKE_REPORTED_FILE_RE.match(line)
        if match is None:
            continue
        source = Path(match.group(1))
        if not source.is_absolute():
            source = makefile.parent / source
        # Repository observations retain the strict in-repository boundary;
        # direct temporary Makefile fixtures may consume only sibling files in
        # their own fixture directory.
        if makefile.is_relative_to(_REPO_ROOT):
            reported.add(_canonical_input_path(source, "Makefile input"))
        elif not source.resolve(strict=True).is_relative_to(makefile.parent.resolve()):
            raise SchemaValidationError(
                str(source), "", "Makefile input must reside beside the fixture Makefile"
            )
        else:
            reported.add(_observation_input_path(source, "Makefile input"))

    # The -f input is trusted independently of GNU Make's diagnostic format.
    if makefile.is_relative_to(_REPO_ROOT):
        _canonical_input_path(makefile, "Makefile")
    else:
        _observation_input_path(makefile, "Makefile")


_MAKE_DATABASE_HEADER_RE = re.compile(r"^([^\t#].*?):\s*(.*)$")


def _parse_make_database(text: str, label: str) -> dict[str, _MakeTargetRecord]:
    """
    Parse ``make -qp`` output into per-target records.

    Only the ``# Files`` section is parsed; variable definitions, implicit
    rules, and hash-table statistics never appear there.  A record starts at
    a column-0 ``name: [prereqs]`` line — GNU make has already resolved
    variable-composed names, so the database carries concrete target names.
    Recipe lines are tab-indented and stored raw so ``$(MAKE)`` recursion
    hazards can be detected later.
    """
    files_idx = text.find("\n# Files")
    if files_idx < 0:
        raise SchemaValidationError(label, "", "GNU make database has no # Files section")
    body = text[files_idx + len("\n# Files") :]
    stats_idx = body.find("# files hash-table stats:")
    if stats_idx >= 0:
        body = body[:stats_idx]
    records: dict[str, _MakeTargetRecord] = {}
    current_names: tuple[str, ...] = ()
    for line in body.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line[0] in "\t ":
            # Recipe line belonging to the current record (raw, unexpanded).
            for name in current_names:
                record = records[name]
                record.has_commands = True
                record.recipe_lines.append(line)
            continue
        match = _MAKE_DATABASE_HEADER_RE.match(line)
        if not match:
            continue
        names = tuple(n for n in match.group(1).split() if n)
        if not names:
            continue
        current_names = names
        prereqs = match.group(2).strip()
        for name in names:
            records.setdefault(name, _MakeTargetRecord(prereqs))
    return records


def _is_observable_make_target(name: str) -> bool:
    """
    Return True when *name* is a concrete, user-invocable goal.

    Special targets (``.PHONY``, ``.DEFAULT``, ...), pattern rules (containing
    ``%``), and the makefile itself are not concrete goals.
    """
    return not name.startswith(".") and "%" not in name and name != "Makefile"


def _parse_make_variables(text: str) -> dict[str, str]:
    """
    Parse ``make -qp`` variable definitions into a name -> value map.

    Only the ``# Variables`` section is parsed; it ends where ``# Files``
    begins.  Simple assignments (``:=``, ``=``, ``?=``, ``+=``, ``!=``,
    ``::=``) are recorded in print order — makefile values print after
    environment values, so they win.  Automatic variables, ``define`` blocks,
    and other constructs are ignored: they are not needed to resolve goal
    text.  Values are stored raw; ``_expand_make_refs`` resolves references.
    """
    variables: dict[str, str] = {}
    start = text.find(_MAKE_VARIABLES_HEADER)
    if start < 0:
        return variables
    body = text[start + len(_MAKE_VARIABLES_HEADER) :]
    files_idx = body.find("\n# Files")
    if files_idx >= 0:
        body = body[:files_idx]
    for line in body.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = _MAKE_VARIABLE_LINE_RE.match(line)
        if match is None:
            continue
        name = match.group(1)
        op = match.group(2)
        value = match.group(3)
        if op == "+=":
            prior = variables.get(name)
            variables[name] = f"{prior} {value}" if prior is not None else value
        else:
            variables[name] = value
    return variables


def _expand_make_refs(value: str, variables: dict[str, str]) -> str:
    """
    Expand ``$(NAME)`` / ``${NAME}`` references from the make database.

    GNU make prints immediately-expanded (``:=``) values already expanded and
    recursive (``=``) values raw; a bounded number of passes resolves both,
    including chains (``A = $(B)``, ``B = gate``).  Escaped dollars (``$$``)
    are left untouched — they are shell variables inside recipe lines.
    Unresolved references stay literal and are later rejected by the
    concrete-goal filter.
    """
    for _ in range(_MAKE_EXPANSION_PASSES):

        def _sub(match: re.Match[str]) -> str:
            name = match.group(1) or match.group(2) or ""
            return variables.get(name, match.group(0))

        expanded = _MAKE_VAR_REF_RE.sub(_sub, value)
        if expanded == value:
            return expanded
        value = expanded
    return value


def _is_concrete_goal_token(token: str) -> bool:
    """
    Return True when *token* is a concrete goal name.

    A goal token must be an observable target name with no unresolved make
    reference — a remaining ``$`` means the recipe's variable composition
    could not be resolved from the database (e.g. a shell ``$$var``).
    """
    return _is_observable_make_target(token) and "$" not in token


def _recursive_make_goals(line: str, variables: dict[str, str]) -> Iterator[str]:
    """
    Yield concrete goal names invoked by a ``$(MAKE)`` recipe line.

    The text after ``$(MAKE)`` is tokenized; the goal run ends at the first
    token containing a shell metacharacter or variable assignment (``|``,
    ``&&``, redirections, ``SECTIONS=...``, ...).  GNU make options
    (``-j4``, ``-C dir``, ...) are skipped; argument-taking options consume
    their argument.  Each goal token is expanded against the make database
    before it is yielded, so ``$(MAKE) $(GATES)`` resolves ``$(GATES)`` to
    its concrete goal list.
    """
    match = _MAKE_RECURSIVE_MAKE_RE.search(line)
    if match is None:
        return
    skip_next = False
    for token in line[match.end() :].split():
        if _MAKE_GOAL_STOP_RE.search(token):
            break
        if token.startswith("-"):
            skip_next = token in _MAKE_ARG_TAKING_OPTIONS
            continue
        if skip_next:
            skip_next = False
            continue
        for piece in _expand_make_refs(token, variables).split():
            if piece and _is_concrete_goal_token(piece):
                yield piece


def _check_reachable_targets(
    records: dict[str, _MakeTargetRecord],
    variables: dict[str, str],
    root: str = "check",
) -> set[str]:
    """
    Return observable target names reachable from the check aggregation root.

    Effective check membership is derived through GNU make's own database
    semantics — never by regex over Makefile source text:

      * prerequisite names come from the resolved ``make -qp`` records, so
        variable-composed and included-file prerequisites are already
        concrete;
      * ``$(MAKE)`` goals in database-attributed recipe lines follow make's
        own recursive-make semantics, so aggregation by recipe delegation is
        observed, including goals composed from make variables.

    A standalone recipe-owning target that is not reachable from *root* is
    deliberately absent: global target effectiveness is not check aggregation.
    When the Makefile defines no *root* target the result is empty
    (fail-closed — nothing is a check member).
    """
    if root not in records:
        return set()
    reached: set[str] = set()
    stack = [root]
    while stack:
        name = stack.pop()
        if name in reached:
            continue
        reached.add(name)
        record = records.get(name)
        if record is None:
            continue
        for prereq in record.prereqs.split():
            if _is_observable_make_target(prereq):
                stack.append(prereq)
        for line in record.recipe_lines:
            stack.extend(_recursive_make_goals(line, variables))
    return {name for name in reached if _is_observable_make_target(name)}


def _closure_has_recursive_make(name: str, records: dict[str, _MakeTargetRecord]) -> bool:
    """
    Return True when invoking *name* would execute a ``$(MAKE)`` recipe line.

    GNU make executes recipe lines containing ``$(MAKE)`` even under
    ``--dry-run``, so dependency graphs containing them must never be
    dry-run.  The check walks the prerequisite closure and inspects raw
    (unexpanded) recipe text from the database.
    """
    seen: set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        record = records.get(current)
        if record is None:
            continue
        if any("$(MAKE)" in line or "${MAKE}" in line for line in record.recipe_lines):
            return True
        stack.extend(record.prereqs.split())
    return False


def _dry_run_runs_commands(path: Path, target: str) -> bool:
    """
    Return True when GNU make's ``--dry-run`` for *target* would run a command.

    A command-less (pure delegation / aggregation) target is effective iff
    ``make --dry-run <target>`` prints at least one recipe line; make chatter
    such as "Nothing to be done" does not count.
    """
    canonical = _observation_input_path(path, "Makefile")
    result = _run_make(
        ["-n", "-r", "-R", "--no-print-directory", "-f", str(canonical), target],
        canonical.parent,
        str(path),
    )
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("make:") or stripped.startswith("make["):
            continue
        return True
    return False


def _effective_makefile_targets(path: Path, records: dict[str, _MakeTargetRecord]) -> set[str]:
    """
    Return effective targets: recipe owners plus runnable delegation targets.

    Recipe-owning targets are effective by definition (the database proves
    they own commands).  Command-less targets are proven by GNU make's own
    ``--dry-run``; those whose dependency closure contains a ``$(MAKE)`` line
    are effective by construction (invoking them runs the recursive make) and
    are never dry-run, preserving the deterministic-observation bound.
    """
    canonical = _observation_input_path(path, "Makefile")
    effective: set[str] = set()
    for name, record in records.items():
        if not _is_observable_make_target(name):
            continue
        if record.has_commands:
            effective.add(name)
    for name, record in records.items():
        if name in effective or not _is_observable_make_target(name):
            continue
        # Remaining records are command-less (observable command owners were
        # already added above): decide effectiveness by dry-run or by the
        # recursive-make closure, never both.
        if _closure_has_recursive_make(name, records):
            effective.add(name)
        elif _dry_run_runs_commands(canonical, name):
            effective.add(name)
    return effective


def _observe_makefile(path: Path) -> tuple[dict[str, _MakeTargetRecord], dict[str, str]]:
    """
    Observe the Makefile once through GNU make and return its parsed database.

    Runs ``make -qp`` in the Makefile's directory with a controlled
    environment, a hard timeout, an output byte bound, and process-group
    cleanup, then parses the printed database into target records and
    variable definitions.  Raises ``SchemaValidationError`` when the Makefile
    is malformed — GNU make exits 2 (which includes missing/malformed
    ``include`` files) — or when make is unavailable, times out, or exceeds
    the output bound.
    """
    canonical = _observation_input_path(path, "Makefile")
    result = _run_make(
        ["-qp", "-r", "-R", "--no-print-directory", "--debug=a", "-f", str(canonical)],
        canonical.parent,
        str(canonical),
    )
    _validate_make_consumed_sources(result.stdout, canonical)
    text = result.stdout.decode("utf-8", errors="replace")
    records = _parse_make_database(text, str(canonical))
    variables = _parse_make_variables(text)
    return records, variables


def _extract_makefile_targets(path: Path) -> set[str]:
    """
    Observe the Makefile through GNU make's own semantics (SA128a).

    Targets that own a recipe are present; command-less targets (pure
    delegation / check aggregation) are present only when GNU make's
    ``--dry-run`` shows they would run at least one command.
    Variable-composed target names are resolved by GNU make itself, so
    ``check-$(SUFFIX)`` is observed as its concrete name.

    Raises ``SchemaValidationError`` when the Makefile is malformed — GNU
    make exits 2 — or when make is unavailable, times out, or exceeds the
    output bound.
    """
    records, _ = _observe_makefile(path)
    return _effective_makefile_targets(path, records)


def _extract_check_members(path: Path) -> set[str]:
    """
    Return the targets reachable from the real ``check`` target (F-001).

    The Makefile is observed once through GNU make (``_observe_makefile``) and
    the database is walked from ``check`` through resolved prerequisites and
    ``$(MAKE)`` recipe goals (``_check_reachable_targets``).  A standalone
    recipe-owning gate that is removed from ``check`` is absent — global
    target effectiveness is not check aggregation.

    Raises ``SchemaValidationError`` when the Makefile is malformed — GNU
    make exits 2, which includes missing/malformed ``include`` files — or
    when make is unavailable, times out, or exceeds the output bound.
    """
    records, variables = _observe_makefile(path)
    return _check_reachable_targets(records, variables)


def _assert_canonical_makefile_input(path: Path) -> None:
    """
    Fail hard when the canonical Makefile input is not a plain in-repo file.

    The parity checker hands the Makefile to GNU make for semantic
    observation, so the canonical input must be a regular, non-symlink file
    inside the repository.  Anything else is a security-boundary violation —
    a symlink could redirect observation (and make's ``$(shell)`` expansion)
    outside the repository.
    """
    _canonical_input_path(path, "Makefile")


# ---------------------------------------------------------------------------
# Bash semantic observation (SA128b)
# ---------------------------------------------------------------------------

_BASH_TIMEOUT_SECONDS = 30.0
_BASH_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_BASH_MAX_FILE_BYTES = 8 * 1024 * 1024
_BASH_MAX_EVENTS = 4096
_BASH_MAX_FRAMES = 4096
_BASH_MAX_ARGV_ITEMS = 256
_BASH_MAX_EVENT_BYTES = 64 * 1024
_BASH_MAX_FRAME_BYTES = 1024 * 1024
_BASH_FILE_READ_CHUNK_BYTES = 64 * 1024
_BOUNDED_COMMUNICATION_POLL_SECONDS = 0.01
_BASH_ERROR_DETAIL_BYTES = 400
_BASH_RESULT_MARKER = "__SA128B_RESULT__"
_BASH_PROCESS_GROUP_SETTLE_SECONDS = 0.05
_BASH_PROCESS_GROUP_CLEANUP_SECONDS = 5.0
_SHELL_GATE_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_OBSERVED_GATE_NAMES: frozenset[str] = frozenset({"frontend-proof", "smoke-install"})
_BASH_ARGV_HEADER_RE = re.compile(r"^ARGV:([0-9]+)$")


def _bash_observation_byte_limit() -> int:
    """Return the combined pipe and file-backed observation byte limit."""
    return min(_BASH_MAX_OUTPUT_BYTES, _BASH_MAX_FILE_BYTES)


def _is_observed_shell_gate(value: str) -> bool:
    """Return whether a recorder argument is a local gate target."""
    return (value.startswith("check-") or value in _OBSERVED_GATE_NAMES) and bool(
        _SHELL_GATE_RE.fullmatch(value)
    )


def _canonical_shell_harness(path: Path, function_name: str) -> str | None:
    """
    Build a function-only Bash program for the canonical local CI script.

    The production script has a command-oriented entrypoint after its function
    declarations.  Feeding that entrypoint to Bash would install dependencies
    and run database checks, so the declaration prefix is retained and the
    selected function is invoked by the harness instead.  The declarations and
    the selected function are still parsed and executed by Bash; this helper
    never inspects their command text to infer gates.
    """
    path = path.resolve(strict=True)
    canonical = path == _REPO_ROOT / "scripts" / "check_ci_locally.sh"
    if not canonical:
        return None

    text = path.read_text(encoding="utf-8")
    entrypoint = '\necho "[1/${TOTAL_STAGES}] Installing dependencies..."'
    marker = text.find(entrypoint)
    if marker < 0:
        raise SchemaValidationError(
            str(path),
            function_name,
            "canonical local CI entrypoint marker is missing",
        )
    root_line = 'ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)'
    prefix = text[:marker].replace(root_line, f"ROOT={shlex.quote(str(_REPO_ROOT))}", 1)
    return prefix


def _shell_observation_harness(path: Path, function_name: str) -> str:
    """Return a Bash program that invokes one source-defined gate function."""
    canonical_prefix = _canonical_shell_harness(path, function_name)
    if canonical_prefix is None:
        source_block = """
source "$1"
source_status=$?
if [ "$source_status" -ne 0 ]; then
    printf '%s source failed with status %s\\n' "$__SA128B_RESULT__" "$source_status" >&2
    exit "$source_status"
fi
: > "$SA128_RECORDER_LOG"
"""
    else:
        source_block = canonical_prefix + "\n"

    # Keep the observer PATH limited to the recorder.  The source function is
    # still run by Bash, but parallel launches are observed through a wrapper
    # that gives every worker its own argv log.  This makes the postcondition
    # check independent of worker completion timing and lets it prove that all
    # launched workers were joined in declaration order.
    return (
        source_block
        + """
unset -f make 2>/dev/null || true
cleanup_temp_files() { :; }
save_worker_traps() { :; }
restore_worker_traps() { :; }
_qs_replay_worker_logs() { :; }
mktemp() { printf '%s\\n' "${SA128_WORKER_DIR:?}"; }

# The recorder uses an argc-prefixed NUL-delimited transport.  NUL cannot
# occur in a Unix argv element, while spaces, newlines, quotes, and wildcard
# characters remain ordinary data.
launch_static_gate() {
    local stage_id="$1"
    local stage_number="$2"
    local description="$3"
    local success_message="$4"
    local failure_label="$5"
    local worker_index="${SA128_LAUNCH_COUNT:-0}"
    local worker_log="$SA128_WORKER_DIR/worker_${worker_index}.argv"
    shift 5

    : "$stage_number" "$description" "$success_message" "$failure_label"
    SA128_LAUNCH_COUNT=$((worker_index + 1))
    (
        export SA128_RECORDER_LOG="$worker_log"
        "$@"
    ) >/dev/null 2>&1 &
    local worker_pid="$!"
    printf '%s\\t%s\\t%s\\n' "$stage_id" "$worker_pid" "$worker_log" >> "$SA128_LAUNCH_LOG"
    WORKER_PIDS+=("$worker_pid")
    WORKER_ORDER+=("$stage_id")
    STATIC_STAGE_NAMES+=("$stage_id")
    STATIC_FAILURE_LABELS+=("$failure_label")
}

# Record every explicit wait and its result without changing the source
# function's wait status.  A missing wait therefore remains observable even
# if a fast worker has already exited by the time the function returns.
wait() {
    local wait_status=0
    local worker_pid
    local worker_status
    if [ "$#" -eq 0 ] || [[ "$1" == -* ]]; then
        if builtin wait "$@"; then
            worker_status=0
        else
            worker_status=$?
        fi
        printf 'SPECIAL\\t%s\\n' "$worker_status" >> "$SA128_WAIT_LOG"
        return "$worker_status"
    fi
    for worker_pid in "$@"; do
        if builtin wait "$worker_pid"; then
            worker_status=0
        else
            worker_status=$?
            wait_status="$worker_status"
        fi
        printf '%s\\t%s\\n' "$worker_pid" "$worker_status" >> "$SA128_WAIT_LOG"
    done
    return "$wait_status"
}

declare -a WORKER_PIDS=()
declare -a WORKER_ORDER=()
declare -a STATIC_STAGE_NAMES=()
declare -a STATIC_FAILURE_LABELS=()

if ! declare -F "${2:-run_static_gates}" >/dev/null; then
    printf '%s function %s() not found\\n' "$__SA128B_RESULT__" "${2:-run_static_gates}" >&2
    exit 2
fi

# Run the function in a child shell so its own errexit setting remains active
# while the parent captures the resulting status with a conditional builtin
# wait.  Calling the function directly from an `if` would suppress errexit in
# the function body and create a false-green partial inventory.
"${2:-run_static_gates}" &
observed_pid="$!"
if builtin wait "$observed_pid"; then
    observed_status=0
else
    observed_status=$?
fi

printf '%s%s\\n' "$__SA128B_RESULT__" "$observed_status"
exit "$observed_status"
"""
    )


def _live_process_group_members(process_group_id: int) -> dict[int, str]:
    """Return live process IDs and states currently in *process_group_id*."""
    members: dict[int, str] = {}
    proc_root = Path("/proc")
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return members

    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8")
        except FileNotFoundError, PermissionError, OSError:
            continue
        closing_paren = stat.rfind(") ")
        if closing_paren < 0:
            continue
        fields = stat[closing_paren + 2 :].split()
        # After the comm field: state, ppid, pgrp, ...
        if len(fields) < 3:
            continue
        try:
            process_id = int(entry.name)
            pgrp = int(fields[2])
        except ValueError:
            continue
        if pgrp == process_group_id and fields[0] != "Z":
            members[process_id] = fields[0]
    return members


def _wait_for_process_group_cleanup(process_group_id: int) -> dict[int, str]:
    """Wait until a process group has no live members, returning residuals."""
    deadline = time.monotonic() + _BASH_PROCESS_GROUP_CLEANUP_SECONDS
    while True:
        members = _live_process_group_members(process_group_id)
        if not members:
            return {}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return members
        time.sleep(min(_BASH_PROCESS_GROUP_SETTLE_SECONDS, remaining))


def _terminate_process_group(
    proc: subprocess.Popen[bytes], process_group_id: int | None = None
) -> dict[int, str]:
    """Terminate and wait for every live member of an observed process group."""
    group_id = process_group_id or proc.pid
    try:
        os.killpg(group_id, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=min(1.0, _BASH_PROCESS_GROUP_CLEANUP_SECONDS))
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        proc.wait(timeout=min(5.0, _BASH_PROCESS_GROUP_CLEANUP_SECONDS))

    residual = _live_process_group_members(group_id)
    if residual:
        try:
            os.killpg(group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return _wait_for_process_group_cleanup(group_id)


def _cleanup_detail(residual: dict[int, str]) -> str:
    """Describe the result of the shared bounded process-group cleanup."""
    if residual:
        ids = ", ".join(str(pid) for pid in sorted(residual))
        return f"cleanup left live process-group members {ids}"
    return "cleanup verified the process group is empty"


def _bash_observation_file_bytes(
    recorder_log: Path, launch_log: Path, wait_log: Path, worker_dir: Path
) -> int:
    """Return the combined size of every Bash observation file channel."""
    total = 0
    paths = (recorder_log, launch_log, wait_log, *worker_dir.glob("worker_*.argv"))
    for path in paths:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            continue
        except OSError:
            # A disappearing worker log is handled by the final structural
            # parser.  It must not turn a bounded observation into an
            # unstructured exception while the process is still running.
            continue
        total += size
        if total > _bash_observation_byte_limit():
            return total
    return total


class _BashObservationReadBudget:
    """Running limits shared by every parsed Bash observation channel."""

    __slots__ = ("bytes_read", "event_count", "frame_count")

    def __init__(self) -> None:
        self.bytes_read = 0
        self.event_count = 0
        self.frame_count = 0

    def account_bytes(self, path: Path, label: str, amount: int, detail: str) -> None:
        """Account for bytes read from one channel against the aggregate bound."""
        self.bytes_read += amount
        if self.bytes_read > _bash_observation_byte_limit():
            raise SchemaValidationError(str(path), label, detail)

    def account_event(self, path: Path, label: str) -> None:
        """Account for one event across all event channels."""
        self.event_count += 1
        if self.event_count > _BASH_MAX_EVENTS:
            raise SchemaValidationError(
                str(path), label, "combined Bash observation event count exceeded the bound"
            )

    def account_frame(self, path: Path, label: str) -> None:
        """Account for one recorder frame across all recorder channels."""
        self.frame_count += 1
        if self.frame_count > _BASH_MAX_FRAMES:
            raise SchemaValidationError(
                str(path), label, "combined Bash recorder frame count exceeded the bound"
            )


def _iter_bounded_file_lines(
    path: Path, label: str, budget: _BashObservationReadBudget | None = None
) -> Iterator[bytes]:
    """Yield newline-delimited file events without an unbounded read."""
    read_budget = budget if budget is not None else _BashObservationReadBudget()
    event_bytes = bytearray()
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise SchemaValidationError(
            str(path), label, f"cannot open observation log: {exc}"
        ) from None

    with stream:
        while True:
            chunk = stream.read(_BASH_FILE_READ_CHUNK_BYTES)
            if not chunk:
                break
            read_budget.account_bytes(
                path, label, len(chunk), "observation event file exceeded the byte bound"
            )
            event_bytes.extend(chunk)
            while True:
                try:
                    newline = event_bytes.index(10)
                except ValueError:
                    if len(event_bytes) > _BASH_MAX_EVENT_BYTES:
                        raise SchemaValidationError(
                            str(path), label, "observation event exceeded the byte bound"
                        ) from None
                    break
                event = bytes(event_bytes[:newline])
                del event_bytes[: newline + 1]
                read_budget.account_event(path, label)
                if len(event) > _BASH_MAX_EVENT_BYTES:
                    raise SchemaValidationError(
                        str(path), label, "observation event exceeded the byte bound"
                    )
                yield event

        if event_bytes:
            read_budget.account_event(path, label)
            if len(event_bytes) > _BASH_MAX_EVENT_BYTES:
                raise SchemaValidationError(
                    str(path), label, "unterminated observation event exceeded the byte bound"
                )
            yield bytes(event_bytes)


def _read_bash_event_log(
    path: Path,
    expected_fields: int,
    label: str,
    budget: _BashObservationReadBudget | None = None,
) -> list[tuple[str, ...]]:
    """Read a bounded tab-delimited Bash event log and validate its shape."""
    read_budget = budget if budget is not None else _BashObservationReadBudget()
    events: list[tuple[str, ...]] = []
    for raw_event in _iter_bounded_file_lines(path, label, read_budget):
        try:
            event = raw_event.decode("utf-8")
        except UnicodeDecodeError:
            raise SchemaValidationError(
                str(path), label, "observation event is not UTF-8"
            ) from None
        fields = tuple(event.split("\t"))
        if len(fields) != expected_fields or any(not field for field in fields):
            raise SchemaValidationError(str(path), label, "malformed observation event")
        events.append(fields)
    return events


def _iter_bounded_nul_fields(
    path: Path, label: str, budget: _BashObservationReadBudget | None = None
) -> Iterator[bytes]:
    """Yield NUL-delimited recorder fields with bounded incremental buffering."""
    read_budget = budget if budget is not None else _BashObservationReadBudget()
    file_bytes = 0
    pending = bytearray()
    terminated = False
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise SchemaValidationError(str(path), label, f"cannot open recorder log: {exc}") from None

    with stream:
        while True:
            chunk = stream.read(_BASH_FILE_READ_CHUNK_BYTES)
            if not chunk:
                break
            file_bytes += len(chunk)
            read_budget.account_bytes(
                path, label, len(chunk), "recorder file exceeded the byte bound"
            )
            pending.extend(chunk)
            while True:
                try:
                    nul = pending.index(0)
                except ValueError:
                    if len(pending) > _BASH_MAX_FRAME_BYTES:
                        raise SchemaValidationError(
                            str(path), label, "recorder frame exceeded the byte bound"
                        ) from None
                    break
                if nul > _BASH_MAX_FRAME_BYTES:
                    raise SchemaValidationError(
                        str(path), label, "recorder frame field exceeded the byte bound"
                    )
                field = bytes(pending[:nul])
                del pending[: nul + 1]
                terminated = True
                yield field

        if pending:
            raise SchemaValidationError(str(path), label, "incomplete Bash recorder transport")
        if not terminated and file_bytes:
            raise SchemaValidationError(str(path), label, "incomplete Bash recorder transport")


def _read_bash_recorder_log(
    path: Path, label: str, budget: _BashObservationReadBudget | None = None
) -> list[tuple[str, ...]]:
    """Parse argc-prefixed recorder frames incrementally and within all bounds."""
    read_budget = budget if budget is not None else _BashObservationReadBudget()
    fields = iter(_iter_bounded_nul_fields(path, label, read_budget))
    invocations: list[tuple[str, ...]] = []
    while True:
        try:
            header_field = next(fields)
        except StopIteration:
            break
        try:
            header = header_field.decode("ascii")
        except UnicodeDecodeError:
            raise SchemaValidationError(
                str(path), label, "invalid Bash recorder frame header"
            ) from None
        match = _BASH_ARGV_HEADER_RE.fullmatch(header)
        if match is None:
            raise SchemaValidationError(str(path), label, "invalid Bash recorder frame header")
        argc = int(match.group(1))
        if argc > _BASH_MAX_ARGV_ITEMS:
            raise SchemaValidationError(
                str(path), label, "recorder argv item count exceeded the bound"
            )
        frame_bytes = len(header_field) + 1
        if frame_bytes > _BASH_MAX_FRAME_BYTES:
            raise SchemaValidationError(str(path), label, "recorder frame exceeded the byte bound")
        args: list[str] = []
        for _ in range(argc):
            try:
                field = next(fields)
            except StopIteration:
                raise SchemaValidationError(
                    str(path), label, "truncated Bash recorder frame"
                ) from None
            frame_bytes += len(field) + 1
            if frame_bytes > _BASH_MAX_FRAME_BYTES:
                raise SchemaValidationError(
                    str(path), label, "recorder frame exceeded the byte bound"
                )
            try:
                args.append(field.decode("utf-8"))
            except UnicodeDecodeError:
                raise SchemaValidationError(
                    str(path), label, "Bash recorder argv is not UTF-8"
                ) from None
        read_budget.account_frame(path, label)
        invocations.append(tuple(args))
    return invocations


def _assert_observation_process_group_clean(proc: subprocess.Popen[bytes]) -> None:
    """Reject successful observation when its process group leaves live work."""
    process_group_id = proc.pid
    residual = _live_process_group_members(process_group_id)
    if not residual:
        return

    residual_ids = ", ".join(str(process_id) for process_id in sorted(residual))
    cleanup_residual = _terminate_process_group(proc, process_group_id)
    cleanup_detail = _cleanup_detail(cleanup_residual)
    raise SchemaValidationError(
        "Bash observation",
        "process-group",
        f"observation left live descendants in process group {proc.pid}: "
        f"{residual_ids}; failing closed; {cleanup_detail}",
    )


def _run_bash_observation(
    path: Path,
    function_name: str,
    recorder_fail_target: str | None = None,
    extra_env: dict[str, str] | None = None,
    repository_source: bool = True,
) -> list[tuple[str, ...]]:
    """Execute a local CI function and return exact recorder argv frames."""
    if repository_source:
        path = _observation_input_path(path, "shell source")
    else:
        path = path.resolve(strict=True)
        if not path.is_file():
            raise SchemaValidationError(str(path), function_name, "script is not a regular file")

    with tempfile.TemporaryDirectory(prefix="sa128b-") as temp_name:
        temp_dir = Path(temp_name)
        bin_dir = temp_dir / "bin"
        bin_dir.mkdir()
        recorder = bin_dir / "make"
        recorder.write_text(
            "#!/bin/bash\n"
            "set -u\n"
            'printf \'ARGV:%d\\0\' "$#" >> "${SA128_RECORDER_LOG:?}"\n'
            'printf \'%s\\0\' "$@" >> "${SA128_RECORDER_LOG:?}"\n'
            'for arg in "$@"; do\n'
            '    if [ "${SA128_RECORDER_FAIL_TARGET:-}" = "$arg" ]; then\n'
            '        exit "${SA128_RECORDER_FAIL_STATUS:-17}"\n'
            "    fi\n"
            "done\n"
            "exit 0\n",
            encoding="utf-8",
        )
        recorder.chmod(0o700)
        log_path = temp_dir / "make.log"
        log_path.touch()
        worker_dir = temp_dir / "workers"
        worker_dir.mkdir()
        launch_log_path = temp_dir / "launch.log"
        wait_log_path = temp_dir / "wait.log"
        env = {
            "PATH": str(bin_dir),
            # The production script resolves Python from PATH/Poetry.  The
            # observer intentionally has a recorder-only PATH, so provide the
            # checker interpreter explicitly to keep this isolated observation
            # deterministic without weakening contributor-side resolution.
            "PYTHON3": sys.executable,
            "HOME": str(temp_dir),
            "TMPDIR": str(temp_dir),
            "LANG": "C",
            "LC_ALL": "C",
            "SA128_RECORDER_LOG": str(log_path),
            "SA128_WORKER_DIR": str(worker_dir),
            "SA128_LAUNCH_LOG": str(launch_log_path),
            "SA128_WAIT_LOG": str(wait_log_path),
            "SA128_LAUNCH_COUNT": "0",
            "__SA128B_RESULT__": _BASH_RESULT_MARKER,
        }
        launch_log_path.touch()
        wait_log_path.touch()
        if recorder_fail_target is not None:
            env["SA128_RECORDER_FAIL_TARGET"] = recorder_fail_target
        if extra_env:
            env.update(extra_env)
        harness = _shell_observation_harness(path, function_name)
        process_group_id: int
        try:
            proc = subprocess.Popen(
                [
                    "/bin/bash",
                    "--noprofile",
                    "--norc",
                    "-c",
                    harness,
                    "sa128b",
                    str(path),
                    function_name,
                ],
                cwd=str(path.parent),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            # Bind the isolated observation group at spawn, not during a
            # later failure path when the direct child may already be gone.
            process_group_id = proc.pid
        except OSError as exc:
            raise SchemaValidationError(
                str(path), function_name, f"failed to start Bash: {exc}"
            ) from None

        try:
            stdout, stderr = _communicate_bounded(
                proc,
                _bash_observation_byte_limit(),
                _BASH_TIMEOUT_SECONDS,
                watched_file_bytes=lambda: _bash_observation_file_bytes(
                    log_path, launch_log_path, wait_log_path, worker_dir
                ),
            )
        except subprocess.TimeoutExpired:
            cleanup = _kill_make_process_group(proc, process_group_id)
            raise SchemaValidationError(
                str(path),
                function_name,
                f"Bash exceeded the {_BASH_TIMEOUT_SECONDS:g}s observation timeout; "
                f"{_cleanup_detail(cleanup)}",
            ) from None
        except _MakeOutputError as exc:
            cleanup = _kill_make_process_group(proc, process_group_id)
            raise SchemaValidationError(
                str(path),
                function_name,
                f"{str(exc).replace('GNU make', 'Bash')}; {_cleanup_detail(cleanup)}",
            ) from None

        returncode = _observation_returncode(proc, process_group_id, str(path))
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace").strip()
        marker_lines = [
            line for line in output.splitlines() if line.startswith(_BASH_RESULT_MARKER)
        ]
        if not marker_lines:
            detail = (
                error or output.strip() or f"Bash exited with status {returncode} before completion"
            )
            cleanup = _kill_make_process_group(proc, process_group_id)
            raise SchemaValidationError(
                str(path),
                function_name,
                f"incomplete Bash observation: {detail[:_BASH_ERROR_DETAIL_BYTES]}; "
                f"{_cleanup_detail(cleanup)}",
            )
        if returncode != 0:
            cleanup = _kill_make_process_group(proc, process_group_id)
            detail = error or f"Bash exited with status {returncode}"
            raise SchemaValidationError(
                str(path),
                function_name,
                f"Bash gate execution failed: {detail[:_BASH_ERROR_DETAIL_BYTES]}; "
                f"{_cleanup_detail(cleanup)}",
            )
        marker_value = marker_lines[-1][len(_BASH_RESULT_MARKER) :]
        try:
            observed_status = int(marker_value)
        except ValueError:
            cleanup = _kill_make_process_group(proc, process_group_id)
            raise SchemaValidationError(
                str(path),
                function_name,
                f"invalid Bash completion marker; {_cleanup_detail(cleanup)}",
            ) from None
        if observed_status != 0:
            cleanup = _kill_make_process_group(proc, process_group_id)
            raise SchemaValidationError(
                str(path),
                function_name,
                f"Bash gate execution returned status {observed_status}; "
                f"{_cleanup_detail(cleanup)}",
            )

        _assert_observation_process_group_clean(proc)

        read_budget = _BashObservationReadBudget()
        if function_name == "run_static_gates_parallel":
            launch_records: list[tuple[str, str, Path]] = []
            launch_events = _read_bash_event_log(launch_log_path, 3, "launch.log", read_budget)
            for stage_id, worker_pid, worker_log in launch_events:
                if not worker_pid.isdecimal():
                    raise SchemaValidationError(
                        str(path), function_name, "malformed launch event worker PID"
                    )
                worker_log_path = Path(worker_log)
                try:
                    worker_log_path = worker_log_path.resolve(strict=False)
                except OSError:
                    raise SchemaValidationError(
                        str(path), function_name, "invalid launch event worker log path"
                    ) from None
                if not worker_log_path.is_relative_to(worker_dir.resolve()) or not re.fullmatch(
                    r"worker_[0-9]+\.argv", worker_log_path.name
                ):
                    raise SchemaValidationError(
                        str(path),
                        function_name,
                        "launch event worker log is outside worker directory",
                    )
                launch_records.append((stage_id, worker_pid, worker_log_path))
            wait_events = _read_bash_event_log(wait_log_path, 2, "wait.log", read_budget)
            if any(actual_pid == "SPECIAL" for actual_pid, _ in wait_events) or len(
                wait_events
            ) != len(launch_events):
                raise SchemaValidationError(
                    str(path),
                    function_name,
                    "parallel observation did not explicitly join every launched worker",
                )
            for (_, expected_pid, _), (actual_pid, worker_status) in zip(
                launch_records, wait_events, strict=True
            ):
                if actual_pid != expected_pid:
                    raise SchemaValidationError(
                        str(path),
                        function_name,
                        "parallel workers were not joined in declaration order",
                    )
                if not worker_status.isdecimal() or int(worker_status) != 0:
                    raise SchemaValidationError(
                        str(path),
                        function_name,
                        f"parallel worker {expected_pid} failed with status {worker_status}",
                    )
            log_paths = [worker_log for _, _, worker_log in launch_records]
        else:
            log_paths = [log_path]

        invocations: list[tuple[str, ...]] = []
        for argv_log in log_paths:
            if not argv_log.exists():
                continue
            invocations.extend(
                _read_bash_recorder_log(argv_log, f"{function_name} recorder", read_budget)
            )
        return invocations


def _extract_observed_shell_gates(path: Path, function_name: str) -> set[str]:
    """Run a shell gate function and map recorder arguments to gate targets."""
    invocations = _run_bash_observation(path, function_name)
    gates: set[str] = set()
    for invocation in invocations:
        for argument in invocation:
            if _is_observed_shell_gate(argument):
                gates.add(argument)
    return gates


def _extract_check_ci_serial_gates(path: Path) -> set[str]:
    """Derive serial local-CI gates from actual Bash execution."""
    return _extract_observed_shell_gates(path, "run_static_gates_serial")


def _extract_check_ci_parallel_gates(path: Path) -> set[str]:
    """Derive parallel local-CI gates from actual Bash execution and joining."""
    return _extract_observed_shell_gates(path, "run_static_gates_parallel")


def _extract_ci_job_names(path: Path) -> set[str]:
    """
    Extract top-level job names from a GitHub Actions workflow YAML.

    Uses structural YAML parsing with duplicate-key rejection (BaseLoader-safe
    for the ``on:`` key).  Returns only top-level keys under ``jobs:`` that
    have a ``steps:`` or ``runs-on:`` subkey (i.e. real jobs, not metadata).

    Raises ``SchemaValidationError`` when the file is malformed, unreadable,
    or contains duplicate YAML keys (caller should treat this as exit 2).
    """
    jobs_raw = _workflow_jobs(path)
    jobs: set[str] = set()
    for key, value in jobs_raw.items():
        if isinstance(key, str) and isinstance(value, dict):
            # A job is a mapping with runs-on and/or steps.  Reusable-workflow
            # references and other YAML mappings are deliberately excluded.
            if "runs-on" in value or "steps" in value:
                jobs.add(key)
    return jobs


def _workflow_jobs(path: Path) -> dict[Any, Any]:
    """Load a workflow and return its structurally parsed ``jobs`` mapping."""
    canonical = _observation_input_path(path, "workflow source")
    text = canonical.read_text(encoding="utf-8")
    data = _parse_yaml_strict(text, str(canonical))
    jobs_raw = data.get("jobs")
    if not isinstance(jobs_raw, dict):
        if "jobs" not in data:
            raise SchemaValidationError(str(path), "", "workflow has no jobs section")
        raise SchemaValidationError(str(path), "jobs", "jobs must be a mapping")
    return jobs_raw


def _workflow_job_steps(path: Path, job_name: str, job_value: Any) -> list[dict[Any, Any]]:
    """Return a workflow job's steps after validating its structural shape."""
    if not isinstance(job_value, dict):
        raise SchemaValidationError(str(path), f"jobs.{job_name}", "job must be a mapping")
    steps = job_value.get("steps", [])
    if not isinstance(steps, list):
        raise SchemaValidationError(str(path), f"jobs.{job_name}.steps", "steps must be a list")
    validated: list[dict[Any, Any]] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise SchemaValidationError(
                str(path), f"jobs.{job_name}.steps[{index}]", "step must be a mapping"
            )
        run_value = step.get("run")
        if "run" in step and not isinstance(run_value, str):
            raise SchemaValidationError(
                str(path), f"jobs.{job_name}.steps[{index}].run", "run must be a string"
            )
        validated.append(step)
    return validated


def _extract_ci_needs(path: Path) -> dict[str, tuple[str, ...]]:
    """Extract the complete hosted job dependency topology from YAML."""
    jobs_raw = _workflow_jobs(path)
    job_names = {
        key
        for key, value in jobs_raw.items()
        if isinstance(key, str)
        and isinstance(value, dict)
        and ("runs-on" in value or "steps" in value)
    }
    topology: dict[str, tuple[str, ...]] = {}
    for job_name in sorted(job_names):
        job_value = jobs_raw[job_name]
        assert isinstance(job_value, dict)
        needs = job_value.get("needs", [])
        if isinstance(needs, str):
            needs_values = (needs,)
        elif isinstance(needs, list) and all(isinstance(item, str) for item in needs):
            needs_values = tuple(needs)
        else:
            raise SchemaValidationError(
                str(path), f"jobs.{job_name}.needs", "needs must be a string or list of strings"
            )
        unknown = set(needs_values) - job_names
        if unknown:
            raise SchemaValidationError(
                str(path),
                f"jobs.{job_name}.needs",
                f"needs unknown job(s): {', '.join(sorted(unknown))}",
            )
        topology[job_name] = needs_values
    return topology


def _extract_ci_run_values(
    path: Path, bound_jobs: set[str] | None = None
) -> dict[str, tuple[str, ...]]:
    """
    Extract ordered ``run:`` values by job from a workflow's YAML tree.

    ``bound_jobs`` narrows the result to registry-bound hosted jobs.  Keeping
    the values grouped by job preserves both the workflow's stage topology and
    the command order inside each job without interpreting shell-looking text.
    """
    jobs_raw = _workflow_jobs(path)
    available_jobs = _extract_ci_job_names(path)
    selected_jobs = available_jobs if bound_jobs is None else bound_jobs
    unknown = selected_jobs - available_jobs
    if unknown:
        raise SchemaValidationError(
            str(path), "jobs", f"bound job(s) are not workflow jobs: {', '.join(sorted(unknown))}"
        )
    values: dict[str, tuple[str, ...]] = {}
    for job_name in sorted(selected_jobs):
        steps = _workflow_job_steps(path, job_name, jobs_raw[job_name])
        values[job_name] = tuple(step["run"] for step in steps if isinstance(step.get("run"), str))
    return values


def _extract_hosted_run_values(
    path: Path, bound_jobs: set[str] | None = None
) -> dict[str, tuple[str, ...]]:
    """Alias naming the hosted-CI command observation explicitly."""
    return _extract_ci_run_values(path, bound_jobs)


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
    jobs_raw = _workflow_jobs(path)
    gates: set[str] = set()

    for job_name, job_value in jobs_raw.items():
        if not isinstance(job_name, str):
            continue
        if not isinstance(job_value, dict) or not ("runs-on" in job_value or "steps" in job_value):
            continue

        # Add top-level job name as a gate identifier
        gates.add(job_name)

        # Execute every run block through the SA128b recorder.  The recorder,
        # rather than a source-text search, supplies the make argv inventory.
        for step in _workflow_job_steps(path, job_name, job_value):
            run_value = step.get("run")
            if isinstance(run_value, str):
                _validate_publish_run_block(run_value, path, job_name)

    run_values = _extract_publish_run_values(path)
    for invocation in _observe_publish_run_blocks(run_values, path):
        for argument in invocation:
            if _is_observed_shell_gate(argument):
                gates.add(argument)

    return gates


def _extract_publish_run_values(path: Path) -> list[tuple[str, str]]:
    """Extract every publish ``run:`` value in workflow order."""
    jobs_raw = _workflow_jobs(path)
    values: list[tuple[str, str]] = []
    for job_name, job_value in jobs_raw.items():
        if not isinstance(job_name, str) or not isinstance(job_value, dict):
            continue
        if not ("runs-on" in job_value or "steps" in job_value):
            continue
        for step in _workflow_job_steps(path, job_name, job_value):
            run_value = step.get("run")
            if isinstance(run_value, str):
                values.append((job_name, run_value))
    return values


_GITHUB_EXPRESSION_RE = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)


def _publish_observation_source(run_value: str) -> str:
    """Wrap a workflow run block as a Bash function for recorder execution."""
    # GitHub expands expressions before invoking Bash.  Replace expressions
    # with an empty shell word for the local observation; the YAML value itself
    # remains the canonical oracle returned by _extract_publish_run_values.
    normalized = _GITHUB_EXPRESSION_RE.sub("''", run_value)
    # GitHub's runner enables errexit for each block.  The observer must let
    # unrelated, unavailable release tooling continue so it can reach and
    # record every make invocation; the recorder itself still fails closed.
    normalized = normalized.replace("set -euo pipefail", "set +e")
    return f"run_publish_block() {{\n{normalized}\nreturn 0\n}}\n"


def _observe_publish_run_blocks(
    run_values: list[tuple[str, str]], path: Path
) -> list[tuple[str, ...]]:
    """Observe each publish run block in its own bounded SA128b session."""
    invocations: list[tuple[str, ...]] = []
    with tempfile.TemporaryDirectory(prefix="sa128c-publish-") as temp_name:
        temp_dir = Path(temp_name)
        scripts_dir = temp_dir / "scripts"
        scripts_dir.mkdir()
        for command in ("version_tool.sh", "provision_test_roles.sh", "test_integration.sh"):
            stub = scripts_dir / command
            stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            stub.chmod(0o700)
        for index, (_, run_value) in enumerate(run_values):
            source = temp_dir / f"publish_run_{index}.sh"
            source.write_text(_publish_observation_source(run_value), encoding="utf-8")
            try:
                # _run_bash_observation creates a fresh recorder, Bash process,
                # environment, and cwd for every workflow step.  Do not combine
                # these functions: GitHub Actions starts each run block in a
                # separate shell, so shell state must not cross step boundaries.
                step_invocations = _run_bash_observation(
                    source,
                    "run_publish_block",
                    extra_env={
                        "GITHUB_WORKSPACE": str(_REPO_ROOT),
                        "GITHUB_REF": "refs/tags/v0.0.0",
                    },
                    repository_source=False,
                )
            except SchemaValidationError as exc:
                raise SchemaValidationError(
                    str(path),
                    f"publish.step[{index}]",
                    f"publish run observation failed: {exc.message}",
                ) from exc
            invocations.extend(step_invocations)
    return invocations


def _validate_publish_run_block(run_value: str, path: Path, job_name: str) -> None:
    """
    Reject shell control forms that make a publish gate ambiguous.

    Gate membership itself is never inferred here.  This guard only rejects
    control-flow forms that would make a recorder result non-canonical; the
    actual argv inventory comes from Bash execution below.
    """
    run_lines = run_value.splitlines()
    for line_index, line in enumerate(run_lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "make" not in stripped:
            continue
        before_make, _, after_make = stripped.partition("make")
        after_target = after_make.split("#", 1)[0].strip()
        if re.search(r"\|\||&&|[^>];|;\s*$|\|\s+[a-z]|&(?!>)\s*$|`|\$\(|subshell", after_target):
            raise SchemaValidationError(
                str(path),
                f"jobs.{job_name}",
                f"Deceptive/control make invocation in publish.yml: {stripped!r}",
            )
        if re.search(r"\b(if|then|else|elif|for|while|case|do|done|esac|fi)\b", before_make):
            raise SchemaValidationError(
                str(path),
                f"jobs.{job_name}",
                f"Conditional/loop-wrapped make invocation: {stripped!r}",
            )
        if line_index:
            previous = run_lines[line_index - 1].strip()
            previous_is_control = re.search(r"\b(if|for|while|case)\s", previous.split("#", 1)[0])
            if previous_is_control or previous.rstrip().endswith(
                ("|", "&&", "||", "then", "do", "else", "elif")
            ):
                raise SchemaValidationError(
                    str(path),
                    f"jobs.{job_name}",
                    f"Make invocation inside control flow: {stripped!r} (preceded by {previous!r})",
                )


def _extract_e2e_trigger_paths(path: Path) -> list[str]:
    """
    Extract the ordered path allowlist from e2e.yml (order preserved, duplicates allowed).

    Only extracts paths from the ``pull_request.paths:`` block.  Skips
    comments and non-path list entries.  Uses column-based indentation
    tracking to avoid false exits from child keys like ``branches:``.
    """
    canonical = _observation_input_path(path, "workflow source")
    text = canonical.read_text(encoding="utf-8")
    data = _parse_yaml_strict(text, str(canonical))
    trigger = data.get("on")
    if not isinstance(trigger, dict):
        raise SchemaValidationError(str(path), "on", "workflow trigger section must be a mapping")
    pull_request = trigger.get("pull_request")
    if not isinstance(pull_request, dict):
        raise SchemaValidationError(str(path), "on.pull_request", "pull_request must be a mapping")
    raw_paths = pull_request.get("paths")
    if not isinstance(raw_paths, list):
        raise SchemaValidationError(str(path), "on.pull_request.paths", "paths must be a list")
    paths: list[str] = []
    for index, value in enumerate(raw_paths):
        if not isinstance(value, str) or not value:
            raise SchemaValidationError(
                str(path), f"on.pull_request.paths[{index}]", "path must be a non-empty string"
            )
        paths.append(value)
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
    if source is None:
        return set()
    source = _canonical_input_path(source, f"{context} source")

    if context in ("local-serial",):
        make_targets = _extract_check_ci_serial_gates(source)
        return {target_to_gate[t] for t in make_targets if t in target_to_gate}

    if context in ("local-parallel",):
        make_targets = _extract_check_ci_parallel_gates(source)
        return {target_to_gate[t] for t in make_targets if t in target_to_gate}

    if context == "hosted":
        # Parse all dependency edges and every command in registry-bound jobs
        # before deriving membership.  This keeps hosted stage topology and
        # command values on the same structural YAML path as job membership.
        _extract_ci_needs(source)
        job_names = _extract_ci_job_names(source)
        _extract_hosted_run_values(source, set(job_to_gate) & job_names)
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
    # Every gate's make_target must be an effective Makefile target.  For
    # check gates (make_targets named ``check-*``) effectiveness means
    # membership in the real ``check`` aggregation: the target must be
    # reachable from ``check`` through GNU make's own database semantics —
    # resolved prerequisites and ``$(MAKE)`` recipe goals — and must itself
    # be effective (own a recipe or prove runnable under ``--dry-run``).  A
    # standalone recipe-owning gate that was removed from ``check`` is
    # deliberately absent: global target effectiveness is not check
    # aggregation.  Non-check gates (``frontend-proof``, ``smoke-install``)
    # are standalone gates gated by their own contexts, so their Makefile
    # requirement is plain effectiveness.
    # Observation executes the Makefile through GNU make, so the canonical
    # input must first pass the plain in-repo file check (fail-hard).
    _assert_canonical_makefile_input(_MAKEFILE_PATH)
    records, variables = _observe_makefile(_MAKEFILE_PATH)
    makefile_effective = _effective_makefile_targets(_MAKEFILE_PATH, records)
    check_members = _check_reachable_targets(records, variables)
    for gate in registry_gates:
        gid = gate["id"]
        bindings = gate.get("bindings", {})
        mt = bindings.get("make_target")
        if not (mt and isinstance(mt, str)):
            continue
        if mt.startswith("check-"):
            if mt not in check_members:
                diagnostics.append(
                    {
                        "level": "missing",
                        "context": "makefile",
                        "gate_id": gid,
                        "source": "Makefile",
                        "detail": (
                            f"Gate {gid!r} declares check make_target {mt!r} "
                            f"but that target is not reachable from the check "
                            f"target (not a member of the check aggregation)"
                        ),
                    }
                )
            elif mt not in makefile_effective:
                diagnostics.append(
                    {
                        "level": "missing",
                        "context": "makefile",
                        "gate_id": gid,
                        "source": "Makefile",
                        "detail": (
                            f"Gate {gid!r} declares check make_target {mt!r} "
                            f"which is reachable from check but is not an "
                            f"effective target (no recipe and no runnable "
                            f"delegation)"
                        ),
                    }
                )
        elif mt not in makefile_effective:
            diagnostics.append(
                {
                    "level": "missing",
                    "context": "makefile",
                    "gate_id": gid,
                    "source": "Makefile",
                    "detail": (
                        f"Gate {gid!r} declares make_target {mt!r} "
                        f"but that target is not an effective Makefile target "
                        f"(no recipe and no runnable delegation)"
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
    if e2e_source and has_e2e_requirement:
        e2e_source = _canonical_input_path(e2e_source, "e2e-trigger source")
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
