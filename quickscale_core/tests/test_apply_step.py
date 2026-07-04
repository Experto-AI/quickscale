"""Tests for quickscale_core.apply — ApplyStep dataclass and APPLY_STEPS registry.

Verifies that the registry satisfies the F12.1a/F12.3b roadmap acceptance criteria:
* Exactly 16 steps in strict 1-based order.
* Verbatim ``failed_step_label`` values (including the three ``None`` entries).
* ``step_id`` equals the verbatim label for the 13 labeled steps.
* ``ApplyStep`` is frozen/immutable.
* All ``step_id`` values are unique.
"""

from __future__ import annotations

import pytest

from quickscale_core.apply import APPLY_STEPS, ApplyStep, step_by_id


# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------


class TestApplyStepsRegistryShape:
    """The registry must contain exactly 16 steps in strict 1-based order.

    F12.3b adds the railway deploy step (order 14) between database
    migrations (13) and authoritative state persistence (now 15).
    """

    def test_length_is_16(self) -> None:
        assert len(APPLY_STEPS) == 16

    def test_order_is_one_based_contiguous(self) -> None:
        orders = [step.order for step in APPLY_STEPS]
        assert orders == list(range(1, 17))

    def test_order_is_strictly_increasing(self) -> None:
        orders = [step.order for step in APPLY_STEPS]
        for i in range(len(orders) - 1):
            assert orders[i] < orders[i + 1]

    def test_registry_is_tuple(self) -> None:
        assert isinstance(APPLY_STEPS, tuple)


# ---------------------------------------------------------------------------
# Verbatim failed_step_label sequence
# ---------------------------------------------------------------------------


# Authoritative ordered list of failed_step_label values (source-of-truth
# derived from apply_command.py _execute_apply_steps_locked).
_EXPECTED_LABELS: tuple[str | None, ...] = (
    "module embedding",  # step 1
    "post-embed state snapshot",  # step 2
    "managed module wiring generation",  # step 3
    "capture managed file hashes",  # step 4
    "backups gitignore hardening",  # step 5
    "notifications env example sync",  # step 6
    "analytics env example sync",  # step 7
    "billing env example sync",  # step 8
    "module dependency sync",  # step 9
    "post-generation dependency and migration setup",  # step 10
    None,  # step 11 — informational
    "docker startup",  # step 12
    "database migrations",  # step 13
    "railway deploy",  # step 14 — F12.3b
    "authoritative state persistence",  # step 15
    None,  # step 16 — informational
)


class TestApplyStepsLabels:
    """failed_step_label values must match the authoritative list verbatim.

    SA18.9 promoted step 4 from ``None`` (best-effort) to
    ``"capture managed file hashes"``, reducing the None count from 3 to 2
    and increasing the labeled count from 13 to 14.
    """

    def test_full_label_sequence_matches(self) -> None:
        actual = tuple(step.failed_step_label for step in APPLY_STEPS)
        assert actual == _EXPECTED_LABELS

    def test_none_positions_are_11_16(self) -> None:
        none_orders = [
            step.order for step in APPLY_STEPS if step.failed_step_label is None
        ]
        assert none_orders == [11, 16]

    def test_labeled_steps_count_is_14(self) -> None:
        labeled = [step for step in APPLY_STEPS if step.failed_step_label is not None]
        assert len(labeled) == 14


# ---------------------------------------------------------------------------
# step_id equals verbatim failed_step_label for labeled steps
# ---------------------------------------------------------------------------


class TestApplyStepsStepId:
    """For the 13 labeled steps, step_id must equal the failed_step_label string."""

    def test_labeled_step_ids_equal_labels(self) -> None:
        for step in APPLY_STEPS:
            if step.failed_step_label is not None:
                assert step.step_id == step.failed_step_label, (
                    f"step {step.order}: step_id={step.step_id!r} "
                    f"!= failed_step_label={step.failed_step_label!r}"
                )

    def test_all_step_ids_are_unique(self) -> None:
        ids = [step.step_id for step in APPLY_STEPS]
        assert len(ids) == len(set(ids)), f"Duplicate step_ids found: {ids}"

    def test_step_ids_are_non_empty_strings(self) -> None:
        for step in APPLY_STEPS:
            assert isinstance(step.step_id, str) and step.step_id


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestApplyStepImmutability:
    """ApplyStep must be frozen — mutating any field must raise."""

    def test_mutating_order_raises(self) -> None:
        step = APPLY_STEPS[0]
        with pytest.raises((AttributeError, TypeError)):
            step.order = 99  # type: ignore[misc]

    def test_mutating_step_id_raises(self) -> None:
        step = APPLY_STEPS[0]
        with pytest.raises((AttributeError, TypeError)):
            step.step_id = "hacked"  # type: ignore[misc]

    def test_mutating_reversible_raises(self) -> None:
        step = APPLY_STEPS[0]
        with pytest.raises((AttributeError, TypeError)):
            step.reversible = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Reversible field
# ---------------------------------------------------------------------------


class TestApplyStepsReversible:
    """All steps are non-reversible; the full apply pipeline has no rollback."""

    def test_all_steps_are_not_reversible(self) -> None:
        for step in APPLY_STEPS:
            assert step.reversible is False, (
                f"step {step.order} ({step.step_id!r}) unexpectedly has reversible=True"
            )


