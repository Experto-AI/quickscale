"""Module configuration functions for QuickScale modules.

This module contains configuration functions for individual QuickScale modules,
including interactive configuration prompts and settings application.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Optional

import click

from quickscale_cli.analytics_contract import (
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
    default_analytics_module_options,
    resolve_analytics_module_options,
    validate_analytics_module_options,
)
from quickscale_cli.backups_contract import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    normalize_backups_module_options,
    validate_backups_env_var_reference,
)
from quickscale_cli.notifications_contract import (
    DEFAULT_NOTIFICATIONS_ALLOWED_TAGS,
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    default_notifications_module_options,
    resolve_notifications_module_options,
    validate_notifications_module_options,
)
from quickscale_cli.social_contract import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LAYOUT_VARIANTS,
    SOCIAL_LINK_TREE_PATH,
    default_social_module_options,
    resolve_social_module_options,
    validate_social_module_options,
)
from quickscale_cli.utils.module_wiring_manager import regenerate_managed_wiring
from quickscale_cli.utils.project_identity import (
    derive_package_from_slug,
    resolve_project_identity,
)


ModuleExecutionMode = Literal["standalone", "apply"]
STANDALONE_MODULE_EXECUTION_MODE: ModuleExecutionMode = "standalone"
APPLY_MODULE_EXECUTION_MODE: ModuleExecutionMode = "apply"


def _is_app_in_installed_apps(settings_content: str, app_name: str) -> bool:
    """Check if an app is already in INSTALLED_APPS.

    Args:
        settings_content: The content of settings.py
        app_name: The app name to check for (e.g., 'django_filters')

    Returns:
        True if the app is already in INSTALLED_APPS, False otherwise
    """
    # Check for app in INSTALLED_APPS list or INSTALLED_APPS +=
    # Match patterns like: "app_name", 'app_name' in lists
    pattern = rf'["\']({re.escape(app_name)})["\']'
    return bool(re.search(pattern, settings_content))


def _filter_new_apps(settings_content: str, apps: list[str]) -> list[str]:
    """Filter out apps that are already in INSTALLED_APPS.

    Args:
        settings_content: The content of settings.py
        apps: List of app names to filter

    Returns:
        List of apps that are NOT already in settings.py
    """
    return [app for app in apps if not _is_app_in_installed_apps(settings_content, app)]


def _merge_existing_config(
    defaults: dict[str, Any],
    existing_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge module defaults with any existing configured values."""
    merged = dict(defaults)
    if existing_config:
        merged.update(dict(existing_config))
    return merged


def _format_tag_list(tags: list[str] | tuple[str, ...]) -> str:
    """Return a comma-separated prompt string for provider-visible tags."""
    return ", ".join(tags)


def _parse_notification_tag_input(raw_value: str, field_name: str) -> list[str]:
    """Normalize comma-separated notification tags using the shared contract."""
    normalized = resolve_notifications_module_options({field_name: raw_value})
    return list(normalized[field_name])


@dataclass(frozen=True)
class AuthMigrationAssessment:
    """Auth migration safety assessment."""

    status: str  # compatible | incompatible | unverifiable
    reason: str

    @property
    def compatible(self) -> bool:
        return self.status == "compatible"

    @property
    def incompatible(self) -> bool:
        return self.status == "incompatible"

    @property
    def unverifiable(self) -> bool:
        return self.status == "unverifiable"


_CORE_AUTH_APPS = {"auth", "admin", "contenttypes", "sessions"}


def _migration_probe_script() -> str:
    """Return Python snippet for migration recorder probing via manage.py shell."""
    return (
        "import json;"
        "from django.db import connection;"
        "from django.db.migrations.recorder import MigrationRecorder;"
        f"core_apps={sorted(_CORE_AUTH_APPS)!r};"
        "recorder=MigrationRecorder(connection);"
        "applied=[(m.app,m.name) for m in recorder.migration_qs];"
        "incompatible=any(app in core_apps for app,_ in applied);"
        "print(json.dumps({'ok': True, 'incompatible': incompatible, 'count': len(applied)}))"
    )


def assess_auth_migration_state(
    project_path: Path | None = None,
) -> AuthMigrationAssessment:
    """Assess whether auth module can be embedded safely.

    Uses Django's MigrationRecorder through project runtime instead of filesystem
    heuristics.
    """
    if project_path is None:
        project_path = Path.cwd()

    manage_py = project_path / "manage.py"
    if not manage_py.exists():
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"manage.py not found at {manage_py}",
        )

    try:
        result = subprocess.run(
            ["python", "manage.py", "shell", "-c", _migration_probe_script()],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"failed to execute Django runtime check: {e}",
        )

    if result.returncode != 0:
        error = (result.stderr or result.stdout or "").strip() or "unknown error"
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"migration recorder check failed: {error}",
        )

    output_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not output_lines:
        return AuthMigrationAssessment(
            status="unverifiable",
            reason="migration recorder check produced no output",
        )

    try:
        payload = json.loads(output_lines[-1])
    except json.JSONDecodeError:
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"unexpected migration recorder output: {output_lines[-1]}",
        )

    if not payload.get("ok"):
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=payload.get("error", "unknown migration recorder error"),
        )

    if payload.get("incompatible"):
        return AuthMigrationAssessment(
            status="incompatible",
            reason=(
                "Default Django auth/admin/session/contenttypes migrations are already "
                "applied in this database."
            ),
        )

    return AuthMigrationAssessment(
        status="compatible",
        reason="No incompatible core auth migrations were detected.",
    )


def has_migrations_been_run(project_path: Path | None = None) -> bool:
    """Backward-compatible helper for tests and existing callers."""
    assessment = assess_auth_migration_state(project_path)
    return assessment.incompatible


def format_auth_migration_remediation(project_path: Path) -> str:
    """Return actionable remediation commands for incompatible auth state."""
    try:
        identity = resolve_project_identity(project_path)
        package_hint = identity.package
    except Exception:
        package_hint = derive_package_from_slug(project_path.name)

    project_abs = project_path.resolve()
    fresh_db_name = f"{package_hint}_fresh"

    return (
        "Remediation options (all may involve data loss):\n\n"
        "1) Fresh disposable local database\n"
        f"   cd {project_abs}\n"
        f"   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/{fresh_db_name}\n"
        "   poetry run python manage.py migrate\n"
        "   quickscale apply\n\n"
        "2) Docker volume reset (destructive)\n"
        f"   cd {project_abs}\n"
        "   docker compose down -v\n"
        "   quickscale up --build\n"
        "   poetry run python manage.py migrate\n"
        "   quickscale apply\n\n"
        "3) Explicitly destructive reset path\n"
        f"   cd {project_abs}\n"
        "   poetry run python manage.py flush --no-input\n"
        "   poetry run python manage.py migrate\n\n"
        "WARNING: These commands can permanently delete data."
    )


