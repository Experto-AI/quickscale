#!/usr/bin/env python3
"""
Check source-module app declarations in authoritative manifests.

The source manifests under ``quickscale_modules`` are the authority for this
check.  A module that contains Django model or migration source must declare
exactly one static ``apps`` wiring projection whose value is a non-empty list
of non-blank strings.  Service-style modules without that source evidence are
allowed to omit the projection.

Exit codes:
    0: every evidence-bearing module conforms.
    1: one or more declaration violations were found.
    2: the source inventory or a manifest could not be trusted.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

MODULES_DIR_NAME = "quickscale_modules"
MANIFEST_NAME = "module.yml"
_REPO_ROOT = Path(os.environ.get("REPO_ROOT", os.getcwd())).resolve()


class AuthorityError(RuntimeError):
    """Raised when the source inventory or manifest authority is unusable."""


class _DuplicateKeyYAMLError(ValueError):
    """Raised when a source manifest repeats a mapping key."""


class _StrictSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
    """Construct a YAML mapping while rejecting duplicate keys."""
    from yaml.nodes import MappingNode

    if not isinstance(node, MappingNode):
        return cast(dict[Any, Any], loader.construct_object(node, deep=deep))
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise _DuplicateKeyYAMLError(f"Duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass(frozen=True)
class ModuleManifest:
    """A parsed source manifest and its module identity."""

    name: str
    path: Path
    data: dict[str, Any]


def _scan_directory(directory: Path, error_context: str) -> list[os.DirEntry[str]]:
    """Return a complete, sorted directory inventory or fail closed."""
    try:
        with os.scandir(directory) as entries:
            return sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        raise AuthorityError(f"{error_context}: {exc}") from exc


def _display_path(path: Path, modules_root: Path) -> str:
    """Return a stable, repository-relative path for diagnostics."""
    try:
        return path.relative_to(modules_root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    """Read and validate the manifest's YAML container shape."""
    try:
        text = manifest_path.read_text(encoding="utf-8")
        parsed = yaml.load(text, Loader=_StrictSafeLoader)
    except _DuplicateKeyYAMLError as exc:
        raise AuthorityError(
            f"Cannot read or parse source manifest {manifest_path}: {exc}"
        ) from exc
    except (OSError, TypeError, UnicodeError, yaml.YAMLError) as exc:
        raise AuthorityError(
            f"Cannot read or parse source manifest {manifest_path}: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise AuthorityError(f"Source manifest must contain a mapping: {manifest_path}")

    name = parsed.get("name")
    if not isinstance(name, str) or not name.strip():
        raise AuthorityError(f"Source manifest has no valid name: {manifest_path}")

    derivation = parsed.get("derivation")
    if derivation is not None and not isinstance(derivation, dict):
        raise AuthorityError(f"Manifest derivation must be a mapping: {manifest_path}")
    if isinstance(derivation, dict):
        projections = derivation.get("wiring_projections")
        if projections is not None and not isinstance(projections, list):
            raise AuthorityError(f"Manifest wiring_projections must be a list: {manifest_path}")

    return parsed


def _manifest_inventory(modules_root: Path) -> list[ModuleManifest]:
    """Load the sorted source manifest inventory or fail closed."""
    try:
        modules_stat = modules_root.stat()
    except FileNotFoundError as exc:
        raise AuthorityError(f"Modules directory not found: {modules_root}") from exc
    except OSError as exc:
        raise AuthorityError(f"Cannot inspect modules directory {modules_root}: {exc}") from exc
    if not stat.S_ISDIR(modules_stat.st_mode):
        raise AuthorityError(f"Modules directory not found: {modules_root}")

    module_entries = _scan_directory(
        modules_root,
        f"Cannot enumerate module manifests in {modules_root}",
    )
    manifest_paths: list[Path] = []
    for entry in module_entries:
        entry_path = Path(entry.path)
        try:
            if not entry.is_dir(follow_symlinks=True):
                continue
        except OSError as exc:
            raise AuthorityError(
                f"Cannot inspect module inventory entry {entry_path}: {exc}"
            ) from exc

        manifest_path = entry_path / MANIFEST_NAME
        try:
            manifest_path.stat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise AuthorityError(f"Cannot inspect source manifest {manifest_path}: {exc}") from exc
        manifest_paths.append(manifest_path)

    if not manifest_paths:
        raise AuthorityError(f"No source manifests found under {modules_root}")

    manifests: list[ModuleManifest] = []
    identities: dict[str, Path] = {}
    for manifest_path in manifest_paths:
        try:
            module_dir = manifest_path.parent
            manifest = _read_manifest(manifest_path)
            name = manifest["name"]
            assert isinstance(name, str)
            previous = identities.get(name)
            if previous is not None:
                raise AuthorityError(
                    f"Duplicate source manifest identity {name!r}: "
                    f"{_display_path(previous, modules_root)} and "
                    f"{_display_path(manifest_path, modules_root)}"
                )
            if name != module_dir.name:
                raise AuthorityError(
                    "Manifest identity does not match its directory: "
                    f"{_display_path(manifest_path, modules_root)} declares {name!r}"
                )
            identities[name] = manifest_path
            manifests.append(ModuleManifest(name=name, path=manifest_path, data=manifest))
        except AuthorityError:
            raise
        except (OSError, UnicodeError) as exc:
            raise AuthorityError(f"Cannot inspect source manifest {manifest_path}: {exc}") from exc

    return manifests


def find_evidence(module_dir: Path) -> tuple[Path, ...]:
    """
    Return sorted model/migration evidence beneath a module's ``src``.

    ``models.py`` is evidence wherever it occurs under ``src``.  Migration
    evidence is any Python file in a directory named ``migrations`` except
    the package's ``__init__.py``.  Names such as README files and adapters do
    not constitute evidence.
    """
    src_dir = module_dir / "src"
    try:
        source_stat = src_dir.stat()
    except FileNotFoundError:
        return ()
    except OSError as exc:
        raise AuthorityError(f"Cannot inspect module source {src_dir}: {exc}") from exc
    if not stat.S_ISDIR(source_stat.st_mode):
        raise AuthorityError(f"Module source path is not a directory: {src_dir}")

    candidates: list[Path] = []
    pending_directories = [src_dir]
    while pending_directories:
        directory = pending_directories.pop()
        entries = _scan_directory(
            directory,
            f"Cannot enumerate module source {src_dir} at {directory}",
        )
        child_directories: list[Path] = []
        for entry in entries:
            path = Path(entry.path)
            try:
                if entry.is_dir(follow_symlinks=False):
                    child_directories.append(path)
                    continue
                if path.suffix != ".py":
                    continue
                candidate_stat = entry.stat(follow_symlinks=True)
            except OSError as exc:
                raise AuthorityError(f"Cannot inspect module source entry {path}: {exc}") from exc
            if stat.S_ISREG(candidate_stat.st_mode):
                candidates.append(path)
        pending_directories.extend(reversed(child_directories))

    evidence: list[Path] = []
    for path in candidates:
        try:
            relative_parts = path.relative_to(src_dir).parts
        except ValueError as exc:
            raise AuthorityError(f"Cannot inspect source evidence {path}: {exc}") from exc
        is_model = path.name == "models.py"
        is_migration = (
            path.suffix == ".py"
            and path.name != "__init__.py"
            and "migrations" in relative_parts[:-1]
        )
        if is_model or is_migration:
            evidence.append(path)

    return tuple(sorted(evidence, key=lambda path: path.relative_to(module_dir).as_posix()))


def _projection_violation(manifest: ModuleManifest, evidence: tuple[Path, ...]) -> str | None:
    """Return one deterministic declaration diagnostic, if the module fails."""
    derivation = manifest.data.get("derivation")
    projections: list[Any] = []
    if isinstance(derivation, dict):
        raw_projections = derivation.get("wiring_projections")
        if isinstance(raw_projections, list):
            projections = raw_projections

    apps = [
        projection
        for projection in projections
        if isinstance(projection, dict) and projection.get("wiring_field") == "apps"
    ]
    evidence_text = ", ".join(
        path.relative_to(manifest.path.parent).as_posix() for path in evidence
    )
    prefix = f"{manifest.name}: evidence={evidence_text}"

    if not apps:
        return f"{prefix}; missing apps declaration"
    if len(apps) != 1:
        return f"{prefix}; duplicate apps declarations (expected exactly one)"

    projection = apps[0]
    if projection.get("derivation_type") != "static":
        return f"{prefix}; malformed apps declaration: derivation_type must be static"

    expression = projection.get("expression")
    if not isinstance(expression, dict):
        return f"{prefix}; malformed apps declaration: expression must be a mapping"

    value = expression.get("value")
    if not isinstance(value, list) or not value:
        return f"{prefix}; malformed apps declaration: expression.value must be non-empty"
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return (
            f"{prefix}; malformed apps declaration: expression.value must contain "
            "only non-blank strings"
        )
    return None


def check_module_app_declarations(modules_root: Path) -> list[str]:
    """Return sorted declaration violations for a source module root."""
    manifests = _manifest_inventory(modules_root)
    violations: list[tuple[str, str]] = []
    for manifest in manifests:
        evidence = find_evidence(manifest.path.parent)
        if not evidence:
            continue
        violation = _projection_violation(manifest, evidence)
        if violation is not None:
            identity = f"{manifest.name}:{evidence[0].relative_to(manifest.path.parent).as_posix()}"
            violations.append((identity, violation))
    return [message for _, message in sorted(violations)]


def main(argv: list[str] | None = None) -> int:
    """Run the source-bound declaration gate."""
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path(args[0]).resolve() if args else _REPO_ROOT
    modules_root = repo_root / MODULES_DIR_NAME
    try:
        violations = check_module_app_declarations(modules_root)
    except AuthorityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for violation in violations:
        print(f"VIOLATION: {violation}")
    if violations:
        print(f"Found {len(violations)} module app declaration violation(s).")
        return 1

    print("All evidence-bearing module app declarations are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
