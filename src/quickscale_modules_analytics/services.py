"""Runtime capture helpers for the QuickScale analytics module."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import logging
import os
from threading import Lock
from typing import Any, Protocol, cast
import warnings

from django.conf import settings
from django.http import HttpRequest

from quickscale_modules_analytics.events import (
    ANALYTICS_EVENT_FORM_SUBMIT,
    ANALYTICS_EVENT_SOCIAL_LINK_CLICK,
)

logger = logging.getLogger(__name__)

ANALYTICS_PROVIDER_POSTHOG = "posthog"
DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR = "POSTHOG_API_KEY"
DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR = "POSTHOG_HOST"
ANALYTICS_POSTHOG_DEFAULT_HOST = "https://us.i.posthog.com"


class AnalyticsClient(Protocol):
    """Minimal PostHog client protocol used by the runtime helpers."""

    disabled: bool

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any: ...

    def shutdown(self) -> None: ...


@dataclass(frozen=True)
class AnalyticsRuntimeSettingsSnapshot:
    """Immutable runtime view of the analytics settings contract."""

    enabled: bool
    provider: str
    posthog_api_key_env_var: str
    posthog_host_env_var: str
    posthog_host: str
    exclude_debug: bool
    exclude_staff: bool
    anonymous_by_default: bool

    @classmethod
    def from_settings(cls) -> AnalyticsRuntimeSettingsSnapshot:
        """Create a runtime snapshot from Django settings."""
        return cls(
            enabled=bool(getattr(settings, "QUICKSCALE_ANALYTICS_ENABLED", True)),
            provider=str(
                getattr(
                    settings,
                    "QUICKSCALE_ANALYTICS_PROVIDER",
                    ANALYTICS_PROVIDER_POSTHOG,
                )
            )
            .strip()
            .lower(),
            posthog_api_key_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
                    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
                )
            ).strip()
            or DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
            posthog_host_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
                    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
                )
            ).strip()
            or DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
            posthog_host=str(
                getattr(
                    settings,
                    "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
                    ANALYTICS_POSTHOG_DEFAULT_HOST,
                )
            ).strip()
            or ANALYTICS_POSTHOG_DEFAULT_HOST,
            exclude_debug=bool(
                getattr(settings, "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG", True)
            ),
            exclude_staff=bool(
                getattr(settings, "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF", False)
            ),
            anonymous_by_default=bool(
                getattr(
                    settings,
                    "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
                    True,
                )
            ),
        )

    def resolve_posthog_api_key(self) -> str:
        """Resolve the PostHog API key from the configured environment variable."""
        env_var_name = (
            self.posthog_api_key_env_var.strip()
            or DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR
        )
        return os.getenv(env_var_name, "").strip()

    def resolve_posthog_host(self) -> str:
        """Resolve the PostHog host from env vars with settings fallback."""
        env_var_name = (
            self.posthog_host_env_var.strip() or DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR
        )
        return (
            os.getenv(env_var_name, "").strip()
            or self.posthog_host.strip()
            or ANALYTICS_POSTHOG_DEFAULT_HOST
        )


_CLIENT_LOCK = Lock()
_ANALYTICS_CLIENT: AnalyticsClient | None = None
_ANALYTICS_LAST_SETTINGS: AnalyticsRuntimeSettingsSnapshot | None = None
_ANALYTICS_DISABLED_REASON: str = "unconfigured"


def get_analytics_runtime_settings() -> AnalyticsRuntimeSettingsSnapshot:
    """Return the active analytics settings snapshot."""
    return AnalyticsRuntimeSettingsSnapshot.from_settings()


def _close_existing_client() -> None:
    global _ANALYTICS_CLIENT

    shutdown = getattr(_ANALYTICS_CLIENT, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown()
        except Exception:
            logger.debug("QuickScale analytics client shutdown failed.", exc_info=True)
    _ANALYTICS_CLIENT = None


def _set_disabled_state(
    snapshot: AnalyticsRuntimeSettingsSnapshot,
    reason: str,
) -> bool:
    global _ANALYTICS_LAST_SETTINGS, _ANALYTICS_DISABLED_REASON

    _close_existing_client()
    _ANALYTICS_LAST_SETTINGS = snapshot
    _ANALYTICS_DISABLED_REASON = reason
    return False


def _request_is_staff(request: HttpRequest | None) -> bool:
    user = getattr(request, "user", None)
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_staff", False)
    )


def analytics_enabled_for_request(
    request: HttpRequest | None,
    runtime_settings: AnalyticsRuntimeSettingsSnapshot | None = None,
) -> bool:
    """Return whether analytics should be exposed for the current request."""
    snapshot = runtime_settings or get_analytics_runtime_settings()
    if not snapshot.enabled:
        return False
    if snapshot.provider != ANALYTICS_PROVIDER_POSTHOG:
        return False
    if snapshot.exclude_debug and bool(getattr(settings, "DEBUG", False)):
        return False
    if snapshot.exclude_staff and _request_is_staff(request):
        return False
    return bool(snapshot.resolve_posthog_api_key())


def configure_analytics_client() -> bool:
    """Initialize or disable the PostHog client based on current settings."""
    global _ANALYTICS_CLIENT, _ANALYTICS_LAST_SETTINGS, _ANALYTICS_DISABLED_REASON

    snapshot = get_analytics_runtime_settings()
    with _CLIENT_LOCK:
        if snapshot == _ANALYTICS_LAST_SETTINGS:
            return _ANALYTICS_CLIENT is not None and not bool(
                getattr(_ANALYTICS_CLIENT, "disabled", False)
            )

        if not snapshot.enabled:
            return _set_disabled_state(snapshot, "disabled")

        if snapshot.provider != ANALYTICS_PROVIDER_POSTHOG:
            logger.warning(
                "QuickScale analytics only supports the PostHog provider in v0.80.0."
            )
            return _set_disabled_state(snapshot, "unsupported-provider")

        if snapshot.exclude_debug and bool(getattr(settings, "DEBUG", False)):
            return _set_disabled_state(snapshot, "debug-excluded")

        api_key = snapshot.resolve_posthog_api_key()
        if not api_key:
            if not bool(getattr(settings, "DEBUG", False)):
                warnings.warn(
                    "QuickScale analytics is enabled but the PostHog API key env var is blank. Analytics capture remains disabled.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            return _set_disabled_state(snapshot, "missing-api-key")

        try:
            posthog_module = import_module("posthog")
        except ImportError:
            logger.warning(
                "QuickScale analytics could not import the PostHog SDK. Analytics capture remains disabled."
            )
            return _set_disabled_state(snapshot, "missing-sdk")

        try:
            factory = getattr(posthog_module, "Posthog", None)
            if callable(factory):
                client = cast(
                    AnalyticsClient,
                    factory(
                        project_api_key=api_key,
                        host=snapshot.resolve_posthog_host(),
                        sync_mode=False,
                        disabled=False,
                        disable_geoip=True,
                    ),
                )
            else:
                client = cast(AnalyticsClient, posthog_module)
                if hasattr(client, "project_api_key"):
                    setattr(client, "project_api_key", api_key)
                if hasattr(client, "host"):
                    setattr(client, "host", snapshot.resolve_posthog_host())
                if hasattr(client, "disabled"):
                    setattr(client, "disabled", False)

            _close_existing_client()
            _ANALYTICS_CLIENT = client
            _ANALYTICS_LAST_SETTINGS = snapshot
            _ANALYTICS_DISABLED_REASON = "active"
            return True
        except Exception:
            logger.warning(
                "QuickScale analytics failed to initialize the PostHog client. Analytics capture remains disabled.",
                exc_info=bool(getattr(settings, "DEBUG", False)),
            )
            return _set_disabled_state(snapshot, "init-error")


def is_analytics_active() -> bool:
    """Return whether analytics capture is active for the current settings."""
    snapshot = get_analytics_runtime_settings()
    if snapshot != _ANALYTICS_LAST_SETTINGS:
        configure_analytics_client()
    return _ANALYTICS_CLIENT is not None and not bool(
        getattr(_ANALYTICS_CLIENT, "disabled", False)
    )


def get_template_analytics_context(
    request: HttpRequest | None = None,
) -> dict[str, object]:
    """Return template-safe analytics config for manual template adoption."""
    snapshot = get_analytics_runtime_settings()
    enabled = analytics_enabled_for_request(request, snapshot)
    return {
        "enabled": enabled,
        "provider": snapshot.provider,
        "posthog_api_key": snapshot.resolve_posthog_api_key() if enabled else "",
        "posthog_api_key_env_var": snapshot.posthog_api_key_env_var,
        "posthog_host": snapshot.resolve_posthog_host(),
        "posthog_host_env_var": snapshot.posthog_host_env_var,
        "exclude_debug": snapshot.exclude_debug,
        "exclude_staff": snapshot.exclude_staff,
        "anonymous_by_default": snapshot.anonymous_by_default,
    }


def get_distinct_id(request: HttpRequest) -> str:
    """Return a stable distinct ID based on the runtime anonymity policy."""
    snapshot = get_analytics_runtime_settings()
    if snapshot.exclude_staff and _request_is_staff(request):
        return ""

    user = getattr(request, "user", None)
    if (
        not snapshot.anonymous_by_default
        and user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "pk", None) is not None
    ):
        return str(user.pk)

    session = getattr(request, "session", None)
    if session is not None:
        try:
            if session.session_key is None:
                if hasattr(session, "create"):
                    session.create()
                elif hasattr(session, "save"):
                    session.save()
        except Exception:
            logger.debug(
                "QuickScale analytics could not initialize a session key.",
                exc_info=True,
            )
        session_key = getattr(session, "session_key", None)
        if session_key:
            return f"session:{session_key}"

    return "anonymous"


def capture_event(
    distinct_id: str,
    event: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Capture an analytics event safely, never raising to callers."""
    if not distinct_id or not event or not is_analytics_active():
        return

    capture = getattr(_ANALYTICS_CLIENT, "capture", None)
    if not callable(capture):
        return

    payload = dict(properties or {})
    try:
        capture(distinct_id=distinct_id, event=event, properties=payload)
    except TypeError:
        try:
            capture(distinct_id, event, payload)
        except Exception:
            logger.warning(
                "QuickScale analytics failed to capture event '%s'.",
                event,
                exc_info=bool(getattr(settings, "DEBUG", False)),
            )
    except Exception:
        logger.warning(
            "QuickScale analytics failed to capture event '%s'.",
            event,
            exc_info=bool(getattr(settings, "DEBUG", False)),
        )


