"""Pytest fixtures for auth module tests"""

import os

import pytest
from django.test import Client


# ---------------------------------------------------------------------------
# bypass_rls marker registration and collection-time opt-in
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register the bypass_rls marker to prevent PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "bypass_rls: test requires BYPASSRLS database privilege "
        "(superuser / migration DDL). Deselected unless QUICKSCALE_ALLOW_BYPASSRLS "
        "is exactly '1'.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Deselect bypass_rls tests unless QUICKSCALE_ALLOW_BYPASSRLS is exactly "1".

    Under NOBYPASSRLS (the default), migration tests and other
    BYPASSRLS-dependent tests are deselected so the suite passes
    cleanly with a restricted DB role.
    """
    if os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1":
        return  # Explicit BYPASSRLS authorization — run all tests
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("bypass_rls"):
            deselected.append(item)
        else:
            selected.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)


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
    from django.contrib.auth import get_user_model

    User = get_user_model()
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
