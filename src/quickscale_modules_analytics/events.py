"""Stable event vocabulary for QuickScale analytics.

Feature modules own their event names; analytics publishes only the generic
``capture_event`` and keeps PostHog's ``$pageview`` name here (rule 22).
"""

ANALYTICS_EVENT_PAGEVIEW = "$pageview"

__all__ = [
    "ANALYTICS_EVENT_PAGEVIEW",
]
