"""Tests for the QuickScale analytics module-owned page."""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.test.client import Client


@override_settings(ROOT_URLCONF="tests.urls")
class AnalyticsDashboardViewTest(TestCase):
    """Verify the module-owned analytics page renders successfully."""

    def test_analytics_dashboard_returns_200(self):
        """The analytics dashboard should return a successful response."""
        client = Client()
        response = client.get("/analytics/")
        assert response.status_code == 200

    def test_analytics_dashboard_contains_analytics_heading(self):
        """The analytics dashboard should render the Analytics heading."""
        client = Client()
        response = client.get("/analytics/")
        content = response.content.decode()
        assert "Analytics" in content

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=False)
    def test_analytics_dashboard_reports_disabled(self):
        """The analytics dashboard should indicate when analytics is disabled."""
        client = Client()
        response = client.get("/analytics/")
        content = response.content.decode()
        assert "disabled" in content.lower()
