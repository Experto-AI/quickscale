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
from django.core.exceptions import ImproperlyConfigured

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
            "compose_rest_framework",
            "correlation_id_var",
            "num_proxies_for",
            "require_production_media_backend",
            "require_production_secret_key",
            "require_redis_cache_client",
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


class TestRedisCacheClientGuard:
    """The Redis cache selection fails closed without its client."""

    def test_redis_url_without_client_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(facade.importlib.util, "find_spec", lambda name: None)

        with pytest.raises(
            ImproperlyConfigured, match="'redis' package is not installed"
        ):
            facade.require_redis_cache_client("redis://localhost:6379/0")

    def test_redis_url_with_client_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(facade.importlib.util, "find_spec", lambda name: object())

        facade.require_redis_cache_client("redis://localhost:6379/0")

    def test_no_redis_url_does_not_probe_the_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probed: list[str] = []
        monkeypatch.setattr(
            facade.importlib.util, "find_spec", lambda name: probed.append(name)
        )

        facade.require_redis_cache_client(None)

        assert probed == []


class TestProductionMediaBackendGuard:
    """Serving production traffic refuses container-local media."""

    def test_serving_refuses_filesystem_storage(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="FileSystemStorage"):
            facade.require_production_media_backend(
                {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}},
                allow_local_media=False,
                serving=True,
            )

    def test_serving_refuses_a_filesystem_subclass(self) -> None:
        from django.core.files.storage import FileSystemStorage

        class ProjectLocalStorage(FileSystemStorage):
            """A project subclass inherits the container-local loss path."""

        with pytest.raises(ImproperlyConfigured, match="FileSystemStorage"):
            facade.require_production_media_backend(
                {"default": {"BACKEND": ProjectLocalStorage}},
                allow_local_media=False,
                serving=True,
            )

    def test_explicit_dev_flag_allows_local_media(self) -> None:
        facade.require_production_media_backend(
            {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}},
            allow_local_media=True,
            serving=True,
        )

    def test_bootstrap_command_is_exempt(self) -> None:
        facade.require_production_media_backend(
            {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}},
            allow_local_media=False,
            serving=False,
        )

    def test_object_storage_passes(self) -> None:
        facade.require_production_media_backend(
            {"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}},
            allow_local_media=False,
            serving=True,
        )

    def test_missing_backend_fails_closed(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="must declare a BACKEND"):
            facade.require_production_media_backend(
                {"default": {}},
                allow_local_media=False,
                serving=True,
            )


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


class TestRestFrameworkComposition:
    """The generated project's DRF composition ships in the facade (SA258b)."""

    def test_defaults_fail_closed(self) -> None:
        """With no module contribution the composed defaults stay fail-closed."""
        composed = facade.compose_rest_framework(
            use_x_forwarded_for=False, trusted_proxy_count=0
        )

        assert composed["EXCEPTION_HANDLER"] == (
            "quickscale_core.runtime.conventions.exception_handler"
        )
        assert composed["DEFAULT_AUTHENTICATION_CLASSES"] == [
            "quickscale_core.runtime.drf.QuickscaleSessionAuthentication",
        ]
        assert composed["DEFAULT_PERMISSION_CLASSES"] == [
            "rest_framework.permissions.IsAuthenticated",
        ]
        assert composed["DEFAULT_RENDERER_CLASSES"] == [
            "rest_framework.renderers.JSONRenderer",
        ]
        assert composed["DEFAULT_PARSER_CLASSES"] == [
            "rest_framework.parsers.JSONParser",
        ]
        assert composed["DEFAULT_THROTTLE_CLASSES"] == [
            "rest_framework.throttling.AnonRateThrottle",
            "rest_framework.throttling.UserRateThrottle",
            "quickscale_core.runtime.drf.QuickscaleScopedRateThrottle",
        ]
        assert composed["DEFAULT_THROTTLE_RATES"] == {
            "anon": "1200/hour",
            "user": "3000/hour",
        }
        assert composed["NUM_PROXIES"] is None

    def test_module_contribution_wins_on_every_key(self) -> None:
        """A module-contributed key wins; unset keys keep the defaults."""
        contribution: dict[str, object] = {
            "EXCEPTION_HANDLER": "myproject.errors.handler",
            "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.BrowsableAPIRenderer",
            ],
            "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.FormParser"],
            "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
            "DEFAULT_THROTTLE_RATES": {"quickscale_billing_checkout": "30/hour"},
            "PAGE_SIZE": 25,
        }

        composed = facade.compose_rest_framework(
            contribution, use_x_forwarded_for=True, trusted_proxy_count=2
        )

        assert composed["EXCEPTION_HANDLER"] == "myproject.errors.handler"
        assert composed["DEFAULT_PERMISSION_CLASSES"] == [
            "rest_framework.permissions.AllowAny",
        ]
        assert composed["DEFAULT_RENDERER_CLASSES"] == [
            "rest_framework.renderers.BrowsableAPIRenderer",
        ]
        assert composed["DEFAULT_PARSER_CLASSES"] == [
            "rest_framework.parsers.FormParser",
        ]
        assert composed["DEFAULT_THROTTLE_CLASSES"] == [
            "rest_framework.throttling.AnonRateThrottle",
        ]
        assert composed["DEFAULT_THROTTLE_RATES"] == {
            "anon": "1200/hour",
            "user": "3000/hour",
            "quickscale_billing_checkout": "30/hour",
        }
        assert composed["PAGE_SIZE"] == 25
        assert composed["NUM_PROXIES"] == 2

    def test_input_contribution_is_not_mutated(self) -> None:
        """Composition copies the module contribution instead of editing it."""
        contribution: dict[str, object] = {
            "DEFAULT_THROTTLE_RATES": {"quickscale_billing_checkout": "30/hour"},
        }

        facade.compose_rest_framework(
            contribution, use_x_forwarded_for=False, trusted_proxy_count=0
        )

        assert contribution == {
            "DEFAULT_THROTTLE_RATES": {"quickscale_billing_checkout": "30/hour"},
        }

    def test_defaults_are_not_shared_between_calls(self) -> None:
        """Callers cannot corrupt the shipped default lists."""
        first = facade.compose_rest_framework(
            use_x_forwarded_for=False, trusted_proxy_count=0
        )
        first_permissions = first["DEFAULT_PERMISSION_CLASSES"]
        assert isinstance(first_permissions, list)
        first_permissions.append("rest_framework.permissions.AllowAny")
        first_parsers = first["DEFAULT_PARSER_CLASSES"]
        assert isinstance(first_parsers, list)
        first_parsers.append("rest_framework.parsers.FormParser")

        second = facade.compose_rest_framework(
            use_x_forwarded_for=False, trusted_proxy_count=0
        )
        assert second["DEFAULT_PERMISSION_CLASSES"] == [
            "rest_framework.permissions.IsAuthenticated",
        ]
        assert second["DEFAULT_PARSER_CLASSES"] == [
            "rest_framework.parsers.JSONParser",
        ]

    def test_non_mapping_throttle_rates_fail_loudly(self) -> None:
        """A malformed module contribution is refused, not silently dropped."""
        with pytest.raises(TypeError, match="DEFAULT_THROTTLE_RATES"):
            facade.compose_rest_framework(
                {"DEFAULT_THROTTLE_RATES": "30/hour"},
                use_x_forwarded_for=False,
                trusted_proxy_count=0,
            )

    def test_declared_scopes_merge_between_defaults_and_contributions(self) -> None:
        """Declared scopes win over the defaults; a project's own rate still wins."""
        composed = facade.compose_rest_framework(
            {"DEFAULT_THROTTLE_RATES": {"quickscale_forms_submit": "1/hour"}},
            throttle_scopes={
                "anon": "10/hour",
                "quickscale_forms_submit": "20/minute",
                "quickscale_billing_checkout": "30/hour",
            },
            use_x_forwarded_for=False,
            trusted_proxy_count=0,
        )

        assert composed["DEFAULT_THROTTLE_RATES"] == {
            "anon": "10/hour",
            "user": "3000/hour",
            "quickscale_billing_checkout": "30/hour",
            "quickscale_forms_submit": "1/hour",
        }

    def test_non_mapping_declared_scopes_fail_loudly(self) -> None:
        """A malformed declared-scope map is refused, not silently dropped."""
        with pytest.raises(TypeError, match="declared throttle scopes"):
            facade.compose_rest_framework(
                throttle_scopes=["quickscale_billing_checkout"],
                use_x_forwarded_for=False,
                trusted_proxy_count=0,
            )

    def test_declared_scopes_do_not_mutate_the_caller_map(self) -> None:
        """Composition copies the declared scopes instead of editing them."""
        declared = {"quickscale_billing_checkout": "30/hour"}

        composed = facade.compose_rest_framework(
            throttle_scopes=declared,
            use_x_forwarded_for=False,
            trusted_proxy_count=0,
        )

        assert declared == {"quickscale_billing_checkout": "30/hour"}
        rates = composed["DEFAULT_THROTTLE_RATES"]
        assert isinstance(rates, dict)
        rates["quickscale_billing_checkout"] = "1/minute"
        assert declared["quickscale_billing_checkout"] == "30/hour"


