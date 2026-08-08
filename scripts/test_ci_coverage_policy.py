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
import subprocess
import tempfile
import textwrap
from pathlib import Path

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

    def _write_fake_tools(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Create deterministic Python and PostgreSQL fakes for recipe tests."""
        fake_python = tmp_path / "fake_python.py"
        event_log = tmp_path / "events.jsonl"
        fake_python.write_text(
            textwrap.dedent(
                """
                #!/usr/bin/env python3
                import json
                import os
                from pathlib import Path
                import signal
                import sys

                args = sys.argv[1:]
                log_path = Path(os.environ["FAKE_LOG"])

                def event(kind, **fields):
                    with log_path.open("a", encoding="utf-8") as stream:
                        json.dump({"kind": kind, **fields}, stream)
                        stream.write("\\n")

                event(
                    "invoke",
                    args=args,
                    coverage_file=os.environ.get("COVERAGE_FILE"),
                    cwd=os.getcwd(),
                )

                if args[:1] == ["-c"]:
                    raise SystemExit(int(os.environ.get("FAKE_PG_EXIT", "1")))

                if args[:2] == ["-m", "pytest"]:
                    coverage_file = os.environ["COVERAGE_FILE"]
                    phase = "phase2" if "phase2" in coverage_file else "phase1"
                    event(
                        "pytest",
                        phase=phase,
                        args=args,
                        coverage_file=coverage_file,
                    )
                    if os.environ.get("FAKE_SIGNAL") == phase:
                        os.kill(os.getppid(), signal.SIGTERM)
                        raise SystemExit(0)
                    if not (
                        phase == "phase2"
                        and os.environ.get("FAKE_NO_PHASE2_FILE") == "1"
                    ):
                        Path(coverage_file).write_text(phase, encoding="utf-8")
                    raise SystemExit(
                        int(os.environ.get(f"FAKE_{phase.upper()}_EXIT", "0"))
                    )

                if args[:2] == ["-m", "coverage"]:
                    command = args[2]
                    event("coverage", command=command, args=args)
                    if command == "combine":
                        data_file = next(
                            arg.split("=", 1)[1]
                            for arg in args
                            if arg.startswith("--data-file=")
                        )
                        event(
                            "combine_inputs",
                            data_file=data_file,
                            input_dir=args[-1],
                        )
                        Path(data_file).write_text("combined", encoding="utf-8")
                    elif command == "json":
                        Path("coverage.json").write_text("{}", encoding="utf-8")
                    raise SystemExit(
                        int(
                            os.environ.get(
                                f"FAKE_COVERAGE_{command.upper()}_EXIT", "0"
                            )
                        )
                    )

                if args and args[0].endswith("check_coverage_policy.py"):
                    event("policy", args=args)
                    raise SystemExit(int(os.environ.get("FAKE_POLICY_EXIT", "0")))

                raise SystemExit(f"unexpected fake Python invocation: {args!r}")
                """
            ).lstrip(),
            encoding="utf-8",
        )
        fake_python.chmod(0o755)

        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        for tool in ("pg_dump", "pg_restore"):
            tool_path = fake_bin / tool
            tool_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool_path.chmod(0o755)
        return fake_python, event_log, fake_bin

    def _run_pipeline(
        self,
        tmp_path: Path,
        *,
        pg_exit: int = 1,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[dict], Path]:
        """Run the actual Make recipe against bounded fake tools."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        fake_python, event_log, fake_bin = self._write_fake_tools(tmp_path)
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        root_coverage = work_dir / ".coverage"
        root_coverage.write_text("unrelated-root-data", encoding="utf-8")
        temp_dir = tmp_path / "system-tmp"
        temp_dir.mkdir()

        env = os.environ.copy()
        for key in ("REQUIRE_BACKUPS_COVERAGE", "PYTEST_XDIST_WORKERS"):
            env.pop(key, None)
        env.update(
            {
                "FAKE_LOG": str(event_log),
                "FAKE_PG_EXIT": str(pg_exit),
                "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                "TMPDIR": str(temp_dir),
            }
        )
        if extra_env:
            env.update(extra_env)

        result = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "-f",
                self.MAKEFILE_PATH,
                f"PYTHON={fake_python}",
                "test-cov",
            ],
            cwd=work_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
        return result, events, work_dir

    @staticmethod
    def _pytest_events(events: list[dict]) -> list[dict]:
        """Return only fake pytest invocations, excluding the DB probe."""
        return [event for event in events if event["kind"] == "pytest"]

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
        """Both isolated phases defer threshold enforcement to the helper."""
        section = self._read_makefile_section("test-cov")
        assert section.count("--cov-fail-under=0") == 2

    def test_phases_use_isolated_coverage_files(self) -> None:
        """Each test phase writes to its own coverage data file."""
        section = self._read_makefile_section("test-cov")
        assert 'phase1_file="$$coverage_dir/combined.phase1"' in section
        assert 'phase2_file="$$coverage_dir/combined.phase2"' in section
        assert 'COVERAGE_FILE="$$phase1_file"' in section
        assert 'COVERAGE_FILE="$$phase2_file"' in section
        assert "--cov-append" not in section, (
            "Coverage phases must not append to a shared data file"
        )

    def test_phases_forward_xdist_args(self) -> None:
        """Both coverage phases inherit the configured xdist arguments."""
        section = self._read_makefile_section("test-cov")
        assert section.count("$(PYTEST_XDIST_ARGS)") == 2

    def test_combines_once_before_reports(self) -> None:
        """One explicit combine feeds all coverage reports."""
        section = self._read_makefile_section("test-cov")
        combine_lines = [
            line for line in section.splitlines() if "$(PYTHON) -m coverage combine" in line
        ]
        assert len(combine_lines) == 1
        combine_index = section.index("coverage combine")
        for report in ("coverage html", "coverage report", "coverage json"):
            assert section.index(report) > combine_index
        assert section.count('--data-file="$$combined_file"') == 4

    def test_coverage_temp_dir_has_cleanup_and_signal_traps(self) -> None:
        """Per-run coverage state is cleaned up on normal and signal exits."""
        section = self._read_makefile_section("test-cov")
        assert "coverage_dir=$$(mktemp -d " in section
        assert "trap cleanup_coverage EXIT" in section
        assert "trap 'exit 130' INT" in section
        assert "trap 'exit 143' TERM" in section
        assert "trap 'exit 129' HUP" in section

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
        """Phase 1 exit code is recorded as the first pipeline failure."""
        section = self._read_makefile_section("test-cov")
        assert 'record_failure "$$phase1_exit"' in section, (
            "Phase 1 failure must be recorded in overall_exit"
        )

    def test_phase4_failure_propagates(self) -> None:
        """Phase 4 exit code is recorded without replacing an earlier failure."""
        section = self._read_makefile_section("test-cov")
        assert 'record_failure "$$policy_exit"' in section, (
            "Phase 4 failure must be recorded in overall_exit"
        )

    def test_first_failure_is_retained_when_combine_fails(self, tmp_path: Path) -> None:
        """A later combine failure must not replace the Phase 1 test failure."""
        result, events, _ = self._run_pipeline(
            tmp_path,
            extra_env={
                "FAKE_PHASE1_EXIT": "7",
                "FAKE_COVERAGE_COMBINE_EXIT": "9",
            },
        )

        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "Error 7" in output
        assert "Error 9" not in output
        assert any(event["kind"] == "combine_inputs" for event in events)

    def test_first_failure_is_retained_when_policy_fails(self, tmp_path: Path) -> None:
        """A later policy failure must not replace the Phase 1 test failure."""
        result, events, _ = self._run_pipeline(
            tmp_path,
            extra_env={
                "FAKE_PHASE1_EXIT": "7",
                "FAKE_POLICY_EXIT": "5",
            },
        )

        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "Error 7" in output
        assert "Error 5" not in output
        assert any(event["kind"] == "policy" for event in events)

    def test_policy_failure_is_captured(self, tmp_path: Path) -> None:
        """A policy failure is captured after reports and returned by the recipe."""
        result, events, _ = self._run_pipeline(
            tmp_path,
            extra_env={"FAKE_POLICY_EXIT": "5"},
        )

        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "Error 5" in output
        assert any(event["kind"] == "policy" for event in events)

    def test_combine_uses_only_isolated_phase_inputs(self, tmp_path: Path) -> None:
        """Both phase files feed one combined output, not the root data file."""
        result, events, work_dir = self._run_pipeline(tmp_path, pg_exit=0)

        assert result.returncode == 0
        pytest_events = self._pytest_events(events)
        phase_files = [event["coverage_file"] for event in pytest_events]
        assert len(phase_files) == 2
        assert len(set(phase_files)) == 2
        assert {Path(path).name for path in phase_files} == {
            "combined.phase1",
            "combined.phase2",
        }

        combine_events = [event for event in events if event["kind"] == "combine_inputs"]
        assert len(combine_events) == 1
        combine = combine_events[0]
        assert Path(combine["input_dir"]) == Path(phase_files[0]).parent
        assert Path(combine["data_file"]).name == "combined"
        assert Path(combine["data_file"]).parent == Path(phase_files[0]).parent
        assert (work_dir / ".coverage").read_text(encoding="utf-8") == "unrelated-root-data"

    def test_optional_backups_unavailable_remains_successful(self, tmp_path: Path) -> None:
        """The standalone target still skips unavailable optional backups coverage."""
        result, events, _ = self._run_pipeline(tmp_path, pg_exit=1)

        assert result.returncode == 0
        assert "skipping module coverage (backups)" in result.stdout
        assert not any(event["kind"] == "pytest" and event["phase"] == "phase2" for event in events)

    def test_required_backups_unavailable_fails_without_combine(self, tmp_path: Path) -> None:
        """Required backups coverage fails closed and does not run partial reports."""
        result, events, _ = self._run_pipeline(
            tmp_path,
            pg_exit=1,
            extra_env={
                "FAKE_PHASE1_EXIT": "7",
                "REQUIRE_BACKUPS_COVERAGE": "1",
            },
        )

        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "Error 7" in output
        assert "Error 1" not in output
        assert "REQUIRE_BACKUPS_COVERAGE is set" in output
        assert not any(event["kind"] == "combine_inputs" for event in events)

    def test_required_backups_missing_artifact_fails_before_combine(self, tmp_path: Path) -> None:
        """A required phase without its data file cannot enter Phase 3."""
        result, events, _ = self._run_pipeline(
            tmp_path,
            pg_exit=0,
            extra_env={
                "FAKE_NO_PHASE2_FILE": "1",
                "REQUIRE_BACKUPS_COVERAGE": "1",
            },
        )

        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "Expected coverage data file is missing" in output
        assert not any(event["kind"] == "combine_inputs" for event in events)

    def test_xdist_and_serial_arguments_reach_both_phases(self, tmp_path: Path) -> None:
        """Configured xdist arguments reach both phases, with serial opt-out."""
        parallel_result, parallel_events, _ = self._run_pipeline(
            tmp_path / "parallel",
            pg_exit=0,
            extra_env={"PYTEST_XDIST_WORKERS": "2"},
        )
        serial_result, serial_events, _ = self._run_pipeline(
            tmp_path / "serial",
            pg_exit=0,
            extra_env={"PYTEST_XDIST_WORKERS": "0"},
        )

        assert parallel_result.returncode == 0
        assert serial_result.returncode == 0
        for event in self._pytest_events(parallel_events):
            worker_index = event["args"].index("-n")
            assert event["args"][worker_index : worker_index + 4] == [
                "-n",
                "2",
                "--dist",
                "loadfile",
            ]
        for event in self._pytest_events(serial_events):
            assert "-n" not in event["args"]

    def test_normal_cleanup_removes_isolated_directory(self, tmp_path: Path) -> None:
        """The EXIT trap removes the temporary coverage directory."""
        result, events, _ = self._run_pipeline(tmp_path)

        assert result.returncode == 0
        phase1 = next(event for event in self._pytest_events(events) if event["phase"] == "phase1")
        assert not Path(phase1["coverage_file"]).parent.exists()

    def test_term_cleanup_removes_isolated_directory(self, tmp_path: Path) -> None:
        """A trapped TERM exits and still removes the temporary directory."""
        result, events, _ = self._run_pipeline(
            tmp_path,
            extra_env={"FAKE_SIGNAL": "phase1"},
        )

        output = result.stdout + result.stderr
        phase1 = next(event for event in self._pytest_events(events) if event["phase"] == "phase1")
        assert result.returncode != 0
        assert "Error 143" in output
        assert not Path(phase1["coverage_file"]).parent.exists()


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


