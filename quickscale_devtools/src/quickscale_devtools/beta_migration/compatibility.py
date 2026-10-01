"""Effective runtime launcher/settings compatibility checks."""

from .constants import (
    _GUNICORN_SHELL_WORD,
    _REQUIRED_RUNTIME_COMMANDS,
    _RUNTIME_COMMAND_LAUNCHERS,
    _SHELL_ENV_ASSIGNMENT,
    _START_SH_PACKAGE_REFERENCE,
)
from .dockerfile import _dockerfile_final_stage_instructions
from .identity import _replace_identity_text_for_path
from .model import (
    BetaMigrationReport,
    RuntimeFileProvenance,
    _append_blocker,
    _append_check,
)
from .runtime_commands import _extract_launcher_runtime_commands
from .settings_facade import _load_settings_facade_contract
from .shell import _active_launcher_line, _shell_tokens
from .start_sh import _start_sh_reachable_logical_lines
import json
import re
from pathlib import Path


def _render_effective_launcher_text(
    report: BetaMigrationReport, launcher_path: Path
) -> str:
    """Render a launcher as it will look after fresh-first identity substitution."""
    if report.donor is None or report.recipient is None:
        raise ValueError(
            "Project snapshots are required for runtime compatibility checks."
        )

    try:
        launcher_text = launcher_path.read_text()
    except OSError as exc:
        raise ValueError(
            f"Unable to read effective runtime launcher {launcher_path}: {exc}"
        ) from exc

    source = report.recipient
    target = report.donor
    return _replace_identity_text_for_path(
        launcher_text,
        relative_path=launcher_path.name,
        source=source.identity,
        target=target.identity,
    )


def _dockerfile_final_stage_settings_assignment(
    launcher_path: Path, launcher_text: str
) -> tuple[int, str] | None:
    """Return the effective final-stage DJANGO_SETTINGS_MODULE assignment."""
    assignment: tuple[int, str] | None = None
    for line_number, instruction in _dockerfile_final_stage_instructions(
        launcher_path, launcher_text
    ):
        directive, _, payload = instruction.partition(" ")
        if directive.upper() != "ENV":
            continue
        tokens = _shell_tokens(launcher_path, line_number, payload)
        parsed_assignments: list[tuple[str, str]] = []
        if tokens and all(
            _SHELL_ENV_ASSIGNMENT.fullmatch(token) is not None for token in tokens
        ):
            for token in tokens:
                match = _SHELL_ENV_ASSIGNMENT.fullmatch(token)
                if match is not None:
                    parsed_assignments.append(
                        (match.group("name"), match.group("value"))
                    )
        elif (
            len(tokens) >= 2
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tokens[0]) is not None
        ):
            parsed_assignments.append((tokens[0], " ".join(tokens[1:])))
        for name, value in parsed_assignments:
            if name == "DJANGO_SETTINGS_MODULE":
                assignment = (line_number, value)
    return assignment


