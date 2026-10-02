"""The module push command.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path

import click

from quickscale_cli.commands._module_shared import _LazyModuleChoice
import quickscale_cli.commands.module_commands as _module_commands


@click.command()
@click.option(
    "--module",
    required=True,
    type=_LazyModuleChoice(),
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
        if not _module_commands.is_git_repo():
            click.secho("❌ Error: Not a git repository", fg="red", err=True)
            raise click.Abort()

        # Check if module is installed using consolidated state.
        # ProjectStateManager.load_state() performs read-through import of
        # legacy config.yml tracking fields when state.yml lacks consolidated
        # tracking metadata, so this works for both new and legacy projects.
        project_path = Path.cwd()
        manager = _module_commands.ProjectStateManager(project_path)
        try:
            state = manager.load_state()
        except Exception as error:
            click.secho(
                f"❌ Failed to load .quickscale/state.yml: {error}",
                fg="red",
                err=True,
            )
            click.echo(
                "💡 Fix or restore .quickscale/state.yml before running "
                "'quickscale push'.",
                err=True,
            )
            raise click.Abort() from error

        if state is None or module not in state.modules:
            click.secho(
                f"❌ Error: Module '{module}' is not installed", fg="red", err=True
            )
            click.echo(
                "\n💡 Tip: Add the module first with 'quickscale plan --add'",
                err=True,
            )
            raise click.Abort()

        module_state = state.modules[module]
        prefix = module_state.prefix

        if not prefix:
            click.secho(
                f"❌ Error: Module '{module}' has no recorded prefix in state",
                fg="red",
                err=True,
            )
            click.echo(
                "\n💡 Re-run 'quickscale apply' to consolidate module tracking "
                "metadata into .quickscale/state.yml.",
                err=True,
            )
            raise click.Abort()

        # Default branch name
        if not branch:
            branch = f"feature/{module}-improvements"

        # Show what will be pushed
        click.echo(f"📤 Preparing to push changes for module: {module}")
        click.echo(f"   Local prefix: {prefix}")
        click.echo(f"   Target branch: {branch}")
        click.echo(f"   Remote: {remote}")

        # Confirm push
        if not click.confirm("\n❓ Continue with push?"):
            click.echo("❌ Push cancelled")
            return

        # Push subtree
        click.echo(f"\n🚀 Pushing to {branch}...")
        _module_commands.run_git_subtree_push(
            prefix=prefix, remote=remote, branch=branch
        )

        # Success message
        click.secho("\n✅ Changes pushed successfully!", fg="green", bold=True)
        click.echo("\n📋 Next steps:")
        click.echo("  1. Create a pull request on GitHub:")
        click.echo(f"     https://github.com/Experto-AI/quickscale/pull/new/{branch}")
        click.echo("  2. Describe your changes and submit for review")
        click.echo("  3. After merge, the split branch will auto-update")

    except _module_commands.GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        click.echo(
            "\n💡 Tip: Make sure you have write access to the repository", err=True
        )
        raise click.Abort()
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()
