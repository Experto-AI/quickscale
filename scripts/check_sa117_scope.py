#!/usr/bin/env python3
"""
SA117 scope and lock-drift checks.

The ``worktree``, ``emit``, and path-set ``lock`` modes are retained for the
existing scope workflow.  ``lock-diff`` is the sole lock-drift route: it
validates the complete version inventory on both sides and compares complete
Poetry lock structures after normalising only the twelve approved module
``package.version`` leaves.
"""

from __future__ import annotations

import argparse
import ast
import copy
import datetime
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Hashable, Mapping
from pathlib import Path
from typing import Any, Final

import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode

SCOPE_DIR: Final[Path] = Path(__file__).resolve().parent
DEFAULT_SCOPE_PATH: Final[Path] = SCOPE_DIR / "sa117_scope.json"
DEFAULT_EVIDENCE_PATH: Final[Path] = Path("/tmp/sa117-lock-diff-evidence.json")
_MODULE_DISCOVERY_RELATIVE_PATH: Final[Path] = Path(
    "quickscale_core/src/quickscale_core/contracts/module_discovery.py"
)
_LOCK_VERSION_SENTINEL: Final[str] = "__SA117_MODULE_PACKAGE_VERSION__"


class LockDiffError(ValueError):
    """An input cannot be verified under the SA117c contract."""


