"""AF5 Phase 2/4: Per-step satisfaction/apply executor with post-step checkpoint flow.

The :class:`ApplyExecutor` reads the recovery ledger, determines which steps
are already satisfied, executes unsatisfied steps through injected callbacks,
and writes checkpoint progress after each step.

Design invariants
-----------------
* **Satisfaction is driven by the ResumeCheckpoint.**  When the ledger carries
  a ``resume_checkpoint``, the executor begins at that step.  When the ledger
  is absent or the checkpoint is ``None``, the executor begins at step 1.
* **Step progress is diagnostic-only.**  The executor writes ``StepProgress``
  entries for observability, but resume gating is on ``ResumeCheckpoint``
  alone — matching the Phase 1 invariant.
* **All 16 steps are checkpointed (AF5 Phase 4).**  Phase 4 extended
  checkpointing from the original non-destructive subset (steps 1-10) to
  cover the full destructive/remote tail (steps 11-16) including Docker
  startup, database migrations, Railway deploy, and finalization.
* **Checkpoint writes are atomic.**  Each call to :meth:`checkpoint_step`
  reads-modifies-writes the ledger file atomically via
  :class:`~quickscale_core.apply.ledger.LedgerManager`.

No imports from ``quickscale_cli`` are permitted here; this module is pure
``quickscale_core`` domain code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from quickscale_core.apply.ledger import (
    LedgerError,
    LedgerManager,
    RecoveryLedger,
    ResumeCheckpoint,
    StepProgress,
)
from quickscale_core.apply.step import APPLY_STEPS, ApplyStep, step_by_id
from quickscale_core.schema.state_schema import QuickScaleState


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def resolve_resume_step(
    resume_checkpoint: ResumeCheckpoint | None,
) -> ApplyStep:
    """Return the first step that needs execution given an optional checkpoint.

    When *resume_checkpoint* is present, returns the step at its
    ``resume_step_id``.  When absent, returns the first step in the registry
    (step 1 — ``"module embedding"``).

    Args:
        resume_checkpoint: The checkpoint from the recovery ledger, or
            ``None`` when no checkpoint exists.

    Returns:
        The :class:`~quickscale_core.apply.step.ApplyStep` to start from.

    Raises:
        LedgerError: If the checkpoint references an unknown step id.
    """
    if resume_checkpoint is not None:
        try:
            return step_by_id(resume_checkpoint.resume_step_id)
        except KeyError as exc:
            raise LedgerError(
                f"Resume checkpoint references unknown step_id="
                f"{resume_checkpoint.resume_step_id!r}"
            ) from exc
    return APPLY_STEPS[0]


def advance_resume_checkpoint(
    current: ResumeCheckpoint | None,
    *,
    completed_step_id: str,
    next_step_id: str | None = None,
    checkpoint_tree_id: str | None = None,
) -> ResumeCheckpoint:
    """Build a :class:`ResumeCheckpoint` that advances past a completed step.

    When *next_step_id* is provided, the returned checkpoint resumes from
    that step.  When omitted, the checkpoint advances one step forward in
    the ordered :data:`~quickscale_core.apply.step.APPLY_STEPS` registry.

    Args:
        current: The existing checkpoint (may be ``None`` for first-time
            checkpoint writes).
        completed_step_id: The step that just completed.
        next_step_id: Optional explicit next step id.  If ``None``, advances
            to the next step in the registry order.
        checkpoint_tree_id: Optional git tree id to capture in the
            checkpoint.

    Returns:
        A new :class:`ResumeCheckpoint` pointing to the next step.
    """
    # Preserve suspend_after from the existing checkpoint when advancing.
    suspend_after = current.suspend_after_step_id if current else None

    if next_step_id is not None:
        resume_id = next_step_id
    else:
        # Advance to the next step in registry order.
        completed_step = step_by_id(completed_step_id)
        next_index = completed_step.order  # 1-based index -> next
        if next_index < len(APPLY_STEPS):
            resume_id = APPLY_STEPS[
                next_index
            ].step_id  # index=order (0-based is order-1)
        else:
            # Already on the last step — stay on the same step.
            resume_id = completed_step_id

    return ResumeCheckpoint(
        resume_step_id=resume_id,
        suspend_after_step_id=suspend_after,
        checkpoint_tree_id=checkpoint_tree_id,
    )


# ---------------------------------------------------------------------------
# ApplyExecutor
# ---------------------------------------------------------------------------


StepExecutorFn = Callable[[ApplyStep], bool]
"""Signature for a step execution callback.

