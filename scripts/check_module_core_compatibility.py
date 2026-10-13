#!/usr/bin/env python3
"""
SA9.2 — Module-vs-oldest-claimed-core compatibility check.

For each module in ``quickscale_modules/*/`` that declares a
``quickscale-core`` dependency in its ``module.yml``:

**Phase 1 — Static analysis (fast path):**

1. Confirms the module manifest declares the bare
   ``quickscale-core`` dependency name (rule 39).
2. Collects all ``from quickscale_core`` / ``import quickscale_core``
   statements from the module's Python source tree using ``ast``.
3. Resolves each imported symbol against the on-disk core source to
   confirm the referenced module path exists and, when a named symbol
   is imported, that the symbol is actually defined in the target file.
4. Asserts the specifier owned by the module ``pyproject.toml`` is the
   monorepo path dependency or exactly the lockstep pin derived from
   ``VERSION`` — floor = the release being published, ceiling = the next
   minor.  The manifest entry itself stays bare; this is the gate that
   keeps a stale or hand-edited pin from reaching publish.

**Phase 2 — Install / import probe (runtime check):**

For each module that declares a quantifiable minimum core version:

5. Creates an isolated temporary virtual environment.
6. Installs ``quickscale-core==<minimum_claimed_version>`` from PyPI.
7. Installs the module's non-core Python dependencies.
8. Adds the module source to the Python path and attempts to import the
   module's package (and its core-importing submodules).

This probe proves that a published consumer who installs only the
oldest supported ``quickscale-core`` release can import the module
without ``ImportError``.  A passing probe is the strongest pre-publish
evidence that the module's ``module.yml`` version claim is honest.

Thoroughness notes
-----------------
- Both top-level imports (``from quickscale_core.x import y``) and
  lazy/nested imports (inside functions, classes) are detected by the
  static pass.
- Literal ``importlib.import_module("quickscale_core...")`` calls reached from
  a module's ``__getattr__`` are followed as lazy facade edges. Other dynamic
  imports and try/except-based optional imports are **not** detected statically.
- Star imports (``from quickscale_core.x import *``) are flagged but
  resolved via ``__all__`` when the target module defines one, or
  reported as requiring manual review otherwise.
- Re-exported names are resolved against the immediate source module,
  matching Python's binding semantics.
- The install/import probe skips modules whose minimum version could
  not be extracted from the dependency spec, and gracefully handles
  versions not yet published to PyPI.

Exit codes:
    0 — all modules compatible
    1 — one or more incompatibilities found
    2 — a configuration or filesystem error
"""

# The implementation lives in private ``_module_core_compat_*`` siblings
# (SA267): ``_module_core_compat_versions`` (version and pyproject/manifest
# parsing), ``_module_core_compat_ast`` (AST import extraction and symbol
# resolution), and ``_module_core_compat_probe`` (the install/import probe).
# This module owns the per-module orchestration, the CLI, and the constants
# the rule-37 identity allowlist pins, and re-exports the pre-split surface
# for unchanged import paths, so a test's seam is the sibling that defines the
# name (decisions.md, Split-Facade Seams).

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import ast as ast
import os as os
import re as re
import subprocess as subprocess
import sys
import tempfile as tempfile
import tomllib  # Python 3.11+ stdlib
from pathlib import Path
from typing import Final
from typing import cast as cast