# ---------------------------------------------------------------------------
# step_by_id helper
# ---------------------------------------------------------------------------


class TestStepById:
    """step_by_id must return the correct step or raise KeyError."""

    def test_lookup_known_step(self) -> None:
        step = step_by_id("module embedding")
        assert step.order == 1
        assert step.failed_step_label == "module embedding"

    def test_lookup_step_4_by_descriptive_id(self) -> None:
        step = step_by_id("capture managed file hashes")
        assert step.order == 4
        assert step.failed_step_label == "capture managed file hashes"

    def test_lookup_railway_deploy_step(self) -> None:
        step = step_by_id("railway deploy")
        assert step.order == 14
        assert step.failed_step_label == "railway deploy"
        assert step.resume == "idempotent-rerun"

    def test_lookup_last_step(self) -> None:
        step = step_by_id("display next steps")
        assert step.order == 16
        assert step.failed_step_label is None

    def test_lookup_unknown_id_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            step_by_id("nonexistent step id")


# ---------------------------------------------------------------------------
# apply_action and resume descriptor regression lock
# ---------------------------------------------------------------------------


# Authoritative ordered sequence of (apply_action, resume) tuples, derived
# verbatim from APPLY_STEPS in quickscale_core/apply/step.py.
# If step.py changes either value for any step, this assertion fails —
# which is the intent: silent drift is a regression.
_EXPECTED_ACTION_RESUME: tuple[tuple[str, str], ...] = (
    ("module embedding", "idempotent-rerun"),  # step 1
    ("post-embed state snapshot", "idempotent-rerun"),  # step 2
    ("managed module wiring generation", "idempotent-rerun"),  # step 3
    ("capture managed file hashes", "idempotent-rerun"),  # step 4
    ("backups gitignore hardening", "idempotent-rerun"),  # step 5
    ("notifications env example sync", "idempotent-rerun"),  # step 6
    ("analytics env example sync", "idempotent-rerun"),  # step 7
    ("billing env example sync", "idempotent-rerun"),  # step 8
    ("module dependency sync", "idempotent-rerun"),  # step 9
    ("post-generation dependency and migration setup", "idempotent-rerun"),  # step 10
    ("apply mutable config", "idempotent-rerun"),  # step 11
    ("docker startup", "idempotent-rerun"),  # step 12
    ("database migrations", "idempotent-rerun"),  # step 13
    ("railway deploy", "idempotent-rerun"),  # step 14 — F12.3b
    ("finalize apply state", "finalize"),  # step 15 — differs from step_id
    ("display next steps", "display"),  # step 16 — resume=display, not idempotent-rerun
)


class TestApplyStepsActionResume:
    """apply_action and resume values must match the authoritative sequence verbatim.

    Steps 15 and 16 are intentionally different from the general pattern:
    - step 15: apply_action='finalize apply state' (not the step_id), resume='finalize'
    - step 16: resume='display' (not 'idempotent-rerun')
    Any future edit to step.py that silently changes these will cause a test failure.
    """

    def test_full_action_resume_sequence_matches(self) -> None:
        actual = tuple((step.apply_action, step.resume) for step in APPLY_STEPS)
        assert actual == _EXPECTED_ACTION_RESUME

    def test_idempotent_rerun_steps_are_1_through_14(self) -> None:
        idempotent_orders = [
            step.order for step in APPLY_STEPS if step.resume == "idempotent-rerun"
        ]
        assert idempotent_orders == list(range(1, 15))

    def test_step_15_has_finalize_resume(self) -> None:
        step = APPLY_STEPS[14]  # 0-based index for order=15
        assert step.order == 15
        assert step.resume == "finalize"
        assert step.apply_action == "finalize apply state"

    def test_step_16_has_display_resume(self) -> None:
        step = APPLY_STEPS[15]  # 0-based index for order=16
        assert step.order == 16
        assert step.resume == "display"
        assert step.apply_action == "display next steps"

    def test_apply_action_values_are_non_empty_strings(self) -> None:
        for step in APPLY_STEPS:
            assert isinstance(step.apply_action, str) and step.apply_action, (
                f"step {step.order}: apply_action is empty or not a string"
            )

    def test_resume_values_are_non_empty_strings(self) -> None:
        for step in APPLY_STEPS:
            assert isinstance(step.resume, str) and step.resume, (
                f"step {step.order}: resume is empty or not a string"
            )

    def test_resume_values_are_from_known_set(self) -> None:
        """resume must be one of the three documented sentinel values."""
        allowed = {"idempotent-rerun", "finalize", "display"}
        for step in APPLY_STEPS:
            assert step.resume in allowed, (
                f"step {step.order}: unexpected resume={step.resume!r}"
            )


# ---------------------------------------------------------------------------
# ApplyStep field types
# ---------------------------------------------------------------------------


class TestApplyStepFieldTypes:
    """Each ApplyStep field must satisfy its declared type contract."""

    def test_all_fields_have_correct_types(self) -> None:
        for step in APPLY_STEPS:
            assert isinstance(step.order, int)
            assert isinstance(step.step_id, str)
            assert step.failed_step_label is None or isinstance(
                step.failed_step_label, str
            )
            assert isinstance(step.apply_action, str)
            assert isinstance(step.resume, str)
            assert isinstance(step.reversible, bool)

    def test_apply_step_is_instance_of_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(ApplyStep)