class TestCorrelationIdContract:
    """The correlation middleware, filter, and formatter share one context var."""

    def test_middleware_stamps_request_and_response(self) -> None:
        request = types.SimpleNamespace(META={"HTTP_X_REQUEST_ID": "trace-1"})
        response: dict[str, str] = {}
        middleware = facade.CorrelationIdMiddleware(lambda _request: response)

        token = facade.correlation_id_var.set("")
        try:
            assert middleware(request) is response
            assert request.correlation_id == "trace-1"
            assert response["X-Request-ID"] == "trace-1"
            assert facade.correlation_id_var.get() == "trace-1"
        finally:
            facade.correlation_id_var.reset(token)

    @pytest.mark.parametrize("client_value", ["a" * 10_240, "x" * 65, "bad:id", ""])
    def test_middleware_replaces_unusable_client_values(
        self, client_value: str
    ) -> None:
        request = types.SimpleNamespace(META={"HTTP_X_REQUEST_ID": client_value})
        response: dict[str, str] = {}
        token = facade.correlation_id_var.set("")
        try:
            facade.CorrelationIdMiddleware(lambda _request: response)(request)

            generated = request.correlation_id
            assert generated != client_value
            uuid.UUID(generated)
            assert response["X-Request-ID"] == generated
        finally:
            facade.correlation_id_var.reset(token)

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

    def test_bypass_flag_is_refused_while_serving(self) -> None:
        with pytest.raises(
            ValueError,
            match="QUICKSCALE_ALLOW_BYPASSRLS=1 is not allowed while serving",
        ):
            facade.resolve_runtime_database_url(
                runtime_database_url="",
                database_url="postgresql://super:secret@db:5432/app",
                allow_bypass_rls=True,
            )

    def test_bypass_flag_is_refused_even_with_a_runtime_url(self) -> None:
        with pytest.raises(
            ValueError,
            match="QUICKSCALE_ALLOW_BYPASSRLS=1 is not allowed while serving",
        ):
            facade.resolve_runtime_database_url(
                runtime_database_url="postgresql://runtime:secret@db:5432/app",
                database_url="postgresql://super:secret@db:5432/app",
                allow_bypass_rls=True,
            )

    def test_privileged_command_ignores_the_bypass_flag(self) -> None:
        assert (
            facade.resolve_runtime_database_url(
                runtime_database_url="",
                database_url="postgresql://super:secret@db:5432/app",
                privileged_command="migrate",
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
