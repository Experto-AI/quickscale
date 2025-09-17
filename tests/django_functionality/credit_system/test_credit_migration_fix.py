"""Unit tests for credit_type field migration fix in QuickScale templates."""
import os
import unittest


class CreditTypeMigrationFixTests(unittest.TestCase):
    """Test that the credit_type field migration fix is correctly implemented in QuickScale templates."""
    
    def test_credit_transaction_model_template_has_credit_type_field(self):
        """Test that CreditTransaction model template has credit_type field defined."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../../quickscale/project_templates/credits/models.py'
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
        # Check for new credit type choices
        self.assertIn("('PAYG_PURCHASE', _('Pay-as-You-Go Purchase'))", models_content,
                     "Should have PAYG_PURCHASE choice")
        self.assertIn("('SUBSCRIPTION_CONSUMPTION', _('Subscription Consumption'))", models_content,
                     "Should have SUBSCRIPTION_CONSUMPTION choice") 
        self.assertIn("('PAYG_CONSUMPTION', _('Pay-as-You-Go Consumption'))", models_content,
                     "Should have PAYG_CONSUMPTION choice")
        self.assertIn("('ADMIN', _('Admin Adjustment'))", models_content,
                     "Should have ADMIN choice")
    
    
    def test_credit_type_field_in_model_indexes(self):
        """Test that credit_type field is included in model indexes."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../../quickscale/project_templates/credits/models.py'
        )
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Check that credit_type is indexed
        self.assertIn("models.Index(fields=['credit_type'])", models_content,
                     "Should have index on credit_type field")
    
    def test_credit_transaction_meta_class_has_correct_indexes(self):
        """Test that CreditTransaction Meta class includes all required indexes."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../../quickscale/project_templates/credits/models.py'
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
            '../../../quickscale/project_templates/credits/admin.py'
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
            '../../../quickscale/project_templates/users/models.py'
        )
        
        stripe_manager_models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../../quickscale/project_templates/stripe_manager/models.py'
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
            '../../../quickscale/project_templates/users/migrations/0004_stripecustomer.py'
        )
        
        self.assertFalse(os.path.exists(users_migration_path),
                        "StripeCustomer migration should not exist in users app")


class CreditTransactionTemplateConsistencyTests(unittest.TestCase):
    """Test consistency between CreditTransaction templates and related files."""
    
    def test_credit_type_choices_consistency(self):
        """Test that credit_type choices are consistent across templates."""
        models_file = os.path.join(
            os.path.dirname(__file__), 
            '../../../quickscale/project_templates/credits/models.py'
        )
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Expected choices - updated to reflect current system
        expected_choices = ['PAYG_PURCHASE', 'SUBSCRIPTION_CONSUMPTION', 'PAYG_CONSUMPTION', 'ADMIN']
        
        for choice in expected_choices:
            self.assertIn(f"('{choice}'", models_content,
                         f"Should have {choice} choice defined")
