"""Unit tests for credit_type field migration fix in QuickScale templates."""
import unittest
import os


class CreditTypeMigrationFixTests(unittest.TestCase):
    """Test that the credit_type field migration fix is correctly implemented in QuickScale templates."""
    
    def test_credit_transaction_model_template_has_credit_type_field(self):
        """Test that CreditTransaction model template has credit_type field defined."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/models.py'
        )
        
        self.assertTrue(os.path.exists(models_file), 
                       "Credits models.py template should exist")
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Check that credit_type field is defined
        self.assertIn('credit_type = models.CharField(', models_content,
                     "CreditTransaction model should have credit_type field")
        
        # Check field properties
        self.assertIn("max_length=20", models_content,
                     "credit_type field should have max_length=20")
        self.assertIn("default='ADMIN'", models_content,
                     "credit_type field should have default='ADMIN'")
        
        # Check choices are defined
        self.assertIn('CREDIT_TYPE_CHOICES', models_content,
                     "Should have CREDIT_TYPE_CHOICES defined")
        self.assertIn("('PURCHASE', _('Purchase'))", models_content,
                     "Should have PURCHASE choice")
        self.assertIn("('CONSUMPTION', _('Consumption'))", models_content,
                     "Should have CONSUMPTION choice") 
        self.assertIn("('ADMIN', _('Admin Adjustment'))", models_content,
                     "Should have ADMIN choice")
    
    
    def test_credit_type_field_in_model_indexes(self):
        """Test that credit_type field is included in model indexes."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/models.py'
        )
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Check that credit_type is indexed
        self.assertIn("models.Index(fields=['credit_type'])", models_content,
                     "Should have index on credit_type field")
    
    def test_migration_file_exists_for_credit_type(self):
        """Test that the migration file for credit_type field exists in templates."""
        migration_path = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/migrations/0003_add_credit_type.py'
        )
        
        self.assertTrue(os.path.exists(migration_path), 
                       "Migration file 0003_add_credit_type.py should exist in templates")
        
        # Read migration content and verify it adds credit_type field
        with open(migration_path, 'r') as f:
            migration_content = f.read()
            
        self.assertIn('AddField', migration_content,
                     "Migration should contain AddField operation")
        self.assertIn('credit_type', migration_content,
                     "Migration should add credit_type field")
        self.assertIn('PURCHASE', migration_content,
                     "Migration should include PURCHASE choice")
        self.assertIn('CONSUMPTION', migration_content,
                     "Migration should include CONSUMPTION choice")
        self.assertIn('ADMIN', migration_content,
                     "Migration should include ADMIN choice")
        self.assertIn('default=\'ADMIN\'', migration_content,
                     "Migration should set default to ADMIN")
        self.assertIn('max_length=20', migration_content,
                     "Migration should set max_length to 20")
    
    def test_migration_dependencies_are_correct(self):
        """Test that the migration has correct dependencies."""
        migration_path = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/migrations/0003_add_credit_type.py'
        )
        
        with open(migration_path, 'r') as f:
            migration_content = f.read()
        
        # Should depend on the previous migration
        self.assertIn("('credits', '0002_add_services')", migration_content,
                     "Migration should depend on 0002_add_services")
    
    def test_credit_transaction_meta_class_has_correct_indexes(self):
        """Test that CreditTransaction Meta class includes all required indexes."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/models.py'
        )
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Check all expected indexes exist
        expected_indexes = [
            "models.Index(fields=['user', '-created_at'])",
            "models.Index(fields=['-created_at'])",
            "models.Index(fields=['credit_type'])"
        ]
        
        for index in expected_indexes:
            self.assertIn(index, models_content,
                         f"Should have index: {index}")
    
    def test_credit_transaction_admin_template_handles_credit_type(self):
        """Test that CreditTransaction admin template includes credit_type field."""
        admin_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/admin.py'
        )
        
        self.assertTrue(os.path.exists(admin_file), 
                       "Credits admin.py template should exist")
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        # Check that credit_type is included in admin configuration
        self.assertIn('credit_type', admin_content,
                     "Admin should reference credit_type field")
    
    def test_no_duplicate_stripe_customer_models(self):
        """Test that StripeCustomer model only exists in stripe_manager, not in users."""
        users_models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/users/models.py'
        )
        
        stripe_manager_models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/stripe_manager/models.py'
        )
        
        # Check users models doesn't have StripeCustomer
        with open(users_models_file, 'r') as f:
            users_content = f.read()
        
        self.assertNotIn('class StripeCustomer', users_content,
                        "Users models should not have StripeCustomer class")
        
        # Check stripe_manager models has StripeCustomer
        with open(stripe_manager_models_file, 'r') as f:
            stripe_content = f.read()
        
        self.assertIn('class StripeCustomer', stripe_content,
                     "Stripe manager models should have StripeCustomer class")
        
        # Check that stripe_manager StripeCustomer has related_name
        self.assertIn("related_name='stripe_customer'", stripe_content,
                     "StripeCustomer should have related_name defined")
    
    def test_no_stripe_customer_migration_in_users_app(self):
        """Test that StripeCustomer migration was removed from users app."""
        users_migration_path = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/users/migrations/0004_stripecustomer.py'
        )
        
        self.assertFalse(os.path.exists(users_migration_path),
                        "StripeCustomer migration should not exist in users app")


class CreditTransactionTemplateConsistencyTests(unittest.TestCase):
    """Test consistency between CreditTransaction templates and related files."""
    
    def test_credit_type_choices_consistency(self):
        """Test that credit_type choices are consistent across templates."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/models.py'
        )
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Expected choices
        expected_choices = ['PURCHASE', 'CONSUMPTION', 'ADMIN']
        
        for choice in expected_choices:
            self.assertIn(f"('{choice}'", models_content,
                         f"Should have {choice} choice defined")
    
    def test_migration_matches_model_definition(self):
        """Test that migration field definition matches model field definition."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/models.py'
        )
        migration_file = os.path.join(
            os.path.dirname(__file__), 
            '../../quickscale/templates/credits/migrations/0003_add_credit_type.py'
        )
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check consistency between model and migration
        if 'max_length=20' in models_content:
            self.assertIn('max_length=20', migration_content,
                         "Migration max_length should match model")
        
        if "default='ADMIN'" in models_content:
            self.assertIn("default='ADMIN'", migration_content,
                         "Migration default should match model")
