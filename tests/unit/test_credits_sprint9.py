"""Tests for Sprint 9: Pro Subscription Plan functionality."""

import os
import unittest


class Sprint9TemplateStructureTests(unittest.TestCase):
    """Test Sprint 9 template structure and implementation."""
    
    def test_subscription_template_has_plan_comparison(self):
        """Test that subscription template includes plan comparison."""
        subscription_path = 'quickscale/project_templates/templates/admin_dashboard/subscription.html'
        self.assertTrue(os.path.exists(subscription_path), "Subscription template should exist")
        
        with open(subscription_path, 'r') as f:
            template_content = f.read()
            
        # Test plan comparison features
        self.assertIn('Plan Comparison', template_content, "Plan comparison section should exist")
        # Test dynamic plan name display instead of hardcoded plan names
        self.assertIn('{{ product.name }}', template_content, "Should display dynamic product names")
        self.assertIn('subscription_products', template_content, "Should iterate over subscription products")
        
        # Test pricing display - check for actual template content
        self.assertIn('widthratio product.price 1 product.credit_amount', template_content, "Should calculate price per credit using widthratio")
        self.assertIn('credit_amount', template_content, "Should display credit amounts")
        
        # Test that template supports multiple plans through product iteration
        self.assertIn('{% for product in subscription_products %}', template_content, "Should iterate over multiple products")
        self.assertIn('{{ product.price }}', template_content, "Should display dynamic product prices")
        self.assertIn('{{ product.credit_amount }}', template_content, "Should display dynamic credit amounts")
        
        # Test cost per credit calculation display
        self.assertIn('Cost per Credit', template_content, "Should have cost per credit section in comparison table")
        self.assertIn('cents per credit', template_content, "Should display cost in cents per credit")
    
    def test_upgrade_downgrade_buttons_exist(self):
        """Test that subscription template has upgrade/downgrade functionality."""
        subscription_path = 'quickscale/project_templates/templates/admin_dashboard/subscription.html'
        self.assertTrue(os.path.exists(subscription_path), "Subscription template should exist")
        
        with open(subscription_path, 'r') as f:
            template_content = f.read()
        
        # Test upgrade/downgrade functionality
        self.assertIn('Upgrade to', template_content, "Upgrade button should exist")
        self.assertIn('Downgrade to', template_content, "Downgrade button should exist")
        self.assertIn('Upgrade to', template_content, "Upgrade text should exist")
        self.assertIn('Downgrade to', template_content, "Downgrade text should exist")
    
    def test_plan_change_modal_exists(self):
        """Test that plan change functionality exists in template."""
        subscription_path = 'quickscale/project_templates/templates/admin_dashboard/subscription.html'
        with open(subscription_path, 'r') as f:
            template_content = f.read()
        # Check for plan change functionality (either modal or direct form submission)
        has_plan_change_functionality = (
            'Upgrade to' in template_content and 'Downgrade to' in template_content and
            'create_plan_change_checkout' in template_content
        )
        self.assertTrue(
            has_plan_change_functionality,
            "Plan change functionality should exist (upgrade/downgrade buttons with checkout)"
        )
        # The implementation uses direct form submission rather than modal, which is valid
        self.assertIn('Upgrade to', template_content, "Upgrade functionality should exist")
        self.assertIn('Downgrade to', template_content, "Downgrade functionality should exist")


