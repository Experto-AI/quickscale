"""Module-owned storage manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
    ModuleWiringSpec,
    ResolverResult,
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    assemble_wiring_spec,
    build_generic_manifest_spec,
    resolve_storage_module_options,
    validate_storage_module_options,
)


def _cloud_storage_settings(resolved: dict[str, Any]) -> dict[str, Any]:
    """Project the ordered S3-compatible settings for cloud backends."""
    querystring_auth = bool(resolved.get("querystring_auth", False))
    optional_options = {
        option_name: value
        for option_name in (
            "bucket_name",
            "endpoint_url",
            "region_name",
            "default_acl",
        )
        if (value := str(resolved.get(option_name, "")).strip())
    }
    storage_options: dict[str, Any] = {
        "querystring_auth": querystring_auth,
        **optional_options,
    }
    settings: dict[str, Any] = {
        "STORAGES": {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": storage_options,
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        },
        "AWS_QUERYSTRING_AUTH": querystring_auth,
    }
    settings.update(
        {
            setting_name: optional_options[option_name]
            for option_name, setting_name in (
                ("bucket_name", "AWS_STORAGE_BUCKET_NAME"),
                ("endpoint_url", "AWS_S3_ENDPOINT_URL"),
                ("region_name", "AWS_S3_REGION_NAME"),
            )
            if option_name in optional_options
        }
    )

    credential_env_vars = (
        (
            "AWS_ACCESS_KEY_ID",
            str(
                resolved.get(
                    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
                    DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
                )
            ).strip(),
        ),
        (
            "AWS_SECRET_ACCESS_KEY",
            str(
                resolved.get(
                    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
                    DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
                )
            ).strip(),
        ),
    )
    settings.update(
        {
            setting_name: f"__QS_ENV__:{env_var_name}"
            for setting_name, env_var_name in credential_env_vars
            if env_var_name
        }
    )

    default_acl = optional_options.get("default_acl")
    if default_acl:
        settings["AWS_DEFAULT_ACL"] = default_acl
    return settings


def _storage_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build the storage module's manifest-driven wiring specification."""
    del project_package

    resolved = resolve_storage_module_options(options)
    validation_issues = validate_storage_module_options(options)
    backend = str(resolved.get("backend", "local")).lower()
    manifest_spec = build_generic_manifest_spec("storage", options)

    media_url = str(resolved.get("media_url", "/media/"))
    public_base_url = str(resolved.get("public_base_url", "")).strip()
    derived_settings: dict[str, Any] = {
        "QUICKSCALE_STORAGE_BACKEND": backend,
        "QUICKSCALE_STORAGE_PUBLIC_BASE_URL": public_base_url,
        "MEDIA_URL": media_url,
        "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED": bool(
            resolved.get("private_media_enabled", False)
        ),
    }

    if backend in {"s3", "r2"}:
        derived_settings.update(_cloud_storage_settings(resolved))

    result = ResolverResult(
        module_name="storage",
        defaults={},
        resolved=resolved,
        validation_issues=validation_issues,
        derived_settings=derived_settings,
        apps=manifest_spec.apps,
        middleware=manifest_spec.middleware,
        url_includes=manifest_spec.url_includes,
        pre_home_url_includes=manifest_spec.pre_home_url_includes,
        managed_files=(),
    )
    return assemble_wiring_spec(result)


def get_manifest_adapter() -> Any:
    """Return the storage module's manifest adapter callable."""
    return _storage_manifest_adapter
