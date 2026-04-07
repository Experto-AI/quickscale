"""Module management commands for QuickScale CLI."""

import subprocess
from pathlib import Path
from typing import Any

import click

from quickscale_cli.module_catalog import get_module_names, get_module_readiness_reason
from quickscale_cli.schema.state_schema import StateError, StateManager
from quickscale_cli.utils.module_dependency_sync import (
    DependencySyncError,
    resolve_embedded_module_install_path as _resolve_install_path_from_dependency_sync,
    sync_project_module_dependencies,
)

from quickscale_core.config import (
    add_module,
    load_config,
    normalize_installed_version,
    update_module_version,
)
from quickscale_core.manifest.loader import ManifestError, get_manifest_for_module
from quickscale_core.utils.git_utils import (
    GitError,
    check_remote_branch_exists,
    is_git_repo,
    is_working_directory_clean,
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
)

from .module_config import (
    MODULE_CONFIGURATORS,
    assess_auth_migration_state,
    format_auth_migration_remediation,
)

# Available modules (including experimental for explicit CLI usage).
AVAILABLE_MODULES = get_module_names(include_experimental=True)


def _validate_git_environment() -> bool:
    """Validate git repository state for module operations.

    Returns:
        True if valid, False otherwise
    """
    if not is_git_repo():
        click.secho("❌ Error: Not a git repository", fg="red", err=True)
        click.echo("\n💡 Tip: Run 'git init' to initialize a git repository", err=True)
        return False

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
        return False

    return True


def _validate_module_not_exists(project_path: Path, module: str) -> bool:
    """Check if module already exists.

    Returns:
        True if module doesn't exist, False if it does
    """
    module_dir = project_path / "modules" / module
    if module_dir.exists():
        click.secho(
            f"❌ Error: Module '{module}' already exists at {module_dir}",
            fg="red",
            err=True,
        )
        click.echo("\n💡 Tip: Remove the existing module directory first", err=True)
        return False
    return True


def _validate_remote_branch(remote: str, branch: str, module: str) -> bool:
    """Check if branch exists on remote.

    Returns:
        True if branch exists, False otherwise
    """
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
        click.echo(
            f"\n📖 Branch '{branch}' does not exist on remote: {remote}", err=True
        )
        return False
    return True


def _check_auth_module_migrations(
    project_path: Path,
    non_interactive: bool,
    allow_unverifiable_auth_state: bool = False,
) -> bool:
    """Check if auth module can be embedded safely.

    Returns:
        True if safe to proceed, False if blocked
    """
    assessment = assess_auth_migration_state(project_path)
    if assessment.compatible:
        return True

    if assessment.unverifiable and allow_unverifiable_auth_state:
        click.secho(
            "\n⚠️  Auth module migration state could not be verified",
            fg="yellow",
            bold=True,
        )
        click.echo(f"\nReason: {assessment.reason}")
        click.echo(
            "\nContinuing because apply is configured to allow unverifiable "
            "migration state checks."
        )
        click.echo(
            "If your database already has baseline Django auth/admin/session/"
            "contenttypes migrations, a destructive reset may still be required."
        )
        click.echo("")
        click.echo(format_auth_migration_remediation(project_path))
        return True

    click.secho(
        "\n⚠️  Auth module migration guardrail triggered",
        fg="yellow",
        bold=True,
    )
    click.echo(f"\nReason: {assessment.reason}")
    click.echo(
        "\n❌ The auth module sets AUTH_USER_MODEL and must be embedded before "
        "incompatible baseline migrations."
    )
    click.echo("")
    click.echo(format_auth_migration_remediation(project_path))

    if non_interactive:
        click.secho(
            "\n❌ Cannot embed auth module in non-interactive mode when "
            f"state is {assessment.status}.",
            fg="red",
            err=True,
        )
        return False

    click.echo(
        "\n❓ Continue anyway? (only if you intentionally accept data-loss remediation)"
    )
    if not click.confirm("Continue?", default=False):
        click.echo("\n❌ Embedding cancelled")
        return False

    return True


def _resolve_embedded_module_install_path(
    project_path: Path,
    module: str,
) -> Path | None:
    """Return the installable package path for an embedded module, if any."""
    return _resolve_install_path_from_dependency_sync(project_path, module)


