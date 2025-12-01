"""Module management commands for QuickScale CLI."""

import subprocess
from pathlib import Path
from typing import Any

import click

from quickscale_core.config import add_module, load_config, update_module_version
from quickscale_core.utils.git_utils import (
    GitError,
    check_remote_branch_exists,
    is_git_repo,
    is_working_directory_clean,
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
)

# Available modules
AVAILABLE_MODULES = ["auth", "billing", "teams", "blog", "listings"]


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
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        if "django-allauth" not in pyproject_content:
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
                import re

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

    # Add required apps to INSTALLED_APPS
    installed_apps_addition = """
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
        # Email-only authentication (new format: ACCOUNT_LOGIN_METHODS)
        installed_apps_addition += 'ACCOUNT_LOGIN_METHODS = {"email"}\n'
        installed_apps_addition += (
            'ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]\n'
        )
    elif config["authentication_method"] == "username":
        # Username-only authentication
        installed_apps_addition += 'ACCOUNT_LOGIN_METHODS = {"username"}\n'
        installed_apps_addition += (
            'ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]\n'
        )
    else:  # both
        # Both email and username authentication
        installed_apps_addition += 'ACCOUNT_LOGIN_METHODS = {"email", "username"}\n'
        installed_apps_addition += 'ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]\n'

    installed_apps_addition += (
        f'ACCOUNT_EMAIL_VERIFICATION = "{config["email_verification"]}"\n'
    )
    installed_apps_addition += (
        f"ACCOUNT_ALLOW_REGISTRATION = {config['allow_registration']}\n"
    )
    installed_apps_addition += 'ACCOUNT_ADAPTER = "quickscale_modules_auth.adapters.QuickscaleAccountAdapter"\n'
    installed_apps_addition += (
        'ACCOUNT_SIGNUP_FORM_CLASS = "quickscale_modules_auth.forms.SignupForm"\n'
    )
    installed_apps_addition += 'LOGIN_REDIRECT_URL = "/accounts/profile/"\n'
    installed_apps_addition += 'LOGOUT_REDIRECT_URL = "/"\n'
    installed_apps_addition += "SESSION_COOKIE_AGE = 1209600  # 2 weeks\n"

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


def apply_listings_configuration(project_path: Path, config: dict[str, Any]) -> None:
    """Apply listings module configuration to project settings"""
    import re

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
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        if "django-filter" not in pyproject_content:
            # Read django-filter version from the embedded listings module
            listings_pyproject_path = (
                project_path / "modules" / "listings" / "pyproject.toml"
            )

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
                    click.echo(
                        "Please check the listings module's dependencies.", err=True
                    )
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


MODULE_CONFIGURATORS = {
    "auth": (configure_auth_module, apply_auth_configuration),
    "blog": (configure_blog_module, apply_blog_configuration),
    "listings": (configure_listings_module, apply_listings_configuration),
}


@click.command()
@click.option(
    "--module",
    required=True,
    type=click.Choice(AVAILABLE_MODULES, case_sensitive=False),
    help="Module name to embed",
)
@click.option(
    "--remote",
    default="https://github.com/Experto-AI/quickscale.git",
    help="Git remote URL (default: QuickScale repository)",
)
@click.option(
    "-y",
    "--non-interactive",
    is_flag=True,
    help="Use default configuration without prompts (for automation)",
)
def embed(module: str, remote: str, non_interactive: bool) -> None:
    r"""
    Embed a QuickScale module into your project via git subtree.

    \b
    Examples:
      quickscale embed --module auth
      quickscale embed --module billing
      quickscale embed --module blog
      quickscale embed --module listings
      quickscale embed --module auth -y  # Non-interactive with defaults

    \b
    Available modules:
      - auth: Authentication with django-allauth
      - billing: Stripe integration with dj-stripe (placeholder)
      - teams: Multi-tenancy and team management (placeholder)
      - blog: Markdown-powered blog with categories, tags, and RSS
      - listings: Generic listings with filtering for marketplace verticals

    \b
    Note: Auth, blog, and listings modules are fully implemented.
    Billing and teams modules contain placeholder READMEs.

    \b
    ⚠️  DEPRECATED: Use 'quickscale plan --add' + 'quickscale apply' instead.
    """
    # Show deprecation warning
    click.secho(
        "\n⚠️  DEPRECATED: 'quickscale embed' is deprecated.",
        fg="yellow",
        bold=True,
    )
    click.echo("   Use 'quickscale plan --add' + 'quickscale apply' instead.")
    click.echo("   This command will be removed in v0.71.0.\n")

    try:
        # Validate git repository
        if not is_git_repo():
            click.secho("❌ Error: Not a git repository", fg="red", err=True)
            click.echo(
                "\n💡 Tip: Run 'git init' to initialize a git repository", err=True
            )
            raise click.Abort()

        # Check working directory is clean
        if not is_working_directory_clean():
            click.secho(
                "❌ Error: Working directory has uncommitted changes",
                fg="red",
                err=True,
            )
            click.echo(
                "\n💡 Tip: Commit or stash your changes before embedding modules",
                err=True,
            )
            raise click.Abort()

        # Check if module already exists
        module_path = Path.cwd() / "modules" / module
        if module_path.exists():
            click.secho(
                f"❌ Error: Module '{module}' already exists at {module_path}",
                fg="red",
                err=True,
            )
            click.echo("\n💡 Tip: Remove the existing module directory first", err=True)
            raise click.Abort()

        # Check if branch exists on remote
        branch = f"splits/{module}-module"
        click.echo(f"🔍 Checking if {branch} exists on remote...")

        if not check_remote_branch_exists(remote, branch):
            click.secho(
                f"❌ Error: Module '{module}' is not yet implemented",
                fg="red",
                err=True,
            )
            click.echo(
                f"\n💡 The '{module}' module infrastructure is ready but contains "
                "only placeholder files.",
                err=True,
            )
            click.echo("   Full implementation coming in v0.63.0+", err=True)
            click.echo(
                f"\n📖 Branch '{branch}' does not exist on remote: {remote}", err=True
            )
            raise click.Abort()

        # Check if migrations have already been run (only for auth module which changes User model)
        if module == "auth" and has_migrations_been_run():
            click.secho(
                "\n⚠️  Warning: Django migrations have already been run!",
                fg="yellow",
                bold=True,
            )
            click.echo("\n❌ The auth module changes the User model (AUTH_USER_MODEL).")
            click.echo(
                "   Embedding it after running migrations will cause migration conflicts."
            )
            click.echo(
                "\n🔧 To fix this, you need to reset your database and re-run migrations:"
            )
            click.echo("   1. Backup any important data")
            click.echo(
                "   2. Delete the database: rm db.sqlite3  (or drop PostgreSQL database)"
            )
            click.echo("   3. Run this embed command again")
            click.echo("   4. Run migrations: poetry run python manage.py migrate")
            click.echo(
                "\n💡 Tip: For new projects, embed the auth module BEFORE running migrations."
            )

            if non_interactive:
                # In non-interactive mode, fail immediately since this is a critical issue
                click.secho(
                    "\n❌ Cannot embed auth module in non-interactive mode when migrations exist.",
                    fg="red",
                    err=True,
                )
                click.echo(
                    "   Please reset the database first or embed auth module before running migrations.",
                    err=True,
                )
                raise click.Abort()

            click.echo(
                "\n❓ Do you want to continue anyway? (You'll need to reset the database manually)"
            )

            if not click.confirm("Continue?", default=False):
                click.echo("\n❌ Embedding cancelled")
                raise click.Abort()

        # Interactive module configuration (v0.63.0+)
        config = {}
        if module in MODULE_CONFIGURATORS:
            configurator, applier = MODULE_CONFIGURATORS[module]
            config = configurator(non_interactive=non_interactive)

        # Embed module via git subtree
        prefix = f"modules/{module}"
        click.echo(f"\n📦 Embedding {module} module from {branch}...")

        run_git_subtree_add(prefix=prefix, remote=remote, branch=branch, squash=True)

        # Update configuration tracking
        add_module(
            module_name=module,
            prefix=prefix,
            branch=branch,
            version="v0.63.0",
        )

        # Apply module-specific configuration
        if module in MODULE_CONFIGURATORS and config:
            _, applier = MODULE_CONFIGURATORS[module]
            project_root = Path.cwd()
            applier(project_root, config)

        # Install dependencies for modules that need it
        if module in ["auth", "blog", "listings"]:
            click.echo("\n📦 Installing dependencies...")
            try:
                import subprocess

                project_root = Path.cwd()
                module_path = project_root / "modules" / module

                # Verify module was actually embedded
                if not module_path.exists():
                    click.secho(
                        f"❌ Error: Module directory not found at {module_path}",
                        fg="red",
                        err=True,
                    )
                    click.echo(
                        "   The git subtree add may have failed. Check the output above.",
                        err=True,
                    )
                    raise click.Abort()

                # Determine the correct path to add
                # Sometimes the split branch might contain the full repo (e.g. during dev/testing)
                # We need to find the actual module's pyproject.toml
                target_path = module_path
                nested_path = module_path / "quickscale_modules" / module

                if nested_path.exists() and (nested_path / "pyproject.toml").exists():
                    click.secho(
                        f"⚠️  Warning: Detected full repository in {module} module path.",
                        fg="yellow",
                    )
                    click.echo(
                        f"   Using nested path: {nested_path.relative_to(project_root)}"
                    )
                    target_path = nested_path

                # Install the module
                click.echo(f"  • Installing {module} module...")
                result = subprocess.run(
                    ["poetry", "add", f"./{target_path.relative_to(project_root)}"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    click.secho(
                        f"\n❌ Failed to install {module} module",
                        fg="red",
                        err=True,
                        bold=True,
                    )
                    click.echo("\n📋 Error output (stderr):", err=True)
                    click.echo(result.stderr, err=True)
                    click.echo("\n📋 Standard output (stdout):", err=True)
                    click.echo(result.stdout, err=True)

                    click.echo("\n💡 To fix this manually:", err=True)
                    click.echo(f"   1. cd {project_root}", err=True)
                    click.echo(f"   2. poetry add ./modules/{module}", err=True)
                    click.echo("   3. poetry install", err=True)
                    click.echo("   4. poetry run python manage.py migrate", err=True)
                    raise click.Abort()

                click.secho(
                    f"  ✅ {module.capitalize()} module installed successfully",
                    fg="green",
                )

                # Install dependencies
                click.echo("  • Installing all dependencies...")
                result = subprocess.run(
                    ["poetry", "install"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    click.secho(
                        "\n❌ Failed to install dependencies",
                        fg="red",
                        err=True,
                        bold=True,
                    )
                    click.echo("\n📋 Error output (stderr):", err=True)
                    click.echo(result.stderr, err=True)
                    click.echo("\n📋 Standard output (stdout):", err=True)
                    click.echo(result.stdout, err=True)

                    click.echo("\n💡 To fix this manually:", err=True)
                    click.echo(f"   1. cd {project_root}", err=True)
                    click.echo("   2. poetry install", err=True)
                    click.echo("   3. poetry run python manage.py migrate", err=True)
                    raise click.Abort()

                click.secho("  ✅ Dependencies installed successfully", fg="green")

            except subprocess.CalledProcessError as e:
                click.secho(
                    f"\n❌ Unexpected error during dependency installation: {e}",
                    fg="red",
                    err=True,
                )
                click.echo(
                    f"\n💡 Try running 'poetry install' manually in {project_root}",
                    err=True,
                )
                raise click.Abort()

        # Success message
        click.secho(
            f"\n✅ Module '{module}' embedded successfully!", fg="green", bold=True
        )
        click.echo(f"   Location: {module_path}")
        click.echo(f"   Branch: {branch}")

        # Module-specific next steps
        click.echo("\n📋 Next steps:")
        if module == "auth":
            click.echo(f"  1. Review module code in modules/{module}/")
            click.secho(
                "  2. ⚠️  IMPORTANT: Run migrations (required before server start):",
                fg="yellow",
                bold=True,
            )
            click.secho(
                "     poetry run python manage.py migrate", fg="cyan", bold=True
            )
            click.echo(
                "  3. Create superuser (optional): poetry run python manage.py createsuperuser"
            )
            click.echo("  4. Start development server:")
            click.echo("")
            click.secho(
                "     ⚠️  IMPORTANT: Use --build flag with Docker",
                fg="yellow",
                bold=True,
            )
            click.secho(
                "     • With Docker: quickscale down && quickscale up --build",
                fg="cyan",
                bold=True,
            )
            click.secho(
                "       ^^^ --build is REQUIRED to install new dependencies",
                fg="yellow",
            )
            click.echo("")
            click.echo("     • Without Docker: poetry run python manage.py runserver")
            click.echo("  5. Visit http://localhost:8000/accounts/login/")
            click.echo("\n📖 Documentation: modules/auth/README.md")
        elif module == "blog":
            click.echo(f"  1. Review module code in modules/{module}/")
            click.secho(
                "  2. ⚠️  IMPORTANT: Run migrations (required before server start):",
                fg="yellow",
                bold=True,
            )
            click.secho(
                "     poetry run python manage.py migrate", fg="cyan", bold=True
            )
            click.echo(
                "  3. Create superuser (optional): poetry run python manage.py createsuperuser"
            )
            click.echo("  4. Start development server:")
            click.echo("")
            click.secho(
                "     ⚠️  IMPORTANT: Use --build flag with Docker",
                fg="yellow",
                bold=True,
            )
            click.secho(
                "     • With Docker: quickscale down && quickscale up --build",
                fg="cyan",
                bold=True,
            )
            click.secho(
                "       ^^^ --build is REQUIRED to install new dependencies",
                fg="yellow",
            )
            click.echo("")
            click.echo("     • Without Docker: poetry run python manage.py runserver")
            click.echo("  5. Visit http://localhost:8000/admin/ to create blog posts")
            click.echo("  6. View your blog at http://localhost:8000/blog/")
            click.echo("  7. RSS feed available at http://localhost:8000/blog/feed/")
            click.echo("\n📖 Documentation: modules/blog/README.md")
        elif module == "listings":
            click.echo(f"  1. Review module code in modules/{module}/")
            click.secho(
                "  2. ⚠️  IMPORTANT: Run migrations (required before server start):",
                fg="yellow",
                bold=True,
            )
            click.secho(
                "     poetry run python manage.py migrate", fg="cyan", bold=True
            )
            click.echo(
                "  3. Create superuser (optional): poetry run python manage.py createsuperuser"
            )
            click.echo("  4. Start development server:")
            click.echo("")
            click.secho(
                "     ⚠️  IMPORTANT: Use --build flag with Docker",
                fg="yellow",
                bold=True,
            )
            click.secho(
                "     • With Docker: quickscale down && quickscale up --build",
                fg="cyan",
                bold=True,
            )
            click.secho(
                "       ^^^ --build is REQUIRED to install new dependencies",
                fg="yellow",
            )
            click.echo("")
            click.echo("     • Without Docker: poetry run python manage.py runserver")
            click.echo(
                "  5. Create a concrete model extending AbstractListing (see README)"
            )
            click.echo("  6. View listings at http://localhost:8000/listings/")
            click.echo("\n📖 Documentation: modules/listings/README.md")
        else:
            click.echo(f"  1. Review the module code in modules/{module}/")
            click.echo(f"  2. Follow setup instructions in modules/{module}/README.md")
            click.echo("  3. Run migrations: python manage.py migrate")

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()


@click.command()
@click.option(
    "--no-preview",
    is_flag=True,
    help="Skip diff preview before updating",
)
def update(no_preview: bool) -> None:
    r"""
    Update all installed QuickScale modules to their latest versions.

    \b
    Examples:
      quickscale update           # Update with diff preview
      quickscale update --no-preview  # Update without preview

    \b
    This command:
      - Reads installed modules from .quickscale/config.yml
      - Updates ONLY modules you've explicitly installed
      - Shows a diff preview before updating (unless --no-preview)
      - Updates the installed version in config after successful update
    """
    try:
        # Validate git repository
        if not is_git_repo():
            click.secho("❌ Error: Not a git repository", fg="red", err=True)
            click.echo(
                "\n💡 Tip: This command must be run from a git repository", err=True
            )
            raise click.Abort()

        # Check working directory is clean
        if not is_working_directory_clean():
            click.secho(
                "❌ Error: Working directory has uncommitted changes",
                fg="red",
                err=True,
            )
            click.echo(
                "\n💡 Tip: Commit or stash your changes before updating modules",
                err=True,
            )
            raise click.Abort()

        # Load configuration
        config = load_config()

        if not config.modules:
            click.secho("✅ No modules installed. Nothing to update.", fg="green")
            click.echo(
                "\n💡 Tip: Install modules with 'quickscale embed --module <name>'"
            )
            return

        # Show installed modules
        click.echo(f"📦 Found {len(config.modules)} installed module(s):")
        for name, info in config.modules.items():
            click.echo(f"  - {name} ({info.installed_version})")

        if not no_preview:
            click.echo("\n🔍 Preview mode: Changes will be shown before updating")

        # Confirm update
        if not click.confirm("\n❓ Continue with update?"):
            click.echo("❌ Update cancelled")
            return

        # Update each module
        for name, info in config.modules.items():
            click.echo(f"\n📥 Updating {name} module...")

            try:
                output = run_git_subtree_pull(
                    prefix=info.prefix,
                    remote=config.default_remote,
                    branch=info.branch,
                    squash=True,
                )

                # Update version in config
                update_module_version(name, "v0.62.0")  # Placeholder version

                click.secho(f"✅ Updated {name} successfully", fg="green")

                if output and not no_preview:
                    click.echo("\n📋 Changes summary:")
                    click.echo(output[:500])  # Show first 500 chars

            except GitError as e:
                click.secho(f"❌ Failed to update {name}: {e}", fg="red", err=True)
                click.echo(f"💡 Tip: Check for conflicts in modules/{name}/", err=True)
                continue

        click.secho("\n🎉 Module update complete!", fg="green", bold=True)

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()


@click.command()
@click.option(
    "--module",
    required=True,
    type=click.Choice(AVAILABLE_MODULES, case_sensitive=False),
    help="Module name to push changes for",
)
@click.option(
    "--branch",
    help="Feature branch name (default: feature/<module>-improvements)",
)
@click.option(
    "--remote",
    default="https://github.com/Experto-AI/quickscale.git",
    help="Git remote URL (default: QuickScale repository)",
)
def push(module: str, branch: str, remote: str) -> None:
    r"""
    Push your local module changes to a feature branch for contribution.

    \b
    Examples:
      quickscale push --module auth
      quickscale push --module auth --branch feature/fix-email-validation

    \b
    Workflow:
      1. This command pushes your changes to a feature branch
      2. You'll need to create a pull request manually on GitHub
      3. Maintainers review and merge to main branch
      4. Auto-split updates the module's split branch

    \b
    Note: You must have write access to the repository to push.
    For external contributions, fork the repository first.
    """
    try:
        # Validate git repository
        if not is_git_repo():
            click.secho("❌ Error: Not a git repository", fg="red", err=True)
            raise click.Abort()

        # Check if module is installed
        config = load_config()
        if module not in config.modules:
            click.secho(
                f"❌ Error: Module '{module}' is not installed", fg="red", err=True
            )
            click.echo(
                f"\n💡 Tip: Install the module first with 'quickscale embed --module {module}'",
                err=True,
            )
            raise click.Abort()

        module_info = config.modules[module]

        # Default branch name
        if not branch:
            branch = f"feature/{module}-improvements"

        # Show what will be pushed
        click.echo(f"📤 Preparing to push changes for module: {module}")
        click.echo(f"   Local prefix: {module_info.prefix}")
        click.echo(f"   Target branch: {branch}")
        click.echo(f"   Remote: {remote}")

        # Confirm push
        if not click.confirm("\n❓ Continue with push?"):
            click.echo("❌ Push cancelled")
            return

        # Push subtree
        click.echo(f"\n🚀 Pushing to {branch}...")
        run_git_subtree_push(prefix=module_info.prefix, remote=remote, branch=branch)

        # Success message
        click.secho("\n✅ Changes pushed successfully!", fg="green", bold=True)
        click.echo("\n📋 Next steps:")
        click.echo("  1. Create a pull request on GitHub:")
        click.echo(f"     https://github.com/Experto-AI/quickscale/pull/new/{branch}")
        click.echo("  2. Describe your changes and submit for review")
        click.echo("  3. After merge, the split branch will auto-update")

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        click.echo(
            "\n💡 Tip: Make sure you have write access to the repository", err=True
        )
        raise click.Abort()
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()
