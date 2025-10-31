# QuickScale Auth Module

**Version**: 0.63.0
**Status**: ✅ Production Ready

Production-ready authentication module for QuickScale projects using django-allauth with custom User model patterns.

## Features

### ✅ Implemented (v0.63.0)

- **django-allauth Integration**: Email/password authentication
- **Custom User Model**: Extends Django's AbstractUser with custom fields support
- **Authentication Views**: Login, logout, signup, password management
- **Account Management**: Profile view/edit, account deletion
- **HTML Theme**: Complete template set with responsive design
- **Form Validation**: Client-side and server-side validation
- **Security**: CSRF protection, password strength indicators
- **Signals**: Post-registration hooks for custom logic

### 🚧 Coming Soon

- **Email Verification** (v0.64.0): Production email workflows
- **Social Providers** (Post-MVP): Google, GitHub, Facebook authentication
- **HTMX Theme** (v0.67.0): HTMX + Alpine.js theme variant
- **React Theme** (v0.68.0): React + TypeScript SPA theme variant

## Installation

### 1. Embed the Module

```bash
quickscale embed --module auth
```

The embed command will:
- Ask interactive configuration questions
- Copy module files to `modules/auth/`
- Automatically configure settings and URLs
- Run initial migrations

### 2. Manual Configuration (if needed)

If you need to manually configure the module:

#### Add to INSTALLED_APPS in `settings.py`:

```python
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # Required by allauth

    # Third-party apps
    "allauth",
    "allauth.account",

    # QuickScale modules
    "quickscale_modules_auth",

    # Your apps
    # ...
]
```

#### Configure django-allauth in `settings.py`:

```python
# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Custom user model
AUTH_USER_MODEL = "quickscale_modules_auth.User"

# Site ID (required by django.contrib.sites)
SITE_ID = 1

# Allauth settings
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "none"  # "mandatory" or "optional" in v0.64.0
ACCOUNT_ALLOW_REGISTRATION = True  # Set to False to disable signups
ACCOUNT_ADAPTER = "quickscale_modules_auth.adapters.QuickscaleAccountAdapter"
ACCOUNT_SIGNUP_FORM_CLASS = "quickscale_modules_auth.forms.SignupForm"
LOGIN_REDIRECT_URL = "/accounts/profile/"
LOGOUT_REDIRECT_URL = "/"

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks
```

#### Include auth URLs in your project's `urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("quickscale_modules_auth.urls")),  # Auth URLs
    # Your other URLs
]
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

## Usage

### Available URLs

After embedding the module, these URLs are available:

- `/accounts/login/` - Login page
- `/accounts/signup/` - Registration page
- `/accounts/logout/` - Logout confirmation
- `/accounts/password/change/` - Change password
- `/accounts/password/reset/` - Request password reset
- `/accounts/profile/` - View profile
- `/accounts/profile/edit/` - Edit profile
- `/accounts/account/delete/` - Delete account

### Template Customization

All templates extend `quickscale_modules_auth/base.html`. To customize:

1. **Override the base template** in your project:
   ```
   templates/quickscale_modules_auth/base.html
   ```

2. **Override individual templates**:
   ```
   templates/quickscale_modules_auth/account/login.html
   templates/quickscale_modules_auth/account/signup.html
   ```

3. **Add custom CSS/JS**:
   ```
   static/quickscale_modules_auth/css/custom.css
   static/quickscale_modules_auth/js/custom.js
   ```

### Custom User Fields

To add custom fields to the User model:

1. **Edit** `modules/auth/models.py`:
   ```python
   class User(AbstractUser):
       # Add custom fields
       phone = models.CharField(max_length=20, blank=True)
       bio = models.TextField(blank=True)
   ```

2. **Create migration**:
   ```bash
   python manage.py makemigrations quickscale_modules_auth
   python manage.py migrate
   ```

3. **Update forms** to include new fields in `modules/auth/forms.py`

### Signal Handlers

The module provides a post-registration signal handler in `signals.py`. Customize it to add your own logic:

```python
@receiver(user_signed_up)
def on_user_signed_up(sender, request, user, **kwargs):
    # Send welcome email
    send_welcome_email(user.email)

    # Create user profile
    UserProfile.objects.create(user=user)

    # Log registration
    logger.info(f"New user registered: {user.username}")
```

## Configuration Options

### Enable/Disable Registration

```python
# In settings.py
ACCOUNT_ALLOW_REGISTRATION = False  # Disable signups
```

### Change Authentication Method

```python
# Use email only (no username)
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USERNAME_REQUIRED = False

# Use username only
ACCOUNT_AUTHENTICATION_METHOD = "username"
ACCOUNT_EMAIL_REQUIRED = False

# Use both (default)
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USERNAME_REQUIRED = True
```

### Session Timeout

```python
SESSION_COOKIE_AGE = 86400  # 1 day in seconds
SESSION_SAVE_EVERY_REQUEST = True  # Extend session on activity
```

## Testing

Run module tests:

```bash
cd modules/auth
pytest
```

With coverage:

```bash
pytest --cov=src/quickscale_modules_auth --cov-report=html
```

## Troubleshooting

### Issue: "No such table: quickscale_auth_user"

**Solution**: Run migrations:
```bash
python manage.py migrate quickscale_modules_auth
```

### Issue: "AUTH_USER_MODEL refers to model that has not been installed"

**Solution**: Add `quickscale_modules_auth` to INSTALLED_APPS before running migrations.

### Issue: Login redirects to /accounts/profile/ but page doesn't exist

**Solution**: Either create a profile view or set a different LOGIN_REDIRECT_URL:
```python
LOGIN_REDIRECT_URL = "/"  # Redirect to home page instead
```

### Issue: Templates not found

**Solution**: Ensure `quickscale_modules_auth` is in INSTALLED_APPS and collectstatic has been run:
```bash
python manage.py collectstatic
```

## Module Distribution

This module uses **git subtree** distribution:

- **Development**: `quickscale_modules/auth/` on main branch
- **Distribution**: `splits/auth-module` branch
- **User embedding**: `quickscale embed --module auth`
- **Updates**: `quickscale update`

## Contributing

To contribute improvements:

```bash
# Make changes in modules/auth/
git add modules/auth/
git commit -m "feat(auth): your improvement"

# Push back to QuickScale (if you have access)
quickscale push --module auth

# Or create a pull request with your changes
```

## Dependencies

- Django >= 4.2, < 6.0
- django-allauth ^0.63.0

## Documentation

- [django-allauth Documentation](https://django-allauth.readthedocs.io/)
- [QuickScale User Manual](../../docs/technical/user_manual.md)
- [QuickScale Roadmap](../../docs/technical/roadmap.md)

## License

MIT License - Same as QuickScale project

## Support

- **Issues**: [GitHub Issues](https://github.com/Experto-AI/quickscale/issues)
- **Docs**: [QuickScale Documentation](../../docs/)
- **Community**: Coming in Post-MVP phases

---

**Note**: This module is production-ready for basic authentication. Email verification and social providers coming in v0.64.0 and later releases.
