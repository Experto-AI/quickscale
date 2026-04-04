"""Tests for analytics template tags."""

from __future__ import annotations

import json

import pytest
from django.template import Context, Template
from django.test import RequestFactory, override_settings

from quickscale_modules_analytics import services


def _request_with_session(rf: RequestFactory):
    request = rf.get("/")
    from django.contrib.sessions.middleware import SessionMiddleware

    middleware = SessionMiddleware(lambda _: None)
    middleware.process_request(request)
    request.session.save()
    return request


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
@pytest.mark.django_db()
def test_analytics_public_config_tag_returns_runtime_config(
    monkeypatch,
    rf: RequestFactory,
) -> None:
    """Template tag should expose the resolved analytics config dictionary."""
    services._ANALYTICS_LAST_SETTINGS = None
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    request = _request_with_session(rf)

    template = Template(
        "{% load analytics_tags %}{% analytics_public_config as config %}"
        "{{ config.provider }}|{{ config.enabled }}|{{ config.posthog_api_key }}"
    )

    rendered = template.render(Context({"request": request}))

    assert rendered == "posthog|True|test-posthog-key"


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
@pytest.mark.django_db()
def test_analytics_public_config_json_tag_serializes_runtime_config(
    monkeypatch,
    rf: RequestFactory,
) -> None:
    """JSON template tag should serialize the same public runtime config payload."""
    services._ANALYTICS_LAST_SETTINGS = None
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    request = _request_with_session(rf)

    template = Template("{% load analytics_tags %}{% analytics_public_config_json %}")
    rendered = template.render(Context({"request": request}))
    payload = json.loads(rendered)

    assert payload["enabled"] is True
    assert payload["provider"] == "posthog"
    assert payload["posthog_api_key"] == "test-posthog-key"


@override_settings(DEBUG=False, QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=False)
def test_analytics_public_config_tag_accepts_missing_request_context(
    monkeypatch,
) -> None:
    """Template tags should degrade cleanly when no request object is present."""
    services._ANALYTICS_LAST_SETTINGS = None
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    template = Template(
        "{% load analytics_tags %}{% analytics_public_config as config %}"
        "{{ config.provider }}|{{ config.enabled }}"
    )
    rendered = template.render(Context({}))

    assert rendered == "posthog|True"