def capture_form_submit(
    distinct_id: str,
    form_id: int | str,
    form_name: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """Capture the canonical forms submission event payload."""
    properties = dict(extra or {})
    properties.update(
        {
            "module": "forms",
            "form_id": str(form_id),
            "form_name": form_name.strip(),
        }
    )
    capture_event(distinct_id, ANALYTICS_EVENT_FORM_SUBMIT, properties)


def capture_social_link_click(
    distinct_id: str,
    provider: str,
    link_id: int | str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Capture the canonical social link click event payload."""
    properties = dict(extra or {})
    properties.update(
        {
            "module": "social",
            "provider": str(provider).strip().lower(),
            "link_id": str(link_id),
        }
    )
    capture_event(distinct_id, ANALYTICS_EVENT_SOCIAL_LINK_CLICK, properties)


__all__ = [
    "ANALYTICS_POSTHOG_DEFAULT_HOST",
    "ANALYTICS_PROVIDER_POSTHOG",
    "AnalyticsRuntimeSettingsSnapshot",
    "analytics_enabled_for_request",
    "capture_event",
    "capture_form_submit",
    "capture_social_link_click",
    "configure_analytics_client",
    "get_analytics_runtime_settings",
    "get_distinct_id",
    "get_template_analytics_context",
    "is_analytics_active",
]
