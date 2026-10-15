#!/usr/bin/env python3
"""
SA204(c) — module migration freeze gate.

The clean-break freeze gives each shipped module's applied migration files a
*content identity*: the SHA-256 of every numbered migration file, recorded in
``scripts/migration_hashes.json`` (``sync_migration_hashes.py`` owns the
manifest).  From the release the freeze lands in, a shipped migration file is
immutable -- it may not be edited in place or disappear, and a schema change
ships as a new, higher-numbered migration.  The identity is file content, so
the gate works in shallow CI clones and needs no Git tag.

The gate compares the checked-in manifest against the shipped modules:

* every recorded ``(module, filename)`` must still resolve to a file whose
  SHA-256 matches the record -- an edited or deleted frozen file fails;
* a numbered migration present on disk but not yet recorded is a legal
  forward addition; the next manifest regeneration freezes it;
* every numbered migration file of a shipped module must name only public
  symbols -- a ``_``-prefixed attribute, module-path component, or imported
  name fails, because frozen history may name only symbols with a stability
  promise;
* the manifest's module set must equal the shipped-module inventory, so an
  unrecorded or removed module fails instead of passing unverified.

Exit codes:
    0 — every frozen migration file matches its recorded identity and no
        numbered migration names a private symbol
    1 — one or more freeze violations
    2 — the manifest or a module tree could not be inspected (fail closed)
"""

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from quickscale_core.contracts.module_discovery import (
    ImproperlyConfigured,
    authoritative_module_names,
    discover_shipped_module_paths,
)
from quickscale_core.migration_hashes import (
    NUMBERED_MIGRATION_PATTERN,
    MigrationHashError,
    hash_migration_file,
    resolve_module_migrations_dir,
)

# Ensure the manifest owner is importable whether this file is executed
# directly (``sys.path[0]`` is ``scripts/``) or imported with only the
# repository root on ``sys.path`` (``scripts.check_migration_freeze``).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sync_migration_hashes import (  # noqa: E402
    REPO_ROOT,
    ManifestError,
    load_manifest_modules,
)

DEFAULT_MANIFEST = REPO_ROOT / "scripts" / "migration_hashes.json"

#: The one importable module whose leading underscores are a language feature
#: rather than a privacy marker.
_LANGUAGE_MODULE = "__future__"


class _InspectionError(Exception):
    """The manifest or a migration file could not be inspected."""


@dataclass(frozen=True)
class _Violation:
    """One freeze violation, rendered deterministically."""

    module: str
    location: str
    detail: str

    def __str__(self) -> str:
        if self.location:
            return f"{self.module}/{self.location}: {self.detail}"
        return f"{self.module}: {self.detail}"


