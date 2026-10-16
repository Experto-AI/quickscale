"""The shared conftest plugin the module suites adopt (decisions rule 18)."""

from __future__ import annotations

from typing import Any

from quickscale_core.testing.pytest_plugin import (
    ALLOW_BYPASS_RLS_ENV_VAR,
    BYPASS_RLS_MARKER,
    pytest_collection_modifyitems,
    pytest_configure,
)


class _RecordingConfig:
    """The two ``pytest.Config`` surfaces the shared hooks touch."""

    def __init__(self) -> None:
        self.marker_lines: list[tuple[str, str]] = []
        self.deselected: list[list[Any]] = []
        self.hook = self

    def addinivalue_line(self, name: str, line: str) -> None:
        self.marker_lines.append((name, line))

    def pytest_deselected(self, *, items: list[Any]) -> None:
        self.deselected.append(list(items))


class _Item:
    def __init__(self, marked: bool) -> None:
        self.marked = marked

    def get_closest_marker(self, name: str) -> object | None:
        assert name == "bypass_rls"
        return object() if self.marked else None


def test_configure_registers_the_bypass_rls_marker() -> None:
    config = _RecordingConfig()

    pytest_configure(config)  # type: ignore[arg-type]

    assert config.marker_lines == [("markers", BYPASS_RLS_MARKER)]
    assert "bypass_rls:" in BYPASS_RLS_MARKER


def test_marked_tests_are_deselected_by_default(monkeypatch) -> None:
    monkeypatch.delenv(ALLOW_BYPASS_RLS_ENV_VAR, raising=False)
    config = _RecordingConfig()
    marked = _Item(marked=True)
    plain = _Item(marked=False)
    items = [plain, marked]

    pytest_collection_modifyitems(config, items)  # type: ignore[arg-type]

    assert items == [plain]
    assert config.deselected == [[marked]]


def test_explicit_authorization_keeps_every_test(monkeypatch) -> None:
    monkeypatch.setenv(ALLOW_BYPASS_RLS_ENV_VAR, "1")
    config = _RecordingConfig()
    marked = _Item(marked=True)
    items = [marked]

    pytest_collection_modifyitems(config, items)  # type: ignore[arg-type]

    assert items == [marked]
    assert config.deselected == []


def test_any_other_value_still_deselects(monkeypatch) -> None:
    monkeypatch.setenv(ALLOW_BYPASS_RLS_ENV_VAR, "true")
    config = _RecordingConfig()
    marked = _Item(marked=True)

    pytest_collection_modifyitems(config, [marked])  # type: ignore[arg-type]

    assert config.deselected == [[marked]]


def test_no_marked_tests_emit_no_deselection(monkeypatch) -> None:
    monkeypatch.delenv(ALLOW_BYPASS_RLS_ENV_VAR, raising=False)
    config = _RecordingConfig()
    plain = _Item(marked=False)

    pytest_collection_modifyitems(config, [plain])  # type: ignore[arg-type]

    assert config.deselected == []
