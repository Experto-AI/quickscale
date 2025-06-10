# **QuickScale User Guide**

Welcome to QuickScale! This guide will help you set up, use, and deploy your QuickScale project effectively.

This guide will help you to know the functionality sections and user flow of QuickScale.

---

## **1. Installation**

QuickScale requires Python 3.11+ and Docker. Follow these steps to install QuickScale:

1. **Install QuickScale**:
   ```bash
   pip install quickscale
   ```

2. **Verify Installation and Required Dependencies**:
   ```bash
   quickscale check
   ```

---

## **2. Creating a New Project**

To create a new project, use the `quickscale init` command:

1. **Initialize a Project**:
   ```bash
   quickscale init my-awesome-project
   ```

2. **Configure the Project**:
   Review and edit `.env` file with your settings:
   ```bash
   cd my-awesome-project
   # Edit .env file with your preferred editor
   ```

3. **Start the Services**:
   ```bash
   quickscale up
   ```

4. **Access the Application**:
   Open your browser and go to `http://localhost:8000` or alternate port if specified in `.env`.

---

## **3. Managing Your Project**

QuickScale provides a CLI for managing your project. Below are the most common commands:

### **3.1. Help**
- **Initialize a Project**:
  ```bash
  quickscale help
  ```

### **3.2. Stopping and Starting Services**
- **Stop Services**:
  ```bash
  quickscale down
  ```
- **Start Services (Again)**:
  ```bash
  quickscale up
  ```

### **3.3. Viewing Logs**
- **View Logs for All Services**:
  ```bash
  quickscale logs
  ```
- **View Logs for a Specific Service**:
  ```bash
  quickscale logs web
  quickscale logs db
  ```

### **3.4. Running Django Commands**
- **Run Django Management Commands**:
  ```bash
  quickscale manage <command>
  ```
  Example:
  ```bash
  quickscale manage help
  ```

### **3.5. Accessing Shells**
- **Interactive Bash Shell**:
  ```bash
  quickscale shell
  ```
- **Django Shell**:
  ```bash
  quickscale django-shell
  ```

### **3.6. AI Service Development**
- **Generate AI Service Template**:
  ```bash
  quickscale generate-service my_ai_service
  quickscale generate-service sentiment_analyzer --type text_processing
  quickscale generate-service image_classifier --type image_processing
  ```
- **Configure Service in Database**:
  ```bash
  quickscale manage configure_service my_service --credit-cost 2.0 --description "My AI service"
  ```

### **3.7. Destroying a Project**
- **Permanently Delete a Project**:
  ```bash
  quickscale destroy
  ```
  > ⚠️ **Warning**: This will delete all project files and data.

---

## **4. Starter Accounts**

QuickScale includes pre-configured accounts for testing:

- **User Account**:
  - Email: `user@test.com`
  - Password: `userpasswd`

- **Admin Account**:
  - Email: `admin@test.com`
  - Password: `adminpasswd`

---

## **5. Troubleshooting**

### **5.1. Common Issues**
- **Docker Not Running**:
  Ensure Docker is installed and running on your system.

- **Port Already in Use**:
  Stop any services using port 8000:
  ```bash
  sudo lsof -i :8000
  sudo kill <PID>
  ```

- **Environment Configuration**:
  - Review and edit `.env` file for proper configuration
  - Make sure required variables are set (check .env.example for reference)
  - For production, ensure secure values are used (not default ones)

#### **Important Environment Variables**

**Basic Configuration:**
```bash
PROJECT_NAME=your-project-name
WEB_PORT=8000
DEBUG=True  # Set to False for production
SECRET_KEY=your-secret-key  # Change for production
```

**Database Configuration:**
```bash
DB_HOST=db
DB_PORT=5432
DB_NAME=quickscale
DB_USER=admin
DB_PASSWORD=adminpasswd
```

**Email Configuration:**
```bash
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@example.com
```

**Credit System (Optional):**
```bash
CREDIT_SYSTEM_ENABLED=True
DEFAULT_CREDIT_BALANCE=0
```

