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

    def test_get_login_redirect_url_custom(self, settings):
        """Test login redirect URL with custom setting"""
        settings.LOGIN_REDIRECT_URL = "/dashboard/"
        request = self.factory.get("/")
        url = self.adapter.get_login_redirect_url(request)
        assert url == "/dashboard/"

    def test_save_user_with_commit(self):
        """Test save_user with commit=True"""
        from django.contrib.auth import get_user_model
        from unittest.mock import Mock, patch

        User = get_user_model()
        request = self.factory.post("/")

        # Create a mock user
        user = Mock(spec=User)
        user.save = Mock()

        # Create a mock form
        form = Mock()

        # Mock the parent's save_user method
        with patch.object(
            QuickscaleAccountAdapter.__bases__[0], "save_user", return_value=user
        ):
            result = self.adapter.save_user(request, user, form, commit=True)

            # Verify user.save() was called
            user.save.assert_called_once()
            assert result == user

    def test_save_user_without_commit(self):
        """Test save_user with commit=False"""
        from django.contrib.auth import get_user_model
        from unittest.mock import Mock, patch

        User = get_user_model()
        request = self.factory.post("/")

        # Create a mock user
        user = Mock(spec=User)
        user.save = Mock()

        # Create a mock form
        form = Mock()

        # Mock the parent's save_user method
        with patch.object(
            QuickscaleAccountAdapter.__bases__[0], "save_user", return_value=user
        ):
            result = self.adapter.save_user(request, user, form, commit=False)

            # Verify user.save() was NOT called
            user.save.assert_not_called()
            assert result == user
