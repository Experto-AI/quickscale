"""Git index checkpointing, staging, and pre-embed dirty-tree checks.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep
working.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click


# AF6 Phase 2 — core step bodies
from quickscale_cli.commands._types import _GitIndexTreeSnapshot
import quickscale_cli.commands.apply_command as _apply_command


def _capture_git_index_snapshot(project_path: Path) -> _GitIndexTreeSnapshot | None:
    """Capture the current git index tree for later index-only restoration."""
    try:
        result = subprocess.run(
            ["git", "write-tree"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        click.secho(
            f"❌ Failed to snapshot git index before apply checkpoint: {error}",
            fg="red",
            err=True,
        )
        return None
    if result.returncode != 0:
        click.secho(
            "❌ Failed to snapshot git index before apply checkpoint.",
            fg="red",
            err=True,
        )
        if result.stderr:
            click.echo(result.stderr.strip(), err=True)
        return None

    tree_id = result.stdout.strip()
    if not tree_id:
        click.secho(
            "❌ Failed to snapshot git index before apply checkpoint: git write-tree returned no tree id.",
            fg="red",
            err=True,
        )
        return None

    return _apply_command._GitIndexTreeSnapshot(tree_id=tree_id)


def _restore_git_index_snapshot(
    project_path: Path,
    snapshot: _GitIndexTreeSnapshot,
) -> bool:
    """Restore the git index snapshot after an apply-owned checkpoint failure."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "read-tree", "--reset", snapshot.tree_id],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        click.secho(
            f"❌ Failed to restore git index after apply checkpoint failure: {error}",
            fg="red",
            err=True,
        )
        return False
    if result.returncode == 0:
        return True

    click.secho(
        "❌ Failed to restore git index after apply checkpoint failure.",
        fg="red",
        err=True,
    )
    if result.stderr:
        click.echo(result.stderr.strip(), err=True)
    return False


def _restore_failed_apply_checkpoint(
    project_path: Path,
    snapshot: _GitIndexTreeSnapshot,
) -> None:
    """Best-effort index restore for failed apply-owned checkpoint commands."""
    if _apply_command._restore_git_index_snapshot(project_path, snapshot):
        return

    click.secho(
        "❌ QuickScale could not restore the git index after the failed apply checkpoint.",
        fg="red",
        err=True,
    )


def _stage_and_commit_with_index_restore(
    project_path: Path,
    *,
    stage_cmd: list[str],
    stage_description: str,
    commit_cmd: list[str],
    commit_description: str,
) -> bool:
    """Run an apply-owned stage/commit pair and restore the prior index on failure."""
    snapshot = _apply_command._capture_git_index_snapshot(project_path)
    if snapshot is None:
        return False

    staged, _ = _apply_command._run_command(stage_cmd, project_path, stage_description)
    if not staged:
        _apply_command._restore_failed_apply_checkpoint(project_path, snapshot)
        return False

    committed, _ = _apply_command._run_command(
        commit_cmd, project_path, commit_description
    )
    if committed:
        return True

    _apply_command._restore_failed_apply_checkpoint(project_path, snapshot)
    return False


