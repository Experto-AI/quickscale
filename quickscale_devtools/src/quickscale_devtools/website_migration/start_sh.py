"""Static grammar validation for the generated start.sh launcher."""

from .constants import (
    _EXEC_SHELL_WORD,
    _SHELL_ENV_ASSIGNMENT,
    _SHELL_TEST_CLOSE,
    _SHELL_TEST_OPEN,
    _START_SH_COMMANDS,
    _START_SH_CONTROL_MARKERS,
    _START_SH_HEREDOC_CALL_ATTRIBUTES,
    _START_SH_HEREDOC_CALL_NAMES,
    _START_SH_HEREDOC_FROM_IMPORTS,
    _START_SH_HEREDOC_IMPORTS,
    _START_SH_INLINE_CALL_ATTRIBUTES,
    _START_SH_INLINE_CALL_NAMES,
    _START_SH_INLINE_FROM_IMPORTS,
    _START_SH_INLINE_IMPORTS,
    _STATIC_MANAGE_COMMAND,
)
from .settings_facade import _static_string_expression
from .shell import (
    _active_launcher_line,
    _has_dynamic_env_assignment_name,
    _is_shell_operator,
    _shell_tokens,
)
import ast
import re
from pathlib import Path


def _validate_unmarked_manage_command(
    launcher_path: Path,
    *,
    line_number: int,
    active_line: str,
    known_commands: dict[str, set[str]],
) -> None:
    """Reject required or unresolved management commands without a selector."""
    if "manage.py" not in active_line:
        return
    command_matches = list(_STATIC_MANAGE_COMMAND.finditer(active_line))
    manage_invocation_count = len(re.findall(r"\bmanage\.py\b", active_line))
    if not command_matches or len(command_matches) != manage_invocation_count:
        raise ValueError(
            f"{launcher_path}:{line_number}: unable to classify a dynamic manage.py "
            "invocation without a static runtime selector."
        )
    if _has_dynamic_env_assignment_name(launcher_path, line_number, active_line):
        raise ValueError(
            f"{launcher_path}:{line_number}: unable to verify a static literal "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selector "
            "because the manage.py environment prefix uses shell construction."
        )

    selector_commands = set().union(*known_commands.values())
    for command_match in command_matches:
        command = command_match.group(1)
        if command in selector_commands:
            raise ValueError(
                f"{launcher_path}:{line_number}: python manage.py {command} must use "
                "its required one-shot QUICKSCALE_*_COMMAND environment prefix."
            )


def _quote_state_after_piece(
    piece: str, quote_character: str | None, escaped: bool
) -> tuple[str | None, bool]:
    """Return the quote and escape state after scanning one shell piece."""
    for character in piece:
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote_character != "'":
            escaped = True
            continue
        if character not in {'"', "'"}:
            continue
        if quote_character == character:
            quote_character = None
        elif quote_character is None:
            quote_character = character
    return quote_character, escaped


def _heredoc_delimiter_of(logical_line: str) -> str | None:
    """Return the heredoc delimiter a complete statement opens, if any."""
    heredoc_match = re.search(
        r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$",
        logical_line,
    )
    if heredoc_match is not None:
        return heredoc_match.group(1)
    return None


def _raise_unterminated_start_sh(
    launcher_path: Path,
    *,
    start_line: int,
    pending: list[str],
    quote_character: str | None,
    heredoc_delimiter: str | None,
) -> None:
    """Raise when the launcher ends inside a heredoc or open shell statement."""
    if heredoc_delimiter is not None:
        raise ValueError(
            f"{launcher_path}: unterminated heredoc is outside the static start.sh grammar."
        )
    if pending or quote_character is not None:
        raise ValueError(
            f"{launcher_path}:{start_line}: unterminated shell statement is outside "
            "the static start.sh grammar."
        )


