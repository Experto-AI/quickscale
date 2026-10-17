"""Small support helpers for the apply and plan commands.

The command modules keep the public Click surface and orchestration flow;
helpers that only prepare subprocess context, or that both command flows use
to judge and explain module option values, live here to keep those
coordinators focused and easy to audit.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import click
import yaml

from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest.option_validation import validate_module_options
from quickscale_core.schema.config_schema import ConfigValidationError


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


def module_option_issues(
    module_name: str, options: Mapping[str, Any] | None
) -> list[str]:
    """Return one configured module's manifest-declared option issues.

    Every module's values are judged by the checks authored next to the
    option in its ``module.yml`` ``validation`` block, through the same
    engine the generated project's startup check uses, so the CLI holds no
    per-module validation copy.
    """
    return validate_module_options(
        load_module_manifest_with_fallback(module_name), options or {}
    )


def module_adapter_module(module_name: str) -> Any | None:
    """Return a managed module's adapter module, or ``None`` when unreachable.

    Module-owned predicates and guidance are adapter code (Module Conventions
    rule 12).  A context with no importable module source (a bundled-only
    install) cannot load the adapter; callers then render generic guidance
    instead of failing, while the option-validation engine still owns the
    abort.
    """
    try:
        from quickscale_core.contracts.module_discovery import (
            ImproperlyConfigured,
        )
        from quickscale_core.manifest.entry_point import (
            load_managed_adapter_module,
        )
    except ImportError:  # pragma: no cover - core always ships with the CLI
        return None
    try:
        return load_managed_adapter_module(module_name)
    except ImproperlyConfigured:
        return None


#: The generic adapter hook a module's adapter module may implement: the CLI
#: calls it with the module's supplied option values when the manifest's
#: declared checks refuse them, and it returns the module's operator
#: remediation text, or ``None`` to accept the shared hint (Module
#: Conventions rule 37).
_OPTION_VALIDATION_GUIDANCE_HOOK = "option_validation_guidance"


def module_option_guidance(
    module_name: str, options: Mapping[str, Any] | None
) -> str | None:
    """Return the module adapter's remediation text for refused options.

    The CLI reaches module-specific behaviour through this one generic
    adapter hook (Module Conventions rule 37): the adapter module optionally
    defines ``option_validation_guidance(options)``.  ``None`` — a module
    whose adapter defines no hook, an unreachable adapter, or values the hook
    cannot resolve — defers to the shared hint.
    """
    adapter = module_adapter_module(module_name)
    if adapter is None:
        return None
    hook = getattr(adapter, _OPTION_VALIDATION_GUIDANCE_HOOK, None)
    if not callable(hook):
        return None
    try:
        guidance = hook(options or {})
    except ConfigValidationError:
        # The hook is called exactly with values the checks refused, which can
        # include a retired key its resolver refuses in turn; the option
        # refusal owns the abort, so guidance degrades to the shared hint.
        return None
    return str(guidance) if guidance else None


def echo_module_option_abort_hint(
    module_name: str, options: Mapping[str, Any] | None
) -> None:
    """Print the remediation hint for a module's refused option values.

    A module adapter's generic guidance, when present, replaces the shared
    hint: the module owns what its operator must do next.
    """
    guidance = module_option_guidance(module_name, options)
    if guidance is not None:
        click.echo(f"\n💡 {guidance}", err=True)
        return
    click.echo(
        f"\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or "
        f"edit quickscale.yml to correct the {module_name} option values.",
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
