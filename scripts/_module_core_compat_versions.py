"""
Version and pyproject/manifest parsing for the SA267(d) split.

The lockstep-pin derivation, PEP 440 minimum extraction, module.yml and
pyproject reading, and the management-command discovery live here.  The facade
and the probe sibling import these names from this defining sibling, never
through the facade (decisions.md, Split-Facade Seams).  Behavior is unchanged
from the pre-split module.
"""

from __future__ import annotations

import re
import tomllib  # Python 3.11+ stdlib
from pathlib import Path
from typing import Final, cast

CORE_DEP_NAME: Final[str] = "quickscale-core"

# Regex to extract the minimum version from a pep-440-style specifier.
# Handles shapes like: >=0.86.0, >=0.86.0,<0.87.0, >=0.86.0,!=0.86.1
_MIN_VERSION_PATTERN: Final[re.Pattern[str]] = re.compile(r">=\s*(?P<min_ver>\d+[.]\d+[.]\d+)")


def _read_version_file(repo_root: Path) -> str:
    """Return the trimmed version string from the repository ``VERSION`` file."""
    version_file = repo_root / "VERSION"
    if not version_file.is_file():
        raise SystemExit(f"VERSION file not found: {version_file}")
    raw = version_file.read_text(encoding="utf-8")
    cleaned = raw.replace("\r", "").strip()
    if not cleaned:
        raise SystemExit(f"VERSION file is empty: {version_file}")
    return cleaned


