# QuickScale Auth Module

Production-ready standalone authentication module for QuickScale projects using django-allauth,
with a custom user model and organization-aware account flows.

## Overview

- django-allauth integration for email/password authentication.
- Custom `User` model extending Django's `AbstractUser`, ready for custom fields.
- Authentication views: login, logout, signup, and password management.
- Account management: profile view/edit and account deletion.
- Responsive account templates and client-side plus server-side form validation.
- Security: CSRF protection and password strength indicators.
- A post-registration signal receiver for project-specific logic.
- A declarative `module.yml` manifest with mutable and immutable options.

`orgs` is required alongside `auth`: it supplies the account adapter that extends this module's
adapter with organization-aware post-login redirects, the tenant middleware, and the
`QUICKSCALE_MODE` runtime mode. Dependencies: Django 6.0+ and django-allauth
`>=65.18.0,<66.0.0`.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

### Mutable options

Mutable options can be changed at any time with `quickscale apply`.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `registration_enabled` | boolean | `true` | `ACCOUNT_ALLOW_REGISTRATION` | Allow new user signups. |
| `email_verification` | string | `none` | `ACCOUNT_EMAIL_VERIFICATION` | Email verification requirement: `none`, `optional`, or `mandatory`. |
| `session_cookie_age` | integer | `1209600` | `SESSION_COOKIE_AGE` | Session cookie lifetime in seconds (default: 2 weeks). |

```yaml
modules:
  auth:
    registration_enabled: false  # Disable signups
    session_cookie_age: 86400    # 1 day session
```

```bash
quickscale apply
```

### Immutable options

Immutable options are set when the module is first added and cannot be changed in place.
Changing one requires removing the module configuration and adding it again with the new
values:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `authentication_method` | string | `email` | How users authenticate: `email`, `username`, or `both`. |

```bash
quickscale remove auth
# Update quickscale.yml with the new immutable options
quickscale apply
```

### allauth settings

The generated settings render the options above into the django-allauth configuration
(65.x format):

```python
AUTH_USER_MODEL = "quickscale_auth.User"
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ALLOW_REGISTRATION = True
ACCOUNT_ADAPTER = "quickscale_modules_orgs.adapters.OrgsAccountAdapter"
ACCOUNT_SIGNUP_FORM_CLASS = "quickscale_modules_auth.forms.SignupForm"
LOGIN_REDIRECT_URL = "/accounts/profile/"
LOGOUT_REDIRECT_URL = "/"
QUICKSCALE_MODE = "solo"  # or "saas"
```

`ACCOUNT_LOGIN_METHODS` and `ACCOUNT_SIGNUP_FIELDS` follow `authentication_method`:

```python
# username only
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]

# both
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
```

Session handling:

```python
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True  # Extend session on activity
```

## Public surface

- `User` model (`quickscale_auth.User`) extending `AbstractUser`; `AUTH_USER_MODEL` points at
  it.
- `SignupForm` in `forms.py`, wired through `ACCOUNT_SIGNUP_FORM_CLASS`.
- Account templates under `templates/quickscale_auth/` (with allauth overrides under
  `templates/account/`) extending `quickscale_auth/base.html`.
- Static assets under `static/quickscale_modules_auth/{css,js}/`.
- Account flows: login, logout, signup, password change and reset, profile view/edit, and
  account deletion.
- `receivers.py` connects a `user_signed_up` receiver from `ready()` as the post-registration
  hook; `signals.py` is reserved for signals the module sends.
- `allauth_adapter.py` holds the module's allauth account adapter; orgs' adapter subclasses it
  so the installed pair keeps organization-aware redirects.

## URLs

The module mounts under `accounts/`, alongside django-allauth's own routes:

