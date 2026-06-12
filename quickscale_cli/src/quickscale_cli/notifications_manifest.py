"""Notifications module manifest-driven configuration adapter.

Replaces the legacy ``notifications_contract.py`` by sourcing defaults from the
notifications ``module.yml`` manifest and routing core normalization and
resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

The public API is a drop-in replacement for the old contract file so callers in
``plan_command.py``, ``apply_command.py``, ``module_wiring_specs.py``, and
``module_config.py`` can migrate without rewriting their logic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import re
from typing import Any

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR = "RESEND_API_KEY"
DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR = "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"

NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION = "resend_api_key_env_var"
NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION = "webhook_secret_env_var"

DEFAULT_NOTIFICATIONS_DEFAULT_TAGS = ("quickscale", "transactional")
DEFAULT_NOTIFICATIONS_ALLOWED_TAGS = (
    "quickscale",
    "transactional",
    "notifications",
    "auth",
    "forms",
    "ops",
    "testing",
)

NOTIFICATIONS_LIVE_EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
NOTIFICATIONS_CONSOLE_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

_NOTIFICATIONS_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")
_DEFAULT_PLACEHOLDER_SENDER_EMAIL = "noreply@example.com"
_LEGACY_NOTIFICATIONS_SECRET_OPTIONS = {
    "resend_api_key": DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    "webhook_secret": DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
}

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOTIFICATIONS_MANIFEST_PATH = (
    _REPO_ROOT / "quickscale_modules" / "notifications" / "module.yml"
)


def _load_notifications_manifest() -> Any:
    """Load the notifications module manifest from ``module.yml``."""
    return load_manifest_from_path(_NOTIFICATIONS_MANIFEST_PATH)


def _build_notifications_derivation_schema() -> ModuleDerivationSchema:
    """Build the derivation schema for the notifications module.

    Captures the normalization and validation rules that the generic resolver
    can execute. Notifications-specific rules that the resolver does not support
    natively (tag normalization and delivery readiness checks) are applied as
    post-resolution steps in the adapter functions below.
    """

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
                        description=(
                            "modules.notifications.sender_email must be a valid email address"
                        ),
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
                        description=(
                            "modules.notifications.resend_api_key_env_var must be an "
                            "environment variable name matching ^[A-Z][A-Z0-9_]*$"
                        ),
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
                        description=(
                            "modules.notifications.webhook_secret_env_var must be an "
                            "environment variable name matching ^[A-Z][A-Z0-9_]*$"
                        ),
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
                        description=(
                            "modules.notifications.webhook_ttl_seconds must be an integer"
                        ),
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
    """Return the default notifications planner/apply contract."""
    manifest = _load_notifications_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


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


def normalize_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return notifications options with raw-secret keys removed."""
    normalized = dict(options or {})

    for legacy_key, default_env_var in _LEGACY_NOTIFICATIONS_SECRET_OPTIONS.items():
        legacy_value = str(normalized.pop(legacy_key, "")).strip()
        env_var_option = (
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION
            if legacy_key == "resend_api_key"
            else NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION
        )
        current_env_var = str(normalized.get(env_var_option, "")).strip()
        if legacy_value and not current_env_var:
            normalized[env_var_option] = default_env_var

    for option_name in (
        "sender_name",
        "sender_email",
        "reply_to_email",
        "resend_domain",
    ):
        if option_name in normalized and normalized[option_name] is not None:
            normalized[option_name] = str(normalized[option_name]).strip()

    for option_name in (
        NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
        NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    ):
        if option_name in normalized and normalized[option_name] is not None:
            normalized[option_name] = str(normalized[option_name]).strip()

    if "default_tags" in normalized:
        normalized["default_tags"] = _normalize_tag_list(normalized["default_tags"])
    if "allowed_tags" in normalized:
        normalized["allowed_tags"] = _normalize_tag_list(normalized["allowed_tags"])
    if normalized.get("reply_to_email") is None:
        normalized["reply_to_email"] = ""

    return normalized


def resolve_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge notifications options with defaults and normalized values.

    Routes through the manifest-driven resolver for defaults extraction and core
    normalization, then applies notifications-specific post-resolution
    normalization for tag-list fields and legacy secret migration behavior.
    """
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


def validate_notifications_env_var_reference(
    option_name: str, value: Any
) -> str | None:
    """Validate a notifications env-var reference field."""
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.notifications.{option_name}"
    if not _NOTIFICATIONS_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )
    return None


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


def notifications_production_targeted(options: Mapping[str, Any] | None) -> bool:
    """Return whether notifications are configured for live production delivery."""
    resolved = resolve_notifications_module_options(options)
    return bool(resolved.get("enabled", True)) and bool(
        str(resolved.get("resend_domain", "")).strip()
    )


def notifications_live_delivery_configured(
    options: Mapping[str, Any] | None,
) -> bool:
    """Return whether notifications can use the live Resend backend safely."""
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
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
            resend_api_key_env_var,
        )
    )


def notifications_runtime_email_backend(
    options: Mapping[str, Any] | None,
) -> str | None:
    """Return the runtime email backend notifications should own."""
    resolved = resolve_notifications_module_options(options)
    if not bool(resolved.get("enabled", True)):
        return None
    if notifications_live_delivery_configured(resolved):
        return NOTIFICATIONS_LIVE_EMAIL_BACKEND
    return NOTIFICATIONS_CONSOLE_EMAIL_BACKEND


def validate_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> list[str]:
    """Return validation issues for notifications module options."""
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
        NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
        resend_api_key_env_var,
    )
    if resend_api_issue:
        issues.append(resend_api_issue)

    webhook_secret_issue = validate_notifications_env_var_reference(
        NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
        webhook_secret_env_var,
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
                "modules.notifications.sender_email cannot use the default "
                "placeholder noreply@example.com when resend_domain is set"
            )
        if not resend_api_key_env_var:
            issues.append(
                "modules.notifications.resend_api_key_env_var is required when resend_domain is set"
            )

    return issues


__all__ = [
    "DEFAULT_NOTIFICATIONS_ALLOWED_TAGS",
    "DEFAULT_NOTIFICATIONS_DEFAULT_TAGS",
    "DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR",
    "DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR",
    "NOTIFICATIONS_CONSOLE_EMAIL_BACKEND",
    "NOTIFICATIONS_LIVE_EMAIL_BACKEND",
    "NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION",
    "NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION",
    "default_notifications_module_options",
    "normalize_notifications_module_options",
    "notifications_live_delivery_configured",
    "notifications_production_targeted",
    "notifications_runtime_email_backend",
    "resolve_notifications_module_options",
    "validate_notifications_env_var_reference",
    "validate_notifications_module_options",
]
