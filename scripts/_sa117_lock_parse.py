"""
Version/lock parsing and inventory reads for the SA267(d) split.

The strict VERSION, TOML, YAML, and Python version readers, the authoritative
module discovery, the expected inventory, and the baseline/candidate content
readers live here.  The facade and the lock-diff sibling import these names
from this defining sibling, never through the facade (decisions.md,
Split-Facade Seams).  Behavior is unchanged from the pre-split module.
"""

from __future__ import annotations

import ast
import datetime
import hashlib
import stat
import subprocess
import sys
import tomllib
from collections.abc import Hashable
from pathlib import Path
from typing import Any, Final

import yaml
from _sa117_scope_contract import SCOPE_DIR
from yaml.events import AliasEvent
from yaml.nodes import MappingNode

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


def _find_version_assignments(tree: ast.Module) -> list[ast.Assign]:
    """Return the direct ``__version__ = <string literal>`` assignments."""
    return [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "__version__"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]


def _binds_version_via_import(node: ast.AST) -> bool:
    """Return whether an import statement binds ``__version__`` (or is a star import)."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            bound_name = alias.asname if alias.asname is not None else alias.name.partition(".")[0]
            if bound_name == "__version__":
                return True
        return False
    if isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                return True
            bound_name = alias.asname if alias.asname is not None else alias.name
            if bound_name == "__version__":
                return True
        return False
    return False


def _binds_reserved_version_name(node: ast.AST, accepted_target: ast.expr) -> bool:
    """Return whether a node binds or deletes ``__version__`` outside the literal."""
    if isinstance(node, ast.Name) and node.id == "__version__":
        return isinstance(node.ctx, (ast.Store, ast.Del)) and node is not accepted_target
    if isinstance(node, ast.arg) and node.arg == "__version__":
        return True
    if (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == "__version__"
    ):
        return True
    if isinstance(node, ast.ExceptHandler) and node.name == "__version__":
        return True
    if isinstance(node, (ast.TypeVar, ast.ParamSpec, ast.TypeVarTuple)):
        return node.name == "__version__"
    if isinstance(node, (ast.MatchAs, ast.MatchStar)):
        return node.name == "__version__"
    if isinstance(node, ast.MatchMapping):
        return node.rest == "__version__"
    return _binds_version_via_import(node)


def _parse_python_version(content: bytes, path: str) -> str:
    """Require exactly one direct ``__version__ = <string>`` assignment."""
    try:
        tree = ast.parse(content.decode("utf-8"), filename=path)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise LockDiffError(f"{path}: malformed Python: {exc}") from exc
    candidates = _find_version_assignments(tree)
    if len(candidates) != 1:
        raise LockDiffError(f"{path}: expected exactly one direct __version__ literal")

    accepted_target = candidates[0].targets[0]
    binding_error = f"{path}: every other __version__ binding or deletion is forbidden"
    for node in ast.walk(tree):
        if _binds_reserved_version_name(node, accepted_target):
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


_BUNDLED_MANIFEST_ROOT: Final[str] = "quickscale_core/src/quickscale_core/data/manifests/"
_SOURCE_MANIFEST_ROOT: Final[str] = "quickscale_modules/"


def _derived_snapshot_source(path: str) -> str | None:
    """
    Return the source manifest a bundled snapshot path is derived from.

    SA280 (b): the bundled manifests under ``data/manifests/`` are build
    artifacts materialized from ``quickscale_modules/<name>/module.yml``.  A
    tree (or Git ref) that has not been materialized yet reads a bundled
    snapshot through its source manifest; the two are the same bytes by
    construction.
    """
    if not path.startswith(_BUNDLED_MANIFEST_ROOT):
        return None
    tail = path[len(_BUNDLED_MANIFEST_ROOT) :]
    module, _, filename = tail.partition("/")
    if not module or filename != "module.yml":
        return None
    return f"{_SOURCE_MANIFEST_ROOT}{module}/module.yml"


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
    missing = [
        path
        for path in paths
        if path not in entries and _derived_snapshot_source(path) not in entries
    ]
    if missing:
        raise LockDiffError(f"baseline is missing expected paths: {', '.join(missing)}")
    contents: dict[str, bytes] = {}
    for path in paths:
        lookup = path if path in entries else _derived_snapshot_source(path)
        mode, kind_sha = entries[lookup]
        kind, object_sha = kind_sha.split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise LockDiffError(f"baseline path is not a regular 100644/100755 blob: {lookup}")
        blob = subprocess.run(
            ["git", "cat-file", "blob", object_sha],
            cwd=repo_root,
            capture_output=True,
            timeout=30,
        )
        if blob.returncode:
            raise LockDiffError(f"cannot read baseline blob: {lookup}")
        contents[path] = blob.stdout
    return contents


def _read_candidate_file(root: Path, path: str) -> bytes | None:
    """Return a candidate file's bytes, or ``None`` when the path is absent."""
    candidate = root / path
    try:
        info = candidate.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LockDiffError(f"candidate path cannot be inspected: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise LockDiffError(f"candidate path is not a regular non-symlink file: {path}")
    try:
        return candidate.read_bytes()
    except OSError as exc:
        raise LockDiffError(f"candidate path cannot be read: {path}") from exc


def _candidate_contents(root: Path, paths: list[str]) -> dict[str, bytes]:
    """
    Read expected candidate files, rejecting symlinks and non-regular files.

    SA280 (b): an absent bundled snapshot (a tree that has not been
    materialized yet) reads through its source manifest instead.
    """
    contents: dict[str, bytes] = {}
    for path in paths:
        payload = _read_candidate_file(root, path)
        if payload is None:
            source = _derived_snapshot_source(path)
            payload = _read_candidate_file(root, source) if source is not None else None
        if payload is None:
            raise LockDiffError(f"candidate path cannot be inspected: {path}")
        contents[path] = payload
    return contents
