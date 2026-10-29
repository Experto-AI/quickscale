"""Shared static shell tokenization and environment-mutation checks."""

from .constants import (
    _DYNAMIC_RUNTIME_COMMAND_MARKER,
    _EXEC_SHELL_WORD,
    _RUNTIME_COMMAND_MARKER,
    _SHELL_ARITHMETIC_OPEN,
    _SHELL_ENV_ASSIGNMENT,
    _SHELL_TEST_CLOSE,
    _SHELL_TEST_OPEN,
)
import re
import shlex
from pathlib import Path


def _has_runtime_selector_marker(active_line: str) -> bool:
    """Return whether one line contains a literal or dynamically named selector."""
    return (
        _RUNTIME_COMMAND_MARKER.search(active_line) is not None
        or _DYNAMIC_RUNTIME_COMMAND_MARKER.search(active_line) is not None
    )


def _active_launcher_line(launcher_path: Path, line: str) -> str:
    """Strip one shell comment while preserving quoted ``#`` characters."""
    if line.lstrip().startswith("#"):
        return ""
    if launcher_path.name == "Dockerfile":
        return line

    quote_character: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote_character != "'":
            escaped = True
            continue
        if character in {'"', "'"}:
            if quote_character == character:
                quote_character = None
            elif quote_character is None:
                quote_character = character
            continue
        if (
            character == "#"
            and quote_character is None
            and (index == 0 or line[index - 1].isspace())
        ):
            return line[:index]
    return line


