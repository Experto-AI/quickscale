"""Tests for analytics runtime services."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, override_settings

from quickscale_modules_analytics.events import (
    ANALYTICS_EVENT_FORM_SUBMIT,
    ANALYTICS_EVENT_SOCIAL_LINK_CLICK,
)
from quickscale_modules_analytics import services


class DummyClient:
    """Minimal fake PostHog client used by service tests."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.captures: list[tuple[str, str, dict[str, Any] | None]] = []
        self.disabled = kwargs.get("disabled", False)
        self.shutdown_called = False

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        self.captures.append((distinct_id, event, properties))

    def shutdown(self) -> None:
        self.shutdown_called = True


class DummyPosthogModule:
    """Fake PostHog module exposing the constructor used by services."""

    def __init__(self) -> None:
        self.clients: list[DummyClient] = []

    def Posthog(self, **kwargs: Any) -> DummyClient:  # noqa: N802 - mimics library API
        client = DummyClient(**kwargs)
        self.clients.append(client)
        return client


class LegacyPosthogModule:
    """Fallback PostHog module shape without a constructor helper."""

    def __init__(self) -> None:
        self.project_api_key = ""
        self.host = ""
        self.disabled = True

    def capture(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def shutdown(self) -> None:
        return None


class BrokenShutdownClient(DummyClient):
    """Client whose shutdown path raises to exercise the defensive branch."""

    def shutdown(self) -> None:
        raise RuntimeError("boom")


class LegacySignatureCaptureClient:
    """Client exposing the legacy positional capture signature only."""

    def __init__(self) -> None:
        self.disabled = False
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def capture(self, *args: Any, **kwargs: Any) -> None:
        if kwargs:
            raise TypeError("legacy positional signature")
        distinct_id, event, properties = args
        self.calls.append((distinct_id, event, properties))


class BrokenLegacyCaptureClient:
    """Client whose keyword and positional capture paths both fail."""

    def __init__(self) -> None:
        self.disabled = False

    def capture(self, *args: Any, **kwargs: Any) -> None:
        if kwargs:
            raise TypeError("legacy positional signature")
        raise RuntimeError("capture failed")


class BrokenCaptureClient:
    """Client whose capture path fails immediately."""

    def __init__(self) -> None:
        self.disabled = False

    def capture(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise RuntimeError("capture failed")


@pytest.fixture(autouse=True)
def reset_analytics_state() -> None:
    """Reset global analytics client state between tests."""
    services._close_existing_client()
    services._ANALYTICS_LAST_SETTINGS = None
    services._ANALYTICS_DISABLED_REASON = "unconfigured"
    yield
    services._close_existing_client()
    services._ANALYTICS_LAST_SETTINGS = None
    services._ANALYTICS_DISABLED_REASON = "unconfigured"


def _add_session(request) -> None:
    middleware = SessionMiddleware(lambda _: None)
    middleware.process_request(request)
    request.session.save()


def _snapshot(**overrides: Any) -> services.AnalyticsRuntimeSettingsSnapshot:
    """Build a runtime snapshot with sensible analytics defaults."""
    defaults: dict[str, Any] = {
        "enabled": True,
        "provider": services.ANALYTICS_PROVIDER_POSTHOG,
        "posthog_api_key_env_var": services.DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
        "posthog_host_env_var": services.DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
        "posthog_host": services.ANALYTICS_POSTHOG_DEFAULT_HOST,
        "exclude_debug": False,
        "exclude_staff": False,
        "anonymous_by_default": True,
    }
    defaults.update(overrides)
    return services.AnalyticsRuntimeSettingsSnapshot(**defaults)


def test_close_existing_client_swallow_shutdown_errors(caplog) -> None:
    """Analytics shutdown failures should never leak to callers."""
    services._ANALYTICS_CLIENT = BrokenShutdownClient()

    caplog.set_level(logging.DEBUG, logger=services.__name__)
    services._close_existing_client()

    assert services._ANALYTICS_CLIENT is None
    assert "client shutdown failed" in caplog.text


def test_analytics_enabled_for_request_rejects_disabled_and_unsupported_snapshots() -> (
    None
):
    """Disabled runtimes and unsupported providers must stay template-inactive."""
    assert (
        services.analytics_enabled_for_request(None, _snapshot(enabled=False)) is False
    )
    assert (
        services.analytics_enabled_for_request(None, _snapshot(provider="plausible"))
        is False
    )


@override_settings(DEBUG=True)
def test_analytics_enabled_for_request_rejects_debug_requests_when_excluded() -> None:
    """DEBUG exclusion should suppress analytics exposure even with valid config."""
    assert (
        services.analytics_enabled_for_request(None, _snapshot(exclude_debug=True))
        is False
    )


@override_settings(DEBUG=True, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=True)
def test_configure_analytics_client_disables_in_debug_mode() -> None:
    """Analytics should stay disabled in DEBUG mode when exclude_debug is true."""
    assert services.configure_analytics_client() is False
    assert services.is_analytics_active() is False


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_configure_analytics_client_warns_when_api_key_missing() -> None:
    """Missing PostHog API keys should disable runtime capture safely."""
    with patch("quickscale_modules_analytics.services.warnings.warn") as mock_warn:
        assert services.configure_analytics_client() is False

    mock_warn.assert_called_once()
    assert services.is_analytics_active() is False


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_ENABLED=False)
def test_configure_analytics_client_disables_when_runtime_is_off() -> None:
    """Disabled analytics settings should keep the client in an explicit off state."""
    assert services.configure_analytics_client() is False
    assert services._ANALYTICS_DISABLED_REASON == "disabled"


def test_configure_analytics_client_defaults_missing_enabled_setting_to_enabled(
    monkeypatch,
) -> None:
    """Missing analytics wiring should preserve the shipped enabled-by-default runtime."""
    runtime_settings = SimpleNamespace(
        DEBUG=False,
        QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False,
    )
    fake_posthog = DummyPosthogModule()
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    with (
        patch(
            "quickscale_modules_analytics.services.settings",
            runtime_settings,
        ),
        patch(
            "quickscale_modules_analytics.services.import_module",
            return_value=fake_posthog,
        ),
    ):
        assert services.get_analytics_runtime_settings().enabled is True
        assert services.configure_analytics_client() is True
        assert services.is_analytics_active() is True

    assert len(fake_posthog.clients) == 1


@override_settings(
    DEBUG=False,
    QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False,
    QUICKSCALE_ANALYTICS_PROVIDER="plausible",
)
def test_configure_analytics_client_rejects_unsupported_providers(caplog) -> None:
    """Only the approved PostHog provider should initialize in v0.80.0."""
    caplog.set_level(logging.WARNING, logger=services.__name__)

    assert services.configure_analytics_client() is False

    assert services._ANALYTICS_DISABLED_REASON == "unsupported-provider"
    assert "only supports the PostHog provider" in caplog.text


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_configure_analytics_client_initializes_posthog_client(monkeypatch) -> None:
    """Analytics should initialize a PostHog client from env vars and settings."""
    fake_posthog = DummyPosthogModule()
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    monkeypatch.setenv("POSTHOG_HOST", "https://eu.i.posthog.com")

    with patch(
        "quickscale_modules_analytics.services.import_module",
        return_value=fake_posthog,
    ):
        assert services.configure_analytics_client() is True

    assert services.is_analytics_active() is True
    assert len(fake_posthog.clients) == 1
    client = fake_posthog.clients[0]
    assert client.kwargs["project_api_key"] == "test-posthog-key"
    assert client.kwargs["host"] == "https://eu.i.posthog.com"
    assert client.kwargs["sync_mode"] is False
    assert client.kwargs["disable_geoip"] is True


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_configure_analytics_client_reuses_cached_settings(monkeypatch) -> None:
    """Repeated setup calls should short-circuit when the runtime snapshot is unchanged."""
    fake_posthog = DummyPosthogModule()
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    with patch(
        "quickscale_modules_analytics.services.import_module",
        return_value=fake_posthog,
    ):
        assert services.configure_analytics_client() is True

    with patch(
        "quickscale_modules_analytics.services.import_module",
        side_effect=AssertionError("cached configuration should not re-import posthog"),
    ):
        assert services.configure_analytics_client() is True


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_configure_analytics_client_disables_when_sdk_is_missing(
    monkeypatch,
    caplog,
) -> None:
    """Import failures should degrade analytics to a safe disabled state."""
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    caplog.set_level(logging.WARNING, logger=services.__name__)

    with patch(
        "quickscale_modules_analytics.services.import_module",
        side_effect=ImportError("posthog not installed"),
    ):
        assert services.configure_analytics_client() is False

    assert services._ANALYTICS_DISABLED_REASON == "missing-sdk"
    assert "could not import the PostHog SDK" in caplog.text


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_configure_analytics_client_supports_module_style_posthog_fallback(
    monkeypatch,
) -> None:
    """Older module-style PostHog SDK shapes should still be configured safely."""
    legacy_module = LegacyPosthogModule()
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    monkeypatch.setenv("POSTHOG_HOST", "https://eu.i.posthog.com")

    with patch(
        "quickscale_modules_analytics.services.import_module",
        return_value=legacy_module,
    ):
        assert services.configure_analytics_client() is True

    assert legacy_module.project_api_key == "test-posthog-key"
    assert legacy_module.host == "https://eu.i.posthog.com"
    assert legacy_module.disabled is False


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_configure_analytics_client_handles_factory_initialization_errors(
    monkeypatch,
    caplog,
) -> None:
    """SDK constructor failures should disable analytics without breaking startup."""

    class BrokenPosthogModule:
        def Posthog(self, **kwargs: Any) -> DummyClient:  # noqa: N802 - library API
            del kwargs
            raise RuntimeError("boom")

    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    caplog.set_level(logging.WARNING, logger=services.__name__)

    with patch(
        "quickscale_modules_analytics.services.import_module",
        return_value=BrokenPosthogModule(),
    ):
        assert services.configure_analytics_client() is False

    assert services._ANALYTICS_DISABLED_REASON == "init-error"
    assert "failed to initialize the PostHog client" in caplog.text


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_capture_event_uses_active_client(monkeypatch) -> None:
    """capture_event should forward events to the configured PostHog client."""
    fake_posthog = DummyPosthogModule()
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    with patch(
        "quickscale_modules_analytics.services.import_module",
        return_value=fake_posthog,
    ):
        assert services.configure_analytics_client() is True

    services.capture_event("session:abc", "custom_event", {"source": "test"})

    assert fake_posthog.clients[0].captures == [
        ("session:abc", "custom_event", {"source": "test"})
    ]


def test_is_analytics_active_reconfigures_when_settings_change() -> None:
    """Active-state checks should refresh the client when runtime settings drift."""
    services._ANALYTICS_CLIENT = None
    services._ANALYTICS_LAST_SETTINGS = None

    with (
        patch(
            "quickscale_modules_analytics.services.get_analytics_runtime_settings",
            return_value=_snapshot(),
        ),
        patch(
            "quickscale_modules_analytics.services.configure_analytics_client"
        ) as mock_configure,
    ):
        assert services.is_analytics_active() is False

    mock_configure.assert_called_once_with()


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_capture_form_submit_uses_canonical_payload(monkeypatch) -> None:
    """capture_form_submit should emit the stable forms event payload."""
    fake_posthog = DummyPosthogModule()
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    with patch(
        "quickscale_modules_analytics.services.import_module",
        return_value=fake_posthog,
    ):
        services.configure_analytics_client()

    services.capture_form_submit(
        "session:abc",
        42,
        "Contact",
        {"source": "landing"},
    )

    assert fake_posthog.clients[0].captures == [
        (
            "session:abc",
            ANALYTICS_EVENT_FORM_SUBMIT,
            {
                "source": "landing",
                "module": "forms",
                "form_id": "42",
                "form_name": "Contact",
            },
        )
    ]


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_capture_social_link_click_uses_canonical_payload(monkeypatch) -> None:
    """capture_social_link_click should emit the stable social event payload."""
    fake_posthog = DummyPosthogModule()
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    with patch(
        "quickscale_modules_analytics.services.import_module",
        return_value=fake_posthog,
    ):
        services.configure_analytics_client()

    services.capture_social_link_click(
        "session:abc",
        "YouTube",
        "99",
        {"surface": "public"},
    )

    assert fake_posthog.clients[0].captures == [
        (
            "session:abc",
            ANALYTICS_EVENT_SOCIAL_LINK_CLICK,
            {
                "surface": "public",
                "module": "social",
                "provider": "youtube",
                "link_id": "99",
            },
        )
    ]


@pytest.mark.django_db()
@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT=False)
def test_get_distinct_id_uses_user_pk_when_opted_in(rf: RequestFactory) -> None:
    """Authenticated users should be used as the distinct ID when allowed."""
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="analytics-user",
        email="analytics-user@example.com",
        password="password123",
    )
    request = rf.get("/")
    _add_session(request)
    request.user = user

    assert services.get_distinct_id(request) == str(user.pk)


