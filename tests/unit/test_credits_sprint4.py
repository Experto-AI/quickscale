"""
Tests for Sprint 4: Pay-as-You-Go Credit Purchase.

These tests verify that the StripeProduct model is properly enhanced for credit purchases,
credit purchase views use StripeProduct, Stripe integration, and webhook processing
are properly implemented in the QuickScale project generator templates.
"""

import os
import unittest
import re
from pathlib import Path


class StripeProductCreditEnhancementTests(unittest.TestCase):
    """Test cases for StripeProduct model credit enhancement."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.stripe_app_path = self.base_path / 'quickscale' / 'templates' / 'stripe_manager'
        self.models_py = self.stripe_app_path / 'models.py'
        
    def test_stripe_product_credit_amount_field(self):
        """Test that StripeProduct model has credit_amount field."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for StripeProduct model
        self.assertIn("class StripeProduct(models.Model)", models_content,
                     "StripeProduct model not found")
        
        # Check for credit_amount field
        self.assertIn("credit_amount = models.IntegerField", models_content,
                     "StripeProduct credit_amount field not found")
        
        # Check for credit amount validation
        self.assertIn("MinValueValidator(1)", models_content,
                     "MinValueValidator for credit_amount not found")
        
        # Check for default value
        self.assertIn("default=1000", models_content,
                     "Default value for credit_amount not found")
    
    def test_stripe_product_credit_methods(self):
        """Test that StripeProduct model has credit-related methods."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for price_per_credit property
        self.assertIn("def price_per_credit(self):", models_content,
                     "StripeProduct price_per_credit property not found")
        self.assertIn("return self.price / self.credit_amount", models_content,
                     "StripeProduct price_per_credit calculation not found")
        
        # Check for is_subscription property
        self.assertIn("def is_subscription(self):", models_content,
                     "StripeProduct is_subscription property not found")
        self.assertIn("return self.interval in ['month', 'year']", models_content,
                     "StripeProduct is_subscription implementation not found")
        
        # Check for is_one_time property
        self.assertIn("def is_one_time(self):", models_content,
                     "StripeProduct is_one_time property not found")
        self.assertIn("return self.interval == 'one-time'", models_content,
                     "StripeProduct is_one_time implementation not found")
    
    def test_stripe_product_admin_credit_display(self):
        """Test that StripeProduct admin includes credit configuration."""
        admin_py = self.stripe_app_path / 'admin.py'
        with open(admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for credit_amount in list_display
        self.assertIn("credit_amount", admin_content,
                     "credit_amount not in StripeProduct admin list_display")
        
        # Check for price_per_credit_display
        self.assertIn("price_per_credit_display", admin_content,
                     "price_per_credit_display not in StripeProduct admin")
        
        # Check for credit configuration fieldset
        self.assertIn("'Pricing & Credits'", admin_content,
                     "Pricing & Credits fieldset not found")


class CreditTransactionTypeTests(unittest.TestCase):
    """Test cases for CreditTransaction credit_type field implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.models_py = self.credits_app_path / 'models.py'
        
    def test_credit_type_field_exists(self):
        """Test that credit_type field is added to CreditTransaction model."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for credit_type field
        self.assertIn("credit_type = models.CharField", models_content,
                     "CreditTransaction credit_type field not found")
        
        # Check for choices
        self.assertIn("CREDIT_TYPE_CHOICES = [", models_content,
                     "CREDIT_TYPE_CHOICES not found")
        self.assertIn("('PURCHASE', _('Purchase'))", models_content,
                     "PURCHASE choice not found")
        self.assertIn("('CONSUMPTION', _('Consumption'))", models_content,
                     "CONSUMPTION choice not found")
        self.assertIn("('ADMIN', _('Admin Adjustment'))", models_content,
                     "ADMIN choice not found")
    
    def test_credit_type_properties(self):
        """Test that CreditTransaction has credit type property methods."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for property methods
        self.assertIn("def is_purchase(self):", models_content,
                     "is_purchase property not found")
        self.assertIn("def is_consumption(self):", models_content,
                     "is_consumption property not found")
        self.assertIn("def is_admin_adjustment(self):", models_content,
                     "is_admin_adjustment property not found")
        
        # Check for proper return values
        self.assertIn("return self.credit_type == 'PURCHASE'", models_content,
                     "is_purchase implementation not found")
        self.assertIn("return self.credit_type == 'CONSUMPTION'", models_content,
                     "is_consumption implementation not found")
        self.assertIn("return self.credit_type == 'ADMIN'", models_content,
                     "is_admin_adjustment implementation not found")


