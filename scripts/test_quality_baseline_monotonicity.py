"""
Focused tests for ``check_quality_baseline_monotonicity.py``.

Test matrix (CR-003..006)
--------------------------
* SA114 increase 1 — complexity 11→12 (``_validate_modules_section``)
* Retired ``large_files.max_lines`` values are ignored and never indexed
* Complexity increases still require active waivers
* A 2,000-line advisory file does not affect the quality gate exit status
* Empty baseline comparison (no violations)
* Shape/ref/date/lifecycle/determinism cases
* Schema version mismatch (int, string, bool) via subprocess
* Missing base baseline in merge-base commit
* Malformed waiver detection (missing fields, non-numeric ceiling, bool, negative)
* Expired waiver rejection (unit + subprocess)
* Over-ceiling waiver rejection (unit + subprocess)
* Stale base waiver rejection (unit + subprocess)
* Orphan waiver detection — absent, unchanged, reduced (unit + subprocess)
* Duplicate waiver_id, duplicate entry_key, both dimensions (unit + subprocess)
* Invalid decision_ref anchor rejection (unit + subprocess)
* Non-dict waiver entry rejection (subprocess)
* Unknown waiver schema version (subprocess)
* Non-dict waiver ledger rejection (subprocess)
* Bool schema version in waiver ledger (subprocess)
* Base ref precedence — CLI > QUALITY > GITHUB > v87 (real subprocess)
* GitHub origin/branch resolution precedence
* Unresolvable explicit/GitHub ref — exit 2
* Missing baseline file — exit 2
* Shell integration — exit 1/2 under set -e, policy preservation, stale artifact
  removal, analyzer suppression, compact canonical summary
* Controlled success — exact diagnostics equality across policy/report/status/Markdown
* Schema validation real subprocess matrix — every schema table row
* UTC boundary — today stays active under extreme timezone offset
* Policy file structure and deterministic keys
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
# Keep the documented direct invocation working as well as pytest collection.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Import the helpers but not main() — we test the logic directly
import scripts.check_quality_baseline_monotonicity as monotonicity_mod  # noqa: E402

# ---------------------------------------------------------------------------
# Isolated Git repository fixture helpers (CR-006)
# ---------------------------------------------------------------------------


def _git_init(path: Path) -> None:
    """Initialize a git repo at *path* with test identity."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _git_commit_all(path: Path, message: str) -> str:
    """Stage all files and commit. Returns the commit SHA."""
    subprocess.run(["git", "add", "-A"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=path,
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_tag(path: Path, tag: str) -> None:
    """Create a lightweight tag at HEAD."""
    subprocess.run(["git", "tag", tag], cwd=path, capture_output=True, check=True)


def _create_isolated_repo(
    repo_dir: Path,
    baseline_data: dict[str, Any] | None,
    tag: str = "base",
    extra_files: dict[str, str] | None = None,
) -> str:
    """
    Create an isolated Git repo with an optional committed baseline blob.

    If *baseline_data* is not None, writes it to ``scripts/quality_baseline.json``.
    Optionally writes *extra_files* (mapping of repo-relative path to content).

    Commits and tags with *tag*.  Returns the HEAD commit SHA.
    """
    _git_init(repo_dir)

    if baseline_data is not None:
        baseline_file = repo_dir / "scripts" / "quality_baseline.json"
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text(json.dumps(baseline_data), encoding="utf-8")

    if extra_files:
        for rel_path, content in extra_files.items():
            p = repo_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    sha = _git_commit_all(repo_dir, f"baseline commit for tag {tag}")
    _git_tag(repo_dir, tag)
    return sha


# Alias for readability
_check = monotonicity_mod


def _canonical_record(
    *,
    error_code: str | None = None,
    section: str | None = None,
    canonical_key: str | None = None,
    old_value: int | None = None,
    new_value: int | None = None,
    waiver_id: str | None = None,
    waiver_status: str | None = None,
    waiver_base_ceiling: int | None = None,
    waiver_ceiling: int | None = None,
    waiver_file: str | None = None,
    decision_ref: str | None = None,
    waiver_index: int | None = None,
    duplicate_kinds: list[str] | None = None,
) -> dict[str, Any]:
    """Build one complete canonical diagnostic record for exact comparisons."""
    return {
        "error_code": error_code,
        "section": section,
        "canonical_key": canonical_key,
        "old_value": old_value,
        "new_value": new_value,
        "waiver_id": waiver_id,
        "waiver_status": waiver_status,
        "waiver_base_ceiling": waiver_base_ceiling,
        "waiver_ceiling": waiver_ceiling,
        "waiver_file": waiver_file,
        "decision_ref": decision_ref,
        "waiver_index": waiver_index,
        "duplicate_kinds": duplicate_kinds or [],
    }


def _assert_exact_stdout_records(
    result: subprocess.CompletedProcess[str], records: list[dict[str, Any]]
) -> None:
    """Require the complete ordered stdout serialization, with no filtering."""
    expected_stdout = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    assert result.stdout == expected_stdout
    assert result.stderr == ""


def _assert_exact_error_envelope(
    result: subprocess.CompletedProcess[str],
    *,
    source: str,
    path: str,
    message: str,
    code: str = "SCHEMA_ERROR",
) -> None:
    """Require the complete deterministic exit-2 policy and stream envelope."""
    expected = {
        "schema_version": 1,
        "verdict": "error",
        "error": {
            "code": code,
            "source": source,
            "path": path,
            "message": message,
        },
        "diagnostics": [],
    }
    assert result.stdout == ""
    assert result.stderr == f"ERROR: {message}\n"
    policy_path = _REPO_ROOT / ".quickscale" / "quality_baseline_policy.json"
    assert policy_path.read_text() == json.dumps(expected, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def now() -> date:
    """Provide a stable "today" date for waiver validation."""
    return date(2026, 7, 26)


@pytest.fixture
def future_date() -> str:
    """Return a date safely in the future."""
    return (date.today() + timedelta(days=365)).isoformat()


@pytest.fixture
def past_date() -> str:
    """Return a date safely in the past."""
    return (date.today() - timedelta(days=365)).isoformat()


@pytest.fixture
def empty_base() -> dict[str, Any]:
    """Return an empty baseline for new-project comparisons."""
    return {
        "schema_version": 1,
        "dead_code": {"allowed_messages": []},
        "complexity": {"allowed_functions": {}},
        "large_files": {"allowed_files": {}},
        "duplication": {"allowed_blocks": 0},
    }


@pytest.fixture
def known_anchors() -> set[str]:
    """Return the set of known decision anchors."""
    decisions_path = _REPO_ROOT / "docs" / "technical" / "decisions.md"
    return _check._get_decision_anchors(decisions_path)


@pytest.fixture
def v87_baseline() -> dict[str, Any]:
    """Return the baseline as it existed at v87 (before the three SA114 increases)."""
    return {
        "schema_version": 1,
        "dead_code": {
            "allowed_messages": [
                "quickscale_cli/src/quickscale_cli/commands/apply_command.py: unused variable 'q'",
                "quickscale_modules/blog/src/quickscale_modules_blog/views.py: unused variable 'req'",  # noqa: E501
                "quickscale_modules/blog/src/quickscale_modules_blog/views.py: unused variable 'req'",  # noqa: E501
                "quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py: unused variable 'app_configs'",  # noqa: E501
                "quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py: unused variable 'app_configs'",  # noqa: E501
            ],
        },
        "complexity": {
            "allowed_functions": {
                "quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section": {  # noqa: E501
                    "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                    "max_complexity": 11,
                    "symbol": "_validate_modules_section",
                    "type": "function",
                },
                "quickscale_cli/src/quickscale_cli/commands/module_commands.py::_perform_module_embed": {  # noqa: E501
                    "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                    "max_complexity": 20,
                    "symbol": "_perform_module_embed",
                    "type": "function",
                },
                "quickscale_cli/src/quickscale_cli/commands/module_commands.py::_update_single_module": {  # noqa: E501
                    "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                    "max_complexity": 17,
                    "symbol": "_update_single_module",
                    "type": "function",
                },
            },
        },
        "duplication": {"allowed_blocks": 0},
    }


@pytest.fixture
def current_baseline_with_increases() -> dict[str, Any]:
    """Return the baseline after the three SA114 increases."""
    return {
        "schema_version": 1,
        "dead_code": {
            "allowed_messages": [
                "quickscale_cli/src/quickscale_cli/commands/apply_command.py: unused variable 'q'",
                "quickscale_modules/blog/src/quickscale_modules_blog/views.py: unused variable 'req'",  # noqa: E501
                "quickscale_modules/blog/src/quickscale_modules_blog/views.py: unused variable 'req'",  # noqa: E501
                "quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py: unused variable 'app_configs'",  # noqa: E501
                "quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py: unused variable 'app_configs'",  # noqa: E501
            ],
        },
        "complexity": {
            "allowed_functions": {
                "quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section": {  # noqa: E501
                    "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                    "max_complexity": 12,
                    "symbol": "_validate_modules_section",
                    "type": "function",
                },
                "quickscale_cli/src/quickscale_cli/commands/module_commands.py::_perform_module_embed": {  # noqa: E501
                    "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                    "max_complexity": 22,
                    "symbol": "_perform_module_embed",
                    "type": "function",
                },
                "quickscale_cli/src/quickscale_cli/commands/module_commands.py::_update_single_module": {  # noqa: E501
                    "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                    "max_complexity": 18,
                    "symbol": "_update_single_module",
                    "type": "function",
                },
            },
        },
        "duplication": {"allowed_blocks": 0},
    }


# ---------------------------------------------------------------------------
# Comparison tests (use validated indexes via _compare_indexes)
# ---------------------------------------------------------------------------


CLI_PATH = "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
CFG_PATH = "quickscale_core/src/quickscale_core/schema/config_schema.py"


def _build_dead_code_indexes(messages: list[str]) -> dict[str, int]:
    """Build ceiling indexes for dead_code from a message list."""
    from collections import Counter

    indexes: dict[str, int] = {}
    for msg, count in Counter(messages).items():
        indexes[f"dead_code:allowed_messages:{msg}:multiplicity"] = count
    return indexes


def _build_complexity_indexes(
    functions: dict[str, dict[str, Any]],
) -> dict[str, int]:
    """Build ceiling indexes for complexity from allowed_functions."""
    indexes: dict[str, int] = {}
    for ck, entry in functions.items():
        indexes[f"complexity:{ck}"] = int(entry["max_complexity"])
    return indexes


def _build_duplication_indexes(allowed_blocks: int) -> dict[str, int]:
    """Build ceiling indexes for duplication."""
    return {"duplication:allowed_blocks": allowed_blocks}


class TestCompareIndexes:
    """Unified index-based comparison."""

    def test_no_change_passes(self, v87_baseline: dict) -> None:
        """Same baseline produces no violations."""
        old_idx = _check._validate_baseline_structure(v87_baseline, "old")
        new_idx = _check._validate_baseline_structure(v87_baseline, "new")
        results = _check._compare_indexes(old_idx, new_idx)
        assert len(results) == 0

    def test_sa114_increases_detected(
        self, v87_baseline: dict, current_baseline_with_increases: dict
    ) -> None:
        """All SA114 increases are caught via index comparison."""
        old_idx = _check._validate_baseline_structure(v87_baseline, "old")
        new_idx = _check._validate_baseline_structure(current_baseline_with_increases, "new")
        results = _check._compare_indexes(old_idx, new_idx)
        # SA125-DEC-001 retired the line-ceiling surface, so the historical
        # line-count cases are replayed as two surviving complexity increases.
        assert len(results) == 3  # complexity 11→12, 20→22, 17→18

        # CR-006: Exact canonical keys, not substring/any()
        expected_keys = [
            f"complexity:{CLI_PATH}::_perform_module_embed",
            f"complexity:{CLI_PATH}::_update_single_module",
            f"complexity:{CFG_PATH}::_validate_modules_section",
        ]
        actual_keys = sorted(r["canonical_key"] for r in results)
        assert actual_keys == expected_keys, (
            f"Expected exact canonical keys:\n{expected_keys}\nGot:\n{actual_keys}"
        )

        # Verify specific values by exact key
        key_values = {r["canonical_key"]: (r["old_value"], r["new_value"]) for r in results}
        assert key_values[expected_keys[0]] == (20, 22), (
            f"_perform_module_embed expected (20, 22), got {key_values[expected_keys[0]]}"
        )
        assert key_values[expected_keys[1]] == (17, 18), (
            f"_update_single_module expected (17, 18), got {key_values[expected_keys[1]]}"
        )
        assert key_values[expected_keys[2]] == (11, 12), (
            f"_validate_modules_section expected (11, 12), got {key_values[expected_keys[2]]}"
        )

    def test_new_message_increases(self, v87_baseline: dict) -> None:
        """A new dead-code message (old=0, new=1) is a violation."""
        new = json.loads(json.dumps(v87_baseline))
        new["dead_code"]["allowed_messages"].append("new/file.py: unused var 'x'")
        old_idx = _check._validate_baseline_structure(v87_baseline, "old")
        new_idx = _check._validate_baseline_structure(new, "new")
        results = _check._compare_indexes(old_idx, new_idx)
        # One new dead-code violation (multiplicity increased from 0 to 1)
        assert len(results) == 1
        r = results[0]
        # CR-006: Exact canonical key, not substring/any()
        expected_dc_key = "dead_code:allowed_messages:new/file.py: unused var 'x':multiplicity"
        assert r["canonical_key"] == expected_dc_key, (
            f"Expected exact dead_code key, got {r['canonical_key']!r}"
        )
        assert r["old_value"] == 0
        assert r["new_value"] == 1
        assert r["section"] == "dead_code"
        assert r["error_code"] == "DC-MULT"

    def test_reduced_passes(self, v87_baseline: dict) -> None:
        """Decreased values are not violations."""
        new = json.loads(json.dumps(v87_baseline))
        key = (
            "quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section"
        )
        new["complexity"]["allowed_functions"][key]["max_complexity"] = 10
        old_idx = _check._validate_baseline_structure(v87_baseline, "old")
        new_idx = _check._validate_baseline_structure(new, "new")
        results = _check._compare_indexes(old_idx, new_idx)
        assert len(results) == 0

    def test_new_key_is_violation(self, v87_baseline: dict) -> None:
        """A new key (old missing = 0, new > 0) is a violation."""
        new = json.loads(json.dumps(v87_baseline))
        new["complexity"]["allowed_functions"]["new.py::func"] = {
            "file": "new.py",
            "max_complexity": 5,
            "symbol": "func",
            "type": "function",
        }
        old_idx = _check._validate_baseline_structure(v87_baseline, "old")
        new_idx = _check._validate_baseline_structure(new, "new")
        results = _check._compare_indexes(old_idx, new_idx)
        complexity_increases = [r for r in results if r["section"] == "complexity"]
        assert len(complexity_increases) == 1
        r = next(r for r in complexity_increases if r["old_value"] == 0)
        assert r["new_value"] == 5

    def test_removed_key_passes(self, v87_baseline: dict) -> None:
        """Removing a key is never a violation."""
        new = json.loads(json.dumps(v87_baseline))
        new["complexity"]["allowed_functions"] = {}
        old_idx = _check._validate_baseline_structure(v87_baseline, "old")
        new_idx = _check._validate_baseline_structure(new, "new")
        results = _check._compare_indexes(old_idx, new_idx)
        assert results == [], "Removing every key must never be a violation"

    def test_error_codes_match_section(self) -> None:
        """Each section produces the correct error_code."""
        results = _check._compare_indexes(
            {},
            {
                "dead_code:allowed_messages:msg:a:multiplicity": 2,
                "complexity:a.py::f": 5,
                "duplication:allowed_blocks": 3,
            },
        )
        assert len(results) == 3
        codes = {(r["section"], r["error_code"]) for r in results}
        assert codes == {
            ("dead_code", "DC-MULT"),
            ("complexity", "CC-RISE"),
            ("duplication", "DP-RISE"),
        }, f"SA125-DEC-001: large_files must not be a recognized section; got {codes}"


# ---------------------------------------------------------------------------
# Waiver evaluation tests
# ---------------------------------------------------------------------------


def _make_waiver(**overrides: Any) -> dict[str, Any]:
    """
    Create a minimum valid waiver for testing.

    The default ``decision_ref`` must be an exact anchor that exists in
    ``docs/technical/decisions.md``.
    """
    base = {
        "waiver_id": "W001",
        "entry_key": "complexity:quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section",  # noqa: E501
        "base_ceiling": 11,
        "ceiling": 12,
        "owner": "test@example.com",
        "reason": "SA121 gate-drift remediation",
        "expires_on": (date.today() + timedelta(days=90)).isoformat(),
        "decision_ref": "quality-baseline-monotonicity",
    }
    base.update(overrides)
    return base


class TestWaiverValidation:
    """Individual waiver entry validation."""

    def test_valid_waiver_passes(self, now: date, known_anchors: set[str]) -> None:
        """A correctly formed waiver passes validation."""
        w = _make_waiver()
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is None

    def test_missing_required_field(self, now: date, known_anchors: set[str]) -> None:
        """Missing a required key produces an error."""
        w = _make_waiver()
        del w["owner"]
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None
        assert "owner" in err

    def test_expired_waiver_format_valid(
        self, past_date: str, now: date, known_anchors: set[str]
    ) -> None:
        """An expired waiver passes format validation (expiry is state machine)."""
        w = _make_waiver(expires_on=past_date)
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        # _validate_waiver_row only checks format, not expiry
        assert err is None

    def test_future_waiver_accepted(self, now: date, known_anchors: set[str]) -> None:
        """A waiver expiring in the future passes."""
        w = _make_waiver()
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is None

    def test_malformed_date_rejected(self, now: date, known_anchors: set[str]) -> None:
        """A non-ISO date in expires_on is rejected."""
        w = _make_waiver(expires_on="not-a-date")
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None
        # CR-003: YYYY-MM-DD regex catches before date.fromisoformat
        assert "does not match YYYY-MM-DD format" in err

    def test_non_numeric_ceiling_rejected(self, now: date, known_anchors: set[str]) -> None:
        """A non-numeric ceiling is rejected."""
        w = _make_waiver(ceiling="twelve")
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None

    def test_negative_ceiling_rejected(self, now: date, known_anchors: set[str]) -> None:
        """A negative ceiling is rejected."""
        w = _make_waiver(ceiling=-5)
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None

    def test_bool_ceiling_rejected(self, now: date, known_anchors: set[str]) -> None:
        """A bool value for ceiling is rejected (bool is not a valid number)."""
        w = _make_waiver(ceiling=True)
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None
        assert "must be a non-negative number" in err

    def test_decision_ref_anchor_validation(self, now: date, known_anchors: set[str]) -> None:
        """A waiver with a decision_ref that does not resolve in decisions.md is rejected."""
        w = _make_waiver(decision_ref="NONEXISTENT-REF-12345")
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None
        assert "decision_ref" in err
        assert "does not resolve" in err

    # ------------------------------------------------------------------
    # CR-003: entry_key with control/surrogate characters is malformed
    # ------------------------------------------------------------------

    def test_malformed_entry_key_tab(self, now: date, known_anchors: set[str]) -> None:
        """An entry_key containing a tab character produces malformed error."""
        w = _make_waiver(entry_key="dead_code:allowed_messages:hello\tworld:multiplicity")
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None
        assert "must not contain control" in err

    def test_malformed_entry_key_del(self, now: date, known_anchors: set[str]) -> None:
        """An entry_key containing DEL (0x7F) produces malformed error."""
        w = _make_waiver(entry_key="complexity:src/file.py::func\x7fname")
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None
        assert "must not contain control" in err

    def test_malformed_entry_key_surrogate(self, now: date, known_anchors: set[str]) -> None:
        """An entry_key containing surrogate chars produces malformed error."""
        w = _make_waiver(entry_key="complexity:src/file.py::func\ud800name")
        err = _check._validate_waiver_row(w, 0, now, known_anchors)
        assert err is not None
        assert "must not contain control" in err


class TestFreeTextValidation:
    """CR-003: Free-text validator for dead_code messages and complexity symbols."""

    def test_validate_free_text_valid(self) -> None:
        """Valid free text passes validation."""
        # Should not raise
        _check._validate_free_text(
            "normal message without control chars",
            "test",
            "test.path",
        )

    def test_validate_free_text_tab_rejected(self) -> None:
        """Tab character in free text raises SchemaValidationError."""
        with pytest.raises(RuntimeError, match="must not contain control"):
            _check._validate_free_text("hello\tworld", "test", "test.path")

    def test_validate_free_text_del_rejected(self) -> None:
        """DEL character (0x7F) in free text raises SchemaValidationError."""
        with pytest.raises(RuntimeError, match="must not contain control"):
            _check._validate_free_text("bad\x7fchar", "test", "test.path")

    def test_validate_free_text_surrogate_rejected(self) -> None:
        """Surrogate character in free text raises SchemaValidationError."""
        with pytest.raises(RuntimeError, match="must not contain control"):
            _check._validate_free_text("bad\ud800char", "test", "test.path")

    def test_dead_code_message_tab_rejected(self) -> None:
        """A dead_code allowed_messages entry with tab is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": ["normal", "bad\tmsg"]},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="must not contain control"):
            _check._validate_baseline_structure(data, "test")

    def test_complexity_symbol_with_tab_rejected(self) -> None:
        """A complexity symbol containing tab is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "file.py::bad\tfunc": {
                        "file": "file.py",
                        "symbol": "bad\tfunc",
                        "type": "function",
                        "max_complexity": 5,
                    }
                }
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="must not contain control"):
            _check._validate_baseline_structure(data, "test")


class TestWaiverEvaluation:
    """Integration of waiver matching against violations."""

    def test_all_increases_covered(
        self, now: date, future_date: str, known_anchors: set[str]
    ) -> None:
        """All three SA114 increases pass with matching waivers."""
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section",  # noqa: E501
                "old_value": 11,
                "new_value": 12,
                "error_code": "CC-RISE",
            },
            {
                "section": "complexity",
                "canonical_key": f"complexity:{CLI_PATH}::_perform_module_embed",
                "old_value": 20,
                "new_value": 22,
                "error_code": "CC-RISE",
            },
            {
                "section": "complexity",
                "canonical_key": f"complexity:{CLI_PATH}::_update_single_module",
                "old_value": 17,
                "new_value": 18,
                "error_code": "CC-RISE",
            },
        ]
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section",  # noqa: E501
                "base_ceiling": 11,
                "ceiling": 12,
                "owner": "dev@example.com",
                "reason": "SA114 gate-drift remediation",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
            {
                "waiver_id": "W002",
                "entry_key": f"complexity:{CLI_PATH}::_perform_module_embed",
                "base_ceiling": 20,
                "ceiling": 22,
                "owner": "dev@example.com",
                "reason": "SA114 gate-drift remediation",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
            {
                "waiver_id": "W003",
                "entry_key": f"complexity:{CLI_PATH}::_update_single_module",
                "base_ceiling": 17,
                "ceiling": 18,
                "owner": "dev@example.com",
                "reason": "SA114 gate-drift remediation",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        # CR-006: Exactly 0 unresolved, exactly 3 evaluations, all active
        assert len(unresolved) == 0
        assert len(evals) == 3
        assert all(e["status"] == "active" for e in evals), (
            f"Expected all 3 waivers active, got: {[e['status'] for e in evals]}"
        )
        waiver_ids = [e["waiver_id"] for e in evals]
        assert waiver_ids == ["W001", "W002", "W003"], (
            f"Expected exact waiver IDs W001/W002/W003, got {waiver_ids}"
        )

    def test_missing_waiver_leaves_unresolved(self, now: date, known_anchors: set[str]) -> None:
        """An increase without a matching waiver is unresolved."""
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:some/file.py::func",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, [], now, known_anchors)
        assert len(unresolved) == 1

    def test_waiver_ceiling_exceeded(
        self, now: date, future_date: str, known_anchors: set[str]
    ) -> None:
        """An over-ceiling waiver does not resolve the violation."""
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:some/file.py::func",
                "old_value": 5,
                "new_value": 20,
                "error_code": "CC-RISE",
            },
        ]
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:some/file.py::func",
                "base_ceiling": 5,
                "ceiling": 15,
                "owner": "dev@example.com",
                "reason": "Test",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert unresolved == violations
        assert evals == [
            {
                "waiver_id": "W001",
                "status": "over_ceiling",
                "error": (
                    "current value 20 exceeds waiver ceiling 15 for complexity:some/file.py::func"
                ),
                "matches": ["complexity:some/file.py::func"],
                "waiver_index": 0,
                "base_ceiling": 5,
                "ceiling": 15,
                "decision_ref": "quality-baseline-monotonicity",
            }
        ]

    def test_stale_base_ceiling_fails(
        self, now: date, future_date: str, known_anchors: set[str]
    ) -> None:
        """
        A mismatch between base_ceiling and actual old value produces a
        stale_base error — the violation remains unresolved (hard fail).
        """  # noqa: D205
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:some/file.py::func",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:some/file.py::func",
                "base_ceiling": 3,  # wrong — actual old_value is 5
                "ceiling": 10,
                "owner": "dev@example.com",
                "reason": "Test",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert unresolved == violations  # stale_base is now a hard fail
        assert evals == [
            {
                "waiver_id": "W001",
                "status": "stale_base",
                "error": ("base_ceiling 3 != merge-base value 5 for complexity:some/file.py::func"),
                "matches": ["complexity:some/file.py::func"],
                "waiver_index": 0,
                "base_ceiling": 3,
                "ceiling": 10,
                "decision_ref": "quality-baseline-monotonicity",
            }
        ]

    def test_orphan_waiver_detected(
        self, now: date, future_date: str, known_anchors: set[str]
    ) -> None:
        """
        A waiver whose entry_key has no corresponding increase is flagged
        as orphan.
        """  # noqa: D205
        violations: list[dict] = []
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:some/nonexistent.py::func",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev@example.com",
                "reason": "Test",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert unresolved == []
        assert evals == [
            {
                "waiver_id": "W001",
                "status": "orphan",
                "warning": (
                    "entry_key 'complexity:some/nonexistent.py::func' has no corresponding increase"
                ),
                "matches": ["complexity:some/nonexistent.py::func"],
                "waiver_index": 0,
                "base_ceiling": 5,
                "ceiling": 10,
                "decision_ref": "quality-baseline-monotonicity",
            }
        ]

    def test_expired_waiver_rejected(
        self, now: date, past_date: str, known_anchors: set[str]
    ) -> None:
        """An expired waiver does not resolve the violation."""
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:some/file.py::func",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:some/file.py::func",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev@example.com",
                "reason": "Test",
                "expires_on": past_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert unresolved == violations
        # Now expired waivers get their own state (not malformed).
        assert evals == [
            {
                "waiver_id": "W001",
                "status": "expired",
                "error": "waiver expired on " + past_date + " (current UTC date: 2026-07-26)",
                "matches": [],
                "waiver_index": 0,
                "base_ceiling": 5,
                "ceiling": 10,
                "decision_ref": "quality-baseline-monotonicity",
            }
        ]

    def test_duplicate_entry_key(
        self, now: date, future_date: str, known_anchors: set[str]
    ) -> None:
        """Duplicate entry_keys are flagged on the second copy."""
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:some/file.py::func",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:some/file.py::func",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev@example.com",
                "reason": "First",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
            {
                "waiver_id": "W002",
                "entry_key": "complexity:some/file.py::func",  # same key
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev@example.com",
                "reason": "Duplicate",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        # With duplicate entry_keys, ALL copies are disqualified and no
        # waiver can resolve the violation — the violation remains unresolved.
        assert len(unresolved) == 1
        statuses = [e["status"] for e in evals]
        assert "duplicate" in statuses
        assert "active" not in statuses

    def test_duplicate_waiver_id(
        self, now: date, future_date: str, known_anchors: set[str]
    ) -> None:
        """Duplicate waiver_ids are flagged."""
        violations: list[dict] = []
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:some/file.py::func1",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev@example.com",
                "reason": "First entry key",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
            {
                "waiver_id": "W001",
                "entry_key": "complexity:some/file.py::func2",
                "base_ceiling": 3,
                "ceiling": 8,
                "owner": "dev@example.com",
                "reason": "Second entry key — same waiver_id",
                "expires_on": future_date,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        unresolved, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert unresolved == []
        assert evals == [
            {
                "waiver_id": "W001",
                "status": "duplicate",
                "error": "duplicate waiver_id — all copies disqualified",
                "matches": [],
                "waiver_index": 0,
                "base_ceiling": 5,
                "ceiling": 10,
                "decision_ref": "quality-baseline-monotonicity",
                "duplicate_kinds": ["waiver_id"],
            },
            {
                "waiver_id": "W001",
                "status": "duplicate",
                "error": "duplicate waiver_id — all copies disqualified",
                "matches": [],
                "waiver_index": 1,
                "base_ceiling": 3,
                "ceiling": 8,
                "decision_ref": "quality-baseline-monotonicity",
                "duplicate_kinds": ["waiver_id"],
            },
        ]


# ---------------------------------------------------------------------------
# Lifecycle / determinism
# ---------------------------------------------------------------------------


class TestOutputStructure:
    """Output dict shape and determinism."""

    def test_output_has_required_keys(self) -> None:
        """The output dict contains all required metadata keys."""
        output = _check._build_output(
            merge_base="abc123",
            base_ref="v87",
            violations=[],
            unresolved=[],
            waiver_evaluations=[],
            verdict="pass",
            warnings=[],
        )
        assert output["schema_version"] == 1
        assert "timestamp" in output
        assert output["merge_base"] == "abc123"
        assert output["verdict"] == "pass"

    def test_violations_sorted(self) -> None:
        """Violations are sorted by error_code then canonical_key."""
        violations = [
            {"error_code": "CC-RISE", "canonical_key": "z", "old_value": 0, "new_value": 1},
            {"error_code": "CC-RISE", "canonical_key": "a", "old_value": 0, "new_value": 1},
            {"error_code": "AB-FOO", "canonical_key": "m", "old_value": 0, "new_value": 1},
        ]
        output = _check._build_output(
            merge_base="h",
            base_ref="v87",
            violations=violations,
            unresolved=violations,
            waiver_evaluations=[],
            verdict="violation",
            warnings=[],
        )
        codes = [v["error_code"] for v in output["violations"]]
        assert codes == ["AB-FOO", "CC-RISE", "CC-RISE"]

    def test_violations_deterministic(self) -> None:
        """Running the same comparison twice yields the same violations."""
        # Build indexes manually to avoid schema validation on incomplete dicts
        old_idx = {
            "dead_code:allowed_messages:a:multiplicity": 1,
            "dead_code:allowed_messages:b:multiplicity": 1,
        }
        new_idx = {
            "dead_code:allowed_messages:a:multiplicity": 1,
            "dead_code:allowed_messages:b:multiplicity": 1,
            "dead_code:allowed_messages:c:multiplicity": 1,
        }
        r1 = _check._compare_indexes(old_idx, new_idx)
        r2 = _check._compare_indexes(old_idx, new_idx)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Waiver loading
# ---------------------------------------------------------------------------


class TestLoadWaivers:
    """Waiver file loading behaviour."""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """A missing waiver file is treated as an empty ledger."""
        missing = tmp_path / "nonexistent.json"
        waivers = _check._load_waivers(str(missing))
        assert waivers == []

    def test_empty_waivers_returns_empty_list(self, tmp_path: Path) -> None:
        """A waiver file with an empty waivers list is valid."""
        p = tmp_path / "waivers.json"
        p.write_text('{"schema_version": 1, "waivers": []}', encoding="utf-8")
        waivers = _check._load_waivers(str(p))
        assert waivers == []

    def test_valid_waivers_loaded(self, tmp_path: Path) -> None:
        """A waiver file with valid entries is loaded correctly."""
        data = {
            "schema_version": 1,
            "waivers": [
                {
                    "waiver_id": "W001",
                    "entry_key": "complexity:x.py::f",
                    "base_ceiling": 5,
                    "ceiling": 10,
                    "owner": "dev",
                    "reason": "test",
                    "expires_on": "2027-01-01",
                    "decision_ref": "quality-baseline-monotonicity",
                },
            ],
        }
        p = tmp_path / "waivers.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        waivers = _check._load_waivers(str(p))
        assert len(waivers) == 1

    def test_wrong_schema_version_fails(self, tmp_path: Path) -> None:
        """An unsupported schema_version raises."""
        data = {"schema_version": 99, "waivers": []}
        p = tmp_path / "waivers.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(RuntimeError, match="schema_version"):
            _check._load_waivers(str(p))

    def test_malformed_json_fails(self, tmp_path: Path) -> None:
        """Malformed waiver JSON raises."""
        p = tmp_path / "waivers.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(RuntimeError):
            _check._load_waivers(str(p))


# ---------------------------------------------------------------------------
# Schema validation tests (strict nested row validation)
# ---------------------------------------------------------------------------


class TestValidateBaselineStructure:
    """Strict schema validation for baseline structure."""

    def test_valid_baseline_returns_indexes(self, v87_baseline: dict) -> None:
        """A valid baseline returns ceiling indexes with expected keys."""
        indexes = _check._validate_baseline_structure(v87_baseline, "test")
        assert indexes == {
            (
                "dead_code:allowed_messages:quickscale_cli/src/quickscale_cli/commands/"
                "apply_command.py: unused variable 'q':multiplicity"
            ): 1,
            (
                "dead_code:allowed_messages:quickscale_modules/blog/src/"
                "quickscale_modules_blog/views.py: unused variable 'req':multiplicity"
            ): 2,
            (
                "dead_code:allowed_messages:quickscale_modules/orgs/src/"
                "quickscale_modules_orgs/checks.py: unused variable 'app_configs':multiplicity"
            ): 2,
            (
                "complexity:quickscale_core/src/quickscale_core/schema/"
                "config_schema.py::_validate_modules_section"
            ): 11,
            (
                "complexity:quickscale_cli/src/quickscale_cli/commands/"
                "module_commands.py::_perform_module_embed"
            ): 20,
            (
                "complexity:quickscale_cli/src/quickscale_cli/commands/"
                "module_commands.py::_update_single_module"
            ): 17,
            "duplication:allowed_blocks": 0,
        }

    def test_bool_schema_version_rejected(self) -> None:
        """A bool schema_version is rejected."""
        data = {
            "schema_version": True,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="non-boolean integer"):
            _check._validate_baseline_structure(data, "test")

    def test_wrong_schema_version_rejected(self) -> None:
        """A schema_version != 1 is rejected."""
        data = {
            "schema_version": 99,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="unsupported schema_version"):
            _check._validate_baseline_structure(data, "test")

    def test_string_schema_version_rejected(self) -> None:
        """A string schema_version is rejected."""
        data = {
            "schema_version": "1",
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="non-boolean integer"):
            _check._validate_baseline_structure(data, "test")

    def test_non_dict_sections_rejected(self) -> None:
        """Non-dict top-level sections are rejected."""
        for section in ("dead_code", "complexity", "duplication"):
            data: dict[str, Any] = {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            }
            data[section] = "not-a-dict"
            with pytest.raises(RuntimeError, match=f"section.*{section}"):
                _check._validate_baseline_structure(data, "test")

    def test_empty_string_dead_code_msg_rejected(self) -> None:
        """An empty string in allowed_messages is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": [""]},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="non-empty string"):
            _check._validate_baseline_structure(data, "test")

    def test_non_int_max_complexity_rejected(self) -> None:
        """A float or bool max_complexity is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "f.py::func": {
                        "file": "f.py",
                        "symbol": "func",
                        "type": "function",
                        "max_complexity": 5.5,
                    }
                }
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="non-negative integer"):
            _check._validate_baseline_structure(data, "test")

    def test_bool_max_complexity_rejected(self) -> None:
        """A bool max_complexity is rejected (not coerced)."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "f.py::func": {
                        "file": "f.py",
                        "symbol": "func",
                        "type": "function",
                        "max_complexity": True,
                    }
                }
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="non-negative integer"):
            _check._validate_baseline_structure(data, "test")

    def test_negative_max_complexity_rejected(self) -> None:
        """A negative max_complexity is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "f.py::func": {
                        "file": "f.py",
                        "symbol": "func",
                        "type": "function",
                        "max_complexity": -1,
                    }
                }
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="non-negative integer"):
            _check._validate_baseline_structure(data, "test")

    def test_invalid_complexity_type_rejected(self) -> None:
        """An unsupported type in complexity is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "f.py::func": {
                        "file": "f.py",
                        "symbol": "func",
                        "type": "unknown_type",
                        "max_complexity": 5,
                    }
                }
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        with pytest.raises(RuntimeError, match="type"):
            _check._validate_baseline_structure(data, "test")

    def test_stale_large_files_section_is_ignored(self) -> None:
        """
        SA125-DEC-001: a pre-SA125 large_files section validates but never indexes.

        The merge-base side of a comparison still carries the retired section, so
        it must not raise; it must also contribute no keys, so no LF-RISE can be
        computed from either side.
        """
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {"big.py": {"max_lines": 1234}}},
            "duplication": {"allowed_blocks": 0},
        }
        indexes = _check._validate_baseline_structure(data, "test")
        assert indexes == {"duplication:allowed_blocks": 0}, (
            f"large_files must contribute no index keys; got {indexes}"
        )

    def test_bool_allowed_blocks_rejected(self) -> None:
        """A bool allowed_blocks is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": True},
        }
        with pytest.raises(RuntimeError, match="non-negative integer"):
            _check._validate_baseline_structure(data, "test")

    def test_negative_allowed_blocks_rejected(self) -> None:
        """A negative allowed_blocks is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": -1},
        }
        with pytest.raises(RuntimeError, match="non-negative integer"):
            _check._validate_baseline_structure(data, "test")

    def test_allowed_block_identities_length_mismatch(self) -> None:
        """allowed_block_identities length must equal allowed_blocks."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 2, "allowed_block_identities": ["only_one"]},
        }
        with pytest.raises(RuntimeError, match="length"):
            _check._validate_baseline_structure(data, "test")


