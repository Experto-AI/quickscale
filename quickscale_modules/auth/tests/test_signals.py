"""Tests for auth module signals"""

import pytest
from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestSignals:
    """Tests for signal handlers"""

    def test_user_signed_up_signal(self):
        """Test user_signed_up signal fires without errors"""
        # Create user and trigger signal
        user = User.objects.create_user(username="newuser", email="new@test.com", password="pass")

        # Signal handler should not raise errors
        user_signed_up.send(sender=User, request=None, user=user)

        # Basic assertion that user exists
        assert User.objects.filter(username="newuser").exists()
