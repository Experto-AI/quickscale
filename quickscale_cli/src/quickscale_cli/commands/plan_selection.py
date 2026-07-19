"""Interactive theme and module selection helpers for the plan command."""

import click

from quickscale_core.contracts.module_catalog import (
    ModuleCatalogEntry,
    get_discovered_module_entries,
    get_module_readiness_reason,
)

# Available themes for selection
AVAILABLE_THEMES = [
    ("showcase_react", "React + TypeScript + shadcn/ui (default, production-ready)"),
]


def _get_module_choices(
    *, include_experimental: bool = False
) -> list[ModuleCatalogEntry]:
    """Return shipped module choices discovered via manifest scanning.

    The authoritative source is manifest-backed discovery
    (:func:`get_discovered_module_entries`).  The *include_experimental*
    parameter is accepted for backward compatibility but has no effect
    — a discovered module is a shipped module.
    """
    return get_discovered_module_entries()


def _format_module_choice(entry: ModuleCatalogEntry) -> str:
    """Format a catalog entry for interactive display."""
    if not entry.ready:
        if entry.name == "billing":
            return (
                f"{entry.name} - {entry.description} "
                "(internal packaged Phase 1 foundation, not public-ready)"
            )
        return f"{entry.name} - {entry.description} (placeholder, not public-ready)"
    if entry.experimental:
        return f"{entry.name} - {entry.description} (experimental)"
    return f"{entry.name} - {entry.description}"


def _get_theme_by_index(idx: int) -> str | None:
    """Get theme ID by index (0-based)."""
    if 0 <= idx < len(AVAILABLE_THEMES):
        return AVAILABLE_THEMES[idx][0]
    return None


def _get_theme_by_name(name: str) -> str | None:
    """Get theme ID by name (case-insensitive)."""
    for theme_id, _ in AVAILABLE_THEMES:
        if name.lower() == theme_id.lower():
            return theme_id
    return None


def _select_theme() -> str:
    """Interactive theme selection."""
    click.echo("\n🎨 Select a theme for your project:")
    for i, (tid, description) in enumerate(AVAILABLE_THEMES, start=1):
        click.echo(f"  {i}. {tid} - {description}")

    while True:
        choice = click.prompt(
            "\nEnter theme number or name",
            default="1",
            show_default=True,
        )

        # Try numeric choice first
        theme_id: str | None
        if choice.isdigit():
            theme_id = _get_theme_by_index(int(choice) - 1)
        else:
            theme_id = _get_theme_by_name(choice)

        if theme_id is not None:
            return theme_id

        click.secho("Invalid choice. Please try again.", fg="red")


def _parse_module_choice(
    part: str, available_modules: list[ModuleCatalogEntry]
) -> str | None:
    """Parse a single module choice (number or name).

    Returns:
        Module ID if valid, None otherwise

    Raises:
        ValueError: If choice is invalid
    """
    if part.isdigit():
        idx = int(part) - 1
        if 0 <= idx < len(available_modules):
            selected = available_modules[idx]
            if not selected.ready:
                raise ValueError(
                    get_module_readiness_reason(selected.name)
                    or f"Unknown module: {selected.name}"
                )
            return selected.name
        raise ValueError(f"Invalid number: {part}")

    # Handle module name
    for entry in available_modules:
        if part.lower() == entry.name.lower():
            if not entry.ready:
                raise ValueError(
                    get_module_readiness_reason(entry.name)
                    or f"Unknown module: {entry.name}"
                )
            return entry.name

    raise ValueError(f"Unknown module: {part}")


def _parse_module_selection(
    choice: str,
    available_modules: list[ModuleCatalogEntry],
) -> list[str]:
    """Parse comma-separated module selection.

    Returns:
        List of unique module IDs

    Raises:
        ValueError: If any choice is invalid
    """
    if not choice.strip():
        return []

    selected: list[str] = []
    parts = [p.strip() for p in choice.split(",")]

    for part in parts:
        module_id = _parse_module_choice(part, available_modules)
        if module_id and module_id not in selected:
            selected.append(module_id)

    return selected


def _select_modules(*, include_experimental: bool = False) -> list[str]:
    """Interactive module selection."""
    available_modules = _get_module_choices(include_experimental=include_experimental)
    click.echo("\n📦 Select modules to embed (optional):")
    for i, entry in enumerate(available_modules, start=1):
        click.echo(f"  {i}. {_format_module_choice(entry)}")

    if include_experimental and any(not entry.ready for entry in available_modules):
        click.echo(
            "\n  Non-public modules are shown for visibility only and cannot be selected"
        )

    click.echo(
        "\n  Enter numbers separated by commas (e.g., 1,3), or press Enter to skip"
    )

    while True:
        choice = click.prompt(
            "Select modules",
            default="",
            show_default=False,
        )

        try:
            return _parse_module_selection(choice, available_modules)
        except ValueError as e:
            click.secho(f"Invalid selection: {e}. Please try again.", fg="red")
