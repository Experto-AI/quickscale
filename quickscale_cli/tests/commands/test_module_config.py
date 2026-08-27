"""Tests for module_config.py - module configuration functions."""

from unittest.mock import patch

from quickscale_cli.commands.module_config import (
    configure_auth_module,
    configure_blog_module,
    get_default_auth_config,
    get_default_blog_config,
    MODULE_CONFIGURATOR_REGISTRY,
    ModuleConfigurator,
)


class TestAuthModuleConfig:
    """Tests for auth module configuration functions."""

    def test_get_default_auth_config(self):
        """Test default auth configuration."""
        config = get_default_auth_config()

        assert config["registration_enabled"] is True
        assert config["email_verification"] == "none"
        assert config["authentication_method"] == "email"
        assert config["session_cookie_age"] == 1209600

    def test_configure_auth_module_non_interactive(self):
        """Test non-interactive auth configuration."""
        config = configure_auth_module(non_interactive=True)

        assert config["registration_enabled"] is True
        assert config["email_verification"] == "none"
        assert config["authentication_method"] == "email"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_auth_module_interactive(self, mock_confirm, mock_prompt):
        """Test interactive auth configuration."""
        mock_confirm.return_value = False
        mock_prompt.side_effect = ["mandatory", "username"]

        config = configure_auth_module(non_interactive=False)

        assert config["registration_enabled"] is False
        assert config["email_verification"] == "mandatory"
        assert config["authentication_method"] == "username"


class TestBlogModuleConfig:
    """Tests for blog module configuration functions."""

    def test_get_default_blog_config(self):
        """Test default blog configuration."""
        config = get_default_blog_config()

        assert config["enable_rss"] is True
        assert config["posts_per_page"] == 10
        assert config["api_rate_limit"] == "5/hour"

    def test_configure_blog_module_non_interactive(self):
        """Test non-interactive blog configuration."""
        config = configure_blog_module(non_interactive=True)

        assert config["enable_rss"] is True
        assert config["posts_per_page"] == 10
        assert config["api_rate_limit"] == "5/hour"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_blog_module_interactive(self, mock_confirm, mock_prompt):
        """Test interactive blog configuration."""
        mock_confirm.return_value = False
        mock_prompt.side_effect = [20, "10/minute"]

        config = configure_blog_module(non_interactive=False)

        assert config["enable_rss"] is False
        assert config["posts_per_page"] == 20
        assert config["api_rate_limit"] == "10/minute"


class TestModuleConfigurators:
    """Tests for MODULE_CONFIGURATOR_REGISTRY."""

    def test_module_configurator_registry_structure(self):
        """Test that MODULE_CONFIGURATOR_REGISTRY is properly structured."""
        assert "auth" in MODULE_CONFIGURATOR_REGISTRY
        assert "blog" in MODULE_CONFIGURATOR_REGISTRY

        for name, entry in MODULE_CONFIGURATOR_REGISTRY.items():
            assert isinstance(entry, ModuleConfigurator)
            assert entry.name == name
            assert callable(entry.configure)

    def test_module_configurator_registry_has_defaults(self):
        """Every registered configurator should expose a get_defaults factory."""
        for name, entry in MODULE_CONFIGURATOR_REGISTRY.items():
            assert entry.get_defaults is not None, (
                f"{name} configurator is missing get_defaults"
            )
            defaults = entry.get_defaults()
            assert isinstance(defaults, dict)

    def test_auth_configurator_in_registry(self):
        """Test auth configurator is accessible from MODULE_CONFIGURATOR_REGISTRY."""
        entry = MODULE_CONFIGURATOR_REGISTRY["auth"]

        config = entry.configure(non_interactive=True)
        assert "registration_enabled" in config

    def test_blog_configurator_in_registry(self):
        """Test blog configurator is accessible from MODULE_CONFIGURATOR_REGISTRY."""
        entry = MODULE_CONFIGURATOR_REGISTRY["blog"]

        config = entry.configure(non_interactive=True)
        assert "enable_rss" in config
