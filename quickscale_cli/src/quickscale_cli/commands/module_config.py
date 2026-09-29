"""Desired-option configuration functions for QuickScale modules.

This module collects and normalizes desired module options. Module manifests and
module-owned adapters define wiring specifications; callers invoke the central
managed-wiring manager for operational work.
"""

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Mapping

import click

from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest.option_validation import validate_module_options
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
) -> None:
    """Abort with actionable messaging when a manifest-owned config is invalid."""
    issues = validate_module_options(manifest, dict(config), supplied=dict(config))
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
    defaults = normalize_module_option_values(
        manifest, _declared_config(manifest, existing_config)
    )

    if non_interactive:
        click.echo(f"\n⚙️  Using default {module_name} module configuration...")
        for option in manifest.get_all_options().values():
            click.echo(
                f"  • {option.description or option.name}: {defaults[option.name]}"
            )
        _raise_for_invalid_manifest_config(module_name, manifest, defaults)
        return defaults

    click.echo(f"\n⚙️  Configuring {module_name} module...")
    config = normalize_module_option_values(
        manifest,
        {
            option_name: _prompt_for_manifest_option(option, defaults[option_name])
            for option_name, option in manifest.get_all_options().items()
        },
    )
    _raise_for_invalid_manifest_config(module_name, manifest, config)
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
    """Build the canonical module configurator registry.

    Centralising registration here keeps the manifest-backed surface in one
    place.
    """
    entries: list[ModuleConfigurator] = [
        ModuleConfigurator(
            name="auth",
            configure=partial(configure_module_from_manifest, "auth"),
            get_defaults=partial(default_module_config_from_manifest, "auth"),
        ),
        ModuleConfigurator(
            name="blog",
            configure=partial(configure_module_from_manifest, "blog"),
            get_defaults=partial(default_module_config_from_manifest, "blog"),
        ),
        ModuleConfigurator(
            name="crm",
            configure=partial(configure_module_from_manifest, "crm"),
            get_defaults=partial(default_module_config_from_manifest, "crm"),
        ),
        ModuleConfigurator(
            name="forms",
            configure=partial(configure_module_from_manifest, "forms"),
            get_defaults=partial(default_module_config_from_manifest, "forms"),
        ),
        ModuleConfigurator(
            name="listings",
            configure=partial(configure_module_from_manifest, "listings"),
            get_defaults=partial(default_module_config_from_manifest, "listings"),
        ),
        ModuleConfigurator(
            name="storage",
            configure=partial(configure_module_from_manifest, "storage"),
            get_defaults=partial(default_module_config_from_manifest, "storage"),
        ),
        ModuleConfigurator(
            name="backups",
            configure=partial(configure_module_from_manifest, "backups"),
            get_defaults=partial(default_module_config_from_manifest, "backups"),
        ),
        ModuleConfigurator(
            name="billing",
            configure=partial(configure_module_from_manifest, "billing"),
            get_defaults=partial(default_module_config_from_manifest, "billing"),
        ),
        ModuleConfigurator(
            name="notifications",
            configure=partial(configure_module_from_manifest, "notifications"),
            get_defaults=partial(default_module_config_from_manifest, "notifications"),
        ),
        ModuleConfigurator(
            name="orgs",
            configure=partial(configure_module_from_manifest, "orgs"),
            get_defaults=partial(default_module_config_from_manifest, "orgs"),
        ),
        ModuleConfigurator(
            name="analytics",
            configure=partial(configure_module_from_manifest, "analytics"),
            get_defaults=partial(default_module_config_from_manifest, "analytics"),
        ),
        ModuleConfigurator(
            name="social",
            configure=partial(configure_module_from_manifest, "social"),
            get_defaults=partial(default_module_config_from_manifest, "social"),
        ),
    ]
    return {entry.name: entry for entry in entries}


MODULE_CONFIGURATOR_REGISTRY: dict[str, ModuleConfigurator] = (
    _build_configurator_registry()
)


def get_module_configurator(module_name: str) -> ModuleConfigurator | None:
    """Return the configurator entry for *module_name*, or ``None``."""
    return MODULE_CONFIGURATOR_REGISTRY.get(module_name)


def get_configurator_module_names() -> list[str]:
    """Return the sorted list of modules that have a registered configurator."""
    return sorted(MODULE_CONFIGURATOR_REGISTRY)
