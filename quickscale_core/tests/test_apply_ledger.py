"""Tests for the apply recovery ledger (F12.1b, SA317).

The ledger records the resume pointer and diagnostic progress only.  Applied
state lives in ``.quickscale/state.yml``; old ledgers that still embed an
applied-state section must load with that section ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from quickscale_core.apply.ledger import (
    LedgerError,
    LedgerManager,
    RecoveryLedger,
    ResumeCheckpoint,
    StepProgress,
)
from quickscale_core.apply.step import APPLY_STEPS
from quickscale_core.schema.state_schema import StateError

_GIT_INDEX_CHECKPOINT = "deadbeefcafebabedeadbeefcafebabedeadbeef"
_FIRST_STEP_ID = APPLY_STEPS[0].step_id
_SECOND_STEP_ID = APPLY_STEPS[1].step_id


def _minimal_ledger_dict() -> dict[str, Any]:
    """Return the smallest valid ledger mapping."""
    return {"git_index_checkpoint": _GIT_INDEX_CHECKPOINT}


def _write_yaml(path: Path, data: Any) -> None:
    """Write a YAML mapping to *path*, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


class TestLedgerAbsent:
    """Absent ledger semantics."""

    def test_load_returns_none_when_file_absent(self, tmp_path: Path) -> None:
        mgr = LedgerManager(tmp_path)

        assert mgr.load() is None


