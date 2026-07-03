"""Required-module version constraint parsing and validation.

Supports inline version floors in ``required_modules`` entries
(e.g. ``"orgs>=0.86.0"``) so modules can declare a minimum
version of another first-party module they depend on.  The
helper avoids introducing the ``packaging`` library — version
comparison uses simple numeric-component comparison.
"""

from __future__ import annotations

import re
from typing import Pattern

from quickscale_core.manifest.loader import ManifestError
from quickscale_core.manifest.schema import ModuleManifest

#: Pattern to match a required_modules entry.
#: Group 1: module name (starts with alpha, then alphanumeric / hyphen / underscore).
#: Group 2: the full ``>=X.Y.Z`` spec (including operator).
#: Group 3: the version part after ``>=`` (dotted digits).
_REQUIRED_MODULE_ENTRY_RE: Pattern[str] = re.compile(
    r"^([a-zA-Z][a-zA-Z0-9_-]*)"
    r"(>=(\d+(?:\.\d+)*))?"
    r"$"
)

#: Pattern to extract numeric components from a dotted version string.
_VERSION_COMPONENT_RE: Pattern[str] = re.compile(r"(\d+)")


def parse_required_module_entry(entry: str) -> tuple[str, str | None]:
    """Parse a single ``required_modules`` list entry.

    Args:
        entry: A string like ``"orgs"`` or ``"orgs>=0.86.0"``.

    Returns:
        A tuple ``(module_name, min_version)`` where *min_version* is
        the raw dotted minimum-version string (e.g. ``"0.86.0"``) or
        ``None`` when no version constraint is present.

    Raises:
        ManifestError: If the entry is empty or malformed.
    """
    stripped = entry.strip()
    if not stripped:
        raise ManifestError("required_modules entry must not be empty")

    match = _REQUIRED_MODULE_ENTRY_RE.match(stripped)
    if not match:
        raise ManifestError(
            f"Invalid required_modules entry: '{entry}'. "
            "Expected '<module_name>' or '<module_name>>=<version>'"
        )

    module_name = match.group(1)
    min_version = match.group(3)  # Group 3 is the version after ``>=``.
    return module_name, min_version


def _normalize_version(version: str) -> str:
    """Strip a leading ``v`` prefix for consistent comparison."""
    normalized = version.strip()
    if (
        normalized[:1].lower() == "v"
        and len(normalized) > 1
        and normalized[1].isdigit()
    ):
        return normalized[1:]
    return normalized


def _parse_version_parts(version: str) -> tuple[int, ...]:
    """Parse a dotted version string into a tuple of numeric components.

    Args:
        version: A string like ``"0.86.0"`` or ``"v0.86.0"``.

    Returns:
        A tuple of integers for comparison, e.g. ``(0, 86, 0)``.

    Raises:
        ValueError: If the version string contains no numeric components.
    """
    cleaned = _normalize_version(version)
    parts = tuple(int(m) for m in _VERSION_COMPONENT_RE.findall(cleaned) if m)
    if not parts:
        raise ValueError(f"Version string has no numeric components: '{version}'")
    return parts


def check_required_module_versions(
    manifests: dict[str, ModuleManifest],
) -> None:
    """Validate that all required-module version constraints are satisfied.

    For each manifest in *manifests*, inspect every entry in its
    ``required_modules`` list.  If an entry carries a ``>=`` version
    floor, look up the target module in *manifests* and compare its
    installed version against the floor.  Fail closed on any violation
    or malformed entry.

    Args:
        manifests: A dict mapping module name to its loaded
            :class:`~quickscale_core.manifest.schema.ModuleManifest`.
            Must include every module that is referenced in any
            ``required_modules`` entry with a version constraint.

    Raises:
        ManifestError: If a version constraint is violated, a required
            module is missing from *manifests*, or an entry is malformed.
    """
    for module_name, manifest in manifests.items():
        for entry in manifest.required_modules:
            required_name, min_version = parse_required_module_entry(entry)

            if min_version is None:
                # No version floor — nothing to check for this entry.
                continue

            # Look up the required module's installed manifest.
            required_manifest = manifests.get(required_name)
            if required_manifest is None:
                raise ManifestError(
                    f"Module '{module_name}' requires '{required_name}' "
                    f"which is not installed",
                    module_name,
                )

            installed_version_str = required_manifest.version
            if not installed_version_str:
                raise ManifestError(
                    f"Module '{required_name}' has no version declared "
                    f"in its manifest (required by '{module_name}' "
                    f"as '{entry}')",
                    module_name,
                )

            try:
                installed_parts = _parse_version_parts(installed_version_str)
                min_parts = _parse_version_parts(min_version)
            except ValueError as exc:
                raise ManifestError(
                    f"Cannot compare versions for required module "
                    f"'{required_name}': {exc}",
                    module_name,
                )

            # Pad the shorter tuple with zeros for fair comparison
            # (e.g. "0.86" vs "0.86.0").
            max_len = max(len(installed_parts), len(min_parts))
            installed_parts = installed_parts + (0,) * (max_len - len(installed_parts))
            min_parts = min_parts + (0,) * (max_len - len(min_parts))

            if installed_parts < min_parts:
                raise ManifestError(
                    f"Module '{module_name}' requires '{required_name}' "
                    f"version >= {min_version}, but installed version is "
                    f"{installed_version_str}",
                    module_name,
                )