# Ensure the private siblings are importable whether this file is executed
# directly (``sys.path[0]`` is ``scripts/``) or imported with only the
# repository root on ``sys.path`` (``scripts.check_module_core_compatibility``).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _module_core_compat_ast import (
    _collect_core_imports as _collect_core_imports,
)
from _module_core_compat_ast import (
    _collect_defined_names as _collect_defined_names,
)
from _module_core_compat_ast import (
    _collect_defined_names_internal as _collect_defined_names_internal,
)
from _module_core_compat_ast import (
    _collect_getattr_dynamic_submodules as _collect_getattr_dynamic_submodules,
)
from _module_core_compat_ast import (
    _collect_lazy_symbol_names as _collect_lazy_symbol_names,
)
from _module_core_compat_ast import (
    _collect_submodule_aliases as _collect_submodule_aliases,
)
from _module_core_compat_ast import (
    _CoreImportVisitor as _CoreImportVisitor,
)
from _module_core_compat_ast import (
    _module_path_to_fs_path as _module_path_to_fs_path,
)
from _module_core_compat_ast import (
    _resolve_import as _resolve_import,
)
from _module_core_compat_ast import (
    _resolve_name_via_getattr_chain as _resolve_name_via_getattr_chain,
)
from _module_core_compat_probe import (
    _build_probe_script as _build_probe_script,
)
from _module_core_compat_probe import (
    _probe_module_install_import as _probe_module_install_import,
)
from _module_core_compat_versions import (
    _MIN_VERSION_PATTERN as _MIN_VERSION_PATTERN,
)
from _module_core_compat_versions import (
    CORE_DEP_NAME as CORE_DEP_NAME,
)
from _module_core_compat_versions import (
    _declared_core_spec as _declared_core_spec,
)
from _module_core_compat_versions import (
    _expected_core_spec as _expected_core_spec,
)
from _module_core_compat_versions import (
    _extract_min_core_version as _extract_min_core_version,
)
from _module_core_compat_versions import (
    _get_core_dep_spec as _get_core_dep_spec,
)
from _module_core_compat_versions import (
    _get_management_command_modules as _get_management_command_modules,
)
from _module_core_compat_versions import (
    _get_module_non_core_deps as _get_module_non_core_deps,
)
from _module_core_compat_versions import (
    _get_module_package_name as _get_module_package_name,
)
from _module_core_compat_versions import (
    _get_pyproject_core_dep as _get_pyproject_core_dep,
)
from _module_core_compat_versions import (
    _parse_module_yml as _parse_module_yml,
)
from _module_core_compat_versions import (
    _parse_version_tuple as _parse_version_tuple,
)
from _module_core_compat_versions import (
    _poetry_spec_to_pep440 as _poetry_spec_to_pep440,
)
from _module_core_compat_versions import (
    _read_version_file as _read_version_file,
)

