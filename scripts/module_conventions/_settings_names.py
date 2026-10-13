"""
Rule 1's settings-name mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_settings`;
that module owns rule 1's orchestration and re-exports this module's names.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scripts.module_conventions.core import (
    CREDENTIAL_REFERENCE_NAMES,
    ENV_VAR_NAME_PATTERN,
    SETTING_NAME_EXCEPTIONS,
    VENDOR_CREDENTIAL_DEFAULTS,
    Module,
)

# Rule 1's fixed suffix types; every standard suffix carries the type in this
# table.  A descriptive boolean (analytics' exclude_debug) is not a suffix.
SETTING_SUFFIX_TYPES: dict[str, str] = {
    "enabled": "boolean",
    "api_enabled": "boolean",
    "per_page": "integer",
    "rate_limit": "string",
    "retention_days": "integer",
    "ttl_seconds": "integer",
    "env_var": "string",
}

ENV_VAR_NAME = ENV_VAR_NAME_PATTERN


def _settings_options(module: Module) -> dict[str, Any]:
    """Collect the manifest's mutable and immutable options, in declaration order."""
    options: dict[str, Any] = {}
    config = module.manifest.get("config")
    if isinstance(config, Mapping):
        for kind in ("mutable", "immutable"):
            block = config.get(kind)
            if isinstance(block, Mapping):
                options.update(block)
    return options


def _enabled_switch_violations(
    module_name: str, prefix: str, options: Mapping[str, Any]
) -> list[str]:
    """Rule 1's enabled-switch clause: declared as the boolean ``<PREFIX>ENABLED``."""
    enabled = options.get("enabled")
    if not isinstance(enabled, Mapping):
        return [f"rule 1: {module_name}: declares no enabled option"]
    violations: list[str] = []
    if enabled.get("type") != "boolean":
        violations.append(
            f"rule 1: {module_name}: enabled type is {enabled.get('type')!r}, expected boolean"
        )
    if enabled.get("django_setting") != f"{prefix}ENABLED":
        violations.append(
            f"rule 1: {module_name}: enabled setting is "
            f"{enabled.get('django_setting')!r}, expected {prefix}ENABLED"
        )
    return violations


def _option_name_violations(
    module_name: str,
    key: str,
    option: Mapping[str, Any],
    prefix: str,
    approved: Mapping[str, Mapping[str, str]],
    credential_options: set[str],
) -> list[str]:
    """Rule 1's per-option clauses: stem, fixed suffix type, env-var default."""
    violations: list[str] = []
    _setting_stem_violations(module_name, key, option, prefix, violations)
    _suffix_type_violations(module_name, key, option, violations)
    _env_var_default_violations(
        module_name, key, option, prefix, approved, credential_options, violations
    )
    return violations


def _setting_stem_violations(
    module_name: str,
    key: str,
    option: Mapping[str, Any],
    prefix: str,
    violations: list[str],
) -> None:
    """Rule 1: a first-party setting carries the module stem, exceptions excepted."""
    setting = option.get("django_setting")
    if isinstance(setting, str) and setting.startswith("QUICKSCALE_"):
        exception = SETTING_NAME_EXCEPTIONS.get(module_name, {}).get(key)
        if exception is None and not setting.startswith(prefix):
            violations.append(
                f"rule 1: {module_name}: option {key!r} setting {setting} lacks the {prefix} stem"
            )


def _suffix_type_violations(
    module_name: str,
    key: str,
    option: Mapping[str, Any],
    violations: list[str],
) -> None:
    """Rule 1: every standard suffix keeps its fixed type."""
    for suffix, expected_type in SETTING_SUFFIX_TYPES.items():
        if key == suffix or key.endswith(f"_{suffix}"):
            if option.get("type") != expected_type:
                violations.append(
                    f"rule 1: {module_name}: option {key!r} type is "
                    f"{option.get('type')!r}, expected {expected_type}"
                )
            break


def _env_var_default_violations(
    module_name: str,
    key: str,
    option: Mapping[str, Any],
    prefix: str,
    approved: Mapping[str, Mapping[str, str]],
    credential_options: set[str],
    violations: list[str],
) -> None:
    """Rule 1's env-var default clauses, including SA263's credential vocabulary."""
    default = option.get("default")
    if not key.endswith("_env_var"):
        return
    if not isinstance(default, str) or not ENV_VAR_NAME.match(default):
        violations.append(
            f"rule 1: {module_name}: option {key!r} default {default!r} is "
            "not an environment-variable name"
        )
    elif key in approved:
        expected = approved[key]["default"]
        if default != expected:
            violations.append(
                f"rule 1: {module_name}: option {key!r} default {default} is "
                f"authorized as {expected}; update the recorded exception to "
                "rename it"
            )
    elif key in VENDOR_CREDENTIAL_DEFAULTS.get(module_name, {}):
        _check_vendor_default(module_name, key, default, violations)
    elif default.startswith("QUICKSCALE_"):
        if not default.startswith(prefix):
            violations.append(
                f"rule 1: {module_name}: option {key!r} default {default} lacks the {prefix} stem"
            )
    elif key in credential_options:
        _check_vendor_default(module_name, key, default, violations)


def _check_vendor_default(module_name: str, key: str, default: str, violations: list[str]) -> None:
    """Refuse a credential reference default outside the controlled vocabulary."""
    expected = VENDOR_CREDENTIAL_DEFAULTS.get(module_name, {}).get(key)
    if expected is not None:
        if default != expected:
            violations.append(
                f"rule 1: {module_name}: option {key!r} default {default} must be {expected}"
            )
        return
    if default in CREDENTIAL_REFERENCE_NAMES:
        return
    approved = ", ".join(CREDENTIAL_REFERENCE_NAMES)
    violations.append(
        f"rule 1: {module_name}: option {key!r} default {default} is not in the "
        f"controlled vocabulary ({approved}); the vendor's variable name or an "
        "operator's name is required"
    )
