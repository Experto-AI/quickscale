"""Shared manifest resolution surface for QuickScale module options.

Owns the manifest loader every option consumer shares
(``load_module_manifest_with_fallback``), the one generic resolver
non-adapter callers use (``resolve_manifest_module_options``), and the
names-only projection a module's startup check reads
(``projected_setting_names``).  A module's
option defaults, normalization, and validation live in its ``module.yml``;
adapter code resolves through the manifest engine via
``quickscale_core.runtime.build_generic_manifest_spec``.  SA217 removed the last
per-module option functions from this surface.  A supplied key the manifest
declares retired is refused with the manifest's message before anything is
resolved, so a retired name is never silently ignored.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    build_schema_from_manifest,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config
from quickscale_core.manifest.resolver_derived import _ENV_VAR_SETTING_SUFFIX

from quickscale_core.contracts.module_discovery import (
    resolve_manifest_base_path,
)


def load_module_manifest_with_fallback(module_name: str) -> Any:
    """Load a shipped module's ``module.yml``, source tree first.

    Follows the AF7 discovery contract established by SA109/SA113/SA111a: read
    from the maintainer monorepo's ``quickscale_modules/`` workspace when it is
    present, and fall back to the bundled manifest snapshots shipped inside the
    ``quickscale_core`` wheel when it is not (installed-wheel context).

    Fail-hard is preserved: when neither source resolves, the underlying
    ``ImproperlyConfigured``/load error propagates rather than yielding a
    silently empty or defaulted manifest.
    """
    return load_manifest_from_path(
        resolve_manifest_base_path() / module_name / "module.yml"
    )


def raise_for_retired_options(manifest: Any, options: Mapping[str, Any]) -> None:
    """Refuse a supplied key the manifest declares retired.

    ``retired_options`` is the one home of a retired key's refusal; resolving
    fails closed with the authored message instead of silently dropping the
    key, matching the sanitize and validation layers.  The non-adapter resolver
    here calls this guard; the adapter entry point enforces the same refusal
    with the module layer's ``ManifestError``.
    """
    retired = sorted(name for name in manifest.retired_options if name in options)
    if not retired:
        return
    from quickscale_core.schema.config_schema import ConfigValidationError

    raise ConfigValidationError(manifest.retired_options[retired[0]])


def resolve_manifest_module_options(
    module_name: str,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one module's declared option values through the manifest engine.

    The manifest owns the defaults, normalization rules, and validation; this
    is the one path non-adapter callers use to read resolved values (module
    adapters use ``quickscale_core.runtime.build_generic_manifest_spec``).
    Declared normalization rules are applied, so the returned mapping carries
    the manifest's canonical forms.  A supplied retired key and a resolution
    issue (an executable projection whose value cannot be represented) each
    fail closed with the manifest's own message.
    """
    manifest = load_module_manifest_with_fallback(module_name)
    supplied = dict(options or {})
    raise_for_retired_options(manifest, supplied)
    schema = build_schema_from_manifest(
        manifest_name=module_name,
        wiring_projections=manifest.wiring_projections,
        derived_settings=manifest.derived_settings,
        option_derivations=manifest.option_derivations,
        version="1",
    )
    result = resolve_module_config(manifest, schema, overrides=supplied)
    if result.validation_issues:
        from quickscale_core.schema.config_schema import ConfigValidationError

        raise ConfigValidationError(result.validation_issues[0])
    return dict(result.resolved)


def projected_setting_names(module_name: str) -> tuple[str, ...]:
    """Return the setting names ``apply`` projects beyond a module's options.

    The generic settings check requires these names wherever the managed
    ``MODULE_SETTINGS`` wiring is present, so no module check re-lists or
    re-tests them (Module Conventions rules 6 and 10): the manifest is the one
    home, and a renamed setting is renamed once, in ``module.yml``.  The
    projection is names-only and reads the module's shipped manifest through
    the same fallback as the other readers here — source tree first, bundled
    snapshot second:

    * every mapped option whose Django setting ends in ``_ENV_VAR``
      contributes its suffix-stripped secret setting (rule 35);
    * every explicitly derived setting contributes its ``setting_key``, except
      a ``computed`` derivation gated by ``when`` or ``omit_if_blank``, whose
      write depends on resolved option values this names-only projection does
      not read;
    * a name a mutable option's own ``django_setting`` already covers is left
      out: the generic settings check (rule 3) validates it, so listing it
      here would re-list a setting that check owns.

    Args:
        module_name: The module whose manifest projection is read.

    Returns:
        The projected setting names, sorted and without duplicates.

    Raises:
        ValueError: when *module_name* is not a non-empty string.
    """
    if not isinstance(module_name, str) or not module_name:
        raise ValueError("projected_setting_names() requires a non-empty module name.")
    manifest = load_module_manifest_with_fallback(module_name)
    schema = build_schema_from_manifest(
        manifest_name=module_name,
        wiring_projections=manifest.wiring_projections,
        derived_settings=manifest.derived_settings,
        option_derivations=manifest.option_derivations,
        version="1",
    )
    declared = set(manifest.get_django_settings_mapping().values())
    projected = {
        setting_key[: -len(_ENV_VAR_SETTING_SUFFIX)]
        for setting_key in declared
        if setting_key.endswith(_ENV_VAR_SETTING_SUFFIX)
    }
    projected.discard("")
    for setting in schema.get_all_derived_settings():
        if setting.setting_key and not _derivation_is_conditional(setting):
            projected.add(setting.setting_key)
    return tuple(sorted(projected - declared))


def _derivation_is_conditional(setting: DerivedSetting) -> bool:
    """Return whether *setting*'s derivation is gated on resolved option values.

    Mirrors the skip the value projection applies when it evaluates a
    ``computed`` setting against resolved values: one gated by ``when`` or
    ``omit_if_blank`` may not be written, so a names-only presence check must
    not require it.
    """
    if setting.derivation_type != "computed":
        return False
    expression = setting.expression
    return bool(expression.get("when")) or bool(expression.get("omit_if_blank"))


__all__ = [
    "load_module_manifest_with_fallback",
    "projected_setting_names",
    "raise_for_retired_options",
    "resolve_manifest_module_options",
]
