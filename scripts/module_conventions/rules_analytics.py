"""Analytics event rule."""

from __future__ import annotations

import ast
from typing import Any

from scripts.module_conventions.core import (
    Corpus,
    Module,
    _call_func_name,
    _docstring_nodes,
    _keyword,
    _literal,
    _parse,
    _string_assignments,
    _string_list,
)


def _names_session_key(node: ast.AST) -> bool:
    """
    Return whether a node reads or names the session credential.

    Rule 22: the credential the session stores (``session.session_key``, or
    the ``"session_key"`` string ``getattr`` reads it through) is the token
    the rule forbids, wherever a module reads or constructs it.
    """
    if isinstance(node, ast.Attribute) and node.attr == "session_key":
        return True
    if isinstance(node, ast.Name) and node.id == "session_key":
        return True
    return isinstance(node, ast.Constant) and node.value == "session_key"


def _session_key_violations(
    module: Module,
    tree: ast.Module,
    rel: str,
) -> list[str]:
    """Return rule 22 violations for session-credential uses in one file."""
    violations: list[str] = []
    docstrings = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if not _names_session_key(node):
            continue
        if isinstance(node, ast.Constant) and id(node) in docstrings:
            continue
        violations.append(
            f"rule 22: {module.name}: {rel}:{node.lineno} uses session_key "
            "(a live session credential) in module source"
        )
    return violations


def rule_22_analytics_events(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    analytics = next((module for module in corpus.modules if module.name == "analytics"), None)
    if analytics is not None:
        services = analytics.files.get("services.py", "")
        if services:
            tree = _parse(services)
            helpers = [
                node.name
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name.startswith("capture_")
            ]
            if helpers != ["capture_event"]:
                violations.append(
                    f"rule 22: analytics: capture helpers are {helpers}, expected ['capture_event']"
                )
            exports = _string_list(tree).get("__all__", [])
            if "capture_event" not in exports:
                violations.append("rule 22: analytics: capture_event is not in services.__all__")
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            violations.extend(_session_key_violations(module, _parse(text), rel))
    for module in corpus.modules:
        if module.name == "analytics":
            continue
        constants: dict[str, Any] = {}
        for rel, text in module.files.items():
            if rel.endswith(".py"):
                constants.update(
                    {
                        name: value
                        for name, value in _string_assignments(_parse(text)).items()
                        if name.isupper() or name.endswith("_EVENT")
                    }
                )
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            for node in ast.walk(_parse(text)):
                if not isinstance(node, ast.Call):
                    continue
                if _call_func_name(node) != "capture_event":
                    continue
                argument = _keyword(node, "event")
                if argument is None and len(node.args) >= 2:
                    argument = node.args[1]
                if isinstance(argument, ast.Name):
                    event = constants.get(argument.id)
                else:
                    event = _literal(argument)
                if not isinstance(event, str):
                    violations.append(
                        f"rule 22: {module.name}: {rel} calls capture_event with no resolvable "
                        "event name"
                    )
                elif event != "$pageview" and not event.startswith(f"quickscale_{module.name}_"):
                    violations.append(
                        f"rule 22: {module.name}: event {event!r} lacks the "
                        f"quickscale_{module.name}_ stem"
                    )
    return violations
