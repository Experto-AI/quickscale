"""
Redaction and replacement-value rules: the anonymization handlers' matchers.

Rules 47 and 48 (Module Conventions, SA245) scope to the five
``_anonymization.py`` handler files.  Rule 47 rejects a module-local identity
matcher — a substring substitution and a module-level complete-address
pattern — and rule 48 rejects a locally spelled replacement sentinel and a
handler entry point that is not ``_anonymization.anonymize_account``.  The
detectors are open-world heuristics: they catch the shapes the convention
forbids, not every possible evasion.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import Corpus, Module, _docstring_nodes, _parse

#: The handler file rules 47 and 48 scope to.
_ANONYMIZATION_FILE = "_anonymization.py"

#: The one name sentinel core defines.
_NAME_SENTINEL = "[redacted]"

#: An address sentinel begins and ends with these fragments.
_ADDRESS_SENTINEL_START = "deleted-"
_ADDRESS_SENTINEL_END = "@invalid"

#: A module-level address pattern stays allowed when it recognizes HTML-entity
#: spellings (the notifications rendered-text opt-in).
_ENTITY_TERMINATOR = ";"


def _dotted_name(node: ast.expr) -> str | None:
    """Return a dotted attribute/name expression as ``a.b.c``, or ``None``."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _literal_skeleton(node: ast.expr) -> str | None:
    """
    Return the literal skeleton of a string or f-string, or ``None``.

    Each formatted value becomes ``{}``, so ``f"deleted-{pk}@invalid"`` reads
    as ``deleted-{}@invalid`` and a plain string reads as itself.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
            elif isinstance(part, ast.FormattedValue):
                parts.append("{}")
            else:
                return None
        return "".join(parts)
    return None


def _compiled_address_pattern(node: ast.stmt) -> str | None:
    """Return a module-level ``re.compile`` address pattern's constant source."""
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return None
    value = node.value
    if not (isinstance(value, ast.Call) and _dotted_name(value.func) == "re.compile"):
        return None
    if not value.args:
        return None
    literal = value.args[0]
    if not (isinstance(literal, ast.Constant) and isinstance(literal.value, str)):
        return None
    if "@" not in literal.value:
        return None
    return literal.value


def rule_47_redaction(corpus: Corpus) -> list[str]:
    """
    Rule 47: identity redaction uses core's matchers.

    A module that removes identity from stored text or payloads uses core's
    ``replace_address`` and ``redact_names``: no substring substitution, and
    no module-local complete-address pattern (except the entity-aware
    escaped-spelling tokenizer the rendered store needs).
    """
    violations: list[str] = []
    for module in corpus.modules:
        source = module.files.get(_ANONYMIZATION_FILE)
        if source is None:
            continue
        tree = _parse(source)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and _dotted_name(node.func) == "re.sub"
                and node.args
                and isinstance(node.args[0], ast.Call)
                and _dotted_name(node.args[0].func) == "re.escape"
            ):
                violations.append(
                    f"rule 47: {module.name}: {_ANONYMIZATION_FILE}:{node.lineno}: "
                    "substitutes an identity with re.escape and no word boundary"
                )
        for node in tree.body:
            pattern = _compiled_address_pattern(node)
            if pattern is not None and _ENTITY_TERMINATOR not in pattern:
                violations.append(
                    f"rule 47: {module.name}: {_ANONYMIZATION_FILE}:{node.lineno}: "
                    "declares a module-level complete-address pattern instead of "
                    "using core's matcher"
                )
    return violations


def rule_48_replacement_values(corpus: Corpus) -> list[str]:
    """
    Rule 48: one set of replacement values and one handler entry-point name.

    Every handler writes core's ``DELETED_ADDRESS(pk)`` for an address and
    core's ``REDACTED`` for a name or username, and its private entry point is
    ``_anonymization.anonymize_account``, which the app config delegates to.
    """
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(_sentinel_violations(module))
        violations.extend(_entry_point_violations(module))
    return violations


def _sentinel_violations(module: Module) -> list[str]:
    """Reject a locally spelled replacement sentinel in the handler file."""
    source = module.files.get(_ANONYMIZATION_FILE)
    if source is None:
        return []
    tree = _parse(source)
    docstrings = _docstring_nodes(tree)
    parts: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts.update(id(part) for part in node.values)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Constant, ast.JoinedStr)) or id(node) in docstrings:
            continue
        if id(node) in parts:
            continue
        skeleton = _literal_skeleton(node)
        if skeleton is None:
            continue
        if skeleton == _NAME_SENTINEL or (
            skeleton.startswith(_ADDRESS_SENTINEL_START)
            and skeleton.endswith(_ADDRESS_SENTINEL_END)
        ):
            violations.append(
                f"rule 48: {module.name}: {_ANONYMIZATION_FILE}:{node.lineno}: "
                "spells a replacement sentinel instead of importing it from core"
            )
    if not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "anonymize_account"
        for node in tree.body
    ):
        violations.append(
            f"rule 48: {module.name}: {_ANONYMIZATION_FILE} has no anonymize_account entry point"
        )
    return violations


def _entry_point_violations(module: Module) -> list[str]:
    """Reject an app config that delegates to a differently named handler."""
    source = module.files.get("apps.py")
    if source is None:
        return []
    tree = _parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        method = next(
            (
                statement
                for statement in node.body
                if isinstance(statement, ast.FunctionDef) and statement.name == "anonymize_account"
            ),
            None,
        )
        if method is None:
            continue
        aliases: set[str] = set()
        for statement in ast.walk(method):
            if isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    if alias.name == "_anonymization":
                        aliases.add(alias.asname or alias.name)
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    if alias.name.endswith("._anonymization"):
                        aliases.add(alias.asname or alias.name.rsplit(".", 1)[-1])
        delegations = {
            call.func.attr
            for call in ast.walk(method)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in aliases
        }
        if delegations != {"anonymize_account"}:
            violations.append(
                f"rule 48: {module.name}: apps.py:{method.lineno}: anonymize_account must "
                "delegate to _anonymization.anonymize_account"
            )
    return violations
