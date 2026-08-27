"""Hermetic PATH-shim tests for the PostgreSQL provisioning contract."""

from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/provision_ci_postgres.sh"


def _invoke_environment(env: dict[str, str] | None = None) -> dict[str, str]:
    variables = os.environ.copy()
    # The suite is also run inside the restricted local-CI lease. Each case
    # must start with an intentionally independent lifecycle environment so a
    # parent lease cannot alter its missing-client, hosted, or fake-Docker
    # boundary assertions.
    for key in (
        "QUICKSCALE_POSTGRES_LEASE",
        "QUICKSCALE_POSTGRES_LEASE_TOKEN",
        "QUICKSCALE_POSTGRES_LEASE_VALIDATED",
        "QUICKSCALE_POSTGRES_PROFILE",
        "PGHOST",
        "PGPORT",
        "PGUSER",
        "QS_PROVISION_SCOPE",
    ):
        variables.pop(key, None)
    for key in tuple(variables):
        if (key.startswith("QS_") and "_DB_" in key) or key == "QUICKSCALE_ALLOW_BYPASSRLS":
            variables.pop(key, None)
    variables.update({"PYTHON": sys.executable, "PYTHONPATH": str(ROOT / "quickscale_core/src")})
    if env:
        variables.update(env)
    return variables


def invoke(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(HELPER), *args],
        cwd=ROOT,
        env=_invoke_environment(env),
        text=True,
        capture_output=True,
        check=False,
    )


def spawn(*args: str, env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["/bin/bash", str(HELPER), *args],
        cwd=ROOT,
        env=_invoke_environment(env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def executable(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\nset -eu\n{body}\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def fake_local_lifecycle_tools(tmp_path: Path) -> tuple[Path, Path]:
    tools = tmp_path / "tools"
    tools.mkdir()
    docker_log = tmp_path / "docker.log"
    image_id = "a" * 64
    executable(
        tools / "docker",
        f'''printf "%s\\n" "$*" >> "{docker_log}"
case " $* " in
  *" image inspect "*) echo "sha256:{image_id}" ;;
  *" create "*) echo "container-id" ;;
  *" port "*) echo "127.0.0.1:55432" ;;
  *"Config.Labels"*) echo "quickscale|integration|${{QS_PROVISION_SCOPE}}" ;;
  *" inspect --type container "*) echo "sha256:{image_id}" ;;
esac''',
    )
    for tool in ("pg_dump", "pg_restore"):
        executable(tools / tool, f'echo "{tool} (PostgreSQL) 18.1"')
    executable(
        tools / "psql",
        """if [[ " $* " == *" --version "* ]]; then
  echo "psql (PostgreSQL) 18.1"
elif [[ " $* " == *" -At "* && " $* " == *" role_name=quickscale_test_role "* ]]; then
  echo "t|t|f|f|f|f"
elif [[ " $* " == *" -At "* && " $* " == *" role_name=quickscale_bypassrls_test_role "* ]]; then
  echo "t|t|f|t|f|f"
elif [[ " $* " == *" -At "* && " $* " == *" inner_role="* ]]; then
  echo "f|f|f|f|f|f"
elif [[ " $* " == *" current_setting("* ]]; then
  echo "180000"
fi""",
    )
    return tools, docker_log


@pytest.mark.parametrize(
    ("command", "expected_status"),
    [(["/bin/true"], 0), (["/bin/bash", "-c", "exit 37"], 37)],
    ids=["success", "failure"],
)
def test_immediate_children_preserve_status_and_cleanup(
    tmp_path: Path, command: list[str], expected_status: int
) -> None:
    tools, docker_log = fake_local_lifecycle_tools(tmp_path)
    ps_count = tmp_path / "ps-count"
    executable(
        tools / "ps",
        f'''count=0
if [[ -f "{ps_count}" ]]; then count=$(<"{ps_count}"); fi
count=$((count + 1))
printf "%s" "$count" > "{ps_count}"
if [[ "$count" -eq 1 ]]; then
  echo "424242"
  exit 0
fi
sleep 0.1
exit 1''',
    )

    result = invoke(
        "run",
        "--profile",
        "restricted",
        "--",
        *command,
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": f"immediate_{expected_status}",
        },
    )

    assert result.returncode == expected_status, result.stderr
    assert "cannot verify the process group of a live child" not in result.stderr
    assert any("rm -f container-id" in call for call in docker_log.read_text().splitlines())
    assert not any(path.name.startswith("quickscale-postgres.") for path in tmp_path.iterdir())


def test_live_child_probe_failure_still_fails_distinct_group_verification(
    tmp_path: Path,
) -> None:
    tools, docker_log = fake_local_lifecycle_tools(tmp_path)
    ps_count = tmp_path / "ps-count"
    executable(
        tools / "ps",
        f'''count=0
if [[ -f "{ps_count}" ]]; then count=$(<"{ps_count}"); fi
count=$((count + 1))
printf "%s" "$count" > "{ps_count}"
if [[ "$count" -eq 1 ]]; then
  echo "424242"
  exit 0
fi
exit 1''',
    )

    started = time.monotonic()
    result = invoke(
        "run",
        "--profile",
        "restricted",
        "--",
        "/bin/sleep",
        "10",
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": "live_probe",
        },
    )

    assert result.returncode != 0
    assert time.monotonic() - started < 5
    assert "cannot verify the process group of a live child" in result.stderr
    assert any("rm -f container-id" in call for call in docker_log.read_text().splitlines())


def test_lifecycle_record_rejects_an_existing_directory_before_allocation(
    tmp_path: Path,
) -> None:
    tools, docker_log = fake_local_lifecycle_tools(tmp_path)
    record = tmp_path / "lifecycle-record"
    record.mkdir()

    result = invoke(
        "run",
        "--profile",
        "restricted",
        "--",
        "/bin/true",
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": "invalid_record",
            "QS_PROVISION_LIFECYCLE_RECORD": str(record),
        },
    )

    assert result.returncode != 0
    assert "must be a regular file path" in result.stderr
    assert not docker_log.exists()


