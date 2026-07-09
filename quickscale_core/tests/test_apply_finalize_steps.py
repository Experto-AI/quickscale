"""Tests for quickscale_core.apply.steps.finalize.

Covers:
* ``step_railway_deploy`` — skip, success, CLI errors, non-zero exit.
* ``step_finalize_state`` — authoritative state save success, recovery
  fallback, double-failure.
* ``step_display_next_steps`` — delegates to callback, always succeeds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quickscale_core.apply.steps.finalize import (
    step_display_next_steps,
    step_finalize_state,
    step_railway_deploy,
)
from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: Any) -> StepContext:
    """Build a minimal StepContext with overrides for test ergonomics."""
    output_path = overrides.pop("output_path", Path("/fake/project"))
    return StepContext(
        output_path=output_path,
        **overrides,
    )


def _assert_success(outcome: StepOutcome, message_substr: str) -> None:
    assert outcome.success is True
    assert outcome.failed_step_label is None
    assert message_substr in outcome.message


def _assert_failure(
    outcome: StepOutcome,
    label: str,
    message_substr: str,
) -> None:
    assert outcome.success is False
    assert outcome.failed_step_label == label
    assert message_substr in outcome.message


def _make_qs_config(slug: str = "testproj") -> Any:
    """Build a minimal QuickScaleConfig-like object with project.slug."""
    from dataclasses import dataclass

    @dataclass
    class _Project:
        slug: str

    @dataclass
    class _Config:
        project: _Project

    return _Config(project=_Project(slug=slug))


# ===================================================================
# step_railway_deploy
# ===================================================================


class MockResult:
    """Minimal mock for subprocess.CompletedProcess-like objects."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestStepRailwayDeploySkip:
    """When is_railway_linked is False, the step is skipped."""

    def test_not_linked_returns_success(self) -> None:
        ctx = _make_context()
        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=False,
            deploy_railway_fn=lambda **kw: None,
            get_service_name_fn=lambda slug: "svc",
        )
        _assert_success(outcome, "Not a Railway-linked project")


class TestStepRailwayDeploySuccess:
    """Happy path for Railway deployment."""

    def test_deploy_success(self) -> None:
        messages: list[str] = []
        ctx = _make_context(
            reporter=lambda msg, **kw: messages.append(msg),
            qs_config=_make_qs_config(),
        )

        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: MockResult(returncode=0),
            get_service_name_fn=lambda slug: "my-svc",
        )
        _assert_success(outcome, "Railway deploy triggered")
        assert any("Railway deploy triggered" in m for m in messages)

    def test_deploy_success_without_reporter(self) -> None:
        ctx = _make_context(reporter=None, qs_config=_make_qs_config())

        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: MockResult(returncode=0),
            get_service_name_fn=lambda slug: "my-svc",
        )
        assert outcome.success is True
        assert outcome.message == "Railway deploy triggered"

    def test_passes_project_path_to_deploy_fn(self) -> None:
        ctx = _make_context(
            output_path=Path("/fake/project"),
            qs_config=_make_qs_config(),
        )
        captured: dict[str, Any] = {}

        def _deploy(**kwargs: Any) -> MockResult:
            captured.update(kwargs)
            return MockResult(returncode=0)

        step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=_deploy,
            get_service_name_fn=lambda slug: "my-svc",
        )
        assert captured.get("project_path") == Path("/fake/project")

    def test_get_service_name_receives_project_slug(self) -> None:
        ctx = _make_context(qs_config=_make_qs_config(slug="testproj"))
        captured_slugs: list[str] = []

        step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: MockResult(returncode=0),
            get_service_name_fn=lambda slug: captured_slugs.append(slug) or "svc",
        )
        assert captured_slugs == ["testproj"]


class TestStepRailwayDeployFailure:
    """Railway deploy error paths."""

    def test_file_not_found_error(self) -> None:
        ctx = _make_context(qs_config=_make_qs_config())

        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: (_ for _ in ()).throw(
                FileNotFoundError("railway not found")
            ),
            get_service_name_fn=lambda slug: "svc",
        )
        _assert_failure(
            outcome, "railway deploy", "Railway CLI error: railway not found"
        )

    def test_timeout_error(self) -> None:
        ctx = _make_context(qs_config=_make_qs_config())

        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: (_ for _ in ()).throw(
                TimeoutError("timed out")
            ),
            get_service_name_fn=lambda slug: "svc",
        )
        _assert_failure(outcome, "railway deploy", "Railway CLI error: timed out")

    def test_non_zero_returncode(self) -> None:
        ctx = _make_context(qs_config=_make_qs_config())

        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: MockResult(returncode=1),
            get_service_name_fn=lambda slug: "svc",
        )
        _assert_failure(outcome, "railway deploy", "non-zero exit code")

    def test_non_zero_returncode_with_stderr_detail(self) -> None:
        ctx = _make_context(qs_config=_make_qs_config())

        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: MockResult(
                returncode=1, stderr="deploy failed: timeout"
            ),
            get_service_name_fn=lambda slug: "svc",
        )
        _assert_failure(outcome, "railway deploy", "deploy failed: timeout")

    def test_non_zero_returncode_without_stderr_falls_back_to_message(self) -> None:
        ctx = _make_context(qs_config=_make_qs_config())

        outcome = step_railway_deploy(
            ctx,
            is_railway_linked=True,
            deploy_railway_fn=lambda **kw: MockResult(
                returncode=1, stdout="", stderr=""
            ),
            get_service_name_fn=lambda slug: "svc",
        )
        _assert_failure(outcome, "railway deploy", "non-zero exit code")


