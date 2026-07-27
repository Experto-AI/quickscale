r"""
Focused tests for the SA117 scope guard (``check_sa117_scope.py``).

Covers:

* NUL-path validation — embedded ``\\x00`` in a path must be rejected.
* Path normalisation — leading ``./`` stripping, separator normalisation.
* Allowlist loading — well-formed scope, missing keys, duplicate paths.
* ``worktree`` mode — pass/fail based on allowlist membership.
* ``emit`` mode — full and phase-filtered output.
* ``lock`` mode — exact match, missing, and extra path detection.

All tests use synthetic scope data — no filesystem fixtures are required
beyond a temporary scope file.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import tempfile
from typing import Any

import pytest

from scripts.check_sa117_scope import (
    _LOCKED_MODULE_PACKAGES,
    _filter_scope_paths,
    _normalise,
    _validate_no_nul,
    build_allowlist,
    load_scope,
    mode_emit,
    mode_lock,
    mode_lock_poetry,
    mode_worktree,
)
from scripts.verify_sa117_publication import (
    _compute_scope_digest,
    op_capture,
    op_verify,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_scope_data() -> dict[str, Any]:
    """Return a minimal valid SA117 scope dict."""
    return {
        "version": "1.0.0",
        "description": "Test scope",
        "paths": [
            {"path": "scripts/test_foo.py", "phase": "1-implement", "notes": ""},
            {"path": "scripts/test_bar.py", "phase": "2-implement", "notes": ""},
        ],
    }


@pytest.fixture
def valid_scope_path(valid_scope_data: dict[str, Any]) -> pathlib.Path:
    """Write *valid_scope_data* to a temporary file and return its path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(valid_scope_data, tmp)
    tmp.close()
    yield pathlib.Path(tmp.name)
    pathlib.Path(tmp.name).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# NUL-path safety
# ---------------------------------------------------------------------------


class TestValidateNoNul:
    """``_validate_no_nul`` rejects paths with embedded NUL characters."""

    def test_clean_path_passes(self) -> None:
        """A normal path without NUL passes validation."""
        assert _validate_no_nul("scripts/foo.py") == "scripts/foo.py"

    def test_nul_raises(self) -> None:
        """A path with embedded NUL raises ``ValueError``."""
        with pytest.raises(ValueError, match="NUL"):
            _validate_no_nul("scripts/\x00foo.py")

    def test_nul_at_end_raises(self) -> None:
        """A path with trailing NUL raises ``ValueError``."""
        with pytest.raises(ValueError, match="NUL"):
            _validate_no_nul("scripts/foo.py\x00")

    def test_multiple_nuls_raises(self) -> None:
        """A path with multiple embedded NUL characters raises ``ValueError``."""
        with pytest.raises(ValueError, match="NUL"):
            _validate_no_nul("\x00scripts/\x00foo.py\x00")


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------


class TestNormalise:
    """``_normalise`` produces clean POSIX relative paths."""

    def test_simple_path(self) -> None:
        """A clean relative path passes through unchanged."""
        assert _normalise("scripts/foo.py") == "scripts/foo.py"

    def test_leading_dot_slash_stripped(self) -> None:
        """Leading ``./`` is stripped."""
        assert _normalise("./scripts/foo.py") == "scripts/foo.py"

    def test_double_leading_dot_slash_stripped(self) -> None:
        """Leading ``././`` is collapsed."""
        assert _normalise("././scripts/foo.py") == "scripts/foo.py"

    def test_backslash_normalised(self) -> None:
        """Backslashes are converted to forward slashes."""
        assert _normalise("scripts\\foo.py") == "scripts/foo.py"

    def test_mixed_separators_normalised(self) -> None:
        """Mixed backslash and forward slash are normalised."""
        assert _normalise("scripts\\sub/foo.py") == "scripts/sub/foo.py"

    def test_nul_raises(self) -> None:
        """NUL in input is still rejected via ``_validate_no_nul``."""
        with pytest.raises(ValueError, match="NUL"):
            _normalise("scripts/\x00foo.py")

    def test_unicode_path(self) -> None:
        """Unicode characters in paths are preserved."""
        path = "scripts/café_测试.py"
        assert _normalise(path) == path

    def test_space_in_path(self) -> None:
        """Spaces in paths are preserved (not NUL-safe truncation)."""
        assert _normalise("scripts/my helper.py") == "scripts/my helper.py"

    def test_empty_string(self) -> None:
        """An empty string normalises to empty."""
        assert _normalise("") == ""

    def test_dot_only(self) -> None:
        """A single dot normalises to empty."""
        assert _normalise(".") == ""

    def test_double_dot_not_in_scope(self) -> None:
        """``..`` components are preserved (caller's responsibility)."""
        assert _normalise("scripts/../foo.py") == "foo.py"


# ---------------------------------------------------------------------------
# Allowlist loading
# ---------------------------------------------------------------------------


class TestLoadScope:
    """``load_scope`` validates the scope JSON structure."""

    def test_loads_valid_scope(self, valid_scope_path: pathlib.Path) -> None:
        """A valid scope file returns the expected entries."""
        entries = load_scope(valid_scope_path)
        assert len(entries) == 2
        assert entries[0]["path"] == "scripts/test_foo.py"

    def test_missing_file_raises(self) -> None:
        """A missing scope file raises ``FileNotFoundError``."""
        with pytest.raises(FileNotFoundError):
            load_scope(pathlib.Path("/nonexistent/sa117_scope.json"))

    def test_missing_paths_key_raises(self) -> None:
        """A scope dict without a 'paths' key raises ``ValueError``."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"version": "1.0.0"}, tmp)
        tmp.close()
        p = pathlib.Path(tmp.name)
        try:
            with pytest.raises(ValueError, match="paths"):
                load_scope(p)
        finally:
            p.unlink(missing_ok=True)

    def test_paths_not_list_raises(self) -> None:
        """A 'paths' value that is not a list raises ``ValueError``."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"paths": "not_a_list"}, tmp)
        tmp.close()
        p = pathlib.Path(tmp.name)
        try:
            with pytest.raises(ValueError, match="paths"):
                load_scope(p)
        finally:
            p.unlink(missing_ok=True)

    def test_entry_not_dict_raises(self) -> None:
        """A non-dict entry in paths raises ``ValueError``."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"paths": ["string_not_dict"]}, tmp)
        tmp.close()
        p = pathlib.Path(tmp.name)
        try:
            with pytest.raises(ValueError, match="not a dict"):
                load_scope(p)
        finally:
            p.unlink(missing_ok=True)

    def test_entry_missing_path_raises(self) -> None:
        """An entry without a 'path' key raises ``ValueError``."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"paths": [{"phase": "1-implement"}]}, tmp)
        tmp.close()
        p = pathlib.Path(tmp.name)
        try:
            with pytest.raises(ValueError, match="missing 'path'"):
                load_scope(p)
        finally:
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# build_allowlist
# ---------------------------------------------------------------------------


