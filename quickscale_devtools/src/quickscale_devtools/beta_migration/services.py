"""Recipient Docker Compose database lifecycle for beta-migration verification."""

from __future__ import annotations

from .constants import (
    RECIPIENT_SERVICES_COMPOSE_DB_UP_ARGV,
    RECIPIENT_SERVICES_COMPOSE_DOWN_ARGV,
    RECIPIENT_SERVICES_CONTAINER_DATABASE_PORT,
    RECIPIENT_SERVICES_PREFIX_ENV,
    RECIPIENT_SERVICES_READY_TIMEOUT_SECONDS,
    RECIPIENT_SERVICES_STOP_TIMEOUT_SECONDS,
    RECIPIENT_SERVICES_TIMEOUT_SECONDS,
)
from .model import BetaMigrationReport, VerificationCommandSpec
from .verification_environment import merge_project_verification_environment
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote


def _recipient_services_prefix(recipient_path: Path) -> str:
    """Return the Compose resource prefix for the recipient's throwaway stack.

    The value is lower-cased, every run of non-alphanumeric characters becomes
    ``_``, and the result is trimmed to the resource-prefix grammar
    (``[a-z0-9][a-z0-9_-]{0,62}``). The tool always exports the prefix, so the
    Compose child environment and the later container lookups agree on the
    same names.
    """
    candidate = re.sub(r"[^a-z0-9]+", "_", recipient_path.name.lower())
    candidate = candidate.strip("_-")[:63].strip("_-")
    if not candidate:
        return "quickscale_beta_recipient"
    return candidate


def _recipient_services_environment(recipient_path: Path) -> dict[str, str]:
    """Return the ambient environment plus the recipient stack's resource prefix.

    The project's declared verification entries are merged in so both the
    Compose interpolation at service start and the verification commands that
    run the project's startup checks can satisfy an enabled module's vendor
    secret requirement and use the declared runtime role URL.
    """
    environment = dict(os.environ)
    environment[RECIPIENT_SERVICES_PREFIX_ENV] = _recipient_services_prefix(
        recipient_path
    )
    return merge_project_verification_environment(environment, recipient_path)


def _spec_needs_recipient_services(spec: VerificationCommandSpec) -> bool:
    """Return whether a verification command needs the recipient database up."""
    return spec.requires_recipient_database


def _reserve_free_host_ports(count: int) -> tuple[str, ...]:
    """Reserve free loopback ports for the throwaway stack's host publications."""
    sockets: list[socket.socket] = []
    try:
        ports: list[str] = []
        for _ in range(count):
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.bind(("127.0.0.1", 0))
            sockets.append(probe)
            ports.append(str(probe.getsockname()[1]))
        return tuple(ports)
    finally:
        for probe in sockets:
            probe.close()


def _compose_environment(recipient_path: Path) -> dict[str, str]:
    """Environment for the recipient's Compose commands."""
    return _recipient_services_environment(recipient_path)


def _database_override_path(recipient_path: Path) -> Path:
    """Return the tool-managed database publication override beside the recipient."""
    return recipient_path.parent / f".{recipient_path.name}.database-port.yml"


def _write_database_override(recipient_path: Path) -> tuple[Path, str]:
    """Publish the recipient database on a reserved loopback port.

    The override lives outside the recipient so the project's own Compose file
    stays untouched, and it exists only for the duration of one verification
    run.
    """
    port = _reserve_free_host_ports(1)[0]
    override_path = _database_override_path(recipient_path)
    override_path.write_text(
        "services:\n"
        "  db:\n"
        "    ports:\n"
        f'      - "127.0.0.1:{port}:{RECIPIENT_SERVICES_CONTAINER_DATABASE_PORT}"\n'
    )
    return override_path, port


