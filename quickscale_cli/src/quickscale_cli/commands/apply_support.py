"""Small support helpers for the apply command.

The command module keeps the public Click surface and orchestration flow;
helpers that only prepare subprocess context live here to keep that
coordinator focused and easy to audit.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import click
import yaml


def _build_quickscale_env() -> dict[str, str]:
    """Build the environment used by nested QuickScale CLI subprocesses.

    Source-tree entries on ``sys.path`` are propagated only to nested
    ``quickscale_cli.main`` calls.  Foreign subprocesses continue to inherit
    their normal environment from the caller.
    """
    extra_paths: list[str] = []
    for path in sys.path:
        if not path or path == ".":
            continue
        path_obj = Path(path)
        if not path_obj.is_dir():
            continue
        if (path_obj / "quickscale_core").is_dir() or (
            path_obj / "quickscale_cli"
        ).is_dir():
            extra_paths.append(path)

    if not extra_paths:
        return os.environ.copy()

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    combined = os.pathsep.join(extra_paths)
    if existing:
        combined = existing + os.pathsep + combined
    env["PYTHONPATH"] = combined
    return env


def _resolve_apply_raw_root(config_path: Path) -> Path:
    """Resolve the output root from a best-effort raw config parse."""
    try:
        raw_config = yaml.safe_load(config_path.read_text())
    except Exception:
        return config_path.resolve().parent

    if not isinstance(raw_config, Mapping):
        return config_path.resolve().parent
    project_raw = raw_config.get("project")
    if not isinstance(project_raw, Mapping):
        return config_path.resolve().parent

    slug = str(project_raw.get("slug") or "")
    if not slug:
        return config_path.resolve().parent
    resolved_config = config_path.resolve()
    if resolved_config.parent.name == slug:
        return resolved_config.parent
    return Path.cwd() / slug


def _report_theme_preflight_error(error: ValueError) -> None:
    """Render the stable CLI error for a failed theme preflight."""
    click.secho("\n❌ Theme validation failed:", fg="red", err=True, bold=True)
    for line in str(error).splitlines():
        click.echo(f"  • {line}", err=True)
    click.echo(
        "\n💡 Update project.theme to 'showcase_react' in all present "
        "configuration files before running 'quickscale apply'.",
        err=True,
    )


def _confirm_apply(ctx: Any, *, no_docker: bool, verbose_docker: bool) -> bool:
    """Collect confirmation choices without mutating the project."""
    show_docker_output = verbose_docker
    if (
        not no_docker
        and ctx.qs_config.docker.start
        and ctx.qs_config.docker.build
        and not verbose_docker
    ):
        show_docker_output = click.confirm(
            "\n🐳 Show Docker build output? (useful for debugging build issues)",
            default=False,
        )

    if not click.confirm("\n❓ Proceed with apply?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()
    return show_docker_output
