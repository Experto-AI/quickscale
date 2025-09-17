# **🚀 QuickScale**  

---

## ⚠️ **BREAKING CHANGE NOTICE** 

**🔥 QuickScale is evolving into a completely new architecture!**

We are transitioning from a **static project generator** to a **WordPress-like layered platform** for Django SaaS applications with industry specialization. This represents a **complete architectural redesign** that will **NOT be backward compatible** with existing QuickScale projects.

### **What's Changing:**
- **From**: Static project generator → Independent Django projects
- **To**: QuickScale core application + theme/skin/plugin layer system → Deployed applications
- **New Features**: Industry-specific business themes, visual presentation skins, community marketplace
- **Benefits**: Shared updates, vertical market specialization, clean separation of concerns

### **Migration Impact:**
- ⚠️ **No Backward Compatibility**: Existing projects will not migrate to the new system
- ⚠️ **Fresh Architecture**: This will be an entirely new platform in the next release, not an update
- ✅ **Current Version Stable**: v0.41.0 remains fully functional for existing projects

### **Learn More:**
📖 **Read the complete evolution plan**: [QUICKSCALE_EVOLUTION.md](./QUICKSCALE_EVOLUTION.md)

---

**A Django SaaS project generator for AI Engineers and Python developers**  

QuickScale is a project generator that creates production-ready Django SaaS applications with Stripe billing, credit systems, AI service frameworks, and comprehensive admin tools. Build and deploy AI-powered SaaS applications quickly with minimal setup.

👉 **Go from AI prototype to paying customers in minutes.**  

## QUICK START 🚀

1. **Install**: `pip install quickscale`
2. **Create project**: `quickscale init my-saas-app`
3. **Configure**: Edit `.env` file with your settings
4. **Start**: `quickscale up`
5. **Access**: `http://localhost:8000`

## KEY FEATURES

- **✅ Complete SaaS Foundation**: Email-only authentication, user management, credit billing
- **✅ Credit System**: Pay-as-you-go and subscription credits with priority consumption
- **✅ AI Service Framework**: BaseService class with automatic credit consumption and usage tracking
- **✅ Modern Stack**: HTMX + Alpine.js frontend, PostgreSQL database, Docker containerization
- **✅ Admin Tools**: User management, credit administration, service configuration, payment tools
- **✅ CLI Management**: Project lifecycle, service generation, Django command integration
- **✅ Starter Accounts**: Pre-configured test accounts (`user@test.com`, `admin@test.com`)


## CLI COMMANDS

QuickScale provides comprehensive command-line tools for project management:

### **Project Management**
```bash
quickscale init <project-name>     # Create new project
quickscale up                      # Start services  
quickscale down                    # Stop services
quickscale ps                      # Show service status
quickscale destroy                 # Delete project (keeps Docker images)
quickscale destroy --delete-images # Delete project + Docker images
```

### **Development Tools**
```bash
quickscale logs [service]          # View logs (web, db, or all)
quickscale shell                   # Interactive bash shell in container
quickscale django-shell            # Django shell in container
quickscale manage <command>        # Run Django management commands
quickscale sync-back [path]        # Sync changes back to templates (dev mode)
```

### **Service Management**
```bash
# Default services are automatically created during 'quickscale up'
quickscale manage create_default_services        # Recreate default example services
quickscale manage configure_service <name>       # Configure individual services
quickscale manage configure_service --list       # List all configured services
```

### **AI Service Framework**
```bash
quickscale generate-service <name>              # Generate AI service template
quickscale generate-service <name> --type text  # Generate text processing service
quickscale generate-service <name> --free       # Generate free service (no credits)
quickscale validate-service <path>              # Validate service implementation
quickscale show-service-examples                # Show example service implementations
```

### **Application Validation**
```bash
quickscale crawl --url <url>                    # Validate application functionality
quickscale crawl --admin --url <url> -v         # Test admin authentication and pages
```

### **System Tools**
```bash
quickscale check                   # Verify system requirements
quickscale version                 # Show version
quickscale help                    # Show help
```

## INCLUDED FEATURES

### **SaaS Foundation**
- **Authentication**: Email-only login, signup, password reset, user management
- **User Dashboard**: Credit balance, usage history, account management
- **Admin Dashboard**: User management, payment tracking, service analytics
- **Public Pages**: Landing page, about, contact forms

