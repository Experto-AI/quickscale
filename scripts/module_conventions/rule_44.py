"""
Rule 44's role-check orchestration and re-export facade.

Rule 44's mechanics live in the private siblings: ``_rule44_names`` holds the
membership-binding environment and the name-resolution helpers,
``_rule44_expressions`` the expression scanner, and ``_rule44_statements``
the statement scanner.  This module orchestrates the rule and re-exports
every moved name so existing import paths and the rule registry keep working.

The rule's operator-escape clause (coherence proposal 54) lives here beside
the orchestration because it names the module that defines the one helper,
and rule 37's allowlist exempts only this module's module-name literals.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``Mapping``, and core's private helpers); the redundant aliases
# keep every one importable from this facade.
import ast as ast
from collections.abc import Iterator as Iterator
from collections.abc import Mapping as Mapping

from scripts.module_conventions._rule44_expressions import (
    _rule_44_bind,
    _rule_44_call_violation,
    _rule_44_scan_expression,
)
from scripts.module_conventions._rule44_names import (
    _RULE_44_ALIAS_PATHS,
    _RULE_44_SOURCE_PARTS,
    RULE_44_MEMBERSHIP_APP,
    RULE_44_MEMBERSHIP_MODEL,
    RULE_44_MEMBERSHIP_SOURCE,
    RULE_44_QUERY_METHODS,
    _Rule44DeferredBodies,
    _Rule44Environment,
    _Rule44Scope,
    _rule_44_argument_names,
    _rule_44_block_bindings,
    _rule_44_bound_names,
    _rule_44_definition_expressions,
    _rule_44_expression_bindings,
    _rule_44_membership_receiver,
    _rule_44_names_membership_model,
    _rule_44_pattern_names,
    _rule_44_qualified_membership,
    _rule_44_scope_declarations,
)
from scripts.module_conventions._rule44_statements import (
    _rule_44_scan_block,
    _rule_44_scan_function,
    _rule_44_scan_statement,
)
from scripts.module_conventions.core import (
    Corpus,
)
from scripts.module_conventions.core import (
    _attribute_chain as _attribute_chain,
)
from scripts.module_conventions.core import (
    _bound_names as _bound_names,
)
from scripts.module_conventions.core import (
    _call_func_name as _call_func_name,
)
from scripts.module_conventions.core import (
    _keyword as _keyword,
)
from scripts.module_conventions.core import (
    _literal as _literal,
)
from scripts.module_conventions.core import (
    _parse as _parse,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "RULE_44_MEMBERSHIP_APP",
    "RULE_44_MEMBERSHIP_MODEL",
    "RULE_44_MEMBERSHIP_SOURCE",
    "RULE_44_QUERY_METHODS",
    "_RULE_44_ALIAS_PATHS",
    "_RULE_44_SOURCE_PARTS",
    "_Rule44DeferredBodies",
    "_Rule44Environment",
    "_Rule44Scope",
    "_rule_44_argument_names",
    "_rule_44_bind",
    "_rule_44_block_bindings",
    "_rule_44_bound_names",
    "_rule_44_call_violation",
    "_rule_44_definition_expressions",
    "_rule_44_expression_bindings",
    "_rule_44_membership_receiver",
    "_rule_44_names_membership_model",
    "_rule_44_pattern_names",
    "_rule_44_qualified_membership",
    "_rule_44_scan_block",
    "_rule_44_scan_expression",
    "_rule_44_scan_function",
    "_rule_44_scan_statement",
    "_rule_44_scope_declarations",
    "rule_44_role_checks",
)


#: Rule 44's one operator escape: the public helper every module calls instead
#: of reading ``is_superuser``, and the module, file, and function that define
#: it.  The facade holds these literals because rule 37's allowlist exempts
#: only this module.
PLATFORM_OPERATOR_HELPER_MODULE = "orgs"
PLATFORM_OPERATOR_HELPER_FILE = "permissions.py"
PLATFORM_OPERATOR_HELPER_FUNCTION = "is_platform_operator"

#: Rule 44's command-only operator entry: the management-command variant of
#: ``operator_access``, referenceable only from ``management/commands/``.
COMMAND_OPERATOR_ACCESS_FUNCTION = "operator_access_for_command"


def rule_44_role_checks(corpus: Corpus) -> list[str]:
    """
    Rule 44: one org-role check; one operator escape; one command entry.

    The role-check clause: no string ``role=`` query outside orgs.  The
    operator-escape clause (proposal 54): no raw ``is_superuser`` read in
    module source outside orgs' ``is_platform_operator`` helper.  The
    command-entry clause: the command-only command variant of orgs'
    ``operator_access`` is referenced only from ``management/commands/``.
    """
    violations: list[str] = []
    for module in corpus.modules:
        if module.name == "orgs":
            continue
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            module_environment = _Rule44Environment()
            _rule_44_scan_block(
                _parse(text).body,
                module_environment,
                module_environment,
                (),
                module_environment,
                module.name,
                rel,
                violations,
            )
    violations.extend(_rule_44_operator_read_violations(corpus))
    violations.extend(_rule_44_command_helper_violations(corpus))
    return violations


def _rule_44_operator_read_violations(corpus: Corpus) -> list[str]:
    """Rule 44: only the helper reads ``is_superuser``."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            helper_file = (
                module.name == PLATFORM_OPERATOR_HELPER_MODULE
                and rel == PLATFORM_OPERATOR_HELPER_FILE
            )
            for node in _rule_44_iter_operator_reads(_parse(text), helper_file):
                violations.append(
                    f"rule 44: {module.name}: {rel}:{node.lineno} reads is_superuser "
                    f"outside {PLATFORM_OPERATOR_HELPER_MODULE}' "
                    f"{PLATFORM_OPERATOR_HELPER_FUNCTION} helper"
                )
    return violations


