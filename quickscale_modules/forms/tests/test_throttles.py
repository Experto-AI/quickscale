"""Tests for forms module throttle helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, override_settings

from quickscale_modules_forms.throttles import FormSubmitThrottle


def test_form_submit_throttle_uses_configured_rate() -> None:
    throttle = FormSubmitThrottle()

    with override_settings(FORMS_RATE_LIMIT="5/hour"):
        assert throttle.get_rate() == "5/hour"


def test_form_submit_throttle_falls_back_to_parent_rate() -> None:
    throttle = FormSubmitThrottle()

    with override_settings(FORMS_RATE_LIMIT=None):
        with patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value="10/minute",
        ) as mocked_super_get_rate:
            assert throttle.get_rate() == "10/minute"

    mocked_super_get_rate.assert_called_once_with()


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
