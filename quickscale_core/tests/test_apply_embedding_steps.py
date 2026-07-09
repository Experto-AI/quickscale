"""Tests for quickscale_core.apply.steps.embedding.

Covers:
* ``step_embed_modules`` — no-modules skip, success, failure, dirty/clean
  worktree, partial commit failure, provenance tracking.
* ``step_post_embed_snapshot`` — success, build-state exception, git
  index capture failure.
* ``EmbedModulesResult`` and ``GitIndexSnapshot`` dataclasses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quickscale_core.apply.steps.embedding import (
    EmbedModulesResult,
    GitIndexSnapshot,
    step_embed_modules,
    step_post_embed_snapshot,
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
# step_embed_modules
# ===================================================================


class TestStepEmbedModulesNoModules:
    """no_modules=True or empty modules_to_embed → immediate success."""

    def test_no_modules_flag_returns_success(self) -> None:
        ctx = _make_context()
        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=True,
            embed_one_module=lambda *a, **kw: True,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        _assert_success(outcome, "No modules to embed")

    def test_empty_modules_list_returns_success(self) -> None:
        ctx = _make_context()
        outcome = step_embed_modules(
            ctx,
            modules_to_embed=[],
            no_modules=False,
            embed_one_module=lambda *a, **kw: True,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        _assert_success(outcome, "No modules to embed")

    def test_does_not_call_callbacks_when_skipped(self) -> None:
        ctx = _make_context()
        embed_calls: list[Any] = []

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=True,
            embed_one_module=lambda *a, **kw: embed_calls.append(1) or True,
            commit_changes=lambda *a, **kw: embed_calls.append(2) or True,
            is_working_directory_clean_fn=lambda *a: embed_calls.append(3) or True,
        )

        assert outcome.success is True
        assert embed_calls == []


class TestStepEmbedModulesSuccess:
    """Happy path: one or more modules are embedded successfully."""

    def test_single_module_success(self) -> None:
        ctx = _make_context()
        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: True,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        _assert_success(outcome, "Embedded 1 module(s): auth")
        assert ctx.embedded_modules == ["auth"]

    def test_multiple_modules_success(self) -> None:
        ctx = _make_context()
        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth", "social"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: True,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        _assert_success(outcome, "Embedded 2 module(s): auth, social")
        assert ctx.embedded_modules == ["auth", "social"]

    def test_provenance_captured(self) -> None:
        ctx = _make_context()

        def _embed(output_path: Any, module_name: str, **kwargs: Any) -> bool:
            sink = kwargs.get("provenance_sink", [])
            sink.append({"module": module_name, "version": "1.0"})
            return True

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=_embed,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        assert outcome.success is True
        assert ctx.provenance_payloads == {"auth": {"module": "auth", "version": "1.0"}}

    def test_provenance_empty_when_not_provided(self) -> None:
        ctx = _make_context()

        def _embed(*args: Any, **kwargs: Any) -> bool:
            return True

        step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=_embed,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        assert ctx.provenance_payloads == {}

    def test_skip_auth_migration_check_when_no_existing_state(self) -> None:
        ctx = _make_context(existing_state=None)
        captured_kwargs: dict[str, Any] = {}

        def _embed(*args: Any, **kwargs: Any) -> bool:
            captured_kwargs.update(kwargs)
            return True

        step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=_embed,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        assert captured_kwargs.get("skip_auth_migration_check") is True

    def test_skip_auth_migration_check_false_with_existing_state(self) -> None:
        ctx = _make_context(existing_state={"version": 1})
        captured_kwargs: dict[str, Any] = {}

        def _embed(*args: Any, **kwargs: Any) -> bool:
            captured_kwargs.update(kwargs)
            return True

        step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=_embed,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        assert captured_kwargs.get("skip_auth_migration_check") is False

    def test_passes_output_path_to_callbacks(self) -> None:
        ctx = _make_context(output_path=Path("/fake/project"))
        embed_args: list[Any] = []
        commit_args: list[Any] = []

        step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: embed_args.append(a) or True,
            commit_changes=lambda *a, **kw: commit_args.append(a) or True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        assert embed_args and embed_args[0][0] == Path("/fake/project")
        assert commit_args and commit_args[0][0] == Path("/fake/project")

    def test_commit_message_contains_module_name(self) -> None:
        ctx = _make_context()
        commit_messages: list[str] = []

        step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: True,
            commit_changes=lambda *a, **kw: commit_messages.append(a[1]) or True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        assert "auth" in commit_messages[0]


class TestStepEmbedModulesFailure:
    """Embed failure paths including worktree state and partial commits."""

    def test_embed_failure_dirty_worktree_partial_commit_succeeds(self) -> None:
        """Embed fails, worktree dirty, partial commit succeeds — general failure."""
        ctx = _make_context()
        commit_messages: list[str] = []

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: False,
            commit_changes=lambda output_path, msg: commit_messages.append(msg) or True,
            is_working_directory_clean_fn=lambda *a: False,
        )
        _assert_failure(
            outcome,
            "module embedding",
            "Module embedding failed for required module: auth",
        )
        assert ctx.embed_failed_module == "auth"
        assert "Partial module: auth (incomplete)" in commit_messages

    def test_embed_failure_dirty_worktree_partial_commit_fails(self) -> None:
        """Embed fails, worktree dirty, partial commit fails — specific message."""
        ctx = _make_context()

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: False,
            commit_changes=lambda *a, **kw: False,
            is_working_directory_clean_fn=lambda *a: False,
        )
        _assert_failure(outcome, "module embedding", "partial module checkpoint commit")
        assert ctx.embed_commit_failure is True
        assert ctx.embedded_modules == []
        assert ctx.provenance_payloads == {}

    def test_embed_failure_clean_worktree_no_commit(self) -> None:
        """Embed fails, worktree clean — no partial commit attempted."""
        ctx = _make_context()
        commit_calls: list[tuple[Any, ...]] = []

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: False,
            commit_changes=lambda *a, **kw: commit_calls.append(a) or True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        _assert_failure(
            outcome,
            "module embedding",
            "Module embedding failed for required module: auth",
        )
        assert commit_calls == []

    def test_commit_after_successful_embed_fails(self) -> None:
        """Embed succeeds but checkpoint commit after embed fails."""
        ctx = _make_context()

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: True,
            commit_changes=lambda *a, **kw: False,
            is_working_directory_clean_fn=lambda *a: True,
        )
        _assert_failure(outcome, "module embedding", "checkpoint commit")
        assert ctx.embed_commit_failure is True

    def test_context_state_on_failure_with_prior_success(self) -> None:
        """When first module succeeds and second fails, ctx has first module."""
        ctx = _make_context()

        call_count: list[int] = []

        def _embed(*args: Any, **kwargs: Any) -> bool:
            call_count.append(1)
            return len(call_count) == 1  # first call succeeds, second fails

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth", "social"],
            no_modules=False,
            embed_one_module=_embed,
            commit_changes=lambda *a, **kw: True,
            is_working_directory_clean_fn=lambda *a: True,
        )
        _assert_failure(
            outcome,
            "module embedding",
            "Module embedding failed for required module: social",
        )
        assert ctx.embedded_modules == ["auth"]

    def test_embed_failure_updates_embedded_modules_on_partial_commit_fail(
        self,
    ) -> None:
        """When partial commit fails, ctx.embedded_modules is set to empty list."""
        ctx = _make_context()

        outcome = step_embed_modules(
            ctx,
            modules_to_embed=["auth"],
            no_modules=False,
            embed_one_module=lambda *a, **kw: False,
            commit_changes=lambda *a, **kw: False,
            is_working_directory_clean_fn=lambda *a: False,
        )
        assert outcome.success is False
        assert ctx.embedded_modules == []


# ===================================================================
# step_post_embed_snapshot
# ===================================================================


class TestStepPostEmbedSnapshotSuccess:
    """Happy path for post-embed state snapshot capture."""

    def test_success_with_mock_snapshot_and_git_index(self) -> None:
        ctx = _make_context()

        outcome = step_post_embed_snapshot(
            ctx,
            build_state_snapshot=lambda: {"applied": True},
            capture_git_index=lambda: GitIndexSnapshot(tree_id="abc123"),
        )
        _assert_success(
            outcome, "Post-embed state snapshot and git index checkpoint captured"
        )
        assert ctx.state_snapshot == {"applied": True}
        assert ctx.checkpoint_tree_id == "abc123"

    def test_state_snapshot_is_none_but_not_failure(self) -> None:
        """build_state_snapshot can return any value; it's stored as-is."""
        ctx = _make_context()

        outcome = step_post_embed_snapshot(
            ctx,
            build_state_snapshot=lambda: None,
            capture_git_index=lambda: GitIndexSnapshot(tree_id="def456"),
        )
        assert outcome.success is True
        assert ctx.state_snapshot is None
        assert ctx.checkpoint_tree_id == "def456"


