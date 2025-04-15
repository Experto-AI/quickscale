"""
Tests for the Product model.
"""

from django.test import TestCase
from decimal import Decimal
from ..models import Product


class ProductModelTests(TestCase):
    """
    Tests for the Product model.
    """
    
    def setUp(self):
        """Set up test data."""
        self.product = Product.objects.create(
            name="Test Product",
            description="This is a test product",
            base_price=Decimal("19.99"),
            currency="USD",
            status=Product.ACTIVE
        )
    
    def test_product_creation(self):
        """Test that a product can be created with required fields."""
        self.assertEqual(self.product.name, "Test Product")
        self.assertEqual(self.product.description, "This is a test product")
        self.assertEqual(self.product.base_price, Decimal("19.99"))
        self.assertEqual(self.product.currency, "USD")
        self.assertEqual(self.product.status, Product.ACTIVE)
        
        # Test default values
        self.assertIsNone(self.product.image)
        self.assertIsNone(self.product.metadata)
        self.assertIsNone(self.product.stripe_product_id)
        
        # Test auto-generated fields
        self.assertIsNotNone(self.product.created)
        self.assertIsNotNone(self.product.updated)
    
    def test_product_string_representation(self):
        """Test the string representation of a product."""
        self.assertEqual(str(self.product), "Test Product")
    
    def test_is_active_method(self):
        """Test the is_active() method."""
        self.assertTrue(self.product.is_active())
        
        # Change status to inactive
        self.product.status = Product.INACTIVE
        self.product.save()
        self.assertFalse(self.product.is_active())
    
    def test_get_formatted_price_usd(self):
        """Test formatted price with USD currency."""
        self.assertEqual(self.product.get_formatted_price(), "$19.99")
    
    def test_get_formatted_price_eur(self):
        """Test formatted price with EUR currency."""
        self.product.currency = "EUR"
        self.product.base_price = Decimal("29.99")
        self.product.save()
        self.assertEqual(self.product.get_formatted_price(), "€29.99")
    
    def test_get_formatted_price_jpy(self):
        """Test formatted price with JPY currency (no decimal places)."""
        self.product.currency = "JPY"
        self.product.base_price = Decimal("1999")
        self.product.save()
        self.assertEqual(self.product.get_formatted_price(), "¥1999")
    
    def test_get_formatted_price_unknown_currency(self):
        """Test formatted price with unknown currency."""
        self.product.currency = "XYZ"
        self.product.base_price = Decimal("99.99")
        self.product.save()
        self.assertEqual(self.product.get_formatted_price(), "XYZ99.99")
    
    def test_ordering(self):
        """Test that products are ordered by created date (newest first)."""
        # Create another product
        product2 = Product.objects.create(
            name="Another Product",
            base_price=Decimal("29.99"),
            currency="USD"
        )
        
        # Get all products ordered by -created (default ordering)
        products = Product.objects.all()
        
        # Second product should come first (more recent)
        self.assertEqual(products[0].id, product2.id)
        self.assertEqual(products[1].id, self.product.id)
    
    def test_metadata_field(self):
        """Test the metadata JSON field."""
        # Update metadata
        metadata = {
            "color": "Blue",
            "weight": "0.5kg",
            "dimensions": {
                "length": 10,
                "width": 5,
                "height": 2
            }
        }
        self.product.metadata = metadata
        self.product.save()
        
        # Retrieve the product and check metadata
        retrieved_product = Product.objects.get(id=self.product.id)
        self.assertEqual(retrieved_product.metadata, metadata)
        self.assertEqual(retrieved_product.metadata["color"], "Blue")
        self.assertEqual(retrieved_product.metadata["dimensions"]["length"], 10) 