"""Tests for the forms module's throttle attachment (Module Conventions rule 32).

The submit endpoint attaches its rate by ``throttle_scope`` alone; the bucket
identity comes from core's one scoped throttle class, whose client-IP branch
must stay identical to the canonical resolver in ``get_client_ip``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, override_settings

from quickscale_core.runtime import QuickscaleScopedRateThrottle
from quickscale_modules_forms.views import FormSubmitAPIView
from quickscale_modules_orgs.current_org import get_client_ip


_MISSING = object()

SCOPE = "quickscale_forms_submit"

CLIENT_IP_CASES = (
    pytest.param(
        False,
        2,
        "198.51.100.1, 10.0.0.1",
        id="disabled",
    ),
    pytest.param(
        True,
        0,
        "198.51.100.1, 10.0.0.1",
        id="zero",
    ),
    pytest.param(True, 1, None, id="absent"),
    pytest.param(True, 1, "", id="empty"),
    pytest.param(
        True,
        3,
        "198.51.100.1, , 10.0.0.1",
        id="empty-hop",
    ),
    pytest.param(True, 2, "198.51.100.1", id="short"),
    pytest.param(
        True,
        2,
        "198.51.100.1, 10.0.0.1",
        id="equal",
    ),
    pytest.param(
        True,
        2,
        "198.51.100.1, 198.51.100.2, 10.0.0.1, 10.0.0.2",
        id="long",
    ),
)

INVALID_PROXY_SETTINGS = (
    pytest.param("USE_X_FORWARDED_FOR", _MISSING, id="missing-use-xff"),
    pytest.param("USE_X_FORWARDED_FOR", None, id="invalid-use-xff-none"),
    pytest.param("USE_X_FORWARDED_FOR", "yes", id="invalid-use-xff-string"),
    pytest.param("TRUSTED_PROXY_COUNT", _MISSING, id="missing-proxy-count"),
    pytest.param("TRUSTED_PROXY_COUNT", "1", id="invalid-proxy-count-string"),
    pytest.param("TRUSTED_PROXY_COUNT", -1, id="invalid-proxy-count-negative"),
    pytest.param("TRUSTED_PROXY_COUNT", True, id="invalid-proxy-count-bool"),
)


def test_submit_view_attaches_its_throttle_by_scope_only() -> None:
    """Rule 32: the view declares the scope and no throttle class."""
    assert FormSubmitAPIView.throttle_scope == SCOPE
    assert "throttle_classes" not in vars(FormSubmitAPIView)


def test_core_scoped_throttle_returns_none_when_scope_is_empty() -> None:
    throttle = QuickscaleScopedRateThrottle()
    request = _make_request(remote_addr="10.0.0.1")
    view = SimpleNamespace(throttle_scope=None)

    # ``ScopedRateThrottle.allow_request`` allows a view with no scope before a
    # bucket is ever built.
    assert throttle.allow_request(request, view) is True


def test_core_scoped_throttle_builds_cache_key_from_the_view_scope() -> None:
    throttle = QuickscaleScopedRateThrottle()
    throttle.scope = SCOPE
    request = _make_request(remote_addr="10.0.0.1")
    view = SimpleNamespace(throttle_scope=SCOPE)

    with patch.object(throttle, "get_ident", return_value="127.0.0.1"):
        cache_key = throttle.get_cache_key(request, view)

    assert cache_key == f"throttle_{SCOPE}_127.0.0.1"


def _make_request(remote_addr: str, xff: str | None = None) -> Any:
    """Build a bare POST request with optional XFF and anonymous user."""
    kwargs: dict[str, str] = {"REMOTE_ADDR": remote_addr}
    if xff is not None:
        kwargs["HTTP_X_FORWARDED_FOR"] = xff
    req = RequestFactory().post("/forms/api/contact/submit/", **kwargs)
    req.user = None  # DRF's get_cache_key checks request.user first
    return req


def _throttle_with_scope() -> QuickscaleScopedRateThrottle:
    throttle = QuickscaleScopedRateThrottle()
    throttle.scope = SCOPE
    return throttle


@override_settings(
    USE_X_FORWARDED_FOR=True,
    TRUSTED_PROXY_COUNT=2,
)
def test_core_scoped_throttle_short_xff_chain_falls_back_to_remote_addr() -> None:
    """When the X-Forwarded-For chain is shorter than TRUSTED_PROXY_COUNT,
    the throttle ident must be REMOTE_ADDR, not the XFF entry (fail-closed)."""
    throttle = _throttle_with_scope()
    request = _make_request(remote_addr="10.0.0.42", xff="203.0.113.50")
    view = SimpleNamespace(throttle_scope=SCOPE)

    cache_key = throttle.get_cache_key(request, view)

    # Chain length 1 < TRUSTED_PROXY_COUNT 2 → REMOTE_ADDR
    assert cache_key == f"throttle_{SCOPE}_10.0.0.42", (
        f"Expected REMOTE_ADDR-based key, got {cache_key!r}"
    )


@override_settings(
    USE_X_FORWARDED_FOR=True,
    TRUSTED_PROXY_COUNT=2,
)
def test_core_scoped_throttle_sufficient_xff_chain_resolves_from_xff() -> None:
    """When the X-Forwarded-For chain meets or exceeds TRUSTED_PROXY_COUNT,
    the throttle ident must resolve from the rightmost trusted entry."""
    throttle = _throttle_with_scope()
    request = _make_request(remote_addr="10.0.0.1", xff="203.0.113.50, 10.0.0.1")
    view = SimpleNamespace(throttle_scope=SCOPE)

    cache_key = throttle.get_cache_key(request, view)

    # Chain length 2 >= TRUSTED_PROXY_COUNT 2 → ips[-2] = "203.0.113.50"
    assert cache_key == f"throttle_{SCOPE}_203.0.113.50", (
        f"Expected XFF-resolved key, got {cache_key!r}"
    )


@override_settings(
    USE_X_FORWARDED_FOR=False,
    TRUSTED_PROXY_COUNT=1,
)
def test_core_scoped_throttle_use_xff_false_ignores_xff() -> None:
    """When USE_X_FORWARDED_FOR is False, the throttle ident must be
    REMOTE_ADDR even when X-Forwarded-For is present."""
    throttle = _throttle_with_scope()
    request = _make_request(remote_addr="10.0.0.99", xff="198.51.100.1")
    view = SimpleNamespace(throttle_scope=SCOPE)

    cache_key = throttle.get_cache_key(request, view)

    assert cache_key == f"throttle_{SCOPE}_10.0.0.99", (
        f"Expected REMOTE_ADDR-based key when USE_X_FORWARDED_FOR=False, "
        f"got {cache_key!r}"
    )


@pytest.mark.parametrize("use_xff,proxy_count,xff", CLIENT_IP_CASES)
def test_core_scoped_throttle_identity_matches_direct_resolver(
    use_xff: bool,
    proxy_count: int,
    xff: str | None,
) -> None:
    """Every value-bearing proxy tuple keeps throttle identity parity."""
    throttle = _throttle_with_scope()
    request = _make_request(remote_addr="10.0.0.1", xff=xff)
    view = SimpleNamespace(throttle_scope=SCOPE)

    with override_settings(
        USE_X_FORWARDED_FOR=use_xff,
        TRUSTED_PROXY_COUNT=proxy_count,
    ):
        expected = get_client_ip(request)
        assert throttle.get_ident(request) == expected
        assert throttle.get_cache_key(request, view) == (f"throttle_{SCOPE}_{expected}")


@pytest.mark.parametrize("setting_name,setting_value", INVALID_PROXY_SETTINGS)
def test_core_scoped_throttle_fail_loud_matches_resolver_without_cache_write(
    setting_name: str,
    setting_value: object,
) -> None:
    """Invalid resolver settings fail before DRF can mutate throttle cache."""
    throttle = _throttle_with_scope()
    request = _make_request(remote_addr="10.0.0.1", xff="198.51.100.1")
    view = SimpleNamespace(throttle_scope=SCOPE)
    values: dict[str, object] = {
        "USE_X_FORWARDED_FOR": False,
        "TRUSTED_PROXY_COUNT": 1,
    }
    if setting_value is _MISSING:
        missing_setting = setting_name
    else:
        values[setting_name] = setting_value
        missing_setting = None

    with override_settings(**values):
        if missing_setting is not None:
            delattr(settings, missing_setting)

        with pytest.raises(ImproperlyConfigured) as direct_error:
            get_client_ip(request)

        with (
            patch.object(throttle.cache, "add") as cache_add,
            patch.object(throttle.cache, "incr") as cache_incr,
            patch.object(throttle.cache, "set") as cache_set,
        ):
            with pytest.raises(ImproperlyConfigured) as throttle_error:
                throttle.allow_request(request, view)

        assert type(throttle_error.value) is type(direct_error.value)
        assert str(throttle_error.value) == str(direct_error.value)
        assert setting_name in str(throttle_error.value)
        cache_add.assert_not_called()
        cache_incr.assert_not_called()
        cache_set.assert_not_called()
