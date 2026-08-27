"""Desired-option configuration functions for QuickScale modules.

This module collects and normalizes desired module options. Module manifests and
module-owned adapters define wiring specifications; callers invoke the central
managed-wiring manager for operational work.
"""

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import click

from quickscale_core.contracts.module_options import (
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    normalize_backups_module_options,
    validate_backups_env_var_reference,
    DEFAULT_NOTIFICATIONS_ALLOWED_TAGS,
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_LAYOUT_VARIANTS,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.contracts.module_options import (
    DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
)
from quickscale_core.contracts.resolvers import (
    default_analytics_module_options,
    resolve_analytics_module_options,
    validate_analytics_module_options,
    default_forms_module_options,
    resolve_forms_module_options,
    validate_forms_module_options,
    default_billing_module_options,
    resolve_billing_module_options,
    validate_billing_module_options,
    default_auth_module_options,
    resolve_auth_module_options,
    default_crm_module_options,
    resolve_crm_module_options,
    default_notifications_module_options,
    resolve_notifications_module_options,
    validate_notifications_module_options,
    default_social_module_options,
    resolve_social_module_options,
    validate_social_module_options,
)


def _merge_existing_config(
    defaults: dict[str, Any],
    existing_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge module defaults with any existing configured values."""
    merged = dict(defaults)
    if existing_config:
        merged.update(dict(existing_config))
    return merged


def _format_tag_list(tags: list[str] | tuple[str, ...]) -> str:
    """Return a comma-separated prompt string for provider-visible tags."""
    return ", ".join(tags)


def _parse_notification_tag_input(raw_value: str, field_name: str) -> list[str]:
    """Normalize comma-separated notification tags using the shared contract."""
    normalized = resolve_notifications_module_options({field_name: raw_value})
    return list(normalized[field_name])


# ============================================================================
# AUTH MODULE CONFIGURATION
# ============================================================================


def get_default_auth_config() -> dict[str, Any]:
    """Get default configuration for auth module (non-interactive mode)"""
    return default_auth_module_options()


def configure_auth_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for auth module"""
    defaults = resolve_auth_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default auth module configuration...")
        config = defaults
        click.echo(
            "  • Registration: "
            + ("Enabled" if config["registration_enabled"] else "Disabled")
        )
        click.echo(f"  • Email verification: {config['email_verification']}")
        click.echo(f"  • Authentication: {config['authentication_method']}")
        return config

    click.echo("\n⚙️  Configuring auth module...")
    click.echo("Answer these questions to customize the authentication setup:\n")

    config = {
        "registration_enabled": click.confirm(
            "Enable user registration?",
            default=bool(defaults["registration_enabled"]),
        ),
        "email_verification": click.prompt(
            "Email verification",
            type=click.Choice(["none", "optional", "mandatory"], case_sensitive=False),
            default=str(defaults["email_verification"]),
            show_choices=True,
        ),
        "authentication_method": click.prompt(
            "Authentication method",
            type=click.Choice(["email", "username", "both"], case_sensitive=False),
            default=str(defaults["authentication_method"]),
            show_choices=True,
        ),
        "session_cookie_age": int(defaults.get("session_cookie_age", 1209600)),
    }

    return config


def _normalize_auth_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy auth config keys to manifest-aligned keys."""
    normalized = dict(config)
    if "registration_enabled" not in normalized and "allow_registration" in normalized:
        normalized["registration_enabled"] = normalized["allow_registration"]
    normalized.setdefault("registration_enabled", True)
    normalized.setdefault("email_verification", "none")
    normalized.setdefault("authentication_method", "email")
    normalized.setdefault("social_providers", [])
    normalized.setdefault("session_cookie_age", 1209600)
    return normalized


# ============================================================================
# BLOG MODULE CONFIGURATION
# ============================================================================


DEFAULT_BLOG_API_RATE_LIMIT = "5/hour"


def get_default_blog_config() -> dict[str, Any]:
    """Get default configuration for blog module (non-interactive mode)"""
    return {
        "posts_per_page": 10,
        "enable_rss": True,
        "api_rate_limit": DEFAULT_BLOG_API_RATE_LIMIT,
    }


def configure_blog_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for blog module"""
    defaults = _merge_existing_config(get_default_blog_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default blog module configuration...")
        config = defaults
        click.echo(f"  • Posts per page: {config['posts_per_page']}")
        click.echo(f"  • RSS feed: {'Enabled' if config['enable_rss'] else 'Disabled'}")
        click.echo(f"  • API rate limit: {config['api_rate_limit']}")
        return config

    click.echo("\n⚙️  Configuring blog module...")
    click.echo("The blog module will be configured with default settings.\n")

    config = {
        "posts_per_page": click.prompt(
            "Posts per page",
            type=int,
            default=int(defaults["posts_per_page"]),
        ),
        "enable_rss": click.confirm(
            "Enable RSS feed?",
            default=bool(defaults["enable_rss"]),
        ),
        "api_rate_limit": click.prompt(
            "Blog API rate limit (e.g. 5/hour, 10/minute)",
            default=str(defaults["api_rate_limit"]),
        ).strip()
        or DEFAULT_BLOG_API_RATE_LIMIT,
    }

    return config


# SA6.2: Listings no longer needs a configurator triad — its
# defaults/normalization/validation now come from module.yml's
# derivation section.  The manifest-driven path in entry_point.py
# handles the wiring directly.


# ============================================================================
# CRM MODULE CONFIGURATION
# ============================================================================


def get_default_crm_config() -> dict[str, Any]:
    """Get default configuration for CRM module (non-interactive mode)"""
    return default_crm_module_options()


def configure_crm_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for CRM module"""
    defaults = resolve_crm_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default CRM module configuration...")
        config = defaults
        click.echo("  • API: Enabled")
        click.echo(f"  • Deals per page: {config['deals_per_page']}")
        click.echo(f"  • Contacts per page: {config['contacts_per_page']}")
        return config

    click.echo("\n⚙️  Configuring CRM module...")
    click.echo(
        "The CRM module provides contact management, companies, and deal pipeline.\n"
    )

    config = resolve_crm_module_options(
        {
            "enable_api": click.confirm(
                "Enable REST API endpoints?",
                default=bool(defaults["enable_api"]),
            ),
            "deals_per_page": click.prompt(
                "Deals per page",
                type=int,
                default=int(defaults["deals_per_page"]),
            ),
            "contacts_per_page": click.prompt(
                "Contacts per page",
                type=int,
                default=int(defaults["contacts_per_page"]),
            ),
        }
    )

    return config


# ============================================================================
# FORMS MODULE CONFIGURATION
# ============================================================================


def get_default_forms_config() -> dict[str, Any]:
    """Return default configuration for the forms module."""
    return default_forms_module_options()


def _raise_for_invalid_forms_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when forms config is invalid."""
    issues = validate_forms_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid forms module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_forms_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure the forms module interactively or using defaults."""
    defaults = resolve_forms_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default forms module configuration...")
        config = defaults
        click.echo(f"  \u2022 Forms per page: {config['forms_per_page']}")
        click.echo(
            f"  \u2022 Spam protection: "
            f"{'Enabled' if config['spam_protection_enabled'] else 'Disabled'}"
        )
        click.echo(f"  \u2022 Rate limit: {config['rate_limit']}")
        click.echo(f"  \u2022 Data retention: {config['data_retention_days']} days")
        click.echo(
            f"  \u2022 Submissions API: "
            f"{'Enabled' if config['submissions_api_enabled'] else 'Disabled'}"
        )
        _raise_for_invalid_forms_config(config)
        return config

    click.echo("\n⚙️  Configuring forms module...")
    config = {
        "forms_per_page": click.prompt(
            "Submissions per page (admin)",
            type=int,
            default=int(defaults["forms_per_page"]),
        ),
        "spam_protection_enabled": click.confirm(
            "Enable honeypot spam protection?",
            default=bool(defaults["spam_protection_enabled"]),
        ),
        "rate_limit": click.prompt(
            "Rate limit for submissions (e.g. 5/hour, 10/minute)",
            default=str(defaults["rate_limit"]),
        ),
        "data_retention_days": click.prompt(
            "Data retention days (0 = keep forever)",
            type=int,
            default=int(defaults["data_retention_days"]),
        ),
        "submissions_api_enabled": click.confirm(
            "Enable REST API for admin submissions?",
            default=bool(defaults["submissions_api_enabled"]),
        ),
    }
    _raise_for_invalid_forms_config(config)
    return config


# ============================================================================
# LISTINGS MODULE CONFIGURATION
# ============================================================================


def get_default_listings_config() -> dict[str, Any]:
    """Return default configuration for the listings module."""
    return {
        "listings_per_page": 12,
    }


def configure_listings_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Interactive configuration for the listings module."""
    defaults = _merge_existing_config(get_default_listings_config(), existing_config)

    if non_interactive:
        click.echo("\n\u2699\ufe0f  Using default listings module configuration...")
        config = defaults
        click.echo(f"  \u2022 Listings per page: {config['listings_per_page']}")
        return config

    click.echo("\n\u2699\ufe0f  Configuring listings module...")
    click.echo("The listings module will be configured with default settings.\n")

    config = {
        "listings_per_page": click.prompt(
            "Listings per page",
            type=int,
            default=int(defaults["listings_per_page"]),
        ),
    }
    click.echo(f"  \u2022 Listings per page: {config['listings_per_page']}")
    return config


# ============================================================================
# STORAGE MODULE CONFIGURATION
# ============================================================================


def get_default_storage_config() -> dict[str, Any]:
    """Return default configuration for the storage module."""
    return {
        "backend": "local",
        "media_url": "/media/",
        "public_base_url": "",
        "bucket_name": "",
        "endpoint_url": "",
        "region_name": "",
        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION: DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
        "default_acl": "",
        "querystring_auth": False,
        "private_media_enabled": False,
    }


def configure_storage_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure storage module settings interactively or with defaults."""
    defaults = _merge_existing_config(get_default_storage_config(), existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default storage module configuration...")
        config = defaults
        click.echo(f"  • Backend: {config['backend']}")
        click.echo(f"  • Media URL: {config['media_url']}")
        click.echo("  • Public base URL: not configured")
        return config

    click.echo("\n⚙️  Configuring storage module...")
    click.echo("Configure media storage backend for local or cloud delivery.\n")

    backend = click.prompt(
        "Storage backend",
        type=click.Choice(["local", "s3", "r2"], case_sensitive=False),
        default=str(defaults["backend"]),
        show_choices=True,
    ).lower()

    config = {
        "backend": backend,
        "media_url": click.prompt(
            "Media URL prefix",
            default=str(defaults["media_url"]),
        ).strip()
        or "/media/",
        "public_base_url": click.prompt(
            "Optional public base URL (CDN/domain)",
            default=str(defaults["public_base_url"]),
            show_default=False,
        ).strip(),
        "bucket_name": str(defaults["bucket_name"]),
        "endpoint_url": str(defaults["endpoint_url"]),
        "region_name": str(defaults["region_name"]),
        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION: str(
            defaults.get(
                STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
                DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
            )
        ),
        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: str(
            defaults.get(
                STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
                DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
            )
        ),
        "default_acl": str(defaults["default_acl"]),
        "querystring_auth": bool(defaults["querystring_auth"]),
        "private_media_enabled": bool(defaults["private_media_enabled"]),
    }

    if backend in {"s3", "r2"}:
        click.echo("\nCloud backend selected. Provide bucket/provider settings.")
        config["bucket_name"] = click.prompt(
            "Bucket name",
            default=str(defaults["bucket_name"]),
        ).strip()
        config["endpoint_url"] = click.prompt(
            "Endpoint URL (required for R2)",
            default=str(defaults["endpoint_url"]),
        ).strip()
        config["region_name"] = click.prompt(
            "Region name",
            default=str(defaults["region_name"]),
        ).strip()
        config[STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION] = (
            click.prompt(
                "Access key ID environment variable name",
                default=str(
                    defaults.get(
                        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
                        DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
                    )
                    or DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
                ),
            ).strip()
            or DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR
        )
        config[STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION] = (
            click.prompt(
                "Secret access key environment variable name",
                default=str(
                    defaults.get(
                        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
                        DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
                    )
                    or DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
                ),
            ).strip()
            or DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR
        )
        config["default_acl"] = click.prompt(
            "Default ACL (blank recommended)",
            default=str(defaults["default_acl"]),
        ).strip()
        config["querystring_auth"] = click.confirm(
            "Enable querystring auth (signed URLs)?",
            default=bool(defaults["querystring_auth"]),
        )
    else:
        config.update(
            {
                "bucket_name": "",
                "endpoint_url": "",
                "region_name": "",
                STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION: "",
                STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: "",
                "default_acl": "",
                "querystring_auth": False,
            }
        )

    return config


# ============================================================================
# BACKUPS MODULE CONFIGURATION
# ============================================================================


def get_default_backups_config() -> dict[str, Any]:
    """Return default configuration for the backups module."""
    return {
        "retention_days": 14,
        "naming_prefix": "db",
        "target_mode": "local",
        "local_directory": ".quickscale/backups",
        "remote_bucket_name": "",
        "remote_prefix": "backups/private",
        "remote_endpoint_url": "",
        "remote_region_name": "",
        BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "",
        BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: "",
        "automation_enabled": False,
        "schedule": "0 2 * * *",
    }


def _resolve_backups_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Merge backups options with defaults while preserving explicit overrides."""
    resolved = get_default_backups_config()
    resolved.update(normalize_backups_module_options(config))
    return resolved


def validate_backups_module_options(config: Mapping[str, Any]) -> list[str]:
    """Return validation issues for backups module options."""
    issues: list[str] = []
    resolved = _resolve_backups_config(config)

    try:
        retention_days = int(resolved["retention_days"])
        if retention_days < 1:
            issues.append("modules.backups.retention_days must be at least 1")
    except TypeError, ValueError:
        issues.append("modules.backups.retention_days must be an integer")

    naming_prefix = str(resolved["naming_prefix"]).strip()
    if not naming_prefix:
        issues.append("modules.backups.naming_prefix cannot be blank")

    target_mode = str(resolved["target_mode"]).strip().lower()
    if target_mode not in {"local", "private_remote"}:
        issues.append("modules.backups.target_mode must be 'local' or 'private_remote'")

    local_directory = str(resolved["local_directory"]).strip()
    if not local_directory:
        issues.append("modules.backups.local_directory cannot be blank")

    automation_enabled = bool(resolved["automation_enabled"])
    schedule = str(resolved["schedule"]).strip()
    if automation_enabled and not schedule:
        issues.append(
            "modules.backups.schedule is required when automation_enabled is true"
        )

    if target_mode == "private_remote":
        bucket_name = str(resolved["remote_bucket_name"]).strip()
        access_key_id_env_var = str(
            resolved[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
        ).strip()
        secret_access_key_env_var = str(
            resolved[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
        ).strip()
        endpoint_url = str(resolved["remote_endpoint_url"]).strip()
        region_name = str(resolved["remote_region_name"]).strip()

        if not bucket_name:
            issues.append(
                "modules.backups.remote_bucket_name is required when "
                "target_mode is private_remote"
            )
        if not access_key_id_env_var:
            issues.append(
                "modules.backups.remote_access_key_id_env_var is required when "
                "target_mode is private_remote"
            )
        else:
            access_key_issue = validate_backups_env_var_reference(
                BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
                access_key_id_env_var,
            )
            if access_key_issue:
                issues.append(access_key_issue)
        if not secret_access_key_env_var:
            issues.append(
                "modules.backups.remote_secret_access_key_env_var is required when "
                "target_mode is private_remote"
            )
        else:
            secret_access_key_issue = validate_backups_env_var_reference(
                BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
                secret_access_key_env_var,
            )
            if secret_access_key_issue:
                issues.append(secret_access_key_issue)
        if not (endpoint_url or region_name):
            issues.append(
                "modules.backups.private_remote mode requires remote_region_name "
                "or remote_endpoint_url"
            )

    return issues


def _raise_for_invalid_backups_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when backups config is invalid."""
    issues = validate_backups_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid backups module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_backups_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure backups module settings interactively or with defaults."""
    defaults = _resolve_backups_config(existing_config or {})

    if non_interactive:
        click.echo("\n⚙️  Using default backups module configuration...")
        config = defaults
        click.echo(f"  • Retention days: {config['retention_days']}")
        click.echo(f"  • Naming prefix: {config['naming_prefix']}")
        click.echo(f"  • Target mode: {config['target_mode']}")
        click.echo(
            f"  • Automation: {'Enabled' if config['automation_enabled'] else 'Disabled'}"
        )
        _raise_for_invalid_backups_config(config)
        return config

    click.echo("\n⚙️  Configuring backups module...")
    click.echo(
        "Backups are private operational artifacts. Restore execution remains "
        "CLI-only and scheduled runs stay command-driven.\n"
    )

    target_mode = click.prompt(
        "Backup target mode",
        type=click.Choice(["local", "private_remote"], case_sensitive=False),
        default=str(defaults["target_mode"]),
        show_choices=True,
    ).lower()

    automation_enabled = click.confirm(
        "Record that external cron/scheduler automation is enabled?",
        default=bool(defaults["automation_enabled"]),
    )

    config = {
        "retention_days": click.prompt(
            "Retention days",
            type=int,
            default=int(defaults["retention_days"]),
        ),
        "naming_prefix": click.prompt(
            "Naming prefix",
            default=str(defaults["naming_prefix"]),
        ).strip()
        or "db",
        "target_mode": target_mode,
        "local_directory": click.prompt(
            "Private local backup directory",
            default=str(defaults["local_directory"]),
        ).strip()
        or ".quickscale/backups",
        "remote_bucket_name": str(defaults["remote_bucket_name"]),
        "remote_prefix": str(defaults["remote_prefix"]),
        "remote_endpoint_url": str(defaults["remote_endpoint_url"]),
        "remote_region_name": str(defaults["remote_region_name"]),
        BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: str(
            defaults[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
        ),
        BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: str(
            defaults[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
        ),
        "automation_enabled": automation_enabled,
        "schedule": str(defaults["schedule"]),
    }

    if automation_enabled:
        config["schedule"] = click.prompt(
            "Documented schedule (cron-like)",
            default=str(defaults["schedule"]),
        ).strip()
    else:
        config["schedule"] = str(defaults["schedule"])

    if target_mode == "private_remote":
        click.echo("\nPrivate remote mode selected. Provide S3-compatible settings.")
        config["remote_bucket_name"] = click.prompt(
            "Remote bucket name",
            default=str(defaults["remote_bucket_name"]),
        ).strip()
        config["remote_prefix"] = (
            click.prompt(
                "Remote object prefix",
                default=str(defaults["remote_prefix"]),
            ).strip()
            or "backups/private"
        )
        config["remote_endpoint_url"] = click.prompt(
            "Remote endpoint URL (leave blank for provider defaults)",
            default=str(defaults["remote_endpoint_url"]),
            show_default=False,
        ).strip()
        config["remote_region_name"] = click.prompt(
            "Remote region name (or auto for endpoint providers)",
            default=str(defaults["remote_region_name"]),
            show_default=bool(defaults["remote_region_name"]),
        ).strip()
        config[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION] = click.prompt(
            "Remote access key id environment variable",
            default=(
                str(defaults[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]).strip()
                or DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
            ),
            show_default=True,
        ).strip()
        config[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION] = click.prompt(
            "Remote secret access key environment variable",
            default=(
                str(defaults[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]).strip()
                or DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
            ),
            show_default=True,
        ).strip()
    else:
        config.update(
            {
                "remote_bucket_name": "",
                "remote_prefix": "backups/private",
                "remote_endpoint_url": "",
                "remote_region_name": "",
                BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "",
                BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: "",
            }
        )

    _raise_for_invalid_backups_config(config)
    return config


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
# ANALYTICS MODULE CONFIGURATION
# ============================================================================


def get_default_analytics_config() -> dict[str, Any]:
    """Return default configuration for the analytics module."""
    return default_analytics_module_options()


def _raise_for_invalid_analytics_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when analytics config is invalid."""
    issues = validate_analytics_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid analytics module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_analytics_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure analytics module settings interactively or with defaults."""
    defaults = resolve_analytics_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default analytics module configuration...")
        click.echo("  • Runtime: " + ("Enabled" if defaults["enabled"] else "Disabled"))
        click.echo(f"  • Provider: {defaults['provider']}")
        click.echo("  • API key env var: " + str(defaults["posthog_api_key_env_var"]))
        click.echo("  • Host: " + str(defaults["posthog_host"]))
        _raise_for_invalid_analytics_config(defaults)
        return defaults

    click.echo("\n⚙️  Configuring analytics module...")
    click.echo(
        "Analytics is PostHog-only in v0.80.0. QuickScale owns the backend "
        "settings and capture helpers, while existing React/HTML theme files stay "
        "user-owned for manual frontend adoption.\n"
    )

    config = resolve_analytics_module_options(
        {
            "enabled": click.confirm(
                "Enable the analytics runtime?",
                default=bool(defaults["enabled"]),
            ),
            "provider": "posthog",
            "posthog_api_key_env_var": click.prompt(
                "PostHog API key environment variable",
                default=(
                    str(defaults["posthog_api_key_env_var"]).strip()
                    or DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR
                ),
                show_default=True,
            ).strip(),
            "posthog_host_env_var": click.prompt(
                "PostHog host environment variable",
                default=(
                    str(defaults["posthog_host_env_var"]).strip()
                    or DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR
                ),
                show_default=True,
            ).strip(),
            "posthog_host": (
                click.prompt(
                    "PostHog host URL",
                    default=(
                        str(defaults["posthog_host"]).strip()
                        or ANALYTICS_POSTHOG_DEFAULT_HOST
                    ),
                    show_default=True,
                ).strip()
                or ANALYTICS_POSTHOG_DEFAULT_HOST
            ),
            "exclude_debug": click.confirm(
                "Disable analytics automatically when DEBUG=True?",
                default=bool(defaults["exclude_debug"]),
            ),
            "exclude_staff": click.confirm(
                "Exclude staff users from analytics capture?",
                default=bool(defaults["exclude_staff"]),
            ),
            "anonymous_by_default": click.confirm(
                "Use anonymous session-based distinct IDs by default?",
                default=bool(defaults["anonymous_by_default"]),
            ),
        }
    )
    _raise_for_invalid_analytics_config(config)
    return config


# ============================================================================
# BILLING MODULE CONFIGURATION
# ============================================================================


def get_default_billing_config() -> dict[str, Any]:
    """Return default configuration for the billing module."""
    return default_billing_module_options()


def _raise_for_invalid_billing_config(config: Mapping[str, Any]) -> None:
    """Abort with actionable messaging when billing config is invalid."""
    issues = validate_billing_module_options(config)
    if not issues:
        return

    click.secho("\n❌ Invalid billing module configuration:", fg="red", err=True)
    for issue in issues:
        click.echo(f"  • {issue}", err=True)
    raise click.Abort()


def configure_billing_module(
    non_interactive: bool = False,
    existing_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Configure billing module settings interactively or with defaults."""
    defaults = resolve_billing_module_options(existing_config)

    if non_interactive:
        click.echo("\n⚙️  Using default billing module configuration...")
        click.echo("  • Runtime: " + ("Enabled" if defaults["enabled"] else "Disabled"))
        click.echo(
            "  • Publishable key env var: " + str(defaults["publishable_key_env_var"])
        )
        click.echo("  • Secret key env var: " + str(defaults["secret_key_env_var"]))
        click.echo(
            "  • Webhook secret env var: " + str(defaults["webhook_secret_env_var"])
        )
        click.echo("  • Billing currency: " + str(defaults["billing_currency"]))
        _raise_for_invalid_billing_config(defaults)
        return defaults

    click.echo("\n⚙️  Configuring billing module...")
    click.echo(
        "Billing is public-ready in quickscale plan, quickscale.yml, and "
        "quickscale apply flows. These settings configure the managed Stripe "
        "runtime, while quickscale apply still requires auth before billing "
        "can be enabled.\n"
    )

    config = resolve_billing_module_options(
        {
            "enabled": click.confirm(
                "Enable the billing runtime?",
                default=bool(defaults["enabled"]),
            ),
            "publishable_key_env_var": click.prompt(
                "Stripe publishable key environment variable",
                default=str(defaults["publishable_key_env_var"]),
                show_default=True,
            ).strip(),
            "secret_key_env_var": click.prompt(
                "Stripe secret key environment variable",
                default=str(defaults["secret_key_env_var"]),
                show_default=True,
            ).strip(),
            "webhook_secret_env_var": click.prompt(
                "Stripe webhook secret environment variable",
                default=str(defaults["webhook_secret_env_var"]),
                show_default=True,
            ).strip(),
            "billing_currency": click.prompt(
                "Billing currency (ISO 4217)",
                default=str(defaults["billing_currency"]),
                show_default=True,
            ).strip(),
        }
    )

    _raise_for_invalid_billing_config(config)
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
# ORGS MODULE
# ============================================================================


def get_default_orgs_config() -> dict[str, Any]:
    """Return default configuration for the orgs module."""
    return {"mode": "solo"}


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
            configure=configure_auth_module,
            get_defaults=get_default_auth_config,
        ),
        ModuleConfigurator(
            name="blog",
            configure=configure_blog_module,
            get_defaults=get_default_blog_config,
        ),
        ModuleConfigurator(
            name="crm",
            configure=configure_crm_module,
            get_defaults=get_default_crm_config,
        ),
        ModuleConfigurator(
            name="forms",
            configure=configure_forms_module,
            get_defaults=get_default_forms_config,
        ),
        ModuleConfigurator(
            name="listings",
            configure=configure_listings_module,
            get_defaults=get_default_listings_config,
        ),
        ModuleConfigurator(
            name="storage",
            configure=configure_storage_module,
            get_defaults=get_default_storage_config,
        ),
        ModuleConfigurator(
            name="backups",
            configure=configure_backups_module,
            get_defaults=get_default_backups_config,
        ),
        ModuleConfigurator(
            name="billing",
            configure=configure_billing_module,
            get_defaults=get_default_billing_config,
        ),
        ModuleConfigurator(
            name="notifications",
            configure=configure_notifications_module,
            get_defaults=get_default_notifications_config,
        ),
        ModuleConfigurator(
            name="analytics",
            configure=configure_analytics_module,
            get_defaults=get_default_analytics_config,
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
