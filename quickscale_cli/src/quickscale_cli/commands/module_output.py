"""Output helpers shared by QuickScale module commands."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import click

from quickscale_core.utils.git_utils import GitError
from quickscale_core.utils.theme_validation import (
    ThemeValidationError,
    validate_theme_preflight,
)

from .module_config import ModuleExecutionMode


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


def _report_local_pre_pull_guard_block(
    module_name: str,
    lines: list[str],
) -> None:
    """Report a bounded local pre-pull guard block for module update."""
    click.secho(
        f"⚠️  Pre-pull local guard blocked update for {module_name}",
        fg="yellow",
        err=True,
        bold=True,
    )
    for line in lines:
        click.echo(line, err=True)


def _validate_embed_theme(project_path: Path) -> bool:
    """Run the read-only theme preflight for module embedding."""
    try:
        validate_theme_preflight(project_path)
    except ThemeValidationError as exc:
        click.secho(
            "\n❌ Theme validation failed for module embed:\n"
            + "\n".join(f"  • {line}" for line in str(exc).splitlines()),
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(
            "\n💡 Update project.theme to 'showcase_react' in all present "
            "configuration files before embedding modules.",
            err=True,
        )
        return False
    return True


def _resolve_embed_source_ref(
    remote: str,
    selected_ref: str,
    module: str,
    execution_mode: ModuleExecutionMode,
    resolver: Callable[[str, str], str],
) -> tuple[bool, str | None]:
    """Resolve the selected embed ref for both standalone and apply modes."""
    del execution_mode
    try:
        return True, resolver(remote, selected_ref)
    except GitError as ref_error:
        click.secho(
            f"❌ Failed to resolve source ref for {module}: {ref_error}",
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(
            "💡 Check network connectivity and the selected remote ref availability.",
            err=True,
        )
        return False, None


def _report_missing_split_tag(
    module: str,
    core_version: str,
    selected_tag: str,
    remote: str,
) -> None:
    """Report that the immutable split for the running core is unpublished."""
    click.secho(
        f"❌ Module '{module}' split for core version {core_version} was not published.",
        fg="red",
        err=True,
        bold=True,
    )
    click.echo(
        f"   Expected immutable tag: {selected_tag}\n   Remote: {remote}",
        err=True,
    )
    click.echo(
        "\n💡 Publish the split for this core version before embedding the module; "
        "QuickScale will not fall back to a moving branch.",
        err=True,
    )


def _report_split_ref_override(module: str, split_ref: str) -> None:
    """Display the maintainer-only warning for an explicit split ref."""
    click.secho(
        f"⚠️  Using explicit split ref override for {module}: {split_ref}\n"
        "   Maintainer/pre-seal use only; this bypasses the sealed core-version "
        "tag and must not be treated as a published immutable release.",
        fg="yellow",
        bold=True,
    )