# ============================================================================
# AUTH MODULE CONFIGURATION
# ============================================================================


def get_default_auth_config() -> dict[str, Any]:
    """Get default configuration for auth module (non-interactive mode)"""
    return {
        "registration_enabled": True,
        "email_verification": "none",
        "authentication_method": "email",
        "social_providers": [],
        "session_cookie_age": 1209600,
    }


def configure_auth_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for auth module"""
    defaults = _merge_existing_config(get_default_auth_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default auth module configuration...")
        config = defaults
        click.echo("  • Registration: Enabled")
        click.echo(f"  • Email verification: {config['email_verification']}")
        click.echo(f"  • Authentication: {config['authentication_method']}")
        return config

    click.echo("\n⚙️  Configuring auth module...")
    click.echo("Answer these questions to customize the authentication setup:\n")

    config = {
        "registration_enabled": click.confirm(
            "Enable user registration?",
            default=bool(defaults["registration_enabled"]),
        ),
        "email_verification": click.prompt(
            "Email verification",
            type=click.Choice(["none", "optional", "mandatory"], case_sensitive=False),
            default=str(defaults["email_verification"]),
            show_choices=True,
        ),
        "authentication_method": click.prompt(
            "Authentication method",
            type=click.Choice(["email", "username", "both"], case_sensitive=False),
            default=str(defaults["authentication_method"]),
            show_choices=True,
        ),
        "social_providers": list(defaults.get("social_providers", [])),
        "session_cookie_age": int(defaults.get("session_cookie_age", 1209600)),
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
    registration_enabled = config.get("registration_enabled")
    if registration_enabled is None:
        registration_enabled = config.get("allow_registration", True)

    session_cookie_age = int(config.get("session_cookie_age", 1209600))

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
    settings_addition += f"ACCOUNT_ALLOW_REGISTRATION = {registration_enabled}\n"
    settings_addition += 'ACCOUNT_ADAPTER = "quickscale_modules_auth.adapters.QuickscaleAccountAdapter"\n'
    settings_addition += (
        'ACCOUNT_SIGNUP_FORM_CLASS = "quickscale_modules_auth.forms.SignupForm"\n'
    )
    settings_addition += 'LOGIN_REDIRECT_URL = "/accounts/profile/"\n'
    settings_addition += 'LOGOUT_REDIRECT_URL = "/"\n'
    settings_addition += f"SESSION_COOKIE_AGE = {session_cookie_age}  # 2 weeks\n"

    return settings_addition


def _normalize_auth_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy auth config keys to manifest-aligned keys."""
    normalized = dict(config)
    if "registration_enabled" not in normalized and "allow_registration" in normalized:
        normalized["registration_enabled"] = normalized["allow_registration"]
    normalized.setdefault("registration_enabled", True)
    normalized.setdefault("email_verification", "none")
    normalized.setdefault("authentication_method", "email")
    normalized.setdefault("social_providers", [])
    normalized.setdefault("session_cookie_age", 1209600)
    return normalized


