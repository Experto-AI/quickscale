# QuickScale Commercial Extensions

<!-- 
COMMERCIAL.md - Commercial Extensions and Business Model

PURPOSE: This document outlines how solo developers and agencies can commercialize QuickScale extensions, create subscription models for premium modules/themes, and build community ecosystems while maintaining open source foundations.

CONTENT GUIDELINES:
- Document commercial licensing and distribution rights under Apache 2.0
- Detail subscription-based access models for premium extensions
- Provide technical implementation examples for commercial modules
- Cover business model options and revenue streams for developers/agencies
- Include security and license management approaches
- Show integration with open source QuickScale components
- Enable community building around commercial extensions

TARGET AUDIENCE: Solo developers, development agencies, commercial extension developers, community contributors
-->

## Overview

QuickScale's Apache 2.0 license enables commercial extensions and subscription models. This document shows how **solo developers and agencies** can build premium modules/themes, monetize their work, and create community ecosystems while leveraging the open source QuickScale foundation.

## Commercial Licensing Rights

### Apache 2.0 License Permissions

The Apache 2.0 license explicitly allows:
- ✅ **Commercial use**: Build and sell commercial products using QuickScale
- ✅ **Private distribution**: Distribute commercial modules privately
- ✅ **Proprietary modifications**: Create proprietary extensions and customizations
- ✅ **Service offerings**: Provide commercial services and support
- ✅ **Combined distribution**: Bundle QuickScale with proprietary code

### Commercial Business Models

**Supported Revenue Streams:**
- **Premium Modules**: Charge for advanced integrations and enterprise features
- **Professional Services**: Custom development and consultation
- **Subscription Access**: Private repositories with tiered access
- **Support Services**: Commercial support and maintenance contracts
- **White-label Solutions**: Branded QuickScale distributions

## Private Repository Architecture

### Commercial Repository Structure

```
private-commercial/
├── proprietary_modules/          # Commercial modules
│   ├── enterprise_auth/         # Enhanced authentication
│   ├── advanced_analytics/      # Business intelligence
│   ├── custom_integrations/     # API connectors
│   └── white_label/            # Branding tools
├── custom_themes/               # Branded themes
│   ├── corporate_theme/        # Enterprise branding
│   ├── industry_specific/      # Vertical solutions
│   └── client_custom/          # Client-specific themes
├── enterprise_features/         # Advanced features
│   ├── multi_tenant/           # Multi-tenancy support
│   ├── audit_logs/            # Compliance features
│   ├── advanced_security/     # Enterprise security
│   └── performance/           # Optimization tools
├── client_configs/              # Client-specific configs
│   ├── client_a/              # Client A configuration
│   ├── client_b/              # Client B configuration
│   └── templates/             # Configuration templates
├── docs/                        # Commercial documentation
├── scripts/                     # Deployment and management scripts
└── tests/                       # Commercial test suites
```

### Hybrid Public/Private Strategy

```
# Public repository (open source parts)
public-quickscale/
├── quickscale_core/              # Public - Apache 2.0
├── quickscale_modules/           # Public modules
│   ├── auth/                    # Free tier
│   ├── payments/                # Free tier
│   └── basic_analytics/         # Free tier
└── quickscale_themes/            # Public themes
    ├── starter/                 # Free
    └── basic/                   # Free

# Private repository (commercial extensions)
private-commercial/
├── quickscale_modules/           # Commercial modules
│   ├── enterprise_auth/         # Professional tier
│   ├── advanced_analytics/      # Enterprise tier
│   └── custom_integrations/     # Professional tier
├── quickscale_themes/            # Commercial themes
│   ├── enterprise/              # Enterprise tier
│   └── white_label/            # Enterprise tier
└── enterprise_features/          # Enterprise features
```

## Benefits of Commercial Approach

This hybrid approach allows you to:

✅ **Leverage all open source QuickScale components**
- Use the stable core, free modules, and basic themes
- Build upon proven Django foundations and patterns
- Benefit from community updates and security fixes

✅ **Build proprietary business logic and features**
- Create custom modules with unique business value
- Develop specialized themes for specific industries
- Implement enterprise features not available in open source

✅ **Distribute commercial modules privately**
- Control access through subscription models
- Maintain competitive advantages in proprietary code
- Implement tiered feature access

✅ **Charge for commercial extensions while using free core**
- Open source foundation reduces development costs
- Charge premium for value-added commercial features
- Multiple revenue streams from same codebase

✅ **Maintain compatibility with QuickScale updates**
- Git subtree enables clean separation of concerns
- Easy updates to open source components
- Backward compatibility through proper versioning

