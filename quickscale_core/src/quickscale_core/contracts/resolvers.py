"""Module options resolution functions.

Provides ``resolve_*_module_options``, ``default_*_module_options``, and
``validate_*_module_options`` for every QuickScale module.  Relocated from
the ``quickscale_cli.*_manifest`` adapter files during T2.3 Phase 4.

Each function follows the same pattern: load the module's ``module.yml``
manifest, build a derivation schema, resolve user overrides against defaults,
and apply module-specific post-resolution coercions.

Constants and low-level ``normalize_*``/``validate_*`` helpers live in
:mod:`quickscale_core.contracts.module_options` alongside the derivation-level
``DerivedSetting``/``WiringProjection`` types.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from quickscale_core.contracts.module_options import (
    # Auth
    AUTH_REGISTRATION_ENABLED_OPTION,
    LEGACY_AUTH_ALLOW_REGISTRATION_OPTION,
    LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION,
    # Backups
    normalize_backups_module_options,
    # Billing
    BILLING_ENV_VAR_OPTION_NAMES,
    # Notifications
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    NOTIFICATIONS_LIVE_EMAIL_BACKEND,
    NOTIFICATIONS_CONSOLE_EMAIL_BACKEND,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    normalize_notifications_module_options,
    # Orgs
    ORGS_MODES,
    # Storage
    STORAGE_BACKENDS,
    DEFAULT_STORAGE_MEDIA_URL,
    DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    validate_storage_env_var_reference,
    # Social
    SOCIAL_LAYOUT_VARIANTS,
    # Common
    validate_notifications_env_var_reference,
)
from quickscale_core.manifest.derivation import (
    DerivedSetting,
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
    build_schema_from_manifest,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

from quickscale_core.contracts.module_discovery import (
    ImproperlyConfigured,
    get_bundled_manifests_path,
    get_modules_base_path,
)


# ---------------------------------------------------------------------------
# Analytics — manifest-driven bridge (SA5.1)
#
# All public functions in this section delegate to the manifest-driven
# pipeline (module.yml derivation rules) instead of the legacy imperative
# derivation schema.  The behaviour is identical — the flat-dict contract
# expected by CLI callers is preserved.
# ---------------------------------------------------------------------------

_ANALYTICS_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _normalize_posthog_host(value: Any) -> str:
    """Canonicalize a PostHog host URL (preserved for backward compat)."""
    candidate = str(value).strip()
    if not candidate:
        return ""
    if not candidate.startswith(("http://", "https://")):
        candidate = "https://" + candidate.lstrip("/")
    return candidate.rstrip("/")


def default_analytics_module_options() -> dict[str, Any]:
    """Return defaults declared in analytics ``module.yml``."""
    manifest = load_manifest_from_path(
        get_modules_base_path() / "analytics" / "module.yml"
    )
    return dict(manifest.get_defaults())


def normalize_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize analytics options (strip, lowercase provider)."""
    normalized = dict(options or {})
    if "provider" in normalized:
        normalized["provider"] = str(normalized["provider"]).strip().lower()
    for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()
    if "posthog_host" in normalized:
        normalized["posthog_host"] = _normalize_posthog_host(normalized["posthog_host"])
    return normalized


