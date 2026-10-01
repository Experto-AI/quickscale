"""Contract tests for the blog module's manifest-owned configuration.

The blog module's option defaults, normalization, and validation are declared
in ``quickscale_modules/blog/module.yml`` and enforced through the shared
manifest engine, and its CLI configurator reads the manifest.  These tests pin
that contract and the operator-facing behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_cli.commands.plan_command import _configure_selected_modules
from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)
from quickscale_core.schema.config_schema import ConfigValidationError, validate_config

_EXPECTED_DEFAULTS: dict[str, object] = {
    "posts_per_page": 10,
    "rss_enabled": True,
    "api_rate_limit": "5/hour",
    "api_upload_max_bytes": 10485760,
    "api_upload_max_width": 4096,
    "api_upload_max_height": 4096,
    "api_allowed_image_formats": ["PNG", "JPEG", "WEBP", "GIF"],
}

_RETIRED_ENABLE_RSS_MESSAGE = (
    "Legacy config key 'enable_rss' is no longer supported. Use 'rss_enabled' instead."
)


def _manifest():
    return load_module_manifest_with_fallback("blog")


# ===========================================================================
# 1. Manifest contract
# ===========================================================================


class TestBlogManifestContract:
    """The manifest declares the defaults, settings, and constraints."""

    def test_manifest_declares_exactly_the_contract_options(self) -> None:
        assert set(_manifest().get_defaults()) == set(_EXPECTED_DEFAULTS)

    def test_manifest_defaults_match_contract(self) -> None:
        assert _manifest().get_defaults() == _EXPECTED_DEFAULTS

    def test_django_settings_are_declared(self) -> None:
        manifest = _manifest()
        assert (
            manifest.get_option("posts_per_page").django_setting
            == "QUICKSCALE_BLOG_POSTS_PER_PAGE"
        )
        assert (
            manifest.get_option("rss_enabled").django_setting
            == "QUICKSCALE_BLOG_RSS_ENABLED"
        )
        assert (
            manifest.get_option("api_rate_limit").django_setting
            == "QUICKSCALE_BLOG_API_RATE_LIMIT"
        )

    def test_manifest_declares_the_option_types(self) -> None:
        manifest = _manifest()
        assert manifest.get_option("posts_per_page").option_type == "integer"
        assert manifest.get_option("rss_enabled").option_type == "boolean"
        assert manifest.get_option("api_rate_limit").option_type == "string"

    def test_manifest_declares_the_upload_option_types(self) -> None:
        manifest = _manifest()
        assert manifest.get_option("api_upload_max_bytes").option_type == "integer"
        assert manifest.get_option("api_upload_max_width").option_type == "integer"
        assert manifest.get_option("api_upload_max_height").option_type == "integer"
        assert manifest.get_option("api_allowed_image_formats").option_type == "list"
        assert (
            manifest.get_option("api_allowed_image_formats").django_setting
            == "QUICKSCALE_BLOG_API_ALLOWED_IMAGE_FORMATS"
        )

    def test_unsupported_or_blank_image_format_is_refused(self) -> None:
        for bad_value in ([""], ["PNG", ""], ["TIFF"]):
            issues = collect_option_validation_issues(
                _manifest(), {"api_allowed_image_formats": bad_value}
            )
            assert any(
                issue.option_name == "api_allowed_image_formats" for issue in issues
            ), bad_value


# ===========================================================================
# 2. Validation engine behaviour
# ===========================================================================


class TestBlogValidation:
    """The shared engine enforces the manifest's declared constraints."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), None) == []

    def test_valid_overrides_pass_validation(self) -> None:
        assert (
            validate_module_options(
                _manifest(),
                {
                    "posts_per_page": 20,
                    "rss_enabled": False,
                    "api_rate_limit": "10/minute",
                },
            )
            == []
        )

    @pytest.mark.parametrize("bad_value", [0, -1, -100])
    def test_non_positive_posts_per_page_is_refused(self, bad_value: int) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"posts_per_page": bad_value}
        )
        assert any(
            issue.option_name == "posts_per_page"
            and "QUICKSCALE_BLOG_POSTS_PER_PAGE" in issue.message
            for issue in issues
        )

    @pytest.mark.parametrize("bad_value", ["", "   ", "5", "5/week"])
    def test_invalid_api_rate_limit_is_refused(self, bad_value: str) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"api_rate_limit": bad_value}
        )
        assert any(issue.option_name == "api_rate_limit" for issue in issues)

    def test_non_boolean_enable_rss_is_refused(self) -> None:
        issues = collect_option_validation_issues(
            _manifest(),
            {"rss_enabled": "yes"},
            supplied={"rss_enabled": "yes"},
        )
        assert any(
            issue.option_name == "rss_enabled" and "boolean" in issue.message
            for issue in issues
        )


