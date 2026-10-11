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
from quickscale_core.module_wiring import _QS_ENV_PREFIX

#: Django-setting suffix marking a mapped option as holding the *name* of an
#: environment variable rather than a value (Module Conventions rule 12's
#: ``_ENV_VAR`` vocabulary, enforced by rule 35).  A mapped option with this
#: suffix keeps its name setting and gains the suffix-stripped secret setting.
_ENV_VAR_SETTING_SUFFIX = "_ENV_VAR"


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


def _deferred_secret_setting_value(env_var_name: Any) -> str:
    """Return the deferred secret projection for one mapped ``_ENV_VAR`` option.

    A nonblank validated name becomes the ``__QS_ENV__:<name>`` reference the
    renderer later resolves through ``os.environ.get``; a blank name becomes
    the literal empty string, never a dangling reference.  Only the
    environment-variable *name* the option declares is projected — resolution
    never reads or persists credential material.
    """
    name = "" if env_var_name is None else str(env_var_name).strip()
    if not name:
        return ""
    return f"{_QS_ENV_PREFIX}{name}"


def _project_env_var_secret_settings(
    manifest: ModuleManifest, resolved: dict[str, Any]
) -> dict[str, Any]:
    """Project each mapped ``_ENV_VAR`` option's suffix-stripped secret setting.

    A manifest option whose mapped ``django_setting`` ends in ``_ENV_VAR``
    declares the *name* of an environment variable holding a secret, so it
    keeps its name setting and gains the suffix-stripped secret setting the
    reference belongs in.  A stripped name the direct baseline already claims
    — another option's setting — is left untouched: that mapping is explicit,
    and a module whose runtime reads a differently named secret setting
    declares that setting itself.

    Args:
        manifest: The manifest declaring the option-to-setting map.
        resolved: The fully resolved option values.

    Returns:
        A mapping of suffix-stripped secret setting names to deferred
        ``__QS_ENV__`` references (or the literal empty string for a blank
        name).
    """
    secrets: dict[str, Any] = {}
    for option_key, setting_key in manifest.get_django_settings_mapping().items():
        if not setting_key.endswith(_ENV_VAR_SETTING_SUFFIX):
            continue
        secret_key = setting_key[: -len(_ENV_VAR_SETTING_SUFFIX)]
        if not secret_key or secret_key in secrets:
            continue
        secrets[secret_key] = _deferred_secret_setting_value(resolved.get(option_key))
    return secrets


def _project_all_derived_settings(
    manifest: ModuleManifest,
    derivation_schema: ModuleDerivationSchema,
    resolved: dict[str, Any],
) -> dict[str, Any]:
    """Project manifest settings, then apply explicit derivations.

    Every mutable manifest option with a ``django_setting`` contributes a
    direct baseline value.  A mapped option whose setting ends in
    ``_ENV_VAR`` additionally contributes the suffix-stripped secret setting
    (rule 35).  Explicit ``DerivedSetting`` declarations are applied afterward
    so an adapter can intentionally transform or supplement that baseline
    without dropping settings that have no explicit derivation.

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
    for secret_key, secret_value in _project_env_var_secret_settings(
        manifest, resolved
    ).items():
        result.setdefault(secret_key, secret_value)
    all_settings = derivation_schema.get_all_derived_settings()

    for setting in all_settings:
        if setting.derivation_type == "computed":
            expression = setting.expression
            if any(
                resolved.get(key) not in values
                for key, values in expression.get("when", {}).items()
            ):
                continue
            if any(
                resolved.get(key) == "" for key in expression.get("omit_if_blank", [])
            ):
                continue
        result[setting.setting_key] = _project_derived_setting(setting, resolved)

    return result
