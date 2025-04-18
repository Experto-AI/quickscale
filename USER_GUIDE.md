# **QuickScale User Guide**

Welcome to QuickScale! This guide will help you set up, use, and deploy your QuickScale project effectively.

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

To create a new project, use the `quickscale build` command:

1. **Build a Project**:
   ```bash
   quickscale build my-awesome-project
   ```

2. **Access the Application**:
   Open your browser and go to `http://localhost:8000`.

   NOTE: It is not necessary to execute `quickscale up`

---

## **3. Managing Your Project**

QuickScale provides a CLI for managing your project. Below are the most common commands:

### **3.1. Navigate to the Project Directory**:
   ```bash
   cd my-awesome-project
   ```

### **3.2. Starting and Stopping Services**
- **Start Services**:
  ```bash
  quickscale up
  ```
- **Stop Services**:
  ```bash
  quickscale down
  ```

### **3.3. Viewing Logs**
- **View Logs for All Services**:
  ```bash
  quickscale logs
  ```
- **View Logs for a Specific Service**:
  ```bash
  quickscale logs web
  ```

### **3.4. Running Django Commands**
- **Run Django Management Commands**:
  ```bash
  quickscale manage <command>
  ```
  Example:
  ```bash
  quickscale manage test
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

### **3.6. Destroying a Project**
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

## **5. Customizing Your Project**

### **5.1. Updating Templates**
QuickScale templates are located in the `templates/` directory. You can customize them to match your branding.

### **5.2. Adding New Apps**
To add a new Django app:
1. Run:
   ```bash
   quickscale manage startapp <app_name>
   ```
2. Add the app to `INSTALLED_APPS` in `core/settings.py`.

---

## **6. Deployment**

QuickScale uses Docker for deployment. Follow these steps to deploy your project:

1. **Set Up Environment Variables**:
   Update the `.env` file with production settings.

2. **Build and Start Services**:
   ```bash
   docker-compose up --build -d
   ```

3. **Run Database Migrations**:
   ```bash
   quickscale manage migrate
   ```

4. **Collect Static Files**:
   ```bash
   quickscale manage collectstatic
   ```

5. **Access the Application**:
   Open your browser and go to your server's IP or domain.

---

## **7. Troubleshooting**

### **7.1. Common Issues**
- **Docker Not Running**:
  Ensure Docker is installed and running on your system.

- **Port Already in Use**:
  Stop any services using port 8000:
  ```bash
  sudo lsof -i :8000
  sudo kill <PID>
  ```

- **Database Connection Errors**:
  Verify your `DATABASE_URL` in the `.env` file.

### **7.2. Logs**
Check logs for detailed error messages:
```bash
quickscale logs
```

### **7.3. Django Manage Commands**

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

### **7.4. Running Codebase Tests**

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

# Run edn to end tests
./run_tests.sh -e

# Run with coverage report
./run_tests.sh --coverage
```

For Django application tests, you can use the Django test runner through the QuickScale CLI:

```bash
# Run all Django tests
quickscale manage test
```

## **8. Additional Resources**

- [Technical Documentation](./TECHNICAL_DOCS.md)
- [Contributing Guide](./CONTRIBUTING.md)
- [Roadmap](./ROADMAP.md)
- [Changelog](./CHANGELOG.md)
- [HomePage](https://github.com/Experto-AI/quickscale)

---

Thank you for using QuickScale! 🚀