| Path | Source | Purpose |
|------|--------|---------|
| `accounts/login/` | django-allauth | Login page |
| `accounts/signup/` | django-allauth | Registration page |
| `accounts/logout/` | django-allauth | Logout confirmation |
| `accounts/password/change/` | django-allauth | Change password |
| `accounts/password/reset/` | django-allauth | Request password reset |
| `accounts/profile/` (`quickscale_auth:profile`) | Module | View profile |
| `accounts/profile/edit/` (`quickscale_auth:profile-edit`) | Module | Edit profile |
| `accounts/account/delete/` (`quickscale_auth:account-delete`) | Module | Delete account |

## Management commands

This module ships no management commands.

## Operations

Add the module through QuickScale:

```bash
quickscale plan myapp --add auth
cd myapp
quickscale apply
```

`quickscale apply` embeds the module into `modules/auth/`, configures settings, middleware, and
URLs, and runs the initial migrations.

A manual installation adds `allauth`, `allauth.account`, `django.contrib.sites`,
`quickscale_modules_auth`, and `quickscale_modules_orgs` to `INSTALLED_APPS`; adds
`allauth.account.middleware.AccountMiddleware` and
`quickscale_modules_orgs.middleware.TenantMiddleware` to `MIDDLEWARE`; applies the settings
block above; and includes the URLs:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("quickscale_modules_auth.urls")),
    # Required alongside auth. In solo mode keep this include before your
    # home route; in saas mode place it after the home route.
    path("", include("quickscale_modules_orgs.urls")),
]
```

Run migrations through the privileged one-shot command; orgs refuses a superuser or BYPASSRLS
database connection otherwise:

```bash
QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" python manage.py migrate
```

Serve under a restricted role (NOSUPERUSER, NOBYPASSRLS). The `QUICKSCALE_ALLOW_BYPASSRLS=1`
opt-in is for non-serving single-tenant development and tests, never serving; see the
[Launcher One-Shot Command-Env Contract](../../docs/technical/decisions.md#launcher-one-shot-command-env-contract).

Optionally create a superuser with `python manage.py createsuperuser`.

### Template customization

All account templates extend `quickscale_auth/base.html`. Override the base template at
`templates/quickscale_auth/base.html`, individual pages at
`templates/quickscale_auth/account/<page>.html`, and add custom assets under
`static/quickscale_modules_auth/css/` or `js/`.

### Troubleshooting

- **"No such table: quickscale_auth_user"** — run `python manage.py migrate quickscale_auth`.
- **"AUTH_USER_MODEL refers to model that has not been installed"** — add
  `quickscale_modules_auth` to `INSTALLED_APPS` before running migrations.
- **Login redirects to `/accounts/profile/` but the page does not exist** — set a different
  `LOGIN_REDIRECT_URL`.
- **Templates not found** — ensure `quickscale_modules_auth` is in `INSTALLED_APPS` and run
  `python manage.py collectstatic`.

## Extending

- **Custom user fields**: add fields to `User` in `modules/auth/models.py`, run
  `python manage.py makemigrations quickscale_auth && python manage.py migrate`, and update
  `forms.py` to include them.
- **Registration hooks**: extend the `user_signed_up` receiver in `receivers.py` to add
  welcome emails, profiles, or logging.
- **Social providers**: provider integrations are not part of the current shipped
  configuration contract.
- **Distribution and updates**: modules are distributed through the git-subtree workflow;
  update an embedded module with `quickscale update`.
- **Development**: module tests run from the maintainer repository root, for example
  `make MODULE=auth test -- --modules`; run `poetry run pytest` inside the module directory for
  a standalone checkout.
- **Documentation**: [django-allauth documentation](https://django-allauth.readthedocs.io/),
  [QuickScale user manual](../../docs/technical/user_manual.md), and
  [QuickScale roadmap](../../docs/technical/roadmap.md).
- **Support**: [GitHub Issues](https://github.com/Experto-AI/quickscale/issues) and the
  [QuickScale documentation](https://github.com/Experto-AI/quickscale/tree/main/docs).
- Licensed under the Apache 2.0 License, same as the QuickScale project.
