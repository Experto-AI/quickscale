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

#: A Jinja statement or expression.  Rule 37's single-name branch scan reads
#: only these tags, so prose and Django ``{% raw %}`` blocks never look like a
#: module branch (SA320 (c)).
_TEMPLATE_JINJA_TAG = re.compile(r"\{%(.*?)%\}|\{\{(.*?)\}\}", re.DOTALL)

#: A module-prefixed token outside a Jinja tag: a setting, a flat helper name,
#: a module package name, or a ``modules/<name>/`` path.  The detector maps
#: each match to a discovered module before reporting it.
_TEMPLATE_MODULE_TOKEN = re.compile(
    r"(?:QUICKSCALE_[A-Z0-9_]+|quickscale_[a-z0-9_]+|modules/[a-z0-9_]+/)"
)

#: Rule 37's comparison operators that make a per-module branch: an equality,
#: inequality, or membership test against one module's name.  A membership
#: test names one module keyed into the configured set, so it is the same
#: per-module branch an equality test is (SA287 (b)).
RULE_37_BRANCH_OPERATORS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)

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


def _template_module_branches(text: str, vocabulary: set[str]) -> list[tuple[int, str]]:
    """
    Return module names a Jinja tag compares against or enumerates.

    A quoted discovered module name inside a Jinja statement or expression is
    a per-module branch (``{% if app_label == "quickscale_backups" %}``,
    ``{% if "orgs" in selected_modules %}``).  Prose and Django template tags
    inside ``{% raw %}`` blocks are not Jinja tags, so they do not match.
    """
    found: list[tuple[int, str]] = []
    for match in _TEMPLATE_JINJA_TAG.finditer(text):
        body = match.group(1) or match.group(2) or ""
        names = sorted(
            {
                quoted.group(1)
                for quoted in _TEMPLATE_QUOTED_NAME.finditer(body)
                if quoted.group(1) in vocabulary
            }
        )
        if not names:
            continue
        lineno = text.count("\n", 0, match.start()) + 1
        found.extend((lineno, name) for name in names)
    return found


def _template_token_module(token: str, vocabulary: set[str]) -> str | None:
    """Return the discovered module a prefixed template token names, if any."""
    for name in vocabulary:
        upper = name.upper()
        if token == f"QUICKSCALE_{upper}" or token.startswith(f"QUICKSCALE_{upper}_"):
            return name
        if token == f"quickscale_modules_{name}" or token.startswith(f"quickscale_modules_{name}_"):
            return name
        if token == f"quickscale_{name}" or token.startswith(f"quickscale_{name}_"):
            return name
        if token.startswith(f"modules/{name}/"):
            return name
    return None


def _template_module_constants(text: str, vocabulary: set[str]) -> list[tuple[int, str, str]]:
    """
    Return module-prefixed tokens found in a Jinja template's text.

    The scan is deliberately token-shaped: a core template that reads
    ``QUICKSCALE_NOTIFICATIONS_*``, names ``quickscale_modules_orgs``, or
    points at ``modules/storage/`` carries per-module knowledge wherever the
    literal lives.  Theme files that are rule 31's declared module surface
    carry recorded exceptions in the rule module.
    """
    found: list[tuple[int, str, str]] = []
    for match in _TEMPLATE_MODULE_TOKEN.finditer(text):
        token = match.group(0)
        module_name = _template_token_module(token, vocabulary)
        if module_name is None:
            continue
        lineno = text.count("\n", 0, match.start()) + 1
        found.append((lineno, module_name, token))
    return found


def _comparison_module_names(compare: ast.Compare, vocabulary: set[str]) -> list[str]:
    """Return the module names an equality, inequality, or membership test names."""
    names: list[str] = []
    if not any(isinstance(op, RULE_37_BRANCH_OPERATORS) for op in compare.ops):
        return names
    parts = [compare.left, *compare.comparators]
    for part in parts:
        if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
            continue
        if part.value not in vocabulary:
            continue
        others = [candidate for candidate in parts if candidate is not part]
        if others and all(isinstance(candidate, RULE_37_BRANCH_OPERANDS) for candidate in others):
            names.append(part.value)
    return names


def _lookup_module_name(node: ast.Call | ast.Subscript, vocabulary: set[str]) -> str | None:
    """Return the module name a ``.get()`` call or a subscript looks up, if any."""
    if isinstance(node, ast.Call):
        function = node.func
        if not (isinstance(function, ast.Attribute) and function.attr == "get"):
            return None
        if not node.args:
            return None
        key = node.args[0]
    else:
        key = node.slice
    if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value in vocabulary:
        return key.value
    return None


