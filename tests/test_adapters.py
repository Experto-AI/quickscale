"""Tests for auth module adapters"""

import pytest
from django.test import RequestFactory
from quickscale_modules_auth.adapters import QuickscaleAccountAdapter


@pytest.mark.django_db
class TestQuickscaleAccountAdapter:
    """Tests for QuickscaleAccountAdapter"""

    def setup_method(self):
        """Set up test fixtures"""
        self.adapter = QuickscaleAccountAdapter()
        self.factory = RequestFactory()

    def test_is_open_for_signup_default(self):
        """Test signup is open by default"""
        request = self.factory.get("/")
        assert self.adapter.is_open_for_signup(request) is True

    def test_is_open_for_signup_disabled(self, settings):
        """Test signup respects ACCOUNT_ALLOW_REGISTRATION setting"""
        settings.ACCOUNT_ALLOW_REGISTRATION = False
        request = self.factory.get("/")
        assert self.adapter.is_open_for_signup(request) is False

    def test_get_login_redirect_url(self):
        """Test login redirect URL"""
        request = self.factory.get("/")
        url = self.adapter.get_login_redirect_url(request)
        assert url == "/accounts/profile/"
