"""
Control cases for the quality gate in ``check_quality.sh`` (SA243).

Each fixed threshold is pinned on both sides of its line through the real
checked-in gate script: a fail-column fixture must exit non-zero, and the
matching warn-column fixture must print and still exit 0.  Synthetic analyzer
output is injected through stub analyzers controlled by ``QS_*_FIXTURE``
environment variables, so no real source tree is measured.

Every run writes its artifacts under a per-test ``QUALITY_OUTPUT_DIR`` so the
repository's ``.quickscale`` directory is never touched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_SHELL_PATH = _SCRIPT_DIR / "check_quality.sh"

_SAMPLE_FILE = "quickscale_core/src/quickscale_core/sample.py"
_OTHER_FILE = "quickscale_core/src/quickscale_core/other.py"

_FIND_CLEAN = "#!/bin/bash\n# stub find — report no large files\nexit 0\n"

_POETRY_STUB = '''#!/usr/bin/env python3
"""Stub poetry for check_quality.sh threshold tests."""

import os
import sys


def main() -> int:
    args = sys.argv[1:]

    if len(args) >= 2 and args[0] == "run":
        tool = args[1]
        tool_args = args[2:]

        if tool in ("vulture", "radon", "pylint") and "--version" in tool_args:
            print(f"{tool} 1.0.0 (stub)")
            return 0

        if tool == "vulture":
            fixture = os.environ.get("QS_VULTURE_FIXTURE", "")
            if fixture:
                print(fixture)
            return int(os.environ.get("QS_VULTURE_EXIT", "0"))

        if tool == "radon":
            if tool_args and tool_args[0] == "cc":
                print(os.environ.get("QS_RADON_CC_FIXTURE", "{}"))
            else:
                print("{}")
            return int(os.environ.get("QS_RADON_EXIT", "0"))

        if tool == "pylint":
            if any(arg == "--min-similarity-lines=19" for arg in tool_args):
                print(os.environ.get("QS_PYLINT_FAIL_FIXTURE", "[]"))
            else:
                print(os.environ.get("QS_PYLINT_WARN_FIXTURE", "[]"))
            return int(os.environ.get("QS_PYLINT_EXIT", "8"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _duplication_entry(
    path: str,
    line: int,
    end_line: int,
    other_path: str = _OTHER_FILE,
    other_line: int = 100,
    other_end: int = 0,
) -> dict:
    """
    Return one pylint R0801 JSON entry naming both block locations.

    ``line``/``end_line`` are one-based inclusive source lines.  Pylint's
    message headers are zero-based and end-exclusive, so the start is written
    as ``line - 1`` and the end as ``end_line``.
    """
    if other_end == 0:
        other_end = other_line + (end_line - line)
    message = (
        "Similar lines in 2 files\n"
        f"=={path.replace('/', '.').removesuffix('.py')}:[{line - 1}:{end_line}]\n"
        f"=={other_path.replace('/', '.').removesuffix('.py')}:[{other_line - 1}:{other_end}]\n"
        + "\n".join(f"    code line {index}" for index in range(line, end_line + 1))
    )
    return {
        "type": "refactor",
        "module": "quickscale",
        "obj": "",
        "line": line,
        "column": 0,
        "endLine": end_line,
        "endColumn": 0,
        "path": path,
        "symbol": "duplicate-code",
        "message": message,
        "message-id": "R0801",
    }


def _radon_entry(complexity: int, entry_type: str = "function", name: str = "helper") -> dict:
    return {
        "name": name,
        "type": entry_type,
        "complexity": complexity,
        "rank": "D" if complexity >= 21 else "C",
        "lineno": 1,
        "endline": 40,
    }


class TestQualityGateThresholds:
    """Each threshold's fail and warn sides run through the real gate."""

    @pytest.fixture
    def quality_output_dir(self, tmp_path: Path) -> Path:
        """Per-test artifact dir; the repository ``.quickscale`` is untouched."""
        return tmp_path / "quality-artifacts"

    def _stub_bin(self, tmp_path: Path) -> Path:
        """Create the stub ``poetry`` script and return its bin directory."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        stub = bin_dir / "poetry"
        stub.write_text(_POETRY_STUB, encoding="utf-8")
        stub.chmod(0o755)
        return bin_dir

    def _find_stub_bin(self, tmp_path: Path, content: str = _FIND_CLEAN) -> Path:
        """Create a stub ``find`` script reporting the controlled file sizes."""
        bin_dir = tmp_path / "findbin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        stub = bin_dir / "find"
        stub.write_text(content, encoding="utf-8")
        stub.chmod(0o755)
        return bin_dir

    def _run_shell(
        self,
        tmp_path: Path,
        quality_output_dir: Path,
        *,
        vulture: str = "",
        vulture_exit: int = 0,
        radon_cc: dict | None = None,
        pylint_warn: list | None = None,
        pylint_fail: list | None = None,
        pylint_warn_raw: str | None = None,
        pylint_exit: int = 8,
        find_content: str = _FIND_CLEAN,
    ) -> subprocess.CompletedProcess:
        """Run the real ``check_quality.sh`` with controlled analyzer output."""
        env = os.environ.copy()
        stub_bin = self._stub_bin(tmp_path)
        find_bin = self._find_stub_bin(tmp_path, find_content)
        env["PATH"] = f"{stub_bin}:{find_bin}:{env.get('PATH', '')}"
        env["QUALITY_OUTPUT_DIR"] = str(quality_output_dir)
        env["QS_VULTURE_FIXTURE"] = vulture
        env["QS_VULTURE_EXIT"] = str(vulture_exit)
        env["QS_RADON_CC_FIXTURE"] = json.dumps(radon_cc or {})
        env["QS_PYLINT_WARN_FIXTURE"] = (
            pylint_warn_raw if pylint_warn_raw is not None else json.dumps(pylint_warn or [])
        )
        env["QS_PYLINT_FAIL_FIXTURE"] = json.dumps(pylint_fail or [])
        env["QS_PYLINT_EXIT"] = str(pylint_exit)
        return subprocess.run(
            [str(_SHELL_PATH)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=180,
            env=env,
        )

    def _status(self, quality_output_dir: Path) -> dict:
        return json.loads(
            (quality_output_dir / "quality_gate_status.json").read_text(encoding="utf-8")
        )

    def _report(self, quality_output_dir: Path) -> dict:
        return json.loads((quality_output_dir / "quality_report.json").read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Dead code: 100% fails, 80-99% warns
    # ------------------------------------------------------------------

    def test_dead_code_at_100_percent_fails(self, tmp_path: Path, quality_output_dir: Path) -> None:
        finding = f"{_SAMPLE_FILE}:10: unused variable 'x' (100% confidence, 1 line)"
        result = self._run_shell(tmp_path, quality_output_dir, vulture=finding)
        assert result.returncode == 1, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["dead_code_fail"] == 1
        assert status["exit_code"] == 1
        assert "unused variable 'x'" in result.stdout
        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "✗ Failing findings" in markdown
        assert "✓ Pass" not in markdown

    def test_dead_code_at_99_percent_warns_and_passes(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        finding = f"{_SAMPLE_FILE}:10: unused variable 'x' (90% confidence, 1 line)"
        result = self._run_shell(tmp_path, quality_output_dir, vulture=finding)
        assert result.returncode == 0, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["dead_code_fail"] == 0
        assert status["dead_code_warning"] == 1
        assert status["exit_code"] == 0
        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "✓ Pass (warnings only)" in markdown

    # ------------------------------------------------------------------
    # Complexity: CC 21 fails, CC 20 warns
    # ------------------------------------------------------------------

    def test_complexity_at_21_fails(self, tmp_path: Path, quality_output_dir: Path) -> None:
        files = {_SAMPLE_FILE: [_radon_entry(21)]}
        result = self._run_shell(tmp_path, quality_output_dir, radon_cc=files)
        assert result.returncode == 1, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["complexity_fail"] == 1
        assert "helper is 21" in result.stdout
        report = self._report(quality_output_dir)
        assert report["fail_findings"]["complexity"][0]["complexity"] == 21
        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "✗ Failing findings" in markdown

    def test_complexity_at_20_warns_and_passes(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        files = {_SAMPLE_FILE: [_radon_entry(20)]}
        result = self._run_shell(tmp_path, quality_output_dir, radon_cc=files)
        assert result.returncode == 0, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["complexity_fail"] == 0
        assert status["complexity_warning"] == 1
        assert "✗ Failing findings" not in result.stdout

    def test_class_aggregate_at_21_is_not_a_failure(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        files = {_SAMPLE_FILE: [_radon_entry(21, entry_type="class", name="Example")]}
        result = self._run_shell(tmp_path, quality_output_dir, radon_cc=files)
        assert result.returncode == 0, result.stdout + result.stderr
        assert self._status(quality_output_dir)["complexity_fail"] == 0

    # ------------------------------------------------------------------
    # File length: 800 fails, 799 warns
    # ------------------------------------------------------------------

    def test_file_at_800_lines_fails(self, tmp_path: Path, quality_output_dir: Path) -> None:
        find = f'#!/bin/bash\nprintf "800\\t{_SAMPLE_FILE}\\n"\nexit 0\n'
        result = self._run_shell(tmp_path, quality_output_dir, find_content=find)
        assert result.returncode == 1, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["large_files_fail"] == 1
        report = self._report(quality_output_dir)
        assert report["fail_findings"]["large_files"] == [{"file": _SAMPLE_FILE, "lines": 800}]
        assert "has 800 lines" in result.stdout

    def test_file_at_799_lines_warns_and_passes(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        find = f'#!/bin/bash\nprintf "799\\t{_SAMPLE_FILE}\\n"\nexit 0\n'
        result = self._run_shell(tmp_path, quality_output_dir, find_content=find)
        assert result.returncode == 0, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["large_files_fail"] == 0
        assert status["large_files_warning"] == 1

    # ------------------------------------------------------------------
    # Duplication: >= 20 similar lines fails, 6-19 warns
    # ------------------------------------------------------------------

    def test_duplication_block_at_20_lines_fails(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        block = [_duplication_entry(_SAMPLE_FILE, 10, 29)]
        result = self._run_shell(tmp_path, quality_output_dir, pylint_warn=block, pylint_fail=block)
        assert result.returncode == 1, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["duplication_fail"] == 1
        assert status["duplication_warning"] == 0
        report = self._report(quality_output_dir)
        assert report["fail_findings"]["duplication"][0]["message-id"] == "R0801"

    def test_duplication_block_at_19_lines_warns_and_passes(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        block = [_duplication_entry(_SAMPLE_FILE, 10, 28)]
        result = self._run_shell(tmp_path, quality_output_dir, pylint_warn=block, pylint_fail=[])
        assert result.returncode == 0, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["duplication_fail"] == 0
        assert status["duplication_warning"] == 1

    def test_duplication_classification_ignores_fail_blocks_in_warn_run(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        fail_block = [_duplication_entry(_SAMPLE_FILE, 10, 29)]
        warn_block = [_duplication_entry(_OTHER_FILE, 50, 61)]
        result = self._run_shell(
            tmp_path,
            quality_output_dir,
            pylint_warn=[*warn_block, *fail_block],
            pylint_fail=fail_block,
        )
        assert result.returncode == 1, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["duplication_fail"] == 1
        assert status["duplication_warning"] == 1

    def test_invalid_pylint_json_fails_closed(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        result = self._run_shell(tmp_path, quality_output_dir, pylint_warn_raw="{not json")
        assert result.returncode == 1
        assert "refusing to treat it as zero findings" in result.stdout
        assert "not valid JSON" in result.stderr

    def test_pylint_analyzer_diagnostic_fails_closed(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A fatal pylint diagnostic must never read as zero duplication."""
        diagnostic = [
            {
                "message-id": "F0001",
                "type": "fatal",
                "message": "No module named 'missing'",
            }
        ]
        result = self._run_shell(
            tmp_path, quality_output_dir, pylint_fail=diagnostic, pylint_exit=8
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "refusing to treat it as zero findings" in result.stdout
        assert "analyzer diagnostic F0001" in result.stderr

    def test_pylint_failure_status_fails_closed(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        result = self._run_shell(tmp_path, quality_output_dir, pylint_exit=1)
        assert result.returncode == 1
        assert "pylint duplication scan failed" in result.stdout

    def test_vulture_unrecognized_output_fails_closed(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A non-finding vulture diagnostic must fail instead of counting zero."""
        result = self._run_shell(
            tmp_path,
            quality_output_dir,
            vulture='bad.py:1: invalid syntax at "def broken(:"',
            vulture_exit=3,
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "refusing to treat it as zero findings" in result.stdout
        assert "unrecognized vulture output" in result.stderr

    def test_vulture_failure_status_fails_closed(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        result = self._run_shell(tmp_path, quality_output_dir, vulture_exit=2)
        assert result.returncode == 1
        assert "vulture scan failed" in result.stdout

    def test_radon_error_object_fails_closed(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """Radon's per-file error object must fail instead of counting zero."""
        bad = {"/tmp/opencode/bad.py": {"error": "invalid syntax (<unknown>, line 1)"}}
        result = self._run_shell(tmp_path, quality_output_dir, radon_cc=bad)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "radon complexity output is not a valid JSON object" in result.stdout

    def test_failing_duplication_block_is_named(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A failing block is named with its locations and source span."""
        block = [_duplication_entry(_SAMPLE_FILE, 10, 29)]
        result = self._run_shell(tmp_path, quality_output_dir, pylint_warn=block, pylint_fail=block)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "lines 10-29" in result.stdout
        assert "span 20 lines" in result.stdout
        report = self._report(quality_output_dir)
        entry = report["fail_findings"]["duplication"][0]
        assert entry["span_lines"] == 20
        assert "lines 10-29" in entry["block_locations"][0]
        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "lines 10-29" in markdown
        assert "span 20 lines" in markdown

    def test_failed_run_clears_previous_verdict(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A failed rerun must not leave the previous run's passing verdict."""
        first = self._run_shell(tmp_path, quality_output_dir)
        assert first.returncode == 0
        assert (quality_output_dir / "quality_gate_status.json").exists()

        second = self._run_shell(tmp_path, quality_output_dir, pylint_warn_raw="{not json")
        assert second.returncode == 1
        assert not (quality_output_dir / "quality_gate_status.json").exists()
        assert not (quality_output_dir / "quality_report.json").exists()
        assert not (quality_output_dir / "quality_report.md").exists()

    # ------------------------------------------------------------------
    # Real pylint boundary: the option is exclusive, the policy is inclusive
    # ------------------------------------------------------------------

    def test_real_pylint_inclusive_boundaries(self, tmp_path: Path) -> None:
        """The gate's option values make pylint's exclusive comparison inclusive."""
        twenty = "\n".join(f"value_{index} = compute_{index}()" for index in range(20)) + "\n"
        six = "\n".join(f"six_{index} = {index}" for index in range(6)) + "\n"
        (tmp_path / "twenty_a.py").write_text(twenty)
        (tmp_path / "twenty_b.py").write_text(twenty)
        (tmp_path / "six_a.py").write_text(six)
        (tmp_path / "six_b.py").write_text(six)

        def block_count(first: Path, second: Path, option: int) -> int:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pylint",
                    str(first),
                    str(second),
                    "--disable=all",
                    "--enable=duplicate-code",
                    f"--min-similarity-lines={option}",
                    "--ignore-comments=yes",
                    "--ignore-docstrings=yes",
                    "--ignore-imports=yes",
                    "--output-format=json",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            entries = json.loads(result.stdout)
            return len([entry for entry in entries if entry.get("message-id") == "R0801"])

        # A block of exactly 20 similar lines fails under option 19 (policy
        # fail line 20) and is invisible at option 20.
        assert block_count(tmp_path / "twenty_a.py", tmp_path / "twenty_b.py", 19) == 1
        assert block_count(tmp_path / "twenty_a.py", tmp_path / "twenty_b.py", 20) == 0
        # A block of exactly 6 similar lines warns under option 5 (policy
        # warn floor 6) and is invisible at option 6.
        assert block_count(tmp_path / "six_a.py", tmp_path / "six_b.py", 5) == 1
        assert block_count(tmp_path / "six_a.py", tmp_path / "six_b.py", 6) == 0

    # ------------------------------------------------------------------
    # A fully clean fixture passes
    # ------------------------------------------------------------------

    def test_clean_fixture_passes(self, tmp_path: Path, quality_output_dir: Path) -> None:
        result = self._run_shell(tmp_path, quality_output_dir)
        assert result.returncode == 0, result.stdout + result.stderr
        status = self._status(quality_output_dir)
        assert status["fail_count"] == 0
        assert status["warning_count"] == 0
        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "✓ Pass" in markdown

    # ------------------------------------------------------------------
    # SA242: physical-line counting and the exact 799/800 boundary
    # ------------------------------------------------------------------

    def test_large_file_counter_counts_unterminated_final_line(self, tmp_path: Path) -> None:
        """The counter includes a final physical line without a newline."""
        shell_text = _SHELL_PATH.read_text(encoding="utf-8")
        assert 'grep -c "" "$python_file"' in shell_text, (
            "check_quality.sh must count physical lines, not newline bytes"
        )
        no_newline_800 = tmp_path / "no_newline_800.py"
        no_newline_800.write_text("\n".join(f"# line {index}" for index in range(800)))
        newline_799 = tmp_path / "newline_799.py"
        newline_799.write_text("\n".join(f"# line {index}" for index in range(799)) + "\n")
        script = (
            "for python_file do "
            'line_count=$(grep -c "" "$python_file" 2>/dev/null || true); '
            "line_count=${line_count:-0}; "
            'printf "%s\\t%s\\n" "$line_count" "$python_file"; '
            "done"
        )
        result = subprocess.run(
            ["sh", "-c", script, "sh", str(no_newline_800), str(newline_799)],
            capture_output=True,
            text=True,
            check=True,
        )
        counts = {
            line.split("\t", 1)[1]: int(line.split("\t", 1)[0])
            for line in result.stdout.splitlines()
        }
        assert counts[str(no_newline_800)] == 800
        assert counts[str(newline_799)] == 799
