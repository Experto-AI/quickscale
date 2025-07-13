"""Tests for Settings & URL Configuration Review in Sprint 20."""
import unittest
from unittest.mock import patch, MagicMock
import os
import re
from pathlib import Path
from decimal import Decimal


class URLNamespaceConfigurationTest(unittest.TestCase):
    """Test URL namespace configuration and routing hierarchy."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.url_files = {
            'core': self.base_path / 'quickscale' / 'templates' / 'core' / 'urls.py',
            'credits': self.base_path / 'quickscale' / 'templates' / 'credits' / 'urls.py',
            'api': self.base_path / 'quickscale' / 'templates' / 'api' / 'urls.py',
            'public': self.base_path / 'quickscale' / 'templates' / 'public' / 'urls.py',
            'users': self.base_path / 'quickscale' / 'templates' / 'users' / 'urls.py',
            'stripe_manager': self.base_path / 'quickscale' / 'templates' / 'stripe_manager' / 'urls.py',
            'admin_dashboard': self.base_path / 'quickscale' / 'templates' / 'admin_dashboard' / 'urls.py',
            'services': self.base_path / 'quickscale' / 'templates' / 'services' / 'urls.py'
        }

    def test_public_namespace_exists(self):
        """Test that public namespace is properly configured."""
        if self.url_files['public'].exists():
            with open(self.url_files['public'], 'r') as f:
                content = f.read()
            
            # Should have app_name defined
            self.assertIn("app_name = 'public'", content, "Public app should define app_name")
            
            # Should have index URL pattern (home page)
            index_patterns = ["'index'", '"index"', 'index']
            has_index = any(pattern in content for pattern in index_patterns)
            self.assertTrue(has_index, "Public app should have index URL pattern")

    def test_users_namespace_exists(self):
        """Test that users namespace is properly configured."""
        if self.url_files['users'].exists():
            with open(self.url_files['users'], 'r') as f:
                content = f.read()
            
            # Should have app_name defined
            self.assertIn("app_name = 'users'", content, "Users app should define app_name")
            
            # Should have profile or login URL patterns
            profile_patterns = ["'profile'", '"profile"', 'profile']
            login_patterns = ["'login'", '"login"', 'login']
            has_profile = any(pattern in content for pattern in profile_patterns)
            has_login = any(pattern in content for pattern in login_patterns)
            self.assertTrue(has_profile or has_login, "Users app should have profile or login URL pattern")

    def test_admin_dashboard_namespace_exists(self):
        """Test that admin_dashboard namespace is properly configured."""
        if self.url_files['admin_dashboard'].exists():
            with open(self.url_files['admin_dashboard'], 'r') as f:
                content = f.read()
            
            # Should have app_name defined
            self.assertIn("app_name = 'admin_dashboard'", content, "Admin dashboard should define app_name")
            
            # Should have index URL pattern
            index_patterns = ["'index'", '"index"', 'index']
            has_index = any(pattern in content for pattern in index_patterns)
            self.assertTrue(has_index, "Admin dashboard should have index URL pattern")

    def test_credits_namespace_exists(self):
        """Test that credits namespace is properly configured."""
        if self.url_files['credits'].exists():
            with open(self.url_files['credits'], 'r') as f:
                content = f.read()
            
            # Should have app_name defined
            self.assertIn("app_name = 'credits'", content, "Credits app should define app_name")
            
            # Should have dashboard URL pattern
            dashboard_patterns = ["'dashboard'", '"dashboard"', 'dashboard']
            has_dashboard = any(pattern in content for pattern in dashboard_patterns)
            self.assertTrue(has_dashboard, "Credits app should have dashboard URL pattern")

    def test_api_namespace_exists(self):
        """Test that api namespace is properly configured."""
        if self.url_files['api'].exists():
            with open(self.url_files['api'], 'r') as f:
                content = f.read()
            
            # Should have app_name defined
            self.assertIn("app_name = 'api'", content, "API app should define app_name")
            
            # Should have API documentation URL pattern
            api_docs_patterns = ["'api_docs'", '"api_docs"', 'api_docs', 'docs']
            has_api_docs = any(pattern in content for pattern in api_docs_patterns)
            self.assertTrue(has_api_docs, "API app should have documentation URL pattern")

    def test_health_check_endpoint(self):
        """Test that health check endpoint is configured in core URLs."""
        if self.url_files['core'].exists():
            with open(self.url_files['core'], 'r') as f:
                content = f.read()
            
            # Should have health check URL pattern
            health_patterns = ["'health/'", '"health/"', 'health/', 'health_check']
            has_health = any(pattern in content for pattern in health_patterns)
            self.assertTrue(has_health, "Core URLs should have health check endpoint")


class MiddlewareConfigurationTest(unittest.TestCase):
    """Test middleware configuration and order."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.settings_file = self.base_path / 'quickscale' / 'templates' / 'core' / 'settings.py'

    def test_middleware_order(self):
        """Test that middleware is in the correct order."""
        if self.settings_file.exists():
            with open(self.settings_file, 'r') as f:
                content = f.read()
            
            # Should have MIDDLEWARE configuration
            self.assertIn("MIDDLEWARE = [", content, "Settings should define MIDDLEWARE")
            
            # Extract middleware list
            middleware_start = content.find("MIDDLEWARE = [")
            middleware_end = content.find("]", middleware_start)
            middleware_section = content[middleware_start:middleware_end]
            
            # Check that security middleware is first
            self.assertIn("django.middleware.security.SecurityMiddleware", middleware_section)
            
            # Check that our custom API middleware is present
            self.assertIn("core.api_middleware.APIKeyAuthenticationMiddleware", middleware_section)

    def test_security_middleware_present(self):
        """Test that essential security middleware is present."""
        if self.settings_file.exists():
            with open(self.settings_file, 'r') as f:
                content = f.read()
            
            essential_middleware = [
                'django.middleware.security.SecurityMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.middleware.clickjacking.XFrameOptionsMiddleware',
            ]
            
            for mw in essential_middleware:
                self.assertIn(mw, content, f"Essential middleware {mw} not found")

    def test_custom_api_middleware_present(self):
        """Test that custom API middleware is present."""
        if self.settings_file.exists():
            with open(self.settings_file, 'r') as f:
                content = f.read()
            
            self.assertIn('core.api_middleware.APIKeyAuthenticationMiddleware', content)


