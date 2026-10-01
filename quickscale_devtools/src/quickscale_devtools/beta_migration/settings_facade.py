"""Static analysis of the versioned runtime settings facade."""

from .constants import _REQUIRED_RUNTIME_COMMANDS
import ast
from pathlib import Path


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
            "runtime settings facade. Replace the inline command-mode contract with "
            "'from quickscale_core.runtime.settings import resolve_runtime_database_url', "
            "assign its result at module scope (for example '_db_url = "
            "resolve_runtime_database_url(...)'), and build DATABASES from that name so "
            "the facade's privileged/runtime selection governs the connection."
        )

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
