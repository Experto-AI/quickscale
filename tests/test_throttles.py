"""Tests for forms module throttle helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, override_settings

from quickscale_modules_forms.throttles import FormSubmitThrottle
from quickscale_modules_orgs.current_org import get_client_ip


_MISSING = object()

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


def test_form_submit_throttle_uses_configured_rate() -> None:
    throttle = FormSubmitThrottle()

    with override_settings(FORMS_RATE_LIMIT="5/hour"):
        assert throttle.get_rate() == "5/hour"


def test_form_submit_throttle_missing_rate_raises_improperly_configured() -> None:
    """SA17.4 — missing FORMS_RATE_LIMIT must raise at request time."""
    throttle = FormSubmitThrottle()

    with override_settings(FORMS_RATE_LIMIT=None):
        with pytest.raises(
            ImproperlyConfigured,
            match="FORMS_RATE_LIMIT",
        ):
            throttle.get_rate()


def test_form_submit_throttle_uses_parent_cache_key_when_view_scope_is_declared() -> (
    None
):
    throttle = FormSubmitThrottle()
    request = RequestFactory().post("/api/forms/submit/")
    view = SimpleNamespace(throttle_scope="custom-scope")

    with patch(
        "rest_framework.throttling.ScopedRateThrottle.get_cache_key",
        return_value="parent-cache-key",
    ) as mocked_super_cache_key:
        assert throttle.get_cache_key(request, view) == "parent-cache-key"

    mocked_super_cache_key.assert_called_once_with(request, view)


def test_form_submit_throttle_returns_none_when_scope_is_empty() -> None:
    throttle = FormSubmitThrottle()
    throttle.scope = ""
    request = RequestFactory().post("/api/forms/submit/")
    view = SimpleNamespace(throttle_scope=None)

    assert throttle.get_cache_key(request, view) is None


def test_form_submit_throttle_builds_cache_key_from_default_scope() -> None:
    throttle = FormSubmitThrottle()
    request = RequestFactory().post("/api/forms/submit/")
    view = SimpleNamespace(throttle_scope=None)

    with patch.object(throttle, "get_ident", return_value="127.0.0.1"):
        cache_key = throttle.get_cache_key(request, view)

    assert cache_key == "throttle_form_submit_127.0.0.1"


# ---------------------------------------------------------------------------
# CR-SA21.2-001 — short/invalid XFF chain parity with get_client_ip
# ---------------------------------------------------------------------------
# Regression: FormSubmitThrottle.get_ident() now delegates to the shared
# get_client_ip() helper.  Short XFF chains (shorter than
# TRUSTED_PROXY_COUNT) must fall back to REMOTE_ADDR instead of trusting
# a potentially spoofed leftmost address.
# ---------------------------------------------------------------------------


def _make_request(remote_addr: str, xff: str | None = None) -> Any:
    """Build a bare POST request with optional XFF and anonymous user."""
    kwargs: dict[str, str] = {"REMOTE_ADDR": remote_addr}
    if xff is not None:
        kwargs["HTTP_X_FORWARDED_FOR"] = xff
    req = RequestFactory().post("/api/forms/submit/", **kwargs)
    req.user = None  # DRF's get_cache_key checks request.user first
    return req


@override_settings(
    USE_X_FORWARDED_FOR=True,
    TRUSTED_PROXY_COUNT=2,
)
def test_form_submit_throttle_short_xff_chain_falls_back_to_remote_addr() -> None:
    """When the X-Forwarded-For chain is shorter than TRUSTED_PROXY_COUNT,
    the throttle ident must be REMOTE_ADDR, not the XFF entry (fail-closed)."""
    throttle = FormSubmitThrottle()
    request = _make_request(remote_addr="10.0.0.42", xff="203.0.113.50")
    view = SimpleNamespace(throttle_scope="form_submit")

    cache_key = throttle.get_cache_key(request, view)

    # Chain length 1 < TRUSTED_PROXY_COUNT 2 → REMOTE_ADDR
    assert cache_key == "throttle_form_submit_10.0.0.42", (
        f"Expected REMOTE_ADDR-based key, got {cache_key!r}"
    )


@override_settings(
    USE_X_FORWARDED_FOR=True,
    TRUSTED_PROXY_COUNT=2,
)
def test_form_submit_throttle_sufficient_xff_chain_resolves_from_xff() -> None:
    """When the X-Forwarded-For chain meets or exceeds TRUSTED_PROXY_COUNT,
    the throttle ident must resolve from the rightmost trusted entry."""
    throttle = FormSubmitThrottle()
    request = _make_request(remote_addr="10.0.0.1", xff="203.0.113.50, 10.0.0.1")
    view = SimpleNamespace(throttle_scope="form_submit")

    cache_key = throttle.get_cache_key(request, view)

    # Chain length 2 >= TRUSTED_PROXY_COUNT 2 → ips[-2] = "203.0.113.50"
    assert cache_key == "throttle_form_submit_203.0.113.50", (
        f"Expected XFF-resolved key, got {cache_key!r}"
    )


@override_settings(
    USE_X_FORWARDED_FOR=False,
    TRUSTED_PROXY_COUNT=1,
)
def test_form_submit_throttle_use_xff_false_ignores_xff() -> None:
    """When USE_X_FORWARDED_FOR is False, the throttle ident must be
    REMOTE_ADDR even when X-Forwarded-For is present (CR-SA21.2-001)."""
    throttle = FormSubmitThrottle()
    request = _make_request(remote_addr="10.0.0.99", xff="198.51.100.1")
    view = SimpleNamespace(throttle_scope="form_submit")

    cache_key = throttle.get_cache_key(request, view)

    assert cache_key == "throttle_form_submit_10.0.0.99", (
        f"Expected REMOTE_ADDR-based key when USE_X_FORWARDED_FOR=False, "
        f"got {cache_key!r}"
    )


@pytest.mark.parametrize("use_xff,proxy_count,xff", CLIENT_IP_CASES)
def test_form_submit_throttle_identity_matches_direct_resolver(
    use_xff: bool,
    proxy_count: int,
    xff: str | None,
) -> None:
    """Every value-bearing proxy tuple keeps throttle identity parity."""
    throttle = FormSubmitThrottle()
    request = _make_request(remote_addr="10.0.0.1", xff=xff)
    view = SimpleNamespace(throttle_scope="form_submit")

    with override_settings(
        USE_X_FORWARDED_FOR=use_xff,
        TRUSTED_PROXY_COUNT=proxy_count,
    ):
        expected = get_client_ip(request)
        assert throttle.get_ident(request) == expected
        assert throttle.get_cache_key(request, view) == (
            f"throttle_form_submit_{expected}"
        )


@pytest.mark.parametrize("setting_name,setting_value", INVALID_PROXY_SETTINGS)
def test_form_submit_throttle_fail_loud_matches_resolver_without_cache_write(
    setting_name: str,
    setting_value: object,
) -> None:
    """Invalid resolver settings fail before DRF can mutate throttle cache."""
    throttle = FormSubmitThrottle()
    request = _make_request(remote_addr="10.0.0.1", xff="198.51.100.1")
    view = SimpleNamespace(throttle_scope="form_submit")
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
