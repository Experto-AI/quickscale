"""Tests for QuickScale core context processors"""

from unittest.mock import MagicMock, patch

from quickscale_core.context_processors import installed_modules


class TestInstalledModulesContextProcessor:
    """Test the installed_modules context processor"""

    def test_installed_modules_only_surfaces_shipped_helper_modules(self):
        """Placeholder modules should never leak into the shipped helper output."""
        mock_config = MagicMock()
        mock_config.modules = {
            "auth": MagicMock(),
            "billing": MagicMock(),
            "teams": MagicMock(),
        }

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(None)

            assert "modules" in result
            modules = result["modules"]

            assert set(modules) == {"auth"}
            assert modules["auth"]["installed"] is True
            assert modules["auth"]["name"] == "Authentication"
            assert modules["auth"]["icon"] == "👤"
            assert modules["auth"]["css_class"] == "nav-link"

    def test_installed_modules_marks_shipped_helper_modules_missing_when_not_installed(
        self,
    ):
        """Only shipped helper modules should appear when config is empty."""
        mock_config = MagicMock()
        mock_config.modules = {}

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(None)

            assert "modules" in result
            modules = result["modules"]

            assert set(modules) == {"auth"}
            assert modules["auth"]["installed"] is False
            assert modules["auth"]["css_class"] == "nav-link disabled"

    def test_installed_modules_config_error(self):
        """Test context processor handles config loading errors gracefully"""
        with patch(
            "quickscale_core.context_processors.load_config",
            side_effect=Exception("Config error"),
        ):
            result = installed_modules(None)

            assert "modules" in result
            assert result["modules"] == {}
