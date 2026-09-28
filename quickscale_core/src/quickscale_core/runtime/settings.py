"""Versioned settings facade for generated QuickScale projects.

This module is the single declaration of the executable runtime contracts that
generated projects used to inline in their user-owned ``settings/base.py`` and
``settings/production.py`` files.  Generated settings import these symbols and
keep only their user configuration, so a contract fix ships through the
``quickscale-core`` lockstep pin instead of reaching only freshly generated
projects.

Public API (SA206):

* :class:`ClientIdentityMiddleware` and :class:`CorrelationIdMiddleware` — the
  generated project's first-position middleware.
* :func:`validated_proxy_settings`, :func:`num_proxies_for`, and
  :func:`secure_proxy_ssl_header` — the trusted-proxy client-IP derivation
  shared by the middleware, the canonical client-IP resolver, and DRF's
  ``NUM_PROXIES`` throttle path.
* :func:`require_production_secret_key` — the production SECRET_KEY guard.
* :data:`KNOWN_PRIVILEGED_COMMANDS`, :data:`KNOWN_NON_DB_COMMANDS`, and
  :func:`resolve_runtime_database_url` — the launcher one-shot command-mode
  contract and the privileged/runtime database selection.
* :class:`CorrelationIdFilter` and :class:`JsonFormatter` — the structured
  logging helpers that consume the correlation context variable.

The import path ``quickscale_core.runtime.settings`` is public API; existing
projects adopt it through a declared contract step.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

__all__ = [
    "ClientIdentityMiddleware",
    "CorrelationIdFilter",
    "CorrelationIdMiddleware",
    "JsonFormatter",
    "KNOWN_NON_DB_COMMANDS",
    "KNOWN_PRIVILEGED_COMMANDS",
    "NON_DB_FALLBACK_DATABASE_URL",
    "SHIPPED_INSECURE_DEFAULT",
    "correlation_id_var",
    "num_proxies_for",
    "require_production_secret_key",
    "resolve_runtime_database_url",
    "secure_proxy_ssl_header",
    "validated_proxy_settings",
]

# ── Trusted-proxy client-IP resolution ───────────────────────────────
#
# ``USE_X_FORWARDED_FOR`` and ``TRUSTED_PROXY_COUNT`` are user configuration in
# the generated settings.  The derivation below is the contract: the client IP
# is extracted at position ``-TRUSTED_PROXY_COUNT`` (the Nth entry from the
# right) in the ``X-Forwarded-For`` chain, and every consumer observes the same
# fail-closed forwarding state.

_FORWARDED_FOR_META_KEY = "HTTP_X_FORWARDED_FOR"


def validated_proxy_settings() -> tuple[bool, int]:
    """Return the fail-loud trusted-proxy configuration."""
    try:
        use_xff = settings.USE_X_FORWARDED_FOR
    except AttributeError as exc:
        raise ImproperlyConfigured("USE_X_FORWARDED_FOR setting is required.") from exc
    if not isinstance(use_xff, bool):
        raise ImproperlyConfigured(
            f"USE_X_FORWARDED_FOR must be a bool, got {use_xff!r}"
        )

    try:
        proxy_count = settings.TRUSTED_PROXY_COUNT
    except AttributeError as exc:
        raise ImproperlyConfigured("TRUSTED_PROXY_COUNT setting is required.") from exc
    if isinstance(proxy_count, bool) or not isinstance(proxy_count, int):
        raise ImproperlyConfigured(
            f"TRUSTED_PROXY_COUNT must be a non-negative integer, got {proxy_count!r}"
        )
    if proxy_count < 0:
        raise ImproperlyConfigured(
            f"TRUSTED_PROXY_COUNT must be a non-negative integer, got {proxy_count}"
        )

    return use_xff, proxy_count


def num_proxies_for(use_x_forwarded_for: bool, trusted_proxy_count: int) -> int | None:
    """Return DRF's right-indexed ``NUM_PROXIES`` value for the trust state."""
    return trusted_proxy_count if use_x_forwarded_for else None


def secure_proxy_ssl_header(use_x_forwarded_for: bool) -> tuple[str, str] | None:
    """Trust ``X-Forwarded-Proto`` only while forwarding trust is enabled."""
    return ("HTTP_X_FORWARDED_PROTO", "https") if use_x_forwarded_for else None


