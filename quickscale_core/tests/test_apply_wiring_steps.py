"""Tests for quickscale_core.apply.steps.wiring — step_capture_hashes.

SA18.9 promotes ``step_capture_hashes`` from best-effort (always returns
``success=True``) to fail-hard: an ``OSError`` during path resolution or
hash computation now returns ``success=False`` with
``failed_step_label="capture managed file hashes"``.

Regression coverage:
* OSError during ``resolve_managed_wiring_paths_fn`` → fail hard.
* OSError during ``compute_file_hashes_fn`` → fail hard.
* No managed paths → ``success=True`` (no-op).
* Success path → hashes computed and recorded correctly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from quickscale_core.apply.steps.types import StepContext
from quickscale_core.apply.steps.wiring import step_capture_hashes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> StepContext:
    """Build a minimal StepContext with overrides for test ergonomics."""
    return StepContext(
        output_path=Path("/fake/project"),
        **overrides,  # type: ignore[arg-type]
    )


def _make_recorded(
    hashes: dict[str, str] | None = None,
) -> tuple[list[tuple[str, str]], Callable[..., None]]:
    """Return a (store, record_hash_fn) pair.

    ``store`` is a list of ``(path, digest)`` tuples that ``record_hash_fn``
    appends to on each call.
    """
    store: list[tuple[str, str]] = []

    def record(path_str: str, digest: str) -> None:
        store.append((path_str, digest))

    return store, record


# ---------------------------------------------------------------------------
# OSError paths  (SA18.9 — fail hard)
# ---------------------------------------------------------------------------


class TestStepCaptureHashesOSError:
    """When an OSError occurs, the step must fail with success=False."""

    def _osec_raise(self) -> list[str]:
        raise OSError(13, "Permission denied", "/fake/managed/file.py")

    def test_oserror_on_resolve_paths_returns_success_false(self) -> None:
        ctx = _make_context()
        _, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {},
            resolve_managed_wiring_paths_fn=self._osec_raise,
            record_hash_fn=record,
        )

        assert outcome.success is False
        assert outcome.failed_step_label == "capture managed file hashes"
        assert "Permission denied" in outcome.message

    def test_oserror_on_compute_hashes_returns_success_false(self) -> None:
        ctx = _make_context()

        def _raise_on_compute(_path: Path, _paths: list[str]) -> dict[str, str]:
            raise OSError(28, "No space left on device", "/fake/managed/file.py")

        _, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=_raise_on_compute,
            resolve_managed_wiring_paths_fn=lambda: ["file.py"],
            record_hash_fn=record,
        )

        assert outcome.success is False
        assert outcome.failed_step_label == "capture managed file hashes"
        assert "No space left on device" in outcome.message

    def test_oserror_does_not_record_hashes(self) -> None:
        ctx = _make_context()
        store, record = _make_recorded()

        step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {},
            resolve_managed_wiring_paths_fn=self._osec_raise,
            record_hash_fn=record,
        )

        assert store == []

    def test_oserror_reporter_is_called(self) -> None:
        messages: list[str] = []

        def _reporter(msg: str, *, ok: bool = True) -> None:
            messages.append(msg)

        ctx = _make_context(reporter=_reporter)

        step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {},
            resolve_managed_wiring_paths_fn=self._osec_raise,
            record_hash_fn=lambda _p, _d: None,
        )

        assert any("Failed to capture" in m for m in messages)


# ---------------------------------------------------------------------------
# No-op path  (no managed paths to track)
# ---------------------------------------------------------------------------


class TestStepCaptureHashesNoPaths:
    """When resolve_managed_wiring_paths_fn returns an empty list."""

    def test_no_managed_paths_returns_success_true(self) -> None:
        ctx = _make_context()
        _, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {},
            resolve_managed_wiring_paths_fn=lambda: [],
            record_hash_fn=record,
        )

        assert outcome.success is True
        assert "No managed wiring paths" in outcome.message

    def test_no_managed_paths_does_not_record(self) -> None:
        ctx = _make_context()
        store, record = _make_recorded()

        step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {},
            resolve_managed_wiring_paths_fn=lambda: [],
            record_hash_fn=record,
        )

        assert store == []


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestStepCaptureHashesSuccess:
    """Happy path: hashes are computed and recorded correctly."""

    def test_records_single_hash(self) -> None:
        ctx = _make_context()
        store, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {"file.py": "abc123"},
            resolve_managed_wiring_paths_fn=lambda: ["file.py"],
            record_hash_fn=record,
        )

        assert outcome.success is True
        assert outcome.failed_step_label is None
        assert store == [("file.py", "abc123")]

    def test_records_multiple_hashes(self) -> None:
        ctx = _make_context()
        store, record = _make_recorded()

        hashes = {"a.py": "111", "b.py": "222", "c.py": "333"}
        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: hashes,
            resolve_managed_wiring_paths_fn=lambda: list(hashes),
            record_hash_fn=record,
        )

        assert outcome.success is True
        assert len(store) == 3
        assert set(store) == {("a.py", "111"), ("b.py", "222"), ("c.py", "333")}

    def test_returns_correct_count_in_message(self) -> None:
        ctx = _make_context()
        _, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {"x.py": "d4e5f6"},
            resolve_managed_wiring_paths_fn=lambda: ["x.py"],
            record_hash_fn=record,
        )

        assert "1 managed file" in outcome.message

    def test_reporter_called_on_success(self) -> None:
        messages: list[str] = []

        def _reporter(msg: str, *, ok: bool = True) -> None:
            messages.append(msg)

        ctx = _make_context(reporter=_reporter)

        step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {"f.py": "xyz"},
            resolve_managed_wiring_paths_fn=lambda: ["f.py"],
            record_hash_fn=lambda _p, _d: None,
        )

        assert any("Tracked managed file hashes" in m for m in messages)


# ---------------------------------------------------------------------------
# Reporter behavior when not provided
# ---------------------------------------------------------------------------


class TestStepCaptureHashesReporterNone:
    """When ctx.reporter is None, no reporter interaction occurs."""

    def test_no_reporter_on_empty_paths(self) -> None:
        ctx = _make_context(reporter=None)
        _, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {},
            resolve_managed_wiring_paths_fn=lambda: [],
            record_hash_fn=record,
        )

        assert outcome.success is True

    def test_no_reporter_on_oserror(self) -> None:
        ctx = _make_context(reporter=None)
        _, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {},
            resolve_managed_wiring_paths_fn=lambda: (_ for _ in ()).throw(
                OSError(13, "fail")
            ),
            record_hash_fn=record,
        )

        assert outcome.success is False
        assert outcome.failed_step_label == "capture managed file hashes"

    def test_no_reporter_on_success(self) -> None:
        ctx = _make_context(reporter=None)
        _, record = _make_recorded()

        outcome = step_capture_hashes(
            ctx,
            compute_file_hashes_fn=lambda _p, _ps: {"f.py": "hash"},
            resolve_managed_wiring_paths_fn=lambda: ["f.py"],
            record_hash_fn=record,
        )

        assert outcome.success is True
