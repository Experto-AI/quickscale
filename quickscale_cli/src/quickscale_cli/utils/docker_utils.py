"""Docker interaction utilities for QuickScale CLI."""

from dataclasses import dataclass
import hashlib
import os
import re
import socket
import subprocess
import sys
import time
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal


class DockerComposePluginRequiredError(RuntimeError):
    """Raised when the Docker Compose v2 plugin is unavailable."""


class BackendImageIdentityError(ValueError):
    """Raised when the inputs for the development backend image are invalid."""


class DockerContainerStatusError(RuntimeError):
    """Raised when Docker cannot provide one valid container status result."""


@dataclass(frozen=True, slots=True)
class ContainerStatus:
    """Structured state returned for one exact-name Docker container query."""

    state: Literal["absent", "created", "running", "exited"]
    exit_code: int | None = None
    display_status: str | None = None

    def __post_init__(self) -> None:
        if self.state not in {"absent", "created", "running", "exited"}:
            raise ValueError(f"unknown container state: {self.state!r}")
        if self.state == "exited" and not isinstance(self.exit_code, int):
            raise ValueError("exited container status requires an integer exit code")
        if self.state != "exited" and self.exit_code is not None:
            raise ValueError("only exited container status may have an exit code")


@dataclass(frozen=True)
class BackendImageIdentity:
    """The stable development backend image contract.

    ``manifest`` is retained for diagnostics and tests.  The Docker tag uses
    the complete SHA-256 digest rather than a truncated prefix so two distinct
    manifests cannot silently address the same local image.
    """

    reference: str
    digest: str
    manifest: bytes

    @property
    def image_reference(self) -> str:
        """Backward-compatible descriptive name for :attr:`reference`."""
        return self.reference


IMAGE_REFERENCE_ENV_VAR = "QUICKSCALE_BACKEND_IMAGE"
IMAGE_DIGEST_ENV_VAR = "QUICKSCALE_BACKEND_IMAGE_DIGEST"
RESOURCE_PREFIX_ENV_VAR = "QUICKSCALE_RESOURCE_PREFIX"
_IMAGE_CONTRACT_VERSION = b"quickscale-backend-image-v1"
_MISSING_LOCK_MARKER = b"<missing-poetry-lock>"
_DEFAULT_BUILD_ARGS = {"INSTALL_DEV": "true"}
_RESOURCE_PREFIX_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}\Z")


def _read_required_bytes(path: Path, label: str) -> bytes:
    """Read a required identity input without normalising its bytes."""
    try:
        return path.read_bytes()
    except OSError as error:
        raise BackendImageIdentityError(
            f"Unable to read required backend image input {label}: {path}"
        ) from error


def _read_project_metadata(path: Path, label: str) -> dict:
    """Read and validate one TOML metadata file."""
    raw = _read_required_bytes(path, label)
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise BackendImageIdentityError(
            f"Malformed backend image input {label}: {path}"
        ) from error
    if not isinstance(data, dict):
        raise BackendImageIdentityError(
            f"Malformed backend image input {label}: {path}"
        )
    return data


def _metadata_value(data: dict, field: str, label: str) -> str:
    """Return a non-empty package metadata value from PEP 621 or Poetry."""
    project = data.get("project")
    poetry = (
        data.get("tool", {}).get("poetry")
        if isinstance(data.get("tool"), dict)
        else None
    )
    value = project.get(field) if isinstance(project, dict) else None
    if value is None and isinstance(poetry, dict):
        value = poetry.get(field)
    if not isinstance(value, str) or not value:
        raise BackendImageIdentityError(
            f"Missing or invalid {field} in embedded package metadata: {label}"
        )
    return value


def _python_constraint(data: dict, path: Path) -> str:
    """Extract the generated project's authoritative Python constraint."""
    project = data.get("project")
    value = project.get("requires-python") if isinstance(project, dict) else None
    if value is None:
        poetry = (
            data.get("tool", {}).get("poetry")
            if isinstance(data.get("tool"), dict)
            else None
        )
        dependencies = poetry.get("dependencies") if isinstance(poetry, dict) else None
        value = dependencies.get("python") if isinstance(dependencies, dict) else None
    if not isinstance(value, str) or not value:
        raise BackendImageIdentityError(
            f"Missing or invalid generated Python constraint: {path}"
        )
    return value


def _frame_field(name: str, value: bytes) -> bytes:
    """Frame one manifest field with explicit UTF-8 name/value lengths."""
    name_bytes = name.encode("ascii")
    return (
        len(name_bytes).to_bytes(4, "big")
        + name_bytes
        + len(value).to_bytes(8, "big")
        + value
    )