✅ **Keep commercial IP completely private**
- Private repositories protect proprietary code
- License validation prevents unauthorized access
- Commercial features isolated from open source contributions

## Subscription-Based Repository Implementation

### Repository Setup Options

#### A. GitHub Private Repository with Access Control

```bash
# Create private repository
gh repo create commercial-quickscale-modules --private \
  --description "Commercial QuickScale modules"

# Manage subscriber access via GitHub teams/organizations
# Subscribers get repository access through GitHub's built-in access control
```

#### B. Self-Hosted Git Server (More Control)

```bash
# Using Gitea, GitLab CE, or similar
docker run -d --name gitea -p 3000:3000 gitea/gitea:latest

# Create subscription-based user groups
# Implement custom access control logic
```

### Subscription Management System

#### A. Simple License Key System

```python
# commercial_license.py
import hashlib
import datetime
import requests

class SubscriptionManager:
    def __init__(self, license_key):
        self.license_key = license_key
        self.api_endpoint = "https://api.yourcompany.com/validate"
    
    def validate_subscription(self):
        """Validate subscription against your server"""
        response = requests.post(self.api_endpoint, json={
            'license_key': self.license_key,
            'module': 'commercial-saas-module',
            'version': '1.0.0'
        })
        
        if response.status_code == 200:
            data = response.json()
            return data.get('valid', False) and not data.get('expired', True)
        return False
    
    def get_features(self):
        """Return available features based on subscription tier"""
        if not self.validate_subscription():
            return []
        
        # Return features based on subscription level
        return ['advanced_analytics', 'custom_integrations', 'priority_support']
    
    def get_tier(self):
        """Get subscription tier"""
        if not self.validate_subscription():
            return 'none'
        
        response = requests.get(f"{self.api_endpoint}/tier", 
                              params={'license_key': self.license_key})
        return response.json().get('tier', 'basic')
```

#### B. Module-Level License Checking

```python
# quickscale_modules/commercial_saas/__init__.py
"""
Commercial SaaS Module - Subscription Required
"""
import os
from commercial_license import SubscriptionManager

def initialize_commercial_module():
    """Initialize commercial module with license validation"""
    license_key = os.getenv('QUICKSCALE_COMMERCIAL_LICENSE')
    
    if not license_key:
        raise LicenseError(
            "Commercial module requires subscription. "
            "Visit https://yourcompany.com/subscribe to get a license key."
        )
    
    manager = SubscriptionManager(license_key)
    if not manager.validate_subscription():
        raise LicenseError(
            "Invalid or expired subscription. "
            "Please renew at https://yourcompany.com/renew"
        )
    
    # Cache validation result
    global _subscription_valid
    _subscription_valid = True
    
    return manager.get_features()

# Initialize on import
FEATURES = initialize_commercial_module()
```

### Distribution Methods

#### A. Git Subtree with Access Tokens

```bash
# Subscriber gets access via personal access token
export GITHUB_TOKEN="ghp_your_subscriber_token_here"

# Pull updates (requires valid subscription)
git subtree pull --prefix=quickscale_modules/commercial_saas \
  https://$GITHUB_TOKEN@github.com/yourcompany/commercial-quickscale-modules.git main --squash
```

#### B. CLI Tool for Subscription Management

