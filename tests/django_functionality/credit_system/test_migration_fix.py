"""Test that Sprint 8 migration implementation includes the Payment model."""

import unittest
from pathlib import Path


class Sprint8MigrationFixTests(unittest.TestCase):
    """Test cases for Sprint 8 Payment model implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.quickscale_root = Path(__file__).parent.parent.parent.parent
        self.credits_migrations_dir = self.quickscale_root / "quickscale" / "project_templates" / "credits" / "migrations"
    
    def test_payment_model_in_initial_migration(self):
        """Test that the Payment model is included in the initial migration."""
        migration_file = self.credits_migrations_dir / "0001_initial.py"
        self.assertTrue(migration_file.exists(), 
                       "Initial migration file should exist")
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check that the migration creates the Payment model
        self.assertIn("migrations.CreateModel", migration_content,
                     "Migration should create models")
        self.assertIn("name='Payment'", migration_content,
                     "Migration should create a model named 'Payment'")
        
        # Check for required Payment fields
        required_fields = [
            'stripe_payment_intent_id',
            'stripe_subscription_id', 
            'amount',
            'currency',
            'payment_type',
            'status',
            'description',
            'created_at',
            'updated_at',
            'user',
            'credit_transaction',
            'subscription'
        ]
        
        for field in required_fields:
            self.assertIn(field, migration_content,
                         f"Migration should include field '{field}'")
        
        # Check for payment type choices
        self.assertIn("CREDIT_PURCHASE", migration_content,
                     "Migration should include CREDIT_PURCHASE payment type")
        self.assertIn("SUBSCRIPTION", migration_content,
                     "Migration should include SUBSCRIPTION payment type")
        self.assertIn("REFUND", migration_content,
                     "Migration should include REFUND payment type")
        
        # Check for status choices
        self.assertIn("pending", migration_content,
                     "Migration should include 'pending' status")
        self.assertIn("succeeded", migration_content,
                     "Migration should include 'succeeded' status")
        self.assertIn("failed", migration_content,
                     "Migration should include 'failed' status")
    
    def test_payment_model_exists_in_models_file(self):
        """Test that the Payment model is properly defined in models.py."""
        models_file = self.quickscale_root / "quickscale" / "project_templates" / "credits" / "models.py"
        self.assertTrue(models_file.exists(), "Models file should exist")
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Check that Payment model is defined
        self.assertIn("class Payment(models.Model):", models_content,
                     "Payment model should be defined in models.py")
        
        # Check for required fields and methods
        required_elements = [
            'PAYMENT_TYPE_CHOICES',
            'STATUS_CHOICES',
            'stripe_payment_intent_id',
            'stripe_subscription_id',
            'amount',
            'currency',
            'payment_type',
            'status',
            'description',
            'user',
            'credit_transaction',
            'subscription',
            'receipt_data',
            'created_at',
            'updated_at'
        ]
        
        for element in required_elements:
            self.assertIn(element, models_content,
                         f"Payment model should include '{element}'")
    
    def test_payment_creation_in_webhook_handlers(self):
        """Test that Payment records are created in webhook handlers."""
        # Check that Payment model is imported in webhook views
        webhook_views_file = self.quickscale_root / "quickscale" / "project_templates" / "stripe_manager" / "views.py"
        
        with open(webhook_views_file, 'r') as f:
            webhook_content = f.read()
        
        # Check that Payment model is imported and used
        self.assertIn("from credits.models import", webhook_content,
                     "Webhook views should import from credits.models")
        self.assertIn("Payment", webhook_content,
                     "Webhook views should reference Payment model")
        
        # Check for payment creation logic
        self.assertIn("payment_type=", webhook_content,
                     "Webhook should handle payment types")
    
    def test_payment_creation_in_success_views(self):
        """Test that Payment records are created in success views as fallback."""
        # Check credit views
        credits_views_file = self.quickscale_root / "quickscale" / "project_templates" / "credits" / "views.py"
        
        with open(credits_views_file, 'r') as f:
            credits_content = f.read()
        
        self.assertIn("from credits.models import", credits_content,
                     "Credits views should import from credits.models")
        
        # Check admin dashboard views
        admin_views_file = self.quickscale_root / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        with open(admin_views_file, 'r') as f:
            admin_content = f.read()
        
        self.assertIn("from credits.models import", admin_content,
                     "Admin dashboard views should import from credits.models")
    
    def test_payment_indexes_in_migration(self):
        """Test that the Payment model has proper database indexes."""
        migration_file = self.credits_migrations_dir / "0001_initial.py"
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check for index creation related to payments
        self.assertIn("migrations.AddIndex", migration_content,
                     "Migration should add database indexes")
        
        # Check that Payment model has proper indexing setup
        self.assertIn("credits_pay", migration_content,
                     "Migration should include payment-related indexes")
        
        # Check for specific payment indexes
        expected_payment_indexes = [
            'credits_pay_user_id',
            'credits_pay_status',
            'credits_pay_payment',
            'credits_pay_stripe_',
            'credits_pay_created'
        ]
        
        for index_pattern in expected_payment_indexes:
            self.assertIn(index_pattern, migration_content,
                         f"Migration should include payment index pattern '{index_pattern}'")

if __name__ == '__main__':
    unittest.main() 