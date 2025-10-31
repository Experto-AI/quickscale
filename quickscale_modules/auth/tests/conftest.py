"""Pytest fixtures for auth module tests"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def user_data():
    """Standard user data for testing"""
    return {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "TestPass123!",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def user(db, user_data):
    """Create a test user"""
    return User.objects.create_user(
        username=user_data["username"],
        email=user_data["email"],
        password=user_data["password"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
    )


@pytest.fixture
def authenticated_client(db, user):
    """Client with authenticated user"""
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def anonymous_client():
    """Anonymous client"""
    return Client()