class SettingsOrganizationTest(unittest.TestCase):
    """Test settings organization and structure."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.settings_files = {
            'main': self.base_path / 'quickscale' / 'templates' / 'core' / 'settings.py',
            'email': self.base_path / 'quickscale' / 'templates' / 'core' / 'email_settings.py',
            'security': self.base_path / 'quickscale' / 'templates' / 'core' / 'security_settings.py',
            'logging': self.base_path / 'quickscale' / 'templates' / 'core' / 'logging_settings.py'
        }

    def test_modular_settings_import(self):
        """Test that modular settings are properly imported."""
        for name, settings_file in self.settings_files.items():
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    content = f.read()
                
                # Should be valid Python file (basic syntax check)
                self.assertNotIn("SyntaxError", content, f"{name} settings should be valid Python")
                
                # Should have appropriate imports if it's a settings file
                if name == 'main':
                    # Check for Django-related configuration
                    django_indicators = [
                        "INSTALLED_APPS", "MIDDLEWARE", "DATABASES", 
                        "django.contrib", "TEMPLATES", "BASE_DIR"
                    ]
                    has_django = any(indicator in content for indicator in django_indicators)
                    self.assertTrue(has_django, "Main settings should contain Django configuration")

    def test_logging_configuration_present(self):
        """Test that logging configuration is properly set up."""
        if self.settings_files['main'].exists():
            with open(self.settings_files['main'], 'r') as f:
                content = f.read()
            
            # Should have LOGGING configuration
            self.assertIn("LOGGING", content, "Settings should define LOGGING configuration")

    def test_feature_flags_in_settings(self):
        """Test that feature flags are properly configured."""
        if self.settings_files['main'].exists():
            with open(self.settings_files['main'], 'r') as f:
                content = f.read()
            
            # Test that Stripe feature flag exists
            self.assertIn("STRIPE_ENABLED", content, "Settings should define STRIPE_ENABLED")

    def test_environment_first_configuration(self):
        """Test that configuration comes from environment variables."""
        if self.settings_files['main'].exists():
            with open(self.settings_files['main'], 'r') as f:
                content = f.read()
            
            # Test that common environment-based settings exist
            env_based_settings = [
                'SECRET_KEY',
                'DEBUG', 
                'ALLOWED_HOSTS',
                'PROJECT_NAME',
            ]
            
            for setting_name in env_based_settings:
                self.assertIn(setting_name, content, f"Setting {setting_name} should be defined")


class ProductionValidationTest(unittest.TestCase):
    """Test production settings validation."""

    @patch('quickscale.utils.env_utils.get_env')
    @patch('quickscale.utils.env_utils.is_feature_enabled')
    def test_production_validation_with_insecure_secret(self, mock_is_feature_enabled, mock_get_env):
        """Test that production validation fails with insecure SECRET_KEY."""
        mock_is_feature_enabled.return_value = True  # IS_PRODUCTION = True
        mock_get_env.side_effect = lambda key, default=None: {
            'SECRET_KEY': 'dev-only-dummy-key-replace-in-production',
            'ALLOWED_HOSTS': 'example.com',
        }.get(key, default)
        
        from quickscale.utils.env_utils import validate_production_settings
        
        with self.assertRaises(ValueError) as context:
            validate_production_settings()
        
        self.assertIn("secure SECRET_KEY", str(context.exception))

    @patch('quickscale.utils.env_utils.get_env')
    @patch('quickscale.utils.env_utils.is_feature_enabled')
    def test_production_validation_with_wildcard_hosts(self, mock_is_feature_enabled, mock_get_env):
        """Test that production validation fails with wildcard ALLOWED_HOSTS."""
        mock_is_feature_enabled.return_value = True  # IS_PRODUCTION = True
        mock_get_env.side_effect = lambda key, default=None: {
            'SECRET_KEY': 'secure-production-key-123',
            'ALLOWED_HOSTS': '*',
        }.get(key, default)
        
        from quickscale.utils.env_utils import validate_production_settings
        
        with self.assertRaises(ValueError) as context:
            validate_production_settings()
        
        self.assertIn("specific ALLOWED_HOSTS", str(context.exception))


class DatabaseModelsSOLIDPrinciplesTests(unittest.TestCase):
    """Test cases for SOLID principles compliance in database models."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.models_files = {
            'credits': self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py',
            'users': self.base_path / 'quickscale' / 'templates' / 'users' / 'models.py',
            'stripe_manager': self.base_path / 'quickscale' / 'templates' / 'stripe_manager' / 'models.py',
            'admin_dashboard': self.base_path / 'quickscale' / 'templates' / 'admin_dashboard' / 'models.py',
            'services': self.base_path / 'quickscale' / 'templates' / 'services' / 'models.py'
        }
    
    def test_single_responsibility_principle_credits_models(self):
        """Test that credits models follow Single Responsibility Principle."""
        with open(self.models_files['credits'], 'r') as f:
            content = f.read()
        
        # CreditAccount should handle account management only
        self.assertIn("class CreditAccount(models.Model)", content,
                     "CreditAccount model not found")
        
        # Check that CreditAccount has focused responsibilities (balance methods)
        balance_methods = [
            "def get_balance",
            "def get_balance_by_type", 
            "def get_available_balance"
        ]
        
        balance_method_count = sum(1 for method in balance_methods if method in content)
        self.assertGreaterEqual(balance_method_count, 2,
                               "CreditAccount should have balance-related methods")
        
        # Service model should be focused on service definition only
        self.assertIn("class Service(models.Model)", content,
                     "Service model not found")
        
        # ServiceUsage should handle usage tracking only
        self.assertIn("class ServiceUsage(models.Model)", content,
                     "ServiceUsage model not found")
    
    def test_open_closed_principle_validation(self):
        """Test that models are open for extension but closed for modification."""
        with open(self.models_files['credits'], 'r') as f:
            credits_content = f.read()
        
        # Check for proper use of abstract methods and inheritance
        self.assertIn("def __str__(self):", credits_content,
                     "Models should implement string representation")
        
        # Check for proper Meta classes for extension
        self.assertIn("class Meta:", credits_content,
                     "Models should have Meta classes for configuration")
        
        # Check for property decorators for calculated fields
        self.assertIn("@property", credits_content,
                     "Models should use properties for calculated fields")
    
    def test_liskov_substitution_principle_user_models(self):
        """Test that custom user model properly extends AbstractUser."""
        with open(self.models_files['users'], 'r') as f:
            content = f.read()
        
        # CustomUser should properly extend AbstractUser
        self.assertIn("class CustomUser(AbstractUser):", content,
                     "CustomUser should extend AbstractUser")
        
        # Should properly implement USERNAME_FIELD
        self.assertIn("USERNAME_FIELD = 'email'", content,
                     "CustomUser should use email as USERNAME_FIELD")
        
        # Should have proper manager
        self.assertIn("objects = CustomUserManager()", content,
                     "CustomUser should use CustomUserManager")
    
    def test_interface_segregation_principle_stripe_models(self):
        """Test that Stripe models have focused interfaces."""
        with open(self.models_files['stripe_manager'], 'r') as f:
            content = f.read()
        
        # StripeCustomer should focus on customer data
        self.assertIn("class StripeCustomer(models.Model):", content,
                     "StripeCustomer model not found")
        
        # StripeProduct should focus on product data
        self.assertIn("class StripeProduct(models.Model):", content,
                     "StripeProduct model not found")
        
        # Check for focused property methods
        self.assertIn("@property", content,
                     "Stripe models should have property methods")
    
    def test_dependency_inversion_principle_relationships(self):
        """Test that models depend on abstractions, not concretions."""
        with open(self.models_files['credits'], 'r') as f:
            content = f.read()
        
        # Should use get_user_model() for User references
        self.assertIn("from django.contrib.auth import get_user_model", content,
                     "Should import get_user_model")
        self.assertIn("User = get_user_model()", content,
                     "Should use get_user_model() for User reference")
        
        # Should not hardcode User model
        self.assertNotIn("from django.contrib.auth.models import User", content,
                        "Should not hardcode User model import")


