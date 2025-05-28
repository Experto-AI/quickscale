"""Test that Sprint 8 migration fix resolves the Payment model database table issue."""

import unittest
from pathlib import Path


class Sprint8MigrationFixTests(unittest.TestCase):
    """Test cases for Sprint 8 migration fix."""
    
    def setUp(self):
        """Set up test environment."""
        self.quickscale_root = Path(__file__).parent.parent.parent
        self.credits_migrations_dir = self.quickscale_root / "quickscale" / "templates" / "credits" / "migrations"
    
    def test_payment_migration_exists(self):
        """Test that the Payment model migration file exists."""
        migration_file = self.credits_migrations_dir / "0003_add_payment_model.py"
        self.assertTrue(migration_file.exists(), 
                       "Payment model migration file 0003_add_payment_model.py should exist")
    
    def test_migration_creates_payment_table(self):
        """Test that the migration contains the Payment model creation."""
        migration_file = self.credits_migrations_dir / "0003_add_payment_model.py"
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check that the migration creates the Payment model
        self.assertIn("migrations.CreateModel", migration_content,
                     "Migration should create the Payment model")
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
            'receipt_data',
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
    
    def test_migration_dependencies_correct(self):
        """Test that the migration has correct dependencies."""
        migration_file = self.credits_migrations_dir / "0003_add_payment_model.py"
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check dependency on previous migration
        self.assertIn("('credits', '0002_add_subscription_support')", migration_content,
                     "Migration should depend on 0002_add_subscription_support")
    
    def test_migration_includes_indexes(self):
        """Test that the migration includes proper database indexes."""
        migration_file = self.credits_migrations_dir / "0003_add_payment_model.py"
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check for index creation
        self.assertIn("migrations.AddIndex", migration_content,
                     "Migration should add database indexes")
        
        # Check for specific indexes
        expected_indexes = [
            'credits_payment_user_idx',
            'credits_payment_stripe_pi_idx',
            'credits_payment_stripe_sub_idx',
            'credits_payment_status_idx',
            'credits_payment_type_idx',
            'credits_payment_created_at_idx'
        ]
        
        for index_name in expected_indexes:
            self.assertIn(index_name, migration_content,
                         f"Migration should include index '{index_name}'")
    
    def test_payment_creation_in_webhook_handlers(self):
        """Test that Payment records are created in webhook handlers."""
        # Check that Payment model is imported in webhook views
        webhook_views_file = self.quickscale_root / "quickscale" / "templates" / "stripe_manager" / "views.py"
        
        with open(webhook_views_file, 'r') as f:
            webhook_content = f.read()
        
        # Check that Payment model is imported and used
        self.assertIn("from credits.models import Payment", webhook_content,
                     "Webhook views should import Payment model")
        self.assertIn("Payment.objects.create", webhook_content,
                     "Webhook views should create Payment records")
        
        # Check specific payment creation scenarios
        self.assertIn("payment_type='CREDIT_PURCHASE'", webhook_content,
                     "Webhook should create CREDIT_PURCHASE payment records")
        self.assertIn("payment_type='SUBSCRIPTION'", webhook_content,
                     "Webhook should create SUBSCRIPTION payment records")
    
    def test_payment_creation_in_success_views(self):
        """Test that Payment records are created in success views as fallback."""
        # Check credit purchase success view
        credits_views_file = self.quickscale_root / "quickscale" / "templates" / "credits" / "views.py"
        
        with open(credits_views_file, 'r') as f:
            credits_content = f.read()
        
        self.assertIn("from credits.models import Payment", credits_content,
                     "Credits views should import Payment model")
        self.assertIn("existing_payment = Payment.objects.filter", credits_content,
                     "Credits views should check for existing payments")
        
        # Check subscription success view
        admin_views_file = self.quickscale_root / "quickscale" / "templates" / "admin_dashboard" / "views.py"
        
        with open(admin_views_file, 'r') as f:
            admin_content = f.read()
        
        self.assertIn("from credits.models import Payment", admin_content,
                     "Admin dashboard views should import Payment model")
        self.assertIn("existing_payment = Payment.objects.filter", admin_content,
                     "Admin dashboard views should check for existing payments")

if __name__ == '__main__':
    unittest.main() 