class TestCheckQuietSectionDispatch:
    """
    Bounded behavioral assertions for ``make check QUIET=1`` section dispatch.

    Each test runs ``make check QUIET=1`` with a fake Python that logs every
    invocation and exits 0, plus a no-op ``MAKE=true`` override so gate targets
    (check-core-compat, etc.) are silently skipped.  This captures which
    source, test, and module directories are actually passed to ruff, mypy,
    and pytest for a given SECTIONS value.
    """

    MAKEFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "Makefile")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write_fake_python(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a deterministic fake Python that logs invocations and exits 0."""
        fake_python = tmp_path / "fake_python.py"
        event_log = tmp_path / "events.jsonl"
        fake_python.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import json, os, sys
                from pathlib import Path

                log_path = Path(os.environ["FAKE_LOG"])
                args = sys.argv[1:]
                with log_path.open("a", encoding="utf-8") as stream:
                    json.dump({"kind": "invoke", "args": args}, stream)
                    stream.write("\\n")
                raise SystemExit(0)
            """).lstrip(),
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        return fake_python, event_log

    @staticmethod
    def _write_fake_node_pnpm(bin_dir: Path) -> None:
        """
        Create fake ``node`` and ``pnpm`` executables that exit 0.

        Callers create a temporary directory, pass it here, then prepend it
        to ``PATH`` so the Makefile's ``command -v`` guard finds them.
        """
        bin_dir.mkdir(parents=True, exist_ok=True)
        for tool in ("node", "pnpm"):
            tool_path = bin_dir / tool
            tool_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool_path.chmod(0o755)

    @staticmethod
    def _write_fake_node_only(bin_dir: Path) -> None:
        """Create a fake ``node`` executable that exits 0."""
        bin_dir.mkdir(parents=True, exist_ok=True)
        tool_path = bin_dir / "node"
        tool_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool_path.chmod(0o755)

    @staticmethod
    def _write_fake_pnpm_only(bin_dir: Path) -> None:
        """Create a fake ``pnpm`` executable that exits 0."""
        bin_dir.mkdir(parents=True, exist_ok=True)
        tool_path = bin_dir / "pnpm"
        tool_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool_path.chmod(0o755)

    def _write_fake_make(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """
        Create a deterministic fake make that logs targets to a JSONL file.

        The fake make exits 1 when ``FAKE_MAKE_FAIL_TARGET`` is set and the
        requested target matches; otherwise exits 0.  Returns the path to the
        script, the event-log path, and a shell-wrapper path that sets the
        required environment variable before invoking the real script.
        """
        script = tmp_path / "fake_make.py"
        event_log = tmp_path / "make_events.jsonl"
        script.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import json, os, sys
                from pathlib import Path

                log_path = Path(os.environ["FAKE_MAKE_LOG"])
                target = sys.argv[1] if len(sys.argv) > 1 else ""
                with log_path.open("a", encoding="utf-8") as stream:
                    json.dump({"kind": "make", "target": target}, stream)
                    stream.write("\\n")
                fail_target = os.environ.get("FAKE_MAKE_FAIL_TARGET", "")
                if fail_target and target == fail_target:
                    print(
                        f"FAKE_MAKE: target '{target}' failed "
                        f"(FAKE_MAKE_FAIL_TARGET={fail_target})",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                sys.exit(0)
            """).lstrip(),
            encoding="utf-8",
        )
        script.chmod(0o755)

        # Shell wrapper ensures FAKE_MAKE_LOG is always set
        wrapper = tmp_path / "fake_make.sh"
        wrapper.write_text(
            textwrap.dedent(f"""\
                #!/bin/sh
                export FAKE_MAKE_LOG="{event_log}"
                exec "{script}" "$@"
            """).lstrip(),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)

        return script, event_log, wrapper

    def _run_quiet_check(
        self,
        tmp_path: Path,
        *,
        sections: str = "",
        module: str = "",
        make_override: str | None = None,
        shell_override: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
        """
        Run ``make check QUIET=1`` with fake Python and no-op sub-make.

        When *shell_override* is set, it is passed as ``SHELL`` to make so
        ``command -v`` behaviour can be controlled for absent-tool tests.
        """
        fake_python, event_log = self._write_fake_python(tmp_path)

        env = os.environ.copy()
        for key in ("SECTIONS", "SECTION", "MODULE", "PYTEST_XDIST_WORKERS"):
            env.pop(key, None)
        env["FAKE_LOG"] = str(event_log)
        if extra_env:
            env.update(extra_env)

        make_value = make_override if make_override is not None else "true"
        cmd = [
            "make",
            "--no-print-directory",
            "-f",
            self.MAKEFILE_PATH,
            f"PYTHON={fake_python}",
            f"MAKE={make_value}",
            "QUIET=1",
        ]
        if shell_override:
            cmd.append(f"SHELL={shell_override}")
        if sections:
            cmd.append(f"SECTIONS={sections}")
        if module:
            cmd.append(f"MODULE={module}")
        cmd.append("check")

        result = subprocess.run(
            cmd,
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        events: list[dict] = []
        if event_log.exists() and event_log.stat().st_size > 0:
            with event_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        return result, events

    @staticmethod
    def _ruff_check_invocations(events: list[dict]) -> list[list[str]]:
        """Return args for each ``ruff check`` invocation."""
        return [e["args"] for e in events if "ruff" in e["args"] and "check" in e["args"]]

    @staticmethod
    def _ruff_format_invocations(events: list[dict]) -> list[list[str]]:
        """Return args for each ``ruff format --check`` invocation."""
        return [e["args"] for e in events if "ruff" in e["args"] and "format" in e["args"]]

    @staticmethod
    def _mypy_invocations(events: list[dict]) -> list[list[str]]:
        """Return args for each ``mypy --show-error-codes`` invocation."""
        return [e["args"] for e in events if "mypy" in e["args"]]

    @staticmethod
    def _pytest_invocations(events: list[dict]) -> list[list[str]]:
        """Return args for each ``pytest`` invocation."""
        return [e["args"] for e in events if "pytest" in e["args"]]

    # ------------------------------------------------------------------
    # Default (all sections)
    # ------------------------------------------------------------------

    def test_default_all_sections_uses_all_dirs(self, tmp_path: Path) -> None:
        """Default QUIET=1 includes all source and test dirs."""
        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0, (
            f"make check QUIET=1 (default) failed: {result.stdout}\n{result.stderr}"
        )

        ruff_check = self._ruff_check_invocations(events)
        ruff_check_str = " ".join(" ".join(a) for a in ruff_check)
        assert "quickscale/src" in ruff_check_str
        assert "quickscale_core/src" in ruff_check_str
        assert "quickscale_cli/src" in ruff_check_str
        assert "quickscale_devtools/src" in ruff_check_str

        pytest_calls = self._pytest_invocations(events)
        pytest_str = " ".join(" ".join(a) for a in pytest_calls)
        assert "quickscale_core/tests" in pytest_str
        assert "quickscale_cli/tests" in pytest_str

    def test_default_includes_modules_when_present(self, tmp_path: Path) -> None:
        """Default QUIET=1 with a real module dir present runs module ruff/mypy."""
        mod_dir = tmp_path / "quickscale_modules" / "testmod" / "src"
        mod_dir.mkdir(parents=True)
        (mod_dir / "__init__.py").write_text("", encoding="utf-8")

        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0

        ruff_check = self._ruff_check_invocations(events)
        ruff_str = " ".join(" ".join(a) for a in ruff_check)
        # Make variable expansion uses relative paths (from cwd)
        assert "quickscale_modules/testmod/src" in ruff_str

        mypy_calls = self._mypy_invocations(events)
        mypy_str = " ".join(" ".join(a) for a in mypy_calls)
        assert "quickscale_modules/testmod/src" in mypy_str

    # ------------------------------------------------------------------
    # Modules-only
    # ------------------------------------------------------------------

    def test_modules_only_skips_pytest(self, tmp_path: Path) -> None:
        """Modules-only QUIET=1 does not run pytest (no core/cli test dirs)."""
        result, events = self._run_quiet_check(tmp_path, sections="modules")
        assert result.returncode == 0, (
            f"make check QUIET=1 SECTIONS=modules failed: {result.stdout}\n{result.stderr}"
        )

        # Should have no pytest invocations
        pytest_calls = self._pytest_invocations(events)
        assert len(pytest_calls) == 0, (
            f"modules-only QUIET=1 must skip pytest; got invocations: {pytest_calls}"
        )

        # Should have ruff runs but only for module dirs, not core/cli
        ruff_check = self._ruff_check_invocations(events)
        ruff_str = " ".join(" ".join(a) for a in ruff_check)
        assert "quickscale_core/src" not in ruff_str, (
            "modules-only QUIET=1 must not include core src"
        )

    def test_modules_only_runs_module_mypy_with_mypypath(self, tmp_path: Path) -> None:
        """Modules-only QUIET=1 runs per-module mypy with MYPYPATH."""
        mod_a = tmp_path / "quickscale_modules" / "mod_a" / "src"
        mod_a.mkdir(parents=True)
        (mod_a / "__init__.py").write_text("", encoding="utf-8")
        mod_b = tmp_path / "quickscale_modules" / "mod_b" / "src"
        mod_b.mkdir(parents=True)
        (mod_b / "__init__.py").write_text("", encoding="utf-8")

        result, events = self._run_quiet_check(tmp_path, sections="modules")
        assert result.returncode == 0

        mypy_calls = self._mypy_invocations(events)
        assert len(mypy_calls) >= 1

        # Each module should have its own mypy invocation with --show-error-codes
        for mod in ("mod_a", "mod_b"):
            found = any(f"quickscale_modules/{mod}" in " ".join(a) for a in mypy_calls)
            assert found, f"module {mod} should have a mypy invocation"

    # ------------------------------------------------------------------
    # Core-only
    # ------------------------------------------------------------------

    def test_core_only_includes_core_dirs(self, tmp_path: Path) -> None:
        """Core-only QUIET=1 includes core src and core tests only."""
        result, events = self._run_quiet_check(tmp_path, sections="core")
        assert result.returncode == 0

        ruff_check_str = " ".join(" ".join(a) for a in self._ruff_check_invocations(events))
        assert "quickscale_core/src" in ruff_check_str
        assert "quickscale/src" not in ruff_check_str
        assert "quickscale_cli/src" not in ruff_check_str

        pytest_str = " ".join(" ".join(a) for a in self._pytest_invocations(events))
        assert "quickscale_core/tests" in pytest_str
        assert "quickscale_cli/tests" not in pytest_str

    # ------------------------------------------------------------------
    # Core + CLI
    # ------------------------------------------------------------------

    def test_core_cli_includes_both_test_dirs(self, tmp_path: Path) -> None:
        """Core+CLI QUIET=1 includes both core and CLI test dirs."""
        result, events = self._run_quiet_check(tmp_path, sections="core cli")
        assert result.returncode == 0

        ruff_str = " ".join(" ".join(a) for a in self._ruff_check_invocations(events))
        assert "quickscale_core/src" in ruff_str
        assert "quickscale_cli/src" in ruff_str

        pytest_str = " ".join(" ".join(a) for a in self._pytest_invocations(events))
        assert "quickscale_core/tests" in pytest_str
        assert "quickscale_cli/tests" in pytest_str

    # ------------------------------------------------------------------
    # Structural — Makefile source patterns
    # ------------------------------------------------------------------

    def test_quiet_path_has_section_filters(self) -> None:
        """Makefile QUIET=1 path uses ACTIVE_SECTIONS filtering (not SRC_DIRS)."""
        with open(self.MAKEFILE_PATH, encoding="utf-8") as fh:
            content = fh.read()

        check_start = content.find("\ncheck:")
        assert check_start >= 0
        section = content[check_start:]

        # The QUIET path should NOT reference SRC_DIRS or TEST_DIRS
        quiet_section_start = section.find("$(QUIET)")
        assert quiet_section_start >= 0
        quiet_section = section[quiet_section_start:]
        # Find the else branch
        else_start = quiet_section.find("\n\telse")
        quiet_then = quiet_section[:else_start] if else_start >= 0 else quiet_section

        # The quiet path must not use the hardcoded SRC_DIRS or TEST_DIRS vars
        assert "$(SRC_DIRS)" not in quiet_then, "QUIET=1 path must not reference hardcoded SRC_DIRS"
        assert "$(TEST_DIRS)" not in quiet_then, (
            "QUIET=1 path must not reference hardcoded TEST_DIRS"
        )

    def test_quiet_path_filters_by_active_sections(self) -> None:
        """Makefile QUIET=1 path filters source dirs by ACTIVE_SECTIONS."""
        with open(self.MAKEFILE_PATH, encoding="utf-8") as fh:
            content = fh.read()

        check_start = content.find("\ncheck:")
        assert check_start >= 0
        section = content[check_start:]

        # Verify the QUIET path uses $(filter ... $(ACTIVE_SECTIONS)) for source dirs
        assert "$(filter quickscale,$(ACTIVE_SECTIONS))" in section
        assert "$(filter core,$(ACTIVE_SECTIONS))" in section
        assert "$(filter cli,$(ACTIVE_SECTIONS))" in section
        assert "$(filter devtools,$(ACTIVE_SECTIONS))" in section

    def test_quiet_path_skips_pytest_when_no_core_cli(self) -> None:
        """Makefile QUIET=1 pytest section checks for core/cli before running."""
        with open(self.MAKEFILE_PATH, encoding="utf-8") as fh:
            content = fh.read()

        check_start = content.find("\ncheck:")
        assert check_start >= 0
        section = content[check_start:]

        # The QUIET path should build test dirs from core/cli ACTIVE_SECTIONS guards
        quiet_q_test = section.find('q_test_dirs=""')
        assert quiet_q_test >= 0, "QUIET path should build q_test_dirs"
        # Verify pytest only runs when q_test_dirs is non-empty
        assert '-n "$$q_test_dirs"' in section

    def test_quiet_path_runs_modules_with_per_module_mypy(self) -> None:
        """Makefile QUIET=1 path runs per-module mypy with MYPYPATH for modules."""
        with open(self.MAKEFILE_PATH, encoding="utf-8") as fh:
            content = fh.read()

        check_start = content.find("\ncheck:")
        assert check_start >= 0
        section = content[check_start:]

        # Module mypy should use MYPYPATH setup like the typecheck target
        assert 'MYPYPATH="$$module_mypypath"' in section
        assert "--show-error-codes" in section
        # Per-module mypy with captured log output (not bare stderr passthrough)
        assert "_mod_log.txt" in section

    # ------------------------------------------------------------------
    # REV-002: Ruff test-directory parity in QUIET mode
    # ------------------------------------------------------------------

    def test_quiet_ruff_includes_core_cli_test_dirs(self, tmp_path: Path) -> None:
        """Default QUIET=1 Ruff includes core and CLI test dirs alongside src."""
        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0, (
            f"make check QUIET=1 failed: {result.stdout}\n{result.stderr}"
        )

        ruff_check = self._ruff_check_invocations(events)
        ruff_check_str = " ".join(" ".join(a) for a in ruff_check)
        assert "quickscale_core/tests" in ruff_check_str, (
            "QUIET=1 Ruff check must include quickscale_core/tests"
        )
        assert "quickscale_cli/tests" in ruff_check_str, (
            "QUIET=1 Ruff check must include quickscale_cli/tests"
        )

        ruff_format = self._ruff_format_invocations(events)
        ruff_format_str = " ".join(" ".join(a) for a in ruff_format)
        assert "quickscale_core/tests" in ruff_format_str, (
            "QUIET=1 Ruff format must include quickscale_core/tests"
        )
        assert "quickscale_cli/tests" in ruff_format_str, (
            "QUIET=1 Ruff format must include quickscale_cli/tests"
        )

    def test_quiet_mypy_src_only(self, tmp_path: Path) -> None:
        """Default QUIET=1 MyPy covers only source dirs, not test dirs."""
        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0, (
            f"make check QUIET=1 failed: {result.stdout}\n{result.stderr}"
        )

        mypy_calls = self._mypy_invocations(events)
        mypy_str = " ".join(" ".join(a) for a in mypy_calls)
        assert "quickscale_core/src" in mypy_str
        assert "quickscale_core/tests" not in mypy_str, (
            "QUIET=1 MyPy must NOT include core test dirs"
        )
        assert "quickscale_cli/tests" not in mypy_str, "QUIET=1 MyPy must NOT include CLI test dirs"

    def test_quiet_module_ruff_includes_test_dirs_when_present(self, tmp_path: Path) -> None:
        """QUIET=1 Ruff for modules includes test dirs when they exist."""
        mod_dir = tmp_path / "quickscale_modules" / "testmod"
        (mod_dir / "src" / "__init__.py").parent.mkdir(parents=True)
        (mod_dir / "src" / "__init__.py").write_text("", encoding="utf-8")
        (mod_dir / "tests" / "__init__.py").parent.mkdir(parents=True)
        (mod_dir / "tests" / "__init__.py").write_text("", encoding="utf-8")

        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0, (
            f"make check QUIET=1 failed: {result.stdout}\n{result.stderr}"
        )

        ruff_check = self._ruff_check_invocations(events)
        ruff_check_str = " ".join(" ".join(a) for a in ruff_check)
        assert "quickscale_modules/testmod/tests" in ruff_check_str, (
            "QUIET=1 module Ruff must include test dirs when present"
        )

        mypy_calls = self._mypy_invocations(events)
        mypy_str = " ".join(" ".join(a) for a in mypy_calls)
        assert "quickscale_modules/testmod/src" in mypy_str
        assert "quickscale_modules/testmod/tests" not in mypy_str, (
            "QUIET=1 module MyPy must NOT include test dirs"
        )

    def test_quiet_module_ruff_skips_test_dirs_when_absent(self, tmp_path: Path) -> None:
        """QUIET=1 Ruff for modules does not add test dir args when absent."""
        mod_dir = tmp_path / "quickscale_modules" / "testmod"
        (mod_dir / "src" / "__init__.py").parent.mkdir(parents=True)
        (mod_dir / "src" / "__init__.py").write_text("", encoding="utf-8")
        # No tests/ dir — intentionally omitted

        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0, (
            f"make check QUIET=1 failed: {result.stdout}\n{result.stderr}"
        )

        ruff_check = self._ruff_check_invocations(events)
        for args in ruff_check:
            args_str = " ".join(args)
            if "quickscale_modules/testmod" in args_str:
                assert "tests" not in args_str, (
                    f"Module without tests/ dir must not include tests arg: {args_str}"
                )
                break
        else:
            raise AssertionError("Expected a Ruff invocation for quickscale_modules/testmod")

    def test_quiet_pytest_core_cli_only(self, tmp_path: Path) -> None:
        """QUIET=1 pytest covers only core and CLI test dirs, not module tests."""
        mod_dir = tmp_path / "quickscale_modules" / "testmod"
        (mod_dir / "src" / "__init__.py").parent.mkdir(parents=True)
        (mod_dir / "src" / "__init__.py").write_text("", encoding="utf-8")
        (mod_dir / "tests" / "__init__.py").parent.mkdir(parents=True)
        (mod_dir / "tests" / "__init__.py").write_text("", encoding="utf-8")

        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0, (
            f"make check QUIET=1 failed: {result.stdout}\n{result.stderr}"
        )

        pytest_calls = self._pytest_invocations(events)
        pytest_str = " ".join(" ".join(a) for a in pytest_calls)
        assert "quickscale_core/tests" in pytest_str
        assert "quickscale_cli/tests" in pytest_str
        assert "quickscale_modules/testmod/tests" not in pytest_str, (
            "QUIET=1 pytest must NOT include module test dirs"
        )

    def test_quiet_pytest_excludes_integration_and_e2e_markers(self, tmp_path: Path) -> None:
        """
        QUIET=1 pytest excludes integration and e2e tests via marker.

        Behavioural contract test: the ``make check QUIET=1`` pytest command
        must include ``-m "not integration and not e2e"`` so that the quiet
        check gate runs only unit/static tests while integration and E2E
        tests remain in the CI E2E lane.
        """
        result, events = self._run_quiet_check(tmp_path)
        assert result.returncode == 0, (
            f"make check QUIET=1 failed: {result.stdout}\n{result.stderr}"
        )

        pytest_calls = self._pytest_invocations(events)
        assert len(pytest_calls) >= 1, "Expected at least one pytest invocation"
        for args in pytest_calls:
            # Skip the ``python -m pytest`` prefix to find pytest's own ``-m``.
            pytest_args = args[args.index("pytest") + 1 :]
            marker_idx = pytest_args.index("-m") if "-m" in pytest_args else -1
            assert marker_idx >= 0, f"QUIET pytest invocation missing pytest -m flag: {args}"
            marker_value = pytest_args[marker_idx + 1]
            assert "not integration" in marker_value and "not e2e" in marker_value, (
                f"QUIET pytest must exclude integration and e2e markers; got -m {marker_value!r}"
            )

    def test_quiet_pytest_forwards_xdist_args(self, tmp_path: Path) -> None:
        """
        QUIET=1 pytest forwards configured xdist arguments.

        The parallel case with an explicit worker count proves the
        forwarding end-to-end.  Serial disable is covered by the
        structural Makefile assertion in
        ``test_quiet_pytest_xdist_serial_filter``.
        """
        parallel_result, parallel_events = self._run_quiet_check(
            tmp_path,
            extra_env={"PYTEST_XDIST_WORKERS": "3"},
        )
        assert parallel_result.returncode == 0

        parallel_calls = self._pytest_invocations(parallel_events)
        for args in parallel_calls:
            pytest_args = args[args.index("pytest") + 1 :]
            worker_idx = pytest_args.index("-n")
            assert pytest_args[worker_idx : worker_idx + 4] == [
                "-n",
                "3",
                "--dist",
                "loadfile",
            ]

    def test_quiet_pytest_xdist_serial_filter(self) -> None:
        """
        Makefile QUIET=1 pytest uses ``$(PYTEST_XDIST_ARGS)`` for serial worker filtering.

        Structural assertion: the Makefile recipe includes
        ``$(PYTEST_XDIST_ARGS)`` which, per the ``$(filter ...)``
        definition, produces empty args for serial worker counts.
        """
        with open(self.MAKEFILE_PATH, encoding="utf-8") as fh:
            content = fh.read()

        check_start = content.find("\ncheck:")
        assert check_start >= 0
        section = content[check_start:]

        # Find the QUIET pytest line specifically
        quiet_start = section.find("$(QUIET)")
        assert quiet_start >= 0
        quiet_section = section[quiet_start:]
        else_start = quiet_section.find("\n\telse")
        quiet_then = quiet_section[:else_start] if else_start >= 0 else quiet_section

        assert "$(PYTEST_XDIST_ARGS)" in quiet_then, (
            "QUIET=1 pytest must reference $(PYTEST_XDIST_ARGS) for xdist forwarding"
        )

    def test_quiet_pytest_forwards_timeout_args(self, tmp_path: Path) -> None:
        """QUIET=1 pytest forwards configured timeout arguments."""
        result, events = self._run_quiet_check(
            tmp_path,
            extra_env={"PYTEST_TIMEOUT": "60"},
        )
        assert result.returncode == 0, (
            f"make check QUIET=1 with PYTEST_TIMEOUT=60 failed: {result.stdout}\n{result.stderr}"
        )

        pytest_calls = self._pytest_invocations(events)
        assert len(pytest_calls) >= 1
        for args in pytest_calls:
            pytest_args = args[args.index("pytest") + 1 :]
            timeout_flag = next((a for a in pytest_args if a.startswith("--timeout=")), None)
            assert timeout_flag is not None, (
                f"QUIET pytest invocation missing --timeout flag: {args}"
            )
            assert timeout_flag == "--timeout=60", f"Expected --timeout=60, got {timeout_flag!r}"
            assert "--timeout-method=thread" in pytest_args, (
                f"QUIET pytest invocation missing --timeout-method=thread: {args}"
            )

    def test_quiet_pytest_timeout_disabled_when_zero(self, tmp_path: Path) -> None:
        """QUIET=1 pytest omits timeout args when PYTEST_TIMEOUT=0."""
        result, events = self._run_quiet_check(
            tmp_path,
            extra_env={"PYTEST_TIMEOUT": "0"},
        )
        assert result.returncode == 0

        pytest_calls = self._pytest_invocations(events)
        assert len(pytest_calls) >= 1
        for args in pytest_calls:
            pytest_args = args[args.index("pytest") + 1 :]
            assert not any(a.startswith("--timeout=") for a in pytest_args), (
                f"QUIET pytest must not include --timeout when PYTEST_TIMEOUT=0: {args}"
            )

    # ------------------------------------------------------------------
    # SA120 — QUIET=1 frontend lint dispatch parity
    # ------------------------------------------------------------------

    def test_quiet_lint_frontend_dispatched(self, tmp_path: Path) -> None:
        """
        QUIET=1 dispatches ``lint-frontend`` through ``$(MAKE)``.

        Exact command::

            make check QUIET=1 MAKE=<fake-make-wrapper>
        """
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)
        result, events = self._run_quiet_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            extra_env={"PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
        )
        assert result.returncode == 0, (
            f"make check QUIET=1 with fake make failed: {result.stdout}\n{result.stderr}"
        )
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" in targets, (
            f"QUIET=1 must dispatch lint-frontend; got targets: {targets}"
        )

    def test_quiet_lint_frontend_same_guard_as_normal(self) -> None:
        """
        Both quiet and normal check paths gate frontend lint on the same

        node/pnpm availability check.
        """
        with open(self.MAKEFILE_PATH, encoding="utf-8") as fh:
            content = fh.read()

        check_start = content.find("\ncheck:")
        assert check_start >= 0
        section = content[check_start:]

        guard = "command -v node >/dev/null 2>&1 && command -v pnpm >/dev/null 2>&1"
        count = section.count(guard)
        assert count >= 2, (
            f"Both quiet and normal paths must contain the node/pnpm guard; "
            f"found {count} occurrence(s)"
        )

    def test_quiet_lint_frontend_failure_propagates(self, tmp_path: Path) -> None:
        """
        Lint-frontend failure in QUIET=1 mode exits nonzero.

        Exact command::

            make check QUIET=1 MAKE=<fake-make-failing-on-lint-frontend>
        """
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)
        result, events = self._run_quiet_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            extra_env={
                "FAKE_MAKE_FAIL_TARGET": "lint-frontend",
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode != 0, (
            "QUIET=1 must propagate lint-frontend failure as nonzero exit; "
            f"got rc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        # Verify lint-frontend was attempted
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" in targets, (
            f"lint-frontend must be attempted in QUIET=1; got targets: {targets}"
        )

    # ------------------------------------------------------------------
    # SA120-REV-002: absent-tool behavior (no host node/pnpm dep)
    # ------------------------------------------------------------------

    @staticmethod
    def _write_shell_wrapper_disabling_node_only(path: Path) -> Path:
        """
        Write a Python-based shell wrapper that disables ``command -v``

        for ``node`` only, used by node-absent tests.

        Delegates everything else to the real ``/bin/sh``.
        """
        path.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import os, sys
                if len(sys.argv) >= 3 and sys.argv[1] == '-c':
                    recipe = sys.argv[2]
                    recipe = recipe.replace(
                        'command -v node >/dev/null 2>&1',
                        'false'
                    )
                    os.execvp('/bin/sh', ['/bin/sh', '-c', recipe])
                os.execvp('/bin/sh', sys.argv[1:])
            """).lstrip(),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    @staticmethod
    def _write_shell_wrapper_disabling_pnpm_only(path: Path) -> Path:
        """
        Write a Python-based shell wrapper that disables ``command -v``

        for ``pnpm`` only, used by pnpm-absent tests.

        Delegates everything else to the real ``/bin/sh``.
        """
        path.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import os, sys
                if len(sys.argv) >= 3 and sys.argv[1] == '-c':
                    recipe = sys.argv[2]
                    recipe = recipe.replace(
                        'command -v pnpm >/dev/null 2>&1',
                        'false'
                    )
                    os.execvp('/bin/sh', ['/bin/sh', '-c', recipe])
                os.execvp('/bin/sh', sys.argv[1:])
            """).lstrip(),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def test_quiet_frontend_lint_skipped_when_node_absent(self, tmp_path: Path) -> None:
        """
        QUIET=1 silently skips frontend lint when node is absent

        (pnpm may be present independently).

        Exact command::

            make check QUIET=1 SHELL=<wrapper-disabling-node-only>
        """
        fake_pnpm_bin = tmp_path / "fake-pnpm-bin"
        self._write_fake_pnpm_only(fake_pnpm_bin)
        shell_wrapper = tmp_path / "shell_wrapper.py"
        self._write_shell_wrapper_disabling_node_only(shell_wrapper)
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)

        result, events = self._run_quiet_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            shell_override=str(shell_wrapper),
            extra_env={
                "PATH": f"{fake_pnpm_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode == 0, (
            f"QUIET=1 must succeed when node is absent; "
            f"got rc={result.returncode}, stdout={result.stdout}, stderr={result.stderr}"
        )
        # Verify lint-frontend was NOT dispatched (guard blocked it)
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" not in targets, (
            f"QUIET=1 must not dispatch lint-frontend when node is absent; got targets: {targets}"
        )

    def test_quiet_frontend_lint_skipped_when_pnpm_absent(self, tmp_path: Path) -> None:
        """
        QUIET=1 silently skips frontend lint when pnpm is absent

        (node may be present independently).

        Exact command::

            make check QUIET=1 SHELL=<wrapper-disabling-pnpm-only>
        """
        fake_node_bin = tmp_path / "fake-node-bin"
        self._write_fake_node_only(fake_node_bin)
        shell_wrapper = tmp_path / "shell_wrapper.py"
        self._write_shell_wrapper_disabling_pnpm_only(shell_wrapper)
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)

        result, events = self._run_quiet_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            shell_override=str(shell_wrapper),
            extra_env={
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode == 0, (
            f"QUIET=1 must succeed when pnpm is absent; "
            f"got rc={result.returncode}, stdout={result.stdout}, stderr={result.stderr}"
        )
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" not in targets, (
            f"QUIET=1 must not dispatch lint-frontend when pnpm is absent; got targets: {targets}"
        )

    # ------------------------------------------------------------------
    # SA120-REV-003: quiet-mode output / failure semantics
    # ------------------------------------------------------------------

    def test_quiet_frontend_lint_success_suppresses_banner(self, tmp_path: Path) -> None:
        """
        QUIET=1 frontend-lint success produces no banner output.

        Exact command::

            make check QUIET=1 MAKE=true
        """
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)

        result, events = self._run_quiet_check(
            tmp_path,
            extra_env={
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode == 0, f"QUIET=1 must succeed; got rc={result.returncode}"
        output = result.stdout + result.stderr

        # Quiet mode must produce no output at all on success (exact silence)
        assert output.strip() == "", (
            f"QUIET=1 must produce no output on success; got output: {output!r}"
        )

    def test_quiet_frontend_lint_failure_replays_captured_log(self, tmp_path: Path) -> None:
        """
        QUIET=1 frontend-lint failure replays captured log and exits nonzero.

        The diagnostic from the failing sub-make must appear in the output
        (not just a bare exit code), confirming the captured-log replay path.

        Exact command::

            make check QUIET=1 MAKE=<fake-make-failing-on-lint-frontend>
        """
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)

        result, events = self._run_quiet_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            extra_env={
                "FAKE_MAKE_FAIL_TARGET": "lint-frontend",
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode != 0, (
            "QUIET=1 must propagate lint-frontend failure as nonzero exit; "
            f"got rc={result.returncode}"
        )
        # Verify the unique diagnostic marker is replayed from the captured log
        output = result.stdout + result.stderr
        diagnostic = "FAKE_MAKE: target 'lint-frontend' failed"
        assert diagnostic in output, (
            f"QUIET=1 must replay the captured log diagnostic on failure; got output: {output}"
        )
        assert output.count(diagnostic) == 1, (
            f"QUIET=1 must replay the diagnostic exactly once; "
            f"count={output.count(diagnostic)}, output={output}"
        )
        # Verify lint-frontend was attempted
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" in targets, (
            f"lint-frontend must be attempted in QUIET=1; got targets: {targets}"
        )

    # ------------------------------------------------------------------
    # SA120-REV-004: common-gate failure prevents frontend dispatch
    # ------------------------------------------------------------------

    def test_quiet_frontend_lint_not_dispatched_when_gate_fails(self, tmp_path: Path) -> None:
        """
        QUIET=1 does not dispatch frontend lint when a repo gate

        (check-core-compat) fails before the frontend section.

        The recipe's ``set -e`` stops at the gate failure, so the
        frontend-lint guard is never reached and no success banner
        is printed.

        Exact command::

            make check QUIET=1 MAKE=<fake-make-failing-on-check-core-compat>
        """
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)

        result, events = self._run_quiet_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            extra_env={
                "FAKE_MAKE_FAIL_TARGET": "check-core-compat",
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode != 0, (
            f"QUIET=1 must exit nonzero when a repo gate fails; got rc={result.returncode}"
        )
        # Verify lint-frontend was NOT dispatched (recipe stopped before frontend section)
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" not in targets, (
            f"QUIET=1 must not dispatch lint-frontend when a gate fails; got targets: {targets}"
        )
        # Verify the gate failure diagnostic appears in output
        output = result.stdout + result.stderr
        assert "FAKE_MAKE: target 'check-core-compat' failed" in output, (
            f"QUIET=1 must show the gate failure diagnostic; got output: {output}"
        )
        # Verify no success banner
        assert "🎉" not in output, "QUIET=1 must not print success banner when a gate fails"


class TestCheckNormalFrontendLint:
    """Normal mode ``make check`` frontend lint behavior (no QUIET)."""

    MAKEFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "Makefile")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_shell_wrapper_disabling_node_only(path: Path) -> Path:
        """
        Write a Python-based shell wrapper that disables ``command -v``

        for ``node`` only, used by node-absent tests.

        GNU Make uses ``SHELL`` to run recipe lines.  By setting ``SHELL`` to
        this wrapper, ``command -v node`` is replaced with ``false``, making
        the guard fail regardless of host PATH.  The wrapper delegates
        everything else to the real ``/bin/sh``.
        """
        path.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import os, sys
                if len(sys.argv) >= 3 and sys.argv[1] == '-c':
                    recipe = sys.argv[2]
                    recipe = recipe.replace(
                        'command -v node >/dev/null 2>&1',
                        'false'
                    )
                    os.execvp('/bin/sh', ['/bin/sh', '-c', recipe])
                os.execvp('/bin/sh', sys.argv[1:])
            """).lstrip(),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    @staticmethod
    def _write_shell_wrapper_disabling_pnpm_only(path: Path) -> Path:
        """
        Write a Python-based shell wrapper that disables ``command -v``

        for ``pnpm`` only, used by pnpm-absent tests.

        GNU Make uses ``SHELL`` to run recipe lines.  By setting ``SHELL`` to
        this wrapper, ``command -v pnpm`` is replaced with ``false``, making
        the guard fail regardless of host PATH.  The wrapper delegates
        everything else to the real ``/bin/sh``.
        """
        path.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import os, sys
                if len(sys.argv) >= 3 and sys.argv[1] == '-c':
                    recipe = sys.argv[2]
                    recipe = recipe.replace(
                        'command -v pnpm >/dev/null 2>&1',
                        'false'
                    )
                    os.execvp('/bin/sh', ['/bin/sh', '-c', recipe])
                os.execvp('/bin/sh', sys.argv[1:])
            """).lstrip(),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def _write_fake_python(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a deterministic fake Python that logs invocations and exits 0."""
        fake_python = tmp_path / "fake_python.py"
        event_log = tmp_path / "events.jsonl"
        fake_python.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import json, os, sys
                from pathlib import Path

                log_path = Path(os.environ["FAKE_LOG"])
                args = sys.argv[1:]
                with log_path.open("a", encoding="utf-8") as stream:
                    json.dump({"kind": "invoke", "args": args}, stream)
                    stream.write("\\n")
                raise SystemExit(0)
            """).lstrip(),
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        return fake_python, event_log

    @staticmethod
    def _write_fake_node_pnpm(bin_dir: Path) -> None:
        """Create fake node and pnpm executables that exit 0."""
        bin_dir.mkdir(parents=True, exist_ok=True)
        for tool in ("node", "pnpm"):
            tool_path = bin_dir / tool
            tool_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool_path.chmod(0o755)

    @staticmethod
    def _write_fake_node_only(bin_dir: Path) -> None:
        """Create a fake node executable that exits 0."""
        bin_dir.mkdir(parents=True, exist_ok=True)
        tool_path = bin_dir / "node"
        tool_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool_path.chmod(0o755)

    @staticmethod
    def _write_fake_pnpm_only(bin_dir: Path) -> None:
        """Create a fake pnpm executable that exits 0."""
        bin_dir.mkdir(parents=True, exist_ok=True)
        tool_path = bin_dir / "pnpm"
        tool_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool_path.chmod(0o755)

    @staticmethod
    def _write_fake_make(tmp_path: Path) -> tuple[Path, Path, Path]:
        """
        Create a deterministic fake make that logs targets to a JSONL file.

        The fake make exits 1 when ``FAKE_MAKE_FAIL_TARGET`` is set and the
        requested target matches; otherwise exits 0.  Returns the path to the
        script, the event-log path, and a shell-wrapper path that sets the
        required environment variable before invoking the real script.
        """
        script = tmp_path / "fake_make.py"
        event_log = tmp_path / "make_events.jsonl"
        script.write_text(
            textwrap.dedent("""\
                #!/usr/bin/env python3
                import json, os, sys
                from pathlib import Path

                log_path = Path(os.environ["FAKE_MAKE_LOG"])
                target = sys.argv[1] if len(sys.argv) > 1 else ""
                with log_path.open("a", encoding="utf-8") as stream:
                    json.dump({"kind": "make", "target": target}, stream)
                    stream.write("\\n")
                fail_target = os.environ.get("FAKE_MAKE_FAIL_TARGET", "")
                if fail_target and target == fail_target:
                    print(
                        f"FAKE_MAKE: target '{target}' failed "
                        f"(FAKE_MAKE_FAIL_TARGET={fail_target})",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                sys.exit(0)
            """).lstrip(),
            encoding="utf-8",
        )
        script.chmod(0o755)

        # Shell wrapper ensures FAKE_MAKE_LOG is always set
        wrapper = tmp_path / "fake_make.sh"
        wrapper.write_text(
            textwrap.dedent(f"""\
                #!/bin/sh
                export FAKE_MAKE_LOG="{event_log}"
                exec "{script}" "$@"
            """).lstrip(),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)

        return script, event_log, wrapper

    def _run_normal_check(
        self,
        tmp_path: Path,
        *,
        sections: str = "",
        module: str = "",
        make_override: str | None = None,
        shell_override: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """
        Run ``make check`` (no QUIET) with fake Python.

        Returns only the completed-process result.  For make-event inspection
        callers use ``make_override`` and read the event log themselves.

        When *shell_override* is set, it is passed as ``SHELL`` to make so
        ``command -v`` behaviour can be controlled for absent-tool tests.
        """
        fake_python, event_log = self._write_fake_python(tmp_path)

        env = os.environ.copy()
        for key in ("SECTIONS", "SECTION", "MODULE", "PYTEST_XDIST_WORKERS"):
            env.pop(key, None)
        env["FAKE_LOG"] = str(event_log)
        if extra_env:
            env.update(extra_env)

        make_value = make_override if make_override is not None else "true"
        cmd = [
            "make",
            "--no-print-directory",
            "-f",
            self.MAKEFILE_PATH,
            f"PYTHON={fake_python}",
            f"MAKE={make_value}",
        ]
        if shell_override:
            cmd.append(f"SHELL={shell_override}")
        if sections:
            cmd.append(f"SECTIONS={sections}")
        if module:
            cmd.append(f"MODULE={module}")
        cmd.append("check")

        result = subprocess.run(
            cmd,
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result

    # ------------------------------------------------------------------
    # Frontend lint dispatch
    # ------------------------------------------------------------------

    def test_normal_frontend_lint_dispatched_with_node_pnpm(self, tmp_path: Path) -> None:
        """
        Normal mode dispatches lint-frontend when node/pnpm are available.

        Exact command::

            make check MAKE=<fake-make-wrapper>
        """
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)

        result = self._run_normal_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            extra_env={
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode == 0, (
            f"normal check with fake make failed: {result.stdout}\n{result.stderr}"
        )
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" in targets, (
            f"normal mode must dispatch lint-frontend; got targets: {targets}"
        )

    def test_normal_frontend_lint_skipped_when_node_absent(self, tmp_path: Path) -> None:
        """
        Normal mode skips lint-frontend when node is absent

        (pnpm may be present independently; shell wrapper disables only node).

        Exact command::

            make check SHELL=<wrapper-disabling-node-only>
        """
        fake_pnpm_bin = tmp_path / "fake-pnpm-bin"
        self._write_fake_pnpm_only(fake_pnpm_bin)
        shell_wrapper = tmp_path / "shell_wrapper.py"
        self._write_shell_wrapper_disabling_node_only(shell_wrapper)

        result = self._run_normal_check(
            tmp_path,
            shell_override=str(shell_wrapper),
            extra_env={
                "PATH": f"{fake_pnpm_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode == 0, (
            f"normal check must succeed when node is absent; "
            f"got rc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        output = result.stdout + result.stderr
        assert "Skipping rendered frontend lint" in output, (
            f"Normal mode must print skip message when node is absent; got output: {output}"
        )
        assert "🎉" in output, (
            "Normal mode must still show success banner when frontend is skipped; "
            f"got output: {output}"
        )
        assert "📦 Linting rendered frontend" not in output, (
            "Normal mode must not print frontend lint banner when node is absent; "
            f"got output: {output}"
        )

    def test_normal_frontend_lint_skipped_when_pnpm_absent(self, tmp_path: Path) -> None:
        """
        Normal mode skips lint-frontend when pnpm is absent

        (node may be present independently; shell wrapper disables only pnpm).

        Exact command::

            make check SHELL=<wrapper-disabling-pnpm-only>
        """
        fake_node_bin = tmp_path / "fake-node-bin"
        self._write_fake_node_only(fake_node_bin)
        shell_wrapper = tmp_path / "shell_wrapper.py"
        self._write_shell_wrapper_disabling_pnpm_only(shell_wrapper)

        result = self._run_normal_check(
            tmp_path,
            shell_override=str(shell_wrapper),
            extra_env={
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode == 0, (
            f"normal check must succeed when pnpm is absent; "
            f"got rc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        output = result.stdout + result.stderr
        assert "Skipping rendered frontend lint" in output, (
            f"Normal mode must print skip message when pnpm is absent; got output: {output}"
        )
        assert "🎉" in output, (
            "Normal mode must still show success banner when frontend is skipped; "
            f"got output: {output}"
        )

    # ------------------------------------------------------------------
    # Output / failure semantics
    # ------------------------------------------------------------------

    def test_normal_frontend_lint_failure_propagates(self, tmp_path: Path) -> None:
        """
        Normal mode lint-frontend failure exits nonzero with no banner.

        Exact command::

            make check MAKE=<fake-make-failing-on-lint-frontend>
        """
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)

        result = self._run_normal_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            extra_env={
                "FAKE_MAKE_FAIL_TARGET": "lint-frontend",
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode != 0, (
            "Normal mode must propagate lint-frontend failure as nonzero exit; "
            f"got rc={result.returncode}"
        )
        # Verify lint-frontend was attempted
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" in targets, (
            f"lint-frontend must be attempted in normal mode; got targets: {targets}"
        )
        # No success banner on failure
        output = result.stdout + result.stderr
        assert "🎉" not in output, (
            "Normal mode must not show success banner when lint-frontend fails; "
            f"got output: {output}"
        )

    def test_normal_frontend_lint_success_shows_banner(self, tmp_path: Path) -> None:
        """
        Normal mode lint-frontend success shows the check-passed banner.

        Exact command::

            make check MAKE=true
        """
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)

        result = self._run_normal_check(
            tmp_path,
            extra_env={
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode == 0, f"normal check must succeed; got rc={result.returncode}"
        output = result.stdout + result.stderr
        assert "🎉 All checks passed!" in output, (
            "Normal mode must show success banner on successful frontend lint; "
            f"got output: {output}"
        )
        assert "📦 Linting rendered frontend" in output, (
            f"Normal mode must show the frontend lint banner; got output: {output}"
        )
        # No skip message when node/pnpm are present
        assert "Skipping rendered frontend lint" not in output, (
            "Normal mode must not show skip message when node/pnpm are available; "
            f"got output: {output}"
        )

    # ------------------------------------------------------------------
    # SA120-REV-004: common-gate failure prevents frontend dispatch
    # ------------------------------------------------------------------

    def test_normal_frontend_lint_not_dispatched_when_gate_fails(self, tmp_path: Path) -> None:
        """
        Normal mode does not dispatch frontend lint when a repo gate

        (check-core-compat) fails before the frontend section.

        The recipe's ``set -e`` stops at the gate failure, so the
        frontend-lint guard is never reached and no success banner
        is printed.

        Exact command::

            make check MAKE=<fake-make-failing-on-check-core-compat>
        """
        _, make_log, fake_make_wrapper = self._write_fake_make(tmp_path)
        fake_node_bin = tmp_path / "fake-node-pnpm-bin"
        self._write_fake_node_pnpm(fake_node_bin)

        result = self._run_normal_check(
            tmp_path,
            make_override=str(fake_make_wrapper),
            extra_env={
                "FAKE_MAKE_FAIL_TARGET": "check-core-compat",
                "PATH": f"{fake_node_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        assert result.returncode != 0, (
            f"Normal mode must exit nonzero when a repo gate fails; got rc={result.returncode}"
        )
        # Verify lint-frontend was NOT dispatched (recipe stopped before frontend section)
        make_events: list[dict] = []
        if make_log.exists() and make_log.stat().st_size > 0:
            with make_log.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        make_events.append(json.loads(line))
        targets = [e["target"] for e in make_events]
        assert "lint-frontend" not in targets, (
            f"Normal mode must not dispatch lint-frontend when a gate fails; got targets: {targets}"
        )
        # Verify the gate failure diagnostic appears in output
        output = result.stdout + result.stderr
        assert "FAKE_MAKE: target 'check-core-compat' failed" in output, (
            f"Normal mode must show the gate failure diagnostic; got output: {output}"
        )
        # Verify no success banner
        assert "🎉" not in output, "Normal mode must not print success banner when a gate fails"


class TestE2EScriptPythonpath:
    """Structural assertions for ``scripts/test_e2e.sh`` lane PYTHONPATH setup."""

    SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "test_e2e.sh")

    def _read_script(self) -> str:
        with open(self.SCRIPT_PATH, encoding="utf-8") as fh:
            return fh.read()

    def test_core_lane_pythonpath_includes_project_root(self) -> None:
        """
        Core E2E lane PYTHONPATH prepends ``$PROJECT_ROOT`` for repo-root imports.

        The Core E2E tests need to resolve ``scripts.*`` imports (e.g.
        ``scripts.publish_module``) via the repository root, so the
        ``lane_pythonpath`` for the ``core`` lane must include
        ``$PROJECT_ROOT`` before the package-specific ``$CORE_DIR`` entries.
        """
        content = self._read_script()

        # Find the core lane assignment block
        core_block_start = content.find('if [ "$lane" = "core" ]; then')
        assert core_block_start >= 0, "run_e2e_lane must have a core lane branch"

        # Find the closing else/fi for the core lane
        else_pos = content.find("\n    else", core_block_start)
        core_block = content[core_block_start:else_pos]

        assert 'lane_pythonpath="$PROJECT_ROOT:$CORE_DIR:$CORE_DIR/src"' in core_block, (
            "Core lane PYTHONPATH must include $PROJECT_ROOT for repo-root import visibility; "
            f"got block: {core_block}"
        )

    def test_cli_lane_pythonpath_does_not_include_project_root(self) -> None:
        """
        CLI E2E lane PYTHONPATH does NOT include ``$PROJECT_ROOT``.

        The CLI package does not need repo-root import visibility, so its
        ``lane_pythonpath`` must remain at ``$CLI_DIR:$CLI_DIR/src`` to
        avoid polluting the import namespace.
        """
        content = self._read_script()

        else_pos = content.find('\n    else\n        lane_label="CLI"')
        assert else_pos >= 0, "run_e2e_lane must have a CLI lane branch"

        # Find the fi that closes the if/else block
        fi_pos = content.find("\n    fi", else_pos)
        cli_block = content[else_pos:fi_pos]

        assert 'lane_pythonpath="$CLI_DIR:$CLI_DIR/src"' in cli_block, (
            f"CLI lane PYTHONPATH must not include $PROJECT_ROOT; got block: {cli_block}"
        )
        assert "PROJECT_ROOT" not in cli_block, (
            "CLI lane PYTHONPATH must not reference $PROJECT_ROOT"
        )
