# QuickScale Auth Module

**Status**: ✅ Production Ready

Production-ready standalone authentication module for QuickScale projects using django-allauth with custom User model patterns.

## Features

### ✅ Implemented

- **django-allauth Integration**: Email/password authentication
- **Custom User Model**: Extends Django's AbstractUser with custom fields support
- **Authentication Views**: Login, logout, signup, password management
- **Account Management**: Profile view/edit, account deletion
- **Modern HTML Theme**: Beautiful, responsive design with gradients and animations
- **Module Navigation**: Dynamic navigation showing installed/uninstalled modules
- **Form Validation**: Client-side and server-side validation
- **Security**: CSRF protection, password strength indicators
- **Signals**: Post-registration hooks for custom logic
- **Module Manifest**: Declarative config with mutable/immutable options

## Module Manifest

The auth module includes a `module.yml` manifest that defines configuration options:

### Mutable Options (can be changed anytime with `quickscale apply`)

| Option | Django Setting | Default | Description |
|--------|---------------|---------|-------------|
| `registration_enabled` | `ACCOUNT_ALLOW_REGISTRATION` | `true` | Allow new user signups |
| `email_verification` | `ACCOUNT_EMAIL_VERIFICATION` | `none` | Email verification mode |
| `session_cookie_age` | `SESSION_COOKIE_AGE` | `1209600` | Session timeout in seconds |

### Immutable Options (set when the module is first added, cannot be changed)

| Option | Default | Description |
|--------|---------|-------------|
| `authentication_method` | `email` | How users authenticate (email, username, or both) |

### Changing Configuration

**Mutable options** can be changed in `quickscale.yml` and applied:

```yaml
modules:
  auth:
    options:
      registration_enabled: false  # Disable signups
      session_cookie_age: 86400    # 1 day session
```

```bash
quickscale apply
```

**Immutable options** require removing the module configuration and adding it again with the new values:

```bash
quickscale remove auth
# Update quickscale.yml with new immutable options
quickscale apply
```

## Navigation & Module Integration

The auth module includes dynamic navigation that shows all available QuickScale modules:

- **Installed modules**: Displayed as clickable links with icons
- **Uninstalled modules**: Shown as disabled/grayed out with "Not installed" indicator
- **Automatic detection**: Uses QuickScale's module configuration system
- **Responsive design**: Navigation adapts to mobile screens

Current documented navigation entry:
- 👤 **Authentication** - Current module (always enabled when installed)

Additional cross-module links should only be documented here once the corresponding shipped integration is part of the auth surface.

### 🚧 Still Evolving

- **Email verification workflows**: Stronger production email flows may continue to evolve
- **Social provider integrations**: Google, GitHub, and similar integrations remain future-facing and are not part of the current shipped configuration contract
- **Additional theme variants**: HTML and React-specific auth experiences may expand over time

## Installation

### 1. Add the Module

```bash
quickscale plan myapp --add auth
cd myapp
quickscale apply
```

This workflow will:
- Add the auth module to your project configuration
- Embed module files into `modules/auth/` during `quickscale apply`
- Automatically configure settings and URLs
- Run initial migrations as part of apply

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

# Allauth settings (django-allauth 65.x format)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # Set to "mandatory" or "optional" as needed
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
    path("accounts/", include("allauth.urls")),
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
# Use email only (default) - django-allauth 65.x format
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]

# Use username only
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]

# Use both (optional alternative)
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
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
- **Project configuration**: `quickscale plan myapp --add auth` followed by `quickscale apply`
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

- Django 6.0+
- django-allauth 65.14+

## Documentation

- [django-allauth Documentation](https://django-allauth.readthedocs.io/)
- [QuickScale User Manual](https://github.com/Experto-AI/quickscale/blob/main/docs/technical/user_manual.md)
- [QuickScale Roadmap](https://github.com/Experto-AI/quickscale/blob/main/docs/technical/roadmap.md)

## License

Apache 2.0 License - Same as QuickScale project

## Support

- **Issues**: [GitHub Issues](https://github.com/Experto-AI/quickscale/issues)
- **Docs**: [QuickScale Documentation](https://github.com/Experto-AI/quickscale/tree/main/docs)
- **Release updates**: Follow the main QuickScale docs and tagged release notes for current support surface changes

---

**Note**: This module is production-ready for basic authentication. Advanced capabilities such as email verification and future social provider integrations may continue to evolve in later releases.
