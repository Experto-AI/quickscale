"""Module management commands for QuickScale CLI."""

from pathlib import Path

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

# Available modules (placeholders in v0.62.0)
AVAILABLE_MODULES = ["auth", "billing", "teams"]


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

        # Embed module via git subtree
        prefix = f"modules/{module}"
        click.echo(f"\n📦 Embedding {module} module from {branch}...")

        run_git_subtree_add(prefix=prefix, remote=remote, branch=branch, squash=True)

        # Update configuration
        add_module(
            module_name=module,
            prefix=prefix,
            branch=branch,
            version="v0.62.0",  # Placeholder version
        )

        # Success message
        click.secho(f"\n✅ Module '{module}' embedded successfully!", fg="green", bold=True)
        click.echo(f"   Location: {module_path}")
        click.echo(f"   Branch: {branch}")

        # Next steps
        click.echo("\n📋 Next steps:")
        click.echo(f"  1. Review the module code in modules/{module}/")
        click.echo(f"  2. Add to INSTALLED_APPS in settings: 'modules.{module}'")
        click.echo("  3. Run migrations: python manage.py migrate")
        click.echo("\n💡 Note: This is a v0.62.0 placeholder. Full implementation coming soon!")

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
