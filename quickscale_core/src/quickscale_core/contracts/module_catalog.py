"""Module catalog metadata for QuickScale.

This module is part of the shared contract surface owned by ``quickscale_core``
so that both the CLI and the schema layer can consume module catalog metadata
without depending on the CLI.

Starting with T2.3 Phase 2, the module catalog is supplemented by
manifest-backed discovery via :mod:`module_discovery`.  The manifest discovery
provides the authoritative list of shipped modules by scanning
``quickscale_modules/*/module.yml``, and a discovered entry's description is
read from that module's manifest — the manifest is a module's one home for
facts about itself (Module Conventions rule 37).  The static catalog declares
the shipped-contract inventory and its readiness flags only.

A module directory without a ``module.yml`` is never a shipped module:
source discovery rejects it fail-closed, while bundled discovery skips it.
"""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleCatalogEntry:
    """Metadata describing a module's availability and UX label.

    ``description`` is carried by discovered entries and read from the
    module's ``module.yml``; the static catalog declares only names and
    readiness, so its entries leave the description empty.
    """

    name: str
    description: str
    ready: bool
    experimental: bool = False


#: The shipped-contract inventory: every module name the contract declares,
#: with its readiness flag.  Descriptions are deliberately absent — a
#: module's ``module.yml`` is their one home (Module Conventions rule 37).
#:
#: Rule 37 names this declared release inventory as its allowed exception.
#: :mod:`module_discovery` refuses a declared module directory that is
#: missing, a consistency test keeps the declaration equal to discovery in
#: the shipped state, and ``AUTHORITATIVE_MODULE_COUNT`` keeps an addition or
#: removal fail-hard until the shipped contract — this inventory, the count,
#: and the manifests — is deliberately updated together.
MODULE_CATALOG: tuple[ModuleCatalogEntry, ...] = (
    ModuleCatalogEntry(name="auth", description="", ready=True),
    ModuleCatalogEntry(name="blog", description="", ready=True),
    ModuleCatalogEntry(name="listings", description="", ready=True),
    ModuleCatalogEntry(name="crm", description="", ready=True),
    ModuleCatalogEntry(name="forms", description="", ready=True),
    ModuleCatalogEntry(name="storage", description="", ready=True),
    ModuleCatalogEntry(name="backups", description="", ready=True),
    ModuleCatalogEntry(name="notifications", description="", ready=True),
    ModuleCatalogEntry(name="analytics", description="", ready=True),
    ModuleCatalogEntry(name="social", description="", ready=True),
    ModuleCatalogEntry(name="billing", description="", ready=True),
    ModuleCatalogEntry(name="orgs", description="", ready=True),
)


# ---------------------------------------------------------------------------
# Manifest description resolution
# ---------------------------------------------------------------------------


def _manifest_descriptions(names: Iterable[str]) -> dict[str, str]:
    """Return each named module's description, read from its ``module.yml``.

    The manifest is the one home of a module's description (Module Conventions
    rule 37).  Manifests are read from the maintainer-monorepo workspace when
    it exists and from the manifests bundled inside the installed
    ``quickscale_core`` package otherwise, the same precedence source
    discovery uses; a manifest that cannot be read fails hard.
    """
    from quickscale_core.contracts.module_discovery import resolve_manifest_base_path
    from quickscale_core.manifest.loader import load_manifest_from_path

    base_path = resolve_manifest_base_path()
    descriptions: dict[str, str] = {}
    for name in names:
        manifest = load_manifest_from_path(base_path / name / "module.yml")
        descriptions[name] = manifest.description
    return descriptions


def _manifest_description(module_name: str) -> str:
    """Return one module's description, read from its ``module.yml``."""
    return _manifest_descriptions([module_name])[module_name]


# ---------------------------------------------------------------------------
# Static catalog lookup
# ---------------------------------------------------------------------------