@pytest.mark.django_db()
def test_get_distinct_id_defaults_to_session_key(rf: RequestFactory) -> None:
    """Anonymous-by-default mode should use a stable session-scoped identifier."""
    request = rf.get("/")
    _add_session(request)
    request.user = SimpleNamespace(is_authenticated=False, is_staff=False)

    distinct_id = services.get_distinct_id(request)

    assert distinct_id.startswith("session:")
    assert distinct_id != "anonymous"


@override_settings(QUICKSCALE_ANALYTICS_EXCLUDE_STAFF=True)
def test_get_distinct_id_returns_blank_for_excluded_staff(
    rf: RequestFactory,
) -> None:
    """Excluded staff requests should not receive a captureable distinct ID."""
    request = rf.get("/")
    request.user = SimpleNamespace(is_authenticated=True, is_staff=True, pk=42)

    assert services.get_distinct_id(request) == ""


def test_get_distinct_id_creates_session_key_when_missing(rf: RequestFactory) -> None:
    """Session-backed anonymous IDs should bootstrap a session key when possible."""

    class SessionWithCreate:
        def __init__(self) -> None:
            self.session_key: str | None = None

        def create(self) -> None:
            self.session_key = "created-session-key"

    request = rf.get("/")
    request.user = SimpleNamespace(is_authenticated=False, is_staff=False)
    request.session = SessionWithCreate()

    assert services.get_distinct_id(request) == "session:created-session-key"


