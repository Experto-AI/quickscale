"""Static analysis of the versioned runtime settings facade."""

from .constants import _REQUIRED_RUNTIME_COMMANDS
from dataclasses import dataclass
from pathlib import Path
from ..handoff_prompt import _write_text_atomically
import ast


def _static_string_expression(node: ast.expr) -> str | None:
    """Resolve a statically constructed string without executing settings code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string_expression(node.left)
        right = _static_string_expression(node.right)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if (
                isinstance(value, ast.FormattedValue)
                and value.conversion == -1
                and value.format_spec is None
            ):
                rendered = _static_string_expression(value.value)
                if rendered is not None:
                    parts.append(rendered)
                    continue
            return None
        return "".join(parts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], (ast.List, ast.Tuple, ast.Set))
    ):
        separator = _static_string_expression(node.func.value)
        items = [_static_string_expression(item) for item in node.args[0].elts]
        if separator is not None and all(item is not None for item in items):
            return separator.join(item for item in items if item is not None)
    return None


def _dotted_expression_name(node: ast.expr) -> str | None:
    """Resolve a plain dotted attribute chain to its source text, if static."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _canonical_read_env_var(node: ast.expr) -> str | None:
    """Return the environment variable a canonical read reads, if it is one."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "config"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in {"RUNTIME_DATABASE_URL", "DATABASE_URL"}
        and len(node.keywords) == 1
        and node.keywords[0].arg == "default"
        and isinstance(node.keywords[0].value, ast.Constant)
        and node.keywords[0].value.value is None
    ):
        return str(node.args[0].value)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _dotted_expression_name(node.func.value) == "os.environ"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value
        in {"QUICKSCALE_PRIVILEGED_COMMAND", "QUICKSCALE_NON_DB_COMMAND"}
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == ""
        and not node.keywords
    ):
        return str(node.args[0].value)
    return None


def _facade_imports(
    tree: ast.Module,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Return the facade import names and the dj_database_url parse names."""
    facade_names: set[str] = set()
    facade_roots: set[str] = set()
    module_aliases: set[str] = set()
    direct_names: set[str] = set()
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "quickscale_core.runtime.settings"
        ):
            for alias in node.names:
                if alias.name == "resolve_runtime_database_url":
                    facade_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "quickscale_core.runtime.settings":
                    facade_roots.add(alias.asname or alias.name)
                if alias.name == "dj_database_url":
                    module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "dj_database_url":
            for alias in node.names:
                if alias.name == "parse":
                    direct_names.add(alias.asname or alias.name)
    return facade_names, facade_roots, module_aliases, direct_names


def _is_facade_selection_call(
    node: ast.expr,
    *,
    facade_names: set[str],
    facade_roots: set[str],
) -> bool:
    """Return whether *node* calls the facade's database selection."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in facade_names:
        return True
    dotted = _dotted_expression_name(func)
    if dotted is None or not dotted.endswith(".resolve_runtime_database_url"):
        return False
    return dotted[: -len(".resolve_runtime_database_url")] in facade_roots


def _is_canonical_selection_call(
    node: ast.Call,
    *,
    runtime_reads: set[str],
    database_reads: set[str],
    privileged_reads: set[str],
    non_db_reads: set[str],
) -> bool:
    """Return whether the facade call receives its canonical input reads."""
    if node.args:
        return False
    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
    required = {
        "runtime_database_url",
        "database_url",
        "privileged_command",
        "non_db_command",
        "allow_bypass_rls",
    }
    if set(keywords) != required:
        return False
    expected = {
        "runtime_database_url": runtime_reads,
        "database_url": database_reads,
        "privileged_command": privileged_reads,
        "non_db_command": non_db_reads,
    }
    for argument, allowed_names in expected.items():
        value = keywords[argument]
        if not isinstance(value, ast.Name) or value.id not in allowed_names:
            return False
    return True


def _is_canonical_parse_call(
    node: ast.expr,
    *,
    selected_name: str,
    module_aliases: set[str],
    direct_names: set[str],
) -> bool:
    """Return whether *node* parses the selected URL through dj_database_url."""
    if not isinstance(node, ast.Call) or not node.args:
        return False
    first = node.args[0]
    if not isinstance(first, ast.Name) or first.id != selected_name:
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in direct_names:
        return True
    dotted = _dotted_expression_name(func)
    if dotted is None or not dotted.endswith(".parse"):
        return False
    return dotted[: -len(".parse")] in module_aliases


def _is_canonical_database_entry(
    node: ast.expr,
    *,
    selected_name: str,
    module_aliases: set[str],
    direct_names: set[str],
) -> bool:
    """Return whether the default connection is built from the selected URL."""
    if isinstance(node, ast.Name):
        return node.id == selected_name
    if _is_canonical_parse_call(
        node,
        selected_name=selected_name,
        module_aliases=module_aliases,
        direct_names=direct_names,
    ):
        return True
    # cast(dict[str, object], dj_database_url.parse(<selected>, ...))
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "cast"
        and len(node.args) == 2
        and _is_canonical_parse_call(
            node.args[1],
            selected_name=selected_name,
            module_aliases=module_aliases,
            direct_names=direct_names,
        )
    )


def _default_entry_is_canonical(
    databases_value: ast.Dict,
    *,
    selected_name: str,
    module_aliases: set[str],
    direct_names: set[str],
) -> bool:
    """Return whether the ``default`` entry parses the selected URL."""
    for key, entry in zip(databases_value.keys, databases_value.values, strict=False):
        if isinstance(key, ast.Constant) and key.value == "default":
            return _is_canonical_database_entry(
                entry,
                selected_name=selected_name,
                module_aliases=module_aliases,
                direct_names=direct_names,
            )
    return False


def _supersedes_selection(node: ast.stmt, *, protected: set[str]) -> bool:
    """Return whether a statement could replace the validated selection."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in protected:
                return True
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "DATABASES"
            ):
                return True
    return (
        isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id in protected
    )