class TestBlogRetiredOption:
    """``enable_rss`` is refused from its manifest declaration."""

    def test_manifest_declares_the_retired_key(self) -> None:
        assert _manifest().retired_options == {
            "enable_rss": _RETIRED_ENABLE_RSS_MESSAGE
        }

    def test_engine_reports_the_retired_key_with_the_declared_message(self) -> None:
        issues = collect_option_validation_issues(_manifest(), {"enable_rss": True})
        assert [(issue.option_name, issue.message) for issue in issues] == [
            ("enable_rss", _RETIRED_ENABLE_RSS_MESSAGE)
        ]

    def test_config_load_refuses_the_retired_key(self) -> None:
        yaml_content = (
            'version: "1"\n'
            "project:\n"
            "  slug: demo\n"
            "  package: demo\n"
            "modules:\n"
            "  blog:\n"
            "    enable_rss: true\n"
        )

        with pytest.raises(ConfigValidationError) as excinfo:
            validate_config(yaml_content)

        assert "enable_rss" in str(excinfo.value)
        assert "rss_enabled" in str(excinfo.value)


# ===========================================================================
# 3. CLI configurator behaviour
# ===========================================================================


class TestBlogConfigurator:
    """The CLI configurator's prompts and defaults come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["blog"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["blog"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_kept(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["blog"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"posts_per_page": 20, "rss_enabled": False},
        )
        assert config["posts_per_page"] == 20
        assert config["rss_enabled"] is False
        assert config["api_rate_limit"] == "5/hour"

    def test_undeclared_existing_keys_are_dropped(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["blog"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"retired_key": "value"},
        )
        assert "retired_key" not in config
        assert config == _EXPECTED_DEFAULTS

    def test_existing_values_are_returned_in_canonical_form(self) -> None:
        """A padded rate limit is stored the way the manifest canonicalizes it."""
        entry = MODULE_CONFIGURATOR_REGISTRY["blog"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"api_rate_limit": "  10/minute  "},
        )
        assert config["api_rate_limit"] == "10/minute"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_interactive_values_are_returned_in_canonical_form(
        self, mock_confirm, mock_prompt
    ) -> None:
        """A padded interactive answer is stored in its canonical form."""
        mock_confirm.return_value = True
        mock_prompt.side_effect = [
            20,
            "  10/minute  ",
            10485760,
            4096,
            4096,
            "PNG, JPEG, WEBP, GIF",
        ]

        entry = MODULE_CONFIGURATOR_REGISTRY["blog"]
        config = entry.configure(non_interactive=False)

        assert config["api_rate_limit"] == "10/minute"
        assert config["posts_per_page"] == 20

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_planner_persists_the_canonical_blog_rate(
        self, mock_confirm, mock_prompt
    ) -> None:
        """The planner's own output carries the canonical rate limit."""
        mock_confirm.return_value = True
        mock_prompt.side_effect = [
            20,
            "  10/minute  ",
            10485760,
            4096,
            4096,
            "PNG, JPEG, WEBP, GIF",
        ]

        configured = _configure_selected_modules(
            ["blog"],
            {},
            new_modules=None,
            allow_reconfigure_existing=False,
        )

        assert configured["blog"]["api_rate_limit"] == "10/minute"
        assert configured["blog"]["posts_per_page"] == 20
