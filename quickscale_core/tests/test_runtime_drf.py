"""Contract tests for the shared DRF helper classes (SA262).

The one session authentication class keeps a 401 challenge for anonymous
callers, so every module session API and the generated settings share the
same scheme instead of a per-module copy.  The one scoped throttle class is
the single attachment point for a view's ``throttle_scope``, keyed by the
authenticated user's pk or the canonical client IP.  The one list paginator
reads its size from the ``<THING>_PER_PAGE`` setting a subclass declares and
returns the bare list.  The combined facade serves all three lazily; these
tests hold that surface in place.

The throttle contract imports Django REST Framework's throttling module,
which reads ``api_settings`` at import, so these tests configure minimal
Django settings first — the same pattern the other runtime test modules use.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request


@pytest.fixture(autouse=True)
def _configured_django() -> None:
    """Configure minimal Django settings before any DRF helper import."""
    if not django_settings.configured:
        django_settings.configure(
            DEBUG=False,
            SECRET_KEY="quickscale-test-key",
            REST_FRAMEWORK={
                "DEFAULT_THROTTLE_RATES": {"quickscale_demo_api": "5/hour"},
            },
            USE_I18N=False,
            USE_TZ=False,
        )


class TestQuickscaleSessionAuthentication:
    """The core session authentication class declares the 401 challenge."""

    def test_is_the_one_session_authentication_class(self) -> None:
        from quickscale_core.runtime import QuickscaleSessionAuthentication

        assert issubclass(QuickscaleSessionAuthentication, SessionAuthentication)

    def test_anonymous_challenge_is_401(self) -> None:
        from quickscale_core.runtime import QuickscaleSessionAuthentication

        scheme = QuickscaleSessionAuthentication()
        assert scheme.authenticate_header(cast(Request, None)) == "Session"

    def test_facade_serves_the_submodule_symbol(self) -> None:
        from quickscale_core.runtime import QuickscaleSessionAuthentication
        from quickscale_core.runtime import drf as drf_helpers

        assert (
            QuickscaleSessionAuthentication
            is drf_helpers.QuickscaleSessionAuthentication
        )


def _request(
    *,
    user: object = None,
    meta: dict[str, str] | None = None,
) -> Request:
    """Build a request stand-in carrying only the throttle-relevant fields."""
    return cast(Request, SimpleNamespace(user=user, META=meta or {}))


def _view(scope: str | None = "quickscale_demo_api") -> object:
    return SimpleNamespace(throttle_scope=scope)


class TestQuickscaleScopedRateThrottle:
    """The core scoped throttle is rule 32's one attachment point."""

    def test_is_the_scoped_throttle_class(self) -> None:
        from rest_framework.throttling import ScopedRateThrottle

        from quickscale_core.runtime import QuickscaleScopedRateThrottle

        assert issubclass(QuickscaleScopedRateThrottle, ScopedRateThrottle)

    def test_facade_serves_the_submodule_symbol(self) -> None:
        from quickscale_core.runtime import QuickscaleScopedRateThrottle
        from quickscale_core.runtime import drf as drf_helpers

        assert QuickscaleScopedRateThrottle is drf_helpers.QuickscaleScopedRateThrottle

    def test_view_without_a_scope_is_allowed_without_a_bucket(self) -> None:
        from quickscale_core.runtime import QuickscaleScopedRateThrottle

        throttle = QuickscaleScopedRateThrottle()
        request = _request(meta={"REMOTE_ADDR": "10.0.0.1"})
        assert throttle.allow_request(request, _view(scope=None)) is True

    def test_authenticated_user_identity_is_the_pk(self) -> None:
        from quickscale_core.runtime import QuickscaleScopedRateThrottle

        throttle = QuickscaleScopedRateThrottle()
        # ``allow_request`` stamps the scope on the instance before DRF reads
        # the cache key; set it here to exercise the keying directly.
        throttle.scope = "quickscale_demo_api"
        request = _request(
            user=SimpleNamespace(pk=17, is_authenticated=True),
            meta={"REMOTE_ADDR": "10.0.0.1"},
        )
        assert (
            throttle.get_cache_key(request, _view())
            == "throttle_quickscale_demo_api_17"
        )

    def test_anonymous_identity_is_the_canonical_forwarded_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quickscale_core.runtime import QuickscaleScopedRateThrottle
        from quickscale_core.runtime import drf as drf_helpers

        monkeypatch.setattr(drf_helpers, "validated_proxy_settings", lambda: (True, 2))
        throttle = QuickscaleScopedRateThrottle()
        request = _request(
            user=SimpleNamespace(pk=None, is_authenticated=False),
            meta={
                "HTTP_X_FORWARDED_FOR": "203.0.113.9, 10.0.0.1",
                "REMOTE_ADDR": "10.0.0.1",
            },
        )
        assert throttle.get_ident(request) == "203.0.113.9"

    def test_untrusted_forwarding_ignores_a_spoofed_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quickscale_core.runtime import QuickscaleScopedRateThrottle
        from quickscale_core.runtime import drf as drf_helpers

        monkeypatch.setattr(drf_helpers, "validated_proxy_settings", lambda: (False, 1))
        throttle = QuickscaleScopedRateThrottle()
        request = _request(
            meta={
                "HTTP_X_FORWARDED_FOR": "198.51.100.1",
                "REMOTE_ADDR": "10.0.0.99",
            }
        )
        assert throttle.get_ident(request) == "10.0.0.99"

    def test_short_forwarded_chain_falls_back_to_remote_addr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quickscale_core.runtime import QuickscaleScopedRateThrottle
        from quickscale_core.runtime import drf as drf_helpers

        monkeypatch.setattr(drf_helpers, "validated_proxy_settings", lambda: (True, 2))
        throttle = QuickscaleScopedRateThrottle()
        request = _request(
            meta={
                "HTTP_X_FORWARDED_FOR": "203.0.113.50",
                "REMOTE_ADDR": "10.0.0.42",
            }
        )
        assert throttle.get_ident(request) == "10.0.0.42"

    def test_zero_trusted_proxies_fall_back_to_remote_addr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quickscale_core.runtime import QuickscaleScopedRateThrottle
        from quickscale_core.runtime import drf as drf_helpers

        monkeypatch.setattr(drf_helpers, "validated_proxy_settings", lambda: (True, 0))
        throttle = QuickscaleScopedRateThrottle()
        request = _request(
            meta={
                "HTTP_X_FORWARDED_FOR": "203.0.113.50",
                "REMOTE_ADDR": "10.0.0.42",
            }
        )
        assert throttle.get_ident(request) == "10.0.0.42"

    def test_proxy_settings_fail_loud_without_cache_mutation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from django.core.exceptions import ImproperlyConfigured

        from quickscale_core.runtime import QuickscaleScopedRateThrottle
        from quickscale_core.runtime import drf as drf_helpers

        def _fail_loud() -> tuple[bool, int]:
            raise ImproperlyConfigured("USE_X_FORWARDED_FOR setting is required.")

        monkeypatch.setattr(drf_helpers, "validated_proxy_settings", _fail_loud)
        throttle = QuickscaleScopedRateThrottle()
        request = _request(
            user=SimpleNamespace(pk=None, is_authenticated=False),
            meta={"REMOTE_ADDR": "10.0.0.1"},
        )

        with (
            patch.object(throttle.cache, "add") as cache_add,
            patch.object(throttle.cache, "incr") as cache_incr,
            patch.object(throttle.cache, "set") as cache_set,
        ):
            with pytest.raises(ImproperlyConfigured):
                throttle.allow_request(request, _view())

        cache_add.assert_not_called()
        cache_incr.assert_not_called()
        cache_set.assert_not_called()


