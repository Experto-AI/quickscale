"""
README content rule.

The mechanics live in the private sibling (``_docs_readme``); this module
orchestrates rule 38 and re-exports every moved name so existing import paths
and the rule registry keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``re``, ``Mapping``, ``Path``, and core's types); the redundant aliases keep
# every one importable from this facade.
import re as re
from collections.abc import Mapping as Mapping
from pathlib import Path as Path

from scripts.module_conventions._docs_readme import (
    _ORG_ROLE_TOKENS,
    _ROLE_LISTING,
    _ROLE_TABLE_HEADER,
    _ROLE_TABLE_VALUE,
    _lists_role_requirement,
    _readme_violations,
    _uses_org_roles,
)
from scripts.module_conventions.core import (
    Corpus,
)
from scripts.module_conventions.core import (
    Module as Module,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "_ORG_ROLE_TOKENS",
    "_ROLE_LISTING",
    "_ROLE_TABLE_HEADER",
    "_ROLE_TABLE_VALUE",
    "_lists_role_requirement",
    "_uses_org_roles",
    "rule_38_readme_content",
)


def rule_38_readme_content(corpus: Corpus) -> list[str]:
    """
    Rule 38: each module's README carries the required sections and their facts.

    The README names the seven required level-two headings in order, carries
    no versioned heading, names every manifest option, every management command,
    and every flag each command declares, and — when the module authorizes
    through orgs' role tools — lists the minimum role in its public surface.
    """
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(_readme_violations(module))
    return violations