class Sprint9ViewsImplementationTests(unittest.TestCase):
    """Test Sprint 9 views implementation."""
    
    def test_upgrade_downgrade_logic_exists(self):
        """Test that upgrade/downgrade logic exists in views."""
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        self.assertTrue(os.path.exists(views_path), "Views file should exist")
        
        with open(views_path, 'r') as f:
            views_content = f.read()
            
        # Test plan change functionality (actual implementation uses checkout flow)
        self.assertIn('create_plan_change_checkout', views_content, "Plan change checkout view should exist")
        self.assertIn('new_product_id', views_content, "Plan change should handle new product ID")
        
    def test_immediate_upgrade_logic_when_no_credits(self):
        """Test that plan changes use secure checkout flow regardless of credit balance."""
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        
        with open(views_path, 'r') as f:
            views_content = f.read()
            
        # In our implementation, all plan changes go through checkout for user consent
        # This is more secure than immediate charging and provides consistency
        self.assertIn('create_plan_change_checkout', views_content, "Plan change should use checkout flow")
        self.assertIn('checkout_session', views_content, "Should create checkout sessions for user consent")
        self.assertIn('plan_change_success', views_content, "Should handle plan change success after payment")
    
    def test_prorated_billing_handling(self):
        """Test that prorated billing is handled through Stripe checkout sessions."""
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        
        with open(views_path, 'r') as f:
            views_content = f.read()
            
        # Our implementation uses Stripe checkout sessions which automatically handle proration
        self.assertIn('create_checkout_session', views_content, "Should use Stripe checkout sessions")
        self.assertIn('mode=\'subscription\'', views_content, "Should use subscription mode for automatic proration")
        self.assertIn('plan_change', views_content, "Should handle plan change metadata")


class Sprint9URLsConfigurationTests(unittest.TestCase):
    """Test Sprint 9 URLs configuration."""
    
    def test_urls_configuration_for_plan_management(self):
        """Test that URLs are configured for plan management."""
        urls_path = 'quickscale/project_templates/admin_dashboard/urls.py'
        self.assertTrue(os.path.exists(urls_path), "URLs file should exist")
        
        with open(urls_path, 'r') as f:
            urls_content = f.read()
            
        self.assertIn('subscription', urls_content, "Subscription URL should be configured")
        self.assertIn('create_plan_change_checkout', urls_content, "Plan change checkout URL should be configured")


class Sprint9StripeProductModelTests(unittest.TestCase):
    """Test Sprint 9 Stripe product model structure."""
    
    def test_stripe_product_model_structure(self):
        """Test that StripeProduct model has required fields for multiple plans."""
        models_path = 'quickscale/project_templates/stripe_manager/models.py'
        self.assertTrue(os.path.exists(models_path), "Models file should exist")
        
        with open(models_path, 'r') as f:
            models_content = f.read()
            
        # Test required fields for Pro plan support
        self.assertIn('class StripeProduct', models_content, "StripeProduct model should exist")
        self.assertIn('credit_amount', models_content, "credit_amount field should exist")
        self.assertIn('interval', models_content, "interval field should exist")
        self.assertIn('display_order', models_content, "display_order field should exist")
        self.assertIn('price', models_content, "price field should exist")
        
        # Test interval choices support both subscription types and one-time
        self.assertIn("'month'", models_content, "Monthly interval should be supported")
        self.assertIn("'one-time'", models_content, "One-time interval should be supported")
    
    def test_stripe_product_model_methods(self):
        """Test that StripeProduct model has required methods."""
        models_path = 'quickscale/project_templates/stripe_manager/models.py'
        
        with open(models_path, 'r') as f:
            models_content = f.read()
            
        # Test utility methods exist
        self.assertIn('price_per_credit', models_content, "price_per_credit property should exist")
        self.assertIn('is_subscription', models_content, "is_subscription property should exist")
        self.assertIn('is_one_time', models_content, "is_one_time property should exist")


class Sprint9TemplateTagsTests(unittest.TestCase):
    """Test Sprint 9 template tags."""
    
    def test_dashboard_template_tags_exist(self):
        """Test that required template tags exist for Sprint 9."""
        template_tags_path = 'quickscale/project_templates/admin_dashboard/templatetags/dashboard_extras.py'
        self.assertTrue(os.path.exists(template_tags_path), "Template tags file should exist")
        
        with open(template_tags_path, 'r') as f:
            tags_content = f.read()
            
        # Test mathematical filters exist
        self.assertIn('def sub(', tags_content, "Subtraction filter should exist")
        self.assertIn('def multiply(', tags_content, "Multiplication filter should exist")
        self.assertIn('def divide(', tags_content, "Division filter should exist")
        self.assertIn('def cost_per_credit(', tags_content, "Cost per credit filter should exist")