```python
# commercial_cli.py
import subprocess
import os
from commercial_license import SubscriptionManager

class CommercialCLI:
    def install_commercial_module(self, module_name, license_key):
        """Install commercial module with subscription validation"""
        
        # Validate subscription first
        manager = SubscriptionManager(license_key)
        if not manager.validate_subscription():
            print("❌ Invalid subscription. Please check your license key.")
            return False
        
        # Get repository URL (could be tier-specific)
        repo_url = self.get_repository_url(module_name, manager.get_tier())
        
        # Install via git subtree
        try:
            subprocess.run([
                'git', 'subtree', 'add', 
                f'--prefix=quickscale_modules/{module_name}',
                repo_url, 'main', '--squash'
            ], check=True)
            
            # Store license key in project config
            self.store_license_key(license_key)
            
            print(f"✅ Successfully installed {module_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Installation failed: {e}")
            return False
    
    def update_commercial_module(self, module_name):
        """Update commercial module (requires valid subscription)"""
        license_key = self.get_stored_license_key()
        manager = SubscriptionManager(license_key)
        
        if not manager.validate_subscription():
            print("❌ Subscription expired. Please renew to update.")
            return False
        
        repo_url = self.get_repository_url(module_name, manager.get_tier())
        
        subprocess.run([
            'git', 'subtree', 'pull',
            f'--prefix=quickscale_modules/{module_name}',
            repo_url, 'main', '--squash'
        ], check=True)
    
    def get_repository_url(self, module_name, tier):
        """Get appropriate repository URL based on tier"""
        base_urls = {
            'basic': f'https://github.com/yourcompany/{module_name}-basic.git',
            'professional': f'https://github.com/yourcompany/{module_name}-pro.git',
            'enterprise': f'https://github.com/yourcompany/{module_name}-enterprise.git'
        }
        return base_urls.get(tier, base_urls['basic'])
    
    def store_license_key(self, license_key):
        """Store license key securely"""
        config_path = '.quickscale/config'
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Encrypt license key before storing
        encrypted_key = self._encrypt_license_key(license_key)
        
        with open(config_path, 'w') as f:
            f.write(f'license_key={encrypted_key}\n')
    
    def get_stored_license_key(self):
        """Retrieve stored license key"""
        config_path = '.quickscale/config'
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r') as f:
            for line in f:
                if line.startswith('license_key='):
                    encrypted_key = line.split('=', 1)[1].strip()
                    return self._decrypt_license_key(encrypted_key)
        return None
    
    def _encrypt_license_key(self, key):
        """Simple encryption for license key storage"""
        # Implement proper encryption in production
        return key[::-1]  # Simple reverse for demo
    
    def _decrypt_license_key(self, encrypted_key):
        """Decrypt stored license key"""
        return encrypted_key[::-1]  # Simple reverse for demo
```

### Subscription Tiers Implementation

#### A. Tier-Based Feature Gates

```python
# commercial_features.py
class CommercialFeatures:
    def __init__(self, subscription_tier):
        self.tier = subscription_tier
    
    def has_feature(self, feature_name):
        """Check if subscription tier includes feature"""
        tier_features = {
            'basic': ['core_commercial', 'email_support'],
            'professional': ['basic', 'advanced_analytics', 'api_integrations'],
            'enterprise': ['professional', 'custom_development', 'white_label', 'phone_support']
        }
        
        return feature_name in tier_features.get(self.tier, [])
    
    def get_available_modules(self):
        """Return modules available for this tier"""
        tier_modules = {
            'basic': ['commercial-auth', 'commercial-payments'],
            'professional': ['basic', 'commercial-analytics', 'commercial-crm'],
            'enterprise': ['professional', 'commercial-enterprise', 'custom-modules']
        }
        
        return tier_modules.get(self.tier, [])
    
    def get_limits(self):
        """Return usage limits for this tier"""
        tier_limits = {
            'basic': {'users': 100, 'api_calls': 10000, 'storage_gb': 10},
            'professional': {'users': 1000, 'api_calls': 100000, 'storage_gb': 100},
            'enterprise': {'users': -1, 'api_calls': -1, 'storage_gb': -1}  # Unlimited
        }
        
        return tier_limits.get(self.tier, tier_limits['basic'])
```

#### B. Repository Branching Strategy

```bash
# Different branches for different subscription tiers
main                    # Latest enterprise features
professional-v1.0       # Professional tier features
basic-v1.0             # Basic tier features

# Subscribers get access to appropriate branch
git subtree add --prefix=quickscale_modules/commercial \
  https://github.com/yourcompany/commercial-modules.git professional-v1.0 --squash
```

### Business Logic Integration

#### A. Subscription-Aware Business Rules

```python
# commercial_saas/business.py
from commercial_features import CommercialFeatures

class CommercialBusinessLogic:
    def __init__(self):
        self.features = CommercialFeatures(self.get_subscription_tier())
        self.limits = self.features.get_limits()
    
    def process_advanced_analytics(self, data):
        """Advanced analytics - enterprise feature"""
        if not self.features.has_feature('advanced_analytics'):
            raise SubscriptionError("Advanced analytics requires Professional tier")
        
        # Check usage limits
        if self._check_usage_limit('api_calls'):
            raise LimitExceededError("API call limit exceeded for your tier")
        
        # Implement advanced analytics logic
        return self._run_advanced_analytics(data)
    
    def create_user(self, user_data):
        """Create user with tier-based limits"""
        current_users = self._get_current_user_count()
        if current_users >= self.limits['users'] and self.limits['users'] != -1:
            raise LimitExceededError(f"User limit ({self.limits['users']}) exceeded for your tier")
        
        return self._create_user_record(user_data)
    
    def get_subscription_tier(self):
        """Get current subscription tier"""
        # Check license and return tier
        return 'professional'  # Example implementation
    
    def _check_usage_limit(self, limit_type):
        """Check if usage limit is exceeded"""
        # Implement usage tracking logic
        return False  # Example: not exceeded
```