@pytest.mark.parametrize(
    ("signal_number", "signal_name", "expected_status"),
    [
        (signal.SIGHUP, "HUP", 129),
        (signal.SIGINT, "INT", 130),
        (signal.SIGTERM, "TERM", 143),
    ],
)
def test_signal_cleanup_waits_for_verified_child_group_and_records_lifecycle(
    tmp_path: Path,
    signal_number: signal.Signals,
    signal_name: str,
    expected_status: int,
) -> None:
    tools, _ = fake_local_lifecycle_tools(tmp_path)
    record = tmp_path / "lifecycle.json"
    descendant_pid_file = tmp_path / "descendant.pid"
    process = spawn(
        "run",
        "--profile",
        "restricted",
        "--",
        "/bin/bash",
        "-c",
        (
            'trap \'kill "$descendant" 2>/dev/null; '
            f'wait "$descendant" 2>/dev/null; exit {expected_status}\' {signal_name}; '
            f"sleep 30 & descendant=$!; printf '%s\\n' \"$descendant\" > {descendant_pid_file!s}; "
            'wait "$descendant"'
        ),
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": f"signal_barrier_{signal_name.lower()}",
            "QS_PROVISION_LIFECYCLE_RECORD": str(record),
        },
    )
    try:
        deadline = time.monotonic() + 10
        readiness: dict[str, object] | None = None
        while time.monotonic() < deadline:
            if record.exists():
                readiness = json.loads(record.read_text())
                if readiness["readiness"]["event"] == "child_group_verified":
                    break
            time.sleep(0.05)
        assert readiness is not None
        assert readiness["readiness"]["verified"] is True
        assert readiness["readiness"]["child_pid"] == readiness["readiness"]["child_pgid"]
        process.send_signal(signal_number)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == expected_status, stderr
    assert stdout == ""
    final_record = json.loads(record.read_text())
    assert final_record["profile"] == "restricted"
    assert final_record["scope"] == f"signal_barrier_{signal_name.lower()}"
    assert final_record["image_id"] == "sha256:" + "a" * 64
    assert final_record["endpoint"] == {"host": "localhost", "port": "55432"}
    assert final_record["readiness"]["event"] == "child_group_verified"
    assert final_record["child_status"] == expected_status
    descendant_pid = int(descendant_pid_file.read_text())
    assert subprocess.run(["kill", "-0", str(descendant_pid)], check=False).returncode != 0
    process_group = int(final_record["readiness"]["child_pgid"])
    process_table = subprocess.run(
        ["ps", "-eo", "pid=,pgid=,stat="], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert not any(
        fields[1] == str(process_group) and not fields[2].startswith("Z")
        for line in process_table
        if (fields := line.split()) and len(fields) >= 3
    )
    assert final_record["cleanup"] == {
        "container": True,
        "scope": True,
        "lease": True,
        "complete": True,
    }
    assert "LIFECYCLE_RECORD=" in stderr


@pytest.mark.parametrize(
    ("profile", "variable", "expected_value", "consumer"),
    [
        (
            "restricted",
            "QS_ANALYTICS_DB_NAME",
            "test_qs_restricted_reused_analytics",
            ROOT / "scripts/test_integration.sh",
        ),
        (
            "isolation",
            "QS_ORGS_DB_NAME",
            "test_qs_isolation_reused_orgs",
            ROOT / "scripts/test_isolation_conformance.sh",
        ),
    ],
    ids=["restricted", "isolation"],
)
def test_reused_local_lease_corrects_profile_environment_and_consumers_reject_repoisoning(
    tmp_path: Path,
    profile: str,
    variable: str,
    expected_value: str,
    consumer: Path,
) -> None:
    tools, _ = fake_local_lifecycle_tools(tmp_path)
    variable_prefix = variable.removesuffix("_NAME")
    corrected = invoke(
        "run",
        "--profile",
        profile,
        "--",
        "/usr/bin/env",
        f"{variable}=poisoned_database",
        f"{variable_prefix}_USER=poisoned_user",
        f"{variable_prefix}_HOST=poisoned.example.invalid",
        f"{variable_prefix}_PORT=1",
        "QUICKSCALE_ALLOW_BYPASSRLS=1",
        "/bin/bash",
        str(HELPER),
        "run",
        "--profile",
        profile,
        "--",
        "/bin/bash",
        "-c",
        (
            f'printf "%s|%s|%s|%s|%s" "${{{variable}}}" '
            f'"${{{variable_prefix}_USER}}" "${{{variable_prefix}_HOST}}" '
            f'"${{{variable_prefix}_PORT}}" "$QUICKSCALE_ALLOW_BYPASSRLS"'
        ),
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": "reused",
        },
    )
    assert corrected.returncode == 0, corrected.stderr
    assert corrected.stdout.endswith(f"{expected_value}|quickscale_test_role|localhost|55432|0")
    assert "poisoned" not in corrected.stdout

    rejected = invoke(
        "run",
        "--profile",
        profile,
        "--",
        "/usr/bin/env",
        f"{variable}=repoisoned_database",
        "QUICKSCALE_ALLOW_BYPASSRLS=1",
        "/bin/bash",
        str(consumer),
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": "rejected",
        },
    )
    assert rejected.returncode != 0
    assert f"{variable} does not match the validated PostgreSQL profile" in rejected.stderr

    bypass_rejected = invoke(
        "run",
        "--profile",
        profile,
        "--",
        "/usr/bin/env",
        "QUICKSCALE_ALLOW_BYPASSRLS=1",
        "/bin/bash",
        str(consumer),
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": "bypass_rejected",
        },
    )
    assert bypass_rejected.returncode != 0
    assert (
        "QUICKSCALE_ALLOW_BYPASSRLS does not match the validated PostgreSQL profile"
        in bypass_rejected.stderr
    )