def _run_command(
    cmd: list[str],
    cwd: Path,
    description: str,
    capture: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Run a shell command with progress output

    Args:
        cmd: Command and arguments
        cwd: Working directory
        description: Description for progress output
        capture: Whether to capture output
        env: Optional environment dict for the subprocess.
            When ``None`` (default), the subprocess inherits the parent's
            environment (``os.environ``).

    Returns:
        Tuple of (success, output)

    """
    click.echo(f"⏳ {description}...")
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=False,
            env=env,
        )
        if result.returncode == 0:
            click.secho(f"✅ {description}", fg="green")
            return True, result.stdout if capture else ""
        else:
            click.secho(f"❌ {description} failed", fg="red")
            if capture and result.stderr:
                click.echo(result.stderr, err=True)
            return False, result.stderr if capture else ""
    except FileNotFoundError as e:
        click.secho(f"❌ Command not found: {cmd[0]}", fg="red", err=True)
        return False, str(e)
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        return False, str(e)


def _init_git(project_path: Path) -> bool:
    """Initialize git repository"""
    success, _ = _apply_command._run_command(
        ["git", "init"],
        project_path,
        "Initializing git repository",
    )
    return success


def _git_commit(project_path: Path, message: str) -> bool:
    """Create a git commit"""
    return _apply_command._stage_and_commit_with_index_restore(
        project_path,
        stage_cmd=["git", "add", "-A"],
        stage_description=f"Staging files for: {message}",
        commit_cmd=["git", "commit", "-m", message],
        commit_description=f"Committing: {message}",
    )


def _init_git_with_config(output_path: Path) -> None:
    """Initialize git repository with configuration."""
    if not _apply_command._init_git(output_path):
        click.secho("⚠️  Git initialization failed, continuing...", fg="yellow")
        return

    subprocess.run(
        ["git", "config", "user.email", "quickscale@example.com"],  # noqa: S607 - PATH-resolved executable by design
        cwd=output_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QuickScale"],  # noqa: S607 - PATH-resolved executable by design
        cwd=output_path,
        capture_output=True,
    )

    if not _apply_command._git_commit(output_path, "Initial project structure"):
        click.secho("⚠️  Initial commit failed, continuing...", fg="yellow")


def _list_git_changed_paths(
    project_path: Path,
    git_args: list[str],
    *,
    description: str,
) -> list[str]:
    """Return changed git paths for pre-embed safety checks."""
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", *git_args],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        click.secho(
            f"\n❌ Failed to inspect {description} before module embedding.",
            fg="red",
            err=True,
        )
        if result.stderr:
            click.echo(result.stderr.strip(), err=True)
        raise click.Abort()

    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def _commit_pending_config_changes(output_path: Path) -> None:
    """Commit pending QuickScale config changes before module embedding

    Stages and commits authoritative QuickScale config/state changes so
    git subtree operations have a clean working directory. Called before
    embedding modules in existing projects.

    Args:
        output_path: Path to the project directory

    """
    if _apply_command.is_working_directory_clean(output_path):
        return

    staged_paths = _apply_command._list_git_changed_paths(
        output_path,
        ["diff", "--cached", "--name-only"],
        description="staged changes",
    )
    unstaged_paths = _apply_command._list_git_changed_paths(
        output_path,
        ["diff", "--name-only"],
        description="unstaged changes",
    )
    untracked_paths = _apply_command._list_git_changed_paths(
        output_path,
        ["ls-files", "--others", "--exclude-standard"],
        description="untracked files",
    )

    dirty_paths = sorted(set(staged_paths) | set(unstaged_paths) | set(untracked_paths))
    unrelated_dirty_paths = [
        path
        for path in dirty_paths
        if not _apply_command._is_pre_embed_allowed_dirty_path(path)
    ]
    checkpoint_paths = _apply_command._get_pre_embed_checkpoint_paths(dirty_paths)

    if unrelated_dirty_paths:
        click.secho(
            "\n❌ Cannot embed modules during 'quickscale apply' because unrelated staged, unstaged, or untracked changes are present:",
            fg="red",
            err=True,
        )
        for path in unrelated_dirty_paths:
            click.echo(f"  • {path}", err=True)
        click.echo(
            "\n💡 Commit, stash, or clean the unrelated changes and re-run 'quickscale apply'. Existing-project apply only permits dirty authoritative QuickScale files in quickscale.yml, .quickscale/state.yml, or .quickscale/config.yml before module embedding.",
            err=True,
        )
        raise click.Abort()

    if not checkpoint_paths:
        return

    if _apply_command._stage_and_commit_with_index_restore(
        output_path,
        stage_cmd=["git", "add", "--", *checkpoint_paths],
        stage_description="Staging pending QuickScale configuration changes",
        commit_cmd=[
            "git",
            "commit",
            "-m",
            "Update QuickScale configuration",
            "--",
            *checkpoint_paths,
        ],
        commit_description="Committing pending QuickScale configuration changes",
    ):
        return

    click.secho(
        "\n❌ Cannot continue 'quickscale apply' because QuickScale could not checkpoint managed configuration changes before module embedding.",
        fg="red",
        err=True,
    )
    raise click.Abort()