### Security Considerations

#### A. License Key Protection

```python
# Never log license keys
import logging
logging.getLogger('commercial_license').setLevel(logging.WARNING)

# Use environment variables
license_key = os.environ.get('QUICKSCALE_COMMERCIAL_LICENSE')

# Avoid printing in logs
print(f"License validation: {'SUCCESS' if is_valid else 'FAILED'}")
# NOT: print(f"License key: {license_key}")
```

#### B. Offline Validation with Caching

```python
# commercial_license_cache.py
import json
import os
import time
from commercial_license import SubscriptionManager

class CachedSubscriptionManager(SubscriptionManager):
    def __init__(self, cache_file='~/.quickscale/license_cache.json', cache_duration=24*60*60):
        super().__init__(license_key=None)  # Will be set per call
        self.cache_file = os.path.expanduser(cache_file)
        self.cache_duration = cache_duration  # 24 hours
    
    def validate_subscription(self, license_key):
        """Validate with cache fallback for offline use"""
        self.license_key = license_key
        
        # Check cache first
        cached_result = self._get_cached_result(license_key)
        if cached_result and self._is_cache_valid(cached_result):
            return cached_result['valid']
        
        # Online validation
        result = super().validate_subscription()
        self._cache_result(license_key, result)
        return result
    
    def _get_cached_result(self, license_key):
        """Get cached validation result"""
        if not os.path.exists(self.cache_file):
            return None
        
        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
                return cache.get(license_key)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _is_cache_valid(self, cached_result):
        """Check if cached result is still valid"""
        if not cached_result:
            return False
        
        cache_time = cached_result.get('timestamp', 0)
        return (time.time() - cache_time) < self.cache_duration
    
    def _cache_result(self, license_key, is_valid):
        """Cache validation result"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        
        # Load existing cache
        cache = {}
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
            except json.JSONDecodeError:
                pass
        
        # Update cache
        cache[license_key] = {
            'valid': is_valid,
            'timestamp': time.time()
        }
        
        # Save cache
        with open(self.cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
```

### Usage Examples

#### A. Subscriber Installation Process

```bash
# 1. Purchase subscription and get license key
# Visit https://yourcompany.com/subscribe

# 2. Install commercial CLI
pip install commercial-quickscale-cli

# 3. Install commercial module
commercial-quickscale install commercial-saas --license=YOUR_LICENSE_KEY

# 4. Verify installation
commercial-quickscale validate-license

# Output:
# ✅ License valid - Professional tier
# ✅ Available features: advanced_analytics, custom_integrations
# ✅ Available modules: commercial-auth, commercial-analytics
```

#### B. Project Configuration with Commercial Modules

```yaml
# quickscale.yml with commercial modules
schema_version: 1
project:
  name: my-enterprise-saas
  version: 1.0.0

theme: starter
backend_extensions: myenterprise.extensions

modules:
  auth: {}                    # Open source - no special config needed
  payments: {}               # Open source - no special config needed  
  commercial_saas: {}        # Commercial - requires subscription

commercial:
  license_key: "${QUICKSCALE_COMMERCIAL_LICENSE}"
  tier: enterprise
  offline_cache: true      # Allow offline validation
  auto_update: true        # Automatically update commercial modules

frontend:
  source: ./custom_frontend/
  variant: enterprise      # Commercial theme variant
```

#### C. Code Usage with Subscription Validation

```python
# myenterprise/extensions.py
from quickscale_themes.starter import models as starter_models
from quickscale_modules.commercial_saas import CommercialAnalytics

class EnterpriseUser(starter_models.User):
    """Extended user model with enterprise features"""
    department = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50)
    
    class Meta:
        app_label = 'myenterprise'

class EnterpriseBusinessLogic:
    def __init__(self):
        self.analytics = CommercialAnalytics()
    
    def generate_enterprise_report(self, data):
        """Generate advanced analytics report"""
        try:
            return self.analytics.generate_report(data)
        except SubscriptionError as e:
            # Handle subscription issues gracefully
            self._fallback_basic_report(data)
        except LimitExceededError as e:
            # Handle usage limits
            self._notify_limit_exceeded()
    
    def _fallback_basic_report(self, data):
        """Fallback to basic reporting if subscription issues"""
        # Implement basic reporting logic
        pass
    
    def _notify_limit_exceeded(self):
        """Notify about usage limit exceeded"""
        # Send notification to upgrade subscription
        pass
```

### Business Model Implementation

#### A. Revenue Tiers