def _regenerate_wiring_for_execution_mode(
    project_path: Path,
    module_name: str,
    module_config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Route managed wiring regeneration based on the active execution mode."""
    if execution_mode == STANDALONE_MODULE_EXECUTION_MODE:
        _regenerate_wiring_for_module(project_path, module_name, module_config)
        return

    _regenerate_wiring_for_module(
        project_path,
        module_name,
        module_config,
        execution_mode=execution_mode,
    )


def _regenerate_wiring_for_module(
    project_path: Path,
    module_name: str,
    module_config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Regenerate deterministic managed wiring for module integrations."""
    if execution_mode == APPLY_MODULE_EXECUTION_MODE:
        return

    modules_dir = project_path / "modules"
    discovered_modules = (
        [p.name for p in modules_dir.iterdir() if p.is_dir()]
        if modules_dir.exists()
        else []
    )
    selected_modules = sorted(set(discovered_modules + [module_name]))

    success, message = regenerate_managed_wiring(
        project_path,
        module_names=selected_modules,
        option_overrides={module_name: module_config},
    )
    if not success:
        click.secho(
            f"❌ Managed wiring regeneration failed: {message}",
            fg="red",
            err=True,
        )
        raise click.Abort()

    click.secho("  ✅ Regenerated managed module wiring", fg="green")


def apply_auth_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply auth module configuration via managed wiring files."""
    normalized_config = _normalize_auth_config(config)

    # Managed wiring includes django-allauth + auth module URL routes.
    _regenerate_wiring_for_execution_mode(
        project_path,
        "auth",
        normalized_config,
        execution_mode=execution_mode,
    )

    # Show configuration summary
    click.echo("\n📋 Configuration applied:")
    registration_enabled = normalized_config["registration_enabled"]
    click.echo(f"  • Registration: {'Enabled' if registration_enabled else 'Disabled'}")
    click.echo(f"  • Email verification: {normalized_config['email_verification']}")
    click.echo(f"  • Authentication: {normalized_config['authentication_method']}")


# ============================================================================
# BLOG MODULE CONFIGURATION
# ============================================================================


def get_default_blog_config() -> dict[str, Any]:
    """Get default configuration for blog module (non-interactive mode)"""
    return {
        "posts_per_page": 10,
        "enable_rss": True,
    }


def configure_blog_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for blog module"""
    defaults = _merge_existing_config(get_default_blog_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default blog module configuration...")
        config = defaults
        click.echo(f"  • Posts per page: {config['posts_per_page']}")
        click.echo("  • RSS feed: Enabled")
        return config

    click.echo("\n⚙️  Configuring blog module...")
    click.echo("The blog module will be configured with default settings.\n")

    config = {
        "posts_per_page": click.prompt(
            "Posts per page",
            type=int,
            default=int(defaults["posts_per_page"]),
        ),
        "enable_rss": click.confirm(
            "Enable RSS feed?",
            default=bool(defaults["enable_rss"]),
        ),
    }

    return config


def apply_blog_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply blog module configuration via managed wiring files."""
    _regenerate_wiring_for_execution_mode(
        project_path,
        "blog",
        config,
        execution_mode=execution_mode,
    )

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


def configure_listings_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for listings module"""
    defaults = _merge_existing_config(get_default_listings_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default listings module configuration...")
        config = defaults
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
            default=int(defaults["listings_per_page"]),
        ),
    }

    return config


def _add_listings_dependencies(project_path: Path, pyproject_path: Path) -> None:
    """Add listings runtime dependencies to project's pyproject.toml."""
    with open(pyproject_path) as f:
        pyproject_content = f.read()

    has_django_filter = "django-filter" in pyproject_content
    has_django_markdownx = "django-markdownx" in pyproject_content

    if has_django_filter and has_django_markdownx:
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

    # Extract listings dependency versions using regex
    try:
        with open(listings_pyproject_path) as f:
            listings_pyproject_content = f.read()

        django_filter_match = re.search(
            r'django-filter\s*=\s*["\']([^"\']+)["\']', listings_pyproject_content
        )
        if not django_filter_match:
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

        django_markdownx_match = re.search(
            r'django-markdownx\s*=\s*["\']([^"\']+)["\']',
            listings_pyproject_content,
        )
        django_filter_version = django_filter_match.group(1)
        django_markdownx_version = (
            django_markdownx_match.group(1) if django_markdownx_match else "^4.0"
        )
    except (FileNotFoundError, AttributeError) as e:
        click.secho(
            f"❌ Error: Failed to parse dependency versions from listings module: {e}",
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
        additions = ""
        if not has_django_filter:
            additions += f'\ndjango-filter = "{django_filter_version}"'
        if not has_django_markdownx:
            additions += f'\ndjango-markdownx = "{django_markdownx_version}"'

        # Add dependencies after the python version line
        updated_dependencies = re.sub(
            r'(python = "[^"]*")',
            rf"\1{additions}",
            dependencies_section,
        )
        pyproject_content = pyproject_content.replace(
            dependencies_section, updated_dependencies
        )

        with open(pyproject_path, "w") as f:
            f.write(pyproject_content)

        if not has_django_filter:
            click.secho("  ✅ Added django-filter to pyproject.toml", fg="green")
        if not has_django_markdownx:
            click.secho("  ✅ Added django-markdownx to pyproject.toml", fg="green")
    else:
        click.secho(
            "⚠️  Warning: Could not find [tool.poetry.dependencies] section in "
            "pyproject.toml",
            fg="yellow",
        )


def _add_django_filter_dependency(project_path: Path, pyproject_path: Path) -> None:
    """Backward-compatible helper that only injects django-filter dependency."""
    with open(pyproject_path) as f:
        pyproject_content = f.read()

    if "django-filter" in pyproject_content:
        return

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

    try:
        with open(listings_pyproject_path) as f:
            listings_pyproject_content = f.read()

        version_match = re.search(
            r'django-filter\s*=\s*["\']([^"\']+)["\']', listings_pyproject_content
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
            f"❌ Error: Failed to parse django-filter version from listings module: {e}",
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

    dependencies_pattern = r"(\[tool\.poetry\.dependencies\][^\[]*)"
    match = re.search(dependencies_pattern, pyproject_content, re.DOTALL)
    if match:
        dependencies_section = match.group(1)
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


def apply_listings_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply listings module configuration via managed wiring files."""
    _regenerate_wiring_for_execution_mode(
        project_path,
        "listings",
        config,
        execution_mode=execution_mode,
    )

    # Show configuration summary
    click.echo("\n📋 Configuration applied:")
    click.echo(f"  • Listings per page: {config['listings_per_page']}")


# ============================================================================
# CRM MODULE CONFIGURATION
# ============================================================================


def get_default_crm_config() -> dict[str, Any]:
    """Get default configuration for CRM module (non-interactive mode)"""
    return {
        "enable_api": True,
        "deals_per_page": 25,
        "contacts_per_page": 50,
        "default_pipeline_stages": [
            "Prospecting",
            "Negotiation",
            "Closed-Won",
            "Closed-Lost",
        ],
    }


def configure_crm_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for CRM module"""
    defaults = _merge_existing_config(get_default_crm_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default CRM module configuration...")
        config = defaults
        click.echo("  • API: Enabled")
        click.echo(f"  • Deals per page: {config['deals_per_page']}")
        click.echo(f"  • Contacts per page: {config['contacts_per_page']}")
        return config

    click.echo("\n⚙️  Configuring CRM module...")
    click.echo(
        "The CRM module provides contact management, companies, and deal pipeline.\n"
    )

    config = {
        "enable_api": click.confirm(
            "Enable REST API endpoints?",
            default=bool(defaults["enable_api"]),
        ),
        "deals_per_page": click.prompt(
            "Deals per page",
            type=int,
            default=int(defaults["deals_per_page"]),
        ),
        "contacts_per_page": click.prompt(
            "Contacts per page",
            type=int,
            default=int(defaults["contacts_per_page"]),
        ),
        "default_pipeline_stages": list(defaults["default_pipeline_stages"]),
    }

    return config


def _get_dependency_version(content: str, package: str) -> Optional[str]:
    """Extract dependency version from pyproject.toml content."""
    match = re.search(
        rf'{package}\s*=\s*["\']([^"\']+)["\']',
        content,
    )
    return match.group(1) if match else None


def _update_pyproject_toml(
    pyproject_path: Path,
    content: str,
    drf_ver: Optional[str],
    filter_ver: Optional[str],
) -> None:
    """Update pyproject.toml with new dependencies."""
    dependencies_pattern = r"(\[tool\.poetry\.dependencies\][^\[]*)"
    match = re.search(dependencies_pattern, content, re.DOTALL)
    if not match:
        return

    dependencies_section = match.group(1)
    additions = ""
    if drf_ver:
        additions += f'\ndjangorestframework = "{drf_ver}"'
    if filter_ver:
        additions += f'\ndjango-filter = "{filter_ver}"'

    updated_dependencies = re.sub(
        r'(python = "[^"]*")',
        rf"\1{additions}",
        dependencies_section,
    )
    content = content.replace(dependencies_section, updated_dependencies)

    with open(pyproject_path, "w") as f:
        f.write(content)

    if drf_ver:
        click.secho("  ✅ Added djangorestframework to pyproject.toml", fg="green")
    if filter_ver:
        click.secho("  ✅ Added django-filter to pyproject.toml", fg="green")


def _add_drf_and_filter_dependencies(
    project_path: Path,
    pyproject_path: Path,
    source_module: str = "crm",
) -> None:
    """Add djangorestframework and django-filter dependencies to project's pyproject.toml.

    Reads the required versions from the already-embedded source_module's pyproject.toml.
    """
    with open(pyproject_path) as f:
        pyproject_content = f.read()

    module_pyproject_path = project_path / "modules" / source_module / "pyproject.toml"

    if not module_pyproject_path.exists():
        click.secho(
            f"❌ Error: {source_module} module pyproject.toml not found. "
            "Cannot determine dependency version requirements.",
            fg="red",
            err=True,
        )
        click.echo(f"Expected file: {module_pyproject_path}", err=True)
        raise click.Abort()

    try:
        with open(module_pyproject_path) as f:
            module_pyproject_content = f.read()

        drf_version = None
        if "djangorestframework" not in pyproject_content:
            drf_version = _get_dependency_version(
                module_pyproject_content, "djangorestframework"
            )

        filter_version = None
        if "django-filter" not in pyproject_content:
            filter_version = _get_dependency_version(
                module_pyproject_content, "django-filter"
            )

        if drf_version or filter_version:
            _update_pyproject_toml(
                pyproject_path, pyproject_content, drf_version, filter_version
            )

    except (FileNotFoundError, AttributeError) as e:
        click.secho(
            f"❌ Error: Failed to parse dependencies from {source_module} module: {e}",
            fg="red",
            err=True,
        )
        raise click.Abort()


def _get_crm_settings_addition(config: dict[str, Any]) -> str:
    """Generate settings addition for CRM module."""
    return f"""
# CRM Module Settings
CRM_DEALS_PER_PAGE = {config["deals_per_page"]}
CRM_CONTACTS_PER_PAGE = {config["contacts_per_page"]}
CRM_ENABLE_API = {config["enable_api"]}
"""


def _update_crm_urls(urls_path: Path) -> None:
    """Add CRM URLs to project's urls.py."""
    if not urls_path.exists():
        return

    with open(urls_path) as f:
        urls_content = f.read()

    if "quickscale_modules_crm" in urls_content:
        return

    if "urlpatterns = [" in urls_content:
        urls_addition = '    path("crm/", include("quickscale_modules_crm.urls")),\n'
        urls_content = urls_content.replace(
            "urlpatterns = [", "urlpatterns = [\n" + urls_addition
        )

        with open(urls_path, "w") as f:
            f.write(urls_content)

        click.secho("  ✅ Updated urls.py with CRM URLs", fg="green")


def apply_crm_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply CRM module configuration via managed wiring files."""
    _regenerate_wiring_for_execution_mode(
        project_path,
        "crm",
        config,
        execution_mode=execution_mode,
    )

    # Show configuration summary
    click.echo("\n📋 Configuration applied:")
    click.echo(f"  • API: {'Enabled' if config['enable_api'] else 'Disabled'}")
    click.echo(f"  • Deals per page: {config['deals_per_page']}")
    click.echo(f"  • Contacts per page: {config['contacts_per_page']}")


# ============================================================================
# FORMS MODULE CONFIGURATION
# ============================================================================


def get_default_forms_config() -> dict[str, Any]:
    """Return default configuration for the forms module."""
    return {
        "forms_per_page": 25,
        "spam_protection_enabled": True,
        "rate_limit": "5/hour",
        "data_retention_days": 365,
        "submissions_api_enabled": True,
    }


def configure_forms_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure the forms module interactively or using defaults."""
    defaults = _merge_existing_config(get_default_forms_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default forms module configuration...")
        config = defaults
        click.echo(f"  \u2022 Forms per page: {config['forms_per_page']}")
        click.echo("  \u2022 Spam protection: Enabled")
        click.echo(f"  \u2022 Rate limit: {config['rate_limit']}")
        click.echo(f"  \u2022 Data retention: {config['data_retention_days']} days")
        click.echo("  \u2022 Submissions API: Enabled")
        return config

    click.echo("\n⚙️  Configuring forms module...")
    config = {
        "forms_per_page": click.prompt(
            "Submissions per page (admin)",
            type=int,
            default=int(defaults["forms_per_page"]),
        ),
        "spam_protection_enabled": click.confirm(
            "Enable honeypot spam protection?",
            default=bool(defaults["spam_protection_enabled"]),
        ),
        "rate_limit": click.prompt(
            "Rate limit for submissions (e.g. 5/hour, 10/minute)",
            default=str(defaults["rate_limit"]),
        ),
        "data_retention_days": click.prompt(
            "Data retention days (0 = keep forever)",
            type=int,
            default=int(defaults["data_retention_days"]),
        ),
        "submissions_api_enabled": click.confirm(
            "Enable REST API for admin submissions?",
            default=bool(defaults["submissions_api_enabled"]),
        ),
    }
    return config


def apply_forms_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply forms module configuration to the project."""
    _regenerate_wiring_for_execution_mode(
        project_path,
        "forms",
        config,
        execution_mode=execution_mode,
    )
    click.echo("\n\U0001f4cb Configuration applied:")
    click.echo(f"  \u2022 Forms per page: {config['forms_per_page']}")
    click.echo(
        f"  \u2022 Spam protection: {'Enabled' if config['spam_protection_enabled'] else 'Disabled'}"
    )
    click.echo(f"  \u2022 Rate limit: {config['rate_limit']}")
    click.echo(f"  \u2022 Data retention: {config['data_retention_days']} days")
    click.echo(
        f"  \u2022 Submissions API: {'Enabled' if config['submissions_api_enabled'] else 'Disabled'}"
    )


# ============================================================================
# STORAGE MODULE CONFIGURATION
# ============================================================================


def get_default_storage_config() -> dict[str, Any]:
    """Return default configuration for the storage module."""
    return {
        "backend": "local",
        "media_url": "/media/",
        "public_base_url": "",
        "bucket_name": "",
        "endpoint_url": "",
        "region_name": "",
        "access_key_id": "",
        "secret_access_key": "",
        "default_acl": "",
        "querystring_auth": False,
        "private_media_enabled": False,
    }


def configure_storage_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure storage module settings interactively or with defaults."""
    defaults = _merge_existing_config(get_default_storage_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default storage module configuration...")
        config = defaults
        click.echo(f"  • Backend: {config['backend']}")
        click.echo(f"  • Media URL: {config['media_url']}")
        click.echo("  • Public base URL: not configured")
        return config

    click.echo("\n⚙️  Configuring storage module...")
    click.echo("Configure media storage backend for local or cloud delivery.\n")

    backend = click.prompt(
        "Storage backend",
        type=click.Choice(["local", "s3", "r2"], case_sensitive=False),
        default=str(defaults["backend"]),
        show_choices=True,
    ).lower()

    config = {
        "backend": backend,
        "media_url": click.prompt(
            "Media URL prefix",
            default=str(defaults["media_url"]),
        ).strip()
        or "/media/",
        "public_base_url": click.prompt(
            "Optional public base URL (CDN/domain)",
            default=str(defaults["public_base_url"]),
            show_default=False,
        ).strip(),
        "bucket_name": str(defaults["bucket_name"]),
        "endpoint_url": str(defaults["endpoint_url"]),
        "region_name": str(defaults["region_name"]),
        "access_key_id": str(defaults["access_key_id"]),
        "secret_access_key": str(defaults["secret_access_key"]),
        "default_acl": str(defaults["default_acl"]),
        "querystring_auth": bool(defaults["querystring_auth"]),
        "private_media_enabled": bool(defaults["private_media_enabled"]),
    }

    if backend in {"s3", "r2"}:
        click.echo("\nCloud backend selected. Provide bucket/provider settings.")
        config["bucket_name"] = click.prompt(
            "Bucket name",
            default=str(defaults["bucket_name"]),
        ).strip()
        config["endpoint_url"] = click.prompt(
            "Endpoint URL (required for R2)",
            default=str(defaults["endpoint_url"]),
        ).strip()
        config["region_name"] = click.prompt(
            "Region name",
            default=str(defaults["region_name"]),
        ).strip()
        config["access_key_id"] = click.prompt(
            "Access key id",
            default=str(defaults["access_key_id"]),
        ).strip()
        config["secret_access_key"] = click.prompt(
            "Secret access key",
            default=str(defaults["secret_access_key"]),
        ).strip()
        config["default_acl"] = click.prompt(
            "Default ACL (blank recommended)",
            default=str(defaults["default_acl"]),
        ).strip()
        config["querystring_auth"] = click.confirm(
            "Enable querystring auth (signed URLs)?",
            default=bool(defaults["querystring_auth"]),
        )
    else:
        config.update(
            {
                "bucket_name": "",
                "endpoint_url": "",
                "region_name": "",
                "access_key_id": "",
                "secret_access_key": "",
                "default_acl": "",
                "querystring_auth": False,
            }
        )

    return config


def _add_storage_dependencies(project_path: Path, pyproject_path: Path) -> None:
    """Add storage runtime dependencies when cloud backend is enabled."""
    with open(pyproject_path) as f:
        pyproject_content = f.read()

    has_storages = "django-storages" in pyproject_content
    has_boto3 = "boto3" in pyproject_content

    if has_storages and has_boto3:
        return

    storage_pyproject_path = project_path / "modules" / "storage" / "pyproject.toml"
    if not storage_pyproject_path.exists():
        click.secho(
            "❌ Error: Storage module pyproject.toml not found. "
            "Cannot determine storage dependency versions.",
            fg="red",
            err=True,
        )
        click.echo(f"Expected file: {storage_pyproject_path}", err=True)
        raise click.Abort()

    try:
        with open(storage_pyproject_path) as f:
            storage_pyproject_content = f.read()

        storages_version = None
        if not has_storages:
            storages_version = _get_dependency_version(
                storage_pyproject_content, "django-storages"
            )

        boto3_version = None
        if not has_boto3:
            boto3_version = _get_dependency_version(storage_pyproject_content, "boto3")
    except (FileNotFoundError, AttributeError) as e:
        click.secho(
            f"❌ Error: Failed to parse storage dependencies: {e}",
            fg="red",
            err=True,
        )
        raise click.Abort()

    dependencies_pattern = r"(\[tool\.poetry\.dependencies\][^\[]*)"
    match = re.search(dependencies_pattern, pyproject_content, re.DOTALL)
    if not match:
        click.secho(
            "⚠️  Warning: Could not find [tool.poetry.dependencies] section in "
            "pyproject.toml",
            fg="yellow",
        )
        return

    dependencies_section = match.group(1)
    additions = ""
    if storages_version:
        additions += f'\ndjango-storages = "{storages_version}"'
    if boto3_version:
        additions += f'\nboto3 = "{boto3_version}"'

    if not additions:
        return

    updated_dependencies = re.sub(
        r'(python = "[^"]*")',
        rf"\1{additions}",
        dependencies_section,
    )
    pyproject_content = pyproject_content.replace(
        dependencies_section, updated_dependencies
    )

    with open(pyproject_path, "w") as f:
        f.write(pyproject_content)

    if storages_version:
        click.secho("  ✅ Added django-storages to pyproject.toml", fg="green")
    if boto3_version:
        click.secho("  ✅ Added boto3 to pyproject.toml", fg="green")


def apply_storage_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply storage module configuration via managed wiring files."""
    normalized = get_default_storage_config() | config

    _regenerate_wiring_for_execution_mode(
        project_path,
        "storage",
        normalized,
        execution_mode=execution_mode,
    )

    click.echo("\n📋 Configuration applied:")
    click.echo(f"  • Backend: {normalized['backend']}")
    click.echo(f"  • Media URL: {normalized['media_url']}")
    public_base_url = str(normalized.get("public_base_url") or "").strip()
    click.echo(
        "  • Public base URL: "
        + (public_base_url if public_base_url else "not configured")
    )
    if normalized["backend"] in {"s3", "r2"}:
        click.echo(
            "  • Bucket: "
            + (str(normalized.get("bucket_name") or "").strip() or "not configured")
        )


# ============================================================================
# BACKUPS MODULE CONFIGURATION
# ============================================================================


def get_default_backups_config() -> dict[str, Any]:
    """Return default configuration for the backups module."""
    return {
        "retention_days": 14,
        "naming_prefix": "db",
        "target_mode": "local",
        "local_directory": ".quickscale/backups",
        "remote_bucket_name": "",
        "remote_prefix": "backups/private",
        "remote_endpoint_url": "",
        "remote_region_name": "",
        BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "",
        BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: "",
        "automation_enabled": False,
        "schedule": "0 2 * * *",
    }


def _resolve_backups_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Merge backups options with defaults while preserving explicit overrides."""
    resolved = get_default_backups_config()
    resolved.update(normalize_backups_module_options(config))
    return resolved


def validate_backups_module_options(config: Mapping[str, Any]) -> list[str]:
    """Return validation issues for backups module options."""
    issues: list[str] = []
    resolved = _resolve_backups_config(config)

    try:
        retention_days = int(resolved["retention_days"])
        if retention_days < 1:
            issues.append("modules.backups.retention_days must be at least 1")
    except TypeError, ValueError:
        issues.append("modules.backups.retention_days must be an integer")

    naming_prefix = str(resolved["naming_prefix"]).strip()
    if not naming_prefix:
        issues.append("modules.backups.naming_prefix cannot be blank")

    target_mode = str(resolved["target_mode"]).strip().lower()
    if target_mode not in {"local", "private_remote"}:
        issues.append("modules.backups.target_mode must be 'local' or 'private_remote'")

    local_directory = str(resolved["local_directory"]).strip()
    if not local_directory:
        issues.append("modules.backups.local_directory cannot be blank")

    automation_enabled = bool(resolved["automation_enabled"])
    schedule = str(resolved["schedule"]).strip()
    if automation_enabled and not schedule:
        issues.append(
            "modules.backups.schedule is required when automation_enabled is true"
        )

    if target_mode == "private_remote":
        bucket_name = str(resolved["remote_bucket_name"]).strip()
        access_key_id_env_var = str(
            resolved[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
        ).strip()
        secret_access_key_env_var = str(
            resolved[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
        ).strip()
        endpoint_url = str(resolved["remote_endpoint_url"]).strip()
        region_name = str(resolved["remote_region_name"]).strip()

        if not bucket_name:
            issues.append(
                "modules.backups.remote_bucket_name is required when "
                "target_mode is private_remote"
            )
        if not access_key_id_env_var:
            issues.append(
                "modules.backups.remote_access_key_id_env_var is required when "
                "target_mode is private_remote"
            )
        else:
            access_key_issue = validate_backups_env_var_reference(
                BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
                access_key_id_env_var,
            )
            if access_key_issue:
                issues.append(access_key_issue)
        if not secret_access_key_env_var:
            issues.append(
                "modules.backups.remote_secret_access_key_env_var is required when "
                "target_mode is private_remote"
            )
        else:
            secret_access_key_issue = validate_backups_env_var_reference(
                BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
                secret_access_key_env_var,
            )
            if secret_access_key_issue:
                issues.append(secret_access_key_issue)
        if not (endpoint_url or region_name):
            issues.append(
                "modules.backups.private_remote mode requires remote_region_name "
                "or remote_endpoint_url"
            )

    return issues


def _raise_for_invalid_backups_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when backups config is invalid."""
    issues = validate_backups_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid backups module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_backups_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure backups module settings interactively or with defaults."""
    defaults = _resolve_backups_config(existing_config or {})

    if non_interactive:
        click.echo("\n⚙️  Using default backups module configuration...")
        config = defaults
        click.echo(f"  • Retention days: {config['retention_days']}")
        click.echo(f"  • Naming prefix: {config['naming_prefix']}")
        click.echo(f"  • Target mode: {config['target_mode']}")
        click.echo(
            f"  • Automation: {'Enabled' if config['automation_enabled'] else 'Disabled'}"
        )
        _raise_for_invalid_backups_config(config)
        return config

    click.echo("\n⚙️  Configuring backups module...")
    click.echo(
        "Backups are private operational artifacts. Restore execution remains "
        "CLI-only and scheduled runs stay command-driven.\n"
    )

    target_mode = click.prompt(
        "Backup target mode",
        type=click.Choice(["local", "private_remote"], case_sensitive=False),
        default=str(defaults["target_mode"]),
        show_choices=True,
    ).lower()

    automation_enabled = click.confirm(
        "Record that external cron/scheduler automation is enabled?",
        default=bool(defaults["automation_enabled"]),
    )

    config = {
        "retention_days": click.prompt(
            "Retention days",
            type=int,
            default=int(defaults["retention_days"]),
        ),
        "naming_prefix": click.prompt(
            "Naming prefix",
            default=str(defaults["naming_prefix"]),
        ).strip()
        or "db",
        "target_mode": target_mode,
        "local_directory": click.prompt(
            "Private local backup directory",
            default=str(defaults["local_directory"]),
        ).strip()
        or ".quickscale/backups",
        "remote_bucket_name": str(defaults["remote_bucket_name"]),
        "remote_prefix": str(defaults["remote_prefix"]),
        "remote_endpoint_url": str(defaults["remote_endpoint_url"]),
        "remote_region_name": str(defaults["remote_region_name"]),
        BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: str(
            defaults[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
        ),
        BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: str(
            defaults[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
        ),
        "automation_enabled": automation_enabled,
        "schedule": str(defaults["schedule"]),
    }

    if automation_enabled:
        config["schedule"] = click.prompt(
            "Documented schedule (cron-like)",
            default=str(defaults["schedule"]),
        ).strip()
    else:
        config["schedule"] = str(defaults["schedule"])

    if target_mode == "private_remote":
        click.echo("\nPrivate remote mode selected. Provide S3-compatible settings.")
        config["remote_bucket_name"] = click.prompt(
            "Remote bucket name",
            default=str(defaults["remote_bucket_name"]),
        ).strip()
        config["remote_prefix"] = (
            click.prompt(
                "Remote object prefix",
                default=str(defaults["remote_prefix"]),
            ).strip()
            or "backups/private"
        )
        config["remote_endpoint_url"] = click.prompt(
            "Remote endpoint URL (leave blank for provider defaults)",
            default=str(defaults["remote_endpoint_url"]),
            show_default=False,
        ).strip()
        config["remote_region_name"] = click.prompt(
            "Remote region name (or auto for endpoint providers)",
            default=str(defaults["remote_region_name"]),
            show_default=bool(defaults["remote_region_name"]),
        ).strip()
        config[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION] = click.prompt(
            "Remote access key id environment variable",
            default=(
                str(defaults[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]).strip()
                or DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
            ),
            show_default=True,
        ).strip()
        config[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION] = click.prompt(
            "Remote secret access key environment variable",
            default=(
                str(defaults[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]).strip()
                or DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
            ),
            show_default=True,
        ).strip()
    else:
        config.update(
            {
                "remote_bucket_name": "",
                "remote_prefix": "backups/private",
                "remote_endpoint_url": "",
                "remote_region_name": "",
                BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "",
                BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: "",
            }
        )

    _raise_for_invalid_backups_config(config)
    return config


def apply_backups_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply backups module configuration via managed wiring files."""
    normalized = _resolve_backups_config(config)
    _raise_for_invalid_backups_config(normalized)
    _regenerate_wiring_for_execution_mode(
        project_path,
        "backups",
        normalized,
        execution_mode=execution_mode,
    )

    click.echo("\n📋 Configuration applied:")
    click.echo(f"  • Retention days: {normalized['retention_days']}")
    click.echo(f"  • Naming prefix: {normalized['naming_prefix']}")
    click.echo(f"  • Target mode: {normalized['target_mode']}")
    click.echo(
        "  • Automation: "
        + ("Enabled" if normalized["automation_enabled"] else "Disabled")
    )
    if normalized["target_mode"] == "private_remote":
        click.echo(
            "  • Remote bucket: "
            + (normalized["remote_bucket_name"] or "not configured")
        )


# ============================================================================
# NOTIFICATIONS MODULE CONFIGURATION
# ============================================================================


def get_default_notifications_config() -> dict[str, Any]:
    """Return default configuration for the notifications module."""
    return default_notifications_module_options()


def _raise_for_invalid_notifications_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when notifications config is invalid."""
    issues = validate_notifications_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid notifications module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_notifications_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure notifications module settings interactively or with defaults."""
    defaults = resolve_notifications_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default notifications module configuration...")
        click.echo(
            f"  • Sender: {defaults['sender_name']} <{defaults['sender_email']}>"
        )
        click.echo("  • Live delivery: configure later (console-safe by default)")
        click.echo("  • Webhook signing: configure later")
        _raise_for_invalid_notifications_config(defaults)
        return defaults

    click.echo("\n⚙️  Configuring notifications module...")
    click.echo(
        "Notifications remain console-safe by default. Configure a verified Resend "
        "domain only when you want live delivery to take ownership of email settings.\n"
    )

    enabled = click.confirm(
        "Enable the notifications runtime?",
        default=bool(defaults["enabled"]),
    )
    sender_name = click.prompt(
        "Sender display name",
        default=str(defaults["sender_name"]),
    ).strip()
    sender_email = click.prompt(
        "Sender email address",
        default=str(defaults["sender_email"]),
    ).strip()
    reply_to_email = click.prompt(
        "Reply-to email address (leave blank to reuse sender)",
        default=str(defaults["reply_to_email"]),
        show_default=bool(defaults["reply_to_email"]),
    ).strip()

    configure_live_delivery_now = enabled and click.confirm(
        "Configure live Resend delivery now?",
        default=bool(defaults["resend_domain"]),
    )
    if configure_live_delivery_now:
        resend_domain = click.prompt(
            "Verified Resend sending domain",
            default=str(defaults["resend_domain"]),
            show_default=bool(defaults["resend_domain"]),
        ).strip()
        resend_api_key_env_var = click.prompt(
            "Resend API key environment variable",
            default=(
                str(defaults[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION]).strip()
                or DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
            ),
            show_default=True,
        ).strip()
    else:
        resend_domain = ""
        resend_api_key_env_var = (
            str(defaults[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION]).strip()
            or DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
        )

    configure_webhooks_now = enabled and click.confirm(
        "Configure webhook signing now?",
        default=bool(defaults[NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION]),
    )
    if configure_webhooks_now:
        webhook_secret_env_var = click.prompt(
            "Webhook secret environment variable",
            default=(
                str(defaults[NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION]).strip()
                or DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR
            ),
            show_default=True,
        ).strip()
    else:
        webhook_secret_env_var = ""

    allowed_tags = _parse_notification_tag_input(
        click.prompt(
            "Allowed provider-visible tags (comma-separated)",
            default=_format_tag_list(
                list(defaults.get("allowed_tags", DEFAULT_NOTIFICATIONS_ALLOWED_TAGS))
            ),
            show_default=True,
        ),
        "allowed_tags",
    )
    default_tags = _parse_notification_tag_input(
        click.prompt(
            "Default provider-visible tags (comma-separated)",
            default=_format_tag_list(list(defaults.get("default_tags", []))),
            show_default=True,
        ),
        "default_tags",
    )
    webhook_ttl_seconds = click.prompt(
        "Webhook timestamp tolerance in seconds",
        type=int,
        default=int(defaults["webhook_ttl_seconds"]),
    )

    config = resolve_notifications_module_options(
        {
            "enabled": enabled,
            "sender_name": sender_name,
            "sender_email": sender_email,
            "reply_to_email": reply_to_email,
            "resend_domain": resend_domain,
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: resend_api_key_env_var,
            NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION: webhook_secret_env_var,
            "default_tags": default_tags,
            "allowed_tags": allowed_tags,
            "webhook_ttl_seconds": webhook_ttl_seconds,
        }
    )
    _raise_for_invalid_notifications_config(config)
    return config


def apply_notifications_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply notifications module configuration via managed wiring files."""
    resolved = resolve_notifications_module_options(config)
    _raise_for_invalid_notifications_config(resolved)
    _regenerate_wiring_for_execution_mode(
        project_path,
        "notifications",
        resolved,
        execution_mode=execution_mode,
    )

    click.echo("\n📋 Configuration applied:")
    click.echo(f"  • Sender: {resolved['sender_name']} <{resolved['sender_email']}>")
    click.echo(
        "  • Live delivery: "
        + (resolved["resend_domain"] or "configure later (console-safe by default)")
    )
    click.echo(
        "  • Webhook secret env var: "
        + (resolved[NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION] or "configure later")
    )


# ============================================================================
# ANALYTICS MODULE CONFIGURATION
# ============================================================================


def get_default_analytics_config() -> dict[str, Any]:
    """Return default configuration for the analytics module."""
    return default_analytics_module_options()


def _raise_for_invalid_analytics_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when analytics config is invalid."""
    issues = validate_analytics_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid analytics module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_analytics_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure analytics module settings interactively or with defaults."""
    defaults = resolve_analytics_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default analytics module configuration...")
        click.echo("  • Runtime: " + ("Enabled" if defaults["enabled"] else "Disabled"))
        click.echo(f"  • Provider: {defaults['provider']}")
        click.echo("  • API key env var: " + str(defaults["posthog_api_key_env_var"]))
        click.echo("  • Host: " + str(defaults["posthog_host"]))
        _raise_for_invalid_analytics_config(defaults)
        return defaults

    click.echo("\n⚙️  Configuring analytics module...")
    click.echo(
        "Analytics is PostHog-only in v0.80.0. QuickScale owns the backend "
        "settings and capture helpers, while existing React/HTML theme files stay "
        "user-owned for manual frontend adoption.\n"
    )

    config = resolve_analytics_module_options(
        {
            "enabled": click.confirm(
                "Enable the analytics runtime?",
                default=bool(defaults["enabled"]),
            ),
            "provider": "posthog",
            "posthog_api_key_env_var": click.prompt(
                "PostHog API key environment variable",
                default=(
                    str(defaults["posthog_api_key_env_var"]).strip()
                    or DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR
                ),
                show_default=True,
            ).strip(),
            "posthog_host_env_var": click.prompt(
                "PostHog host environment variable",
                default=(
                    str(defaults["posthog_host_env_var"]).strip()
                    or DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR
                ),
                show_default=True,
            ).strip(),
            "posthog_host": (
                click.prompt(
                    "PostHog host URL",
                    default=(
                        str(defaults["posthog_host"]).strip()
                        or ANALYTICS_POSTHOG_DEFAULT_HOST
                    ),
                    show_default=True,
                ).strip()
                or ANALYTICS_POSTHOG_DEFAULT_HOST
            ),
            "exclude_debug": click.confirm(
                "Disable analytics automatically when DEBUG=True?",
                default=bool(defaults["exclude_debug"]),
            ),
            "exclude_staff": click.confirm(
                "Exclude staff users from analytics capture?",
                default=bool(defaults["exclude_staff"]),
            ),
            "anonymous_by_default": click.confirm(
                "Use anonymous session-based distinct IDs by default?",
                default=bool(defaults["anonymous_by_default"]),
            ),
        }
    )
    _raise_for_invalid_analytics_config(config)
    return config


def apply_analytics_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply analytics module configuration via managed wiring files."""
    resolved = resolve_analytics_module_options(config)
    _raise_for_invalid_analytics_config(resolved)
    _regenerate_wiring_for_execution_mode(
        project_path,
        "analytics",
        resolved,
        execution_mode=execution_mode,
    )

    click.echo("\n📋 Configuration applied:")
    click.echo("  • Runtime: " + ("Enabled" if resolved["enabled"] else "Disabled"))
    click.echo("  • Provider: " + str(resolved["provider"]))
    click.echo("  • API key env var: " + str(resolved["posthog_api_key_env_var"]))
    click.echo("  • Host env var: " + str(resolved["posthog_host_env_var"]))
    click.echo("  • Host fallback: " + str(resolved["posthog_host"]))
    click.echo(
        "  • Exclusions: "
        + ("debug" if resolved["exclude_debug"] else "debug allowed")
        + ", "
        + ("staff excluded" if resolved["exclude_staff"] else "staff included")
    )


# ============================================================================
# SOCIAL MODULE CONFIGURATION
# ============================================================================


def get_default_social_config() -> dict[str, Any]:
    """Return default configuration for the social module."""
    return default_social_module_options()


def _raise_for_invalid_social_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when social config is invalid."""
    issues = validate_social_module_options(dict(config))
    if not issues:
        return

    click.secho("\n❌ Invalid social module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_social_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure social module settings interactively or with defaults."""
    defaults = resolve_social_module_options(dict(existing_config or {}))

    if non_interactive:
        click.echo("\n⚙️  Using default social module configuration...")
        click.echo(
            "  • Link tree: "
            + ("Enabled" if defaults["link_tree_enabled"] else "Disabled")
            + f" ({SOCIAL_LINK_TREE_PATH})"
        )
        click.echo(
            "  • Embeds: "
            + ("Enabled" if defaults["embeds_enabled"] else "Disabled")
            + f" ({SOCIAL_EMBEDS_PATH})"
        )
        click.echo("  • Providers: " + ", ".join(defaults["provider_allowlist"]))
        _raise_for_invalid_social_config(defaults)
        return defaults

    click.echo("\n⚙️  Configuring social module...")
    click.echo(
        "Social keeps a managed backend transport plus canonical public paths. "
        "Fresh showcase_react generations keep the Django-owned public pages at "
        f"{SOCIAL_LINK_TREE_PATH} and {SOCIAL_EMBEDS_PATH}, while showcase_html and "
        "existing generated projects require manual theme adoption.\n"
    )

    config = resolve_social_module_options(
        {
            "link_tree_enabled": click.confirm(
                f"Enable the fixed {SOCIAL_LINK_TREE_PATH} public surface?",
                default=bool(defaults["link_tree_enabled"]),
            ),
            "layout_variant": click.prompt(
                "Default link-tree layout variant",
                type=click.Choice(list(SOCIAL_LAYOUT_VARIANTS), case_sensitive=False),
                default=str(defaults["layout_variant"]),
                show_choices=True,
            ).lower(),
            "embeds_enabled": click.confirm(
                f"Enable the fixed {SOCIAL_EMBEDS_PATH} public surface?",
                default=bool(defaults["embeds_enabled"]),
            ),
            "provider_allowlist": click.prompt(
                "Allowlisted providers (comma-separated)",
                default=", ".join(defaults["provider_allowlist"]),
                show_default=True,
            ),
            "cache_ttl_seconds": click.prompt(
                "Cache TTL in seconds",
                type=int,
                default=int(defaults["cache_ttl_seconds"]),
            ),
            "links_per_page": click.prompt(
                "Links per page",
                type=int,
                default=int(defaults["links_per_page"]),
            ),
            "embeds_per_page": click.prompt(
                "Embeds per page",
                type=int,
                default=int(defaults["embeds_per_page"]),
            ),
        }
    )

    _raise_for_invalid_social_config(config)
    return config


def apply_social_configuration(
    project_path: Path,
    config: dict[str, Any],
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> None:
    """Apply social module configuration via managed wiring files."""
    resolved = resolve_social_module_options(config)
    _raise_for_invalid_social_config(resolved)
    _regenerate_wiring_for_execution_mode(
        project_path,
        "social",
        resolved,
        execution_mode=execution_mode,
    )

    click.echo("\n📋 Configuration applied:")
    click.echo(
        "  • Link tree: "
        + ("Enabled" if resolved["link_tree_enabled"] else "Disabled")
        + f" ({SOCIAL_LINK_TREE_PATH})"
    )
    click.echo(
        "  • Embeds: "
        + ("Enabled" if resolved["embeds_enabled"] else "Disabled")
        + f" ({SOCIAL_EMBEDS_PATH})"
    )
    click.echo(
        "  • Managed backend transport: "
        + f"{SOCIAL_INTEGRATION_BASE_PATH} and {SOCIAL_INTEGRATION_EMBEDS_PATH}"
    )
    click.echo(
        "  • Public pages: fresh showcase_react keeps "
        + f"{SOCIAL_LINK_TREE_PATH} and {SOCIAL_EMBEDS_PATH}; showcase_html and "
        "existing generated projects require manual theme adoption."
    )
    click.echo("  • Layout variant: " + str(resolved["layout_variant"]))
    click.echo("  • Providers: " + ", ".join(list(resolved["provider_allowlist"])))


# ============================================================================
# MODULE CONFIGURATORS REGISTRY
# ============================================================================

MODULE_CONFIGURATORS = {
    "auth": (configure_auth_module, apply_auth_configuration),
    "blog": (configure_blog_module, apply_blog_configuration),
    "listings": (configure_listings_module, apply_listings_configuration),
    "crm": (configure_crm_module, apply_crm_configuration),
    "forms": (configure_forms_module, apply_forms_configuration),
    "storage": (configure_storage_module, apply_storage_configuration),
    "backups": (configure_backups_module, apply_backups_configuration),
    "notifications": (
        configure_notifications_module,
        apply_notifications_configuration,
    ),
    "analytics": (configure_analytics_module, apply_analytics_configuration),
    "social": (configure_social_module, apply_social_configuration),
}