def resolve_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve analytics module options via the manifest runtime path.

    Delegates to ``build_schema_from_manifest`` using the derivation rules
    declared in ``module.yml`` (instead of the legacy hardcoded schema).
    Applies legacy-compatible post-resolution string normalisation.
    """
    manifest = load_manifest_from_path(
        get_modules_base_path() / "analytics" / "module.yml"
    )
    schema = build_schema_from_manifest(
        manifest_name="analytics",
        wiring_projections=manifest.wiring_projections,
        derived_settings=manifest.derived_settings,
        option_derivations=manifest.option_derivations,
        version="1",
    )
    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Apply analytics-specific post-resolution normalisation.
    if "posthog_host" in resolved:
        resolved["posthog_host"] = _normalize_posthog_host(resolved["posthog_host"])
    resolved["provider"] = str(resolved.get("provider", "")).strip().lower()
    resolved["posthog_api_key_env_var"] = str(
        resolved.get("posthog_api_key_env_var", "")
    ).strip()
    resolved["posthog_host_env_var"] = str(
        resolved.get("posthog_host_env_var", "")
    ).strip()
    resolved["posthog_host"] = _normalize_posthog_host(resolved.get("posthog_host", ""))

    return resolved


def validate_analytics_env_var_reference(option_name: str, value: Any) -> str | None:
    candidate = str(value).strip()
    if not candidate:
        return None
    qualified_option = f"modules.analytics.{option_name}"
    if not _ANALYTICS_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return f"{qualified_option} must be an environment variable name matching ^[A-Z][A-Z0-9_]*$"
    return None


def validate_analytics_module_options(options: Mapping[str, Any] | None) -> list[str]:
    from urllib.parse import urlsplit  # noqa: PLC0415

    resolved = resolve_analytics_module_options(options)
    issues: list[str] = []
    provider = str(resolved.get("provider", "")).strip().lower()
    if provider not in ("posthog",):
        issues.append("modules.analytics.provider must be one of: posthog")
    for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
        issue = validate_analytics_env_var_reference(
            option_name, resolved.get(option_name, "")
        )
        if issue:
            issues.append(issue)
    # Inline PostHog host URL validation (was _is_valid_posthog_host).
    _ph_host = str(resolved.get("posthog_host", "")).strip()
    if _ph_host:
        _parsed = urlsplit(_ph_host)
        if not (_parsed.scheme in {"http", "https"} and bool(_parsed.netloc)):
            issues.append(
                "modules.analytics.posthog_host must be an absolute http(s) URL"
            )
    else:
        issues.append("modules.analytics.posthog_host must be an absolute http(s) URL")
    for option_name in (
        "enabled",
        "exclude_debug",
        "exclude_staff",
        "anonymous_by_default",
    ):
        if not isinstance(resolved.get(option_name), bool):
            issues.append(f"modules.analytics.{option_name} must be a boolean")
    return issues


def analytics_production_targeted(options: Mapping[str, Any] | None) -> bool:
    resolved = resolve_analytics_module_options(options)
    if not bool(resolved.get("enabled", True)):
        return False
    api_key_env_var = str(resolved.get("posthog_api_key_env_var", "")).strip()
    return not bool(
        validate_analytics_env_var_reference("posthog_api_key_env_var", api_key_env_var)
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _load_auth_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "auth" / "module.yml")


def _build_auth_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="auth", version="1", option_derivations={}
    )


def default_auth_module_options() -> dict[str, Any]:
    manifest = _load_auth_manifest()
    return dict(manifest.get_defaults())


def normalize_auth_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    from quickscale_core.schema.config_schema import ConfigValidationError

    normalized = dict(options or {})
    if LEGACY_AUTH_ALLOW_REGISTRATION_OPTION in normalized:
        raise ConfigValidationError(
            f"Legacy config key '{LEGACY_AUTH_ALLOW_REGISTRATION_OPTION}' is "
            f"no longer supported. Use '{AUTH_REGISTRATION_ENABLED_OPTION}' instead."
        )
    if LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION in normalized:
        raise ConfigValidationError(
            f"Legacy config key '{LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION}' is "
            "no longer supported. Remove it from the auth module options."
        )
    return normalized


def resolve_auth_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = _load_auth_manifest()
    schema = _build_auth_derivation_schema()
    normalized_overrides = normalize_auth_module_options(options)
    result = resolve_module_config(manifest, schema, overrides=normalized_overrides)
    return dict(result.resolved)


def format_auth_desired_config_contract() -> str:
    return "\n".join(
        [
            "Canonical auth keys/value shapes:",
            "modules.auth.registration_enabled: true|false",
            "modules.auth.email_verification: none|optional|mandatory",
            "modules.auth.authentication_method: email|username|both",
            "modules.auth.session_cookie_age: <positive integer seconds>  # optional",
            "Remove legacy keys like modules.auth.allow_registration and modules.auth.social_providers.",
        ]
    )


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


def _load_backups_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "backups" / "module.yml")


def default_backups_module_options() -> dict[str, Any]:
    manifest = _load_backups_manifest()
    return dict(manifest.get_defaults())


def resolve_backups_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults = default_backups_module_options()
    normalized = normalize_backups_module_options(options)
    merged = dict(defaults)
    merged.update(normalized)
    return merged


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

_BILLING_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _load_billing_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "billing" / "module.yml")


def _build_billing_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="billing", version="1", option_derivations={}
    )


def default_billing_module_options() -> dict[str, Any]:
    manifest = _load_billing_manifest()
    return dict(manifest.get_defaults())


def normalize_billing_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized = dict(options or {})
    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()
    if "billing_currency" in normalized:
        normalized["billing_currency"] = (
            str(normalized["billing_currency"]).strip().lower()
        )
    return normalized


def resolve_billing_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = _load_billing_manifest()
    schema = _build_billing_derivation_schema()
    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)
    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        resolved[option_name] = str(resolved[option_name]).strip()
    resolved["billing_currency"] = str(resolved["billing_currency"]).strip().lower()
    return resolved


def validate_billing_env_var_reference(option_name: str, value: Any) -> str | None:
    candidate = str(value).strip()
    if not candidate:
        return None
    qualified_option = f"modules.billing.{option_name}"
    if not _BILLING_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return f"{qualified_option} must be an environment variable name matching ^[A-Z][A-Z0-9_]*$"
    return None


def validate_billing_currency(value: Any) -> str | None:
    from quickscale_core.contracts.module_options import BILLING_SUPPORTED_CURRENCIES

    candidate = str(value).strip().lower()
    if not candidate:
        return "modules.billing.billing_currency cannot be blank"
    if candidate not in BILLING_SUPPORTED_CURRENCIES:
        return (
            "modules.billing.billing_currency must be one of the supported QuickScale billing currency codes: "
            + ", ".join(BILLING_SUPPORTED_CURRENCIES)
        )
    return None


def validate_billing_module_options(options: Mapping[str, Any] | None) -> list[str]:
    resolved = resolve_billing_module_options(options)
    issues: list[str] = []
    if not isinstance(resolved.get("enabled", True), bool):
        issues.append("modules.billing.enabled must be a boolean")
    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        issue = validate_billing_env_var_reference(
            option_name, resolved.get(option_name, "")
        )
        if issue:
            issues.append(issue)
    currency_issue = validate_billing_currency(resolved.get("billing_currency", ""))
    if currency_issue:
        issues.append(currency_issue)
    return issues


def billing_production_targeted(options: Mapping[str, Any] | None) -> bool:
    resolved = resolve_billing_module_options(options)
    if not bool(resolved.get("enabled", True)):
        return False
    if validate_billing_currency(resolved.get("billing_currency", "")):
        return False
    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        candidate = str(resolved.get(option_name, "")).strip()
        if not candidate or validate_billing_env_var_reference(option_name, candidate):
            return False
    return True


# ---------------------------------------------------------------------------
# Blog
# ---------------------------------------------------------------------------

DEFAULT_BLOG_POSTS_PER_PAGE = 10
DEFAULT_BLOG_ENABLE_RSS = True
DEFAULT_BLOG_API_RATE_LIMIT = "5/hour"

BLOG_MODULE_OPTION_KEYS = frozenset(
    {
        "posts_per_page",
        "enable_rss",
        "api_rate_limit",
    }
)


def _load_blog_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "blog" / "module.yml")


def _build_blog_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="blog",
        version="1",
        option_derivations={
            "api_rate_limit": OptionDerivation(
                option_key="api_rate_limit",
                normalization_rules=[
                    NormalizationRule(
                        source_key="api_rate_limit",
                        target_key="api_rate_limit",
                        rule_type="strip",
                    )
                ],
            ),
        },
    )


def default_blog_module_options() -> dict[str, Any]:
    manifest = _load_blog_manifest()
    return dict(manifest.get_defaults())


def normalize_blog_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(options or {})
    if "api_rate_limit" in normalized:
        normalized["api_rate_limit"] = str(normalized["api_rate_limit"]).strip()
    return normalized


def resolve_blog_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = _load_blog_manifest()
    schema = _build_blog_derivation_schema()
    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)
    resolved["posts_per_page"] = int(resolved["posts_per_page"])
    resolved["enable_rss"] = bool(resolved["enable_rss"])
    resolved["api_rate_limit"] = str(resolved.get("api_rate_limit", "")).strip()
    return resolved


def validate_blog_module_options(options: Mapping[str, Any] | None) -> list[str]:
    resolved = resolve_blog_module_options(options)
    issues: list[str] = []
    posts = resolved.get("posts_per_page")
    try:
        if int(posts) <= 0:  # type: ignore[arg-type]
            issues.append("modules.blog.posts_per_page must be a positive integer")
    except (TypeError, ValueError):
        issues.append("modules.blog.posts_per_page must be a positive integer")
    if not isinstance(resolved.get("enable_rss"), bool):
        issues.append("modules.blog.enable_rss must be a boolean")
    rate = str(resolved.get("api_rate_limit", "")).strip()
    if not rate:
        issues.append("modules.blog.api_rate_limit cannot be blank")
    return issues


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION = "default_pipeline_stages"


def _load_crm_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "crm" / "module.yml")


def _build_crm_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="crm",
        version="1",
        option_derivations={
            "enable_api": OptionDerivation(
                option_key="enable_api",
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_ENABLE_API",
                        source_options=["enable_api"],
                        derivation_type="direct",
                        expression={"option": "enable_api"},
                    )
                ],
            ),
            "deals_per_page": OptionDerivation(
                option_key="deals_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="deals_per_page",
                        target_key="deals_per_page",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="deals_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.crm.deals_per_page must be a positive integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_DEALS_PER_PAGE",
                        source_options=["deals_per_page"],
                        derivation_type="direct",
                        expression={"option": "deals_per_page"},
                    )
                ],
            ),
            "contacts_per_page": OptionDerivation(
                option_key="contacts_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="contacts_per_page",
                        target_key="contacts_per_page",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="contacts_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.crm.contacts_per_page must be a positive integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_CONTACTS_PER_PAGE",
                        source_options=["contacts_per_page"],
                        derivation_type="direct",
                        expression={"option": "contacts_per_page"},
                    )
                ],
            ),
        },
    )


def default_crm_module_options() -> dict[str, Any]:
    manifest = _load_crm_manifest()
    return dict(manifest.get_defaults())


def normalize_crm_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    from quickscale_core.schema.config_schema import ConfigValidationError

    normalized = dict(options or {})
    if LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION in normalized:
        raise ConfigValidationError(
            "Legacy config key 'default_pipeline_stages' is no longer supported. "
            "Remove it from the CRM module options."
        )
    return normalized


def resolve_crm_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = _load_crm_manifest()
    schema = _build_crm_derivation_schema()
    cleaned = normalize_crm_module_options(options)
    result = resolve_module_config(manifest, schema, overrides=cleaned)
    resolved = dict(result.resolved)
    resolved["deals_per_page"] = int(resolved.get("deals_per_page", 25))
    resolved["contacts_per_page"] = int(resolved.get("contacts_per_page", 50))
    resolved["enable_api"] = bool(resolved.get("enable_api", True))
    return resolved


def validate_crm_module_options(options: Mapping[str, Any] | None) -> list[str]:
    issues: list[str] = []
    if options is not None and "enable_api" in options:
        if not isinstance(options["enable_api"], bool):
            issues.append("modules.crm.enable_api must be boolean")
    resolved = resolve_crm_module_options(options)
    deals_per_page = int(resolved["deals_per_page"])
    if deals_per_page < 1:
        issues.append("modules.crm.deals_per_page must be at least 1")
    contacts_per_page = int(resolved["contacts_per_page"])
    if contacts_per_page < 1:
        issues.append("modules.crm.contacts_per_page must be at least 1")
    return issues


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

DEFAULT_FORMS_PER_PAGE = 25
DEFAULT_FORMS_SPAM_PROTECTION_ENABLED = True
DEFAULT_FORMS_RATE_LIMIT = "5/hour"
DEFAULT_FORMS_DATA_RETENTION_DAYS = 365
DEFAULT_FORMS_SUBMISSIONS_API_ENABLED = True

_FORMS_RATE_LIMIT_PATTERN = re.compile(r"^\d+/(second|minute|hour|day)$")


def _load_forms_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "forms" / "module.yml")


def _build_forms_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="forms",
        version="1",
        option_derivations={
            "forms_per_page": OptionDerivation(
                option_key="forms_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="forms_per_page",
                        target_key="forms_per_page",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="forms_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.forms.forms_per_page must be a positive integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_PER_PAGE",
                        source_options=["forms_per_page"],
                        derivation_type="direct",
                        expression={"option": "forms_per_page"},
                    )
                ],
            ),
            "spam_protection_enabled": OptionDerivation(
                option_key="spam_protection_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_SPAM_PROTECTION",
                        source_options=["spam_protection_enabled"],
                        derivation_type="direct",
                        expression={"option": "spam_protection_enabled"},
                    )
                ],
            ),
            "rate_limit": OptionDerivation(
                option_key="rate_limit",
                normalization_rules=[
                    NormalizationRule(
                        source_key="rate_limit",
                        target_key="rate_limit",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="rate_limit",
                        rule_type="pattern",
                        pattern=r"^\d+/(second|minute|hour|day)$",
                        description="modules.forms.rate_limit must match format '<count>/<period>'",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_RATE_LIMIT",
                        source_options=["rate_limit"],
                        derivation_type="direct",
                        expression={"option": "rate_limit"},
                    )
                ],
            ),
            "data_retention_days": OptionDerivation(
                option_key="data_retention_days",
                normalization_rules=[
                    NormalizationRule(
                        source_key="data_retention_days",
                        target_key="data_retention_days",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="data_retention_days",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.forms.data_retention_days must be a non-negative integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_DATA_RETENTION_DAYS",
                        source_options=["data_retention_days"],
                        derivation_type="direct",
                        expression={"option": "data_retention_days"},
                    )
                ],
            ),
            "submissions_api_enabled": OptionDerivation(
                option_key="submissions_api_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_SUBMISSIONS_API",
                        source_options=["submissions_api_enabled"],
                        derivation_type="direct",
                        expression={"option": "submissions_api_enabled"},
                    )
                ],
            ),
        },
    )


def default_forms_module_options() -> dict[str, Any]:
    manifest = _load_forms_manifest()
    return dict(manifest.get_defaults())


def normalize_forms_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(options or {})
    if "rate_limit" in normalized:
        normalized["rate_limit"] = str(normalized["rate_limit"]).strip()
    return normalized


def resolve_forms_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = _load_forms_manifest()
    schema = _build_forms_derivation_schema()
    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)
    resolved["rate_limit"] = str(resolved.get("rate_limit", "")).strip()
    resolved["forms_per_page"] = int(resolved.get("forms_per_page", 25))
    resolved["data_retention_days"] = int(resolved.get("data_retention_days", 365))
    resolved["spam_protection_enabled"] = bool(
        resolved.get("spam_protection_enabled", True)
    )
    resolved["submissions_api_enabled"] = bool(
        resolved.get("submissions_api_enabled", True)
    )
    return resolved


def validate_forms_module_options(options: Mapping[str, Any] | None) -> list[str]:
    resolved = resolve_forms_module_options(options)
    issues: list[str] = []
    try:
        forms_per_page = int(resolved.get("forms_per_page", 0))
        if forms_per_page < 1:
            issues.append("modules.forms.forms_per_page must be at least 1")
    except (TypeError, ValueError):
        issues.append("modules.forms.forms_per_page must be a positive integer")
    try:
        data_retention_days = int(resolved.get("data_retention_days", -1))
        if data_retention_days < 0:
            issues.append(
                "modules.forms.data_retention_days must be a non-negative integer"
            )
    except (TypeError, ValueError):
        issues.append(
            "modules.forms.data_retention_days must be a non-negative integer"
        )
    rate_limit = str(resolved.get("rate_limit", "")).strip()
    if not _FORMS_RATE_LIMIT_PATTERN.match(rate_limit):
        issues.append(
            "modules.forms.rate_limit must match format '<count>/<period>' where period is one of: second, minute, hour, day"
        )
    for option_name in ("spam_protection_enabled", "submissions_api_enabled"):
        if not isinstance(resolved.get(option_name), bool):
            issues.append(f"modules.forms.{option_name} must be a boolean")
    return issues


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

_DEFAULT_PLACEHOLDER_SENDER_EMAIL = "noreply@example.com"
_NOTIFICATIONS_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")
_LEGACY_NOTIFICATIONS_SECRET_OPTIONS = {
    "resend_api_key": DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    "webhook_secret": DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
}


def _load_notifications_manifest() -> Any:
    try:
        return load_manifest_from_path(
            get_modules_base_path() / "notifications" / "module.yml"
        )
    except ImproperlyConfigured:
        # SA113 pattern: fall back to bundled manifest snapshots when
        # the source-tree modules workspace is unavailable (installed
        # wheel context).
        return load_manifest_from_path(
            get_bundled_manifests_path() / "notifications" / "module.yml"
        )


def _normalize_tag(value: Any) -> str:
    candidate = str(value).strip().lower().replace("_", "-")
    candidate = re.sub(r"\s+", "-", candidate)
    candidate = re.sub(r"[^a-z0-9-]", "", candidate)
    candidate = re.sub(r"-{2,}", "-", candidate).strip("-")
    return candidate[:50]


def _normalize_tag_list(values: Sequence[Any] | Any) -> list[str]:
    if isinstance(values, str):
        raw_values: Sequence[Any] = [part for part in values.split(",")]
    elif isinstance(values, Sequence):
        raw_values = values
    else:
        raw_values = [values]
    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        tag = _normalize_tag(value)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_PATTERN.fullmatch(value))


def _uses_placeholder_sender_email(value: Any) -> bool:
    return str(value).strip().casefold() == _DEFAULT_PLACEHOLDER_SENDER_EMAIL.casefold()


def _is_valid_domain(value: str) -> bool:
    candidate = value.strip()
    if not candidate or "://" in candidate or "/" in candidate:
        return False
    if candidate.startswith(".") or candidate.endswith("."):
        return False
    return bool(_DOMAIN_PATTERN.fullmatch(candidate) and "." in candidate)


def _build_notifications_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="notifications",
        version="1",
        option_derivations={
            "enabled": OptionDerivation(
                option_key="enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_ENABLED",
                        source_options=["enabled"],
                        derivation_type="direct",
                        expression={"option": "enabled"},
                    )
                ],
            ),
            "sender_name": OptionDerivation(
                option_key="sender_name",
                normalization_rules=[
                    NormalizationRule(
                        source_key="sender_name",
                        target_key="sender_name",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="sender_name",
                        rule_type="required",
                        description="modules.notifications.sender_name cannot be blank",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_SENDER_NAME",
                        source_options=["sender_name"],
                        derivation_type="direct",
                        expression={"option": "sender_name"},
                    )
                ],
            ),
            "sender_email": OptionDerivation(
                option_key="sender_email",
                normalization_rules=[
                    NormalizationRule(
                        source_key="sender_email",
                        target_key="sender_email",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="sender_email",
                        rule_type="required",
                        description="modules.notifications.sender_email must be a valid email address",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL",
                        source_options=["sender_email"],
                        derivation_type="direct",
                        expression={"option": "sender_email"},
                    )
                ],
            ),
            "reply_to_email": OptionDerivation(
                option_key="reply_to_email",
                normalization_rules=[
                    NormalizationRule(
                        source_key="reply_to_email",
                        target_key="reply_to_email",
                        rule_type="strip",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL",
                        source_options=["reply_to_email"],
                        derivation_type="direct",
                        expression={"option": "reply_to_email"},
                    )
                ],
            ),
            "resend_domain": OptionDerivation(
                option_key="resend_domain",
                normalization_rules=[
                    NormalizationRule(
                        source_key="resend_domain",
                        target_key="resend_domain",
                        rule_type="strip",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN",
                        source_options=["resend_domain"],
                        derivation_type="direct",
                        expression={"option": "resend_domain"},
                    )
                ],
            ),
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: OptionDerivation(
                option_key=NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
                normalization_rules=[
                    NormalizationRule(
                        source_key=NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
                        target_key=NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key=NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
                        rule_type="pattern",
                        pattern=r"^[A-Z][A-Z0-9_]*$",
                        description="modules.notifications.resend_api_key_env_var must be an environment variable name matching ^[A-Z][A-Z0-9_]*$",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR",
                        source_options=[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION],
                        derivation_type="direct",
                        expression={
                            "option": NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION
                        },
                    )
                ],
            ),
            NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION: OptionDerivation(
                option_key=NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
                normalization_rules=[
                    NormalizationRule(
                        source_key=NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
                        target_key=NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key=NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
                        rule_type="pattern",
                        pattern=r"^[A-Z][A-Z0-9_]*$",
                        description="modules.notifications.webhook_secret_env_var must be an environment variable name matching ^[A-Z][A-Z0-9_]*$",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR",
                        source_options=[NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION],
                        derivation_type="direct",
                        expression={
                            "option": NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION
                        },
                    )
                ],
            ),
            "default_tags": OptionDerivation(
                option_key="default_tags",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS",
                        source_options=["default_tags"],
                        derivation_type="direct",
                        expression={"option": "default_tags"},
                    )
                ],
            ),
            "allowed_tags": OptionDerivation(
                option_key="allowed_tags",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS",
                        source_options=["allowed_tags"],
                        derivation_type="direct",
                        expression={"option": "allowed_tags"},
                    )
                ],
            ),
            "webhook_ttl_seconds": OptionDerivation(
                option_key="webhook_ttl_seconds",
                normalization_rules=[
                    NormalizationRule(
                        source_key="webhook_ttl_seconds",
                        target_key="webhook_ttl_seconds",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="webhook_ttl_seconds",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.notifications.webhook_ttl_seconds must be an integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS",
                        source_options=["webhook_ttl_seconds"],
                        derivation_type="direct",
                        expression={"option": "webhook_ttl_seconds"},
                    )
                ],
            ),
        },
    )


def default_notifications_module_options() -> dict[str, Any]:
    manifest = _load_notifications_manifest()
    return dict(manifest.get_defaults())


def notifications_production_targeted(options: Mapping[str, Any] | None) -> bool:
    resolved = resolve_notifications_module_options(options)
    return bool(resolved.get("enabled", True)) and bool(
        str(resolved.get("resend_domain", "")).strip()
    )


def notifications_live_delivery_configured(options: Mapping[str, Any] | None) -> bool:
    resolved = resolve_notifications_module_options(options)
    if not notifications_production_targeted(resolved):
        return False
    sender_name = str(resolved.get("sender_name", "")).strip()
    sender_email = str(resolved.get("sender_email", "")).strip()
    resend_domain = str(resolved.get("resend_domain", "")).strip()
    resend_api_key_env_var = str(
        resolved.get(NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION, "")
    ).strip()
    return (
        bool(sender_name)
        and _is_valid_email(sender_email)
        and not _uses_placeholder_sender_email(sender_email)
        and _is_valid_domain(resend_domain)
        and not validate_notifications_env_var_reference(
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION, resend_api_key_env_var
        )
    )


def notifications_runtime_email_backend(
    options: Mapping[str, Any] | None,
) -> str | None:
    resolved = resolve_notifications_module_options(options)
    if not bool(resolved.get("enabled", True)):
        return None
    if notifications_live_delivery_configured(resolved):
        return NOTIFICATIONS_LIVE_EMAIL_BACKEND
    return NOTIFICATIONS_CONSOLE_EMAIL_BACKEND


def resolve_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    manifest = _load_notifications_manifest()
    schema = _build_notifications_derivation_schema()
    cleaned = normalize_notifications_module_options(options)
    result = resolve_module_config(manifest, schema, overrides=cleaned)
    resolved = dict(result.resolved)
    resolved["default_tags"] = _normalize_tag_list(resolved.get("default_tags", []))
    resolved["allowed_tags"] = _normalize_tag_list(resolved.get("allowed_tags", []))
    if resolved.get("reply_to_email") is None:
        resolved["reply_to_email"] = ""
    return resolved


def validate_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> list[str]:
    resolved = resolve_notifications_module_options(options)
    issues: list[str] = []
    enabled = resolved.get("enabled", True)
    if not isinstance(enabled, bool):
        issues.append("modules.notifications.enabled must be a boolean")
    sender_name = str(resolved.get("sender_name", "")).strip()
    sender_email = str(resolved.get("sender_email", "")).strip()
    reply_to_email = str(resolved.get("reply_to_email", "")).strip()
    resend_domain = str(resolved.get("resend_domain", "")).strip()
    if not sender_name:
        issues.append("modules.notifications.sender_name cannot be blank")
    if not sender_email or not _is_valid_email(sender_email):
        issues.append(
            "modules.notifications.sender_email must be a valid email address"
        )
    if reply_to_email and not _is_valid_email(reply_to_email):
        issues.append(
            "modules.notifications.reply_to_email must be a valid email address"
        )
    if resend_domain and not _is_valid_domain(resend_domain):
        issues.append(
            "modules.notifications.resend_domain must be a bare verified sending domain"
        )
    resend_api_key_env_var = str(
        resolved.get(NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION, "")
    ).strip()
    webhook_secret_env_var = str(
        resolved.get(NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION, "")
    ).strip()
    resend_api_issue = validate_notifications_env_var_reference(
        NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION, resend_api_key_env_var
    )
    if resend_api_issue:
        issues.append(resend_api_issue)
    webhook_secret_issue = validate_notifications_env_var_reference(
        NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION, webhook_secret_env_var
    )
    if webhook_secret_issue:
        issues.append(webhook_secret_issue)
    allowed_tags = _normalize_tag_list(resolved.get("allowed_tags", []))
    default_tags = _normalize_tag_list(resolved.get("default_tags", []))
    if not allowed_tags:
        issues.append("modules.notifications.allowed_tags cannot be empty")
    invalid_default_tags = [tag for tag in default_tags if tag not in set(allowed_tags)]
    if invalid_default_tags:
        issues.append(
            "modules.notifications.default_tags must be a subset of allowed_tags"
        )
    try:
        webhook_ttl_seconds = int(resolved.get("webhook_ttl_seconds", 300))
        if webhook_ttl_seconds < 1:
            issues.append(
                "modules.notifications.webhook_ttl_seconds must be at least 1"
            )
    except (TypeError, ValueError):
        issues.append("modules.notifications.webhook_ttl_seconds must be an integer")
    if notifications_production_targeted(resolved):
        if _uses_placeholder_sender_email(sender_email):
            issues.append(
                "modules.notifications.sender_email cannot use the default placeholder noreply@example.com when resend_domain is set"
            )
        if not resend_api_key_env_var:
            issues.append(
                "modules.notifications.resend_api_key_env_var is required when resend_domain is set"
            )
    return issues


# ---------------------------------------------------------------------------
# Orgs
# ---------------------------------------------------------------------------


def _load_orgs_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "orgs" / "module.yml")


def _build_orgs_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="orgs",
        version="1",
        option_derivations={
            "mode": OptionDerivation(
                option_key="mode",
                normalization_rules=[
                    NormalizationRule(
                        source_key="mode", target_key="mode", rule_type="strip"
                    ),
                    NormalizationRule(
                        source_key="mode", target_key="mode", rule_type="lowercase"
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="mode",
                        rule_type="choices",
                        allowed_values=list(ORGS_MODES),
                        description="modules.orgs.mode must be one of: "
                        + ", ".join(ORGS_MODES),
                    ),
                ],
            ),
        },
    )


def default_orgs_module_options() -> dict[str, Any]:
    manifest = _load_orgs_manifest()
    return dict(manifest.get_defaults())


def normalize_orgs_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(options or {})
    if "mode" in normalized:
        normalized["mode"] = str(normalized["mode"]).strip().lower()
    return normalized


def resolve_orgs_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = _load_orgs_manifest()
    schema = _build_orgs_derivation_schema()
    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)
    mode = str(resolved.get("mode", "")).strip().lower()
    resolved["mode"] = mode
    return resolved


def validate_orgs_module_options(options: Mapping[str, Any] | None) -> list[str]:
    raw_normalized = normalize_orgs_module_options(options)
    defaults = default_orgs_module_options()
    merged: dict[str, Any] = {**defaults, **raw_normalized}
    issues: list[str] = []
    mode = str(merged.get("mode", "")).strip().lower()
    if mode not in ORGS_MODES:
        issues.append("modules.orgs.mode must be one of: " + ", ".join(ORGS_MODES))
    return issues


# ---------------------------------------------------------------------------
# Social
# ---------------------------------------------------------------------------

_SOCIAL_PROVIDER_TOKEN_PATTERN = re.compile(r"[^a-z0-9-]+")
_SOCIAL_MULTI_DASH_PATTERN = re.compile(r"-{2,}")


def _load_social_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "social" / "module.yml")


def _build_social_derivation_schema() -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name="social",
        version="1",
        option_derivations={
            "link_tree_enabled": OptionDerivation(
                option_key="link_tree_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_LINK_TREE_ENABLED",
                        source_options=["link_tree_enabled"],
                        derivation_type="direct",
                        expression={"option": "link_tree_enabled"},
                    )
                ],
            ),
            "layout_variant": OptionDerivation(
                option_key="layout_variant",
                normalization_rules=[
                    NormalizationRule(
                        source_key="layout_variant",
                        target_key="layout_variant",
                        rule_type="strip",
                    ),
                    NormalizationRule(
                        source_key="layout_variant",
                        target_key="layout_variant",
                        rule_type="lowercase",
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_LAYOUT_VARIANT",
                        source_options=["layout_variant"],
                        derivation_type="direct",
                        expression={"option": "layout_variant"},
                    )
                ],
            ),
            "embeds_enabled": OptionDerivation(
                option_key="embeds_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_EMBEDS_ENABLED",
                        source_options=["embeds_enabled"],
                        derivation_type="direct",
                        expression={"option": "embeds_enabled"},
                    )
                ],
            ),
            "provider_allowlist": OptionDerivation(
                option_key="provider_allowlist",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST",
                        source_options=["provider_allowlist"],
                        derivation_type="direct",
                        expression={"option": "provider_allowlist"},
                    )
                ],
            ),
            "cache_ttl_seconds": OptionDerivation(
                option_key="cache_ttl_seconds",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS",
                        source_options=["cache_ttl_seconds"],
                        derivation_type="direct",
                        expression={"option": "cache_ttl_seconds"},
                    )
                ],
            ),
            "links_per_page": OptionDerivation(
                option_key="links_per_page",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_LINKS_PER_PAGE",
                        source_options=["links_per_page"],
                        derivation_type="direct",
                        expression={"option": "links_per_page"},
                    )
                ],
            ),
            "embeds_per_page": OptionDerivation(
                option_key="embeds_per_page",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE",
                        source_options=["embeds_per_page"],
                        derivation_type="direct",
                        expression={"option": "embeds_per_page"},
                    )
                ],
            ),
        },
    )


def default_social_module_options() -> dict[str, Any]:
    manifest = _load_social_manifest()
    return dict(manifest.get_defaults())


def _normalize_social_provider_token(value: Any) -> str:
    candidate = str(value).strip().lower().replace("&", "and")
    candidate = re.sub(r"[\s_/]+", "-", candidate)
    candidate = _SOCIAL_PROVIDER_TOKEN_PATTERN.sub("", candidate)
    return _SOCIAL_MULTI_DASH_PATTERN.sub("-", candidate).strip("-")


def normalize_social_provider(value: Any) -> str | None:
    token = _normalize_social_provider_token(value)
    if not token:
        return None
    _SOCIAL_PROVIDER_ALIASES = {
        "facebook": "facebook",
        "fb": "facebook",
        "instagram": "instagram",
        "ig": "instagram",
        "linkedin": "linkedin",
        "linked-in": "linkedin",
        "tiktok": "tiktok",
        "tik-tok": "tiktok",
        "x": "x",
        "twitter": "x",
        "x-twitter": "x",
        "x-twitter-com": "x",
        "youtube": "youtube",
        "you-tube": "youtube",
    }
    return _SOCIAL_PROVIDER_ALIASES.get(token)


def _coerce_social_allowlist_values(values: Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, str):
        return [part for part in values.split(",")]
    if isinstance(values, list):
        return list(values)
    if isinstance(values, tuple):
        return list(values)
    return [values]


def normalize_social_provider_allowlist(values: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in _coerce_social_allowlist_values(values):
        canonical = normalize_social_provider(value)
        candidate = canonical or _normalize_social_provider_token(value)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def normalize_social_module_options(options: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(options or {})
    if "provider_allowlist" in normalized:
        normalized["provider_allowlist"] = normalize_social_provider_allowlist(
            normalized["provider_allowlist"]
        )
    if "layout_variant" in normalized:
        normalized["layout_variant"] = str(normalized["layout_variant"]).strip().lower()
    return normalized


def resolve_social_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_social_module_options(dict(options or {}))
    manifest = _load_social_manifest()
    schema = _build_social_derivation_schema()
    result = resolve_module_config(manifest, schema, overrides=normalized)
    resolved = dict(result.resolved)
    resolved["provider_allowlist"] = normalize_social_provider_allowlist(
        resolved.get("provider_allowlist", [])
    )
    resolved["layout_variant"] = str(resolved.get("layout_variant", "")).strip().lower()
    return resolved


def validate_social_module_options(options: dict[str, Any] | None) -> list[str]:
    # Lazy import to avoid circular dependency:
    # contract.resolvers -> manifest.social_manifest -> contracts.module_options
    from quickscale_core.manifest.social_manifest import social_provider_supports_embeds  # noqa: PLC0415

    resolved = resolve_social_module_options(options)
    issues: list[str] = []
    if not isinstance(resolved.get("link_tree_enabled"), bool):
        issues.append("modules.social.link_tree_enabled must be a boolean")
    if not isinstance(resolved.get("embeds_enabled"), bool):
        issues.append("modules.social.embeds_enabled must be a boolean")
    layout_variant = str(resolved.get("layout_variant", "")).strip().lower()
    if layout_variant not in SOCIAL_LAYOUT_VARIANTS:
        issues.append("modules.social.layout_variant must be one of: list, cards, grid")
    provider_allowlist = normalize_social_provider_allowlist(
        resolved.get("provider_allowlist", [])
    )
    if not provider_allowlist:
        issues.append("modules.social.provider_allowlist cannot be empty")
    # Check for unknown providers
    _SOCIAL_PROVIDER_BY_NAME = {
        "facebook": None,
        "instagram": None,
        "linkedin": None,
        "tiktok": None,
        "x": None,
        "youtube": None,
    }
    unknown_providers = [
        provider
        for provider in provider_allowlist
        if provider not in _SOCIAL_PROVIDER_BY_NAME
    ]
    if unknown_providers:
        issues.append(
            "modules.social.provider_allowlist contains unsupported providers: "
            + ", ".join(sorted(unknown_providers))
        )
    if not resolved.get("link_tree_enabled") and not resolved.get("embeds_enabled"):
        issues.append(
            "modules.social must leave link_tree_enabled or embeds_enabled enabled"
        )
    if resolved.get("embeds_enabled"):
        embed_providers = [
            provider
            for provider in provider_allowlist
            if social_provider_supports_embeds(provider)
        ]
        if not embed_providers:
            issues.append(
                "modules.social.provider_allowlist must include tiktok or youtube "
                "when embeds_enabled is true"
            )
    for option_name in ("cache_ttl_seconds", "links_per_page", "embeds_per_page"):
        try:
            value = int(resolved.get(option_name, 0))
            if value < 1:
                issues.append(f"modules.social.{option_name} must be at least 1")
        except (TypeError, ValueError):
            issues.append(f"modules.social.{option_name} must be an integer")
    return issues


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _load_storage_manifest() -> Any:
    return load_manifest_from_path(get_modules_base_path() / "storage" / "module.yml")


def _normalize_media_url(media_url: str) -> str:
    normalized = (media_url or "/media/").strip()
    if not normalized.startswith("/") and not normalized.startswith("http"):
        normalized = "/" + normalized
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


def _build_storage_derivation_schema() -> ModuleDerivationSchema:
    _strip_keys = (
        "public_base_url",
        "bucket_name",
        "endpoint_url",
        "region_name",
        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        "default_acl",
    )
    strip_derivations = {
        key: OptionDerivation(
            option_key=key,
            normalization_rules=[
                NormalizationRule(source_key=key, target_key=key, rule_type="strip")
            ],
        )
        for key in _strip_keys
    }
    return ModuleDerivationSchema(
        module_name="storage",
        version="1",
        option_derivations={
            "backend": OptionDerivation(
                option_key="backend",
                normalization_rules=[
                    NormalizationRule(
                        source_key="backend",
                        target_key="backend",
                        rule_type="lowercase",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="backend",
                        rule_type="choices",
                        allowed_values=list(STORAGE_BACKENDS),
                        description="modules.storage.backend must be one of: "
                        + ", ".join(STORAGE_BACKENDS),
                    )
                ],
            ),
            **strip_derivations,
        },
    )


def default_storage_module_options() -> dict[str, Any]:
    manifest = _load_storage_manifest()
    return dict(manifest.get_defaults())


def normalize_storage_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized = dict(options or {})
    if "backend" in normalized:
        normalized["backend"] = str(normalized["backend"]).lower()
    if "media_url" in normalized:
        normalized["media_url"] = _normalize_media_url(str(normalized["media_url"]))
    if "public_base_url" in normalized:
        normalized["public_base_url"] = str(normalized["public_base_url"]).strip()

    # Convert legacy literal credential options to env-var references.
    legacy_access_key_id = str(normalized.pop("access_key_id", "")).strip()
    legacy_secret_access_key = str(normalized.pop("secret_access_key", "")).strip()
    access_key_env_var = str(
        normalized.get(STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION, "")
    ).strip()
    secret_access_key_env_var = str(
        normalized.get(STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION, "")
    ).strip()
    if legacy_access_key_id and not access_key_env_var:
        normalized[STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION] = (
            DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR
        )
    if legacy_secret_access_key and not secret_access_key_env_var:
        normalized[STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION] = (
            DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR
        )

    for key in (
        "bucket_name",
        "endpoint_url",
        "region_name",
        "default_acl",
        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    ):
        if key in normalized:
            normalized[key] = str(normalized[key]).strip()
    return normalized


def resolve_storage_module_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = _load_storage_manifest()
    schema = _build_storage_derivation_schema()
    normalized = normalize_storage_module_options(options)
    result = resolve_module_config(manifest, schema, overrides=normalized)
    resolved = dict(result.resolved)
    backend = str(resolved.get("backend", "")).lower()
    resolved["backend"] = backend
    resolved["media_url"] = _normalize_media_url(
        str(resolved.get("media_url", DEFAULT_STORAGE_MEDIA_URL))
    )
    resolved["public_base_url"] = str(resolved.get("public_base_url", "")).strip()
    resolved["private_media_enabled"] = bool(
        resolved.get("private_media_enabled", False)
    )
    resolved["querystring_auth"] = bool(resolved.get("querystring_auth", False))
    for key in (
        "bucket_name",
        "endpoint_url",
        "region_name",
        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        "default_acl",
    ):
        resolved[key] = str(resolved.get(key, "")).strip()
    return resolved


def validate_storage_module_options(options: Mapping[str, Any] | None) -> list[str]:
    raw_normalized = normalize_storage_module_options(options)
    defaults = default_storage_module_options()
    merged: dict[str, Any] = {**defaults, **raw_normalized}
    issues: list[str] = []
    backend = str(merged.get("backend", "")).lower()
    if backend not in STORAGE_BACKENDS:
        issues.append(
            "modules.storage.backend must be one of: " + ", ".join(STORAGE_BACKENDS)
        )
    if not isinstance(merged.get("private_media_enabled"), bool):
        issues.append("modules.storage.private_media_enabled must be a boolean")
    # Validate env-var references when a cloud backend is configured.
    if backend in {"s3", "r2"}:
        for option_name in (
            STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
            STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        ):
            issue = validate_storage_env_var_reference(
                option_name, merged.get(option_name, "")
            )
            if issue:
                issues.append(issue)
    return issues


__all__ = [
    # Analytics
    "analytics_production_targeted",
    "default_analytics_module_options",
    "normalize_analytics_module_options",
    "resolve_analytics_module_options",
    "validate_analytics_env_var_reference",
    "validate_analytics_module_options",
    # Auth
    "default_auth_module_options",
    "format_auth_desired_config_contract",
    "normalize_auth_module_options",
    "resolve_auth_module_options",
    # Backups
    "default_backups_module_options",
    "resolve_backups_module_options",
    # Billing
    "billing_production_targeted",
    "default_billing_module_options",
    "normalize_billing_module_options",
    "resolve_billing_module_options",
    "validate_billing_currency",
    "validate_billing_env_var_reference",
    "validate_billing_module_options",
    # Blog
    "BLOG_MODULE_OPTION_KEYS",
    "DEFAULT_BLOG_API_RATE_LIMIT",
    "DEFAULT_BLOG_ENABLE_RSS",
    "DEFAULT_BLOG_POSTS_PER_PAGE",
    "default_blog_module_options",
    "normalize_blog_module_options",
    "resolve_blog_module_options",
    "validate_blog_module_options",
    # CRM
    "LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION",
    "default_crm_module_options",
    "normalize_crm_module_options",
    "resolve_crm_module_options",
    "validate_crm_module_options",
    # Forms
    "DEFAULT_FORMS_DATA_RETENTION_DAYS",
    "DEFAULT_FORMS_PER_PAGE",
    "DEFAULT_FORMS_RATE_LIMIT",
    "DEFAULT_FORMS_SPAM_PROTECTION_ENABLED",
    "DEFAULT_FORMS_SUBMISSIONS_API_ENABLED",
    "default_forms_module_options",
    "normalize_forms_module_options",
    "resolve_forms_module_options",
    "validate_forms_module_options",
    # Notifications
    "default_notifications_module_options",
    "notifications_live_delivery_configured",
    "notifications_production_targeted",
    "notifications_runtime_email_backend",
    "resolve_notifications_module_options",
    "validate_notifications_module_options",
    # Orgs
    "default_orgs_module_options",
    "normalize_orgs_module_options",
    "resolve_orgs_module_options",
    "validate_orgs_module_options",
    # Social
    "default_social_module_options",
    "normalize_social_module_options",
    "normalize_social_provider",
    "normalize_social_provider_allowlist",
    "resolve_social_module_options",
    "validate_social_module_options",
    # Storage
    "default_storage_module_options",
    "normalize_storage_module_options",
    "resolve_storage_module_options",
    "validate_storage_env_var_reference",
    "validate_storage_module_options",
]
