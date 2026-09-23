"""Contract tests for the versioned runtime settings facade (SA206).

The facade is the single declaration of the executable contracts that
generated projects used to inline in their settings files.  These tests hold
the facade itself in place: the privileged-command allowlists, the
proxy-trust derivation, the correlation-ID middleware/filter pair, the
production SECRET_KEY guard, and the launcher command-mode selection.
"""

from __future__ import annotations

import contextvars
import logging
import types
import uuid

import pytest

from quickscale_core.runtime import settings as facade


class TestFacadePublicSurface:
    """The facade exposes every moved contract symbol."""

    def test_public_symbols_are_exported(self) -> None:
        expected = {
            "ClientIdentityMiddleware",
            "CorrelationIdFilter",
            "CorrelationIdMiddleware",
            "JsonFormatter",
            "KNOWN_NON_DB_COMMANDS",
            "KNOWN_PRIVILEGED_COMMANDS",
            "NON_DB_FALLBACK_DATABASE_URL",
            "correlation_id_var",
            "num_proxies_for",
            "require_production_secret_key",
            "resolve_runtime_database_url",
            "secure_proxy_ssl_header",
            "validated_proxy_settings",
        }
        assert expected <= set(facade.__all__)
        for symbol in expected:
            assert getattr(facade, symbol) is not None

    def test_privileged_and_non_db_allowlists(self) -> None:
        assert facade.KNOWN_PRIVILEGED_COMMANDS == frozenset(
            {"migrate", "createcachetable"}
        )
        assert facade.KNOWN_NON_DB_COMMANDS == frozenset(
            {"collectstatic", "compilemessages"}
        )

    def test_correlation_context_variable_is_a_contextvar(self) -> None:
        assert isinstance(facade.correlation_id_var, contextvars.ContextVar)
        assert facade.correlation_id_var.name == "correlation_id"


class TestProxyTrustDerivation:
    """The proxy-trust derivation is shared by every consumer."""

    def test_num_proxies_follows_forwarding_trust(self) -> None:
        assert facade.num_proxies_for(True, 3) == 3
        assert facade.num_proxies_for(False, 3) is None
        assert facade.num_proxies_for(True, 0) == 0

    def test_secure_proxy_ssl_header_follows_forwarding_trust(self) -> None:
        assert facade.secure_proxy_ssl_header(True) == (
            "HTTP_X_FORWARDED_PROTO",
            "https",
        )
        assert facade.secure_proxy_ssl_header(False) is None

    def test_validated_proxy_settings_accepts_valid_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            facade,
            "settings",
            types.SimpleNamespace(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=2),
        )
        assert facade.validated_proxy_settings() == (True, 2)

    @pytest.mark.parametrize(
        ("use_xff", "proxy_count"),
        [(None, 1), ("yes", 1), (True, None), (True, "1"), (True, -1), (True, True)],
    )
    def test_validated_proxy_settings_fails_loud(
        self,
        monkeypatch: pytest.MonkeyPatch,
        use_xff: object,
        proxy_count: object,
    ) -> None:
        from django.core.exceptions import ImproperlyConfigured

        monkeypatch.setattr(
            facade,
            "settings",
            types.SimpleNamespace(
                USE_X_FORWARDED_FOR=use_xff, TRUSTED_PROXY_COUNT=proxy_count
            ),
        )
        with pytest.raises(ImproperlyConfigured):
            facade.validated_proxy_settings()

    def test_client_identity_middleware_normalizes_and_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            facade,
            "settings",
            types.SimpleNamespace(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=2),
        )
        request = types.SimpleNamespace(
            META={"HTTP_X_FORWARDED_FOR": "attacker, client, proxy"}
        )
        seen: list[object] = []

        def get_response(normalized_request: object) -> object:
            seen.append(normalized_request)
            return "response"

        assert facade.ClientIdentityMiddleware(get_response)(request) == "response"
        assert request.META["HTTP_X_FORWARDED_FOR"] == "attacker, client, proxy"
        assert seen == [request]

        short_chain = types.SimpleNamespace(META={"HTTP_X_FORWARDED_FOR": "attacker"})
        facade.ClientIdentityMiddleware(get_response)(short_chain)
        assert "HTTP_X_FORWARDED_FOR" not in short_chain.META


