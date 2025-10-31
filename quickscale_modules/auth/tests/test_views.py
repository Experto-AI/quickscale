"""Tests for auth module views"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestProfileView:
    """Tests for ProfileView"""

    def test_profile_view_requires_authentication(self, anonymous_client):
        """Test profile view redirects anonymous users"""
        response = anonymous_client.get(reverse("quickscale_auth:profile"))
        assert response.status_code == 302  # Redirect to login

    def test_profile_view_authenticated(self, authenticated_client, user):
        """Test profile view displays user info"""
        response = authenticated_client.get(reverse("quickscale_auth:profile"))
        assert response.status_code == 200
        assert user.username.encode() in response.content


@pytest.mark.django_db
class TestProfileUpdateView:
    """Tests for ProfileUpdateView"""

    def test_profile_update_requires_authentication(self, anonymous_client):
        """Test profile update redirects anonymous users"""
        response = anonymous_client.get(reverse("quickscale_auth:profile-edit"))
        assert response.status_code == 302

    def test_profile_update_get(self, authenticated_client):
        """Test profile update GET displays form"""
        response = authenticated_client.get(reverse("quickscale_auth:profile-edit"))
        assert response.status_code == 200

    def test_profile_update_post_valid(self, authenticated_client, user):
        """Test profile update with valid data"""
        response = authenticated_client.post(
            reverse("quickscale_auth:profile-edit"),
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": user.email,
            },
        )
        assert response.status_code == 302
        user.refresh_from_db()
        assert user.first_name == "Updated"


@pytest.mark.django_db
class TestAccountDeleteView:
    """Tests for AccountDeleteView"""

    def test_account_delete_requires_authentication(self, anonymous_client):
        """Test account delete redirects anonymous users"""
        response = anonymous_client.get(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 302

    def test_account_delete_get(self, authenticated_client):
        """Test account delete GET displays confirmation"""
        response = authenticated_client.get(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 200

    def test_account_delete_post(self, authenticated_client, user):
        """Test account deletion"""
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        user_id = user.id
        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 302
        assert not user_model.objects.filter(id=user_id).exists()
