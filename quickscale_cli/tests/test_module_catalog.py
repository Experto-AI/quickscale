"""Tests for module catalog helpers."""

from quickscale_cli.module_catalog import (
    find_not_ready_modules,
    get_module_entry,
    get_module_entries,
    get_module_names,
    get_module_readiness_reason,
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
    assert "social" in names
    assert "billing" not in names
    assert "teams" not in names


def test_get_module_names_includes_experimental_when_requested() -> None:
    """Explicit include_experimental should surface placeholder entries."""
    names = get_module_names(include_experimental=True)

    assert "billing" in names
    assert "teams" in names
    assert "storage" in names
    assert "backups" in names
    assert "social" in names


def test_get_module_entry_returns_notifications_metadata() -> None:
    """Catalog lookup should return notifications metadata for ready modules."""
    entry = get_module_entry("notifications")

    assert entry is not None
    assert entry.name == "notifications"
    assert entry.ready is True


def test_get_module_entry_returns_social_metadata() -> None:
    """Catalog lookup should return social metadata for ready modules."""
    entry = get_module_entry("social")

    assert entry is not None
    assert entry.name == "social"
    assert entry.ready is True


def test_get_module_readiness_reason_reports_placeholder_modules() -> None:
    """Placeholder directories should expose an actionable readiness message."""
    reason = get_module_readiness_reason("billing")

    assert reason is not None
    assert "billing" in reason
    assert "placeholder" in reason


def test_find_not_ready_modules_filters_ready_modules() -> None:
    """Readiness filtering should keep only known placeholder modules."""
    assert find_not_ready_modules(["auth", "billing", "teams", "unknown"]) == [
        "billing",
        "teams",
    ]