def _launcher_package_mismatch(
    launcher_path: Path,
    launcher_text: str,
    *,
    expected_package: str,
) -> str | None:
    """Return a mismatch when any execution-relevant package target is unresolved."""
    mismatches: list[str] = []
    referenced_packages: list[str] = []
    gunicorn_invocations = 0
    docker_runtime_directives = 0
    docker_continuation = False

    if launcher_path.name == "start.sh":
        launcher_lines = [
            (line_number, line)
            for line_number, line, reachable, _unconditional in _start_sh_reachable_logical_lines(
                launcher_path, launcher_text
            )
            if reachable
        ]
    else:
        launcher_lines = list(enumerate(launcher_text.splitlines(), start=1))

    for line_number, line in launcher_lines:
        active_line = _active_launcher_line(launcher_path, line)
        if not active_line.strip():
            continue
        continued_docker_instruction = docker_continuation
        if launcher_path.name == "Dockerfile":
            docker_continuation = active_line.rstrip().endswith("\\")
        if launcher_path.name == "start.sh":
            matches = list(_START_SH_PACKAGE_REFERENCE.finditer(active_line))
            referenced_packages.extend(match.group(1) for match in matches)
            if active_line.count(".wsgi") != len(matches):
                mismatches.append(
                    f"{launcher_path}:{line_number} contains an unresolved or dynamic "
                    ".wsgi target"
                )
            for match in matches:
                if match.group(1) != expected_package:
                    mismatches.append(
                        f"{launcher_path}:{line_number} references {match.group(1)}; "
                        f"expected {expected_package}"
                    )

        if launcher_path.name == "Dockerfile" and not continued_docker_instruction:
            directive_match = re.match(
                r"^\s*(CMD|ENTRYPOINT)\s+(.+?)\s*$",
                active_line,
                re.IGNORECASE,
            )
            if directive_match is not None:
                docker_runtime_directives += 1
                directive = directive_match.group(1).upper()
                payload = directive_match.group(2)
                try:
                    command = json.loads(payload)
                except json.JSONDecodeError:
                    command = None
                if directive != "CMD" or command != ["./start.sh"]:
                    mismatches.append(
                        f"{launcher_path}:{line_number} must use the canonical "
                        'CMD ["./start.sh"] runtime entrypoint'
                    )

        if launcher_path.name != "start.sh" or not re.search(
            r"\bgunicorn\b", active_line
        ):
            continue
        tokens = _shell_tokens(launcher_path, line_number, active_line)
        if tokens[-1:] == ["\\"]:
            tokens.pop()
        gunicorn_indices = [
            index for index, token in enumerate(tokens) if token == _GUNICORN_SHELL_WORD
        ]
        gunicorn_invocations += len(gunicorn_indices)
        for index in gunicorn_indices:
            if (
                index + 1 >= len(tokens)
                or re.fullmatch(
                    rf"{re.escape(expected_package)}\.wsgi(?::application)?",
                    tokens[index + 1],
                )
                is None
            ):
                rendered_target = (
                    tokens[index + 1] if index + 1 < len(tokens) else "(missing)"
                )
                mismatches.append(
                    f"{launcher_path}:{line_number} has unresolved or incorrect gunicorn "
                    f"target {rendered_target!r}; expected {expected_package}.wsgi:application"
                )

    if launcher_path.name == "start.sh" and not referenced_packages:
        mismatches.append(f"{launcher_path} contains no static .wsgi package reference")
    if launcher_path.name == "start.sh" and gunicorn_invocations != 1:
        mismatches.append(
            f"{launcher_path} must contain exactly one static gunicorn invocation; "
            f"found {gunicorn_invocations}"
        )
    if launcher_path.name == "Dockerfile" and docker_runtime_directives != 1:
        mismatches.append(
            f"{launcher_path} must contain exactly one canonical Docker runtime "
            f"CMD directive; found {docker_runtime_directives}"
        )
    if launcher_path.name == "Dockerfile":
        settings_assignment = _dockerfile_final_stage_settings_assignment(
            launcher_path, launcher_text
        )
        expected_settings = f"{expected_package}.settings.production"
        if settings_assignment is None:
            mismatches.append(
                f"{launcher_path} final stage must define ENV "
                f"DJANGO_SETTINGS_MODULE={expected_settings}"
            )
        elif settings_assignment[1] != expected_settings:
            line_number, actual_settings = settings_assignment
            mismatches.append(
                f"{launcher_path}:{line_number} final-stage DJANGO_SETTINGS_MODULE "
                f"is {actual_settings!r}; expected {expected_settings!r}"
            )
    if not mismatches:
        return None
    return "; ".join(mismatches)


