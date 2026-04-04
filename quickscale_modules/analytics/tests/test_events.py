"""Tests for analytics event vocabulary constants."""

from quickscale_modules_analytics.events import (
    ANALYTICS_EVENT_FORM_SUBMIT,
    ANALYTICS_EVENT_PAGEVIEW,
    ANALYTICS_EVENT_SOCIAL_LINK_CLICK,
)


def test_event_constants_match_the_v080_contract() -> None:
    """The first-party analytics event vocabulary should remain stable."""
    assert ANALYTICS_EVENT_PAGEVIEW == "$pageview"
    assert ANALYTICS_EVENT_FORM_SUBMIT == "form_submit"
    assert ANALYTICS_EVENT_SOCIAL_LINK_CLICK == "social_link_click"
