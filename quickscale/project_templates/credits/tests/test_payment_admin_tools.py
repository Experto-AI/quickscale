"""Migrated from template validation tests."""

"""
Tests for Sprint 18 Payment Admin Tools functionality.

Tests payment search, payment investigation, and refund initiation features
for admin users in the QuickScale project generator template.
"""

import json
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock

# Set up template path and Django settings
from .base import DjangoIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.messages import get_messages

from credits.models import CreditAccount, CreditTransaction, Payment, UserSubscription
from stripe_manager.models import StripeProduct, StripeCustomer
from admin_dashboard.models import AuditLog
from admin_dashboard.utils import log_admin_action

User = get_user_model()

class PaymentSearchIntegrationTests(DjangoIntegrationTestCase):
    """Test payment search functionality for admin users."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for payment search tests."""
        # ...existing code...
