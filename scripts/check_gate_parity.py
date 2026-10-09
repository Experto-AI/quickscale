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
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

_REGISTRY_PATH = _REPO_ROOT / "scripts" / "gate_registry.json"
_TRIGGER_INPUTS_CONTRACT = (
    "trigger_inputs is the ordered, bidirectional E2E allowlist partition; "
    "it never controls whether a gate runs"
)


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
            "make_recipe",
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

        # Missing gate keys.  ``make_recipe`` is optional: its absence means
        # the gate's Make recipe stays hand-written in the Makefile.
        gate_missing = (gate_keys - {"make_recipe"}) - set(gate.keys())
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

        # --- make_recipe (generated Make target recipe) ---
        # Optional.  When present it is the single authored copy of the gate's
        # Make recipe; ``sync_ci_gate_jobs.py`` renders it into the generated
        # ``scripts/gates.mk`` include.  A gate without it keeps its recipe
        # hand-written in the Makefile.
        recipe = gate.get("make_recipe")
        if recipe is not None:
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
                        f"gate[{i}] ({gid}).make_recipe[{ridx}] must be one "
                        f"whitespace-trimmed recipe line",
                    )
            if not isinstance(bindings.get("make_target"), str):
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].make_recipe",
                    f"gate[{i}] ({gid}).make_recipe requires a string make_target binding",
                )

        # --- Local executable membership -----------------------------------
        # A gate that declares a local execution context must carry the Make
        # target and the stage the local runner's fan-out derives from
        # (stages 3-7).  Otherwise both local-CI modes skip it silently: a
        # registry edit would pass generation and currency while the gate
        # never runs locally.
        local_contexts = sorted({"local-serial", "local-parallel"} & set(rc))
        if local_contexts:
            local_target = bindings.get("make_target")
            if not isinstance(local_target, str) or not local_target:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].bindings.make_target",
                    f"gate[{i}] ({gid}) declares local context(s) "
                    f"{', '.join(local_contexts)} but has no Make target for the local runner",
                )
            if not _is_strict_int(lcs) or not 3 <= lcs <= 7:
                raise SchemaValidationError(
                    "registry",
                    f"gates[{i}].bindings.local_ci_stage",
                    f"gate[{i}] ({gid}) declares local context(s) "
                    f"{', '.join(local_contexts)} but local_ci_stage {lcs!r} is outside the "
                    f"executable stages 3-7",
                )

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
            if not path_safe_re.match(pp):
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
