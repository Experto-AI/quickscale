"""Wiring-parity tests for the manifest-driven notifications path (M4 follow-up).

Compares the legacy ``_notifications_wiring`` builder output against the
manifest-driven ``build_manifest_wiring_spec("notifications", ...)`` for every
option case, asserting full
:class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Scope
-----
* Default options (empty dict) — console backend, no anymail
* Disabled case (enabled=False) — no EMAIL_BACKEND, no anymail
* Live-delivery case (resend_domain + valid sender + api key env var) — anymail
  prepended, live Resend backend
* Custom sender name / email
* Custom tags
* Combined override cases
"""

from __future__ import annotations

from wiring_parity import assert_wiring_parity


class TestNotificationsWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("notifications", [{}])


class TestNotificationsWiringParityDisabled:
    """Disabled notifications: no EMAIL_BACKEND, no anymail app."""

    def test_disabled_returns_matching_spec(self) -> None:
        assert_wiring_parity("notifications", [{"enabled": False}])

    def test_disabled_apps_no_anymail(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("notifications", {"enabled": False})
        assert "anymail" not in spec.apps

    def test_disabled_no_email_backend(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("notifications", {"enabled": False})
        assert "EMAIL_BACKEND" not in spec.settings


class TestNotificationsWiringParityConsoleBackend:
    """Enabled without live delivery: console backend, no anymail."""

    def test_console_backend_no_anymail(self) -> None:
        assert_wiring_parity(
            "notifications",
            [{"sender_name": "Test Sender", "sender_email": "test@example.com"}],
        )

    def test_console_backend_settings(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec(
            "notifications",
            {"sender_name": "Test Sender", "sender_email": "test@example.com"},
        )
        assert "anymail" not in spec.apps
        assert (
            spec.settings.get("EMAIL_BACKEND")
            == "django.core.mail.backends.console.EmailBackend"
        )


class TestNotificationsWiringParityLiveDelivery:
    """Live delivery: anymail prepended, Resend backend."""

    _LIVE_OPTIONS = {
        "sender_name": "My App",
        "sender_email": "hello@myapp.com",
        "resend_domain": "myapp.com",
        "resend_api_key_env_var": "RESEND_API_KEY",
    }

    def test_live_delivery_parity(self) -> None:
        assert_wiring_parity("notifications", [self._LIVE_OPTIONS])

    def test_live_delivery_has_anymail(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("notifications", self._LIVE_OPTIONS)
        assert spec.apps[0] == "anymail"
        assert "quickscale_modules_notifications" in spec.apps

    def test_live_delivery_has_resend_backend(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("notifications", self._LIVE_OPTIONS)
        assert (
            spec.settings.get("EMAIL_BACKEND") == "anymail.backends.resend.EmailBackend"
        )


class TestNotificationsWiringParityOverrides:
    """Overridden options must produce equal specs from both paths."""

    def test_custom_sender_name(self) -> None:
        assert_wiring_parity(
            "notifications",
            [{"sender_name": "Custom Sender"}],
        )

    def test_custom_sender_email(self) -> None:
        assert_wiring_parity(
            "notifications",
            [{"sender_email": "custom@example.com"}],
        )

    def test_custom_reply_to(self) -> None:
        assert_wiring_parity(
            "notifications",
            [{"reply_to_email": "support@example.com"}],
        )

    def test_custom_resend_domain(self) -> None:
        assert_wiring_parity(
            "notifications",
            [{"resend_domain": "mail.example.com"}],
        )

    def test_custom_webhook_ttl(self) -> None:
        assert_wiring_parity(
            "notifications",
            [{"webhook_ttl_seconds": 600}],
        )

    def test_custom_default_tags(self) -> None:
        assert_wiring_parity(
            "notifications",
            [{"default_tags": ["custom", "transactional"]}],
        )

    def test_combined_overrides(self) -> None:
        assert_wiring_parity(
            "notifications",
            [
                {
                    "sender_name": "Combined",
                    "sender_email": "combined@example.com",
                    "reply_to_email": "reply@example.com",
                    "webhook_ttl_seconds": 120,
                }
            ],
        )


class TestNotificationsWiringParityBatchCases:
    """Run multiple option cases through the harness in a single call."""

    def test_multiple_cases_in_one_call(self) -> None:
        assert_wiring_parity(
            "notifications",
            [
                {},
                {"enabled": False},
                {"sender_name": "Batch Sender"},
                {
                    "sender_name": "Live",
                    "sender_email": "live@myapp.com",
                    "resend_domain": "myapp.com",
                    "resend_api_key_env_var": "RESEND_API_KEY",
                },
            ],
        )
