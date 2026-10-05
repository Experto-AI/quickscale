"""Extraction of static runtime command selectors from launchers."""

from .constants import (
    _RUNTIME_COMMAND_NAMES,
    _SHELL_ENV_ASSIGNMENT,
    _STATIC_RUNTIME_COMMAND,
    _UNCONDITIONAL_RUNTIME_COMMANDS,
)
from .dockerfile import (
    _dockerfile_final_stage_physical_lines,
    _validate_dockerfile_grammar,
)
from .shell import (
    _active_launcher_line,
    _has_runtime_selector_marker,
    _is_shell_operator,
    _shell_tokens,
    _validate_persistent_environment_mutation,
)
from .start_sh import (
    _start_sh_reachable_logical_lines,
    _validate_start_sh_grammar,
    _validate_unmarked_manage_command,
)
import re
from pathlib import Path


def _reject_selector_line_continuation(
    launcher_path: Path, *, line_number: int, active_line: str
) -> None:
    """Reject shell line continuations on non-Dockerfile selector lines."""
    if launcher_path.name != "Dockerfile" and active_line.rstrip().endswith("\\"):
        raise ValueError(
            f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND selectors must use one static literal "
            "assignment without shell line continuation."
        )


def _selector_line_tokens(
    launcher_path: Path, *, line_number: int, active_line: str
) -> list[str]:
    """Tokenize a selector line, stripping its Dockerfile RUN/&& decorations."""
    tokens = _shell_tokens(launcher_path, line_number, active_line)
    if not tokens:
        return []
    if launcher_path.name == "Dockerfile" and tokens[-1:] == ["&&"]:
        tokens.pop()
    if any(_is_shell_operator(token) for token in tokens):
        raise ValueError(
            f"{launcher_path}:{line_number}: runtime command selectors must be one-shot "
            "environment prefixes for one command; shell control operators are not supported."
        )
    if launcher_path.name == "Dockerfile" and tokens[:1] == ["RUN"]:
        tokens.pop(0)
    return tokens


def _scan_selector_assignments(
    tokens: list[str], launcher_path: Path, *, line_number: int
) -> list[tuple[int, str, str]]:
    """Collect selector assignments and reject dynamically constructed names."""
    selector_assignments: list[tuple[int, str, str]] = []
    for index, token in enumerate(tokens):
        assignment_match = _SHELL_ENV_ASSIGNMENT.fullmatch(token)
        if assignment_match is not None:
            assignment_name = assignment_match.group("name")
            assignment_value = assignment_match.group("value")
            if assignment_name in _RUNTIME_COMMAND_NAMES:
                selector_assignments.append((index, assignment_name, assignment_value))
                continue
            if "QUICKSCALE_" in assignment_name and "COMMAND" in assignment_name:
                raise ValueError(
                    f"{launcher_path}:{line_number}: runtime selector {assignment_name!r} "
                    "must use exactly QUICKSCALE_PRIVILEGED_COMMAND or "
                    "QUICKSCALE_NON_DB_COMMAND with a static literal command."
                )
        elif "QUICKSCALE_" in token and "COMMAND" in token:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND selectors must use a static literal "
                "NAME=value environment assignment."
            )
    return selector_assignments


def _resolve_python_command_index(
    tokens: list[str], launcher_path: Path, *, line_number: int
) -> int:
    """Return the single python token index the selector must prefix."""
    python_indices = [
        index for index, token in enumerate(tokens) if token in {"python", "python3"}
    ]
    if len(python_indices) != 1:
        raise ValueError(
            f"{launcher_path}:{line_number}: runtime selector must prefix exactly one "
            "static python manage.py command."
        )
    return python_indices[0]


def _command_prefix_assignments(
    tokens: list[str], python_index: int, launcher_path: Path, *, line_number: int
) -> dict[str, list[str]]:
    """Return the one-shot environment prefix assignments before python."""
    prefix_tokens = tokens[:python_index]
    if prefix_tokens[:1] == ["env"]:
        prefix_tokens = prefix_tokens[1:]
    if prefix_tokens[-1:] == ["exec"]:
        prefix_tokens = prefix_tokens[:-1]
    if "export" in prefix_tokens or not prefix_tokens:
        raise ValueError(
            f"{launcher_path}:{line_number}: runtime selectors must be one-shot command "
            "environment prefixes; export and persistent assignment forms are not supported."
        )

    prefix_assignments: dict[str, list[str]] = {}
    for token in prefix_tokens:
        assignment_match = _SHELL_ENV_ASSIGNMENT.fullmatch(token)
        if assignment_match is None:
            raise ValueError(
                f"{launcher_path}:{line_number}: runtime selectors must be one-shot command "
                "environment prefixes immediately before python manage.py."
            )
        prefix_assignments.setdefault(assignment_match.group("name"), []).append(
            assignment_match.group("value")
        )
    return prefix_assignments


