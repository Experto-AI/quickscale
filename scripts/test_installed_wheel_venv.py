"""
Focused behavioural tests for the SA112a installed-wheel provisioner.

These tests exercise the four-file SA112a scope (``scripts/smoke_install.sh``,
``scripts/_installed_wheel_venv.sh``, ``scripts/provision_installed_venv.sh``)
against a fake repository and a fake Poetry toolchain, so the full pipeline
(stage -> build -> venv -> install -> workdir) is exercised service-free in
seconds.  The fake Poetry builds real, pip-installable wheels, so the
provisioner's success path is a true end-to-end run with the exact
``[installed-wheel]`` stderr markers and the one-line stdout contract.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
WRAPPER = SCRIPTS / "provision_installed_venv.sh"
HELPER = SCRIPTS / "_installed_wheel_venv.sh"
SMOKE_GATE = SCRIPTS / "smoke_install.sh"

VERSION = "0.87.0"

EXPECTED_MARKERS = (
    "[installed-wheel] BUILD quickscale_core==0.87.0",
    "[installed-wheel] BUILD quickscale_cli==0.87.0",
    "[installed-wheel] BUILD quickscale==0.87.0",
    "[installed-wheel] INSTALL quickscale_core==0.87.0",
    "[installed-wheel] INSTALL quickscale_cli==0.87.0",
    "[installed-wheel] INSTALL quickscale==0.87.0",
)

EXPECTED_SUBCOMMANDS = (
    "version",
    "up",
    "down",
    "shell",
    "manage",
    "logs",
    "ps",
    "deploy",
    "dr",
    "update",
    "push",
    "plan",
    "apply",
    "status",
    "remove",
)

FAKE_POETRY = r'''#!/usr/bin/env python3
"""Fake poetry used by test_installed_wheel_venv.py (SA112a focused tests).

Implements just enough of the Poetry surface the provisioner calls (env use,
env info -p, build, --version) to drive the full staged-build pipeline.  The
build command emits a real, pip-installable wheel per staged package so the
provisioner's install step genuinely succeeds.
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
import time
import zipfile
from pathlib import Path


def _log(line: str) -> None:
    path = os.environ.get("FAKE_POETRY_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(line + "\n")


def _name_and_version(pyproject: Path) -> tuple[str, str]:
    name = "fake-package"
    version = "0.0.0"
    for raw in pyproject.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith('name = "'):
            name = line.split('"', 1)[1].split('"', 1)[0]
        elif line.startswith('version = "'):
            version = line.split('"', 1)[1].split('"', 1)[0]
    return name.replace("-", "_"), version


def _build_wheel(dist_dir: Path, name: str, version: str) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel = dist_dir / f"{name}-{version}-py3-none-any.whl"
    files: dict[str, bytes] = {
        f"{name}/__init__.py": b"# fake wheel\n",
        f"{name}-{version}.dist-info/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {name}\n"
            f"Version: {version}\n"
            "Summary: fake wheel for installed-wheel provisioner tests\n"
        ).encode(),
        f"{name}-{version}.dist-info/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: fake-poetry\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode(),
    }
    record: list[str] = []
    for relative, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        record.append(f"{relative},sha256={digest},{len(data)}")
    record.append(f"{name}-{version}.dist-info/RECORD,,")
    files[f"{name}-{version}.dist-info/RECORD"] = ("\n".join(record) + "\n").encode()
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, data in files.items():
            archive.writestr(relative, data)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return 0
    command = args[0]
    if command == "--version":
        version_exit = int(os.environ.get("FAKE_POETRY_VERSION_EXIT", "0"))
        if version_exit:
            return version_exit
        print("Poetry (version 2.4.1)")
        return 0
    if command == "env":
        if len(args) >= 2 and args[1] == "use":
            return 0
        if len(args) >= 3 and args[1] == "info" and args[2] == "-p":
            base = os.environ.get("POETRY_VIRTUALENVS_PATH", "/tmp")
            print(os.path.join(base, "fake-env"))
            return 0
    if command == "build":
        _log("BUILD_START cwd=%s" % os.getcwd())
        sentinel = Path("REGRESSION_SENTINEL")
        _log("SENTINEL=%s" % ("present" if sentinel.exists() else "absent"))
        sleep = float(os.environ.get("FAKE_POETRY_BUILD_SLEEP", "0"))
        if sleep:
            time.sleep(sleep)
        exit_code = int(os.environ.get("FAKE_POETRY_BUILD_EXIT", "0"))
        if exit_code == 0:
            name, version = _name_and_version(Path("pyproject.toml"))
            _build_wheel(Path("dist"), name, version)
        _log("BUILD_END exit=%d" % exit_code)
        return exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

