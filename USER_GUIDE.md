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

2. **Navigate to the Project Directory**:
   ```bash
   cd my-awesome-project
   ```

3. **Access the Application**:
   Open your browser and go to `http://localhost:8000`.

---

## **3. Managing Your Project**

QuickScale provides a CLI for managing your project. Below are the most common commands:

### **3.1. Starting and Stopping Services**
- **Start Services**:
  ```bash
  quickscale up
  ```
- **Stop Services**:
  ```bash
  quickscale down
  ```

### **3.2. Viewing Logs**
- **View Logs for All Services**:
  ```bash
  quickscale logs
  ```
- **View Logs for a Specific Service**:
  ```bash
  quickscale logs web
  ```

### **3.3. Running Django Commands**
- **Run Django Management Commands**:
  ```bash
  quickscale manage <command>
  ```
  Example:
  ```bash
  quickscale manage createsuperuser
  ```

### **3.4. Accessing Shells**
- **Interactive Bash Shell**:
  ```bash
  quickscale shell
  ```
- **Django Shell**:
  ```bash
  quickscale django-shell
  ```

### **3.5. Destroying a Project**
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

---

## **8. Additional Resources**

- [Technical Documentation](./TECHNICAL_DOCS.md)
- [Contributing Guide](./CONTRIBUTING.md)
- [Roadmap](./ROADMAP.md)
- [Changelog](./CHANGELOG.md)
- [HomePage](https://github.com/Experto-AI/quickscale)

---

Thank you for using QuickScale! 🚀