def _frame_named_pairs(pairs: list[tuple[str, str]], label: str) -> bytes:
    """Frame ordered name/value records without delimiter ambiguity."""
    return b"".join(
        _frame_field(
            label,
            _frame_field("name", name.encode("utf-8"))
            + _frame_field("version", value.encode("utf-8")),
        )
        for name, value in pairs
    )


def validate_resource_prefix(prefix: str) -> str:
    """Validate and return a Docker-safe resource prefix."""
    if (
        not isinstance(prefix, str)
        or _RESOURCE_PREFIX_PATTERN.fullmatch(prefix) is None
    ):
        raise ValueError(
            "QUICKSCALE_RESOURCE_PREFIX must start with a lowercase ASCII letter or "
            "digit and contain only lowercase letters, digits, '_' or '-'"
        )
    return prefix


def get_resource_prefix(
    project_path: Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Return the validated explicit resource prefix or ordinary project name."""
    source_environment = os.environ if environment is None else environment
    configured = source_environment.get(RESOURCE_PREFIX_ENV_VAR)
    if configured is not None:
        return validate_resource_prefix(configured)
    path = project_path if project_path is not None else Path.cwd()
    return validate_resource_prefix(compose_project_name(path))


def _embedded_module_versions(modules_root: Path) -> list[tuple[str, str]]:
    """Return sorted embedded package name/version pairs for the manifest."""
    if not modules_root.exists():
        return []
    if not modules_root.is_dir():
        raise BackendImageIdentityError(
            f"Embedded modules path is not a directory: {modules_root}"
        )
    try:
        module_paths = sorted(path for path in modules_root.iterdir() if path.is_dir())
    except OSError as error:
        raise BackendImageIdentityError(
            f"Unable to inspect embedded modules: {modules_root}"
        ) from error

    modules: list[tuple[str, str]] = []
    for module_path in module_paths:
        metadata_path = module_path / "pyproject.toml"
        if not metadata_path.exists():
            raise BackendImageIdentityError(
                f"Missing embedded package metadata: {metadata_path}"
            )
        metadata = _read_project_metadata(metadata_path, f"module {module_path.name}")
        modules.append(
            (
                _metadata_value(metadata, "name", module_path.name),
                _metadata_value(metadata, "version", module_path.name),
            )
        )
    return modules


def _validated_build_args(
    build_args: Mapping[str, str] | None,
) -> dict[str, str]:
    """Return manifest build arguments after strict string validation."""
    selected_args = dict(_DEFAULT_BUILD_ARGS if build_args is None else build_args)
    invalid = any(
        not isinstance(name, str) or not name or not isinstance(value, str)
        for name, value in selected_args.items()
    )
    if invalid:
        raise BackendImageIdentityError(
            "Backend image build arguments must be non-empty strings"
        )
    return selected_args


def build_backend_image_identity(
    project_path: Path | None = None,
    *,
    build_args: Mapping[str, str] | None = None,
) -> BackendImageIdentity:
    """Build the deterministic full-digest backend image identity.

    The project path is used only to locate generated files.  It is never
    included in the manifest, which makes identical generated inputs produce
    the same reference in different directories.
    """
    root = (project_path or Path.cwd()).resolve()
    dockerfile_path = root / "Dockerfile"
    pyproject_path = root / "pyproject.toml"
    dockerfile = _read_required_bytes(dockerfile_path, "Dockerfile")
    pyproject = _read_project_metadata(pyproject_path, "generated pyproject.toml")
    python_constraint = _python_constraint(pyproject, pyproject_path)

    lock_path = root / "poetry.lock"
    lock = (
        _MISSING_LOCK_MARKER
        if not lock_path.exists()
        else _read_required_bytes(lock_path, "poetry.lock")
    )

    modules = _embedded_module_versions(root / "modules")
    selected_args = _validated_build_args(build_args)

    fields = [
        ("contract", _IMAGE_CONTRACT_VERSION),
        ("dockerfile", dockerfile),
        ("python-constraint", python_constraint.encode("utf-8")),
        ("poetry-lock", lock),
        (
            "embedded-modules",
            _frame_named_pairs(sorted(modules), "module"),
        ),
        (
            "build-args",
            _frame_named_pairs(sorted(selected_args.items()), "arg"),
        ),
    ]
    manifest = b"".join(_frame_field(name, value) for name, value in fields)
    digest = hashlib.sha256(manifest).hexdigest()
    return BackendImageIdentity(
        reference=f"quickscale-backend:sha256-{digest}",
        digest=digest,
        manifest=manifest,
    )


# Descriptive alias used by callers that treat the digest as a calculation.
calculate_backend_image_identity = build_backend_image_identity


def build_backend_child_environment(
    identity: BackendImageIdentity,
    *,
    base_environment: Mapping[str, str] | None = None,
    project_path: Path | None = None,
) -> dict[str, str]:
    """Return a copied child environment containing P1 Compose values."""
    environment = dict(os.environ if base_environment is None else base_environment)
    environment[IMAGE_REFERENCE_ENV_VAR] = identity.reference
    environment[IMAGE_DIGEST_ENV_VAR] = identity.digest
    environment[RESOURCE_PREFIX_ENV_VAR] = get_resource_prefix(
        project_path,
        environment=environment,
    )
    return environment


def is_interactive() -> bool:
    """Check if running in an interactive terminal (has TTY)."""
    return sys.stdout.isatty() and sys.stdin.isatty()


def is_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=5)
        return True
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def find_docker_compose() -> Path | None:
    """Locate docker-compose.yml in current directory."""
    compose_file = Path("docker-compose.yml")
    return compose_file if compose_file.exists() else None


def get_docker_compose_command() -> list[str]:
    """Get the Docker Compose v2 command."""
    try:
        subprocess.run(
            ["docker", "compose", "version"], capture_output=True, check=True, timeout=2
        )
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as error:
        raise DockerComposePluginRequiredError(
            "Docker Compose v2 is required. Install or update Docker so the "
            "'docker compose' command is available."
        ) from error

    return ["docker", "compose"]


def _parse_container_status(container_name: str, output: str) -> ContainerStatus:
    """Parse one exact-name Docker status row into the structured contract."""
    rows = output.splitlines()
    if len(rows) != 1:
        raise DockerContainerStatusError(
            f"Docker status query for {container_name!r} returned {len(rows)} rows; "
            "expected exactly one result"
        )

    fields = rows[0].split("\t")
    if len(fields) != 3 or fields[0] != container_name:
        raise DockerContainerStatusError(
            f"Docker status query for {container_name!r} returned malformed output: "
            f"{rows[0]!r}"
        )

    state = fields[1].lower()
    display_status = fields[2]
    if state not in {"created", "running", "exited"}:
        raise DockerContainerStatusError(
            f"Docker status query for {container_name!r} returned unknown state "
            f"{fields[1]!r}"
        )
    if state == "exited":
        match = re.fullmatch(r"Exited \((-?\d+)\)(?: .*)?", display_status)
        if match is None:
            raise DockerContainerStatusError(
                f"Docker status query for {container_name!r} returned malformed "
                f"exited status: {display_status!r}"
            )
        return ContainerStatus(
            state="exited",
            exit_code=int(match.group(1)),
            display_status=display_status,
        )
    if state == "created":
        return ContainerStatus(state="created", display_status=display_status)
    return ContainerStatus(state="running", display_status=display_status)


def get_container_status(container_name: str) -> ContainerStatus:
    """Get one exact-name container's structured state.

    Empty output is the only successful ``absent`` result. Docker invocation
    failures and ambiguous or malformed output raise instead of masquerading as
    an absent container.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name=^/{re.escape(container_name)}$",
                "--format",
                "{{.Names}}\t{{.State}}\t{{.Status}}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        output = result.stdout.strip()
        if not output:
            return ContainerStatus(state="absent")
        return _parse_container_status(container_name, output)
    except (subprocess.SubprocessError, FileNotFoundError) as error:
        raise DockerContainerStatusError(
            f"Docker status query failed for container {container_name!r}: {error}"
        ) from error


def exec_in_container(
    container_name: str, command: list[str], interactive: bool = False
) -> int:
    """Execute command in a container."""
    cmd = ["docker", "exec"]
    if interactive:
        cmd.append("-it")
    cmd.append(container_name)
    cmd.extend(command)

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except subprocess.SubprocessError:
        return 1


def get_running_containers() -> list[str]:
    """Get list of running QuickScale containers."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        containers = [c for c in result.stdout.strip().split("\n") if c]
        return containers
    except subprocess.SubprocessError, subprocess.TimeoutExpired:
        return []


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a port is available for binding.

    This is more accurate than checking for listening processes because it
    actually attempts to bind to the port, which is what Docker will do.

    Args:
        port: Port number to check
        host: Host address (default: 0.0.0.0 to match Docker behavior)

    Returns:
        True if port is available, False if already in use
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        # Port is already in use
        sock.close()
        return False


def wait_for_port_release(
    port: int, timeout: float = 5.0, interval: float = 0.2
) -> bool:
    """Wait for a port to become available.

    Docker's proxy process may take a few seconds to fully release ports
    after containers are stopped, especially on slower systems.

    Args:
        port: Port number to wait for
        timeout: Maximum time to wait in seconds (default: 5.0 for docker-proxy cleanup)
        interval: Time between checks in seconds

    Returns:
        True if port became available, False if timeout
    """
    elapsed = 0.0
    while elapsed < timeout:
        if is_port_available(port):
            return True
        time.sleep(interval)
        elapsed += interval
    return False


def get_port_from_env() -> int:
    """Get the Docker port from the environment.

    Returns the docker-compose-aligned default (8000) only when ``PORT`` is
    unset. A present but non-numeric ``PORT`` is treated as a configuration
    error and raises ``ValueError``.
    """
    import os

    # Check PORT environment variable (matches docker-compose.yml)
    port_str = os.environ.get("PORT", "8000")
    try:
        return int(port_str)
    except ValueError as error:
        raise ValueError(
            f"PORT environment variable must be an integer, got {port_str!r}"
        ) from error


# ---------------------------------------------------------------------------
# Stale Compose volume detection
# ---------------------------------------------------------------------------
# Compose derives its project name from the project directory and prefixes
# every named volume with it.  A freshly generated project whose slug matches
# a previously-used one therefore silently reattaches to the old database,
# and Django then fails with an opaque ``InconsistentMigrationHistory``
# because the leftover schema predates the modules embedded this time.


def compose_project_name(project_path: Path) -> str:
    """Return the Compose project name derived from *project_path*.

    Mirrors Compose's normalization: lowercase, with every character outside
    ``[a-z0-9_-]`` replaced by an underscore and leading separators dropped.
    """
    resolved_name: object = project_path.resolve().name
    # Keep this helper friendly to callers that provide a lightweight Path
    # double; real Path objects always take the resolved branch.
    if not isinstance(resolved_name, str):
        resolved_name = project_path.name
    normalized = "".join(
        char if char.isalnum() or char in "_-" else "_"
        for char in resolved_name.lower()
    )
    return normalized.lstrip("_-")


def compose_declared_volume_names(compose_file: Path) -> list[str]:
    """Return the top-level named volumes declared in a Compose file.

    Parsed with a minimal line reader rather than a YAML dependency so the
    helper stays usable wherever the CLI runs.  Returns an empty list when the
    file is unreadable or declares no top-level ``volumes:`` block.
    """
    try:
        lines = compose_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    volumes: list[str] = []
    in_volumes_block = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[:1].isspace():
            # A new top-level key ends any volumes block we were reading.
            in_volumes_block = stripped.rstrip(":") == "volumes"
            continue
        if not in_volumes_block:
            continue
        # Only first-level entries under `volumes:` name a volume; deeper
        # indentation carries that volume's own options.
        indent = len(line) - len(line.lstrip())
        if indent > 2:
            continue
        name = stripped.split(":", 1)[0].strip()
        if name and name not in volumes:
            volumes.append(name)
    return volumes


def list_existing_volumes(names: list[str]) -> list[str]:
    """Return the subset of *names* that currently exist as Docker volumes."""
    if not names:
        return []
    try:
        result = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return []

    existing = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return [name for name in names if name in existing]


def find_stale_project_volumes(project_path: Path) -> list[str]:
    """Return pre-existing Compose volumes belonging to *project_path*.

    Meaningful only for a project whose database has never been provisioned
    by this checkout: any hit is a leftover from an earlier project that
    happened to use the same directory name.
    """
    compose_file = project_path / "docker-compose.yml"
    if not compose_file.exists():
        return []

    project_name = compose_project_name(project_path)
    if not project_name:
        return []

    candidates = [
        f"{project_name}_{volume}"
        for volume in compose_declared_volume_names(compose_file)
    ]
    return list_existing_volumes(candidates)


def remove_volumes(names: list[str]) -> tuple[list[str], list[str]]:
    """Remove Docker volumes, returning ``(removed, failed)`` name lists."""
    removed: list[str] = []
    failed: list[str] = []
    for name in names:
        try:
            result = subprocess.run(
                ["docker", "volume", "rm", name],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            failed.append(name)
            continue
        if result.returncode == 0:
            removed.append(name)
        else:
            failed.append(name)
    return removed, failed


def compose_down(project_path: Path) -> bool:
    """Stop and remove this project's Compose containers (volumes untouched).

    Containers left behind by an earlier project of the same name keep its
    volumes attached, so they must be released before the volumes can be
    removed.  Returns True when Compose reports success.
    """
    try:
        compose_cmd = get_docker_compose_command()
    except DockerComposePluginRequiredError:
        return False

    try:
        result = subprocess.run(
            compose_cmd + ["down", "--remove-orphans"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False
    return result.returncode == 0
