"""
Scope-document and contract validation for the SA267(d) ``check_sa117_scope`` split.

The single SA117 fact document, its allowlist, and its strict mode/profile/
option/consumer contract are loaded and validated here.  The facade and the
other siblings import these names from this defining sibling, never through
the facade (decisions.md, Split-Facade Seams).  Behavior is unchanged from the
pre-split module.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

SCOPE_DIR: Final[Path] = Path(__file__).resolve().parent
DEFAULT_SCOPE_PATH: Final[Path] = SCOPE_DIR / "sa117_scope.json"


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


def _validate_option_contract(
    mode_name: str, option_name: str, option: Any, seen_flags: set[str]
) -> None:
    """Validate one mode option declaration; a malformed option fails closed."""
    if not re.fullmatch(r"[a-z][a-z0-9-]*", option_name):
        raise ValueError(f"invalid SA117 option name: {mode_name}/{option_name}")
    if not isinstance(option, dict) or not {"flag", "kind", "help"} <= set(option):
        raise ValueError(f"invalid SA117 option contract: {mode_name}/{option_name}")
    if not set(option) <= {"flag", "kind", "help", "nargs", "default"}:
        raise ValueError(f"unknown SA117 option field: {mode_name}/{option_name}")
    if not all(isinstance(option[key], str) for key in ("flag", "kind", "help")):
        raise ValueError(f"invalid SA117 option types: {mode_name}/{option_name}")
    if option["flag"] != f"--{option_name}" or option["flag"] in seen_flags:
        raise ValueError(f"invalid or duplicate SA117 option flag: {mode_name}/{option_name}")
    if not option["help"]:
        raise ValueError(f"empty SA117 option help: {mode_name}/{option_name}")
    seen_flags.add(option["flag"])
    if option["kind"] not in {"paths", "store_true", "value", "path"}:
        raise ValueError(f"unknown SA117 option kind: {option['kind']!r}")
    if option["kind"] == "paths" and option.get("nargs") != "*":
        raise ValueError(f"paths option must have nargs '*': {mode_name}/{option_name}")
    if option["kind"] != "paths" and "nargs" in option:
        raise ValueError(f"nargs is only valid for paths options: {mode_name}/{option_name}")
    if "default" in option and option["kind"] not in {"path", "value"}:
        raise ValueError(f"default is invalid for boolean/path-list option: {option_name}")
    if "default" in option and not isinstance(option["default"], str):
        raise ValueError(f"SA117 option default must be a string: {mode_name}/{option_name}")


def _validate_profile_declaration(
    mode_name: str, profile: str, declaration: Any, option_names: set[str]
) -> set[str]:
    """Validate one caller profile's required/optional declaration."""
    if (
        not isinstance(declaration, dict)
        or set(declaration) != {"required", "optional"}
        or not isinstance(declaration["required"], list)
        or not isinstance(declaration["optional"], list)
        or any(
            not isinstance(item, str) for item in declaration["required"] + declaration["optional"]
        )
    ):
        raise ValueError(f"invalid SA117 profile declaration: {mode_name}/{profile}")
    required = declaration["required"]
    optional = declaration["optional"]
    if len(required) != len(set(required)) or len(optional) != len(set(optional)):
        raise ValueError(f"duplicate SA117 profile option: {mode_name}/{profile}")
    if set(required) & set(optional) or not set(required + optional) <= option_names:
        raise ValueError(f"unknown or overlapping SA117 profile option: {mode_name}/{profile}")
    return set(required + optional)


def _validate_mode_contract(mode_name: str, mode: Any) -> None:
    """Validate one mode's help, options, and profile declarations."""
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
        _validate_option_contract(mode_name, option_name, option, seen_flags)
    option_names = set(options)
    declared_options: set[str] = set()
    for profile, declaration in profiles.items():
        declared_options |= _validate_profile_declaration(
            mode_name, profile, declaration, option_names
        )
    if declared_options != option_names:
        raise ValueError(f"undeclared SA117 mode option: {mode_name}")


def _validate_contract_modes(modes: Any) -> None:
    """Validate the four mode declarations."""
    if not isinstance(modes, dict) or set(modes) != {"worktree", "emit", "lock", "lock-diff"}:
        raise ValueError("SA117 contract modes must be exactly worktree, emit, lock, lock-diff")
    for mode_name, mode in modes.items():
        _validate_mode_contract(mode_name, mode)


def _validate_contract_consumers(consumers: Any) -> None:
    """Validate the named consumer declarations."""
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


def _validate_contract_metadata(metadata: Any) -> None:
    """Validate the revision metadata block."""
    if not isinstance(metadata, dict) or set(metadata) != {"rev_004"}:
        raise ValueError("SA117 contract metadata must contain only rev_004")
    if not isinstance(metadata["rev_004"], str):
        raise ValueError("SA117 rev_004 metadata must be a string")


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
    _validate_contract_modes(contract["modes"])
    _validate_contract_consumers(contract["consumers"])
    _validate_contract_metadata(contract["metadata"])


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
