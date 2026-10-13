"""
Rule 33's shared-namespace stems: database functions, sessions, lock keys.

Implementation detail of :mod:`scripts.module_conventions.rules_identity`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import re

from scripts.module_conventions.core import (
    Corpus,
    Module,
    _literal,
    _parse,
    _string_assignments,
)


def _is_session_receiver(node: ast.expr) -> bool:
    """
    Return whether *node* is a Django session object.

    Only ``request.session``-shaped attributes and the bare name ``session``
    count; a vendor object whose variable ends in ``_session`` (a Stripe
    checkout session, for example) is a mapping of provider fields, not the
    project's session store.
    """
    if isinstance(node, ast.Name):
        return node.id == "session"
    if isinstance(node, ast.Attribute):
        return node.attr == "session"
    return False


def _session_literal_keys(tree: ast.Module) -> list[tuple[int, str]]:
    """
    Return literal session keys read or written through a session object.

    Named keys (a constant or a variable) are the ``*SESSION_KEY`` clause's
    business; this covers the literal forms a writer reaches for directly:
    ``request.session['key']`` and ``session.get/pop/setdefault('key')``.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _is_session_receiver(node.value):
            key = _literal(node.slice)
            if isinstance(key, str):
                found.append((node.lineno, key))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"get", "pop", "setdefault"}
            and _is_session_receiver(node.func.value)
            and node.args
        ):
            key = _literal(node.args[0])
            if isinstance(key, str):
                found.append((node.lineno, key))
    return found


def _shared_stem_file_violations(module: Module, tree: ast.Module, stem: str) -> list[str]:
    """Return rule 33's database-function and session-constant violations."""
    violations: list[str] = []
    for name, value in _string_assignments(tree).items():
        if name.endswith("FUNC_NAME") and not value.startswith(f"{stem}_"):
            violations.append(
                f"rule 33: {module.name}: database function {name} lacks the {stem}_ stem"
            )
        if name.endswith("SESSION_KEY") and not value.startswith(f"{stem}:"):
            violations.append(f"rule 33: {module.name}: session key {name} lacks the {stem}: stem")
        match = re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([A-Za-z0-9_]+)", value)
        if match and not match.group(1).startswith(f"{stem}_"):
            violations.append(
                f"rule 33: {module.name}: database function {match.group(1)!r} "
                f"lacks the {stem}_ stem"
            )
    return violations


def _session_literal_violations(module: Module, rel: str, tree: ast.Module, stem: str) -> list[str]:
    """Return rule 33's violations for literal session keys."""
    violations: list[str] = []
    for lineno, key in _session_literal_keys(tree):
        if not key.startswith(f"{stem}:"):
            violations.append(
                f"rule 33: {module.name}: {rel}:{lineno} session key {key!r} lacks the {stem}: stem"
            )
    return violations


def _lock_key_violations(module: Module, tree: ast.Module, stem: str) -> list[str]:
    """Return rule 33's violations for advisory-lock key prefixes."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "lock_key" not in node.name:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.JoinedStr) or not child.values:
                continue
            first = child.values[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            prefix = first.value.split("{", 1)[0]
            if prefix and not prefix.startswith(f"{stem}:"):
                violations.append(
                    f"rule 33: {module.name}: advisory-lock key prefix {prefix!r} "
                    f"lacks the {stem}: stem"
                )
    return violations


def rule_33_shared_stems(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            violations.extend(_shared_stem_file_violations(module, tree, stem))
            violations.extend(_session_literal_violations(module, rel, tree, stem))
            violations.extend(_lock_key_violations(module, tree, stem))
    return violations