### **Billing & Credits System**
- **Stripe Integration**: Secure payment processing and subscription management
- **Credit Types**: Pay-as-you-go (never expire) and subscription credits (monthly)
- **Subscription Plans**: Basic and Pro tiers with automatic credit allocation
- **Payment History**: Complete transaction tracking with downloadable receipts
- **Admin Tools**: Manual credit management, payment investigation, refund processing

### **AI Service Framework**
- **Service Templates**: Generate text, image, and data processing services
- **Credit Integration**: Automatic credit consumption and usage tracking
- **BaseService Class**: Standard interface for all AI services with validation
- **Service Management**: Enable/disable services, track usage, cost configuration
- **API Ready**: RESTful API structure for service integration
- **Example Services**: Pre-configured demonstration services including sentiment analysis, keyword extraction, and free demo services

### **Technical Stack**
- **Backend**: Django 5.0+, PostgreSQL, Docker containerization
- **Frontend**: HTMX + Alpine.js for dynamic interactions
- **Styling**: Bulma CSS framework (responsive, clean design)
- **Deployment**: Docker Compose with environment configuration

## DEFAULT ACCOUNTS

QuickScale creates test accounts automatically for immediate development:

Default accounts available after startup:
- Regular User: user@test.com / userpasswd
- Administrator: admin@test.com / adminpasswd

Default AI services available for testing:
- Text Sentiment Analysis (1.0 credits)
- Image Metadata Extractor (10.0 credits)
- Demo Free Service (0.0 credits - FREE)

Access services at: http://localhost:8000/services/

*Note: Accounts are created automatically on first `quickscale up`. Change passwords in production.*

## CONFIGURATION

QuickScale uses a **Configuration Singleton** pattern for efficient environment management. Edit `.env` file in your project directory:

```env
# Project Settings
PROJECT_NAME=MyAwesomeApp
DEBUG=True
SECRET_KEY=auto-generated

# Database
DB_NAME=myapp_db
DB_USER=myapp_user
DB_PASSWORD=auto-generated

# Ports (auto-detected if in use)
WEB_PORT=8000
DB_PORT_EXTERNAL=5432

# Feature Flags (Ultra-Minimal Beta Configuration)
ENABLE_STRIPE=False               # Payment processing
ENABLE_SUBSCRIPTIONS=False        # Subscription plans
ENABLE_API_ENDPOINTS=False        # RESTful API access
ENABLE_SERVICE_GENERATOR=False    # AI service CLI commands

# Stripe (optional for development)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### **Configuration Architecture**

QuickScale implements a **single-read, cached configuration system** that:
- **Reads `.env` once** at startup for optimal performance
- **Caches all environment variables** to avoid repeated file system access
- **Uses feature flags** to enable/disable functionality without code changes
- **Validates required settings** based on enabled features
- **Supports different deployment modes** (development, production, testing)

### **Feature Flag System**

Control application features through environment variables:
- `ENABLE_STRIPE=True` - Enable payment processing and billing
- `ENABLE_SUBSCRIPTIONS=True` - Enable subscription plans and management
- `ENABLE_API_ENDPOINTS=True` - Enable RESTful API endpoints
- `ENABLE_SERVICE_GENERATOR=True` - Enable AI service generation commands

*Note: The Ultra-Minimal Beta defaults to basic functionality only. Enable features as needed for your use case.*

## DOCUMENTATION

- [**User Guide**](./USER_GUIDE.md) - Complete setup, usage, and deployment guide
- [**Technical Documentation**](./TECHNICAL_DOCS.md) - Architecture, API, and development details
- [**Testing Guide**](./docs/testing-guide.md) - Comprehensive testing documentation
- [**Contributing Guide**](./CONTRIBUTING.md) - Development guidelines and AI assistant rules
- [**Roadmap**](./ROADMAP.md) - Future features and development plans
- [**Changelog**](./CHANGELOG.md) - Release notes and version history

### **Specialized Documentation**
- [Credit System](./docs/CREDIT_SYSTEM.md) - Billing and subscription system details
- [Stripe Integration](./docs/STRIPE_INTEGRATION_REVIEW.md) - Payment processing implementation
- [AI Service Development](./docs/AI_VISUAL_DEVELOPMENT_SYSTEM.md) - Service creation guidelines