def _facade_selection_targets_databases(tree: ast.Module) -> bool:
    """Return whether module scope delegates the database selection canonically.

    This is a whitelist: the donor settings must import the facade selection,
    read the runtime and command-mode inputs through their canonical
    environment reads, call the facade with those names, and build the default
    connection from the call's result — with no later statement that could
    supersede the selection.  A syntactic call alone is not enough: donor
    settings that call the facade in an unused function, feed it the privileged
    URL, or let another URL win for the default connection would otherwise be
    accepted and then serve under the privileged role.
    """
    facade_names, facade_roots, module_aliases, direct_names = _facade_imports(tree)
    if not facade_names and not facade_roots:
        return False
    if not module_aliases and not direct_names:
        return False

    bound: set[str] = (
        set(facade_names) | set(facade_roots) | set(module_aliases) | set(direct_names)
    )
    reads: dict[str, set[str]] = {}
    selected_name: str | None = None
    databases_seen = False

    for node in tree.body:
        if databases_seen:
            if _supersedes_selection(node, protected=bound | {"DATABASES"}):
                return False
            continue
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        name = target.id
        if name in bound:
            # Rebinding an imported name or a validated read can replace the
            # contract source with anything.
            return False
        env_var = _canonical_read_env_var(node.value)
        if env_var is not None:
            reads.setdefault(env_var, set()).add(name)
            bound.add(name)
            continue
        value = node.value
        if _is_facade_selection_call(
            value, facade_names=facade_names, facade_roots=facade_roots
        ):
            if not isinstance(value, ast.Call) or not _is_canonical_selection_call(
                value,
                runtime_reads=reads.get("RUNTIME_DATABASE_URL", set()),
                database_reads=reads.get("DATABASE_URL", set()),
                privileged_reads=reads.get("QUICKSCALE_PRIVILEGED_COMMAND", set()),
                non_db_reads=reads.get("QUICKSCALE_NON_DB_COMMAND", set()),
            ):
                return False
            selected_name = name
            bound.add(name)
            continue
        if name == "DATABASES":
            if selected_name is None:
                return False
            if not isinstance(node.value, ast.Dict) or not _default_entry_is_canonical(
                node.value,
                selected_name=selected_name,
                module_aliases=module_aliases,
                direct_names=direct_names,
            ):
                return False
            databases_seen = True
            bound.add(name)

    return databases_seen


def _load_settings_facade_contract(settings_path: Path) -> dict[str, set[str]]:
    """Confirm effective production settings call the versioned runtime facade.

    SA206 moved the launcher one-shot command contract into
    ``quickscale_core.runtime.settings``.  Donor settings that still carry an
    inline copy of the contract are refused before any mutation; the allowlists
    the launchers are checked against come from the facade itself, so the
    contract has a single declaration.
    """
    try:
        tree = ast.parse(settings_path.read_text(), filename=str(settings_path))
    except (OSError, SyntaxError) as exc:
        raise ValueError(
            f"Unable to parse effective production settings {settings_path}: {exc}"
        ) from exc

    if not _facade_selection_targets_databases(tree):
        raise ValueError(
            f"{settings_path} does not select its database through the QuickScale "  # noqa: S608 - operator diagnostic text, not SQL
            "runtime settings facade, and its inline block does not match a "
            "pre-facade shape the migration rewrites automatically. Replace the "
            "inline command-mode contract with "
            "'from quickscale_core.runtime.settings import resolve_runtime_database_url', "
            "assign its result at module scope (for example '_db_url = "
            "resolve_runtime_database_url(...)'), and build DATABASES from that name so "
            "the facade's privileged/runtime selection governs the connection."
        )

    return _load_known_runtime_commands()


