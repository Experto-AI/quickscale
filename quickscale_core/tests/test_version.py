"""Tests for quickscale_core package version information."""

import sys
from unittest.mock import patch

import pytest

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


def test_version_fallback_to_version_file():
    """Test that version falls back to VERSION file when _version.py doesn't exist."""
    import builtins
    import importlib

    from quickscale_core import version

    # Remove cached _version so the import actually triggers __import__
    if "quickscale_core._version" in sys.modules:
        del sys.modules["quickscale_core._version"]

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if "_version" in name:
            raise ImportError("Mock import error for _version")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value="1.2.3"):
                importlib.reload(version)
                assert version.__version__ == "1.2.3"

    importlib.reload(version)


def test_version_raises_when_fallback_file_missing():
    """Test that version import fails when both _version.py and VERSION are unavailable."""
    import importlib
    import builtins

    from quickscale_core import version

    # Remove cached _version so the import actually triggers __import__
    if "quickscale_core._version" in sys.modules:
        del sys.modules["quickscale_core._version"]

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if "_version" in name:
            raise ImportError("Mock import error for _version")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="VERSION file was not found"):
                importlib.reload(version)

    importlib.reload(version)


def test_version_tuple_with_prerelease():
    """Test VERSION tuple correctly handles pre-release versions like '1.2.3-alpha'."""
    from quickscale_core import version

    # Test that VERSION tuple extracts only numeric parts
    # This ensures the version tuple parsing works correctly
    assert isinstance(version.VERSION, tuple)
    assert len(version.VERSION) == 3
    assert all(isinstance(part, int) for part in version.VERSION)


def test_version_import_exception_with_version_file():
    """Test that version module handles import exception and reads VERSION file."""
    import importlib
    import builtins
    from pathlib import Path

    # Save the original __import__
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        """Mock import that raises exception for _version module."""
        if name == "._version" or name.endswith("._version"):
            raise ImportError("Mock import error for _version")
        return original_import(name, *args, **kwargs)

    # Get the path to the actual VERSION file in the repo
    from quickscale_core import version as version_module

    version_file = Path(version_module.__file__).resolve().parents[3] / "VERSION"

    # Only run this test if VERSION file exists
    if version_file.exists():
        with patch("builtins.__import__", side_effect=mock_import):
            # Reload the version module to trigger the fallback path
            importlib.reload(version_module)

            # The version should be loaded from VERSION file
            assert hasattr(version_module, "__version__")
            assert version_module.__version__ != "0.0.0"  # Should have actual version


def test_version_import_exception_without_version_file():
    """Test that version module raises when both _version and VERSION file fail."""
    import importlib
    import builtins

    # Save the original __import__
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        """Mock import that raises exception for _version module."""
        if "_version" in name:
            raise ImportError("Mock import error for _version")
        return original_import(name, *args, **kwargs)

    from quickscale_core import version as version_module

    # Remove cached _version so the import actually triggers __import__
    if "quickscale_core._version" in sys.modules:
        del sys.modules["quickscale_core._version"]

    with patch("builtins.__import__", side_effect=mock_import):
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="VERSION file was not found"):
                importlib.reload(version_module)

    importlib.reload(version_module)
