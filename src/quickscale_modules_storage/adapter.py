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
        bucket_name = str(resolved.get("bucket_name", "")).strip()
        endpoint_url = str(resolved.get("endpoint_url", "")).strip()
        region_name = str(resolved.get("region_name", "")).strip()
        default_acl = str(resolved.get("default_acl", "")).strip()
        querystring_auth = bool(resolved.get("querystring_auth", False))
        access_key_id_env_var = str(
            resolved.get(
                STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
                DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
            )
        ).strip()
        secret_access_key_env_var = str(
            resolved.get(
                STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
                DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
            )
        ).strip()

        storage_options: dict[str, Any] = {
            "querystring_auth": querystring_auth,
        }
        if bucket_name:
            storage_options["bucket_name"] = bucket_name
        if endpoint_url:
            storage_options["endpoint_url"] = endpoint_url
        if region_name:
            storage_options["region_name"] = region_name
        if default_acl:
            storage_options["default_acl"] = default_acl

        derived_settings["STORAGES"] = {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": storage_options,
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        }
        derived_settings["AWS_QUERYSTRING_AUTH"] = querystring_auth
        if bucket_name:
            derived_settings["AWS_STORAGE_BUCKET_NAME"] = bucket_name
        if endpoint_url:
            derived_settings["AWS_S3_ENDPOINT_URL"] = endpoint_url
        if region_name:
            derived_settings["AWS_S3_REGION_NAME"] = region_name
        if access_key_id_env_var:
            derived_settings["AWS_ACCESS_KEY_ID"] = (
                f"__QS_ENV__:{access_key_id_env_var}"
            )
        if secret_access_key_env_var:
            derived_settings["AWS_SECRET_ACCESS_KEY"] = (
                f"__QS_ENV__:{secret_access_key_env_var}"
            )
        if default_acl:
            derived_settings["AWS_DEFAULT_ACL"] = default_acl

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
