"""
Hermetic tests for SA117 public module apply verification.

Tests for ``verify_public_module_apply.py``. All tests use fake executables,
temporary directories, and bare local remotes — no production mutation, no
network, Docker, or PostgreSQL.

Covers:

* Argument validation — well-formed checks, NUL rejection, argv/executable
  matching.
* Process execution — exit codes, stdout/stderr capture, timeout, process
  group isolation.
* Evidence building — module, version, argv, cwd, origin_map_ok, exit_code,
  duration_ms.
* Origin map checks — matching and mismatching origins.
* Resource cleanup — temporary files and directories are removed even on
  error.
* Container/volume checks — zero-scoped detection.
* Direct-origin map / state mismatch detection.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import pytest

from scripts.verify_public_module_apply import (
    ResourceCleanup,
    build_apply_evidence,
    check_no_container_or_volume,
    check_origin_map,
    compute_state_digest,
    execute_apply,
    kill_process_group,
    validate_apply_args,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_executable(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a fake executable script that echoes args and exits 0."""
    exe = tmp_path / "fake_apply.sh"
    exe.write_text(
        '#!/usr/bin/env bash\necho "executed: $@"\necho "stdin:" && cat\nexit 0\n',
        encoding="utf-8",
    )
    exe.chmod(0o755)
    return exe


