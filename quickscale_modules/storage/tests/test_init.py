"""Tests for the storage package's lazy public exports."""

from __future__ import annotations

import quickscale_modules_storage as package
import pytest

from quickscale_modules_storage import helpers


def test_lazy_exports_are_runtime_bound_and_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve every public export and retain its first resolved identity."""
    for name in package.__all__:
        monkeypatch.delitem(package.__dict__, name, raising=False)
        helper_value = getattr(helpers, name)

        assert getattr(package, name) is helper_value
        assert package.__dict__[name] is helper_value

        replacement = object()
        monkeypatch.setattr(helpers, name, replacement)
        assert getattr(package, name) is helper_value


def test_unknown_lazy_export_raises_without_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject names outside the runtime export authority without caching them."""
    unknown_name = "__quickscale_storage_unknown_export__"
    assert unknown_name not in package.__all__
    monkeypatch.delitem(package.__dict__, unknown_name, raising=False)

    with pytest.raises(AttributeError):
        getattr(package, unknown_name)

    assert unknown_name not in package.__dict__
