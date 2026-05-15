"""Shared pytest fixtures for the QuickScale billing module."""

from __future__ import annotations

import os

import django
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()


@pytest.fixture
def user(db):
    """Return a regular user for billing model tests."""

    user_model = get_user_model()
    return user_model.objects.create_user(
        username="billing-user",
        email="billing-user@example.com",
        password="billingpass123",
    )


@pytest.fixture
def superuser(db):
    """Return a superuser for admin tests."""

    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="billing-admin",
        email="billing-admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def admin_client(superuser) -> Client:
    """Return an authenticated Django client for admin requests."""

    client = Client()
    client.force_login(superuser)
    return client
