"""Module embedding step adapters.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import click


from quickscale_cli.commands._module_shared import ModuleEmbedProvenance
from quickscale_core.schema.state_schema import (
    QuickScaleState,
)

# AF6 Phase 2 — core step bodies
from quickscale_cli.commands._types import EmbedModulesResult

import quickscale_core.apply.steps.types as _types
import quickscale_core.apply.steps as _steps
import quickscale_cli.commands._types as _types_2
import quickscale_cli.commands._module_shared as _module_shared
import quickscale_cli.commands._module_embed as _module_embed
import quickscale_cli.commands._git_ops as _git_ops
import quickscale_core.utils.git_repo as _git_repo


def _embed_module(
    project_path: Path,
    module_name: str,
    skip_auth_migration_check: bool = False,
    provenance_sink: list[ModuleEmbedProvenance] | None = None,
    split_ref: str | None = None,
) -> bool:
    """Embed a module using the embed_module function with non-interactive mode"""
    click.echo(f"⏳ Embedding module: {module_name}...")

    try:
        embed_kwargs: dict[str, Any] = {
            "module": module_name,
            "project_path": project_path,
            "non_interactive": True,
            "allow_unverifiable_auth_state": True,
            "skip_auth_migration_check": skip_auth_migration_check,
            "sync_dependencies": False,
            "install_dependencies": False,
            "execution_mode": _module_shared.APPLY_MODULE_EXECUTION_MODE,
            "provenance_sink": provenance_sink,
        }
        if split_ref is not None:
            embed_kwargs["split_ref"] = split_ref
        success = _module_embed.embed_module(
            **embed_kwargs,
        )

        if success:
            click.secho(f"✅ Module embedded: {module_name}", fg="green")
            return True
        else:
            click.secho(f"❌ Failed to embed module: {module_name}", fg="red", err=True)
            return False
    except Exception as e:
        click.secho(f"❌ Unexpected error embedding module: {e}", fg="red", err=True)
        return False


def _embed_modules_step(
    output_path: Path,
    modules_to_embed: list[str],
    no_modules: bool,
    existing_state: QuickScaleState | None,
    split_ref_overrides: Mapping[str, str] | None = None,
) -> EmbedModulesResult:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    if no_modules or not modules_to_embed:
        if existing_state and not modules_to_embed:
            click.echo("⏭️  No new modules to embed")
        return _types_2.EmbedModulesResult(success=True, embedded_modules=[])

    step_ctx = _types.StepContext(
        output_path=output_path,
        existing_state=existing_state,
    )

    overrides = split_ref_overrides or {}

    def _embed_one_module(
        path: Path,
        module_name: str,
        *,
        skip_auth_migration_check: bool,
        provenance_sink: list[ModuleEmbedProvenance] | None,
    ) -> bool:
        embed_kwargs: dict[str, Any] = {
            "skip_auth_migration_check": skip_auth_migration_check,
            "provenance_sink": provenance_sink,
        }
        if module_name in overrides:
            embed_kwargs["split_ref"] = overrides[module_name]
        return _embed_module(
            path,
            module_name,
            **embed_kwargs,
        )

    outcome = _steps.step_embed_modules(
        step_ctx,
        modules_to_embed=modules_to_embed,
        no_modules=no_modules,
        embed_one_module=_embed_one_module,
        commit_changes=_git_ops._git_commit,
        is_working_directory_clean_fn=_git_repo.is_working_directory_clean,
    )

    if outcome.success:
        return _types_2.EmbedModulesResult(
            success=True,
            embedded_modules=step_ctx.embedded_modules,
            provenance_payloads=(
                step_ctx.provenance_payloads if step_ctx.provenance_payloads else None
            ),
        )

    # Failure path — distinguish hard-stop (commit failure) from soft-stop
    # (embed failure) to match historical behavior expected by tests.
    if step_ctx.embed_commit_failure:
        raise click.Abort()

    return _types_2.EmbedModulesResult(
        success=False,
        embedded_modules=step_ctx.embedded_modules,
        failed_module=step_ctx.embed_failed_module,
    )


def _embed_modules_ran_successfully(embed_result: EmbedModulesResult) -> bool:
    """Return ``True`` when modules were actually embedded (not a no-op)."""
    return embed_result.success and bool(embed_result.embedded_modules)
