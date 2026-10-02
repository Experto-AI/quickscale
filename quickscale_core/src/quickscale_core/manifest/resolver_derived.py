"""Derived Django-settings projection for the manifest-driven resolver.

Split out of :mod:`quickscale_core.manifest.resolver`; the resolver facade
re-exports these helpers so existing imports keep working.  This module owns
the projection of ``DerivedSetting`` declarations into Django settings.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    ModuleDerivationSchema,
)
from quickscale_core.manifest.resolver_expressions import (
    _select_conditional_value,
)
from quickscale_core.manifest.schema import ModuleManifest


def _derive_static_setting(setting: DerivedSetting, resolved: dict[str, Any]) -> Any:
    """Return the ``static`` derivation's constant value (or its default)."""
    return setting.expression.get("value", setting.default)


def _derive_direct_setting(setting: DerivedSetting, resolved: dict[str, Any]) -> Any:
    """Return the ``direct`` derivation's option value, or its default."""
    option_key = setting.expression.get("option")
    if option_key and option_key in resolved:
        value = resolved[option_key]
        return value if value is not None else setting.default
    return setting.default


def _derive_conditional_setting(
    setting: DerivedSetting, resolved: dict[str, Any]
) -> Any:
    """Return the first matching ``conditional`` branch, or the default."""
    return _select_conditional_value(
        setting.expression, setting.source_options, resolved, setting.default
    )


def _derive_computed_setting(setting: DerivedSetting, resolved: dict[str, Any]) -> Any:
    """Render the ``computed`` derivation's template, or return the default."""
    template = setting.expression.get("template", "")
    if template:
        try:
            # Build a safe substitution context from resolved values
            context = {k: str(v) if v is not None else "" for k, v in resolved.items()}
            return template.format(**context)
        except KeyError, IndexError, ValueError, AttributeError:
            return setting.default
    return setting.default


_DERIVED_SETTING_HANDLERS: dict[
    str, Callable[[DerivedSetting, dict[str, Any]], Any]
] = {
    "static": _derive_static_setting,
    "direct": _derive_direct_setting,
    "conditional": _derive_conditional_setting,
    "computed": _derive_computed_setting,
}


def _project_derived_setting(setting: DerivedSetting, resolved: dict[str, Any]) -> Any:
    """Compute the value for a single derived Django setting.

    Args:
        setting: The derived setting declaration.
        resolved: The fully resolved option values.

    Returns:
        The computed setting value.
    """
    handler = _DERIVED_SETTING_HANDLERS.get(setting.derivation_type)
    if handler is None:
        # Unknown derivation type: return default
        return setting.default
    return handler(setting, resolved)


def _project_all_derived_settings(
    manifest: ModuleManifest,
    derivation_schema: ModuleDerivationSchema,
    resolved: dict[str, Any],
) -> dict[str, Any]:
    """Project manifest settings, then apply explicit derivations.

    Every mutable manifest option with a ``django_setting`` contributes a
    direct baseline value.  Explicit ``DerivedSetting`` declarations are
    applied afterward so an adapter can intentionally transform or supplement
    that baseline without dropping settings that have no explicit derivation.

    Args:
        manifest: The manifest declaring the mutable option-to-setting map.
        derivation_schema: The module's derivation schema.
        resolved: The fully resolved option values.

    Returns:
        A mapping of Django setting keys to their computed values.
    """
    result = {
        setting_key: resolved[option_key]
        for option_key, setting_key in manifest.get_django_settings_mapping().items()
    }
    all_settings = derivation_schema.get_all_derived_settings()

    for setting in all_settings:
        result[setting.setting_key] = _project_derived_setting(setting, resolved)

    return result
