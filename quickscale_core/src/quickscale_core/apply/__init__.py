"""Apply pipeline step model and recovery ledger for QuickScale.

This package exposes the :class:`~quickscale_core.apply.step.ApplyStep`
dataclass and the ordered registry
:data:`~quickscale_core.apply.step.APPLY_STEPS` that enumerate the 16
canonical steps of the ``quickscale apply`` command.

The :func:`~quickscale_core.apply.step.step_by_id` helper provides
O(n) lookup by stable step id when needed; import it directly from
this package for convenience.

F12.1b adds the recovery-ledger schema and loader:
:class:`~quickscale_core.apply.ledger.RecoveryLedger`,
:class:`~quickscale_core.apply.ledger.StepProgress`,
:class:`~quickscale_core.apply.ledger.LedgerManager`, and
:class:`~quickscale_core.apply.ledger.LedgerError`.

AF6 Phase 1 adds the step-extraction boundary at
:mod:`~quickscale_core.apply.steps.types`.  The types re-exported from
this package are forward-looking shims so that Phase 2 callers can
import them via ``quickscale_core.apply`` without changing import paths.

AF6 Phase 2 extracts the 16 apply step bodies into
:mod:`~quickscale_core.apply.steps`.  The step body functions are
re-exported here for Phase 3 callers that need them from the package root.
"""

from quickscale_core.apply.ledger import (
    LedgerError,
    LedgerManager,
    RecoveryLedger,
    StepProgress,
)
from quickscale_core.apply.step import APPLY_STEPS, ApplyStep, step_by_id
from quickscale_core.apply.steps import (
    ApplyStepProtocol,
    EmbedModulesResult,
    GitIndexSnapshot,
    StepContext,
    StepHook,
    StepOutcome,
    StepReporter,
    step_analytics_env_sync,
    step_apply_mutable_config,
    step_backups_gitignore,
    step_billing_env_sync,
    step_capture_hashes,
    step_display_next_steps,
    step_embed_modules,
    step_finalize_state,
    step_notifications_env_sync,
    step_post_embed_snapshot,
    step_post_generation_setup,
    step_railway_deploy,
    step_regenerate_wiring,
    step_run_migrations,
    step_start_docker,
    step_sync_dependencies,
)

__all__ = [
    "APPLY_STEPS",
    "ApplyStep",
    "ApplyStepProtocol",
    "EmbedModulesResult",
    "GitIndexSnapshot",
    "LedgerError",
    "LedgerManager",
    "RecoveryLedger",
    "StepContext",
    "StepHook",
    "StepOutcome",
    "StepProgress",
    "StepReporter",
    "step_analytics_env_sync",
    "step_apply_mutable_config",
    "step_backups_gitignore",
    "step_billing_env_sync",
    "step_by_id",
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
