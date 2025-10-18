# Railway Deployment Guide

## Overview

Railway.app is a modern platform-as-a-service (PaaS) that simplifies deploying Django applications with PostgreSQL databases. QuickScale-generated projects work seamlessly with Railway's infrastructure.

## Prerequisites

- Railway account ([railway.app](https://railway.app))
- Railway CLI installed (`npm install -g @railway/cli`)
- QuickScale project generated via `quickscale init`
- Git repository for your project

## Quick Start

```bash
# 1. Generate QuickScale project
quickscale init myapp
cd myapp

# 2. Initialize Railway project
railway init

# 3. Add PostgreSQL database
railway add

# 4. Configure environment variables
railway variables set SECRET_KEY=your-secret-key
railway variables set ALLOWED_HOSTS=myapp.railway.app
railway variables set DEBUG=False

# 5. Deploy
railway up
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (generate a secure random string) | `django-insecure-...` |
| `DATABASE_URL` | PostgreSQL connection (auto-provided by Railway) | `postgresql://...` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `myapp.railway.app` |
| `DEBUG` | Debug mode (always False in production) | `False` |
| `DJANGO_SETTINGS_MODULE` | Django settings module | `myapp.settings.production` |

### Optional Configuration

- `RAILWAY_ENVIRONMENT` - Detected automatically by Railway
- `PORT` - Auto-assigned by Railway (default: 8000)

## Database Setup

Railway automatically provisions PostgreSQL and provides the `DATABASE_URL` environment variable. QuickScale's generated settings are pre-configured to use this.

## Static Files

QuickScale uses WhiteNoise for static file serving, which works out-of-the-box on Railway without additional CDN configuration.

## Deployment Options

### Option 1: Docker Deployment (Recommended)

Railway auto-detects the `Dockerfile` in QuickScale projects and builds using Docker.

**Benefits**:
- Exact production environment matching local development
- Full control over dependencies and build process
- Consistent across all deployment platforms

### Option 2: Nixpacks Deployment

Railway can auto-detect Django projects and build using Nixpacks.

**Benefits**:
- Faster builds
- Automatic dependency detection
- Simpler configuration

### Option 3: Using `railway.json`

Add an optional `railway.json` to customize deployment:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## CI/CD Integration

Railway can deploy automatically from GitHub:

1. Connect your GitHub repository in Railway dashboard
2. Configure branch-based deployments (e.g., `main` → production)
3. Every push to main triggers automatic deployment
4. Use GitHub Actions for testing before Railway deployment

## Troubleshooting

### Common Issues

**Database Connection Errors**:
- Verify `DATABASE_URL` environment variable is set
- Check Railway PostgreSQL service is running
- Review connection logs in Railway dashboard

**Static Files Not Loading**:
- Run `python manage.py collectstatic` during build
- Verify WhiteNoise is in `MIDDLEWARE` settings
- Check `STATIC_ROOT` configuration

**502 Bad Gateway**:
- Verify application is listening on Railway's `PORT` env var
- Check application logs for startup errors
- Ensure Gunicorn is configured correctly

**Build Failures**:
- Check `Dockerfile` syntax
- Verify all dependencies in `pyproject.toml`
- Review Railway build logs for specific errors

## Deployment Checklist

- [ ] Generate project: `quickscale init myapp`
- [ ] Initialize git repository
- [ ] Create Railway project
- [ ] Add PostgreSQL database
- [ ] Configure environment variables
- [ ] Deploy to Railway
- [ ] Run database migrations
- [ ] Create superuser account
- [ ] Verify site is accessible
- [ ] Test all critical functionality
- [ ] Configure custom domain (optional)
- [ ] Set up monitoring and alerts

## Real-World Validation

Railway deployment will be validated as part of v0.60.0 development. The deployment workflow and troubleshooting guide will be updated with real-world experience.

## Additional Resources

- [Railway Documentation](https://docs.railway.app/)
- [Railway Django Template](https://railway.app/template/django)
- [Railway CLI Reference](https://docs.railway.app/develop/cli)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)

## Deployment Helper Script

QuickScale projects include a deployment helper script:

```bash
./scripts/deploy_railway.sh
```

This script:
- Validates environment variables are set
- Runs database migrations
- Collects static files
- Provides deployment checklist
- Tests database connectivity

## Next Steps

After successful deployment:

1. **Monitor Application**: Use Railway's built-in logging and metrics
2. **Set Up Custom Domain**: Configure DNS and SSL certificates
3. **Enable Backups**: Configure automated PostgreSQL backups
4. **Scale Resources**: Adjust Railway resources based on traffic
5. **CI/CD Pipeline**: Automate deployments with GitHub Actions

## Support

For Railway-specific issues:
- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Railway Documentation: [docs.railway.app](https://docs.railway.app)

For QuickScale deployment questions:
- GitHub Issues: Check project documentation for support links
- User Manual: [user_manual.md](../technical/user_manual.md)

---

**Note**: This guide is based on QuickScale's generated project structure and Railway's best practices. The workflow has been validated with QuickScale-generated projects.
