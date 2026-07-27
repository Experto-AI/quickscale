"""
Hermetic tests for SA117 publication verification (``verify_sa117_publication.py``).

All tests use temporary directories and fake evidence — no production data,
no network, no public mutation.  Covers:

* Evidence creation and validation (required fields, types, ISO datetime).
* Scope digest computation.
* ``capture``, ``verify``, ``authorize``, and ``rollback`` operations.
* Error handling: missing files, malformed JSON, empty values.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
from typing import Any

import pytest

from scripts.verify_sa117_publication import (
    _compute_scope_digest,
    _make_evidence,
    _read_evidence,
    _validate_evidence,
    _write_evidence,
    op_authorize,
    op_capture,
    op_rollback,
    op_verify,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def evidence_dir() -> pathlib.Path:
    """Return a temporary directory for evidence files."""
    tmp = tempfile.mkdtemp()
    yield pathlib.Path(tmp)
    # Cleanup
    for root, dirs, files in os.walk(tmp, topdown=False):
        for name in files:
            os.unlink(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(tmp)


@pytest.fixture
def valid_scope_file() -> pathlib.Path:
    """Return a temporary scope JSON file with 2 paths."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(
        {
            "version": "1.0.0",
            "paths": [
                {"path": "scripts/foo.py", "phase": "1", "notes": ""},
                {"path": "scripts/bar.py", "phase": "1", "notes": ""},
            ],
        },
        tmp,
    )
    tmp.close()
    p = pathlib.Path(tmp.name)
    yield p
    p.unlink(missing_ok=True)


@pytest.fixture
def valid_evidence() -> dict[str, Any]:
    """Return a minimal valid evidence dict."""
    return _make_evidence(
        version="0.87.0",
        phase="1-implement",
        paths_count=2,
        scope_digest="abc123def456",
    )


# ---------------------------------------------------------------------------
# _make_evidence
# ---------------------------------------------------------------------------


class TestMakeEvidence:
    """``_make_evidence`` produces a well-formed evidence dict."""

    def test_has_required_fields(self) -> None:
        evidence = _make_evidence(
            version="0.87.0",
            phase="1-implement",
            paths_count=79,
            scope_digest="abc123",
        )
        assert evidence["version"] == "0.87.0"
        assert evidence["phase"] == "1-implement"
        assert evidence["paths_count"] == 79
        assert evidence["scope_digest"] == "abc123"
        assert "captured_at" in evidence
        assert evidence["schema_version"] == "1"

    def test_captured_at_is_iso_datetime(self) -> None:
        evidence = _make_evidence(
            version="0.87.0",
            phase="1",
            paths_count=1,
            scope_digest="d",
        )
        # Should not raise
        import datetime

        datetime.datetime.fromisoformat(evidence["captured_at"])


# ---------------------------------------------------------------------------
# _validate_evidence
# ---------------------------------------------------------------------------


class TestValidateEvidence:
    """``_validate_evidence`` checks required fields and types."""

    def test_valid_evidence_passes(self, valid_evidence: dict[str, Any]) -> None:
        _validate_evidence(valid_evidence)  # no raise

    def test_missing_field_raises(self, valid_evidence: dict[str, Any]) -> None:
        del valid_evidence["version"]
        with pytest.raises(ValueError, match="version"):
            _validate_evidence(valid_evidence)

    def test_wrong_type_raises(self, valid_evidence: dict[str, Any]) -> None:
        valid_evidence["paths_count"] = "not_an_int"
        with pytest.raises(ValueError, match="paths_count"):
            _validate_evidence(valid_evidence)

    def test_invalid_captured_at_raises(self, valid_evidence: dict[str, Any]) -> None:
        valid_evidence["captured_at"] = "not-a-date"
        with pytest.raises(ValueError, match="captured_at"):
            _validate_evidence(valid_evidence)

    def test_empty_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required field"):
            _validate_evidence({})


# ---------------------------------------------------------------------------
# _compute_scope_digest
# ---------------------------------------------------------------------------


class TestComputeScopeDigest:
    """``_compute_scope_digest`` produces a SHA-256 hex digest."""

    def test_returns_hex_string(self, valid_scope_file: pathlib.Path) -> None:
        digest = _compute_scope_digest(valid_scope_file)
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in digest)

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            _compute_scope_digest(pathlib.Path("/nonexistent.json"))

    def test_consistent_digest(self, valid_scope_file: pathlib.Path) -> None:
        d1 = _compute_scope_digest(valid_scope_file)
        d2 = _compute_scope_digest(valid_scope_file)
        assert d1 == d2


# ---------------------------------------------------------------------------
# Evidence I/O
# ---------------------------------------------------------------------------