def _shell_tokens(launcher_path: Path, line_number: int, line: str) -> list[str]:
    """Tokenize one accepted launcher line without evaluating shell syntax."""
    candidate = line.rstrip()
    if candidate.endswith("\\"):
        candidate = candidate[:-1].rstrip()
    lexer = shlex.shlex(candidate, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError as exc:
        raise ValueError(
            f"{launcher_path}:{line_number}: unable to parse launcher line as static shell syntax: {exc}"
        ) from exc


def _is_shell_operator(token: str) -> bool:
    return bool(token) and all(character in ";&|()" for character in token)


def _has_dynamic_env_assignment_name(
    launcher_path: Path, line_number: int, active_line: str
) -> bool:
    """Return whether an env prefix computes an assignment name at runtime."""
    if re.search(r"(?:^|[/\s])env(?:[\s;&|()]|$)", active_line) is None:
        return False
    tokens = _shell_tokens(launcher_path, line_number, active_line)
    command_tokens: list[str] = []
    command_segments: list[list[str]] = []
    for token in tokens:
        if _is_shell_operator(token):
            if command_tokens:
                command_segments.append(command_tokens)
                command_tokens = []
            continue
        command_tokens.append(token)
    if command_tokens:
        command_segments.append(command_tokens)

    for segment in command_segments:
        for python_index, token in enumerate(segment):
            if (
                token not in {"python", "python3"}
                or python_index + 1 >= len(segment)
                or segment[python_index + 1] != "manage.py"
            ):
                continue
            env_indices = [
                index
                for index, prefix_token in enumerate(segment[:python_index])
                if Path(prefix_token).name == "env"
            ]
            if not env_indices:
                continue
            env_index = env_indices[-1]
            for prefix_token in segment[env_index + 1 : python_index]:
                if prefix_token == _EXEC_SHELL_WORD or prefix_token.startswith("-"):
                    continue
                if _SHELL_ENV_ASSIGNMENT.fullmatch(prefix_token) is not None:
                    continue
                if any(marker in prefix_token for marker in ("=", "$", "`")):
                    return True
    return False


_COMMAND_PREFIXES: frozenset[str] = frozenset(
    {"!", "{", "if", "elif", "while", "until", "then", "else", "do"}
)

_CHILD_SHELL_NAMES: frozenset[str] = frozenset({"sh", "bash", "dash", "zsh", "ksh"})


def _pending_segment(segments: list[list[str]], segment: list[str]) -> None:
    """Append a non-empty command segment to the segment list."""
    if segment:
        segments.append(segment)


def _shell_command_segments(tokens: list[str]) -> list[list[str]]:
    """Split tokens into command segments, preserving arithmetic/test spans."""
    segments: list[list[str]] = []
    segment: list[str] = []
    in_arithmetic_command = False
    in_test_command = False
    for token in tokens:
        if in_arithmetic_command:
            in_arithmetic_command = "))" not in token
            continue
        if in_test_command:
            segment.append(token)
            in_test_command = token != _SHELL_TEST_CLOSE
            continue
        if token == _SHELL_ARITHMETIC_OPEN:
            _pending_segment(segments, segment)
            segment = []
            in_arithmetic_command = True
            continue
        if token == _SHELL_TEST_OPEN:
            in_test_command = True
            segment.append(token)
            continue
        if _is_shell_operator(token):
            _pending_segment(segments, segment)
            segment = []
            continue
        segment.append(token)
    _pending_segment(segments, segment)
    return segments


def _command_start_index(command_tokens: list[str]) -> int | None:
    """Return the index where a segment's actual command starts, if any."""
    command_index = 0
    while command_index < len(command_tokens):
        token = command_tokens[command_index]
        if _SHELL_ENV_ASSIGNMENT.fullmatch(token) is not None:
            command_index += 1
            continue
        if token in {"builtin", "command"}:
            command_index += 1
            continue
        if token in _COMMAND_PREFIXES:
            command_index += 1
            continue
        break
    if command_index >= len(command_tokens):
        return None
    return command_index


def _is_exported_declaration(arguments: list[str]) -> bool:
    """Return whether declaration arguments request export (``-x``)."""
    return any(
        argument.startswith("-") and "x" in argument[1:] for argument in arguments
    )


def _is_child_shell_command(command_name: str, arguments: list[str]) -> bool:
    """Return whether the command runs an opaque child shell with ``-c``."""
    return command_name in _CHILD_SHELL_NAMES and any(
        argument.startswith("-") and "c" in argument[1:] for argument in arguments
    )


def _is_allexport_command(command: str, arguments: list[str]) -> bool:
    """Return whether a ``set`` command requests allexport behavior."""
    return command == "set" and (
        any(argument.startswith("-") and "a" in argument[1:] for argument in arguments)
        or any(
            argument == "allexport" and index > 0 and arguments[index - 1] == "-o"
            for index, argument in enumerate(arguments)
        )
    )


def _reject_persistent_command(
    command: str,
    arguments: list[str],
    launcher_path: Path,
    *,
    line_number: int,
    shell_function_candidate: re.Match[str] | None,
) -> bool:
    """Reject one persistent-mutation command; True when it is an export."""
    command_name = Path(command).name
    if command_name in {"alias", "unalias", "shopt"}:
        raise ValueError(
            f"{launcher_path}:{line_number}: {command_name} is an unsupported "
            "persistent shell behavior; runtime launchers must use directly "
            "inspectable static commands and static literal "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors."
        )
    if _is_child_shell_command(command_name, arguments):
        raise ValueError(
            f"{launcher_path}:{line_number}: opaque child-shell execution through "
            f"{command_name} -c is unsupported; runtime launchers must expose "
            "commands directly with static literal "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors "
            "for compatibility validation."
        )
    if shell_function_candidate is not None:
        raise ValueError(
            f"{launcher_path}:{line_number}: shell function definitions are "
            "unsupported because they can hide persistent environment mutation; "
            "runtime selectors must remain static literals."
        )
    if "$" in command or "`" in command:
        raise ValueError(
            f"{launcher_path}:{line_number}: dynamic shell command indirection is "
            "unsupported because it can hide persistent environment mutation; "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors "
            "and runtime launcher commands must use static literals."
        )
    if command in {"declare", "local", "typeset"} and _is_exported_declaration(
        arguments
    ):
        raise ValueError(
            f"{launcher_path}:{line_number}: exported shell declarations are an "
            "unsupported persistent environment mutation; "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors "
            "must use static literal one-shot prefixes."
        )
    if _is_allexport_command(command, arguments):
        raise ValueError(
            f"{launcher_path}:{line_number}: shell allexport is an unsupported "
            "persistent environment mutation; QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND selectors must use static literal one-shot "
            "prefixes."
        )
    if command in {".", "eval", "source"}:
        raise ValueError(
            f"{launcher_path}:{line_number}: {command} is an unsupported indirect "
            "environment mutation path; QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND selectors must use static literal one-shot "
            "prefixes."
        )
    return command == "export"


def _validate_export_names(
    arguments: list[str], launcher_path: Path, *, line_number: int
) -> None:
    """Reject a persistent export whose name is not a static literal."""
    for export_token in arguments:
        if export_token.startswith("-"):
            continue
        assignment_match = _SHELL_ENV_ASSIGNMENT.fullmatch(export_token)
        if assignment_match is not None or re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", export_token
        ):
            continue
        raise ValueError(
            f"{launcher_path}:{line_number}: persistent export names must be "
            "static literals; a dynamically constructed export name can hide "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND."
        )


