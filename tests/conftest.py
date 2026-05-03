"""Pytest configuration for blog module tests"""

import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

# Configure Django before importing models
if not settings.configured:
    settings_path = Path(__file__).with_name("settings.py")
    settings_module_name = "quickscale_modules_blog_test_settings"
    settings_spec = spec_from_file_location(settings_module_name, settings_path)
    if settings_spec is None or settings_spec.loader is None:
        raise RuntimeError(f"Unable to load blog test settings from {settings_path}")
    test_settings = module_from_spec(settings_spec)
    sys.modules[settings_module_name] = test_settings
    settings_spec.loader.exec_module(test_settings)

    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module_name
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
