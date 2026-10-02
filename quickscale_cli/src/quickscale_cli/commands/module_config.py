"""Desired-option configuration functions for QuickScale modules.

This module collects and normalizes desired module options. Module manifests and
module-owned adapters define wiring specifications; callers invoke the central
managed-wiring manager for operational work.
"""

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Mapping

import click

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)
from quickscale_core.manifest.resolver import normalize_module_option_values


# ============================================================================
# MANIFEST-DRIVEN MODULE CONFIGURATION
# ============================================================================


def _declared_config(
    manifest: Any,
    existing_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge manifest defaults with the existing values the manifest declares."""
    merged = dict(manifest.get_defaults())
    for option_name, value in dict(existing_config or {}).items():
        if option_name in merged:
            merged[option_name] = value
    return merged


def default_module_config_from_manifest(module_name: str) -> dict[str, Any]:
    """Return a module's manifest-declared option defaults.

    This is the non-interactive default factory for every module whose
    desired-option configuration the manifest owns.
    """
    return dict(load_module_manifest_with_fallback(module_name).get_defaults())


def _is_blank_stored_value(value: Any) -> bool:
    """Return whether a stored option value counts as unset for prompting."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return not value
    return False


def _prompt_for_manifest_option(option: Any, current: Any) -> Any:
    """Prompt once for one manifest-declared option, by its declared shape.

    The prompt's default is the stored value when it carries one, else the
    option's declared default, so a blank stored value never hides the
    conventional value the manifest declares (storage's credential-variable
    names on a local-to-cloud reconfiguration, for example).
    """
    description = option.description or option.name
    validation = option.validation or {}
    fallback = option.default if _is_blank_stored_value(current) else current

    if option.option_type == "boolean":
        return click.confirm(description, default=bool(fallback))

    if option.option_type == "integer":
        return click.prompt(description, type=int, default=int(fallback))

    choices = validation.get("choices")
    if option.option_type == "string" and isinstance(choices, list) and choices:
        return click.prompt(
            description,
            type=click.Choice(
                [str(choice) for choice in choices], case_sensitive=False
            ),
            default=str(fallback),
            show_choices=True,
        )

    if option.option_type == "list":
        rendered = click.prompt(
            description,
            default=", ".join(str(value) for value in fallback or []),
            show_default=bool(fallback),
        )
        return [part.strip() for part in rendered.split(",") if part.strip()]

    return click.prompt(description, default=str(fallback), show_default=bool(fallback))


def _raise_for_invalid_manifest_config(
    module_name: str,
    manifest: Any,
    config: Mapping[str, Any],
    *,
    supplied: Mapping[str, Any] | None = None,
) -> None:
    """Abort with actionable messaging when a manifest-owned config is invalid.

    *supplied* carries the values as they were authored, before the manifest's
    normalization, so the declared type is judged on what the caller entered (a
    comma string for a list option is an accepted spelling) rather than only on
    its canonical form; it defaults to *config*.
    """
    issues = validate_module_options(
        manifest,
        dict(config),
        supplied=dict(config if supplied is None else supplied),
    )
    if not issues:
        return

    click.secho(f"\n❌ Invalid {module_name} module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def _raise_for_retired_existing_config(
    module_name: str,
    manifest: Any,
    existing_config: Mapping[str, Any] | None,
) -> None:
    """Abort when *existing_config* still carries a retired option key.

    ``_declared_config`` drops undeclared names so a newer manifest can shed
    options; a key the manifest *declares retired* is refused here instead, so
    reconfiguring a project never silently discards it.
    """
    retired_supplied = sorted(
        key for key in dict(existing_config or {}) if key in manifest.retired_options
    )
    if not retired_supplied:
        return

    click.secho(f"\n❌ Invalid {module_name} module configuration:", fg="red", err=True)
    for key in retired_supplied:
        click.echo(f"  • {manifest.retired_options[key]}", err=True)
    raise click.Abort()


def _drop_invalid_existing(
    module_name: str,
    manifest: Any,
    existing: Mapping[str, Any],
) -> dict[str, Any]:
    """Drop stored values the manifest refuses before they seed a prompt.

    An unsupported stored shape (a mapping where a list is required) must not
    be rendered as a prompt default and accepted back as a valid-looking list;
    the affected option falls back to its manifest default, the issues are
    surfaced, and the user can still enter a replacement.
    """
    issues = collect_option_validation_issues(
        manifest, dict(existing), supplied=dict(existing)
    )
    if not issues:
        return dict(existing)
    click.secho(
        f"\n⚠️  Existing {module_name} configuration has invalid values; "
        "the affected options fall back to their manifest defaults.",
        fg="yellow",
        err=True,
    )
    for issue in issues:
        click.echo(f"  • {issue.message}", err=True)
    invalid_options = {issue.option_name for issue in issues}
    return {
        name: value for name, value in existing.items() if name not in invalid_options
    }


def configure_module_from_manifest(
    module_name: str,
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure a module from the options its ``module.yml`` declares.

    The manifest owns the prompt set, the defaults, and the validation: each
    option is prompted by its declared ``type`` (and its declared ``choices``
    when it is a closed set), the collected values are put through the
    manifest's declared normalization, and the canonical values then go through
    the same option-validation engine ``plan`` and ``apply`` use, so a wrong
    type or a violated cross-option rule names the setting before it is
    written.  The returned values are the manifest's canonical forms, so what
    the caller writes to ``quickscale.yml`` is what the engine and the wiring
    see.
    """
    manifest = load_module_manifest_with_fallback(module_name)
    _raise_for_retired_existing_config(module_name, manifest, existing_config)
    existing = _declared_config(manifest, existing_config)

    if non_interactive:
        defaults = normalize_module_option_values(manifest, existing)
        click.echo(f"\n⚙️  Using default {module_name} module configuration...")
        for option in manifest.get_all_options().values():
            click.echo(
                f"  • {option.description or option.name}: {defaults[option.name]}"
            )
        _raise_for_invalid_manifest_config(
            module_name, manifest, defaults, supplied=existing
        )
        return defaults

    existing = _drop_invalid_existing(module_name, manifest, existing)
    defaults = normalize_module_option_values(manifest, existing)

    click.echo(f"\n⚙️  Configuring {module_name} module...")
    collected = {
        option_name: _prompt_for_manifest_option(option, defaults[option_name])
        for option_name, option in manifest.get_all_options().items()
    }
    config = normalize_module_option_values(manifest, collected)
    _raise_for_invalid_manifest_config(
        module_name, manifest, config, supplied=collected
    )
    return config


# ============================================================================
# MODULE CONFIGURATORS REGISTRY
# ============================================================================


@dataclass(frozen=True)
class ModuleConfigurator:
    """Manifest-backed configurator entry for a single module.

    Each entry wraps the module's desired-option configurator and an optional
    non-interactive default factory. Operational wiring is owned by manifests
    and module adapters and is invoked through the central manager.

    Attributes:
        name: Canonical module identifier (e.g. ``"auth"``).
        configure: Interactive or non-interactive configurator callable.
            Signature: ``(non_interactive=False, existing_config=None) -> dict``.
        get_defaults: Optional factory returning the module's non-interactive
            default option dictionary.
    """

    name: str
    configure: Callable[..., dict[str, Any]]
    get_defaults: Callable[[], dict[str, Any]] | None = None


def _build_configurator_registry() -> dict[str, ModuleConfigurator]:
    """Build the canonical module configurator registry from the declared catalog.

    Every declared module configures through its manifest, so the registry
    derives from core's declared release inventory (Module Conventions rule 37's
    allowed exception, kept equal to discovery by the catalog consistency test)
    instead of a hand-written module list.  The static catalog is read at
    import without filesystem discovery (decisions.md: no import-time discovery),
    and the manifest-backed surface stays centralised here.
    """
    return {
        entry.name: ModuleConfigurator(
            name=entry.name,
            configure=partial(configure_module_from_manifest, entry.name),
            get_defaults=partial(default_module_config_from_manifest, entry.name),
        )
        for entry in MODULE_CATALOG
    }


MODULE_CONFIGURATOR_REGISTRY: dict[str, ModuleConfigurator] = (
    _build_configurator_registry()
)


def get_module_configurator(module_name: str) -> ModuleConfigurator | None:
    """Return the configurator entry for *module_name*, or ``None``."""
    return MODULE_CONFIGURATOR_REGISTRY.get(module_name)


def get_configurator_module_names() -> list[str]:
    """Return the sorted list of modules that have a registered configurator."""
    return sorted(MODULE_CONFIGURATOR_REGISTRY)
