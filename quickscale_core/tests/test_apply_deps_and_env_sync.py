"""Tests for quickscale_core.apply.steps.deps and .env_sync.

Covers:
* ``step_sync_dependencies`` — success and failure.
* ``step_post_generation_setup`` — success and failure.
* ``step_backups_gitignore`` — success and failure.
* ``step_notifications_env_sync`` — success and failure.
* ``step_analytics_env_sync`` — success and failure.
* ``step_billing_env_sync`` — success and failure.

Each step body follows the same pattern: inject a callback that returns
``True`` (success) or ``False`` (failure) and verify the ``StepOutcome``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quickscale_core.apply.steps.deps import (
    step_post_generation_setup,
    step_sync_dependencies,
)
from quickscale_core.apply.steps.env_sync import (
    step_analytics_env_sync,
    step_backups_gitignore,
    step_billing_env_sync,
    step_notifications_env_sync,
)
from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: Any) -> StepContext:
    """Build a minimal StepContext with overrides for test ergonomics."""
    return StepContext(
        output_path=Path("/fake/project"),
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
# deps — step_sync_dependencies
# ===================================================================


class TestStepSyncDependencies:
    """step_sync_dependencies: module dependency sync."""

    def test_success(self) -> None:
        ctx = _make_context(qs_config={})
        outcome = step_sync_dependencies(
            ctx,
            sync_project_deps_fn=lambda _path, _config: True,
        )
        _assert_success(outcome, "Module dependencies synced")

    def test_failure(self) -> None:
        ctx = _make_context(qs_config={})
        outcome = step_sync_dependencies(
            ctx,
            sync_project_deps_fn=lambda _path, _config: False,
        )
        _assert_failure(
            outcome,
            "module dependency sync",
            "Unable to reconcile",
        )


# ===================================================================
# deps — step_post_generation_setup
# ===================================================================


class TestStepPostGenerationSetup:
    """step_post_generation_setup: post-generation dependency and migration setup."""

    def test_success(self) -> None:
        ctx = _make_context()
        outcome = step_post_generation_setup(
            ctx,
            run_post_gen_steps_fn=lambda _path: True,
        )
        _assert_success(outcome, "Post-generation dependencies completed")

    def test_failure(self) -> None:
        ctx = _make_context()
        outcome = step_post_generation_setup(
            ctx,
            run_post_gen_steps_fn=lambda _path: False,
        )
        _assert_failure(
            outcome,
            "post-generation dependency and migration setup",
            "Poetry lock refresh",
        )

    def test_passes_output_path(self) -> None:
        captured: list[Path] = []

        def _capture(path: Path) -> bool:
            captured.append(path)
            return True

        ctx = _make_context()
        step_post_generation_setup(
            ctx,
            run_post_gen_steps_fn=_capture,
        )
        assert captured == [Path("/fake/project")]


# ===================================================================
# env_sync — parametrised over all four sync functions
# ===================================================================

_ENV_SYNC_CASES: list[Any] = [
    (
        "backups_gitignore",
        step_backups_gitignore,
        "ensure_backups_ignore_fn",
        "Backups gitignore rules applied",
        "backups gitignore hardening",
        "Unable to update .gitignore",
    ),
    (
        "notifications_env_sync",
        step_notifications_env_sync,
        "sync_notifications_fn",
        "Notifications env vars synced",
        "notifications env example sync",
        "Unable to update .env.example with notifications",
    ),
    (
        "analytics_env_sync",
        step_analytics_env_sync,
        "sync_analytics_fn",
        "Analytics env vars synced",
        "analytics env example sync",
        "Unable to update .env.example with analytics",
    ),
    (
        "billing_env_sync",
        step_billing_env_sync,
        "sync_billing_fn",
        "Billing env vars synced",
        "billing env example sync",
        "Unable to update .env.example with billing",
    ),
]


class TestEnvSyncFunctions:
    """Parametrised success/failure tests for all four env-sync step bodies."""

    @pytest.mark.parametrize(
        ("_name", "step_func", "kwarg", "success_msg", "fail_label", "fail_msg"),
        _ENV_SYNC_CASES,
    )
    def test_success(
        self,
        _name: str,
        step_func: Any,
        kwarg: str,
        success_msg: str,
        fail_label: str,
        fail_msg: str,
    ) -> None:
        ctx = _make_context(qs_config={})
        outcome = step_func(ctx, **{kwarg: lambda _path, _config: True})
        _assert_success(outcome, success_msg)

    @pytest.mark.parametrize(
        ("_name", "step_func", "kwarg", "success_msg", "fail_label", "fail_msg"),
        _ENV_SYNC_CASES,
    )
    def test_failure(
        self,
        _name: str,
        step_func: Any,
        kwarg: str,
        success_msg: str,
        fail_label: str,
        fail_msg: str,
    ) -> None:
        ctx = _make_context(qs_config={})
        outcome = step_func(ctx, **{kwarg: lambda _path, _config: False})
        _assert_failure(outcome, fail_label, fail_msg)

    @pytest.mark.parametrize(
        ("_name", "step_func", "kwarg", "success_msg", "fail_label", "fail_msg"),
        _ENV_SYNC_CASES,
    )
    def test_passes_output_path_and_config(
        self,
        _name: str,
        step_func: Any,
        kwarg: str,
        success_msg: str,
        fail_label: str,
        fail_msg: str,
    ) -> None:
        captured_args: list[Any] = []

        def _capture(path: Any, config: Any) -> bool:
            captured_args.extend([path, config])
            return True

        ctx = _make_context(qs_config={"project_name": "test"})
        step_func(ctx, **{kwarg: _capture})
        assert captured_args == [Path("/fake/project"), {"project_name": "test"}]