def _validate_selector_attachment(
    *,
    launcher_path: Path,
    line_number: int,
    active_line: str,
    tokens: list[str],
    python_index: int,
    selector_index: int,
    environment_name: str,
    command: str,
    prefix_assignments: dict[str, list[str]],
) -> None:
    """Reject a selector that is not one static literal manage.py prefix."""
    if selector_index >= python_index or environment_name not in prefix_assignments:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must be an environment "
            "prefix attached to the python manage.py invocation."
        )
    if len(prefix_assignments[environment_name]) != 1:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} may be assigned only once."
        )
    literal_assignment = re.compile(
        rf"\b{re.escape(environment_name)}=(?:{re.escape(command)}|"
        rf"\"{re.escape(command)}\"|'{re.escape(command)}')(?=\s|$)"
    )
    if literal_assignment.search(active_line) is None:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must use one static "
            "literal assignment without shell concatenation."
        )
    if _STATIC_RUNTIME_COMMAND.fullmatch(command) is None:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must use a static literal "
            f"command name; unable to verify {command or '(empty)'!r}."
        )
    _validate_manage_command(
        tokens=tokens,
        python_index=python_index,
        environment_name=environment_name,
        command=command,
        launcher_path=launcher_path,
        line_number=line_number,
    )


def _validate_manage_command(
    *,
    tokens: list[str],
    python_index: int,
    environment_name: str,
    command: str,
    launcher_path: Path,
    line_number: int,
) -> None:
    """Reject a selector whose manage.py command is not the literal selector."""
    if len(tokens) <= python_index + 2 or tokens[python_index + 1] != "manage.py":
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must prefix exactly one "
            "static python manage.py command."
        )
    manage_command = tokens[python_index + 2]
    if (
        _STATIC_RUNTIME_COMMAND.fullmatch(manage_command) is None
        or manage_command != command
    ):
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name}={command} must match "
            f"the same static literal manage.py command; unable to verify {manage_command!r}."
        )


def _validate_selector_flag_rules(
    *,
    launcher_path: Path,
    line_number: int,
    environment_name: str,
    command: str,
    prefix_assignments: dict[str, list[str]],
) -> None:
    """Reject privileged and bypass flag combinations the grammar forbids."""
    if environment_name == "QUICKSCALE_PRIVILEGED_COMMAND":
        if prefix_assignments.get("RUNTIME_DATABASE_URL") != [""]:
            raise ValueError(
                f"{launcher_path}:{line_number}: {environment_name}={command} must blank "
                "RUNTIME_DATABASE_URL in the same static literal environment prefix "
                "before python manage.py."
            )
        if "QUICKSCALE_ALLOW_BYPASSRLS" in prefix_assignments:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_ALLOW_BYPASSRLS is not "
                "supported for privileged commands."
            )
    bypass_values = prefix_assignments.get("QUICKSCALE_ALLOW_BYPASSRLS")
    if bypass_values is not None and (
        environment_name != "QUICKSCALE_NON_DB_COMMAND" or bypass_values != ["1"]
    ):
        raise ValueError(
            f"{launcher_path}:{line_number}: QUICKSCALE_ALLOW_BYPASSRLS=1 is only "
            "supported with QUICKSCALE_NON_DB_COMMAND."
        )


