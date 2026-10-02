"""Module-update snapshots, commits, and wiring persistence helpers.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import click

from quickscale_cli.commands._module_shared import _UpdatePathSnapshot
import quickscale_cli.commands.module_commands as _module_commands


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
        _module_commands._remove_update_path(snapshot.path)
        return

    if snapshot.backup_path is None:
        raise RuntimeError(f"Missing rollback payload for {snapshot.path}")

    _module_commands._remove_update_path(snapshot.path)
    if snapshot.is_dir:
        shutil.copytree(snapshot.backup_path, snapshot.path)
        return

    snapshot.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot.backup_path, snapshot.path)


def _restore_update_snapshots(snapshots: list[_UpdatePathSnapshot]) -> None:
    """Restore all module update snapshots in reverse mutation order."""
    for snapshot in reversed(snapshots):
        _module_commands._restore_update_snapshot(snapshot)


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
    ]
    return [
        _module_commands._snapshot_update_path(path, backup_root, label)
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
            raise _module_commands.GitError(
                "Failed to inspect staged changes before recording contract adoption"
            )
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "commit", "-m", commit_message],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise _module_commands.GitError(
            f"Failed to commit the recorded contract adoption: {e.stderr}"
        )


def _regenerate_and_record_managed_wiring(
    project_path: Path,
    project_package: str,
) -> tuple[bool, str]:
    """Regenerate the managed wiring after every module pull and hash it.

    Runs once per update, after all module pulls succeeded: regeneration
    validates every embedded manifest against the running core version, so a
    half-updated mixed-version set would fail mid-update.  The pre-update
    wiring is restored when regeneration fails — including a failure while
    persisting the refreshed hash records — so an aborted update never leaves
    a half-written settings file or a wiring/state mismatch.  The managed-file
    hash records are refreshed so ``quickscale status`` does not report
    QuickScale's own regeneration as drift.
    """
    package_root = project_path / project_package
    wiring_paths = (
        package_root / "settings" / "modules.py",
        package_root / "urls_modules.py",
        package_root / "quickscale_managed",
    )
    with TemporaryDirectory(prefix="quickscale-update-wiring-") as backup_dir:
        snapshots = [
            _module_commands._snapshot_update_path(
                path, Path(backup_dir), f"managed-{index}"
            )
            for index, path in enumerate(wiring_paths)
        ]
        try:
            success, message = _module_commands.regenerate_managed_wiring(
                project_path,
                project_package=project_package,
            )
            if not success:
                _module_commands._restore_update_snapshots(snapshots)
                return False, message
            _module_commands._record_managed_wiring_hashes(
                project_path, project_package
            )
        except Exception as error:  # noqa: BLE001 - restore before surfacing
            _module_commands._restore_update_snapshots(snapshots)
            return False, str(error)
    return True, message


def _record_managed_wiring_hashes(
    project_path: Path,
    project_package: str,
) -> None:
    """Record the regenerated wiring's hashes in the authoritative state."""
    state_manager = _module_commands.StateManager(project_path)
    state = state_manager.load()
    if state is None:
        return

    managed_paths = [
        f"{project_package}/{relative}"
        for relative in _module_commands.DEFAULT_MANAGED_WIRING_PATHS
    ]
    for path_str, digest in _module_commands.compute_file_hashes(
        project_path, managed_paths
    ).items():
        state.managed_files[path_str] = _module_commands.ManagedFileRecord(
            path=path_str,
            hash=digest,
        )
    state_manager.save(state)


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


def _commit_regenerated_managed_wiring(project_package: str) -> None:
    """Commit regenerated managed wiring and its refreshed hash records."""
    tracked_paths: list[str] = []
    package_root = Path(project_package)
    for wiring_path in (
        package_root / "settings" / "modules.py",
        package_root / "urls_modules.py",
        package_root / "quickscale_managed",
    ):
        # A path that no longer exists but is tracked must be staged so a
        # regeneration that removes a managed file commits its deletion.
        if wiring_path.exists() or _module_commands._git_tracks_path(wiring_path):
            tracked_paths.append(str(wiring_path))
    state_path = Path(".quickscale") / "state.yml"
    if state_path.exists():
        tracked_paths.append(str(state_path))
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
        raise _module_commands.GitError(
            f"Failed to stage regenerated managed wiring: {e.stderr}"
        )

    cached_diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],  # noqa: S607 - PATH-resolved executable by design
        capture_output=True,
        text=True,
    )
    if cached_diff.returncode == 0:
        return
    if cached_diff.returncode != 1:
        raise _module_commands.GitError(
            "Failed to inspect staged changes before the wiring commit"
        )

    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "commit", "-m", "chore: regenerate managed module wiring"],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise _module_commands.GitError(
            f"Failed to commit regenerated managed wiring: {e.stderr}"
        )


def _roll_back_partial_module_update(
    project_path: Path,
    pre_update_head: str,
    updated_modules: list[str],
    project_package: str | None = None,
) -> None:
    """Restore already-committed pulls and wiring after a post-pull failure.

    ``update`` commits each successful module pull before continuing, so a
    later failure would otherwise leave the earlier modules' new code paired
    with the pre-update managed wiring.  Restoring the updated module trees,
    the managed wiring, and the tracking files the update touched from the
    commit that preceded the update keeps the project coherent; the
    restoration is committed so the tree stays clean for the operator's next
    command.
    """
    if not updated_modules or not pre_update_head:
        return

    restore_paths = [f"modules/{name}" for name in updated_modules]
    if project_package:
        restore_paths.extend(
            [
                f"{project_package}/settings/modules.py",
                f"{project_package}/urls_modules.py",
                f"{project_package}/quickscale_managed",
            ]
        )
    restore_paths.extend(
        [
            ".quickscale/state.yml",
            ".quickscale/config.yml",
            "pyproject.toml",
        ]
    )

    try:
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
            if _module_commands._path_in_commit(project_path, pre_update_head, path)
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
        if cached_diff.returncode != 1:
            return
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "commit", "-m", "chore: roll back partial module update"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        click.secho(
            "⚠️  Failed to roll back the modules updated before the failure; "
            "reconcile with 'quickscale apply' before serving.",
            fg="yellow",
            err=True,
        )
        if error.stderr:
            click.echo(error.stderr.strip(), err=True)


def _commit_module_update(module_name: str, module_prefix: str) -> None:
    """Create a commit for a successfully updated module."""
    tracked_paths = [module_prefix]
    config_path = Path(".quickscale") / "config.yml"
    if config_path.exists():
        tracked_paths.append(str(config_path))
    state_path = Path(".quickscale") / "state.yml"
    if state_path.exists():
        tracked_paths.append(str(state_path))
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        tracked_paths.append(str(pyproject_path))

    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "add", *tracked_paths],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise _module_commands.GitError(
            f"Failed to stage {module_name} update commit: {e.stderr}"
        )

    cached_diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],  # noqa: S607 - PATH-resolved executable by design
        capture_output=True,
        text=True,
    )

    if cached_diff.returncode == 0:
        click.echo(f"ℹ️  No staged changes detected for {module_name}; skipping commit")
        return

    if cached_diff.returncode != 1:
        raise _module_commands.GitError(
            "Failed to inspect staged changes before module update commit"
        )

    commit_message = f"chore(modules): update {module_name} module"
    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "commit", "-m", commit_message],  # noqa: S607 - PATH-resolved executable by design
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise _module_commands.GitError(
            f"Failed to commit {module_name} update: {e.stderr}"
        )
