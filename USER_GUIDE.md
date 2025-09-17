# **QuickScale User Guide**

Welcome to QuickScale! This guide provides complete setup and deployment instructions for building SaaS applications with Django, Stripe billing, and AI service frameworks.

## **1. Installation & Setup**

### **Prerequisites**
- Python 3.11+ 
- Docker & Docker Compose
- Git (for development)

### **Install QuickScale**
```bash
# Install from PyPI
pip install quickscale

# Verify installation
quickscale check
```

### **Create Your First Project**
```bash
# Initialize new SaaS project
quickscale init my-saas-app

# Navigate to project directory
cd my-saas-app

# Review configuration file
cat .env

# Start services
quickscale up

# Access application
open http://localhost:8000
```

## **2. Project Management**

### **Starting & Stopping Services**
```bash
# Start all services (web app + database)
quickscale up

# Start with Docker cache rebuild
quickscale up --no-cache

# Stop all services
quickscale down

# Check service status
quickscale ps

# View service logs
quickscale logs              # All services
quickscale logs web          # Web application only
quickscale logs db           # Database only
```

### **Development Tools**
```bash
# Interactive bash shell in web container
quickscale shell

# Execute command in container
quickscale shell -c "python manage.py showmigrations"

# Django shell for model interaction
quickscale django-shell

# Run Django management commands
quickscale manage migrate
quickscale manage createsuperuser
quickscale manage collectstatic
```

### **Project Cleanup**
```bash
# Remove project (keeps Docker images for faster rebuild)
quickscale destroy

# Remove project and Docker images (slower rebuild)
quickscale destroy --delete-images
```

### **AI Service Development**
```bash
# Generate AI service template
quickscale generate-service my_ai_service

# Generate specific service types
quickscale generate-service sentiment_analyzer --type text_processing
quickscale generate-service image_classifier --type image_processing

# Validate service implementation
quickscale validate-service ./services/my_service.py

# Show available service examples
quickscale show-service-examples

# Configure service in database
quickscale manage configure_service my_service --credit-cost 2.0 --description "My AI service"
```

### **Application Validation**
```bash
# Test application health and page rendering
quickscale crawl

# Test with admin credentials
quickscale crawl --admin

# Test custom application URL
quickscale crawl --url http://localhost:8080

# Detailed validation with all page lists
quickscale crawl --detailed

# Custom authentication credentials
quickscale crawl --email test@example.com --password mypassword
```

## **3. Default Accounts & Access**

QuickScale creates test accounts automatically for immediate development:

### **User Account**
- **Email**: `user@test.com`
- **Password**: `userpasswd`
- **Access**: User dashboard, credit management, service usage

### **Admin Account**  
- **Email**: `admin@test.com`
- **Password**: `adminpasswd`
- **Access**: Admin dashboard, user management, payment tools, service analytics

*Note: Change passwords in production environments*

## **4. Configuration**

QuickScale uses a **Configuration Singleton** pattern for optimal performance and consistency. Edit `.env` file in your project directory:

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

# Feature Flags (Control application functionality)
ENABLE_STRIPE=False               # Payment processing and billing
ENABLE_SUBSCRIPTIONS=False        # Subscription management
ENABLE_API_ENDPOINTS=False        # RESTful API access
ENABLE_SERVICE_GENERATOR=False    # AI service generation
ENABLE_CREDIT_TYPES=False         # Multiple credit types (pay-as-you-go + subscription)
ENABLE_ADVANCED_ADMIN=False       # Advanced admin features

# Stripe (required when ENABLE_STRIPE=True)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### **Configuration Features**

**Performance Optimizations**:
- **Single Environment Read**: Configuration loaded once at startup
- **Cached Variables**: All settings cached in memory for fast access
- **Lazy Loading**: Only validates settings for enabled features

**Feature Flag System**:
- **Progressive Enhancement**: Start with minimal features, enable as needed
- **Safe Rollbacks**: Disable problematic features without code changes
- **Environment-Specific**: Different configurations for development/production

**Ultra-Minimal Beta Mode** (Default):
- Basic authentication and user management
- Simple credit system (fixed allocation)
- Single demo AI service
- Core admin functionality only

Enable additional features by setting the corresponding `ENABLE_*` flags to `True`.

## **5. Troubleshooting**

### **Common Issues**
- **Docker Not Running**: Ensure Docker is installed and running on your system
- **Port Already in Use**: QuickScale will fail immediately if the configured port is in use
- **Database Connection Errors**: Check `DB_USER`, `DB_PASSWORD`, and other database settings in `.env` file
- ** Stripe Configuration**: If using Stripe, ensure `ENABLE_STRIPE` is set to `True` and keys are correct

