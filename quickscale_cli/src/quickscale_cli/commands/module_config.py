"""Module configuration functions for QuickScale modules.

This module contains configuration functions for individual QuickScale modules,
including interactive configuration prompts and settings application.
"""

import re
import subprocess
from pathlib import Path
from typing import Any

import click


def has_migrations_been_run() -> bool:
    """Check if Django migrations have been run in the current project"""
    # Check for SQLite database file
    if Path("db.sqlite3").exists():
        return True

    # Check for PostgreSQL database by running Django check
    try:
        result = subprocess.run(
            ["python", "manage.py", "showmigrations", "--plan"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # If we can run showmigrations and see any [X] marks, migrations have been applied
        if result.returncode == 0 and "[X]" in result.stdout:
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return False


# ============================================================================
# AUTH MODULE CONFIGURATION
# ============================================================================


def get_default_auth_config() -> dict[str, Any]:
    """Get default configuration for auth module (non-interactive mode)"""
    return {
        "allow_registration": True,
        "email_verification": "none",
        "authentication_method": "email",
    }


def configure_auth_module(non_interactive: bool = False) -> dict[str, Any]:
    """Interactive configuration for auth module"""
    if non_interactive:
        click.echo("\n⚙️  Using default auth module configuration...")
        config = get_default_auth_config()
        click.echo("  • Registration: Enabled")
        click.echo(f"  • Email verification: {config['email_verification']}")
        click.echo(f"  • Authentication: {config['authentication_method']}")
        return config

    click.echo("\n⚙️  Configuring auth module...")
    click.echo("Answer these questions to customize the authentication setup:\n")

    config = {
        "allow_registration": click.confirm("Enable user registration?", default=True),
        "email_verification": click.prompt(
            "Email verification",
            type=click.Choice(["none", "optional", "mandatory"], case_sensitive=False),
            default="none",
            show_choices=True,
        ),
        "authentication_method": click.prompt(
            "Authentication method",
            type=click.Choice(["email", "username", "both"], case_sensitive=False),
            default="email",
            show_choices=True,
        ),
    }

    return config


def _add_django_allauth_dependency(project_path: Path, pyproject_path: Path) -> None:
    """Add django-allauth dependency to project's pyproject.toml."""
    with open(pyproject_path) as f:
        pyproject_content = f.read()

    if "django-allauth" in pyproject_content:
        return

    # Read django-allauth version from the embedded auth module
    auth_pyproject_path = project_path / "modules" / "auth" / "pyproject.toml"

    if not auth_pyproject_path.exists():
        click.secho(
            "❌ Error: Auth module pyproject.toml not found. "
            "Cannot determine django-allauth version requirement.",
            fg="red",
            err=True,
        )
        click.echo(f"Expected file: {auth_pyproject_path}", err=True)
        click.echo(
            "This indicates the auth module was not embedded correctly.",
            err=True,
        )
        raise click.Abort()

    # Extract django-allauth version using regex
    try:
        with open(auth_pyproject_path) as f:
            auth_pyproject_content = f.read()

        version_match = re.search(
            r'django-allauth\s*=\s*["\']([^"\']+)["\']', auth_pyproject_content
        )
        if not version_match:
            click.secho(
                "❌ Error: Cannot find django-allauth version in auth module's "
                "pyproject.toml",
                fg="red",
                err=True,
            )
            click.echo(f"File: {auth_pyproject_path}", err=True)
            click.echo('Expected format: django-allauth = "^x.x.x"', err=True)
            click.echo("Please check the auth module's dependencies.", err=True)
            raise click.Abort()
        django_allauth_version = version_match.group(1)
    except (FileNotFoundError, AttributeError) as e:
        click.secho(
            f"❌ Error: Failed to parse django-allauth version from auth module: {e}",
            fg="red",
            err=True,
        )
        click.echo(f"File: {auth_pyproject_path}", err=True)
        click.echo(
            "Please ensure the auth module is properly embedded and its "
            "pyproject.toml is valid.",
            err=True,
        )
        raise click.Abort()

    # Try to add to [tool.poetry.dependencies] section
    dependencies_pattern = r"(\[tool\.poetry\.dependencies\][^\[]*)"
    match = re.search(dependencies_pattern, pyproject_content, re.DOTALL)
    if match:
        dependencies_section = match.group(1)
        # Add django-allauth after the python version line
        updated_dependencies = re.sub(
            r'(python = "[^"]*")',
            rf'\1\ndjango-allauth = "{django_allauth_version}"',
            dependencies_section,
        )
        pyproject_content = pyproject_content.replace(
            dependencies_section, updated_dependencies
        )

        with open(pyproject_path, "w") as f:
            f.write(pyproject_content)

        click.secho("  ✅ Added django-allauth to pyproject.toml", fg="green")
    else:
        click.secho(
            "⚠️  Warning: Could not find [tool.poetry.dependencies] section in "
            "pyproject.toml",
            fg="yellow",
        )


def _generate_auth_settings_addition(config: dict[str, Any]) -> str:
    """Generate the settings addition string for auth module."""
    settings_addition = """
# QuickScale Auth Module - Added by quickscale embed
INSTALLED_APPS += [
    "django.contrib.sites",  # Required by allauth
    "quickscale_modules_auth",  # Must be before allauth.account for template overrides
    "allauth",
    "allauth.account",
]

# Allauth Middleware (must be added to MIDDLEWARE)
MIDDLEWARE += [
    "allauth.account.middleware.AccountMiddleware",
]

# Authentication Configuration
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Custom User Model
AUTH_USER_MODEL = "quickscale_modules_auth.User"

# Site ID (required by django.contrib.sites)
SITE_ID = 1

# Allauth Settings
"""

    # Add configuration based on user choices (using new django-allauth 0.62+ format)
    if config["authentication_method"] == "email":
        settings_addition += 'ACCOUNT_LOGIN_METHODS = {"email"}\n'
        settings_addition += (
            'ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]\n'
        )
    elif config["authentication_method"] == "username":
        settings_addition += 'ACCOUNT_LOGIN_METHODS = {"username"}\n'
        settings_addition += (
            'ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]\n'
        )
    else:  # both
        settings_addition += 'ACCOUNT_LOGIN_METHODS = {"email", "username"}\n'
        settings_addition += 'ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]\n'

    settings_addition += (
        f'ACCOUNT_EMAIL_VERIFICATION = "{config["email_verification"]}"\n'
    )
    settings_addition += (
        f"ACCOUNT_ALLOW_REGISTRATION = {config['allow_registration']}\n"
    )
    settings_addition += 'ACCOUNT_ADAPTER = "quickscale_modules_auth.adapters.QuickscaleAccountAdapter"\n'
    settings_addition += (
        'ACCOUNT_SIGNUP_FORM_CLASS = "quickscale_modules_auth.forms.SignupForm"\n'
    )
    settings_addition += 'LOGIN_REDIRECT_URL = "/accounts/profile/"\n'
    settings_addition += 'LOGOUT_REDIRECT_URL = "/"\n'
    settings_addition += "SESSION_COOKIE_AGE = 1209600  # 2 weeks\n"

    return settings_addition


def apply_auth_configuration(project_path: Path, config: dict[str, Any]) -> None:
    """Apply auth module configuration to project settings"""
    # QuickScale uses settings/base.py and project_name/urls.py structure
    settings_path = project_path / f"{project_path.name}" / "settings" / "base.py"
    urls_path = project_path / f"{project_path.name}" / "urls.py"
    pyproject_path = project_path / "pyproject.toml"

    if not settings_path.exists():
        click.secho(
            "⚠️  Warning: settings.py not found, skipping auto-configuration",
            fg="yellow",
        )
        return

    # Read settings.py
    with open(settings_path) as f:
        settings_content = f.read()

    # Check if already configured
    if "quickscale_modules_auth" in settings_content:
        click.echo("ℹ️  Auth module already configured in settings.py")
        return

    # Add django-allauth dependency to pyproject.toml
    if pyproject_path.exists():
        _add_django_allauth_dependency(project_path, pyproject_path)

    # Generate settings addition
    installed_apps_addition = _generate_auth_settings_addition(config)

    # Append to settings.py
    with open(settings_path, "a") as f:
        f.write("\n" + installed_apps_addition)

    click.secho("  ✅ Updated settings.py with auth configuration", fg="green")

    # Update urls.py
    if urls_path.exists():
        with open(urls_path) as f:
            urls_content = f.read()

        if "allauth" not in urls_content:
            # Find urlpatterns and add auth URLs
            if "urlpatterns = [" in urls_content:
                urls_addition = (
                    '    path("accounts/", include("allauth.urls")),\n'
                    '    path("accounts/", include("quickscale_modules_auth.urls")),  # Auth URLs\n'
                )
                urls_content = urls_content.replace(
                    "urlpatterns = [", "urlpatterns = [\n" + urls_addition
                )

                with open(urls_path, "w") as f:
                    f.write(urls_content)

                click.secho("  ✅ Updated urls.py with auth URLs", fg="green")

    # Show configuration summary
    click.echo("\n📋 Configuration applied:")
    click.echo(
        f"  • Registration: {'Enabled' if config['allow_registration'] else 'Disabled'}"
    )
    click.echo(f"  • Email verification: {config['email_verification']}")
    click.echo(f"  • Authentication: {config['authentication_method']}")


# ============================================================================
# BLOG MODULE CONFIGURATION
# ============================================================================


def get_default_blog_config() -> dict[str, Any]:
    """Get default configuration for blog module (non-interactive mode)"""
    return {
        "posts_per_page": 10,
        "enable_rss": True,
    }


def configure_blog_module(non_interactive: bool = False) -> dict[str, Any]:
    """Interactive configuration for blog module"""
    if non_interactive:
        click.echo("\n⚙️  Using default blog module configuration...")
        config = get_default_blog_config()
        click.echo(f"  • Posts per page: {config['posts_per_page']}")
        click.echo("  • RSS feed: Enabled")
        return config

    click.echo("\n⚙️  Configuring blog module...")
    click.echo("The blog module will be configured with default settings.\n")

    config = {
        "posts_per_page": click.prompt(
            "Posts per page",
            type=int,
            default=10,
        ),
        "enable_rss": click.confirm("Enable RSS feed?", default=True),
    }

    return config


def apply_blog_configuration(project_path: Path, config: dict[str, Any]) -> None:
    """Apply blog module configuration to project settings"""
    # QuickScale uses settings/base.py and project_name/urls.py structure
    settings_path = project_path / f"{project_path.name}" / "settings" / "base.py"
    urls_path = project_path / f"{project_path.name}" / "urls.py"

    if not settings_path.exists():
        click.secho(
            "⚠️  Warning: settings.py not found, skipping auto-configuration",
            fg="yellow",
        )
        return

    # Read settings.py
    with open(settings_path) as f:
        settings_content = f.read()

    # Check if already configured
    if "quickscale_modules_blog" in settings_content:
        click.echo("ℹ️  Blog module already configured in settings.py")
        return

    # Add required apps to INSTALLED_APPS
    installed_apps_addition = """
# QuickScale Blog Module - Added by quickscale embed
INSTALLED_APPS += [
    "markdownx",  # Markdown editor with image upload
    "quickscale_modules_blog",  # Blog module
]

# Blog Module Settings
"""

    installed_apps_addition += f"BLOG_POSTS_PER_PAGE = {config['posts_per_page']}\n"
    installed_apps_addition += """MARKDOWNX_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
]
MARKDOWNX_MEDIA_PATH = "blog/markdownx/"
"""

    # Append to settings.py
    with open(settings_path, "a") as f:
        f.write("\n" + installed_apps_addition)

    click.secho("  ✅ Updated settings.py with blog configuration", fg="green")

    # Update urls.py
    if urls_path.exists():
        with open(urls_path) as f:
            urls_content = f.read()

        if "quickscale_modules_blog" not in urls_content:
            # Find urlpatterns and add blog URLs
            if "urlpatterns = [" in urls_content:
                urls_addition = (
                    '    path("blog/", include("quickscale_modules_blog.urls")),\n'
                )
                if config["enable_rss"]:
                    urls_addition += '    path("markdownx/", include("markdownx.urls")),  # Markdown editor upload\n'
                urls_content = urls_content.replace(
                    "urlpatterns = [", "urlpatterns = [\n" + urls_addition
                )

                with open(urls_path, "w") as f:
                    f.write(urls_content)

                click.secho("  ✅ Updated urls.py with blog URLs", fg="green")

    # Show configuration summary
    click.echo("\n📋 Configuration applied:")
    click.echo(f"  • Posts per page: {config['posts_per_page']}")
    click.echo(f"  • RSS feed: {'Enabled' if config['enable_rss'] else 'Disabled'}")


# ============================================================================
# LISTINGS MODULE CONFIGURATION
# ============================================================================


def get_default_listings_config() -> dict[str, Any]:
    """Get default configuration for listings module (non-interactive mode)"""
    return {
        "listings_per_page": 12,
    }


def configure_listings_module(non_interactive: bool = False) -> dict[str, Any]:
    """Interactive configuration for listings module"""
    if non_interactive:
        click.echo("\n⚙️  Using default listings module configuration...")
        config = get_default_listings_config()
        click.echo(f"  • Listings per page: {config['listings_per_page']}")
        return config

    click.echo("\n⚙️  Configuring listings module...")
    click.echo(
        "The listings module provides an abstract base model for marketplace listings.\n"
    )

    config = {
        "listings_per_page": click.prompt(
            "Listings per page",
            type=int,
            default=12,
        ),
    }

    return config


def _add_django_filter_dependency(project_path: Path, pyproject_path: Path) -> None:
    """Add django-filter dependency to project's pyproject.toml."""
    with open(pyproject_path) as f:
        pyproject_content = f.read()

    if "django-filter" in pyproject_content:
        return

    # Read django-filter version from the embedded listings module
    listings_pyproject_path = project_path / "modules" / "listings" / "pyproject.toml"

    if not listings_pyproject_path.exists():
        click.secho(
            "❌ Error: Listings module pyproject.toml not found. "
            "Cannot determine django-filter version requirement.",
            fg="red",
            err=True,
        )
        click.echo(f"Expected file: {listings_pyproject_path}", err=True)
        click.echo(
            "This indicates the listings module was not embedded correctly.",
            err=True,
        )
        raise click.Abort()

    # Extract django-filter version using regex
    try:
        with open(listings_pyproject_path) as f:
            listings_pyproject_content = f.read()

        version_match = re.search(
            r'django-filter\s*=\s*["\']([^"\']+)["\']',
            listings_pyproject_content,
        )
        if not version_match:
            click.secho(
                "❌ Error: Cannot find django-filter version in listings "
                "module's pyproject.toml",
                fg="red",
                err=True,
            )
            click.echo(f"File: {listings_pyproject_path}", err=True)
            click.echo('Expected format: django-filter = "^x.x.x"', err=True)
            click.echo("Please check the listings module's dependencies.", err=True)
            raise click.Abort()
        django_filter_version = version_match.group(1)
    except (FileNotFoundError, AttributeError) as e:
        click.secho(
            f"❌ Error: Failed to parse django-filter version from listings "
            f"module: {e}",
            fg="red",
            err=True,
        )
        click.echo(f"File: {listings_pyproject_path}", err=True)
        click.echo(
            "Please ensure the listings module is properly embedded and its "
            "pyproject.toml is valid.",
            err=True,
        )
        raise click.Abort()

    # Try to add to [tool.poetry.dependencies] section
    dependencies_pattern = r"(\[tool\.poetry\.dependencies\][^\[]*)"
    match = re.search(dependencies_pattern, pyproject_content, re.DOTALL)
    if match:
        dependencies_section = match.group(1)
        # Add django-filter after the python version line
        updated_dependencies = re.sub(
            r'(python = "[^"]*")',
            rf'\1\ndjango-filter = "{django_filter_version}"',
            dependencies_section,
        )
        pyproject_content = pyproject_content.replace(
            dependencies_section, updated_dependencies
        )

        with open(pyproject_path, "w") as f:
            f.write(pyproject_content)

        click.secho("  ✅ Added django-filter to pyproject.toml", fg="green")
    else:
        click.secho(
            "⚠️  Warning: Could not find [tool.poetry.dependencies] section in "
            "pyproject.toml",
            fg="yellow",
        )


def apply_listings_configuration(project_path: Path, config: dict[str, Any]) -> None:
    """Apply listings module configuration to project settings"""
    # QuickScale uses settings/base.py and project_name/urls.py structure
    settings_path = project_path / f"{project_path.name}" / "settings" / "base.py"
    urls_path = project_path / f"{project_path.name}" / "urls.py"
    pyproject_path = project_path / "pyproject.toml"

    if not settings_path.exists():
        click.secho(
            "⚠️  Warning: settings.py not found, skipping auto-configuration",
            fg="yellow",
        )
        return

    # Read settings.py
    with open(settings_path) as f:
        settings_content = f.read()

    # Check if already configured
    if "quickscale_modules_listings" in settings_content:
        click.echo("ℹ️  Listings module already configured in settings.py")
        return

    # Add django-filter dependency to pyproject.toml
    if pyproject_path.exists():
        _add_django_filter_dependency(project_path, pyproject_path)

    # Add required apps to INSTALLED_APPS
    installed_apps_addition = """
# QuickScale Listings Module - Added by quickscale embed
INSTALLED_APPS += [
    "django_filters",  # Filtering support
    "quickscale_modules_listings",  # Listings module
]

# Listings Module Settings
"""

    installed_apps_addition += f"LISTINGS_PER_PAGE = {config['listings_per_page']}\n"

    # Append to settings.py
    with open(settings_path, "a") as f:
        f.write("\n" + installed_apps_addition)

    click.secho("  ✅ Updated settings.py with listings configuration", fg="green")

    # Update urls.py
    if urls_path.exists():
        with open(urls_path) as f:
            urls_content = f.read()

        if "quickscale_modules_listings" not in urls_content:
            # Find urlpatterns and add listings URLs
            if "urlpatterns = [" in urls_content:
                urls_addition = '    path("listings/", include("quickscale_modules_listings.urls")),\n'
                urls_content = urls_content.replace(
                    "urlpatterns = [", "urlpatterns = [\n" + urls_addition
                )

                with open(urls_path, "w") as f:
                    f.write(urls_content)

                click.secho("  ✅ Updated urls.py with listings URLs", fg="green")

    # Show configuration summary
    click.echo("\n📋 Configuration applied:")
    click.echo(f"  • Listings per page: {config['listings_per_page']}")


# ============================================================================
# MODULE CONFIGURATORS REGISTRY
# ============================================================================

MODULE_CONFIGURATORS = {
    "auth": (configure_auth_module, apply_auth_configuration),
    "blog": (configure_blog_module, apply_blog_configuration),
    "listings": (configure_listings_module, apply_listings_configuration),
}
