"""Module-owned storage manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ManifestError,
    ModuleWiringSpec,
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    build_generic_manifest_spec,
    load_module_manifest,
    validate_module_options,
)


def _canonical_media_url(media_url: str) -> str:
    """Return *media_url* in the canonical leading/trailing-slash form."""
    normalized = (media_url or "/media/").strip()
    if not normalized.startswith("/") and not normalized.startswith("http"):
        normalized = "/" + normalized
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


def _cloud_storage_settings(resolved: dict[str, Any]) -> dict[str, Any]:
    """Project the ordered S3-compatible settings for cloud backends."""
    querystring_auth = bool(resolved["querystring_auth"])
    optional_options = {
        option_name: value
        for option_name in (
            "bucket_name",
            "endpoint_url",
            "region_name",
            "default_acl",
        )
        if (value := str(resolved[option_name]).strip())
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
            str(resolved[STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION]).strip(),
        ),
        (
            "AWS_SECRET_ACCESS_KEY",
            str(resolved[STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]).strip(),
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


def _storage_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Project storage's settings from the resolved options.

    The manifest declares every option's default, normalization rule, and
    validation block; this hook validates the resolved values through the
    same engine ``plan`` and ``apply`` use, then applies the coercions and
    canonical forms the declarative resolver cannot express (the media URL's
    canonical slashes and the ordered cloud-backend settings block).
    """
    issues = validate_module_options(load_module_manifest("storage"), resolved)
    if issues:
        raise ManifestError(
            "Module 'storage' has validation issues that must be resolved before "
            "assembly:\n" + "\n".join(f"  • {issue}" for issue in issues)
        )

    backend = str(resolved["backend"]).lower()
    settings = dict(spec.settings)
    settings.update(
        {
            "QUICKSCALE_STORAGE_BACKEND": backend,
            "MEDIA_URL": _canonical_media_url(str(resolved["media_url"])),
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL": str(
                resolved["public_base_url"]
            ).strip(),
            "AWS_STORAGE_BUCKET_NAME": str(resolved["bucket_name"]).strip(),
            "AWS_S3_ENDPOINT_URL": str(resolved["endpoint_url"]).strip(),
            "AWS_S3_REGION_NAME": str(resolved["region_name"]).strip(),
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID_ENV_VAR": str(
                resolved[STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION]
            ).strip(),
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY_ENV_VAR": str(
                resolved[STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
            ).strip(),
            "AWS_DEFAULT_ACL": str(resolved["default_acl"]).strip(),
            "AWS_QUERYSTRING_AUTH": bool(resolved["querystring_auth"]),
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED": bool(
                resolved["private_media_enabled"]
            ),
        }
    )

    if backend in {"s3", "r2"}:
        settings.update(_cloud_storage_settings(resolved))

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _storage_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build the storage module's manifest-driven wiring specification."""
    del project_package

    return build_generic_manifest_spec(
        "storage",
        options,
        post_hook=_storage_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the storage module's manifest adapter callable."""
    return _storage_manifest_adapter
