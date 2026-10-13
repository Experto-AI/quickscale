#!/usr/bin/env python3
"""
Private sibling: the authoritative gate-registry schema (SA267).

``check_gate_parity`` re-exports every name in this module as its pre-split
surface; the strict-JSON loader and the decomposed ``_validate_registry`` live
here so the facade stays inside the file-size and complexity thresholds.
Diagnostic messages, field paths, and the order in which the first violation
is reported are the pre-split contract and are pinned by the parity controls.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent

_TRIGGER_INPUTS_CONTRACT = (
    "trigger_inputs is the ordered, bidirectional E2E allowlist partition; "
    "it never controls whether a gate runs"
)

_KNOWN_CONTEXTS: frozenset[str] = frozenset(
    {
        "local-serial",
        "local-parallel",
        "hosted",
        "publish",
        "e2e-trigger",
    }
)

_TOP_LEVEL_KEYS: frozenset[str] = frozenset({"schema_version", "description", "contexts", "gates"})

_GATE_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "description",
        "required_contexts",
        "bindings",
        "make_recipe",
        "depends_on",
        "trigger_inputs",
    }
)

_BINDING_KEYS: frozenset[str] = frozenset({"make_target", "ci_job", "local_ci_stage"})

_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
_PATH_SAFE_RE = re.compile(r"^(?!.*\.\.)[a-zA-Z0-9_./*-]+$")


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


def _is_strict_int(value: object) -> bool:
    """Return True if *value* is an ``int`` but not a ``bool``."""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass
class _RegistryIndex:
    """Per-registry bookkeeping shared across the per-gate validators."""

    seen_ids: set[str] = field(default_factory=set)
    seen_make_targets: dict[str, str] = field(default_factory=dict)
    seen_ci_jobs: dict[str, str] = field(default_factory=dict)


def _validate_top_level_keys(data: dict[str, Any]) -> None:
    """Reject unknown top-level keys before missing ones, as pre-split."""
    top_unknown = set(data.keys()) - _TOP_LEVEL_KEYS
    if top_unknown:
        raise SchemaValidationError(
            "registry",
            "",
            f"unknown top-level key(s): {', '.join(sorted(top_unknown))}",
        )
    top_missing = _TOP_LEVEL_KEYS - set(data.keys())
    if top_missing:
        raise SchemaValidationError(
            "registry",
            "",
            f"missing required top-level key(s): {', '.join(sorted(top_missing))}",
        )


def _validate_schema_version(data: dict[str, Any]) -> None:
    """Require schema_version 1 and reject booleans masquerading as integers."""
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


def _validate_registry_description(data: dict[str, Any]) -> None:
    """Require a non-empty top-level description."""
    desc_top = data.get("description")
    if not isinstance(desc_top, str) or not desc_top:
        raise SchemaValidationError(
            "registry",
            "description",
            "description must be a non-empty string",
        )


def _validate_contexts(contexts: Any) -> frozenset[str]:
    """Require the exact known context set with non-empty descriptions."""
    if not isinstance(contexts, dict):
        raise SchemaValidationError(
            "registry",
            "contexts",
            f"contexts must be a dict (got {type(contexts).__name__})",
        )

    declared_contexts = set(contexts.keys())
    unknown = declared_contexts - _KNOWN_CONTEXTS
    if unknown:
        raise SchemaValidationError(
            "registry",
            "contexts",
            f"unknown context(s): {', '.join(sorted(unknown))}",
        )
    missing_contexts = _KNOWN_CONTEXTS - declared_contexts
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
    return _KNOWN_CONTEXTS


def _require_gates(gates: Any) -> list[dict[str, Any]]:
    """Require a non-empty gates list."""
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
    return gates


def _require_gate_keys(gate: dict[str, Any], i: int) -> None:
    """Reject unknown gate keys, then missing required ones (make_recipe optional)."""
    gate_unknown = set(gate.keys()) - _GATE_KEYS
    if gate_unknown:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}]",
            f"unknown key(s) in gate[{i}]: {', '.join(sorted(gate_unknown))}",
        )
    gate_missing = (_GATE_KEYS - {"make_recipe"}) - set(gate.keys())
    if gate_missing:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}]",
            f"missing required key(s) in gate[{i}]: {', '.join(sorted(gate_missing))}",
        )


def _validate_gate_id(gate: dict[str, Any], i: int, index: _RegistryIndex) -> str:
    """Validate and register one gate id."""
    gid = gate.get("id")
    if not isinstance(gid, str) or not gid:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].id",
            f"gate[{i}].id must be a non-empty string",
        )
    if not _ID_RE.match(gid):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].id",
            f"gate[{i}].id {gid!r} contains unsafe characters",
        )
    if gid in index.seen_ids:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].id",
            f"duplicate gate id: {gid!r}",
        )
    index.seen_ids.add(gid)
    return gid


def _validate_gate_description(gate: dict[str, Any], i: int, gid: str) -> None:
    """Require a non-empty gate description."""
    desc = gate.get("description")
    if not isinstance(desc, str) or not desc:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].description",
            f"gate[{i}] ({gid}).description must be a non-empty string",
        )


def _validate_required_contexts(
    gate: dict[str, Any], i: int, gid: str, known_contexts: frozenset[str]
) -> list[str]:
    """Require non-empty, known, duplicate-free required_contexts."""
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
    return rc


def _validate_gate_bindings(gate: dict[str, Any], i: int, gid: str) -> dict[str, Any]:
    """Validate the bindings mapping's shape and value types."""
    bindings = gate.get("bindings")
    if not isinstance(bindings, dict):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].bindings",
            f"gate[{i}] ({gid}).bindings must be a dict",
        )
    bind_unknown = set(bindings.keys()) - _BINDING_KEYS
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
    return bindings