def test_get_distinct_id_uses_save_when_create_is_unavailable(
    rf: RequestFactory,
) -> None:
    """The distinct-id helper should fall back to session.save() when needed."""

    class SessionWithSave:
        def __init__(self) -> None:
            self.session_key: str | None = None

        def save(self) -> None:
            self.session_key = "saved-session-key"

    request = rf.get("/")
    request.user = SimpleNamespace(is_authenticated=False, is_staff=False)
    request.session = SessionWithSave()

    assert services.get_distinct_id(request) == "session:saved-session-key"


def test_get_distinct_id_returns_anonymous_when_session_bootstrap_fails(
    rf: RequestFactory,
    caplog,
) -> None:
    """Session initialization failures should degrade to a stable anonymous ID."""

    class BrokenSession:
        session_key: str | None = None

        def create(self) -> None:
            raise RuntimeError("boom")

    request = rf.get("/")
    request.user = SimpleNamespace(is_authenticated=False, is_staff=False)
    request.session = BrokenSession()

    caplog.set_level(logging.DEBUG, logger=services.__name__)

    assert services.get_distinct_id(request) == "anonymous"
    assert "could not initialize a session key" in caplog.text


@pytest.mark.django_db()
@override_settings(
    DEBUG=False,
    QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False,
    QUICKSCALE_ANALYTICS_EXCLUDE_STAFF=True,
)
def test_template_context_disables_tracking_for_staff(
    monkeypatch, rf: RequestFactory
) -> None:
    """Staff exclusion should suppress template-exposed analytics values."""
    user_model = get_user_model()
    staff_user = user_model.objects.create_user(
        username="analytics-staff",
        email="analytics-staff@example.com",
        password="password123",
        is_staff=True,
    )
    request = rf.get("/")
    _add_session(request)
    request.user = staff_user
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    context = services.get_template_analytics_context(request)

    assert context["enabled"] is False
    assert context["posthog_api_key"] == ""


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_template_context_resolves_runtime_env_vars(monkeypatch) -> None:
    """Template context should resolve runtime env vars without persisting them."""
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    monkeypatch.setenv("POSTHOG_HOST", "https://eu.i.posthog.com")

    context = services.get_template_analytics_context()

    assert context["enabled"] is True
    assert context["posthog_api_key"] == "test-posthog-key"
    assert context["posthog_host"] == "https://eu.i.posthog.com"