def _read_embedded_module_version(project_path: Path, module: str) -> str:
    """Read the canonical installed version from the embedded module manifest."""
    manifest = get_manifest_for_module(project_path, module, strict=True)
    assert manifest is not None
    normalized = normalize_installed_version(manifest.version)
    return normalized or manifest.version


def _sync_state_module_version(project_path: Path, module: str, version: str) -> None:
    """Mirror embedded module versions into applied state when present."""
    state_manager = StateManager(project_path)
    state = state_manager.load()
    if state is None or module not in state.modules:
        return

    state.modules[module].version = version
    state_manager.save(state)


def _validate_module_readiness(module: str) -> bool:
    """Reject placeholder modules from embed/apply flows."""
    readiness_reason = get_module_readiness_reason(module)
    if readiness_reason is None:
        return True

    click.secho(f"❌ Error: {readiness_reason}", fg="red", err=True)
    click.echo(
        "\n💡 Placeholder directories remain in the repository for documentation and "
        "future work only.",
        err=True,
    )
    return False


def _perform_module_embed(
    project_path: Path,
    module: str,
    remote: str,
    branch: str,
    config: dict[str, Any],
    *,
    sync_dependencies: bool = True,
    install_dependencies: bool = True,
) -> bool:
    """Execute the actual module embedding.

    Returns:
        True if successful, False otherwise
    """
    prefix = f"modules/{module}"
    click.echo(f"\n📦 Embedding {module} module from {branch}...")

    run_git_subtree_add(prefix=prefix, remote=remote, branch=branch, squash=True)

    try:
        installed_version = _read_embedded_module_version(project_path, module)
    except ManifestError as error:
        click.secho(
            f"\n❌ Embedded module manifest error: {error}",
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(
            "\n💡 Fix the embedded module.yml or remove the partial module embed "
            "before continuing.",
            err=True,
        )
        return False

    # Update configuration tracking
    add_module(
        module_name=module,
        prefix=prefix,
        branch=branch,
        version=installed_version,
        project_path=project_path,
    )

    # Apply module-specific configuration
    if module in MODULE_CONFIGURATORS and config:
        _, applier = MODULE_CONFIGURATORS[module]
        applier(project_path, config)

    if sync_dependencies:
        if not _sync_module_dependencies(project_path, module, config):
            return False

    if (
        install_dependencies
        and _resolve_embedded_module_install_path(project_path, module) is not None
    ):
        if not _install_module_dependencies(project_path, module):
            return False

    # Success message
    module_dir = project_path / "modules" / module
    click.secho(f"\n✅ Module '{module}' embedded successfully!", fg="green", bold=True)
    click.echo(f"   Location: {module_dir}")
    click.echo(f"   Branch: {branch}")

    return True


def embed_module(
    module: str,
    project_path: Path | None = None,
    remote: str = "https://github.com/Experto-AI/quickscale.git",
    non_interactive: bool = True,
    allow_unverifiable_auth_state: bool = False,
    skip_auth_migration_check: bool = False,
    sync_dependencies: bool = True,
    install_dependencies: bool = True,
) -> bool:
    """
    Embed a QuickScale module into a project via git subtree.

    This is the internal function used by `quickscale apply` to embed modules.
    It handles git subtree operations, module configuration, and dependency installation.

    Args:
        module: Module name to embed (auth, billing, teams, blog, listings)
        project_path: Path to the project directory. If None, uses current directory.
        remote: Git remote URL (default: QuickScale repository)
        non_interactive: Use default configuration without prompts
        allow_unverifiable_auth_state: Continue when auth migration state
            cannot be verified (used by quickscale apply for fresh projects)
        skip_auth_migration_check: Skip auth migration guardrail entirely
            (used by quickscale apply for freshly generated projects)
        sync_dependencies: Sync missing pyproject.toml dependency entries for the
            embedded module
        install_dependencies: Run `poetry install` after dependency sync

    Returns:
        True if embedding succeeded, False otherwise

    Raises:
        GitError: If git operations fail
        click.Abort: If validation fails or user cancels

    """
    if project_path is None:
        project_path = Path.cwd()

    # Change to project directory for git operations
    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(project_path)

        # Validation steps
        if not _validate_git_environment():
            return False

        if not _validate_module_not_exists(project_path, module):
            return False

        if not _validate_module_readiness(module):
            return False

        branch = f"splits/{module}-module"
        if not _validate_remote_branch(remote, branch, module):
            return False

        # Auth module special check
        if module == "auth" and not skip_auth_migration_check:
            if not _check_auth_module_migrations(
                project_path,
                non_interactive,
                allow_unverifiable_auth_state,
            ):
                return False

        # Interactive module configuration
        config: dict[str, Any] = {}
        if module in MODULE_CONFIGURATORS:
            configurator, applier = MODULE_CONFIGURATORS[module]
            config = configurator(non_interactive=non_interactive)

        # Perform embedding
        return _perform_module_embed(
            project_path,
            module,
            remote,
            branch,
            config,
            sync_dependencies=sync_dependencies,
            install_dependencies=install_dependencies,
        )

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        return False
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        return False
    finally:
        # Always restore original directory
        import os

        os.chdir(original_cwd)


def _install_module_dependencies(project_path: Path, module: str) -> bool:
    """Install dependencies for a module.

    Args:
        project_path: Path to the project directory
        module: Module name

    Returns:
        True if installation succeeded, False otherwise
    """
    click.echo("\n📦 Installing dependencies...")
    try:
        module_dir = project_path / "modules" / module

        # Verify module was actually embedded
        if not module_dir.exists():
            click.secho(
                f"❌ Error: Module directory not found at {module_dir}",
                fg="red",
                err=True,
            )
            click.echo(
                "   The git subtree add may have failed. Check the output above.",
                err=True,
            )
            return False

        target_path = _resolve_embedded_module_install_path(project_path, module)
        if target_path is None:
            click.echo(
                f"  • No installable Python package detected for {module}; skipping Poetry install."
            )
            return True

        click.echo("  • Refreshing poetry.lock...")
        lock_result = subprocess.run(
            ["poetry", "lock"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        if lock_result.returncode != 0:
            _print_installation_error(
                project_path,
                module,
                lock_result,
                command_name="poetry lock",
            )
            return False

        click.secho("  ✅ poetry.lock refreshed", fg="green")

        click.echo("  • Installing all dependencies...")
        result = subprocess.run(
            ["poetry", "install"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            _print_installation_error(
                project_path,
                module,
                result,
            )
            return False

        click.secho("  ✅ Dependencies installed successfully", fg="green")
        return True

    except Exception as e:
        click.secho(
            f"\n❌ Unexpected error during dependency installation: {e}",
            fg="red",
            err=True,
        )
        click.echo(
            f"\n💡 Try running 'poetry install' manually in {project_path}",
            err=True,
        )
        return False


def _print_installation_error(
    project_path: Path,
    module: str,
    result: subprocess.CompletedProcess[str],
    *,
    command_name: str = "poetry install",
) -> None:
    """Print detailed installation error message."""
    click.secho(
        f"\n❌ Failed to run {command_name} for {module} module",
        fg="red",
        err=True,
        bold=True,
    )
    click.echo("\n📋 Error output (stderr):", err=True)
    click.echo(result.stderr, err=True)
    click.echo("\n📋 Standard output (stdout):", err=True)
    click.echo(result.stdout, err=True)

    click.echo("\n💡 To fix this manually:", err=True)
    click.echo(f"   1. cd {project_path}", err=True)
    click.echo("   2. poetry lock", err=True)
    click.echo("   3. poetry install", err=True)
    click.echo("   4. poetry run python manage.py migrate", err=True)


def _sync_module_dependencies(
    project_path: Path,
    module: str,
    config: dict[str, Any] | None = None,
) -> bool:
    """Sync missing project dependency entries for an embedded module."""
    click.echo("\n📦 Syncing dependency entries...")

    try:
        sync_result = sync_project_module_dependencies(
            project_path,
            {module: config or {}},
        )
    except (DependencySyncError, ManifestError) as error:
        click.secho(
            f"\n❌ Failed to sync {module} dependency entries",
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(f"\n📋 Error: {error}", err=True)
        click.echo("\n💡 To fix this manually:", err=True)
        click.echo(f"   1. Ensure modules/{module}/module.yml is valid", err=True)
        click.echo(
            f"   2. Ensure modules/{module}/pyproject.toml contains matching Poetry dependency versions",
            err=True,
        )
        click.echo("   3. Re-run the embed/apply command", err=True)
        return False

    if sync_result.added_package_dependencies:
        click.echo(
            "  • Added package dependencies: "
            + ", ".join(sync_result.added_package_dependencies)
        )
    if sync_result.added_path_dependencies:
        click.echo(
            "  • Added module path dependencies: "
            + ", ".join(sync_result.added_path_dependencies)
        )
    if not sync_result.changed:
        click.echo("  • Dependency entries already in sync.")

    click.secho("  ✅ Dependency entries synced", fg="green")
    return True


def _validate_update_environment() -> None:
    """Validate git environment for update command.

    Raises:
        click.Abort: If validation fails
    """
    if not is_git_repo():
        click.secho("❌ Error: Not a git repository", fg="red", err=True)
        click.echo("\n💡 Tip: This command must be run from a git repository", err=True)
        raise click.Abort()

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


def _update_single_module(
    name: str, info: Any, default_remote: str, no_preview: bool
) -> bool:
    """Update a single module via git subtree pull."""
    click.echo(f"\n📥 Updating {name} module...")
    project_path = Path.cwd()

    try:
        # Abort before any subtree/config mutation if applied state is invalid.
        StateManager(project_path).load()

        output = run_git_subtree_pull(
            prefix=info.prefix,
            remote=default_remote,
            branch=info.branch,
            squash=True,
        )

        installed_version = _read_embedded_module_version(project_path, name)
        update_module_version(name, installed_version, project_path)
        _sync_state_module_version(project_path, name, installed_version)

        _commit_module_update(name, info.prefix)

        click.secho(f"✅ Updated {name} successfully", fg="green")

        if output and not no_preview:
            click.echo("\n📋 Changes summary:")
            click.echo(output[:500])  # Show first 500 chars

        return True

    except StateError as error:
        click.secho(
            f"❌ Failed to load .quickscale/state.yml: {error}",
            fg="red",
            err=True,
        )
        click.echo(
            "💡 Fix .quickscale/state.yml or regenerate it with 'quickscale apply' "
            "before updating modules.",
            err=True,
        )
        return False
    except ManifestError as e:
        click.secho(f"❌ Failed to update {name}: {e}", fg="red", err=True)
        click.echo(
            f"💡 Fix modules/{name}/module.yml or remove and re-embed the module.",
            err=True,
        )
        return False
    except GitError as e:
        click.secho(f"❌ Failed to update {name}: {e}", fg="red", err=True)
        click.echo(f"💡 Tip: Check for conflicts in modules/{name}/", err=True)
        return False


def _commit_module_update(module_name: str, module_prefix: str) -> None:
    """Create a commit for a successfully updated module."""
    tracked_paths = [module_prefix]
    config_path = Path(".quickscale") / "config.yml"
    if config_path.exists():
        tracked_paths.append(str(config_path))
    state_path = Path(".quickscale") / "state.yml"
    if state_path.exists():
        tracked_paths.append(str(state_path))

    try:
        subprocess.run(
            ["git", "add", *tracked_paths],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to stage {module_name} update commit: {e.stderr}")

    cached_diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
    )

    if cached_diff.returncode == 0:
        click.echo(f"ℹ️  No staged changes detected for {module_name}; skipping commit")
        return

    if cached_diff.returncode != 1:
        raise GitError("Failed to inspect staged changes before module update commit")

    commit_message = f"chore(modules): update {module_name} module"
    try:
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to commit {module_name} update: {e.stderr}")


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
            - Commits each successful module update before continuing
    """
    try:
        _validate_update_environment()

        # Load configuration
        config = load_config()

        if not config.modules:
            click.secho("✅ No modules installed. Nothing to update.", fg="green")
            click.echo(
                "\n💡 Tip: Install modules with 'quickscale embed --module <name>'"
            )
            return

        for name in config.modules:
            if not _validate_module_readiness(name):
                raise click.Abort()

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

        failed_modules: list[str] = []

        # Update each module
        for name, info in config.modules.items():
            if not _update_single_module(name, info, config.default_remote, no_preview):
                failed_modules.append(name)
                break

        if failed_modules:
            click.secho(
                "\n❌ Module update stopped due to failure",
                fg="red",
                bold=True,
                err=True,
            )
            click.echo(
                f"Failed module(s): {', '.join(failed_modules)}",
                err=True,
            )
            raise click.Abort()

        click.secho("\n🎉 Module update complete!", fg="green", bold=True)

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        raise click.Abort()
    except click.Abort:
        raise
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
