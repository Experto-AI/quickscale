"""
Redaction and replacement-value rules: the anonymization handlers' matchers.

Rules 47 and 48 (Module Conventions, SA245) scope to the five
``_anonymization.py`` handler files.  Rule 47 rejects a module-local identity
matcher — a substring substitution and a module-level complete-address
pattern — and rule 48 rejects a locally spelled replacement sentinel and a
handler entry point that is not ``_anonymization.anonymize_account``.  The
detectors are open-world heuristics: they catch the shapes the convention
forbids, not every possible evasion.

The mechanics live in the private sibling (``_redaction_handlers``); this
module orchestrates rules 47 and 48 and re-exports every moved name so
existing import paths and the rule registry keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast`` and core's private helpers); the redundant aliases keep every one
# importable from this facade.
import ast as ast

from scripts.module_conventions._redaction_handlers import (
    _ADDRESS_SENTINEL_END,
    _ADDRESS_SENTINEL_START,
    _ANONYMIZATION_FILE,
    _ENTITY_TERMINATOR,
    _NAME_SENTINEL,
    _compiled_address_pattern,
    _dotted_name,
    _entry_point_violations,
    _literal_skeleton,
    _matcher_violations,
    _sentinel_violations,
)
from scripts.module_conventions.core import (
    Corpus,
)
from scripts.module_conventions.core import (
    Module as Module,
)
from scripts.module_conventions.core import (
    _docstring_nodes as _docstring_nodes,
)
from scripts.module_conventions.core import (
    _parse as _parse,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "_ADDRESS_SENTINEL_END",
    "_ADDRESS_SENTINEL_START",
    "_ANONYMIZATION_FILE",
    "_ENTITY_TERMINATOR",
    "_NAME_SENTINEL",
    "_compiled_address_pattern",
    "_dotted_name",
    "_entry_point_violations",
    "_literal_skeleton",
    "_sentinel_violations",
    "rule_47_redaction",
    "rule_48_replacement_values",
)


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
        violations.extend(_matcher_violations(module))
    return violations


def rule_48_replacement_values(corpus: Corpus) -> list[str]:
    """
    Rule 48: one set of replacement values and one handler entry-point name.

    A handler that removes identity from stored text or payloads writes core's
    ``DELETED_ADDRESS(pk)`` for an address and core's ``REDACTED`` for a name or
    username, and every handler's private entry point is
    ``_anonymization.anonymize_account``, which the app config delegates to.
    """
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(_sentinel_violations(module))
        violations.extend(_entry_point_violations(module))
    return violations
