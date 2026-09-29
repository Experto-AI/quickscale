"""Desired-option configuration functions for QuickScale modules.

This module collects and normalizes desired module options. Module manifests and
module-owned adapters define wiring specifications; callers invoke the central
managed-wiring manager for operational work.
"""

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Mapping

import click

from quickscale_core.contracts.module_options import (
    DEFAULT_NOTIFICATIONS_ALLOWED_TAGS,
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_LAYOUT_VARIANTS,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.contracts.resolvers import (
    default_notifications_module_options,
    resolve_notifications_module_options,
    validate_notifications_module_options,
    default_social_module_options,
    resolve_social_module_options,
    validate_social_module_options,
)
from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest.option_validation import validate_module_options
from quickscale_core.manifest.resolver import normalize_module_option_values


def _format_tag_list(tags: list[str] | tuple[str, ...]) -> str:
    """Return a comma-separated prompt string for provider-visible tags."""
    return ", ".join(tags)


def _parse_notification_tag_input(raw_value: str, field_name: str) -> list[str]:
    """Normalize comma-separated notification tags using the shared contract."""
    normalized = resolve_notifications_module_options({field_name: raw_value})
    return list(normalized[field_name])


# ============================================================================
# NOTIFICATIONS MODULE CONFIGURATION
# ============================================================================


def get_default_notifications_config() -> dict[str, Any]:
    """Return default configuration for the notifications module."""
    return default_notifications_module_options()


def _raise_for_invalid_notifications_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when notifications config is invalid."""
    issues = validate_notifications_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid notifications module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_notifications_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure notifications module settings interactively or with defaults."""
    defaults = resolve_notifications_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default notifications module configuration...")
        click.echo(
            f"  • Sender: {defaults['sender_name']} <{defaults['sender_email']}>"
        )
        click.echo("  • Live delivery: configure later (console-safe by default)")
        click.echo("  • Webhook signing: configure later")
        _raise_for_invalid_notifications_config(defaults)
        return defaults

    click.echo("\n⚙️  Configuring notifications module...")
    click.echo(
        "Notifications remain console-safe by default. Configure a verified Resend "
        "domain only when you want live delivery to take ownership of email settings.\n"
    )

    enabled = click.confirm(
        "Enable the notifications runtime?",
        default=bool(defaults["enabled"]),
    )
    sender_name = click.prompt(
        "Sender display name",
        default=str(defaults["sender_name"]),
    ).strip()
    sender_email = click.prompt(
        "Sender email address",
        default=str(defaults["sender_email"]),
    ).strip()
    reply_to_email = click.prompt(
        "Reply-to email address (leave blank to reuse sender)",
        default=str(defaults["reply_to_email"]),
        show_default=bool(defaults["reply_to_email"]),
    ).strip()

    configure_live_delivery_now = enabled and click.confirm(
        "Configure live Resend delivery now?",
        default=bool(defaults["resend_domain"]),
    )
    if configure_live_delivery_now:
        resend_domain = click.prompt(
            "Verified Resend sending domain",
            default=str(defaults["resend_domain"]),
            show_default=bool(defaults["resend_domain"]),
        ).strip()
        resend_api_key_env_var = click.prompt(
            "Resend API key environment variable",
            default=(
                str(defaults[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION]).strip()
                or DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
            ),
            show_default=True,
        ).strip()
    else:
        resend_domain = ""
        resend_api_key_env_var = (
            str(defaults[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION]).strip()
            or DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
        )

    configure_webhooks_now = enabled and click.confirm(
        "Configure webhook signing now?",
        default=bool(defaults[NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION]),
    )
    if configure_webhooks_now:
        webhook_secret_env_var = click.prompt(
            "Webhook secret environment variable",
            default=(
                str(defaults[NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION]).strip()
                or DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR
            ),
            show_default=True,
        ).strip()
    else:
        webhook_secret_env_var = ""

    allowed_tags = _parse_notification_tag_input(
        click.prompt(
            "Allowed provider-visible tags (comma-separated)",
            default=_format_tag_list(
                list(defaults.get("allowed_tags", DEFAULT_NOTIFICATIONS_ALLOWED_TAGS))
            ),
            show_default=True,
        ),
        "allowed_tags",
    )
    default_tags = _parse_notification_tag_input(
        click.prompt(
            "Default provider-visible tags (comma-separated)",
            default=_format_tag_list(list(defaults.get("default_tags", []))),
            show_default=True,
        ),
        "default_tags",
    )
    webhook_ttl_seconds = click.prompt(
        "Webhook timestamp tolerance in seconds",
        type=int,
        default=int(defaults["webhook_ttl_seconds"]),
    )

    config = resolve_notifications_module_options(
        {
            "enabled": enabled,
            "sender_name": sender_name,
            "sender_email": sender_email,
            "reply_to_email": reply_to_email,
            "resend_domain": resend_domain,
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: resend_api_key_env_var,
            NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION: webhook_secret_env_var,
            "default_tags": default_tags,
            "allowed_tags": allowed_tags,
            "webhook_ttl_seconds": webhook_ttl_seconds,
        }
    )
    _raise_for_invalid_notifications_config(config)
    return config


# ============================================================================
# SOCIAL MODULE CONFIGURATION
# ============================================================================


def get_default_social_config() -> dict[str, Any]:
    """Return default configuration for the social module."""
    return default_social_module_options()


def _raise_for_invalid_social_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when social config is invalid."""
    issues = validate_social_module_options(dict(config))
    if not issues:
        return

    click.secho("\n❌ Invalid social module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_social_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure social module settings interactively or with defaults."""
    defaults = resolve_social_module_options(dict(existing_config or {}))

    if non_interactive:
        click.echo("\n⚙️  Using default social module configuration...")
        click.echo(
            "  • Link tree: "
            + ("Enabled" if defaults["link_tree_enabled"] else "Disabled")
            + f" ({SOCIAL_LINK_TREE_PATH})"
        )
        click.echo(
            "  • Embeds: "
            + ("Enabled" if defaults["embeds_enabled"] else "Disabled")
            + f" ({SOCIAL_EMBEDS_PATH})"
        )
        click.echo("  • Providers: " + ", ".join(defaults["provider_allowlist"]))
        _raise_for_invalid_social_config(defaults)
        return defaults

    click.echo("\n⚙️  Configuring social module...")
    click.echo(
        "Social keeps a managed backend transport plus canonical public paths. "
        "Fresh showcase_react generations keep the Django-owned public pages at "
        f"{SOCIAL_LINK_TREE_PATH} and {SOCIAL_EMBEDS_PATH}, while existing "
        "generated projects require manual theme adoption.\n"
    )

    config = resolve_social_module_options(
        {
            "link_tree_enabled": click.confirm(
                f"Enable the fixed {SOCIAL_LINK_TREE_PATH} public surface?",
                default=bool(defaults["link_tree_enabled"]),
            ),
            "layout_variant": click.prompt(
                "Default link-tree layout variant",
                type=click.Choice(list(SOCIAL_LAYOUT_VARIANTS), case_sensitive=False),
                default=str(defaults["layout_variant"]),
                show_choices=True,
            ).lower(),
            "embeds_enabled": click.confirm(
                f"Enable the fixed {SOCIAL_EMBEDS_PATH} public surface?",
                default=bool(defaults["embeds_enabled"]),
            ),
            "provider_allowlist": click.prompt(
                "Allowlisted providers (comma-separated)",
                default=", ".join(defaults["provider_allowlist"]),
                show_default=True,
            ),
            "cache_ttl_seconds": click.prompt(
                "Cache TTL in seconds",
                type=int,
                default=int(defaults["cache_ttl_seconds"]),
            ),
            "links_per_page": click.prompt(
                "Links per page",
                type=int,
                default=int(defaults["links_per_page"]),
            ),
            "embeds_per_page": click.prompt(
                "Embeds per page",
                type=int,
                default=int(defaults["embeds_per_page"]),
            ),
        }
    )

    _raise_for_invalid_social_config(config)
    return config


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
    when it is a closed set), and the collected values go through the same
    option-validation engine ``plan`` and ``apply`` use, so a wrong type or a
    violated cross-option rule names the setting before it is written.  The
    returned values are the manifest's canonical forms, so what the caller
    writes to ``quickscale.yml`` is what the engine and the wiring see.
    """
    manifest = load_module_manifest_with_fallback(module_name)
    _raise_for_retired_existing_config(module_name, manifest, existing_config)
    defaults = _declared_config(manifest, existing_config)

    if non_interactive:
        click.echo(f"\n⚙️  Using default {module_name} module configuration...")
        for option in manifest.get_all_options().values():
            click.echo(
                f"  • {option.description or option.name}: {defaults[option.name]}"
            )
        _raise_for_invalid_manifest_config(module_name, manifest, defaults)
        return normalize_module_option_values(manifest, defaults)

    click.echo(f"\n⚙️  Configuring {module_name} module...")
    config = {
        option_name: _prompt_for_manifest_option(option, defaults[option_name])
        for option_name, option in manifest.get_all_options().items()
    }
    _raise_for_invalid_manifest_config(module_name, manifest, config)
    return normalize_module_option_values(manifest, config)


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
            configure=configure_notifications_module,
            get_defaults=get_default_notifications_config,
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
            configure=configure_social_module,
            get_defaults=get_default_social_config,
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