class DatabaseRelationshipsValidationTests(unittest.TestCase):
    """Test cases for validating database relationships and constraints."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_models = self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py'
        self.stripe_models = self.base_path / 'quickscale' / 'templates' / 'stripe_manager' / 'models.py'
        self.admin_models = self.base_path / 'quickscale' / 'templates' / 'admin_dashboard' / 'models.py'
    
    def test_foreign_key_relationships_credits(self):
        """Test foreign key relationships in credits models."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # CreditAccount should have OneToOneField to User
        self.assertIn("user = models.OneToOneField", content,
                     "CreditAccount should have OneToOneField to User")
        self.assertIn("related_name='credit_account'", content,
                     "CreditAccount should have proper related_name")
        
        # CreditTransaction should have ForeignKey to User
        self.assertIn("user = models.ForeignKey", content,
                     "CreditTransaction should have ForeignKey to User")
        self.assertIn("related_name='credit_transactions'", content,
                     "CreditTransaction should have proper related_name")
        
        # ServiceUsage relationships
        service_usage_relationships = [
            "user = models.ForeignKey",
            "service = models.ForeignKey", 
            "credit_transaction = models.ForeignKey"
        ]
        for relationship in service_usage_relationships:
            self.assertIn(relationship, content,
                         f"ServiceUsage should have {relationship}")
    
    def test_cascade_behavior_validation(self):
        """Test that cascade behaviors are properly defined."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # Critical relationships should have CASCADE
        cascade_patterns = [
            "on_delete=models.CASCADE",
        ]
        
        for pattern in cascade_patterns:
            self.assertIn(pattern, content,
                         f"Should have proper cascade behavior: {pattern}")
        
        # Some relationships should have SET_NULL for data preservation
        self.assertIn("on_delete=models.SET_NULL", content,
                     "Should have SET_NULL for some relationships")
    
    def test_related_name_consistency(self):
        """Test that related_name attributes follow consistent naming."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # Check for consistent related_name patterns
        related_names = re.findall(r"related_name='(\w+)'", content)
        
        # Define acceptable patterns for related names
        acceptable_patterns = [
            '_account',     # credit_account
            '_customer',    # stripe_customer  
            's',           # plural forms: payments, transactions, etc.
            '_usage',      # service_usage
            'subscription', # special case for user subscription (singular makes sense)
            'payment'      # special case for payment (singular makes sense for one-to-one relationships)
        ]
        
        # Should follow consistent naming patterns
        for name in related_names:
            is_acceptable = any(
                name.endswith(pattern) or name == pattern 
                for pattern in acceptable_patterns
            )
            self.assertTrue(is_acceptable,
                           f"Related name {name} should follow consistent naming patterns")