def _demo_pagination_class() -> type:
    """Return a module-style paginator subclass (imported after configuration)."""
    from quickscale_core.runtime import PlainListPagination

    class _DemoPagination(PlainListPagination):
        page_size_setting = "QUICKSCALE_DEMO_PER_PAGE"

    return _DemoPagination


class TestPlainListPagination:
    """The core paginator reads its size from the declared setting (rule 9)."""

    def test_is_a_page_number_pagination_subclass(self) -> None:
        from rest_framework.pagination import PageNumberPagination

        from quickscale_core.runtime import PlainListPagination

        assert issubclass(PlainListPagination, PageNumberPagination)

    def test_facade_serves_the_submodule_symbol(self) -> None:
        from quickscale_core.runtime import PlainListPagination
        from quickscale_core.runtime import drf as drf_helpers

        assert PlainListPagination is drf_helpers.PlainListPagination

    @override_settings(QUICKSCALE_DEMO_PER_PAGE=7)
    def test_page_size_comes_from_the_declared_setting(self) -> None:
        paginator = _demo_pagination_class()()
        assert paginator.get_page_size(cast(Request, None)) == 7

    def test_no_declared_setting_fails_loud(self) -> None:
        from quickscale_core.runtime import PlainListPagination

        with pytest.raises(ImproperlyConfigured, match="page_size_setting"):
            PlainListPagination().get_page_size(cast(Request, None))

    def test_missing_setting_fails_loud(self) -> None:
        from quickscale_core.runtime import PlainListPagination

        class _Missing(PlainListPagination):
            page_size_setting = "QUICKSCALE_DEMO_MISSING_PER_PAGE"

        with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_DEMO_MISSING"):
            _Missing().get_page_size(cast(Request, None))

    @pytest.mark.parametrize("invalid", [0, -3, 2.9, True, "many", "25", None])
    def test_invalid_setting_values_fail_loud(self, invalid: object) -> None:
        paginator = _demo_pagination_class()()
        with override_settings(QUICKSCALE_DEMO_PER_PAGE=invalid):
            with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_DEMO"):
                paginator.get_page_size(cast(Request, None))

    def test_response_keeps_the_bare_list_shape(self) -> None:
        paginator = _demo_pagination_class()()
        response = paginator.get_paginated_response([{"id": 1}, {"id": 2}])
        assert response.data == [{"id": 1}, {"id": 2}]

    def test_client_cannot_override_the_page_size(self) -> None:
        from quickscale_core.runtime import PlainListPagination

        assert PlainListPagination.page_size_query_param is None