def _start_sh_logical_lines(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Return complete shell statements while excluding proved heredoc bodies."""
    logical_lines: list[tuple[int, str]] = []
    pending: list[str] = []
    start_line = 1
    quote_character: str | None = None
    escaped = False
    heredoc_delimiter: str | None = None

    for line_number, raw_line in enumerate(launcher_text.splitlines(), start=1):
        if heredoc_delimiter is not None:
            if raw_line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue

        active_line = _active_launcher_line(launcher_path, raw_line).rstrip()
        if not active_line.strip() and not pending:
            continue
        if not pending:
            start_line = line_number

        continued = active_line.endswith("\\") and quote_character != "'"
        piece = active_line[:-1].rstrip() if continued else active_line
        pending.append(piece)
        quote_character, escaped = _quote_state_after_piece(
            piece, quote_character, escaped
        )

        if quote_character is not None or continued:
            continue

        logical_line = "\n".join(part for part in pending if part).strip()
        pending = []
        if not logical_line:
            continue
        logical_lines.append((start_line, logical_line))
        heredoc_delimiter = _heredoc_delimiter_of(logical_line)

    _raise_unterminated_start_sh(
        launcher_path,
        start_line=start_line,
        pending=pending,
        quote_character=quote_character,
        heredoc_delimiter=heredoc_delimiter,
    )
    return logical_lines


def _validate_start_sh_command_substitutions(
    launcher_path: Path, line_number: int, logical_line: str
) -> None:
    """Allow only the generated, read-only ``$(which python)`` substitution."""
    cursor = 0
    while True:
        start = logical_line.find("$(", cursor)
        if start < 0:
            return
        if logical_line.startswith("$((", start):
            raise ValueError(
                f"{launcher_path}:{line_number}: shell arithmetic expansion is outside "
                "the static literal start.sh grammar for QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND validation."
            )
        depth = 1
        index = start + 2
        while index < len(logical_line) and depth:
            if logical_line.startswith("$(", index):
                depth += 1
                index += 2
                continue
            if logical_line[index] == ")":
                depth -= 1
            index += 1
        if depth:
            raise ValueError(
                f"{launcher_path}:{line_number}: unterminated command substitution is "
                "outside the static literal start.sh grammar."
            )
        command = logical_line[start + 2 : index - 1].strip()
        if command != "which python":
            raise ValueError(
                f"{launcher_path}:{line_number}: command substitution {command!r} is "
                "outside the static literal start.sh grammar for "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation."
            )
        cursor = index


def _start_sh_segments(
    launcher_path: Path, line_number: int, logical_line: str
) -> list[list[str]]:
    """Split one logical statement into executable segments."""
    normalized = re.sub(r"(?<!\S)(?:[12])?>&[12](?=\s|$)", "QS_REDIRECT", logical_line)
    tokens = _shell_tokens(launcher_path, line_number, normalized)
    segments: list[list[str]] = []
    segment: list[str] = []
    in_test_command = False
    for token in tokens:
        if token == _SHELL_TEST_OPEN:
            in_test_command = True
            segment.append(token)
            continue
        if in_test_command:
            segment.append(token)
            if token == _SHELL_TEST_CLOSE:
                in_test_command = False
            continue
        if _is_shell_operator(token):
            if any(character in token for character in "()") or token not in {
                ";",
                "&&",
                "||",
                "|",
            }:
                raise ValueError(
                    f"{launcher_path}:{line_number}: shell operator {token!r} is "
                    "outside the static literal start.sh grammar for "
                    "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation."
                )
            if segment:
                segments.append(segment)
                segment = []
            continue
        segment.append(token)
    if in_test_command:
        raise ValueError(
            f"{launcher_path}:{line_number}: unterminated [[ ]] condition is outside "
            "the static literal start.sh grammar."
        )
    if segment:
        segments.append(segment)
    return segments


def _validate_start_sh_python_import(
    launcher_path: Path,
    line_number: int,
    node: ast.Import | ast.ImportFrom,
    *,
    heredoc: bool,
) -> None:
    """Accept only imports used by the generated launcher's static payloads."""
    if isinstance(node, ast.Import):
        allowed_imports = (
            _START_SH_HEREDOC_IMPORTS if heredoc else _START_SH_INLINE_IMPORTS
        )
        rejected = [
            alias.name for alias in node.names if alias.name not in allowed_imports
        ]
    else:
        module_name = node.module or ""
        allowed_from_imports = (
            _START_SH_HEREDOC_FROM_IMPORTS if heredoc else _START_SH_INLINE_FROM_IMPORTS
        )
        allowed_names = allowed_from_imports.get(module_name)
        if not heredoc and module_name.endswith(".wsgi"):
            allowed_names = frozenset({"application"})
        rejected = (
            [f"{module_name}.{alias.name}" for alias in node.names]
            if allowed_names is None
            else [
                f"{module_name}.{alias.name}"
                for alias in node.names
                if alias.name not in allowed_names
            ]
        )
    if rejected:
        raise ValueError(
            f"{launcher_path}:{line_number}: embedded Python import "
            f"{', '.join(rejected)!r} is outside the generated static payload "
            "grammar for QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND validation."
        )


def _validate_start_sh_python_payload(
    launcher_path: Path,
    line_number: int,
    payload: str,
    *,
    heredoc: bool,
) -> None:
    """Reject Python payloads that can hide a management-command process."""
    try:
        tree = ast.parse(payload.strip(), filename=f"{launcher_path}:{line_number}")
    except SyntaxError as exc:
        raise ValueError(
            f"{launcher_path}:{line_number}: embedded Python must parse statically; "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation "
            f"cannot inspect the payload: {exc}"
        ) from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _validate_start_sh_python_import(
                launcher_path, line_number, node, heredoc=heredoc
            )

    allowed_call_names = (
        _START_SH_HEREDOC_CALL_NAMES if heredoc else _START_SH_INLINE_CALL_NAMES
    )
    allowed_call_attributes = (
        _START_SH_HEREDOC_CALL_ATTRIBUTES
        if heredoc
        else _START_SH_INLINE_CALL_ATTRIBUTES
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.expr)
            and _static_string_expression(node) == "manage.py"
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: embedded Python constructs a manage.py "
                "operand outside a directly inspectable static literal "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND prefix."
            )
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
            allowed = call_name in allowed_call_names
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
            allowed = call_name in allowed_call_attributes
        else:
            call_name = ast.dump(node.func, include_attributes=False)
            allowed = False
        if not allowed:
            raise ValueError(
                f"{launcher_path}:{line_number}: embedded Python call {call_name!r} "
                "is outside the generated static payload grammar for "
                "QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND validation."
            )


