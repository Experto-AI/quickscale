# **🚀 QuickScale**  

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

### **AI Service Framework**
```bash
quickscale generate-service <name>              # Generate AI service template
quickscale generate-service <name> --type text  # Generate text processing service
quickscale generate-service <name> --free       # Generate free service (no credits)
quickscale validate-service <path>              # Validate service implementation
quickscale show-service-examples                # Show example service implementations
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

### **Technical Stack**
- **Backend**: Django 5.0+, PostgreSQL, Docker containerization
- **Frontend**: HTMX + Alpine.js for dynamic interactions
- **Styling**: Bulma CSS framework (responsive, clean design)
- **Deployment**: Docker Compose with environment configuration

## DEFAULT ACCOUNTS

QuickScale creates test accounts automatically for immediate development:

- **User Account**: 
  - Email: `user@test.com` | Password: `userpasswd`
  - Access: User dashboard, billing, services

- **Admin Account**: 
  - Email: `admin@test.com` | Password: `adminpasswd`
  - Access: Admin dashboard, user management, payment tools

*Note: Accounts are created automatically on first `quickscale up`. Change passwords in production.*

## CONFIGURATION

Edit `.env` file in your project directory:

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

# Stripe (optional for development)
STRIPE_ENABLED=False
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## DOCUMENTATION

- [**User Guide**](./USER_GUIDE.md) - Complete setup, usage, and deployment guide
- [**Technical Documentation**](./TECHNICAL_DOCS.md) - Architecture, API, and development details
- [**Contributing Guide**](./CONTRIBUTING.md) - Development guidelines and AI assistant rules
- [**Roadmap**](./ROADMAP.md) - Future features and development plans
- [**Changelog**](./CHANGELOG.md) - Release notes and version history

### **Specialized Documentation**
- [Credit System](./docs/CREDIT_SYSTEM.md) - Billing and subscription system details
- [Stripe Integration](./docs/STRIPE_INTEGRATION_REVIEW.md) - Payment processing implementation
- [AI Service Development](./docs/AI_VISUAL_DEVELOPMENT_SYSTEM.md) - Service creation guidelines