VERSION_SHIM = r'''#!/usr/bin/env python3
"""Version-reporting python shim for provisioner selection tests.

The provisioner probes candidates with ``python -c <spec check>``; this shim
executes that code with a fake ``sys`` module whose ``version_info`` derives
from its own executable basename (python3.13 -> 3.13, etc.), so candidate
ordering can be tested without real 3.13/3.15 binaries.
"""
from __future__ import annotations

import os
import sys
import types

if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    name = os.path.basename(sys.argv[0])  # e.g. python3.14
    fake_version = tuple(int(part) for part in name.removeprefix("python").split("."))
    fake_sys = types.SimpleNamespace(version_info=fake_version, exit=sys.exit)
    real_import = __import__

    def patched_import(module_name: str, *args: object, **kwargs: object) -> object:
        if module_name == "sys":
            return fake_sys
        return real_import(module_name, *args, **kwargs)

    sys.modules["builtins"].__import__ = patched_import  # type: ignore[assignment]
    code = sys.argv[2]
    exec(compile(code, "<version-shim>", "exec"), {"__name__": "__main__"})
    sys.exit(0)
sys.exit(0)
'''

SLOW_PYTHON_SHIM = r'''#!/usr/bin/env python3
"""Spec-check python shim for the F-003 early-signal tests.

Identical to VERSION_SHIM except that a ``-c`` invocation first writes a
synchronization marker file and sleeps before answering, so a test can signal
the provisioner deterministically while it is inside its pre-allocation
toolchain window (after OUTPUT_DIR adoption, before internal class
allocation).
"""
from __future__ import annotations

import os
import sys
import time
import types

if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    marker = os.environ.get("SLOW_PYTHON_MARKER")
    if marker:
        with open(marker, "w", encoding="utf-8") as stream:
            stream.write("ready\n")
    sleep = float(os.environ.get("SLOW_PYTHON_SLEEP", "0"))
    if sleep:
        time.sleep(sleep)
    name = os.path.basename(sys.argv[0])  # e.g. python3.14
    fake_version = tuple(int(part) for part in name.removeprefix("python").split("."))
    fake_sys = types.SimpleNamespace(version_info=fake_version, exit=sys.exit)
    real_import = __import__

    def patched_import(module_name: str, *args: object, **kwargs: object) -> object:
        if module_name == "sys":
            return fake_sys
        return real_import(module_name, *args, **kwargs)

    sys.modules["builtins"].__import__ = patched_import  # type: ignore[assignment]
    code = sys.argv[2]
    exec(compile(code, "<version-shim>", "exec"), {"__name__": "__main__"})
    sys.exit(0)
sys.exit(0)
'''


