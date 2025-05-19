from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from ..models import StripeProduct
from decimal import Decimal

class StripeProductAdminTest(TestCase):
    """Test cases for StripeProduct admin interface."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin_user = get_user_model().objects.create_superuser(
            'admin@test.com',
            'adminpasswd'
        )
        self.client.login(email='admin@test.com', password='adminpasswd')
        
        self.product = StripeProduct.objects.create(
            name='Test Product',
            description='Test Description',
            price=Decimal('10.00'),
            currency='USD',
            interval='month',
            stripe_id='prod_test123',
            display_order=1,
            active=True
        )

    def test_list_display(self):
        """Test admin list display."""
        url = reverse('admin:stripe_manager_stripeproduct_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, '10.00')
        self.assertContains(response, 'USD')
        self.assertContains(response, 'Monthly')

    def test_search(self):
        """Test admin search functionality."""
        url = reverse('admin:stripe_manager_stripeproduct_changelist')
        response = self.client.get(url, {'q': self.product.name})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_filter(self):
        """Test admin filters."""
        url = reverse('admin:stripe_manager_stripeproduct_changelist')
        response = self.client.get(url, {'active__exact': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_edit_form(self):
        """Test admin edit form."""
        url = reverse('admin:stripe_manager_stripeproduct_change', args=[self.product.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, self.product.description)
        self.assertContains(response, str(self.product.price))

    def test_fieldset_organization(self):
        """Test fieldset organization in admin form."""
        url = reverse('admin:stripe_manager_stripeproduct_change', args=[self.product.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check for fieldset headers
        self.assertContains(response, 'Basic Information')
        self.assertContains(response, 'Pricing')
        self.assertContains(response, 'Display Settings')
        self.assertContains(response, 'System Information')

    def test_sync_action(self):
        """Test sync action in admin."""
        url = reverse('admin:stripe_manager_stripeproduct_sync', args=[self.product.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect after sync

    def test_bulk_sync_action(self):
        """Test bulk sync action."""
        url = reverse('admin:stripe_manager_stripeproduct_changelist')
        data = {
            'action': 'sync_selected',
            '_selected_action': [self.product.id]
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirect after sync 