def _register_binding_collisions(
    bindings: dict[str, Any], i: int, gid: str, index: _RegistryIndex
) -> None:
    """Reject make_target / ci_job values already claimed by another gate."""
    mt = bindings.get("make_target")
    if mt and isinstance(mt, str):
        if mt in index.seen_make_targets:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].bindings.make_target",
                f"make_target {mt!r} already used by gate {index.seen_make_targets[mt]!r}",
            )
        index.seen_make_targets[mt] = gid

    cj = bindings.get("ci_job")
    if cj and isinstance(cj, str):
        if cj in index.seen_ci_jobs:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].bindings.ci_job",
                f"ci_job {cj!r} already used by gate {index.seen_ci_jobs[cj]!r}",
            )
        index.seen_ci_jobs[cj] = gid


def _validate_make_recipe(gate: dict[str, Any], i: int, gid: str, bindings: dict[str, Any]) -> None:
    """Validate the optional generated Make recipe lines."""
    # Optional.  When present it is the single authored copy of the gate's
    # Make recipe; ``sync_ci_gate_jobs.py`` renders it into the generated
    # ``scripts/gates.mk`` include.  A gate without it keeps its recipe
    # hand-written in the Makefile.
    recipe = gate.get("make_recipe")
    if recipe is None:
        return
    if not isinstance(recipe, list):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].make_recipe",
            f"gate[{i}] ({gid}).make_recipe must be a list of recipe-line strings",
        )
    if not recipe:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].make_recipe",
            f"gate[{i}] ({gid}).make_recipe must be a non-empty list",
        )
    for ridx, recipe_line in enumerate(recipe):
        if not isinstance(recipe_line, str) or not recipe_line:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].make_recipe[{ridx}]",
                f"gate[{i}] ({gid}).make_recipe[{ridx}] must be a non-empty string",
            )
        if "\n" in recipe_line or "\r" in recipe_line or recipe_line != recipe_line.strip():
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].make_recipe[{ridx}]",
                f"gate[{i}] ({gid}).make_recipe[{ridx}] must be one whitespace-trimmed recipe line",
            )
    if not isinstance(bindings.get("make_target"), str):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].make_recipe",
            f"gate[{i}] ({gid}).make_recipe requires a string make_target binding",
        )


def _validate_local_membership(rc: list[str], bindings: dict[str, Any], i: int, gid: str) -> None:
    """
    Require local-context gates to be executable by the local runner.

    A gate that declares a local execution context must carry the Make target
    and the stage the local runner's fan-out derives from (stages 3-7).
    Otherwise both local-CI modes skip it silently: a registry edit would pass
    generation and currency while the gate never runs locally.
    """
    local_contexts = sorted({"local-serial", "local-parallel"} & set(rc))
    if not local_contexts:
        return
    local_target = bindings.get("make_target")
    if not isinstance(local_target, str) or not local_target:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].bindings.make_target",
            f"gate[{i}] ({gid}) declares local context(s) "
            f"{', '.join(local_contexts)} but has no Make target for the local runner",
        )
    lcs = bindings.get("local_ci_stage")
    if not _is_strict_int(lcs) or not 3 <= lcs <= 7:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].bindings.local_ci_stage",
            f"gate[{i}] ({gid}) declares local context(s) "
            f"{', '.join(local_contexts)} but local_ci_stage {lcs!r} is outside the "
            f"executable stages 3-7",
        )


def _validate_depends_on(gate: dict[str, Any], i: int, gid: str) -> None:
    """Require depends_on to be a list of non-empty strings."""
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


def _validate_trigger_inputs(gate: dict[str, Any], i: int, gid: str) -> None:
    """Require path-safe, unique trigger_inputs entries."""
    ti = gate.get("trigger_inputs")
    if not isinstance(ti, list):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].trigger_inputs",
            f"gate[{i}] ({gid}).trigger_inputs must be a list; {_TRIGGER_INPUTS_CONTRACT}",
        )
    seen_ti: set[str] = set()
    for pidx, pp in enumerate(ti):
        if not isinstance(pp, str) or not pp:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].trigger_inputs[{pidx}]",
                f"gate[{i}] ({gid}).trigger_inputs[{pidx}] must be a non-empty string; "
                f"{_TRIGGER_INPUTS_CONTRACT}",
            )
        if not _PATH_SAFE_RE.match(pp):
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].trigger_inputs[{pidx}]",
                f"gate[{i}] ({gid}).trigger_inputs[{pidx}] {pp!r} contains unsafe characters; "
                f"{_TRIGGER_INPUTS_CONTRACT}",
            )
        if pp in seen_ti:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].trigger_inputs[{pidx}]",
                f"gate[{i}] ({gid}).trigger_inputs contains duplicate path: {pp!r}; "
                f"{_TRIGGER_INPUTS_CONTRACT}",
            )
        seen_ti.add(pp)


