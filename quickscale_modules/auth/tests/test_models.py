"""Tests for auth module models"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Tests for custom User model"""

    def test_create_user(self, user_data):
        """Test creating a user with valid data"""
        user = User.objects.create_user(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
        )

        assert user.username == user_data["username"]
        assert user.email == user_data["email"]
        assert user.check_password(user_data["password"])
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self, user_data):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
        )

        assert user.is_active
        assert user.is_staff
        assert user.is_superuser

    def test_user_string_representation(self, user):
        """Test __str__ returns full name or username"""
        assert str(user) == "Test User"

        # Test with no full name
        user.first_name = ""
        user.last_name = ""
        user.save()
        assert str(user) == user.username

    def test_get_absolute_url(self, user):
        """Test get_absolute_url returns profile URL"""
        url = user.get_absolute_url()
        assert url == "/accounts/profile/"

    def test_get_display_name(self, user):
        """Test get_display_name returns full name or username"""
        assert user.get_display_name() == "Test User"

        user.first_name = ""
        user.last_name = ""
        assert user.get_display_name() == user.username

    def test_user_ordering(self, db):
        """Test users are ordered by date_joined descending"""
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="pass"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="pass"
        )

        users = list(User.objects.all())
        assert users[0] == user2  # Most recent first
        assert users[1] == user1
