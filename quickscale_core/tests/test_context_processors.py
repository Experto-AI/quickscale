"""Tests for QuickScale core context processors"""

from unittest.mock import patch, MagicMock

from quickscale_core.context_processors import installed_modules


class TestInstalledModulesContextProcessor:
    """Test the installed_modules context processor"""

    def test_installed_modules_with_config(self):
        """Test context processor returns correct module info when config exists"""
        mock_config = MagicMock()
        mock_config.modules = {"auth": MagicMock(), "billing": MagicMock()}

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(None)

            assert "modules" in result
            modules = result["modules"]

            # Check auth module (installed)
            assert "auth" in modules
            assert modules["auth"]["installed"] is True
            assert modules["auth"]["name"] == "Authentication"
            assert modules["auth"]["icon"] == "👤"
            assert modules["auth"]["css_class"] == "nav-link"

            # Check billing module (installed)
            assert "billing" in modules
            assert modules["billing"]["installed"] is True
            assert modules["billing"]["css_class"] == "nav-link"

            # Check teams module (not installed)
            assert "teams" in modules
            assert modules["teams"]["installed"] is False
            assert modules["teams"]["css_class"] == "nav-link disabled"

    def test_installed_modules_empty_config(self):
        """Test context processor handles empty config"""
        mock_config = MagicMock()
        mock_config.modules = {}

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(None)

            assert "modules" in result
            modules = result["modules"]

            # All modules should be marked as not installed
            for module_name in ["auth", "billing", "teams"]:
                assert module_name in modules
                assert modules[module_name]["installed"] is False
                assert modules[module_name]["css_class"] == "nav-link disabled"

    def test_installed_modules_config_error(self):
        """Test context processor handles config loading errors gracefully"""
        with patch(
            "quickscale_core.context_processors.load_config",
            side_effect=Exception("Config error"),
        ):
            result = installed_modules(None)

            assert "modules" in result
            assert result["modules"] == {}
