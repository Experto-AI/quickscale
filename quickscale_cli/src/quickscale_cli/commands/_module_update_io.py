"""Module-update snapshots, commits, and wiring persistence helpers.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import click

from quickscale_cli.commands._module_shared import _UpdatePathSnapshot

import quickscale_core.project_state_hashes as _project_state_hashes
import quickscale_core.utils.git_errors as _git_errors
import quickscale_core.utils.poetry_env as _poetry_env
import quickscale_cli.utils.module_wiring_manager as _module_wiring_manager


def _remove_update_path(path: Path) -> None:
    """Remove a file or directory if it exists."""
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
        return

    path.unlink()


def _snapshot_update_path(
    path: Path,
    backup_root: Path,
    label: str,
) -> _UpdatePathSnapshot:
    """Snapshot a file or directory before a module update mutates it."""
    if not path.exists():
        return _UpdatePathSnapshot(
            path=path,
            backup_path=None,
            existed=False,
            is_dir=False,
        )

    backup_path = backup_root / label
    if path.is_dir():
        shutil.copytree(path, backup_path)
        return _UpdatePathSnapshot(
            path=path,
            backup_path=backup_path,
            existed=True,
            is_dir=True,
        )

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return _UpdatePathSnapshot(
        path=path,
        backup_path=backup_path,
        existed=True,
        is_dir=False,
    )


def _restore_update_snapshot(snapshot: _UpdatePathSnapshot) -> None:
    """Restore a single module update snapshot."""
    if not snapshot.existed:
        _remove_update_path(snapshot.path)
        return

    if snapshot.backup_path is None:
        raise RuntimeError(f"Missing rollback payload for {snapshot.path}")

    _remove_update_path(snapshot.path)
    if snapshot.is_dir:
        shutil.copytree(snapshot.backup_path, snapshot.path)
        return

    snapshot.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot.backup_path, snapshot.path)


def _restore_update_snapshots(snapshots: list[_UpdatePathSnapshot]) -> None:
    """Restore all module update snapshots in reverse mutation order."""
    for snapshot in reversed(snapshots):
        _restore_update_snapshot(snapshot)


def _record_update_mutation_snapshots(
    project_path: Path,
    module_prefix: str,
    backup_root: Path,
) -> list[_UpdatePathSnapshot]:
    """Snapshot every artifact a subtree update may mutate locally."""
    snapshot_targets = [
        ("module-tree", project_path / module_prefix),
        ("legacy-config-yml", project_path / ".quickscale" / "config.yml"),
        ("state-yml", project_path / ".quickscale" / "state.yml"),
        ("pyproject-toml", project_path / "pyproject.toml"),
        ("poetry-lock", project_path / "poetry.lock"),
    ]
    return [
        _snapshot_update_path(path, backup_root, label)
        for label, path in snapshot_targets
    ]


def _refresh_git_index_after_update_rollback(
    project_path: Path,
    snapshots: list[_UpdatePathSnapshot],
) -> bool:
    """Best-effort index refresh so restored files do not remain staged."""
    tracked_paths = [
        str(snapshot.path.relative_to(project_path))
        for snapshot in snapshots
        if snapshot.path.exists() or snapshot.existed
    ]
    if not tracked_paths:
        return True

    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "add", "-A", *tracked_paths],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True

    click.secho(
        "⚠️  Rollback restored files, but QuickScale could not refresh the git index.",
        fg="yellow",
        err=True,
    )
    if result.stderr:
        click.echo(result.stderr.strip(), err=True)
    return False


def _commit_contract_adoption() -> None:
    """Commit the recorded contract adoption so the tree stays clean.

    ``git subtree pull`` refuses to run on a tree with tracked modifications,
    so the adoption record is written only after the module mutations and
    committed here; the next command's clean-tree check then passes too.
    """
    state_path = Path(".quickscale") / "state.yml"
    commit_message = "chore: record generated-project contract adoption"
    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "add", str(state_path)],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
        cached_diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            text=True,
        )
        if cached_diff.returncode == 0:
            return
        if cached_diff.returncode != 1:
            raise _git_errors.GitError(
                "Failed to inspect staged changes before recording contract adoption"
            )
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "commit", "-m", commit_message],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise _git_errors.GitError(
            f"Failed to commit the recorded contract adoption: {e.stderr}"
        )


def _regenerate_and_record_managed_wiring(
    project_path: Path,
    project_package: str,
    state: Any,
) -> tuple[bool, str]:
    """Regenerate the managed wiring after every module pull and hash it.

    Runs once per update, after all module pulls succeeded: regeneration
    validates every embedded manifest against the running core version, so a
    half-updated mixed-version set would fail mid-update.  The pre-update
    wiring is restored when regeneration fails — including a failure while
    recording the refreshed hash records — so an aborted update never leaves
    a half-written settings file or a wiring/state mismatch.

    The managed-file hash records are refreshed in the caller's in-memory
    *state* and saved by the set's single ``state.yml`` write (SA319 (b)), so
    ``quickscale status`` does not report QuickScale's own regeneration as
    drift.
    """
    package_root = project_path / project_package
    wiring_paths = (
        package_root / "settings" / "modules.py",
        package_root / "urls_modules.py",
        package_root / "quickscale_managed",
        *(
            project_path / relative
            for relative in _project_state_hashes.DEFAULT_MANAGED_PROJECT_PATHS
        ),
    )
    with TemporaryDirectory(prefix="quickscale-update-wiring-") as backup_dir:
        snapshots = [
            _snapshot_update_path(path, Path(backup_dir), f"managed-{index}")
            for index, path in enumerate(wiring_paths)
        ]
        try:
            success, message = _module_wiring_manager.regenerate_managed_wiring(
                project_path,
                project_package=project_package,
            )
            if not success:
                _restore_update_snapshots(snapshots)
                return False, message
            _record_managed_wiring_hashes(state, project_path, project_package)
        except Exception as error:  # noqa: BLE001 - restore before surfacing
            _restore_update_snapshots(snapshots)
            return False, str(error)
    return True, message


def _refresh_update_lockfile(project_path: Path) -> bool:
    """Refresh ``poetry.lock`` after the module set's dependency entries change.

    Runs once, after every subtree pull and dependency repin, so the lock
    describes the whole updated set instead of an intermediate mix.  A project
    without ``pyproject.toml`` has no Poetry lock to refresh and passes.
    """
    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.exists():
        click.echo("  • No pyproject.toml detected; skipping poetry.lock refresh.")
        return True

    click.echo("\n📦 Refreshing poetry.lock...")
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["poetry", "lock"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            text=True,
            env=_poetry_env.build_isolated_poetry_env(),
        )
    except OSError as error:
        click.secho(
            f"❌ Failed to run 'poetry lock': {error}",
            fg="red",
            err=True,
        )
        click.echo(
            "💡 Install Poetry and retry, or run 'poetry lock' in the project "
            "before committing.",
            err=True,
        )
        return False

    if result.returncode != 0:
        click.secho("❌ Failed to refresh poetry.lock", fg="red", err=True)
        if result.stderr:
            click.echo(result.stderr.strip(), err=True)
        click.echo(
            "💡 Resolve the dependency error, then run 'poetry lock' in the project.",
            err=True,
        )
        return False

    click.secho("  ✅ poetry.lock refreshed", fg="green")
    return True


def _record_managed_wiring_hashes(
    state: Any,
    project_path: Path,
    project_package: str,
) -> None:
    """Record the regenerated wiring's hashes in the caller's state object.

    The caller loads state once for the whole module set and saves it once
    (SA319 (b)); this helper only refreshes the hash records in memory.
    """
    _project_state_hashes.record_managed_file_hashes(
        state.managed_files, project_path, project_package
    )


def _git_tracks_path(path: Path) -> bool:
    """Return whether git tracks any file under *path*."""
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "ls-files", "--", str(path)],  # noqa: S607 - PATH-resolved executable by design
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def _path_in_commit(project_path: Path, commit: str, path: str) -> bool:
    """Return whether *commit* holds any file under *path*."""
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "ls-tree", "--name-only", commit, "--", path],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def _commit_exists(project_path: Path, commit: str) -> bool:
    """Return whether *commit* resolves to a commit in this repository."""
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _is_ancestor(project_path: Path, ancestor: str) -> bool:
    """Return whether *ancestor* is reachable from the current HEAD."""
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _commit_module_update_set(
    module_names: list[str],
    project_package: str | None,
    *,
    transaction_id: str | None = None,
) -> None:
    """Commit the whole updated module set once (SA319 (b)).

    ``git subtree pull`` creates its own transport commit per module; this
    single commit carries the set's metadata: every pulled module prefix, the
    refreshed ``pyproject.toml``/``poetry.lock``, the surviving legacy
    tracking file, the one authoritative ``state.yml`` write, and the
    regenerated managed wiring and hash records.  The update journal is never
    staged.
    """
    tracked_paths: list[str] = [f"modules/{name}" for name in module_names]
    package_root = Path(project_package) if project_package else None
    managed_paths: list[Path] = [
        Path(".quickscale") / "config.yml",
        Path(".quickscale") / "state.yml",
        Path("pyproject.toml"),
        Path("poetry.lock"),
    ]
    if package_root is not None:
        managed_paths.extend(
            [
                package_root / "settings" / "modules.py",
                package_root / "urls_modules.py",
                package_root / "quickscale_managed",
                *(
                    Path(relative)
                    for relative in _project_state_hashes.DEFAULT_MANAGED_PROJECT_PATHS
                ),
            ]
        )
    for managed_path in managed_paths:
        # A path that no longer exists but is tracked must be staged so a
        # regeneration that removes a managed file commits its deletion.
        if managed_path.exists() or _git_tracks_path(managed_path):
            tracked_paths.append(str(managed_path))
    if not tracked_paths:
        return

    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "add", "-A", "--", *tracked_paths],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise _git_errors.GitError(
            f"Failed to stage the updated module set: {e.stderr}"
        )

    cached_diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],  # noqa: S607 - PATH-resolved executable by design
        capture_output=True,
        text=True,
    )
    if cached_diff.returncode == 0:
        click.echo("ℹ️  No staged module-set changes detected; skipping commit")
        return
    if cached_diff.returncode != 1:
        raise _git_errors.GitError(
            "Failed to inspect staged changes before the module-set commit"
        )

    commit_message = "chore(modules): update installed modules"
    if transaction_id:
        commit_message += f"\n\nQS-Update-Transaction: {transaction_id}"
    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "commit", "-m", commit_message],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise _git_errors.GitError(
            f"Failed to commit the updated module set: {e.stderr}"
        )


def _roll_back_partial_module_update(
    project_path: Path,
    pre_update_head: str,
    updated_modules: list[str],
    project_package: str | None = None,
) -> bool:
    """Restore module trees and tracking files from a pre-update commit.

    The update flow uses this with an empty module list to restore the
    transaction's tracking files (state, legacy config, pyproject, lock, and
    managed wiring) to the journal's baseline before it resumes a set.
    Passing module names also restores those trees and is used by focused
    recovery tests; the restoration is committed when it stages changes.

    Returns ``True`` when the pre-update content was restored (including the
    case where nothing needed restoring), and ``False`` when the restoration
    failed.  A caller that holds the update journal keeps it on ``False`` so
    the next run can retry the recovery.
    """
    if not pre_update_head:
        return True

    restore_paths = [f"modules/{name}" for name in updated_modules]
    if project_package:
        restore_paths.extend(
            [
                f"{project_package}/settings/modules.py",
                f"{project_package}/urls_modules.py",
                f"{project_package}/quickscale_managed",
                *_project_state_hashes.DEFAULT_MANAGED_PROJECT_PATHS,
            ]
        )
    restore_paths.extend(
        [
            ".quickscale/state.yml",
            ".quickscale/config.yml",
            "pyproject.toml",
            "poetry.lock",
        ]
    )

    try:
        # A failed wiring regeneration can leave a managed file the pre-update
        # commit does not track (the theme seam declaration):
        # ``git rm --ignore-unmatch`` leaves an untracked file in the worktree,
        # so clear the managed project paths first.  Paths the pre-update
        # commit does track are restored by the checkout below.
        for relative in _project_state_hashes.DEFAULT_MANAGED_PROJECT_PATHS:
            _remove_update_path(project_path / relative)
        # A lockfile the pre-update commit does not track must disappear too;
        # ``git rm --ignore-unmatch`` leaves an untracked file in place.
        if not _path_in_commit(project_path, pre_update_head, "poetry.lock"):
            _remove_update_path(project_path / "poetry.lock")

        # Remove every path a successful pull or a failed wiring commit may
        # have added or staged, then restore the pre-update content: a plain
        # checkout keeps files that exist only in the newer commit, and a
        # staged-but-uncommitted wiring change would otherwise ride into the
        # rollback commit.
        for path in restore_paths:
            subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
                [  # noqa: S607 - PATH-resolved executable by design
                    "git",
                    "rm",
                    "-r",
                    "-f",
                    "-q",
                    "--ignore-unmatch",
                    "--",
                    path,
                ],
                cwd=project_path,
                check=True,
                capture_output=True,
                text=True,
            )
        restore_from_head = [
            path
            for path in restore_paths
            if _path_in_commit(project_path, pre_update_head, path)
        ]
        if restore_from_head:
            subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
                ["git", "checkout", pre_update_head, "--", *restore_from_head],  # noqa: S607 - PATH-resolved executable by design
                cwd=project_path,
                check=True,
                capture_output=True,
                text=True,
            )
        cached_diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        if cached_diff.returncode == 0:
            return True
        if cached_diff.returncode != 1:
            raise _git_errors.GitError(
                "Failed to inspect staged changes before the rollback commit"
            )
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "commit", "-m", "chore: roll back partial module update"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, _git_errors.GitError) as error:
        click.secho(
            "⚠️  Failed to roll back the modules updated before the failure; "
            "reconcile the module set before serving.",
            fg="yellow",
            err=True,
        )
        detail = getattr(error, "stderr", "")
        if detail:
            click.echo(detail.strip(), err=True)
        return False
    return True