def _write_repo(root: Path) -> None:
    """Create a minimal repository the provisioner accepts as REPO_ROOT."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fake-monorepo"\nversion = "0.0.0"\nrequires-python = ">=3.14,<3.15"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# fake repo\n", encoding="utf-8")
    for package in ("quickscale_core", "quickscale_cli", "quickscale"):
        pkg = root / package
        pkg.mkdir(parents=True, exist_ok=True)
        path_dep = (
            'quickscale-core = {path = "../quickscale_core", develop = true}\n'
            if package == "quickscale_cli"
            else ""
        )
        (pkg / "pyproject.toml").write_text(
            f'[project]\nname = "{package.replace("_", "-")}"\n'
            f'version = "{VERSION}"\nrequires-python = ">=3.14,<3.15"\n'
            f"{path_dep}",
            encoding="utf-8",
        )
    # A source file whose bytes must never change across provisioner runs.
    (root / "quickscale_core" / "src").mkdir(parents=True, exist_ok=True)
    (root / "quickscale_core" / "src" / "core.py").write_text(
        "SOURCE_BYTES = 1\n", encoding="utf-8"
    )


def _snapshot_source(root: Path) -> dict[str, bytes]:
    """Hash every source file that must remain byte-stable."""
    snapshot: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".venv" not in path.parts and "__pycache__" not in path.parts:
            snapshot[str(path.relative_to(root))] = path.read_bytes()
    return snapshot


def _fake_environment(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    _write_repo(repo)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    poetry = bin_dir / "poetry"
    poetry.write_text(FAKE_POETRY, encoding="utf-8")
    poetry.chmod(0o755)
    # The provisioner selects a python3.14 candidate; symlink the interpreter
    # running this test suite (3.14.x in the repo venv).
    python_link = bin_dir / "python3.14"
    if python_link.is_symlink() or python_link.exists():
        python_link.unlink()
    python_link.symlink_to(sys.executable)

    tmp_root = tmp_path / "tmp"
    tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(bin_dir), env.get("PATH", "")))
    env["TMPDIR"] = str(tmp_root)
    env["FAKE_POETRY_LOG"] = str(tmp_path / "poetry.log")
    env.pop("QS_SMOKE_REGRESSION_CORE", None)
    return repo, env


def _run_wrapper(
    env: dict[str, str], repo: Path, output: Path, timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(WRAPPER), str(repo), str(output)],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _internal_leftovers(tmp_path: Path, env: dict[str, str]) -> list[Path]:
    return sorted(Path(env["TMPDIR"]).glob("quickscale-iv-*"))


def _slow_python_environment(tmp_path: Path, marker: Path) -> tuple[Path, dict[str, str]]:
    """
    Fake repo/env whose python3.14 candidate is a slow spec-check shim.

    The shim writes ``marker`` and sleeps before answering the provisioner's
    spec probe, so a test can signal the provisioner while it is between
    OUTPUT_DIR adoption and internal class allocation.
    """
    repo, env = _fake_environment(tmp_path)
    shim = tmp_path / "bin" / "python3.14"
    if shim.is_symlink() or shim.exists():
        shim.unlink()
    shim.write_text(SLOW_PYTHON_SHIM, encoding="utf-8")
    shim.chmod(0o755)
    env["SLOW_PYTHON_MARKER"] = str(marker)
    env["SLOW_PYTHON_SLEEP"] = "5"
    return repo, env


def _popen_and_signal_after_marker(
    argv: list[str], env: dict[str, str], marker: Path, signum: signal.Signals
) -> tuple[int, str, str]:
    """Start a process, wait for the slow-shim marker, signal it, and reap it."""
    process = subprocess.Popen(
        argv,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if marker.exists():
                break
            time.sleep(0.05)
        assert marker.exists(), "slow python shim never wrote its marker"
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    assert process.returncode is not None
    return process.returncode, stdout, stderr


def test_wrapper_usage_and_argument_errors(tmp_path: Path) -> None:
    """Missing/relative arguments exit 2, print usage to stderr, keep stdout empty."""
    _, env = _fake_environment(tmp_path)

    for argv in ([], [str(tmp_path)], ["/tmp"]):
        result = subprocess.run(
            [str(WRAPPER), *argv], env=env, capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 2, argv
        assert result.stdout == "", argv
        assert "Usage: provision_installed_venv.sh REPO_ROOT OUTPUT_DIR" in result.stderr, argv

    repo, env = _fake_environment(tmp_path)
    relative = subprocess.run(
        [str(WRAPPER), "relative-root", str(tmp_path / "output")],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert relative.returncode == 2
    assert relative.stdout == ""
    assert "REPO_ROOT must be an absolute path" in relative.stderr

    repo, env = _fake_environment(tmp_path)
    relative_output = subprocess.run(
        [str(WRAPPER), str(repo), "relative-output"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert relative_output.returncode == 2
    assert relative_output.stdout == ""
    assert "OUTPUT_DIR must be an absolute path" in relative_output.stderr


def test_seam_rejects_non_repo_and_non_empty_output(tmp_path: Path) -> None:
    """REPO_ROOT without VERSION/pyproject and a non-empty OUTPUT_DIR exit 2."""
    repo, env = _fake_environment(tmp_path)
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    result = _run_wrapper(env, not_a_repo, tmp_path / "output")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "VERSION file not found" in result.stderr

    repo, env = _fake_environment(tmp_path)
    pre_filled = tmp_path / "prefilled"
    pre_filled.mkdir()
    (pre_filled / "caller-data.txt").write_text("keep me\n", encoding="utf-8")
    result = _run_wrapper(env, repo, pre_filled)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "OUTPUT_DIR must not exist or must be empty" in result.stderr
    # The helper never deletes pre-existing caller data.
    assert (pre_filled / "caller-data.txt").exists()


def test_success_streams_markers_and_output_survival(tmp_path: Path) -> None:
    """Success: exit 0, one-line stdout, six markers once/in order, output survives."""
    repo, env = _fake_environment(tmp_path)
    output = tmp_path / "output"
    result = _run_wrapper(env, repo, output)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{output}\n"
    markers = [line for line in result.stderr.splitlines() if line.startswith("[installed-wheel]")]
    assert markers == list(EXPECTED_MARKERS)

    assert (output / "venv" / "bin" / "python").exists()
    assert (output / "work").is_dir()
    assert _internal_leftovers(tmp_path, env) == []


def test_source_inertness_and_byte_stability(tmp_path: Path) -> None:
    """Neither a success nor a failed run may rewrite any source file bytes."""
    repo, env = _fake_environment(tmp_path)
    before = _snapshot_source(repo)

    result = _run_wrapper(env, repo, tmp_path / "output-success")
    assert result.returncode == 0, result.stderr
    assert _snapshot_source(repo) == before

    env["FAKE_POETRY_BUILD_EXIT"] = "37"
    result = _run_wrapper(env, repo, tmp_path / "output-failure")
    assert result.returncode == 37, result.stderr
    assert _snapshot_source(repo) == before


def test_injected_exit_37_cleans_every_class(tmp_path: Path) -> None:
    """A build failure propagates its exact status and cleans all four classes."""
    repo, env = _fake_environment(tmp_path)
    env["FAKE_POETRY_BUILD_EXIT"] = "37"
    output = tmp_path / "output"
    result = _run_wrapper(env, repo, output)

    assert result.returncode == 37
    assert result.stdout == ""
    assert not output.exists()
    assert _internal_leftovers(tmp_path, env) == []
    # Only the core BUILD marker was emitted before the failure.
    markers = [line for line in result.stderr.splitlines() if line.startswith("[installed-wheel]")]
    assert markers == [EXPECTED_MARKERS[0]]


def test_early_toolchain_failure_cleans_preexisting_empty_output(tmp_path: Path) -> None:
    """F-003: a pre-allocation toolchain failure cleans an adopted empty output."""
    repo, env = _fake_environment(tmp_path)
    # The fake poetry reports failure for --version, so the toolchain check
    # fails before any internal class is allocated.
    env["FAKE_POETRY_VERSION_EXIT"] = "1"
    output = tmp_path / "output"
    output.mkdir()

    result = _run_wrapper(env, repo, output)

    assert result.returncode == 1, result.stderr
    assert result.stdout == ""
    assert "[installed-wheel]" not in result.stderr
    assert not output.exists()
    assert _internal_leftovers(tmp_path, env) == []


def test_early_toolchain_failure_direct_source_dispatches_caller_trap(
    tmp_path: Path,
) -> None:
    """F-003: an early failure restores/dispatches traps and cleans the adopted empty output."""
    repo, env = _fake_environment(tmp_path)
    env["FAKE_POETRY_VERSION_EXIT"] = "1"
    output = tmp_path / "output"
    output.mkdir()

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
trap 'echo "CALLER_EXIT_STATUS=$?"' EXIT
trap 'echo CALLER_HUP' HUP
trap 'echo CALLER_INT' INT
trap 'echo CALLER_TERM' TERM
quickscale_provision_installed_venv '{repo}' '{output}'
"""
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, timeout=180
    )

    assert result.returncode == 1, result.stderr
    # The provisioner's own stdout stays empty on failure: the only stdout is
    # the caller's EXIT trap evidence carrying the exact initiating status.
    assert result.stdout == "CALLER_EXIT_STATUS=1\n"
    assert not output.exists()
    assert _internal_leftovers(tmp_path, env) == []