class TestBuildAllowlist:
    """``build_allowlist`` builds a normalised-path lookup."""

    def test_builds_lookup(self, valid_scope_data: dict[str, Any]) -> None:
        """A valid scope builds a lookup with normalised keys."""
        lookup = build_allowlist(valid_scope_data["paths"])
        assert "scripts/test_foo.py" in lookup
        assert "scripts/test_bar.py" in lookup

    def test_duplicate_normalised_path_raises(self) -> None:
        """Two entries with the same normalised path raise ``ValueError``."""
        entries = [
            {"path": "scripts/foo.py", "phase": "1", "notes": ""},
            {"path": "./scripts/foo.py", "phase": "2", "notes": ""},
        ]
        with pytest.raises(ValueError, match="duplicate"):
            build_allowlist(entries)


# ---------------------------------------------------------------------------
# _filter_scope_paths
# ---------------------------------------------------------------------------


class TestFilterScopePaths:
    """``_filter_scope_paths`` filters path sets by scripts/ prefix."""

    def test_no_filter_when_scripts_only_false(self) -> None:
        """When scripts_only is False, all paths are returned unchanged."""
        paths = {"scripts/foo.py", "Makefile", "pyproject.toml"}
        result = _filter_scope_paths(paths, scripts_only=False)
        assert result == paths

    def test_filters_to_scripts_only(self) -> None:
        """When scripts_only is True, only scripts/ paths remain."""
        paths = {"scripts/foo.py", "Makefile", "pyproject.toml", "scripts/bar.py"}
        result = _filter_scope_paths(paths, scripts_only=True)
        assert result == {"scripts/foo.py", "scripts/bar.py"}

    def test_empty_set_returns_empty(self) -> None:
        """An empty set returns empty regardless of scripts_only."""
        assert _filter_scope_paths(set(), scripts_only=True) == set()
        assert _filter_scope_paths(set(), scripts_only=False) == set()

    def test_no_scripts_paths_returns_empty_when_filtered(self) -> None:
        """When scripts_only is True but no paths start with scripts/, empty set."""
        result = _filter_scope_paths({"Makefile", "README.md"}, scripts_only=True)
        assert result == set()


# ---------------------------------------------------------------------------
# Mode: worktree
# ---------------------------------------------------------------------------


