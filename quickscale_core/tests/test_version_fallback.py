"""Tests for version.py fallback logic when _version.py is not available."""

import builtins
from pathlib import Path
from unittest.mock import patch


def test_version_fallback_import_error():
    """Test version module handles import error gracefully."""
    # Test the fallback path by simulating _version import failure
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="1.2.3\n"):
            # Import the module fresh (this will use the fallback if _version.py doesn't exist)
            import importlib.util

            # Get the path to version.py
            version_file = (
                Path(__file__).parent.parent / "src" / "quickscale_core" / "version.py"
            )

            # Load the module with a unique name to avoid cache
            spec = importlib.util.spec_from_file_location(
                "test_version_module", version_file
            )
            test_module = importlib.util.module_from_spec(spec)

            # Temporarily block the _version import
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if "_version" in name:
                    raise ImportError("Mocked import error for _version")
                return original_import(name, *args, **kwargs)

            builtins.__import__ = mock_import

            try:
                spec.loader.exec_module(test_module)

                # Verify the module loaded with fallback version
                assert hasattr(test_module, "__version__")
                assert isinstance(test_module.__version__, str)
            finally:
                # Restore original import
                builtins.__import__ = original_import


def test_version_fallback_no_version_file():
    """Test version module falls back to 0.0.0 when VERSION file missing."""
    import importlib.util

    # Get the path to version.py
    version_file = (
        Path(__file__).parent.parent / "src" / "quickscale_core" / "version.py"
    )

    # Load the module with a unique name
    spec = importlib.util.spec_from_file_location("test_version_no_file", version_file)
    test_module = importlib.util.module_from_spec(spec)

    # Mock Path.exists to return False
    with patch("pathlib.Path.exists", return_value=False):
        # Temporarily block the _version import
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "_version" in name:
                raise ModuleNotFoundError("No _version module")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        try:
            spec.loader.exec_module(test_module)

            # Should fall back to 0.0.0
            assert hasattr(test_module, "__version__")
            assert test_module.__version__ == "0.0.0"
        finally:
            builtins.__import__ = original_import


def test_version_tuple_creation():
    """Test VERSION tuple is created correctly from version string."""
    import importlib.util

    version_file = (
        Path(__file__).parent.parent / "src" / "quickscale_core" / "version.py"
    )
    spec = importlib.util.spec_from_file_location("test_version_tuple", version_file)
    test_module = importlib.util.module_from_spec(spec)

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="2.3.4-alpha"):
            # Temporarily block the _version import
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if "_version" in name:
                    raise ImportError("No _version")
                return original_import(name, *args, **kwargs)

            builtins.__import__ = mock_import

            try:
                spec.loader.exec_module(test_module)

                # Verify VERSION tuple was created correctly
                assert hasattr(test_module, "VERSION")
                assert test_module.VERSION == (2, 3, 4)
            finally:
                builtins.__import__ = original_import