def _compose_command(
    tail: tuple[str, ...],
    recipient_path: Path,
    override_path: Path | None = None,
) -> tuple[str, ...]:
    """Build one fixed-argv Docker Compose command for the recipient."""
    arguments = ["docker", "compose", "-f", str(recipient_path / "docker-compose.yml")]
    if override_path is not None:
        arguments.extend(["-f", str(override_path)])
    return (*arguments, *tail)


def _run_compose_command(
    argv: tuple[str, ...],
    recipient_path: Path,
    environment: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run one fixed-argv Docker Compose command in the recipient."""
    return subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        list(argv),
        cwd=recipient_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _tail(text: str, limit: int = 400) -> str:
    """Collapse whitespace and keep the trailing diagnostic text."""
    cleaned = " ".join(text.split())
    return cleaned[-limit:] if len(cleaned) > limit else cleaned


def _wait_for_database_container(recipient_path: Path, prefix: str) -> None:
    """Wait until the Compose database container reports a healthy state."""
    container = f"{prefix}_db"
    inspect_argv = (
        "docker",
        "inspect",
        "--format",
        "{{.State.Health.Status}}",
        container,
    )
    environment = _recipient_services_environment(recipient_path)
    deadline = time.monotonic() + RECIPIENT_SERVICES_READY_TIMEOUT_SECONDS
    last_detail = ""
    while True:
        try:
            probe = _run_compose_command(inspect_argv, recipient_path, environment, 30)
        except (subprocess.TimeoutExpired, OSError) as exc:
            last_detail = str(exc)
        else:
            state = probe.stdout.strip()
            if probe.returncode == 0 and state == "healthy":
                return
            if probe.returncode == 0 and state == "unhealthy":
                raise ValueError(
                    f"the recipient database container {container} reported an "
                    "unhealthy state."
                )
            last_detail = _tail(probe.stderr or probe.stdout)
        if time.monotonic() >= deadline:
            raise ValueError(
                f"the recipient database container {container} did not become "
                f"healthy within {RECIPIENT_SERVICES_READY_TIMEOUT_SECONDS}s: "
                f"{last_detail}"
            )
        time.sleep(2)


def _inspect_container(
    recipient_path: Path, container: str, inspect_format: str
) -> object:
    """Return one container inspect value as parsed JSON."""
    inspect_argv = ["docker", "inspect", "--format", inspect_format, container]
    probe = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        inspect_argv,
        cwd=recipient_path,
        env=_recipient_services_environment(recipient_path),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if probe.returncode != 0:
        raise ValueError(
            f"Unable to inspect the recipient database container {container}: "
            f"{_tail(probe.stderr or probe.stdout) or '(no output)'}"
        )
    try:
        return json.loads(probe.stdout or "null")
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Unexpected inspect output for the recipient database container "
            f"{container}: {_tail(probe.stdout)}"
        ) from exc


def _recipient_database_url(recipient_path: Path) -> str:
    """Return the host URL of the running recipient database service.

    The database name, user, and password come from the container's own
    environment and the host port from its loopback publication, so the
    database-backed verification command connects to exactly the database the
    project's Compose service defines.
    """
    container = f"{_recipient_services_prefix(recipient_path)}_db"
    entries: dict[str, str] = {}
    container_environment = _inspect_container(
        recipient_path, container, "{{json .Config.Env}}"
    )
    if isinstance(container_environment, list):
        for entry in container_environment:
            if not isinstance(entry, str):
                continue
            name, separator, value = entry.partition("=")
            if separator:
                entries[name] = value
    ports = _inspect_container(
        recipient_path, container, "{{json .NetworkSettings.Ports}}"
    )
    publications: list[dict[str, object]] = []
    if isinstance(ports, dict):
        candidate = ports.get(f"{RECIPIENT_SERVICES_CONTAINER_DATABASE_PORT}/tcp")
        if isinstance(candidate, list):
            publications = [item for item in candidate if isinstance(item, dict)]
    database = entries.get("POSTGRES_DB")
    user = entries.get("POSTGRES_USER")
    if not database or not user or not publications:
        raise ValueError(
            f"The recipient database container {container} does not publish a "
            f"database on a host port with the Compose service credentials."
        )
    host = str(publications[0].get("HostIp") or "127.0.0.1")
    host_port = publications[0].get("HostPort")
    credentials = quote(user, safe="")
    password = entries.get("POSTGRES_PASSWORD")
    if password:
        credentials += f":{quote(password, safe='')}"
    return f"postgresql://{credentials}@{host}:{host_port}/{database}"


def _start_recipient_services(report: BetaMigrationReport) -> str:
    """Start the recipient's database service with a host-published port.

    The project's generated production image compiles the frontend sources in
    its build, and those sources are pre-port manual work, so the migration
    verification runs in the recipient's own Poetry environment against the
    Compose database service instead of a backend container. The database
    starts from a clean state and must report healthy; failures raise
    ``ValueError`` so the workflow fails closed instead of running the
    database-backed verification against nothing.
    """
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")
    recipient_path = report.recipient.path
    prefix = _recipient_services_prefix(recipient_path)
    environment = _compose_environment(recipient_path)
    existing_override = _database_override_path(recipient_path)

    # A throwaway recipient is regenerated on every iteration; clearing any
    # leftover stack first keeps a previous run's database and volumes from
    # masking or falsifying this run's verification result.
    try:
        _run_compose_command(
            _compose_command(
                RECIPIENT_SERVICES_COMPOSE_DOWN_ARGV,
                recipient_path,
                existing_override if existing_override.is_file() else None,
            ),
            recipient_path,
            environment,
            RECIPIENT_SERVICES_STOP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired, OSError:
        pass

    override_path, port = _write_database_override(recipient_path)
    try:
        db_result = _run_compose_command(
            _compose_command(
                RECIPIENT_SERVICES_COMPOSE_DB_UP_ARGV, recipient_path, override_path
            ),
            recipient_path,
            environment,
            RECIPIENT_SERVICES_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"`docker compose up -d db` timed out after "
            f"{RECIPIENT_SERVICES_TIMEOUT_SECONDS}s in {recipient_path}."
        ) from exc
    except OSError as exc:
        raise ValueError(
            f"Docker Compose is required to verify the recipient's database-backed "
            f"commands: {exc}"
        ) from exc
    if db_result.returncode != 0:
        detail = _tail(db_result.stderr) or _tail(db_result.stdout) or "(no output)"
        raise ValueError(
            f"`docker compose up -d db` failed with exit code "
            f"{db_result.returncode} in {recipient_path}: {detail}"
        )
    _wait_for_database_container(recipient_path, prefix)
    return (
        f"Started the recipient Docker Compose database service (resource prefix "
        f"{prefix}, container {prefix}_db, host port {port}) for the database-backed "
        f"verification commands."
    )


def _stop_recipient_services(report: BetaMigrationReport) -> str | None:
    """Stop the recipient's database service; return a failure detail on error."""
    if report.recipient is None:
        return "the recipient snapshot is unavailable"
    recipient_path = report.recipient.path
    override_path = _database_override_path(recipient_path)
    try:
        result = _run_compose_command(
            _compose_command(
                RECIPIENT_SERVICES_COMPOSE_DOWN_ARGV,
                recipient_path,
                override_path if override_path.is_file() else None,
            ),
            recipient_path,
            _recipient_services_environment(recipient_path),
            RECIPIENT_SERVICES_STOP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return (
            f"`docker compose down` timed out after "
            f"{RECIPIENT_SERVICES_STOP_TIMEOUT_SECONDS}s"
        )
    except OSError as exc:
        return f"Docker Compose is unavailable: {exc}"
    if result.returncode != 0:
        return (
            f"`docker compose down` failed with exit code {result.returncode}: "
            f"{_tail(result.stderr) or _tail(result.stdout) or '(no output)'}"
        )
    try:
        override_path.unlink(missing_ok=True)
    except OSError as exc:
        return f"the database port override file could not be removed: {exc}"
    return None