def get_module_entry(module_name: str) -> ModuleCatalogEntry | None:
    """Return module metadata for a declared module name.

    The declared name and readiness flag come from the static catalog; the
    description is read from the module's ``module.yml``, its one home
    (Module Conventions rule 37).

    Args:
        module_name: The module name to look up.

    Returns:
        A :class:`ModuleCatalogEntry` if the module is declared in the static
        catalog, ``None`` otherwise.
    """
    for entry in MODULE_CATALOG:
        if entry.name == module_name:
            return ModuleCatalogEntry(
                name=entry.name,
                description=_manifest_description(entry.name),
                ready=entry.ready,
                experimental=entry.experimental,
            )
    return None


# ---------------------------------------------------------------------------
# Manifest-backed discovery (T2.3 Phase 2+)
# ---------------------------------------------------------------------------


def get_discovered_module_names() -> list[str]:
    """Return the authoritative list of shipped module names.

    Resolution follows a fixed precedence:

    1.  **Source inventory** — ``quickscale_modules/*/module.yml`` scanned
        via :func:`discover_shipped_module_names`.  This is the primary
        source when running inside the maintainer monorepo or when a
        runtime override is active.

    2.  **Bundled inventory** — manifests shipped with the installed
        ``quickscale_core`` package, discovered via
        :func:`discover_bundled_module_names`.  This is the fallback for
        installed-wheel contexts where no source workspace is available.

    3.  **Fail-hard** — raises :exc:`ImproperlyConfigured` if neither
        source nor bundled inventory can be resolved.

    A module directory without a ``module.yml`` is never a shipped module:
    source discovery fails closed on such a directory, while bundled
    discovery skips it.

    Returns:
        Sorted list of shipped module names.

    Raises:
        ImproperlyConfigured: If no module inventory is available.
    """
    from quickscale_core.contracts.module_discovery import authoritative_module_names

    return authoritative_module_names()


def get_discovered_module_entries() -> list[ModuleCatalogEntry]:
    """Return :class:`ModuleCatalogEntry` instances for every shipped module
    discovered via manifest scanning, with each description read from that
    module's ``module.yml``.

    Entries are sorted alphabetically by name.  Every discovered module is
    marked as ``ready=True`` (a valid ``module.yml`` is the readiness signal).
    Experimental and non-ready flags from the static catalog are **not**
    carried over — a discovered module is a shipped module.

    Returns:
        List of :class:`ModuleCatalogEntry` for discovered modules.
    """
    discovered_names = get_discovered_module_names()
    descriptions = _manifest_descriptions(discovered_names)

    entries: list[ModuleCatalogEntry] = []
    seen: set[str] = set()
    for name in discovered_names:
        if name in seen:
            continue
        seen.add(name)
        entries.append(
            ModuleCatalogEntry(name=name, description=descriptions[name], ready=True)
        )

    return entries


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


def find_not_ready_modules(module_names: Iterable[str]) -> list[str]:
    """Return known module names that are present but not publicly ready.

    This includes modules from the static catalog flagged as non-ready.

    Args:
        module_names: Iterable of module names to check.

    Returns:
        Sorted list of non-ready module names.
    """
    not_ready: list[str] = []
    for module_name in module_names:
        entry = get_module_entry(module_name)
        if entry is not None and not entry.ready and module_name not in not_ready:
            not_ready.append(module_name)
    return sorted(not_ready)


def get_module_readiness_reason(module_name: str) -> str | None:
    """Return an actionable readiness error for non-public-ready modules.

    Looks the module name up in the static catalog.

    Args:
        module_name: The module name to check.

    Returns:
        A human-readable reason string if the module is not ready, or
        ``None`` if the module is ready.

    Raises:
        ValueError: If the module name is not recognized.
    """
    entry = get_module_entry(module_name)
    if entry is None:
        raise ValueError(
            f"Unknown module name '{module_name}'. "
            "Expected a known QuickScale module name."
        )
    if entry.ready:
        return None

    module_display_name = module_name.replace("_", " ").title()
    return (
        f"Module '{module_name}' is not a public-ready QuickScale module yet. "
        f"{module_display_name} remains excluded from public quickscale plan, "
        "quickscale.yml, quickscale apply, and quickscale status workflows until "
        "it ships."
    )
