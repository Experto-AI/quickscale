"""
Rule 39's manifest-dependency mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_dependencies`;
that module re-exports every public name defined here, so existing import
paths keep working.
"""

from __future__ import annotations

import re
import tomllib
from typing import Any

from scripts.module_conventions.core import (
    SNAKE_CASE,
    Module,
)

#: The lockstep core dependency every module declares (SA260); its manifest
#: name is bare and its spec lives in the module's ``pyproject.toml``.
CORE_DEPENDENCY_NAME = "quickscale-core"

#: Bare PEP 508 package names.  A version specifier belongs in the module's
#: ``pyproject.toml``, never in the manifest (coherence proposal 18).
DEPENDENCY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")

#: pyproject runtime table keys that are not module runtime packages.
BASE_RUNTIME_DEPENDENCY_NAMES = frozenset({"python", "django"})


def _dependency_value_is_usable(value: Any) -> bool:
    """
    Return whether a Poetry dependency value declares a usable spec.

    A bare, empty, or spec-less table declares no version, path, URL, or VCS
    source, so the dependency cannot resolve for a consumer.
    """
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(
            isinstance(value.get(key), str) and value.get(key).strip()
            for key in ("version", "path", "url", "git")
        )
    return False


def _pyproject_runtime_dependencies(module: Module) -> dict[str, bool]:
    """
    Map a pyproject's runtime dependency names to usable-spec status.

    A module without a readable, well-formed ``pyproject.toml`` returns an
    empty mapping: rule 11 and rule 18 report the missing or malformed file,
    so rule 39 does not repeat the diagnosis, while the manifest-side checks
    still fail closed.
    """
    text = module.root_files.get("pyproject.toml")
    if not text:
        return {}
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}
    poetry = data.get("tool", {}).get("poetry", {})
    dependencies = poetry.get("dependencies", {}) if isinstance(poetry, dict) else {}
    if not isinstance(dependencies, dict):
        return {}
    return {
        name.lower(): _dependency_value_is_usable(value)
        for name, value in dependencies.items()
        if name.lower() not in BASE_RUNTIME_DEPENDENCY_NAMES
    }


def _required_module_findings(module: Module, known: set[str]) -> list[str]:
    """Return rule 39's findings for the manifest's required_modules clause."""
    violations: list[str] = []
    manifest = module.manifest
    if "implies" in manifest:
        violations.append(f"rule 39: {module.name}: retired implies key present")
    if "required_modules" not in manifest:
        violations.append(f"rule 39: {module.name}: manifest is missing required_modules")
    else:
        required = manifest["required_modules"]
        if not isinstance(required, list):
            violations.append(f"rule 39: {module.name}: required_modules must be a list")
        else:
            for entry in required:
                if not isinstance(entry, str) or not SNAKE_CASE.match(entry):
                    violations.append(
                        f"rule 39: {module.name}: required module {entry!r} is not a bare name"
                    )
                elif entry not in known:
                    violations.append(f"rule 39: {module.name}: unknown required module {entry!r}")
    return violations


def _dependency_declaration_findings(module: Module) -> list[str]:
    """Return rule 39's findings for the manifest dependencies and their specs."""
    violations: list[str] = []
    manifest = module.manifest
    if "dependencies" not in manifest:
        violations.append(f"rule 39: {module.name}: manifest is missing dependencies")
        return violations
    declared = manifest["dependencies"]
    if not isinstance(declared, list):
        violations.append(f"rule 39: {module.name}: dependencies must be a list")
        return violations
    declared_names: set[str] = set()
    for entry in declared:
        if not isinstance(entry, str) or DEPENDENCY_NAME_PATTERN.match(entry) is None:
            violations.append(
                f"rule 39: {module.name}: dependency {entry!r} is not a bare package "
                "name (the spec lives in pyproject.toml)"
            )
            continue
        declared_names.add(entry.lower())
    if CORE_DEPENDENCY_NAME not in declared_names:
        violations.append(
            f"rule 39: {module.name}: manifest dependencies do not declare {CORE_DEPENDENCY_NAME}"
        )
    runtime = _pyproject_runtime_dependencies(module)
    for name in sorted(declared_names - runtime.keys()):
        violations.append(
            f"rule 39: {module.name}: dependency {name!r} has no spec in pyproject.toml"
        )
    for name in sorted(name for name in declared_names if name in runtime and not runtime[name]):
        violations.append(
            f"rule 39: {module.name}: dependency {name!r} has no usable spec in pyproject.toml"
        )
    return violations