def _rule_44_iter_operator_reads(node: ast.AST, helper_file: bool) -> Iterator[ast.AST]:
    """Yield raw ``is_superuser`` reads, skipping the helper's own body."""
    if (
        helper_file
        and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == PLATFORM_OPERATOR_HELPER_FUNCTION
    ):
        return
    if _rule_44_reads_superuser(node):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _rule_44_iter_operator_reads(child, helper_file)


def _rule_44_reads_superuser(node: ast.AST) -> bool:
    """Return whether *node* is a raw ``is_superuser`` read."""
    if isinstance(node, ast.Attribute):
        return node.attr == "is_superuser" and isinstance(node.ctx, ast.Load)
    if isinstance(node, ast.Call) and _call_func_name(node) == "getattr":
        return len(node.args) >= 2 and _literal(node.args[1]) == "is_superuser"
    return False


def _rule_44_command_helper_violations(corpus: Corpus) -> list[str]:
    """Rule 44: the command-only operator entry stays in management commands."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            if rel.startswith("management/commands/"):
                continue
            for node in _rule_44_iter_command_helper_refs(_parse(text)):
                violations.append(
                    f"rule 44: {module.name}: {rel}:{node.lineno} references "
                    f"{COMMAND_OPERATOR_ACCESS_FUNCTION} outside management commands"
                )
    return violations


def _rule_44_iter_command_helper_refs(node: ast.AST) -> Iterator[ast.AST]:
    """Yield references to the command-only operator entry."""
    if _rule_44_references_command_helper(node):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _rule_44_iter_command_helper_refs(child)


def _rule_44_references_command_helper(node: ast.AST) -> bool:
    """
    Return whether *node* names the command-only operator entry.

    An import alias matches on either side so a renamed import
    (``import operator_access_for_command as elevate``) stays refused.
    """
    if isinstance(node, ast.alias):
        return (
            node.name.split(".")[-1] == COMMAND_OPERATOR_ACCESS_FUNCTION
            or node.asname == COMMAND_OPERATOR_ACCESS_FUNCTION
        )
    if isinstance(node, ast.Attribute):
        return node.attr == COMMAND_OPERATOR_ACCESS_FUNCTION
    return isinstance(node, ast.Name) and node.id == COMMAND_OPERATOR_ACCESS_FUNCTION