Takes the :class:`~quickscale_core.apply.step.ApplyStep` to execute and
returns ``True`` on success.
"""


class ApplyExecutor:
    """AF5 per-step executor that manages satisfaction and checkpoint state.

    The executor reads the recovery ledger to determine which steps to run,
    delegates execution to injected callbacks, and writes checkpoint progress
    after each step.

    Typical usage::

        executor = ApplyExecutor(project_path)
        checkpoint = executor.get_checkpoint()
        first_step = executor.find_first_unsatisfied_step(checkpoint)
        executor.execute_remaining_steps(first_step, my_step_fn)
    """

    def __init__(self, project_path: Path) -> None:
        self._ledger_manager = LedgerManager(project_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_checkpoint(self) -> ResumeCheckpoint | None:
        """Load the current resume checkpoint from the recovery ledger.

        Returns:
            The :class:`ResumeCheckpoint` from the ledger, or ``None`` if
            the ledger is absent or carries no checkpoint.

        Raises:
            LedgerError: If the ledger file exists but is malformed.
        """
        ledger = self._ledger_manager.load()
        if ledger is None:
            return None
        return ledger.resume_checkpoint

    def load_ledger(self) -> RecoveryLedger | None:
        """Load the full recovery ledger.

        Returns:
            The :class:`RecoveryLedger` if the file exists, or ``None``.
        """
        return self._ledger_manager.load()

    def find_first_unsatisfied_step(
        self,
        resume_checkpoint: ResumeCheckpoint | None = None,
    ) -> ApplyStep:
        """Return the first step that needs execution.

        Args:
            resume_checkpoint: Optional checkpoint.  When ``None``, reads
                the checkpoint from the recovery ledger.

        Returns:
            The :class:`ApplyStep` to start from.
        """
        if resume_checkpoint is None:
            resume_checkpoint = self.get_checkpoint()
        return resolve_resume_step(resume_checkpoint)

    def checkpoint_step(
        self,
        step: ApplyStep,
        *,
        status: str = "completed",
        detail: str | None = None,
        next_step: ApplyStep | None = None,
        checkpoint_tree_id: str | None = None,
        state_snapshot: QuickScaleState | None = None,
    ) -> RecoveryLedger:
        """Write a checkpoint for a completed step.

        This reads the current recovery ledger, adds a
        :class:`StepProgress` entry for *step*, advances the
        :class:`ResumeCheckpoint` to the next step, and saves atomically.

        Args:
            step: The step that just completed.
            status: Progress status (default ``"completed"``).
            detail: Optional human-readable detail for the progress entry.
            next_step: Optional explicit next step.  When ``None``, advances
                one step forward in the registry.
            checkpoint_tree_id: Optional git tree id.  When provided,
                updates the ledger's ``git_index_checkpoint`` (overriding
                any carried-forward value).
            state_snapshot: Optional ``QuickScaleState`` snapshot to
                use as the ledger's ``applied_state``.  When provided,
                overrides both carried-forward and fallback state so the
                recovery ledger reflects the real post-embed baseline
                instead of placeholder placeholders.

        Returns:
            The saved :class:`RecoveryLedger`.

        Raises:
            LedgerError: If the ledger cannot be saved.
        """
        existing = self._ledger_manager.load()

        # Build step progress entry for the completed step.
        progress_entry = StepProgress(
            step_id=step.step_id,
            status=status,
            detail=detail,
        )

        # Compute the next step for the resume checkpoint.
        next_step_id: str | None = None
        if next_step is not None:
            next_step_id = next_step.step_id
        elif step.order < len(APPLY_STEPS):
            next_step_id = APPLY_STEPS[
                step.order
            ].step_id  # order is 1-based, next is at same index

        new_checkpoint = advance_resume_checkpoint(
            existing.resume_checkpoint if existing else None,
            completed_step_id=step.step_id,
            next_step_id=next_step_id,
            checkpoint_tree_id=checkpoint_tree_id,
        )

        # Merge progress with any existing progress entries.
        merged_progress: dict[str, StepProgress] = {}
        if existing is not None and existing.step_progress is not None:
            merged_progress.update(existing.step_progress)
        merged_progress[step.step_id] = progress_entry

        if existing is not None:
            # Use provided state_snapshot if available, otherwise carry
            # forward the existing applied_state.  Also honour an explicit
            # checkpoint_tree_id when one is provided (AF5-CR-002).
            applied_state = (
                state_snapshot if state_snapshot is not None else existing.applied_state
            )
            gic = (
                checkpoint_tree_id
                if checkpoint_tree_id is not None
                else existing.git_index_checkpoint
            )
            ledger = RecoveryLedger(
                applied_state=applied_state,
                resume_checkpoint=new_checkpoint,
                step_progress=merged_progress,
                git_index_checkpoint=gic,
            )
        else:
            # No existing ledger: build a minimal one.  When
            # state_snapshot is provided (post-embed), use the real
            # state instead of placeholder fields (AF5-CR-002).
            from quickscale_core.schema.state_schema import ProjectState

            gic = checkpoint_tree_id or "pending"
            if state_snapshot is not None:
                applied_state = state_snapshot
            else:
                applied_state = QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="__checkpoint__",
                        package="__checkpoint__",
                        theme="__checkpoint__",
                    ),
                )
            ledger = RecoveryLedger(
                applied_state=applied_state,
                resume_checkpoint=new_checkpoint,
                step_progress=merged_progress,
                git_index_checkpoint=gic,
            )

        self._ledger_manager.save(ledger)
        return ledger

    def execute_remaining_steps(
        self,
        from_step: ApplyStep,
        step_fn: StepExecutorFn,
        *,
        suspend_after: str | None = None,
        checkpoint_each: bool = True,
    ) -> tuple[list[ApplyStep], list[ApplyStep]]:
        """Execute remaining steps from *from_step* through the registry.

        Each step is executed via *step_fn*.  When *checkpoint_each* is
        ``True``, a checkpoint is written after each successful step.

        Args:
            from_step: The first step to execute.
            step_fn: Callback that executes a single step and returns
                ``True`` on success.
            suspend_after: Optional step id at which to stop after
                completion.
            checkpoint_each: Whether to write a checkpoint after each
                successful step.

        Returns:
            A ``(completed, failed)`` tuple of step lists.  *completed*
            contains steps that ran successfully; *failed* contains the
            first step that failed (empty on full success).
        """
        start_index = from_step.order - 1  # 0-based index
        completed: list[ApplyStep] = []
        failed: list[ApplyStep] = []

        for step in APPLY_STEPS[start_index:]:
            success = step_fn(step)

            if not success:
                failed.append(step)
                break

            completed.append(step)

            if checkpoint_each:
                self.checkpoint_step(step)

            if suspend_after and step.step_id == suspend_after:
                break

        return completed, failed


__all__ = [
    "ApplyExecutor",
    "StepExecutorFn",
    "advance_resume_checkpoint",
    "resolve_resume_step",
]
