"""AF5 Phase 3: Deterministic fault-injection harness for apply executor recovery testing.

This module provides a reusable harness for testing the apply executor's per-step
checkpoint and resume-recovery flow through the **real** :class:`~quickscale_core.apply.executor.ApplyExecutor`,
the **real** :class:`~quickscale_core.apply.ledger.LedgerManager`, and the **shipped**
:data:`~quickscale_core.apply.step.APPLY_STEPS` registry.

Design invariants
-----------------
* **Deterministic by construction** — no randomness, no wall-clock timing.
* **CI-safe** — uses ``tmp_path`` for ledger files and mock step functions.
* **Real recovery loader** — exercises :meth:`~quickscale_core.apply.ledger.LedgerManager.load`,
  not a fake loader.
* **Real step registry** — uses the shipped :data:`~quickscale_core.apply.step.APPLY_STEPS`
  tuple, not a parallel fake registry.
* **No live side effects** — the caller provides step callbacks that return
  ``True``/``False`` without real Docker, Railway, or filesystem operations.

Typical usage in a test::

    from quickscale_core.tests.fault_injection_harness import (
        FaultInjector,
        assert_convergent_recovery,
        make_safe_step_fn,
    )

    def test_recovery_from_step_5(tmp_path):
        result = assert_convergent_recovery(
            tmp_path,
            make_safe_step_fn(),
            fail_at_step_id=APPLY_STEPS[4].step_id,
        )
        assert result["injector_first"].failed_step_id == APPLY_STEPS[4].step_id
        assert len(result["completed_first"]) == 4
        assert not result["failed_first"]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quickscale_core.apply import (
    APPLY_STEPS,
    ApplyExecutor,
    ApplyStep,
    ResumeCheckpoint,
)
from quickscale_core.apply.executor import StepExecutorFn


# ---------------------------------------------------------------------------
# FaultInjector — deterministic step-failure wrapper
# ---------------------------------------------------------------------------


class FaultInjector:
    """Wraps a step executor function and injects failure at a selected step.

    Records which steps were called, in order, across the pass.  The injector
    returns ``True`` for every step except the configured target, for which it
    returns ``False`` (simulating a runtime failure).

    Typical usage::

        injector = FaultInjector(
            my_step_fn,
            fail_at_step_id="backups gitignore hardening",
        )
        completed, failed = executor.execute_remaining_steps(first_step, injector)
        assert injector.failed_step_id == "backups gitignore hardening"
        assert "module embedding" in injector.called_step_ids

    Attributes:
        called_step_ids: Ordered list of step IDs that were passed to the
            wrapped step function.
        failed_step_id: The step ID at which the injector returned ``False``,
            or ``None`` if no failure was triggered.
    """

    def __init__(
        self,
        step_fn: StepExecutorFn,
        fail_at_step_id: str | None = None,
    ) -> None:
        if fail_at_step_id is not None:
            _validate_step_id(fail_at_step_id)
        self._step_fn = step_fn
        self._fail_at = fail_at_step_id
        self.called_step_ids: list[str] = []
        self.failed_step_id: str | None = None

    def __call__(self, step: ApplyStep) -> bool:
        """Execute *step* through the wrapped function, injecting failure if configured.

        Args:
            step: The :class:`~quickscale_core.apply.step.ApplyStep` to execute.

        Returns:
            ``True`` if the step succeeded (or was not targeted), ``False`` if
            this step is the configured failure target.
        """
        self.called_step_ids.append(step.step_id)
        if step.step_id == self._fail_at:
            self.failed_step_id = step.step_id
            return False
        return self._step_fn(step)


# ---------------------------------------------------------------------------
# Mock step functions
# ---------------------------------------------------------------------------


def make_safe_step_fn() -> StepExecutorFn:
    """Create a step executor function that succeeds for every step.

    Returns a no-op callback that returns ``True`` unconditionally, suitable
    for testing recovery convergence without real side effects.

    Returns:
        A :data:`StepExecutorFn` that returns ``True`` for any step.
    """

    def _fn(step: ApplyStep) -> bool:
        return True

    return _fn


# ---------------------------------------------------------------------------
# Convergence assertion helper
# ---------------------------------------------------------------------------


def assert_convergent_recovery(
    tmp_path: Path,
    step_fn: StepExecutorFn,
    fail_at_step_id: str,
    *,
    initial_checkpoint: ResumeCheckpoint | None = None,
    suspend_after: str | None = None,
) -> dict[str, Any]:
    """Run the executor with deterministic fault injection, then recover, and
    assert full convergence.

    This exercises the real :class:`ApplyExecutor`, the real
    :class:`~quickscale_core.apply.ledger.LedgerManager`, and the shipped
    :data:`APPLY_STEPS` registry through a simulated crash-then-recovery
    cycle:

    1. **First pass** — the executor runs from the first unsatisfied step
       (determined by *initial_checkpoint*) and the ``FaultInjector`` causes
       the step identified by *fail_at_step_id* to return ``False``.
    2. **Recovery pass** — a **fresh** :class:`ApplyExecutor` loads the
       persisted checkpoint and resumes from the first unsatisfied step.
       No further faults are injected.

    Args:
        tmp_path: A pytest ``tmp_path`` for the project root.  The recovery
            ledger is written inside ``<tmp_path>/.quickscale/``.
        step_fn: The step executor callback.  Must return ``True`` for all
            steps except the one targeted by *fail_at_step_id*.
        fail_at_step_id: The stable step ID at which to inject a failure on
            the first pass.  Must be a valid step ID from :data:`APPLY_STEPS`.
        initial_checkpoint: Optional starting
            :class:`~quickscale_core.apply.ledger.ResumeCheckpoint`.  When
            ``None`` the executor behaves as if no checkpoint exists (starts
            from step 1).
        suspend_after: Optional step ID at which to stop the recovery pass.
            Passed through to
            :meth:`~quickscale_core.apply.executor.ApplyExecutor.execute_remaining_steps`.

    Returns:
        A dictionary with structured test details:

        * ``completed_first`` — list of step IDs completed in the first pass.
        * ``failed_first`` — list of step IDs that failed in the first pass
          (always exactly one: *fail_at_step_id*).
        * ``completed_second`` — list of step IDs completed in the recovery pass.
        * ``first_unsatisfied`` — step ID identified as the first unsatisfied
          step at the start of the recovery pass.
        * ``final_ledger`` — the
          :class:`~quickscale_core.apply.ledger.RecoveryLedger` after the
          recovery pass completes.
        * ``injector_first`` — the :class:`FaultInjector` used in the first pass.
        * ``injector_second`` — the :class:`FaultInjector` used in the recovery
          pass (never injects a fault).
        * ``final_checkpoint`` — the
          :class:`~quickscale_core.apply.ledger.ResumeCheckpoint` from the
          final ledger.

    Raises:
        AssertionError: If any recovery convergence invariant is violated.
            Details include the step lists and injector state to simplify
            diagnosis.
    """
    _validate_step_id(fail_at_step_id)

    # ------------------------------------------------------------------
    # Phase 1: First pass with fault injection
    # ------------------------------------------------------------------
    executor = ApplyExecutor(tmp_path)
    first = executor.find_first_unsatisfied_step(initial_checkpoint)
    injector = FaultInjector(step_fn, fail_at_step_id=fail_at_step_id)

    completed1, failed1 = executor.execute_remaining_steps(first, injector)

    # --- Assertions for Phase 1 ---

    # The failure must have been injected at the expected step.
    assert len(failed1) == 1, (
        f"Expected exactly 1 failure, got {len(failed1)}. "
        f"Completed: {[s.step_id for s in completed1]}"
    )
    assert failed1[0].step_id == fail_at_step_id, (
        f"Expected failure at {fail_at_step_id}, got {failed1[0].step_id}"
    )
    assert injector.failed_step_id == fail_at_step_id, (
        f"FaultInjector.failed_step_id mismatch: "
        f"expected {fail_at_step_id}, got {injector.failed_step_id}"
    )

    # The failing step's step_fn must have been called.
    assert fail_at_step_id in injector.called_step_ids, (
        f"FaultInjector did not record a call to the failing step "
        f"{fail_at_step_id}; called: {injector.called_step_ids}"
    )

    # Checkpoint presence depends on whether any step completed.
    # When the failure is at step 1, no checkpoint exists (no step
    # completed).  When at any later step, the checkpoint must point
    # to the failing step (the last successful checkpoint advanced
    # past the step before the failing one).
    checkpoint = executor.get_checkpoint()
    fail_idx = _registry_index(fail_at_step_id)
    if fail_idx == 0:
        # Failure at step 1 — no checkpoint expected.
        assert checkpoint is None, (
            f"Expected no checkpoint when step 1 fails, got {checkpoint}"
        )
    else:
        assert checkpoint is not None, (
            f"No checkpoint found after first pass for fail_at_step_id="
            f"{fail_at_step_id!r}. Completed steps before failure: "
            f"{[s.step_id for s in completed1]}"
        )
        # The checkpoint's resume_step_id must point to the failing step.
        assert checkpoint.resume_step_id == fail_at_step_id, (
            f"Expected checkpoint to resume from {fail_at_step_id}, "
            f"got {checkpoint.resume_step_id}"
        )

    # ------------------------------------------------------------------
    # Phase 2: Recovery pass — fresh executor, no injected faults
    # ------------------------------------------------------------------
    executor2 = ApplyExecutor(tmp_path)
    first2 = executor2.find_first_unsatisfied_step()

    assert first2.step_id == fail_at_step_id, (
        f"First unsatisfied step on recovery expected {fail_at_step_id}, "
        f"got {first2.step_id}"
    )

    injector2 = FaultInjector(step_fn)  # No failure on recovery
    completed2, failed2 = executor2.execute_remaining_steps(
        first2,
        injector2,
        suspend_after=suspend_after,
    )

    # --- Assertions for Phase 2 ---

    assert len(failed2) == 0, (
        f"Recovery produced unexpected failures: {[s.step_id for s in failed2]}"
    )
    assert injector2.failed_step_id is None, (
        "Recovery injector should not have recorded any failure"
    )

    # All steps from the failing step forward must have been called
    # during the recovery pass.
    failing_idx = _registry_index(fail_at_step_id)
    remaining_step_ids = {s.step_id for s in APPLY_STEPS[failing_idx:]}
    called_in_second = set(injector2.called_step_ids)
    assert called_in_second.issubset(remaining_step_ids), (
        f"Recovery called unexpected steps outside range "
        f"[{fail_at_step_id}..]: {called_in_second - remaining_step_ids}"
    )

    # The failing step must appear in the recovery pass (it was not
    # completed in the first pass).
    assert fail_at_step_id in injector2.called_step_ids, (
        f"Recovery pass did not call the previously-failing step "
        f"{fail_at_step_id}; called: {injector2.called_step_ids}"
    )

    # ------------------------------------------------------------------
    # Load final ledger state for inspection
    # ------------------------------------------------------------------
    final_ledger = executor2.load_ledger()
    assert final_ledger is not None, "Final ledger must exist after recovery"

    final_checkpoint = final_ledger.resume_checkpoint

    return {
        "completed_first": [s.step_id for s in completed1],
        "failed_first": [s.step_id for s in failed1],
        "completed_second": [s.step_id for s in completed2],
        "first_unsatisfied": first2.step_id,
        "final_ledger": final_ledger,
        "final_checkpoint": final_checkpoint,
        "injector_first": injector,
        "injector_second": injector2,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_step_id(step_id: str) -> None:
    """Raise :class:`ValueError` if *step_id* is not in :data:`APPLY_STEPS`."""
    for step in APPLY_STEPS:
        if step.step_id == step_id:
            return
    raise ValueError(
        f"Unknown step_id={step_id!r}. Valid IDs: {[s.step_id for s in APPLY_STEPS]}"
    )


def _registry_index(step_id: str) -> int:
    """Return the 0-based index of *step_id* in :data:`APPLY_STEPS`.

    Raises:
        ValueError: If *step_id* is not found.
    """
    for i, step in enumerate(APPLY_STEPS):
        if step.step_id == step_id:
            return i
    raise ValueError(f"step_id={step_id!r} not found in APPLY_STEPS")