```python
# pricing_tiers.py
SUBSCRIPTION_TIERS = {
    'basic': {
        'price_monthly': 49,
        'price_yearly': 490,
        'features': ['core_commercial', 'email_support', 'basic_modules'],
        'limits': {'users': 100, 'api_calls': 10000, 'storage_gb': 10}
    },
    'professional': {
        'price_monthly': 149,
        'price_yearly': 1490,
        'features': ['basic', 'advanced_analytics', 'api_integrations', 'priority_support'],
        'limits': {'users': 1000, 'api_calls': 100000, 'storage_gb': 100}
    },
    'enterprise': {
        'price_monthly': 499,
        'price_yearly': 4990,
        'features': ['professional', 'custom_development', 'white_label', 'phone_support'],
        'limits': {'users': -1, 'api_calls': -1, 'storage_gb': -1}  # Unlimited
    }
}

def get_tier_features(tier_name):
    """Get features for a subscription tier"""
    return SUBSCRIPTION_TIERS.get(tier_name, {}).get('features', [])

def calculate_pricing(tier_name, billing_cycle='monthly'):
    """Calculate pricing for tier and billing cycle"""
    tier = SUBSCRIPTION_TIERS.get(tier_name, {})
    if billing_cycle == 'yearly':
        return tier.get('price_yearly', 0)
    return tier.get('price_monthly', 0)
```

#### B. License Generation and Management

```python
# license_generator.py
import uuid
import hashlib
import json
from datetime import datetime, timedelta

class LicenseGenerator:
    def generate_license(self, tier, customer_id, validity_days=365):
        """Generate a new license key"""
        license_data = {
            'license_id': str(uuid.uuid4()),
            'customer_id': customer_id,
            'tier': tier,
            'issued_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=validity_days)).isoformat(),
            'features': get_tier_features(tier)
        }
        
        # Create license key from hash
        license_string = json.dumps(license_data, sort_keys=True)
        license_key = hashlib.sha256(license_string.encode()).hexdigest()[:32].upper()
        
        # Store license data (in database)
        self._store_license_data(license_key, license_data)
        
        return license_key
    
    def validate_license_format(self, license_key):
        """Basic format validation"""
        return len(license_key) == 32 and license_key.isalnum()
    
    def _store_license_data(self, license_key, data):
        """Store license data in database"""
        # Implement database storage
        pass
```

### Deployment and Operations

#### A. Commercial Module Updates

```bash
# Automated update script for commercial modules
#!/bin/bash
# update_commercial_modules.sh

LICENSE_KEY="${QUICKSCALE_COMMERCIAL_LICENSE}"
if [ -z "$LICENSE_KEY" ]; then
    echo "❌ QUICKSCALE_COMMERCIAL_LICENSE not set"
    exit 1
fi

# Validate subscription before update
if ! commercial-quickscale validate-license --quiet; then
    echo "❌ Invalid or expired subscription"
    exit 1
fi

# Update all commercial modules
commercial-quickscale update-all

echo "✅ Commercial modules updated successfully"
```

#### B. Monitoring and Analytics

```python
# commercial_monitoring.py
class CommercialUsageMonitor:
    def __init__(self):
        self.metrics = {}
    
    def track_usage(self, feature, customer_id):
        """Track feature usage for billing/analytics"""
        if customer_id not in self.metrics:
            self.metrics[customer_id] = {}
        
        if feature not in self.metrics[customer_id]:
            self.metrics[customer_id][feature] = 0
        
        self.metrics[customer_id][feature] += 1
        
        # Check limits
        self._check_limits(customer_id, feature)
    
    def _check_limits(self, customer_id, feature):
        """Check if usage exceeds tier limits"""
        # Implement limit checking logic
        pass
    
    def generate_usage_report(self, customer_id):
        """Generate usage report for customer"""
        return self.metrics.get(customer_id, {})
    
    def export_metrics(self):
        """Export metrics for business intelligence"""
        # Export to analytics system
        pass
```

This commercial strategy enables you to build sustainable business models around QuickScale while maintaining the benefits of the open source foundation. The subscription-based approach provides recurring revenue while the Apache 2.0 license ensures legal compliance and community collaboration opportunities.

MVP note: For Phase 1 the recommended and supported distribution method is git subtree (embedding the minimal starter theme and core into client repos). More advanced distribution options (publishing private/subscription packages via pip or private package indices) will be designed and implemented Post-MVP.

Compatibility note: The new QuickScale architecture is intentionally breaking and not backward compatible; automated migrations are out-of-scope for the MVP. This document covers commercial distribution approaches for Post-MVP extensions where pip-based and registry-based options will be considered.