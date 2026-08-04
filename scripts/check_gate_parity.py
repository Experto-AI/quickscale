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
from collections.abc import Iterator
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


def _kill_make_process_group(proc: subprocess.Popen[bytes]) -> None:
    """Kill the observed make and its whole process group (``$(shell)`` children)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _communicate_bounded(
    proc: subprocess.Popen[bytes],
    max_bytes: int,
    timeout: float,
) -> tuple[bytes, bytes]:
    """
    Read both pipes with a combined byte bound and a hard deadline.

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

    def drain(key: selectors.SelectorKey) -> None:
        nonlocal total
        sink: bytearray = key.data
        fileobj = key.fileobj
        while True:
            if isinstance(fileobj, int):
                chunk = os.read(fileobj, 65536)
            else:
                chunk = os.read(fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(fileobj)
                return
            sink.extend(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise _MakeOutputError(
                    f"GNU make exceeded the {max_bytes} byte observation output bound"
                )

    try:
        while selector.get_map():
            if proc.poll() is not None:
                # Process finished: drain remaining pipe data without a deadline.
                for key in tuple(selector.get_map().values()):
                    drain(key)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            for key, _ in selector.select(timeout=remaining):
                drain(key)
    finally:
        selector.close()
    return bytes(out_sink), bytes(err_sink)


def _run_make(args: list[str], cwd: Path, label: str) -> _MakeResult:
    """
    Run GNU make with a controlled environment and hard observation bounds.

    Raises ``SchemaValidationError`` when make cannot be started, exceeds the
    timeout or output bound, or exits with a GNU make error code (>= 2) —
    which for a query/dry-run invocation means the Makefile is malformed.
    Exit codes 0 and 1 are valid database output (``-q`` returns 1 when the
    default goal would need updating).
    """
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
    except FileNotFoundError:
        raise SchemaValidationError(label, "", "GNU make executable not found on PATH") from None
    except OSError as exc:
        raise SchemaValidationError(label, "", f"failed to start GNU make: {exc}") from None

    try:
        stdout, stderr = _communicate_bounded(proc, _MAKE_MAX_OUTPUT_BYTES, _MAKE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_make_process_group(proc)
        raise SchemaValidationError(
            label, "", f"GNU make exceeded the {_MAKE_TIMEOUT_SECONDS:g}s observation timeout"
        ) from None
    except _MakeOutputError as exc:
        _kill_make_process_group(proc)
        raise SchemaValidationError(label, "", str(exc)) from None

    returncode = proc.wait()
    if returncode not in (0, 1):
        detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
        if detail:
            detail = detail[:_MAKE_ERROR_DETAIL_BYTES]
            message = f"GNU make exited with status {returncode}: {detail}"
        else:
            message = f"GNU make exited with status {returncode}"
        raise SchemaValidationError(label, "", message)
    return _MakeResult(returncode, stdout, stderr)


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
    result = _run_make(
        ["-n", "-r", "-R", "--no-print-directory", "-f", str(path), target],
        path.parent,
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
        elif _dry_run_runs_commands(path, name):
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
    if not path.exists():
        raise SchemaValidationError(str(path), "", "Makefile not found")
    if not path.is_file():
        raise SchemaValidationError(str(path), "", "Makefile is not a regular file")
    result = _run_make(
        ["-qp", "-r", "-R", "--no-print-directory", "-f", str(path)],
        path.parent,
        str(path),
    )
    text = result.stdout.decode("utf-8", errors="replace")
    records = _parse_make_database(text, str(path))
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
    if path.is_symlink():
        raise SchemaValidationError(str(path), "", "Makefile must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise FileNotFoundError(path) from None
    if not resolved.is_file():
        raise SchemaValidationError(str(path), "", "Makefile is not a regular file")
    if not resolved.is_relative_to(_REPO_ROOT.resolve()):
        raise SchemaValidationError(str(path), "", "Makefile must reside inside the repository")


# ---------------------------------------------------------------------------
# Bash semantic observation (SA128b)
# ---------------------------------------------------------------------------

_BASH_TIMEOUT_SECONDS = 30.0
_BASH_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_BASH_ERROR_DETAIL_BYTES = 400
_BASH_RESULT_MARKER = "__SA128B_RESULT__"
_BASH_PROCESS_GROUP_SETTLE_SECONDS = 0.05
_BASH_PROCESS_GROUP_CLEANUP_SECONDS = 5.0
_SHELL_GATE_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_OBSERVED_GATE_NAMES: frozenset[str] = frozenset({"frontend-proof", "smoke-install"})
_BASH_ARGV_HEADER_RE = re.compile(r"^ARGV:([0-9]+)$")


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
    try:
        canonical = path.resolve() == (_REPO_ROOT / "scripts" / "check_ci_locally.sh").resolve()
    except OSError:
        canonical = False
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
declare -a launch_pids=()
declare -a launch_logs=()
declare -a wait_pids=()
declare -a wait_statuses=()

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

if [ "$observed_status" -eq 0 ] && [ "${2:-run_static_gates}" = "run_static_gates_parallel" ]; then
    validation_error=""
    launch_count=0
    expected_pid=""
    actual_pid=""
    worker_status=0
    while IFS=$'\\t' read -r stage_id worker_pid worker_log; do
        [ -n "${worker_pid:-}" ] || continue
        launch_count=$((launch_count + 1))
        launch_pids[$((launch_count - 1))]="$worker_pid"
        launch_logs[$((launch_count - 1))]="$worker_log"
    done < "$SA128_LAUNCH_LOG"

    wait_count=0
    special_wait=false
    while IFS=$'\\t' read -r actual_pid worker_status; do
        if [ "${actual_pid:-}" = "SPECIAL" ]; then
            special_wait=true
            continue
        fi
        [ -n "${actual_pid:-}" ] || continue
        wait_pids[$wait_count]="$actual_pid"
        wait_statuses[$wait_count]="${worker_status:-127}"
        wait_count=$((wait_count + 1))
    done < "$SA128_WAIT_LOG"

    if [ "$special_wait" = true ] || [ "$wait_count" -ne "$launch_count" ]; then
        validation_error="parallel observation did not explicitly join every launched worker"
    else
        for ((i = 0; i < launch_count; i++)); do
            expected_pid="${launch_pids[$i]}"
            actual_pid="${wait_pids[$i]}"
            if [ "$expected_pid" != "$actual_pid" ]; then
                validation_error="parallel workers were not joined in declaration order"
                break
            fi
            worker_status="${wait_statuses[$i]}"
            if [ "$worker_status" -ne 0 ]; then
                validation_error="parallel worker $expected_pid failed with status $worker_status"
                break
            fi
        done
    fi

    if [ -z "$validation_error" ]; then
        for ((i = 0; i < launch_count; i++)); do
            worker_pid="${launch_pids[$i]}"
            if kill -0 "$worker_pid" 2>/dev/null; then
                validation_error="parallel observation left worker $worker_pid running"
                break
            fi
        done
    fi
    if [ -n "$validation_error" ]; then
        printf '%s\\n' "$validation_error" >&2
        observed_status=2
    fi
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


def _terminate_process_group(proc: subprocess.Popen[bytes]) -> dict[int, str]:
    """Terminate and wait for every live member of an observed process group."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

    residual = _live_process_group_members(proc.pid)
    if residual:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return _wait_for_process_group_cleanup(proc.pid)


def _assert_observation_process_group_clean(proc: subprocess.Popen[bytes]) -> None:
    """Reject successful observation when its process group leaves live work."""
    residual = _live_process_group_members(proc.pid)
    if not residual:
        # Require a second empty observation to close the fork-after-check race.
        time.sleep(_BASH_PROCESS_GROUP_SETTLE_SECONDS)
        residual = _live_process_group_members(proc.pid)
    if not residual:
        return

    residual_ids = ", ".join(str(process_id) for process_id in sorted(residual))
    cleanup_residual = _terminate_process_group(proc)
    if cleanup_residual:
        remaining_ids = ", ".join(str(process_id) for process_id in sorted(cleanup_residual))
        cleanup_detail = f"; cleanup left live members {remaining_ids}"
    else:
        cleanup_detail = "; residual process group terminated and reaped"
    raise SchemaValidationError(
        "Bash observation",
        "process-group",
        f"observation left live descendants in process group {proc.pid}: "
        f"{residual_ids}; failing closed{cleanup_detail}",
    )


def _run_bash_observation(
    path: Path,
    function_name: str,
    recorder_fail_target: str | None = None,
) -> list[tuple[str, ...]]:
    """Execute a local CI function and return exact recorder argv frames."""
    if not path.exists():
        raise SchemaValidationError(str(path), function_name, "script not found")
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
        env = {
            "PATH": str(bin_dir),
            "HOME": str(temp_dir),
            "TMPDIR": str(temp_dir),
            "LANG": "C",
            "LC_ALL": "C",
            "SA128_RECORDER_LOG": str(log_path),
            "SA128_WORKER_DIR": str(worker_dir),
            "SA128_LAUNCH_LOG": str(temp_dir / "launch.log"),
            "SA128_WAIT_LOG": str(temp_dir / "wait.log"),
            "SA128_LAUNCH_COUNT": "0",
            "__SA128B_RESULT__": _BASH_RESULT_MARKER,
        }
        (temp_dir / "launch.log").touch()
        (temp_dir / "wait.log").touch()
        if recorder_fail_target is not None:
            env["SA128_RECORDER_FAIL_TARGET"] = recorder_fail_target
        harness = _shell_observation_harness(path, function_name)
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
        except OSError as exc:
            raise SchemaValidationError(
                str(path), function_name, f"failed to start Bash: {exc}"
            ) from None

        try:
            stdout, stderr = _communicate_bounded(
                proc, _BASH_MAX_OUTPUT_BYTES, _BASH_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            _kill_make_process_group(proc)
            raise SchemaValidationError(
                str(path),
                function_name,
                f"Bash exceeded the {_BASH_TIMEOUT_SECONDS:g}s observation timeout",
            ) from None
        except _MakeOutputError as exc:
            _kill_make_process_group(proc)
            raise SchemaValidationError(
                str(path), function_name, str(exc).replace("GNU make", "Bash")
            ) from None

        returncode = proc.wait()
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace").strip()
        marker_lines = [
            line for line in output.splitlines() if line.startswith(_BASH_RESULT_MARKER)
        ]
        if not marker_lines:
            detail = (
                error or output.strip() or f"Bash exited with status {returncode} before completion"
            )
            raise SchemaValidationError(
                str(path),
                function_name,
                f"incomplete Bash observation: {detail[:_BASH_ERROR_DETAIL_BYTES]}",
            )
        if returncode != 0:
            _kill_make_process_group(proc)
            detail = error or f"Bash exited with status {returncode}"
            raise SchemaValidationError(
                str(path),
                function_name,
                f"Bash gate execution failed: {detail[:_BASH_ERROR_DETAIL_BYTES]}",
            )
        marker_value = marker_lines[-1][len(_BASH_RESULT_MARKER) :]
        try:
            observed_status = int(marker_value)
        except ValueError:
            raise SchemaValidationError(
                str(path), function_name, "invalid Bash completion marker"
            ) from None
        if observed_status != 0:
            raise SchemaValidationError(
                str(path), function_name, f"Bash gate execution returned status {observed_status}"
            )

        _assert_observation_process_group_clean(proc)

        if function_name == "run_static_gates_parallel":
            launch_records: list[tuple[str, str, Path]] = []
            for line in (temp_dir / "launch.log").read_text(encoding="utf-8").splitlines():
                stage_id, worker_pid, worker_log = line.split("\t", 2)
                launch_records.append((stage_id, worker_pid, Path(worker_log)))
            log_paths = [worker_log for _, _, worker_log in launch_records]
        else:
            log_paths = [log_path]

        invocations: list[tuple[str, ...]] = []
        for argv_log in log_paths:
            if not argv_log.exists():
                continue
            raw = argv_log.read_bytes()
            if not raw:
                continue
            if not raw.endswith(b"\0"):
                raise SchemaValidationError(
                    str(path), function_name, "incomplete Bash recorder transport"
                )
            fields = raw[:-1].split(b"\0")
            field_index = 0
            while field_index < len(fields):
                try:
                    header = fields[field_index].decode("ascii")
                except UnicodeDecodeError:
                    raise SchemaValidationError(
                        str(path), function_name, "invalid Bash recorder frame header"
                    ) from None
                match = _BASH_ARGV_HEADER_RE.fullmatch(header)
                if match is None:
                    raise SchemaValidationError(
                        str(path), function_name, "invalid Bash recorder frame header"
                    )
                argc = int(match.group(1))
                first_arg = field_index + 1
                last_arg = first_arg + argc
                if last_arg > len(fields):
                    raise SchemaValidationError(
                        str(path), function_name, "truncated Bash recorder frame"
                    )
                try:
                    invocation = tuple(
                        field.decode("utf-8") for field in fields[first_arg:last_arg]
                    )
                except UnicodeDecodeError:
                    raise SchemaValidationError(
                        str(path), function_name, "Bash recorder argv is not UTF-8"
                    ) from None
                invocations.append(invocation)
                field_index = last_arg
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
            # ``in_paths`` is only ever set together with ``paths_indent``, so
            # this assert is a pure type-narrowing no-op (SA128a mypy fix).
            assert paths_indent is not None
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