**Stripe Payment Processing (Optional):**
```bash
STRIPE_ENABLED=True
STRIPE_PUBLIC_KEY=pk_test_your_key_here
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_LIVE_MODE=False  # Set to True for production
```

**Port Fallback (Optional):**
```bash
WEB_PORT_ALTERNATIVE_FALLBACK=yes
DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK=yes
```

- **Database Connection Errors**:
  - Verify your `DB_USER`, `DB_PASSWORD`, and other database settings in `.env` file
  - Check if database service is running: `quickscale ps`
  - View database logs: `quickscale logs db`
  - View web server logs: `quickscale logs web`

### **5.2. Logs**
Check logs for detailed error messages:
```bash
quickscale logs
quickscale logs web
quickscale logs db
```

### **5.3. Django Manage Commands**

QuickScale seamlessly integrates with Django's management commands through the `quickscale manage` command. This allows you to run any Django management command within your project's Docker container.

Common Django management commands:

```bash
# Database management
quickscale manage migrate           # Run database migrations
quickscale manage makemigrations    # Create new migrations based on model changes
quickscale manage sqlmigrate app_name migration_name  # SQL statements for migration

# Development server
quickscale manage runserver         # Run development server (rarely needed as Docker handles this)

# User management
quickscale manage createsuperuser   # Create a Django admin superuser
quickscale manage changepassword    # Change a user's password

# Application management
quickscale manage startapp app_name # Create a new Django app
quickscale manage shell             # Open Django interactive shell
quickscale manage dbshell           # Open database shell

# Static files
quickscale manage collectstatic     # Collect static files
quickscale manage findstatic        # Find static file locations

# Testing
quickscale manage test              # Run all tests
quickscale manage test app_name     # Run tests for specific app
quickscale manage test app.TestClass # Run tests in a specific test class
quickscale manage test app.TestClass.test_method # Run a specific test method

# Maintenance
quickscale manage clearsessions     # Clear expired sessions
quickscale manage flush             # Remove all data from database
quickscale manage dumpdata          # Export data from database
quickscale manage loaddata          # Import data to database

# Inspection
quickscale manage check             # Check for project issues
quickscale manage diffsettings      # Display differences between current settings and Django defaults
quickscale manage inspectdb         # Generate models from database
quickscale manage showmigrations    # Show migration status
```
---

## **6. Using the Web Interface**

Once your QuickScale project is running, you can access it through your web browser at `http://localhost:8000`.

### **6.1. Public Pages**

- **Home Page** (`/`): Landing page with project overview
- **About Page** (`/about/`): Information about your project
- **Contact Page** (`/contact/`): Contact form for user inquiries
- **Login Page** (`/accounts/login/`): User authentication
- **Sign Up Page** (`/accounts/signup/`): New user registration

### **6.2. User Authentication**

QuickScale uses email-based authentication:

1. **Registration**:
   - Go to `/accounts/signup/`
   - Enter your email and password (no username required)
   - Check your email for verification link
   - Click the verification link to activate your account

2. **Login**:
   - Go to `/accounts/login/`
   - Enter your email and password
   - Access your user dashboard after successful login

3. **Password Reset**:
   - Click "Forgot Password?" on the login page
   - Enter your email address
   - Check email for reset instructions

### **6.3. User Dashboard**

After logging in, users can access:

- **Profile Management** (`/users/profile/`): Update personal information
- **Account Settings**: Change password and preferences
- **Credit Dashboard** (`/admin_dashboard/`): View and manage credits (if credit system is enabled)

### **6.4. Admin Areas**

Staff users have access to additional features:

- **Admin Dashboard** (`/admin_dashboard/`): User and system management
- **Django Admin** (`/admin/`): Full administrative interface
- **User Management**: View and manage user accounts
- **Credit Management**: Handle user credits and billing (if enabled)
- **Service Management** (`/admin_dashboard/services/`): Configure and monitor application services
  - Enable/disable services in real-time
  - View service usage analytics and statistics
  - Monitor credit consumption per service
  - Track unique users and service performance
  - Bulk operations for service management

