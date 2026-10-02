"""Shared apply-command types, constants, and pre-embed path predicates.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep
working.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


from quickscale_cli.commands.module_commands import (
    ModuleEmbedProvenance,
)
from quickscale_core.schema.config_schema import (
    QuickScaleConfig,
)
from quickscale_core.schema.delta import ConfigDelta
from quickscale_core.schema.state_schema import (
    QuickScaleState,
    StateManager,
)
from quickscale_core.manifest import ModuleManifest

# AF6 Phase 2 — core step bodies
import quickscale_cli.commands.apply_command as _apply_command


@dataclass
class ApplyContext:
    """Context object for the apply command execution."""

    config_path: Path
    qs_config: QuickScaleConfig
    output_path: Path
    state_manager: StateManager
    existing_state: QuickScaleState | None
    manifests: dict[str, ModuleManifest]
    delta: ConfigDelta
    has_pending_post_embed_recovery: bool = False
    had_existing_state: bool = False
    confirm_contract_adoption: bool = False


@dataclass
class EmbedModulesResult:
    """Result for module embedding step."""

    success: bool
    embedded_modules: list[str]
    failed_module: str | None = None
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None


@dataclass(frozen=True)
class _GitIndexTreeSnapshot:
    """Captured git index tree used to restore apply-owned staging."""

    tree_id: str


_UNSAFE_GITIGNORE_LEADING_CHARACTERS = frozenset({"!", "#"})


_UNSAFE_GITIGNORE_GLOB_CHARACTERS = frozenset({"*", "?", "["})


_APPLY_RECOVERY_FILENAME = "apply-recovery.yml"


_APPLY_RECOVERY_STEM = PurePosixPath(_APPLY_RECOVERY_FILENAME).stem


_AF5_DESTRUCTIVE_CONFIRM_BYPASS: bool = False


_PRE_EMBED_AUTHORITATIVE_GIT_PATHS = (
    "quickscale.yml",
    ".quickscale/state.yml",
    ".quickscale/config.yml",
)


_FAILED_STEP = {
    step.step_id: step.failed_step_label
    for step in _apply_command.APPLY_STEPS
    if step.failed_step_label is not None
}


def _is_pre_embed_authoritative_path(path: str) -> bool:
    """Return whether a path belongs to authoritative QuickScale config state."""
    return path in _PRE_EMBED_AUTHORITATIVE_GIT_PATHS


def _is_transient_apply_recovery_path(path: str) -> bool:
    """Return whether a path is a transient apply-recovery artifact."""
    relative_path = PurePosixPath(path)
    return relative_path.parent == PurePosixPath(
        ".quickscale"
    ) and relative_path.name.startswith(_APPLY_RECOVERY_STEM)


def _is_pre_embed_allowed_dirty_path(path: str) -> bool:
    """Return whether a dirty path is apply-owned and safe to ignore or checkpoint."""
    return _apply_command._is_pre_embed_authoritative_path(
        path
    ) or _apply_command._is_transient_apply_recovery_path(path)


def _get_pre_embed_checkpoint_paths(paths: list[str]) -> list[str]:
    """Return authoritative paths that belong in the synthetic pre-embed commit."""
    path_set = set(paths)
    return [path for path in _PRE_EMBED_AUTHORITATIVE_GIT_PATHS if path in path_set]
