"""Tests for quickscale_core package version information."""

import quickscale_core


def test_version_exists():
    """Test version attribute is defined and is a string."""
    assert hasattr(quickscale_core, "__version__")
    assert isinstance(quickscale_core.__version__, str)


def test_version_format():
    """Test version follows semantic versioning format with three numeric parts."""
    version = quickscale_core.__version__
    parts = version.split(".")
    assert len(parts) == 3, "Version should have 3 parts (major.minor.patch)"
    assert all(part.isdigit() for part in parts), "All version parts should be numeric"


def test_version_tuple():
    """Test VERSION tuple is accessible and contains three integers."""
    assert hasattr(quickscale_core, "VERSION")
    assert isinstance(quickscale_core.VERSION, tuple)
    assert len(quickscale_core.VERSION) == 3