---

## **7. Credit System & Billing**

If your project has the credit system enabled, users can purchase and manage credits for service usage.

### **7.1. Understanding Credits**

- **Pay-as-you-go Credits**: Purchase credits once, use anytime (never expire)
- **Subscription Credits**: Monthly credits that expire at the end of each billing period
- **Credit Priority**: Subscription credits are used first, then pay-as-you-go credits

### **7.2. Viewing Your Credit Balance**

1. Log in to your account
2. Go to the Admin Dashboard (`/admin_dashboard/`)
3. View your current credit balance and breakdown
4. See transaction history and usage patterns

### **7.3. Purchasing Credits**

**One-time Credit Purchase:**
1. Navigate to the credit dashboard
2. Select a credit package
3. Complete payment through Stripe checkout
4. Credits are added to your account immediately

**Subscription Plans:**
1. Compare available plans (Basic vs Pro)
2. Select your preferred plan
3. Complete subscription setup through Stripe
4. Receive monthly credit allocation automatically

### **7.4. Managing Subscriptions**

- **View Current Plan**: See your active subscription details
- **Upgrade/Downgrade**: Change plans with automatic credit transfer
- **Cancel Subscription**: End recurring billing while keeping unused credits
- **Billing History**: Access payment records and receipts

### **7.5. Using Credits**

Credits are automatically consumed when using services:
- System checks available credits before allowing service access
- Usage is tracked and displayed in your dashboard
- Low balance warnings help you avoid service interruptions

---

## **8. Payment & Billing**

### **8.1. Payment Methods**

QuickScale uses Stripe for secure payment processing:
- Credit/debit cards
- Digital wallets (Apple Pay, Google Pay)
- Bank transfers (where available)

### **8.2. Receipts and Invoices**

- Automatic receipt generation for all payments
- Downloadable receipts with unique reference numbers
- Complete payment history accessible in your dashboard
- Monthly invoices for subscription payments

### **8.3. Payment Issues**

If you experience payment problems:
1. Check your payment method is valid and has sufficient funds
2. Verify billing address information
3. Contact support through the contact form
4. Check your email for payment failure notifications

---

## **9. AI Service Development Guide**

QuickScale includes a comprehensive AI service framework that allows AI engineers to quickly create and deploy AI services with automatic credit consumption and billing.

### **9.1. Getting Started with AI Services**

**Generate Your First Service:**
```bash
# Basic AI service
quickscale generate-service my_first_service

# Text processing service (sentiment analysis, summarization, etc.)
quickscale generate-service text_analyzer --type text_processing

# Image processing service (classification, analysis, etc.)
quickscale generate-service image_processor --type image_processing
```

**Configure Service in Database:**
```bash
# Configure service with credit cost
quickscale manage configure_service my_first_service --credit-cost 1.0 --description "My first AI service"

# List all configured services
quickscale manage configure_service --list

# Update existing service
quickscale manage configure_service my_first_service --update --credit-cost 2.0
```

### **9.2. Service Development Workflow**

1. **Generate Template**: Use `quickscale generate-service` to create service boilerplate
2. **Implement Logic**: Add your AI processing logic to the `execute_service` method
3. **Configure Database**: Set credit costs and activate the service
4. **Test Service**: Use the generated example files to test your implementation
5. **Deploy**: Service automatically integrates with credit system and admin interface

### **9.3. Example Service Structure**

```python
@register_service("my_service_name")
class MyAIService(BaseService):
    """Your AI service description."""
    
    def execute_service(self, user: User, **kwargs) -> Dict[str, Any]:
        """Implement your AI logic here."""
        # 1. Validate inputs
        input_data = kwargs.get('input_data')
        if not input_data:
            raise ValueError("input_data is required")
        
        # 2. Process with your AI model/API
        result = your_ai_processing_function(input_data)
        
        # 3. Return structured results
        return {
            'status': 'completed',
            'result': result,
            'metadata': {
                'service_name': 'my_service_name',
                'processing_time': '50ms'
            }
        }
```