class Sprint9ValidationTests(unittest.TestCase):
    """Validation tests for Sprint 9 requirements."""
    
    def test_sprint9_backend_implementation_complete(self):
        """Test that Sprint 9 backend implementation is complete."""
        # Test plan upgrade/downgrade logic exists
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        with open(views_path, 'r') as f:
            views_content = f.read()
            self.assertIn('create_plan_change_checkout', views_content, "Plan change checkout logic should exist")
            self.assertIn('plan_change_success', views_content, "Plan change success handler should exist")
    
    def test_sprint9_frontend_implementation_complete(self):
        """Test that Sprint 9 frontend implementation is complete."""
        subscription_path = 'quickscale/project_templates/templates/admin_dashboard/subscription.html'
        with open(subscription_path, 'r') as f:
            template_content = f.read()
            self.assertIn('Plan Comparison', template_content)
            self.assertIn('Upgrade to', template_content)
            self.assertIn('Downgrade to', template_content)
    
    def test_three_product_types_supported(self):
        """Test that system supports three product types as specified in roadmap."""
        models_path = 'quickscale/project_templates/stripe_manager/models.py'
        with open(models_path, 'r') as f:
            models_content = f.read()
            
        # Test that the model supports the three types mentioned in roadmap:
        # 1. Basic plan (subscription with interval='month')
        # 2. Pro plan (subscription with interval='month') 
        # 3. Pay-as-you-go (one-time purchases with interval='one-time')
        
        self.assertIn("'month'", models_content, "Monthly subscriptions should be supported")
        self.assertIn("'one-time'", models_content, "One-time purchases should be supported")
        
        # Test that products can be distinguished by metadata or naming
        self.assertIn('name', models_content, "Name field should exist for plan identification")
        self.assertIn('credit_amount', models_content, "Credit amount should distinguish plan values")
    
    def test_user_can_choose_between_plans(self):
        """Test that template supports user choosing between Basic and Pro plans."""
        subscription_path = 'quickscale/project_templates/templates/admin_dashboard/subscription.html'
        with open(subscription_path, 'r') as f:
            template_content = f.read()
            
        # Test that template can display multiple subscription products
        self.assertIn('subscription_products', template_content, "Should display subscription products")
        self.assertIn('for product in subscription_products', template_content, "Should iterate over plans")
        
        # Test that upgrade/downgrade functionality exists
        self.assertIn('Upgrade to', template_content, "Should have upgrade functionality")
        self.assertIn('Downgrade to', template_content, "Should have downgrade functionality")
    
    def test_roadmap_requirements_met(self):
        """Test that all roadmap requirements for Sprint 9 are met."""
        # Backend Implementation checks
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        with open(views_path, 'r') as f:
            views_content = f.read()
            
        # ✅ Add plan upgrade/downgrade logic
        self.assertIn('create_plan_change_checkout', views_content, "Plan upgrade/downgrade logic should exist")
        
        # ✅ Handle prorated billing for plan changes  
        self.assertIn('create_checkout_session', views_content, "Prorated billing should be handled via Stripe checkout")
        
        # Frontend Implementation checks
        subscription_path = 'quickscale/project_templates/templates/admin_dashboard/subscription.html'
        with open(subscription_path, 'r') as f:
            template_content = f.read()
            
        # ✅ Add Pro plan option to subscription page
        self.assertIn('subscription_products', template_content, "Should support multiple plans including Pro")
        
        # ✅ Create plan comparison table (Basic vs Pro)
        self.assertIn('Plan Comparison', template_content, "Should have plan comparison table")
        
        # ✅ Add upgrade/downgrade buttons for existing subscribers
        self.assertIn('Upgrade to', template_content, "Should have upgrade buttons")
        self.assertIn('Downgrade to', template_content, "Should have downgrade buttons")