#: Every name the facade re-exports.  Per decisions.md § Split-Facade Seams a
#: facade re-exports public names only: incidental imported bindings
#: (``ast``, ``cast``, ``Path``, ...) stay module attributes but are
#: deliberately not part of the wildcard surface.
__all__ = [
    "CORE_DEP_NAME",
    "CORE_SRC_RELATIVE",
    "MODULES_DIR_RELATIVE",
    "MODULE_YML",
    "REPO_ROOT_ENV",
    "SKIP_INSTALL_PROBE_FLAG",
    "SKIP_INSTALL_PROBE_MODULES",
    "main",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT_ENV: Final[str] = "REPO_ROOT"
_DEFAULT_REPO_ROOT: Final[Path] = Path(os.environ.get(REPO_ROOT_ENV, os.getcwd())).resolve()

CORE_SRC_RELATIVE: Final[Path] = Path("quickscale_core/src")
MODULES_DIR_RELATIVE: Final[Path] = Path("quickscale_modules")
MODULE_YML: Final[str] = "module.yml"

# Modules exempt from the install/import probe (Phase 2) only.
# Static analysis (Phase 1) still runs for all modules.
# This is a temporary measure — remove entries when their root cause is fixed.
SKIP_INSTALL_PROBE_MODULES: Final[dict[str, str]] = {
    "backups": (
        "Pre-existing version mismatch: no published quickscale-core "
        ">=0.86.0,<0.87.0 contains quickscale_core.dr_engine, which "
        "backups' services.py and management commands require. "
        "Skipped until SA9.3\u2013SA9.5 facade work replaces the deep "
        "dr_engine imports with quickscale_core.runtime (roadmap "
        "decision confirmed 2026-07-03)."
    ),
}


# ---------------------------------------------------------------------------
# Per-module checks
# ---------------------------------------------------------------------------


def _check_pyproject_pin(
    mod_dir: Path, expected_spec: str, current_version_str: str
) -> tuple[bool, bool]:
    """
    Check one module's pyproject lockstep pin.

    Returns ``(failed, skip_module)``; a malformed pyproject reports and
    short-circuits the module.
    """
    try:
        pyproject_core = _get_pyproject_core_dep(mod_dir)
    except tomllib.TOMLDecodeError as exc:
        print(f"  ERROR: Malformed module pyproject.toml ({mod_dir / 'pyproject.toml'}): {exc}")
        return True, True
    if pyproject_core is None:
        print("  FAIL: pyproject.toml does not declare quickscale-core.")
        return True, False
    if isinstance(pyproject_core, str):
        declared_spec = pyproject_core.replace(" ", "")
        if declared_spec != expected_spec:
            print(
                f"  FAIL: lockstep pin is {declared_spec or '(empty)'}; expected "
                f"{expected_spec} for core {current_version_str}."
            )
            return True, False
        return False, False
    if isinstance(pyproject_core, dict):
        if "version" in pyproject_core:
            # A declared version wins for consumers, exactly as the CLI
            # resolver selects it; it must be a non-blank lockstep pin,
            # even when a path is also declared.
            table_version = pyproject_core["version"]
            if not isinstance(table_version, str) or not table_version.strip():
                print(
                    "  FAIL: pyproject.toml quickscale-core version spec is blank or not a string."
                )
                return True, False
            declared_spec = table_version.replace(" ", "")
            if declared_spec != expected_spec:
                print(
                    f"  FAIL: lockstep pin is {declared_spec or '(empty)'}; "
                    f"expected {expected_spec} for core {current_version_str}."
                )
                return True, False
            return False, False
        if isinstance(pyproject_core.get("path"), str) and pyproject_core["path"].strip():
            # Monorepo path dependency: no published spec to stamp.
            return False, False
        print(
            "  FAIL: pyproject.toml quickscale-core entry declares no usable "
            "source (path or version)."
        )
        return True, False
    print(
        "  FAIL: pyproject.toml quickscale-core entry declares no usable source (path or version)."
    )
    return True, False


def _check_module_imports(mod_dir: Path, core_src_root: Path) -> tuple[bool, bool]:
    """
    Resolve one module's static quickscale_core imports.

    Returns ``(failed, skip_module)``; a missing source tree or a clean tree
    short-circuits the module's later phases.
    """
    src_dir = mod_dir / "src"
    if not src_dir.is_dir():
        print("  SKIP: No src/ directory — cannot check imports.")
        return False, True

    imports_by_file = _collect_core_imports(src_dir)
    if not imports_by_file:
        print("  OK: No quickscale_core imports found in module source.")
        return False, True

    # Resolve each import
    file_issues: list[str] = []
    for py_file, import_list in imports_by_file.items():
        rel_path = py_file.relative_to(src_dir)
        for module_path, imported_names in import_list:
            issues = _resolve_import(core_src_root, module_path, imported_names)
            if issues:
                file_issues.append(f"  In {rel_path}:")
                file_issues.extend(issues)

    if file_issues:
        print("  IMPORT ISSUES:")
        for line in file_issues:
            print(f"    {line}")
        return True, False

    total_groups = sum(len(lst) for lst in imports_by_file.values())
    total_files = len(imports_by_file)
    files_label = "file" if total_files == 1 else "files"
    groups_label = "group" if total_groups == 1 else "groups"
    print(
        f"  OK: {total_groups} quickscale_core import {groups_label}"
        f" in {total_files} {files_label} resolved."
    )
    return False, False


def _run_install_probe(mod_name: str, mod_dir: Path, src_dir: Path, min_ver_str: str) -> bool:
    """Run the Phase 2 install/import probe; return whether it reported issues."""
    if mod_name in SKIP_INSTALL_PROBE_MODULES:
        print(f"  INSTALL PROBE: Skipped — {SKIP_INSTALL_PROBE_MODULES[mod_name]}")
        return False
    try:
        package_name = _get_module_package_name(mod_dir)
    except tomllib.TOMLDecodeError as exc:
        print(f"  ERROR: Malformed module pyproject.toml ({mod_dir / 'pyproject.toml'}): {exc}")
        return True
    if package_name and src_dir.is_dir():
        probe_issues = _probe_module_install_import(
            mod_name=mod_name,
            package_name=package_name,
            min_version=min_ver_str,
            src_dir=src_dir,
            module_dir=mod_dir,
        )
        for pi in probe_issues:
            print(pi)
        return bool(probe_issues)
    print("  INSTALL PROBE: Could not determine package name from pyproject.toml — skipping probe.")
    return False


def _check_module(
    mod_dir: Path, core_src_root: Path, current_version_str: str, skip_install_probe: bool
) -> tuple[bool, bool, bool]:
    """
    Run every per-module check.

    Returns ``(failed, declares_core, reached_end)``: ``reached_end`` is false
    for a short-circuited module, which does not get the trailing blank line.
    """
    mod_name = mod_dir.name
    module_yml = mod_dir / MODULE_YML

    # Parse module.yml for core dependency
    try:
        data = _parse_module_yml(module_yml)
    except Exception as exc:
        print(f"[{mod_name}] ERROR: Could not parse {module_yml}: {exc}")
        return True, False, False

    dep_entry = _get_core_dep_spec(data)
    if dep_entry is None:
        print(f"[{mod_name}] No quickscale-core dependency declared — skipping.")
        return False, False, False

    print(f"[{mod_name}] quickscale-core dependency: {dep_entry}")

    expected_spec = _expected_core_spec(current_version_str)
    failed = False

    # Rule 39: the manifest lists the bare dependency name; the spec lives
    # in the module pyproject.toml.
    if dep_entry.strip() != CORE_DEP_NAME:
        print(
            f"  FAIL: manifest entry must be the bare name {CORE_DEP_NAME!r} "
            f"with the spec in pyproject.toml (rule 39); got {dep_entry!r}."
        )
        failed = True

    # The module pyproject owns the spec: the monorepo path dependency, or
    # exactly the lockstep pin derived from VERSION, so a stale or
    # hand-edited pin fails the gate rather than passing on a floor
    # comparison alone.
    pin_failed, skip_module = _check_pyproject_pin(mod_dir, expected_spec, current_version_str)
    if pin_failed:
        failed = True
    if skip_module:
        return failed, True, False

    # Phase 2 probes the floor of the derived lockstep spec: the oldest
    # released core the generated project's pin admits.
    min_ver_str = _extract_min_core_version(expected_spec)
    if min_ver_str is None:
        print(
            f"  WARNING: Could not extract minimum version from spec "
            f"({expected_spec}). Cannot verify version baseline."
        )

    imports_failed, skip_module = _check_module_imports(mod_dir, core_src_root)
    if imports_failed:
        failed = True
    if skip_module:
        return failed, True, False

    # ---- Phase 2: install / import probe ----
    if not skip_install_probe and min_ver_str is not None:
        if _run_install_probe(mod_name, mod_dir, mod_dir / "src", min_ver_str):
            failed = True

    return failed, True, True


SKIP_INSTALL_PROBE_FLAG: Final[str] = "--skip-install-probe"


# Prevent accidental import-time side effects by keeping main() explicit.
def main(argv: list[str] | None = None) -> int:
    """Run the compatibility check and return an exit code."""
    if argv is None:
        argv = sys.argv[1:]

    # Parse flags before positional arguments
    skip_install_probe = SKIP_INSTALL_PROBE_FLAG in argv
    positional_args = [a for a in argv if a != SKIP_INSTALL_PROBE_FLAG]

    repo_root = _DEFAULT_REPO_ROOT
    # Allow overriding via first positional argument for convenience
    if positional_args:
        repo_root = Path(positional_args[0]).resolve()

    core_src_root = (repo_root / CORE_SRC_RELATIVE).resolve()
    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()

    if not core_src_root.is_dir():
        print(
            f"ERROR: Core source directory not found: {core_src_root}",
            file=sys.stderr,
        )
        return 2
    if not modules_root.is_dir():
        print(
            f"ERROR: Modules directory not found: {modules_root}",
            file=sys.stderr,
        )
        return 2

    # Read current core version
    try:
        current_version_str = _read_version_file(repo_root)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Repository core version: {current_version_str}")
    print()

    overall_exit = 0

    # Scan module directories
    module_dirs = sorted(modules_root.iterdir())
    modules_found = 0
    modules_with_core_dep = 0

    for mod_dir in module_dirs:
        if not mod_dir.is_dir():
            continue
        if not (mod_dir / MODULE_YML).is_file():
            continue

        modules_found += 1
        failed, declares_core, reached_end = _check_module(
            mod_dir, core_src_root, current_version_str, skip_install_probe
        )
        if failed:
            overall_exit = 1
        if declares_core:
            modules_with_core_dep += 1
        if reached_end:
            print()  # blank line between modules

    # Summary
    if modules_found == 0:
        print("No modules found under quickscale_modules/.")
        return 0

    if modules_with_core_dep == 0:
        print("No modules declare a quickscale-core dependency.")
        return 0

    if overall_exit == 0:
        print("All modules compatible.")
    else:
        print("One or more compatibility issues found.")

    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
