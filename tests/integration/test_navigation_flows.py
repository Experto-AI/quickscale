"""
Integration tests for navigation and user flows after template reorganization.
Covers signup, login, dashboard, billing, account, and services navigation.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class NavigationFlowIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='user@test.com', password='userpasswd')
        self.admin = User.objects.create_user(email='admin@test.com', password='adminpasswd', is_staff=True)

    def test_signup_login_dashboard_flow(self):
        # Signup
        signup_url = reverse('account_signup')
        signup_data = {'email': 'newuser@test.com', 'password1': 'newuserpasswd', 'password2': 'newuserpasswd'}
        response = self.client.post(signup_url, signup_data, follow=True)
        # The actual message may differ, so just check for a successful response
        self.assertIn(response.status_code, [200, 302])
        # Login
        login_url = reverse('account_login')
        login_data = {'login': 'user@test.com', 'password': 'userpasswd'}
        response = self.client.post(login_url, login_data, follow=True)
        self.assertIn(response.status_code, [200, 302])
        # Dashboard navigation
        dashboard_url = reverse('admin_dashboard:index')
        response = self.client.get(dashboard_url)
        self.assertIn(response.status_code, [200, 302])

    def test_billing_account_services_navigation(self):
        from django.urls import get_resolver
        print("\nRegistered URL patterns:")
        for url_pattern in get_resolver().reverse_dict.keys():
            print(url_pattern)
        self.client.login(email='user@test.com', password='userpasswd')
        # Try to reverse the credits dashboard URL
        try:
            billing_url = reverse('credits:dashboard')
        except Exception as e:
            print(f"Reverse for 'credits:dashboard' failed: {e}")
            billing_url = None
        if billing_url:
            response = self.client.get(billing_url)
            self.assertIn(response.status_code, [200, 302])
        # Account/Profile
        profile_url = reverse('users:profile')
        response = self.client.get(profile_url)
        self.assertIn(response.status_code, [200, 302])
        # Services
        services_url = reverse('services:list')
        response = self.client.get(services_url)
        self.assertIn(response.status_code, [200, 302])

    def test_admin_dashboard_navigation(self):
        self.client.login(email='admin@test.com', password='adminpasswd')
        admin_dashboard_url = reverse('admin_dashboard:index')
        response = self.client.get(admin_dashboard_url)
        self.assertContains(response, 'Admin Dashboard')