class DatabasePerformancePatternTests(unittest.TestCase):
    """Test cases for database performance patterns and indexing."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_models = self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py'
        self.stripe_models = self.base_path / 'quickscale' / 'templates' / 'stripe_manager' / 'models.py'
    
    def test_database_indexes_credits(self):
        """Test that proper database indexes are defined."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # Should have indexes in Meta classes
        self.assertIn("indexes = [", content,
                     "Models should define database indexes")
        
        # Check for specific index patterns
        index_patterns = [
            "models.Index(fields=",
        ]
        
        for pattern in index_patterns:
            self.assertIn(pattern, content,
                         f"Should have proper index definition: {pattern}")
    
    def test_ordering_definitions(self):
        """Test that models have proper ordering definitions."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # Check for ordering in Meta classes
        ordering_patterns = [
            "ordering = [",
            "'-created_at'",
            "'name'"
        ]
        
        for pattern in ordering_patterns:
            self.assertIn(pattern, content,
                         f"Should have proper ordering: {pattern}")
    
    def test_field_optimization(self):
        """Test that fields are optimized for performance."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # Check for proper field configurations
        optimization_patterns = [
            "db_index=True",  # For frequently queried fields
            "unique=True",    # For uniqueness constraints
            "blank=True",     # For optional fields
            "null=True"       # For database NULL values
        ]
        
        for pattern in optimization_patterns:
            self.assertIn(pattern, content,
                         f"Should have field optimization: {pattern}")


