"""
Tests for Sprint 3: Basic Service Credit Consumption.

These tests verify that the Service model, ServiceUsage model, credit consumption logic,
and service views are properly implemented in the QuickScale project generator templates.
"""

import os
import unittest
import re
from pathlib import Path


class ServiceModelTests(unittest.TestCase):
    """Test cases for Service model implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.models_py = self.credits_app_path / 'models.py'
        self.admin_py = self.credits_app_path / 'admin.py'
        self.views_py = self.credits_app_path / 'views.py'
        self.urls_py = self.credits_app_path / 'urls.py'
        
    def test_service_model_exists(self):
        """Test that Service model is defined with required fields."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for Service model
        self.assertIn("class Service(models.Model)", models_content,
                     "Service model not found")
        
        # Check for required fields
        self.assertIn("name = models.CharField", models_content,
                     "Service name field not found")
        self.assertIn("description = models.TextField", models_content,
                     "Service description field not found")
        self.assertIn("credit_cost = models.DecimalField", models_content,
                     "Service credit_cost field not found")
        self.assertIn("is_active = models.BooleanField", models_content,
                     "Service is_active field not found")
        
        # Check for timestamps
        self.assertIn("created_at = models.DateTimeField", models_content,
                     "Service created_at field not found")
        self.assertIn("updated_at = models.DateTimeField", models_content,
                     "Service updated_at field not found")
    
    def test_service_model_validation(self):
        """Test that Service model has proper validation."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for credit cost validation
        self.assertIn("MinValueValidator", models_content,
                     "MinValueValidator not found for credit_cost")
        self.assertIn("Decimal('0.0')", models_content,
                     "Minimum credit cost validation not found")
        
        # Check for unique constraint on name
        self.assertIn("unique=True", models_content,
                     "Unique constraint on service name not found")
    
    def test_service_model_meta_options(self):
        """Test that Service model has proper meta options."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for verbose names
        self.assertIn("verbose_name = _('service')", models_content,
                     "Service verbose_name not found")
        self.assertIn("verbose_name_plural = _('services')", models_content,
                     "Service verbose_name_plural not found")
        
        # Check for ordering
        self.assertIn("ordering = ['name']", models_content,
                     "Service ordering not found")
    
    def test_service_model_string_representation(self):
        """Test that Service model has proper string representation."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for __str__ method with defensive programming and free service support
        self.assertIn('def __str__(self):', models_content,
                     "Service model should have __str__ method")
        self.assertIn('name = self.name or', models_content,
                     "Service __str__ method should have defensive name handling")
        self.assertIn('credit_cost = self.credit_cost or', models_content,
                     "Service __str__ method should have defensive credit_cost handling")
        self.assertIn('if credit_cost == 0:', models_content,
                     "Service __str__ method should handle free services")
        self.assertIn('return f"{name} (Free)"', models_content,
                     "Service __str__ method should return 'Free' for zero cost")
        self.assertIn('return f"{name} ({credit_cost} credits)"', models_content,
                     "Service __str__ method should return credits for paid services")


class ServiceUsageModelTests(unittest.TestCase):
    """Test cases for ServiceUsage model implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.models_py = self.credits_app_path / 'models.py'
        
    def test_service_usage_model_exists(self):
        """Test that ServiceUsage model is defined with required fields."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for ServiceUsage model
        self.assertIn("class ServiceUsage(models.Model)", models_content,
                     "ServiceUsage model not found")
        
        # Check for required foreign key fields
        self.assertIn("user = models.ForeignKey", models_content,
                     "ServiceUsage user field not found")
        self.assertIn("service = models.ForeignKey", models_content,
                     "ServiceUsage service field not found")
        self.assertIn("credit_transaction = models.ForeignKey", models_content,
                     "ServiceUsage credit_transaction field not found")
        
        # Check for timestamp
        self.assertIn("created_at = models.DateTimeField", models_content,
                     "ServiceUsage created_at field not found")
    
    def test_service_usage_model_relationships(self):
        """Test that ServiceUsage model has proper relationships."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for proper related names
        self.assertIn("related_name='service_usages'", models_content,
                     "ServiceUsage user related_name not found")
        self.assertIn("related_name='usages'", models_content,
                     "ServiceUsage service related_name not found")
        self.assertIn("related_name='service_usage'", models_content,
                     "ServiceUsage credit_transaction related_name not found")
    
    def test_service_usage_model_meta_options(self):
        """Test that ServiceUsage model has proper meta options."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for verbose names
        self.assertIn("verbose_name = _('service usage')", models_content,
                     "ServiceUsage verbose_name not found")
        self.assertIn("verbose_name_plural = _('service usages')", models_content,
                     "ServiceUsage verbose_name_plural not found")
        
        # Check for ordering
        self.assertIn("ordering = ['-created_at']", models_content,
                     "ServiceUsage ordering not found")
        
        # Check for database indexes
        self.assertIn("models.Index(fields=['user', '-created_at']", models_content,
                     "ServiceUsage user index not found")
        self.assertIn("models.Index(fields=['service', '-created_at']", models_content,
                     "ServiceUsage service index not found")


class CreditConsumptionTests(unittest.TestCase):
    """Test cases for credit consumption functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.models_py = self.credits_app_path / 'models.py'
        
    def test_consume_credits_method_exists(self):
        """Test that consume_credits_with_priority method is implemented in CreditAccount."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for consume_credits_with_priority method (actual implementation)
        self.assertIn("def consume_credits_with_priority(self, amount: Decimal, description: str)", models_content,
                     "consume_credits_with_priority method not found")
        
        # Check for proper validation
        self.assertIn("if amount <= 0:", models_content,
                     "Amount validation not found in consume_credits_with_priority")
        self.assertIn("raise ValueError(\"Amount must be positive\")", models_content,
                     "Amount validation error not found")
        
        # Check for balance validation using available balance method
        self.assertIn("available_balance = account.get_available_balance()", models_content,
                     "Balance check not found in consume_credits_with_priority")
        self.assertIn("if available_balance < amount:", models_content,
                     "Insufficient credits check not found")
        
        # Check for transaction creation with negative amount
        self.assertIn("amount=-amount", models_content,
                     "Negative amount for consumption not found")
    
    def test_insufficient_credits_error_exists(self):
        """Test that InsufficientCreditsError exception is defined."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for custom exception
        self.assertIn("class InsufficientCreditsError(Exception)", models_content,
                     "InsufficientCreditsError exception not found")
        
        # Check that it's raised in consume_credits
        self.assertIn("raise InsufficientCreditsError", models_content,
                     "InsufficientCreditsError not raised in consume_credits")
    
    def test_atomic_transaction_usage(self):
        """Test that credit consumption uses atomic transactions."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for transaction.atomic usage
        self.assertIn("with transaction.atomic():", models_content,
                     "Atomic transaction not used in consume_credits")


class ServiceViewsTests(unittest.TestCase):
    """Test cases for service views implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.views_py = self.credits_app_path / 'views.py'
        
    def test_services_list_view_exists(self):
        """Test that services_list view is implemented."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for services_list view
        self.assertIn("def services_list(request):", views_content,
                     "services_list view not found")
        
        # Check for login required decorator
        self.assertIn("@login_required", views_content,
                     "login_required decorator not found on services_list")
        
        # Check for active services query
        self.assertIn("Service.objects.filter(is_active=True)", views_content,
                     "Active services query not found")
        
        # Check for usage count calculation
        self.assertIn("service.user_usage_count", views_content,
                     "User usage count calculation not found")
    
    def test_use_service_view_exists(self):
        """Test that use_service view is implemented."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for use_service view
        self.assertIn("def use_service(request, service_id):", views_content,
                     "use_service view not found")
        
        # Check for POST method restriction
        self.assertIn("@require_http_methods([\"POST\"])", views_content,
                     "POST method restriction not found on use_service")
        
        # Check for service retrieval
        self.assertIn("get_object_or_404(Service, id=service_id, is_active=True)", views_content,
                     "Service retrieval not found")
        
        # Check for credit consumption (actual method name)
        self.assertIn("credit_account.consume_credits_with_priority", views_content,
                     "Credit consumption not found")
        
        # Check for service usage creation
        self.assertIn("ServiceUsage.objects.create", views_content,
                     "ServiceUsage creation not found")
    
    def test_use_service_error_handling(self):
        """Test that use_service view has proper error handling."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for InsufficientCreditsError handling
        self.assertIn("except InsufficientCreditsError", views_content,
                     "InsufficientCreditsError handling not found")
        
        # Check for general exception handling
        self.assertIn("except Exception as e:", views_content,
                     "General exception handling not found")
        
        # Check for success and error messages
        self.assertIn("messages.success", views_content,
                     "Success message not found")
        self.assertIn("messages.error", views_content,
                     "Error message not found")
    
    def test_service_usage_api_view_exists(self):
        """Test that service_usage_api view is implemented."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for service_usage_api view
        self.assertIn("def service_usage_api(request, service_id):", views_content,
                     "service_usage_api view not found")
        
        # Check for GET method restriction
        self.assertIn("@require_http_methods([\"GET\"])", views_content,
                     "GET method restriction not found on service_usage_api")
        
        # Check for JSON response
        self.assertIn("return JsonResponse", views_content,
                     "JsonResponse not found in service_usage_api")
        
        # Check for usage count calculation
        self.assertIn("ServiceUsage.objects.filter", views_content,
                     "Usage count query not found")
        
        # Check for sufficient credits check
        self.assertIn("has_sufficient_credits", views_content,
                     "Sufficient credits check not found")


