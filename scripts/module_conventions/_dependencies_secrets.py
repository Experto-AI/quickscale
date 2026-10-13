"""
Rule 35's environment-reference mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_dependencies`;
that module re-exports every public name defined here, so existing import
paths keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import (
    _attribute_chain,
    _literal,
)

# Rule 35's one listed exception: orgs' RLS boot guard reads core's runtime-role
# variables before settings load.
CORE_RUNTIME_ROLE_ENV_VARS = (
    "QUICKSCALE_ALLOW_BYPASSRLS",
    "QUICKSCALE_PRIVILEGED_COMMAND",
)


def _environ_name_sets(tree: ast.Module) -> tuple[set[str], set[str], set[str]]:
    """Return the effective names of ``os``, ``os.environ``, and ``os.getenv``."""
    os_names = {"os"}
    environ_names = {"environ"}
    getenv_names = {"getenv"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    os_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name == "environ":
                    environ_names.add(alias.asname or alias.name)
                elif alias.name == "getenv":
                    getenv_names.add(alias.asname or alias.name)
    return os_names, environ_names, getenv_names


def _environ_path(chain: tuple[str, ...], os_names: set[str], environ_names: set[str]) -> bool:
    """Return whether a chain names ``os.environ`` or one of its import aliases."""
    return (len(chain) == 1 and chain[0] in environ_names) or (
        len(chain) == 2 and chain[0] in os_names and chain[1] == "environ"
    )


def _environ_call_reference(
    node: ast.Call,
    os_names: set[str],
    environ_names: set[str],
    getenv_names: set[str],
) -> tuple[int, str | None] | None:
    """Return the reference a ``getenv`` / ``environ.get`` call records, if any."""
    chain = _attribute_chain(node.func)
    if chain is None:
        return None
    getenv_call = (len(chain) == 1 and chain[0] in getenv_names) or (
        len(chain) == 2 and chain[0] in os_names and chain[1] == "getenv"
    )
    environ_get_call = (len(chain) == 2 and chain[0] in environ_names and chain[1] == "get") or (
        len(chain) == 3 and chain[0] in os_names and chain[1:] == ("environ", "get")
    )
    if not (getenv_call or environ_get_call):
        return None
    literal = _literal(node.args[0]) if node.args else None
    return node.lineno, literal if isinstance(literal, str) else None


def _environ_call_references(
    tree: ast.Module,
    os_names: set[str],
    environ_names: set[str],
    getenv_names: set[str],
) -> tuple[list[tuple[int, str | None]], set[int]]:
    """Return the call references and the node ids a later pass must skip."""
    references: list[tuple[int, str | None]] = []
    handled: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        reference = _environ_call_reference(node, os_names, environ_names, getenv_names)
        if reference is None:
            continue
        references.append(reference)
        if isinstance(node.func, ast.Attribute):
            handled.add(id(node.func))
            handled.add(id(node.func.value))
    return references, handled


def _environ_path_references(
    tree: ast.Module,
    os_names: set[str],
    environ_names: set[str],
    handled: set[int],
) -> list[tuple[int, str | None]]:
    """Return subscript, attribute, and bare-name environment references."""
    references: list[tuple[int, str | None]] = []
    for node in ast.walk(tree):
        if id(node) in handled:
            continue
        if isinstance(node, ast.Subscript):
            chain = _attribute_chain(node.value)
            if chain is not None and _environ_path(chain, os_names, environ_names):
                literal = _literal(node.slice)
                references.append((node.lineno, literal if isinstance(literal, str) else None))
                handled.add(id(node.value))
        elif isinstance(node, ast.Attribute) and node.attr == "environ":
            chain = _attribute_chain(node)
            if chain is not None and _environ_path(chain, os_names, environ_names):
                references.append((node.lineno, None))
        elif isinstance(node, ast.Name) and node.id in environ_names:
            references.append((node.lineno, None))
    return references


def _environ_references(tree: ast.Module) -> list[tuple[int, str | None]]:
    """
    Rule 35: every ``os.getenv`` / ``os.environ`` use and its literal name.

    Import aliases of ``os``, ``os.environ``, and ``os.getenv`` are followed.
    A use whose variable name is not a string literal records ``None``.  A
    call or subscript marks the receiver it belongs to, so one use is reported
    once.
    """
    os_names, environ_names, getenv_names = _environ_name_sets(tree)
    references, handled = _environ_call_references(tree, os_names, environ_names, getenv_names)
    references.extend(_environ_path_references(tree, os_names, environ_names, handled))
    return references