def _select_effective_runtime_files(
    report: BetaMigrationReport,
) -> tuple[Path, tuple[Path, Path]]:
    """Record provenance and return effective settings and launcher source paths."""
    if report.donor is None or report.recipient is None:
        raise ValueError(
            "Project snapshots are required for runtime compatibility checks."
        )

    report.runtime_provenance = RuntimeFileProvenance(
        settings_production="donor",
        start_sh="recipient",
        dockerfile="recipient",
    )
    return (
        report.donor.package_dir / "settings" / "production.py",
        (
            report.recipient.path / "start.sh",
            report.recipient.path / "Dockerfile",
        ),
    )


def _validate_runtime_compatibility(report: BetaMigrationReport) -> None:
    """Fail closed when effective launchers invoke unsupported command modes."""
    donor = report.donor
    recipient = report.recipient
    if report.blockers or donor is None or recipient is None:
        return

    settings_path, launcher_paths = _select_effective_runtime_files(report)
    try:
        known_commands = _load_settings_facade_contract(settings_path)
        expected_package = donor.identity.package
        referenced_commands: dict[str, set[str]] = {
            "QUICKSCALE_PRIVILEGED_COMMAND": set(),
            "QUICKSCALE_NON_DB_COMMAND": set(),
        }
        command_sources: dict[tuple[str, str], list[Path]] = {}
        package_mismatches: list[str] = []
        launcher_command_mismatches: list[str] = []
        for launcher_path in launcher_paths:
            launcher_text = _render_effective_launcher_text(report, launcher_path)
            launcher_commands = _extract_launcher_runtime_commands(
                launcher_path,
                known_commands=known_commands,
                launcher_text=launcher_text,
            )
            for environment_name, commands in launcher_commands.items():
                referenced_commands[environment_name].update(commands)
                for command in commands:
                    command_sources.setdefault((environment_name, command), []).append(
                        launcher_path
                    )
                    expected_launcher = _RUNTIME_COMMAND_LAUNCHERS[environment_name]
                    if launcher_path.name != expected_launcher:
                        launcher_command_mismatches.append(
                            f"{environment_name}={command} appears in {launcher_path}; "
                            f"it is only supported in {expected_launcher}"
                        )
                if launcher_path.name == _RUNTIME_COMMAND_LAUNCHERS[environment_name]:
                    for command in sorted(
                        _REQUIRED_RUNTIME_COMMANDS[environment_name] - commands
                    ):
                        launcher_command_mismatches.append(
                            f"required {environment_name}={command} invocation is "
                            f"missing from the effective {launcher_path.name}"
                        )
            package_mismatch = _launcher_package_mismatch(
                launcher_path,
                launcher_text,
                expected_package=expected_package,
            )
            if package_mismatch is not None:
                package_mismatches.append(package_mismatch)
    except ValueError as exc:
        detail = str(exc)
        _append_check(
            report,
            name="runtime-launcher-settings-compatibility",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    unsupported: list[str] = []
    for environment_name, commands in referenced_commands.items():
        for command in sorted(commands - known_commands[environment_name]):
            sources = ", ".join(
                str(path) for path in command_sources[(environment_name, command)]
            )
            unsupported.append(
                f"{environment_name}={command} in {sources} is not allowed by {settings_path}"
            )

    if unsupported or launcher_command_mismatches or package_mismatches:
        mismatches = [*unsupported, *launcher_command_mismatches, *package_mismatches]
        detail = "Effective runtime launcher/settings mismatch: " + "; ".join(
            mismatches
        )
        _append_check(
            report,
            name="runtime-launcher-settings-compatibility",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    detail_parts = []
    for environment_name in (
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_NON_DB_COMMAND",
    ):
        rendered = ", ".join(sorted(referenced_commands[environment_name])) or "(none)"
        detail_parts.append(f"{environment_name}: {rendered}")
    _append_check(
        report,
        name="runtime-launcher-settings-compatibility",
        status="passed",
        detail=(
            f"Effective launchers are compatible with {settings_path}: "
            + "; ".join(detail_parts)
        ),
    )