# ===================================================================
# step_finalize_state
# ===================================================================


class TestStepFinalizeStateSuccess:
    """Authoritative state save succeeds."""

    def test_authoritative_state_saved(self) -> None:
        ctx = _make_context()
        recovery_cleared: list[bool] = []

        outcome = step_finalize_state(
            ctx,
            save_project_state_fn=lambda: True,
            save_recovery_state_fn=lambda **kw: True,
            clear_recovery_state_fn=lambda: recovery_cleared.append(True),
            checkpoint_tree_id="abc123",
        )
        _assert_success(outcome, "Authoritative state saved")
        assert recovery_cleared == [True]

    def test_clears_recovery_even_when_state_save_succeeds(self) -> None:
        ctx = _make_context()
        cleared: bool = False

        def _clear() -> None:
            nonlocal cleared
            cleared = True

        step_finalize_state(
            ctx,
            save_project_state_fn=lambda: True,
            save_recovery_state_fn=lambda **kw: True,
            clear_recovery_state_fn=_clear,
            checkpoint_tree_id="abc123",
        )
        assert cleared is True


class TestStepFinalizeStateRecoveryFallback:
    """Authoritative state save fails, recovery save attempted."""

    def test_recovery_save_succeeds_returns_failure_with_recovery_message(self) -> None:
        ctx = _make_context()

        outcome = step_finalize_state(
            ctx,
            save_project_state_fn=lambda: False,
            save_recovery_state_fn=lambda **kw: True,
            clear_recovery_state_fn=lambda: None,
            checkpoint_tree_id="abc123",
        )
        _assert_failure(
            outcome, "authoritative state persistence", "apply-recovery.yml"
        )

    def test_recovery_save_receives_checkpoint_tree_id(self) -> None:
        ctx = _make_context()
        captured_kwargs: dict[str, Any] = {}

        step_finalize_state(
            ctx,
            save_project_state_fn=lambda: False,
            save_recovery_state_fn=lambda **kw: captured_kwargs.update(kw) or True,
            clear_recovery_state_fn=lambda: None,
            checkpoint_tree_id="abc-tree-123",
        )
        assert captured_kwargs.get("checkpoint_tree_id") == "abc-tree-123"


class TestStepFinalizeStateDoubleFailure:
    """Both state and recovery save fail."""

    def test_both_fail_returns_failure_without_recovery_message(self) -> None:
        ctx = _make_context()

        outcome = step_finalize_state(
            ctx,
            save_project_state_fn=lambda: False,
            save_recovery_state_fn=lambda **kw: False,
            clear_recovery_state_fn=lambda: None,
            checkpoint_tree_id="abc123",
        )
        _assert_failure(
            outcome,
            "authoritative state persistence",
            "could not save .quickscale/state.yml",
        )
        # Should mention both failures
        assert "apply-recovery.yml" in outcome.message


# ===================================================================
# step_display_next_steps
# ===================================================================


class TestStepDisplayNextSteps:
    """Informational step that always succeeds."""

    def test_delegates_to_callback_with_correct_args(self) -> None:
        ctx = _make_context(output_path=Path("/fake/project"))

        captured: dict[str, Any] = {}

        def _display_fn(
            output_path: Path,
            qs_config: Any,
            no_docker: bool,
            docker_started: bool | None,
            **kwargs: Any,
        ) -> None:
            captured.update(
                output_path=output_path,
                qs_config=qs_config,
                no_docker=no_docker,
                docker_started=docker_started,
                existing_project=kwargs.get("existing_project"),
            )

        outcome = step_display_next_steps(
            ctx,
            display_next_steps_fn=_display_fn,
            no_docker=True,
            docker_started=False,
            existing_project=True,
        )
        _assert_success(outcome, "Apply complete")
        assert captured["output_path"] == Path("/fake/project")
        assert captured["no_docker"] is True
        assert captured["docker_started"] is False
        assert captured["existing_project"] is True

    def test_always_returns_success(self) -> None:
        ctx = _make_context()

        outcome = step_display_next_steps(
            ctx,
            display_next_steps_fn=lambda *a, **kw: None,
            no_docker=False,
            docker_started=None,
            existing_project=False,
        )
        assert outcome.success is True
        assert outcome.failed_step_label is None
