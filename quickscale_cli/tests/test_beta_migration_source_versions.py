"""Contract tests for the beta migration's declared source-version window."""

from __future__ import annotations

import pytest
from quickscale_core import __version__ as running_release
from quickscale_devtools.beta_migration import source_versions


def test_declared_window_ends_at_the_running_release() -> None:
    """The declaration is the release window the smoke gate proves."""
    declared = source_versions.validate_supported_source_versions()

    assert declared == ("0.87.0", "0.88.0", "0.89.0")
    assert declared[-1] == running_release


def test_declared_range_spans_the_running_minor_line() -> None:
    """The range string names the oldest supported release and the next ceiling."""
    assert source_versions.supported_source_version_range() == ">=0.87.0,<0.90.0"


def test_tag_generated_versions_exclude_the_running_release() -> None:
    """Only older releases come from tags; the running release is generated live."""
    assert source_versions.tag_generated_source_versions() == ("0.87.0", "0.88.0")


def test_parse_release_version_returns_numeric_components() -> None:
    """A plain release string becomes a comparable numeric tuple."""
    assert source_versions.parse_release_version("0.89.0") == (0, 89, 0)


@pytest.mark.parametrize(
    "value",
    ["", "0.87", "v0.87.0", "0.87.0rc1", "0.87.0.1", "latest"],
)
def test_parse_release_version_rejects_non_release_strings(value: str) -> None:
    """The declaration never accepts a range, prerelease, or label."""
    with pytest.raises(ValueError, match="expected X.Y.Z"):
        source_versions.parse_release_version(value)


def test_declaration_rejects_a_stale_newest_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A release bump must extend the declaration instead of passing silently."""
    monkeypatch.setattr(
        source_versions,
        "SUPPORTED_SOURCE_VERSIONS",
        ("0.87.0", "0.88.0", "0.89.0", "0.90.0"),
    )

    with pytest.raises(ValueError, match="must end at the running release"):
        source_versions.validate_supported_source_versions()


def test_declaration_rejects_duplicates_and_descending_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window is an ordered set, not an arbitrary list."""
    monkeypatch.setattr(
        source_versions,
        "SUPPORTED_SOURCE_VERSIONS",
        ("0.88.0", "0.87.0", running_release),
    )

    with pytest.raises(ValueError, match="unique and in ascending order"):
        source_versions.validate_supported_source_versions()


def test_declaration_rejects_an_empty_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty declaration cannot prove any source version."""
    monkeypatch.setattr(source_versions, "SUPPORTED_SOURCE_VERSIONS", ())

    with pytest.raises(ValueError, match="declaration is empty"):
        source_versions.validate_supported_source_versions()
