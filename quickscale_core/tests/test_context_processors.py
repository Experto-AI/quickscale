"""Tests for QuickScale core context processors"""

from unittest.mock import MagicMock, patch

from quickscale_core.context_processors import installed_modules


class TestInstalledModulesContextProcessor:
    """Test the installed_modules context processor"""

    def test_installed_modules_surfaces_auth_and_billing_only(self):
        """Helper output should expose auth and billing while keeping teams hidden."""
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

            assert set(modules) == {"auth", "billing"}
            assert modules["auth"]["installed"] is True
            assert modules["auth"]["name"] == "Authentication"
            assert modules["auth"]["icon"] == "👤"
            assert modules["auth"]["css_class"] == "nav-link"
            assert modules["billing"]["installed"] is True
            assert modules["billing"]["name"] == "Billing"
            assert modules["billing"]["icon"] == "💳"
            assert modules["billing"]["url"] == "/billing/pricing/"

    def test_installed_modules_marks_shipped_helper_modules_missing_when_not_installed(
        self,
    ):
        """Auth and billing should appear disabled when config is empty."""
        mock_config = MagicMock()
        mock_config.modules = {}

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(None)

            assert "modules" in result
            modules = result["modules"]

            assert set(modules) == {"auth", "billing"}
            assert modules["auth"]["installed"] is False
            assert modules["auth"]["css_class"] == "nav-link disabled"
            assert modules["billing"]["installed"] is False
            assert modules["billing"]["css_class"] == "nav-link disabled"
            assert modules["billing"]["url"] == "/billing/pricing/"

    def test_installed_modules_uses_dashboard_link_for_authenticated_billing_users(
        self,
    ):
        """Billing helper links should point signed-in users at the module dashboard."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/billing/dashboard/"

    def test_installed_modules_config_error(self):
        """Test context processor handles config loading errors gracefully"""
        with patch(
            "quickscale_core.context_processors.load_config",
            side_effect=Exception("Config error"),
        ):
            result = installed_modules(None)

            assert "modules" in result
            assert result["modules"] == {}