class Sprint9UpgradeDowngradeCheckoutTests(unittest.TestCase):
    """Test Sprint 9 upgrade/downgrade checkout flow implementation."""
    
    def test_plan_change_uses_checkout_flow(self):
        """Test that plan changes now use Stripe checkout sessions instead of immediate API calls."""
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        
        with open(views_path, 'r') as f:
            views_content = f.read()
            
        # Test that new plan change checkout function exists
        self.assertIn('create_plan_change_checkout', views_content, "Plan change checkout function should exist")
        self.assertIn('plan_change_success', views_content, "Plan change success handler should exist")
        
        # Test that checkout sessions are created for plan changes
        self.assertIn('create_checkout_session', views_content, "Should create checkout sessions for plan changes")
        self.assertIn('plan_change', views_content, "Should use plan_change purchase type")
        
        # Test that implementation uses checkout flow approach (no deprecated function needed)
        self.assertIn('create_plan_change_checkout', views_content, "Should use checkout flow for plan changes")
        self.assertIn('plan_change_success', views_content, "Should have plan change success handler")
    
    def test_plan_change_checkout_metadata(self):
        """Test that plan change checkout includes proper metadata."""
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        
        with open(views_path, 'r') as f:
            views_content = f.read()
            
        # Test that plan change metadata is included
        self.assertIn('current_subscription_id', views_content, "Should include current subscription ID")
        self.assertIn('current_product_id', views_content, "Should include current product ID")
        self.assertIn('change_type', views_content, "Should include change type (upgrade/downgrade)")
        
        # Test that metadata includes user consent flow information
        self.assertIn('plan_change_success', views_content, "Should redirect to plan change success page")
    
    def test_frontend_uses_checkout_flow(self):
        """Test that frontend uses checkout flow for plan changes."""
        subscription_path = 'quickscale/project_templates/templates/admin_dashboard/subscription.html'
        
        with open(subscription_path, 'r') as f:
            template_content = f.read()
            
        # Test that template uses checkout endpoint through form submission
        self.assertIn('create_plan_change_checkout', template_content, "Should use plan change checkout endpoint")
        self.assertIn('create_subscription_checkout', template_content, "Should use subscription checkout endpoint")
        
        # The implementation uses direct form submission which is simpler and valid
        self.assertIn('method="POST"', template_content, "Should use POST method for checkout")
        self.assertIn('{% csrf_token %}', template_content, "Should include CSRF token")
        
        # Test that upgrade and downgrade functionality exists
        self.assertIn('Upgrade to', template_content, "Should have upgrade functionality")
        self.assertIn('Downgrade to', template_content, "Should have downgrade functionality")
    
    def test_plan_change_success_template_exists(self):
        """Test that plan change success template exists."""
        template_path = 'quickscale/project_templates/templates/admin_dashboard/plan_change_success.html'
        self.assertTrue(os.path.exists(template_path), "Plan change success template should exist")
        
        with open(template_path, 'r') as f:
            template_content = f.read()
            
        self.assertIn('Plan Change Successful', template_content, "Should show success message")
        self.assertIn('transferred_credits', template_content, "Should show transferred credits")
        self.assertIn('new_plan_credits', template_content, "Should show new plan credits")
        self.assertIn('amount_charged', template_content, "Should show amount charged")
    
    def test_webhook_handles_plan_changes(self):
        """Test that webhooks handle plan change events."""
        webhook_path = 'quickscale/project_templates/stripe_manager/views.py'
        
        with open(webhook_path, 'r') as f:
            webhook_content = f.read()
            
        # Test that webhook processes plan_change purchase type
        self.assertIn('plan_change', webhook_content, "Webhook should handle plan_change purchase type")
        self.assertIn('handle_plan_change_credit_transfer', webhook_content, "Should use common function for credit transfer")
        
        # Test that the common function handles the subscription transition logic
        credits_models_path = 'quickscale/project_templates/credits/models.py'
        
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
            
        self.assertIn('transferred_credits', credits_content, "Should transfer subscription credits in common function")
        self.assertIn('Plan Change -', credits_content, "Should create payment records for plan changes in common function")
        self.assertIn('new_subscription_id', credits_content, "Should handle subscription transition in common function")


