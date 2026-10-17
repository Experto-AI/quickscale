"""
Rule 12's manifest-option mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_settings`;
that module owns rule 12's orchestration and re-exports this module's names.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

from scripts.module_conventions.core import (
    SETTING_NAME_EXCEPTIONS,
    SNAKE_CASE,
    Module,
    _parse,
)
from scripts.module_conventions.url_options import check_url_normalization

OPTION_VALIDATION_KEYS = (
    "choices",
    "min",
    "max",
    "pattern",
    "not_empty",
    "required_when",
    "any_of",
    "subset_of",
    "excludes",
    "intersects",
)

OPTION_TYPES = ("string", "integer", "boolean", "list", "mapping")

#: Rule 12's key/type applicability, mirroring the loader's
#: ``VALIDATION_KEY_TYPES`` in ``quickscale_core.manifest.option_validation``:
#: a key outside its declared type's entry would check a value the engine
#: never gives it a meaningful form of.
VALIDATION_KEY_TYPES: dict[str, frozenset[str]] = {
    "choices": frozenset(OPTION_TYPES),
    "min": frozenset({"integer"}),
    "max": frozenset({"integer"}),
    "pattern": frozenset({"string"}),
    "not_empty": frozenset({"list", "string"}),
    "required_when": frozenset(OPTION_TYPES),
    "any_of": frozenset(OPTION_TYPES),
    "subset_of": frozenset({"list"}),
    "excludes": frozenset({"boolean", "integer", "string"}),
    "intersects": frozenset({"list"}),
}


def _declares_option_blocks(manifest: Mapping[str, Any]) -> bool:
    """Return whether the manifest declares both option blocks."""
    config = manifest.get("config")
    return isinstance(config, Mapping) and "mutable" in config and "immutable" in config


def _manifest_key_violations(module_name: str, manifest: Mapping[str, Any]) -> list[str]:
    """Rule 12's manifest-level keys: dependencies present, implies retired."""
    violations: list[str] = []
    if "dependencies" not in manifest:
        violations.append(f"rule 12: {module_name}: manifest has no dependencies key")
    if "implies" in manifest:
        violations.append(f"rule 12: {module_name}: retired implies key present")
    return violations


def _contains_key(node: Any, key: str) -> bool:
    if isinstance(node, Mapping):
        if key in node:
            return True
        return any(_contains_key(value, key) for value in node.values())
    if isinstance(node, list):
        return any(_contains_key(item, key) for item in node)
    return False


def _option_schema_violations(module: Module, kind: str, key: Any, option: Any) -> list[str]:
    """Rule 12's clauses for one manifest option, in their pre-split order."""
    prefix = f"rule 12: {module.name}: option {key!r}"
    if not isinstance(key, str) or not SNAKE_CASE.match(key):
        return [f"{prefix} is not snake_case"]
    if not isinstance(option, Mapping):
        return [f"{prefix} must be a mapping"]
    violations = _option_field_violations(prefix, option)
    _option_setting_violations(module, kind, key, option, prefix, violations)
    check_url_normalization(module, key, option, violations)
    return violations


def _option_field_violations(prefix: str, option: Mapping[str, Any]) -> list[str]:
    """Rule 12: an option's type, default, description, and validation keys."""
    violations: list[str] = []
    if option.get("type") not in OPTION_TYPES:
        violations.append(f"{prefix} has type {option.get('type')!r}")
    if "default" not in option:
        violations.append(f"{prefix} has no default")
    if not str(option.get("description", "")).strip():
        violations.append(f"{prefix} has no description")
    validation = option.get("validation")
    if validation not in (None, {}):
        if not isinstance(validation, Mapping):
            violations.append(f"{prefix} validation must be a mapping")
        else:
            for rule_key in validation:
                if rule_key not in OPTION_VALIDATION_KEYS:
                    violations.append(f"{prefix} uses unsupported validation key {rule_key!r}")
            violations.extend(_validation_type_violations(prefix, option, validation))
    return violations


def _validation_type_violations(
    prefix: str, option: Mapping[str, Any], validation: Mapping[str, Any]
) -> list[str]:
    """Rule 12: every validation key applies to the option's declared type."""
    option_type = option.get("type")
    if option_type not in OPTION_TYPES:
        return []
    return [
        f"{prefix} uses validation key {rule_key!r} on a {option_type} option"
        for rule_key in validation
        if rule_key in VALIDATION_KEY_TYPES and option_type not in VALIDATION_KEY_TYPES[rule_key]
    ]