def _validate_start_sh_python_heredocs(launcher_path: Path, launcher_text: str) -> None:
    """Validate every executable Python heredoc body before it is skipped as shell."""
    lines = launcher_text.splitlines()
    index = 0
    while index < len(lines):
        line_number = index + 1
        active_line = _active_launcher_line(launcher_path, lines[index]).rstrip()
        delimiter_match = re.search(
            r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$",
            active_line,
        )
        python_match = re.search(
            r"(?:^|\s)(?:[^\s;&|()]+/)?python3?(?:\s|$)", active_line
        )
        if delimiter_match is None or python_match is None:
            index += 1
            continue

        delimiter = delimiter_match.group(1)
        payload_start = index + 1
        payload_end = payload_start
        while payload_end < len(lines) and lines[payload_end].strip() != delimiter:
            payload_end += 1
        if payload_end >= len(lines):
            raise ValueError(
                f"{launcher_path}:{line_number}: unterminated Python heredoc is "
                "outside the static literal start.sh grammar."
            )
        _validate_start_sh_python_payload(
            launcher_path,
            line_number,
            "\n".join(lines[payload_start:payload_end]),
            heredoc=True,
        )
        index = payload_end + 1


def _validate_start_sh_python_command(
    launcher_path: Path,
    line_number: int,
    tokens: list[str],
    command_index: int,
) -> None:
    """Require a directly inspectable Python execution mode in start.sh."""
    arguments = tokens[command_index + 1 :]
    if arguments == ["--version"]:
        return
    if arguments[:1] == ["-c"] and len(arguments) == 2:
        _validate_start_sh_python_payload(
            launcher_path, line_number, arguments[1], heredoc=False
        )
        return
    if (
        arguments[:1] == ["-"]
        and len(arguments) == 2
        and re.fullmatch(r"<<-?[A-Za-z_][A-Za-z0-9_]*", arguments[1])
    ):
        return
    if arguments[:1] == ["manage.py"]:
        if any("<" in argument or ">" in argument for argument in arguments):
            raise ValueError(
                f"{launcher_path}:{line_number}: python manage.py input redirection "
                "is outside the directly inspectable static literal start.sh grammar."
            )
        if arguments[1:2] == ["shell"] and "-c" not in arguments:
            raise ValueError(
                f"{launcher_path}:{line_number}: python manage.py shell requires one "
                "statically validated -c payload."
            )
        if "-c" in arguments:
            code_index = arguments.index("-c") + 1
            if code_index != len(arguments) - 1:
                raise ValueError(
                    f"{launcher_path}:{line_number}: python manage.py -c requires a "
                    "single trailing static literal payload."
                )
            _validate_start_sh_python_payload(
                launcher_path, line_number, arguments[code_index], heredoc=False
            )
        return
    rendered_operand = arguments[0] if arguments else "(missing)"
    raise ValueError(
        f"{launcher_path}:{line_number}: Python script operand {rendered_operand!r} is "
        "outside the directly inspectable static literal start.sh grammar for "
        "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation."
    )