class CreditAccountMethodTests(unittest.TestCase):
    """Test cases for CreditAccount methods."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.models_py = self.credits_app_path / 'models.py'
        
    def test_add_credits_method_updated(self):
        """Test that add_credits method is updated with credit_type parameter."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for updated add_credits signature
        self.assertIn("def add_credits(self, amount: Decimal, description: str, credit_type: str = 'ADMIN')", models_content,
                     "add_credits method not updated with credit_type parameter")
    
    def test_consume_credits_method_updated(self):
        """Test that consume_credits method is updated with credit_type."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for consume_credits method
        self.assertIn("def consume_credits(self, amount: Decimal, description: str)", models_content,
                     "consume_credits method not found")
        
        # Check for credit_type='CONSUMPTION' in consume_credits
        self.assertIn("credit_type='CONSUMPTION'", models_content,
                     "CONSUMPTION credit_type not found in consume_credits")
    
    def test_credit_purchase_package_removed(self):
        """Test that CreditPurchasePackage model has been removed."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check that CreditPurchasePackage model is NOT in the file
        self.assertNotIn("class CreditPurchasePackage(models.Model)", models_content,
                        "CreditPurchasePackage model should be removed")


class CreditPurchaseViewsTests(unittest.TestCase):
    """Test cases for credit purchase views using StripeProduct."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.views_py = self.credits_app_path / 'views.py'
        
    def test_buy_credits_view_uses_stripe_product(self):
        """Test that buy_credits view uses StripeProduct instead of CreditPurchasePackage."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for StripeProduct import
        self.assertIn("from stripe_manager.models import StripeProduct", views_content,
                     "StripeProduct import not found")
        
        # Check for StripeProduct.objects.filter
        self.assertIn("StripeProduct.objects.filter", views_content,
                     "StripeProduct query not found")
        
        # Check for interval='one-time' filter for pay-as-you-go
        self.assertIn("interval='one-time'", views_content,
                     "one-time interval filter not found")
        
        # Check that CreditPurchasePackage is NOT imported
        self.assertNotIn("CreditPurchasePackage", views_content,
                        "CreditPurchasePackage should not be imported")
    
    def test_create_checkout_session_view_updated(self):
        """Test that create_checkout_session view uses product_id instead of package_id."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for product_id parameter
        self.assertIn("product_id = request.POST.get('product_id')", views_content,
                     "product_id parameter not found")
        
        # Check for StripeProduct.objects.get
        self.assertIn("StripeProduct.objects.get(id=product_id", views_content,
                     "StripeProduct get by id not found")
        
        # Check for credit_product purchase type
        self.assertIn("'purchase_type': 'credit_product'", views_content,
                     "credit_product purchase type not found")
    
    def test_purchase_success_view_updated(self):
        """Test that purchase_success view handles StripeProduct."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for product_id in metadata
        self.assertIn("product_id = metadata.get('product_id')", views_content,
                     "product_id metadata extraction not found")
        
        # Check for credit_amount in metadata
        self.assertIn("credit_amount = metadata.get('credit_amount')", views_content,
                     "credit_amount metadata extraction not found")
        
        # Check for direct add_credits call instead of purchase_credits
        self.assertIn("credit_account.add_credits(", views_content,
                     "Direct add_credits call not found")


