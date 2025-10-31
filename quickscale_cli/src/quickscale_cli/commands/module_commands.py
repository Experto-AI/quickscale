"""Module management commands for QuickScale CLI."""

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
AVAILABLE_MODULES = ["auth", "billing", "teams"]


def configure_auth_module() -> dict[str, Any]:
    """Interactive configuration for auth module"""
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
    settings_path = project_path / "settings.py"
    urls_path = project_path / "urls.py"

    if not settings_path.exists():
        click.secho("⚠️  Warning: settings.py not found, skipping auto-configuration", fg="yellow")
        return

    # Read settings.py
    with open(settings_path) as f:
        settings_content = f.read()

    # Check if already configured
    if "quickscale_modules_auth" in settings_content:
        click.echo("ℹ️  Auth module already configured in settings.py")
        return

    # Add required apps to INSTALLED_APPS
    installed_apps_addition = """
# QuickScale Auth Module - Added by quickscale embed
INSTALLED_APPS += [
    "django.contrib.sites",  # Required by allauth
    "allauth",
    "allauth.account",
    "quickscale_modules_auth",
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

    # Add configuration based on user choices
    if config["authentication_method"] == "email":
        installed_apps_addition += 'ACCOUNT_AUTHENTICATION_METHOD = "email"\n'
        installed_apps_addition += "ACCOUNT_USERNAME_REQUIRED = False\n"
        installed_apps_addition += "ACCOUNT_EMAIL_REQUIRED = True\n"
    elif config["authentication_method"] == "username":
        installed_apps_addition += 'ACCOUNT_AUTHENTICATION_METHOD = "username"\n'
        installed_apps_addition += "ACCOUNT_USERNAME_REQUIRED = True\n"
        installed_apps_addition += "ACCOUNT_EMAIL_REQUIRED = False\n"
    else:  # both
        installed_apps_addition += 'ACCOUNT_AUTHENTICATION_METHOD = "email"\n'
        installed_apps_addition += "ACCOUNT_USERNAME_REQUIRED = True\n"
        installed_apps_addition += "ACCOUNT_EMAIL_REQUIRED = True\n"

    installed_apps_addition += f'ACCOUNT_EMAIL_VERIFICATION = "{config["email_verification"]}"\n'
    installed_apps_addition += f'ACCOUNT_ALLOW_REGISTRATION = {config["allow_registration"]}\n'
    installed_apps_addition += (
        'ACCOUNT_ADAPTER = "quickscale_modules_auth.adapters.QuickscaleAccountAdapter"\n'
    )
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

        if "quickscale_modules_auth" not in urls_content:
            # Find urlpatterns and add auth URLs
            if "urlpatterns = [" in urls_content:
                urls_addition = (
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
    click.echo(f"  • Registration: {'Enabled' if config['allow_registration'] else 'Disabled'}")
    click.echo(f"  • Email verification: {config['email_verification']}")
    click.echo(f"  • Authentication: {config['authentication_method']}")


MODULE_CONFIGURATORS = {
    "auth": (configure_auth_module, apply_auth_configuration),
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
def embed(module: str, remote: str) -> None:
    r"""
    Embed a QuickScale module into your project via git subtree.

    \b
    Examples:
      quickscale embed --module auth
      quickscale embed --module billing

    \b
    Available modules (v0.62.0 placeholders):
      - auth: Authentication with django-allauth (placeholder)
      - billing: Stripe integration with dj-stripe (placeholder)
      - teams: Multi-tenancy and team management (placeholder)

    \b
    Note: In v0.62.0, modules contain only placeholder READMEs explaining
    they're not yet implemented. Full implementations coming in v0.63.0+.
    """
    try:
        # Validate git repository
        if not is_git_repo():
            click.secho("❌ Error: Not a git repository", fg="red", err=True)
            click.echo("\n💡 Tip: Run 'git init' to initialize a git repository", err=True)
            raise click.Abort()

        # Check working directory is clean
        if not is_working_directory_clean():
            click.secho("❌ Error: Working directory has uncommitted changes", fg="red", err=True)
            click.echo("\n💡 Tip: Commit or stash your changes before embedding modules", err=True)
            raise click.Abort()

        # Check if module already exists
        module_path = Path.cwd() / "modules" / module
        if module_path.exists():
            click.secho(
                f"❌ Error: Module '{module}' already exists at {module_path}", fg="red", err=True
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
            click.echo(f"\n📖 Branch '{branch}' does not exist on remote: {remote}", err=True)
            raise click.Abort()

        # Interactive module configuration (v0.63.0+)
        config = {}
        if module in MODULE_CONFIGURATORS:
            configurator, applier = MODULE_CONFIGURATORS[module]
            config = configurator()

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

        # Success message
        click.secho(f"\n✅ Module '{module}' embedded successfully!", fg="green", bold=True)
        click.echo(f"   Location: {module_path}")
        click.echo(f"   Branch: {branch}")

        # Module-specific next steps
        click.echo("\n📋 Next steps:")
        if module == "auth":
            click.echo(f"  1. Review module code in modules/{module}/")
            click.echo("  2. Run migrations: python manage.py migrate")
            click.echo("  3. Create superuser (optional): python manage.py createsuperuser")
            click.echo("  4. Visit http://localhost:8000/accounts/login/")
            click.echo("\n� Documentation: modules/auth/README.md")
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
            click.echo("\n💡 Tip: This command must be run from a git repository", err=True)
            raise click.Abort()

        # Check working directory is clean
        if not is_working_directory_clean():
            click.secho("❌ Error: Working directory has uncommitted changes", fg="red", err=True)
            click.echo("\n💡 Tip: Commit or stash your changes before updating modules", err=True)
            raise click.Abort()

        # Load configuration
        config = load_config()

        if not config.modules:
            click.secho("✅ No modules installed. Nothing to update.", fg="green")
            click.echo("\n💡 Tip: Install modules with 'quickscale embed --module <name>'")
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
            click.secho(f"❌ Error: Module '{module}' is not installed", fg="red", err=True)
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
        click.echo("\n💡 Tip: Make sure you have write access to the repository", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()
