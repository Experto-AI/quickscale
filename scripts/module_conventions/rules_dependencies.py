"""
Dependency, secret, type-check, and module-dependency rules.

The mechanics live in private sibling modules (``_dependencies_layers``,
``_dependencies_secrets``, ``_dependencies_manifests``,
``_dependencies_typecheck``); this module orchestrates the four detectors and
re-exports every moved name so existing import paths and the rule registry
keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``configparser``, ``os``, ``re``, ``tomllib``, ``Any``, and core's
# helpers); the redundant aliases keep every one importable from this facade.
import ast as ast
import configparser
import os as os
import re as re
import tomllib as tomllib
from typing import Any as Any

from scripts.module_conventions._dependencies_layers import (
    _core_module_setting_findings,
    _module_layer_findings,
    conventions_layer_table,
    layer_table_findings,
)
from scripts.module_conventions._dependencies_manifests import (
    BASE_RUNTIME_DEPENDENCY_NAMES,
    CORE_DEPENDENCY_NAME,
    DEPENDENCY_NAME_PATTERN,
    _dependency_declaration_findings,
    _dependency_value_is_usable,
    _pyproject_runtime_dependencies,
    _required_module_findings,
)
from scripts.module_conventions._dependencies_secrets import (
    CORE_RUNTIME_ROLE_ENV_VARS,
    _environ_references,
)
from scripts.module_conventions._dependencies_typecheck import (
    RULE_36_ALLOWED_DISABLED_CODES,
    RULE_36_ALLOWED_RELAXATION_KEYS,
    RULE_36_FALSE_VALUES,
    RULE_36_FORBIDDEN_SECTION_KEYS,
    RULE_36_KNOWN_EFFECTIVE_KEYS,
    RULE_36_MODULE_GLOB,
    RULE_36_RELAXED_FOLLOW_IMPORTS,
    RULE_36_RELAXED_VALUES,
    RULE_36_SECTION_TEMPLATE,
    RULE_36_TRUE_VALUES,
    _module_typecheck_findings,
    _mypy_effective_option,
    _mypy_glob_targets_module,
)
from scripts.module_conventions.core import (
    MODULE_LAYERS,
    Corpus,
    _parse,
    _same_layer_cycles,
)
from scripts.module_conventions.core import (
    SNAKE_CASE as SNAKE_CASE,
)
from scripts.module_conventions.core import (
    Module as Module,
)
from scripts.module_conventions.core import (
    _attribute_chain as _attribute_chain,
)
from scripts.module_conventions.core import (
    _cross_module_imports as _cross_module_imports,
)
from scripts.module_conventions.core import (
    _literal as _literal,
)
from scripts.module_conventions.core import (
    _setting_name_module as _setting_name_module,
)
from scripts.module_conventions.core import (
    _settings_attribute_reads as _settings_attribute_reads,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "BASE_RUNTIME_DEPENDENCY_NAMES",
    "CORE_DEPENDENCY_NAME",
    "CORE_RUNTIME_ROLE_ENV_VARS",
    "DEPENDENCY_NAME_PATTERN",
    "RULE_36_ALLOWED_DISABLED_CODES",
    "RULE_36_ALLOWED_RELAXATION_KEYS",
    "RULE_36_FALSE_VALUES",
    "RULE_36_FORBIDDEN_SECTION_KEYS",
    "RULE_36_KNOWN_EFFECTIVE_KEYS",
    "RULE_36_MODULE_GLOB",
    "RULE_36_RELAXED_FOLLOW_IMPORTS",
    "RULE_36_RELAXED_VALUES",
    "RULE_36_SECTION_TEMPLATE",
    "RULE_36_TRUE_VALUES",
    "_dependency_value_is_usable",
    "_environ_references",
    "_mypy_effective_option",
    "_mypy_glob_targets_module",
    "_pyproject_runtime_dependencies",
    "conventions_layer_table",
    "layer_table_findings",
    "rule_35_secrets",
    "rule_36_typecheck_config",
    "rule_39_module_dependencies",
    "rule_5_dependency_direction",
)


def rule_5_dependency_direction(corpus: Corpus) -> list[str]:
    """Enforce the layer table and acyclic same-layer imports (rule 5)."""
    violations: list[str] = []
    edges: dict[str, set[str]] = {}
    for module in corpus.modules:
        module_violations, same_layer = _module_layer_findings(
            module, MODULE_LAYERS.get(module.name)
        )
        violations.extend(module_violations)
        if same_layer:
            edges.setdefault(module.name, set()).update(same_layer)
    for cycle in _same_layer_cycles(edges):
        violations.append(f"rule 5: same-layer import cycle: {' -> '.join(cycle)}")
    violations.extend(_core_module_setting_findings(corpus.core_files))
    return violations


def rule_35_secrets(corpus: Corpus) -> list[str]:
    """
    Rule 35: secrets reach module code as applied settings, not os.environ.

    The statically checkable clause: module code calls neither ``os.getenv``
    nor ``os.environ``; orgs' RLS boot guard reading core's two runtime-role
    variables in ``checks.py`` is the one listed exception (it runs before
    settings load).
    """
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            for lineno, variable in _environ_references(_parse(text)):
                if (
                    module.name == "orgs"
                    and rel == "checks.py"
                    and variable in CORE_RUNTIME_ROLE_ENV_VARS
                ):
                    continue
                detail = f" ({variable})" if variable else ""
                violations.append(
                    f"rule 35: {module.name}: {rel}:{lineno} uses os.getenv/os.environ"
                    f"{detail} instead of an applied setting"
                )
    return violations


def rule_39_module_dependencies(corpus: Corpus) -> list[str]:
    """
    Rule 39: declared dependency names, and their pyproject specs (SA260).

    ``required_modules`` and ``dependencies`` are always present; both list
    bare names, the specs live in the module ``pyproject.toml``, and every
    module declares the lockstep ``quickscale-core`` dependency.
    """
    violations: list[str] = []
    known = {module.name for module in corpus.modules}
    for module in corpus.modules:
        violations.extend(_required_module_findings(module, known))
        violations.extend(_dependency_declaration_findings(module))
    return violations


def rule_36_typecheck_config(corpus: Corpus) -> list[str]:
    """Rule 36: one root mypy.ini section per module, within the allowed set."""
    violations: list[str] = []
    parser = configparser.RawConfigParser()
    if corpus.mypy_ini.strip():
        parser.read_string(corpus.mypy_ini)
    for module in corpus.modules:
        violations.extend(_module_typecheck_findings(module.name, parser))
    return violations
