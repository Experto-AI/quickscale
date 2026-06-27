"""Apply step extraction boundary for QuickScale.

This package defines the core-safe runtime boundary that extracted apply
step bodies must use.  The seam lives at
:mod:`quickscale_core.apply.steps.types` and is the *only* allowed
extraction boundary.

Phase 1 created this scaffolding and the protocol definitions.  Phase 2
extracts the 16 apply step bodies into concern-focused modules.

No imports from ``quickscale_cli`` are permitted anywhere in this package.
"""

from quickscale_core.apply.steps.types import (
    ApplyStepProtocol,
    StepContext,
    StepHook,
    StepOutcome,
    StepReporter,
)

# Step body modules
from quickscale_core.apply.steps.deps import (
    step_post_generation_setup,
    step_sync_dependencies,
)
from quickscale_core.apply.steps.embedding import (
    EmbedModulesResult,
    GitIndexSnapshot,
    step_embed_modules,
    step_post_embed_snapshot,
)
from quickscale_core.apply.steps.env_sync import (
    step_analytics_env_sync,
    step_backups_gitignore,
    step_billing_env_sync,
    step_notifications_env_sync,
)
from quickscale_core.apply.steps.finalize import (
    step_display_next_steps,
    step_finalize_state,
    step_railway_deploy,
)
from quickscale_core.apply.steps.infrastructure import (
    step_apply_mutable_config,
    step_run_migrations,
    step_start_docker,
)
from quickscale_core.apply.steps.wiring import (
    step_capture_hashes,
    step_regenerate_wiring,
)

__all__ = [
    "ApplyStepProtocol",
    "EmbedModulesResult",
    "GitIndexSnapshot",
    "StepContext",
    "StepHook",
    "StepOutcome",
    "StepReporter",
    "step_analytics_env_sync",
    "step_apply_mutable_config",
    "step_backups_gitignore",
    "step_billing_env_sync",
    "step_capture_hashes",
    "step_display_next_steps",
    "step_embed_modules",
    "step_finalize_state",
    "step_notifications_env_sync",
    "step_post_embed_snapshot",
    "step_post_generation_setup",
    "step_railway_deploy",
    "step_regenerate_wiring",
    "step_run_migrations",
    "step_start_docker",
    "step_sync_dependencies",
]
