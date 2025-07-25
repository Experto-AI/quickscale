"""Tests for stripe_manager app registration and template tag discovery."""

import os
import pytest
from unittest import mock
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.template import Template, Context, TemplateSyntaxError


class TestStripeAppRegistration(TestCase):
    """Test that the stripe_manager app is correctly registered in the system."""

    def test_app_in_installed_apps(self):
        """Test that stripe_manager app is properly registered in INSTALLED_APPS."""
        from django.apps import apps
        self.assertTrue(apps.is_installed('stripe_manager'), 
                        "stripe_manager app is not found in installed apps")

    @override_settings(INSTALLED_APPS=['django.contrib.auth', 'stripe_manager.apps.StripeConfig'])
    def test_app_config_loads_correctly(self):
        """Test that the app config for stripe_manager loads correctly."""
        from django.apps import apps
        app_config = apps.get_app_config('stripe_manager')
        self.assertEqual(app_config.name, 'stripe_manager')
        self.assertEqual(app_config.verbose_name, 'Stripe Integration')


class TestStripeTemplateTagsRegistration(TestCase):
    """Test the registration and discovery of stripe template tags."""

    @patch('core.env_utils.is_feature_enabled')
    def test_template_tags_load_when_stripe_enabled(self, mock_is_enabled):
        """Test that stripe_tags can be loaded when Stripe is enabled."""
        mock_is_enabled.return_value = True
        
        # Test template tag loading directly
        template = Template("{% load stripe_tags %}")
        context = Context({})
        # If it renders without error, the tag library was loaded successfully
        self.assertEqual(template.render(context), "")

    @patch('core.env_utils.is_feature_enabled')
    def test_template_tags_not_needed_when_stripe_disabled(self, mock_is_enabled):
        """Test handling when Stripe is disabled."""
        mock_is_enabled.return_value = False
        
        # Create a template that handles conditionally loading stripe_tags
        template_str = """
        {% if stripe_enabled %}
            {% load stripe_tags %}
            {{ price|format_stripe_price }}
        {% else %}
            Price unavailable
        {% endif %}
        """
        
        template = Template(template_str)
        context = Context({
            'stripe_enabled': False,
            'price': {'unit_amount': 1000, 'currency': 'usd'}
        })
        
        # Should render without error, showing the fallback text
        self.assertIn("Price unavailable", template.render(context).strip())

    def test_format_stripe_price_filter_registered(self):
        """Test that format_stripe_price filter is properly registered."""
        from django.template.defaultfilters import get_filter_by_name
        
        try:
            # This should be available when stripe_tags is properly registered
            filter_func = get_filter_by_name('format_stripe_price')
            self.assertIsNotNone(filter_func)
        except Exception as e:
            self.fail(f"format_stripe_price filter not registered: {e}")

    def test_conditional_loading_in_template(self):
        """Test loading stripe_tags conditionally inside a template."""
        # Create a template that conditionally loads the tag library
        template_str = """
        {% load static %}
        {% if stripe_enabled %}
            {% load stripe_tags %}
            {{ price|format_stripe_price }}
        {% else %}
            <span class="tag is-warning">Price info unavailable</span>
        {% endif %}
        """
        
        # Test with stripe enabled
        with patch('core.env_utils.is_feature_enabled', return_value=True):
            template = Template(template_str)
            price = {'unit_amount': 1000, 'currency': 'usd'}
            context = Context({
                'stripe_enabled': True,
                'price': price
            })
            
            # Should load stripe_tags and format the price
            rendered = template.render(context)
            self.assertIn("$10.00", rendered)
        
        # Test with stripe disabled
        with patch('core.env_utils.is_feature_enabled', return_value=False):
            template = Template(template_str)
            context = Context({
                'stripe_enabled': False,
                'price': None
            })
            
            # Should show the fallback message without trying to load stripe_tags
            rendered = template.render(context)
            self.assertIn("Price info unavailable", rendered) 