def _option_setting_violations(
    module: Module,
    kind: str,
    key: str,
    option: Mapping[str, Any],
    prefix: str,
    violations: list[str],
) -> None:
    """Rule 12: an option's ``django_setting`` mapping, exceptions included."""
    setting = option.get("django_setting")
    if kind == "mutable" and setting is None:
        violations.append(f"{prefix} is mutable but declares no django_setting")
    elif kind == "immutable" and setting is not None:
        violations.append(f"{prefix} is immutable but declares a django_setting")
    elif isinstance(setting, str):
        exception = SETTING_NAME_EXCEPTIONS.get(module.name, {}).get(key)
        if exception is not None:
            if setting != exception:
                violations.append(f"{prefix} maps to {setting}, expected {exception}")
        elif setting not in {
            f"QUICKSCALE_{key.upper()}",
            f"QUICKSCALE_{module.name.upper()}_{key.upper()}",
        }:
            violations.append(f"{prefix} maps to {setting}, expected a QUICKSCALE_ suffix")
        if key.startswith(f"{module.name}_"):
            violations.append(f"{prefix} repeats the module name")


#: Rule 12's adapter clause: adapter code evaluates the manifest's declared
#: validation, so a compiled pattern in ``adapter.py`` is refused (coherence
#: proposal 55).
_ADAPTER_FILE = "adapter.py"

_RE_MODULE = "re"

_RE_COMPILE_NAME = "compile"


def _re_bindings(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """
    Return the names bound to the ``re`` module and to its ``compile``.

    The import spellings an adapter could compile a pattern with are gathered
    from the import statements: ``import re [as <alias>]`` binds the module and
    ``from re import compile [as <alias>]`` binds the function, so neither an
    alias nor a direct import slips past the ban.  A later rebinding of an
    imported name (``compiled = re.compile``) or a star import stays outside
    this static scan's scope; no shipped adapter uses either.
    """
    module_names: set[str] = set()
    compile_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _RE_MODULE:
                    module_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == _RE_MODULE:
            for alias in node.names:
                if alias.name == _RE_COMPILE_NAME:
                    compile_names.add(alias.asname or alias.name)
    return frozenset(module_names), frozenset(compile_names)


def _compiled_pattern_lines(tree: ast.Module) -> list[int]:
    """Return the source lines of ``re.compile`` calls in *tree*."""
    module_names, compile_names = _re_bindings(tree)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in compile_names:
                lines.append(node.lineno)
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == _RE_COMPILE_NAME
            and isinstance(func.value, ast.Name)
            and func.value.id in module_names
        ):
            lines.append(node.lineno)
    return sorted(lines)


def _adapter_pattern_compilation_violations(module: Module) -> list[str]:
    """Rule 12: ``adapter.py`` compiles no pattern of its own."""
    source = module.files.get(_ADAPTER_FILE)
    if not source:
        return []
    return [
        f"rule 12: {module.name}: {_ADAPTER_FILE}:{line}: compiles a pattern with "
        "re.compile instead of evaluating the manifest's declared validation"
        for line in _compiled_pattern_lines(_parse(source))
    ]


#: Rule 32's adapter clause (coherence proposal 55): a module declares its DRF
#: throttle scopes in its manifest's ``throttle_scopes`` projection, so a
#: ``DEFAULT_THROTTLE_RATES`` literal in ``adapter.py`` is refused.
_DEFAULT_THROTTLE_RATES_LITERAL = "DEFAULT_THROTTLE_RATES"


def _default_throttle_rates_literal_lines(tree: ast.Module) -> list[int]:
    """
    Return the source lines of ``DEFAULT_THROTTLE_RATES`` string literals.

    The literal is looked up as a string constant, so both the bare key and
    the ``REST_FRAMEWORK`` sub-key spelling are caught.  A name computed at
    runtime (a concatenation, a ``getattr``) stays outside this static scan's
    scope; no shipped adapter uses one.
    """
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == _DEFAULT_THROTTLE_RATES_LITERAL
    )


def _adapter_default_throttle_rates_violations(module: Module) -> list[str]:
    """Rule 32: ``adapter.py`` writes no ``DEFAULT_THROTTLE_RATES`` literal."""
    source = module.files.get(_ADAPTER_FILE)
    if not source:
        return []
    return [
        f"rule 12: {module.name}: {_ADAPTER_FILE}:{line}: writes a "
        "DEFAULT_THROTTLE_RATES literal instead of declaring the module's "
        "throttle_scopes in its manifest"
        for line in _default_throttle_rates_literal_lines(_parse(source))
    ]
