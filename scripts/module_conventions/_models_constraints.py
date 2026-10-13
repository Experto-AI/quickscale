"""
Rule 25's constraint-name mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_models`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import (
    _call_func_name,
    _keyword,
    _literal,
    _meta_class,
    _model_classes,
)


def _literal_field_tokens(call: ast.Call) -> set[str] | None:
    """Return the tokens of a literal ``fields`` list, or None when not literal."""
    fields = _keyword(call, "fields")
    if not isinstance(fields, (ast.List, ast.Tuple)):
        return None
    tokens: set[str] = set()
    for element in fields.elts:
        value = _literal(element)
        if not isinstance(value, str):
            return None
        tokens.update(part for part in value.split("_") if part)
    return tokens


def _condition_tokens(call: ast.Call) -> set[str] | None:
    """Return the tokens of a literal ``Q`` condition, or None when opaque."""
    condition = _keyword(call, "condition")
    if condition is None:
        return set()
    tokens: set[str] = set()
    for node in ast.walk(condition):
        if isinstance(node, ast.Call):
            if _call_func_name(node) != "Q" or node.args:
                return None
            for keyword in node.keywords:
                if keyword.arg:
                    tokens.update(part for part in keyword.arg.split("__") if part)
                    tokens.update(part for part in keyword.arg.split("_") if part)
    return tokens


def _constraint_owners(tree: ast.Module) -> dict[int, str]:
    """Map each Meta constraint call to the model class that declares it."""
    owners: dict[int, str] = {}
    for node in _model_classes(tree):
        meta = _meta_class(node)
        if meta is None:
            continue
        for statement in meta.body:
            value: ast.expr | None = None
            if isinstance(statement, ast.Assign):
                value = statement.value
            elif isinstance(statement, ast.AnnAssign):
                value = statement.value
            if isinstance(value, (ast.List, ast.Tuple)):
                candidates = [element for element in value.elts if isinstance(element, ast.Call)]
            elif isinstance(value, ast.Call):
                candidates = [value]
            else:
                continue
            for candidate in candidates:
                if _call_func_name(candidate) in {"UniqueConstraint", "CheckConstraint"}:
                    owners[id(candidate)] = node.name
    return owners


def _abstract_meta_calls(tree: ast.Module) -> set[int]:
    """
    Return the ids of calls declared inside an ``abstract = True`` Meta.

    Rule 25's recorded exception: an abstract base's ``Index`` entries may stay
    unnamed, because a fixed or templated name is inherited by every concrete
    subclass and either collides in the shared schema or breaks Django's
    30-character ``models.E034`` check.  Django generates a unique, bounded
    name per concrete subclass instead.  Constraints are not exempt: a
    ``UniqueConstraint`` or ``CheckConstraint`` still needs its explicit name.
    """
    abstract_calls: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Meta":
            continue
        if not any(
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "abstract"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is True
            for statement in node.body
        ):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                abstract_calls.add(id(inner))
    return abstract_calls


def _token_matches(token: str, candidates: set[str]) -> bool:
    """Return whether a purpose token names one of the candidate tokens."""
    return any(token in candidate or candidate in token for candidate in candidates)


def _check_purpose_names_fields(
    module_name: str,
    rel: str,
    node: ast.Call,
    name: str,
    purpose_tokens: list[str],
    violations: list[str],
) -> None:
    """Rule 25: a unique constraint's purpose names its constrained fields."""
    field_tokens = _literal_field_tokens(node)
    if field_tokens is None or not purpose_tokens:
        return
    condition_tokens = _condition_tokens(node)
    if condition_tokens is None:
        # A helper-built condition is opaque; require at least one field token.
        if not any(_token_matches(token, field_tokens) for token in purpose_tokens):
            violations.append(
                f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                "does not name a constrained field"
            )
        return
    allowed = field_tokens | condition_tokens
    for token in purpose_tokens:
        if not _token_matches(token, allowed):
            violations.append(
                f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                f"purpose token {token!r} names no constrained field"
            )