class TestEvidenceIO:
    """``_write_evidence`` and ``_read_evidence`` round-trip."""

    def test_round_trip(self, valid_evidence: dict[str, Any], evidence_dir: pathlib.Path) -> None:
        path = evidence_dir / "test_evidence.json"
        written = _write_evidence(valid_evidence, path)
        assert written == path
        assert path.is_file()

        loaded = _read_evidence(path)
        assert loaded["version"] == valid_evidence["version"]
        assert loaded["phase"] == valid_evidence["phase"]

    def test_read_nonexistent_raises(self, evidence_dir: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            _read_evidence(evidence_dir / "nonexistent.json")

    def test_read_malformed_json_raises(self, evidence_dir: pathlib.Path) -> None:
        path = evidence_dir / "bad.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            _read_evidence(path)

    def test_read_non_dict_json_raises(self, evidence_dir: pathlib.Path) -> None:
        path = evidence_dir / "list.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="not a JSON object"):
            _read_evidence(path)


# ---------------------------------------------------------------------------
# op_capture
# ---------------------------------------------------------------------------


class TestOpCapture:
    """``op_capture`` writes evidence files."""

    def test_capture_creates_file(
        self, valid_scope_file: pathlib.Path, evidence_dir: pathlib.Path
    ) -> None:
        rc = op_capture(
            version="0.87.0",
            phase="1-implement",
            scope_path=valid_scope_file,
            evidence_dir=evidence_dir,
        )
        assert rc == 0

        # Should have created one evidence file
        files = list(evidence_dir.glob("sa117_evidence_*.json"))
        assert len(files) == 1

        # Validate the content
        evidence = json.loads(files[0].read_bytes())
        assert evidence["version"] == "0.87.0"
        assert evidence["phase"] == "1-implement"
        assert evidence["paths_count"] == 2

    def test_capture_missing_scope_returns_error(self, evidence_dir: pathlib.Path) -> None:
        rc = op_capture(
            version="0.87.0",
            phase="1",
            scope_path=pathlib.Path("/nonexistent/scope.json"),
            evidence_dir=evidence_dir,
        )
        assert rc == 2

    def test_capture_counts_paths(
        self, valid_scope_file: pathlib.Path, evidence_dir: pathlib.Path
    ) -> None:
        rc = op_capture(
            version="0.87.0",
            phase="1",
            scope_path=valid_scope_file,
            evidence_dir=evidence_dir,
        )
        assert rc == 0
        files = list(evidence_dir.glob("sa117_evidence_*.json"))
        evidence = json.loads(files[0].read_bytes())
        assert evidence["paths_count"] == 2  # our fixture has 2


# ---------------------------------------------------------------------------
# op_verify
# ---------------------------------------------------------------------------


class TestOpVerify:
    """``op_verify`` validates evidence consistency."""

    def test_verify_valid_evidence_passes(
        self,
        valid_scope_file: pathlib.Path,
        evidence_dir: pathlib.Path,
    ) -> None:
        # First capture evidence
        rc = op_capture(
            version="0.87.0",
            phase="1-implement",
            scope_path=valid_scope_file,
            evidence_dir=evidence_dir,
        )
        assert rc == 0

        evidence_file = next(evidence_dir.glob("sa117_evidence_*.json"))
        rc = op_verify(
            evidence_path=evidence_file,
            scope_path=valid_scope_file,
        )
        assert rc == 0

    def test_verify_with_wrong_scope_fails(
        self,
        valid_scope_file: pathlib.Path,
        evidence_dir: pathlib.Path,
    ) -> None:
        # Capture with one scope
        rc = op_capture(
            version="0.87.0",
            phase="1",
            scope_path=valid_scope_file,
            evidence_dir=evidence_dir,
        )
        assert rc == 0

        # Create a second scope with different content
        tmp2 = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(
            {
                "version": "2.0",
                "paths": [{"path": "other.py", "phase": "1", "notes": ""}],
            },
            tmp2,
        )
        tmp2.close()
        other_scope = pathlib.Path(tmp2.name)

        try:
            evidence_file = next(evidence_dir.glob("sa117_evidence_*.json"))
            rc = op_verify(
                evidence_path=evidence_file,
                scope_path=other_scope,
            )
            assert rc == 1  # digest mismatch
        finally:
            other_scope.unlink(missing_ok=True)

    def test_verify_missing_evidence_returns_error(self, valid_scope_file: pathlib.Path) -> None:
        rc = op_verify(
            evidence_path=pathlib.Path("/nonexistent/evidence.json"),
            scope_path=valid_scope_file,
        )
        assert rc == 2

    def test_verify_malformed_evidence_returns_error(
        self, evidence_dir: pathlib.Path, valid_scope_file: pathlib.Path
    ) -> None:
        bad_path = evidence_dir / "bad_evidence.json"
        bad_path.write_text("not json", encoding="utf-8")
        rc = op_verify(
            evidence_path=bad_path,
            scope_path=valid_scope_file,
        )
        assert rc == 2


# ---------------------------------------------------------------------------
# op_authorize
# ---------------------------------------------------------------------------


class TestOpAuthorize:
    """``op_authorize`` produces authorisation tokens."""

    def test_authorize_creates_token(self, evidence_dir: pathlib.Path) -> None:
        rc = op_authorize(
            version="0.87.0",
            evidence_digest="abc123def456",
            auth_dir=evidence_dir,
        )
        assert rc == 0

        files = list(evidence_dir.glob("sa117_auth_*.json"))
        assert len(files) == 1
        record = json.loads(files[0].read_bytes())
        assert record["version"] == "0.87.0"
        assert record["evidence_digest"] == "abc123def456"
        assert record["token"].startswith("sa117_auth_")

    def test_authorize_empty_version_returns_error(self, evidence_dir: pathlib.Path) -> None:
        rc = op_authorize(
            version="",
            evidence_digest="abc123",
            auth_dir=evidence_dir,
        )
        assert rc == 2

    def test_authorize_empty_digest_returns_error(self, evidence_dir: pathlib.Path) -> None:
        rc = op_authorize(
            version="0.87.0",
            evidence_digest="",
            auth_dir=evidence_dir,
        )
        assert rc == 2

    def test_authorize_whitespace_only_version_returns_error(
        self, evidence_dir: pathlib.Path
    ) -> None:
        rc = op_authorize(
            version="   ",
            evidence_digest="abc",
            auth_dir=evidence_dir,
        )
        assert rc == 2


# ---------------------------------------------------------------------------
# op_rollback
# ---------------------------------------------------------------------------


class TestOpRollback:
    """``op_rollback`` revokes authorisation tokens."""

    def test_rollback_with_matching_digest_succeeds(self, evidence_dir: pathlib.Path) -> None:
        # Authorize first
        rc = op_authorize(
            version="0.87.0",
            evidence_digest="abc123",
            auth_dir=evidence_dir,
        )
        assert rc == 0

        # Read the token
        auth_file = next(evidence_dir.glob("sa117_auth_*.json"))
        record = json.loads(auth_file.read_bytes())
        token = record["token"]

        # Rollback with matching digest
        rc = op_rollback(
            auth_token=token,
            evidence_digest="abc123",
            auth_dir=evidence_dir,
        )
        assert rc == 0

        # Auth file should be removed
        assert not auth_file.is_file()

    def test_rollback_with_wrong_digest_rejected(self, evidence_dir: pathlib.Path) -> None:
        rc = op_authorize(
            version="0.87.0",
            evidence_digest="abc123",
            auth_dir=evidence_dir,
        )
        assert rc == 0

        auth_file = next(evidence_dir.glob("sa117_auth_*.json"))
        record = json.loads(auth_file.read_bytes())
        token = record["token"]

        # Rollback with wrong digest — should be rejected
        rc = op_rollback(
            auth_token=token,
            evidence_digest="wrong_digest",
            auth_dir=evidence_dir,
        )
        assert rc == 1  # semantic rejection

        # Auth file should still exist
        assert auth_file.is_file()

    def test_rollback_nonexistent_token_returns_error(self, evidence_dir: pathlib.Path) -> None:
        rc = op_rollback(
            auth_token="nonexistent_token",
            evidence_digest="abc123",
            auth_dir=evidence_dir,
        )
        assert rc == 2


# ---------------------------------------------------------------------------
# Integration: capture → verify → authorize → rollback
# ---------------------------------------------------------------------------


class TestPublicationWorkflow:
    """End-to-end publication gate flow."""

    def test_full_workflow(
        self,
        valid_scope_file: pathlib.Path,
        evidence_dir: pathlib.Path,
    ) -> None:
        # 1. Capture
        rc = op_capture(
            version="0.87.0",
            phase="1-implement",
            scope_path=valid_scope_file,
            evidence_dir=evidence_dir,
        )
        assert rc == 0

        evidence_file = next(evidence_dir.glob("sa117_evidence_*.json"))

        # 2. Verify
        rc = op_verify(
            evidence_path=evidence_file,
            scope_path=valid_scope_file,
        )
        assert rc == 0

        # Read evidence for digest
        evidence = json.loads(evidence_file.read_bytes())
        digest = evidence["scope_digest"]

        # 3. Authorize
        rc = op_authorize(
            version="0.87.0",
            evidence_digest=digest,
            auth_dir=evidence_dir,
        )
        assert rc == 0

        # Get the token
        auth_file = next(evidence_dir.glob("sa117_auth_*.json"))
        auth_record = json.loads(auth_file.read_bytes())
        token = auth_record["token"]

        # 4. Rollback with matching digest
        rc = op_rollback(
            auth_token=token,
            evidence_digest=digest,
            auth_dir=evidence_dir,
        )
        assert rc == 0
        assert not auth_file.is_file()
