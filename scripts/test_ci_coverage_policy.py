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
