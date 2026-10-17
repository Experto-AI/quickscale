"""Focused tests for the notifications manifest adapter."""

from __future__ import annotations

import copy
import importlib

import pytest

from quickscale_core.manifest import (
    ManifestError,
    build_generic_manifest_spec,
    load_module_manifest,
)
from quickscale_modules_notifications.adapter import (
    _notifications_manifest_adapter,
    get_manifest_adapter,
    notifications_live_delivery_configured,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert get_manifest_adapter() is _notifications_manifest_adapter


def test_manifest_owns_the_notifications_mount() -> None:
    """Rule 7: the manifest's url_includes is the mount's only home."""
    spec = build_generic_manifest_spec("notifications", {})

    assert spec.url_includes == (
        ("notifications/", "quickscale_modules_notifications.urls"),
    )
    assert spec.pre_home_url_includes == ()


def test_default_delivery_is_console_safe() -> None:
    spec = _notifications_manifest_adapter({})

    # The manifest's apps projection is the sole INSTALLED_APPS
    # authority, so anymail is installed whenever the module is; the console
    # backend is selected at runtime until live delivery is configured.
    assert "anymail" in spec.apps
    assert spec.settings["EMAIL_BACKEND"] == (
        "django.core.mail.backends.console.EmailBackend"
    )
    assert spec.settings["DEFAULT_FROM_EMAIL"] == "noreply@example.com"
    assert (
        "notifications/",
        "quickscale_modules_notifications.urls",
    ) in spec.url_includes


def test_live_resend_delivery_sets_email_settings() -> None:
    spec = _notifications_manifest_adapter(
        {
            "sender_name": "Ops",
            "sender_email": "ops@example.com",
            "resend_domain": "mg.example.com",
            "resend_api_key_env_var": "OPS_RESEND_API_KEY",
        }
    )

    assert spec.apps[0] == "anymail"
    assert spec.settings["EMAIL_BACKEND"] == "anymail.backends.resend.EmailBackend"
    assert spec.settings["DEFAULT_FROM_EMAIL"] == "ops@example.com"
    assert spec.settings["SERVER_EMAIL"] == "ops@example.com"


def test_disabled_notifications_retain_email_settings() -> None:
    spec = _notifications_manifest_adapter({"enabled": False})

    assert "quickscale_modules_notifications" in spec.apps
    # Rule 1 (D3): the settings surface is retained while off; delivery is
    # refused at the runtime service boundary instead.
    assert spec.settings["EMAIL_BACKEND"] == (
        "django.core.mail.backends.console.EmailBackend"
    )
    assert spec.settings["DEFAULT_FROM_EMAIL"] == "noreply@example.com"
    assert spec.settings["SERVER_EMAIL"] == "noreply@example.com"


def test_adapter_projects_secret_settings_from_env_var_names() -> None:
    spec = _notifications_manifest_adapter({})

    assert (
        spec.settings["QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY"]
        == "__QS_ENV__:RESEND_API_KEY"
    )
    assert (
        spec.settings["QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"]
        == "__QS_ENV__:QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
    )


def test_adapter_projects_configured_resend_key_env_var_name() -> None:
    spec = _notifications_manifest_adapter(
        {
            "sender_name": "Ops",
            "sender_email": "ops@example.com",
            "resend_domain": "mg.example.com",
            "resend_api_key_env_var": "OPS_RESEND_API_KEY",
        }
    )

    assert (
        spec.settings["QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY"]
        == "__QS_ENV__:OPS_RESEND_API_KEY"
    )


def test_null_reply_to_email_is_refused() -> None:
    """A null option value is refused as the wrong raw type, never coerced."""
    with pytest.raises(ManifestError, match="QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL"):
        _notifications_manifest_adapter({"reply_to_email": None})


def test_sender_aliases_arrive_from_the_manifest_boundary() -> None:
    """DEFAULT_FROM_EMAIL/SERVER_EMAIL are manifest-declared sender aliases."""
    spec = _notifications_manifest_adapter({})

    assert spec.settings["DEFAULT_FROM_EMAIL"] == "noreply@example.com"
    assert spec.settings["SERVER_EMAIL"] == "noreply@example.com"


def test_live_delivery_follows_the_manifest_declared_rules(monkeypatch) -> None:
    """The predicate evaluates the declared validation, not a restated copy."""
    adapter_module = importlib.import_module("quickscale_modules_notifications.adapter")
    complete = {
        "sender_name": "Ops",
        "sender_email": "other@example.com",
        "resend_domain": "mg.example.com",
        "resend_api_key_env_var": "OPS_RESEND_API_KEY",
    }
    assert adapter_module.notifications_live_delivery_configured(complete)

    manifest = copy.deepcopy(load_module_manifest("notifications"))
    manifest.mutable_options["sender_email"].validation["pattern"] = (
        r"^ops@example\.com$"
    )
    monkeypatch.setattr(adapter_module, "load_module_manifest", lambda _name: manifest)

    assert not adapter_module.notifications_live_delivery_configured(complete)
    assert adapter_module.notifications_live_delivery_configured(
        {**complete, "sender_email": "ops@example.com"}
    )


def test_live_delivery_requires_a_usable_api_key_reference() -> None:
    """A blank reference is refused by the declared required_when rule.

    ``apply`` refuses this configuration too, so the predicate never counts a
    manifest-invalid configuration as live-ready.
    """
    complete = {
        "sender_name": "Ops",
        "sender_email": "ops@example.com",
        "resend_domain": "mg.example.com",
    }
    assert not notifications_live_delivery_configured(
        {**complete, "resend_api_key_env_var": ""}
    )
    assert not notifications_live_delivery_configured(
        {**complete, "resend_api_key_env_var": "   "}
    )
    assert notifications_live_delivery_configured(
        {**complete, "resend_api_key_env_var": "OPS_RESEND_API_KEY"}
    )


def test_live_delivery_requires_a_declared_sender_name_type() -> None:
    """The declared string type decides, not a ``str()`` coercion of it."""
    complete = {
        "sender_email": "ops@example.com",
        "resend_domain": "mg.example.com",
        "resend_api_key_env_var": "OPS_RESEND_API_KEY",
    }
    assert not notifications_live_delivery_configured({**complete, "sender_name": 123})
    assert not notifications_live_delivery_configured({**complete, "sender_name": None})
