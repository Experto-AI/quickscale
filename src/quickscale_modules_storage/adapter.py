"""Module-owned storage manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ModuleWiringSpec,
    build_generic_manifest_spec,
)


def _cloud_storage_settings(resolved: dict[str, Any]) -> dict[str, Any]:
    """Project the ordered S3-compatible settings for cloud backends.

    Every value arrives canonical from the manifest boundary: optional
    provider entries are omitted while blank. Credential aliases are already
    projected by the manifest and are not manufactured by this composite. The
    hook neither re-coerces nor re-reads a raw option.
    """
    querystring_auth = resolved["querystring_auth"]
    optional_options = {
        option_name: resolved[option_name]
        for option_name in (
            "bucket_name",
            "endpoint_url",
            "region_name",
            "default_acl",
        )
        if resolved[option_name]
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

    return settings


def _storage_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Project storage's cloud-backend settings from canonical values.

    The manifest declares every option's default, normalization rule, check,
    projection, and derived setting — MEDIA_URL included, through the
    ``path_or_absolute_url`` kind whose blank handling resolves through the
    option's own declared default.  This hook contributes only what the
    declarative resolver cannot express: the ordered ``STORAGES`` composite
    and provider filtering. The manifest owns cloud-only scalar aliases.
    """
    settings = dict(spec.settings)
    if resolved["backend"] in {"s3", "r2"}:
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