### **Logs**
Check logs for detailed error messages:
```bash
quickscale logs
quickscale logs web
quickscale logs db
```

### **Django Management Commands**
QuickScale integrates with Django's management commands through `quickscale manage`:

```bash
# Database management
quickscale manage migrate           # Run database migrations
quickscale manage makemigrations    # Create new migrations

# User management
quickscale manage createsuperuser   # Create a Django admin superuser
quickscale manage changepassword    # Change a user's password

# Testing
quickscale manage test              # Run all tests
quickscale manage test app_name     # Run tests for specific app

# Static files
quickscale manage collectstatic     # Collect static files

# Inspection
quickscale manage check             # Check for project issues
quickscale manage showmigrations    # Show migration status
```

## **6. Using the Web Interface**

Once your QuickScale project is running, access it at `http://localhost:8000`.

### **Authentication**
- **Registration**: `/accounts/signup/` - Enter email/password, verify email to activate
- **Login**: `/accounts/login/` - Use email/password to access dashboard
- **Password Reset**: Click "Forgot Password?" and follow email instructions

### **User Dashboard** 
- **Profile Management**: Update personal information
- **Credit Balance**: View and manage credits (if enabled)
- **Account Settings**: Change password and preferences

### **Admin Dashboard** (Staff only)
- **User Management**: View and manage user accounts
- **Credit Administration**: Manual credit adjustments with audit trails
- **Payment Tools**: Search payments, investigate issues, process refunds
- **Service Management**: Enable/disable services, view analytics

## **7. Credit System & Billing** (Optional)

If Stripe is enabled, users can purchase and manage credits:

### **Credit Types**
- **Pay-as-you-go**: Never expire, used second
- **Subscription**: Monthly allocation, used first

### **Purchasing**
- **One-time**: Select package, pay through Stripe checkout
- **Subscription**: Choose plan (Basic/Pro), automatic monthly allocation

### **Management**
- View balance breakdown and transaction history
- Upgrade/downgrade plans with automatic credit transfer
- Cancel subscriptions while keeping unused credits

---

For more detailed information, see:
- [**Technical Documentation**](./TECHNICAL_DOCS.md) - Architecture and development details
- [**Contributing Guide**](./CONTRIBUTING.md) - Development guidelines

## **8. AI Service Development**

QuickScale includes an AI service framework for creating credit-based AI services.

**Quick Start:**
```bash
# Generate a new AI service
quickscale generate-service --name my-ai-service

# View available service templates
quickscale show-service-examples

# Validate service configuration
quickscale validate-service
```

**Service Features:**
- **Credit Integration**: Automatic credit consumption and billing
- **Template System**: Pre-built service templates and examples  
- **API Endpoints**: RESTful API with authentication
- **Usage Tracking**: Built-in usage analytics and monitoring
- **Rate Limiting**: Configurable rate limiting and quotas

**Service Templates Available:**
- Text processing services
- Image analysis services
- API integration services
- Custom AI model services

For detailed AI service development, see [Technical Documentation](./TECHNICAL_DOCS.md).

---

## **9. Testing QuickScale Codebase**

Install test dependencies and run the test suite:


```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
./run_tests.sh

# Run unit tests
./run_tests.sh -u

# Run integration tests
./run_tests.sh -i

# Run end to end tests
./run_tests.sh -e

# Run with coverage report
./run_tests.sh --coverage

# Show only failed tests
./run_tests.sh --failures-only

# Stop on first failure
./run_tests.sh --exitfirst -u

# Run specific test file, specially for debugging
python -m pytest tests/unit/specific_unit_test.py
```

For Django application tests, you can use the Django test runner through the QuickScale CLI:

```bash
# Run all Django tests
quickscale manage test
```

## **10. Troubleshooting**

**Common Issues:**

- **Port conflicts**: Update ports in `.env` file
- **Database connection**: Verify PostgreSQL is running and credentials are correct
- **Static files**: Run `quickscale manage collectstatic`
- **Migrations**: Run `quickscale manage migrate`

**Getting Help:**
- Check logs: `quickscale logs`
- Verify configuration: `quickscale status`
- See [Technical Documentation](./TECHNICAL_DOCS.md) for detailed troubleshooting

---

## **Additional Resources**

- [Technical Documentation](./TECHNICAL_DOCS.md) - Architecture and development details
- [Credit System Documentation](./docs/CREDIT_SYSTEM.md) - Credit system details
- [Contributing Guide](./CONTRIBUTING.md) - Development guidelines  
- [Roadmap](./ROADMAP.md) - Future development plans
- [Changelog](./CHANGELOG.md) - Version history
- [GitHub Repository](https://github.com/Experto-AI/quickscale) - Source code

---

Thank you for using QuickScale! 🚀
