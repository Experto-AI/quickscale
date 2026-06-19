"""Apply pipeline step model and recovery ledger for QuickScale.

This package exposes the :class:`~quickscale_core.apply.step.ApplyStep`
dataclass and the ordered registry
:data:`~quickscale_core.apply.step.APPLY_STEPS` that enumerate the 15
canonical steps of the ``quickscale apply`` command.

The :func:`~quickscale_core.apply.step.step_by_id` helper provides
O(n) lookup by stable step id when needed; import it directly from
this package for convenience.

F12.1b adds the recovery-ledger schema and loader:
:class:`~quickscale_core.apply.ledger.RecoveryLedger`,
:class:`~quickscale_core.apply.ledger.StepProgress`,
:class:`~quickscale_core.apply.ledger.LedgerManager`, and
:class:`~quickscale_core.apply.ledger.LedgerError`.
"""

from quickscale_core.apply.ledger import (
    LedgerError,
    LedgerManager,
    RecoveryLedger,
    StepProgress,
)
from quickscale_core.apply.step import APPLY_STEPS, ApplyStep, step_by_id

__all__ = [
    "APPLY_STEPS",
    "ApplyStep",
    "LedgerError",
    "LedgerManager",
    "RecoveryLedger",
    "StepProgress",
    "step_by_id",
]
