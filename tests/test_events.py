"""Tests for analytics event vocabulary constants."""

from quickscale_modules_analytics.events import ANALYTICS_EVENT_PAGEVIEW


def test_analytics_keeps_only_the_posthog_pageview_event() -> None:
    """Feature events are owned by their sending modules (rule 22)."""
    from quickscale_modules_analytics import events

    assert ANALYTICS_EVENT_PAGEVIEW == "$pageview"
    assert events.__all__ == ["ANALYTICS_EVENT_PAGEVIEW"]
