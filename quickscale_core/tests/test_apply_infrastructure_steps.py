"""Tests for quickscale_core.apply.steps.infrastructure.

Covers:
* ``step_apply_mutable_config`` — delta/reporter interactions.
* ``step_start_docker`` — skip, success, failure.
* ``step_run_migrations`` — Docker path, local path, skip, missing
  local callback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quickscale_core.apply.steps.infrastructure import (
    step_apply_mutable_config,
    step_run_migrations,
    step_start_docker,
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


# ===================================================================
# step_apply_mutable_config  (step 11 — informational)
# ===================================================================


class _DeltaWithConfigChanges:
    """Minimal delta mock with has_mutable_config_changes=True."""

    has_mutable_config_changes = True


class _DeltaWithoutConfigChanges:
    """Minimal delta mock with has_mutable_config_changes=False."""

    has_mutable_config_changes = False


class TestStepApplyMutableConfigNoDelta:
    """When ctx.delta is None, the step is a no-op."""

    def test_no_delta_returns_success(self) -> None:
        ctx = _make_context(delta=None)
        outcome = step_apply_mutable_config(ctx)
        _assert_success(outcome, "Mutable config check complete")

    def test_no_delta_no_reporter_needed(self) -> None:
        ctx = _make_context(delta=None, reporter=None)
        outcome = step_apply_mutable_config(ctx)
        assert outcome.success is True


class TestStepApplyMutableConfigNoChanges:
    """Delta exists but has no mutable config changes."""

    def test_no_changes_returns_success_silently(self) -> None:
        messages: list[str] = []
        ctx = _make_context(
            delta=_DeltaWithoutConfigChanges(),
            reporter=lambda msg, **kw: messages.append(msg),
        )

        outcome = step_apply_mutable_config(ctx)
        _assert_success(outcome, "Mutable config check complete")
        assert messages == []


class TestStepApplyMutableConfigWithChanges:
    """Delta has mutable config changes — reporter is called."""

    def test_reporter_called_when_changes_exist(self) -> None:
        messages: list[str] = []
        ctx = _make_context(
            delta=_DeltaWithConfigChanges(),
            reporter=lambda msg, **kw: messages.append(msg),
        )

        outcome = step_apply_mutable_config(ctx)
        _assert_success(outcome, "Mutable config check complete")
        assert any("Mutable configuration changes applied" in m for m in messages)

    def test_no_reporter_does_not_crash(self) -> None:
        ctx = _make_context(delta=_DeltaWithConfigChanges(), reporter=None)
        outcome = step_apply_mutable_config(ctx)
        assert outcome.success is True


# ===================================================================
# step_start_docker  (step 12)
# ===================================================================


class TestStepStartDockerSkip:
    """Docker auto-start not configured."""

    def test_not_configured_returns_skip(self) -> None:
        ctx = _make_context()
        outcome = step_start_docker(
            ctx,
            should_auto_start_docker=False,
            start_docker_fn=lambda *a, **kw: True,
        )
        _assert_success(outcome, "Docker auto-start not configured, skipping")


class TestStepStartDockerSuccess:
    """Docker starts successfully."""

    def test_docker_started(self) -> None:
        ctx = _make_context()
        outcome = step_start_docker(
            ctx,
            should_auto_start_docker=True,
            start_docker_fn=lambda *a, **kw: True,
        )
        _assert_success(outcome, "Docker services started")

    def test_passes_output_path_and_config(self) -> None:
        ctx = _make_context(output_path=Path("/fake/project"), qs_config={"key": "val"})
        captured: list[Any] = []

        def _start(output_path: Path, qs_config: Any) -> bool:
            captured.extend([output_path, qs_config])
            return True

        step_start_docker(
            ctx,
            should_auto_start_docker=True,
            start_docker_fn=_start,
        )
        assert captured == [Path("/fake/project"), {"key": "val"}]


class TestStepStartDockerFailure:
    """Docker startup fails."""

    def test_docker_failed(self) -> None:
        ctx = _make_context()
        outcome = step_start_docker(
            ctx,
            should_auto_start_docker=True,
            start_docker_fn=lambda *a, **kw: False,
        )
        _assert_failure(outcome, "docker startup", "Docker auto-start failed")


# ===================================================================
# step_run_migrations  (step 13)
# ===================================================================


class TestStepRunMigrationsDockerPath:
    """Migrations via Docker container."""

    def test_docker_migrations_success(self) -> None:
        ctx = _make_context()
        outcome = step_run_migrations(
            ctx,
            should_auto_start_docker=True,
            docker_started=True,
            run_migrations_in_docker_fn=lambda _path: True,
        )
        _assert_success(outcome, "Database migrations completed in Docker")

    def test_docker_migrations_failure(self) -> None:
        ctx = _make_context()
        outcome = step_run_migrations(
            ctx,
            should_auto_start_docker=True,
            docker_started=True,
            run_migrations_in_docker_fn=lambda _path: False,
        )
        _assert_failure(
            outcome, "database migrations", "Migrations failed inside Docker"
        )

    def test_docker_migrations_passes_output_path(self) -> None:
        ctx = _make_context(output_path=Path("/fake/project"))
        captured: list[Path] = []

        step_run_migrations(
            ctx,
            should_auto_start_docker=True,
            docker_started=True,
            run_migrations_in_docker_fn=lambda path: captured.append(path) or True,
        )
        assert captured == [Path("/fake/project")]


class TestStepRunMigrationsLocalPath:
    """Local migrations (existing-project or --no-docker path)."""

    def test_local_migrations_success(self) -> None:
        ctx = _make_context()
        outcome = step_run_migrations(
            ctx,
            should_auto_start_docker=False,
            docker_started=None,
            run_migrations_in_docker_fn=lambda _path: True,
            should_run_local_migrations=True,
            run_local_migrations_fn=lambda _path: True,
        )
        _assert_success(outcome, "Database migrations completed (local)")

    def test_local_migrations_failure(self) -> None:
        ctx = _make_context()
        outcome = step_run_migrations(
            ctx,
            should_auto_start_docker=False,
            docker_started=None,
            run_migrations_in_docker_fn=lambda _path: True,
            should_run_local_migrations=True,
            run_local_migrations_fn=lambda _path: False,
        )
        _assert_failure(
            outcome, "database migrations", "Local database migrations failed"
        )

    def test_local_migrations_callback_none(self) -> None:
        ctx = _make_context()
        outcome = step_run_migrations(
            ctx,
            should_auto_start_docker=False,
            docker_started=None,
            run_migrations_in_docker_fn=lambda _path: True,
            should_run_local_migrations=True,
            run_local_migrations_fn=None,
        )
        _assert_failure(
            outcome,
            "database migrations",
            "Local migrations requested but no callback provided",
        )

    def test_local_migrations_passes_output_path(self) -> None:
        ctx = _make_context(output_path=Path("/fake/project"))
        captured: list[Path] = []

        step_run_migrations(
            ctx,
            should_auto_start_docker=False,
            docker_started=None,
            run_migrations_in_docker_fn=lambda _path: True,
            should_run_local_migrations=True,
            run_local_migrations_fn=lambda path: captured.append(path) or True,
        )
        assert captured == [Path("/fake/project")]


class TestStepRunMigrationsSkip:
    """No migration path configured."""

    def test_both_docker_and_local_not_configured(self) -> None:
        ctx = _make_context()
        outcome = step_run_migrations(
            ctx,
            should_auto_start_docker=False,
            docker_started=None,
            run_migrations_in_docker_fn=lambda _path: True,
        )
        _assert_success(outcome, "Migrations step skipped")

    def test_docker_started_but_not_configured(self) -> None:
        """docker_started can be True even when should_auto_start_docker is False
        from a prior step; the migration step respects should_auto_start_docker."""
        ctx = _make_context()
        outcome = step_run_migrations(
            ctx,
            should_auto_start_docker=False,
            docker_started=True,
            run_migrations_in_docker_fn=lambda _path: True,
        )
        _assert_success(outcome, "Migrations step skipped")