### **9.4. Service Integration Features**

- **Automatic Credit Consumption**: Credits automatically deducted when service is used
- **Usage Tracking**: Complete audit trail of service usage
- **Admin Interface**: Real-time service management through admin dashboard
- **API Integration**: Services automatically available via API endpoints
- **Error Handling**: Consistent error patterns and validation
- **Documentation**: Auto-generated usage examples and documentation

### **9.5. Available Example Services**

QuickScale includes several example services that demonstrate best practices:

- **Text Sentiment Analysis**: Analyze sentiment with confidence scoring
- **Keyword Extraction**: Extract important keywords from text
- **Image Metadata Extraction**: Extract metadata from image files
- **Data Validation**: Validate different data formats (text, email, JSON)

For complete documentation, see the generated `docs/service_development_guide.md` in your project.

---

## **10. Running Codebase Tests**

QuickScale includes a comprehensive test suite to ensure functionality works as expected.

First, install the test dependencies:

```bash
pip install -r requirements-test.txt
```

The simplest way to run tests is using the `run_tests.sh` script:

```bash
# Run all tests (default)
./run_tests.sh

# Run unit tests
./run_tests.sh -u

# Run integration tests
./run_tests.sh -i

# Run end to end tests
./run_tests.sh -e

# Run with coverage report
./run_tests.sh --coverage
```

For Django application tests, you can use the Django test runner through the QuickScale CLI:

```bash
# Run all Django tests
quickscale manage test
```

---

## **11. Advanced CLI Features**

### **11.1. Shell Commands**

**Interactive Shell:**
```bash
quickscale shell
```

**Run Single Command:**
```bash
quickscale shell -c "ls -la"
```

### **11.2. Enhanced Logging**

**View logs with timestamps:**
```bash
quickscale logs -t
```

**Follow logs continuously:**
```bash
quickscale logs -f
```

**View logs from specific time:**
```bash
quickscale logs --since 30m
quickscale logs --since 2h
```

**Limit log lines:**
```bash
quickscale logs --lines 50
```

**Service-specific logs:**
```bash
quickscale logs web -t --lines 100
quickscale logs db --since 1h
```

### **11.3. Service Status**

Check running services:
```bash
quickscale ps
```

### **11.4. Automatic Port Fallback**

QuickScale can automatically find and use alternative ports if the default `WEB_PORT` (8000) or `DB_PORT_EXTERNAL` (5432) are already in use on your system. This feature is controlled by environment variables in your project's `.env` file:

- `WEB_PORT_ALTERNATIVE_FALLBACK`: Set to `yes` to enable automatic fallback for the web server port.
- `DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK`: Set to `yes` to enable automatic fallback for the PostgreSQL database external port.

If fallback is enabled and a port conflict is detected when you run `quickscale up`, QuickScale will attempt to find an available port in a nearby range. The new port will be displayed in the console output.

If fallback is disabled (default) and a port conflict occurs, `quickscale up` will fail with a clear error message instructing you to free the port, specify a different port manually, or enable the fallback feature.

## **12. Additional Resources**

- [Technical Documentation](./TECHNICAL_DOCS.md)
- [Contributing Guide](./CONTRIBUTING.md)
- [Roadmap](./ROADMAP.md)
- [Changelog](./CHANGELOG.md)
- [HomePage](https://github.com/Experto-AI/quickscale)
- Other documentation links:
  - [CREDIT_SYSTEM.md](./docs/CREDIT_SYSTEM.md) Credit System Documentation.
  - [DATABASE_VARIABLES.md](./docs/DATABASE_VARIABLES.md) Database Environment Variables. 
  - [MESSAGE_MANAGER.md](./docs/MESSAGE_MANAGER.md) Message Manager Utility.
  
---

Thank you for using QuickScale! 🚀