def _validate_start_sh_if_clause(
    launcher_path: Path, line_number: int, tokens: list[str]
) -> None:
    """Reject an if/elif clause that is not one static ``[[ ]]`` condition."""
    if len(tokens) < 3 or tokens[1] != "[[" or tokens[-1] != "]]":
        raise ValueError(
            f"{launcher_path}:{line_number}: {tokens[0]} must use one static [[ ]] "
            "condition in the start.sh grammar."
        )


def _validate_start_sh_for_clause(
    launcher_path: Path, line_number: int, tokens: list[str]
) -> None:
    """Reject for-loop syntax outside the static start.sh grammar."""
    if (
        len(tokens) < 4
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tokens[1]) is None
        or tokens[2] != "in"
    ):
        raise ValueError(
            f"{launcher_path}:{line_number}: for-loop syntax is outside the "
            "static literal start.sh grammar."
        )


def _validate_start_sh_prefix_segment(
    launcher_path: Path, line_number: int, tokens: list[str]
) -> bool:
    """Validate an opening/control segment; True when it is fully handled."""
    if tokens[0] in {"if", "elif"}:
        _validate_start_sh_if_clause(launcher_path, line_number, tokens)
        return True
    if tokens[0] == "for":
        _validate_start_sh_for_clause(launcher_path, line_number, tokens)
        return True
    if tokens[0] in _START_SH_CONTROL_MARKERS:
        marker = tokens.pop(0)
        if marker in {"done", "fi"} and tokens:
            raise ValueError(
                f"{launcher_path}:{line_number}: commands after {marker} are outside "
                "the static literal start.sh grammar."
            )
        if tokens:
            _validate_start_sh_segment(launcher_path, line_number, tokens)
        return True
    if tokens[0] == "[[":
        if tokens[-1] != "]]":
            raise ValueError(
                f"{launcher_path}:{line_number}: unterminated static [[ ]] condition."
            )
        return True
    return False


def _start_sh_leading_command_index(tokens: list[str]) -> int:
    """Skip leading environment assignments; return len(tokens) when none remain."""
    command_index = 0
    while command_index < len(tokens):
        if _SHELL_ENV_ASSIGNMENT.fullmatch(tokens[command_index]) is None:
            break
        command_index += 1
    return command_index


def _start_sh_executable_index(tokens: list[str], command_index: int) -> int | None:
    """Skip an exec/env prefix; None when only the prefix remains."""
    if tokens[command_index] == "exec":
        command_index += 1
    if command_index < len(tokens) and Path(tokens[command_index]).name == "env":
        command_index += 1
        while command_index < len(tokens):
            token = tokens[command_index]
            if token.startswith("-") or _SHELL_ENV_ASSIGNMENT.fullmatch(token):
                command_index += 1
                continue
            break
    if command_index >= len(tokens):
        return None
    return command_index


def _validate_start_sh_segment(
    launcher_path: Path, line_number: int, tokens: list[str]
) -> None:
    """Validate one executable segment against the positive command grammar."""
    if not tokens:
        return
    if _validate_start_sh_prefix_segment(launcher_path, line_number, tokens):
        return

    command_index = _start_sh_leading_command_index(tokens)
    if command_index >= len(tokens):
        return
    executable_index = _start_sh_executable_index(tokens, command_index)
    if executable_index is None:
        raise ValueError(
            f"{launcher_path}:{line_number}: incomplete command prefix is outside the "
            "static literal start.sh grammar."
        )

    command = tokens[executable_index]
    command_name = Path(command).name
    if "$" in command or "`" in command or command_name not in _START_SH_COMMANDS:
        raise ValueError(
            f"{launcher_path}:{line_number}: command {command!r} is outside the static "
            "literal start.sh grammar; QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND selectors and executable command positions "
            "must be directly inspectable."
        )
    if command_name in {"python", "python3"}:
        _validate_start_sh_python_command(
            launcher_path, line_number, tokens, executable_index
        )


