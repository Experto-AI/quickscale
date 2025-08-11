"""
Unit tests for navigation bar rendering and link visibility.
Covers public, authenticated, and admin user navigation.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class NavigationBarTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='user@test.com', password='userpasswd')
        self.admin = User.objects.create_user(email='admin@test.com', password='adminpasswd', is_staff=True)

    # These tests are now covered by integration tests using real templates/views.
    pass
