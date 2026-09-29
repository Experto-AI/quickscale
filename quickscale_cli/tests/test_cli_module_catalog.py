"""Tests for module catalog helpers."""

import pytest

from quickscale_core.contracts.module_catalog import (
    find_not_ready_modules,
    get_module_entry,
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


def test_get_module_readiness_reason_returns_none_for_public_ready_billing() -> None:
    """Billing should no longer expose a non-public readiness message."""
    assert get_module_readiness_reason("billing") is None


def test_get_module_readiness_reason_raises_for_deleted_teams() -> None:
    """The deleted teams placeholder is no longer a known module."""
    with pytest.raises(ValueError, match="Unknown module name"):
        get_module_readiness_reason("teams")


def test_get_module_readiness_reason_raises_for_unknown_module() -> None:
    """Unknown module names should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown module name"):
        get_module_readiness_reason("nonexistent")


def test_find_not_ready_modules_filters_ready_modules() -> None:
    """Readiness filtering keeps only known non-public modules; none remain."""
    assert find_not_ready_modules(["auth", "billing", "teams", "unknown"]) == []