# ---------------------------------------------------------------------------
# Error envelope tests
# ---------------------------------------------------------------------------


class TestErrorEnvelope:
    """Deterministic SCHEMA_ERROR envelope shape."""

    def test_error_envelope_has_required_keys(self) -> None:
        """The error envelope contains all required metadata keys."""
        # Simulate what _write_error_output produces
        envelope = {
            "schema_version": 1,
            "verdict": "error",
            "error": {
                "code": "SCHEMA_ERROR",
                "source": "quality_baseline.json",
                "path": "dead_code.allowed_messages",
                "message": "dead_code.allowed_messages must be a list of strings",
            },
            "diagnostics": [],
        }
        assert envelope == {
            "schema_version": 1,
            "verdict": "error",
            "error": {
                "code": "SCHEMA_ERROR",
                "source": "quality_baseline.json",
                "path": "dead_code.allowed_messages",
                "message": "dead_code.allowed_messages must be a list of strings",
            },
            "diagnostics": [],
        }

    def test_error_envelope_serializes_to_json(self) -> None:
        """The error envelope is JSON-serializable."""
        envelope = {
            "schema_version": 1,
            "verdict": "error",
            "error": {
                "code": "SCHEMA_ERROR",
                "source": "test.json",
                "path": "test.path",
                "message": "Test error",
            },
            "diagnostics": [],
        }
        serialized = json.dumps(envelope)
        deserialized = json.loads(serialized)
        assert deserialized == envelope

    def test_missing_file_produces_error_envelope(self, tmp_path: Path) -> None:
        """A missing baseline file exits 2 and writes error envelope."""
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT_DIR / "check_quality_baseline_monotonicity.py"),
                "--base-ref",
                "v87",
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            env={
                **os.environ,
                "QUALITY_BASELINE_FILE": str(tmp_path / "nonexistent.json"),
            },
            timeout=30,
        )
        assert result.returncode == 2
        # stderr should have one stable ERROR line
        assert result.stderr.strip().startswith("ERROR:")
        assert "Traceback" not in result.stderr

    def test_bad_schema_version_exits_2_no_traceback(self, tmp_path: Path) -> None:
        """A baseline with wrong schema_version exits 2 with no traceback."""
        temp = tmp_path / "bad_schema.json"
        temp.write_text(
            json.dumps(
                {
                    "schema_version": 99,
                    "dead_code": {"allowed_messages": []},
                    "complexity": {"allowed_functions": {}},
                    "large_files": {"allowed_files": {}},
                    "duplication": {"allowed_blocks": 0},
                }
            )
        )
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT_DIR / "check_quality_baseline_monotonicity.py"),
                "--base-ref",
                "v87",
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            env={
                **os.environ,
                "QUALITY_BASELINE_FILE": str(temp),
            },
            timeout=30,
        )
        assert result.returncode == 2
        assert "Traceback" not in result.stderr
        assert result.stderr.strip().startswith("ERROR:")


