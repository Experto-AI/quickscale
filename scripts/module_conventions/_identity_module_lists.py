"""
Rule 37's literal, branch, and constant scan mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_identity`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping

from scripts.module_conventions.core import GENERATOR_TEMPLATE_ROOT, _parse

#: Rule 37's template spellings of a module enumeration (enforcement gap 13).
_TEMPLATE_BRACKET_LITERAL = re.compile(r"[\[(]([^\])]*)[\])]")

_TEMPLATE_QUOTED_NAME = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")

_TEMPLATE_PIPE_GROUP = re.compile(r"\((?:\?:)?([A-Za-z0-9_|]+)\)")

#: Rule 37's comparison operators that make a per-module branch: an equality
#: or inequality test against one module's name.  Membership tests read the
#: configured set, which is a reference to it, not a branch on one module.
RULE_37_BRANCH_OPERATORS = (ast.Eq, ast.NotEq)

#: Rule 37's branch operands: anything that can carry a module name in an
#: expression -- a plain name, an attribute, a subscript (``entry['name']``),
#: or a call (``entry.get('name')``).  A literal-to-literal comparison is
#: data, not a module branch.
RULE_37_BRANCH_OPERANDS = (ast.Name, ast.Attribute, ast.Subscript, ast.Call)

#: Rule 37's enumeration threshold: two or more distinct module names in one
#: literal is a module enumeration; a single name counts when it is an assigned
#: constant (a registry or an exclusion), and a one-name expression inside a
#: call is a reference, not an enumeration.
RULE_37_MINIMUM_MODULE_NAMES = 2


def _assigned_literal_symbols(tree: ast.Module) -> dict[int, str]:
    """Return the symbol name each assigned literal value is bound to."""
    symbols: dict[int, str] = {}
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None:
            continue
        if isinstance(value, ast.Call) and len(value.args) == 1 and not value.keywords:
            value = value.args[0]
        for target in targets:
            if isinstance(target, ast.Name):
                symbols[id(value)] = target.id
    return symbols


def _returned_literal_symbols(tree: ast.Module) -> dict[int, str]:
    """Return the symbol name each returned list/tuple/set literal carries."""
    symbols: dict[int, str] = {}
    for function in (
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        for statement in ast.walk(function):
            if isinstance(statement, ast.Return) and isinstance(
                statement.value, (ast.List, ast.Tuple, ast.Set)
            ):
                symbols[id(statement.value)] = f"return:{function.name}"
    return symbols


def _module_literal_names(
    tree: ast.Module, vocabulary: set[str]
) -> list[tuple[int, str, list[str]]]:
    """
    Return literal collections holding several module names.

    Every string constant inside the collection counts, so a hand-written
    registry of constructor calls (``Entry(name="auth")``) is caught, not only
    a flat list of string literals.  A one-name collection counts when it is an
    assigned constant (a singleton registry or an exclusion) or a returned
    list/tuple/set (a function-provided inventory); a one-name expression
    inside a call is a reference and does not.
    """
    symbols = _assigned_literal_symbols(tree)
    symbols.update(_returned_literal_symbols(tree))
    found: list[tuple[int, str, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            continue
        names = [
            inner.value
            for inner in ast.walk(node)
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str)
        ]
        matched = sorted({name for name in names if name in vocabulary})
        symbol = symbols.get(id(node), "<expression>")
        if len(matched) >= RULE_37_MINIMUM_MODULE_NAMES or (
            len(matched) == 1 and symbol != "<expression>"
        ):
            found.append((node.lineno, symbol, matched))
    return found


def _string_module_alternations(
    tree: ast.Module, vocabulary: set[str]
) -> list[tuple[int, str, list[str]]]:
    """
    Return string constants carrying a module-name alternation.

    Python has no dedicated spelling for an enumeration held in one string,
    so the detector reads the same pipe-group shape the template detector
    reads: a regex or formatted string that enumerates module names (for
    example ``(alpha|beta)``) is a module list wherever it lives.
    """
    found: list[tuple[int, str, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        for match in _TEMPLATE_PIPE_GROUP.finditer(node.value):
            names = sorted(part for part in match.group(1).split("|") if part in vocabulary)
            if len(names) >= RULE_37_MINIMUM_MODULE_NAMES:
                found.append((node.lineno, f"<string alternation:{match.group(1)}>", names))
    return found


def _template_module_literals(text: str, vocabulary: set[str]) -> list[tuple[int, str, list[str]]]:
    """
    Return literal module enumerations found in a Jinja template's text.

    Templates carry no AST, so the detector reads the two spellings an
    enumeration takes there: a bracketed literal of quoted names, and a
    pipe-separated route alternation (``(blog|listings|...)``).  A single
    name is a reference, not an enumeration, and does not count.
    """
    found: list[tuple[int, str, list[str]]] = []
    for match in _TEMPLATE_BRACKET_LITERAL.finditer(text):
        names = sorted(
            {
                quoted.group(1)
                for quoted in _TEMPLATE_QUOTED_NAME.finditer(match.group(1))
                if quoted.group(1) in vocabulary
            }
        )
        if len(names) >= RULE_37_MINIMUM_MODULE_NAMES:
            found.append((text.count("\n", 0, match.start()) + 1, "<template literal>", names))
    for match in _TEMPLATE_PIPE_GROUP.finditer(text):
        names = sorted(part for part in match.group(1).split("|") if part in vocabulary)
        if len(names) >= RULE_37_MINIMUM_MODULE_NAMES:
            found.append(
                (
                    text.count("\n", 0, match.start()) + 1,
                    f"<template alternation:{match.group(1)}>",
                    names,
                )
            )
    return found


def _module_name_branches(tree: ast.Module, vocabulary: set[str]) -> list[tuple[int, str, str]]:
    """Return equality comparisons against a discovered module name."""
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, RULE_37_BRANCH_OPERATORS) for op in node.ops):
            continue
        parts = [node.left, *node.comparators]
        for part in parts:
            if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                continue
            if part.value not in vocabulary:
                continue
            others = [candidate for candidate in parts if candidate is not part]
            if others and all(
                isinstance(candidate, RULE_37_BRANCH_OPERANDS) for candidate in others
            ):
                found.append((node.lineno, ast.unparse(node), part.value))
    return found


def _module_prefixed_constants(tree: ast.Module, vocabulary: set[str]) -> list[tuple[int, str]]:
    """Return module-level constant names prefixed with a module name."""
    found: list[tuple[int, str]] = []
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            stripped = target.id.lstrip("_")
            if any(stripped.startswith(f"{name.upper()}_") for name in vocabulary):
                found.append((node.lineno, target.id))
    return found


def _module_list_violations(
    tree_name: str,
    rel: str,
    text: str,
    vocabulary: set[str],
    allowed_literal_files: frozenset[tuple[str, str]],
    allowed_literals: Mapping[tuple[str, str, str], str],
    allowed_branches: Mapping[tuple[str, str, str], str],
    allowed_constants: Mapping[tuple[str, str, str], str],
) -> list[str]:
    """Return rule 37's findings for one corpus file, its exceptions applied."""
    is_python = rel.endswith(".py")
    is_template = (
        tree_name == "core" and rel.startswith(GENERATOR_TEMPLATE_ROOT) and rel.endswith(".j2")
    )
    if not is_python and not is_template:
        return []
    if tree_name == "scripts" and is_python and rel.split("/")[-1].startswith("test_"):
        return []
    if is_python and (tree_name, rel) in allowed_literal_files:
        return []
    violations: list[str] = []
    if is_python:
        parsed = _parse(text)
        found = _module_literal_names(parsed, vocabulary) + _string_module_alternations(
            parsed, vocabulary
        )
    else:
        found = _template_module_literals(text, vocabulary)
    for lineno, symbol, names in found:
        if (tree_name, rel, symbol) in allowed_literals:
            continue
        count = len(names)
        label = "module name" if count == 1 else "module names"
        violations.append(
            f"rule 37: {tree_name}/{rel}:{lineno} literal {symbol} lists "
            f"{count} {label}: {', '.join(names)}"
        )
    if not is_python or tree_name not in ("core", "cli"):
        return violations
    tree = _parse(text)
    for lineno, expression, name in _module_name_branches(tree, vocabulary):
        if (tree_name, rel, name) in allowed_branches:
            continue
        violations.append(
            f"rule 37: {tree_name}/{rel}:{lineno} branches on module name {name!r}: {expression}"
        )
    for lineno, constant in _module_prefixed_constants(tree, vocabulary):
        if (tree_name, rel, constant) in allowed_constants:
            continue
        violations.append(
            f"rule 37: {tree_name}/{rel}:{lineno} declares module-prefixed constant {constant}"
        )
    return violations