def _load_known_runtime_commands() -> dict[str, set[str]]:
    """Return the command allowlists declared by the installed facade."""
    # Imported lazily: this maintainer tool runs in the repository environment,
    # where quickscale-core's Django dependency is installed, while the module
    # itself stays importable without it.
    from quickscale_core.runtime.settings import (
        KNOWN_NON_DB_COMMANDS,
        KNOWN_PRIVILEGED_COMMANDS,
    )

    known_commands: dict[str, set[str]] = {
        "QUICKSCALE_PRIVILEGED_COMMAND": set(KNOWN_PRIVILEGED_COMMANDS),
        "QUICKSCALE_NON_DB_COMMAND": set(KNOWN_NON_DB_COMMANDS),
    }
    expected_privileged_commands = _REQUIRED_RUNTIME_COMMANDS[
        "QUICKSCALE_PRIVILEGED_COMMAND"
    ]
    if known_commands["QUICKSCALE_PRIVILEGED_COMMAND"] != expected_privileged_commands:
        expected = ", ".join(sorted(expected_privileged_commands))
        raise ValueError(
            "The installed quickscale-core runtime settings facade must declare "
            f"exactly the supported privileged commands: {expected}."
        )
    return known_commands


@dataclass(frozen=True)
class PreFacadeSettingsRewrite:
    """A recognized pre-facade donor settings file rewritten onto the facade.

    ``contract_lines`` is the 1-based inclusive line span of the inline
    database/command contract that was replaced.  ``carried_settings`` names
    every donor setting the rewrite keeps outside that span, so the report can
    state what was carried rather than replaced.
    """

    rewritten_text: str
    contract_lines: tuple[int, int]
    carried_settings: tuple[str, ...]


# Names the inline database/command contract binds for itself.  A statement
# inside the replaced span may bind one of these; binding anything else means
# the span holds donor content that the rewrite would silently discard.
_INLINE_CONTRACT_BINDINGS: frozenset[str] = frozenset(
    {
        "_db_url",
        "_KNOWN_NON_DB_COMMANDS",
        "_KNOWN_PRIVILEGED_COMMANDS",
        "_non_db_command",
        "_privileged_command",
        "_runtime_db_url",
        "DATABASES",
        "database_url",
    }
)


def _canonical_read_bindings(tree: ast.Module) -> dict[str, str]:
    """Map each module-level canonical read name to the variable it reads."""
    bindings: dict[str, str] = {}
    for node in tree.body:
        if (
            not isinstance(node, ast.Assign)
            or len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Name)
        ):
            continue
        env_var = _canonical_read_env_var(node.value)
        if env_var is not None:
            bindings[node.targets[0].id] = env_var
    return bindings


def _databases_assignment_index(statements: list[ast.stmt], start: int) -> int | None:
    """Return the index of the first ``DATABASES = {...}`` literal after start."""
    for index in range(start, len(statements)):
        node = statements[index]
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "DATABASES"
            and isinstance(node.value, ast.Dict)
        ):
            return index
    return None


def _statement_assigned_names(statement: ast.stmt) -> set[str]:
    """Return every name a statement (or branch of it) assigns directly."""
    names: set[str] = set()
    if isinstance(statement, ast.Assign):
        names.update(
            target.id for target in statement.targets if isinstance(target, ast.Name)
        )
    elif isinstance(statement, ast.AnnAssign):
        if isinstance(statement.target, ast.Name) and statement.value is not None:
            names.add(statement.target.id)
    elif isinstance(statement, ast.If):
        for child in [*statement.body, *statement.orelse]:
            names |= _statement_assigned_names(child)
    return names


_ALLOWED_DATABASE_KEYWORDS: frozenset[str] = frozenset(
    {"default", "conn_max_age", "conn_health_checks"}
)