def _parse_runtime_command_line(
    launcher_path: Path,
    *,
    line_number: int,
    active_line: str,
) -> tuple[str, str] | None:
    """Parse one selector-bearing line under the shipped one-shot grammar."""
    _reject_selector_line_continuation(
        launcher_path, line_number=line_number, active_line=active_line
    )
    tokens = _selector_line_tokens(
        launcher_path, line_number=line_number, active_line=active_line
    )
    if not tokens:
        return None

    selector_assignments = _scan_selector_assignments(
        tokens, launcher_path, line_number=line_number
    )

    has_selector_marker = _has_runtime_selector_marker(active_line)
    has_bypass_marker = "QUICKSCALE_ALLOW_BYPASSRLS" in active_line
    if not selector_assignments:
        if has_selector_marker:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND selectors must use a supported static literal "
                "assignment with no dynamically constructed variable name."
            )
        if has_bypass_marker:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_ALLOW_BYPASSRLS is only "
                "supported as a one-shot prefix for QUICKSCALE_NON_DB_COMMAND."
            )
        return None
    if len(selector_assignments) != 1:
        raise ValueError(
            f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND and "
            "QUICKSCALE_NON_DB_COMMAND static literal selectors are mutually exclusive "
            "and may appear only once."
        )

    python_index = _resolve_python_command_index(
        tokens, launcher_path, line_number=line_number
    )
    prefix_assignments = _command_prefix_assignments(
        tokens, python_index, launcher_path, line_number=line_number
    )

    selector_index, environment_name, command = selector_assignments[0]
    _validate_selector_attachment(
        launcher_path=launcher_path,
        line_number=line_number,
        active_line=active_line,
        tokens=tokens,
        python_index=python_index,
        selector_index=selector_index,
        environment_name=environment_name,
        command=command,
        prefix_assignments=prefix_assignments,
    )
    _validate_selector_flag_rules(
        launcher_path=launcher_path,
        line_number=line_number,
        environment_name=environment_name,
        command=command,
        prefix_assignments=prefix_assignments,
    )
    return environment_name, command


def _extract_launcher_runtime_commands(
    launcher_path: Path,
    *,
    known_commands: dict[str, set[str]],
    launcher_text: str | None = None,
) -> dict[str, set[str]]:
    """Extract static command-mode assignments from one effective launcher.

    Any assignment that cannot be resolved without shell evaluation blocks the
    migration.  Ignoring an indirect value would let a launcher bypass the
    production-settings allowlist that this preflight is meant to enforce.
    """
    if launcher_text is None:
        try:
            launcher_text = launcher_path.read_text()
        except OSError as exc:
            raise ValueError(
                f"Unable to read effective runtime launcher {launcher_path}: {exc}"
            ) from exc

    commands: dict[str, set[str]] = {
        "QUICKSCALE_PRIVILEGED_COMMAND": set(),
        "QUICKSCALE_NON_DB_COMMAND": set(),
    }
    if launcher_path.name == "start.sh":
        _validate_start_sh_grammar(launcher_path, launcher_text)
    elif launcher_path.name == "Dockerfile":
        _validate_dockerfile_grammar(launcher_path, launcher_text)
    if launcher_path.name == "start.sh":
        launcher_lines = _start_sh_reachable_logical_lines(launcher_path, launcher_text)
    else:
        launcher_lines = [
            (line_number, line, True, True)
            for line_number, line in _dockerfile_final_stage_physical_lines(
                launcher_path, launcher_text
            )
        ]
    for line_number, line, reachable, unconditional in launcher_lines:
        active_line = _active_launcher_line(launcher_path, line)
        if not active_line.strip():
            continue

        _validate_persistent_environment_mutation(
            launcher_path, line_number, active_line
        )

        docker_env_line = (
            launcher_path.name == "Dockerfile"
            and re.match(r"^\s*ENV\b", active_line, re.IGNORECASE) is not None
        )
        has_selector_marker = _has_runtime_selector_marker(active_line)
        has_bypass_marker = "QUICKSCALE_ALLOW_BYPASSRLS" in active_line
        if docker_env_line and (has_selector_marker or has_bypass_marker):
            raise ValueError(
                f"{launcher_path}:{line_number}: runtime command selectors are one-shot "
                "inline prefixes; persistent Docker ENV assignments are not supported."
            )
        if not (has_selector_marker or has_bypass_marker):
            _validate_unmarked_manage_command(
                launcher_path,
                line_number=line_number,
                active_line=active_line,
                known_commands=known_commands,
            )
            continue
        parsed = _parse_runtime_command_line(
            launcher_path,
            line_number=line_number,
            active_line=active_line,
        )
        if parsed is not None:
            environment_name, command = parsed
            if command not in known_commands[environment_name]:
                raise ValueError(
                    f"{launcher_path}:{line_number}: {environment_name}={command} is "
                    "not allowed by the effective production settings."
                )
            if (
                command in _UNCONDITIONAL_RUNTIME_COMMANDS[environment_name]
                and not unconditional
            ):
                raise ValueError(
                    f"{launcher_path}:{line_number}: {environment_name}={command} "
                    "must be unconditionally executable on the top-level startup path."
                )
            if reachable:
                commands[environment_name].add(command)
    return commands