def test_success_with_preexisting_empty_output_survives(tmp_path: Path) -> None:
    """F-003: adopting a pre-existing empty OUTPUT_DIR does not disturb the success transfer."""
    repo, env = _fake_environment(tmp_path)
    output = tmp_path / "output"
    output.mkdir()

    result = _run_wrapper(env, repo, output)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{output}\n"
    assert (output / "venv" / "bin" / "python").exists()
    assert (output / "work").is_dir()
    assert _internal_leftovers(tmp_path, env) == []


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, 143),
        (signal.SIGINT, 130),
        (signal.SIGHUP, 129),
    ],
    ids=["TERM", "INT", "HUP"],
)
def test_synchronized_signal_cleanup_and_status(
    tmp_path: Path, signum: signal.Signals, expected: int
) -> None:
    """A signal during provisioning cleans all four classes and exits 128+signum."""
    repo, env = _fake_environment(tmp_path)
    env["FAKE_POETRY_BUILD_SLEEP"] = "2"
    output = tmp_path / "output"
    log_path = Path(env["FAKE_POETRY_LOG"])

    process = subprocess.Popen(
        [str(WRAPPER), str(repo), str(output)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if log_path.exists() and "BUILD_START" in log_path.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        assert "BUILD_START" in log_path.read_text(encoding="utf-8")
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == expected, (stdout, stderr)
    assert not output.exists()
    assert _internal_leftovers(tmp_path, env) == []


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, 143),
        (signal.SIGINT, 130),
        (signal.SIGHUP, 129),
    ],
    ids=["TERM", "INT", "HUP"],
)
def test_synchronized_early_signal_cleans_preexisting_empty_output(
    tmp_path: Path, signum: signal.Signals, expected: int
) -> None:
    """F-003: a signal in the pre-allocation window cleans an adopted pre-existing empty output."""
    marker = tmp_path / "slow-python.marker"
    repo, env = _slow_python_environment(tmp_path, marker)
    output = tmp_path / "output"
    output.mkdir()

    returncode, stdout, stderr = _popen_and_signal_after_marker(
        [str(WRAPPER), str(repo), str(output)], env, marker, signum
    )

    assert returncode == expected, (stdout, stderr)
    assert stdout == ""
    assert not output.exists()
    assert _internal_leftovers(tmp_path, env) == []


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, 143),
        (signal.SIGINT, 130),
        (signal.SIGHUP, 129),
    ],
    ids=["TERM", "INT", "HUP"],
)
def test_synchronized_early_signal_direct_source_dispatches_caller_trap(
    tmp_path: Path, signum: signal.Signals, expected: int
) -> None:
    """F-003: an early signal restores/dispatches traps and cleans the adopted empty output."""
    marker = tmp_path / "slow-python.marker"
    repo, env = _slow_python_environment(tmp_path, marker)
    output = tmp_path / "output"
    output.mkdir()

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
trap 'echo "CALLER_EXIT_STATUS=$?"' EXIT
trap 'echo CALLER_HUP' HUP
trap 'echo CALLER_INT' INT
trap 'echo CALLER_TERM' TERM
quickscale_provision_installed_venv '{repo}' '{output}'
"""
    returncode, stdout, stderr = _popen_and_signal_after_marker(
        ["bash", "-c", script], env, marker, signum
    )

    assert returncode == expected, (stdout, stderr)
    # The caller's EXIT trap fires with the exact signal status, and it is the
    # only stdout: the provisioner's own stdout stays empty on signal.
    assert stdout == f"CALLER_EXIT_STATUS={expected}\n"
    assert not output.exists()
    assert _internal_leftovers(tmp_path, env) == []


def test_caller_trap_parity(tmp_path: Path) -> None:
    """A direct (non-subshell) call restores the caller's traps exactly."""
    repo, env = _fake_environment(tmp_path)
    output = tmp_path / "output"
    before_file = tmp_path / "traps.before"
    after_file = tmp_path / "traps.after"
    seam_out = tmp_path / "seam.out"

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
trap 'echo CALLER_EXIT' EXIT
trap 'echo CALLER_HUP' HUP
trap 'echo CALLER_INT' INT
trap 'echo CALLER_TERM' TERM
capture() {{
    trap -p EXIT
    trap -p HUP
    trap -p INT
    trap -p TERM
}}
capture > '{before_file}'
quickscale_provision_installed_venv '{repo}' '{output}' > '{seam_out}'
capture > '{after_file}'
if ! diff -u '{before_file}' '{after_file}'; then
    echo 'TRAP MISMATCH' >&2
    exit 1