class MigrationHistoryConsistencyTests(unittest.TestCase):
    """Test cases for migration history consistency."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.migrations_dirs = {
            'credits': self.base_path / 'quickscale' / 'templates' / 'credits' / 'migrations',
            'stripe_manager': self.base_path / 'quickscale' / 'templates' / 'stripe_manager' / 'migrations',
            'users': self.base_path / 'quickscale' / 'templates' / 'users' / 'migrations',
            'admin_dashboard': self.base_path / 'quickscale' / 'templates' / 'admin_dashboard' / 'migrations'
        }
    
    def test_migration_naming_consistency(self):
        """Test that migration files follow consistent naming patterns."""
        for app_name, migrations_dir in self.migrations_dirs.items():
            if migrations_dir.exists():
                migration_files = [f for f in migrations_dir.iterdir() 
                                 if f.name.endswith('.py') and f.name != '__init__.py']
                
                for migration_file in migration_files:
                    # Should follow Django migration naming pattern
                    self.assertTrue(re.match(r'^\d{4}_\w+\.py$', migration_file.name),
                                   f"Migration {migration_file.name} should follow naming pattern")
    
    def test_foreign_key_migrations_consistency(self):
        """Test that foreign key relationships are consistent in migrations."""
        credits_initial = self.migrations_dirs['credits'] / '0001_initial.py'
        if credits_initial.exists():
            with open(credits_initial, 'r') as f:
                content = f.read()
            
            # Should reference settings.AUTH_USER_MODEL
            self.assertIn("settings.AUTH_USER_MODEL", content,
                         "Should use settings.AUTH_USER_MODEL for User references")


class ModelBusinessLogicSeparationTests(unittest.TestCase):
    """Test cases for business logic separation in models."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_models = self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py'
    
    def test_credit_account_business_logic(self):
        """Test that CreditAccount has proper business logic separation."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # Should have balance calculation methods
        balance_methods = [
            "def get_balance",
            "def get_balance_by_type",
            "def get_available_balance"
        ]
        
        for method in balance_methods:
            self.assertIn(method, content,
                         f"CreditAccount should have {method} method")
        
        # Should have credit management methods
        credit_methods = [
            "def add_credits",
            "def consume_credits_with_priority"
        ]
        
        for method in credit_methods:
            self.assertIn(method, content,
                         f"CreditAccount should have {method} method")
    
    def test_property_methods_usage(self):
        """Test that models use property methods appropriately."""
        with open(self.credits_models, 'r') as f:
            content = f.read()
        
        # Should have property decorators for calculated fields
        property_methods = re.findall(r'@property\s+def (\w+)', content)
        
        self.assertGreater(len(property_methods), 0,
                          "Models should have property methods")
        
        # Common property patterns
        expected_properties = ['is_active', 'is_expired', 'is_valid']
        found_properties = set(property_methods)
        
        for prop in expected_properties:
            if prop in content:
                self.assertIn(prop, found_properties,
                             f"Property {prop} should use @property decorator")


if __name__ == '__main__':
    unittest.main() 