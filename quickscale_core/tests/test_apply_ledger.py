"""Tests for quickscale_core.apply.ledger — F12.1b acceptance criteria.

Verifies:
* present-valid ledger  -> parsed :class:`RecoveryLedger`
* present-valid ledger WITHOUT step_progress -> parsed (step_progress is None)
* absent ledger file -> ``None``
* malformed: not-a-dict -> raises :class:`LedgerError`
* malformed: missing required applied-state field -> raises :class:`LedgerError`
* step_progress with unknown step id -> raises :class:`LedgerError`
* step_progress round-trips through save+load byte-faithfully
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from quickscale_core.apply import APPLY_STEPS
from quickscale_core.apply.ledger import (
    LedgerError,
    LedgerManager,
    RecoveryLedger,
    ResumeCheckpoint,
    StepProgress,
)
from quickscale_core.schema.state_schema import (
    ProjectState,
    QuickScaleState,
    StateError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIRST_STEP_ID = APPLY_STEPS[0].step_id  # "module embedding"
_SECOND_STEP_ID = APPLY_STEPS[1].step_id  # "post-embed state snapshot"

#: Stable checkpoint-like tree id used throughout ledger tests.
_GIT_INDEX_CHECKPOINT = "cafebabedeadbeefcafebabedeadbeefcafebabe"


def _minimal_state() -> QuickScaleState:
    """Build the smallest valid QuickScaleState for ledger tests."""
    return QuickScaleState(
        version="1",
        project=ProjectState(
            slug="myapp",
            package="myapp",
            theme="showcase_html",
            created_at="2025-01-01T00:00:00",
            last_applied="2025-06-01T00:00:00",
        ),
    )


def _minimal_ledger_dict() -> dict[str, Any]:
    """Minimal YAML-serialisable dict representing a valid ledger with no step_progress."""
    return {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": "showcase_html",
            "created_at": "2025-01-01T00:00:00",
            "last_applied": "2025-06-01T00:00:00",
        },
        "git_index_checkpoint": _GIT_INDEX_CHECKPOINT,
    }


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Absent file → None
# ---------------------------------------------------------------------------


class TestLedgerAbsent:
    """load() must return None when the ledger file does not exist."""

    def test_load_returns_none_when_file_absent(self, tmp_path: Path) -> None:
        mgr = LedgerManager(tmp_path)
        assert not mgr.ledger_file.exists()
        assert mgr.load() is None


# ---------------------------------------------------------------------------
# Present + valid (no step_progress)
# ---------------------------------------------------------------------------


class TestLedgerPresentValidNoStepProgress:
    """A valid ledger without step_progress must parse successfully."""

    def test_load_returns_ledger(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert isinstance(result, RecoveryLedger)

    def test_step_progress_is_none_when_absent(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.step_progress is None

    def test_applied_state_fields_are_correct(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        state = result.applied_state
        assert state.project.slug == "myapp"
        assert state.project.package == "myapp"
        assert state.project.theme == "showcase_html"
        assert state.version == "1"


# ---------------------------------------------------------------------------
# Present + valid WITH step_progress
# ---------------------------------------------------------------------------


class TestLedgerPresentValidWithStepProgress:
    """A valid ledger with a recognised step_progress must parse successfully."""

    def test_load_returns_ledger_with_step_progress(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": _FIRST_STEP_ID, "status": "completed"},
            {"step_id": _SECOND_STEP_ID, "status": "failed", "detail": "disk full"},
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.step_progress is not None
        assert len(result.step_progress) == 2

    def test_step_progress_entries_have_correct_fields(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": _FIRST_STEP_ID, "status": "completed"},
            {"step_id": _SECOND_STEP_ID, "status": "failed", "detail": "disk full"},
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        sp = result.step_progress
        assert sp is not None

        first = sp[_FIRST_STEP_ID]
        assert first.step_id == _FIRST_STEP_ID
        assert first.status == "completed"
        assert first.detail is None

        second = sp[_SECOND_STEP_ID]
        assert second.step_id == _SECOND_STEP_ID
        assert second.status == "failed"
        assert second.detail == "disk full"

    def test_all_16_step_ids_are_valid(self, tmp_path: Path) -> None:
        """Every id in APPLY_STEPS is accepted in step_progress."""
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": s.step_id, "status": "completed"} for s in APPLY_STEPS
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.step_progress is not None
        assert len(result.step_progress) == 16


# ---------------------------------------------------------------------------
# Malformed → raises LedgerError
# ---------------------------------------------------------------------------


class TestLedgerMalformed:
    """Malformed or inconsistent ledger files must raise LedgerError."""

    def test_not_a_dict_raises(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger_path, "w") as fh:
            fh.write("- this\n- is\n- a\n- list\n")

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_missing_project_section_raises(self, tmp_path: Path) -> None:
        data = {"version": "1"}  # missing 'project'
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_missing_project_slug_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        del data["project"]["slug"]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_missing_project_package_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        del data["project"]["package"]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_missing_project_theme_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        del data["project"]["theme"]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_project_not_a_dict_raises(self, tmp_path: Path) -> None:
        data = {"version": "1", "project": "not-a-dict"}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger_path, "w") as fh:
            fh.write("key: [\n  unclosed\n")  # invalid YAML

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()


# ---------------------------------------------------------------------------
# Unknown step_id in step_progress → raises LedgerError
# ---------------------------------------------------------------------------


class TestLedgerUnknownStepId:
    """step_progress referencing an unknown step id must raise LedgerError."""

    def test_unknown_step_id_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": "nonexistent step that never existed", "status": "completed"},
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="unknown step_id"):
            mgr.load()

    def test_mixed_valid_and_unknown_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": _FIRST_STEP_ID, "status": "completed"},
            {"step_id": "bad-unknown-step", "status": "failed"},
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_missing_step_id_field_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"status": "completed"},  # missing step_id
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()


# ---------------------------------------------------------------------------
# Round-trip: save + load produces byte-faithful step_progress
# ---------------------------------------------------------------------------


class TestLedgerRoundTrip:
    """save() + load() must round-trip the ledger including step_progress."""

    def test_round_trip_no_step_progress(self, tmp_path: Path) -> None:
        state = _minimal_state()
        ledger = RecoveryLedger(
            applied_state=state,
            step_progress=None,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        assert mgr.ledger_file.exists()

        loaded = mgr.load()
        assert loaded is not None
        assert loaded.step_progress is None
        assert loaded.applied_state.project.slug == "myapp"

    def test_round_trip_with_step_progress(self, tmp_path: Path) -> None:
        state = _minimal_state()
        sp = {
            _FIRST_STEP_ID: StepProgress(
                step_id=_FIRST_STEP_ID, status="completed", detail=None
            ),
            _SECOND_STEP_ID: StepProgress(
                step_id=_SECOND_STEP_ID, status="failed", detail="network timeout"
            ),
        }
        ledger = RecoveryLedger(
            applied_state=state,
            step_progress=sp,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.step_progress is not None
        assert len(loaded.step_progress) == 2

        first = loaded.step_progress[_FIRST_STEP_ID]
        assert first.step_id == _FIRST_STEP_ID
        assert first.status == "completed"
        assert first.detail is None

        second = loaded.step_progress[_SECOND_STEP_ID]
        assert second.step_id == _SECOND_STEP_ID
        assert second.status == "failed"
        assert second.detail == "network timeout"

    def test_round_trip_preserves_applied_state_version(self, tmp_path: Path) -> None:
        state = _minimal_state()
        state.version = "2"
        ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.applied_state.version == "2"

    def test_round_trip_all_16_steps(self, tmp_path: Path) -> None:
        """All 16 step ids survive a save+load cycle."""
        state = _minimal_state()
        sp = {
            s.step_id: StepProgress(step_id=s.step_id, status="completed")
            for s in APPLY_STEPS
        }
        ledger = RecoveryLedger(
            applied_state=state,
            step_progress=sp,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.step_progress is not None
        assert set(loaded.step_progress.keys()) == {s.step_id for s in APPLY_STEPS}

    def test_save_uses_tmp_then_replaces(self, tmp_path: Path) -> None:
        """Atomic write: tmp file must not exist after a successful save."""
        state = _minimal_state()
        ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)

        assert mgr.ledger_file.exists()
        assert not mgr._tmp_file.exists()

    def test_save_creates_quickscale_dir(self, tmp_path: Path) -> None:
        """save() must create .quickscale/ if it does not exist."""
        state = _minimal_state()
        ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        assert not (tmp_path / ".quickscale").exists()
        mgr.save(ledger)
        assert mgr.ledger_file.exists()

    def test_yaml_convention_default_flow_style_false(self, tmp_path: Path) -> None:
        """Saved YAML must use block style (not inline flow style)."""
        state = _minimal_state()
        ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        content = mgr.ledger_file.read_text()

        # Block-style YAML uses newlines between keys; flow style uses { }
        assert "{" not in content
        assert "}" not in content


# ---------------------------------------------------------------------------
# Presence semantics: step_progress must not affect recovery gating
# ---------------------------------------------------------------------------


class TestPresenceSemantics:
    """step_progress is diagnostic-only; resume gating is on ledger presence."""

    def test_ledger_is_not_none_when_file_present_with_step_progress(
        self, tmp_path: Path
    ) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = [
            {"step_id": _FIRST_STEP_ID, "status": "completed"},
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        recovery = mgr.load()

        # Presence gate: any non-None return means file was present
        assert recovery is not None

    def test_ledger_is_none_when_file_absent_regardless_of_logic(
        self, tmp_path: Path
    ) -> None:
        mgr = LedgerManager(tmp_path)
        # No file written; presence gate returns None unconditionally
        assert mgr.load() is None


# ---------------------------------------------------------------------------
# LedgerError is a subclass of StateError
# ---------------------------------------------------------------------------


class TestLedgerErrorHierarchy:
    """LedgerError must be a subclass of StateError for transparent catch."""

    def test_ledger_error_is_state_error(self) -> None:
        err = LedgerError("test")
        assert isinstance(err, StateError)

    def test_ledger_error_caught_as_state_error(self, tmp_path: Path) -> None:
        data: list[Any] = ["not", "a", "dict"]
        ledger_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger_path, "w") as fh:
            yaml.dump(data, fh)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(StateError):
            mgr.load()


# ---------------------------------------------------------------------------
# Additional coverage: StepProgress.from_dict edge cases
# ---------------------------------------------------------------------------


class TestStepProgressFromDict:
    """Edge cases in StepProgress.from_dict to hit all error branches."""

    def test_non_dict_entry_raises(self) -> None:
        with pytest.raises(LedgerError, match="mapping"):
            StepProgress.from_dict("not a dict")  # type: ignore[arg-type]

    def test_empty_step_id_raises(self) -> None:
        with pytest.raises(LedgerError, match="non-empty string"):
            StepProgress.from_dict({"step_id": "", "status": "completed"})

    def test_non_string_step_id_raises(self) -> None:
        with pytest.raises(LedgerError, match="non-empty string"):
            StepProgress.from_dict({"step_id": 42, "status": "completed"})

    def test_empty_status_raises(self) -> None:
        with pytest.raises(LedgerError, match="non-empty string"):
            StepProgress.from_dict({"step_id": _FIRST_STEP_ID, "status": ""})

    def test_non_string_status_raises(self) -> None:
        with pytest.raises(LedgerError, match="non-empty string"):
            StepProgress.from_dict({"step_id": _FIRST_STEP_ID, "status": 99})

    def test_non_string_detail_raises(self) -> None:
        with pytest.raises(LedgerError, match="string or absent"):
            StepProgress.from_dict(
                {"step_id": _FIRST_STEP_ID, "status": "ok", "detail": 123}
            )

    def test_missing_status_field_raises(self) -> None:
        with pytest.raises(LedgerError, match="status"):
            StepProgress.from_dict({"step_id": _FIRST_STEP_ID})  # no status key


# ---------------------------------------------------------------------------
# Additional coverage: RecoveryLedger.to_dict with non-empty modules/files
# ---------------------------------------------------------------------------


class TestRecoveryLedgerToDictWithModules:
    """RecoveryLedger.to_dict must include modules and managed_files when present."""

    def test_round_trip_with_module(self, tmp_path: Path) -> None:
        """A ledger with a non-empty module survives save+load."""
        from quickscale_core.schema.state_schema import ModuleState

        state = _minimal_state()
        state.modules["auth"] = ModuleState(
            name="auth",
            version="1.0.0",
            commit_sha="abc123",
            embedded_at="2025-01-01T00:00:00",
        )
        ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert "auth" in loaded.applied_state.modules
        assert loaded.applied_state.modules["auth"].version is not None

    def test_round_trip_with_managed_files(self, tmp_path: Path) -> None:
        """A ledger with managed_files survives save+load."""
        from quickscale_core.schema.state_schema import ManagedFileRecord

        state = _minimal_state()
        state.managed_files["myapp/settings/modules.py"] = ManagedFileRecord(
            path="myapp/settings/modules.py",
            hash="deadbeef",
            applied_at="2025-01-01T00:00:00",
        )
        ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        mgr = LedgerManager(tmp_path)

        mgr.save(ledger)
        loaded = mgr.load()

        assert loaded is not None
        assert "myapp/settings/modules.py" in loaded.applied_state.managed_files

    def test_managed_files_list_with_non_dict_entry_raises(
        self, tmp_path: Path
    ) -> None:
        """Non-dict entries in a list-form managed_files section must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["managed_files"] = [
            "not-a-dict",
            {
                "path": "myapp/settings/base.py",
                "hash": "aabbcc",
                "applied_at": "2025-01-01",
            },
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="must be a mapping"):
            mgr.load()

    def test_managed_files_list_with_missing_required_field_raises(
        self, tmp_path: Path
    ) -> None:
        """Entries missing required fields in list-form managed_files must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["managed_files"] = [
            {"path": "ok/file.py", "hash": "abc", "applied_at": "2025-01-01"},
            {"path": "bad/file.py"},  # missing hash — must raise
        ]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="missing required fields"):
            mgr.load()

    def test_managed_files_dict_form_parses(self, tmp_path: Path) -> None:
        """Dict-keyed form of managed_files section also parses correctly."""
        data = _minimal_ledger_dict()
        data["managed_files"] = {
            "myapp/settings/base.py": {
                "hash": "deadbeef",
                "applied_at": "2025-01-01",
            },
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert "myapp/settings/base.py" in result.applied_state.managed_files

    def test_managed_files_dict_form_non_dict_value_raises(
        self, tmp_path: Path
    ) -> None:
        """Non-dict value in dict-keyed managed_files must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["managed_files"] = {
            "ok/file.py": {"hash": "abc", "applied_at": "2025-01-01"},
            "bad/file.py": "not-a-dict-value",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="must be a mapping"):
            mgr.load()

    def test_managed_files_invalid_top_level_type_raises(self, tmp_path: Path) -> None:
        """managed_files must fail hard when present with a non-list/non-mapping type."""
        data = _minimal_ledger_dict()
        data["managed_files"] = "not-a-list-or-mapping"
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="list or mapping"):
            mgr.load()

    def test_managed_files_explicit_null_raises(self, tmp_path: Path) -> None:
        """managed_files: null must raise LedgerError — explicit null is not the
        same as key absence."""
        data = _minimal_ledger_dict()
        data["managed_files"] = None  # YAML null → Python None
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="got None"):
            mgr.load()

    def test_managed_files_dict_form_missing_hash_raises(self, tmp_path: Path) -> None:
        """Dict-keyed entry missing required 'hash' must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["managed_files"] = {
            "ok/file.py": {"hash": "abc", "applied_at": "2025-01-01"},
            "no-hash/file.py": {"applied_at": "2025-01-01"},  # missing hash
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="missing required fields"):
            mgr.load()


# ---------------------------------------------------------------------------
# Additional coverage: _parse_step_progress dict-keyed form
# ---------------------------------------------------------------------------


class TestStepProgressDictKeyedForm:
    """step_progress as a dict (step_id -> {status, detail}) must also parse."""

    def test_dict_keyed_step_progress_parses(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        # Dict form: keys are step_ids, values are {status, detail}
        data["step_progress"] = {
            _FIRST_STEP_ID: {"status": "completed"},
            _SECOND_STEP_ID: {"status": "failed", "detail": "oops"},
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.step_progress is not None
        assert len(result.step_progress) == 2
        assert result.step_progress[_FIRST_STEP_ID].status == "completed"
        assert result.step_progress[_SECOND_STEP_ID].detail == "oops"

    def test_dict_keyed_with_unknown_step_id_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = {
            "bad-unknown-step": {"status": "completed"},
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_dict_keyed_with_non_dict_value_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["step_progress"] = {
            _FIRST_STEP_ID: "not-a-dict",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_invalid_step_progress_type_raises(self, tmp_path: Path) -> None:
        """step_progress that is neither list nor dict must raise."""
        data = _minimal_ledger_dict()
        data["step_progress"] = "just-a-string"
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="list or mapping"):
            mgr.load()


# ---------------------------------------------------------------------------
# Additional coverage: modules section malformed in applied state
# ---------------------------------------------------------------------------


class TestAppliedStateMalformedModules:
    """modules section errors in the applied-state portion must raise LedgerError."""

    def test_modules_not_a_dict_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["modules"] = ["not", "a", "dict"]
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="modules.*mapping"):
            mgr.load()

    def test_module_entry_not_a_dict_raises(self, tmp_path: Path) -> None:
        data = _minimal_ledger_dict()
        data["modules"] = {"auth": "not-a-dict"}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="mapping"):
            mgr.load()


# ---------------------------------------------------------------------------
# Git-index checkpoint field
# ---------------------------------------------------------------------------


class TestRecoveryLedgerGitIndexCheckpoint:
    """git_index_checkpoint field in RecoveryLedger must survive save+load."""

    def test_round_trip_with_git_index_checkpoint(self, tmp_path: Path) -> None:
        """A ledger with a valid git_index_checkpoint round-trips."""
        state = _minimal_state()
        ledger = RecoveryLedger(
            applied_state=state,
            step_progress=None,
            git_index_checkpoint="abc123def456abc123def456abc123def456abc1",
        )
        mgr = LedgerManager(tmp_path)
        mgr.save(ledger)

        loaded = mgr.load()
        assert loaded is not None
        assert loaded.git_index_checkpoint == "abc123def456abc123def456abc123def456abc1"

    def test_fail_hard_on_missing_git_index_checkpoint(self, tmp_path: Path) -> None:
        """A present ledger without git_index_checkpoint must raise LedgerError."""
        data = {
            "version": "1",
            "project": {
                "slug": "myapp",
                "package": "myapp",
                "theme": "showcase_html",
                "created_at": "2025-01-01T00:00:00",
                "last_applied": "2025-06-01T00:00:00",
            },
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="is required"):
            mgr.load()

    def test_parse_with_inline_git_index_checkpoint(self, tmp_path: Path) -> None:
        """A YAML file with git_index_checkpoint set must parse correctly."""
        data = _minimal_ledger_dict()
        data["git_index_checkpoint"] = "deadbeefcafebabedeadbeefcafebabedeadbeef"
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.git_index_checkpoint == "deadbeefcafebabedeadbeefcafebabedeadbeef"

    def test_empty_string_raises(self, tmp_path: Path) -> None:
        """An empty git_index_checkpoint must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["git_index_checkpoint"] = ""
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_non_string_value_raises(self, tmp_path: Path) -> None:
        """A non-string git_index_checkpoint must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["git_index_checkpoint"] = 12345
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError):
            mgr.load()

    def test_dict_includes_git_index_checkpoint_when_set(self) -> None:
        """to_dict must include git_index_checkpoint when it is set."""
        state = _minimal_state()
        ledger = RecoveryLedger(
            applied_state=state,
            git_index_checkpoint="aabbccddeeff00112233445566778899aabbccdd",
        )
        d = ledger.to_dict()
        assert d["git_index_checkpoint"] == "aabbccddeeff00112233445566778899aabbccdd"

    def test_dict_includes_git_index_checkpoint_always(self) -> None:
        """to_dict must always include git_index_checkpoint."""
        state = _minimal_state()
        ledger = RecoveryLedger(
            applied_state=state,
            step_progress=None,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        d = ledger.to_dict()
        assert d["git_index_checkpoint"] == _GIT_INDEX_CHECKPOINT


# ---------------------------------------------------------------------------
# Package-level re-exports
# ---------------------------------------------------------------------------


class TestPackageLevelReExports:
    """The apply package __init__.py must re-export the new ledger symbols."""

    def test_ledger_error_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import LedgerError as LE

        assert LE is LedgerError

    def test_ledger_manager_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import LedgerManager as LM

        assert LM is LedgerManager

    def test_recovery_ledger_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import RecoveryLedger as RL

        assert RL is RecoveryLedger

    def test_step_progress_is_importable_from_apply(self) -> None:
        from quickscale_core.apply import StepProgress as SP

        assert SP is StepProgress

    def test_resume_checkpoint_is_importable_from_apply(self) -> None:
        """ResumeCheckpoint must be re-exported from the apply package."""
        from quickscale_core.apply import ResumeCheckpoint as RC

        assert RC is ResumeCheckpoint


# ---------------------------------------------------------------------------
# AF5 Phase 1 — ResumeCheckpoint and AF6-era compatibility
# ---------------------------------------------------------------------------


class TestAF5ResumeCheckpoint:
    """AF5 resume-checkpoint dataclass — shape, parsing, and round-trip."""

    # --- AF6-era compatibility: absent resume_checkpoint ---

    def test_af6_era_ledger_without_resume_checkpoint_loads(
        self, tmp_path: Path
    ) -> None:
        """An AF6-era ledger (no resume_checkpoint) must parse successfully."""
        data = _minimal_ledger_dict()
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.resume_checkpoint is None

    # --- Valid resume_checkpoint parsing ---

    def test_load_with_valid_resume_checkpoint(self, tmp_path: Path) -> None:
        """A ledger with a valid resume_checkpoint must parse successfully."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": _FIRST_STEP_ID,
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.resume_checkpoint is not None
        assert result.resume_checkpoint.resume_step_id == _FIRST_STEP_ID
        assert result.resume_checkpoint.suspend_after_step_id is None
        assert result.resume_checkpoint.checkpoint_tree_id is None

    def test_load_with_full_resume_checkpoint(self, tmp_path: Path) -> None:
        """A ledger with all resume_checkpoint fields must parse."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": _FIRST_STEP_ID,
            "suspend_after_step_id": _SECOND_STEP_ID,
            "checkpoint_tree_id": "deadbeefcafebabedeadbeefcafebabedeadbeef",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        result = mgr.load()

        assert result is not None
        assert result.resume_checkpoint is not None
        assert result.resume_checkpoint.resume_step_id == _FIRST_STEP_ID
        assert result.resume_checkpoint.suspend_after_step_id == _SECOND_STEP_ID
        assert (
            result.resume_checkpoint.checkpoint_tree_id
            == "deadbeefcafebabedeadbeefcafebabedeadbeef"
        )

    # --- Round-trip ---

    def test_round_trip_resume_checkpoint(self, tmp_path: Path) -> None:
        """ResumeCheckpoint must survive save+load."""
        state = _minimal_state()
        rc = ResumeCheckpoint(
            resume_step_id=_FIRST_STEP_ID,
            suspend_after_step_id=_SECOND_STEP_ID,
            checkpoint_tree_id="aabbccddeeff00112233445566778899aabbccdd",
        )
        ledger = RecoveryLedger(
            applied_state=state,
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
        """Minimal ResumeCheckpoint (only resume_step_id) must round-trip."""
        state = _minimal_state()
        rc = ResumeCheckpoint(resume_step_id=_FIRST_STEP_ID)
        ledger = RecoveryLedger(
            applied_state=state,
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

    def test_round_trip_preserves_existing_resume_checkpoint_through_save(
        self, tmp_path: Path
    ) -> None:
        """A RecoveryLedger with resume_checkpoint must re-save the field
        when to_dict() is called, so that downstream consumers that create
        a fresh RecoveryLedger from existing state (e.g. remove_command)
        preserve the checkpoint."""
        state = _minimal_state()
        rc = ResumeCheckpoint(resume_step_id=_FIRST_STEP_ID)
        ledger = RecoveryLedger(
            applied_state=state,
            resume_checkpoint=rc,
            git_index_checkpoint=_GIT_INDEX_CHECKPOINT,
        )
        d = ledger.to_dict()
        assert "resume_checkpoint" in d
        assert d["resume_checkpoint"]["resume_step_id"] == _FIRST_STEP_ID

    # --- Malformed resume_checkpoint ---

    def test_resume_checkpoint_not_a_dict_raises(self, tmp_path: Path) -> None:
        """resume_checkpoint that is not a dict must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = "just-a-string"
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="must be a mapping"):
            mgr.load()

    def test_resume_checkpoint_missing_resume_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        """resume_checkpoint without resume_step_id must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {"suspend_after_step_id": _FIRST_STEP_ID}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="missing required field"):
            mgr.load()

    def test_resume_checkpoint_empty_resume_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        """resume_checkpoint with empty resume_step_id must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {"resume_step_id": ""}
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="non-empty string"):
            mgr.load()

    def test_resume_checkpoint_unknown_resume_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        """resume_checkpoint with unknown step id must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": "nonexistent-step-that-never-existed"
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="unknown step_id"):
            mgr.load()

    def test_resume_checkpoint_unknown_suspend_after_step_id_raises(
        self, tmp_path: Path
    ) -> None:
        """suspend_after_step_id referencing unknown step must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": _FIRST_STEP_ID,
            "suspend_after_step_id": "bad-unknown-step",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="unknown"):
            mgr.load()

    def test_resume_checkpoint_empty_checkpoint_tree_id_raises(
        self, tmp_path: Path
    ) -> None:
        """Empty checkpoint_tree_id must raise LedgerError."""
        data = _minimal_ledger_dict()
        data["resume_checkpoint"] = {
            "resume_step_id": _FIRST_STEP_ID,
            "checkpoint_tree_id": "",
        }
        _write_yaml(tmp_path / ".quickscale" / "apply-recovery.yml", data)

        mgr = LedgerManager(tmp_path)
        with pytest.raises(LedgerError, match="non-empty"):
            mgr.load()

    # --- ResumeCheckpoint.from_dict edge cases ---

    def test_resume_checkpoint_from_dict_non_dict_value_raises(self) -> None:
        """ResumeCheckpoint.from_dict must reject non-dict input."""
        with pytest.raises(LedgerError, match="mapping"):
            ResumeCheckpoint.from_dict("not-a-dict")  # type: ignore[arg-type]

    def test_resume_checkpoint_from_dict_missing_resume_step_id_raises(
        self,
    ) -> None:
        """ResumeCheckpoint.from_dict must reject missing resume_step_id."""
        with pytest.raises(LedgerError, match="missing required field"):
            ResumeCheckpoint.from_dict({"suspend_after_step_id": "test"})

    def test_resume_checkpoint_from_dict_non_string_resume_step_id_raises(
        self,
    ) -> None:
        """ResumeCheckpoint.from_dict must reject non-string resume_step_id."""
        with pytest.raises(LedgerError, match="non-empty string"):
            ResumeCheckpoint.from_dict({"resume_step_id": 42})

    def test_resume_checkpoint_from_dict_empty_suspend_after_raises(
        self,
    ) -> None:
        """ResumeCheckpoint.from_dict must reject empty suspend_after_step_id."""
        with pytest.raises(LedgerError, match="non-empty"):
            ResumeCheckpoint.from_dict(
                {"resume_step_id": _FIRST_STEP_ID, "suspend_after_step_id": ""}
            )
