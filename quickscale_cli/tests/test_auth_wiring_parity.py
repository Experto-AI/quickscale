"""Wiring-parity tests for the manifest-driven auth path (Track 2 M4 follow-up).

Compares the legacy ``_auth_wiring`` builder output against the
manifest-driven ``build_manifest_wiring_spec("auth", ...)`` for every
option case, asserting full
:class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Scope
-----
* Default options (empty dict) — email auth, registration enabled
* Login-method branching: username-only, both, email (default)
* Legacy ``allow_registration`` normalisation fallback
* ``registration_enabled`` override
* Custom ``email_verification`` values
* Custom ``session_cookie_age``
* Combined override cases
* Batch multi-case parity
"""

from __future__ import annotations

from wiring_parity import assert_wiring_parity


class TestAuthWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("auth", [{}])


class TestAuthWiringParityLoginMethodBranching:
    """Login-method branching: authentication_method drives login_methods and signup_fields."""

    def test_username_only(self) -> None:
        assert_wiring_parity("auth", [{"authentication_method": "username"}])

    def test_both_methods(self) -> None:
        assert_wiring_parity("auth", [{"authentication_method": "both"}])

    def test_email_explicit(self) -> None:
        assert_wiring_parity("auth", [{"authentication_method": "email"}])

    def test_username_login_methods_setting(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {"authentication_method": "username"})
        assert spec.settings["ACCOUNT_LOGIN_METHODS"] == {"username"}
        assert spec.settings["ACCOUNT_SIGNUP_FIELDS"] == [
            "username*",
            "password1*",
            "password2*",
        ]

    def test_both_login_methods_setting(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {"authentication_method": "both"})
        assert spec.settings["ACCOUNT_LOGIN_METHODS"] == {"email", "username"}
        assert spec.settings["ACCOUNT_SIGNUP_FIELDS"] == [
            "email*",
            "username*",
            "password1*",
            "password2*",
        ]

    def test_email_login_methods_setting(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {})
        assert spec.settings["ACCOUNT_LOGIN_METHODS"] == {"email"}
        assert spec.settings["ACCOUNT_SIGNUP_FIELDS"] == [
            "email*",
            "password1*",
            "password2*",
        ]


class TestAuthWiringParityLegacyAllowRegistration:
    """Legacy ``allow_registration`` key must normalise to ``registration_enabled``."""

    def test_legacy_allow_registration_false(self) -> None:
        assert_wiring_parity("auth", [{"allow_registration": False}])

    def test_legacy_allow_registration_true(self) -> None:
        assert_wiring_parity("auth", [{"allow_registration": True}])

    def test_legacy_fallback_setting_value(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {"allow_registration": False})
        assert spec.settings["ACCOUNT_ALLOW_REGISTRATION"] is False


class TestAuthWiringParityRegistrationEnabled:
    """Canonical ``registration_enabled`` overrides."""

    def test_registration_disabled(self) -> None:
        assert_wiring_parity("auth", [{"registration_enabled": False}])

    def test_registration_enabled_explicit(self) -> None:
        assert_wiring_parity("auth", [{"registration_enabled": True}])


class TestAuthWiringParityEmailVerification:
    """Email verification option overrides."""

    def test_verification_mandatory(self) -> None:
        assert_wiring_parity("auth", [{"email_verification": "mandatory"}])

    def test_verification_optional(self) -> None:
        assert_wiring_parity("auth", [{"email_verification": "optional"}])

    def test_verification_none_explicit(self) -> None:
        assert_wiring_parity("auth", [{"email_verification": "none"}])


class TestAuthWiringParitySessionCookieAge:
    """Session cookie age overrides."""

    def test_custom_session_cookie_age(self) -> None:
        assert_wiring_parity("auth", [{"session_cookie_age": 3600}])

    def test_session_cookie_age_int_coercion(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {"session_cookie_age": 7200})
        assert spec.settings["SESSION_COOKIE_AGE"] == 7200
        assert isinstance(spec.settings["SESSION_COOKIE_AGE"], int)


class TestAuthWiringParityStaticSettings:
    """Static settings must be present and identical in both paths."""

    def test_apps(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {})
        assert spec.apps == (
            "django.contrib.sites",
            "quickscale_modules_auth",
            "allauth",
            "allauth.account",
        )

    def test_middleware(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {})
        assert spec.middleware == ("allauth.account.middleware.AccountMiddleware",)

    def test_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {})
        assert spec.url_includes == (
            ("accounts/", "allauth.urls"),
            ("accounts/", "quickscale_modules_auth.urls"),
        )

    def test_authentication_backends(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("auth", {})
        assert spec.settings["AUTHENTICATION_BACKENDS"] == [
            "django.contrib.auth.backends.ModelBackend",
            "allauth.account.auth_backends.AuthenticationBackend",
        ]


class TestAuthWiringParityCombinedOverrides:
    """Combined option overrides must produce equal specs from both paths."""

    def test_combined_overrides(self) -> None:
        assert_wiring_parity(
            "auth",
            [
                {
                    "authentication_method": "both",
                    "registration_enabled": False,
                    "email_verification": "mandatory",
                    "session_cookie_age": 86400,
                }
            ],
        )

    def test_combined_with_legacy_key(self) -> None:
        assert_wiring_parity(
            "auth",
            [
                {
                    "authentication_method": "username",
                    "allow_registration": False,
                    "email_verification": "optional",
                }
            ],
        )


class TestAuthWiringParityBatchCases:
    """Run multiple option cases through the harness in a single call."""

    def test_multiple_cases_in_one_call(self) -> None:
        assert_wiring_parity(
            "auth",
            [
                {},
                {"authentication_method": "username"},
                {"authentication_method": "both"},
                {"allow_registration": False},
                {"registration_enabled": False},
                {"email_verification": "mandatory"},
                {"session_cookie_age": 3600},
                {
                    "authentication_method": "both",
                    "registration_enabled": False,
                    "email_verification": "mandatory",
                    "session_cookie_age": 86400,
                },
            ],
        )