class TestStepPostEmbedSnapshotFailure:
    """Failure paths for post-embed state snapshot capture."""

    def test_build_state_snapshot_raises_exception(self) -> None:
        ctx = _make_context()

        outcome = step_post_embed_snapshot(
            ctx,
            build_state_snapshot=lambda: (_ for _ in ()).throw(
                ValueError("corrupt data")
            ),
            capture_git_index=lambda: GitIndexSnapshot(tree_id="abc"),
        )
        _assert_failure(outcome, "post-embed state snapshot", "corrupt data")

    def test_capture_git_index_returns_none(self) -> None:
        ctx = _make_context()

        outcome = step_post_embed_snapshot(
            ctx,
            build_state_snapshot=lambda: {"applied": True},
            capture_git_index=lambda: None,
        )
        _assert_failure(
            outcome,
            "post-embed state snapshot",
            "git index tree id",
        )

    def test_context_not_updated_on_failure(self) -> None:
        ctx = _make_context()

        step_post_embed_snapshot(
            ctx,
            build_state_snapshot=lambda: (_ for _ in ()).throw(RuntimeError("fail")),
            capture_git_index=lambda: GitIndexSnapshot(tree_id="abc"),
        )
        assert ctx.state_snapshot is None
        assert ctx.checkpoint_tree_id is None


# ===================================================================
# Dataclass tests
# ===================================================================


class TestEmbedModulesResult:
    """EmbedModulesResult dataclass."""

    def test_defaults(self) -> None:
        result = EmbedModulesResult(success=True)
        assert result.success is True
        assert result.embedded_modules == []
        assert result.failed_module is None
        assert result.provenance_payloads is None
        assert result.commit_sha_map == {}

    def test_with_values(self) -> None:
        result = EmbedModulesResult(
            success=False,
            embedded_modules=["auth"],
            failed_module="social",
            provenance_payloads={"auth": {"sha": "abc"}},
            commit_sha_map={"auth": "abc123"},
        )
        assert result.success is False
        assert result.embedded_modules == ["auth"]
        assert result.failed_module == "social"
        assert result.provenance_payloads == {"auth": {"sha": "abc"}}
        assert result.commit_sha_map == {"auth": "abc123"}


class TestGitIndexSnapshot:
    """GitIndexSnapshot dataclass."""

    def test_tree_id(self) -> None:
        snap = GitIndexSnapshot(tree_id="abc123def456")
        assert snap.tree_id == "abc123def456"