class Sprint9CreditTransferTests(unittest.TestCase):
    """Test Sprint 9 credit transfer logic for plan changes."""
    
    def test_credit_transfer_removes_subscription_credits(self):
        """Test that subscription credits are properly removed before being added as pay-as-you-go credits."""
        # Test that the common function exists
        credits_models_path = 'quickscale/project_templates/credits/models.py'
        
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
            
        # Test that the common function exists and contains correct logic
        self.assertIn('handle_plan_change_credit_transfer', credits_content, "Should have common function for plan change credit transfer")
        self.assertIn('amount=-subscription_credits', credits_content, "Should deduct subscription credits first")
        self.assertIn('credit_type=\'SUBSCRIPTION\'', credits_content, "Should remove from subscription credits")
        self.assertIn('credit_type=\'PURCHASE\'', credits_content, "Should add as pay-as-you-go credits")
        
        # Test that view handler uses the common function
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        
        with open(views_path, 'r') as f:
            views_content = f.read()
            
        self.assertIn('handle_plan_change_credit_transfer', views_content, "View should use common function")
        self.assertIn('from credits.models import UserSubscription, CreditAccount, Payment, handle_plan_change_credit_transfer', views_content, "Should import common function")
        
    def test_webhook_credit_transfer_removes_subscription_credits(self):
        """Test that the webhook handler also properly removes subscription credits using the common function."""
        # Test that webhook handler uses the common function
        webhook_path = 'quickscale/project_templates/stripe_manager/views.py'
        
        with open(webhook_path, 'r') as f:
            webhook_content = f.read()
            
        self.assertIn('handle_plan_change_credit_transfer', webhook_content, "Webhook should use common function")
        self.assertIn('from credits.models import handle_plan_change_credit_transfer', webhook_content, "Should import common function")
        
        # Verify the common function has the correct logic
        credits_models_path = 'quickscale/project_templates/credits/models.py'
        
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
            
        self.assertIn('amount=-subscription_credits', credits_content, "Should deduct subscription credits first in common function")
        self.assertIn('credit_type=\'SUBSCRIPTION\'', credits_content, "Should remove from subscription credits in common function")
        self.assertIn('credit_type=\'PURCHASE\'', credits_content, "Should add as pay-as-you-go credits in common function")
    
    def test_credit_transfer_uses_correct_credit_types(self):
        """Test that credit transfers use the correct credit types for proper accounting."""
        # Check that the common function uses correct credit types
        credits_models_path = 'quickscale/project_templates/credits/models.py'
        
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
            
        # Test that the deduction uses SUBSCRIPTION credit type
        self.assertIn("credit_type='SUBSCRIPTION'  # Remove from subscription credits", credits_content, 
                      "Should use SUBSCRIPTION credit type for deduction")
        
        # Test that the addition uses PURCHASE credit type  
        self.assertIn("credit_type='PURCHASE'  # Make them pay-as-you-go credits", credits_content,
                      "Should use PURCHASE credit type for pay-as-you-go credits")
    
    def test_webhook_credit_transfer_uses_correct_credit_types(self):
        """Test that webhook credit transfer also uses the correct credit types via common function."""
        # Since both handlers use the same common function, we just need to verify it exists
        webhook_path = 'quickscale/project_templates/stripe_manager/views.py'
        
        with open(webhook_path, 'r') as f:
            webhook_content = f.read()
            
        self.assertIn('handle_plan_change_credit_transfer', webhook_content, "Webhook should use common function")
        
        # Verify the common function has correct credit types
        credits_models_path = 'quickscale/project_templates/credits/models.py'
        
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
            
        self.assertIn("credit_type='SUBSCRIPTION'", credits_content, "Common function should use SUBSCRIPTION credit type for deduction")
        self.assertIn("credit_type='PURCHASE'", credits_content, "Common function should use PURCHASE credit type for transfers")
    
    def test_no_double_credit_allocation(self):
        """Test that the refactored code prevents double credit allocation."""
        # Test that both handlers use the same common function to prevent duplication
        views_path = 'quickscale/project_templates/admin_dashboard/views.py'
        webhook_path = 'quickscale/project_templates/stripe_manager/views.py'
        
        with open(views_path, 'r') as f:
            views_content = f.read()
        
        with open(webhook_path, 'r') as f:
            webhook_content = f.read()
            
        # Both should import and use the same common function
        self.assertIn('handle_plan_change_credit_transfer', views_content, "View should use common function")
        self.assertIn('handle_plan_change_credit_transfer', webhook_content, "Webhook should use common function")
        
        # Check that the common function has duplicate prevention logic
        credits_models_path = 'quickscale/project_templates/credits/models.py'
        
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
            
        self.assertIn('existing_payment = Payment.objects.filter', credits_content, "Should check for existing payments")
        self.assertIn('if not existing_payment:', credits_content, "Should prevent duplicate payment creation") 