"""Module embedding flow and dependency installation.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from quickscale_cli.commands._module_shared import (
    APPLY_MODULE_EXECUTION_MODE,
    ModuleEmbedProvenance,
    ModuleExecutionMode,
    STANDALONE_MODULE_EXECUTION_MODE,
)
import quickscale_cli.commands.module_commands as _module_commands


def _cleanup_failed_apply_embed(project_path: Path, module: str) -> None:
    """Best-effort cleanup for apply embeds that fail after subtree add."""
    module_path = project_path / "modules" / module
    try:
        if module_path.is_dir():
            shutil.rmtree(module_path)
        elif module_path.exists():
            module_path.unlink()
    except OSError as error:
        click.secho(
            f"⚠️  Failed to remove partial apply embed at {module_path}: {error}",
            fg="yellow",
        )

    try:
        _module_commands.remove_module(module, project_path)
    except OSError as error:
        click.secho(
            "⚠️  Failed to remove legacy tracking for partial apply embed "
            f"'{module}': {error}",
            fg="yellow",
        )


def _record_embed_provenance(
    success: bool,
    provenance: ModuleEmbedProvenance | None,
    provenance_sink: list[ModuleEmbedProvenance] | None,
) -> None:
    """Append successful apply provenance to the caller-owned sink."""
    if success and provenance is not None and provenance_sink is not None:
        provenance_sink.append(provenance)


def _cleanup_failed_apply_embed_if_needed(
    project_path: Path,
    module: str,
    execution_mode: ModuleExecutionMode,
) -> None:
    """Clean up a failed embed only for apply-side execution."""
    if execution_mode == APPLY_MODULE_EXECUTION_MODE:
        _module_commands._cleanup_failed_apply_embed(project_path, module)


def _perform_module_embed(
    project_path: Path,
    module: str,
    remote: str,
    branch: str,
    config: dict[str, Any],
    *,
    source_ref: str,
    selected_ref: str | None = None,
    sync_dependencies: bool = True,
    install_dependencies: bool = True,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> tuple[bool, ModuleEmbedProvenance | None]:
    """Execute the actual module embedding.

    The resolver-owned *source_ref* is forwarded directly to
    :func:`run_git_subtree_add` so that the subtree content is bound to the
    exact resolved commit SHA.  The same value is carried forward in the returned
    :class:`ModuleEmbedProvenance` payload for later phases.

    Returns:
        Tuple of (success, provenance).  *provenance* is populated on
        success and ``None`` on failure.
    """
    prefix = f"modules/{module}"
    click.echo(f"\n📦 Embedding {module} module from {branch}...")

    # This seam is deliberately SHA-only: ref selection and peeling happen
    # before this function, so a tag or moving branch can never reach subtree.
    _module_commands.run_git_subtree_add(
        prefix=prefix, remote=remote, branch=source_ref, squash=True
    )

    try:
        installed_version = _module_commands._read_embedded_module_version(
            project_path, module
        )
    except _module_commands.ManifestError as error:
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
        _module_commands._cleanup_failed_apply_embed_if_needed(
            project_path, module, execution_mode
        )
        return False, None
    except _module_commands.ModuleVersionMismatchError as error:
        click.secho(
            f"\n❌ {error}",
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(
            "\n💡 Update QuickScale to the latest version before embedding "
            "this module.",
            err=True,
        )
        _module_commands._cleanup_failed_apply_embed_if_needed(
            project_path, module, execution_mode
        )
        return False, None

    if execution_mode != APPLY_MODULE_EXECUTION_MODE:
        _module_commands.add_module(
            module_name=module,
            prefix=prefix,
            branch=branch,
            version=installed_version,
            project_path=project_path,
        )

    if execution_mode == STANDALONE_MODULE_EXECUTION_MODE:
        embedded_modules = {
            path.name
            for path in (project_path / "modules").iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }
        embedded_modules.add(module)
        try:
            wiring_success, wiring_message = _module_commands.regenerate_managed_wiring(
                project_path,
                module_names=sorted(embedded_modules),
                option_overrides={module: dict(config)},
            )
        except Exception as error:
            wiring_success, wiring_message = False, str(error)
        if not wiring_success:
            click.secho(
                f"\n❌ Managed module wiring regeneration failed: {wiring_message}",
                fg="red",
                err=True,
                bold=True,
            )
            return False, None
        click.echo("  ✅ Regenerated managed module wiring")

    if sync_dependencies:
        if not _module_commands._sync_module_dependencies(
            project_path, {module: config}
        ):
            _module_commands._cleanup_failed_apply_embed_if_needed(
                project_path, module, execution_mode
            )
            return False, None

    if (
        install_dependencies
        and _module_commands._resolve_embedded_module_install_path(project_path, module)
        is not None
    ):
        if not _module_commands._install_module_dependencies(project_path, module):
            _module_commands._cleanup_failed_apply_embed_if_needed(
                project_path, module, execution_mode
            )
            return False, None

    if execution_mode == APPLY_MODULE_EXECUTION_MODE:
        try:
            _module_commands.add_module(
                module_name=module,
                prefix=prefix,
                branch=branch,
                version=installed_version,
                project_path=project_path,
            )
        except Exception as error:
            _module_commands._cleanup_failed_apply_embed(project_path, module)
            click.secho(
                f"\n❌ Failed to update legacy module tracking for {module}: {error}",
                fg="red",
                err=True,
                bold=True,
            )
            return False, None

    # Success message
    module_dir = project_path / "modules" / module
    click.secho(f"\n✅ Module '{module}' embedded successfully!", fg="green", bold=True)
    click.echo(f"   Location: {module_dir}")
    click.echo(f"   Selected ref: {selected_ref or source_ref}")

    provenance = ModuleEmbedProvenance(
        module_name=module,
        prefix=prefix,
        tracking_branch=branch,
        source_ref=source_ref,
        installed_version=installed_version,
        selected_ref=selected_ref or source_ref,
    )
    return True, provenance


def embed_module(
    module: str,
    project_path: Path | None = None,
    remote: str = "https://github.com/Experto-AI/quickscale.git",
    non_interactive: bool = True,
    allow_unverifiable_auth_state: bool = False,
    skip_auth_migration_check: bool = False,
    sync_dependencies: bool = True,
    install_dependencies: bool = True,
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
    provenance_sink: list[ModuleEmbedProvenance] | None = None,
    split_ref: str | None = None,
) -> bool:
    """
    Embed a QuickScale module into a project via git subtree.

    This is the internal function used by `quickscale apply` to embed modules.
    It handles git subtree operations, module configuration, and dependency installation.

    Args:
        module: Module name to embed (auth, billing, blog, listings)
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
        execution_mode: Internal embedding mode used to control when managed
            wiring regeneration happens
        provenance_sink: Optional mutable list that receives the per-module
            :class:`ModuleEmbedProvenance` payload on successful embeds.
        split_ref: Optional explicit maintainer override. When absent, the
            immutable tag for the running core version is required.

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

        # CR-SA94-REV-A-003: Run read-only theme preflight before any
        # git, remote, auth, subtree, filesystem, or state mutation.
        # This rejects retired-theme / malformed-source projects before
        # any probe or mutation occurs.  The shared
        # regenerate_managed_wiring guard also runs preflight internally.
        if not _module_commands._validate_embed_theme(project_path):
            return False

        # Validation steps
        if not _module_commands._validate_git_environment():
            return False

        if not _module_commands._validate_module_not_exists(project_path, module):
            return False

        if not _module_commands._validate_module_readiness(
            module,
            execution_mode=execution_mode,
        ):
            return False

        # Auth module special check
        if module == "auth" and not skip_auth_migration_check:
            if not _module_commands._check_auth_module_migrations(
                project_path,
                non_interactive,
                allow_unverifiable_auth_state,
            ):
                return False

        branch = _module_commands.resolve_split_branch(module)
        resolver: Callable[[str, str], str]
        if split_ref is None:
            selected_ref = _module_commands.resolve_split_tag(
                module, _module_commands.quickscale_version
            )
            if not _module_commands.check_remote_tag_exists(remote, selected_ref):
                _module_commands._report_missing_split_tag(
                    module,
                    _module_commands.quickscale_version,
                    selected_ref,
                    remote,
                )
                return False
            resolver = _module_commands.resolve_remote_tag
        else:
            _module_commands.validate_tag_name(split_ref)
            selected_ref = split_ref
            branch = split_ref
            _module_commands._report_split_ref_override(module, selected_ref)
            resolver = _module_commands.resolve_remote_ref

        # Resolve the selected textual ref exactly once. Both standalone and
        # apply paths use the returned peeled SHA for subtree and provenance.
        ref_resolved, source_ref = _module_commands._resolve_embed_source_ref(
            remote,
            selected_ref,
            module,
            execution_mode,
            resolver,
        )
        if not ref_resolved or source_ref is None:
            return False

        # Interactive module configuration
        config: dict[str, Any] = {}
        configurator_entry = _module_commands.MODULE_CONFIGURATOR_REGISTRY.get(module)
        if configurator_entry is not None:
            config = configurator_entry.configure(non_interactive=non_interactive)

        # Perform embedding
        success, provenance = _module_commands._perform_module_embed(
            project_path,
            module,
            remote,
            branch,
            config,
            source_ref=source_ref,
            selected_ref=selected_ref,
            sync_dependencies=sync_dependencies,
            install_dependencies=install_dependencies,
            execution_mode=execution_mode,
        )

        _module_commands._record_embed_provenance(success, provenance, provenance_sink)

        return success

    except _module_commands.GitError as e:
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

        target_path = _module_commands._resolve_embedded_module_install_path(
            project_path, module
        )
        if target_path is None:
            click.echo(
                f"  • No installable Python package detected for {module}; skipping Poetry install."
            )
            return True

        click.echo("  • Refreshing poetry.lock...")
        poetry_env = _module_commands.build_isolated_poetry_env()
        lock_result = subprocess.run(
            ["poetry", "lock"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            text=True,
            env=poetry_env,
        )

        if lock_result.returncode != 0:
            _module_commands._print_installation_error(
                project_path,
                module,
                lock_result,
                command_name="poetry lock",
            )
            return False

        click.secho("  ✅ poetry.lock refreshed", fg="green")

        click.echo("  • Installing all dependencies...")
        result = subprocess.run(
            ["poetry", "install"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            text=True,
            env=poetry_env,
        )

        if result.returncode != 0:
            _module_commands._print_installation_error(
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


def _sync_module_dependencies(
    project_path: Path,
    modules_options: dict[str, dict[str, Any] | None],
) -> bool:
    """Sync project dependency entries for embedded modules (update path).

    Accepts a dict of ``{module_name: options_or_none}`` so that shared
    dependencies across multiple installed modules are resolved to the
    highest compatible version floor during repinning (SA9.1-REV-004).

    Uses repin mode so that existing path-style or out-of-range entries
    from pre-SA9.1 applies are corrected to the bounded range from the
    updated module manifest (REV-001).
    """
    click.echo("\n📦 Syncing dependency entries...")

    try:
        sync_result = _module_commands.sync_project_module_dependencies(
            project_path,
            modules_options,
            repin_existing=True,
        )
    except (
        _module_commands.DependencySyncError,
        _module_commands.ManifestError,
    ) as error:
        module_names = ", ".join(sorted(modules_options))
        click.secho(
            f"\n❌ Failed to sync dependency entries for {module_names}",
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(f"\n📋 Error: {error}", err=True)
        click.echo("\n💡 To fix this manually:", err=True)
        click.echo("   1. Ensure each module's module.yml is valid", err=True)
        click.echo(
            "   2. Ensure each module's pyproject.toml contains matching "
            "Poetry dependency versions",
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
