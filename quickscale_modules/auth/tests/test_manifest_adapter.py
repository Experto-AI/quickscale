"""Focused tests for the auth manifest adapter."""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_core.schema.config_schema import ConfigValidationError
from quickscale_modules_auth.adapter import (
    _auth_manifest_adapter,
    get_manifest_adapter,
)


class TestAuthManifestAdapter:
    """Auth adapter settings and wiring contract."""

    def test_sentinel_returns_callable(self) -> None:
        """The public sentinel returns the module adapter."""
        assert get_manifest_adapter() is _auth_manifest_adapter

    @pytest.mark.parametrize(
        ("method", "login_methods", "signup_fields"),
        [
            ("email", {"email"}, ["email*", "password1*", "password2*"]),
            ("username", {"username"}, ["username*", "password1*", "password2*"]),
            (
                "both",
                {"email", "username"},
                ["email*", "username*", "password1*", "password2*"],
            ),
        ],
    )
    def test_authentication_method_projection(
        self,
        method: str,
        login_methods: set[str],
        signup_fields: list[str],
    ) -> None:
        """Email, username, and both modes preserve their exact projections."""
        spec = _auth_manifest_adapter({"authentication_method": method})

        assert isinstance(spec, ModuleWiringSpec)
        assert spec.apps == (
            "django.contrib.sites",
            "quickscale_modules_auth",
            "allauth",
            "allauth.account",
        )
        assert spec.settings["ACCOUNT_LOGIN_METHODS"] == login_methods
        assert spec.settings["ACCOUNT_SIGNUP_FIELDS"] == signup_fields

    def test_defaults_and_overrides_preserve_wiring_order(self) -> None:
        """Defaults, overrides, middleware, and URL order remain stable."""
        spec = _auth_manifest_adapter(
            {
                "registration_enabled": False,
                "email_verification": "mandatory",
                "session_cookie_age": 3600,
            }
        )

        assert spec.settings["ACCOUNT_ALLOW_REGISTRATION"] is False
        assert spec.settings["ACCOUNT_EMAIL_VERIFICATION"] == "mandatory"
        assert spec.settings["SESSION_COOKIE_AGE"] == 3600
        assert spec.middleware == ("allauth.account.middleware.AccountMiddleware",)
        assert spec.url_includes == (
            ("accounts/", "allauth.urls"),
            ("accounts/", "quickscale_modules_auth.urls"),
        )
        assert spec.pre_home_url_includes == ()
        assert spec.settings["ACCOUNT_ADAPTER"] == (
            "quickscale_modules_auth.adapters.QuickscaleAccountAdapter"
        )
        assert spec.settings["ACCOUNT_SIGNUP_FORM_CLASS"] == (
            "quickscale_modules_auth.forms.SignupForm"
        )

    @pytest.mark.parametrize(
        "options",
        [
            {"allow_registration": False},
            {"social_providers": ["google"]},
        ],
    )
    def test_legacy_options_fail_closed(self, options: dict[str, Any]) -> None:
        """Removed legacy option names retain the resolver's explicit errors."""
        with pytest.raises(ConfigValidationError) as exc_info:
            _auth_manifest_adapter(options)

        assert "no longer supported" in str(exc_info.value)

    def test_repeated_calls_do_not_leak_options_or_wiring(self) -> None:
        """Repeated calls with different modes remain independent."""
        username = _auth_manifest_adapter({"authentication_method": "username"})
        email = _auth_manifest_adapter({"authentication_method": "email"})
        username_again = _auth_manifest_adapter({"authentication_method": "username"})

        assert username.settings["ACCOUNT_LOGIN_METHODS"] == {"username"}
        assert email.settings["ACCOUNT_LOGIN_METHODS"] == {"email"}
        assert username_again == username