class TestLedgerPresentValid:
    """A present, valid ledger parses its recovery metadata."""

    def test_load_returns_ledger(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml", _minimal_ledger_dict()
        )

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.git_index_checkpoint == _GIT_INDEX_CHECKPOINT
        assert loaded.step_progress is None
        assert loaded.resume_checkpoint is None

    def test_ledger_has_no_applied_state_field(self, tmp_path: Path) -> None:
        """The ledger is not a second applied-state owner."""
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml", _minimal_ledger_dict()
        )

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert not hasattr(loaded, "applied_state")

    def test_legacy_applied_state_section_is_ignored(self, tmp_path: Path) -> None:
        """An old ledger keeps loading; its embedded state is not reinterpreted."""
        data = {
            "version": "1",
            "project": {
                "slug": "myapp",
                "package": "myapp",
                "theme": "showcase_react",
                "created_at": "2025-01-01T00:00:00",
                "last_applied": "2025-01-01T00:00:00",
            },
            "modules": {
                "auth": {
                    "version": "0.71.0",
                    "commit_sha": "abc123",
                    "embedded_at": "2025-01-01T00:00:00",
                }
            },
            "managed_files": [
                {"path": "a.py", "hash": "abc", "applied_at": "2025-01-01"}
            ],
            "resume_checkpoint": {"resume_step_id": _FIRST_STEP_ID},
            "git_index_checkpoint": _GIT_INDEX_CHECKPOINT,
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.git_index_checkpoint == _GIT_INDEX_CHECKPOINT
        assert loaded.resume_checkpoint is not None
        assert loaded.resume_checkpoint.resume_step_id == _FIRST_STEP_ID

    def test_step_progress_is_none_when_absent(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml", _minimal_ledger_dict()
        )

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.step_progress is None


class TestLedgerPresentValidWithStepProgress:
    """Step-progress parsing and validation."""

    def test_load_returns_ledger_with_step_progress(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": _FIRST_STEP_ID, "status": "completed"},
            {"step_id": _SECOND_STEP_ID, "status": "completed", "detail": "ok"},
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.step_progress is not None
        assert set(loaded.step_progress) == {_FIRST_STEP_ID, _SECOND_STEP_ID}
        assert loaded.step_progress[_SECOND_STEP_ID].detail == "ok"

    def test_all_16_step_ids_are_valid(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": step.step_id, "status": "completed"} for step in APPLY_STEPS
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.step_progress is not None
        assert set(loaded.step_progress) == {step.step_id for step in APPLY_STEPS}


class TestLedgerMalformed:
    """Malformed ledgers fail hard."""

    def test_not_a_dict_raises(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", ["not-a-dict"])

        with pytest.raises(LedgerError, match="must be a YAML mapping"):
            LedgerManager(tmp_path).load()

    def test_missing_git_index_checkpoint_raises(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", {})

        with pytest.raises(LedgerError, match="git_index_checkpoint"):
            LedgerManager(tmp_path).load()

    def test_empty_git_index_checkpoint_raises(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml",
            {"git_index_checkpoint": ""},
        )

        with pytest.raises(LedgerError, match="git_index_checkpoint"):
            LedgerManager(tmp_path).load()

    def test_non_string_git_index_checkpoint_raises(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml",
            {"git_index_checkpoint": 42},
        )

        with pytest.raises(LedgerError, match="git_index_checkpoint"):
            LedgerManager(tmp_path).load()

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        recovery = tmp_path / ".quickscale" / "apply-recovery.yml"
        recovery.parent.mkdir(parents=True, exist_ok=True)
        recovery.write_text("project: [unterminated\n")

        with pytest.raises(LedgerError, match="Failed to parse"):
            LedgerManager(tmp_path).load()


class TestLedgerUnknownStepId:
    """Unknown or malformed step ids fail hard."""

    def test_unknown_step_id_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [{"step_id": "not-a-step", "status": "completed"}]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="unknown step_id"):
            LedgerManager(tmp_path).load()

    def test_mixed_valid_and_unknown_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": _FIRST_STEP_ID, "status": "completed"},
            {"step_id": "not-a-step", "status": "completed"},
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="unknown step_id"):
            LedgerManager(tmp_path).load()

    def test_missing_step_id_field_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [{"status": "completed"}]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="missing required field 'step_id'"):
            LedgerManager(tmp_path).load()


class TestLedgerRoundTrip:
    """Save/load round trips preserve recovery metadata."""

    def test_round_trip_no_step_progress(self, tmp_path: Path) -> None:
        ledger = RecoveryLedger(git_index_checkpoint=_GIT_INDEX_CHECKPOINT)
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.git_index_checkpoint == _GIT_INDEX_CHECKPOINT
        assert loaded.step_progress is None
        assert loaded.resume_checkpoint is None

    def test_round_trip_with_step_progress(self, tmp_path: Path) -> None:
        sp = {
            _FIRST_STEP_ID: StepProgress(
                step_id=_FIRST_STEP_ID, status="completed", detail=None
            ),
            _SECOND_STEP_ID: StepProgress(
                step_id=_SECOND_STEP_ID, status="failed", detail="network timeout"
            ),
        }
        ledger = RecoveryLedger(
            step_progress=sp,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.step_progress is not None
        assert len(loaded.step_progress) == 2
        assert loaded.step_progress[_SECOND_STEP_ID].detail == "network timeout"

    def test_round_trip_all_16_steps(self, tmp_path: Path) -> None:
        sp = {
            s.step_id: StepProgress(step_id=s.step_id, status="completed")
            for s in APPLY_STEPS
        }
        ledger = RecoveryLedger(
            step_progress=sp,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.step_progress is not None
        assert set(loaded.step_progress) == {s.step_id for s in APPLY_STEPS}

    def test_save_uses_tmp_then_replaces(self, tmp_path: Path) -> None:
        """Atomic write: tmp file must not exist after a successful save."""
        mgr = LedgerManager(tmp_path)

        mgr.save(RecoveryLedger(git_index_checkpoint=_GIT_INDEX_CHECKPOINT))

        assert mgr.ledger_file.exists()
        assert not mgr._tmp_file.exists()

    def test_save_creates_quickscale_dir(self, tmp_path: Path) -> None:
        mgr = LedgerManager(tmp_path)

        assert not (tmp_path / ".quickscale").exists()
        mgr.save(RecoveryLedger(git_index_checkpoint=_GIT_INDEX_CHECKPOINT))
        assert mgr.ledger_file.exists()

    def test_yaml_convention_default_flow_style_false(self, tmp_path: Path) -> None:
        mgr = LedgerManager(tmp_path)
        mgr.save(RecoveryLedger(git_index_checkpoint=_GIT_INDEX_CHECKPOINT))

        text = mgr.ledger_file.read_text()
        assert "git_index_checkpoint:" in text
        assert "{" not in text


class TestPresenceSemantics:
    """Ledger presence drives the recovery gate, never step_progress."""

    def test_ledger_is_not_none_when_file_present_with_step_progress(
        self, tmp_path: Path
    ) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [{"step_id": _FIRST_STEP_ID, "status": "completed"}]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        assert LedgerManager(tmp_path).load() is not None

    def test_ledger_is_none_when_file_absent_regardless_of_logic(
        self, tmp_path: Path
    ) -> None:
        assert LedgerManager(tmp_path).load() is None


class TestLedgerErrorHierarchy:
    """LedgerError stays catchable as StateError."""

    def test_ledger_error_is_state_error(self) -> None:
        assert issubclass(LedgerError, StateError)

    def test_ledger_error_caught_as_state_error(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", {})

        with pytest.raises(StateError):
            LedgerManager(tmp_path).load()


class TestStepProgressFromDict:
    """StepProgress validates its own fields."""

    def test_non_dict_entry_raises(self) -> None:
        with pytest.raises(LedgerError, match="must be a mapping"):
            StepProgress.from_dict("not-a-mapping")  # type: ignore[arg-type]

    def test_empty_step_id_raises(self) -> None:
        with pytest.raises(LedgerError, match="must be a non-empty string"):
            StepProgress.from_dict({"step_id": "", "status": "completed"})

    def test_non_string_step_id_raises(self) -> None:
        with pytest.raises(LedgerError, match="must be a non-empty string"):
            StepProgress.from_dict({"step_id": 1, "status": "completed"})

    def test_empty_status_raises(self) -> None:
        with pytest.raises(LedgerError, match="must be a non-empty string"):
            StepProgress.from_dict({"step_id": _FIRST_STEP_ID, "status": ""})

    def test_non_string_status_raises(self) -> None:
        with pytest.raises(LedgerError, match="must be a non-empty string"):
            StepProgress.from_dict({"step_id": _FIRST_STEP_ID, "status": 1})

    def test_non_string_detail_raises(self) -> None:
        with pytest.raises(LedgerError, match="must be a string or absent"):
            StepProgress.from_dict(
                {"step_id": _FIRST_STEP_ID, "status": "completed", "detail": 1}
            )

    def test_missing_status_field_raises(self) -> None:
        with pytest.raises(LedgerError, match="missing required field 'status'"):
            StepProgress.from_dict({"step_id": _FIRST_STEP_ID})


class TestStepProgressDictKeyedForm:
    """Hand-authored dict-keyed step_progress remains accepted."""

    def test_dict_keyed_step_progress_parses(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = {
            _FIRST_STEP_ID: {"status": "completed", "detail": "ok"}
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.step_progress is not None
        assert loaded.step_progress[_FIRST_STEP_ID].detail == "ok"

    def test_dict_keyed_with_unknown_step_id_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = {"not-a-step": {"status": "completed"}}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="unknown step_id"):
            LedgerManager(tmp_path).load()

    def test_dict_keyed_with_non_dict_value_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = {_FIRST_STEP_ID: "completed"}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="must be a mapping"):
            LedgerManager(tmp_path).load()

    def test_invalid_step_progress_type_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = "not-a-list-or-dict"
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="must be a list or mapping"):
            LedgerManager(tmp_path).load()


class TestRecoveryLedgerGitIndexCheckpoint:
    """git_index_checkpoint is required and round-trips."""

    def test_round_trip_with_git_index_checkpoint(self, tmp_path: Path) -> None:
        ledger = RecoveryLedger(git_index_checkpoint=_GIT_INDEX_CHECKPOINT)
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.git_index_checkpoint == _GIT_INDEX_CHECKPOINT

    def test_fail_hard_on_missing_git_index_checkpoint(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml",
            {"step_progress": []},
        )

        with pytest.raises(LedgerError, match="git_index_checkpoint"):
            LedgerManager(tmp_path).load()

    def test_parse_with_inline_git_index_checkpoint(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml",
            {"git_index_checkpoint": "abc123"},
        )

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.git_index_checkpoint == "abc123"

    def test_dict_includes_git_index_checkpoint_always(self) -> None:
        ledger = RecoveryLedger(git_index_checkpoint="abc123")

        assert ledger.to_dict()["git_index_checkpoint"] == "abc123"


class TestPackageLevelReExports:
    """The apply package keeps exporting the ledger surface."""

    def test_ledger_error_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import LedgerError as Imported

        assert Imported is LedgerError

    def test_ledger_manager_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import LedgerManager as Imported

        assert Imported is LedgerManager

    def test_recovery_ledger_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import RecoveryLedger as Imported

        assert Imported is RecoveryLedger

    def test_step_progress_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import StepProgress as Imported

        assert Imported is StepProgress

    def test_resume_checkpoint_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import ResumeCheckpoint as Imported

        assert Imported is ResumeCheckpoint


class TestAF5ResumeCheckpoint:
    """Resume-checkpoint parsing and round trips."""

    def test_af6_era_ledger_without_resume_checkpoint_loads(
        self, tmp_path: Path
    ) -> None:
        _write_yaml(
            tmp_path / ".quickscale" / "apply-recovery.yml", _minimal_ledger_dict()
        )

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.resume_checkpoint is None

    def test_load_with_valid_resume_checkpoint(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {"resume_step_id": _FIRST_STEP_ID}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.resume_checkpoint is not None
        assert loaded.resume_checkpoint.resume_step_id == _FIRST_STEP_ID

    def test_load_with_full_resume_checkpoint(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": _FIRST_STEP_ID,
            "suspend_after_step_id": _SECOND_STEP_ID,
            "checkpoint_tree_id": "deadbeefcafebabedeadbeefcafebabedeadbeef",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        loaded = LedgerManager(tmp_path).load()

        assert loaded is not None
        assert loaded.resume_checkpoint is not None
        assert loaded.resume_checkpoint.suspend_after_step_id == _SECOND_STEP_ID

    def test_round_trip_resume_checkpoint(self, tmp_path: Path) -> None:
        rc = ResumeCheckpoint(
            resume_step_id=_FIRST_STEP_ID,
            suspend_after_step_id=_SECOND_STEP_ID,
            checkpoint_tree_id="aabbccddeeff00112233445566778899aabbccdd",
        )
        ledger = RecoveryLedger(
            resume_checkpoint=rc,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.resume_checkpoint is not None
        assert loaded.resume_checkpoint.resume_step_id == _FIRST_STEP_ID
        assert loaded.resume_checkpoint.suspend_after_step_id == _SECOND_STEP_ID
        assert (
            loaded.resume_checkpoint.checkpoint_tree_id
            == "aabbccddeeff00112233445566778899aabbccdd"
        )

    def test_round_trip_resume_checkpoint_without_optional_fields(
        self, tmp_path: Path
    ) -> None:
        rc = ResumeCheckpoint(resume_step_id=_FIRST_STEP_ID)
        ledger = RecoveryLedger(
            resume_checkpoint=rc,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.resume_checkpoint is not None
        assert loaded.resume_checkpoint.resume_step_id == _FIRST_STEP_ID
        assert loaded.resume_checkpoint.suspend_after_step_id is None
        assert loaded.resume_checkpoint.checkpoint_tree_id is None

    def test_resume_checkpoint_not_a_dict_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = "just-a-string"
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="must be a mapping"):
            LedgerManager(tmp_path).load()

    def test_resume_checkpoint_missing_resume_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="missing required field"):
            LedgerManager(tmp_path).load()

    def test_resume_checkpoint_empty_resume_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {"resume_step_id": ""}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="non-empty string"):
            LedgerManager(tmp_path).load()

    def test_resume_checkpoint_unknown_resume_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {"resume_step_id": "not-a-step"}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="unknown step_id"):
            LedgerManager(tmp_path).load()

    def test_resume_checkpoint_unknown_suspend_after_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": _FIRST_STEP_ID,
            "suspend_after_step_id": "not-a-step",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="unknown suspend_after_step_id"):
            LedgerManager(tmp_path).load()

    def test_resume_checkpoint_empty_checkpoint_tree_id_raises(
        self, tmp_path: Path
    ) -> None:
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": _FIRST_STEP_ID,
            "checkpoint_tree_id": "",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        with pytest.raises(LedgerError, match="checkpoint_tree_id"):
            LedgerManager(tmp_path).load()

    def test_resume_checkpoint_from_dict_non_dict_value_raises(self) -> None:
        with pytest.raises(LedgerError, match="must be a mapping"):
            ResumeCheckpoint.from_dict("not-a-mapping")  # type: ignore[arg-type]

    def test_resume_checkpoint_from_dict_missing_resume_step_id_raises(self) -> None:
        with pytest.raises(LedgerError, match="missing required field"):
            ResumeCheckpoint.from_dict({})

    def test_resume_checkpoint_from_dict_non_string_resume_step_id_raises(self) -> None:
        with pytest.raises(LedgerError, match="non-empty string"):
            ResumeCheckpoint.from_dict({"resume_step_id": 1})

    def test_resume_checkpoint_from_dict_empty_suspend_after_raises(self) -> None:
        with pytest.raises(LedgerError, match="non-empty string"):
            ResumeCheckpoint.from_dict(
                {"resume_step_id": _FIRST_STEP_ID, "suspend_after_step_id": ""}
            )
