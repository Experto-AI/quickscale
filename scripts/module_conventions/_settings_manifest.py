"""
Rule 12's manifest-option mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_settings`;
that module owns rule 12's orchestration and re-exports this module's names.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scripts.module_conventions.core import (
    SETTING_NAME_EXCEPTIONS,
    SNAKE_CASE,
    Module,
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
    return violations


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