fi
if [[ "$(cat '{seam_out}')" != '{output}' ]]; then
    echo 'OUTPUT MISMATCH' >&2
    exit 1
fi
echo 'PARITY OK'
"""
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, timeout=180
    )
    assert result.returncode == 0, result.stderr
    assert "PARITY OK" in result.stdout
    # The caller's EXIT trap was restored and still fires on script exit.
    assert "CALLER_EXIT" in result.stdout


def test_repeated_invocation_success_then_failure_cleans_second_output(
    tmp_path: Path,
) -> None:
    """F-001: a failed run after a successful one in the same shell must not leak."""
    repo, env = _fake_environment(tmp_path)
    output_ok = tmp_path / "output-ok"
    output_fail = tmp_path / "output-fail"
    seam_ok = tmp_path / "seam-ok.out"
    seam_fail = tmp_path / "seam-fail.out"

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
quickscale_provision_installed_venv '{repo}' '{output_ok}' > '{seam_ok}'
FAKE_POETRY_BUILD_EXIT=37 quickscale_provision_installed_venv '{repo}' '{output_fail}' \\
    > '{seam_fail}'
"""
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, timeout=180
    )

    # The second (direct-source) invocation fails the whole shell with the
    # exact initiating status.
    assert result.returncode == 37, result.stderr
    # The first, transferred output survives; the second, failed output was
    # cleaned even though the shell already carried a transferred flag.
    assert (output_ok / "venv" / "bin" / "python").exists()
    assert not output_fail.exists()
    # Failure stdout on the seam stays empty; success stdout was the dir.
    assert seam_fail.read_text(encoding="utf-8") == ""
    assert seam_ok.read_text(encoding="utf-8") == f"{output_ok}\n"
    assert _internal_leftovers(tmp_path, env) == []


