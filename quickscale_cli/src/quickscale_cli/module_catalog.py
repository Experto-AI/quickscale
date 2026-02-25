"""Module catalog metadata for QuickScale CLI."""

from dataclasses import dataclass


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
        ready=False,
        experimental=True,
    ),
    ModuleCatalogEntry(
        name="billing",
        description="Stripe integration",
        ready=False,
        experimental=True,
    ),
    ModuleCatalogEntry(
        name="teams",
        description="Multi-tenancy and team management",
        ready=False,
        experimental=True,
    ),
)


def get_module_entry(module_name: str) -> ModuleCatalogEntry | None:
    """Return module metadata for a module name."""
    for entry in MODULE_CATALOG:
        if entry.name == module_name:
            return entry
    return None


def get_module_names(*, include_experimental: bool = True) -> list[str]:
    """Return module names from the catalog."""
    entries = get_module_entries(include_experimental=include_experimental)
    return [entry.name for entry in entries]


def get_module_entries(
    *, include_experimental: bool = False
) -> list[ModuleCatalogEntry]:
    """Return catalog entries filtered by readiness/experimental visibility."""
    if include_experimental:
        return list(MODULE_CATALOG)
    return [entry for entry in MODULE_CATALOG if entry.ready]
