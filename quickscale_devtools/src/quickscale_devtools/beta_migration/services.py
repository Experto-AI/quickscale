"""Recipient Docker Compose service lifecycle for beta-migration verification."""

from __future__ import annotations

from .constants import (
    RECIPIENT_SERVICES_COMMAND_PREFIXES,
    RECIPIENT_SERVICES_COMPOSE_START_ARGV,
    RECIPIENT_SERVICES_COMPOSE_STOP_ARGV,
    RECIPIENT_SERVICES_PREFIX_ENV,
    RECIPIENT_SERVICES_READY_TIMEOUT_SECONDS,
    RECIPIENT_SERVICES_STOP_TIMEOUT_SECONDS,
    RECIPIENT_SERVICES_TIMEOUT_SECONDS,
)
from .model import BetaMigrationReport, VerificationCommandSpec
import os
import re
import socket
import subprocess
import time
from pathlib import Path


def _recipient_services_prefix(recipient_path: Path) -> str:
    """Return the Compose resource prefix for the recipient's throwaway stack.

    The value is lower-cased, every run of non-alphanumeric characters becomes
    ``_``, and the result is trimmed to the resource-prefix grammar
    (``[a-z0-9][a-z0-9_-]{0,62}``). The tool always exports the prefix, so the
    Compose child environment and the later ``quickscale manage`` container
    lookup agree on the same names.
    """
    candidate = re.sub(r"[^a-z0-9]+", "_", recipient_path.name.lower())
    candidate = candidate.strip("_-")[:63].strip("_-")
    if not candidate:
        return "quickscale_beta_recipient"
    return candidate


def _recipient_services_environment(recipient_path: Path) -> dict[str, str]:
    """Return the ambient environment plus the recipient stack's resource prefix."""
    environment = dict(os.environ)
    environment[RECIPIENT_SERVICES_PREFIX_ENV] = _recipient_services_prefix(
        recipient_path
    )
    return environment


def _spec_needs_recipient_services(spec: VerificationCommandSpec) -> bool:
    """Return whether a verification command runs against the Docker stack."""
    return any(
        spec.argv[: len(prefix)] == prefix
        for prefix in RECIPIENT_SERVICES_COMMAND_PREFIXES
    )


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
    """Environment for the recipient's Compose commands with unique host ports."""
    environment = _recipient_services_environment(recipient_path)
    backend_port, frontend_port = _reserve_free_host_ports(2)
    environment["PORT"] = backend_port
    environment["QUICKSCALE_FRONTEND_HOST_PORT"] = frontend_port
    return environment


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


def _wait_for_backend_container(recipient_path: Path, prefix: str) -> None:
    """Wait until the Compose backend container reports a running state.

    The backend service starts only after the database and frontend
    healthchecks pass, so a running backend container means the service-backed
    verification commands have a live stack to exec into.
    """
    container = f"{prefix}_backend"
    inspect_argv = ("docker", "inspect", "--format", "{{.State.Running}}", container)
    environment = _recipient_services_environment(recipient_path)
    deadline = time.monotonic() + RECIPIENT_SERVICES_READY_TIMEOUT_SECONDS
    last_detail = ""
    while True:
        try:
            probe = _run_compose_command(inspect_argv, recipient_path, environment, 30)
        except (subprocess.TimeoutExpired, OSError) as exc:
            last_detail = str(exc)
        else:
            if probe.returncode == 0 and probe.stdout.strip() == "true":
                return
            last_detail = _tail(probe.stderr or probe.stdout)
        if time.monotonic() >= deadline:
            raise ValueError(
                f"the recipient backend container {container} did not reach a "
                f"running state within {RECIPIENT_SERVICES_READY_TIMEOUT_SECONDS}s: "
                f"{last_detail}"
            )
        time.sleep(2)


def _start_recipient_services(report: BetaMigrationReport) -> str:
    """Start the recipient's Docker Compose stack before service-backed commands.

    The stack is brought up from a clean state (any leftover throwaway
    containers and volumes are removed first) and the call returns only once the
    backend container is running. Failures raise ``ValueError`` so the workflow
    fails closed instead of running docker-backed verification against nothing.
    """
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")
    recipient_path = report.recipient.path
    prefix = _recipient_services_prefix(recipient_path)
    environment = _compose_environment(recipient_path)

    # A throwaway recipient is regenerated on every iteration; clearing any
    # leftover stack first keeps a previous run's database and volumes from
    # masking or falsifying this run's verification result.
    try:
        _run_compose_command(
            RECIPIENT_SERVICES_COMPOSE_STOP_ARGV,
            recipient_path,
            environment,
            RECIPIENT_SERVICES_STOP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired, OSError:
        pass

    try:
        result = _run_compose_command(
            RECIPIENT_SERVICES_COMPOSE_START_ARGV,
            recipient_path,
            environment,
            RECIPIENT_SERVICES_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"`docker compose up -d --build` timed out after "
            f"{RECIPIENT_SERVICES_TIMEOUT_SECONDS}s in {recipient_path}."
        ) from exc
    except OSError as exc:
        raise ValueError(
            f"Docker Compose is required to verify the recipient's docker-backed "
            f"commands: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = _tail(result.stderr) or _tail(result.stdout) or "(no output)"
        raise ValueError(
            f"`docker compose up -d --build` failed with exit code "
            f"{result.returncode} in {recipient_path}: {detail}"
        )
    _wait_for_backend_container(recipient_path, prefix)
    return (
        f"Started the recipient Docker Compose stack (resource prefix {prefix}, "
        f"backend container {prefix}_backend) for the service-backed verification "
        f"commands."
    )


def _stop_recipient_services(report: BetaMigrationReport) -> str | None:
    """Stop the recipient's stack; return a failure detail instead of raising."""
    if report.recipient is None:
        return "the recipient snapshot is unavailable"
    recipient_path = report.recipient.path
    try:
        result = _run_compose_command(
            RECIPIENT_SERVICES_COMPOSE_STOP_ARGV,
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
    return None
