"""Rule 3 and 10's supplied-settings guards.

Implementation detail of :mod:`quickscale_core.runtime.conventions`; that
module re-exports the public guard, so existing import paths keep working.
The guards read the project's managed settings wiring: the declared
``MODULE_SETTINGS_SCHEMA`` entries, and — wherever the ``MODULE_SETTINGS``
mapping is present — the module's manifest-projected settings, which no
module check re-tests (rule 10).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from django.conf import settings

from quickscale_core.contracts.resolvers import projected_setting_names

#: The managed-settings block ``quickscale apply`` writes and the checks read.
_SETTINGS_SCHEMA_ATTRIBUTE = "MODULE_SETTINGS_SCHEMA"


def _declared_setting_is_supplied(setting_name: str) -> bool:
    """Return whether the managed wiring supplied *setting_name*.

    In a generated project ``settings/modules.py`` contributes both the
    ``MODULE_SETTINGS`` mapping and the schema, and ``settings/base.py``
    applies the mapping; a declared setting absent from that mapping was not
    written by ``apply``, even when a base template default or a library
    default happens to define the name.  Without the managed mapping (module
    test settings, standalone configurations) the configured settings must
    explicitly set the name; Django's ``is_overridden`` distinguishes that
    from a global or third-party default.
    """
    managed = getattr(settings, "MODULE_SETTINGS", None)
    if isinstance(managed, Mapping):
        return setting_name in managed and hasattr(settings, setting_name)
    is_overridden = getattr(settings, "is_overridden", None)
    if not callable(is_overridden):
        return hasattr(settings, setting_name)
    return bool(hasattr(settings, setting_name) and is_overridden(setting_name))


def module_settings_are_supplied(module_name: str) -> bool:
    """Return whether every declared setting of *module_name* is supplied.

    Django invokes every registered system check independently, so a module's
    own check may run even when the generic settings check reported a missing
    setting.  The module check asks this helper before reading a declared
    setting: the names come from the project's ``MODULE_SETTINGS_SCHEMA``,
    never a hand-maintained list, and a missing or malformed schema reports
    ``False`` so the generic check stays the one that names the fix.  Where
    the managed ``MODULE_SETTINGS`` mapping is present, the module's
    manifest-projected settings count too, so a module check reading one of
    them stays silent while the generic check names it (rule 10).

    Args:
        module_name: The module whose declared settings are checked.

    Returns:
        ``True`` when the schema declares settings for *module_name* and every
        one of them — and, with managed wiring, every projected setting — is
        supplied; ``False`` otherwise.

    Raises:
        ValueError: when *module_name* is not a non-empty string.
    """
    if not isinstance(module_name, str) or not module_name:
        raise ValueError(
            "module_settings_are_supplied() requires a non-empty module name."
        )
    schema_all = getattr(settings, _SETTINGS_SCHEMA_ATTRIBUTE, None)
    if not isinstance(schema_all, Mapping):
        return False
    module_schema = schema_all.get(module_name)
    if not isinstance(module_schema, Mapping) or not module_schema:
        return False
    for entry in module_schema.values():
        if not isinstance(entry, Mapping):
            return False
        setting_name = entry.get("setting")
        if not isinstance(setting_name, str) or not _declared_setting_is_supplied(
            setting_name
        ):
            return False
    return not _missing_projected_settings(projected_setting_names(module_name))


def _missing_projected_settings(projected_settings: Sequence[str]) -> list[str]:
    """Return the projected settings the managed wiring does not carry.

    ``apply`` writes the projected settings and the ``MODULE_SETTINGS``
    mapping together, so a projected name absent from that mapping was not
    written by the apply that wrote the schema.  The requirement is verified
    where the managed mapping is present; without it (module test settings,
    standalone configurations) the settings module defines its own set and
    the projection is not a managed contract.
    """
    managed = getattr(settings, "MODULE_SETTINGS", None)
    if not isinstance(managed, Mapping):
        return []
    return [
        name
        for name in projected_settings
        if name not in managed or not hasattr(settings, name)
    ]