def normalize_client_ip_headers(request: object) -> None:
    """Normalize XFF once so canonical and ordinary DRF consumers agree."""
    use_xff, proxy_count = validated_proxy_settings()
    request_meta = getattr(request, "META", {})
    forwarded_for = request_meta.get(_FORWARDED_FOR_META_KEY)

    if not use_xff or proxy_count == 0 or not isinstance(forwarded_for, str):
        request_meta.pop(_FORWARDED_FOR_META_KEY, None)
        return

    forwarded_hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    if len(forwarded_hops) < proxy_count:
        request_meta.pop(_FORWARDED_FOR_META_KEY, None)
        return

    request_meta[_FORWARDED_FOR_META_KEY] = ", ".join(forwarded_hops)


class ClientIdentityMiddleware:
    """Establish the generated project's shared fail-closed identity seam."""

    def __init__(self, get_response: object) -> None:
        self.get_response = get_response

    def __call__(self, request: object) -> object:
        normalize_client_ip_headers(request)
        return self.get_response(request)  # type: ignore[operator]


# ── Structured logging and correlation ID support ────────────────────


# Context variable that bridges the middleware correlation_id to the
# logging filter without coupling the filter to Django internals or
# requiring thread-local cleanup.
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)

# Bounded shape for a client-supplied ``X-Request-ID``.  Trace ids built from
# these characters pass through unchanged; anything longer or outside the
# character class is replaced by a generated UUID, so one oversized header
# cannot multiply the request's log footprint by its record count.
_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class CorrelationIdFilter(logging.Filter):
    """Add a ``correlation_id`` attribute to every log record.

    The middleware (:class:`CorrelationIdMiddleware`) stamps each request
    with a ``correlation_id`` (from the ``X-Request-ID`` header or a new
    UUID) and stores it in the ``correlation_id_var`` context variable.
    This filter reads that per-request value into the record so that
    formatters (including :class:`JsonFormatter`) can emit it.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging.

    Renders every log line as a single JSON object with ``timestamp``,
    ``level``, ``logger``, ``module``, ``message``, and
    ``correlation_id`` keys.  Exception tracebacks are included under an
    ``exception`` key when present.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, object] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", ""),
        }
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, default=str)


class CorrelationIdMiddleware:
    """Ensure every request carries a traceable ``correlation_id``.

    Reads the ``X-Request-ID`` header when it matches
    ``_CORRELATION_ID_PATTERN`` (at most 64 characters drawn from
    ``[A-Za-z0-9._-]``), allowing front-end proxies or clients to propagate
    an existing ID.  Any other value — absent, oversized, or carrying
    characters outside that class — is discarded and a fresh UUID is
    generated instead, so client input cannot inflate the size of every log
    line the request emits.  The ID is exposed on ``request.correlation_id``
    and set as the ``X-Request-ID`` response header so downstream consumers
    can correlate requests end-to-end.
    """

    def __init__(self, get_response: object) -> None:
        self.get_response = get_response

    def __call__(self, request: object) -> object:
        client_request_id = getattr(request, "META", {}).get("HTTP_X_REQUEST_ID")
        if isinstance(client_request_id, str) and _CORRELATION_ID_PATTERN.fullmatch(
            client_request_id
        ):
            correlation_id = client_request_id
        else:
            correlation_id = str(uuid.uuid4())
        request.correlation_id = correlation_id  # type: ignore[attr-defined]
        correlation_id_var.set(correlation_id)
        response = self.get_response(request)  # type: ignore[operator]
        response["X-Request-ID"] = correlation_id
        return response


# ── Production SECRET_KEY guard ──────────────────────────────────────

# The deliberately insecure value the generator ships until the operator
# sets a real SECRET_KEY; named as a shipped default, not a credential.
SHIPPED_INSECURE_DEFAULT = "django-insecure-change-this-in-production"


def require_production_secret_key(secret_key: object) -> str:
    """Reject blank or shipped placeholder SECRET_KEY values in production."""
    normalized_secret_key = str(secret_key).strip()
    if not normalized_secret_key or normalized_secret_key == SHIPPED_INSECURE_DEFAULT:
        raise ValueError(
            "SECRET_KEY must be set to a non-empty, non-default value in "
            "production. Generate one with: "
            "python -c 'from django.core.management.utils import "
            "get_random_secret_key; print(get_random_secret_key())'"
        )
    return normalized_secret_key


# ── Launcher one-shot command-mode contract ──────────────────────────

KNOWN_PRIVILEGED_COMMANDS = frozenset({"migrate", "createcachetable"})
KNOWN_NON_DB_COMMANDS = frozenset({"collectstatic", "compilemessages"})
NON_DB_FALLBACK_DATABASE_URL = "postgresql://dummy:dummy@localhost:5432/dummy"


def resolve_runtime_database_url(
    *,
    runtime_database_url: str | None,
    database_url: str | None,
    privileged_command: str = "",
    non_db_command: str = "",
    allow_bypass_rls: bool = False,
) -> str:
    """Select the database URL for the active launcher command mode.

    Fails closed with the same messages the generated production settings have
    always raised.  ``QUICKSCALE_PRIVILEGED_COMMAND`` and
    ``QUICKSCALE_NON_DB_COMMAND`` are mutually exclusive; a privileged command
    requires an explicitly blank ``RUNTIME_DATABASE_URL`` and a superuser
    ``DATABASE_URL``; a non-DB bootstrap command may run without a database;
    runtime serving requires ``RUNTIME_DATABASE_URL`` unless the explicit
    ``QUICKSCALE_ALLOW_BYPASSRLS=1`` opt-out bridges to ``DATABASE_URL``.
    """
    if privileged_command and non_db_command:
        raise ValueError(
            "Both QUICKSCALE_PRIVILEGED_COMMAND and QUICKSCALE_NON_DB_COMMAND "
            "are set. These modes are mutually exclusive. "
            "Set only one command-mode variable at a time."
        )

    if privileged_command:
        # Privileged DB command: validate and require superuser DATABASE_URL
        if privileged_command not in KNOWN_PRIVILEGED_COMMANDS:
            raise ValueError(
                f"Unknown QUICKSCALE_PRIVILEGED_COMMAND value {privileged_command!r}. "
                f"Supported values: {', '.join(sorted(KNOWN_PRIVILEGED_COMMANDS))}."
            )
        if runtime_database_url is None or runtime_database_url != "":
            raise ValueError(
                "RUNTIME_DATABASE_URL must be explicitly blank when "
                "QUICKSCALE_PRIVILEGED_COMMAND is set. "
                'Set RUNTIME_DATABASE_URL="" alongside the privileged command.'
            )
        if not database_url:
            raise ValueError(
                "DATABASE_URL is required for privileged database commands. "
                "Set DATABASE_URL to the superuser connection string."
            )
        return database_url

    if non_db_command:
        # Non-DB bootstrap command: validate, provide dummy URL if needed
        if non_db_command not in KNOWN_NON_DB_COMMANDS:
            raise ValueError(
                f"Unknown QUICKSCALE_NON_DB_COMMAND value {non_db_command!r}. "
                f"Supported values: {', '.join(sorted(KNOWN_NON_DB_COMMANDS))}."
            )
        return database_url or NON_DB_FALLBACK_DATABASE_URL

    if runtime_database_url:
        return runtime_database_url

    if runtime_database_url == "" and allow_bypass_rls:
        # Explicit non-serving dev/test opt-out: bridge to DATABASE_URL
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is not set or is empty. "
                "QUICKSCALE_ALLOW_BYPASSRLS=1 requires the superuser "
                "DATABASE_URL for privileged operations. "
                "Ensure the database service is linked to your app service."
            )
        return database_url

    # Runtime serving: fail closed — RUNTIME_DATABASE_URL is required
    raise ValueError(
        "RUNTIME_DATABASE_URL is required for runtime serving. "
        "The restricted NOSUPERUSER/NOBYPASSRLS database role connection "
        "string must be provided when serving requests. "
        "Set RUNTIME_DATABASE_URL in your environment to the runtime role's "
        "PostgreSQL connection string. "
        "For privileged commands, the deployment script (start.sh) "
        "automatically sets QUICKSCALE_PRIVILEGED_COMMAND and clears "
        "RUNTIME_DATABASE_URL so the superuser DATABASE_URL is used instead."
    )
