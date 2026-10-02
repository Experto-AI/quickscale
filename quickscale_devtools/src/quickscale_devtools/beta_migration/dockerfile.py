"""Static grammar validation for the generated Dockerfile."""

from .constants import (
    _DOCKER_CONTROL_ONLY,
    _DOCKER_CONTROL_PREFIXES,
    _DOCKER_GENERATED_KEY_PAYLOAD,
    _DOCKER_RUN_COMMANDS,
    _SHELL_ENV_ASSIGNMENT,
)
from .settings_facade import _static_string_expression
from .shell import (
    _is_shell_operator,
    _shell_tokens,
    _validate_persistent_environment_mutation,
)
from .start_sh import _validate_start_sh_python_command
import ast
import re
from pathlib import Path


def _dockerfile_logical_instructions(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Join Dockerfile continuations into statically inspectable instructions."""
    instructions: list[tuple[int, str]] = []
    pending: list[str] = []
    start_line = 1
    for line_number, raw_line in enumerate(launcher_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        if not pending:
            start_line = line_number
        continued = stripped.endswith("\\")
        pending.append(stripped[:-1].rstrip() if continued else stripped)
        if continued:
            continue
        instruction = " ".join(part for part in pending if part)
        pending = []
        if instruction:
            instructions.append((start_line, instruction))
    if pending:
        raise ValueError(
            f"{launcher_path}:{start_line}: unterminated Dockerfile continuation is "
            "outside the static runtime grammar."
        )
    return instructions


def _dockerfile_final_stage_instructions(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Return instructions that contribute directly to the effective final stage."""
    instructions = _dockerfile_logical_instructions(launcher_path, launcher_text)
    final_stage_start = max(
        (
            index
            for index, (_line_number, instruction) in enumerate(instructions)
            if instruction.partition(" ")[0].upper() == "FROM"
        ),
        default=-1,
    )
    if final_stage_start < 0:
        return []
    return instructions[final_stage_start + 1 :]


def _dockerfile_final_stage_physical_lines(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Return physical lines belonging to the effective final Docker stage."""
    final_from_line = max(
        (
            line_number
            for line_number, instruction in _dockerfile_logical_instructions(
                launcher_path, launcher_text
            )
            if instruction.partition(" ")[0].upper() == "FROM"
        ),
        default=-1,
    )
    if final_from_line < 0:
        return []
    return [
        (line_number, line)
        for line_number, line in enumerate(launcher_text.splitlines(), start=1)
        if line_number > final_from_line
    ]


def _strip_validated_docker_python_substitutions(
    launcher_path: Path, line_number: int, payload: str
) -> str:
    """Replace only generated, read-only Docker command substitutions."""
    pattern = re.compile(
        r"\$\(\s*python3?\s+-c\s+(?P<quote>['\"])(?P<code>.*?)(?P=quote)\s*\)"
    )
    matches = list(pattern.finditer(payload))
    validated = payload
    expected_ast = ast.dump(
        ast.parse(_DOCKER_GENERATED_KEY_PAYLOAD), include_attributes=False
    )
    for match in reversed(matches):
        actual_ast = ast.dump(
            ast.parse(match.group("code").strip()), include_attributes=False
        )
        if actual_ast != expected_ast:
            raise ValueError(
                f"{launcher_path}:{line_number}: Dockerfile Python command "
                "substitution is outside the generated SECRET_KEY grammar."
            )
        validated = (
            validated[: match.start()] + "QS_SECRET_KEY" + validated[match.end() :]
        )

    allowed_read_only_substitutions = {
        "date -u +%H:%M:%SZ",
        "poetry --version",
        "ls -lh /app/staticfiles | wc -l",
    }
    generic_pattern = re.compile(r"\$\((?P<command>[^()]*)\)")
    generic_matches = list(generic_pattern.finditer(validated))
    for match in reversed(generic_matches):
        if match.group("command").strip() not in allowed_read_only_substitutions:
            raise ValueError(
                f"{launcher_path}:{line_number}: Dockerfile command substitution "
                "is outside the generated read-only runtime grammar."
            )
        validated = (
            validated[: match.start()] + "QS_SUBSTITUTION" + validated[match.end() :]
        )
    if "$(" in validated:
        raise ValueError(
            f"{launcher_path}:{line_number}: nested Dockerfile command substitution is "
            "outside the generated static runtime grammar."
        )
    return validated


def _validate_docker_healthcheck_payload(
    launcher_path: Path, line_number: int, payload: str
) -> None:
    """Accept only generated read-only Python healthcheck payload capabilities."""
    try:
        tree = ast.parse(payload.strip(), filename=f"{launcher_path}:{line_number}")
    except SyntaxError as exc:
        raise ValueError(
            f"{launcher_path}:{line_number}: Docker healthcheck Python payload must "
            f"parse statically: {exc}"
        ) from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name not in {"os", "urllib.request"} for alias in node.names):
                raise ValueError(
                    f"{launcher_path}:{line_number}: Docker healthcheck import is "
                    "outside the generated static runtime grammar."
                )
        elif isinstance(node, ast.ImportFrom):
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker healthcheck from-import is "
                "outside the generated static runtime grammar."
            )
        elif (
            isinstance(node, ast.expr)
            and _static_string_expression(node) == "manage.py"
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker healthcheck constructs a "
                "manage.py operand outside a runtime selector."
            )
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
            allowed = call_name == "print"
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
            allowed = call_name in {"get", "urlopen"}
        else:
            call_name = ast.dump(node.func, include_attributes=False)
            allowed = False
        if not allowed:
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker healthcheck Python call "
                f"{call_name!r} is outside the generated static runtime grammar."
            )


def _docker_segment_command_indexes(segment: list[str]) -> list[int]:
    """Return executable command positions in one static shell segment."""
    command_index = 0
    while (
        command_index < len(segment)
        and segment[command_index] in _DOCKER_CONTROL_PREFIXES
    ):
        command_index += 1
    if command_index >= len(segment):
        return []
    if segment[command_index] in _DOCKER_CONTROL_ONLY:
        return []
    if segment[command_index] == "for":
        return []
    if segment[command_index] == "if":
        command_index += 1
    while command_index < len(segment) and _SHELL_ENV_ASSIGNMENT.fullmatch(
        segment[command_index]
    ):
        command_index += 1
    if command_index >= len(segment):
        return []

    command_indexes = [command_index]
    if Path(segment[command_index]).name != "timeout":
        return command_indexes
    nested_index = command_index + 1
    while nested_index < len(segment) and segment[nested_index].startswith("-"):
        nested_index += 1
    if nested_index < len(segment):
        nested_index += 1
    if nested_index < len(segment):
        command_indexes.append(nested_index)
    return command_indexes


def _validate_dockerfile_run(
    launcher_path: Path, line_number: int, payload: str
) -> None:
    """Validate every Python execution in one shell-form RUN instruction."""
    if "`" in payload:
        raise ValueError(
            f"{launcher_path}:{line_number}: Docker RUN backtick execution is outside "
            "the generated static runtime grammar."
        )
    if payload.lstrip().startswith("["):
        raise ValueError(
            f"{launcher_path}:{line_number}: exec-form Docker RUN is outside the "
            "generated static runtime grammar."
        )
    normalized = _strip_validated_docker_python_substitutions(
        launcher_path, line_number, payload
    )
    _validate_persistent_environment_mutation(launcher_path, line_number, normalized)
    tokens = _shell_tokens(launcher_path, line_number, normalized)
    segment_start = 0
    for index in range(len(tokens) + 1):
        at_boundary = index == len(tokens) or _is_shell_operator(tokens[index])
        if not at_boundary:
            continue
        segment = tokens[segment_start:index]
        segment_start = index + 1
        for command_index in _docker_segment_command_indexes(segment):
            command_name = Path(segment[command_index]).name
            if command_name not in _DOCKER_RUN_COMMANDS:
                raise ValueError(
                    f"{launcher_path}:{line_number}: Docker RUN command "
                    f"{segment[command_index]!r} is outside the generated static "
                    "runtime grammar."
                )
            if command_name in {"python", "python3"}:
                _validate_start_sh_python_command(
                    launcher_path, line_number, segment, command_index
                )


def _validate_dockerfile_grammar(launcher_path: Path, launcher_text: str) -> None:
    """Apply a fail-closed grammar to executable generated Docker instructions."""
    for line_number, instruction in _dockerfile_logical_instructions(
        launcher_path, launcher_text
    ):
        directive, _, payload = instruction.partition(" ")
        directive = directive.upper()
        if directive in {"ENTRYPOINT", "ONBUILD", "SHELL"}:
            raise ValueError(
                f"{launcher_path}:{line_number}: Dockerfile {directive} is outside the "
                "generated static runtime grammar."
            )
        if directive == "RUN":
            _validate_dockerfile_run(launcher_path, line_number, payload)
            continue
        if directive != "HEALTHCHECK":
            continue
        tokens = _shell_tokens(launcher_path, line_number, payload)
        try:
            command_index = tokens.index("CMD") + 1
        except ValueError as exc:
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker HEALTHCHECK must use one "
                "static CMD python -c payload."
            ) from exc
        arguments = tokens[command_index:]
        if (
            len(arguments) != 3
            or Path(arguments[0]).name not in {"python", "python3"}
            or arguments[1] != "-c"
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker HEALTHCHECK must use one "
                "static CMD python -c payload."
            )
        _validate_docker_healthcheck_payload(launcher_path, line_number, arguments[2])
