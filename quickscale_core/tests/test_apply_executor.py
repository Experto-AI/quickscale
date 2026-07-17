"""Tests for quickscale_core.apply.executor — AF5 Phase 2 acceptance criteria.

Verifies:
* ``resolve_resume_step`` returns the correct step from a ResumeCheckpoint
* ``resolve_resume_step`` returns step 1 when checkpoint is ``None``
* ``advance_resume_checkpoint`` produces the correct next-step checkpoint
* ``ApplyExecutor.find_first_unsatisfied_step`` skips completed steps
* ``ApplyExecutor.checkpoint_step`` writes progress and advances checkpoint
* Checkpoint round-trips through save+load
* Skip logic: when recovery is pending with a step-5 checkpoint, steps 1-4
  are satisfied and step 5 is the first unsatisfied step
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from quickscale_core.apply import (
    APPLY_STEPS,
    ApplyExecutor,
    ResumeCheckpoint,
)
from quickscale_core.apply.executor import (
    advance_resume_checkpoint,
    resolve_resume_step,
)
from quickscale_core.apply.ledger import (
    LedgerError,
    LedgerManager,
    RecoveryLedger,
)
from quickscale_core.schema.state_schema import (
    ProjectState,
    QuickScaleState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIRST_STEP_ID = APPLY_STEPS[0].step_id  # "module embedding"
_SECOND_STEP_ID = APPLY_STEPS[1].step_id  # "post-embed state snapshot"
_THIRD_STEP_ID = APPLY_STEPS[2].step_id  # "managed module wiring generation"
_FIFTH_STEP_ID = APPLY_STEPS[4].step_id  # "backups gitignore hardening"
_TENTH_STEP_ID = APPLY_STEPS[9].step_id  # "post-generation dependency..."
_LAST_STEP_ID = APPLY_STEPS[-1].step_id  # "display next steps"

_GIT_INDEX_CHECKPOINT = "cafebabedeadbeefcafebabedeadbeefcafebabe"


def _minimal_state() -> QuickScaleState:
    """Build the smallest valid QuickScaleState for test ledgers."""
    return QuickScaleState(
        version="1",
        project=ProjectState(
            slug="myapp",
            package="myapp",
            theme="showcase_react",
            created_at="2025-01-01T00:00:00",
            last_applied="2025-06-01T00:00:00",
        ),
    )


def _write_ledger(path: Path, data: dict[str, Any]) -> None:
    """Write a YAML recovery ledger at the project path."""
    ledger_dir = path / ".quickscale"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    with open(ledger_dir / "apply-recovery.yml", "w") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False)


# ===========================================================================
# resolve_resume_step
# ===========================================================================


class TestResolveResumeStep:
    """resolve_resume_step must return the correct ApplyStep."""

    def test_with_checkpoint_returns_checkpoint_step(self) -> None:
        rc = ResumeCheckpoint(resume_step_id=_FIFTH_STEP_ID)
        step = resolve_resume_step(rc)
        assert step.step_id == _FIFTH_STEP_ID
        assert step.order == 5

    def test_with_none_checkpoint_returns_step_1(self) -> None:
        step = resolve_resume_step(None)
        assert step.step_id == _FIRST_STEP_ID
        assert step.order == 1

    def test_with_mid_registry_step(self) -> None:
        rc = ResumeCheckpoint(resume_step_id=_TENTH_STEP_ID)
        step = resolve_resume_step(rc)
        assert step.step_id == _TENTH_STEP_ID
        assert step.order == 10

    def test_with_unknown_step_id_raises(self) -> None:
        rc = ResumeCheckpoint(resume_step_id="nonexistent-step")
        with pytest.raises(LedgerError, match="unknown step_id"):
            resolve_resume_step(rc)


# ===========================================================================
# advance_resume_checkpoint
# ===========================================================================


class TestAdvanceResumeCheckpoint:
    """advance_resume_checkpoint must produce the correct next checkpoint."""

    def test_advances_one_step_forward(self) -> None:
        """From step 1, advance to step 2."""
        result = advance_resume_checkpoint(
            None,
            completed_step_id=_FIRST_STEP_ID,
        )
        assert result.resume_step_id == _SECOND_STEP_ID
        assert result.suspend_after_step_id is None
        assert result.checkpoint_tree_id is None

    def test_advances_from_mid_registry(self) -> None:
        """From step 5, advance to step 6."""
        step_5 = APPLY_STEPS[4]
        step_6 = APPLY_STEPS[5]
        result = advance_resume_checkpoint(
            None,
            completed_step_id=step_5.step_id,
        )
        assert result.resume_step_id == step_6.step_id

    def test_advance_from_last_step_stays_on_last(self) -> None:
        """From the last step (16), staying on the same step since there is
        no next step."""
        result = advance_resume_checkpoint(
            None,
            completed_step_id=_LAST_STEP_ID,
        )
        # Stays on the current step when at the end of the registry.
        assert result.resume_step_id == _LAST_STEP_ID

    def test_preserves_suspend_after_from_existing(self) -> None:
        """When advancing, the existing suspend_after_step_id is preserved."""
        existing = ResumeCheckpoint(
            resume_step_id=_FIRST_STEP_ID,
            suspend_after_step_id=_SECOND_STEP_ID,
        )
        result = advance_resume_checkpoint(
            existing,
            completed_step_id=_FIRST_STEP_ID,
        )
        assert result.resume_step_id == _SECOND_STEP_ID
        assert result.suspend_after_step_id == _SECOND_STEP_ID  # preserved

    def test_with_explicit_next_step_id(self) -> None:
        """When next_step_id is provided, it is used instead of auto-advance."""
        result = advance_resume_checkpoint(
            None,
            completed_step_id=_FIRST_STEP_ID,
            next_step_id=_FIFTH_STEP_ID,
        )
        assert result.resume_step_id == _FIFTH_STEP_ID

    def test_includes_checkpoint_tree_id(self) -> None:
        """When checkpoint_tree_id is provided, it must appear in the result."""
        result = advance_resume_checkpoint(
            None,
            completed_step_id=_FIRST_STEP_ID,
            checkpoint_tree_id=_GIT_INDEX_CHECKPOINT,
        )
        assert result.resume_step_id == _SECOND_STEP_ID
        assert result.checkpoint_tree_id == _GIT_INDEX_CHECKPOINT

    def test_carries_forward_checkpoint_tree_id(self) -> None:
        """An existing checkpoint's tree_id is NOT carried forward — preserve
        semantics is tested via explicit next_step_id path."""
        existing = ResumeCheckpoint(
            resume_step_id=_FIRST_STEP_ID,
            checkpoint_tree_id=_GIT_INDEX_CHECKPOINT,
        )
        result = advance_resume_checkpoint(
            existing,
            completed_step_id=_FIRST_STEP_ID,
        )
        # The tree_id from the completed step is not carried forward;
        # the caller provides it when it is available.
        assert result.checkpoint_tree_id is None


# ===========================================================================
# ApplyExecutor — checkpoint reading
# ===========================================================================


class TestApplyExecutorGetCheckpoint:
    """ApplyExecutor.get_checkpoint must read from the recovery ledger."""

    def test_returns_none_when_no_ledger(self, tmp_path: Path) -> None:
        executor = ApplyExecutor(tmp_path)
        assert executor.get_checkpoint() is None

    def test_returns_none_when_no_resume_checkpoint(
        self,
        tmp_path: Path,
    ) -> None:
        """An AF6-era ledger without resume_checkpoint returns None."""
        _write_ledger(
            tmp_path,
            {
                "version": "1",
                "project": {
                    "slug": "myapp",
                    "package": "myapp",
                    "theme": "showcase_react",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-06-01T00:00:00",
                },
                "git_index_checkpoint": _GIT_INDEX_CHECKPOINT,
            },
        )
        executor = ApplyExecutor(tmp_path)
        assert executor.get_checkpoint() is None

    def test_returns_checkpoint_when_present(self, tmp_path: Path) -> None:
        _write_ledger(
            tmp_path,
            {
                "version": "1",
                "project": {
                    "slug": "myapp",
                    "package": "myapp",
                    "theme": "showcase_react",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-06-01T00:00:00",
                },
                "resume_checkpoint": {
                    "resume_step_id": _FIFTH_STEP_ID,
                },
                "git_index_checkpoint": _GIT_INDEX_CHECKPOINT,
            },
        )
        executor = ApplyExecutor(tmp_path)
        checkpoint = executor.get_checkpoint()
        assert checkpoint is not None
        assert checkpoint.resume_step_id == _FIFTH_STEP_ID


# ===========================================================================
# ApplyExecutor — find_first_unsatisfied_step
# ===========================================================================


class TestApplyExecutorFindFirstUnsatisfied:
    """find_first_unsatisfied_step must return the correct step."""

    def test_no_checkpoint_starts_at_step_1(self, tmp_path: Path) -> None:
        executor = ApplyExecutor(tmp_path)
        step = executor.find_first_unsatisfied_step(None)
        assert step.order == 1
        assert step.step_id == _FIRST_STEP_ID

    def test_with_checkpoint_resumes_at_checkpoint_step(
        self,
        tmp_path: Path,
    ) -> None:
        executor = ApplyExecutor(tmp_path)
        rc = ResumeCheckpoint(resume_step_id=_FIFTH_STEP_ID)
        step = executor.find_first_unsatisfied_step(rc)
        assert step.order == 5
        assert step.step_id == _FIFTH_STEP_ID

    def test_resumes_from_persisted_ledger(self, tmp_path: Path) -> None:
        """Reads checkpoint from the persisted ledger when not provided."""
        _write_ledger(
            tmp_path,
            {
                "version": "1",
                "project": {
                    "slug": "myapp",
                    "package": "myapp",
                    "theme": "showcase_react",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-06-01T00:00:00",
                },
                "resume_checkpoint": {
                    "resume_step_id": _TENTH_STEP_ID,
                },
                "git_index_checkpoint": _GIT_INDEX_CHECKPOINT,
            },
        )
        executor = ApplyExecutor(tmp_path)
        step = executor.find_first_unsatisfied_step()
        assert step.order == 10
        assert step.step_id == _TENTH_STEP_ID


# ===========================================================================
# ApplyExecutor — checkpoint_step
# ===========================================================================


class TestApplyExecutorCheckpointStep:
    """checkpoint_step must write progress and advance the checkpoint."""

    def test_writes_step_progress_for_first_step(self, tmp_path: Path) -> None:
        executor = ApplyExecutor(tmp_path)
        step = APPLY_STEPS[0]  # "module embedding"

        executor.checkpoint_step(step)

        # Verify the ledger was written.
        ledger = executor.load_ledger()
        assert ledger is not None
        assert ledger.step_progress is not None
        assert _FIRST_STEP_ID in ledger.step_progress
        assert ledger.step_progress[_FIRST_STEP_ID].status == "completed"

    def test_advances_resume_checkpoint_after_step(self, tmp_path: Path) -> None:
        executor = ApplyExecutor(tmp_path)
        step_1 = APPLY_STEPS[0]

        executor.checkpoint_step(step_1)

        # Resume checkpoint should point to step 2.
        ledger = executor.load_ledger()
        assert ledger is not None
        assert ledger.resume_checkpoint is not None
        assert ledger.resume_checkpoint.resume_step_id == _SECOND_STEP_ID

    def test_round_trips_multiple_checkpoints(self, tmp_path: Path) -> None:
        executor = ApplyExecutor(tmp_path)

        # Checkpoint step 1, then step 2, then step 3.
        executor.checkpoint_step(APPLY_STEPS[0])  # step 1
        executor.checkpoint_step(APPLY_STEPS[1])  # step 2
        executor.checkpoint_step(APPLY_STEPS[2])  # step 3

        ledger = executor.load_ledger()
        assert ledger is not None
        assert ledger.step_progress is not None
        assert len(ledger.step_progress) == 3
        assert _FIRST_STEP_ID in ledger.step_progress
        assert _SECOND_STEP_ID in ledger.step_progress
        assert _THIRD_STEP_ID in ledger.step_progress
        # Resume checkpoint should point to step 4.
        assert ledger.resume_checkpoint is not None
        assert ledger.resume_checkpoint.resume_step_id == APPLY_STEPS[3].step_id

    def test_checkpoint_with_checkpoint_tree_id(self, tmp_path: Path) -> None:
        executor = ApplyExecutor(tmp_path)
        step = APPLY_STEPS[0]

        executor.checkpoint_step(step, checkpoint_tree_id=_GIT_INDEX_CHECKPOINT)

        ledger = executor.load_ledger()
        assert ledger is not None
        assert ledger.resume_checkpoint is not None
        assert ledger.resume_checkpoint.checkpoint_tree_id == _GIT_INDEX_CHECKPOINT

    def test_adds_progress_detail(self, tmp_path: Path) -> None:
        executor = ApplyExecutor(tmp_path)
        step = APPLY_STEPS[0]

        executor.checkpoint_step(
            step, status="completed", detail="All modules embedded"
        )

        ledger = executor.load_ledger()
        assert ledger is not None
        assert ledger.step_progress is not None
        entry = ledger.step_progress[_FIRST_STEP_ID]
        assert entry.status == "completed"
        assert entry.detail == "All modules embedded"

    def test_recovery_ledger_applied_state_is_preserved(
        self,
        tmp_path: Path,
    ) -> None:
        """An existing recovery ledger's applied_state must survive checkpoint
        writes (the checker does NOT replace the applied state)."""
        # First, create a recovery ledger with an applied state.
        state = _minimal_state()
        mgr = LedgerManager(tmp_path)
        initial_ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr.save(initial_ledger)

        # Now write a checkpoint step.
        executor = ApplyExecutor(tmp_path)
        executor.checkpoint_step(APPLY_STEPS[0])

        # The applied_state must still be the original.
        ledger = executor.load_ledger()
        assert ledger is not None
        assert ledger.applied_state.project.slug == "myapp"
        assert ledger.git_index_checkpoint == _GIT_INDEX_CHECKPOINT


# ===========================================================================
# Integration: skip logic for recovery
# ===========================================================================


class TestApplyExecutorRecoverySkip:
    """When a resume checkpoint is present, steps before it are satisfied."""

    def test_first_unsatisfied_step_with_checkpoint_at_step_5(
        self,
        tmp_path: Path,
    ) -> None:
        """A checkpoint at step 5 means steps 1-4 are satisfied, step 5 is first."""
        _write_ledger(
            tmp_path,
            {
                "version": "1",
                "project": {
                    "slug": "myapp",
                    "package": "myapp",
                    "theme": "showcase_react",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-06-01T00:00:00",
                },
                "resume_checkpoint": {
                    "resume_step_id": _FIFTH_STEP_ID,
                },
                "git_index_checkpoint": _GIT_INDEX_CHECKPOINT,
            },
        )
        executor = ApplyExecutor(tmp_path)
        step = executor.find_first_unsatisfied_step()
        assert step.order == 5

    def test_should_run_skip_before_checkpoint(self, tmp_path: Path) -> None:
        """The _should_run pattern (simulated) must skip steps before the checkpoint."""
        executor = ApplyExecutor(tmp_path)
        rc = ResumeCheckpoint(resume_step_id=_FIFTH_STEP_ID)
        first_unsatisfied = executor.find_first_unsatisfied_step(rc)

        # Steps before the checkpoint should be considered satisfied.
        assert first_unsatisfied.order == 5

        # Simulate the _should_run closure:
        for order in range(1, 5):
            assert order < first_unsatisfied.order  # would be skipped

        for order in range(5, 17):
            assert order >= first_unsatisfied.order  # would run


# ===========================================================================
# Integration: full checkpoint round-trip through CLI seam
# ===========================================================================


class TestApplyExecutorCheckpointRoundTrip:
    """End-to-end checkpoint write + reload cycle."""

    def test_write_then_load_round_trip(self, tmp_path: Path) -> None:
        """Write 3 checkpoints, then verify they can be re-read."""
        executor = ApplyExecutor(tmp_path)

        executor.checkpoint_step(APPLY_STEPS[0])
        executor.checkpoint_step(APPLY_STEPS[1])
        executor.checkpoint_step(APPLY_STEPS[2])

        # Re-read checkpoint
        checkpoint = executor.get_checkpoint()
        assert checkpoint is not None
        assert checkpoint.resume_step_id == APPLY_STEPS[3].step_id  # step 4

        # Re-create executor (simulating new process) and verify
        executor2 = ApplyExecutor(tmp_path)
        checkpoint2 = executor2.get_checkpoint()
        assert checkpoint2 is not None
        assert checkpoint2.resume_step_id == APPLY_STEPS[3].step_id

        ledger = executor2.load_ledger()
        assert ledger is not None
        assert ledger.step_progress is not None
        assert len(ledger.step_progress) == 3

    def test_checkpoint_with_progress_and_tree_id(self, tmp_path: Path) -> None:
        """Checkpoint with all optional fields must round-trip."""
        executor = ApplyExecutor(tmp_path)

        executor.checkpoint_step(
            APPLY_STEPS[0],
            status="completed",
            detail="Modules embedded successfully",
            checkpoint_tree_id=_GIT_INDEX_CHECKPOINT,
        )

        ledger = executor.load_ledger()
        assert ledger is not None
        assert ledger.resume_checkpoint is not None
        assert ledger.resume_checkpoint.checkpoint_tree_id == _GIT_INDEX_CHECKPOINT
        assert ledger.resume_checkpoint.resume_step_id == _SECOND_STEP_ID
        assert ledger.step_progress is not None
        assert ledger.step_progress[_FIRST_STEP_ID].detail == (
            "Modules embedded successfully"
        )


# ===========================================================================
# AF5 Phase 3 — Deterministic fault-injection harness & convergence assertions
# ===========================================================================


class TestAF5Phase3FaultInjection:
    """AF5 Phase 3/4: Fault-injection harness for recovery convergence testing.

    These tests exercise the **real** :class:`ApplyExecutor`, the **real**
    :class:`~quickscale_core.apply.ledger.LedgerManager`, and the **shipped**
    :data:`APPLY_STEPS` registry through a simulated crash-then-recovery cycle
    using the :class:`~quickscale_core.tests.fault_injection_harness.FaultInjector`.

    No live Docker, Railway, or filesystem side effects are triggered — the
    step function is a no-op mock that returns ``True`` for every step except
    the one targeted by the injector.

    AF5 Phase 4 extended checkpointing to all 16 steps.  The fault-injection
    harness already supports the full registry (including destructive/remote
    steps 11-16) through the generic :func:`assert_convergent_recovery` and
    :class:`FaultInjector` API.
    """

    # ------------------------------------------------------------------
    # Basic fault injection at a mid-registry safe step
    # ------------------------------------------------------------------

    def test_fault_at_step_5_recovery_converges(self, tmp_path: Path) -> None:
        """Inject failure at step 5 (backups gitignore), recover, converge."""
        from fault_injection_harness import (
            assert_convergent_recovery,
            make_safe_step_fn,
        )

        step_5 = APPLY_STEPS[4]
        result = assert_convergent_recovery(
            tmp_path,
            make_safe_step_fn(),
            fail_at_step_id=step_5.step_id,
        )

        # First pass completed steps 1-4; step 5 failed.
        assert result["completed_first"] == [APPLY_STEPS[i].step_id for i in range(4)]
        assert result["failed_first"] == [step_5.step_id]
        assert result["injector_first"].failed_step_id == step_5.step_id

        # Recovery pass found first unsatisfied at step 5.
        assert result["first_unsatisfied"] == step_5.step_id

        # Recovery called step 5 and all subsequent steps.
        assert step_5.step_id in result["injector_second"].called_step_ids
        assert result["injector_second"].failed_step_id is None
        assert not result["failed_first"] or len(result["failed_first"]) == 1

        # Final checkpoint exists and shows recovery completed.
        assert result["final_checkpoint"] is not None
        assert result["final_ledger"] is not None
        assert result["final_ledger"].step_progress is not None

        # Verify progress was written for steps that completed in the
        # first pass AND steps that completed in the recovery pass.
        for step in APPLY_STEPS[:4]:
            assert step.step_id in result["final_ledger"].step_progress, (
                f"Missing progress for step {step.order} ({step.step_id})"
            )
        for step in APPLY_STEPS[4:]:
            assert step.step_id in result["final_ledger"].step_progress, (
                f"Missing progress for step {step.order} ({step.step_id})"
            )

    # ------------------------------------------------------------------
    # Fault at the very first step
    # ------------------------------------------------------------------

    def test_fault_at_step_1_recovery_converges(self, tmp_path: Path) -> None:
        """Inject failure at step 1 (module embedding), recover, converge."""
        from fault_injection_harness import (
            assert_convergent_recovery,
            make_safe_step_fn,
        )

        step_1 = APPLY_STEPS[0]
        result = assert_convergent_recovery(
            tmp_path,
            make_safe_step_fn(),
            fail_at_step_id=step_1.step_id,
        )

        # First pass: no steps completed, step 1 failed immediately.
        assert result["completed_first"] == [], (
            f"Expected no completed steps on first pass, got "
            f"{result['completed_first']}"
        )
        assert result["failed_first"] == [step_1.step_id]

        # Recovery pass found first unsatisfied at step 1.
        assert result["first_unsatisfied"] == step_1.step_id

        # Recovery ran step 1 through the end of the registry.
        assert result["injector_second"].called_step_ids[0] == step_1.step_id
        assert result["injector_second"].failed_step_id is None
        assert len(result["completed_second"]) >= 10  # Safe steps covered

    # ------------------------------------------------------------------
    # Fault at the last safe step (step 10)
    # ------------------------------------------------------------------

    def test_fault_at_step_10_recovery_converges(self, tmp_path: Path) -> None:
        """Inject failure at step 10 (post-generation setup), recover, converge."""
        from fault_injection_harness import (
            assert_convergent_recovery,
            make_safe_step_fn,
        )

        step_10 = APPLY_STEPS[9]
        result = assert_convergent_recovery(
            tmp_path,
            make_safe_step_fn(),
            fail_at_step_id=step_10.step_id,
        )

        # First pass completed steps 1-9.
        assert result["completed_first"] == [APPLY_STEPS[i].step_id for i in range(9)]
        assert result["failed_first"] == [step_10.step_id]

        # Recovery started from step 10.
        assert result["first_unsatisfied"] == step_10.step_id

        # Recovery completed step 10 through the end of the registry.
        assert step_10.step_id in result["injector_second"].called_step_ids
        assert result["injector_second"].failed_step_id is None

    # ------------------------------------------------------------------
    # Fault injector records call order correctly
    # ------------------------------------------------------------------

    def test_fault_injector_records_call_order(self, tmp_path: Path) -> None:
        """FaultInjector must record step calls in execution order."""
        from fault_injection_harness import (
            FaultInjector,
            make_safe_step_fn,
        )

        step_fn = make_safe_step_fn()
        injector = FaultInjector(step_fn, fail_at_step_id=_FIFTH_STEP_ID)

        executor = ApplyExecutor(tmp_path)
        first = executor.find_first_unsatisfied_step(None)
        executor.execute_remaining_steps(first, injector)

        # Called steps must be in registry order: 1, 2, 3, 4, 5.
        assert len(injector.called_step_ids) == 5, (
            f"Expected exactly 5 calls, got {len(injector.called_step_ids)}: "
            f"{injector.called_step_ids}"
        )
        assert injector.called_step_ids[0] == _FIRST_STEP_ID
        assert injector.called_step_ids[1] == _SECOND_STEP_ID
        assert injector.called_step_ids[2] == _THIRD_STEP_ID
        assert injector.called_step_ids[3] == APPLY_STEPS[3].step_id  # step 4
        assert injector.called_step_ids[4] == _FIFTH_STEP_ID  # failing step
        assert injector.failed_step_id == _FIFTH_STEP_ID

    def test_fault_injector_no_failure_records_all_steps(
        self,
        tmp_path: Path,
    ) -> None:
        """FaultInjector without a failure target must record all steps."""
        from fault_injection_harness import (
            FaultInjector,
            make_safe_step_fn,
        )

        step_fn = make_safe_step_fn()
        injector = FaultInjector(step_fn)  # No failure

        executor = ApplyExecutor(tmp_path)
        first = executor.find_first_unsatisfied_step(None)
        executor.execute_remaining_steps(first, injector)

        # All 16 steps should have been called.
        assert len(injector.called_step_ids) == 16
        assert injector.called_step_ids == [s.step_id for s in APPLY_STEPS]
        assert injector.failed_step_id is None

    # ------------------------------------------------------------------
    # Legacy-ledger compatibility: AF6-era ledger without resume_checkpoint
    # ------------------------------------------------------------------

    def test_legacy_ledger_without_checkpoint_recovery(
        self,
        tmp_path: Path,
    ) -> None:
        """A legacy (AF6-era) ledger without resume_checkpoint must still
        recover correctly after a fault-injected failure.

        When the ledger exists but carries no ``resume_checkpoint``, the
        executor starts from step 1.  After a checkpoint is written during
        the first pass, the recovery pass loads the new checkpoint and
        resumes from the failing step.
        """
        from fault_injection_harness import (
            assert_convergent_recovery,
            make_safe_step_fn,
        )

        # Write an AF6-era ledger (no resume_checkpoint).
        _write_ledger(
            tmp_path,
            {
                "version": "1",
                "project": {
                    "slug": "myapp",
                    "package": "myapp",
                    "theme": "showcase_react",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-06-01T00:00:00",
                },
                "git_index_checkpoint": _GIT_INDEX_CHECKPOINT,
            },
        )

        step_5 = APPLY_STEPS[4]
        result = assert_convergent_recovery(
            tmp_path,
            make_safe_step_fn(),
            fail_at_step_id=step_5.step_id,
        )

        # Even with an existing legacy ledger, the first pass starts from
        # step 1 (no resume_checkpoint) and the recovery converges.
        assert len(result["completed_first"]) == 4
        assert result["failed_first"] == [step_5.step_id]
        assert result["first_unsatisfied"] == step_5.step_id
        assert result["injector_second"].failed_step_id is None
        assert result["final_ledger"] is not None
        assert result["final_ledger"].resume_checkpoint is not None

    # ------------------------------------------------------------------
    # Fault injection with initial checkpoint (simulating partial progress)
    # ------------------------------------------------------------------

    def test_fault_with_initial_checkpoint_at_step_3(
        self,
        tmp_path: Path,
    ) -> None:
        """When an initial checkpoint at step 3 exists, the executor skips
        steps 1-2 and starts from step 3.  A fault at step 5 then produces
        a first pass that completes step 3-4 and fails at step 5, and the
        recovery resumes from step 5.
        """
        from fault_injection_harness import (
            assert_convergent_recovery,
            make_safe_step_fn,
        )

        step_3 = APPLY_STEPS[2]
        step_5 = APPLY_STEPS[4]

        initial = ResumeCheckpoint(resume_step_id=step_3.step_id)
        result = assert_convergent_recovery(
            tmp_path,
            make_safe_step_fn(),
            fail_at_step_id=step_5.step_id,
            initial_checkpoint=initial,
        )

        # First pass completed steps 3-4 (not 1-2, which were already
        # satisfied), then failed at step 5.
        assert result["completed_first"] == [
            step_3.step_id,
            APPLY_STEPS[3].step_id,
        ], f"Unexpected completed_first: {result['completed_first']}"
        assert result["failed_first"] == [step_5.step_id]
        assert result["first_unsatisfied"] == step_5.step_id
        assert result["injector_second"].failed_step_id is None

    # ------------------------------------------------------------------
    # Convergence: injector records only safe steps before failure
    # ------------------------------------------------------------------

    def test_fault_safe_step_count(self, tmp_path: Path) -> None:
        """The first pass must only call steps strictly before the
        failing step (steps 1..N-1) plus the failing step itself."""
        from fault_injection_harness import (
            FaultInjector,
            make_safe_step_fn,
        )

        step_fn = make_safe_step_fn()
        injector = FaultInjector(step_fn, fail_at_step_id=_FIFTH_STEP_ID)

        executor = ApplyExecutor(tmp_path)
        first = executor.find_first_unsatisfied_step(None)
        executor.execute_remaining_steps(first, injector)

        # The injector must have been called for steps 1 through 5
        # (4 safe successes + 1 failure).
        called = injector.called_step_ids
        assert len(called) == 5, f"Expected 5 calls, got {len(called)}: {called}"

        # The first four calls (steps 1-4) must have been successes;
        # the step_fn was called for them (injector delegates to _step_fn
        # and returns its result).
        assert injector.failed_step_id == _FIFTH_STEP_ID
        assert _FIFTH_STEP_ID not in [called[i] for i in range(4)], (
            "Failing step must not be in the first 4 calls"
        )

    # ------------------------------------------------------------------
    # Fatal: invalid step_id raises
    # ------------------------------------------------------------------

    def test_unknown_step_id_raises_value_error(self) -> None:
        """FaultInjector with an unknown step_id must raise ValueError."""
        from fault_injection_harness import (
            FaultInjector,
            make_safe_step_fn,
        )

        with pytest.raises(ValueError, match="Unknown step_id"):
            FaultInjector(
                make_safe_step_fn(),
                fail_at_step_id="nonexistent-step",
            )

    def test_assert_convergent_recovery_unknown_step_id_raises(
        self,
        tmp_path: Path,
    ) -> None:
        """assert_convergent_recovery with unknown step_id must raise ValueError."""
        from fault_injection_harness import (
            assert_convergent_recovery,
            make_safe_step_fn,
        )

        with pytest.raises(ValueError, match="Unknown step_id"):
            assert_convergent_recovery(
                tmp_path,
                make_safe_step_fn(),
                fail_at_step_id="nonexistent-step",
            )
