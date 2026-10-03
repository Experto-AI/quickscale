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

    # ------------------------------------------------------------------
    # SA233: moved complexity entries
    # ------------------------------------------------------------------

    _MOVED_BASELINE_KEY = "quickscale_core.sample.old_home.helper"
    _MOVED_MODULE = "quickscale_core.sample.new_home"
    _MOVED_PATH = "quickscale_core/src/quickscale_core/sample/new_home.py"

    @staticmethod
    def _radon_entry(complexity: int) -> dict:
        """Return one radon function record named ``helper``."""
        return {
            "name": "helper",
            "type": "function",
            "complexity": complexity,
            "rank": "C",
            "lineno": 1,
            "endline": 9,
        }

    def _radon_stub(
        self,
        tmp_path: Path,
        actual_files: dict[str, list[dict]],
        inventory_files: dict[str, list[dict]],
    ) -> Path:
        """
        Return a poetry stub with per-run radon output.

        ``--min`` marks the threshold-filtered run; its absence marks the
        full-grade inventory run.
        """
        actual_json = json.dumps(actual_files)
        inventory_json = json.dumps(inventory_files)
        poetry_stub = _POETRY_STUB.replace(
            """        # Radon analysis --- return empty JSON
        if tool == "radon":
            print("{}")
            return 0""",
            f"""        # Radon analysis --- controlled per-run output
        if tool == "radon":
            if "--min" in tool_args:
                print({actual_json!r})
            else:
                print({inventory_json!r})
            return 0""",
        )
        assert poetry_stub != _POETRY_STUB, "poetry stub radon branch not found"
        return self._poetry_stub(tmp_path, poetry_stub)

    def _complexity_inputs(
        self, tmp_path: Path, entries: list[tuple[str, str, int]]
    ) -> tuple[Path, Path]:
        """Return a baseline/ledger pair adding the given complexity entries."""
        baseline = json.loads(
            (_REPO_ROOT / "scripts" / "quality_baseline.json").read_text(encoding="utf-8")
        )
        for module, qualname, ceiling in entries:
            baseline["complexity"]["allowed_functions"][f"{module}.{qualname}"] = {
                "module": module,
                "qualname": qualname,
                "type": "function",
                "max_complexity": ceiling,
            }
        # The find stub reports the orchestration file at 2,000 lines; list it
        # so the fixture isolates the moved complexity entries.
        baseline["file_length"] = {
            "allowed_files": {
                _ORCHESTRATION_FILE: {
                    "max_lines": 2897,
                    "reason": "Control-case fixture",
                }
            }
        }
        temp_baseline = tmp_path / "baseline_complexity_control.json"
        temp_baseline.write_text(json.dumps(baseline), encoding="utf-8")

        ledger = json.loads(
            (_REPO_ROOT / "scripts" / "quality_waivers.json").read_text(encoding="utf-8")
        )
        for index, (module, qualname, ceiling) in enumerate(entries):
            ledger["waivers"].append(
                {
                    "waiver_id": f"W-CTRL-CPX-{index}",
                    "entry_key": f"complexity:{module}.{qualname}",
                    "base_ceiling": 0,
                    "ceiling": ceiling,
                    "owner": "test@example.com",
                    "reason": "Control-case fixture for a complexity entry",
                    "expires_on": _WAIVER_EXPIRES,
                    "decision_ref": "quality-baseline-monotonicity",
                }
            )
        ledger["waivers"].append(
            {
                "waiver_id": "W-CTRL-FL-MOVE",
                "entry_key": f"file_length:{_ORCHESTRATION_FILE}",
                "base_ceiling": 0,
                "ceiling": 2897,
                "owner": "test@example.com",
                "reason": "Control-case fixture for the file-length ratchet",
                "expires_on": _WAIVER_EXPIRES,
                "decision_ref": "file-size-metric-policy",
            }
        )
        temp_waivers = tmp_path / "waivers_complexity_control.json"
        temp_waivers.write_text(json.dumps(ledger), encoding="utf-8")
        return temp_baseline, temp_waivers

    def _moved_complexity_stubs(
        self, tmp_path: Path, complexity: int
    ) -> tuple[Path, Path, Path, Path]:
        """Return poetry/find stub dirs and a baseline/ledger pair for a move."""
        files = {self._MOVED_PATH: [self._radon_entry(complexity)]}
        poetry_bin = self._radon_stub(tmp_path, files, files)
        find_bin = self._find_stub(tmp_path)
        temp_baseline, temp_waivers = self._complexity_inputs(
            tmp_path, [("quickscale_core.sample.old_home", "helper", 12)]
        )
        return poetry_bin, find_bin, temp_baseline, temp_waivers

    def test_pure_move_is_not_a_regression(self, tmp_path: Path, quality_output_dir: Path) -> None:
        """A function at its pre-move ceiling produces no regression."""
        poetry_bin, find_bin, temp_baseline, temp_waivers = self._moved_complexity_stubs(
            tmp_path, 12
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
            f"Expected exit 0 for a pure move, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        status = json.loads(
            (quality_output_dir / "quality_gate_status.json").read_text(encoding="utf-8")
        )
        assert status["total_regressions"] == 0
        report = json.loads(
            (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
        )
        assert report["regressions"]["complexity"]["new_or_worse"] == []
        resolved = report["regressions"]["complexity"]["resolved"]
        assert self._MOVED_BASELINE_KEY not in [entry["key"] for entry in resolved]

    def test_worsened_move_fails_the_gate(self, tmp_path: Path, quality_output_dir: Path) -> None:
        """A moved function above its pre-move ceiling fails the gate."""
        poetry_bin, find_bin, temp_baseline, temp_waivers = self._moved_complexity_stubs(
            tmp_path, 15
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
            f"Expected exit 1 for a worsened move, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        status = json.loads(
            (quality_output_dir / "quality_gate_status.json").read_text(encoding="utf-8")
        )
        assert status["warning_regressions"] == 1
        report = json.loads(
            (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
        )
        regressions = report["regressions"]["complexity"]["new_or_worse"]
        assert len(regressions) == 1
        entry = regressions[0]
        assert entry["module"] == self._MOVED_MODULE
        assert entry["qualname"] == "helper"
        assert entry["regression_type"] == "increased"
        assert entry["allowed_max_complexity"] == 12
        assert entry["delta"] == 3

    def test_reduced_stationary_function_is_not_a_move_source(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """A function reduced below the reporting threshold is not a move source."""
        actual = {
            "quickscale_core/src/quickscale_core/sample/new_home.py": [self._radon_entry(12)],
        }
        inventory = {
            "quickscale_core/src/quickscale_core/sample/old_home.py": [self._radon_entry(5)],
            "quickscale_core/src/quickscale_core/sample/new_home.py": [self._radon_entry(12)],
        }
        poetry_bin = self._radon_stub(tmp_path, actual, inventory)
        find_bin = self._find_stub(tmp_path)
        temp_baseline, temp_waivers = self._complexity_inputs(
            tmp_path, [("quickscale_core.sample.old_home", "helper", 12)]
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
            f"Expected exit 1 for a new function beside a reduced stationary one, "
            f"got {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        report = json.loads(
            (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
        )
        regressions = report["regressions"]["complexity"]["new_or_worse"]
        assert len(regressions) == 1
        entry = regressions[0]
        assert entry["module"] == "quickscale_core.sample.new_home"
        assert entry["qualname"] == "helper"
        assert entry["regression_type"] == "new"
        assert entry["allowed_max_complexity"] is None

    def test_move_matching_is_order_independent(
        self, tmp_path: Path, quality_output_dir: Path
    ) -> None:
        """Permuting analyzer file order cannot change the move verdict."""
        a_path = "quickscale_core/src/quickscale_core/sample/a_home.py"
        z_path = "quickscale_core/src/quickscale_core/sample/z_home.py"
        entries = [
            ("quickscale_core.sample.old1", "helper", 20),
            ("quickscale_core.sample.old2", "helper", 12),
        ]
        for order, files in (
            (
                "a-first",
                {a_path: [self._radon_entry(20)], z_path: [self._radon_entry(12)]},
            ),
            (
                "z-first",
                {z_path: [self._radon_entry(12)], a_path: [self._radon_entry(20)]},
            ),
        ):
            order_dir = tmp_path / order
            poetry_bin = self._radon_stub(order_dir, files, files)
            find_bin = self._find_stub(order_dir)
            temp_baseline, temp_waivers = self._complexity_inputs(order_dir, entries)
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
                f"Expected exit 0 for {order} move ordering, got {result.returncode}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
            report = json.loads(
                (quality_output_dir / "quality_report.json").read_text(encoding="utf-8")
            )
            assert report["regressions"]["complexity"]["new_or_worse"] == []

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