def _contract_statement_only(statement: ast.stmt) -> bool:
    """Return whether a span statement assigns only plain contract names.

    A Subscript or Attribute assignment target would be dropped by the rewrite
    without binding anything the allowed-name check can see, so every
    assignment target must be a plain name.
    """
    if isinstance(statement, ast.Raise):
        return True
    if isinstance(statement, ast.Assign):
        return len(statement.targets) == 1 and isinstance(
            statement.targets[0], ast.Name
        )
    if isinstance(statement, ast.AnnAssign):
        return statement.value is not None and isinstance(statement.target, ast.Name)
    if isinstance(statement, ast.If):
        return all(
            _contract_statement_only(child)
            for child in [*statement.body, *statement.orelse]
        )
    return False


def _sole_default_selection_entry(node: ast.expr) -> bool:
    """Return whether one database entry selects one connection from a URL name."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "cast"
        and len(node.args) == 2
    ):
        return _sole_default_selection_entry(node.args[1])
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    if node.func.attr not in {"config", "parse"}:
        return False
    if any(
        keyword.arg is None or keyword.arg not in _ALLOWED_DATABASE_KEYWORDS
        for keyword in node.keywords
    ):
        return False
    if len(node.args) == 1 and isinstance(node.args[0], ast.Name):
        return True
    return any(
        keyword.arg == "default" and isinstance(keyword.value, ast.Name)
        for keyword in node.keywords
    )


def _is_sole_default_database_selection(node: ast.Dict) -> bool:
    """Return whether DATABASES configures only the selected default connection.

    A second connection or an unrecognized parse keyword is donor
    configuration the rewrite would remove, so the caller refuses instead of
    rewriting.
    """
    if any(key is None for key in node.keys) or len(node.keys) != 1:
        return False
    key = node.keys[0]
    if not (isinstance(key, ast.Constant) and key.value == "default"):
        return False
    return _sole_default_selection_entry(node.values[0])


def _boundary_lines_are_clean(text: str, first: ast.stmt, last: ast.stmt) -> bool:
    """Return whether both boundary lines hold only their statement.

    The rewrite replaces whole physical lines, so an unrelated statement
    sharing the first or last boundary line would be removed with it.  Column
    offsets are UTF-8 byte offsets, so the check is done on encoded lines.
    """
    lines = text.splitlines(keepends=True)
    first_bytes = lines[first.lineno - 1].encode("utf-8")
    if first_bytes[: first.col_offset].strip():
        return False
    last_bytes = lines[(last.end_lineno or last.lineno) - 1].encode("utf-8")
    suffix = last_bytes[last.end_col_offset or 0 :].strip()
    return not suffix or suffix.startswith(b"#")


def _inline_contract_span(
    tree: ast.Module, text: str
) -> tuple[tuple[int, int], dict[str, str]] | None:
    """Return the replaced line span and canonical reads of an inline contract.

    The span runs from the first module-level canonical database-URL read to
    the first following ``DATABASES = {...}`` literal.  Every statement in
    between must be a plain assignment or branch that binds only contract
    names, and the DATABASES literal must configure only the selected default
    connection; anything else is donor content and the caller refuses instead
    of rewriting.
    """
    statements = tree.body
    reads = _canonical_read_bindings(tree)
    if "DATABASE_URL" not in reads.values():
        return None

    start = next(
        (
            index
            for index, node in enumerate(statements)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and _canonical_read_env_var(node.value)
            in {"DATABASE_URL", "RUNTIME_DATABASE_URL"}
        ),
        None,
    )
    if start is None:
        return None

    end = _databases_assignment_index(statements, start)
    if end is None:
        return None
    if not _boundary_lines_are_clean(text, statements[start], statements[end]):
        return None

    allowed = set(reads) | _INLINE_CONTRACT_BINDINGS
    for node in statements[start : end + 1]:
        if not _contract_statement_only(node):
            return None
        if not _statement_assigned_names(node) <= allowed:
            return None
    databases_assignment = statements[end]
    if not (
        isinstance(databases_assignment, ast.Assign)
        and isinstance(databases_assignment.value, ast.Dict)
        and _is_sole_default_database_selection(databases_assignment.value)
    ):
        return None
    span = (
        statements[start].lineno,
        statements[end].end_lineno or statements[end].lineno,
    )
    return span, reads


def _carried_setting_names(tree: ast.Module, span: tuple[int, int]) -> tuple[str, ...]:
    """Return the public setting names the rewrite keeps outside the span."""
    names: set[str] = set()
    for node in tree.body:
        node_start = node.lineno
        node_end = node.end_lineno or node.lineno
        if node_start >= span[0] and node_end <= span[1]:
            continue
        names.update(
            name
            for name in _statement_assigned_names(node)
            if not name.startswith("_") and name != "DATABASES"
        )
    return tuple(sorted(names))


def _render_facade_selection_block(reads: dict[str, str]) -> str:
    """Render the canonical facade selection using the donor's read names."""
    runtime_name = next(
        (name for name, env in reads.items() if env == "RUNTIME_DATABASE_URL"),
        "_runtime_database_url",
    )
    database_name = next(name for name, env in reads.items() if env == "DATABASE_URL")
    privileged_name = next(
        (name for name, env in reads.items() if env == "QUICKSCALE_PRIVILEGED_COMMAND"),
        "_privileged_command",
    )
    non_db_name = next(
        (name for name, env in reads.items() if env == "QUICKSCALE_NON_DB_COMMAND"),
        "_non_db_command",
    )
    lines = [
        "from quickscale_core.runtime.settings import resolve_runtime_database_url",
        f'{runtime_name} = config("RUNTIME_DATABASE_URL", default=None)',
        f'{database_name} = config("DATABASE_URL", default=None)',
        f'{privileged_name} = os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND", "")',
        f'{non_db_name} = os.environ.get("QUICKSCALE_NON_DB_COMMAND", "")',
        "_db_url = resolve_runtime_database_url(",
        f"    runtime_database_url={runtime_name},",
        f"    database_url={database_name},",
        f"    privileged_command={privileged_name},",
        f"    non_db_command={non_db_name},",
        '    allow_bypass_rls=os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1",',
        ")",
        "DATABASES = {",
        '    "default": dj_database_url.parse(',
        "        _db_url, conn_max_age=600, conn_health_checks=True",
        "    ),",
        "}",
    ]
    return "\n".join(lines) + "\n"


