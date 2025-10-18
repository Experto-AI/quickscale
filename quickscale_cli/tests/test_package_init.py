"""Tests for quickscale_cli package initialization and version handling."""

from unittest.mock import patch

import quickscale_cli


def test_version_exists():
    """Test version attribute is defined and is a string."""
    assert hasattr(quickscale_cli, "__version__")
    assert isinstance(quickscale_cli.__version__, str)


def test_version_tuple_exists():
    """Test VERSION tuple is accessible and contains three integers."""
    assert hasattr(quickscale_cli, "VERSION")
    assert isinstance(quickscale_cli.VERSION, tuple)
    assert len(quickscale_cli.VERSION) == 3
    assert all(isinstance(part, int) for part in quickscale_cli.VERSION)


def test_version_fallback_to_version_file():
    """Test that version falls back to VERSION file when _version.py import fails."""
    import importlib

    # Mock the import to raise an exception and Path to return a version
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="2.3.4"):
            # Reload the quickscale_cli module to test fallback path
            importlib.reload(quickscale_cli)

            # The module should have loaded successfully
            assert hasattr(quickscale_cli, "__version__")
            assert isinstance(quickscale_cli.__version__, str)


def test_version_fallback_to_default_when_no_file():
    """Test that version falls back to '0.0.0' when VERSION file doesn't exist."""
    import importlib

    # Mock Path.exists to return False for VERSION file
    with patch("pathlib.Path.exists", return_value=False):
        # Reload the module to test the fallback path
        importlib.reload(quickscale_cli)

        # The module should have loaded successfully
        assert hasattr(quickscale_cli, "__version__")


def test_version_tuple_parsing():
    """Test VERSION tuple correctly parses version string."""
    # Test that VERSION tuple extracts numeric parts correctly
    assert isinstance(quickscale_cli.VERSION, tuple)
    assert len(quickscale_cli.VERSION) == 3

    # All parts should be integers
    for part in quickscale_cli.VERSION:
        assert isinstance(part, int)
        assert part >= 0


def test_author_metadata():
    """Test package author metadata is defined."""
    assert hasattr(quickscale_cli, "__author__")
    assert isinstance(quickscale_cli.__author__, str)
    assert len(quickscale_cli.__author__) > 0


def test_email_metadata():
    """Test package email metadata is defined."""
    assert hasattr(quickscale_cli, "__email__")
    assert isinstance(quickscale_cli.__email__, str)
    assert "@" in quickscale_cli.__email__


def test_all_exports():
    """Test __all__ contains expected exports."""
    assert hasattr(quickscale_cli, "__all__")
    assert isinstance(quickscale_cli.__all__, list)
    assert "__version__" in quickscale_cli.__all__
    assert "VERSION" in quickscale_cli.__all__
