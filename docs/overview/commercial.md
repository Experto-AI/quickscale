# QuickScale Commercial Extensions

<!--
commercial.md - Commercial Extensions and Business Model

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

🔎 **Scope note**: Commercial distribution via PyPI and private repositories is **Phase 4 (v1.0.0+)** per [roadmap.md Post-MVP evolution](../technical/roadmap.md#post-mvp-evolution-phases-2). The MVP (Phase 1) uses git-subtree for code sharing across your own projects. Packaging and commercial distribution capabilities arrive in Phase 4.

## Quick Reference

- **License**: Apache 2.0 allows commercial use, private distribution, and proprietary extensions.
- **Phase**: Commercial PyPI distribution is **Phase 4 (v2.0.0+)**. Everything beyond personal git-subtree workflows is Post-MVP planning.
- **Where to start**: Embed QuickScale as a personal toolkit first; revisit this guide once you have repeatable commercial demand.
-- **Technical patterns**: See the [backend extensions policy](../technical/decisions.md#backend-extensions-policy) for canonical code hooks.

## Commercial Distribution Timeline

| Phase | Version | Commercial Capability |
|-------|---------|---------------------|
| Phase 1 | v0.57.0 | Personal toolkit only (git subtree) |
| Phase 2 | v0.58-v0.5x | Module extraction via git subtree |
| Phase 3 | v0.6x | Professional polish, prepare for distribution |
| Phase 4 | v1.0.0+ | **PyPI + private repository distribution enabled** |

See [roadmap.md](../technical/roadmap.md) for detailed phase descriptions and timeline.

## Table of Contents
- [Commercial Licensing Rights](#commercial-licensing-rights)
- [Post-MVP Playbook](#post-mvp-playbook)
    - [Private Repository Architecture](#private-repository-architecture)
    - [Benefits of Commercial Approach](#benefits-of-commercial-approach)
    - [Subscription-Based Repository Implementation](#subscription-based-repository-implementation)
    - [Business Logic Integration](#business-logic-integration-post-mvp)
    - [Security Considerations](#security-considerations)
    - [Operational Logistics](#operational-logistics)
- [See Also](#see-also)

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

---

## Post-MVP Playbook

> Everything below describes phase 3+ capabilities. Use it for planning only; the MVP delivers none of these features yet.

### Private Repository Architecture

#### Commercial Repository Structure

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

#### Hybrid Public/Private Strategy

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

### Benefits of Commercial Approach

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

### Subscription-Based Repository Implementation

#### Repository Setup Options

##### A. GitHub Private Repository with Access Control

```bash
# Create private repository
gh repo create commercial-quickscale-modules --private \
  --description "Commercial QuickScale modules"

# Manage subscriber access via GitHub teams/organizations
# Subscribers get repository access through GitHub's built-in access control
```

##### B. Self-Hosted Git Server (More Control)

```bash
# Using Gitea, GitLab CE, or similar
docker run -d --name gitea -p 3000:3000 gitea/gitea:latest

# Create subscription-based user groups
# Implement custom access control logic
```

#### Subscription Management System

##### A. Simple License Key System

```python
# commercial_license.py
class SubscriptionManager:
    def __init__(self, license_key):  # Store the license key for validation workflows
        pass

    def validate_subscription(self):  # Validate the license with your commercial backend
        pass

    def get_features(self):  # Return feature flags for the current subscription tier
        pass

    def get_tier(self):  # Report the subscription tier used for feature gating
        pass
```

##### B. Module-Level License Checking

```python
# quickscale_modules/commercial_saas/__init__.py
"""Commercial SaaS Module - Subscription Required"""
import os
from commercial_license import SubscriptionManager

def initialize_commercial_module():  # Validate the license before exposing commercial features (Post-MVP placeholder)
    pass

FEATURES = initialize_commercial_module()  # Placeholder for lazily-evaluated feature metadata
```

#### Distribution Methods (Post-MVP)

ℹ️ Remember: distribution automation lives firmly in Post-MVP territory.

##### A. Git Subtree with Access Tokens

```bash
# Subscriber gets access via personal access token
export GITHUB_TOKEN="ghp_your_subscriber_token_here"

# Pull updates (requires valid subscription)
git subtree pull --prefix=quickscale_modules/commercial_saas \
  https://$GITHUB_TOKEN@github.com/yourcompany/commercial-quickscale-modules.git main --squash
```

##### B. CLI Tool for Subscription Management

```python
# commercial_cli.py
from commercial_license import SubscriptionManager

class CommercialCLI:
    def install_commercial_module(self, module_name, license_key):  # Validate the license and fetch the module (Post-MVP)
        pass

    def update_commercial_module(self, module_name):  # Refresh a module after re-validating the subscriber (Post-MVP)
        pass

    def get_repository_url(self, module_name, tier):  # Map subscription tier to the correct repository URL (Post-MVP)
        pass

    def store_license_key(self, license_key):  # Persist the encrypted license key for future updates (Post-MVP)
        pass

    def get_stored_license_key(self):  # Retrieve the previously stored license key (Post-MVP)
        pass
```

#### Subscription Tiers Implementation

##### A. Tier-Based Feature Gates

```python
# commercial_features.py
class CommercialFeatures:
    def __init__(self, subscription_tier):  # Capture subscription tier metadata (Post-MVP)
        pass

    def has_feature(self, feature_name):  # Check if the current tier unlocks a feature (Post-MVP)
        pass

    def get_available_modules(self):  # Return modules available for the subscription tier (Post-MVP)
        pass

    def get_limits(self):  # Return usage limits for the subscription tier (Post-MVP)
        pass
```

##### B. Repository Branching Strategy

```bash
# Different branches for different subscription tiers
main                    # Latest enterprise features
professional-v1.0       # Professional tier features
basic-v1.0             # Basic tier features

# Subscribers get access to appropriate branch
git subtree add --prefix=quickscale_modules/commercial \
  https://github.com/yourcompany/commercial-modules.git professional-v1.0 --squash
```

### Business Logic Integration (Post-MVP)

#### A. Subscription-Aware Business Rules

```python
# commercial_saas/business.py
from commercial_features import CommercialFeatures

class CommercialBusinessLogic:
    def __init__(self):  # Prepare commercial feature helpers for the active tier (Post-MVP)
        pass

    def process_advanced_analytics(self, data):  # Run advanced analytics reserved for premium tiers (Post-MVP)
        pass

    def create_user(self, user_data):  # Enforce tier-based limits when creating users (Post-MVP)
        pass

    def get_subscription_tier(self):  # Determine the active subscription tier (Post-MVP)
        pass

    def _check_usage_limit(self, limit_type):  # Check whether usage limits are exceeded (Post-MVP)
        pass
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
    def __init__(self, cache_file='~/.quickscale/license_cache.json', cache_duration=24*60*60):  # Configure cache location and duration (Post-MVP)
        pass

    def validate_subscription(self, license_key):  # Validate with cache fallback for offline use (Post-MVP)
        pass

    def _get_cached_result(self, license_key):  # Retrieve cached validation result (Post-MVP)
        pass

    def _is_cache_valid(self, cached_result):  # Determine whether the cached result is still valid (Post-MVP)
        pass

    def _cache_result(self, license_key, is_valid):  # Persist validation results back to the cache (Post-MVP)
        pass
```

### Operational Logistics

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

#### B. Project Configuration with Commercial Modules (Post-MVP illustrative)

ℹ️ This YAML-driven workflow is illustrative and sits firmly in Post-MVP plans.

For canonical guidance on backend extension patterns, see the [backend extensions policy](../technical/decisions.md#backend-extensions-policy).

```yaml
# quickscale.yml with commercial modules (Post-MVP illustrative - not part of MVP)
schema_version: 1
project:
  name: my-enterprise-saas
  version: 0.70.0

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
    def __init__(self):  # Prepare analytics helpers for enterprise workflows (Post-MVP)
        pass

    def generate_enterprise_report(self, data):  # Generate advanced analytics for enterprise tiers (Post-MVP)
        pass

    def _fallback_basic_report(self, data):  # Provide a basic report when premium features are unavailable (Post-MVP)
        pass

    def _notify_limit_exceeded(self):  # Trigger notifications when usage limits are exceeded (Post-MVP)
        pass
```

#### Business Model Implementation

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

def get_tier_features(tier_name):  # Return the feature list for a subscription tier (Post-MVP)
    pass

def calculate_pricing(tier_name, billing_cycle='monthly'):  # Calculate pricing for a tier and billing cycle (Post-MVP)
    pass
```

#### B. License Generation and Management

```python
# license_generator.py
import uuid
import hashlib
import json
from datetime import datetime, timedelta

class LicenseGenerator:
    def generate_license(self, tier, customer_id, validity_days=365):  # Produce license metadata and return a key (Post-MVP)
        pass

    def validate_license_format(self, license_key):  # Validate the license key format (Post-MVP)
        pass

    def _store_license_data(self, license_key, data):  # Persist license metadata to storage (Post-MVP)
        pass
```

#### Deployment and Operations

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

# Update all commercial modules (Post-MVP illustrative helper - not provided by MVP)
# Note: This `commercial-quickscale` helper is an example of a Post-MVP convenience that
# would wrap manual git subtree or package registry operations. MVP users should follow
# the documented manual subtree or package workflows.
commercial-quickscale update-all

echo "✅ Commercial modules updated successfully"
```

#### B. Monitoring and Analytics

```python
# commercial_monitoring.py
class CommercialUsageMonitor:
    def __init__(self):  # Initialize billing/analytics tracking structures (Post-MVP)
        pass

    def track_usage(self, feature, customer_id):  # Record feature usage for billing analytics (Post-MVP)
        pass

    def _check_limits(self, customer_id, feature):  # Verify whether usage exceeds tier limits (Post-MVP)
        pass

    def generate_usage_report(self, customer_id):  # Summarize usage metrics for a customer (Post-MVP)
        pass

    def export_metrics(self):  # Export metrics to external analytics tooling (Post-MVP)
        pass
```

This commercial strategy enables you to build sustainable business models around QuickScale while maintaining the benefits of the open source foundation. The subscription-based approach provides recurring revenue while the Apache 2.0 license ensures legal compliance and community collaboration opportunities.

ℹ️ Reminder: everything in this section remains Post-MVP vision work.

Compatibility note: The new QuickScale architecture is intentionally breaking and not backward compatible; automated migrations are out-of-scope for the MVP. This document covers commercial distribution approaches for Post-MVP extensions where pip-based and registry-based options will be considered.

## See Also

- [decisions.md](../technical/decisions.md) — authoritative technical scope and backend extension policy
- [scaffolding.md](../technical/scaffolding.md) — canonical directory structures and naming matrix
- [roadmap.md](../technical/roadmap.md) — implementation phases that unlock the commercial playbook
