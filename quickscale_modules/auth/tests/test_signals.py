"""Tests for auth module signals"""

from importlib import import_module

import pytest
from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model

from quickscale_modules_auth.apps import QuickscaleAuthConfig

User = get_user_model()


@pytest.mark.django_db
class TestSignals:
    """Tests for signal handlers"""

    def test_user_signed_up_signal(self):
        """Test user_signed_up signal fires without errors"""
        # Create user and trigger signal
        user = User.objects.create_user(
            username="newuser", email="new@test.com", password="pass"
        )

        # Signal handler should not raise errors
        user_signed_up.send(sender=User, request=None, user=user)

        # Basic assertion that user exists
        assert User.objects.filter(username="newuser").exists()

    def test_app_ready_surfaces_signal_import_errors(self, monkeypatch):
        """Startup should surface signal import failures instead of swallowing them."""
        app_module = import_module("quickscale_modules_auth")
        app_config = QuickscaleAuthConfig("quickscale_modules_auth", app_module)

        def raise_import_error(module_name: str):
            raise ImportError(f"boom: {module_name}")

        monkeypatch.setattr(
            "quickscale_modules_auth.apps.import_module", raise_import_error
        )

        with pytest.raises(ImportError, match="boom: quickscale_modules_auth.signals"):
            app_config.ready()