def _parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse ``'0.86.0'`` → ``(0, 86, 0)``."""
    parts = version_str.strip().split(".", maxsplit=2)
    return tuple(int(p) for p in parts)


def _extract_min_core_version(dep_spec: str) -> str | None:
    """
    Extract the minimum version from a PEP 440 dependency specifier.

    Examples::

        >>> _extract_min_core_version(">=0.86.0")
        '0.86.0'
        >>> _extract_min_core_version(">=0.86.0,<0.87.0")
        '0.86.0'
        >>> _extract_min_core_version("^0.86")
        None  # not PEP 440; the repo uses PEP 440 style
    """
    match = _MIN_VERSION_PATTERN.search(dep_spec)
    if match:
        return match.group("min_ver")
    return None


def _expected_core_spec(version_str: str) -> str:
    """
    Return the lockstep specifier a module must declare for *version_str*.

    The rule (release_gates_policy.md §Module Version Lockstep) is mechanical: the
    floor is the release being published, the ceiling is the next minor.

        >>> _expected_core_spec("0.88.0")
        '>=0.88.0,<0.89.0'
    """
    major, minor, *_ = version_str.split(".")
    return f">={version_str},<{major}.{int(minor) + 1}.0"


def _declared_core_spec(dep_spec: str) -> str:
    """Strip the distribution name off a dependency entry, leaving the specifier."""
    return dep_spec[len(CORE_DEP_NAME) :].strip()


def _parse_module_yml(module_yml: Path) -> dict:
    """Parse a ``module.yml`` file, returning the raw dict."""
    import yaml  # pyyaml is a core dependency

    with module_yml.open(encoding="utf-8") as fh:
        return cast(dict, yaml.safe_load(fh))


def _get_core_dep_spec(data: dict) -> str | None:
    """
    Return the ``quickscale-core`` dependency entry from a parsed module.yml.

    Returns ``None`` if the module doesn't depend on core.  Rule 39 makes the
    entry a bare name; a version suffix here is refused by the caller.
    """
    deps = data.get("dependencies", [])
    if not isinstance(deps, list):
        return None
    for dep in deps:
        if not isinstance(dep, str):
            continue
        # Match both "quickscale-core" and a legacy "quickscale-core>=..." form
        if dep.startswith(CORE_DEP_NAME) or dep.startswith(f"{CORE_DEP_NAME} "):
            return dep
    return None


def _get_pyproject_core_dep(mod_dir: Path) -> object | None:
    """
    Return the module pyproject's ``quickscale-core`` dependency value.

    The value is the monorepo path table or a version string; ``None`` when
    the file or the dependency is absent.  A malformed ``pyproject.toml``
    raises :class:`tomllib.TOMLDecodeError` for the caller to report.
    """
    pyproject = mod_dir / "pyproject.toml"
    if not pyproject.is_file():
        return None
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    poetry = data.get("tool", {}).get("poetry", {})
    deps = poetry.get("dependencies", {}) if isinstance(poetry, dict) else {}
    if not isinstance(deps, dict):
        return None
    return deps.get(CORE_DEP_NAME)


def _get_module_package_name(module_dir: Path) -> str | None:
    """
    Extract the importable package name from a module's ``pyproject.toml``.

    Looks at ``[tool.poetry.packages]`` and returns the ``include`` value
    of the first entry.  Returns ``None`` if the file is absent or the
    information cannot be extracted.
    """
    pyproject = module_dir / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError:
        return None
    packages = data.get("tool", {}).get("poetry", {}).get("packages", [])
    if not isinstance(packages, list):
        return None
    for entry in packages:
        if isinstance(entry, dict):
            name = entry.get("include")
            if isinstance(name, str) and name:
                return name
    return None


def _poetry_spec_to_pep440(spec: str) -> str:
    """
    Convert a Poetry version specifier to PEP 440 form for ``pip install``.

    Handles the forms found in this repository:

    * ``^X.Y.Z`` → ``>=X.Y.Z,<X+1.0.0`` (X >= 1) or ``>=0.Y.Z,<0.Y+1.0`` (X == 0)
    * ``^X.Y``   → ``>=X.Y,<X+1.0`` (X >= 1) or ``>=0.Y,<0.Y+1`` (X == 0)
    * ``~X.Y.Z`` → ``>=X.Y.Z,<X.Y+1.0``
    * Everything else is passed through as-is (assumed PEP 440 compatible).

    This is intentionally limited to the forms present in the QuickScale
    monorepo module dependencies.  It is not a general Poetry-to-PEP 440
    converter.
    """
    # Caret: ^X.Y.Z or ^X.Y
    caret_match = re.match(r"^\^(\d+)\.(\d+)(?:\.(\d+))?$", spec)
    if caret_match:
        major = int(caret_match.group(1))
        minor = int(caret_match.group(2))
        patch = caret_match.group(3)
        if major >= 1:
            upper_major = major + 1
            lower = f"{major}.{minor}" if patch is None else f"{major}.{minor}.{patch}"
            upper = f"{upper_major}.0.0"
        else:
            # Pre-1.0: bounded by minor version (Poetry's convention)
            upper_minor = minor + 1
            lower = f"0.{minor}" if patch is None else f"0.{minor}.{patch}"
            upper = f"0.{upper_minor}.0"
        return f">={lower},<{upper}"

    # Tilde: ~X.Y.Z
    tilde_match = re.match(r"^~(\d+)\.(\d+)\.(\d+)$", spec)
    if tilde_match:
        major = int(tilde_match.group(1))
        minor = int(tilde_match.group(2))
        patch = tilde_match.group(3)
        upper_minor = minor + 1
        return f">={major}.{minor}.{patch},<{major}.{upper_minor}.0"

    # Plain wildcard: X.Y.* or just a bare version
    # Pass through unchanged (pip may handle it or fail with a clear error)
    return spec


def _get_module_non_core_deps(module_dir: Path) -> list[str]:
    """
    Return non-core, installable dependency specs from a module's pyproject.

    Excludes ``python``, ``quickscale-core``, and any dependency entry that
    uses a path (editable / develop) form.  The returned list uses PEP 440
    specifiers suitable for passing to ``pip install``.
    """
    pyproject = module_dir / "pyproject.toml"
    if not pyproject.is_file():
        return []
    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError:
        return []

    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    if not isinstance(poetry_deps, dict):
        return []

    specs: list[str] = []
    for dep_name, dep_spec in poetry_deps.items():
        if dep_name in ("python", "quickscale-core"):
            continue
        if isinstance(dep_spec, str):
            converted = _poetry_spec_to_pep440(dep_spec)
            specs.append(f"{dep_name}{converted}")
        elif isinstance(dep_spec, dict):
            # Skip path-only deps (editable / develop entries);
            # include version-constrained entries.
            if "path" in dep_spec and "version" not in dep_spec:
                continue
            version = dep_spec.get("version", "")
            if version:
                converted = _poetry_spec_to_pep440(version)
                specs.append(f"{dep_name}{converted}")
    return specs


def _get_management_command_modules(package_name: str, src_dir: Path) -> list[str]:
    """
    Return dotted import paths for management command modules in *package_name*.

    Scans ``src_dir/<package_name>/management/commands/*.py`` (skipping
    ``__init__.py`` and underscore-prefixed support modules, the way Django's
    own command discovery does) and returns fully-qualified dotted paths
    suitable for ``importlib.import_module`` or ``__import__``.

    Returns an empty list when the directory does not exist or no commands
    are found.
    """
    pkg_dir = src_dir / package_name
    commands_dir = pkg_dir / "management" / "commands"
    if not commands_dir.is_dir():
        return []
    modules: list[str] = []
    for cmd_file in sorted(commands_dir.iterdir()):
        if cmd_file.suffix == ".py" and not cmd_file.stem.startswith("_"):
            modules.append(f"{package_name}.management.commands.{cmd_file.stem}")
    return modules