class TestModeWorktree:
    """``mode_worktree`` validates paths against the allowlist."""

    def test_all_paths_allowed(self, valid_scope_path: pathlib.Path) -> None:
        """Paths that are all in the allowlist pass."""
        rc = mode_worktree(
            valid_scope_path,
            paths=["scripts/test_foo.py", "scripts/test_bar.py"],
        )
        assert rc == 0

    def test_path_not_in_allowlist_fails(self, valid_scope_path: pathlib.Path) -> None:
        """A path not in the allowlist fails."""
        rc = mode_worktree(
            valid_scope_path,
            paths=["scripts/unknown.py"],
        )
        assert rc == 1

    def test_non_scripts_path_ignored_with_scripts_only(
        self, valid_scope_path: pathlib.Path
    ) -> None:
        """Paths outside ``scripts/`` are ignored when ``scripts_only=True``."""
        rc = mode_worktree(
            valid_scope_path,
            paths=["Makefile", "pyproject.toml"],
            scripts_only=True,
        )
        assert rc == 0

    def test_non_scripts_path_fails_without_scripts_only(
        self, valid_scope_path: pathlib.Path
    ) -> None:
        """Paths outside ``scripts/`` cause violations when not in allowlist."""
        rc = mode_worktree(
            valid_scope_path,
            paths=["Makefile", "pyproject.toml", "scripts/test_foo.py"],
            scripts_only=False,
        )
        # Makefile and pyproject.toml are not in the test allowlist
        assert rc == 1

    def test_all_paths_in_allowlist_pass_without_scripts_only(
        self, valid_scope_path: pathlib.Path
    ) -> None:
        """When all paths are in the allowlist (including non-scripts), pass."""
        # Create scope that includes a non-scripts path
        scope_data = {
            "version": "1.0.0",
            "paths": [
                {"path": "scripts/test_foo.py", "phase": "1", "notes": ""},
                {"path": "Makefile", "phase": "1", "notes": ""},
            ],
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(scope_data, tmp)
        tmp.close()
        p = pathlib.Path(tmp.name)
        try:
            rc = mode_worktree(p, paths=["scripts/test_foo.py", "Makefile"])
            assert rc == 0
        finally:
            p.unlink(missing_ok=True)

    def test_nul_path_returns_error(self, valid_scope_path: pathlib.Path) -> None:
        """A NUL-containing path causes exit 2."""
        rc = mode_worktree(
            valid_scope_path,
            paths=["scripts/\x00evil.py"],
        )
        assert rc == 2

    def test_missing_scope_file_returns_error(self) -> None:
        """A missing scope file causes exit 2."""
        rc = mode_worktree(
            pathlib.Path("/nonexistent/sa117_scope.json"),
            paths=["scripts/foo.py"],
        )
        assert rc == 2

    def test_mixed_allowed_and_violation(self, valid_scope_path: pathlib.Path) -> None:
        """When some paths are allowed and some are not, exit 1."""
        rc = mode_worktree(
            valid_scope_path,
            paths=["scripts/test_foo.py", "scripts/unknown.py"],
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# Mode: emit
# ---------------------------------------------------------------------------


class TestModeEmit:
    """``mode_emit`` prints allowlist paths."""

    def test_emit_all_paths(self, valid_scope_path: pathlib.Path, capsys) -> None:
        """Emit without phase filter prints all paths."""
        rc = mode_emit(valid_scope_path)
        captured = capsys.readouterr()
        assert rc == 0
        assert "scripts/test_foo.py" in captured.out
        assert "scripts/test_bar.py" in captured.out

    def test_emit_filtered_by_phase(self, valid_scope_path: pathlib.Path, capsys) -> None:
        """Emit with ``--phase`` filters to matching entries."""
        rc = mode_emit(valid_scope_path, phase="1-implement")
        captured = capsys.readouterr()
        assert rc == 0
        assert "scripts/test_foo.py" in captured.out
        assert "scripts/test_bar.py" not in captured.out

    def test_emit_no_match_phase(self, valid_scope_path: pathlib.Path, capsys) -> None:
        """Emit with a phase that has no entries prints nothing."""
        rc = mode_emit(valid_scope_path, phase="nonexistent")
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out.strip() == ""

    def test_emit_missing_scope_returns_error(self) -> None:
        """Emit with a missing scope file causes exit 2."""
        rc = mode_emit(pathlib.Path("/nonexistent/sa117_scope.json"))
        assert rc == 2


# ---------------------------------------------------------------------------
# Mode: lock
# ---------------------------------------------------------------------------


class TestModeLock:
    """``mode_lock`` verifies exact path-set match."""

    def test_exact_match_passes(self, valid_scope_path: pathlib.Path) -> None:
        """When all and only the allowlist paths are present, exit 0."""
        rc = mode_lock(
            valid_scope_path,
            paths=["scripts/test_foo.py", "scripts/test_bar.py"],
        )
        assert rc == 0

    def test_missing_path_fails(self, valid_scope_path: pathlib.Path) -> None:
        """When an allowlist path is missing, exit 1."""
        rc = mode_lock(
            valid_scope_path,
            paths=["scripts/test_foo.py"],  # test_bar.py missing
        )
        assert rc == 1

    def test_extra_path_fails(self, valid_scope_path: pathlib.Path) -> None:
        """When an extra path is present, exit 1."""
        rc = mode_lock(
            valid_scope_path,
            paths=["scripts/test_foo.py", "scripts/test_bar.py", "scripts/extra.py"],
        )
        assert rc == 1

    def test_nul_path_returns_error(self, valid_scope_path: pathlib.Path) -> None:
        """A NUL-containing path causes exit 2."""
        rc = mode_lock(
            valid_scope_path,
            paths=["scripts/\x00evil.py"],
        )
        assert rc == 2

    def test_missing_scope_returns_error(self) -> None:
        """Lock with a missing scope file causes exit 2."""
        rc = mode_lock(
            pathlib.Path("/nonexistent/sa117_scope.json"),
            paths=["scripts/foo.py"],
        )
        assert rc == 2

    def test_non_scripts_paths_ignored_with_scripts_only(
        self, valid_scope_path: pathlib.Path
    ) -> None:
        """Paths outside ``scripts/`` are not compared when ``scripts_only=True``."""
        rc = mode_lock(
            valid_scope_path,
            paths=["scripts/test_foo.py", "scripts/test_bar.py", "Makefile"],
            scripts_only=True,
        )
        assert rc == 0

    def test_extra_non_scripts_path_fails_without_scripts_only(
        self, valid_scope_path: pathlib.Path
    ) -> None:
        """An extra non-scripts path causes failure when ``scripts_only=False``."""
        rc = mode_lock(
            valid_scope_path,
            paths=["scripts/test_foo.py", "scripts/test_bar.py", "Makefile"],
            scripts_only=False,
        )
        # Makefile is extra (not in allowlist)
        assert rc == 1

    def test_exact_full_match_passes(self, valid_scope_path: pathlib.Path) -> None:
        """When the full path set (including non-scripts) matches exactly, pass."""
        # Create scope that includes scripts + non-scripts
        scope_data = {
            "version": "1.0.0",
            "paths": [
                {"path": "scripts/test_foo.py", "phase": "1", "notes": ""},
                {"path": "scripts/test_bar.py", "phase": "1", "notes": ""},
                {"path": "Makefile", "phase": "1", "notes": ""},
            ],
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(scope_data, tmp)
        tmp.close()
        p = pathlib.Path(tmp.name)
        try:
            rc = mode_lock(
                p,
                paths=["scripts/test_foo.py", "scripts/test_bar.py", "Makefile"],
                scripts_only=False,
            )
            assert rc == 0
        finally:
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Mode: lock (poetry.lock version guard)
# ---------------------------------------------------------------------------


class TestModeLockPoetry:
    """``mode_lock_poetry`` verifies module package versions in poetry.lock."""

    def test_twelve_expected_packages(self) -> None:
        """There are exactly 12 expected module packages."""
        assert len(_LOCKED_MODULE_PACKAGES) == 12

    def test_package_names_are_distinct(self) -> None:
        """All package names are unique."""
        assert len(set(_LOCKED_MODULE_PACKAGES)) == len(_LOCKED_MODULE_PACKAGES)

    def test_all_packages_match_version(self, tmp_path: pathlib.Path) -> None:
        """When all module packages match expected version, exit 0."""
        lock_content = _make_lock_with_versions("0.87.0")
        lock_path = tmp_path / "poetry.lock"
        lock_path.write_text(lock_content)
        output_path = tmp_path / "evidence.json"

        rc = mode_lock_poetry(
            candidate_path=lock_path,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 0

    def test_package_version_mismatch(self, tmp_path: pathlib.Path) -> None:
        """When a module package has a wrong version, exit 1."""
        lock_content = _make_lock_with_versions("0.86.0")  # all wrong
        lock_path = tmp_path / "poetry.lock"
        lock_path.write_text(lock_content)
        output_path = tmp_path / "evidence.json"

        rc = mode_lock_poetry(
            candidate_path=lock_path,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 1

    def test_missing_module_packages(self, tmp_path: pathlib.Path) -> None:
        """When module packages are missing from lock, exit 1."""
        lock_content = _make_lock_with_versions("0.87.0", include_all=False)
        lock_path = tmp_path / "poetry.lock"
        lock_path.write_text(lock_content)
        output_path = tmp_path / "evidence.json"

        rc = mode_lock_poetry(
            candidate_path=lock_path,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 1

    def test_missing_lock_file(self, tmp_path: pathlib.Path) -> None:
        """When the lock file does not exist, exit 2."""
        rc = mode_lock_poetry(
            candidate_path=tmp_path / "nonexistent.lock",
            expected_version="0.87.0",
            output_path=tmp_path / "evidence.json",
        )
        assert rc == 2

    def test_evidence_written_on_success(self, tmp_path: pathlib.Path) -> None:
        """Evidence JSON is written on successful check."""
        lock_content = _make_lock_with_versions("0.87.0")
        lock_path = tmp_path / "poetry.lock"
        lock_path.write_text(lock_content)
        output_path = tmp_path / "evidence.json"

        rc = mode_lock_poetry(
            candidate_path=lock_path,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 0
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["status"] == "ok"
        assert data["expected_version"] == "0.87.0"

    def test_evidence_written_on_failure(self, tmp_path: pathlib.Path) -> None:
        """Evidence JSON is written even when versions mismatch."""
        lock_content = _make_lock_with_versions("0.86.0")
        lock_path = tmp_path / "poetry.lock"
        lock_path.write_text(lock_content)
        output_path = tmp_path / "evidence.json"

        rc = mode_lock_poetry(
            candidate_path=lock_path,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 1
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["status"] == "mismatch"
        assert len(data["violations"]) > 0


# ---------------------------------------------------------------------------
# Real scope validation
# ---------------------------------------------------------------------------


class TestRealScope:
    """Validation of the real ``sa117_scope.json`` allowlist."""

    SCOPE_PATH = pathlib.Path("scripts/sa117_scope.json")

    def test_real_scope_has_exactly_106_entries(self) -> None:
        """The real scope file contains exactly 106 path entries (86 + 20-record append)."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)
        assert len(entries) == 106, f"Expected exactly 106 scope entries, got {len(entries)}"

    def test_closeout_phase_entry_is_allowlisted(self) -> None:
        """A closeout-phase scripts/ entry passes worktree mode (still in allowlist)."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        rc = mode_worktree(
            self.SCOPE_PATH,
            paths=["scripts/README.md"],  # phase "1-closeout"
        )
        assert rc == 0, (
            f"Closeout-phase scripts/ entry should be allowlisted, but worktree returned {rc}"
        )

    def test_repair_entries_exact_five(self) -> None:
        """Exactly 5 repair entries (incl. validation_policy), all phase '10-repair' with notes."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)
        repair = [e for e in entries if e.get("phase") == "10-repair"]
        assert len(repair) == 5, f"Expected exactly 5 repair-phase entries, got {len(repair)}"
        for entry in repair:
            assert "path" in entry, f"Repair entry missing 'path': {entry}"
            assert entry.get("phase") == "10-repair", f"Repair entry has wrong phase: {entry}"
            assert entry.get("notes", "").strip(), (
                f"Repair entry has empty or whitespace-only notes: {entry}"
            )

    def test_repair_entries_correct_paths(self) -> None:
        """The 5 repair entries have the exact expected doc paths including validation_policy."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)
        repair = [e for e in entries if e.get("phase") == "10-repair"]
        repair_paths = sorted(e["path"] for e in repair)
        expected = sorted(
            [
                "docs/technical/decisions.md",
                "docs/technical/user_manual.md",
                "docs/technical/plan-apply-system.md",
                "docs/technical/versioning.md",
                "docs/technical/validation_policy.md",
            ]
        )
        assert repair_paths == expected, (
            f"Repair entry paths mismatch.\n  Expected: {expected}\n  Got:      {repair_paths}"
        )

    def test_repair_entries_readme_not_duplicated(self) -> None:
        """The existing scripts/README.md entry is still present exactly once."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)
        readme_entries = [e for e in entries if e["path"] == "scripts/README.md"]
        assert len(readme_entries) == 1, (
            f"Expected exactly 1 scripts/README.md entry, got {len(readme_entries)}"
        )

    # ------------------------------------------------------------------
    # Direct set assertion (frozen repair-entry path set)
    # ------------------------------------------------------------------

    def test_repair_entries_using_set_assertion(self) -> None:
        """Repair-entry path set matches expected exactly using direct set comparison."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)
        repair_paths_set = {e["path"] for e in entries if e.get("phase") == "10-repair"}
        expected_paths_set = {
            "docs/technical/decisions.md",
            "docs/technical/user_manual.md",
            "docs/technical/plan-apply-system.md",
            "docs/technical/versioning.md",
            "docs/technical/validation_policy.md",
        }
        assert repair_paths_set == expected_paths_set, (
            f"Repair entry path set mismatch.\n"
            f"  Extra:   {repair_paths_set - expected_paths_set}\n"
            f"  Missing: {expected_paths_set - repair_paths_set}"
        )

    # ------------------------------------------------------------------
    # Scripts-only checker seam
    # ------------------------------------------------------------------

    def test_scripts_only_checker_seam(self) -> None:
        """``mode_worktree`` with ``scripts_only=True`` ignores non-scripts paths."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"

        # A non-scripts path not in the allowlist passes (scripts/ filter)
        rc = mode_worktree(
            self.SCOPE_PATH,
            paths=["Makefile", "pyproject.toml"],
            scripts_only=True,
        )
        assert rc == 0, f"Non-scripts paths should be ignored with scripts_only=True, got rc={rc}"

        # A non-scripts path mixed with a scripts/ violation still catches violation
        rc = mode_worktree(
            self.SCOPE_PATH,
            paths=["Makefile", "scripts/unknown_new_file.py"],
            scripts_only=True,
        )
        assert rc == 1, (
            f"scripts/ violations should still be caught alongside non-scripts, got rc={rc}"
        )

    def test_full_scope_check(self) -> None:
        """Without ``scripts_only``, all paths are checked (non-scripts violations caught)."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"

        # A non-scripts path NOT in the allowlist should FAIL without scripts_only
        rc = mode_worktree(
            self.SCOPE_PATH,
            paths=["nonexistent_file.py"],
            scripts_only=False,
        )
        assert rc == 1, f"Non-scripts path should fail without scripts_only, got rc={rc}"

        # Makefile is in the allowlist, so it should pass
        rc = mode_worktree(
            self.SCOPE_PATH,
            paths=["Makefile"],
            scripts_only=False,
        )
        assert rc == 0, f"Makefile should pass full scope check, got rc={rc}"

    # ------------------------------------------------------------------
    # Frozen baseline payload: 20 non-scope modified files
    # ------------------------------------------------------------------

    def test_appended_20_records_are_in_scope(self) -> None:
        """All 20 appended records are now present in the scope allowlist (validates append)."""
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)
        scope_paths = {e["path"] for e in entries}

        # The 20 records appended to the original 86-entry scope
        appended_paths = {
            "docs/technical/validation_policy.md",
            "poetry.lock",
            "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
            "quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py",
            "quickscale_cli/tests/commands/test_module_commands.py",
            "quickscale_cli/tests/test_module_wiring_manager_manifest.py",
            "quickscale_core/src/quickscale_core/data/manifests/analytics/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/backups/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/billing/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/blog/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/crm/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/forms/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/notifications/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/social/module.yml",
            "quickscale_core/src/quickscale_core/data/manifests/storage/module.yml",
            "quickscale_core/src/quickscale_core/manifest/loader.py",
            "quickscale_core/src/quickscale_core/utils/git_utils.py",
            "quickscale_core/tests/test_git_utils.py",
            "quickscale_core/tests/test_manifest_loader.py",
            "scripts/publish_module.py",
        }
        assert len(appended_paths) == 20, (
            f"Appended set should have exactly 20 entries, got {len(appended_paths)}"
        )
        # Verify all 20 appended paths are now in the scope allowlist
        overlap = appended_paths & scope_paths
        assert len(overlap) == 20, (
            f"Expected all 20 appended paths to be in the allowlist, "
            f"but {20 - len(overlap)} are missing: {appended_paths - scope_paths}"
        )

    def test_appended_20_records_exact_ordered_objects(self) -> None:
        """
        Verify the 20 appended records match the approved literal payload exactly.

        Compares path, phase, and notes — compared as ordered dicts, not just
        membership.
        """
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)

        # Entries 86–105 (0-indexed) are the 20 appended records
        appended_entries = entries[86:106]
        assert len(appended_entries) == 20, (
            f"Expected 20 appended entries (indices 86–105), got {len(appended_entries)}"
        )

        expected = [
            {
                "path": "docs/technical/validation_policy.md",
                "phase": "10-repair",
                "notes": "SA117 repair — validation policy documentation corrections.",
            },
            {
                "path": "poetry.lock",
                "phase": "3-implement",
                "notes": "Root poetry.lock — SA117 version lockstep anchor.",
            },
            {
                "path": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                "phase": "4-implement",
                "notes": "SA117 closeout — module commands manifest wiring.",
            },
            {
                "path": "quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py",
                "phase": "4-implement",
                "notes": "SA117 closeout — module wiring manifest resolution.",
            },
            {
                "path": "quickscale_cli/tests/commands/test_module_commands.py",
                "phase": "9-implement",
                "notes": "SA117 closeout — module commands test.",
            },
            {
                "path": "quickscale_cli/tests/test_module_wiring_manager_manifest.py",
                "phase": "9-implement",
                "notes": "SA117 closeout — wiring manager manifest test.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/analytics/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/backups/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/billing/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/blog/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/crm/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/forms/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/"
                "notifications/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/social/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/data/manifests/storage/module.yml",
                "phase": "8-closeout",
                "notes": "Core manifest snapshot — SA117 evidence.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/manifest/loader.py",
                "phase": "4-implement",
                "notes": "SA117 closeout — manifest loader resolution.",
            },
            {
                "path": "quickscale_core/src/quickscale_core/utils/git_utils.py",
                "phase": "4-implement",
                "notes": "SA117 closeout — git utilities evidence.",
            },
            {
                "path": "quickscale_core/tests/test_git_utils.py",
                "phase": "9-implement",
                "notes": "SA117 closeout — git utilities test.",
            },
            {
                "path": "quickscale_core/tests/test_manifest_loader.py",
                "phase": "9-implement",
                "notes": "SA117 closeout — manifest loader test.",
            },
            {
                "path": "scripts/publish_module.py",
                "phase": "2-implement",
                "notes": "Module publish script — SA117 version lockstep enforcement.",
            },
        ]

        # Per-index diagnostics — collect all mismatches, no dead code path
        mismatches: list[str] = []
        for i, (got, exp) in enumerate(zip(appended_entries, expected)):
            if got != exp:
                mismatches.append(f"  Index 86+{i}: expected {exp}, got {got}")
        assert not mismatches, (
            "Appended records do not match the approved literal payload:\n" + "\n".join(mismatches)
        )

    # ------------------------------------------------------------------
    # Original 86-entry prefix SHA-256 assertion
    # ------------------------------------------------------------------

    def test_original_86_prefix_sha256_preserved(self) -> None:
        """
        Assert the original 86-entry prefix SHA-256 digest matches the plan-reviewed baseline.

        The SA117 scope allowlist started as an 86-entry file that was
        reviewed and approved during SA117 plan review.  The 20-record
        append operation appended to that file without modifying any
        existing entry.  This test freezes the canonical SHA-256 digest
        of ``entries[:86]`` serialised as compact sorted-key JSON and
        asserts the current prefix still matches, proving the append
        preserved the original payload intact.

        The digest was computed from the plan-reviewed pre-append file
        and committed as an immutable provenance anchor.  If the prefix
        ever changes, the new prefix must itself be plan-reviewed before
        any suffix test can pass.
        """
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"
        entries = load_scope(self.SCOPE_PATH)

        prefix = json.dumps(
            entries[:86],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        actual_digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()

        # Canonical digest of the plan-reviewed 86-entry prefix
        # (computed 2026-07-27 from SA117 plan-review approved artifact)
        canonical_prefix_digest: str = (
            "a34e4f6a294c0911660a7e4e35289782ff1688e30abf497eca705e1ffde45cf1"
        )
        assert actual_digest == canonical_prefix_digest, (
            f"Original 86-entry prefix SHA-256 has changed.\n"
            f"  Expected: {canonical_prefix_digest}\n"
            f"  Actual:   {actual_digest}\n\n"
            "The prefix must not change without plan review.  If the prefix "
            "was intentionally modified, update the frozen digest and obtain "
            "plan-review approval before proceeding."
        )

    # ------------------------------------------------------------------
    # Fresh / stale publication evidence (mode_lock_poetry evidence shape)
    # ------------------------------------------------------------------

    def test_fresh_publication_evidence(self, tmp_path: pathlib.Path) -> None:
        """Fresh evidence output from mode_lock_poetry has expected structure and status 'ok'."""
        lock_content = _make_lock_with_versions("0.87.0")
        lock_path = tmp_path / "poetry.lock"
        lock_path.write_text(lock_content)
        output_path = tmp_path / "evidence.json"

        rc = mode_lock_poetry(
            candidate_path=lock_path,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 0, f"Fresh evidence expected rc=0, got {rc}"

        assert output_path.exists(), "Evidence file was not written"
        data = json.loads(output_path.read_text())
        assert data["status"] == "ok", (
            f"Fresh evidence status should be 'ok', got {data['status']!r}"
        )
        assert data["expected_version"] == "0.87.0"
        assert data["module_packages_found"] == 12
        assert data["module_packages_expected"] == 12
        assert data["violations"] == []
        assert "candidate" in data
        assert "tool" in data

    def test_stale_publication_evidence(self, tmp_path: pathlib.Path) -> None:
        """Stale evidence has expected structure and status 'mismatch'."""
        lock_content = _make_lock_with_versions("0.86.0")
        lock_path = tmp_path / "poetry.lock"
        lock_path.write_text(lock_content)
        output_path = tmp_path / "evidence.json"

        rc = mode_lock_poetry(
            candidate_path=lock_path,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 1, f"Stale evidence expected rc=1, got {rc}"

        assert output_path.exists(), "Evidence file was not written"
        data = json.loads(output_path.read_text())
        assert data["status"] == "mismatch", (
            f"Stale evidence status should be 'mismatch', got {data['status']!r}"
        )
        assert data["expected_version"] == "0.87.0"
        assert data["module_packages_found"] == 12
        assert data["module_packages_expected"] == 12
        assert len(data["violations"]) > 0
        for v in data["violations"]:
            assert v["expected_version"] == "0.87.0"
            assert v["actual_version"] == "0.86.0"

    # ------------------------------------------------------------------
    # Amended-scope publication capture/verify (SA117-CR-002)
    # ------------------------------------------------------------------

    def test_amended_scope_publication_verify(self, tmp_path: pathlib.Path) -> None:
        """
        Capture and verify publication evidence for the real amended scope.

        Exercises ``op_capture`` and ``op_verify`` in an isolated ``tmp_path``
        with no network, Docker, or external state:

        * ``op_capture`` against the real 106-entry scope writes evidence with
          ``paths_count == 106`` and the correct raw SHA-256 digest.
        * ``op_verify`` on the captured evidence passes (return 0).
        * Evidence captured against the old 86-entry scope fails ``op_verify``
          against the current 106-entry scope (return 1, digest mismatch).
        """
        assert self.SCOPE_PATH.exists(), f"Scope file not found: {self.SCOPE_PATH}"

        # Copy real scope into isolated tmp_path
        scope_path = tmp_path / "sa117_scope.json"
        scope_path.write_bytes(self.SCOPE_PATH.read_bytes())

        # --- Fresh evidence: capture via op_capture ---
        fresh_dir = tmp_path / "fresh"
        rc_capture = op_capture(
            version="0.87.0",
            phase="final",
            scope_path=scope_path,
            evidence_dir=fresh_dir,
        )
        assert rc_capture == 0, f"op_capture expected rc=0, got {rc_capture}"

        # Find the captured evidence file
        fresh_files = sorted(fresh_dir.glob("sa117_evidence_*.json"))
        assert len(fresh_files) == 1, (
            f"Expected exactly one evidence file in fresh dir, got {len(fresh_files)}"
        )
        fresh_path = fresh_files[0]

        # Assert captured paths_count equals load_scope count (106)
        entries = load_scope(scope_path)
        fresh_evidence = json.loads(fresh_path.read_bytes())
        assert fresh_evidence["paths_count"] == len(entries), (
            f"Captured evidence paths_count expected {len(entries)}, "
            f"got {fresh_evidence['paths_count']}"
        )
        assert len(entries) == 106, f"Expected exactly 106 scope entries, got {len(entries)}"

        # Assert raw SHA-256 matches
        raw_digest = _compute_scope_digest(scope_path)
        assert fresh_evidence["scope_digest"] == raw_digest, (
            f"Captured evidence scope_digest mismatch.\n"
            f"  Expected: {raw_digest}\n"
            f"  Got:      {fresh_evidence['scope_digest']}"
        )

        # op_verify fresh evidence returns 0
        rc_fresh = op_verify(evidence_path=fresh_path, scope_path=scope_path)
        assert rc_fresh == 0, f"Fresh evidence verify expected rc=0, got {rc_fresh}"

        # --- Stale evidence: old 86 count + old pre-append digest ---
        entries_full = load_scope(self.SCOPE_PATH)
        old_scope_dict = {
            "version": "1.0.0",
            "description": entries_full[0]["notes"] if len(entries_full) > 0 else "",
            "paths": entries_full[:86],
        }
        old_scope_bytes = (json.dumps(old_scope_dict, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        old_scope_path = tmp_path / "sa117_scope_86.json"
        old_scope_path.write_bytes(old_scope_bytes)

        stale_dir = tmp_path / "stale"
        rc_stale_capture = op_capture(
            version="0.87.0",
            phase="final",
            scope_path=old_scope_path,
            evidence_dir=stale_dir,
        )
        assert rc_stale_capture == 0, f"Stale op_capture expected rc=0, got {rc_stale_capture}"

        stale_files = sorted(stale_dir.glob("sa117_evidence_*.json"))
        assert len(stale_files) == 1, (
            f"Expected exactly one evidence file in stale dir, got {len(stale_files)}"
        )
        stale_path = stale_files[0]

        # Verify stale evidence against the CURRENT (106-entry) scope — must fail
        rc_stale = op_verify(evidence_path=stale_path, scope_path=scope_path)
        assert rc_stale == 1, (
            f"Stale evidence (count=86, old digest) verify expected rc=1, "
            f"got {rc_stale} — digest must fail against current scope"
        )

        # Confirm stale evidence reports 86 paths
        stale_evidence = json.loads(stale_path.read_bytes())
        assert stale_evidence["paths_count"] == 86, (
            f"Stale evidence paths_count expected 86, got {stale_evidence['paths_count']}"
        )


# ---------------------------------------------------------------------------
# Worktree mode: paths required (CR-005 baseline-to-candidate contract)
# ---------------------------------------------------------------------------


class TestModeWorktreePathsRequired:
    """``mode_worktree`` now requires explicit ``--paths``."""

    def test_worktree_requires_paths(self, valid_scope_path: pathlib.Path) -> None:
        """Calling mode_worktree without paths returns exit 2."""
        rc = mode_worktree(valid_scope_path)
        assert rc == 2, "mode_worktree without paths should return 2"


# ---------------------------------------------------------------------------
# Real temp git repo + Make target tests (SA117-CR-005)
# ---------------------------------------------------------------------------


class TestModeWorktreeRealGitRepo:
    """Worktree mode with a real temp git repository."""

    def test_real_temp_git_repo_passes(self, tmp_path: pathlib.Path) -> None:
        """A real temp git repo with only allowlisted paths passes."""
        # Create scope allowlist
        scope_data = {
            "version": "1.0.0",
            "paths": [
                {"path": "src/main.py", "phase": "1", "notes": ""},
                {"path": "README.md", "phase": "1", "notes": ""},
            ],
        }
        scope_path = tmp_path / "scope.json"
        scope_path.write_text(json.dumps(scope_data))

        # Init git repo, add files, commit
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "src").mkdir()
        (repo / "src" / "main.py").write_text("print('hello')\n")
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            capture_output=True,
        )

        # Run worktree with candidate paths from the git repo
        rc = mode_worktree(
            scope_path,
            paths=["src/main.py", "README.md"],
        )
        assert rc == 0, f"Expected pass (0), got {rc}"

    def test_real_temp_git_repo_fails_on_extra(self, tmp_path: pathlib.Path) -> None:
        """A real temp git repo with an unlisted file in candidate fails."""
        scope_data = {
            "version": "1.0.0",
            "paths": [
                {"path": "src/main.py", "phase": "1", "notes": ""},
            ],
        }
        scope_path = tmp_path / "scope.json"
        scope_path.write_text(json.dumps(scope_data))

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "src").mkdir()
        (repo / "src" / "main.py").write_text("print('hello')\n")
        (repo / "unlisted.py").write_text("# unauthorized\n")
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            capture_output=True,
        )

        # Candidate includes an unlisted file
        rc = mode_worktree(
            scope_path,
            paths=["src/main.py", "unlisted.py"],
        )
        assert rc == 1, f"Expected fail (1) for extra file, got {rc}"

    def test_real_temp_git_repo_scripts_only(self, tmp_path: pathlib.Path) -> None:
        """Real git repo with scripts_only=1 filters to scripts/ paths."""
        scope_data = {
            "version": "1.0.0",
            "paths": [
                {"path": "scripts/build.sh", "phase": "1", "notes": ""},
                {"path": "Makefile", "phase": "1", "notes": ""},
            ],
        }
        scope_path = tmp_path / "scope.json"
        scope_path.write_text(json.dumps(scope_data))

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "scripts").mkdir()
        (repo / "scripts" / "build.sh").write_text("#!/bin/sh\necho build\n")
        (repo / "Makefile").write_text("build:\n\techo build\n")
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            capture_output=True,
        )

        # With scripts_only=True, Makefile is ignored
        rc = mode_worktree(
            scope_path,
            paths=["scripts/build.sh", "Makefile"],
            scripts_only=True,
        )
        assert rc == 0, f"Expected pass (0) with scripts_only, got {rc}"

        # With scripts_only=False, Makefile must be in allowlist (it is)
        rc = mode_worktree(
            scope_path,
            paths=["scripts/build.sh", "Makefile"],
            scripts_only=False,
        )
        assert rc == 0, f"Expected pass (0) without scripts_only, got {rc}"

        # With scripts_only=False and an extra non-scripts path, fail
        rc = mode_worktree(
            scope_path,
            paths=["scripts/build.sh", "extra.txt"],
            scripts_only=False,
        )
        assert rc == 1, f"Expected fail (1) for extra path, got {rc}"


# ---------------------------------------------------------------------------
# Git ref validation, baseline lock loading, drift detection (SA117-CR-006)
# ---------------------------------------------------------------------------


class TestResolveGitRef:
    """``_resolve_git_ref`` resolves refs to full SHAs."""

    def test_valid_ref_resolves(self, tmp_path: pathlib.Path) -> None:
        """A valid git ref resolves to a 40-char SHA."""
        from scripts.check_sa117_scope import _resolve_git_ref

        # Use HEAD of the current repo
        sha = _resolve_git_ref("HEAD")
        assert sha is not None
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)

    def test_invalid_ref_returns_none(self) -> None:
        """An unresolvable ref returns None."""
        from scripts.check_sa117_scope import _resolve_git_ref

        sha = _resolve_git_ref("nonexistent-ref-12345")
        assert sha is None


class TestLoadLockPackageMap:
    """``_load_lock_package_map`` parses poetry.lock TOML into name→version."""

    def test_parses_packages(self) -> None:
        from scripts.check_sa117_scope import _load_lock_package_map

        toml = (
            "[[package]]\n"
            'name = "requests"\n'
            'version = "2.31.0"\n'
            "\n"
            "[[package]]\n"
            'name = "quickscale-module-auth"\n'
            'version = "0.87.0"\n'
        )
        result = _load_lock_package_map(toml)
        assert result == {"requests": "2.31.0", "quickscale-module-auth": "0.87.0"}

    def test_empty_lock(self) -> None:
        from scripts.check_sa117_scope import _load_lock_package_map

        assert _load_lock_package_map("") == {}
        assert _load_lock_package_map("[metadata]\nversion = '1'\n") == {}


class TestModeVerifyLockDiff:
    """``mode_verify_lock_diff`` validates refs, baseline, and drift."""

    def test_invalid_ref_returns_error(self, tmp_path: pathlib.Path) -> None:
        """An unresolvable baseline ref returns exit 2."""
        from scripts.check_sa117_scope import mode_verify_lock_diff

        rc = mode_verify_lock_diff(
            candidate_path=tmp_path / "nonexistent.lock",
            baseline_ref="deadbeefcafebabe000000000000000000000000",
        )
        assert rc == 2

    def test_allowed_module_version_changes_pass(self, tmp_path: pathlib.Path) -> None:
        """Module package version bumps to expected_version are allowed."""
        from scripts.check_sa117_scope import (
            _LOCKED_MODULE_PACKAGES,
            mode_verify_lock_diff,
        )

        # Build baseline lock (all module packages at 0.86.0)
        baseline_lines = [
            "[[package]]",
            'name = "unrelated-dep"',
            'version = "1.0.0"',
            "",
        ]
        for pkg in _LOCKED_MODULE_PACKAGES:
            baseline_lines.append("[[package]]")
            baseline_lines.append(f'name = "{pkg}"')
            baseline_lines.append('version = "0.86.0"')
            baseline_lines.append("")
        baseline_lock = "\n".join(baseline_lines) + "\n"

        # Build candidate lock (all module packages at 0.87.0)
        candidate_lines = [
            "[[package]]",
            'name = "unrelated-dep"',
            'version = "1.0.0"',
            "",
        ]
        for pkg in _LOCKED_MODULE_PACKAGES:
            candidate_lines.append("[[package]]")
            candidate_lines.append(f'name = "{pkg}"')
            candidate_lines.append('version = "0.87.0"')
            candidate_lines.append("")
        candidate_lock = "\n".join(candidate_lines) + "\n"

        baseline_path = tmp_path / "baseline.lock"
        baseline_path.write_text(baseline_lock)
        candidate_path = tmp_path / "candidate.lock"
        candidate_path.write_text(candidate_lock)
        output_path = tmp_path / "evidence.json"

        # Init a temp git repo, commit baseline
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "poetry.lock").write_text(baseline_lock)
        subprocess.run(["git", "add", "poetry.lock"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=tmp_path,
            capture_output=True,
        )

        baseline_ref = "HEAD"

        rc = mode_verify_lock_diff(
            candidate_path=candidate_path,
            baseline_ref=baseline_ref,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 0, f"Expected clean (0), got {rc}"

    def test_unauthorized_drift_detected(self, tmp_path: pathlib.Path) -> None:
        """Non-module package version bumps are unauthorized drift."""
        from scripts.check_sa117_scope import (
            _LOCKED_MODULE_PACKAGES,
            mode_verify_lock_diff,
        )

        # Build baseline lock
        baseline_lines = [
            "[[package]]",
            'name = "unrelated-dep"',
            'version = "1.0.0"',
            "",
        ]
        for pkg in _LOCKED_MODULE_PACKAGES:
            baseline_lines.append("[[package]]")
            baseline_lines.append(f'name = "{pkg}"')
            baseline_lines.append('version = "0.87.0"')
            baseline_lines.append("")
        baseline_lock = "\n".join(baseline_lines) + "\n"

        # Candidate has unauthorized bump on unrelated-dep
        candidate_lines = [
            "[[package]]",
            'name = "unrelated-dep"',
            'version = "2.0.0"',  # Unauthorized bump
            "",
        ]
        for pkg in _LOCKED_MODULE_PACKAGES:
            candidate_lines.append("[[package]]")
            candidate_lines.append(f'name = "{pkg}"')
            candidate_lines.append('version = "0.87.0"')
            candidate_lines.append("")
        candidate_lock = "\n".join(candidate_lines) + "\n"

        candidate_path = tmp_path / "candidate.lock"
        candidate_path.write_text(candidate_lock)
        output_path = tmp_path / "evidence.json"

        # Init temp git repo with baseline
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "poetry.lock").write_text(baseline_lock)
        subprocess.run(["git", "add", "poetry.lock"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=tmp_path,
            capture_output=True,
        )

        baseline_ref = "HEAD"

        rc = mode_verify_lock_diff(
            candidate_path=candidate_path,
            baseline_ref=baseline_ref,
            expected_version="0.87.0",
            output_path=output_path,
        )
        assert rc == 1, f"Expected drift (1), got {rc}"

        # Verify evidence was written
        assert output_path.exists()
        evidence = json.loads(output_path.read_text())
        assert evidence["status"] == "drift"
        assert len(evidence["unauthorized_drift"]) == 1
        assert evidence["unauthorized_drift"][0]["package"] == "unrelated-dep"
        assert evidence["unauthorized_drift"][0]["change"] == "version_changed"


# ---------------------------------------------------------------------------
# Helper: build a synthetic poetry.lock with module package entries
# ---------------------------------------------------------------------------


def _make_lock_with_versions(
    version: str,
    *,
    include_all: bool = True,
) -> str:
    """
    Return a minimal poetry.lock TOML string with module package entries.

    When *include_all* is True, all 12 expected module packages are included.
    When False, only the first 6 are included (to test missing-package detection).
    """
    lines = [
        "[[package]]",
        'name = "a-real-dependency"',
        'version = "1.0.0"',
        "",
    ]
    packages = _LOCKED_MODULE_PACKAGES if include_all else _LOCKED_MODULE_PACKAGES[:6]
    for pkg_name in packages:
        lines.append("[[package]]")
        lines.append(f'name = "{pkg_name}"')
        lines.append(f'version = "{version}"')
        lines.append("")

    lines.append("[metadata]")
    lines.append('lock-version = "2.0"')
    lines.append('python-versions = ">=3.13,<3.15"')
    lines.append('content-hash = "abc123"')
    lines.append("")

    return "\n".join(lines)
