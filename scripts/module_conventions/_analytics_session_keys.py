"""
Rule 22's session-credential mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_analytics`;
that module owns rule 22's orchestration and re-exports this module's names.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import (
    Corpus,
    Module,
    _docstring_nodes,
    _parse,
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


def _session_key_violations(module: Module, tree: ast.Module, rel: str) -> list[str]:
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


def _session_key_scan_violations(corpus: Corpus) -> list[str]:
    """Scan every module's Python source for uses of the session credential."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            violations.extend(_session_key_violations(module, _parse(text), rel))
    return violations