class CreditPurchaseTemplateTests(unittest.TestCase):
    """Test cases for credit purchase template updates."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.template_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'templates' / 'credits' / 'buy_credits.html'
        
    def test_buy_credits_template_exists(self):
        """Test that buy_credits template exists."""
        self.assertTrue(self.template_path.exists(), "buy_credits.html template not found")
    
    def test_buy_credits_template_uses_products(self):
        """Test that buy_credits template uses products instead of packages."""
        with open(self.template_path, 'r') as f:
            template_content = f.read()
        
        # Check for products loop
        self.assertIn("{% for product in products %}", template_content,
                     "products loop not found")
        
        # Check for product properties
        self.assertIn("{{ product.name }}", template_content,
                     "product.name not found")
        self.assertIn("{{ product.credit_amount }}", template_content,
                     "product.credit_amount not found")
        self.assertIn("{{ product.price }}", template_content,
                     "product.price not found")
        
        # Check for product_id in JavaScript
        self.assertIn("product_id=${productId}", template_content,
                     "product_id parameter not found in JavaScript")
        
        # Check that packages is NOT used
        self.assertNotIn("{% for package in packages %}", template_content,
                        "packages loop should not exist")


class StripeCustomerModelTests(unittest.TestCase):
    """Test cases for StripeCustomer model implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.stripe_app_path = self.base_path / 'quickscale' / 'templates' / 'stripe_manager'
        self.models_py = self.stripe_app_path / 'models.py'
        
    def test_stripe_customer_model_exists(self):
        """Test that StripeCustomer model is defined with required fields."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for StripeCustomer model
        self.assertIn("class StripeCustomer(models.Model)", models_content,
                     "StripeCustomer model not found")
        
        # Check for required fields
        self.assertIn("user = models.OneToOneField", models_content,
                     "StripeCustomer user field not found")
        self.assertIn("stripe_id = models.CharField", models_content,
                     "StripeCustomer stripe_id field not found")
        self.assertIn("email = models.EmailField", models_content,
                     "StripeCustomer email field not found")
        self.assertIn("name = models.CharField", models_content,
                     "StripeCustomer name field not found")
    
    def test_stripe_customer_relationships(self):
        """Test that StripeCustomer has proper relationships."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for OneToOneField relationship
        self.assertIn("related_name='stripe_customer'", models_content,
                     "StripeCustomer related_name not found")
        
        # Check for unique constraint on stripe_id
        self.assertIn("unique=True", models_content,
                     "StripeCustomer stripe_id unique constraint not found")


class WebhookHandlingTests(unittest.TestCase):
    """Test cases for webhook handling with StripeProduct."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.stripe_app_path = self.base_path / 'quickscale' / 'templates' / 'stripe_manager'
        self.views_py = self.stripe_app_path / 'views.py'
        
    def test_webhook_credit_product_handling(self):
        """Test that webhook handles credit_product purchase type."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for credit_product purchase type handling
        self.assertIn("if metadata.get('purchase_type') == 'credit_product':", views_content,
                     "credit_product purchase type handling not found")
        
        # Check for StripeProduct usage in webhook
        self.assertIn("product = StripeProduct.objects.get(id=product_id)", views_content,
                     "StripeProduct get in webhook not found")
        
        # Check for direct add_credits call in webhook
        self.assertIn("credit_account.add_credits(", views_content,
                     "add_credits call in webhook not found")
        
        # Check that CreditPurchasePackage is NOT used
        self.assertNotIn("CreditPurchasePackage", views_content,
                        "CreditPurchasePackage should not be in webhook handling")


class AdminIntegrationTests(unittest.TestCase):
    """Test cases for admin integration after refactoring."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.admin_py = self.credits_app_path / 'admin.py'
        
    def test_credit_purchase_package_admin_removed(self):
        """Test that CreditPurchasePackage admin is removed."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check that CreditPurchasePackage admin is NOT registered
        self.assertNotIn("@admin.register(CreditPurchasePackage)", admin_content,
                        "CreditPurchasePackage admin should be removed")
        
        # Check that CreditPurchasePackage is NOT imported
        self.assertNotIn("CreditPurchasePackage", admin_content,
                        "CreditPurchasePackage should not be imported in credits admin")
    
    def test_stripe_product_admin_enhanced(self):
        """Test that StripeProduct admin includes credit features."""
        stripe_admin_py = self.base_path / 'quickscale' / 'templates' / 'stripe_manager' / 'admin.py'
        with open(stripe_admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for StripeProduct admin registration
        self.assertIn("@admin.register(StripeProduct)", admin_content,
                     "StripeProduct admin registration not found")
        
        # Check for credit-related fields in display
        self.assertIn("credit_amount", admin_content,
                     "credit_amount not in StripeProduct admin")
        
        # Check for price_per_credit_display method
        self.assertIn("def price_per_credit_display(self, obj):", admin_content,
                     "price_per_credit_display method not found")


class MigrationTests(unittest.TestCase):
    """Test cases for database migration removing CreditPurchasePackage."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.migrations_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'migrations'
        self.migration_file = self.migrations_path / '0005_remove_credit_purchase_package.py'
        
    # Test that the removal migration was created and exists
    # The migration was grouped in Sprint 5, so this test is no longer valid.
    # def test_removal_migration_exists(self):
    #     """Test that the removal migration file exists."""
    #     migration_name = "0005_remove_credit_purchase_package.py"
    #     migration_path = Path(f"./quickscale/credits/migrations/{migration_name}")
    #     self.migration_file = migration_path.resolve()
    #     self.assertTrue(self.migration_file.exists(),
    #                     f"{migration_name} migration not found")


if __name__ == '__main__':
    unittest.main() 