def _authoritative_module_names(repo_root: Path | None = None) -> list[str]:
    """Load the source inventory through the repository-local discovery shim."""
    root = (repo_root or SCOPE_DIR.parent).resolve()
    shim = root / _MODULE_DISCOVERY_RELATIVE_PATH
    if not shim.is_file():
        raise LockDiffError(f"module discovery shim not found: {shim}")
    try:
        result = subprocess.run(
            [sys.executable, str(shim), "--list-modules"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LockDiffError(f"module discovery shim failed: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise LockDiffError(f"module discovery shim rejected inventory: {detail}")
    names = [line for line in result.stdout.splitlines() if line]
    if not names:
        raise LockDiffError("module discovery shim returned an empty inventory")
    return names


def _locked_module_packages(module_names: list[str]) -> list[str]:
    """Return Poetry package names corresponding to authoritative modules."""
    return [f"quickscale-module-{name}" for name in module_names]


# Compatibility for direct tests and callers that inspect the historical
# private name.  This is deliberately inert: authoritative discovery is lazy
# and only happens while executing lock-diff.
_LOCKED_MODULE_PACKAGES: Final[list[str]] = [
    "quickscale-module-analytics",
    "quickscale-module-auth",
    "quickscale-module-backups",
    "quickscale-module-billing",
    "quickscale-module-blog",
    "quickscale-module-crm",
    "quickscale-module-forms",
    "quickscale-module-listings",
    "quickscale-module-notifications",
    "quickscale-module-orgs",
    "quickscale-module-social",
    "quickscale-module-storage",
]


def _validate_no_nul(path: str) -> str:
    """Reject a path containing an embedded NUL."""
    if "\x00" in path:
        raise ValueError(f"path contains embedded NUL character: {path!r}")
    return path


def _normalise(path: str) -> str:
    """Return a lexical POSIX-style relative path."""
    cleaned = _validate_no_nul(path).replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    parts = [part for part in cleaned.split("/") if part and part != "."]
    resolved: list[str] = []
    for part in parts:
        if part == ".." and resolved:
            resolved.pop()
        elif part != "..":
            resolved.append(part)
    return "/".join(resolved)


def _normalise_candidate(path: str) -> str:
    """Reject rooted candidate spellings before lexical normalisation."""
    _validate_no_nul(path)
    if path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path):
        raise ValueError(f"candidate path must be relative: {path!r}")
    return _normalise(path)


def _json_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON object keys before schema validation."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_scope_document(scope_path: Path = DEFAULT_SCOPE_PATH) -> dict[str, Any]:
    """Load and strictly validate the single SA117 fact document."""
    if not scope_path.is_file():
        raise FileNotFoundError(f"SA117 scope file not found: {scope_path}")
    try:
        with scope_path.open("rb") as handle:
            data = json.load(handle, object_pairs_hook=_json_without_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed SA117 scope JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("SA117 scope document must be a JSON object")
    if set(data) != {"version", "description", "paths", "contract"}:
        raise ValueError("SA117 scope document has missing or unknown top-level fields")
    if not isinstance(data["version"], str) or not data["version"]:
        raise ValueError("SA117 scope version must be a non-empty string")
    if not isinstance(data["description"], str):
        raise ValueError("SA117 scope description must be a string")
    paths = data["paths"]
    if not isinstance(paths, list):
        raise ValueError("SA117 scope document 'paths' must be a list")
    seen_paths: set[str] = set()
    for entry in paths:
        if not isinstance(entry, dict) or set(entry) != {"path", "phase", "notes"}:
            raise ValueError(f"invalid SA117 scope entry shape: {entry!r}")
        if not all(isinstance(entry[key], str) for key in ("path", "phase", "notes")):
            raise ValueError(f"invalid SA117 scope entry types: {entry!r}")
        path = entry["path"]
        if not path or path != _normalise(path):
            raise ValueError(f"SA117 scope path must be canonical and relative: {path!r}")
        if path in seen_paths:
            raise ValueError(f"duplicate SA117 scope path: {path!r}")
        if not entry["phase"]:
            raise ValueError(f"SA117 scope phase must be non-empty: {path!r}")
        seen_paths.add(path)
    build_allowlist(paths)
    _validate_contract(data["contract"])
    return data


def _validate_contract(contract: Any) -> None:
    """Validate mode/profile/option/consumer contract data without defaults."""
    if not isinstance(contract, dict):
        raise ValueError("SA117 contract must be a JSON object")
    if set(contract) != {"schema_version", "profiles", "modes", "consumers", "metadata"}:
        raise ValueError("SA117 contract has missing or unknown fields")
    if type(contract["schema_version"]) is not int or contract["schema_version"] != 1:
        raise ValueError("unsupported SA117 contract schema_version")
    if contract["profiles"] != ["direct", "make"]:
        raise ValueError("SA117 contract profiles must be exactly direct and make")
    modes = contract["modes"]
    if not isinstance(modes, dict) or set(modes) != {"worktree", "emit", "lock", "lock-diff"}:
        raise ValueError("SA117 contract modes must be exactly worktree, emit, lock, lock-diff")
    for mode_name, mode in modes.items():
        if not isinstance(mode, dict) or set(mode) != {"help", "options", "profiles"}:
            raise ValueError(f"invalid SA117 mode contract: {mode_name}")
        if not isinstance(mode["help"], str) or not mode["help"]:
            raise ValueError(f"SA117 mode {mode_name!r} help must be a non-empty string")
        options = mode["options"]
        profiles = mode["profiles"]
        if not isinstance(options, dict) or not isinstance(profiles, dict):
            raise ValueError(f"SA117 mode {mode_name!r} options/profiles must be objects")
        if set(profiles) != {"direct", "make"}:
            raise ValueError(f"SA117 mode {mode_name!r} profiles are incomplete")
        seen_flags: set[str] = set()
        for option_name, option in options.items():
            if not re.fullmatch(r"[a-z][a-z0-9-]*", option_name):
                raise ValueError(f"invalid SA117 option name: {mode_name}/{option_name}")
            if not isinstance(option, dict) or not {"flag", "kind", "help"} <= set(option):
                raise ValueError(f"invalid SA117 option contract: {mode_name}/{option_name}")
            if not set(option) <= {"flag", "kind", "help", "nargs", "default"}:
                raise ValueError(f"unknown SA117 option field: {mode_name}/{option_name}")
            if not all(isinstance(option[key], str) for key in ("flag", "kind", "help")):
                raise ValueError(f"invalid SA117 option types: {mode_name}/{option_name}")
            if option["flag"] != f"--{option_name}" or option["flag"] in seen_flags:
                raise ValueError(
                    f"invalid or duplicate SA117 option flag: {mode_name}/{option_name}"
                )
            if not option["help"]:
                raise ValueError(f"empty SA117 option help: {mode_name}/{option_name}")
            seen_flags.add(option["flag"])
            if option["kind"] not in {"paths", "store_true", "value", "path"}:
                raise ValueError(f"unknown SA117 option kind: {option['kind']!r}")
            if option["kind"] == "paths" and option.get("nargs") != "*":
                raise ValueError(f"paths option must have nargs '*': {mode_name}/{option_name}")
            if option["kind"] != "paths" and "nargs" in option:
                raise ValueError(
                    f"nargs is only valid for paths options: {mode_name}/{option_name}"
                )
            if "default" in option and option["kind"] not in {"path", "value"}:
                raise ValueError(f"default is invalid for boolean/path-list option: {option_name}")
            if "default" in option and not isinstance(option["default"], str):
                raise ValueError(
                    f"SA117 option default must be a string: {mode_name}/{option_name}"
                )
        option_names = set(options)
        declared_options: set[str] = set()
        for profile, declaration in profiles.items():
            if (
                not isinstance(declaration, dict)
                or set(declaration) != {"required", "optional"}
                or not isinstance(declaration["required"], list)
                or not isinstance(declaration["optional"], list)
                or any(
                    not isinstance(item, str)
                    for item in declaration["required"] + declaration["optional"]
                )
            ):
                raise ValueError(f"invalid SA117 profile declaration: {mode_name}/{profile}")
            required = declaration["required"]
            optional = declaration["optional"]
            if len(required) != len(set(required)) or len(optional) != len(set(optional)):
                raise ValueError(f"duplicate SA117 profile option: {mode_name}/{profile}")
            if set(required) & set(optional) or not set(required + optional) <= option_names:
                raise ValueError(
                    f"unknown or overlapping SA117 profile option: {mode_name}/{profile}"
                )
            declared_options.update(required + optional)
        if declared_options != option_names:
            raise ValueError(f"undeclared SA117 mode option: {mode_name}")
    consumers = contract["consumers"]
    if not isinstance(consumers, list) or not consumers:
        raise ValueError("SA117 contract consumers must be a non-empty list")
    seen_consumers: set[str] = set()
    seen_consumer_paths: set[str] = set()
    for consumer in consumers:
        if not isinstance(consumer, dict) or set(consumer) != {"name", "path"}:
            raise ValueError(f"invalid SA117 consumer declaration: {consumer!r}")
        if not all(isinstance(consumer[key], str) and consumer[key] for key in ("name", "path")):
            raise ValueError(f"invalid SA117 consumer types: {consumer!r}")
        if consumer["name"] in seen_consumers:
            raise ValueError(f"duplicate SA117 consumer: {consumer['name']!r}")
        path = consumer["path"]
        if path != _normalise(path):
            raise ValueError(f"SA117 consumer path must be canonical and relative: {path!r}")
        if path in seen_consumer_paths:
            raise ValueError(f"duplicate SA117 consumer path: {path!r}")
        seen_consumers.add(consumer["name"])
        seen_consumer_paths.add(path)
    if not isinstance(contract["metadata"], dict) or set(contract["metadata"]) != {"rev_004"}:
        raise ValueError("SA117 contract metadata must contain only rev_004")
    if not isinstance(contract["metadata"]["rev_004"], str):
        raise ValueError("SA117 rev_004 metadata must be a string")


def load_scope(scope_path: Path = DEFAULT_SCOPE_PATH) -> list[dict[str, Any]]:
    """Load the strictly validated path allowlist."""
    return _load_scope_document(scope_path)["paths"]


def build_allowlist(scope_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a normalised allowlist, rejecting lexical duplicates."""
    result: dict[str, dict[str, Any]] = {}
    for entry in scope_entries:
        path = _normalise(entry["path"])
        if path in result:
            raise ValueError(f"duplicate path in SA117 scope: {path!r}")
        result[path] = entry
    return result


def _contract_mode(scope_path: Path, mode: str) -> dict[str, Any]:
    """Return one already validated mode declaration."""
    return _load_scope_document(scope_path)["contract"]["modes"][mode]


def _required_inputs(scope_path: Path, mode: str, profile: str, values: Mapping[str, Any]) -> None:
    """Fail closed when a caller profile omits or supplies unsupported inputs."""
    if profile not in {"direct", "make"}:
        raise ValueError(f"unknown SA117 caller profile: {profile!r}")
    mode_contract = _contract_mode(scope_path, mode)
    declaration = mode_contract["profiles"][profile]
    for option in declaration["required"]:
        value = values.get(option.replace("-", "_"))
        if value is None:
            raise ValueError(f"{option} is required for {profile} {mode} mode")
    allowed = set(declaration["required"] + declaration["optional"])
    for option, option_contract in mode_contract["options"].items():
        if option in allowed:
            continue
        value = values.get(option.replace("-", "_"))
        supplied = value is not None and (option_contract["kind"] != "store_true" or value is True)
        if supplied:
            raise ValueError(f"{option} is not supported for {profile} {mode} mode")


def _tokenise_make_paths(paths: list[str] | None) -> list[str] | None:
    """Parse Make's one raw data argument without evaluating shell syntax."""
    if paths is None:
        return None
    if len(paths) != 1:
        return paths
    raw = paths[0]
    _validate_no_nul(raw)
    try:
        return shlex.split(raw, posix=True)
    except ValueError as exc:
        raise ValueError(f"invalid Make PATHS data: {exc}") from exc


def _filter_scope_paths(paths: set[str], *, scripts_only: bool) -> set[str]:
    """Filter a path set to ``scripts/`` for legacy phase-1 callers."""
    return {path for path in paths if not scripts_only or path.startswith("scripts/")}


def _read_git_tracked_files(repo_root: Path) -> list[str]:
    """Return tracked paths from a repository."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, timeout=30
    )
    if result.returncode:
        raise RuntimeError(f"git ls-files failed (exit {result.returncode}): {result.stderr}")
    return [line for line in result.stdout.splitlines() if line]


def mode_worktree(
    scope_path: Path,
    *,
    paths: list[str] | None = None,
    repo_root: Path | None = None,
    allow_untracked: bool = False,
    scripts_only: bool = False,
    profile: str = "direct",
) -> int:
    """Check that candidate paths are members of the allowlist."""
    del repo_root
    try:
        _required_inputs(
            scope_path,
            "worktree",
            profile,
            {
                "paths": paths,
                "allow_untracked": allow_untracked,
                "scripts_only": scripts_only,
            },
        )
        if profile == "make":
            paths = _tokenise_make_paths(paths)
        if not paths:
            raise ValueError(f"paths is required for {profile} worktree mode")
        allowed = build_allowlist(load_scope(scope_path))
        current = {_normalise_candidate(path) for path in paths}
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    violations = sorted(
        _filter_scope_paths(current, scripts_only=scripts_only)
        - _filter_scope_paths(set(allowed), scripts_only=scripts_only)
    )
    if violations:
        print("SA117 scope violations (paths not in allowlist):", file=sys.stderr)
        print("\n".join(f"  {path}" for path in violations), file=sys.stderr)
        return 1
    print("SA117 worktree check: all paths are in the allowlist.")
    return 0


def mode_emit(scope_path: Path, *, phase: str | None = None, profile: str = "direct") -> int:
    """Emit allowlisted paths, optionally filtered by phase."""
    try:
        _required_inputs(scope_path, "emit", profile, {"phase": phase})
        entries = load_scope(scope_path)
        for entry in entries:
            if phase is None or entry.get("phase") == phase:
                print(_normalise(entry["path"]))
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def mode_lock(
    scope_path: Path,
    *,
    paths: list[str] | None = None,
    repo_root: Path | None = None,
    scripts_only: bool = False,
    profile: str = "direct",
) -> int:
    """Check that a candidate path set exactly matches the allowlist."""
    try:
        _required_inputs(
            scope_path,
            "lock",
            profile,
            {"paths": paths, "scripts_only": scripts_only},
        )
        if profile == "make":
            paths = _tokenise_make_paths(paths)
        allowed = build_allowlist(load_scope(scope_path))
        current_paths = (
            paths if paths is not None else _read_git_tracked_files(repo_root or SCOPE_DIR.parent)
        )
        current = _filter_scope_paths(
            {_normalise_candidate(path) for path in current_paths}, scripts_only=scripts_only
        )
        expected = _filter_scope_paths(set(allowed), scripts_only=scripts_only)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    missing = sorted(expected - current)
    extra = sorted(current - expected)
    if missing or extra:
        if missing:
            print("LOCK MISMATCH — missing from worktree:", file=sys.stderr)
            print("\n".join(f"  {path}" for path in missing), file=sys.stderr)
        if extra:
            print("LOCK MISMATCH — extra in worktree:", file=sys.stderr)
            print("\n".join(f"  {path}" for path in extra), file=sys.stderr)
        return 1
    print("SA117 lock check: paths match allowlist exactly.")
    return 0


def _parse_canonical_version(value: Any) -> str:
    """Use the production canonical parser through a fail-closed wrapper."""
    if not isinstance(value, str):
        raise LockDiffError("version is not a string")
    try:
        from quickscale_core.manifest.loader import _parse_canonical_version_triple

        triple = _parse_canonical_version_triple(value)
    except Exception as exc:  # noqa: BLE001 - the checker must fail closed
        raise LockDiffError(f"invalid canonical version {value!r}: {exc}") from exc
    if (
        not isinstance(triple, tuple)
        or len(triple) != 3
        or not all(isinstance(part, int) for part in triple)
    ):
        raise LockDiffError("canonical version parser returned an invalid triple")
    return value


def _parse_version_file(content: bytes, path: str) -> str:
    """Parse a VERSION file with no whitespace or extra records."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LockDiffError(f"{path}: VERSION is not UTF-8") from exc
    lines = text.splitlines()
    if len(lines) != 1 or lines[0] != text.rstrip("\n") or not lines[0]:
        raise LockDiffError(f"{path}: expected exactly one version line")
    return _parse_canonical_version(lines[0])


def _parse_toml(content: bytes, path: str) -> dict[str, Any]:
    """Parse TOML strictly, including duplicate-key rejection from tomllib."""
    try:
        data = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise LockDiffError(f"{path}: malformed TOML: {exc}") from exc
    if not isinstance(data, dict):
        raise LockDiffError(f"{path}: TOML root is not a mapping")
    _reject_toml_temporal_values(data, path)
    return data


def _reject_toml_temporal_values(value: Any, path: str, location: str = "$") -> None:
    """Reject TOML temporal values before they can enter comparison evidence."""
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        raise LockDiffError(f"{path}: temporal TOML value is not supported at {location}")
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_toml_temporal_values(child, path, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_toml_temporal_values(child, path, f"{location}[{index}]")


class _StrictYamlLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys and merge keys."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        if not isinstance(node, MappingNode):
            raise LockDiffError("YAML root contains a non-mapping node")
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                raise LockDiffError("YAML mapping key is not hashable")
            try:
                hash(key)
            except TypeError as exc:
                raise LockDiffError("YAML mapping key is not hashable") from exc
            if key == "<<":
                raise LockDiffError("YAML merge keys are not allowed")
            if key in result:
                raise LockDiffError(f"duplicate YAML key: {key!r}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _parse_manifest(content: bytes, path: str, module_name: str) -> str:
    """Parse a manifest while rejecting YAML aliases, anchors, and merges."""
    try:
        text = content.decode("utf-8")
        for event in yaml.parse(text):
            if isinstance(event, AliasEvent) or getattr(event, "anchor", None) is not None:
                raise LockDiffError(f"{path}: YAML anchors and aliases are not allowed")
        data = yaml.load(text, Loader=_StrictYamlLoader)
    except (UnicodeDecodeError, yaml.YAMLError, LockDiffError) as exc:
        raise LockDiffError(f"{path}: malformed YAML: {exc}") from exc
    if not isinstance(data, dict) or data.get("name") != module_name:
        raise LockDiffError(f"{path}: name must be exactly {module_name!r}")
    version = data.get("version")
    if not isinstance(version, str):
        raise LockDiffError(f"{path}: version must be a string")
    return _parse_canonical_version(version)


def _parse_python_version(content: bytes, path: str) -> str:
    """Require exactly one direct ``__version__ = <string>`` assignment."""
    try:
        tree = ast.parse(content.decode("utf-8"), filename=path)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise LockDiffError(f"{path}: malformed Python: {exc}") from exc
    candidates = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "__version__"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(candidates) != 1:
        raise LockDiffError(f"{path}: expected exactly one direct __version__ literal")

    accepted_target = candidates[0].targets[0]
    binding_error = f"{path}: every other __version__ binding or deletion is forbidden"
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__version__":
            if isinstance(node.ctx, (ast.Store, ast.Del)) and node is not accepted_target:
                raise LockDiffError(binding_error)
        elif isinstance(node, ast.arg) and node.arg == "__version__":
            raise LockDiffError(binding_error)
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == "__version__"
        ):
            raise LockDiffError(binding_error)
        elif isinstance(node, ast.ExceptHandler) and node.name == "__version__":
            raise LockDiffError(binding_error)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = (
                    alias.asname if alias.asname is not None else alias.name.partition(".")[0]
                )
                if bound_name == "__version__":
                    raise LockDiffError(binding_error)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    raise LockDiffError(binding_error)
                bound_name = alias.asname if alias.asname is not None else alias.name
                if bound_name == "__version__":
                    raise LockDiffError(binding_error)
        elif (
            isinstance(node, (ast.TypeVar, ast.ParamSpec, ast.TypeVarTuple))
            and node.name == "__version__"
        ):
            raise LockDiffError(binding_error)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == "__version__":
            raise LockDiffError(binding_error)
        elif isinstance(node, ast.MatchMapping) and node.rest == "__version__":
            raise LockDiffError(binding_error)
    return _parse_canonical_version(candidates[0].value.value)


def _parse_project_version(content: bytes, path: str, expected_name: str) -> str:
    """Parse a project TOML and validate its exact project name and version."""
    data = _parse_toml(content, path)
    project = data.get("project")
    if not isinstance(project, dict) or project.get("name") != expected_name:
        raise LockDiffError(f"{path}: project.name must be exactly {expected_name!r}")
    version = project.get("version")
    return _parse_canonical_version(version)


def _expected_inventory(
    repo_root: Path | None = None, module_names: list[str] | None = None
) -> list[str]:
    """Return the inventory paths derived from the authoritative modules."""
    module_names = (
        module_names if module_names is not None else _authoritative_module_names(repo_root)
    )
    paths = ["VERSION", "poetry.lock"]
    paths.extend(
        [
            "quickscale/pyproject.toml",
            "quickscale_core/pyproject.toml",
            "quickscale_cli/pyproject.toml",
        ]
    )
    paths.extend(
        [
            "quickscale_core/src/quickscale_core/_version.py",
            "quickscale_cli/src/quickscale_cli/_version.py",
        ]
    )
    for module in module_names:
        paths.extend(
            [
                f"quickscale_modules/{module}/pyproject.toml",
                f"quickscale_modules/{module}/src/quickscale_modules_{module}/__init__.py",
                f"quickscale_modules/{module}/module.yml",
                f"quickscale_core/src/quickscale_core/data/manifests/{module}/module.yml",
            ]
        )
    return paths


def _parse_lock_data(content: bytes, path: str, module_packages: list[str]) -> dict[str, Any]:
    """Parse a lock and validate its complete, unique package inventory."""
    data = _parse_toml(content, path)
    packages = data.get("package")
    if not isinstance(packages, list) or not packages:
        raise LockDiffError(f"{path}: package must be a non-empty array")
    seen: set[str] = set()
    for package in packages:
        if (
            not isinstance(package, dict)
            or not isinstance(package.get("name"), str)
            or not isinstance(package.get("version"), str)
        ):
            raise LockDiffError(f"{path}: every package must have string name and version")
        name = package["name"]
        if name in seen:
            raise LockDiffError(f"{path}: duplicate package record {name!r}")
        seen.add(name)
    missing = sorted(set(module_packages) - seen)
    if missing:
        raise LockDiffError(f"{path}: missing expected module packages: {', '.join(missing)}")
    if len([name for name in seen if name in module_packages]) != len(module_packages):
        raise LockDiffError(
            f"{path}: expected exactly {len(module_packages)} module package records"
        )
    return data


def _parse_inventory(
    contents: dict[str, bytes], label: str, module_names: list[str]
) -> dict[str, Any]:
    """Validate every inventory file and return parsed values and lock data."""
    values: dict[str, str] = {}
    values["VERSION"] = _parse_version_file(contents["VERSION"], f"{label}/VERSION")
    project_names = {
        "quickscale/pyproject.toml": "quickscale",
        "quickscale_core/pyproject.toml": "quickscale-core",
        "quickscale_cli/pyproject.toml": "quickscale-cli",
    }
    for path, name in project_names.items():
        values[path] = _parse_project_version(contents[path], f"{label}/{path}", name)
    values["quickscale_core/src/quickscale_core/_version.py"] = _parse_python_version(
        contents["quickscale_core/src/quickscale_core/_version.py"],
        f"{label}/quickscale_core/_version.py",
    )
    values["quickscale_cli/src/quickscale_cli/_version.py"] = _parse_python_version(
        contents["quickscale_cli/src/quickscale_cli/_version.py"],
        f"{label}/quickscale_cli/_version.py",
    )
    for module in module_names:
        yml_paths = [
            f"quickscale_modules/{module}/module.yml",
            f"quickscale_core/src/quickscale_core/data/manifests/{module}/module.yml",
        ]
        for path in yml_paths:
            values[path] = _parse_manifest(contents[path], f"{label}/{path}", module)
        project_path = f"quickscale_modules/{module}/pyproject.toml"
        values[project_path] = _parse_project_version(
            contents[project_path], f"{label}/{project_path}", f"quickscale-module-{module}"
        )
        init_path = f"quickscale_modules/{module}/src/quickscale_modules_{module}/__init__.py"
        values[init_path] = _parse_python_version(contents[init_path], f"{label}/{init_path}")
    module_packages = _locked_module_packages(module_names)
    lock_data = _parse_lock_data(contents["poetry.lock"], f"{label}/poetry.lock", module_packages)
    packages = {package["name"]: package["version"] for package in lock_data["package"]}
    for name in module_packages:
        values[f"poetry.lock#package[{name}].version"] = _parse_canonical_version(packages[name])
    snapshot_version = values["VERSION"]
    bad = [path for path, value in values.items() if value != snapshot_version]
    if bad:
        raise LockDiffError(
            f"{label}: version values disagree with VERSION: {', '.join(sorted(bad))}"
        )
    return {"values": values, "lock": lock_data}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _inventory_digest(contents: dict[str, bytes], paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_sha256(contents[path])))
    return digest.hexdigest()


def _resolve_git_ref(ref: str, repo_path: Path | None = None) -> str | None:
    """Resolve a commit ref exactly once to a full immutable SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except OSError, subprocess.SubprocessError:
        return None
    sha = result.stdout.strip()
    if result.returncode or len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
        return None
    return sha


def _git_top_level(repo_path: Path) -> Path | None:
    """Resolve the exact Git top-level directory containing ``repo_path``."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode or not result.stdout.strip():
        return None
    try:
        return Path(result.stdout.strip()).resolve()
    except OSError, RuntimeError:
        return None


def _git_baseline_contents(
    repo_root: Path, resolved_sha: str, paths: list[str]
) -> dict[str, bytes]:
    """Read and validate the expected baseline tree entries."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", resolved_sha],
        cwd=repo_root,
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        raise LockDiffError(f"git ls-tree failed: {result.stderr.decode(errors='replace')}")
    entries: dict[str, tuple[str, str]] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, object_sha = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise LockDiffError("baseline tree contains an invalid Git entry") from exc
        entries[path] = (mode, kind + " " + object_sha)
    missing = [path for path in paths if path not in entries]
    if missing:
        raise LockDiffError(f"baseline is missing expected paths: {', '.join(missing)}")
    contents: dict[str, bytes] = {}
    for path in paths:
        mode, kind_sha = entries[path]
        kind, object_sha = kind_sha.split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise LockDiffError(f"baseline path is not a regular 100644/100755 blob: {path}")
        blob = subprocess.run(
            ["git", "cat-file", "blob", object_sha],
            cwd=repo_root,
            capture_output=True,
            timeout=30,
        )
        if blob.returncode:
            raise LockDiffError(f"cannot read baseline blob: {path}")
        contents[path] = blob.stdout
    return contents


def _candidate_contents(root: Path, paths: list[str]) -> dict[str, bytes]:
    """Read expected candidate files, rejecting symlinks and non-regular files."""
    contents: dict[str, bytes] = {}
    for path in paths:
        candidate = root / path
        try:
            info = candidate.lstat()
        except OSError as exc:
            raise LockDiffError(f"candidate path cannot be inspected: {path}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise LockDiffError(f"candidate path is not a regular non-symlink file: {path}")
        try:
            contents[path] = candidate.read_bytes()
        except OSError as exc:
            raise LockDiffError(f"candidate path cannot be read: {path}") from exc
    return contents


def _normalise_lock(
    lock_data: dict[str, Any], module_packages: list[str]
) -> tuple[dict[str, Any], list[str]]:
    """Deep-copy a lock and replace only validated module version leaves."""
    normalised = copy.deepcopy(lock_data)
    leaves: list[str] = []
    for package in normalised["package"]:
        if package["name"] in module_packages:
            package["version"] = _LOCK_VERSION_SENTINEL
            leaves.append(f"package[{package['name']}].version")
    if sorted(leaves) != sorted(f"package[{name}].version" for name in module_packages):
        raise LockDiffError("lock normalisation did not find every validated module leaf")
    return normalised, sorted(leaves)


def _collect_differences(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    """Collect deterministic structural differences for evidence."""
    if type(left) is not type(right):
        return [{"path": path or "$", "baseline": left, "candidate": right}]
    if isinstance(left, dict):
        differences: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                differences.append(
                    {"path": child, "baseline": left.get(key), "candidate": right.get(key)}
                )
            else:
                differences.extend(_collect_differences(left[key], right[key], child))
        return differences
    if isinstance(left, list):
        differences = []
        for index in range(max(len(left), len(right))):
            child = f"{path}[{index}]"
            if index >= len(left) or index >= len(right):
                differences.append(
                    {
                        "path": child,
                        "baseline": left[index] if index < len(left) else None,
                        "candidate": right[index] if index < len(right) else None,
                    }
                )
            else:
                differences.extend(_collect_differences(left[index], right[index], child))
        return differences
    if left != right:
        return [{"path": path or "$", "baseline": left, "candidate": right}]
    return []


def _remove_evidence(path: Path) -> None:
    """Remove stale evidence after output-path safety checks pass."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise LockDiffError(f"cannot remove stale evidence {path}: {exc}") from exc


def _write_evidence_atomic(path: Path, evidence: dict[str, Any]) -> None:
    """Write deterministic JSON through an atomic same-directory replace."""
    fd: int | None = None
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary_path = Path(temporary)
        encoded = (
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception as exc:
        cleanup_errors: list[OSError] = []
        if fd is not None:
            try:
                os.close(fd)
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            raise LockDiffError(
                f"cannot clean temporary evidence for {path}: {cleanup_errors[0]}"
            ) from exc
        raise LockDiffError(f"cannot write evidence {path}: {exc}") from exc


def mode_verify_lock_diff(
    candidate_path: Path,
    *,
    baseline_ref: str,
    expected_version: str | None = None,
    output_path: Path | None = None,
) -> int:
    """Run the complete fail-closed SA117c lock-diff proof."""
    output = (output_path or DEFAULT_EVIDENCE_PATH).expanduser()
    output_safe_to_remove = False
    try:
        candidate_path = candidate_path.expanduser()
        if candidate_path.name != "poetry.lock":
            raise LockDiffError("candidate must be the repository-root poetry.lock")
        if expected_version is None:
            raise LockDiffError("expected-version is required")
        _parse_canonical_version(expected_version)
        root = candidate_path.parent.resolve()
        module_names = _authoritative_module_names(root)
        module_packages = _locked_module_packages(module_names)
        paths = _expected_inventory(root, module_names)
        output_resolved = output.resolve()
        for path in paths:
            if output_resolved == (root / path).resolve():
                raise LockDiffError(
                    f"evidence output must not resolve to candidate inventory input: {path}"
                )
        output_safe_to_remove = True
        _remove_evidence(output)
        if candidate_path.is_symlink() or not candidate_path.is_file():
            raise LockDiffError("candidate poetry.lock must be a regular non-symlink file")
        git_root = _git_top_level(root)
        if git_root is None:
            raise LockDiffError("candidate root is not a Git repository")
        if git_root != root:
            raise LockDiffError(
                f"candidate root must be the Git top-level repository: {root} != {git_root}"
            )
        resolved_sha = _resolve_git_ref(baseline_ref, repo_path=root)
        if resolved_sha is None:
            raise LockDiffError(
                f"baseline ref {baseline_ref!r} did not resolve to a full commit SHA"
            )
        baseline_contents = _git_baseline_contents(root, resolved_sha, paths)
        candidate_contents = _candidate_contents(root, paths)
        baseline = _parse_inventory(baseline_contents, "baseline", module_names)
        candidate = _parse_inventory(candidate_contents, "candidate", module_names)
        if candidate["values"]["VERSION"] != expected_version:
            raise LockDiffError(
                f"expected-version {expected_version!r} disagrees with candidate VERSION "
                f"{candidate['values']['VERSION']!r}"
            )
        baseline_lock, baseline_leaves = _normalise_lock(baseline["lock"], module_packages)
        candidate_lock, candidate_leaves = _normalise_lock(candidate["lock"], module_packages)
        if baseline_leaves != candidate_leaves:
            raise LockDiffError("baseline and candidate lock leaf inventories differ")
        differences = _collect_differences(baseline_lock, candidate_lock)
        baseline_lock_bytes = baseline_contents["poetry.lock"]
        candidate_lock_bytes = candidate_contents["poetry.lock"]
        baseline_root_digest = _inventory_digest(baseline_contents, paths)
        candidate_root_digest = _inventory_digest(candidate_contents, paths)
        clean = not differences
        evidence: dict[str, Any] = {
            "schema_version": 1,
            "tool": "check_sa117_scope.py lock-diff",
            "status": "clean" if clean else "drift",
            "exit_code": 0 if clean else 1,
            "expected_version": expected_version,
            "baseline": {
                "ref": baseline_ref,
                "resolved_sha": resolved_sha,
                "root": str(root),
                "root_digest": baseline_root_digest,
                "lock_digest": _sha256(baseline_lock_bytes),
                "version": baseline["values"]["VERSION"],
            },
            "candidate": {
                "path": str(candidate_path),
                "root": str(root),
                "root_digest": candidate_root_digest,
                "lock_digest": _sha256(candidate_lock_bytes),
                "version": candidate["values"]["VERSION"],
            },
            "inventory": {
                "files_expected": len(paths),
                "files_parsed": len(candidate_contents),
                "values_expected": len(candidate["values"]),
                "values_parsed": len(candidate["values"]),
                "expected_file_count": len(paths),
                "expected_version_value_count": len(candidate["values"]),
                "baseline_file_count": len(baseline_contents),
                "candidate_file_count": len(candidate_contents),
                "baseline_version_value_count": len(baseline["values"]),
                "candidate_version_value_count": len(candidate["values"]),
                "paths": paths,
            },
            "lock_comparison": {
                "raw_equal": baseline["lock"] == candidate["lock"],
                "normalized_equal": clean,
                "allowed_version_leaves": baseline_leaves,
                "allowed_version_leaf_count": len(baseline_leaves),
                "baseline_package_count": len(baseline["lock"]["package"]),
                "candidate_package_count": len(candidate["lock"]["package"]),
            },
            "differences": differences,
        }
        _write_evidence_atomic(output, evidence)
        if clean:
            print("SA117 lock-diff: clean; normalized lock structures match.")
        else:
            print("SA117 lock-diff: unauthorized lock structure drift detected.", file=sys.stderr)
        print(f"Evidence written to {output}")
        return 0 if clean else 1
    except Exception as exc:  # noqa: BLE001 - command-line checker must never traceback
        print(f"ERROR: {exc}", file=sys.stderr)
        if output_safe_to_remove:
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
        return 2


def _build_parser(scope_path: Path = DEFAULT_SCOPE_PATH) -> argparse.ArgumentParser:
    """Build the CLI from the strict JSON mode/option declaration."""
    contract = _load_scope_document(scope_path)["contract"]
    parser = argparse.ArgumentParser(prog="check_sa117_scope.py")
    parser.add_argument("--scope", type=Path, default=scope_path)
    parser.add_argument("--profile", default="direct", help="Caller profile (direct or make).")
    parser.add_argument(
        "--render-make-help",
        action="store_true",
        help="Render the SA117 section consumed by the root Makefile help target.",
    )
    subparsers = parser.add_subparsers(dest="mode", required=False)
    for mode_name, mode in contract["modes"].items():
        subparser = subparsers.add_parser(mode_name, help=mode["help"])
        for option_name, option in mode["options"].items():
            kwargs: dict[str, Any] = {"dest": option_name.replace("-", "_")}
            if option["kind"] == "store_true":
                kwargs["action"] = "store_true"
            elif option["kind"] == "paths":
                kwargs.update(nargs="*", default=None)
            elif option["kind"] == "path":
                kwargs["type"] = Path
                if "default" in option:
                    kwargs["default"] = Path(option["default"])
            else:
                if "default" in option:
                    kwargs["default"] = option["default"]
            subparser.add_argument(option["flag"], help=option["help"], **kwargs)
    return parser


def _requested_scope_path(argv: list[str]) -> Path:
    """Select the fact document before building the parser it defines."""
    selected = DEFAULT_SCOPE_PATH
    for index, argument in enumerate(argv):
        if argument == "--scope":
            if index + 1 >= len(argv):
                raise ValueError("--scope requires a path")
            selected = Path(argv[index + 1])
        elif argument.startswith("--scope="):
            selected = Path(argument.partition("=")[2])
    return selected


def _render_make_help(scope_path: Path = DEFAULT_SCOPE_PATH) -> None:
    """Render only the SA117 help block; Make owns placement in its help text."""
    contract = _load_scope_document(scope_path)["contract"]
    modes = contract["modes"]
    print("SA117 scope / publication gates:")
    print("  make sa117-check PATHS='...'      - " + modes["worktree"]["help"])
    print("  make sa117-emit                   - " + modes["emit"]["help"])
    print("  make sa117-lock PATHS='...'       - " + modes["lock"]["help"])
    print("  make sa117-lock-diff              - " + modes["lock-diff"]["help"])
    print("  make sa117-capture VERSION=X PHASE=Y - Capture publication evidence")
    print("  make sa117-verify EVIDENCE=path   - Verify publication evidence")
    print("  make sa117-authorize VERSION=X DIGEST=D - Authorize a publication")
    print("  make sa117-rollback TOKEN=T DIGEST=D - Roll back a prior authorization")
    print("  make sa117-apply MODULE=M TARGET=T EXEC=E ARGV=A - Execute and verify a module apply")
    print("  make sa117-check-origin MODULE=M DECLARED=O EXPECTED=E - Check origin map consistency")
    print("  make sa117-check-containers TARGET=T - Check for zero container/volume configuration")


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        scope_path = _requested_scope_path(arguments)
        args = _build_parser(scope_path).parse_args(arguments)
        if args.render_make_help:
            _render_make_help(args.scope)
            return 0
        if args.mode is None:
            raise ValueError("a checker mode is required")
        profile_values = vars(args)
        _required_inputs(args.scope, args.mode, args.profile, profile_values)
        if args.mode == "worktree":
            return mode_worktree(
                args.scope,
                paths=args.paths,
                allow_untracked=args.allow_untracked,
                scripts_only=args.scripts_only,
                profile=args.profile,
            )
        if args.mode == "emit":
            return mode_emit(args.scope, phase=args.phase, profile=args.profile)
        if args.mode == "lock":
            return mode_lock(
                args.scope, paths=args.paths, scripts_only=args.scripts_only, profile=args.profile
            )
        if args.mode == "lock-diff":
            return mode_verify_lock_diff(
                args.candidate,
                baseline_ref=args.baseline_ref,
                expected_version=args.expected_version,
                output_path=args.output,
            )
        raise ValueError(f"unsupported checker mode: {args.mode!r}")
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