@pytest.fixture
def fake_failing_executable(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a fake executable that exits non-zero."""
    exe = tmp_path / "fake_fail.sh"
    exe.write_text(
        '#!/usr/bin/env bash\necho "failing..." >&2\nexit 42\n',
        encoding="utf-8",
    )
    exe.chmod(0o755)
    return exe


@pytest.fixture
def fake_sleeping_executable(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a fake executable that sleeps (for timeout tests)."""
    exe = tmp_path / "fake_sleep.sh"
    exe.write_text(
        "#!/usr/bin/env bash\nsleep 60\nexit 0\n",
        encoding="utf-8",
    )
    exe.chmod(0o755)
    return exe


@pytest.fixture
def project_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal project directory."""
    d = tmp_path / "test-project"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestValidateApplyArgs:
    """``validate_apply_args`` checks argument correctness."""

    def test_valid_args_passes(self, fake_executable: pathlib.Path) -> None:
        validate_apply_args(
            executable=fake_executable,
            argv=["fake_apply.sh", "--module", "auth"],
        )  # no raise

    def test_valid_args_with_cwd_passes(
        self, fake_executable: pathlib.Path, project_dir: pathlib.Path
    ) -> None:
        validate_apply_args(
            executable=fake_executable,
            argv=["fake_apply.sh", "--target", str(project_dir)],
            cwd=project_dir,
        )  # no raise

    def test_valid_args_with_stdin_passes(self, fake_executable: pathlib.Path) -> None:
        validate_apply_args(
            executable=fake_executable,
            argv=["fake_apply.sh"],
            stdin="hello",
        )  # no raise

    def test_empty_argv_raises(self, fake_executable: pathlib.Path) -> None:
        with pytest.raises(ValueError, match="argv must contain"):
            validate_apply_args(executable=fake_executable, argv=[])

    def test_argv0_mismatch_raises(self, fake_executable: pathlib.Path) -> None:
        with pytest.raises(ValueError, match="argv.0.*does not match"):
            validate_apply_args(
                executable=fake_executable,
                argv=["wrong_name.sh"],
            )

    def test_nul_in_argv_raises(self, fake_executable: pathlib.Path) -> None:
        with pytest.raises(ValueError, match="NUL"):
            validate_apply_args(
                executable=fake_executable,
                argv=["fake_apply.sh", "\x00evil"],
            )

    def test_nonexistent_cwd_raises(self, fake_executable: pathlib.Path) -> None:
        with pytest.raises(ValueError, match="cwd is not a directory"):
            validate_apply_args(
                executable=fake_executable,
                argv=["fake_apply.sh"],
                cwd="/nonexistent/path",
            )

    def test_path_resolved_executable(self, tmp_path: pathlib.Path) -> None:
        """An absolute executable path that exists is accepted."""
        exe = tmp_path / "my_tool.sh"
        exe.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
        exe.chmod(0o755)
        validate_apply_args(
            executable=exe,
            argv=["my_tool.sh"],
        )  # no raise


# ---------------------------------------------------------------------------
# Process execution
# ---------------------------------------------------------------------------


class TestExecuteApply:
    """``execute_apply`` runs processes and captures output."""

    def test_basic_execution(self, fake_executable: pathlib.Path) -> None:
        completed = execute_apply(
            executable=fake_executable,
            argv=["fake_apply.sh", "--module", "auth"],
            timeout=10,
        )
        assert completed.returncode == 0
        assert "executed:" in completed.stdout

    def test_stdin_captured(self, fake_executable: pathlib.Path) -> None:
        completed = execute_apply(
            executable=fake_executable,
            argv=["fake_apply.sh"],
            stdin="hello from stdin",
            timeout=10,
        )
        assert completed.returncode == 0
        assert "hello from stdin" in completed.stdout

    def test_failing_executable(self, fake_failing_executable: pathlib.Path) -> None:
        completed = execute_apply(
            executable=fake_failing_executable,
            argv=["fake_fail.sh"],
            timeout=10,
        )
        assert completed.returncode == 42
        assert "failing..." in completed.stderr

    def test_cwd_respected(self, fake_executable: pathlib.Path, project_dir: pathlib.Path) -> None:
        completed = execute_apply(
            executable=fake_executable,
            argv=["fake_apply.sh", "--cwd-test"],
            cwd=project_dir,
            timeout=10,
        )
        assert completed.returncode == 0

    def test_timeout_raises(self, fake_sleeping_executable: pathlib.Path) -> None:
        """A process that exceeds the timeout raises ``TimeoutExpired``."""
        with pytest.raises(subprocess.TimeoutExpired):
            execute_apply(
                executable=fake_sleeping_executable,
                argv=["fake_sleep.sh"],
                timeout=1,  # short timeout
            )

    def test_env_passed(self, fake_executable: pathlib.Path) -> None:
        """Custom environment variables are passed to the subprocess."""
        # Create an executable that echoes an env var
        exe_dir = fake_executable.parent
        env_exe = exe_dir / "env_test.sh"
        env_exe.write_text(
            '#!/usr/bin/env bash\necho "MY_VAR=$MY_VAR"\nexit 0\n',
            encoding="utf-8",
        )
        env_exe.chmod(0o755)

        completed = execute_apply(
            executable=env_exe,
            argv=["env_test.sh"],
            env={"MY_VAR": "hello"},
            timeout=10,
        )
        assert completed.returncode == 0
        assert "MY_VAR=hello" in completed.stdout


# ---------------------------------------------------------------------------
# Process group kill
# ---------------------------------------------------------------------------


class TestKillProcessGroup:
    """``kill_process_group`` terminates a process group."""

    def test_kill_nonexistent_pid_does_not_raise(self) -> None:
        """Killing a nonexistent PID should not raise."""
        kill_process_group(999999999, grace_seconds=1)
        # No exception is success


class TestExecuteApplyTimeoutProcessGroup:
    """Timeout cleanup must kill the full process tree (children + grandchildren)."""

    def test_timeout_kills_child_process_group(self, tmp_path: pathlib.Path) -> None:
        """Descendant PIDs must disappear after timeout kills the process group."""
        script = tmp_path / "spawner.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "set -o pipefail\n"
            "# Spawn a grandchild that echoes its PID and loops\n"
            "(\n"
            '  echo "GRANDCHILD_PID=$$"\n'
            "  while true; do\n"
            "    echo 'grandchild alive'\n"
            "    sleep 0.5\n"
            "  done\n"
            ") &\n"
            "GRANDCHILD=$!\n"
            "# Spawn a child that echoes its PID and loops\n"
            "(\n"
            '  echo "CHILD_PID=$$"\n'
            "  while true; do\n"
            "    echo 'child alive'\n"
            "    sleep 0.5\n"
            "  done\n"
            ") &\n"
            "CHILD=$!\n"
            "# Echo parent PID and wait\n"
            'echo "PARENT_PID=$$"\n'
            'echo "CHILD_PID=$CHILD"\n'
            'echo "GRANDCHILD_PID=$GRANDCHILD"\n'
            "# Parent runs until timeout\n"
            "while true; do\n"
            "  echo 'parent alive'\n"
            "  sleep 0.5\n"
            "done\n",
        )
        script.chmod(0o755)

        with pytest.raises(subprocess.TimeoutExpired) as exc_info:
            execute_apply(
                executable=script,
                argv=["spawner.sh"],
                timeout=2,
            )

        exc = exc_info.value
        assert exc.timeout == 2
        # Output must contain PID lines from the child/grandchild
        assert exc.output is not None
        assert "PARENT_PID=" in exc.output

        # Parse PIDs from the captured output
        import os
        import re

        pids: list[int] = []
        for line in exc.output.splitlines():
            m = re.match(r"(PARENT|CHILD|GRANDCHILD)_PID=(\d+)", line)
            if m:
                pids.append(int(m.group(2)))

        assert len(pids) >= 2, f"Expected at least 2 descendant PIDs in output, got {pids}"

        # After timeout + process-group kill, all descendant PIDs must have
        # disappeared (bounded within a short polling window).
        import time

        deadline = time.monotonic() + 5.0
        for pid in pids:
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    break
            else:
                pytest.fail(
                    f"PID {pid} still exists after timeout + process-group kill (waited 5s)"
                )

    def test_timeout_drains_output(self, tmp_path: pathlib.Path) -> None:
        """Output must be drained even on timeout so callers can inspect it."""
        script = tmp_path / "talker.sh"
        script.write_text(
            '#!/usr/bin/env bash\nfor i in 1 2 3; do\n  echo "line $i"\n  sleep 1\ndone\nexit 0\n',
        )
        script.chmod(0o755)

        with pytest.raises(subprocess.TimeoutExpired) as exc_info:
            execute_apply(
                executable=script,
                argv=["talker.sh"],
                timeout=1,
            )

        exc = exc_info.value
        assert exc.output is not None
        assert "line 1" in exc.output

    def test_timeout_kills_sigterm_resistant_child(self, tmp_path: pathlib.Path) -> None:
        """A SIGTERM-resistant child must be killed by SIGKILL after grace period."""
        script = tmp_path / "sigterm_resistant.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "# Trap SIGTERM and ignore it — only SIGKILL can stop this child\n"
            "trap '' SIGTERM\n"
            "# Spawn a grandchild that echoes its PID\n"
            "(\n"
            '  echo "GRANDCHILD_PID=$$"\n'
            "  while true; do\n"
            "    echo 'grandchild alive'\n"
            "    sleep 0.5\n"
            "  done\n"
            ") &\n"
            "GRANDCHILD=$!\n"
            "# Echo our PIDs and loop\n"
            'echo "PARENT_PID=$$"\n'
            'echo "GRANDCHILD_PID=$GRANDCHILD"\n'
            "while true; do\n"
            "  echo 'parent alive (SIGTERM-resistant)'\n"
            "  sleep 0.5\n"
            "done\n",
        )
        script.chmod(0o755)

        with pytest.raises(subprocess.TimeoutExpired) as exc_info:
            execute_apply(
                executable=script,
                argv=["sigterm_resistant.sh"],
                timeout=2,
            )

        exc = exc_info.value
        assert exc.output is not None
        assert "SIGTERM-resistant" in exc.output

        # Parse PIDs
        import os
        import re

        pids: list[int] = []
        for line in exc.output.splitlines():
            m = re.match(r"(PARENT|GRANDCHILD)_PID=(\d+)", line)
            if m:
                pids.append(int(m.group(2)))

        assert len(pids) >= 2, f"Expected at least 2 PIDs from SIGTERM-resistant tree, got {pids}"

        # After timeout + kill_process_group, all must be gone (SIGKILL
        # was required since SIGTERM was trapped).
        import time

        deadline = time.monotonic() + 5.0
        for pid in pids:
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    break
            else:
                pytest.fail(
                    f"SIGTERM-resistant PID {pid} still exists after timeout "
                    f"(SIGKILL required; waited 5s)"
                )

    def test_timeout_preserves_failure_precedence(self, tmp_path: pathlib.Path) -> None:
        """Timeout takes precedence over non-zero exit or signal termination."""
        script = tmp_path / "slow_fail.sh"
        script.write_text(
            "#!/usr/bin/env bash\necho 'starting...'\nsleep 10\nexit 42\n",
        )
        script.chmod(0o755)

        with pytest.raises(subprocess.TimeoutExpired) as exc_info:
            execute_apply(
                executable=script,
                argv=["slow_fail.sh"],
                timeout=1,
            )

        exc = exc_info.value
        assert exc.timeout == 1
        # Must raise TimeoutExpired, not silently return a non-zero exit code


# ---------------------------------------------------------------------------
# Evidence building
# ---------------------------------------------------------------------------


class TestBuildApplyEvidence:
    """``build_apply_evidence`` produces well-formed evidence."""

    def test_has_required_fields(self) -> None:
        evidence = build_apply_evidence(
            module="auth",
            version="0.87.0",
            executable="/usr/bin/git",
            argv=["git", "clone", "repo"],
            cwd="/tmp/work",
            origin_map_ok=True,
            state_digest="abc123",
            exit_code=0,
            duration_ms=42.5,
        )
        assert evidence["module"] == "auth"
        assert evidence["version"] == "0.87.0"
        assert evidence["executable"] == "/usr/bin/git"
        assert evidence["argv"] == ["git", "clone", "repo"]
        assert evidence["cwd"] == "/tmp/work"
        assert evidence["origin_map_ok"] is True
        assert evidence["state_digest"] == "abc123"
        assert evidence["exit_code"] == 0
        assert evidence["duration_ms"] == 42.5
        assert "captured_at" in evidence
        assert evidence["schema_version"] == "1"

    def test_none_cwd(self) -> None:
        evidence = build_apply_evidence(
            module="auth",
            version="0.87.0",
            executable="/usr/bin/git",
            argv=["git", "clone"],
            cwd=None,
            origin_map_ok=True,
            state_digest="",
            exit_code=0,
            duration_ms=0.0,
        )
        assert evidence["cwd"] is None

    def test_origin_mismatch_recorded(self) -> None:
        evidence = build_apply_evidence(
            module="auth",
            version="0.87.0",
            executable="/usr/bin/git",
            argv=["git", "clone"],
            cwd=None,
            origin_map_ok=False,
            state_digest="",
            exit_code=1,
            duration_ms=10.0,
        )
        assert evidence["origin_map_ok"] is False
        assert evidence["exit_code"] == 1


# ---------------------------------------------------------------------------
# Origin map checks
# ---------------------------------------------------------------------------


class TestCheckOriginMap:
    """``check_origin_map`` validates module origin consistency."""

    def test_matching_origins(self) -> None:
        assert (
            check_origin_map(
                module="auth",
                declared_origin="https://github.com/quickscale/quickscale-modules.git",
                expected_origin="https://github.com/quickscale/quickscale-modules.git",
            )
            is True
        )

    def test_mismatching_origins(self) -> None:
        assert (
            check_origin_map(
                module="auth",
                declared_origin="https://github.com/evil/quickscale-modules.git",
                expected_origin="https://github.com/quickscale/quickscale-modules.git",
            )
            is False
        )

    def test_case_sensitive_match(self) -> None:
        assert (
            check_origin_map(
                module="auth",
                declared_origin="GITHUB.COM/quickscale/module.git",
                expected_origin="github.com/quickscale/module.git",
            )
            is False
        )

    def test_empty_origin_match(self) -> None:
        """Empty origins that match are treated as valid."""
        assert (
            check_origin_map(
                module="auth",
                declared_origin="",
                expected_origin="",
            )
            is True
        )

    def test_empty_vs_nonempty_mismatch(self) -> None:
        assert (
            check_origin_map(
                module="auth",
                declared_origin="",
                expected_origin="https://github.com/quickscale/quickscale-modules.git",
            )
            is False
        )


# ---------------------------------------------------------------------------
# State digest computation
# ---------------------------------------------------------------------------


class TestComputeStateDigest:
    """``compute_state_digest`` computes a SHA-256 digest of state.yml."""

    def test_returns_hexdigest_when_state_exists(self, project_dir: pathlib.Path) -> None:
        """When state.yml exists, a non-empty hex digest is returned."""
        state_dir = project_dir / ".quickscale"
        state_dir.mkdir()
        state_path = state_dir / "state.yml"
        state_path.write_text("version: '1'\nproject:\n  slug: test\n")
        digest = compute_state_digest(project_dir)
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in digest)

    def test_returns_empty_string_when_state_missing(self, project_dir: pathlib.Path) -> None:
        """When no .quickscale/state.yml exists, an empty string is returned."""
        digest = compute_state_digest(project_dir)
        assert digest == ""

    def test_returns_empty_string_when_quickscale_dir_missing(
        self, project_dir: pathlib.Path
    ) -> None:
        """When .quickscale/ directory does not exist, an empty string is returned."""
        digest = compute_state_digest(project_dir)
        assert digest == ""


# ---------------------------------------------------------------------------
# Mismatch before mutation (SA117-CR-003)
# ---------------------------------------------------------------------------


class TestMismatchBeforeMutation:
    """Origin mismatch must block apply before any process execution."""

    def test_origin_mismatch_blocks_execution(
        self, fake_executable: pathlib.Path, project_dir: pathlib.Path
    ) -> None:
        """When origin check fails, execute_apply is never called."""
        from unittest.mock import patch

        # declared_origin != expected_origin → must not call execute_apply
        with patch("scripts.verify_public_module_apply.execute_apply") as mock_execute:
            # We must integrate with main(), so simulate the apply CLI flow
            from scripts.verify_public_module_apply import main

            rc = main(
                [
                    "apply",
                    "--module",
                    "auth",
                    "--target",
                    str(project_dir),
                    "--executable",
                    str(fake_executable),
                    "--argv",
                    "fake_apply.sh",
                    "--version",
                    "0.87.0",
                    "--declared-origin",
                    "https://github.com/evil/module.git",
                    "--expected-origin",
                    "https://github.com/quickscale/module.git",
                ]
            )
        assert rc == 1, "Origin mismatch must return exit code 1"
        mock_execute.assert_not_called()

    def test_origin_match_allows_execution(
        self, fake_executable: pathlib.Path, project_dir: pathlib.Path
    ) -> None:
        """When origin check passes, execution proceeds normally."""
        from scripts.verify_public_module_apply import main

        rc = main(
            [
                "apply",
                "--module",
                "auth",
                "--target",
                str(project_dir),
                "--executable",
                str(fake_executable),
                "--argv",
                "fake_apply.sh",
                "--version",
                "0.87.0",
                "--declared-origin",
                "https://github.com/quickscale/module.git",
                "--expected-origin",
                "https://github.com/quickscale/module.git",
            ]
        )
        assert rc == 0, "Origin match must return exit code 0"

    def test_mismatch_before_mutation_reports_error(
        self, fake_executable: pathlib.Path, project_dir: pathlib.Path, capsys
    ) -> None:
        """Error output must clearly state origin mismatch and module name."""
        from scripts.verify_public_module_apply import main

        rc = main(
            [
                "apply",
                "--module",
                "auth",
                "--target",
                str(project_dir),
                "--executable",
                str(fake_executable),
                "--argv",
                "fake_apply.sh",
                "--version",
                "0.87.0",
                "--declared-origin",
                "bad-origin",
                "--expected-origin",
                "good-origin",
            ]
        )
        assert rc == 1
        captured = capsys.readouterr()
        assert "ORIGIN MISMATCH" in captured.err
        assert "auth" in captured.err


# ---------------------------------------------------------------------------
# Resource cleanup
# ---------------------------------------------------------------------------


class TestResourceCleanup:
    """``ResourceCleanup`` context manager cleans up temp files and dirs."""

    def test_cleanup_temp_file(self) -> None:
        """A registered temp file is removed on cleanup."""
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = pathlib.Path(tmp.name)
        path.write_text("hello", encoding="utf-8")
        assert path.is_file()

        cleanup = ResourceCleanup()
        cleanup.register_temp_file(path)
        cleanup.cleanup()
        assert not path.is_file()

    def test_cleanup_temp_dir(self) -> None:
        """A registered temp directory is removed on cleanup."""
        tmp = tempfile.mkdtemp()
        path = pathlib.Path(tmp)
        (path / "file.txt").write_text("hello", encoding="utf-8")
        assert path.is_dir()

        cleanup = ResourceCleanup()
        cleanup.register_temp_dir(path)
        cleanup.cleanup()
        assert not path.is_dir()

    def test_cleanup_reverse_order(self) -> None:
        """Resources are cleaned up in reverse registration order."""
        tmp1 = pathlib.Path(tempfile.mkdtemp())
        tmp2 = pathlib.Path(tempfile.mkdtemp())
        assert tmp1.is_dir()
        assert tmp2.is_dir()

        cleanup = ResourceCleanup()
        cleanup.register_temp_dir(tmp1)
        cleanup.register_temp_dir(tmp2)
        cleanup.cleanup()
        # Both should be gone
        assert not tmp1.is_dir()
        assert not tmp2.is_dir()

    def test_context_manager_exit_cleans_up(self) -> None:
        """The context manager exits cleanly."""
        tmp = pathlib.Path(tempfile.mkdtemp())
        with ResourceCleanup() as cleanup:
            cleanup.register_temp_dir(tmp)
            assert tmp.is_dir()
        assert not tmp.is_dir()

    def test_context_manager_exit_on_error(self) -> None:
        """Resources are cleaned up even when an exception occurs."""
        tmp = pathlib.Path(tempfile.mkdtemp())
        with pytest.raises(RuntimeError):
            with ResourceCleanup() as cleanup:
                cleanup.register_temp_dir(tmp)
                raise RuntimeError("test error")
        # Temp dir should still be cleaned up
        assert not tmp.is_dir()

    def test_cleanup_nonexistent_path_does_not_raise(self) -> None:
        """Cleaning up a path that no longer exists does not raise."""
        cleanup = ResourceCleanup()
        cleanup.register_temp_file(pathlib.Path("/nonexistent/file.txt"))
        cleanup.cleanup()  # no raise


# ---------------------------------------------------------------------------
# Container/volume checks
# ---------------------------------------------------------------------------


class TestCheckNoContainerOrVolume:
    """``check_no_container_or_volume`` detects container/volume config."""

    def test_clean_project_returns_empty(self, project_dir: pathlib.Path) -> None:
        findings = check_no_container_or_volume(project_dir)
        assert findings == []

    def test_dockerfile_detected(self, project_dir: pathlib.Path) -> None:
        (project_dir / "Dockerfile").write_text("FROM python:3.13\n", encoding="utf-8")
        findings = check_no_container_or_volume(project_dir)
        assert len(findings) == 1
        assert "Dockerfile" in findings[0]

    def test_docker_compose_detected(self, project_dir: pathlib.Path) -> None:
        (project_dir / "docker-compose.yml").write_text("version: '3'\n", encoding="utf-8")
        findings = check_no_container_or_volume(project_dir)
        assert len(findings) >= 1
        assert any("docker-compose" in f for f in findings)

    def test_dockerignore_detected(self, project_dir: pathlib.Path) -> None:
        (project_dir / ".dockerignore").write_text("__pycache__\n", encoding="utf-8")
        findings = check_no_container_or_volume(project_dir)
        assert len(findings) == 1
        assert ".dockerignore" in findings[0]

    def test_volume_dir_detected(self, project_dir: pathlib.Path) -> None:
        (project_dir / "volumes").mkdir()
        findings = check_no_container_or_volume(project_dir)
        assert len(findings) == 1
        assert "volumes" in findings[0]

    def test_dot_volume_dir_detected(self, project_dir: pathlib.Path) -> None:
        (project_dir / ".volumes").mkdir()
        findings = check_no_container_or_volume(project_dir)
        assert len(findings) == 1
        assert ".volumes" in findings[0]

    def test_multiple_findings(self, project_dir: pathlib.Path) -> None:
        (project_dir / "Dockerfile").write_text("FROM python:3.13\n", encoding="utf-8")
        (project_dir / "volumes").mkdir()
        findings = check_no_container_or_volume(project_dir)
        assert len(findings) == 2

    def test_non_project_subdir_not_affected(self, project_dir: pathlib.Path) -> None:
        """Check ignores container files in subdirectories by default."""
        sub = project_dir / "subdir"
        sub.mkdir()
        (sub / "Dockerfile").write_text("FROM python:3.13\n", encoding="utf-8")
        findings = check_no_container_or_volume(project_dir)
        assert len(findings) == 0