class ServiceUrlsTests(unittest.TestCase):
    """Test cases for service URL configuration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.urls_py = self.credits_app_path / 'urls.py'
        
    def test_service_urls_exist(self):
        """Test that service URLs are properly configured."""
        with open(self.urls_py, 'r') as f:
            urls_content = f.read()
        
        # Check for services list URL
        self.assertIn("path('services/', views.services_list, name='services')", urls_content,
                     "Services list URL not found")
        
        # Check for use service URL
        self.assertIn("path('services/<int:service_id>/use/', views.use_service, name='use_service')", urls_content,
                     "Use service URL not found")
        
        # Check for service usage API URL
        self.assertIn("path('services/<int:service_id>/api/', views.service_usage_api, name='service_usage_api')", urls_content,
                     "Service usage API URL not found")


class ServiceAdminTests(unittest.TestCase):
    """Test cases for service admin configuration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.admin_py = self.credits_app_path / 'admin.py'
        
    def test_service_admin_exists(self):
        """Test that Service admin is properly configured."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for Service admin registration
        self.assertIn("@admin.register(Service)", admin_content,
                     "Service admin registration not found")
        
        # Check for ServiceAdmin class
        self.assertIn("class ServiceAdmin(admin.ModelAdmin)", admin_content,
                     "ServiceAdmin class not found")
        
        # Check for list display
        self.assertIn("list_display = ('name', 'credit_cost', 'is_active', 'usage_count'", admin_content,
                     "Service list_display not found")
        
        # Check for usage_count method
        self.assertIn("def usage_count(self, obj):", admin_content,
                     "Service usage_count method not found")
    
    def test_service_usage_admin_exists(self):
        """Test that ServiceUsage admin is properly configured."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for ServiceUsage admin registration
        self.assertIn("@admin.register(ServiceUsage)", admin_content,
                     "ServiceUsage admin registration not found")
        
        # Check for ServiceUsageAdmin class
        self.assertIn("class ServiceUsageAdmin(admin.ModelAdmin)", admin_content,
                     "ServiceUsageAdmin class not found")
        
        # Check for read-only permissions
        self.assertIn("def has_add_permission(self, request):", admin_content,
                     "ServiceUsage add permission restriction not found")
        self.assertIn("return False", admin_content,
                     "ServiceUsage permission restrictions not properly implemented")


if __name__ == '__main__':
    unittest.main() 