def test_repeated_invocation_success_then_signal_cleans_second_output(
    tmp_path: Path,
) -> None:
    """F-001: a signaled run after a successful one in the same shell must not leak."""
    repo, env = _fake_environment(tmp_path)
    output_ok = tmp_path / "output-ok"
    output_sig = tmp_path / "output-signaled"
    sig_log = tmp_path / "poetry-signal.log"

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
quickscale_provision_installed_venv '{repo}' '{output_ok}' >/dev/null
FAKE_POETRY_BUILD_SLEEP=2 FAKE_POETRY_LOG='{sig_log}' \\
    quickscale_provision_installed_venv '{repo}' '{output_sig}' >/dev/null
"""
    process = subprocess.Popen(
        ["bash", "-c", script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if sig_log.exists() and "BUILD_START" in sig_log.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        assert "BUILD_START" in sig_log.read_text(encoding="utf-8")
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 143, (stdout, stderr)
    # The first, transferred output survives; the second, signaled output was
    # cleaned despite the inherited transferred flag.
    assert (output_ok / "venv" / "bin" / "python").exists()
    assert not output_sig.exists()
    assert _internal_leftovers(tmp_path, env) == []


def test_caller_trap_dispatched_on_failure(tmp_path: Path) -> None:
    """F-002: direct-source failure restores and dispatches the caller's traps."""
    repo, env = _fake_environment(tmp_path)
    output = tmp_path / "output"
    probe = tmp_path / "traps.probe"

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
PROBE='{probe}'
trap 'echo "CALLER_EXIT_STATUS=$?"; trap -p EXIT HUP INT TERM > "$PROBE"' EXIT
trap 'echo CALLER_HUP' HUP
trap 'echo CALLER_INT' INT
trap 'echo CALLER_TERM' TERM
FAKE_POETRY_BUILD_EXIT=37 quickscale_provision_installed_venv '{repo}' '{output}'
"""
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, timeout=180
    )

    assert result.returncode == 37, result.stderr
    # The caller's EXIT trap was dispatched exactly once, with the exact
    # initiating status; the seam itself wrote nothing to stdout on failure.
    assert result.stdout == "CALLER_EXIT_STATUS=37\n"
    assert not output.exists()
    # The caller's HUP/INT/TERM registrations were restored before dispatch.
    probe_text = probe.read_text(encoding="utf-8")
    assert "CALLER_HUP" in probe_text
    assert "CALLER_INT" in probe_text
    assert "CALLER_TERM" in probe_text


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, 143),
        (signal.SIGINT, 130),
        (signal.SIGHUP, 129),
    ],
    ids=["TERM", "INT", "HUP"],
)
def test_caller_trap_dispatched_on_signal(
    tmp_path: Path, signum: signal.Signals, expected: int
) -> None:
    """F-002: direct-source signal restores the caller's traps and dispatches its EXIT trap."""
    repo, env = _fake_environment(tmp_path)
    env["FAKE_POETRY_BUILD_SLEEP"] = "2"
    output = tmp_path / "output"
    log_path = Path(env["FAKE_POETRY_LOG"])

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
trap 'echo "CALLER_EXIT_STATUS=$?"' EXIT
trap 'echo CALLER_HUP' HUP
trap 'echo CALLER_INT' INT
trap 'echo CALLER_TERM' TERM
quickscale_provision_installed_venv '{repo}' '{output}'
"""
    process = subprocess.Popen(
        ["bash", "-c", script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if log_path.exists() and "BUILD_START" in log_path.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        assert "BUILD_START" in log_path.read_text(encoding="utf-8")
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    # The caller's EXIT trap fires with the exact signal status (128 + signum),
    # and the seam itself wrote nothing to stdout on signal.
    assert process.returncode == expected, (stdout, stderr)
    assert stdout == f"CALLER_EXIT_STATUS={expected}\n"
    assert not output.exists()
    assert _internal_leftovers(tmp_path, env) == []


def test_regression_core_forwarding(tmp_path: Path) -> None:
    """QS_SMOKE_REGRESSION_CORE makes the provisioner stage core from that copy."""
    repo, env = _fake_environment(tmp_path)
    regression = tmp_path / "regression-core"
    shutil.copytree(repo / "quickscale_core", regression)
    (regression / "REGRESSION_SENTINEL").write_text("marker\n", encoding="utf-8")
    env["QS_SMOKE_REGRESSION_CORE"] = str(regression)

    result = _run_wrapper(env, repo, tmp_path / "output")
    assert result.returncode == 0, result.stderr
    log = Path(env["FAKE_POETRY_LOG"]).read_text(encoding="utf-8")
    assert "SENTINEL=present" in log

    # Control: without the env var the staged core carries no sentinel.
    repo, env = _fake_environment(tmp_path)
    control_log = tmp_path / "poetry-control.log"
    env["FAKE_POETRY_LOG"] = str(control_log)
    result = _run_wrapper(env, repo, tmp_path / "output-control")
    assert result.returncode == 0, result.stderr
    log = control_log.read_text(encoding="utf-8")
    assert "SENTINEL=absent" in log
    assert "SENTINEL=present" not in log


def test_python_candidate_selection_order(tmp_path: Path) -> None:
    """Candidate ordering skips out-of-spec interpreters and keeps the first valid one."""
    bin_dir = tmp_path / "shim-bin"
    bin_dir.mkdir()
    for minor in ("3.13", "3.14", "3.15"):
        shim = bin_dir / f"python{minor}"
        shim.write_text(VERSION_SHIM, encoding="utf-8")
        shim.chmod(0o755)

    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
result="$(
    printf '%s\\n' '{bin_dir}/python3.15' '{bin_dir}/python3.13' '{bin_dir}/python3.14' \\
    | quickscale_installed_wheel_select_python '>=3.14,<3.15'
)"
echo "SELECTED=$result"
"""
    env = os.environ.copy()
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert f"SELECTED={bin_dir}/python3.14" in result.stdout

    # No in-spec candidate -> selection fails.
    script = f"""#!/usr/bin/env bash
set -euo pipefail
source '{HELPER}'
if printf '%s\\n' '{bin_dir}/python3.13' '{bin_dir}/python3.15' \\
    | quickscale_installed_wheel_select_python '>=3.14,<3.15' >/dev/null; then
    echo 'UNEXPECTED SELECTION'
    exit 1
fi
echo 'NO MATCH OK'
"""
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert "NO MATCH OK" in result.stdout


