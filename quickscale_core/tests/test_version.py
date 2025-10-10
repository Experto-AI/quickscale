"""Basic tests for quickscale_core package."""

import quickscale_core


def test_version_exists():
    """Test that version is defined."""
    assert hasattr(quickscale_core, "__version__")
    assert isinstance(quickscale_core.__version__, str)


def test_version_format():
    """Test that version follows semantic versioning."""
    version = quickscale_core.__version__
    parts = version.split(".")
    assert len(parts) == 3, "Version should have 3 parts (major.minor.patch)"
    assert all(part.isdigit() for part in parts), "All version parts should be numeric"


def test_version_tuple():
    """Test that VERSION tuple is accessible."""
    assert hasattr(quickscale_core, "VERSION")
    assert isinstance(quickscale_core.VERSION, tuple)
    assert len(quickscale_core.VERSION) == 3
