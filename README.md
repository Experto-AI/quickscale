# **🚀 Quick-Scale**  


**A SaaS starter kit for AI Engineers and Python-first developers using Django**  

Quick-Scale is designed to help **AI Engineers, Data Scientists, and Backend/Cloud developers** launch SaaS applications **quickly and efficiently**. 

It is a project generator that provides a **ready-to-use** Django-based framework with best practices for **scalability, authentication, billing, and deployment**—so you can focus on building your product, not setting up infrastructure.  

👉 **Go from idea to paying customers with minimal setup.**  

Ideal for **solo developers** or small teams looking to turn their ideas into production-ready SaaS solutions **with minimal effort**.  

## GET STARTED 🔥 - LAUNCH QUICKLY 🚀

1.  Install: `pip install quickscale`
2.  Create project: `quickscale init awesome-project`
3.  Configure: Review and edit `.env` file with your settings
    - To set your project name (used in About and other pages), add `PROJECT_NAME=YourAppName` to your `.env` file.
4.  Start: `quickscale up`
5.  Access: `http://localhost:8000`

## KEY FEATURES

- **Complete SaaS Foundation**: Authentication, user management, and **Stripe** billing integration (**in progress**)
- **Ready-to-Use Pages**: Landing, dashboard, login, signup, profile, and more
- **Modern Frontend**: HTMX and Alpine.js for dynamic interactions without complex JavaScript
- **Containerized**: Docker setup for consistent development and deployment
- **Command-Line Control**: Intuitive CLI for managing your project lifecycle
- **Starter Accounts**: Pre-configured user and admin accounts for immediate testing
- **Fail-Fast Port Validation**: Clear error messages when ports are in use, requiring explicit configuration


## PROJECT USAGE

QuickScale provides a convenient command-line interface to manage your projects:

```
Available commands:
  init           - Initialize a new QuickScale project
  up             - Start the project services
  down           - Stop the project services
  logs           - View project logs (optional service parameter: web, db)
  manage         - Run Django management commands
  check          - Check project status and requirements
  ps             - Show the status of running services
  shell          - Enter an interactive bash shell in the web container
  django-shell   - Enter the Django shell in the web container
  destroy        - Permanently destroy the current project (Warning deletes all code; by default keeps Docker images)
  help           - Show this help message
  version        - Show the current version of QuickScale
```

Examples:
```bash
quickscale init awesome-project   # Create a new project called "awesome-project"
quickscale up                     # Start the services
quickscale logs web               # View logs from the web service
quickscale shell                  # Enter an interactive bash shell in the web container
quickscale django-shell           # Enter the Django shell in the web container
quickscale down                   # Stop the services
quickscale destroy                # Destroy project, containers, and volumes (keeps Docker images for fast rebuild)
quickscale destroy --delete-images # Destroy project, containers, volumes, and Docker images (slower rebuild)
```

## STARTER PAGES

- Public: 
  - Home: Landing page
  - Login: User authentication
  - Register: New user registration
  - Contact: Contact form
  - About: Project information
  - Navigation Bar: Site navigation
- User Private: 
  - Dashboard: User dashboard ("My Dashboard")
  - Profile: User profile management
  - Settings: User settings
- Admin Private: 
  - Dashboard: Admin dashboard for staff users
  - Profile: Admin profile
  - Settings: System settings
  - Users CRUD: User management

## STARTER DATABASE

QuickScale automatically creates default test accounts for immediate use:

- **User Account**: 
  - Email: `user@test.com`
  - Password: `userpasswd`
  - Access: User dashboard and features

- **Administrator Account**: 
  - Email: `admin@test.com`
  - Password: `adminpasswd`
  - Access: Admin dashboard, user management, and all features

**Note**: These accounts are created automatically when you run `quickscale up` for the first time. If you encounter login issues, ensure you're using the exact email addresses and passwords shown above.

## DOCUMENTATION

- [User Guide](./USER_GUIDE.md) - How to use QuickScale, including setup and deployment instructions
- [Technical Documentation](./TECHNICAL_DOCS.md) - Technical stack, project structure, and development details
- [Contributing Guide](./CONTRIBUTING.md) - How to contribute to QuickScale. 
  Also it is a template for AI codding assistants to generate code for the project.
  Cursor, Windsurf and GitHub Coplitot rules are linked to this file.
- [Roadmap](./ROADMAP.md) - Future plans and features for QuickScale
- [Changelog](./CHANGELOG.md) - Release notes and version history
- [HomePage](https://github.com/Experto-AI/quickscale)
- Other documentation links:
  - [CREDIT_SYSTEM.md](./docs/CREDIT_SYSTEM.md) Credit System Documentation.
  - [DATABASE_VARIABLES.md](./docs/DATABASE_VARIABLES.md) Database Environment Variables. 
  - [MESSAGE_MANAGER.md](./docs/MESSAGE_MANAGER.md) Message Manager Utility.
