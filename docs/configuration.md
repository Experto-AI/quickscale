# Configuration Guide

## Environment Variables

QuickScale uses environment variables for configuration, following the twelve-factor app methodology. Configuration is managed through `.env` files and environment-specific settings.

## Database Configuration

### Standardization on DB_* Variables

QuickScale uses a standardized approach to database configuration through `DB_*` environment variables.

#### The Problem (Solved)
Previously, there was duplication between:
1. `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Django naming convention
2. `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - PostgreSQL Docker variables

#### The Solution
QuickScale now standardizes on `DB_*` variables for Django settings while mapping to `POSTGRES_*` variables for Docker:

```bash
# Database Configuration (Primary)
DB_NAME=quickscale_db
DB_USER=quickscale_user  
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# These are automatically mapped for Docker PostgreSQL
POSTGRES_DB=${DB_NAME}
POSTGRES_USER=${DB_USER}
POSTGRES_PASSWORD=${DB_PASSWORD}
```

#### Benefits
- **Consistency**: Single source of truth for database settings
- **DRY Principle**: No duplication of configuration values
- **Docker Compatibility**: Automatic mapping to PostgreSQL container variables
- **Maintainability**: Easier configuration management

### Database URLs
Alternative configuration using database URLs:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

## Core Application Settings

### Basic Configuration
```bash
# Project Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Application URLs
SITE_URL=http://localhost:8000
SITE_NAME=Your SaaS App

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# For production:
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-email@gmail.com
# EMAIL_HOST_PASSWORD=your-app-password
```

### Security Settings
```bash
# CSRF and Security
CSRF_TRUSTED_ORIGINS=http://localhost:8000,https://yourdomain.com
SECURE_SSL_REDIRECT=False  # Set to True in production
SESSION_COOKIE_SECURE=False  # Set to True in production with HTTPS
CSRF_COOKIE_SECURE=False  # Set to True in production with HTTPS
```

## Stripe Configuration

### API Keys
```bash
# Stripe Settings
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Stripe Environment
STRIPE_LIVE_MODE=False  # Set to True for production
```

### Webhook Configuration
```bash
# Webhook Endpoint (automatically configured)
# https://yourdomain.com/stripe/webhook/

# Required Webhook Events:
# - payment_intent.succeeded
# - invoice.payment_succeeded  
# - customer.subscription.updated
# - customer.subscription.deleted
```

## Authentication Settings

### Email-Only Authentication
```bash
# Disable username requirement
ACCOUNT_USER_MODEL_USERNAME_FIELD=None
ACCOUNT_EMAIL_REQUIRED=True
ACCOUNT_USERNAME_REQUIRED=False
ACCOUNT_AUTHENTICATION_METHOD=email

# Email verification
ACCOUNT_EMAIL_VERIFICATION=mandatory
ACCOUNT_CONFIRM_EMAIL_ON_GET=True
```

### Social Authentication (Optional)
```bash
# Google OAuth (optional)
GOOGLE_OAUTH_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-client-secret

# GitHub OAuth (optional)  
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

## Redis Configuration (Optional)

### Cache Settings
```bash
# Redis for caching and sessions
REDIS_URL=redis://localhost:6379/0

# Cache backend
CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
CACHE_LOCATION=redis://localhost:6379/1

# Session backend
SESSION_ENGINE=django.contrib.sessions.backends.cache
SESSION_CACHE_ALIAS=default
```

## Logging Configuration

### Development Logging
```bash
# Logging Level
LOG_LEVEL=DEBUG

# Log to console in development
LOGGING_HANDLER=console
```

### Production Logging
```bash
# Production logging settings
LOG_LEVEL=INFO
LOGGING_HANDLER=file

# Log file location
LOG_FILE=/var/log/quickscale/app.log

# Structured logging
LOGGING_FORMAT=json
```

## File Storage Configuration

### Local Development
```bash
# Static and media files
STATIC_URL=/static/
MEDIA_URL=/media/
STATIC_ROOT=/app/staticfiles/
MEDIA_ROOT=/app/media/
```

### Production Storage
```bash
# AWS S3 Configuration (optional)
USE_S3=True
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=your-bucket-name.s3.amazonaws.com
```

## API Configuration

### Rate Limiting
```bash
# API rate limits
API_RATE_LIMIT_PER_MINUTE=60
API_RATE_LIMIT_PER_HOUR=3600
API_RATE_LIMIT_PER_DAY=86400
```

### CORS Settings
```bash
# CORS configuration for API access
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
CORS_ALLOW_CREDENTIALS=True
```

## Monitoring and Analytics

### Error Tracking
```bash
# Sentry for error tracking (optional)
SENTRY_DSN=https://your-sentry-dsn
SENTRY_ENVIRONMENT=development

# Health checks
HEALTH_CHECK_TOKEN=your-health-check-token
```

### Performance Monitoring
```bash
# Performance monitoring
ENABLE_PROFILING=False
PROFILING_SAMPLE_RATE=0.01

# Database query logging
LOG_DB_QUERIES=False  # Only in development
```

## Environment-Specific Configurations

### Development (.env.development)
```bash
DEBUG=True
LOG_LEVEL=DEBUG
STRIPE_LIVE_MODE=False
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SECURE_SSL_REDIRECT=False
```

### Staging (.env.staging)
```bash
DEBUG=False
LOG_LEVEL=INFO
STRIPE_LIVE_MODE=False
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SECURE_SSL_REDIRECT=True
```

### Production (.env.production)
```bash
DEBUG=False
LOG_LEVEL=WARNING
STRIPE_LIVE_MODE=True
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## Configuration Validation

### Environment Validation
QuickScale includes configuration validation on startup:

```python
# Automatic validation checks
def validate_configuration():
    required_vars = [
        'SECRET_KEY',
        'DB_NAME',
        'STRIPE_SECRET_KEY',
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ConfigurationError(f"Missing required environment variables: {missing_vars}")
```

### Health Checks
```bash
# Check configuration health
quickscale health

# Validate environment
quickscale config validate

# Show current configuration (sanitized)
quickscale config show
```

## Docker Configuration

### Docker Compose Environment
```yaml
version: '3.8'
services:
  web:
    environment:
      - DB_HOST=postgres
      - REDIS_URL=redis://redis:6379/0
      
  postgres:
    environment:
      - POSTGRES_DB=${DB_NAME}
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      
  redis:
    command: redis-server --appendonly yes
```

### Production Deployment
```bash
# Environment variable precedence:
# 1. OS environment variables
# 2. .env file
# 3. Default values

# Use Docker secrets for sensitive data
docker secret create db_password /path/to/password/file
```

## Security Best Practices

### Secret Management
- **Never commit secrets**: Use `.env` files with `.gitignore`
- **Rotate regularly**: Change secrets periodically
- **Use secret managers**: AWS Secrets Manager, HashiCorp Vault for production
- **Principle of least privilege**: Minimal required permissions

### Configuration Security
- **Validate inputs**: Check configuration values on startup
- **Sanitize outputs**: Never log sensitive configuration
- **Use strong defaults**: Secure default values where possible
- **Environment separation**: Different secrets per environment

This configuration system provides secure, flexible, and maintainable settings management for QuickScale applications across all deployment environments.