def _module_name_branches(tree: ast.Module, vocabulary: set[str]) -> list[tuple[int, str, str]]:
    """
    Return comparisons, lookups, and subscripts against a discovered module name.

    An equality, inequality, or membership comparison names one module; so do
    ``mapping.get("<name>")`` and ``mapping["<name>"]``, the lookup spellings
    of the same per-module branch (SA287 (b)).
    """
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for name in _comparison_module_names(node, vocabulary):
                found.append((node.lineno, ast.unparse(node), name))
        elif isinstance(node, (ast.Call, ast.Subscript)):
            name = _lookup_module_name(node, vocabulary)
            if name is not None:
                found.append((node.lineno, ast.unparse(node), name))
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


def _literal_violations(
    tree_name: str,
    rel: str,
    found: list[tuple[int, str, list[str]]],
    allowed_literals: Mapping[tuple[str, str, str], str],
) -> list[str]:
    """Return the literal-list findings, the recorded exceptions applied."""
    violations: list[str] = []
    for lineno, symbol, names in found:
        if (tree_name, rel, symbol) in allowed_literals:
            continue
        count = len(names)
        label = "module name" if count == 1 else "module names"
        violations.append(
            f"rule 37: {tree_name}/{rel}:{lineno} literal {symbol} lists "
            f"{count} {label}: {', '.join(names)}"
        )
    return violations


def _template_branch_violations(
    text: str,
    vocabulary: set[str],
    tree_name: str,
    rel: str,
    allowed: Mapping[tuple[str, str, str], str],
) -> list[str]:
    """Return the single-name branch findings, the recorded exceptions applied."""
    return [
        f"rule 37: {tree_name}/{rel}:{lineno} branches on module name {name!r} in a template"
        for lineno, name in _template_module_branches(text, vocabulary)
        if (tree_name, rel, name) not in allowed
    ]


def _template_constant_violations(
    text: str,
    vocabulary: set[str],
    tree_name: str,
    rel: str,
    allowed: Mapping[tuple[str, str, str], str],
) -> list[str]:
    """Return the prefixed-constant findings, the recorded exceptions applied."""
    violations: list[str] = []
    seen_tokens: set[tuple[int, str]] = set()
    for lineno, name, token in _template_module_constants(text, vocabulary):
        if (tree_name, rel, name) in allowed or (lineno, token) in seen_tokens:
            continue
        seen_tokens.add((lineno, token))
        violations.append(
            f"rule 37: {tree_name}/{rel}:{lineno} declares module-prefixed "
            f"template constant {token}"
        )
    return violations


def _python_branch_violations(
    text: str,
    vocabulary: set[str],
    tree_name: str,
    rel: str,
    allowed_branches: Mapping[tuple[str, str, str], str],
    allowed_constants: Mapping[tuple[str, str, str], str],
) -> list[str]:
    """Return the Python branch and prefixed-constant findings."""
    tree = _parse(text)
    violations: list[str] = []
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


def _module_list_violations(
    tree_name: str,
    rel: str,
    text: str,
    vocabulary: set[str],
    allowed_literal_files: frozenset[tuple[str, str]],
    allowed_literals: Mapping[tuple[str, str, str], str],
    allowed_branches: Mapping[tuple[str, str, str], str],
    allowed_constants: Mapping[tuple[str, str, str], str],
    allowed_template_branches: Mapping[tuple[str, str, str], str] | None = None,
    allowed_template_constants: Mapping[tuple[str, str, str], str] | None = None,
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
    template_branches = allowed_template_branches or {}
    template_constants = allowed_template_constants or {}
    if is_python:
        parsed = _parse(text)
        found = _module_literal_names(parsed, vocabulary) + _string_module_alternations(
            parsed, vocabulary
        )
    else:
        found = _template_module_literals(text, vocabulary)
    violations = _literal_violations(tree_name, rel, found, allowed_literals)
    if is_template:
        violations.extend(
            _template_branch_violations(text, vocabulary, tree_name, rel, template_branches)
        )
        violations.extend(
            _template_constant_violations(text, vocabulary, tree_name, rel, template_constants)
        )
    if not is_python or tree_name not in ("core", "cli"):
        return violations
    violations.extend(
        _python_branch_violations(
            text, vocabulary, tree_name, rel, allowed_branches, allowed_constants
        )
    )
    return violations
