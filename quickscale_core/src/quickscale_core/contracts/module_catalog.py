"""Module catalog metadata for QuickScale.

This module is part of the shared contract surface owned by ``quickscale_core``
so that both the CLI and the schema layer can consume module catalog metadata
without depending on the CLI.

Starting with T2.3 Phase 2, the module catalog is supplemented by
manifest-backed discovery via :mod:`module_discovery`.  The static catalog
entries provide descriptive metadata and UX labels; the manifest discovery
provides the authoritative list of shipped modules by scanning
``quickscale_modules/*/module.yml``.

Known placeholder modules (such as ``teams``) that lack a ``module.yml`` are
**not** discovered and are instead rejected through a fail-closed path.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from quickscale_core.contracts.module_discovery import (
    discover_shipped_module_names,
    get_placeholder_rejection_reason,
    is_placeholder_module,
)


@dataclass(frozen=True)
class ModuleCatalogEntry:
    """Metadata describing a module's availability and UX label."""

    name: str
    description: str
    ready: bool
    experimental: bool = False


MODULE_CATALOG: tuple[ModuleCatalogEntry, ...] = (
    ModuleCatalogEntry(
        name="auth",
        description="Authentication with django-allauth",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="blog",
        description="Markdown-powered blog with categories and RSS",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="listings",
        description="Generic listings for marketplace verticals",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="crm",
        description="Customer Relationship Management (contacts, deals, pipeline)",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="forms",
        description="Generic form builder with admin management and React renderer",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="storage",
        description="Shared media storage infrastructure (local + S3-compatible)",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="backups",
        description="Private operational database backups with guarded restore workflows",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="notifications",
        description="Transactional email delivery with Resend and Anymail",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="analytics",
        description="PostHog website analytics with flat settings and starter-theme support",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="social",
        description="Curated social links and embeds with managed backend integration",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="billing",
        description="Stripe integration with credits-first pricing and dashboard routes",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="orgs",
        description="Organizations and multi-tenant foundations with memberships and invitations",
        ready=True,
    ),
    ModuleCatalogEntry(
        name="teams",
        description="Multi-tenancy and team management",
        ready=False,
        experimental=True,
    ),
)


# ---------------------------------------------------------------------------
# Static catalog lookup
# ---------------------------------------------------------------------------


def get_module_entry(module_name: str) -> ModuleCatalogEntry | None:
    """Return module metadata for a module name from the static catalog.

    Args:
        module_name: The module name to look up.

    Returns:
        A :class:`ModuleCatalogEntry` if the module exists in the static
        catalog, ``None`` otherwise.
    """
    for entry in MODULE_CATALOG:
        if entry.name == module_name:
            return entry
    return None


def get_module_names(*, include_experimental: bool = True) -> list[str]:
    """Return module names from the catalog.

    .. note::
       This function is kept for backward compatibility.  For the
       authoritative list of shipped modules, prefer
       :func:`get_discovered_module_names`.

    Args:
        include_experimental: If ``True`` (default), includes experimental
            (non-ready) modules in the result.

    Returns:
        Sorted list of module names from the static catalog.
    """
    entries = get_module_entries(include_experimental=include_experimental)
    return [entry.name for entry in entries]


def get_module_entries(
    *, include_experimental: bool = False
) -> list[ModuleCatalogEntry]:
    """Return catalog entries filtered by readiness/experimental visibility.

    .. note::
       This function is kept for backward compatibility.  For the
       authoritative list of shipped modules, prefer
       :func:`get_discovered_module_entries`.

    Args:
        include_experimental: If ``True``, includes experimental
            (non-ready) entries.

    Returns:
        List of :class:`ModuleCatalogEntry` instances.
    """
    if include_experimental:
        return list(MODULE_CATALOG)
    return [entry for entry in MODULE_CATALOG if entry.ready]


# ---------------------------------------------------------------------------
# Manifest-backed discovery (T2.3 Phase 2+)
# ---------------------------------------------------------------------------


def get_discovered_module_names() -> list[str]:
    """Return the authoritative list of shipped module names discovered by
    scanning ``quickscale_modules/*/module.yml``.

    This is the primary source of truth for which modules are available.
    Placeholder directories (e.g. ``teams``) without ``module.yml`` are
    excluded.  Returns an empty list when the module workspace cannot be
    read.

    Returns:
        Sorted list of shipped module names.
    """
    return discover_shipped_module_names()


def get_discovered_module_entries() -> list[ModuleCatalogEntry]:
    """Return :class:`ModuleCatalogEntry` instances for every shipped module
    discovered via manifest scanning, supplemented with descriptive metadata
    from the static catalog where available.

    Entries are sorted alphabetically by name.  Every discovered module is
    marked as ``ready=True`` (a valid ``module.yml`` is the readiness signal).
    Experimental and non-ready flags from the static catalog are **not**
    carried over — a discovered module is a shipped module.

    Returns:
        List of :class:`ModuleCatalogEntry` for discovered modules.
    """
    discovered_names = discover_shipped_module_names()

    entries: list[ModuleCatalogEntry] = []
    seen: set[str] = set()
    for name in discovered_names:
        if name in seen:
            continue
        seen.add(name)
        # Supplement with static catalog description when available.
        static_entry = get_module_entry(name)
        description = static_entry.description if static_entry else ""
        entries.append(
            ModuleCatalogEntry(name=name, description=description, ready=True)
        )

    return entries


# ---------------------------------------------------------------------------
# Readiness / placeholder rejection
# ---------------------------------------------------------------------------


def find_not_ready_modules(module_names: Iterable[str]) -> list[str]:
    """Return known module names that are present but not publicly ready.

    This includes modules from the static catalog flagged as non-ready, as
    well as known placeholder module names (e.g. ``teams``) that are
    fail-closed outside the discovered catalog.

    Args:
        module_names: Iterable of module names to check.

    Returns:
        Sorted list of non-ready module names.
    """
    not_ready: list[str] = []
    for module_name in module_names:
        if is_placeholder_module(module_name):
            if module_name not in not_ready:
                not_ready.append(module_name)
            continue
        entry = get_module_entry(module_name)
        if entry is not None and not entry.ready and module_name not in not_ready:
            not_ready.append(module_name)
    return sorted(not_ready)


def get_module_readiness_reason(module_name: str) -> str | None:
    """Return an actionable readiness error for non-public-ready modules.

    Checks known placeholder module names first (fail-closed), then falls
    back to the static catalog.

    Args:
        module_name: The module name to check.

    Returns:
        A human-readable reason string if the module is not ready, or
        ``None`` if the module is ready or unknown.
    """
    # Fail-closed check for known placeholder names outside the catalog.
    placeholder_reason = get_placeholder_rejection_reason(module_name)
    if placeholder_reason is not None:
        return placeholder_reason

    # Fall back to the static catalog.
    entry = get_module_entry(module_name)
    if entry is None or entry.ready:
        return None

    module_display_name = module_name.replace("_", " ").title()
    return (
        f"Module '{module_name}' remains placeholder inventory only and is not a "
        "public-ready QuickScale module yet. "
        f"{module_display_name} remains excluded from public quickscale plan, "
        "quickscale.yml, quickscale apply, and quickscale status workflows until "
        "it ships."
    )
