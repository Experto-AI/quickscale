"""Manifest-backed module discovery for QuickScale.

Replaces the previous purely static module catalog with filesystem-backed
discovery that enumerates shipped modules by scanning for valid
``module.yml`` files under the repository's ``quickscale_modules/``
workspace.

Discovery reports the filesystem observation for every module directory:
``ACTIVE`` when its manifest is present, ``INCOMPLETE`` when its manifest is
missing, and ``ABSENT`` when an expected directory is missing.  Consumers
decide which observations are valid for their operation.

This module is the canonical seam where later phases can add richer
manifest-derived metadata (readiness flags, version constraints, etc.)
without altering the core discovery contract.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
from typing import Final

import importlib.resources as _resources


class ImproperlyConfigured(Exception):
    """Raised when QuickScale is improperly configured.

    Replaces Django's ``django.core.exceptions.ImproperlyConfigured`` as the
    canonical configuration-failure exception for QuickScale's shared contract
    layer.  Callers outside Django contexts should import this exception from
    this module rather than from ``django.core.exceptions``.
    """


#: The number of source modules in the shipped contract.  The inventory is
#: discovered from manifests at runtime, while this count keeps additions and
#: removals fail-hard until the shipped contract is deliberately updated.
AUTHORITATIVE_MODULE_COUNT: Final[int] = 12

#: Human-readable reason template for placeholder rejection.
_PLACEHOLDER_REASON_TEMPLATE: Final[str] = (
    "Module '{name}' remains placeholder inventory only and is not a "
    "public-ready QuickScale module yet. "
    "{display_name} remains excluded from public quickscale plan, "
    "quickscale.yml, quickscale apply, and quickscale status workflows until "
    "it ships."
)

# ---------------------------------------------------------------------------
# Resolution provenance
# ---------------------------------------------------------------------------


class ModuleResolutionSource(Enum):
    """Identifies which module resolution source is currently active.

    Resolution follows a fixed precedence:

    * ``OVERRIDE`` — a runtime override has been set via
      :func:`set_modules_base_path` (always wins when set).
    * ``MONOREPO`` — the maintainer monorepo ``quickscale_modules/``
      directory exists.  This is the default for development and CI.
    * ``BUNDLED`` — no override or monorepo path is available, but the
      installed ``quickscale_core`` package contains bundled manifests.
      Source-required operations (``get_modules_base_path``,
      ``discover_shipped_module_paths``) **fail** in this state —
      callers must use :func:`discover_bundled_module_names` instead.

    Call :func:`get_resolution_source` to query the active source.
    """

    OVERRIDE = "override"
    MONOREPO = "monorepo"
    BUNDLED = "bundled"


class ModulePresenceState(Enum):
    """Filesystem presence observed for one declared or discovered module."""

    ABSENT = "absent"
    ACTIVE = "active"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class ModulePresenceRecord:
    """Immutable observation of one module directory and its manifest state."""

    name: str
    state: ModulePresenceState
    path: Path | None

    @property
    def module_path(self) -> Path | None:
        """Return the observed module directory, when it exists."""
        return self.path

    @property
    def manifest_path(self) -> Path | None:
        """Return the observed manifest path, when the directory exists."""
        return self.path / "module.yml" if self.path is not None else None


# ---------------------------------------------------------------------------
# Configurable modules base path
# ---------------------------------------------------------------------------

#: Runtime-overridable path to the modules workspace.  When set to a
#: non-``None`` value, all manifest loading and discovery routes through
#: this path instead of the default maintainer-monorepo layout
#: (``quickscale_modules/`` at the repository root).
_modules_base_path: Path | None = None


def set_modules_base_path(path: str | Path | None) -> None:
    """Override the modules base path for packaged/embedded-project contexts.

    Call this once at application startup to point manifest discovery at
    the correct location for the current runtime layout (installed package
    data directory, embedded project workspace, etc.).

    Args:
        path: Absolute path to the directory containing module
            subdirectories (each with a ``module.yml``).  Pass ``None`` to
            clear any previous override (restoring the monorepo default
            or ``ImproperlyConfigured`` on the next call to
            :func:`get_modules_base_path`).
    """
    global _modules_base_path
    _modules_base_path = Path(path) if path is not None else None


def get_modules_base_path() -> Path:
    """Return the modules base path, with runtime override support.

    When :func:`set_modules_base_path` has been called, returns the
    overridden path.  Otherwise resolves the maintainer-monorepo
    ``quickscale_modules/`` directory relative to this file's location
    in the package tree::

        quickscale_core/src/quickscale_core/contracts/module_discovery.py
        parents[4] -> repository root -> quickscale_modules/

    Raises ``ImproperlyConfigured`` if the monorepo path does not exist
    and no runtime override has been set.  The bundled/installed-package
    context is not a supported fallback — see AF7 decision.

    Returns:
        Absolute ``Path`` to the modules base directory.

    Raises:
        ImproperlyConfigured: If the monorepo ``quickscale_modules/``
            directory does not exist and no runtime override is set.
    """
    if _modules_base_path is not None:
        return _modules_base_path

    # Monorepo checkout (development / CI).
    monorepo_path = Path(__file__).resolve().parents[4] / "quickscale_modules"
    if monorepo_path.is_dir():
        return monorepo_path

    # Bundled/installed-package context is not a supported fallback
    # (AF7 decision — fail hard when the module source is not available).
    raise ImproperlyConfigured(
        f"Modules base path not found: expected '{monorepo_path}' to exist. "
        "Set a runtime override via set_modules_base_path() when running "
        "outside the maintainer monorepo."
    )


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def discover_module_presence(
    base_path: str | Path | None = None,
    expected_names: Iterable[str] = (),
) -> list[ModulePresenceRecord]:
    """Report manifest presence for actual directories and expected names.

    A directory containing ``module.yml`` is ``ACTIVE``.  A directory without
    that file is ``INCOMPLETE``.  An expected name without a directory is
    ``ABSENT``.  Results are sorted by module name and never parse manifests;
    parsing remains the manifest loader's responsibility.
    """
    modules_base = Path(base_path) if base_path is not None else get_modules_base_path()
    expected = set(expected_names)
    records: dict[str, ModulePresenceRecord] = {}

    if modules_base.is_dir():
        for entry in sorted(modules_base.iterdir()):
            if not entry.is_dir():
                continue
            path = entry.resolve()
            state = (
                ModulePresenceState.ACTIVE
                if (entry / "module.yml").is_file()
                else ModulePresenceState.INCOMPLETE
            )
            records[entry.name] = ModulePresenceRecord(entry.name, state, path)

    for name in expected:
        if name not in records:
            records[name] = ModulePresenceRecord(name, ModulePresenceState.ABSENT, None)

    return [records[name] for name in sorted(records)]


def _declared_module_names() -> tuple[str, ...]:
    """Return catalog names without creating a module-discovery import cycle."""
    try:
        from quickscale_core.contracts.module_catalog import MODULE_CATALOG
    except ModuleNotFoundError as exc:
        # The standalone discovery shim is also used by hermetic release
        # tooling, which supplies only this contract module and fake manifests.
        if exc.name != "quickscale_core.contracts.module_catalog":
            raise
        return ()

    return tuple(entry.name for entry in MODULE_CATALOG)


def _declared_placeholder_names() -> frozenset[str]:
    """Return placeholder names from the catalog when the catalog is present."""
    try:
        from quickscale_core.contracts.module_catalog import MODULE_CATALOG
    except ModuleNotFoundError as exc:
        if exc.name != "quickscale_core.contracts.module_catalog":
            raise
        return frozenset()
    return frozenset(entry.name for entry in MODULE_CATALOG if entry.placeholder)


def _presence_records_for_projection(
    base_path: str | Path | None = None,
) -> list[ModulePresenceRecord]:
    """Return observations and reject unsafe projection inputs."""
    records = discover_module_presence(
        base_path=base_path,
        expected_names=_declared_module_names(),
    )
    placeholder_names = _declared_placeholder_names()
    invalid: list[str] = []
    for record in records:
        if (
            record.state is ModulePresenceState.ACTIVE
            and record.name in placeholder_names
        ):
            invalid.append(f"{record.name} is a declared placeholder")
        elif (
            record.state is ModulePresenceState.INCOMPLETE
            and record.name not in placeholder_names
        ):
            invalid.append(f"{record.name} is missing module.yml")
    if invalid:
        raise ImproperlyConfigured(
            "Module presence is incomplete or contains a placeholder: "
            + "; ".join(invalid)
        )
    return records


def discover_shipped_module_names() -> list[str]:
    """Return alphabetically sorted names of shipped modules discovered by
    scanning the configured modules base path for ``*/module.yml`` files.

    Only active directories are included.  Declared placeholders remain
    observable as incomplete records but are excluded from this projection.
    Undeclared incomplete directories fail closed instead of being silently
    dropped.  Returns an empty list when the workspace contains no manifests.

    The modules base path is configurable at runtime via
    :func:`set_modules_base_path` — see :func:`get_modules_base_path`.

    Raises ``ImproperlyConfigured`` if no modules base path can be
    determined (see :func:`get_modules_base_path`).

    Returns:
        Sorted list of shipped module names.
    """
    return [
        record.name
        for record in _presence_records_for_projection()
        if record.state is ModulePresenceState.ACTIVE
    ]


def validate_active_module_subset(
    active_names: Iterable[str], release_names: Iterable[str]
) -> None:
    """Validate an active module set against the twelve-module release set.

    Generated projects may legitimately provide a subset, but every active
    name must belong to the release inventory.  The release inventory itself
    must retain its authoritative count and uniqueness.
    """
    active = list(active_names)
    release = list(release_names)
    if len(release) != AUTHORITATIVE_MODULE_COUNT or len(set(release)) != len(release):
        raise ImproperlyConfigured(
            "Module inventory count drift: expected "
            f"{AUTHORITATIVE_MODULE_COUNT} unique release modules, found "
            f"{len(release)}"
        )
    if len(set(active)) != len(active):
        raise ImproperlyConfigured(
            "Active module subset contains duplicate module names: "
            + ", ".join(sorted(name for name in set(active) if active.count(name) > 1))
        )
    unknown = sorted(set(active) - set(release))
    if unknown:
        raise ImproperlyConfigured(
            "Active module subset contains names outside the release inventory: "
            + ", ".join(unknown)
        )


def authoritative_module_names() -> list[str]:
    """Return the fail-hard inventory of shipped module names.

    Source manifests are preferred in the maintainer monorepo; installed and
    generated contexts resolve the same inventory from bundled manifests.
    Placeholder names are never public modules, even if a malformed or future
    repository state gives one a manifest.  A count mismatch is also rejected
    so consumers cannot silently operate on an accidentally changed release
    inventory.

    Raises:
        ImproperlyConfigured: If a placeholder is discovered or the number of
            discovered modules differs from :data:`AUTHORITATIVE_MODULE_COUNT`.
    """
    if _modules_base_path is not None:
        names = discover_shipped_module_names()
        release_names = discover_bundled_module_names()
        validate_active_module_subset(names, release_names)
        if names != release_names:
            raise ImproperlyConfigured(
                "Authoritative module inventory is incomplete: active override "
                "does not contain the complete release inventory"
            )
        return names

    try:
        get_modules_base_path()
    except ImproperlyConfigured:
        names = discover_bundled_module_names()
    else:
        names = discover_shipped_module_names()
    validate_active_module_subset(names, names)
    return names


def discover_shipped_module_paths() -> dict[str, Path]:
    """Return a mapping of shipped module names to their absolute directory
    paths, discovered by scanning ``*/module.yml`` under the configured
    modules base path.

    The modules base path is configurable at runtime via
    :func:`set_modules_base_path` — see :func:`get_modules_base_path`.

    Raises ``ImproperlyConfigured`` if no modules base path can be
    determined (see :func:`get_modules_base_path`).

    Returns:
        Dict mapping module name to its absolute ``Path``.  Empty when the
        workspace contains no valid manifests.
    """
    return {
        record.name: record.path
        for record in _presence_records_for_projection()
        if record.state is ModulePresenceState.ACTIVE and record.path is not None
    }


def is_placeholder_module(name: str) -> bool:
    """Return ``True`` when *name* is a known placeholder module that should
    be rejected outside the discovered catalog surface.

    This is the fail-closed check for explicit placeholder names like ``teams``
    that exist as repository directories but do **not** carry a ``module.yml``.

    Args:
        name: The module name to check.

    Returns:
        ``True`` if the name is a known placeholder.
    """
    from quickscale_core.contracts.module_catalog import get_module_entry

    entry = get_module_entry(name)
    return entry is not None and entry.placeholder


def get_placeholder_rejection_reason(name: str) -> str | None:
    """Return an actionable rejection message for a known placeholder module,
    or ``None`` if the name is not a known placeholder.

    Args:
        name: The module name to check.

    Returns:
        A human-readable rejection string, or ``None``.
    """
    if not is_placeholder_module(name):
        return None
    display_name = name.replace("_", " ").title()
    return _PLACEHOLDER_REASON_TEMPLATE.format(
        name=name,
        display_name=display_name,
    )


# ---------------------------------------------------------------------------
# Resolution source observability
# ---------------------------------------------------------------------------


def get_resolution_source() -> ModuleResolutionSource:
    """Return the current active module resolution source.

    Follows the fixed precedence defined in :class:`ModuleResolutionSource`:

    1.  Runtime override (via :func:`set_modules_base_path`) — returns
        ``OVERRIDE``.
    2.  Maintainer monorepo ``quickscale_modules/`` — returns ``MONOREPO``.
    3.  Bundled manifests within the installed ``quickscale_core`` package
        — returns ``BUNDLED`` (only when the bundled directory exists and
        contains at least one valid ``module.yml``).
    4.  No source available — raises :exc:`ImproperlyConfigured`.

    Returns:
        The active :class:`ModuleResolutionSource`.

    Raises:
        ImproperlyConfigured: If no module resolution source can be
            determined.
    """
    if _modules_base_path is not None:
        return ModuleResolutionSource.OVERRIDE

    monorepo_path = Path(__file__).resolve().parents[4] / "quickscale_modules"
    if monorepo_path.is_dir():
        return ModuleResolutionSource.MONOREPO

    # Check whether bundled manifests are available and usable.
    try:
        ref = _resources.files("quickscale_core") / "data" / "manifests"
    except Exception as exc:
        raise ImproperlyConfigured(
            "No module resolution source available. "
            "Set a runtime override via set_modules_base_path(), run from the "
            "maintainer monorepo, or install quickscale_core with bundled module "
            "data."
        ) from exc

    if not ref.is_dir():
        raise ImproperlyConfigured(
            "No module resolution source available. "
            "Set a runtime override via set_modules_base_path(), run from the "
            "maintainer monorepo, or install quickscale_core with bundled module "
            "data."
        )

    # Verify bundled manifests are non-empty (at least one valid module.yml).
    try:
        has_valid = any(
            entry.is_dir() and (entry / "module.yml").is_file()
            for entry in ref.iterdir()
        )
    except Exception as exc:
        raise ImproperlyConfigured(
            f"Failed to read bundled manifests directory '{ref}': {exc}"
        ) from exc

    if not has_valid:
        raise ImproperlyConfigured(
            f"No valid module.yml files found in bundled manifests "
            f"directory '{ref}'. The quickscale_core installation may "
            "be corrupted."
        )

    return ModuleResolutionSource.BUNDLED


# ---------------------------------------------------------------------------
# Bundled manifest access
# ---------------------------------------------------------------------------


def get_bundled_manifests_path() -> Path:
    """Return the path to the bundled module manifests directory.

    Uses ``importlib.resources`` to locate ``data/manifests`` within the
    installed ``quickscale_core`` package.  The returned path is valid for
    both installed wheels and filesystem development (editable) installs.

    Raises:
        ImproperlyConfigured: If the bundled manifests directory is absent
            or cannot be read.
    """
    try:
        ref = _resources.files("quickscale_core") / "data" / "manifests"
    except Exception as exc:
        raise ImproperlyConfigured(
            "Bundled manifests directory not found in installed package. "
            "Ensure quickscale_core is properly installed."
        ) from exc

    if not ref.is_dir():
        raise ImproperlyConfigured(
            f"Bundled manifests directory '{ref}' not found. "
            "The quickscale_core installation may be corrupted."
        )

    return Path(str(ref))


def resolve_manifest_base_path() -> Path:
    """Return the base directory to read shipped module manifests from.

    Prefers the maintainer monorepo's ``quickscale_modules/`` workspace and
    falls back to the manifest snapshots bundled inside the ``quickscale_core``
    wheel when that workspace is absent (installed-wheel context).  This is the
    AF7 discovery contract established by SA109/SA113/SA111a, single-homed here
    so every manifest-reading call site resolves identically.

    Fail-hard is preserved: when neither source resolves, ``ImproperlyConfigured``
    propagates from :func:`get_bundled_manifests_path` rather than yielding a
    silently empty or defaulted manifest.

    Note this resolves *manifest* reads only.  Source-required operations
    (:func:`get_modules_base_path`, :func:`discover_shipped_module_paths`, and
    ``load_module_manifest``) intentionally remain fail-hard against the source
    tree.  ``refresh_managed_adapters`` may consult bundled *names* to validate a
    generated subset, but it loads adapter source only from the active base.

    Raises:
        ImproperlyConfigured: If neither the source workspace nor the bundled
            manifests directory is available.
    """
    try:
        return get_modules_base_path()
    except ImproperlyConfigured:
        return get_bundled_manifests_path()


def discover_bundled_module_names() -> list[str]:
    """Return alphabetically sorted names of modules from the bundled
    manifests within the installed ``quickscale_core`` package.

    Uses ``importlib.resources`` to read the bundled manifest directory.
    This is the primary inventory source for installed-wheel contexts where
    no monorepo ``quickscale_modules/`` directory is available.

    Raises:
        ImproperlyConfigured: If the bundled manifests directory is absent,
            empty, unreadable, or contains no valid ``module.yml`` files.

    Returns:
        Sorted list of module names discovered from bundled manifests.
    """
    manifests_path = get_bundled_manifests_path()

    discovered: list[str] = []
    try:
        for entry in sorted(manifests_path.iterdir()):
            if not entry.is_dir():
                continue
            manifest_file = entry / "module.yml"
            if manifest_file.is_file():
                discovered.append(entry.name)
    except Exception as exc:
        raise ImproperlyConfigured(
            f"Failed to read bundled manifests directory '{manifests_path}': {exc}"
        ) from exc

    if not discovered:
        raise ImproperlyConfigured(
            "No valid module.yml files found in bundled manifests directory "
            f"'{manifests_path}'. The quickscale_core installation may be "
            "corrupted."
        )

    return discovered


__all__ = [
    "AUTHORITATIVE_MODULE_COUNT",
    "ModulePresenceRecord",
    "ModulePresenceState",
    "ModuleResolutionSource",
    "authoritative_module_names",
    "discover_bundled_module_names",
    "discover_module_presence",
    "discover_shipped_module_names",
    "discover_shipped_module_paths",
    "get_bundled_manifests_path",
    "get_modules_base_path",
    "get_placeholder_rejection_reason",
    "get_resolution_source",
    "is_placeholder_module",
    "set_modules_base_path",
    "validate_active_module_subset",
]


def _main(argv: list[str] | None = None) -> int:
    """Expose a hermetic command-line shim for repository tooling."""
    parser = argparse.ArgumentParser(prog="module_discovery.py")
    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="print the authoritative source module inventory, one per line",
    )
    args = parser.parse_args(argv)
    if not args.list_modules:
        parser.error("the --list-modules option is required")
    try:
        print("\n".join(authoritative_module_names()))
    except ImproperlyConfigured as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