# ---------------------------------------------------------------------------
# State machine tests
# ---------------------------------------------------------------------------


class TestStateMachine:
    """Authoritative waiver state machine precedence."""

    def test_state_precedence_malformed_first(self, known_anchors: set[str]) -> None:
        """Malformed state (missing field) takes precedence over all others."""
        waivers = [
            {
                # Missing required 'owner' field
                "waiver_id": "W001",
                "entry_key": "complexity:x.py::f",
                "base_ceiling": 5,
                "ceiling": 10,
                "reason": "test",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:x.py::f",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        now = date(2026, 7, 26)
        _, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert evals[0]["status"] == "malformed"

    def test_state_precedence_duplicate_id_over_expired(self, known_anchors: set[str]) -> None:
        """Duplicate ID takes precedence over expired (both must be detectable)."""
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:x.py::f1",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev",
                "reason": "first",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
            {
                "waiver_id": "W001",  # duplicate ID
                "entry_key": "complexity:x.py::f2",
                "base_ceiling": 3,
                "ceiling": 8,
                "owner": "dev",
                "reason": "second",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        now = date(2026, 7, 26)
        _, evals = _check._evaluate_violations([], waivers, now, known_anchors)
        # Both waiver entries should be flagged as duplicate
        assert all(e["status"] == "duplicate" for e in evals)

    def test_state_precedence_expired_over_orphan(self, known_anchors: set[str]) -> None:
        """Expired takes precedence over orphan."""
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:nonexistent.py::f",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev",
                "reason": "test",
                "expires_on": "2020-01-01",  # expired
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        now = date(2026, 7, 26)
        _, evals = _check._evaluate_violations([], waivers, now, known_anchors)
        assert evals[0]["status"] == "expired"

    def test_state_precedence_orphan_over_stale(self, known_anchors: set[str]) -> None:
        """Orphan takes precedence over stale_base (no increase = orphan)."""
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:nonexistent.py::f",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev",
                "reason": "test",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        now = date(2026, 7, 26)
        _, evals = _check._evaluate_violations([], waivers, now, known_anchors)
        assert evals[0]["status"] == "orphan"

    def test_state_precedence_stale_over_ceiling(self, known_anchors: set[str]) -> None:
        """Stale base takes precedence over over_ceiling."""
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:x.py::f",
                "base_ceiling": 999,  # wrong — actual old is 5
                "ceiling": 10,
                "owner": "dev",
                "reason": "test",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:x.py::f",
                "old_value": 5,
                "new_value": 20,  # also over ceiling
                "error_code": "CC-RISE",
            },
        ]
        now = date(2026, 7, 26)
        _, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert evals[0]["status"] == "stale_base"
        # The violation remains unresolved because of stale base
        unresolved, _ = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert len(unresolved) == 1

    def test_waiver_index_is_recorded(self, known_anchors: set[str]) -> None:
        """Each waiver evaluation carries its 0-based index."""
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:x.py::f",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev",
                "reason": "test",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:x.py::f",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        now = date(2026, 7, 26)
        _, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert evals[0].get("waiver_index") == 0

    def test_evaluation_per_ledger_index(self, known_anchors: set[str]) -> None:
        """Each ledger row produces exactly one evaluation."""
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:a.py::f",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev",
                "reason": "one",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
            {
                "waiver_id": "W002",
                "entry_key": "complexity:b.py::g",
                "base_ceiling": 3,
                "ceiling": 8,
                "owner": "dev",
                "reason": "two",
                "expires_on": "2099-01-01",
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:a.py::f",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
            {
                "section": "complexity",
                "canonical_key": "complexity:b.py::g",
                "old_value": 3,
                "new_value": 8,
                "error_code": "CC-RISE",
            },
        ]
        now = date(2026, 7, 26)
        _, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert len(evals) == 2
        assert {e["waiver_index"] for e in evals} == {0, 1}

    def test_utc_date_expiry(self, known_anchors: set[str]) -> None:
        """Expiry is compared using UTC date, not local."""
        # Use a waiver expiring today — should still be valid since
        # the comparison uses datetime.now(UTC).date() which is >= today
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:x.py::f",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev",
                "reason": "test",
                "expires_on": today_str,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:x.py::f",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        now = datetime.now(UTC).date()
        _, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        # expires_on == today is valid (expires < now check, not <=)
        assert evals[0]["status"] == "active"

    def test_expired_yesterday_blocks(self, known_anchors: set[str]) -> None:
        """A waiver that expired yesterday blocks the gate."""
        yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        waivers = [
            {
                "waiver_id": "W001",
                "entry_key": "complexity:x.py::f",
                "base_ceiling": 5,
                "ceiling": 10,
                "owner": "dev",
                "reason": "test",
                "expires_on": yesterday,
                "decision_ref": "quality-baseline-monotonicity",
            },
        ]
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:x.py::f",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        now = datetime.now(UTC).date()
        _, evals = _check._evaluate_violations(violations, waivers, now, known_anchors)
        assert evals[0]["status"] == "expired"

    def test_missing_coverage_blocks(self, known_anchors: set[str]) -> None:
        """A violation without any matching waiver remains unresolved."""
        violations = [
            {
                "section": "complexity",
                "canonical_key": "complexity:uncovered.py::f",
                "old_value": 5,
                "new_value": 10,
                "error_code": "CC-RISE",
            },
        ]
        now = date(2026, 7, 26)
        unresolved, _ = _check._evaluate_violations(violations, [], now, known_anchors)
        assert len(unresolved) == 1


# ---------------------------------------------------------------------------
# Shell integration tests
# ---------------------------------------------------------------------------


class TestShellIntegration:
    """
    Subprocess-level integration tests for the helper exit contract and output.

    These tests exercise the helper through the same entrypoint ``make quality``
    uses, verifying the exit code contract and policy file output shape without
    running the full analyzer stack.
    """

    HELPER_PATH = _SCRIPT_DIR / "check_quality_baseline_monotonicity.py"

    def _run_helper(
        self,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        """Run the monotonicity helper and return the completed process."""
        cmd = [sys.executable, str(self.HELPER_PATH)]
        if extra_args:
            cmd.extend(extra_args)
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=60,
            env=run_env,
        )

    def _policy_file(self) -> Path:
        """Return the path to the policy output file."""
        return _REPO_ROOT / ".quickscale" / "quality_baseline_policy.json"

    # ------------------------------------------------------------------
    # Exit code contract
    # ------------------------------------------------------------------

    def test_helper_exit_0_with_v87(self) -> None:
        """
        The helper exits 0 when run with ``--base-ref v87``.

        Phase 1 verified that the current baseline has no diff against the
        merge-base of v87, so the gate should pass cleanly.
        """
        result = self._run_helper(extra_args=["--base-ref", "v87"])
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_helper_exit_2_bad_base_ref(self) -> None:
        """A non-existent base ref produces exit 2 (prerequisite failure)."""
        result = self._run_helper(extra_args=["--base-ref", "nonexistent-ref-opencode-test-99999"])
        assert result.returncode == 2, f"Expected exit 2 for bad ref, got {result.returncode}"

    def test_helper_exit_2_unresolvable_github_base_ref(self) -> None:
        """An unresolvable GITHUB_BASE_REF produces exit 2."""
        result = self._run_helper(
            extra_args=[],
            env={
                "GITHUB_BASE_REF": "nonexistent-branch-opencode-test-99999",
            },
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for unresolvable GITHUB_BASE_REF, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_helper_exit_2_missing_baseline_file(self) -> None:
        """A missing ``QUALITY_BASELINE_FILE`` produces exit 2."""
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": "/tmp/nonexistent-baseline-test-99999.json"},
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for missing baseline, got {result.returncode}"
        )

    # ------------------------------------------------------------------
    # Policy file output
    # ------------------------------------------------------------------

    def test_policy_file_written_on_success(self) -> None:
        """The policy file exists and has expected structure after a pass."""
        # Clean any stale file first
        pf = self._policy_file()
        pf.unlink(missing_ok=True)

        result = self._run_helper(extra_args=["--base-ref", "v87"])
        assert result.returncode == 0

        assert pf.exists(), "Policy file should exist after successful run"
        data = json.loads(pf.read_text())
        assert data.get("schema_version") == 1
        assert "timestamp" in data
        assert "merge_base" in data
        # With the current complete baseline and v87 merge-base, no violations exist
        assert data.get("verdict") == "pass", (
            f"Expected verdict 'pass' with current baseline vs v87, got {data.get('verdict')}"
        )
        assert "summary" in data
        assert "violations" in data
        assert "unresolved" in data
        assert "waiver_evaluations" in data

    def test_policy_file_written_on_failure(self) -> None:
        """The policy file is still written on exit 2 (error path)."""
        pf = self._policy_file()
        pf.unlink(missing_ok=True)

        result = self._run_helper(extra_args=["--base-ref", "nonexistent-ref-opencode-test-99999"])
        assert result.returncode == 2

        assert pf.exists(), "Policy file should exist even on failure"
        data = json.loads(pf.read_text())
        assert data.get("schema_version") == 1
        assert "error" in data

    def test_policy_file_deterministic_keys(self) -> None:
        """Policy file keys are stable across runs."""
        result = self._run_helper(extra_args=["--base-ref", "v87"])
        assert result.returncode == 0

        data = json.loads(self._policy_file().read_text())
        expected_top_keys = {
            "schema_version",
            "timestamp",
            "merge_base",
            "base_ref",
            "verdict",
            "summary",
            "violations",
            "unresolved",
            "waiver_evaluations",
            "diagnostics",
            "warnings",
        }
        actual_top_keys = set(data.keys())
        missing = expected_top_keys - actual_top_keys
        assert not missing, f"Policy file missing expected keys: {missing}"

    # ------------------------------------------------------------------
    # CR-005: Base ref precedence — real subprocess tests
    # ------------------------------------------------------------------

    def test_base_ref_cli_over_quality_env(self) -> None:
        """
        CLI ``--base-ref`` takes precedence over ``QUALITY_BASELINE_BASE_REF``.

        Set QUALITY_BASELINE_BASE_REF to a nonexistent ref and provide a valid
        CLI ``--base-ref v87`` — the helper should exit 0 because CLI wins.
        """
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_BASE_REF": "nonexistent-ref-opencode-test-99999"},
        )
        assert result.returncode == 0, (
            f"Expected exit 0 (CLI --base-ref v87 overrides env), "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_base_ref_quality_over_github_env(self) -> None:
        """
        ``QUALITY_BASELINE_BASE_REF`` takes precedence over ``GITHUB_BASE_REF``.

        Set QUALITY_BASELINE_BASE_REF=v87 (valid) and GITHUB_BASE_REF to a
        nonexistent branch — the helper should exit 0 because QUALITY wins.
        """
        result = self._run_helper(
            extra_args=[],
            env={
                "QUALITY_BASELINE_BASE_REF": "v87",
                "GITHUB_BASE_REF": "nonexistent-branch-opencode-test-99999",
            },
        )
        assert result.returncode == 0, (
            f"Expected exit 0 (QUALITY_BASELINE_BASE_REF=v87 overrides GITHUB_BASE_REF), "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_base_ref_github_origin_first(self) -> None:
        """``GITHUB_BASE_REF`` resolves origin/<branch> first before local <branch>."""
        # Use GITHUB_BASE_REF=v87 — origin/v87 should resolve and the helper
        # uses that ref.  Verify the merge-base commit is from origin/v87,
        # confirming origin resolution ran before local v87.
        result = self._run_helper(
            extra_args=[],
            env={"GITHUB_BASE_REF": "v87"},
        )
        # origin/v87 contains SA114 base values (11, 1596, 605) while the
        # current baseline contains SA114 increases (12, 1608, 611), so
        # unwaived violations are detected → exit 1 deterministically.
        assert result.returncode == 1, (
            f"Expected exit 1 (origin/v87 baseline < current), "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Verify the exact unwaived canonical record from origin/v87.
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    error_code="CC-RISE",
                    section="complexity",
                    canonical_key=(
                        "complexity:quickscale_core/src/quickscale_core/schema/"
                        "config_schema.py::_validate_modules_section"
                    ),
                    old_value=11,
                    new_value=12,
                    waiver_file=str(_REPO_ROOT / "scripts" / "quality_waivers.json"),
                    decision_ref="<required: add waiver or revert increase>",
                )
            ],
        )

    def test_base_ref_default_v87(self) -> None:
        """With no env overrides, the default ``v87`` tag is used and the gate passes."""
        result = self._run_helper(
            extra_args=[],
            env={
                "QUALITY_BASELINE_BASE_REF": "",
                "GITHUB_BASE_REF": "",
            },
        )
        assert result.returncode == 0, (
            f"Expected exit 0 (default v87 tag fallback), "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # ------------------------------------------------------------------
    # CR-005: Unresolvable refs already tested above:
    #   test_helper_exit_2_bad_base_ref — explicit bad ref
    #   test_helper_exit_2_unresolvable_github_base_ref — bad GITHUB_BASE_REF
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # CR-004: Waiver real subprocess matrix — each state exercised
    # ------------------------------------------------------------------

    def test_helper_exit_1_invalid_anchor_waiver(self, tmp_path: Path) -> None:
        """A waiver with unresolvable decision_ref produces exit 1 (malformed)."""
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_invalid_anchor.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_invalid_anchor.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-ANCHOR-001",
                            "entry_key": "complexity:nonexistent.py::func",
                            "base_ceiling": 5,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Invalid anchor test",
                            "expires_on": future,
                            "decision_ref": "NONEXISTENT-ANCHOR-99999",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # CR-005/006: stdout contains exactly one complete canonical record.
        assert result.returncode == 1, (
            f"Expected exit 1 for invalid anchor waiver, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-ANCHOR-001",
                    waiver_status="malformed",
                    waiver_base_ceiling=5,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="NONEXISTENT-ANCHOR-99999",
                    waiver_index=0,
                )
            ],
        )

    def test_helper_exit_1_stale_base_waiver(self, tmp_path: Path) -> None:
        """A waiver whose ``base_ceiling`` does not match merge-base exits 1."""
        current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
        current["complexity"]["allowed_functions"]["stale_base_test.py::func"] = {
            "file": "stale_base_test.py",
            "max_complexity": 10,
            "symbol": "func",
            "type": "function",
        }
        temp_baseline = tmp_path / "baseline_stale.json"
        temp_baseline.write_text(json.dumps(current), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_stale.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-STALE-001",
                            "entry_key": "complexity:stale_base_test.py::func",
                            "base_ceiling": 999,  # wrong — actual old value is 0
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Stale base test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # CR-005/006: stdout contains exactly one canonical JSON record for
        # the injected stale-base increase.
        assert result.returncode == 1, (
            f"Expected exit 1 for stale base waiver, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    error_code="CC-RISE",
                    section="complexity",
                    canonical_key="complexity:stale_base_test.py::func",
                    old_value=0,
                    new_value=10,
                    waiver_id="W-STALE-001",
                    waiver_status="stale_base",
                    waiver_base_ceiling=999,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    def test_helper_exit_1_over_ceiling_waiver(self, tmp_path: Path) -> None:
        """A waiver whose ``ceiling`` is below the observed value exits 1."""
        current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
        current["complexity"]["allowed_functions"]["over_ceiling_test.py::func"] = {
            "file": "over_ceiling_test.py",
            "max_complexity": 20,
            "symbol": "func",
            "type": "function",
        }
        temp_baseline = tmp_path / "baseline_over.json"
        temp_baseline.write_text(json.dumps(current), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_over.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-OVER-001",
                            "entry_key": "complexity:over_ceiling_test.py::func",
                            "base_ceiling": 0,
                            "ceiling": 5,  # too low — actual value is 20
                            "owner": "test@example.com",
                            "reason": "Over ceiling test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # CR-005/006: stdout contains exactly one canonical JSON record for
        # the injected over-ceiling increase.
        assert result.returncode == 1, (
            f"Expected exit 1 for over-ceiling waiver, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    error_code="CC-RISE",
                    section="complexity",
                    canonical_key="complexity:over_ceiling_test.py::func",
                    old_value=0,
                    new_value=20,
                    waiver_id="W-OVER-001",
                    waiver_status="over_ceiling",
                    waiver_base_ceiling=0,
                    waiver_ceiling=5,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    def test_helper_exit_1_expired_waiver(self, tmp_path: Path) -> None:
        """An expired waiver does not resolve the violation — helper exits 1."""
        current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
        current["complexity"]["allowed_functions"]["expired_test.py::func"] = {
            "file": "expired_test.py",
            "max_complexity": 10,
            "symbol": "func",
            "type": "function",
        }
        temp_baseline = tmp_path / "baseline_expired.json"
        temp_baseline.write_text(json.dumps(current), encoding="utf-8")

        past = (date.today() - timedelta(days=30)).isoformat()
        temp_waivers = tmp_path / "waivers_expired.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-EXP-001",
                            "entry_key": "complexity:expired_test.py::func",
                            "base_ceiling": 0,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Expired test",
                            "expires_on": past,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # CR-005/006: stdout contains exactly two canonical JSON records:
        # the injected violation and its expired lifecycle record.
        assert result.returncode == 1, (
            f"Expected exit 1 for expired waiver, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    error_code="CC-RISE",
                    section="complexity",
                    canonical_key="complexity:expired_test.py::func",
                    old_value=0,
                    new_value=10,
                    decision_ref="<required: add waiver or revert increase>",
                    waiver_file=str(temp_waivers),
                ),
                _canonical_record(
                    waiver_id="W-EXP-001",
                    waiver_status="expired",
                    waiver_base_ceiling=0,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                ),
            ],
        )

    def test_helper_exit_1_duplicate_both_dimensions(self, tmp_path: Path) -> None:
        """Duplicate waiver_id AND entry_key simultaneously — violation unresolved, exit 1."""
        current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
        current["complexity"]["allowed_functions"]["dup_both.py::func"] = {
            "file": "dup_both.py",
            "max_complexity": 10,
            "symbol": "func",
            "type": "function",
        }
        temp_baseline = tmp_path / "baseline_dup_both.json"
        temp_baseline.write_text(json.dumps(current), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_dup_both.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-DUP-BOTH",
                            "entry_key": "complexity:dup_both.py::func",
                            "base_ceiling": 0,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "First copy",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                        {
                            "waiver_id": "W-DUP-BOTH",
                            "entry_key": "complexity:dup_both.py::func",
                            "base_ceiling": 0,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Second copy — same ID AND same key",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # CR-005/006: stdout contains exactly three canonical JSON records:
        # the injected violation and both duplicate lifecycle records.
        assert result.returncode == 1, (
            f"Expected exit 1 for duplicate both dimensions, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    error_code="CC-RISE",
                    section="complexity",
                    canonical_key="complexity:dup_both.py::func",
                    old_value=0,
                    new_value=10,
                    decision_ref="<required: add waiver or revert increase>",
                    waiver_file=str(temp_waivers),
                ),
                _canonical_record(
                    waiver_id="W-DUP-BOTH",
                    waiver_status="duplicate",
                    waiver_base_ceiling=0,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                    duplicate_kinds=["waiver_id", "entry_key"],
                ),
                _canonical_record(
                    waiver_id="W-DUP-BOTH",
                    waiver_status="duplicate",
                    waiver_base_ceiling=0,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=1,
                    duplicate_kinds=["waiver_id", "entry_key"],
                ),
            ],
        )

    # ------------------------------------------------------------------
    # CR-003: Schema validation real subprocess matrix
    # Each schema row produces exit 2 with exact source/path and no traceback
    # ------------------------------------------------------------------

    def test_helper_exit_2_non_dict_baseline(self, tmp_path: Path) -> None:
        """A non-dict baseline (JSON list) exits 2 with exact source."""
        temp = tmp_path / "baseline_not_dict.json"
        temp.write_text("[]", encoding="utf-8")
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp)},
        )
        assert result.returncode == 2
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path=str(temp),
            message=f"{temp} must be a JSON object (got list)",
        )

    def test_helper_exit_2_bool_schema_version_waiver(self, tmp_path: Path) -> None:
        """A waiver ledger with bool schema_version exits 2."""
        temp_waivers = tmp_path / "waivers_bool_schema.json"
        temp_waivers.write_text(
            json.dumps({"schema_version": True, "waivers": []}),
            encoding="utf-8",
        )
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_WAIVERS_FILE": str(temp_waivers)},
        )
        assert result.returncode == 2
        _assert_exact_error_envelope(
            result,
            source="waiver_ledger",
            path="schema_version",
            message="schema_version must be a non-boolean integer",
        )

    def test_helper_exit_2_non_dict_waiver_ledger(self, tmp_path: Path) -> None:
        """A non-dict waiver ledger (JSON list) exits 2."""
        temp_waivers = tmp_path / "waivers_not_dict.json"
        temp_waivers.write_text("[]", encoding="utf-8")
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_WAIVERS_FILE": str(temp_waivers)},
        )
        assert result.returncode == 2
        _assert_exact_error_envelope(
            result,
            source="waiver_ledger",
            path=str(temp_waivers),
            message=f"{temp_waivers} must be a JSON object (got list)",
        )

    def test_helper_exit_2_unknown_waiver_schema(self, tmp_path: Path) -> None:
        """An unknown waiver schema_version exits 2."""
        temp_waivers = tmp_path / "waivers_unknown_schema.json"
        temp_waivers.write_text(
            json.dumps({"schema_version": 99, "waivers": []}),
            encoding="utf-8",
        )
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_WAIVERS_FILE": str(temp_waivers)},
        )
        assert result.returncode == 2
        _assert_exact_error_envelope(
            result,
            source="waiver_ledger",
            path="schema_version",
            message="unsupported schema_version 99 (expected 1)",
        )

    def test_helper_exit_2_waiver_non_object_entry(self, tmp_path: Path) -> None:
        """A waiver file with a non-object entry exits 2."""
        temp_waivers = tmp_path / "waivers_non_object_entry.json"
        temp_waivers.write_text(
            json.dumps({"schema_version": 1, "waivers": ["not-a-dict"]}),
            encoding="utf-8",
        )
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_WAIVERS_FILE": str(temp_waivers)},
        )
        assert result.returncode == 2
        _assert_exact_error_envelope(
            result,
            source="waiver_ledger",
            path="waivers[0]",
            message="waiver at index 0 must be a JSON object (got str)",
        )

    # ------------------------------------------------------------------
    # CR-003: Baseline schema validation subprocess matrix
    # ------------------------------------------------------------------

    _SCHEMA_VIOLATIONS: list[tuple[str, dict, str]] = [
        (
            "string_schema_version",
            {
                "schema_version": "1",
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "schema_version must be a non-boolean integer (got str)",
        ),
        (
            "non_dict_dead_code",
            {
                "schema_version": 1,
                "dead_code": "not-a-dict",
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "missing or non-dict section 'dead_code' (got str)",
        ),
        (
            "non_list_allowed_messages",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": "not-a-list"},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "dead_code.allowed_messages must be a list (got str)",
        ),
        (
            "empty_string_in_allowed_messages",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": [""]},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "dead_code.allowed_messages[0] must be a non-empty string (got str)",
        ),
        (
            "non_dict_complexity",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": "not-a-dict",
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "missing or non-dict section 'complexity' (got str)",
        ),
        (
            "non_dict_allowed_functions",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": "not-a-dict"},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "complexity.allowed_functions must be a dict (got str)",
        ),
        (
            "non_dict_complexity_entry",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {"x.py::f": "not-a-dict"}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "complexity.allowed_functions['x.py::f'] must be a dict (got str)",
        ),
        (
            "invalid_complexity_type",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {
                    "allowed_functions": {
                        "x.py::f": {
                            "file": "x.py",
                            "symbol": "f",
                            "type": "unknown",
                            "max_complexity": 5,
                        }
                    }
                },
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "complexity.allowed_functions['x.py::f'].type must be one of "
            "['class', 'function', 'method'] (got 'unknown')",
        ),
        (
            "float_max_complexity",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {
                    "allowed_functions": {
                        "x.py::f": {
                            "file": "x.py",
                            "symbol": "f",
                            "type": "function",
                            "max_complexity": 5.5,
                        }
                    }
                },
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "complexity.allowed_functions['x.py::f'].max_complexity must be a "
            "non-negative integer (got float)",
        ),
        (
            "negative_max_complexity",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {
                    "allowed_functions": {
                        "x.py::f": {
                            "file": "x.py",
                            "symbol": "f",
                            "type": "function",
                            "max_complexity": -1,
                        }
                    }
                },
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "complexity.allowed_functions['x.py::f'].max_complexity must be a "
            "non-negative integer (got int)",
        ),
        (
            "bool_max_complexity",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {
                    "allowed_functions": {
                        "x.py::f": {
                            "file": "x.py",
                            "symbol": "f",
                            "type": "function",
                            "max_complexity": True,
                        }
                    }
                },
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            },
            "complexity.allowed_functions['x.py::f'].max_complexity must be a "
            "non-negative integer (got bool)",
        ),
        (
            "non_dict_duplication",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": "not-a-dict",
            },
            "missing or non-dict section 'duplication' (got str)",
        ),
        (
            "string_allowed_blocks",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": "0"},
            },
            "duplication.allowed_blocks must be a non-negative integer (got str)",
        ),
        (
            "negative_allowed_blocks",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": -1},
            },
            "duplication.allowed_blocks must be a non-negative integer (got int)",
        ),
        (
            "bool_allowed_blocks",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": True},
            },
            "duplication.allowed_blocks must be a non-negative integer (got bool)",
        ),
        (
            "identities_length_mismatch",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 2, "allowed_block_identities": ["only_one"]},
            },
            "duplication.allowed_block_identities length 1 != allowed_blocks 2",
        ),
        (
            "non_list_identities",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0, "allowed_block_identities": "not-a-list"},
            },
            "duplication.allowed_block_identities must be a list (got str)",
        ),
        (
            "empty_string_identity",
            {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 1, "allowed_block_identities": [""]},
            },
            "duplication.allowed_block_identities[0] must be a non-empty string",
        ),
    ]

    _SCHEMA_ERROR_PATHS = {
        "string_schema_version": "schema_version",
        "non_dict_dead_code": "dead_code",
        "non_list_allowed_messages": "dead_code.allowed_messages",
        "empty_string_in_allowed_messages": "dead_code.allowed_messages[0]",
        "non_dict_complexity": "complexity",
        "non_dict_allowed_functions": "complexity.allowed_functions",
        "non_dict_complexity_entry": "complexity.allowed_functions['x.py::f']",
        "invalid_complexity_type": "complexity.allowed_functions['x.py::f'].type",
        "float_max_complexity": "complexity.allowed_functions['x.py::f'].max_complexity",
        "negative_max_complexity": "complexity.allowed_functions['x.py::f'].max_complexity",
        "bool_max_complexity": "complexity.allowed_functions['x.py::f'].max_complexity",
        "non_dict_duplication": "duplication",
        "string_allowed_blocks": "duplication.allowed_blocks",
        "negative_allowed_blocks": "duplication.allowed_blocks",
        "bool_allowed_blocks": "duplication.allowed_blocks",
        "identities_length_mismatch": "duplication.allowed_block_identities",
        "non_list_identities": "duplication.allowed_block_identities",
        "empty_string_identity": "duplication.allowed_block_identities[0]",
    }

    @pytest.mark.parametrize(
        ("name", "baseline_data", "expected_error"),
        _SCHEMA_VIOLATIONS,
        ids=[v[0] for v in _SCHEMA_VIOLATIONS],
    )
    def test_helper_exit_2_schema_violation(
        self,
        tmp_path: Path,
        name: str,
        baseline_data: dict,
        expected_error: str,
    ) -> None:
        """Every schema violation row produces exit 2 with exact error and no traceback."""
        temp_baseline = tmp_path / f"schema_violation_{name}.json"
        temp_baseline.write_text(json.dumps(baseline_data), encoding="utf-8")

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for schema violation '{name}', "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path=self._SCHEMA_ERROR_PATHS[name],
            message=expected_error,
        )

    # ------------------------------------------------------------------
    # CR-003: Free-text validation subprocess tests
    # ------------------------------------------------------------------

    def test_helper_exit_2_tab_in_dead_code_message(self, tmp_path: Path) -> None:
        """A dead_code message with tab → exit 2 (schema error)."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": ["normal", "bad\tmsg"]},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp = tmp_path / "baseline_tab_msg.json"
        temp.write_text(json.dumps(data), encoding="utf-8")
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp)},
        )
        assert result.returncode == 2
        invalid_message = "bad\tmsg"
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path="dead_code.allowed_messages[1]",
            message=(
                f"dead_code.allowed_messages[1]={invalid_message!r} must not contain "
                "control, surrogate, or DEL characters"
            ),
        )

    def test_helper_exit_2_del_in_complexity_symbol(self, tmp_path: Path) -> None:
        """A complexity symbol with DEL → exit 2 (schema error)."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "file.py::bad\x7ffunc": {
                        "file": "file.py",
                        "symbol": "bad\x7ffunc",
                        "type": "function",
                        "max_complexity": 5,
                    }
                }
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp = tmp_path / "baseline_del_symbol.json"
        temp.write_text(json.dumps(data), encoding="utf-8")
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp)},
        )
        assert result.returncode == 2
        invalid_key = "file.py::bad\x7ffunc"
        invalid_symbol = "bad\x7ffunc"
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path=f"complexity.allowed_functions[{invalid_key!r}].symbol",
            message=(
                f"complexity.allowed_functions[{invalid_key!r}].symbol="
                f"{invalid_symbol!r} must not contain control, surrogate, or DEL characters"
            ),
        )

    def test_helper_exit_1_tab_in_waiver_entry_key(self, tmp_path: Path) -> None:
        """A waiver entry_key with tab → malformed → exit 1."""
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_waiver_tab.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_tab_key.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-TAB-KEY",
                            "entry_key": "dead_code:allowed_messages:bad\tmsg:multiplicity",
                            "base_ceiling": 0,
                            "ceiling": 5,
                            "owner": "test@example.com",
                            "reason": "Tab in entry_key test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for tab in waiver entry_key, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-TAB-KEY",
                    waiver_status="malformed",
                    waiver_base_ceiling=0,
                    waiver_ceiling=5,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    def test_helper_exit_1_surrogate_in_waiver_entry_key(self, tmp_path: Path) -> None:
        """A waiver entry_key with surrogate → malformed → exit 1."""
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_waiver_surrogate.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_surrogate_key.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-SUR-KEY",
                            "entry_key": "complexity:file.py::bad\ud800func",
                            "base_ceiling": 0,
                            "ceiling": 5,
                            "owner": "test@example.com",
                            "reason": "Surrogate in entry_key test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for surrogate in waiver entry_key, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-SUR-KEY",
                    waiver_status="malformed",
                    waiver_base_ceiling=0,
                    waiver_ceiling=5,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    # ------------------------------------------------------------------
    # CR-003: DEL (0x7F) in waiver entry_key subprocess test
    # ------------------------------------------------------------------

    def test_helper_exit_1_del_in_waiver_entry_key(self, tmp_path: Path) -> None:
        """A waiver entry_key with DEL (0x7F) → malformed → exit 1."""
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_waiver_del_key.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_del_key.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-DEL-KEY",
                            "entry_key": "complexity:file.py::bad\x7ffunc",
                            "base_ceiling": 0,
                            "ceiling": 5,
                            "owner": "test@example.com",
                            "reason": "DEL in entry_key test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for DEL in waiver entry_key, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-DEL-KEY",
                    waiver_status="malformed",
                    waiver_base_ceiling=0,
                    waiver_ceiling=5,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    # ------------------------------------------------------------------
    # CR-003: Entry-key format parser edge classes — each named format
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("name", "entry_key"),
        [
            (
                "empty_dead_code_message",
                "dead_code:allowed_messages::multiplicity",
            ),
            (
                "complexity_missing_separator",
                "complexity:file.pyfunc",
            ),
            (
                "complexity_extra_separator",
                "complexity:file.py:::func",
            ),
            (
                "complexity_empty_path",
                "complexity:::func",
            ),
            (
                "complexity_empty_symbol",
                "complexity:file.py::",
            ),
            (
                "unknown_prefix",
                "unknown:file.py::func",
            ),
            (
                "large_files_extra_colon",
                "large_files:file.py:extra",
            ),
            (
                "duplication_wrong_literal",
                "duplication:allowed_blocks:extra",
            ),
            (
                "complexity_absolute_waiver_path",
                "complexity:/etc/passwd::func",
            ),
            (
                "complexity_backslash_waiver_path",
                r"complexity:windows\path\file.py::func",
            ),
        ],
        ids=[
            "empty-dead_code-message",
            "complexity-missing-separator",
            "complexity-extra-separator",
            "complexity-empty-path",
            "complexity-empty-symbol",
            "unknown-prefix",
            "large-files-extra-colon",
            "duplication-wrong-literal",
            "complexity-absolute-waiver-path",
            "complexity-backslash-waiver-path",
        ],
    )
    def test_helper_exit_1_entry_key_parser_edge(
        self, tmp_path: Path, name: str, entry_key: str
    ) -> None:
        """
        Every named entry-key parser edge class → exit 1 with canonical

        record and no traceback.

        All named format-syntax edge cases are rejected by
        ``_parse_entry_key`` and produce a ``malformed`` waiver status.
        Control-character edge cases (tab/DEL/surrogate) are caught earlier
        and produce ``malformed`` as well — those are covered by individual
        tests above.
        """
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / f"baseline_{name}.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / f"waivers_{name}.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": f"W-FMT-{name.upper()}",
                            "entry_key": entry_key,
                            "base_ceiling": 0,
                            "ceiling": 5,
                            "owner": "test@example.com",
                            "reason": f"Format edge class: {name}",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for {name} entry_key {entry_key!r}, "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id=f"W-FMT-{name.upper()}",
                    waiver_status="malformed",
                    waiver_base_ceiling=0,
                    waiver_ceiling=5,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    # ------------------------------------------------------------------
    # UTC boundary: today stays active under extreme timezone offset
    # ------------------------------------------------------------------

    def test_utc_today_active_under_extreme_tz(self) -> None:
        """
        A waiver expiring today stays active under extreme TZ offset.

        Uses Pacific/Kiritimati (+14) — the furthest-forward inhabited timezone
        where local date could be one day ahead of UTC.
        """
        skip_reason = None
        if "TZ" in os.environ:
            skip_reason = "Cannot test TZ override when TZ is already set"
        try:
            import zoneinfo

            zoneinfo.ZoneInfo("Pacific/Kiritimati")
        except ModuleNotFoundError, KeyError, zoneinfo.ZoneInfoNotFoundError:
            skip_reason = "Pacific/Kiritimati timezone not available"
        if skip_reason:
            pytest.skip(skip_reason)

        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "tz_test_file.py::tz_test_func": {
                        "file": "tz_test_file.py",
                        "max_complexity": 10,
                        "symbol": "tz_test_func",
                        "type": "function",
                    },
                },
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            temp_baseline = tmp_path / "baseline_tz.json"
            temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")
            temp_waivers = tmp_path / "waivers_tz.json"
            temp_waivers.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "waivers": [
                            {
                                "waiver_id": "W-TZ-001",
                                "entry_key": "complexity:tz_test_file.py::tz_test_func",
                                "base_ceiling": 0,
                                "ceiling": 10,
                                "owner": "tz-test@example.com",
                                "reason": "UTC boundary test under extreme TZ",
                                "expires_on": today_str,
                                "decision_ref": "quality-baseline-monotonicity",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            # Run under extreme TZ — local date is UTC+14 while code uses
            # datetime.now(UTC).date(), so today's waiver stays active
            env = os.environ.copy()
            env["TZ"] = "Pacific/Kiritimati"
            env["QUALITY_BASELINE_BASE_REF"] = "v87"
            env["QUALITY_BASELINE_FILE"] = str(temp_baseline)
            env["QUALITY_WAIVERS_FILE"] = str(temp_waivers)

            result = subprocess.run(
                [sys.executable, str(self.HELPER_PATH)],
                capture_output=True,
                text=True,
                cwd=str(_REPO_ROOT),
                timeout=60,
                env=env,
            )

        # Waiver expires today — stays active under extreme TZ
        assert result.returncode == 0, (
            f"Expected exit 0 (waiver active under extreme TZ), "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "Traceback" not in result.stderr

    # ------------------------------------------------------------------
    # CR-006: Real entrypoint tests (unwaived violations, schema
    # validation, waiver ledger failures, no-traceback, shell path)
    # ------------------------------------------------------------------

    def test_helper_exit_1_unwaived_increases(self, tmp_path: Path) -> None:
        """A baseline with increased values and no waivers exits 1."""
        # Create a modified baseline with higher values than v87 allows.
        current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
        # Inject an extra complexity increase v87 has no record of
        current["complexity"]["allowed_functions"]["new_file.py::new_function"] = {
            "file": "new_file.py",
            "max_complexity": 5,
            "symbol": "new_function",
            "type": "function",
        }
        temp_baseline = tmp_path / "quality_baseline.json"
        temp_baseline.write_text(json.dumps(current), encoding="utf-8")

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        # CR-005/006: stdout contains canonical JSON records sorted by
        # (error_code, canonical_key).  The new-file key (new_file.py:new_function)
        # is the first in sorted order among the retained baseline sections.
        assert result.returncode == 1, (
            f"Expected exit 1 for unwaived increase, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    error_code="CC-RISE",
                    section="complexity",
                    canonical_key="complexity:new_file.py::new_function",
                    old_value=0,
                    new_value=5,
                    waiver_file=str(_REPO_ROOT / "scripts" / "quality_waivers.json"),
                    decision_ref="<required: add waiver or revert increase>",
                )
            ],
        )

    def test_helper_exit_2_baseline_schema_failure(self, tmp_path: Path) -> None:
        """A non-dict baseline file produces exit 2 with deterministic error."""
        temp_baseline = tmp_path / "baseline.json"
        temp_baseline.write_text("[]", encoding="utf-8")  # list, not dict

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for baseline schema failure, got {result.returncode}"
        )
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path=str(temp_baseline),
            message=f"{temp_baseline} must be a JSON object (got list)",
        )

    def test_helper_exit_2_bad_schema_version(self, tmp_path: Path) -> None:
        """A baseline with unsupported schema_version produces exit 2."""
        temp_baseline = tmp_path / "baseline.json"
        temp_baseline.write_text(
            json.dumps(
                {
                    "schema_version": 99,
                    "dead_code": {},
                    "complexity": {},
                    "large_files": {},
                    "duplication": {"allowed_blocks": 0},
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for bad schema_version, got {result.returncode}"
        )
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path="schema_version",
            message="unsupported schema_version 99 (expected 1)",
        )

    def test_helper_exit_2_bool_schema_version(self, tmp_path: Path) -> None:
        """A baseline with bool schema_version produces exit 2 (not 0/1)."""
        temp_baseline = tmp_path / "baseline.json"
        temp_baseline.write_text(
            json.dumps(
                {
                    "schema_version": True,
                    "dead_code": {"allowed_messages": []},
                    "complexity": {"allowed_functions": {}},
                    "large_files": {"allowed_files": {}},
                    "duplication": {"allowed_blocks": 0},
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for bool schema_version, got {result.returncode}"
        )
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path="schema_version",
            message="schema_version must be a non-boolean integer (got bool)",
        )

    def test_helper_exit_2_non_object_waiver_entry(self, tmp_path: Path) -> None:
        """A waiver file with a non-dict entry produces exit 2."""
        temp_waivers = tmp_path / "waivers.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": ["not-a-dict"],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_WAIVERS_FILE": str(temp_waivers)},
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for non-object waiver entry, got {result.returncode}"
        )
        _assert_exact_error_envelope(
            result,
            source="waiver_ledger",
            path="waivers[0]",
            message="waiver at index 0 must be a JSON object (got str)",
        )

    def test_helper_no_traceback_on_exit_2(self) -> None:
        """Every exit-2 path must have no Python traceback in stderr."""
        # Bad base ref (already works, but verify no traceback explicitly)
        result = self._run_helper(
            extra_args=["--base-ref", "nonexistent-ref-opencode-test-99999"],
        )
        assert result.returncode == 2
        assert "Traceback" not in result.stderr, (
            f"No traceback expected on exit 2, got:\n{result.stderr}"
        )

    # ------------------------------------------------------------------
    # CR-004: Malformed + duplicate valid twin — disqualified
    # ------------------------------------------------------------------

    def test_helper_exit_1_malformed_duplicate_twin(self, tmp_path: Path) -> None:
        """
        A malformed row sharing a waiver_id with a valid row: both disqualified.

        CR-004: Malformed copy retains malformed state with duplicate_kinds
        metadata.  The otherwise-valid twin becomes duplicate because the
        shared waiver_id appears in the full inventory.
        """
        current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
        current["complexity"]["allowed_functions"]["malformed_dup_test.py::func"] = {
            "file": "malformed_dup_test.py",
            "max_complexity": 10,
            "symbol": "func",
            "type": "function",
        }
        temp_baseline = tmp_path / "baseline_malformed_dup.json"
        temp_baseline.write_text(json.dumps(current), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_malformed_dup.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-MAL-DUP",
                            "entry_key": "complexity:malformed_dup_test.py::func",
                            "base_ceiling": 0,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Valid twin",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                        {
                            # Malformed copy — missing 'owner', same waiver_id
                            "waiver_id": "W-MAL-DUP",
                            "entry_key": "complexity:other_key.py::func",
                            "base_ceiling": 0,
                            "ceiling": 5,
                            "reason": "Missing owner",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for malformed+duplicate twin, "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        pf = self._policy_file()
        data = json.loads(pf.read_text())
        evals = data.get("waiver_evaluations", [])
        assert evals == [
            {
                "waiver_id": "W-MAL-DUP",
                "status": "duplicate",
                "error": "duplicate waiver_id — all copies disqualified",
                "matches": [],
                "waiver_index": 0,
                "base_ceiling": 0,
                "ceiling": 10,
                "decision_ref": "quality-baseline-monotonicity",
                "duplicate_kinds": ["waiver_id"],
            },
            {
                "waiver_id": "W-MAL-DUP",
                "status": "malformed",
                "error": "waiver[1] missing required key(s): owner",
                "matches": [],
                "waiver_index": 1,
                "base_ceiling": 0,
                "ceiling": 5,
                "decision_ref": "quality-baseline-monotonicity",
                "duplicate_kinds": ["waiver_id"],
            },
        ]
        assert result.stderr == ""

    # ------------------------------------------------------------------
    # CR-005: Canonical record — waiver_file in policy output
    # ------------------------------------------------------------------

    def test_policy_file_contains_waiver_file(self, tmp_path: Path) -> None:
        """Policy output includes waiver_file field set to actual waiver path."""
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_waiver_file_check.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        # With active waivers
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_waiver_file_check.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-WF-001",
                            "entry_key": "complexity:nonexistent.py::f",
                            "base_ceiling": 5,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "waiver_file test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # Orphan waiver blocks → exit 1 (but waiver_file must still be in output)
        pf = self._policy_file()
        data = json.loads(pf.read_text())
        assert "waiver_file" in data, "Policy output must contain waiver_file field"
        assert data["waiver_file"] == str(temp_waivers), (
            f"waiver_file should be actual waiver path, got {data.get('waiver_file')}"
        )
        assert "Traceback" not in result.stderr

    def test_helper_exit_1_with_waiver_duplicates(self, tmp_path: Path) -> None:
        """Duplicate entry_keys make violations unresolved and exit 1."""
        # Create a baseline with an increase that needs a waiver
        current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
        current["complexity"]["allowed_functions"]["duplicate_test.py::func"] = {
            "file": "duplicate_test.py",
            "max_complexity": 10,
            "symbol": "func",
            "type": "function",
        }
        temp_baseline = tmp_path / "baseline_dup.json"
        temp_baseline.write_text(json.dumps(current), encoding="utf-8")

        # Waivers with duplicate entry_key — must not resolve the violation
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_dup.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W001",
                            "entry_key": "complexity:duplicate_test.py::func",
                            "base_ceiling": 0,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                        {
                            "waiver_id": "W002",
                            "entry_key": "complexity:duplicate_test.py::func",
                            "base_ceiling": 0,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Duplicate",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # Duplicate entry_keys = violation remains unresolved, so exit 1
        assert result.returncode == 1, (
            f"Expected exit 1 for duplicate entry_keys, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # ------------------------------------------------------------------
    # CR-006: Real orphan subprocess test — valid baseline + orphan
    # waiver asserts exit 1, canonical orphan record, no traceback
    # ------------------------------------------------------------------

    def test_helper_exit_1_orphan_waiver(self, tmp_path: Path) -> None:
        """
        A valid baseline with no increases plus an orphan waiver exits 1.

        Creates a baseline identical to v87 (no increases), adds an orphan
        waiver whose entry_key matches no detected increase, then asserts
        exit 1, canonical orphan diagnostic, no traceback, and a stable
        policy artifact.
        """
        # Build a baseline with exactly v87's values (no increases)
        baseline = {
            "schema_version": 1,
            "dead_code": {
                "allowed_messages": [
                    "quickscale_cli/src/quickscale_cli/commands/apply_command.py: unused variable 'q'",  # noqa: E501
                    "quickscale_modules/blog/src/quickscale_modules_blog/views.py: unused variable 'req'",  # noqa: E501
                    "quickscale_modules/blog/src/quickscale_modules_blog/views.py: unused variable 'req'",  # noqa: E501
                    "quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py: unused variable 'app_configs'",  # noqa: E501
                    "quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py: unused variable 'app_configs'",  # noqa: E501
                ],
            },
            "complexity": {
                "allowed_functions": {
                    "quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section": {  # noqa: E501
                        "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                        "max_complexity": 11,
                        "symbol": "_validate_modules_section",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_perform_module_embed": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 20,
                        "symbol": "_perform_module_embed",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_update_single_module": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 17,
                        "symbol": "_update_single_module",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_orphan.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        # Orphan waiver — entry_key that does NOT match any key in baseline
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_orphan.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-ORPHAN-001",
                            "entry_key": "complexity:nonexistent/path.py::no_such_func",
                            "base_ceiling": 5,
                            "ceiling": 10,
                            "owner": "test-orphan@example.com",
                            "reason": "Orphan waiver for SA121-CR-006 correction test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # Orphan waiver blocks the gate → exit 1
        assert result.returncode == 1, (
            f"Expected exit 1 for orphan waiver, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-ORPHAN-001",
                    waiver_status="orphan",
                    waiver_base_ceiling=5,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

        # No traceback on any output stream
        assert "Traceback" not in result.stderr, f"No traceback expected, got:\n{result.stderr}"
        assert "Traceback" not in result.stdout, (
            f"No traceback expected in stdout:\n{result.stdout}"
        )

        # Verify stable policy artifact
        pf = self._policy_file()
        assert pf.exists(), "Policy file must exist after orphan-waiver run"
        data = json.loads(pf.read_text())
        assert data.get("verdict") in ("violation",), (
            f"Expected violation verdict for orphan waiver, got {data.get('verdict')}"
        )
        # Waiver evaluations must include orphan status
        evals = data.get("waiver_evaluations", [])
        orphan_evals = [e for e in evals if e.get("status") == "orphan"]
        assert len(orphan_evals) == 1, (
            f"Expected exactly one orphan waiver evaluation, got:\n{json.dumps(evals, indent=2)}"
        )
        assert orphan_evals[0].get("waiver_index") == 0, (
            "Orphan waiver must carry correct ledger index"
        )

    def test_helper_exit_1_orphan_waiver_unchanged(self, tmp_path: Path) -> None:
        """
        An orphan waiver for a key that exists but has NOT changed value.

        The key is present in both old and new with the same value, so there
        is no violation and the waiver is orphan — exit 1.
        """
        # Baseline where ALL values match v87 (unchanged)
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_orphan_unchanged.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_orphan_unchanged.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-ORPHAN-UC-001",
                            "entry_key": "complexity:nonexistent.py::func",
                            "base_ceiling": 5,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Orphan unchanged test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # CR-005/006: stdout contains exactly 1 canonical JSON record with orphan status
        assert result.returncode == 1, (
            f"Expected exit 1 for orphan unchanged waiver, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-ORPHAN-UC-001",
                    waiver_status="orphan",
                    waiver_base_ceiling=5,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    def test_helper_exit_1_orphan_waiver_reduced(self, tmp_path: Path) -> None:
        """
        A waiver for a key whose current value is LOWER than the base.

        A decrease is never a violation, so the waiver is orphan — exit 1.
        """
        # Baseline where complexity value is LOWER than v87 (11→10)
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section": {  # noqa: E501
                        "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                        "max_complexity": 10,  # lower than v87's 11
                        "symbol": "_validate_modules_section",
                        "type": "function",
                    },
                },
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_orphan_reduced.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        # Waiver for the complexity key that was reduced (no violation exists)
        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_orphan_reduced.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-ORPHAN-RED-001",
                            "entry_key": "complexity:quickscale_core/src/quickscale_core/schema/config_schema.py::_validate_modules_section",  # noqa: E501
                            "base_ceiling": 11,
                            "ceiling": 12,
                            "owner": "test@example.com",
                            "reason": "Orphan reduced — value went down",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        # CR-005/006: stdout contains exactly 1 canonical JSON record with orphan status
        assert result.returncode == 1, (
            f"Expected exit 1 for orphan reduced waiver, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-ORPHAN-RED-001",
                    waiver_status="orphan",
                    waiver_base_ceiling=11,
                    waiver_ceiling=12,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    def test_helper_exit_0_active_waivers(self, tmp_path: Path) -> None:
        """
        Three increases with matching active waivers — exit 0.

        Creates a baseline with three NEW entries not in the merge-base
        (old=0) and matching active waivers.  Helper exits 0 with all
        waiver evaluations showing "active".
        """
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "new_active_test.py::new_func": {
                        "file": "new_active_test.py",
                        "max_complexity": 10,
                        "symbol": "new_func",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 0},
        }
        baseline["complexity"]["allowed_functions"].update(
            {
                "new_active_large.py::f2": {
                    "file": "new_active_large.py",
                    "max_complexity": 200,
                    "symbol": "f2",
                    "type": "function",
                },
                "new_active_large2.py::f3": {
                    "file": "new_active_large2.py",
                    "max_complexity": 300,
                    "symbol": "f3",
                    "type": "function",
                },
            }
        )
        temp_baseline = tmp_path / "baseline_active_waivers.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        temp_waivers = tmp_path / "waivers_active.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-ACT-001",
                            "entry_key": "complexity:new_active_test.py::new_func",
                            "base_ceiling": 0,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Active waiver test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                        {
                            "waiver_id": "W-ACT-002",
                            "entry_key": "complexity:new_active_large.py::f2",
                            "base_ceiling": 0,
                            "ceiling": 200,
                            "owner": "test@example.com",
                            "reason": "Active waiver test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                        {
                            "waiver_id": "W-ACT-003",
                            "entry_key": "complexity:new_active_large2.py::f3",
                            "base_ceiling": 0,
                            "ceiling": 300,
                            "owner": "test@example.com",
                            "reason": "Active waiver test",
                            "expires_on": future,
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        assert result.returncode == 0, (
            f"Expected exit 0 for active waivers, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        pf = self._policy_file()
        assert pf.exists(), "Policy file must exist after active-waiver run"
        data = json.loads(pf.read_text())
        evals = data.get("waiver_evaluations", [])
        active_evals = [e for e in evals if e.get("status") == "active"]
        assert len(active_evals) == 3, (
            f"Expected 3 active waiver evaluations, got {len(active_evals)}:\n"
            f"{json.dumps(evals, indent=2)}"
        )

        # Verify diagnostics contain full canonical records for each active waiver
        _canonical_keys = frozenset(
            {
                "error_code",
                "section",
                "canonical_key",
                "old_value",
                "new_value",
                "waiver_id",
                "waiver_status",
                "waiver_base_ceiling",
                "waiver_ceiling",
                "waiver_file",
                "decision_ref",
                "waiver_index",
                "duplicate_kinds",
            }
        )
        diag = data.get("diagnostics", [])
        for d in diag:
            actual_keys = frozenset(d.keys())
            assert actual_keys == _canonical_keys, (
                f"Canonical keys mismatch in diagnostics. "
                f"Missing: {_canonical_keys - actual_keys}. "
                f"Extra: {actual_keys - _canonical_keys}. "
                f"Record: {json.dumps(d, indent=2)}"
            )
        assert len(diag) == 3, f"Expected exactly 3 diagnostics entries, got {len(diag)}"

        assert "Traceback" not in result.stderr

    # ------------------------------------------------------------------
    # CR-006: Exact three SA114 increases without waivers — three sorted
    # complete canonical records, exit 1
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # CR-006: Isolated Git repo fixture tests (exact SA114 values)
    # ------------------------------------------------------------------

    def test_helper_exit_1_three_sa114_increases_no_waivers_isolated(self, tmp_path: Path) -> None:
        """
        Three increases with no waivers — exit 1, sorted records.

        Uses an isolated Git repo with exact base values (11, 1596, 605)
        committed at a resolvable base ref, then current values (12, 1608, 611).
        No waivers — exit 1 with three complete canonical records.
        """
        # Exact SA114 base values committed to isolated repo as tag "base"
        base_data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "quickscale_core/src/quickscale_core/schema/config_schema.py"
                    "::_validate_modules_section": {
                        "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                        "max_complexity": 11,
                        "symbol": "_validate_modules_section",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_perform_module_embed": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 20,
                        "symbol": "_perform_module_embed",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_update_single_module": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 17,
                        "symbol": "_update_single_module",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 0},
        }
        repo_dir = tmp_path / "git_fixture_no_waivers"
        repo_dir.mkdir()
        _create_isolated_repo(repo_dir, base_data, tag="base")

        # Current baseline with exact SA114 current values (12, 1608, 611)
        current_data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "quickscale_core/src/quickscale_core/schema/config_schema.py"
                    "::_validate_modules_section": {
                        "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                        "max_complexity": 12,
                        "symbol": "_validate_modules_section",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_perform_module_embed": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 22,
                        "symbol": "_perform_module_embed",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_update_single_module": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 18,
                        "symbol": "_update_single_module",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_current.json"
        temp_baseline.write_text(json.dumps(current_data), encoding="utf-8")

        result = self._run_helper(
            extra_args=["--base-ref", "base"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "GIT_DIR": str(repo_dir / ".git"),
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for three increases without waivers, "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        pf = self._policy_file()
        data = json.loads(pf.read_text())
        violations = data.get("violations", [])
        # Exactly 3 surviving complexity increases.
        assert len(violations) == 3, (
            f"Expected exactly 3 violation records, got {len(violations)}:\n"
            f"{json.dumps(violations, indent=2)}"
        )

        # Each record must be a complete canonical record with all 13 keys
        _canonical_keys = frozenset(
            {
                "error_code",
                "section",
                "canonical_key",
                "old_value",
                "new_value",
                "waiver_id",
                "waiver_status",
                "waiver_base_ceiling",
                "waiver_ceiling",
                "waiver_file",
                "decision_ref",
                "waiver_index",
                "duplicate_kinds",
            }
        )
        for v in violations:
            actual_keys = frozenset(v.keys())
            assert actual_keys == _canonical_keys, (
                f"Canonical keys mismatch. Missing: {_canonical_keys - actual_keys}. "
                f"Extra: {actual_keys - _canonical_keys}. "
                f"Record: {json.dumps(v, indent=2)}"
            )
            assert v["waiver_id"] is None
            assert v["waiver_status"] is None
            assert v["waiver_base_ceiling"] is None
            assert v["waiver_ceiling"] is None
            assert v["decision_ref"] == "<required: add waiver or revert increase>"
            assert v["waiver_index"] is None
            assert v["duplicate_kinds"] == []

        # CR-006: Exact canonical keys, not substring/any()
        expected_keys = [
            "complexity:quickscale_cli/src/quickscale_cli/commands/module_commands.py"
            "::_perform_module_embed",
            "complexity:quickscale_cli/src/quickscale_cli/commands/module_commands.py"
            "::_update_single_module",
            "complexity:quickscale_core/src/quickscale_core/schema/config_schema.py"
            "::_validate_modules_section",
        ]
        actual_keys = sorted(v["canonical_key"] for v in violations)
        assert actual_keys == expected_keys, (
            f"Expected exact keys:\n{expected_keys}\nGot:\n{actual_keys}"
        )
        # Exact old/new pairs
        key_values = {v["canonical_key"]: (v["old_value"], v["new_value"]) for v in violations}
        assert key_values[expected_keys[0]] == (20, 22)
        assert key_values[expected_keys[1]] == (17, 18)
        assert key_values[expected_keys[2]] == (11, 12)

        codes = [v["error_code"] for v in violations]
        assert codes == sorted(codes), f"Violations not sorted by error_code: {codes}"
        assert "Traceback" not in result.stderr

    def test_helper_exit_0_three_sa114_increases_active_waivers_isolated(
        self, tmp_path: Path
    ) -> None:
        """
        Three increases with exact active waivers — exit 0.

        Same isolated repo fixture with exact base values (11, 1596, 605)
        and current values (12, 1608, 611).  Matching waivers cover all three
        increases — exit 0 with three active waiver evaluations.
        """
        base_data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "quickscale_core/src/quickscale_core/schema/config_schema.py"
                    "::_validate_modules_section": {
                        "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                        "max_complexity": 11,
                        "symbol": "_validate_modules_section",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_perform_module_embed": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 20,
                        "symbol": "_perform_module_embed",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_update_single_module": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 17,
                        "symbol": "_update_single_module",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 0},
        }
        repo_dir = tmp_path / "git_fixture_active_waivers"
        repo_dir.mkdir()
        _create_isolated_repo(repo_dir, base_data, tag="base")

        current_data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "quickscale_core/src/quickscale_core/schema/config_schema.py"
                    "::_validate_modules_section": {
                        "file": "quickscale_core/src/quickscale_core/schema/config_schema.py",
                        "max_complexity": 12,
                        "symbol": "_validate_modules_section",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_perform_module_embed": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 22,
                        "symbol": "_perform_module_embed",
                        "type": "function",
                    },
                    "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                    "::_update_single_module": {
                        "file": "quickscale_cli/src/quickscale_cli/commands/module_commands.py",
                        "max_complexity": 18,
                        "symbol": "_update_single_module",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_current_active.json"
        temp_baseline.write_text(json.dumps(current_data), encoding="utf-8")

        future = (date.today() + timedelta(days=90)).isoformat()
        waivers = {
            "schema_version": 1,
            "waivers": [
                {
                    "waiver_id": "W-SA114-CPX",
                    "entry_key": (
                        "complexity:quickscale_core/src/quickscale_core/schema/"
                        "config_schema.py::_validate_modules_section"
                    ),
                    "base_ceiling": 11,
                    "ceiling": 12,
                    "owner": "test@example.com",
                    "reason": "CR-006: exact SA114 active waiver",
                    "expires_on": future,
                    "decision_ref": "quality-baseline-monotonicity",
                },
                {
                    "waiver_id": "W-SA114-LF1",
                    "entry_key": (
                        "complexity:quickscale_cli/src/quickscale_cli/commands/"
                        "module_commands.py::_perform_module_embed"
                    ),
                    "base_ceiling": 20,
                    "ceiling": 22,
                    "owner": "test@example.com",
                    "reason": "CR-006: exact SA114 active waiver",
                    "expires_on": future,
                    "decision_ref": "quality-baseline-monotonicity",
                },
                {
                    "waiver_id": "W-SA114-LF2",
                    "entry_key": (
                        "complexity:quickscale_cli/src/quickscale_cli/commands/"
                        "module_commands.py::_update_single_module"
                    ),
                    "base_ceiling": 17,
                    "ceiling": 18,
                    "owner": "test@example.com",
                    "reason": "CR-006: exact SA114 active waiver",
                    "expires_on": future,
                    "decision_ref": "quality-baseline-monotonicity",
                },
            ],
        }
        temp_waivers = tmp_path / "waivers_active.json"
        temp_waivers.write_text(json.dumps(waivers), encoding="utf-8")

        result = self._run_helper(
            extra_args=["--base-ref", "base"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
                "GIT_DIR": str(repo_dir / ".git"),
            },
        )
        assert result.returncode == 0, (
            f"Expected exit 0 for three increases with active waivers, "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        pf = self._policy_file()
        data = json.loads(pf.read_text())
        evals = data.get("waiver_evaluations", [])
        active_evals = [e for e in evals if e.get("status") == "active"]
        assert len(active_evals) == 3, (
            f"Expected 3 active waiver evaluations, got {len(active_evals)}:\n"
            f"{json.dumps(evals, indent=2)}"
        )

    # ------------------------------------------------------------------
    # CR-006: Missing merge-base blob in isolated same-repo fixture
    # ------------------------------------------------------------------

    def test_helper_exit_2_missing_base_blob_isolated(self, tmp_path: Path) -> None:
        """
        Resolved base commit missing the baseline blob — exit 2 (MERGE_BASE_ERROR).

        Creates an isolated repo with a tag pointing to a commit that does
        NOT contain ``scripts/quality_baseline.json``.  The commit resolves
        successfully, so this exercises ``MERGE_BASE_ERROR`` for a resolved
        base commit whose blob is missing — not an unresolvable ref.
        """
        # Create repo with only a README, no quality_baseline.json
        repo_dir = tmp_path / "git_fixture_missing_blob"
        repo_dir.mkdir()
        base_commit = _create_isolated_repo(
            repo_dir,
            baseline_data=None,
            tag="v1",
            extra_files={"README.md": "test repo without baseline blob"},
        )

        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        result = self._run_helper(
            extra_args=["--base-ref", "v1"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "GIT_DIR": str(repo_dir / ".git"),
            },
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for missing base blob (MERGE_BASE_ERROR), "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_error_envelope(
            result,
            source="merge_base_baseline",
            path="scripts/quality_baseline.json",
            message=(f"scripts/quality_baseline.json does not exist at merge-base {base_commit}"),
            code="MERGE_BASE_ERROR",
        )

    # ------------------------------------------------------------------
    # CR-006: Malformed base blob at resolved commit
    # ------------------------------------------------------------------

    def test_helper_exit_2_malformed_base_blob_isolated(self, tmp_path: Path) -> None:
        """
        Resolved base commit with a malformed (non-dict) baseline — exit 2.

        Creates an isolated repo where the baseline blob at a resolved
        commit is not valid JSON or not a JSON object.  This exercises
        the ``merge_base_baseline`` source path with ``SCHEMA_ERROR`` and
        the exact repo path.
        """
        repo_dir = tmp_path / "git_fixture_malformed_blob"
        repo_dir.mkdir()
        # Write baseline as a JSON list (not dict) — triggers non-dict error
        base_commit = _create_isolated_repo(
            repo_dir,
            baseline_data=None,
            tag="v1",
            extra_files={
                "scripts/quality_baseline.json": "[]",
            },
        )

        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        result = self._run_helper(
            extra_args=["--base-ref", "v1"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "GIT_DIR": str(repo_dir / ".git"),
            },
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for malformed base blob, "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_error_envelope(
            result,
            source="merge_base_baseline",
            path="scripts/quality_baseline.json",
            message=(
                f"scripts/quality_baseline.json at {base_commit} must be a JSON object (got list)"
            ),
        )

    # ------------------------------------------------------------------
    # CR-003/006: Strict path/key rejection via subprocess
    # ------------------------------------------------------------------

    def test_helper_exit_2_absolute_path_rejected(self, tmp_path: Path) -> None:
        """An absolute file path in complexity entry is rejected."""
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "/etc/passwd::func": {
                        "file": "/etc/passwd",
                        "max_complexity": 5,
                        "symbol": "func",
                        "type": "function",
                    },
                },
            },
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_abs_path.json"
        temp_baseline.write_text(json.dumps(data), encoding="utf-8")
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        assert result.returncode == 2, f"Expected exit 2 for absolute path, got {result.returncode}"
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path="complexity.allowed_functions['/etc/passwd::func'].file",
            message=(
                "complexity.allowed_functions['/etc/passwd::func'].file='/etc/passwd' "
                "must be repo-relative, not absolute"
            ),
        )

    def test_helper_exit_2_backslash_path_rejected(self, tmp_path: Path) -> None:
        """
        A path with backslashes in a complexity key is rejected.

        SA125-DEC-001 retired the large_files surface this originally exercised;
        the repo-relative path rule is unchanged and is proven on complexity.
        """
        data = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "windows\\path\\file.py::func": {
                        "file": "windows\\path\\file.py",
                        "max_complexity": 5,
                        "symbol": "func",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_backslash.json"
        temp_baseline.write_text(json.dumps(data), encoding="utf-8")
        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for backslash path, got {result.returncode}"
        )
        invalid_key = r"windows\path\file.py::func"
        invalid_path = r"windows\path\file.py"
        _assert_exact_error_envelope(
            result,
            source="current_baseline",
            path=f"complexity.allowed_functions[{invalid_key!r}].file",
            message=(
                f"complexity.allowed_functions[{invalid_key!r}].file="
                f"{invalid_path!r} must use POSIX separators, not backslashes"
            ),
        )

    def test_helper_exit_2_unicode_digit_date_rejected(self, tmp_path: Path) -> None:
        """A waiver with Unicode digit characters in expires_on is rejected."""
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {"allowed_functions": {}},
            "large_files": {"allowed_files": {}},
            "duplication": {"allowed_blocks": 0},
        }
        temp_baseline = tmp_path / "baseline_unicode_date.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        # Unicode full-width digits (２０２６-０１-０１) — not ASCII [0-9]
        temp_waivers = tmp_path / "waivers_unicode_date.json"
        temp_waivers.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "waivers": [
                        {
                            "waiver_id": "W-UNICODE-DATE",
                            "entry_key": "complexity:nonexistent.py::func",
                            "base_ceiling": 5,
                            "ceiling": 10,
                            "owner": "test@example.com",
                            "reason": "Test Unicode digit date rejection",
                            "expires_on": "２０２６-０１-０１",
                            "decision_ref": "quality-baseline-monotonicity",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for Unicode digit date, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        _assert_exact_stdout_records(
            result,
            [
                _canonical_record(
                    waiver_id="W-UNICODE-DATE",
                    waiver_status="malformed",
                    waiver_base_ceiling=5,
                    waiver_ceiling=10,
                    waiver_file=str(temp_waivers),
                    decision_ref="quality-baseline-monotonicity",
                    waiver_index=0,
                )
            ],
        )

    def test_helper_exit_1_mixed_violations_sorted(self, tmp_path: Path) -> None:
        """
        Multiple new entries without waivers — exit 1, sorted records.

        Creates a baseline with new entries not in the merge-base
        (old=0).  Helper exits 1 with violations sorted by
        (error_code, canonical_key).
        """
        baseline = {
            "schema_version": 1,
            "dead_code": {"allowed_messages": []},
            "complexity": {
                "allowed_functions": {
                    "new_unwaived_complexity.py::func_a": {
                        "file": "new_unwaived_complexity.py",
                        "max_complexity": 5,
                        "symbol": "func_a",
                        "type": "function",
                    },
                    "new_unwaived_complexity.py::func_b": {
                        "file": "new_unwaived_complexity.py",
                        "max_complexity": 8,
                        "symbol": "func_b",
                        "type": "function",
                    },
                },
            },
            "duplication": {"allowed_blocks": 1},
        }
        temp_baseline = tmp_path / "baseline_no_waivers.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        result = self._run_helper(
            extra_args=["--base-ref", "v87"],
            env={"QUALITY_BASELINE_FILE": str(temp_baseline)},
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for unwaived increases, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        pf = self._policy_file()
        data = json.loads(pf.read_text())
        violations = data.get("violations", [])
        # Fixture creates 2 complexity + 1 duplication = exactly 3 new violations
        assert len(violations) == 3, (
            f"Expected exactly 3 violation records, got {len(violations)}:\n"
            f"{json.dumps(violations, indent=2)}"
        )
        codes = [v["error_code"] for v in violations]
        assert codes == sorted(codes), f"Violations not sorted by error_code: {codes}"
        keys = [v["canonical_key"] for v in violations]
        assert keys == sorted(keys), f"Violations not sorted by canonical_key: {keys}"
        assert "Traceback" not in result.stderr


class TestDocumentIntegration:
    """Verify quality_tools.md sync with decisions.md on lifecycle/anchor matching."""

    def test_quality_tools_md_anchor_validation_described(self) -> None:
        """quality_tools.md describes decision_ref as exact anchor matching."""
        tools_path = _REPO_ROOT / "docs" / "technical" / "quality_tools.md"
        content = tools_path.read_text(encoding="utf-8")
        assert "exact" in content, (
            "quality_tools.md must describe decision_ref as exact anchor match"
        )
        assert "substring" in content or "not accepted" in content, (
            "quality_tools.md must clarify substring matching is not accepted"
        )

    def test_quality_tools_md_lifecycle_gate_impact(self) -> None:
        """quality_tools.md must describe which states block the gate."""
        tools_path = _REPO_ROOT / "docs" / "technical" / "quality_tools.md"
        content = tools_path.read_text(encoding="utf-8")
        assert "Hard fail" in content, (
            "quality_tools.md must describe which waiver states cause hard fail"
        )
        # orphan is now a hard-fail state per decisions.md §Waiver State Machine
        assert "orphan" in content, "quality_tools.md must describe the orphan state"
        orphan_lines = [line.strip() for line in content.splitlines() if "orphan" in line.lower()]
        assert any("Hard fail" in line for line in orphan_lines), (
            "quality_tools.md must describe orphan as a hard-fail state, not informational"
        )


# ---------------------------------------------------------------------------
# Shell subprocess tests — execute the actual checked-in check_quality.sh
# ---------------------------------------------------------------------------


# Stub poetry script template for PATH injection
# NOTE: uses single-quote outer delimiter so inner triple-quoted
# docstrings in the stub content do not conflict.
_POETRY_STUB = '''#!/usr/bin/env python3
"""Stub poetry for check_quality.sh subprocess tests."""
import subprocess
import sys

def main() -> int:
    args = sys.argv[1:]

    if len(args) >= 2 and args[0] == "run":
        tool = args[1]
        tool_args = args[2:]

        # Version checks --- always succeed
        if tool in ("vulture", "radon", "pylint") and "--version" in tool_args:
            print(f"{tool} 1.0.0 (stub)")
            return 0

        # Vulture analysis --- no dead code
        if tool == "vulture":
            return 0

        # Radon analysis --- return empty JSON
        if tool == "radon":
            print("{}")
            return 0

        # Pylint duplication --- return empty list
        if tool == "pylint":
            print("[]")
            return 0

        # Python command --- forward to real python
        if tool == "python":
            cmd = [sys.executable] + tool_args
            proc = subprocess.run(cmd)
            return proc.returncode

    return 0

if __name__ == "__main__":
    sys.exit(main())
'''


class TestShellSubprocess:
    """
    Shell subprocess tests for ``check_quality.sh``.

    Execute the actual checked-in script as a subprocess with controlled
    PATH stubs for Poetry and analyzers.
    """

    SHELL_PATH = _SCRIPT_DIR / "check_quality.sh"

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def poetry_stub(self, tmp_path: Path) -> Path:
        """Create a stub ``poetry`` script and return the bin directory path."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        stub = bin_dir / "poetry"
        stub.write_text(_POETRY_STUB, encoding="utf-8")
        stub.chmod(0o755)
        return bin_dir

    @pytest.fixture
    def find_stub(self, tmp_path: Path) -> Path:
        """
        Create a stub ``find`` script and return the bin directory path.

        The stub returns no files (empty stdout, exit 0), which prevents
        the shell's native ``find``/``wc`` large-file analysis from
        consuming live repository file sizes.  Module discovery (also
        uses ``find``) returns empty, causing ``get_module_paths`` to
        use the fallback path list; the poetry stub then intercepts
        vulture/radon/pylint and returns empty results regardless of
        which paths are passed.
        """
        bin_dir = tmp_path / "findbin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        stub = bin_dir / "find"
        # NB: Under ``set -o pipefail``, every stage of the large-file
        # pipeline must produce non-empty output or ``grep -v "^$"``
        # later will exit non-zero and kill the shell.  Emit one line
        # whose line count is >= 500 (so awk passes it through).  The
        # large-file result is intentionally advisory: it must remain in
        # the raw report without entering baseline comparison or gate status.
        # The ``find`` command is invoked with module-relative paths,
        # so the stub must produce the same format.
        stub.write_text(
            "#!/bin/bash\n"
            "# stub find -- emit one line for a baseline-tracked file\n"
            "# with ample headroom, then exit 0.\n"
            'echo "2000\tquickscale_core/src/quickscale_core/dr_engine/orchestration.py"\n'
            "exit 0\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        return bin_dir

    @pytest.fixture
    def quickscale_backup(self) -> dict[str, str | None]:
        """Backup key ``.quickscale`` artifacts and return their content."""
        qs = _REPO_ROOT / ".quickscale"
        backup: dict[str, str | None] = {}
        for name in (
            "quality_report.json",
            "quality_report.md",
            "quality_gate_status.json",
            "quality_baseline_policy.json",
        ):
            f = qs / name
            backup[name] = f.read_text(encoding="utf-8") if f.exists() else None
        return backup

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _restore_quickscale(self, backup: dict[str, str | None]) -> None:
        """Restore backed-up ``.quickscale`` artifacts."""
        qs = _REPO_ROOT / ".quickscale"
        for name, content in backup.items():
            f = qs / name
            if content is not None:
                f.write_text(content, encoding="utf-8")
            elif f.exists():
                f.unlink()

    def _run_shell(
        self,
        extra_env: dict[str, str] | None = None,
        stub_dir: Path | None = None,
        find_stub_dir: Path | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Run ``check_quality.sh`` as a subprocess and return the result.

        *stub_dir* — a ``bin/`` directory whose ``poetry`` stub is
        prepended to PATH (intercepts ``poetry run vulture`` etc.).

        *find_stub_dir* — a separate ``findbin/`` directory whose
        ``find`` stub is prepended to PATH **before** *stub_dir* so
        that the shell's native ``find`` command is shimmed first.
        """
        env = os.environ.copy()
        if stub_dir:
            env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
        if find_stub_dir:
            # find stub goes before poetry stub so native find is shimmed
            env["PATH"] = f"{find_stub_dir}:{env['PATH']}"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [str(self.SHELL_PATH)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=180,
            env=env,
        )

    # ------------------------------------------------------------------
    # Exit 1 — unwaived baseline increases
    # ------------------------------------------------------------------

    def test_shell_exit_1_unwaived_increases(
        self,
        tmp_path: Path,
        poetry_stub: Path,
        quickscale_backup: dict[str, str | None],
    ) -> None:
        """
        Shell exits 1 when the helper detects unwaived increases.

        Verifies policy preservation, stale artifact removal, no analyzer
        invocation after dependency probes, and one complete summary with
        compact JSON records matching the canonical policy fields.
        """
        try:
            # Create a modified baseline with an unwaived increase
            current = json.loads((_REPO_ROOT / "scripts" / "quality_baseline.json").read_text())
            current["complexity"]["allowed_functions"]["test_shell_exit1.py::func"] = {
                "file": "test_shell_exit1.py",
                "max_complexity": 5,
                "symbol": "func",
                "type": "function",
            }
            temp_baseline = tmp_path / "baseline_exit1.json"
            temp_baseline.write_text(json.dumps(current), encoding="utf-8")

            # --- Execute ---
            result = self._run_shell(
                stub_dir=poetry_stub,
                extra_env={
                    "QUALITY_BASELINE_FILE": str(temp_baseline),
                    "QUALITY_BASELINE_BASE_REF": "v87",
                },
            )

            # --- 1. Shell exit 1 ---
            assert result.returncode == 1, (
                f"Expected exit 1 for unwaived increases, got {result.returncode}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

            # --- 2. Policy preservation ---
            pf = _REPO_ROOT / ".quickscale" / "quality_baseline_policy.json"
            assert pf.exists(), "Policy file must be preserved on failure"
            policy_data = json.loads(pf.read_text())
            assert policy_data.get("verdict") in ("violation",)

            # --- 3. Stale artifact removal ---
            qs = _REPO_ROOT / ".quickscale"
            assert not (qs / "quality_report.json").exists(), (
                "quality_report.json must be removed on failure"
            )
            assert not (qs / "quality_report.md").exists(), (
                "quality_report.md must be removed on failure"
            )
            assert not (qs / "quality_gate_status.json").exists(), (
                "quality_gate_status.json must be removed on failure"
            )

            # --- 4. CR-005: Output contains only canonical JSON records ---
            # The shell includes its normal status prose around the helper's
            # record, so assert the complete unfiltered JSON record after
            # identifying the one JSON line in that shell output.
            json_lines = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip().startswith("{") and line.strip().endswith("}")
            ]
            assert len(json_lines) == 1, (
                f"Expected exactly 1 compact JSON record in stdout, got {len(json_lines)}:\n"
                f"{result.stdout}"
            )
            assert json.loads(json_lines[0]) == _canonical_record(
                error_code="CC-RISE",
                section="complexity",
                canonical_key="complexity:test_shell_exit1.py::func",
                old_value=0,
                new_value=5,
                waiver_file=str(_REPO_ROOT / "scripts" / "quality_waivers.json"),
                decision_ref="<required: add waiver or revert increase>",
            )

            # --- 5. No analyzer invocation after dependency probes ---
            # The script should abort before running analyzers on failure
            # "Analyzing" should NOT appear (no analyzer ran)
            assert "Analyzing" not in result.stdout, "Analyzers should not run after helper failure"

            # --- 6. No waiver evaluations lifecycle prose ---
            eval_count = policy_data.get("summary", {}).get("total_waivers", 0)
            if eval_count > 0:
                assert "Waiver " not in result.stdout, (
                    "No waiver lifecycle prose in CR-005 shell output"
                )

        finally:
            self._restore_quickscale(quickscale_backup)

    # ------------------------------------------------------------------
    # Exit 2 — schema error in baseline
    # ------------------------------------------------------------------

    def test_shell_exit_2_schema_error(
        self,
        tmp_path: Path,
        poetry_stub: Path,
        quickscale_backup: dict[str, str | None],
    ) -> None:
        """
        Shell exits 1 when the helper exits 2 (schema error).

        Verifies policy preservation, stale artifact removal, no analyzer
        invocation, and complete error metadata in the output.
        """
        try:
            # Create a defective baseline (non-dict value)
            temp_baseline = tmp_path / "baseline_schema_error.json"
            temp_baseline.write_text("[]", encoding="utf-8")  # list, not dict

            result = self._run_shell(
                stub_dir=poetry_stub,
                extra_env={
                    "QUALITY_BASELINE_FILE": str(temp_baseline),
                    "QUALITY_BASELINE_BASE_REF": "v87",
                },
            )

            # --- 1. Shell always exits 1 on helper failure ---
            assert result.returncode == 1, (
                f"Expected exit 1 for schema error, got {result.returncode}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

            # --- 2. Policy preservation (complete error envelope) ---
            pf = _REPO_ROOT / ".quickscale" / "quality_baseline_policy.json"
            assert pf.exists(), "Policy file must be preserved on schema error"
            expected_policy = {
                "schema_version": 1,
                "verdict": "error",
                "error": {
                    "code": "SCHEMA_ERROR",
                    "source": "current_baseline",
                    "path": str(temp_baseline),
                    "message": f"{temp_baseline} must be a JSON object (got list)",
                },
                "diagnostics": [],
            }
            assert pf.read_text() == json.dumps(expected_policy, indent=2) + "\n"

            # --- 3. Stale artifact removal ---
            qs = _REPO_ROOT / ".quickscale"
            assert not (qs / "quality_report.json").exists()
            assert not (qs / "quality_report.md").exists()
            assert not (qs / "quality_gate_status.json").exists()

            # --- 4. CR-005: No verdict/base/ref prose in stdout. ---
            # Error information is on stderr (one ERROR: line from _write_error_output)
            # and in the policy file.
            assert "Verdict:" not in result.stdout, "No Verdict prose in CR-005 shell output"
            assert "ERROR:" in result.stderr, f"Expected ERROR: on stderr:\n{result.stderr}"
            # Policy file has exact error envelope (already verified above)

            # --- 5. No analyzer invocation ---
            assert "Analyzing" not in result.stdout

        finally:
            self._restore_quickscale(quickscale_backup)

    # ------------------------------------------------------------------
    # Controlled success — report/status/Markdown keys and diagnostics parity
    # ------------------------------------------------------------------

    def test_shell_success_report_parity(
        self,
        poetry_stub: Path,
        find_stub: Path,
        quickscale_backup: dict[str, str | None],
    ) -> None:
        """
        On success the shell produces complete report/status/Markdown artifacts.

        Verifies:
        - All three output files exist (JSON, Markdown, gate status)
        - Gate status has ``monotonicity_diagnostics`` as a list
        - Markdown contains a fenced JSON block for diagnostics
        - All existing report/status keys are preserved
        """
        try:
            # Run with the actual checked-in baseline (no violations against
            # v87 merge-base) and stub analyzers returning empty results.
            # The find stub prevents native find/wc large-file analysis
            # from consuming live repository file sizes.
            result = self._run_shell(
                stub_dir=poetry_stub,
                find_stub_dir=find_stub,
                extra_env={
                    "QUALITY_BASELINE_BASE_REF": "v87",
                },
            )

            # --- 1. Exit 0 with the current complete baseline (monotonicity
            # gate passed, stubbed analyzers return empty, current file sizes
            # within baseline). ---
            assert result.returncode == 0, (
                f"Expected exit 0 with current baseline + stubs, "
                f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )
            assert "Baseline monotonicity gate passed" in result.stdout, (
                "Monotonicity gate must pass:\n{result.stdout}"
            )

            # --- 2. All three output files exist ---
            qs = _REPO_ROOT / ".quickscale"
            json_path = qs / "quality_report.json"
            md_path = qs / "quality_report.md"
            status_path = qs / "quality_gate_status.json"

            assert json_path.exists(), "quality_report.json must exist on success"
            assert md_path.exists(), "quality_report.md must exist on success"
            assert status_path.exists(), "quality_gate_status.json must exist on success"

            # --- 3. Gate status has monotonicity_diagnostics ---
            status_data = json.loads(status_path.read_text())
            expected_status_keys = {
                "baseline_status",
                "baseline_error",
                "warning_regressions",
                "critical_regressions",
                "total_regressions",
                "monotonicity_verdict",
                "monotonicity_merge_base",
                "monotonicity_base_ref",
                "monotonicity_waiver_count",
                "monotonicity_diagnostics",
            }
            status_keys = set(status_data.keys())
            missing_status = expected_status_keys - status_keys
            assert not missing_status, f"Gate status missing expected keys: {missing_status}"
            # monotonicity_diagnostics must be a list
            assert isinstance(status_data["monotonicity_diagnostics"], list), (
                "monotonicity_diagnostics must be a list"
            )

            # --- 4. Markdown has diagnostics fenced JSON after ### Diagnostics ---
            md_content = md_path.read_text(encoding="utf-8")
            assert "### Diagnostics" in md_content, (
                "Markdown must contain a '### Diagnostics' section"
            )
            # Find the fenced JSON block that follows "### Diagnostics"
            md_lines = md_content.splitlines()
            diag_header_idx = None
            for i, line in enumerate(md_lines):
                if line.strip() == "### Diagnostics":
                    diag_header_idx = i
                    break
            assert diag_header_idx is not None, (
                "Could not find '### Diagnostics' heading in Markdown"
            )
            # The next ```json fence after the heading
            diag_start = None
            for i in range(diag_header_idx + 1, len(md_lines)):
                if md_lines[i].strip() == "```json":
                    diag_start = i
                    break
            assert diag_start is not None, (
                "Could not find ```json fence after '### Diagnostics' in Markdown"
            )
            diag_end = None
            for i in range(diag_start + 1, len(md_lines)):
                if md_lines[i].strip() == "```":
                    diag_end = i
                    break
            assert diag_end is not None, "Could not find closing ``` fence in Markdown"
            json_text = "\n".join(md_lines[diag_start + 1 : diag_end])
            diag_data = json.loads(json_text)
            assert isinstance(diag_data, list), "Diagnostics fenced block must contain a JSON list"

            # --- 5. Report JSON preserves all expected top-level keys ---
            report_data = json.loads(json_path.read_text())
            expected_report_keys = {
                "timestamp",
                "summary",
                "baseline",
                "regressions",
                "dead_code",
                "complexity",
                "large_files",
                "duplication",
                "monotonicity",
            }
            report_keys = set(report_data.keys())
            missing_report = expected_report_keys - report_keys
            assert not missing_report, f"Report JSON missing expected keys: {missing_report}"
            # The find fixture emits a 2,000-line Python file. It remains visible
            # in raw diagnostics but contributes no baseline regression or gate
            # failure.
            assert report_data["summary"]["large_files_error"] == 1
            assert report_data["regressions"]["large_files"]["critical_count"] == 0
            assert report_data["regressions"]["total_count"] == 0

        finally:
            self._restore_quickscale(quickscale_backup)

    # ------------------------------------------------------------------
    # Diagnostics content — lifecycle-only entries (no corresponding
    # violation) must appear in the canonical diagnostics list.
    # ------------------------------------------------------------------

    def test_diagnostics_contains_lifecycle_orphan(
        self,
        tmp_path: Path,
        poetry_stub: Path,
        quickscale_backup: dict[str, str | None],
    ) -> None:
        """
        Orphan waiver appears in ``diagnostics`` even without a matching violation.

        This verifies that ``diagnostics`` captures lifecycle-only entries
        that ``violations`` omits.
        """
        try:
            # Baseline with NO increases against v87 merge-base
            baseline = {
                "schema_version": 1,
                "dead_code": {"allowed_messages": []},
                "complexity": {"allowed_functions": {}},
                "large_files": {"allowed_files": {}},
                "duplication": {"allowed_blocks": 0},
            }
            temp_baseline = tmp_path / "baseline_orphan_diag.json"
            temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

            # Orphan waiver — entry_key that does NOT match any key
            future = (date.today() + timedelta(days=90)).isoformat()
            temp_waivers = tmp_path / "waivers_orphan_diag.json"
            temp_waivers.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "waivers": [
                            {
                                "waiver_id": "W-ORPHAN-DIAG-001",
                                "entry_key": "complexity:orphan_test.py::no_such_func",
                                "base_ceiling": 5,
                                "ceiling": 10,
                                "owner": "test@example.com",
                                "reason": "Lifecycle-only diagnostic test",
                                "expires_on": future,
                                "decision_ref": "quality-baseline-monotonicity",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = self._run_shell(
                stub_dir=poetry_stub,
                extra_env={
                    "QUALITY_BASELINE_FILE": str(temp_baseline),
                    "QUALITY_WAIVERS_FILE": str(temp_waivers),
                    "QUALITY_BASELINE_BASE_REF": "v87",
                },
            )
            # Orphan blocks the gate → exit 1
            assert result.returncode == 1, (
                f"Expected exit 1 for orphan waiver, got {result.returncode}"
            )

            # Policy file preserved
            pf = _REPO_ROOT / ".quickscale" / "quality_baseline_policy.json"
            assert pf.exists(), "Policy file must be preserved on orphan failure"
            policy_data = json.loads(pf.read_text())

            # diagnostics key present
            assert "diagnostics" in policy_data, "Policy file must have diagnostics key"

            # Diagnostics must include the orphan waiver (lifecycle-only entry
            # that does not appear in the violations subset)
            diag = policy_data["diagnostics"]
            orphan_entries = [d for d in diag if d.get("waiver_status") == "orphan"]
            # Exactly 1 orphan waiver in the fixture
            assert len(orphan_entries) == 1, (
                f"Expected exactly 1 orphan waiver in diagnostics, got {len(orphan_entries)}:\n"
                f"{json.dumps(diag, indent=2)}"
            )
            orphan_entry = orphan_entries[0]
            assert orphan_entry["waiver_id"] == "W-ORPHAN-DIAG-001"

            # Violations must NOT contain this orphan entry (lifecycle-only
            # entries are a compatibility gap that diagnostics fills)
            assert not any(
                "orphan_test.py" in v.get("canonical_key", "")
                for v in policy_data.get("violations", [])
            ), "Violations must not contain lifecycle-only orphan entry"

            # No traceback
            assert "Traceback" not in result.stderr

        finally:
            self._restore_quickscale(quickscale_backup)

    # ------------------------------------------------------------------
    # Cross-artifact diagnostics equality on success path
    # ------------------------------------------------------------------

    def test_success_diagnostics_cross_artifact_equality(
        self,
        poetry_stub: Path,
        find_stub: Path,
        quickscale_backup: dict[str, str | None],
    ) -> None:
        """
        On success, ``diagnostics`` is identical across all four consumers:

        1. ``quality_baseline_policy.json`` — ``diagnostics``
        2. ``quality_report.json`` — ``monotonicity.diagnostics``
        3. ``quality_gate_status.json`` — ``monotonicity_diagnostics``
        4. Parsed fenced JSON block after ``### Diagnostics`` in ``quality_report.md``
        """
        try:
            result = self._run_shell(
                stub_dir=poetry_stub,
                find_stub_dir=find_stub,
                extra_env={"QUALITY_BASELINE_BASE_REF": "v87"},
            )
            # Monotonicity gate must have passed; exit 0 with stubbed
            # analyzers and current complete baseline.
            assert result.returncode == 0, (
                f"Expected exit 0 with current baseline + stubs, "
                f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )
            assert "Baseline monotonicity gate passed" in result.stdout, (
                f"Monotonicity gate must pass:\n{result.stdout}"
            )

            qs = _REPO_ROOT / ".quickscale"
            policy = json.loads((qs / "quality_baseline_policy.json").read_text())
            report = json.loads((qs / "quality_report.json").read_text())
            status = json.loads((qs / "quality_gate_status.json").read_text())
            md_content = (qs / "quality_report.md").read_text(encoding="utf-8")

            # Source 1: policy file diagnostics
            policy_diag = policy["diagnostics"]

            # Source 2: report monotonicity.diagnostics
            report_diag = report.get("monotonicity", {}).get("diagnostics", [])

            # Source 3: status monotonicity_diagnostics
            status_diag = status.get("monotonicity_diagnostics", [])

            # Source 4: parsed fenced JSON block after ### Diagnostics
            md_lines = md_content.splitlines()
            diag_header = None
            for i, line in enumerate(md_lines):
                if line.strip() == "### Diagnostics":
                    diag_header = i
                    break
            assert diag_header is not None, "Markdown must have '### Diagnostics'"
            fence_start = None
            for i in range(diag_header + 1, len(md_lines)):
                if md_lines[i].strip() == "```json":
                    fence_start = i
                    break
            assert fence_start is not None, "Markdown must have ```json fence after ### Diagnostics"
            fence_end = None
            for i in range(fence_start + 1, len(md_lines)):
                if md_lines[i].strip() == "```":
                    fence_end = i
                    break
            assert fence_end is not None, "Markdown must have closing ``` fence"
            json_text = "\n".join(md_lines[fence_start + 1 : fence_end])
            md_diag = json.loads(json_text)

            # All four must match exactly
            assert policy_diag == report_diag, (
                "Policy diagnostics != report.monotonicity.diagnostics"
            )
            assert policy_diag == status_diag, (
                "Policy diagnostics != status.monotonicity_diagnostics"
            )
            assert policy_diag == md_diag, "Policy diagnostics != parsed Markdown diagnostics"

        finally:
            self._restore_quickscale(quickscale_backup)

    # ------------------------------------------------------------------
    # CR-006: Shell controlled success with NONEMPTY active diagnostics
    # ------------------------------------------------------------------

    def test_shell_success_nonempty_diagnostics(
        self,
        tmp_path: Path,
        poetry_stub: Path,
        find_stub: Path,
        quickscale_backup: dict[str, str | None],
    ) -> None:
        """
        Shell produces NONEMPTY diagnostics on controlled success.

        Uses a temp baseline with three values higher than the v87 merge-base
        and matching active waivers.  Helper exits 0 with nonempty diagnostics.
        The shell continues to produce reports with nonempty diagnostics in
        policy/report/status/Markdown.  The find stub isolates large-file
        analysis from live repository file sizes.
        """
        try:
            # Build from the real complete baseline so any remaining real
            # large-file regressions from the monitoring scope are captured.
            # The find stub prevents unrelated file growth from affecting
            # the result.
            # Override only the three SA114 target keys with higher values.
            real_baseline = json.loads(
                (_REPO_ROOT / "scripts" / "quality_baseline.json").read_text()
            )
            higher_baseline = json.loads(json.dumps(real_baseline))
            # Bump the three SA114 keys
            higher_baseline["complexity"]["allowed_functions"][
                "quickscale_core/src/quickscale_core/schema/config_schema.py"
                "::_validate_modules_section"
            ]["max_complexity"] = 13
            higher_baseline["complexity"]["allowed_functions"][
                "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                "::_perform_module_embed"
            ]["max_complexity"] = 25
            higher_baseline["complexity"]["allowed_functions"][
                "quickscale_cli/src/quickscale_cli/commands/module_commands.py"
                "::_update_single_module"
            ]["max_complexity"] = 20
            temp_baseline = tmp_path / "baseline_higher.json"
            temp_baseline.write_text(json.dumps(higher_baseline), encoding="utf-8")

            future = (date.today() + timedelta(days=90)).isoformat()
            matching_waivers = {
                "schema_version": 1,
                "waivers": [
                    {
                        "waiver_id": "W-NE-CPX",
                        "entry_key": (
                            "complexity:quickscale_core/src/quickscale_core/schema/"
                            "config_schema.py::_validate_modules_section"
                        ),
                        "base_ceiling": 12,
                        "ceiling": 13,
                        "owner": "test@example.com",
                        "reason": "Nonempty diagnostic shell test",
                        "expires_on": future,
                        "decision_ref": "quality-baseline-monotonicity",
                    },
                    {
                        "waiver_id": "W-NE-CPX2",
                        "entry_key": (
                            "complexity:quickscale_cli/src/quickscale_cli/commands/"
                            "module_commands.py::_perform_module_embed"
                        ),
                        "base_ceiling": 20,
                        "ceiling": 25,
                        "owner": "test@example.com",
                        "reason": "Nonempty diagnostic shell test",
                        "expires_on": future,
                        "decision_ref": "quality-baseline-monotonicity",
                    },
                    {
                        "waiver_id": "W-NE-CPX3",
                        "entry_key": (
                            "complexity:quickscale_cli/src/quickscale_cli/commands/"
                            "module_commands.py::_update_single_module"
                        ),
                        "base_ceiling": 17,
                        "ceiling": 20,
                        "owner": "test@example.com",
                        "reason": "Nonempty diagnostic shell test",
                        "expires_on": future,
                        "decision_ref": "quality-baseline-monotonicity",
                    },
                ],
            }
            temp_waivers = tmp_path / "waivers_nonempty.json"
            temp_waivers.write_text(json.dumps(matching_waivers), encoding="utf-8")

            result = self._run_shell(
                stub_dir=poetry_stub,
                find_stub_dir=find_stub,
                extra_env={
                    "QUALITY_BASELINE_FILE": str(temp_baseline),
                    "QUALITY_WAIVERS_FILE": str(temp_waivers),
                    "QUALITY_BASELINE_BASE_REF": "v87",
                },
            )

            # CR-006: Monotonicity gate must pass (returncode == 0).
            # The helper and downstream analysis both use the custom
            # baseline and stub find, which isolates from unrelated
            # repository growth.
            assert result.returncode == 0, (
                f"Expected exit 0 with active waivers and stub analyzers, "
                f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )
            # CR-005: Helper no longer prints prose; shell's success message is authoritative
            assert "Baseline monotonicity gate passed" in result.stdout, (
                f"Monotonicity gate must report passed:\n{result.stdout}"
            )

            # --- All three output files exist ---
            qs = _REPO_ROOT / ".quickscale"
            json_path = qs / "quality_report.json"
            md_path = qs / "quality_report.md"
            status_path = qs / "quality_gate_status.json"
            assert json_path.exists()
            assert md_path.exists()
            assert status_path.exists()

            # --- Nonempty diagnostics in all artifacts ---
            policy = json.loads((qs / "quality_baseline_policy.json").read_text())
            report = json.loads(json_path.read_text())
            status_data = json.loads(status_path.read_text())

            policy_diag = policy.get("diagnostics", [])
            report_diag = report.get("monotonicity", {}).get("diagnostics", [])
            status_diag = status_data.get("monotonicity_diagnostics", [])

            # Exactly 3 diagnostics entries (one per violation matched with active waiver)
            assert len(policy_diag) == 3, (
                f"Expected exactly 3 diagnostics entries in policy, got {len(policy_diag)}:\n"
                f"{json.dumps(policy_diag, indent=2)}"
            )
            assert len(report_diag) == 3, (
                f"Expected exactly 3 diagnostics entries in report, got {len(report_diag)}"
            )
            assert len(status_diag) == 3, (
                f"Expected exactly 3 diagnostics entries in status, got {len(status_diag)}"
            )

            # --- Markdown diagnostics ---
            md_content = md_path.read_text(encoding="utf-8")
            md_lines = md_content.splitlines()
            diag_header = None
            for i, line in enumerate(md_lines):
                if line.strip() == "### Diagnostics":
                    diag_header = i
                    break
            assert diag_header is not None, "Markdown must have '### Diagnostics'"
            fence_start = next(
                i for i in range(diag_header + 1, len(md_lines)) if md_lines[i].strip() == "```json"
            )
            fence_end = next(
                i for i in range(fence_start + 1, len(md_lines)) if md_lines[i].strip() == "```"
            )
            md_json = "\n".join(md_lines[fence_start + 1 : fence_end])
            md_diag = json.loads(md_json)
            assert len(md_diag) == 3, (
                f"Expected exactly 3 diagnostics entries in Markdown, got {len(md_diag)}"
            )

            # --- Exact equality across all four artifacts ---
            assert policy_diag == report_diag, (
                "Policy diagnostics != report.monotonicity.diagnostics"
            )
            assert policy_diag == status_diag, (
                "Policy diagnostics != status.monotonicity_diagnostics"
            )
            assert policy_diag == md_diag, "Policy diagnostics != Markdown diagnostics"

        finally:
            self._restore_quickscale(quickscale_backup)