def _validate_start_sh_grammar(launcher_path: Path, launcher_text: str) -> None:
    """Validate the complete effective start.sh with a positive shell grammar."""
    _validate_start_sh_python_heredocs(launcher_path, launcher_text)
    for line_number, logical_line in _start_sh_logical_lines(
        launcher_path, launcher_text
    ):
        if "`" in logical_line:
            raise ValueError(
                f"{launcher_path}:{line_number}: backtick execution is outside the "
                "static literal start.sh grammar."
            )
        _validate_start_sh_command_substitutions(
            launcher_path, line_number, logical_line
        )
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\([^;&|`$]*\)", logical_line):
            continue
        if re.fullmatch(
            r"\(\(\s*[A-Za-z_][A-Za-z0-9_]*\s*(?:\+=|-=|\+\+|--)\s*\d*\s*\)\)"
            r"(?:\s*\|\|\s*true)?",
            logical_line,
        ):
            continue
        for segment in _start_sh_segments(launcher_path, line_number, logical_line):
            _validate_start_sh_segment(launcher_path, line_number, segment)


def _start_sh_line_is_unconditional_terminator(
    launcher_path: Path, line_number: int, logical_line: str
) -> bool:
    """Return whether one top-level line unconditionally replaces/exits the shell."""
    tokens = _shell_tokens(launcher_path, line_number, logical_line)
    if not tokens:
        return False
    if any(_is_shell_operator(token) for token in tokens):
        if any(
            token == _EXEC_SHELL_WORD or Path(token).name == "exit" for token in tokens
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: compound top-level exit/exec is "
                "outside the static startup reachability grammar."
            )
        return False
    command_index = 0
    while command_index < len(tokens) and _SHELL_ENV_ASSIGNMENT.fullmatch(
        tokens[command_index]
    ):
        command_index += 1
    if command_index < len(tokens) and Path(tokens[command_index]).name == "env":
        command_index += 1
        while command_index < len(tokens) and (
            tokens[command_index].startswith("-")
            or _SHELL_ENV_ASSIGNMENT.fullmatch(tokens[command_index]) is not None
        ):
            command_index += 1
    if command_index >= len(tokens):
        return False
    return tokens[command_index] == "exec" or Path(tokens[command_index]).name == "exit"


def _start_sh_set_enables_errexit(arguments: list[str]) -> bool:
    """Return whether a ``set`` argument list enables errexit."""
    return arguments == ["-o", "errexit"] or any(
        option.startswith("-") and "e" in option[1:] for option in arguments
    )


def _start_sh_set_disables_errexit(arguments: list[str]) -> bool:
    """Return whether a ``set`` argument list disables errexit."""
    return arguments == ["+o", "errexit"] or any(
        option.startswith("+") and "e" in option[1:] for option in arguments
    )


def _start_sh_unconditional_effect(
    launcher_path: Path, line_number: int, segment: list[str], *, errexit: bool
) -> bool | None:
    """Return the new errexit state, or None when the segment does not change it."""
    if segment[0] == "set":
        if _start_sh_set_enables_errexit(segment[1:]):
            return True
        if _start_sh_set_disables_errexit(segment[1:]):
            return False
        return None
    if errexit and Path(segment[0]).name == "false":
        raise ValueError(
            f"{launcher_path}:{line_number}: top-level false under active "
            "set -e terminates before required startup commands."
        )
    return None


def _start_sh_segment_errexit(
    launcher_path: Path,
    line_number: int,
    segments: list[list[str]],
    *,
    unconditional: bool,
    errexit: bool,
) -> bool:
    """Return the errexit state after one reachable, top-level annotation."""
    if not unconditional or len(segments) != 1 or not segments[0]:
        return errexit
    updated = _start_sh_unconditional_effect(
        launcher_path, line_number, segments[0], errexit=errexit
    )
    return errexit if updated is None else updated


def _start_sh_reachable_logical_lines(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str, bool, bool]]:
    """Annotate reachable lines and whether they are on the top-level path."""
    annotated: list[tuple[int, str, bool, bool]] = []
    control_depth = 0
    terminated = False
    errexit = False
    for line_number, logical_line in _start_sh_logical_lines(
        launcher_path, launcher_text
    ):
        try:
            segments = _start_sh_segments(launcher_path, line_number, logical_line)
        except ValueError:
            # The positive grammar already validated special generated forms such
            # as array assignments and arithmetic commands before reachability is
            # calculated. They neither open control blocks nor terminate the shell.
            segments = []
        first_tokens = [segment[0] for segment in segments if segment]
        closes = sum(token in {"done", "fi"} for token in first_tokens)
        opens = sum(token in {"for", "if", "until", "while"} for token in first_tokens)
        effective_depth = max(0, control_depth - closes)
        reachable = not terminated
        unconditional = reachable and effective_depth == 0
        annotated.append((line_number, logical_line, reachable, unconditional))
        errexit = _start_sh_segment_errexit(
            launcher_path,
            line_number,
            segments,
            unconditional=unconditional,
            errexit=errexit,
        )
        if (
            reachable
            and effective_depth == 0
            and segments
            and _start_sh_line_is_unconditional_terminator(
                launcher_path, line_number, logical_line
            )
        ):
            terminated = True
        control_depth = max(0, control_depth + opens - closes)
    return annotated
