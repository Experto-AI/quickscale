"""
Focused tests for ``check_coverage_policy.py``.

Test matrix
----------
* Passing data -- both thresholds met (equal-weight mean >= 90%, all files >= 80%)
* Mean below threshold -- equal-weight package mean drops below 90%
* File below threshold despite passing mean -- mean >= 90% but one file < 80%
* Opposite verdict -- equal-weight mean passes where weighted mean would not
* Missing package data -- empty file set / no recognised packages (exit 2)
* Unknown package path -- file outside ``quickscale_core/`` or ``quickscale_cli/`` (exit 2)
* Malformed input -- missing ``files`` key, invalid JSON, nonexistent path
* Summary validation errors -- missing/non-numeric/non-finite/negative/out-of-range
* Wiring / marker assertion -- ``make test-cov`` Phase behaviours
"""

from __future__ import annotations

import json
import math
import os
import tempfile

from scripts.check_coverage_policy import check_policy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cov_json(
    files: dict,
    totals: dict | None = None,
) -> str:
    """
    Write a temporary coverage.json and return its absolute path.

    Caller is responsible for calling ``_cleanup`` on the returned path.
    """
    if totals is None:
        totals = {"covered_lines": 0, "num_statements": 0}

    data: dict = {
        "meta": {"format": 1, "version": "7.x", "timestamp": "2026-01-01T00:00:00"},
        "files": files,
        "totals": totals,
    }

    fd, path = tempfile.mkstemp(suffix=".json", prefix="cov_test_")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def _cleanup(path: str) -> None:
    """Remove *path* if it exists."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckCoveragePolicy:
    """Coverage policy checker end-to-end tests."""

    # -- Passing -----------------------------------------------------------

    def test_passing_coverage(self) -> None:
        """Both thresholds met: equal-weight mean >= 90% and all files >= 80%."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/bar.py": {
                "summary": {
                    "covered_lines": 90,
                    "num_statements": 100,
                    "percent_covered": 90.0,
                },
            },
        }
        totals = {"covered_lines": 185, "num_statements": 200}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 0
        finally:
            _cleanup(path)

    # -- Mean failure ------------------------------------------------------

    def test_mean_below_threshold(self) -> None:
        """Equal-weight package mean is below 90%."""
        files = {
            "quickscale_core/src/low.py": {
                "summary": {
                    "covered_lines": 80,
                    "num_statements": 100,
                    "percent_covered": 80.0,
                },
            },
            "quickscale_cli/src/low.py": {
                "summary": {
                    "covered_lines": 75,
                    "num_statements": 100,
                    "percent_covered": 75.0,
                },
            },
        }
        totals = {"covered_lines": 155, "num_statements": 200}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 1
        finally:
            _cleanup(path)

    # -- Per-file failure --------------------------------------------------

    def test_file_below_threshold_despite_mean(self) -> None:
        """
        Mean passes (>=90%) but one file is below 80%.

        Two large files at 95% balance one small file at 70%, giving a
        passing mean but failing the per-file gate.
        """
        files = {
            "quickscale_core/src/high_a.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_core/src/high_b.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/low.py": {
                "summary": {
                    "covered_lines": 70,
                    "num_statements": 100,
                    "percent_covered": 70.0,
                },
            },
        }
        totals = {"covered_lines": 260, "num_statements": 300}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 1
        finally:
            _cleanup(path)

    # -- Opposite verdict: equal-weight vs weighted aggregate ------------

    def test_equal_weight_passes_where_weighted_would_fail(self) -> None:
        """
        Opposite-verdict fixture.

        One small package at 95% (200 stmts) and one large package at 89%
        (2000 stmts).  Weighted aggregate mean = ~89.5% (< 90%).  Equal-weight
        package mean = (95 + 89) / 2 = 92.0% (>= 90%).  This proves the helper
        uses per-package equal-weight arithmetic, not statement weighting.
        """
        files = {
            "quickscale_core/src/small.py": {
                "summary": {
                    "covered_lines": 190,
                    "num_statements": 200,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/large.py": {
                "summary": {
                    "covered_lines": 1780,
                    "num_statements": 2000,
                    "percent_covered": 89.0,
                },
            },
        }
        totals = {"covered_lines": 1970, "num_statements": 2200}
        path = _make_cov_json(files, totals)
        try:
            # Equal-weight: (95% + 89%) / 2 = 92.0% -> passes 90% threshold
            assert check_policy(path) == 0
        finally:
            _cleanup(path)

    # -- Missing / empty data ----------------------------------------------

    def test_empty_files_dict(self) -> None:
        """Empty ``files`` dict returns exit 2 (data error)."""
        files: dict = {}
        totals = {"covered_lines": 0, "num_statements": 0}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    # -- Unknown package path ----------------------------------------------

    def test_unknown_package_path_fails_closed(self) -> None:
        """A file outside recognised packages should exit 2."""
        files = {
            "some_other_pkg/mod.py": {
                "summary": {
                    "covered_lines": 50,
                    "num_statements": 100,
                    "percent_covered": 50.0,
                },
            },
        }
        totals = {"covered_lines": 50, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_unknown_package_mixed_with_known(self) -> None:
        """An unknown file among known packages still exits 2."""
        files = {
            "quickscale_core/src/ok.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/ok.py": {
                "summary": {
                    "covered_lines": 90,
                    "num_statements": 100,
                    "percent_covered": 90.0,
                },
            },
            "vendor/third_party.py": {
                "summary": {
                    "covered_lines": 50,
                    "num_statements": 100,
                    "percent_covered": 50.0,
                },
            },
        }
        totals = {"covered_lines": 235, "num_statements": 300}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    # -- Malformed input ---------------------------------------------------

    def test_missing_files_key(self) -> None:
        """JSON missing the ``files`` key returns exit 2."""
        fd, path = tempfile.mkstemp(suffix=".json", prefix="cov_test_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"meta": {}, "totals": {}}, fh)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_missing_totals_key(self) -> None:
        """JSON missing the ``totals`` key returns exit 2."""
        fd, path = tempfile.mkstemp(suffix=".json", prefix="cov_test_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"meta": {}, "files": {}}, fh)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_invalid_json(self) -> None:
        """Completely invalid JSON returns exit 2."""
        fd, path = tempfile.mkstemp(suffix=".json", prefix="cov_test_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("this is not valid json {{{")
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_nonexistent_file(self) -> None:
        """Nonexistent path returns exit 2."""
        result = check_policy("/tmp/___nonexistent_cov_file___.json")
        assert result == 2

    # -- Summary validation (fail-closed) ----------------------------------

    def test_missing_summary_fails_closed(self) -> None:
        """File entry without a summary dict exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/bar.py": {
                "not_summary": "broken",
            },
        }
        totals = {"covered_lines": 95, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_non_numeric_covered_lines_fails_closed(self) -> None:
        """Non-numeric covered_lines exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": "ninety",
                    "num_statements": 100,
                    "percent_covered": 90.0,
                },
            },
        }
        totals = {"covered_lines": 0, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_non_finite_percent_fails_closed(self) -> None:
        """NaN or Inf percent_covered exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 90,
                    "num_statements": 100,
                    "percent_covered": math.nan,
                },
            },
        }
        totals = {"covered_lines": 90, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_negative_statements_fails_closed(self) -> None:
        """Negative num_statements exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 0,
                    "num_statements": -10,
                    "percent_covered": 0.0,
                },
            },
        }
        totals = {"covered_lines": 0, "num_statements": -10}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_covered_exceeds_statements_fails_closed(self) -> None:
        """covered_lines > num_statements exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 200,
                    "num_statements": 100,
                    "percent_covered": 200.0,
                },
            },
        }
        totals = {"covered_lines": 200, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_missing_covered_lines_fails_closed(self) -> None:
        """Missing covered_lines key in summary exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "num_statements": 100,
                    "percent_covered": 90.0,
                },
            },
        }
        totals = {"covered_lines": 0, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    # -- Non-dict root ----------------------------------------------------

    def test_null_root_fails_closed(self) -> None:
        """Coverage JSON with null root returns exit 2."""
        fd, path = tempfile.mkstemp(suffix=".json", prefix="cov_test_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(None, fh)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_array_root_fails_closed(self) -> None:
        """Coverage JSON with array root returns exit 2."""
        fd, path = tempfile.mkstemp(suffix=".json", prefix="cov_test_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([], fh)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_string_root_fails_closed(self) -> None:
        """Coverage JSON with string root returns exit 2."""
        fd, path = tempfile.mkstemp(suffix=".json", prefix="cov_test_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump("oops", fh)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    # -- Non-dict file records --------------------------------------------

    def test_non_dict_file_entry_null_fails_closed(self) -> None:
        """File entry that is null exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/bar.py": None,
        }
        totals = {"covered_lines": 95, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_non_dict_file_entry_list_fails_closed(self) -> None:
        """File entry that is a list exits 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/bar.py": [1, 2, 3],
        }
        totals = {"covered_lines": 95, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    # -- Missing required package -----------------------------------------

    def test_missing_core_package_fails_closed(self) -> None:
        """Coverage data without quickscale_core files exits 2."""
        files = {
            "quickscale_cli/src/only.py": {
                "summary": {
                    "covered_lines": 90,
                    "num_statements": 100,
                    "percent_covered": 90.0,
                },
            },
        }
        totals = {"covered_lines": 90, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_missing_cli_package_fails_closed(self) -> None:
        """Coverage data without quickscale_cli files exits 2."""
        files = {
            "quickscale_core/src/only.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
        }
        totals = {"covered_lines": 95, "num_statements": 100}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    # -- Non-canonical traversal paths ------------------------------------

    def test_parent_traversal_path_rejected(self) -> None:
        """Path with ``..`` traversal is rejected with exit 2."""
        files = {
            "quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_core/../quickscale_cli/src/bar.py": {
                "summary": {
                    "covered_lines": 90,
                    "num_statements": 100,
                    "percent_covered": 90.0,
                },
            },
        }
        totals = {"covered_lines": 185, "num_statements": 200}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    def test_self_reference_path_rejected(self) -> None:
        """Path with ``./`` self-reference is rejected with exit 2."""
        files = {
            "./quickscale_core/src/foo.py": {
                "summary": {
                    "covered_lines": 95,
                    "num_statements": 100,
                    "percent_covered": 95.0,
                },
            },
            "quickscale_cli/src/bar.py": {
                "summary": {
                    "covered_lines": 90,
                    "num_statements": 100,
                    "percent_covered": 90.0,
                },
            },
        }
        totals = {"covered_lines": 185, "num_statements": 200}
        path = _make_cov_json(files, totals)
        try:
            assert check_policy(path) == 2
        finally:
            _cleanup(path)

    # -- Wiring / marker assertion ----------------------------------------

    def test_makefile_uses_not_e2e_marker(self) -> None:
        """
        Makefile ``test-cov`` target uses ``-m "not e2e"`` marker.

        Behavioural contract test: ``make test-cov`` must exclude only E2E
        tests (not integration tests) so the combined coverage measurement
        includes both unit and integration-tagged tests from core and CLI
        directories.
        """
        repo_root = os.path.join(os.path.dirname(__file__), "..")
        makefile = os.path.join(repo_root, "Makefile")
        with open(makefile, encoding="utf-8") as fh:
            content = fh.read()

        # Find the test-cov target section
        cov_section_start = content.find("test-cov:")
        assert cov_section_start >= 0, "Makefile must have a test-cov target"

        # Search for marker in the target recipe lines
        section = content[cov_section_start:]
        found = False
        for line in section.split("\n"):
            if '-m "not e2e"' in line:
                found = True
                break

        assert found, (
            "test-cov target must include '-m \"not e2e\"' to include "
            "integration-tagged tests in the coverage measurement"
        )


class TestMakefileCoveragePipeline:
    """Bounded behavioural assertions for the ``make test-cov`` pipeline."""

    MAKEFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "Makefile")

    def _read_makefile_section(self, anchor: str) -> str:
        """Return the Makefile from *anchor* to the next target."""
        with open(self.MAKEFILE_PATH, encoding="utf-8") as fh:
            content = fh.read()
        start = content.find(f"\n{anchor}:")
        if start == -1:
            start = content.find(f"{anchor}:")
        assert start >= 0, f"Target {anchor!r} not found in Makefile"
        # Read until next target at column 0
        remainder = content[start:]
        end = remainder.find("\n\n#")
        if end == -1:
            end = len(remainder)
        return remainder[:end]

    def test_phase1_uses_fail_under_zero(self) -> None:
        """Phase 1 uses ``--cov-fail-under=0`` to defer threshold to helper."""
        section = self._read_makefile_section("test-cov")
        assert "--cov-fail-under=0" in section, (
            "Phase 1 must use --cov-fail-under=0 to defer statement-weighted "
            "threshold enforcement to the Phase 4 policy helper"
        )

    def test_phase2_uses_cov_append(self) -> None:
        """Phase 2 uses ``--cov-append`` to augment the combined measurement."""
        section = self._read_makefile_section("test-cov")
        assert "--cov-append" in section, (
            "Phase 2 must use --cov-append so the backups-module run "
            "contributes to the same combined .coverage file"
        )

    def test_phase3_fail_under_zero(self) -> None:
        """Phase 3 coverage report uses ``--fail-under=0`` (deferred)."""
        section = self._read_makefile_section("test-cov")
        assert "--fail-under=0" in section, (
            "Phase 3 (coverage report) must use --fail-under=0 so the "
            "policy helper in Phase 4 is the sole authority"
        )

    def test_phase4_invokes_policy_helper(self) -> None:
        """Phase 4 invokes ``check_coverage_policy.py``."""
        section = self._read_makefile_section("test-cov")
        assert "check_coverage_policy.py" in section, (
            "Phase 4 must invoke check_coverage_policy.py for policy enforcement"
        )

    def test_phase1_failure_propagates(self) -> None:
        """Phase 1 exit code propagates to ``overall_exit``."""
        section = self._read_makefile_section("test-cov")
        assert "overall_exit=$$phase1_exit" in section.replace(" ", "").replace("\t", ""), (
            "Phase 1 failure must propagate to overall_exit"
        )

    def test_phase4_failure_propagates(self) -> None:
        """Phase 4 exit code propagates when overall_exit is still 0."""
        section = self._read_makefile_section("test-cov")
        assert "overall_exit=$$policy_exit" in section.replace(" ", "").replace("\t", ""), (
            "Phase 4 failure must set overall_exit when it is still 0"
        )


class TestCheckCILocallyStageNumbering:
    """Structural assertions for ``check_ci_locally.sh`` stage numbering."""

    SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "check_ci_locally.sh")

    def _read_script(self) -> str:
        with open(self.SCRIPT_PATH, encoding="utf-8") as fh:
            return fh.read()

    def test_has_total_stages_variable(self) -> None:
        """Script defines a TOTAL_STAGES variable for dynamic stage counting."""
        content = self._read_script()
        assert "TOTAL_STAGES=" in content, (
            "Script must define TOTAL_STAGES for dynamic stage numbering"
        )

    def test_no_hardcoded_denominators(self) -> None:
        """
        No main-stage echos use hardcoded ``[N/11]`` or ``[N/12]``.

        All stage-numbered echos must use ``${TOTAL_STAGES}`` so the
        denominator adapts to --e2e vs non-E2E mode.
        """
        content = self._read_script()
        for line in content.splitlines():
            stripped = line.strip()
            # Only look at echo lines that appear to be stage headers
            if stripped.startswith("echo ") and "[1/" in stripped:
                # Assert no hardcoded /11 or /12
                assert "/11" not in stripped, f"Hardcoded /11 denominator found: {stripped!r}"
                assert "/12" not in stripped, f"Hardcoded /12 denominator found: {stripped!r}"

    def test_e2e_skip_message_unnumbered(self) -> None:
        """The E2E-skip message (non-E2E path) has no stage-number prefix."""
        content = self._read_script()
        found = False
        for line in content.splitlines():
            if "Skipping E2E tests" in line and "echo" in line:
                assert "[" not in line, (
                    f"E2E-skip message must not have a stage-number prefix: {line.strip()!r}"
                )
                found = True
        assert found, "E2E-skip echo message not found"

    def test_e2e_stage_uses_variable_denominator(self) -> None:
        """The E2E test stage header uses ``${TOTAL_STAGES}`` for its denominator."""
        content = self._read_script()
        found_dynamic = False
        for line in content.splitlines():
            if "Running E2E tests" in line and "echo" in line:
                # Must use ${TOTAL_STAGES} not a hardcoded number
                assert "${TOTAL_STAGES}" in line, (
                    f"E2E stage header must use ${{TOTAL_STAGES}}, got: {line.strip()!r}"
                )
                found_dynamic = True
        assert found_dynamic, "E2E stage header echo not found"
