from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from ..models import StripeProduct

class StripeProductModelTest(TestCase):
    """Test cases for StripeProduct model."""

    def setUp(self):
        """Set up test data."""
        self.product_data = {
            'name': 'Test Product',
            'description': 'Test Description',
            'price': Decimal('10.00'),
            'currency': 'USD',
            'interval': 'month',
            'stripe_id': 'prod_test123',
            'display_order': 1,
            'active': True
        }

    def test_create_product(self):
        """Test product creation."""
        product = StripeProduct.objects.create(**self.product_data)
        self.assertEqual(product.name, self.product_data['name'])
        self.assertEqual(product.price, self.product_data['price'])
        self.assertEqual(product.currency, self.product_data['currency'])
        self.assertEqual(product.interval, self.product_data['interval'])
        self.assertEqual(product.stripe_id, self.product_data['stripe_id'])
        self.assertEqual(product.display_order, self.product_data['display_order'])
        self.assertTrue(product.active)

    def test_product_ordering(self):
        """Test product ordering by display_order."""
        # Create products in reverse order
        StripeProduct.objects.create(
            **{**self.product_data, 'display_order': 2, 'name': 'Second'}
        )
        StripeProduct.objects.create(
            **{**self.product_data, 'display_order': 1, 'name': 'First'}
        )
        
        products = StripeProduct.objects.all()
        self.assertEqual(products[0].name, 'First')
        self.assertEqual(products[1].name, 'Second')

    def test_negative_price_validation(self):
        """Test price validation."""
        with self.assertRaises(ValidationError):
            StripeProduct.objects.create(
                **{**self.product_data, 'price': Decimal('-10.00')}
            )

    def test_invalid_currency(self):
        """Test currency validation."""
        with self.assertRaises(ValidationError):
            StripeProduct.objects.create(
                **{**self.product_data, 'currency': 'INVALID'}
            )

    def test_invalid_interval(self):
        """Test interval validation."""
        with self.assertRaises(ValidationError):
            StripeProduct.objects.create(
                **{**self.product_data, 'interval': 'invalid'}
            )

    def test_duplicate_stripe_id(self):
        """Test unique stripe_id constraint."""
        StripeProduct.objects.create(**self.product_data)
        with self.assertRaises(ValidationError):
            StripeProduct.objects.create(**self.product_data)

    def test_str_representation(self):
        """Test string representation."""
        product = StripeProduct.objects.create(**self.product_data)
        expected = f"{self.product_data['name']} (Monthly)"
        self.assertEqual(str(product), expected) 