def _module_imports(tree: ast.Module, module: str) -> bool:
    """Return whether *module* is bound under its own name at module scope.

    An aliased ``import os as operating_system`` does not bind ``os``, so the
    generated ``os.environ.get(...)`` reads would raise NameError unless the
    rewrite adds its own import.
    """
    for node in tree.body:
        if isinstance(node, ast.Import) and any(
            alias.name == module and alias.asname is None for alias in node.names
        ):
            return True
    return False


def _module_binds_config(tree: ast.Module) -> bool:
    """Return whether ``config`` is imported from decouple at module scope."""
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "decouple":
            if any(alias.name == "config" for alias in node.names):
                return True
    return False


def _plan_pre_facade_settings_rewrite(
    settings_path: Path,
) -> PreFacadeSettingsRewrite | None:
    """Plan a rewrite of a recognized pre-facade database selection, if any.

    Returns ``None`` when the file already delegates to the facade or when its
    inline contract does not match a shape the rewrite can preserve exactly, in
    which case the caller keeps its existing fail-closed refusal.
    """
    try:
        text = settings_path.read_text()
        tree = ast.parse(text, filename=str(settings_path))
    except OSError, SyntaxError:
        return None
    if _facade_selection_targets_databases(tree):
        return None

    span_hint = _inline_contract_span(tree, text)
    if span_hint is None:
        return None
    span, reads = span_hint
    facade_names, _, module_aliases, _ = _facade_imports(tree)
    if facade_names:
        # A facade import outside the rewritten span means the file already
        # carries facade-shaped content the rewrite must not guess about.
        return None
    if not module_aliases:
        return None
    if not _module_binds_config(tree):
        return None
    if not _module_imports(tree, "os"):
        # The generated privileged/non-db reads need os; add the import to the
        # replacement span when the donor never imported it.
        block = "import os\n" + _render_facade_selection_block(reads)
    else:
        block = _render_facade_selection_block(reads)

    lines = text.splitlines(keepends=True)
    rewritten = "".join(lines[: span[0] - 1]) + block + "".join(lines[span[1] :])
    try:
        rewritten_tree = ast.parse(rewritten, filename=str(settings_path))
    except SyntaxError:
        return None
    if not _facade_selection_targets_databases(rewritten_tree):
        return None
    return PreFacadeSettingsRewrite(
        rewritten_text=rewritten,
        contract_lines=span,
        carried_settings=_carried_setting_names(tree, span),
    )


def _write_rewritten_settings(
    settings_path: Path, rewrite: PreFacadeSettingsRewrite
) -> None:
    """Atomically write a rewritten settings module after compile validation."""
    try:
        compile(rewrite.rewritten_text, str(settings_path), "exec")
    except SyntaxError as error:
        raise ValueError(
            f"Refusing to write invalid rewritten settings to {settings_path}: {error}"
        ) from error
    _write_text_atomically(settings_path, rewrite.rewritten_text)
