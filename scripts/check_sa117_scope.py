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
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Hashable
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
# private name.  Production paths below always resolve the inventory for the
# candidate repository at the point of use.
_LOCKED_MODULE_PACKAGES: Final[list[str]] = _locked_module_packages(_authoritative_module_names())


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


def load_scope(scope_path: Path = DEFAULT_SCOPE_PATH) -> list[dict[str, Any]]:
    """Load the path allowlist and validate its outer shape."""
    if not scope_path.is_file():
        raise FileNotFoundError(f"SA117 scope file not found: {scope_path}")
    with scope_path.open("rb") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("paths"), list):
        raise ValueError(f"SA117 scope file must contain a 'paths' list: {scope_path}")
    for entry in data["paths"]:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ValueError(f"invalid SA117 scope entry: {entry!r}")
    return data["paths"]


def build_allowlist(scope_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a normalised allowlist, rejecting lexical duplicates."""
    result: dict[str, dict[str, Any]] = {}
    for entry in scope_entries:
        path = _normalise(entry["path"])
        if path in result:
            raise ValueError(f"duplicate path in SA117 scope: {path!r}")
        result[path] = entry
    return result


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
) -> int:
    """Check that candidate paths are members of the allowlist."""
    del repo_root, allow_untracked
    try:
        allowed = build_allowlist(load_scope(scope_path))
        if paths is None:
            raise ValueError("--paths is required for worktree mode")
        current = {_normalise(path) for path in paths}
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


def mode_emit(scope_path: Path, *, phase: str | None = None) -> int:
    """Emit allowlisted paths, optionally filtered by phase."""
    try:
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
) -> int:
    """Check that a candidate path set exactly matches the allowlist."""
    try:
        allowed = build_allowlist(load_scope(scope_path))
        current_paths = (
            paths if paths is not None else _read_git_tracked_files(repo_root or SCOPE_DIR.parent)
        )
        current = _filter_scope_paths(
            {_normalise(path) for path in current_paths}, scripts_only=scripts_only
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


def _expected_inventory(repo_root: Path | None = None) -> list[str]:
    """Return the inventory paths derived from the authoritative modules."""
    module_names = _authoritative_module_names(repo_root)
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
        paths = _expected_inventory(root)
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
    except (LockDiffError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if output_safe_to_remove:
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="check_sa117_scope.py")
    parser.add_argument("--scope", type=Path, default=DEFAULT_SCOPE_PATH)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    worktree = subparsers.add_parser("worktree")
    worktree.add_argument("--paths", nargs="*", default=None)
    worktree.add_argument("--allow-untracked", action="store_true")
    worktree.add_argument("--scripts-only", action="store_true")
    emit = subparsers.add_parser("emit")
    emit.add_argument("--phase")
    lock = subparsers.add_parser("lock")
    lock.add_argument("--paths", nargs="*", default=None)
    lock.add_argument("--scripts-only", action="store_true")
    lock_diff = subparsers.add_parser("lock-diff")
    lock_diff.add_argument("--baseline-ref", required=True)
    lock_diff.add_argument("--candidate", type=Path, required=True)
    lock_diff.add_argument("--expected-version", required=True)
    lock_diff.add_argument("--output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.mode == "worktree":
        return mode_worktree(
            args.scope,
            paths=args.paths,
            allow_untracked=args.allow_untracked,
            scripts_only=args.scripts_only,
        )
    if args.mode == "emit":
        return mode_emit(args.scope, phase=args.phase)
    if args.mode == "lock":
        return mode_lock(args.scope, paths=args.paths, scripts_only=args.scripts_only)
    if args.mode == "lock-diff":
        return mode_verify_lock_diff(
            args.candidate,
            baseline_ref=args.baseline_ref,
            expected_version=args.expected_version,
            output_path=args.output,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