def test_smoke_gate_oracle_and_probe_parity() -> None:
    """The gate keeps its 20 probes and its two-line terminal stdout oracle."""
    content = SMOKE_GATE.read_text(encoding="utf-8")

    success_line = "✅ All smoke tests passed!"
    green_line = "✅ Smoke install gate passed — all checks green."
    assert content.count(success_line) == 1
    assert content.count(green_line) == 1
    # Runtime order: the success line is the final echo before the gate's
    # exit 0; the green line is emitted by the EXIT-trap cleanup right after
    # a significant empty line (echo ""), i.e. second-final nonblank.
    assert content.strip().endswith(f'echo "{success_line}"\nexit 0')
    cleanup_tail = content[content.index("cleanup()") :]
    assert f'echo ""\n        echo "{green_line}"' in cleanup_tail

    def parse_array(name: str) -> list[str]:
        start = content.index(f"{name}=(")
        end = content.index(")", start)
        return [line.strip().strip('"') for line in content[start:end].splitlines() if '"' in line]

    assert parse_array("SMOKE_COMMANDS") == ["--version", "version", "--help"]
    assert parse_array("SUBCOMMANDS") == list(EXPECTED_SUBCOMMANDS)
    # 3 root + 15 subcommand --help + status + plan = 20 probes.
    assert "outside project, expect exit 1" in content
    assert "plan testproj (all 12 modules, expect exit 0)" in content
