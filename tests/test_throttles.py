"""Tests for forms module throttle helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, override_settings

from quickscale_modules_forms.throttles import FormSubmitThrottle


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
