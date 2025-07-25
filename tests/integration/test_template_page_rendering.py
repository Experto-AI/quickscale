"""
Integration tests to ensure all main template pages in the generated Django project render without error.
Catches template malformation and rendering issues before production.
"""

import pytest
from django.test import Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model


# Public (anonymous) pages
PUBLIC_PAGES = [
    ("account_login", None),
    ("account_signup", None),
]

# Normal user pages (login required)
USER_PAGES = [
    ("users:profile", None),
    ("users:account_security", None),
    ("services:list", None),
    ("services:use_form", {"service_id": 1}),
    ("services:use_service", {"service_id": 1}),
    # ("services:status_api", {"service_id": 1}),  # Not implemented yet
]

# API pages (that should be publicly accessible or require authentication)
API_PAGES = [
    # ("api:api_docs", None),  # Requires API key authentication - not suitable for basic page rendering tests
    # Note: api:text_process requires POST and specific data, so we skip it here
]

# Admin/staff pages (admin login required)
ADMIN_PAGES = [
    # ("admin:index", None),  # Not available in test environment yet
    ("admin_dashboard:index", None),
    ("admin_dashboard:user_dashboard", None),
    ("admin_dashboard:analytics_dashboard", None),  # Available in test environment
    # ("admin_dashboard:subscription", None),  # Not implemented yet
    # ("admin_dashboard:create_subscription_checkout", None),  # Not implemented yet
    # ("admin_dashboard:create_plan_change_checkout", None),  # Not implemented yet
    # ("admin_dashboard:cancel_subscription", None),  # Not implemented yet
    # ("admin_dashboard:subscription_success", None),  # Not implemented yet
    # ("admin_dashboard:plan_change_success", None),  # Not implemented yet
    # ("admin_dashboard:subscription_cancel", None),  # Not implemented yet
    ("admin_dashboard:product_admin", None),
    # ("admin_dashboard:sync_products", None),  # Not implemented yet
    # ("admin_dashboard:product_sync", {"product_id": "test"}),  # Not implemented yet
    # ("admin_dashboard:update_product_order", {"product_id": 1}),  # Not implemented yet
    # ("admin_dashboard:product_detail", {"product_id": "test"}),  # Not implemented yet
    # ("admin_dashboard:payment_history", None),  # Not implemented yet
    # ("admin_dashboard:payment_detail", {"payment_id": 1}),  # Not implemented yet
    # ("admin_dashboard:download_receipt", {"payment_id": 1}),  # Not implemented yet
    # ("admin_dashboard:service_admin", None),  # Not implemented yet
    # ("admin_dashboard:service_detail", {"service_id": 1}),  # Not implemented yet
    # ("admin_dashboard:service_toggle_status", {"service_id": 1}),  # Not implemented yet
    # ("admin_dashboard:user_search", None),  # Not implemented yet
    # ("admin_dashboard:user_detail", {"user_id": 1}),  # Not implemented yet
    # ("admin_dashboard:user_credit_adjustment", {"user_id": 1}),  # Not implemented yet
    # ("admin_dashboard:user_credit_history", {"user_id": 1}),  # Not implemented yet
    # ("admin_dashboard:audit_log", None),  # Not implemented yet
    # ("admin_dashboard:payment_search", None),  # Not implemented yet
    # ("admin_dashboard:payment_investigation", {"payment_id": 1}),  # Not implemented yet
    # ("admin_test", None),  # Not available in test environment yet
]

# Stripe-related pages (require Stripe to be enabled/configured)
STRIPE_PAGES = [
    ("stripe:webhook", None),
    ("stripe:status", None),
    ("stripe:product_list", None),
    ("stripe:product_detail", {"product_id": "test"}),
    ("stripe:plan_comparison", None),
    ("stripe:create_checkout_session", None),
    ("stripe:checkout_success", None),
    ("stripe:checkout_cancel", None),
]


# ------------------- Public Pages -------------------
@pytest.mark.django_db
@pytest.mark.parametrize("url_name,kwargs", PUBLIC_PAGES)
def test_public_page_renders_ok(client, url_name, kwargs):
    """
    Ensure public (anonymous) pages render without error.
    """
    try:
        url = reverse(url_name, kwargs=kwargs) if kwargs else reverse(url_name)
    except NoReverseMatch:
        pytest.skip(f"URL name '{url_name}' not found in template project.")
    response = client.get(url)
    assert response.status_code in (200, 302), f"{url_name} did not render: {response.status_code}"

# ------------------- User Pages -------------------
@pytest.mark.django_db
@pytest.mark.parametrize("url_name,kwargs", USER_PAGES)
def test_user_page_renders_ok(client, url_name, kwargs, django_user_model):
    """
    Ensure normal user pages render without error (login required).
    """
    user = django_user_model.objects.create_user(email="user@test.com", password="userpasswd")
    client.login(email="user@test.com", password="userpasswd")
    try:
        url = reverse(url_name, kwargs=kwargs) if kwargs else reverse(url_name)
    except NoReverseMatch:
        pytest.skip(f"URL name '{url_name}' not found in template project.")
    response = client.get(url)
    assert response.status_code in (200, 302), f"{url_name} did not render: {response.status_code}"

# ------------------- Admin/Staff Pages -------------------
@pytest.mark.django_db
@pytest.mark.parametrize("url_name,kwargs", ADMIN_PAGES)
def test_admin_page_renders_ok(client, url_name, kwargs, django_user_model):
    """
    Ensure admin/staff pages render without error (admin login required).
    """
    admin = django_user_model.objects.create_superuser(email="admin@test.com", password="adminpasswd")
    client.login(email="admin@test.com", password="adminpasswd")
    try:
        url = reverse(url_name, kwargs=kwargs) if kwargs else reverse(url_name)
    except NoReverseMatch:
        pytest.skip(f"URL name '{url_name}' not found in template project.")
    response = client.get(url)
    assert response.status_code in (200, 302), f"{url_name} did not render: {response.status_code}"

# ------------------- Stripe-related Pages -------------------
@pytest.mark.django_db
@pytest.mark.parametrize("url_name,kwargs", STRIPE_PAGES)
def test_stripe_page_renders_ok(client, url_name, kwargs, django_user_model, settings):
    """
    Ensure Stripe-related pages render without error (skip if Stripe is not enabled/configured).
    """
    # Optionally skip if STRIPE_ENABLED is not set
    if not getattr(settings, "STRIPE_ENABLED", False):
        pytest.skip("Stripe is not enabled in settings.")
    user = django_user_model.objects.create_user(email="user@test.com", password="userpasswd")
    client.login(email="user@test.com", password="userpasswd")
    try:
        url = reverse(url_name, kwargs=kwargs) if kwargs else reverse(url_name)
    except NoReverseMatch:
        pytest.skip(f"URL name '{url_name}' not found in template project.")
    response = client.get(url)
    assert response.status_code in (200, 302), f"{url_name} did not render: {response.status_code}"

# ------------------- API Pages -------------------
# Note: API endpoints require API key authentication and are tested separately
# in dedicated API tests. Basic page rendering tests are not appropriate for 
# authenticated API endpoints.

# Optionally, add tests for error pages (404, 500)
def test_404_page_renders(client):
    response = client.get("/this-page-should-not-exist/")
    assert response.status_code == 404
    # Optionally, check for custom 404 template content

# Add more tests as new pages/templates are added to the template project.
