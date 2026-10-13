"""
Checks/errors, email, notification person-link, and stub-exemption rules.

The mechanics live in private sibling modules (``_misc_flow``,
``_misc_ready``, ``_misc_checks``, ``_misc_rules``); this module orchestrates
rule 10's per-module findings and re-exports every moved name so existing
import paths and the rule registry keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``tomllib``, ``Mapping``, ``Corpus``, and core's private helpers);
# the redundant aliases keep every one importable from this facade.
import ast as ast
import tomllib as tomllib
from collections.abc import Mapping as Mapping

from scripts.module_conventions._misc_checks import (
    _BUILTIN_EXCEPTION_BASES,
    _base_is_exception,
    _base_origin,
    _base_origins,
    _declares_module_error,
    _expected_error_base,
    _import_bindings,
    _module_rule_10_violations,
)
from scripts.module_conventions._misc_flow import (
    _calls_within,
    _collect_direct_calls,
    _contains_break,
    _contains_continue,
    _contains_jump,
    _direct_calls,
    _effective_cases,
    _match_exhaustive,
    _may_fall_through,
    _statements_terminate,
)
from scripts.module_conventions._misc_ready import (
    _ready_registration_order,
    _ready_scope_signature_calls,
    _registration_reachable,
)
from scripts.module_conventions._misc_rules import (
    _mapping_key_writes,
    rule_20_email,
    rule_45_stub_exemptions,
    rule_50_notification_links,
)
from scripts.module_conventions.core import (
    Corpus,
)
from scripts.module_conventions.core import (
    _call_func_name as _call_func_name,
)
from scripts.module_conventions.core import (
    _class_names as _class_names,
)
from scripts.module_conventions.core import (
    _parse as _parse,
)
from scripts.module_conventions.core import (
    _static_truth as _static_truth,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "_BUILTIN_EXCEPTION_BASES",
    "_base_is_exception",
    "_base_origin",
    "_base_origins",
    "_calls_within",
    "_collect_direct_calls",
    "_contains_break",
    "_contains_continue",
    "_contains_jump",
    "_declares_module_error",
    "_direct_calls",
    "_effective_cases",
    "_expected_error_base",
    "_import_bindings",
    "_mapping_key_writes",
    "_match_exhaustive",
    "_may_fall_through",
    "_ready_registration_order",
    "_ready_scope_signature_calls",
    "_registration_reachable",
    "_statements_terminate",
    "rule_10_checks_errors",
    "rule_20_email",
    "rule_45_stub_exemptions",
    "rule_50_notification_links",
)


def rule_10_checks_errors(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(_module_rule_10_violations(module))
    return violations