class TestCorrelationIdContract:
    """The correlation middleware, filter, and formatter share one context var."""

    def test_middleware_stamps_request_and_response(self) -> None:
        request = types.SimpleNamespace(META={"HTTP_X_REQUEST_ID": "trace-1"})
        response: dict[str, str] = {}
        middleware = facade.CorrelationIdMiddleware(lambda _request: response)

        assert middleware(request) is response
        assert request.correlation_id == "trace-1"
        assert response["X-Request-ID"] == "trace-1"
        assert facade.correlation_id_var.get() == "trace-1"

    @pytest.mark.parametrize("client_value", ["a" * 10_240, "x" * 65, "bad:id", ""])
    def test_middleware_replaces_unusable_client_values(
        self, client_value: str
    ) -> None:
        request = types.SimpleNamespace(META={"HTTP_X_REQUEST_ID": client_value})
        response: dict[str, str] = {}
        facade.CorrelationIdMiddleware(lambda _request: response)(request)

        generated = request.correlation_id
        assert generated != client_value
        uuid.UUID(generated)
        assert response["X-Request-ID"] == generated

    def test_filter_reads_the_shared_context_variable(self) -> None:
        token = facade.correlation_id_var.set("req-abc")
        try:
            record = logging.LogRecord(
                "test", logging.INFO, __file__, 1, "message", (), None
            )
            assert facade.CorrelationIdFilter().filter(record) is True
            assert record.correlation_id == "req-abc"  # type: ignore[attr-defined]
        finally:
            facade.correlation_id_var.reset(token)

    def test_json_formatter_emits_correlation_id(self) -> None:
        token = facade.correlation_id_var.set("req-json")
        try:
            record = logging.LogRecord(
                "test", logging.INFO, __file__, 1, "message", (), None
            )
            facade.CorrelationIdFilter().filter(record)
            rendered = facade.JsonFormatter().format(record)
            assert '"correlation_id": "req-json"' in rendered
            assert '"message": "message"' in rendered
        finally:
            facade.correlation_id_var.reset(token)


class TestSecretKeyGuard:
    """The production SECRET_KEY guard rejects blank and shipped values."""

    def test_accepts_a_real_secret(self) -> None:
        assert facade.require_production_secret_key("  real-secret  ") == "real-secret"

    @pytest.mark.parametrize(
        "value", ["", "   ", "django-insecure-change-this-in-production"]
    )
    def test_rejects_blank_and_shipped_placeholder(self, value: object) -> None:
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            facade.require_production_secret_key(value)


class TestRuntimeDatabaseSelection:
    """The launcher command-mode selection keeps its fail-closed contract."""

    def test_privileged_command_selects_superuser_url(self) -> None:
        assert (
            facade.resolve_runtime_database_url(
                runtime_database_url="",
                database_url="postgresql://super:secret@db:5432/app",
                privileged_command="migrate",
            )
            == "postgresql://super:secret@db:5432/app"
        )

    def test_non_db_command_falls_back_to_dummy_url(self) -> None:
        assert (
            facade.resolve_runtime_database_url(
                runtime_database_url=None,
                database_url=None,
                non_db_command="collectstatic",
            )
            == facade.NON_DB_FALLBACK_DATABASE_URL
        )

    def test_runtime_url_is_selected_for_serving(self) -> None:
        assert (
            facade.resolve_runtime_database_url(
                runtime_database_url="postgresql://runtime:secret@db:5432/app",
                database_url="postgresql://super:secret@db:5432/app",
            )
            == "postgresql://runtime:secret@db:5432/app"
        )

    def test_bypass_opt_in_bridges_to_superuser_url(self) -> None:
        assert (
            facade.resolve_runtime_database_url(
                runtime_database_url="",
                database_url="postgresql://super:secret@db:5432/app",
                allow_bypass_rls=True,
            )
            == "postgresql://super:secret@db:5432/app"
        )

    def test_runtime_serving_fails_closed_without_runtime_url(self) -> None:
        with pytest.raises(ValueError, match="RUNTIME_DATABASE_URL is required"):
            facade.resolve_runtime_database_url(
                runtime_database_url=None,
                database_url="postgresql://super:secret@db:5432/app",
            )

    def test_command_modes_are_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            facade.resolve_runtime_database_url(
                runtime_database_url="",
                database_url="postgresql://super:secret@db:5432/app",
                privileged_command="migrate",
                non_db_command="collectstatic",
            )

    @pytest.mark.parametrize(
        ("privileged_command", "non_db_command", "expected"),
        [
            ("dropdb", "", "Unknown QUICKSCALE_PRIVILEGED_COMMAND"),
            ("", "shell", "Unknown QUICKSCALE_NON_DB_COMMAND"),
        ],
    )
    def test_unknown_commands_fail_closed(
        self, privileged_command: str, non_db_command: str, expected: str
    ) -> None:
        with pytest.raises(ValueError, match=expected):
            facade.resolve_runtime_database_url(
                runtime_database_url="",
                database_url="postgresql://super:secret@db:5432/app",
                privileged_command=privileged_command,
                non_db_command=non_db_command,
            )

    def test_privileged_command_requires_blank_runtime_url(self) -> None:
        with pytest.raises(ValueError, match="must be explicitly blank"):
            facade.resolve_runtime_database_url(
                runtime_database_url="postgresql://runtime:secret@db:5432/app",
                database_url="postgresql://super:secret@db:5432/app",
                privileged_command="migrate",
            )

    def test_privileged_command_requires_superuser_url(self) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL is required for privileged"):
            facade.resolve_runtime_database_url(
                runtime_database_url="",
                database_url=None,
                privileged_command="migrate",
            )