def test_describe_is_pure_and_binds_discovery_once(tmp_path: Path) -> None:
    result = invoke(
        "describe",
        "--profile",
        "restricted",
        "--format",
        "json",
        env={"TMPDIR": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    description = json.loads(result.stdout)
    modules = description["discovery"]["modules"]
    assert len(modules) == 12 and modules == sorted(modules)
    assert description["discovery"]["command"][-1] == "--list-modules"
    assert [item["key"] for item in description["databases"]] == ["smoke", *modules]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "profile", ["backups", "restricted", "isolation", "bypassrls", "client-only"]
)
def test_all_profiles_have_exact_database_and_environment_contract(profile: str) -> None:
    result = invoke(
        "describe",
        "--profile",
        profile,
        "--format",
        "json",
        env={"QS_PROVISION_HOSTED": "1"},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    if profile == "backups":
        assert [entry["key"] for entry in data["databases"]] == ["backups"]
        assert set(data["environment"]) == {
            "QS_BACKUPS_DB_" + suffix for suffix in ("NAME", "USER", "HOST", "PORT")
        }
    elif profile == "client-only":
        assert data["databases"] == [] and data["environment"] == {}
    else:
        modules = data["discovery"]["modules"]
        expected = ["smoke", *modules]
        if profile == "isolation":
            expected = [key for key in expected if key != "backups"]
        assert [entry["key"] for entry in data["databases"]] == expected
        if profile == "isolation":
            mapped = sorted(
                {
                    key.removeprefix("QS_").split("_DB_", 1)[0].lower()
                    for key in data["environment"]
                    if key.startswith("QS_")
                }
            )
            assert len(mapped) == 6
            assert "backups" not in mapped
        else:
            mapped = [entry["module"] for entry in data["databases"] if entry["module"]]
        assert set(data["environment"]) == {
            f"QS_{module.upper()}_DB_{suffix}"
            for module in mapped
            for suffix in ("NAME", "USER", "HOST", "PORT")
        } | {"QUICKSCALE_ALLOW_BYPASSRLS"}
    if profile == "bypassrls":
        assert data["role"]["name"] == "quickscale_bypassrls_test_role"
        assert data["environment"]["QUICKSCALE_ALLOW_BYPASSRLS"] == "1"
    elif profile in {"restricted", "isolation"}:
        assert data["role"]["name"] == "quickscale_test_role"
        assert data["environment"]["QUICKSCALE_ALLOW_BYPASSRLS"] == "0"


def test_profile_descriptions_are_complete_source_bindings() -> None:
    """Every hosted profile exposes all facts consumed by workflow callers."""
    for profile in ("backups", "restricted", "isolation", "bypassrls", "client-only"):
        result = invoke(
            "describe",
            "--profile",
            profile,
            "--format",
            "json",
            env={"QS_PROVISION_HOSTED": "1"},
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["profile"] == profile
        assert data["discovery"]["modules"] == sorted(data["discovery"]["modules"])
        assert len(data["discovery"]["modules"]) == 12
        if profile == "client-only":
            assert data["databases"] == []
            assert data["environment"] == {}
        else:
            assert data["databases"]
            assert data["role"]["flags"]


def test_local_profile_names_are_qualified_and_disjoint() -> None:
    restricted = invoke(
        "describe",
        "--profile",
        "restricted",
        "--format",
        "json",
        env={"QS_PROVISION_SCOPE": "alpha"},
    )
    bypass = invoke(
        "describe",
        "--profile",
        "bypassrls",
        "--format",
        "json",
        env={"QS_PROVISION_SCOPE": "beta"},
    )
    assert restricted.returncode == bypass.returncode == 0
    left = {entry["name"] for entry in json.loads(restricted.stdout)["databases"]}
    right = {entry["name"] for entry in json.loads(bypass.stdout)["databases"]}
    assert all("restricted_alpha" in name for name in left)
    assert all("bypassrls_beta" in name for name in right)
    assert left.isdisjoint(right)


def test_discovery_failure_empty_unsafe_duplicate_and_drift_fail_closed(tmp_path: Path) -> None:
    cases = {
        "failure": "exit 7",
        "empty": "exit 0",
        "unsafe": "printf 'analytics\\nnot-safe!\\n'",
        "duplicate": "printf 'analytics\\nanalytics\\n'",
        "drift": "printf 'auth\\nanalytics\\n'",
    }
    for name, body in cases.items():
        shim = tmp_path / name
        executable(shim, body)
        result = invoke(
            "describe",
            "--profile",
            "restricted",
            "--format",
            "json",
            env={"PYTHON": str(shim)},
        )
        assert result.returncode != 0, name


@pytest.mark.parametrize(
    "variables",
    [{"PGHOST": "bad host"}, {"PGHOST": "bad\nhost"}, {"PGPORT": "0"}, {"PGPORT": "5432;"}],
)
def test_host_and_port_are_validated_before_mutation(variables: dict[str, str]) -> None:
    result = invoke("describe", "--profile", "restricted", "--format", "json", env=variables)
    assert result.returncode != 0


def test_local_never_installs_clients_and_requires_docker(tmp_path: Path) -> None:
    """The Docker prerequisite is checked after clients, without host fallbacks."""
    only_bash = tmp_path / "only-bash"
    only_bash.mkdir()
    (only_bash / "dirname").symlink_to("/usr/bin/dirname")
    result = invoke(
        "run",
        "--profile",
        "restricted",
        "--",
        "true",
        env={"PATH": str(only_bash), "TMPDIR": str(tmp_path)},
    )
    assert result.returncode != 0 and "required PostgreSQL client" in result.stderr
    tools = tmp_path / "tools"
    tools.mkdir()
    # Keep this branch hermetic: the host has both Docker and apt-get, so a
    # PATH containing /usr/bin would turn a negative prerequisite test into a
    # real allocation or an installation attempt.  The client scripts use an
    # env-based shebang, while the helper needs dirname before it reaches its
    # Docker guard; expose only those utilities and the PostgreSQL shims.
    (tools / "bash").symlink_to("/bin/bash")
    (tools / "dirname").symlink_to("/usr/bin/dirname")
    for tool in ("psql", "pg_dump", "pg_restore"):
        executable(tools / tool, f'echo "{tool} (PostgreSQL) 18.1"')
    docker_log = tmp_path / "docker.log"
    apt_log = tmp_path / "apt-get.log"
    result = invoke(
        "run",
        "--profile",
        "restricted",
        "--",
        "true",
        env={
            "PATH": str(tools),
            "TMPDIR": str(tmp_path),
            "QS_DOCKER_LOG": str(docker_log),
            "QS_APT_LOG": str(apt_log),
        },
    )
    assert result.returncode != 0
    assert result.stderr == "ERROR: Docker is required for local PostgreSQL\n"
    assert not docker_log.exists()
    assert not apt_log.exists()
    assert not any(path.name.startswith("quickscale-postgres.") for path in tmp_path.iterdir())


def test_hosted_setup_is_github_only_and_client_only_writes_lease(tmp_path: Path) -> None:
    outside = invoke("hosted-setup", "--profile", "client-only", env={"RUNNER_TEMP": str(tmp_path)})
    assert outside.returncode != 0 and "GitHub-only" in outside.stderr
    tools = tmp_path / "tools"
    tools.mkdir()
    for tool in ("psql", "pg_dump", "pg_restore"):
        executable(tools / tool, f'echo "{tool} (PostgreSQL) 18.2"')
    github_env = tmp_path / "GITHUB_ENV"
    result = invoke(
        "hosted-setup",
        "--profile",
        "client-only",
        env={
            "GITHUB_ACTIONS": "true",
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_ENV": str(github_env),
            "PATH": f"{tools}:/usr/bin",
        },
    )
    assert result.returncode == 0, result.stderr
    lines = github_env.read_text().splitlines()
    assert any(line.startswith("QUICKSCALE_POSTGRES_LEASE=") for line in lines)
    assert any(line.startswith("QUICKSCALE_POSTGRES_LEASE_TOKEN=") for line in lines)
    lease_dirs = [
        path for path in tmp_path.iterdir() if path.name.startswith("quickscale-postgres.")
    ]
    assert len(lease_dirs) == 1
    assert lease_dirs[0].stat().st_mode & 0o777 == 0o700
    assert (lease_dirs[0] / "lease").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("kind", ["forged", "stale", "mismatched"])
def test_forged_stale_and_profile_mismatched_leases_fail_closed(tmp_path: Path, kind: str) -> None:
    directory = tmp_path / "lease-dir"
    directory.mkdir(mode=0o700)
    token = "a" * 64
    lease = directory / "lease"
    lease.write_text(
        "mode=local\nprofile=restricted\nendpoint_host=localhost\nendpoint_port=5432\n"
        "scope=scope\ncontainer_id=cid\nhelper_pid=99999999\ndescription_digest="
        + "d" * 64
        + "\n"
        + f"token={token}\n"
    )
    lease.chmod(0o600)
    supplied = {"QUICKSCALE_POSTGRES_LEASE": str(lease), "QUICKSCALE_POSTGRES_LEASE_TOKEN": token}
    if kind == "forged":
        supplied["QUICKSCALE_POSTGRES_LEASE_TOKEN"] = "b" * 64
    elif kind == "mismatched":
        lease.write_text(lease.read_text().replace("profile=restricted", "profile=bypassrls"))
    result = invoke("run", "--profile", "restricted", "--", "true", env=supplied)
    assert result.returncode != 0
    assert any(word in result.stderr for word in ("forged", "stale", "mismatched"))


def test_equal_validation_markers_cannot_bypass_live_lease_validation(tmp_path: Path) -> None:
    token = "a" * 64
    environment = os.environ.copy()
    environment.pop("GITHUB_ACTIONS", None)
    environment.update(
        {
            "QUICKSCALE_POSTGRES_LEASE": str(tmp_path / "missing-lease"),
            "QUICKSCALE_POSTGRES_LEASE_TOKEN": token,
            "QUICKSCALE_POSTGRES_LEASE_VALIDATED": token,
            "QUICKSCALE_POSTGRES_PROFILE": "restricted",
        }
    )
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "scripts/test_integration.sh")],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "malformed or stale PostgreSQL lease" in result.stderr


def test_lease_description_digest_is_bound_to_current_profile(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    executable(tools / "docker", "echo 'quickscale|integration|scope'")
    directory = tmp_path / "lease-dir"
    directory.mkdir(mode=0o700)
    token = "a" * 64
    lease = directory / "lease"
    lease.write_text(
        "mode=local\nprofile=restricted\nendpoint_host=localhost\nendpoint_port=5432\n"
        f"scope=scope\ncontainer_id=cid\nhelper_pid={os.getpid()}\n"
        f"description_digest={'d' * 64}\ntoken={token}\n"
    )
    lease.chmod(0o600)
    result = invoke(
        "validate",
        "--profile",
        "restricted",
        env={
            "QUICKSCALE_POSTGRES_LEASE": str(lease),
            "QUICKSCALE_POSTGRES_LEASE_TOKEN": token,
            "QS_PROVISION_SCOPE": "scope",
            "PATH": f"{tools}:/usr/bin",
        },
    )
    assert result.returncode != 0
    assert "description digest does not match" in result.stderr


def test_label_visible_before_id_return_is_cleaned_by_exact_scope(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    log = tmp_path / "docker.log"
    for tool in ("psql", "pg_dump", "pg_restore"):
        executable(tools / tool, f'echo "{tool} (PostgreSQL) 18.1"')
    image_id = "a" * 64
    executable(
        tools / "docker",
        f'''printf "%s\\n" "$*" >> "{log}"
case " $* " in
  *"image inspect"*) echo "sha256:{image_id}" ;;
  *" create "*) ;;
  *"ps -aq"*) ;;
esac''',
    )
    result = invoke(
        "run",
        "--profile",
        "restricted",
        "--",
        "true",
        env={
            "PATH": f"{tools}:/usr/bin",
            "TMPDIR": str(tmp_path),
            "QS_PROVISION_SCOPE": "preid",
        },
    )
    assert result.returncode != 0
    calls = log.read_text().splitlines()
    assert any("create" in call for call in calls)
    assert any("ps -aq" in call and "com.quickscale.scope=preid" in call for call in calls)
    create_index = next(i for i, call in enumerate(calls) if "create" in call)
    cleanup_index = next(i for i, call in enumerate(calls) if "ps -aq" in call)
    assert create_index < cleanup_index


def test_roles_sql_and_safety_contracts_are_explicit() -> None:
    roles = (ROOT / "scripts/provision_test_roles.sh").read_text()
    helper = HELPER.read_text()
    assert "LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE" in roles
    assert "NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE" in roles
    assert "LOGIN CREATEDB BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEROLE" in roles
    assert "ON_ERROR_STOP=1" in roles and "ON_ERROR_STOP=1" in helper
    assert "eval " not in helper and "source " not in helper
    assert "image-contract" in helper and "label=com.quickscale.scope" in helper
    assert "apt.postgresql.org" in helper and "postgresql-client-18" in helper
    assert "GITHUB_PATH" in helper


def test_hyphenated_docker_container_name_remains_supported(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    executable(
        tools / "docker",
        r"""if [[ " $* " == *" -At "* ]]; then
  case " $* " in
    *"role_name=quickscale_test_role"*) echo "t|t|f|f|f|f" ;;
    *) echo "f|f|f|f|f|f" ;;
  esac
fi""",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{tools}:/usr/bin"
    result = subprocess.run(
        [
            "/bin/bash",
            str(ROOT / "scripts/provision_test_roles.sh"),
            "--docker",
            "--container",
            "quickscale-postgres-1",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_make_local_lifecycle_keeps_hosted_callers_compatible() -> None:
    makefile = (ROOT / "Makefile").read_text()
    integration = (ROOT / "scripts/test_integration.sh").read_text()
    isolation = (ROOT / "scripts/test_isolation_conformance.sh").read_text()
    assert makefile.count('$${GITHUB_ACTIONS:-}" = "true') >= 3
    assert (
        "scripts/provision_ci_postgres.sh run --profile restricted -- "
        "scripts/check_ci_locally.sh --e2e"
    ) in makefile
    assert '[[ "${GITHUB_ACTIONS:-}" != true ]]' in integration
    assert '[[ "${GITHUB_ACTIONS:-}" != true ]]' in isolation
