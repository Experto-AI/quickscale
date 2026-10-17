"""
Package structure rules: public surface, files, signals, commands, tooling.

The mechanics live in private sibling modules (``_package_surfaces``,
``_package_legacy``, ``_package_commands``, ``_package_services``,
``_package_files``, ``_package_pyproject``); this module orchestrates rules 4,
6, 17, and 23 and re-exports every moved name so existing import paths and the
rule registry keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``tomllib``, ``Mapping``, ``Path``, ``Any``, and core's helpers);
# the redundant aliases keep every one importable from this facade.
import ast as ast
import tomllib as tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any as Any

from scripts.module_conventions._package_capabilities import (
    CORE_CONVENTIONS_RELATIVE_PATH as CORE_CONVENTIONS_RELATIVE_PATH,
)
from scripts.module_conventions._package_capabilities import (
    DJANGO_APP_CONFIG_MEMBERS as DJANGO_APP_CONFIG_MEMBERS,
)
from scripts.module_conventions._package_capabilities import (
    capability_declaration_findings,
    core_capabilities,
    named_hook_names,
)
from scripts.module_conventions._package_commands import (
    CONFIRM_COMMAND_KEYWORDS,
    DESTRUCTIVE_OPERATION_WORDS,
    ORGANIZATION_SELECTOR_FLAG,
    _command_findings,
    _command_flags,
    _constant_string,
    _literal_strings,
)
from scripts.module_conventions._package_files import (
    RULE_11_ONE_OFF_FILES,
    RULE_11_REQUIRED_FILES,
    RULE_11_REQUIRED_ROOT_FILES,
    RULE_11_REQUIRED_TESTS,
    _has_tenant_model,
    rule_11_package_files,
    rule_15_package_root,
    rule_16_signals,
    rule_18_package_tooling,
)
from scripts.module_conventions._package_legacy import (
    RETIRED_SETTINGS_NAME,
    _all_option_keys,
    _manifest_retired_settings,
    _mapping_entries,
    _module_legacy_findings,
    _retired_declaration_keys,
    _retired_name_reads,
    _setting_relist_findings,
    _settings_attribute_names,
)
from scripts.module_conventions._package_services import (
    _module_bindings,
    _service_declarations,
    _service_functions,
    _service_usage_findings,
)
from scripts.module_conventions._package_surfaces import (
    _capability_arguments,
    _file_surface_violations,
    _module_member_bindings,
    _module_string_constants,
    _private_member_accesses,
    _public_surface,
)
from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES as MODULE_ABSTRACT_BASES,
)
from scripts.module_conventions.core import (
    MODULE_IMPORT_PREFIX as MODULE_IMPORT_PREFIX,
)
from scripts.module_conventions.core import (
    ORG_PUBLIC_SURFACE as ORG_PUBLIC_SURFACE,
)
from scripts.module_conventions.core import (
    Corpus,
    _parse,
)
from scripts.module_conventions.core import (
    Module as Module,
)
from scripts.module_conventions.core import (
    _ancestors as _ancestors,
)
from scripts.module_conventions.core import (
    _attribute_chain as _attribute_chain,
)
from scripts.module_conventions.core import (
    _call_func_name as _call_func_name,
)
from scripts.module_conventions.core import (
    _class_names as _class_names,
)
from scripts.module_conventions.core import (
    _cross_module_imports as _cross_module_imports,
)
from scripts.module_conventions.core import (
    _declared_exports as _declared_exports,
)
from scripts.module_conventions.core import (
    _docstring_nodes as _docstring_nodes,
)
from scripts.module_conventions.core import (
    _is_settings_receiver as _is_settings_receiver,
)
from scripts.module_conventions.core import (
    _keyword as _keyword,
)
from scripts.module_conventions.core import (
    _model_classes as _model_classes,
)
from scripts.module_conventions.core import (
    _module_target as _module_target,
)
from scripts.module_conventions.core import (
    _service_module_bindings as _service_module_bindings,
)
from scripts.module_conventions.core import (
    _setting_name_module as _setting_name_module,
)
from scripts.module_conventions.core import (
    _settings_attribute_reads as _settings_attribute_reads,
)
from scripts.module_conventions.core import (
    _settings_bindings as _settings_bindings,
)
from scripts.module_conventions.core import (
    _string_assignments as _string_assignments,
)
from scripts.module_conventions.core import (
    _string_list as _string_list,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "CONFIRM_COMMAND_KEYWORDS",
    "CORE_CONVENTIONS_RELATIVE_PATH",
    "DESTRUCTIVE_OPERATION_WORDS",
    "DJANGO_APP_CONFIG_MEMBERS",
    "ORGANIZATION_SELECTOR_FLAG",
    "RETIRED_SETTINGS_NAME",
    "RULE_11_ONE_OFF_FILES",
    "RULE_11_REQUIRED_FILES",
    "RULE_11_REQUIRED_ROOT_FILES",
    "RULE_11_REQUIRED_TESTS",
    "_all_option_keys",
    "_capability_arguments",
    "_command_flags",
    "_constant_string",
    "_has_tenant_model",
    "_literal_strings",
    "_manifest_retired_settings",
    "_mapping_entries",
    "_module_bindings",
    "_module_member_bindings",
    "_module_string_constants",
    "_private_member_accesses",
    "_public_surface",
    "_retired_declaration_keys",
    "_service_functions",
    "_settings_attribute_names",
    "capability_declaration_findings",
    "core_capabilities",
    "named_hook_names",
    "rule_11_package_files",
    "rule_15_package_root",
    "rule_16_signals",
    "rule_17_management_commands",
    "rule_18_package_tooling",
    "rule_23_service_surface",
    "rule_4_public_surface",
    "rule_6_no_legacy_names",
)


def rule_4_public_surface(corpus: Corpus) -> list[str]:
    """
    Enforce the public-surface and capability-vocabulary rules (rule 4).

    The capability vocabulary is core's own ``CAPABILITIES``, parsed
    fail-closed: an unreadable declaration is reported as such instead of
    reading every collected or declared name as unknown.  Each module's
    ``AppConfig`` declarations are checked against it, then every package file
    for the surface, setting, and app-config-walk clauses.
    """
    try:
        capabilities = core_capabilities(corpus.core_conventions_text)
    except ValueError as exc:
        return [f"rule 4: core CAPABILITIES unreadable: {exc}"]
    named_hooks = named_hook_names(corpus)
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(capability_declaration_findings(module, capabilities, named_hooks))
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            violations.extend(_file_surface_violations(module, rel, text, capabilities))
    return violations


def rule_6_no_legacy_names(corpus: Corpus) -> list[str]:
    """
    Rule 6: renames are refusals, not aliases.

    The statically checkable clauses: no shipped manifest authors a
    ``legacy_aliases`` entry (the loader refuses authoring; the
    derivation-schema ``LegacyKeyAlias`` type stays a retained API), a retired
    option key is not also accepted as a live option, retired setting names
    live in the manifest (never a Python ``RETIRED_SETTINGS`` mapping), a
    module's declared retired setting names are read nowhere in shipped source
    outside their refusal declaration, and a module's ``checks.py`` reads its
    setting names from the manifest projection instead of re-listing them.
    """
    violations: list[str] = []
    retired: set[str] = set()
    for module in corpus.modules:
        retired.update(_manifest_retired_settings(module))
        violations.extend(_module_legacy_findings(module))
        violations.extend(_setting_relist_findings(module))
    if not retired:
        return violations
    populations: list[tuple[str, Mapping[str, str]]] = [
        (f"{module.name}: ", module.files) for module in corpus.modules
    ]
    populations.append(("core ", corpus.core_files))
    populations.append(("cli ", corpus.cli_files))
    violations.extend(_retired_name_reads(populations, retired))
    return violations


def rule_17_management_commands(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.startswith("management/commands/") or not rel.endswith(".py"):
                continue
            command = Path(rel).stem
            if command == "__init__" or command.startswith("_"):
                # Django discovers commands as non-underscore modules in the
                # commands package, so a private support module is not a command.
                continue
            violations.extend(_command_findings(module.name, command, _parse(text)))
    return violations


def rule_23_service_surface(corpus: Corpus) -> list[str]:
    """services.py declares __all__, and its public functions take a subject (rule 23)."""
    violations: list[str] = []
    exports: dict[str, set[str]] = {}
    for module in corpus.modules:
        module_violations, declared = _service_declarations(module)
        violations.extend(module_violations)
        if declared is not None:
            exports[module.name] = declared
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            violations.extend(_service_usage_findings(module, rel, _parse(text), exports))
    return violations
