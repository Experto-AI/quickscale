"""
Settings rules: names, reads, manifest options, snapshots, and optional senders.

The mechanics live in private sibling modules (``_settings_names``,
``_settings_reads``, ``_settings_manifest``, ``_settings_snapshots``,
``_settings_senders``); this module orchestrates rules 1, 3, 12, 42, and 43,
and re-exports every moved name so existing import paths and the rule registry
keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``re``, ``Mapping``, ``Any``, and core's helpers); the redundant
# aliases keep every one importable from this facade.
import ast as ast
import re as re
from collections.abc import Mapping
from typing import Any as Any

from scripts.module_conventions._settings_core_templates import (
    rule_30_settings_composition,
)
from scripts.module_conventions._settings_manifest import (
    OPTION_TYPES,
    OPTION_VALIDATION_KEYS,
    _adapter_default_throttle_rates_violations,
    _adapter_pattern_compilation_violations,
    _contains_key,
    _declares_option_blocks,
    _derived_consumer_violations,
    _manifest_key_violations,
    _option_schema_violations,
)
from scripts.module_conventions._settings_names import (
    ENV_VAR_NAME,
    SETTING_SUFFIX_TYPES,
    _check_vendor_default,
    _enabled_switch_violations,
    _option_name_violations,
    _settings_options,
)
from scripts.module_conventions._settings_reads import (
    _declared_settings,
    _duplicated_default_violations,
    _manifest_declared_settings,
    _module_level_targets,
    _option_settings,
    _read_violations,
    _tests_settings_violations,
)
from scripts.module_conventions._settings_senders import (
    _RULE_43_SETTINGS_ATTRIBUTE,
    _attribute_binding_module,
    _broad_except_violations,
    _call_other_module_service,
    _cross_attribute_violations,
    _getattr_service_owner,
    _guard_call_violations,
    _guarded_module_name,
    _import_module_service_bindings,
    _other_module_service_imports,
    _reference_module_name,
)
from scripts.module_conventions._settings_snapshots import (
    _COERCION_BUILTINS,
    _RULE_42_EXPORTED_SNAPSHOT,
    _call_builds_settings_snapshot,
    _class_defines_from_settings,
    _intra_module_import_names,
    _is_direct_setting_read,
    _returns_settings_snapshot,
    _settings_snapshot_names,
    _snapshot_scan_violations,
)
from scripts.module_conventions.core import (
    CREDENTIAL_REFERENCE_NAMES as CREDENTIAL_REFERENCE_NAMES,
)
from scripts.module_conventions.core import (
    ENV_VAR_NAME_PATTERN as ENV_VAR_NAME_PATTERN,
)
from scripts.module_conventions.core import (
    MODULE_IMPORT_PREFIX as MODULE_IMPORT_PREFIX,
)
from scripts.module_conventions.core import (
    MODULE_LAYERS as MODULE_LAYERS,
)
from scripts.module_conventions.core import (
    QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS,
    Corpus,
    _credential_reference_options,
    _parse,
    _required_modules,
    _service_module_bindings,
    _string_assignments,
)
from scripts.module_conventions.core import (
    SETTING_NAME_EXCEPTIONS as SETTING_NAME_EXCEPTIONS,
)
from scripts.module_conventions.core import (
    SNAKE_CASE as SNAKE_CASE,
)
from scripts.module_conventions.core import (
    VENDOR_CREDENTIAL_DEFAULTS as VENDOR_CREDENTIAL_DEFAULTS,
)
from scripts.module_conventions.core import (
    Module as Module,
)
from scripts.module_conventions.core import (
    _attribute_chain as _attribute_chain,
)
from scripts.module_conventions.core import (
    _body_nodes as _body_nodes,
)
from scripts.module_conventions.core import (
    _bound_names as _bound_names,
)
from scripts.module_conventions.core import (
    _call_func_name as _call_func_name,
)
from scripts.module_conventions.core import (
    _declared_exports as _declared_exports,
)
from scripts.module_conventions.core import (
    _is_settings_receiver as _is_settings_receiver,
)
from scripts.module_conventions.core import (
    _keyword as _keyword,
)
from scripts.module_conventions.core import (
    _module_target as _module_target,
)
from scripts.module_conventions.core import (
    _scope_nodes as _scope_nodes,
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
from scripts.module_conventions.url_options import (
    check_url_normalization as check_url_normalization,
)

# Rule 23's listed exception: analytics' services are best-effort and never
# raise to callers, so a caller may tolerate any failure while using them.
# The module-name table stays in this rule-37-exempt facade and is passed into
# the private sibling's scan.
_RULE_43_BEST_EFFORT_MODULES = frozenset({"analytics"})

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "ENV_VAR_NAME",
    "OPTION_TYPES",
    "OPTION_VALIDATION_KEYS",
    "SETTING_SUFFIX_TYPES",
    "_COERCION_BUILTINS",
    "_RULE_42_EXPORTED_SNAPSHOT",
    "_RULE_43_BEST_EFFORT_MODULES",
    "_RULE_43_SETTINGS_ATTRIBUTE",
    "_adapter_default_throttle_rates_violations",
    "_attribute_binding_module",
    "_call_builds_settings_snapshot",
    "_call_other_module_service",
    "_check_vendor_default",
    "_class_defines_from_settings",
    "_contains_key",
    "_declared_settings",
    "_getattr_service_owner",
    "_guarded_module_name",
    "_import_module_service_bindings",
    "_intra_module_import_names",
    "_is_direct_setting_read",
    "_manifest_declared_settings",
    "_module_level_targets",
    "_option_settings",
    "_other_module_service_imports",
    "_reference_module_name",
    "_returns_settings_snapshot",
    "_settings_snapshot_names",
    "rule_12_manifest_options",
    "rule_1_settings_names",
    "rule_30_settings_composition",
    "rule_3_settings_reads",
    "rule_42_settings_snapshots",
    "rule_43_optional_senders",
)


# ---------------------------------------------------------------------------
# Rule detectors
# ---------------------------------------------------------------------------


def rule_1_settings_names(corpus: Corpus) -> list[str]:
    """
    Rule 1: the setting family, the enabled switch, and env-var options.

    The statically checkable clauses: every module declares its enabled switch
    as ``QUICKSCALE_<MODULE>_ENABLED`` (boolean); every first-party setting
    carries the ``QUICKSCALE_<MODULE>_`` stem, the listed third-party
    exceptions excepted; every standard suffix keeps its fixed type; an
    ``_env_var`` option's default is an environment-variable name, and a
    QuickScale-defined one carries the module stem (rule 35's projection).

    SA263 adds the credential-default clauses: a credential reference option's
    default is either the controlled vocabulary's vendor name or one of the
    per-option authorized QuickScale names, and an operator's own name stays
    allowed — the rule fixes the convention default, never the override.
    """
    violations: list[str] = []
    for module in corpus.modules:
        options = _settings_options(module)
        prefix = f"QUICKSCALE_{module.name.upper()}_"
        approved = QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS.get(module.name, {})
        credential_options = _credential_reference_options(module)
        violations.extend(_enabled_switch_violations(module.name, prefix, options))
        for key, option in options.items():
            if not isinstance(key, str) or not isinstance(option, Mapping):
                continue
            violations.extend(
                _option_name_violations(
                    module.name, key, option, prefix, approved, credential_options
                )
            )
    return violations


def rule_3_settings_reads(corpus: Corpus) -> list[str]:
    """
    Rule 3: reads go to the module's own declared settings, directly.

    The statically checkable clauses: module code reads only settings its
    manifest (or its own adapter) declares, never another module's setting,
    and reads no setting through ``getattr(settings, ...)``; the module's
    ``tests/settings.py`` defines every manifest option's setting.  An
    option's default lives only in the manifest, so a module-source
    ``*DEFAULT*`` constant, function default, or ``or`` fallback that repeats
    one is a second home (coherence proposal 12).
    """
    violations: list[str] = []
    for module in corpus.modules:
        declared = _declared_settings(module)
        violations.extend(_tests_settings_violations(module))
        violations.extend(_read_violations(module, declared))
        violations.extend(_duplicated_default_violations(module))
    return violations


def rule_12_manifest_options(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        # The adapter clauses are checked for every module, whatever shape its
        # manifest is in: adapter code evaluates the declared validation and
        # writes no throttle-rate literal of its own.
        violations.extend(_adapter_pattern_compilation_violations(module))
        violations.extend(_adapter_default_throttle_rates_violations(module))
        manifest = module.manifest
        if not _declares_option_blocks(manifest):
            violations.append(f"rule 12: {module.name}: config must declare mutable and immutable")
            continue
        violations.extend(_manifest_key_violations(module.name, manifest))
        for kind in ("mutable", "immutable"):
            options = manifest["config"].get(kind)
            if not isinstance(options, Mapping):
                violations.append(f"rule 12: {module.name}: config.{kind} must be a mapping")
                continue
            for key, option in options.items():
                violations.extend(_option_schema_violations(module, kind, key, option))
        violations.extend(_derived_consumer_violations(corpus, module))
        # ``frontend_resources`` declares API response shapes, so a payload
        # field may legitimately be named ``validation_rules``; the retired-key
        # rule governs manifest authoring, not the generated frontend contract.
        authoring = {key: value for key, value in manifest.items() if key != "frontend_resources"}
        if _contains_key(authoring, "validation_rules"):
            violations.append(f"rule 12: {module.name}: manifest declares retired validation_rules")
    return violations


def rule_42_settings_snapshots(corpus: Corpus) -> list[str]:
    """Rule 42: a settings snapshot lives only in the private ``_settings.py``."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            violations.extend(_snapshot_scan_violations(module, rel, _parse(text)))
    return violations


def rule_43_optional_senders(corpus: Corpus) -> list[str]:
    """Rule 43: senders guard per ``required_modules`` and one error base."""
    violations: list[str] = []
    for module in corpus.modules:
        required = _required_modules(module)
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            service_bindings = _service_module_bindings(tree)
            import_module_bindings = _import_module_service_bindings(tree)
            service_names = _other_module_service_imports(tree, module.name)
            constants = _string_assignments(tree)
            violations.extend(
                _guard_call_violations(
                    module,
                    rel,
                    tree,
                    required,
                    service_names,
                    service_bindings,
                    import_module_bindings,
                    constants,
                )
            )
            violations.extend(
                _cross_attribute_violations(
                    module, rel, tree, service_bindings, import_module_bindings
                )
            )
            violations.extend(
                _broad_except_violations(
                    module,
                    rel,
                    tree,
                    service_names,
                    service_bindings,
                    import_module_bindings,
                    _RULE_43_BEST_EFFORT_MODULES,
                )
            )
    return violations