def _validate_gate_entry(
    gate: dict[str, Any], i: int, known_contexts: frozenset[str], index: _RegistryIndex
) -> None:
    """Validate one gate object in the pre-split field order."""
    if not isinstance(gate, dict):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}]",
            f"gate at index {i} must be a JSON object (got {type(gate).__name__})",
        )
    _require_gate_keys(gate, i)
    gid = _validate_gate_id(gate, i, index)
    _validate_gate_description(gate, i, gid)
    rc = _validate_required_contexts(gate, i, gid, known_contexts)
    bindings = _validate_gate_bindings(gate, i, gid)
    _register_binding_collisions(bindings, i, gid, index)
    _validate_make_recipe(gate, i, gid, bindings)
    _validate_local_membership(rc, bindings, i, gid)
    _validate_depends_on(gate, i, gid)
    _validate_trigger_inputs(gate, i, gid)


def _validate_gate_entries(gates: list[dict[str, Any]], known_contexts: frozenset[str]) -> set[str]:
    """Validate every gate object and return the seen gate-id set."""
    index = _RegistryIndex()
    for i, gate in enumerate(gates):
        _validate_gate_entry(gate, i, known_contexts, index)
    return index.seen_ids


def _validate_cross_gate_dependencies(gates: list[dict[str, Any]], seen_ids: set[str]) -> None:
    """Reject self-referential and unknown depends_on entries."""
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


def _find_dependency_cycle(
    dependencies: dict[str, tuple[str, ...]], gate_ids: tuple[str, ...]
) -> tuple[str, ...] | None:
    """
    Return the first dependency cycle under canonical traversal, or None.

    Use an explicit DFS stack rather than recursion so the registry can
    contain arbitrarily long dependency chains without depending on Python's
    recursion limit.  The traversal order and reported cycle are canonical:
    gate IDs and adjacency entries are visited lexicographically, and the
    cycle is rotated to begin at its lexicographically smallest member.
    """
    state: dict[str, int] = {gid: 0 for gid in gate_ids}  # 0=unseen, 1=active, 2=done

    for start in gate_ids:
        if state[start] != 0:
            continue

        state[start] = 1
        path: list[str] = [start]
        path_positions: dict[str, int] = {start: 0}
        stack: list[tuple[str, Iterator[str]]] = [(start, iter(dependencies[start]))]

        while stack:
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
                return tuple(path[path_positions[successor] :])
    return None


def _cycle_error(cycle: tuple[str, ...]) -> SchemaValidationError:
    """Build the canonical cycle diagnostic for one detected cycle."""
    cycle_start = min(cycle)
    start_index = cycle.index(cycle_start)
    ordered_cycle = cycle[start_index:] + cycle[:start_index]
    cycle_members = ", ".join(repr(gid) for gid in sorted(cycle))
    cycle_path = " -> ".join((*ordered_cycle, cycle_start))
    if len(cycle) == 2:
        # Keep the Phase 1 diagnostic wording for the existing two-node
        # case while making its member order deterministic.
        ordered_members = sorted(cycle)
        detail = f"circular dependency between {ordered_members[0]!r} and {ordered_members[1]!r}"
    else:
        detail = f"circular dependency among gates: {cycle_members} ({cycle_path})"
    return SchemaValidationError(
        "registry",
        f"gates.{cycle_start}.depends_on",
        detail,
    )


def _raise_dependency_cycle(gates: list[dict[str, Any]], seen_ids: set[str]) -> None:
    """Raise the canonical diagnostic when the dependency graph has a cycle."""
    dependencies = {gate["id"]: tuple(sorted(gate.get("depends_on", []))) for gate in gates}
    gate_ids = tuple(sorted(seen_ids))
    cycle = _find_dependency_cycle(dependencies, gate_ids)
    if cycle is not None:
        raise _cycle_error(cycle)


def _validate_registry(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Validate the registry JSON structure.

    Returns the validated gates list.  Raises ``SchemaValidationError`` on the
    first structural violation.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError("registry", "", "must be a JSON object")

    _validate_top_level_keys(data)
    _validate_schema_version(data)
    _validate_registry_description(data)
    known_contexts = _validate_contexts(data["contexts"])
    gates = _require_gates(data["gates"])
    seen_ids = _validate_gate_entries(gates, known_contexts)
    _validate_cross_gate_dependencies(gates, seen_ids)
    _raise_dependency_cycle(gates, seen_ids)
    return gates


# ---------------------------------------------------------------------------
# Registry loading (strict JSON with duplicate-key rejection)
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