def _check_constraint_names_checked_field(
    module_name: str,
    rel: str,
    node: ast.Call,
    name: str,
    purpose_tokens: list[str],
    violations: list[str],
) -> bool:
    """
    Rule 25: a check constraint's purpose names a checked field.

    Returns True when the purpose satisfied the clause (or the condition is
    opaque and therefore not statically checkable).
    """
    condition_tokens = _condition_tokens(node)
    if condition_tokens is None or not purpose_tokens:
        return True
    allowed = condition_tokens | (_literal_field_tokens(node) or set())
    if any(_token_matches(token, allowed) for token in purpose_tokens):
        return True
    violations.append(
        f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
        "purpose names no checked field"
    )
    return False


def _duplicate_keyword_violations(module_name: str, rel: str, tree: ast.Module) -> list[str]:
    """Rule 25: ``unique_together``/``index_together`` stay out of every Meta."""
    violations: list[str] = []
    for meta in (
        node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "Meta"
    ):
        for statement in meta.body:
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {
                    "unique_together",
                    "index_together",
                }:
                    violations.append(
                        f"rule 25: {module_name}: {rel}:{statement.lineno} uses {target.id}"
                    )
    return violations


def _index_call_violations(module_name: str, rel: str, node: ast.Call, name: str) -> list[str]:
    """Rule 25: an index name carries the stemmed, bounded ``_idx`` shape."""
    violations: list[str] = []
    if not name.startswith(f"qs_{module_name}_") or not name.endswith("_idx"):
        violations.append(
            f"rule 25: {module_name}: {rel}:{node.lineno} index {name!r} "
            f"must be qs_{module_name}_<model>_<field>_idx"
        )
    elif len(name) > 30:
        violations.append(
            f"rule 25: {module_name}: {rel}:{node.lineno} index {name!r} "
            "exceeds Django's 30-character limit"
        )
    return violations


def _named_constraint_violations(
    module_name: str,
    rel: str,
    node: ast.Call,
    kind: str,
    name: str,
    owners: dict[int, str],
) -> list[str]:
    """Rule 25: a named constraint's purpose names its checked or unique fields."""
    violations: list[str] = []
    owner = owners.get(id(node))
    prefix = (
        f"quickscale_{module_name}_{owner.lower()}_"
        if owner is not None
        else f"quickscale_{module_name}_"
    )
    if not name.startswith(prefix):
        violations.append(
            f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
            f"must start with {prefix}"
        )
    elif len(name) > 63:
        violations.append(
            f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
            "exceeds PostgreSQL's 63-character limit"
        )
    else:
        purpose_tokens = name[len(prefix) :].split("_")
        if "org" in purpose_tokens:
            violations.append(
                f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                "names the organization field as 'org'"
            )
        if kind == "UniqueConstraint":
            if purpose_tokens[-1] != "unique":
                violations.append(
                    f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                    "must end with _unique"
                )
            elif "unique" in purpose_tokens[:-1]:
                violations.append(
                    f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                    "uses 'unique' outside the _unique suffix"
                )
            elif not purpose_tokens[:-1]:
                violations.append(
                    f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                    "purpose names no constrained field"
                )
            else:
                _check_purpose_names_fields(
                    module_name, rel, node, name, purpose_tokens[:-1], violations
                )
        else:
            _check_constraint_names_checked_field(
                module_name, rel, node, name, purpose_tokens, violations
            )
    return violations


def _constraint_call_violations(
    module_name: str,
    rel: str,
    node: ast.Call,
    kind: str,
    abstract_calls: set[int],
    owners: dict[int, str],
) -> list[str]:
    """Rule 25's findings for one constraint or index call, name presence first."""
    name = _literal(_keyword(node, "name"))
    if not isinstance(name, str) or not name:
        if kind == "Index" and id(node) in abstract_calls:
            return []
        return [f"rule 25: {module_name}: {rel}:{node.lineno} {kind} without a name"]
    if kind == "Index":
        return _index_call_violations(module_name, rel, node, name)
    return _named_constraint_violations(module_name, rel, node, kind, name, owners)
