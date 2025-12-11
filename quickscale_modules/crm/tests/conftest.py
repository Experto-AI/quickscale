"""Pytest fixtures for CRM module tests"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from quickscale_modules_crm.models import (
    Company,
    Contact,
    ContactNote,
    Deal,
    DealNote,
    Stage,
    Tag,
)


@pytest.fixture
def user(db):
    """Create a test user"""
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="TestPass123!",
    )


@pytest.fixture
def api_client():
    """Create an API client"""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Create an authenticated API client"""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def tag(db):
    """Create a test tag"""
    return Tag.objects.create(name="VIP")


@pytest.fixture
def company(db):
    """Create a test company"""
    return Company.objects.create(
        name="Acme Corp",
        industry="Technology",
        website="https://acme.example.com",
    )


@pytest.fixture
def contact(db, company):
    """Create a test contact"""
    return Contact.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        title="Sales Manager",
        company=company,
    )


@pytest.fixture
def stage(db):
    """Create a test stage"""
    return Stage.objects.create(name="Prospecting", order=1)


@pytest.fixture
def closed_won_stage(db):
    """Create Closed-Won stage"""
    return Stage.objects.create(name="Closed-Won", order=3)


@pytest.fixture
def closed_lost_stage(db):
    """Create Closed-Lost stage"""
    return Stage.objects.create(name="Closed-Lost", order=4)


@pytest.fixture
def deal(db, contact, stage, user):
    """Create a test deal"""
    return Deal.objects.create(
        title="Enterprise Deal",
        contact=contact,
        amount=Decimal("50000.00"),
        stage=stage,
        probability=75,
        owner=user,
    )


@pytest.fixture
def contact_note(db, contact, user):
    """Create a test contact note"""
    return ContactNote.objects.create(
        contact=contact,
        created_by=user,
        text="Discussed pricing options",
    )


@pytest.fixture
def deal_note(db, deal, user):
    """Create a test deal note"""
    return DealNote.objects.create(
        deal=deal,
        created_by=user,
        text="Follow up next week",
    )
