"""Pytest configuration for blog module tests"""

import django
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

# Configure Django before importing models
if not settings.configured:
    from tests import settings as test_settings

    settings.configure(default_settings=test_settings)
    django.setup()

User = get_user_model()


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Set up test database with migrations"""
    from django.core.management import call_command

    with django_db_blocker.unblock():
        call_command("migrate", "--run-syncdb", verbosity=0)


@pytest.fixture
def user(db):
    """Create a test user"""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def author_user(db):
    """Create a test user for blog posts"""
    return User.objects.create_user(
        username="author",
        email="author@example.com",
        password="authorpass123",
        first_name="Test",
        last_name="Author",
    )
