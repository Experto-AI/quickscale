"""
Rule 44's role-check orchestration and re-export facade.

Rule 44's mechanics live in the private siblings: ``_rule44_names`` holds the
membership-binding environment and the name-resolution helpers,
``_rule44_expressions`` the expression scanner, and ``_rule44_statements``
the statement scanner.  This module orchestrates the rule and re-exports
every moved name so existing import paths and the rule registry keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``Mapping``, and core's private helpers); the redundant aliases
# keep every one importable from this facade.
import ast as ast
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


def rule_44_role_checks(corpus: Corpus) -> list[str]:
    """Rule 44: one org-role check; no string ``role=`` query outside orgs."""
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
    return violations
