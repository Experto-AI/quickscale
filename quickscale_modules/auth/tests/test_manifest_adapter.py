"""Focused tests for the auth manifest adapter."""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.manifest import ManifestError, build_generic_manifest_spec
from quickscale_core.module_wiring import ModuleWiringSpec
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
        assert spec.settings["ACCOUNT_SIGNUP_FORM_CLASS"] == (
            "quickscale_modules_auth.forms.SignupForm"
        )

    def test_disabled_module_drops_the_accounts_mount(self) -> None:
        """Rule 1 (D3): off keeps the installed app and settings and mounts
        none of the module's public account URLs."""
        spec = _auth_manifest_adapter({"enabled": False})

        assert spec.settings["QUICKSCALE_AUTH_ENABLED"] is False
        assert "quickscale_modules_auth" in spec.apps
        assert spec.url_includes == ()
        assert spec.pre_home_url_includes == ()
        assert spec.middleware == ("allauth.account.middleware.AccountMiddleware",)
        assert spec.settings["AUTH_USER_MODEL"] == "quickscale_auth.User"

    def test_manifest_owns_the_accounts_mount(self) -> None:
        """Rule 7: the manifest's url_includes is the mount's only home."""
        spec = build_generic_manifest_spec("auth", {"authentication_method": "email"})

        assert spec.url_includes == (
            ("accounts/", "allauth.urls"),
            ("accounts/", "quickscale_modules_auth.urls"),
        )
        assert spec.pre_home_url_includes == ()

    def test_manifest_owns_the_account_adapter(self) -> None:
        """Rule 30: auth's manifest is the single writer of ACCOUNT_ADAPTER.

        Auth owns the one allauth adapter; installed modules contribute their
        post-auth redirects as AppConfig capabilities instead of another
        adapter class that extends this one.
        """
        spec = _auth_manifest_adapter({"authentication_method": "email"})

        assert spec.settings["ACCOUNT_ADAPTER"] == (
            "quickscale_modules_auth.allauth_adapter.QuickscaleAccountAdapter"
        )

    @pytest.mark.parametrize(
        "options",
        [
            {"allow_registration": False},
            {"social_providers": ["google"]},
        ],
    )
    def test_legacy_options_fail_closed(self, options: dict[str, Any]) -> None:
        """Removed legacy option names are refused by the manifest engine."""
        with pytest.raises(ManifestError) as exc_info:
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