def test_capture_event_returns_early_when_runtime_is_inactive() -> None:
    """Inactive analytics runtimes should ignore capture calls without side effects."""
    client = DummyClient()
    services._ANALYTICS_CLIENT = client

    with patch(
        "quickscale_modules_analytics.services.is_analytics_active",
        return_value=False,
    ):
        services.capture_event("session:abc", "custom_event", {"source": "test"})

    assert client.captures == []


def test_capture_event_ignores_non_callable_client_capture() -> None:
    """Capture helpers should no-op when the resolved client has no callable capture."""
    services._ANALYTICS_CLIENT = SimpleNamespace(disabled=False, capture="not-callable")

    with patch(
        "quickscale_modules_analytics.services.is_analytics_active",
        return_value=True,
    ):
        services.capture_event("session:abc", "custom_event", {"source": "test"})


def test_capture_event_falls_back_to_legacy_positional_signature() -> None:
    """Legacy PostHog client signatures should still receive event payloads."""
    client = LegacySignatureCaptureClient()
    services._ANALYTICS_CLIENT = client

    with patch(
        "quickscale_modules_analytics.services.is_analytics_active",
        return_value=True,
    ):
        services.capture_event("session:abc", "legacy_event", {"source": "test"})

    assert client.calls == [("session:abc", "legacy_event", {"source": "test"})]


def test_capture_event_logs_when_legacy_fallback_fails(caplog) -> None:
    """Legacy fallback failures should be logged and swallowed."""
    services._ANALYTICS_CLIENT = BrokenLegacyCaptureClient()
    caplog.set_level(logging.WARNING, logger=services.__name__)

    with patch(
        "quickscale_modules_analytics.services.is_analytics_active",
        return_value=True,
    ):
        services.capture_event("session:abc", "broken_event", {"source": "test"})

    assert "failed to capture event 'broken_event'" in caplog.text


def test_capture_event_logs_generic_client_errors(caplog) -> None:
    """Unexpected capture exceptions should stay non-blocking and logged."""
    services._ANALYTICS_CLIENT = BrokenCaptureClient()
    caplog.set_level(logging.WARNING, logger=services.__name__)

    with patch(
        "quickscale_modules_analytics.services.is_analytics_active",
        return_value=True,
    ):
        services.capture_event("session:abc", "broken_event", {"source": "test"})

    assert "failed to capture event 'broken_event'" in caplog.text