def _display_path(path: Path) -> str:
    """Return a repository-relative display path when possible."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


def _private_references(migration_path: Path) -> list[tuple[int, str]]:
    """
    Return ``(lineno, reference)`` for every private-symbol reference.

    Three reference shapes are private: an attribute whose name starts with
    ``_`` (the historical ``models._BlogMediaAssetImageField`` shape), an
    imported name starting with ``_``, and a module path with any private
    component.  ``from __future__ import ...`` is the one language-feature
    exception.
    """
    try:
        source = migration_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _InspectionError(f"read failed: {_display_path(migration_path)}: {exc}") from exc
    try:
        tree = ast.parse(source, filename=str(migration_path))
    except SyntaxError as exc:
        raise _InspectionError(f"AST parse failed: {_display_path(migration_path)}: {exc}") from exc

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            found.append((node.lineno, ast.unparse(node)))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module != _LANGUAGE_MODULE and _has_private_component(module):
                found.append((node.lineno, module))
            for alias in node.names:
                if alias.name.startswith("_"):
                    reference = f"{module}.{alias.name}" if module else alias.name
                    found.append((node.lineno, reference))
        elif isinstance(node, ast.Import):
            found.extend(
                (node.lineno, alias.name)
                for alias in node.names
                if alias.name != _LANGUAGE_MODULE and _has_private_component(alias.name)
            )
    found.sort()
    return found


def _has_private_component(dotted_name: str) -> bool:
    """Return whether any component of a dotted name starts with ``_``."""
    return any(component.startswith("_") for component in dotted_name.split("."))


def _collect_violations(
    manifest_modules: dict[str, dict[str, str]],
    names: list[str],
    paths: dict[str, Path],
) -> list[_Violation]:
    """Compare the manifest and the numbered migrations of every module."""
    violations: list[_Violation] = []
    shipped = set(names)
    recorded = set(manifest_modules)
    for extra in sorted(recorded - shipped):
        violations.append(
            _Violation(extra, "", "recorded in the manifest but not a shipped module")
        )
    for missing in sorted(shipped - recorded):
        violations.append(_Violation(missing, "", "shipped module has no manifest record"))

    for module_name in sorted(recorded & shipped):
        module_path = paths.get(module_name)
        if module_path is None:  # pragma: no cover - discovery mismatch fails closed
            continue
        migrations_dir = resolve_module_migrations_dir(module_path)
        recorded_files = manifest_modules[module_name]
        if migrations_dir is None:
            if recorded_files:
                violations.append(
                    _Violation(
                        module_name,
                        "",
                        "recorded migrations are gone: the module no longer ships "
                        "a migrations package",
                    )
                )
            continue

        for filename in sorted(recorded_files):
            if not NUMBERED_MIGRATION_PATTERN.match(filename):
                violations.append(
                    _Violation(
                        module_name,
                        filename,
                        "manifest records a file that is not a numbered migration",
                    )
                )
                continue
            file_path = migrations_dir / filename
            if not file_path.is_file():
                violations.append(_Violation(module_name, filename, "frozen file is missing"))
                continue
            try:
                digest = hash_migration_file(file_path)
            except OSError as exc:
                raise _InspectionError(f"read failed: {_display_path(file_path)}: {exc}") from exc
            if digest != recorded_files[filename]:
                violations.append(
                    _Violation(
                        module_name,
                        filename,
                        "frozen content changed "
                        f"(recorded {recorded_files[filename]}, found {digest})",
                    )
                )

        for file_path in sorted(migrations_dir.iterdir()):
            if not (file_path.is_file() and NUMBERED_MIGRATION_PATTERN.match(file_path.name)):
                continue
            for lineno, reference in _private_references(file_path):
                violations.append(
                    _Violation(
                        module_name,
                        f"{file_path.name}:{lineno}",
                        f"references private symbol {reference}",
                    )
                )

    violations.sort(key=lambda violation: (violation.module, violation.location, violation.detail))
    return violations


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the shipped modules' migration files against the freeze manifest.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        type=str,
        help="Path to the manifest (default: scripts/migration_hashes.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the migration freeze gate and return an exit code."""
    args = _parse_args(argv)
    manifest_path = Path(args.manifest).resolve() if args.manifest else DEFAULT_MANIFEST

    try:
        manifest_modules = load_manifest_modules(manifest_path)
        names = authoritative_module_names()
        paths = discover_shipped_module_paths()
        if sorted(paths) != names:
            raise _InspectionError(
                "discovered module directories do not match the authoritative "
                f"inventory: {sorted(paths)} != {names}"
            )
        violations = _collect_violations(manifest_modules, names, paths)
    except (
        ManifestError,
        MigrationHashError,
        ImproperlyConfigured,
        _InspectionError,
        UnicodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"ERROR: File not found: {exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"ERROR: Permission denied: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: I/O error: {exc}", file=sys.stderr)
        return 2

    if not violations:
        frozen_count = sum(len(files) for files in manifest_modules.values())
        print(
            "Frozen module migrations match their recorded content identity:\n"
            f"  • {frozen_count} recorded migration file(s) byte-identical across "
            f"{len(manifest_modules)} recorded module(s).\n"
            "  • No numbered migration names a private symbol."
        )
        return 0

    print("Migration freeze violations:")
    for violation in violations:
        print(f"  {violation}")
    print(
        f"\n{len(violations)} freeze violation(s) found.\n"
        "A frozen migration file is immutable: edit none, delete none, and ship "
        "a new numbered migration for a schema change."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
