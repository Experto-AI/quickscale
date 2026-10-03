"""
Control cases for the quality gate in ``check_quality.sh`` (SA231).

Each covered failure mode is fed a synthetic violation through the real
checked-in gate script and must make the gate exit non-zero; the paired
accepted run proves the same fixture passes, so the failure direction cannot
pass by accident.

Every run writes its artifacts under a per-test ``QUALITY_OUTPUT_DIR`` so the
repository's ``.quickscale`` directory is never touched.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.test_quality_baseline_monotonicity import _POETRY_STUB

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_SHELL_PATH = _SCRIPT_DIR / "check_quality.sh"
_DEFAULT_BASE_REF = "main"

_ORCHESTRATION_FILE = "quickscale_core/src/quickscale_core/dr_engine/orchestration.py"
_NEW_BIG_FILE = "quickscale_core/src/quickscale_core/new_big.py"
# The stub reports this many lines for ``_ORCHESTRATION_FILE``; the fixture
# ceiling controls the verdict.
_STUB_LINE_COUNT = 2000
_WAIVER_EXPIRES = "2027-03-31"

_FIND_STUB = (
    "#!/bin/bash\n"
    "# stub find -- report the listed file at a controlled size\n"
    f'echo "{_STUB_LINE_COUNT}\t{_ORCHESTRATION_FILE}"\n'
    "exit 0\n"
)

_FIND_STUB_WITH_NEW_FILE = (
    "#!/bin/bash\n"
    "# stub find -- report the listed file plus one unlisted large file\n"
    f'echo "{_STUB_LINE_COUNT}\t{_ORCHESTRATION_FILE}"\n'
    f'echo "900\t{_NEW_BIG_FILE}"\n'
    "exit 0\n"
)

_DUPLICATION_ENTRY = (
    '{"message-id": "R0801", "message": "Similar lines in 2 files", '
    '"path": "quickscale_core/src/quickscale_core/new_dup.py", "line": 10, '
    '"endLine": 20, "locations": ['
    '{"path": "quickscale_core/src/quickscale_core/new_dup.py", "line": 10, '
    '"endLine": 20}, '
    '{"path": "quickscale_core/src/quickscale_core/other.py", "line": 30, '
    '"endLine": 40}]}'
)
_DUPLICATION_JSON = f"[{_DUPLICATION_ENTRY}]"
_DUPLICATION_POETRY_STUB = _POETRY_STUB.replace(
    """        # Pylint duplication --- return empty list
        if tool == "pylint":
            print("[]")
            return 0""",
    f"""        # Pylint duplication --- one synthetic block; pylint exits 8
        if tool == "pylint":
            print({_DUPLICATION_JSON!r})
            return 8""",
)
assert _DUPLICATION_POETRY_STUB != _POETRY_STUB, "poetry stub pylint branch not found"


class TestQualityGateControl:
    """Control cases for the quality gate."""

    # ------------------------------------------------------------------
    # Fixtures and helpers
    # ------------------------------------------------------------------

    @pytest.fixture
    def quality_output_dir(self, tmp_path: Path) -> Path:
        """Per-test artifact dir; the repository ``.quickscale`` is untouched."""
        return tmp_path / "quality-artifacts"

    def _poetry_stub(self, tmp_path: Path, content: str = _POETRY_STUB) -> Path:
        """Create a stub ``poetry`` script and return the bin directory path."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        stub = bin_dir / "poetry"
        stub.write_text(content, encoding="utf-8")
        stub.chmod(0o755)
        return bin_dir

    def _find_stub(self, tmp_path: Path, content: str = _FIND_STUB) -> Path:
        """Create a stub ``find`` script reporting the controlled file sizes."""
        bin_dir = tmp_path / "findbin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        stub = bin_dir / "find"
        stub.write_text(content, encoding="utf-8")
        stub.chmod(0o755)
        return bin_dir

    def _temp_inputs(
        self,
        tmp_path: Path,
        *,
        file_length_entries: dict[str, int],
        duplication_blocks: int | None = None,
    ) -> tuple[Path, Path]:
        """
        Return a temp baseline and ledger carrying the fixture overrides.

        Every synthetic ``file_length`` entry gets a matching waiver so the
        monotonicity gate accepts the fixture; the real ledger is used
        otherwise, minus the duplication waiver when the ceiling is lowered.
        """
        baseline = json.loads(
            (_REPO_ROOT / "scripts" / "quality_baseline.json").read_text(encoding="utf-8")
        )
        baseline["file_length"] = {
            "allowed_files": {
                path: {
                    "max_lines": max_lines,
                    "reason": "control-case fixture",
                }
                for path, max_lines in file_length_entries.items()
            }
        }
        if duplication_blocks is not None:
            baseline["duplication"] = {"allowed_blocks": duplication_blocks}
        temp_baseline = tmp_path / "baseline_control.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        ledger = json.loads(
            (_REPO_ROOT / "scripts" / "quality_waivers.json").read_text(encoding="utf-8")
        )
        waivers = list(ledger["waivers"])
        if duplication_blocks == 0:
            waivers = [
                waiver for waiver in waivers if waiver["entry_key"] != "duplication:allowed_blocks"
            ]
        for index, (path, max_lines) in enumerate(file_length_entries.items()):
            waivers.append(
                {
                    "waiver_id": f"W-CTRL-FL-{index}",
                    "entry_key": f"file_length:{path}",
                    "base_ceiling": 0,
                    "ceiling": max_lines,
                    "owner": "test@example.com",
                    "reason": "Control-case fixture for the file-length ratchet",
                    "expires_on": _WAIVER_EXPIRES,
                    "decision_ref": "file-size-metric-policy",
                }
            )
        ledger["waivers"] = waivers
        temp_waivers = tmp_path / "waivers_control.json"
        temp_waivers.write_text(json.dumps(ledger), encoding="utf-8")
        return temp_baseline, temp_waivers

    def _run_shell(
        self,
        quality_output_dir: Path,
        extra_env: dict[str, str] | None = None,
        stub_dir: Path | None = None,
        find_stub_dir: Path | None = None,
    ) -> subprocess.CompletedProcess:
        """Run the real ``check_quality.sh`` with the PATH stubs applied."""
        env = os.environ.copy()
        if stub_dir:
            env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
        if find_stub_dir:
            env["PATH"] = f"{find_stub_dir}:{env['PATH']}"
        env["QUALITY_OUTPUT_DIR"] = str(quality_output_dir)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [str(_SHELL_PATH)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=180,
            env=env,
        )

    # ------------------------------------------------------------------
    # Control cases
    # ------------------------------------------------------------------

    def test_listed_ceiling_accepts_the_file(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A listed file within its ceiling produces no regression."""
        poetry_bin = self._poetry_stub(tmp_path)
        find_bin = self._find_stub(tmp_path)
        temp_baseline, temp_waivers = self._temp_inputs(
            tmp_path, file_length_entries={_ORCHESTRATION_FILE: 2897}
        )
        result = self._run_shell(
            quality_output_dir,
            stub_dir=poetry_bin,
            find_stub_dir=find_bin,
            extra_env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
                "QUALITY_BASELINE_BASE_REF": _DEFAULT_BASE_REF,
            },
        )
        assert result.returncode == 0, (
            f"Expected exit 0 for a listed file within its ceiling, "
            f"got {result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        status = json.loads(
            (quality_output_dir / "quality_gate_status.json").read_text(encoding="utf-8")
        )
        assert status["total_regressions"] == 0
        assert status["critical_regressions"] == 0

        report = json.loads(
            (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
        )
        assert report["summary"]["large_files_error"] == 1
        assert report["regressions"]["large_files"]["critical_count"] == 0

    def test_grown_file_fails_the_gate(self, tmp_path: Path, quality_output_dir: Path) -> None:
        """A file grown past its listed ceiling fails the gate."""
        poetry_bin = self._poetry_stub(tmp_path)
        find_bin = self._find_stub(tmp_path)
        temp_baseline, temp_waivers = self._temp_inputs(
            tmp_path, file_length_entries={_ORCHESTRATION_FILE: _STUB_LINE_COUNT - 1}
        )
        result = self._run_shell(
            quality_output_dir,
            stub_dir=poetry_bin,
            find_stub_dir=find_bin,
            extra_env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
                "QUALITY_BASELINE_BASE_REF": _DEFAULT_BASE_REF,
            },
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for a file grown past its ceiling, "
            f"got {result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        status = json.loads(
            (quality_output_dir / "quality_gate_status.json").read_text(encoding="utf-8")
        )
        assert status["critical_regressions"] == 1
        assert status["total_regressions"] == 1

        report = json.loads(
            (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
        )
        grown = report["regressions"]["large_files"]["new_or_grown"]
        assert [entry["file"] for entry in grown] == [_ORCHESTRATION_FILE]
        assert grown[0]["regression_type"] == "grown"
        assert grown[0]["allowed_max_lines"] == _STUB_LINE_COUNT - 1

        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "Large file" in markdown
        assert _ORCHESTRATION_FILE in markdown

    def test_unlisted_large_file_fails_the_gate(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A file at or above 800 lines with no baseline entry fails the gate."""
        poetry_bin = self._poetry_stub(tmp_path)
        find_bin = self._find_stub(tmp_path, _FIND_STUB_WITH_NEW_FILE)
        temp_baseline, temp_waivers = self._temp_inputs(
            tmp_path, file_length_entries={_ORCHESTRATION_FILE: 2897}
        )
        result = self._run_shell(
            quality_output_dir,
            stub_dir=poetry_bin,
            find_stub_dir=find_bin,
            extra_env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
                "QUALITY_BASELINE_BASE_REF": _DEFAULT_BASE_REF,
            },
        )
        assert result.returncode == 2, (
            f"Expected exit 2 for an unlisted large file, "
            f"got {result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        status = json.loads(
            (quality_output_dir / "quality_gate_status.json").read_text(encoding="utf-8")
        )
        assert status["critical_regressions"] == 1
        assert status["total_regressions"] == 1

        report = json.loads(
            (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
        )
        new_files = report["regressions"]["large_files"]["new_or_grown"]
        assert [entry["file"] for entry in new_files] == [_NEW_BIG_FILE]
        assert new_files[0]["regression_type"] == "new"
        assert new_files[0]["allowed_max_lines"] is None

        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "new at or above 800" in markdown
        assert _NEW_BIG_FILE in markdown

    def test_new_duplication_block_fails_the_gate(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A duplication count above the accepted ceiling fails the gate."""
        poetry_bin = self._poetry_stub(tmp_path, _DUPLICATION_POETRY_STUB)
        find_bin = self._find_stub(tmp_path)
        temp_baseline, temp_waivers = self._temp_inputs(
            tmp_path,
            file_length_entries={_ORCHESTRATION_FILE: 2897},
            duplication_blocks=0,
        )
        result = self._run_shell(
            quality_output_dir,
            stub_dir=poetry_bin,
            find_stub_dir=find_bin,
            extra_env={
                "QUALITY_BASELINE_FILE": str(temp_baseline),
                "QUALITY_WAIVERS_FILE": str(temp_waivers),
                "QUALITY_BASELINE_BASE_REF": _DEFAULT_BASE_REF,
            },
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for a new duplication block, "
            f"got {result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        status = json.loads(
            (quality_output_dir / "quality_gate_status.json").read_text(encoding="utf-8")
        )
        assert status["warning_regressions"] == 1
        assert status["total_regressions"] == 1

        report = json.loads(
            (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
        )
        assert report["summary"]["duplication_blocks"] == 1
        blocks = report["regressions"]["duplication"]["new_blocks"]
        assert [entry["message-id"] for entry in blocks] == ["R0801"]

        markdown = (quality_output_dir / "quality_report.md").read_text(encoding="utf-8")
        assert "Duplication:" in markdown
