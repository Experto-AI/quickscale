"""Manifest-declared settings schema compilation and runtime checking.

Module Conventions rule 3 fixes how a generated project's settings reach a
running site.  ``quickscale apply`` writes every declared setting into the
managed ``settings/modules.py`` together with a ``MODULE_SETTINGS_SCHEMA``
holding each setting's type and the manifest's validation rules.  At startup
the generic check in :mod:`quickscale_core.runtime` validates the settings a
project actually carries against that schema, without coercion, and refuses
startup naming the setting and the fix.

This module owns both halves of the data contract:

* :func:`compile_settings_schema` turns a loaded
  :class:`~quickscale_core.manifest.schema.ModuleManifest` into the mapping
  ``apply`` writes — option name to ``{"setting", "type", "validation"}``.
  Only mutable options participate: an immutable option has no
  ``django_setting`` and never reaches Django settings.
* :func:`collect_setting_issues` validates actual setting values against a
  compiled schema.  It reconstructs the manifest's mutable options from the
  schema and runs the same per-option validation engine ``plan`` and
  ``apply`` use, so the vocabulary cannot drift; with no declared
  normalization rules the engine is a pure check — a value of the wrong
  shape is refused, never coerced into the right one.  A list option whose
  manifest declares a ``list`` normalization rule carries that fact as
  ``list_items``, so the check runs the engine's non-scalar-item guard too —
  still without normalizing the value it validates.

:func:`load_settings_schema` is the convenience the module test settings use
to build their schema from the module's own manifest, the form rule 3 blesses
("module test settings define every declared setting; they may be generated
from the manifest").
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.option_validation import (
    OptionValidationIssue,
    collect_option_validation_issues,
    has_list_normalizer,
    setting_display_name,
    unsupported_list_items,
)
from quickscale_core.manifest.schema import ConfigOption, ModuleManifest

__all__ = [
    "collect_setting_issues",
    "compile_settings_schema",
    "load_settings_schema",
]

#: Compiled schema type: option name -> ``setting`` / ``type`` / ``validation``.
SettingsSchema = dict[str, dict[str, object]]


def compile_settings_schema(manifest: ModuleManifest) -> SettingsSchema:
    """Compile *manifest*'s mutable options into their settings schema entry.

    Every mutable option declares a ``django_setting`` (the loader refuses a
    mutable option without one), so the result carries exactly the settings a
    running project must hold.  The entry repeats the option's declared type
    and its ``validation`` block verbatim; the value-level checks the schema
    validates are the same ones ``plan`` and ``apply`` run.

    Args:
        manifest: The loaded module manifest.

    Returns:
        Option-name-keyed schema entries, sorted by option name so the
        rendered managed file is deterministic.
    """
    schema: SettingsSchema = {}
    for option_name, option in sorted(manifest.mutable_options.items()):
        django_setting = option.django_setting
        if django_setting is None:
            # A mutable option without a django_setting is refused by the
            # loader; refuse here too rather than writing an unusable entry.
            raise ValueError(
                f"Mutable option {option_name!r} of module {manifest.name!r} "
                "declares no django_setting."
            )
        entry: dict[str, object] = {
            "setting": django_setting,
            "type": option.option_type,
            "validation": dict(option.validation or {}),
        }
        if has_list_normalizer(manifest, option_name):
            # The runtime check reconstructs options without the manifest's
            # normalization rules, so the entry carries the one fact its
            # item-shape guard needs; the value itself is never normalized.
            entry["list_items"] = True
        schema[option_name] = entry
    return schema


def load_settings_schema(manifest_path: Path) -> SettingsSchema:
    """Load a ``module.yml`` path and compile its settings schema.

    The convenience module test settings use to derive their schema from the
    module's own manifest instead of hand-maintaining a copy.
    """
    return compile_settings_schema(load_manifest_from_path(manifest_path))


def collect_setting_issues(
    module_name: str,
    module_schema: Mapping[str, Mapping[str, Any]],
    values: Mapping[str, Any],
) -> list[OptionValidationIssue]:
    """Validate actual setting *values* against a compiled schema.

    Only options present in *values* are checked; a setting the project does
    not carry is the caller's concern, so every entry in *values* must be an
    option of *module_schema*.  The engine runs without the manifest's
    normalization rules, so a value of the wrong shape is refused rather than
    coerced: rule 3 requires the runtime check to validate the value a
    project actually carries.

    Args:
        module_name: The module the schema belongs to (used in messages).
        module_schema: A compiled schema for one module.
        values: Option-name-keyed values the project actually carries.

    Returns:
        Every failed constraint, in option-name order.
    """
    options: dict[str, ConfigOption] = {}
    for option_name in values:
        entry = module_schema.get(option_name)
        if entry is None:
            raise ValueError(
                f"Unknown option {option_name!r} of module {module_name!r}; "
                "every checked value must be declared in the schema."
            )
        option_type = entry.get("type")
        django_setting = entry.get("setting")
        validation = entry.get("validation")
        if not isinstance(option_type, str) or not isinstance(django_setting, str):
            raise ValueError(
                f"Malformed schema entry for option {option_name!r} of module "
                f"{module_name!r}; expected 'setting' and 'type' strings."
            )
        if not isinstance(validation, Mapping):
            raise ValueError(
                f"Malformed schema validation for option {option_name!r} of "
                f"module {module_name!r}; expected a mapping."
            )
        options[option_name] = ConfigOption(
            name=option_name,
            option_type=option_type,
            django_setting=django_setting,
            mutability="mutable",
            validation=dict(cast("Mapping[str, Any]", validation)),
        )

    manifest = ModuleManifest(
        name=module_name,
        version="",
        mutable_options=options,
    )
    issues = list(collect_option_validation_issues(manifest, dict(values)))
    for option_name, value in values.items():
        if module_schema[option_name].get("list_items") is not True:
            continue
        unsupported = unsupported_list_items(value)
        if unsupported:
            label = setting_display_name(module_name, options[option_name])
            rendered = ", ".join(str(item) for item in unsupported)
            issues.append(
                OptionValidationIssue(
                    option_name,
                    f"{label} contains unsupported items: {rendered}",
                )
            )
    return issues