def _validate_persistent_environment_mutation(
    launcher_path: Path, line_number: int, active_line: str
) -> None:
    """Reject persistent shell environment changes outside the static grammar."""
    command_boundary = r"(?:^|[;&|()])\s*(?:(?:builtin|command)\s+)?"
    export_candidate = re.search(r"(?:^|[\s;&|()])export(?:\s|$)", active_line)
    exported_declaration_candidate = re.search(
        rf"{command_boundary}(?:declare|local|typeset)\b[^;&|()]*\s-[A-Za-z]*x",
        active_line,
    )
    allexport_candidate = re.search(
        rf"{command_boundary}set\b[^;&|()]*(?:\s-[A-Za-z]*a|\s-o\s+allexport)",
        active_line,
    )
    indirect_candidate = re.search(
        rf"{command_boundary}(?:\.|eval|source)(?:\s|$)", active_line
    )
    opaque_shell_candidate = re.search(
        r"(?:^|[\s;&|()])"
        r"(?:alias|unalias|shopt|(?:[^\s;&|()]+/)?(?:sh|bash|dash|zsh|ksh))"
        r"(?:\s|$)",
        active_line,
    )
    shell_function_candidate = re.search(
        r"(?:^|[;&|()]|\bfunction\s+)\s*[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\)\s*\{",
        active_line,
    )
    dynamic_command_boundary = (
        r"(?:^|[;&|]|(?<!\()\((?!\())\s*"
        r"(?:(?:if|elif|while|until|then|else|do|!)\s+)*"
        r"(?:(?:builtin|command)\s+)?"
    )
    dynamic_command_candidate = re.search(
        rf"{dynamic_command_boundary}"
        r"(?:[A-Za-z_][A-Za-z0-9_]*=[^\s;&|()]+\s+)*"
        r"(?:[\"']?\$|`)",
        active_line,
    )
    if not any(
        (
            export_candidate,
            exported_declaration_candidate,
            allexport_candidate,
            indirect_candidate,
            opaque_shell_candidate,
            shell_function_candidate,
            dynamic_command_candidate,
        )
    ):
        return

    tokens = _shell_tokens(launcher_path, line_number, active_line)
    for command_tokens in _shell_command_segments(tokens):
        command_index = _command_start_index(command_tokens)
        if command_index is None:
            continue
        command = command_tokens[command_index]
        arguments = command_tokens[command_index + 1 :]
        is_export = _reject_persistent_command(
            command,
            arguments,
            launcher_path,
            line_number=line_number,
            shell_function_candidate=shell_function_candidate,
        )
        if not is_export or _has_runtime_selector_marker(active_line):
            continue
        _validate_export_names(arguments, launcher_path, line_number=line_number)
