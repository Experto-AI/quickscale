"""Shared module-command types, environment checks, and state helpers.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import click


import quickscale_cli.utils.auth_migration as _auth_migration
import quickscale_cli.utils._dependency_io as _dependency_io
import quickscale_core.manifest.loader as _loader
import quickscale_core.config as _config
import quickscale_core.schema.state_schema as _state_schema
import quickscale_core.project_state_manager as _project_state_manager
import quickscale_core.project_state_drift as _project_state_drift
import quickscale_core.contracts.module_catalog as _module_catalog
import quickscale_core.utils.git_repo as _git_repo
import datetime as _datetime

ModuleExecutionMode = Literal["standalone", "apply"]


STANDALONE_MODULE_EXECUTION_MODE: ModuleExecutionMode = "standalone"


APPLY_MODULE_EXECUTION_MODE: ModuleExecutionMode = "apply"


class _LazyModuleChoice(click.Choice):
    """A :class:`click.Choice` subclass that resolves module names lazily.

    Defers the call to :func:`get_discovered_module_names` until the first
    time the choices are actually accessed (during CLI argument parsing).
    All ``click.Choice`` behaviours — case-insensitive canonicalisation,
    help metavar rendering, and invalid-choice diagnostics — are preserved.
    """

    def __init__(self) -> None:
        # Intentionally skip ``super().__init__()`` — we expose ``choices``
        # via a property that resolves lazily and provide a setter so that
        # Click's internal ``self.choices = ...`` in its own ``__init__`` is
        # not required.
        self.case_sensitive = False
        self._resolved_choices: list[str] | None = None

    @property  # type: ignore[override]
    def choices(self) -> list[str]:
        if self._resolved_choices is None:
            from quickscale_core.contracts.module_catalog import (
                get_discovered_module_names,
            )

            self._resolved_choices = get_discovered_module_names()
        return self._resolved_choices

    @choices.setter
    def choices(self, value: object) -> None:
        if value is None:
            self._resolved_choices = None
        elif isinstance(value, list):
            self._resolved_choices = [str(v) for v in value]
        else:
            self._resolved_choices = [str(value)]


@dataclass(frozen=True)
class _UpdatePathSnapshot:
    """Filesystem snapshot used to roll back module update mutations."""

    path: Path
    backup_path: Path | None
    existed: bool
    is_dir: bool


@dataclass(frozen=True)
class ModuleEmbedProvenance:
    """Per-module provenance payload for the apply-side handoff seam.

    Carries the exact source ref (commit SHA) resolved once per module add
    during apply, along with the tracking metadata needed by later phases
    for state/recovery persistence.  The same ``source_ref`` value is used
    for both the subtree add operation and the in-memory handoff so that
    the embedded content and the recorded provenance cannot drift.
    """

    module_name: str
    prefix: str
    tracking_branch: str
    source_ref: str
    installed_version: str
    selected_ref: str | None = None


def _validate_git_environment() -> bool:
    """Validate git repository state for module operations.

    Returns:
        True if valid, False otherwise
    """
    if not _git_repo.is_git_repo():
        click.secho("❌ Error: Not a git repository", fg="red", err=True)
        click.echo("\n💡 Tip: Run 'git init' to initialize a git repository", err=True)
        return False

    if not _git_repo.is_working_directory_clean():
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
    """Legacy branch probe retained for source compatibility.

    Embed selection no longer calls this helper; immutable tag selection owns
    the embed remote contract. Existing integrations may still import the
    private helper, so keep its historical diagnostic behavior isolated here.
    """
    click.echo(f"🔍 Checking if {branch} exists on remote...")
    if not _git_repo.check_remote_branch_exists(remote, branch):
        click.secho(
            f"❌ Error: Module '{module}' is not yet implemented",
            fg="red",
            err=True,
        )
        click.echo(
            f"\n📖 Branch '{branch}' does not exist on remote: {remote}",
            err=True,
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
    assessment = _auth_migration.assess_auth_migration_state(project_path)
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
        click.echo(_auth_migration.format_auth_migration_remediation(project_path))
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
    click.echo(_auth_migration.format_auth_migration_remediation(project_path))

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
    return _dependency_io.resolve_embedded_module_install_path(project_path, module)


def _read_embedded_module_version(project_path: Path, module: str) -> str:
    """Read the canonical installed version from the embedded module manifest.

    Raises:
        ManifestError: If the manifest cannot be loaded or is invalid.
        ModuleVersionMismatchError: If the manifest version is older than the
            current core version.
    """
    manifest = _loader.get_manifest_for_module(project_path, module, strict=True)
    assert manifest is not None  # noqa: S101 - internal invariant guaranteed by the caller
    _loader.assert_manifest_version_matches_core(manifest.version, module)
    normalized = _config.normalize_installed_version(manifest.version)
    return normalized or manifest.version


def _sync_state_module_version(
    project_path: Path,
    module: str,
    version: str,
    *,
    commit_sha: str | None = None,
) -> None:
    """Mirror embedded module versions and provenance into applied state.

    Updates ``state.modules[module].version`` and, when *commit_sha* is
    provided, ``state.modules[module].commit_sha``.  The ``embedded_at``
    timestamp is always refreshed to reflect the current update so the
    full provenance triple (version, commit_sha, embedded_at) stays
    consistent.  The state file must already contain the module entry;
    modules absent from state are silently skipped (callers should ensure
    state is materialized first).
    """
    state_manager = _state_schema.StateManager(project_path)
    state = state_manager.load()
    if state is None or module not in state.modules:
        return

    state.modules[module].version = version
    if commit_sha is not None:
        state.modules[module].commit_sha = commit_sha
    state.modules[module].embedded_at = _datetime.datetime.now().isoformat()
    state_manager.save(state)


def _warn_version_drift_for_update(
    project_path: Path,
    config: Any,
) -> list[Any]:
    """Surface module version drift between state and legacy config.

    The drift between ``.quickscale/state.yml`` and ``.quickscale/config.yml``
    is non-fatal: the update flow rewrites both sources, so warnings here
    are informational. They signal that an external process changed
    ``config.yml`` after the last apply.
    """
    manager = _project_state_manager.ProjectStateManager(project_path)
    try:
        state = manager.load_state()
    except _state_schema.StateError as error:
        click.secho(
            f"⚠️  Could not read .quickscale/state.yml for drift check: {error}",
            fg="yellow",
        )
        return []

    drift = _project_state_drift.check_version_drift(state, config)
    if not drift:
        return []

    click.secho(
        "\n⚠️  Module version drift between .quickscale/state.yml and "
        ".quickscale/config.yml:",
        fg="yellow",
        bold=True,
    )
    for warning in drift:
        click.echo(f"  • {warning.message}")
    click.echo(
        "\n💡 Update will reconcile .quickscale/config.yml to the freshly "
        "installed state-managed version. The drift is informational and not fatal.",
    )
    return drift


def _validate_module_readiness(
    module: str,
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> bool:
    """Reject non-public modules from standalone embed/update flows."""
    readiness_reason = _module_catalog.get_module_readiness_reason(module)
    if readiness_reason is None:
        return True

    click.secho(f"❌ Error: {readiness_reason}", fg="red", err=True)
    click.echo(
        "\n💡 Placeholder directories remain in the repository for documentation and "
        "future work only.",
        err=True,
    )
    return False


def _validate_update_environment() -> None:
    """Validate git environment for update command.

    Raises:
        click.Abort: If validation fails
    """
    if not _git_repo.is_git_repo():
        click.secho("❌ Error: Not a git repository", fg="red", err=True)
        click.echo("\n💡 Tip: This command must be run from a git repository", err=True)
        raise click.Abort()

    if not _git_repo.is_working_directory_clean():
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
