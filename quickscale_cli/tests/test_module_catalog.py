"""Tests for module catalog helpers."""

from quickscale_cli.module_catalog import (
    get_module_entry,
    get_module_entries,
    get_module_names,
)


def test_get_module_entry_returns_storage_metadata() -> None:
    """Catalog lookup should return storage metadata for ready modules."""
    entry = get_module_entry("storage")

    assert entry is not None
    assert entry.name == "storage"
    assert entry.ready is True


def test_get_module_entry_returns_none_for_unknown_module() -> None:
    """Catalog lookup should return None for unknown module names."""
    assert get_module_entry("unknown") is None


def test_get_module_entries_filters_experimental_by_default() -> None:
    """Default catalog listing should omit experimental modules."""
    entries = get_module_entries()
    names = [entry.name for entry in entries]

    assert "storage" in names
    assert "backups" in names
    assert "billing" not in names
    assert "teams" not in names


def test_get_module_names_includes_experimental_when_requested() -> None:
    """Explicit include_experimental should surface experimental modules."""
    names = get_module_names(include_experimental=True)

    assert "billing" in names
    assert "teams" in names
    assert "storage" in names
    assert "backups" in names
