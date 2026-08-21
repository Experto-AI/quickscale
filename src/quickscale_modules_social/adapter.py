"""Module-owned social manifest adapter.

This is the **sole** social adapter for monorepo and embedded
``modules/`` contexts.  It is registered dynamically by
:func:`quickscale_core.manifest.entry_point.refresh_managed_adapters`
when the module package is importable.

When the module package is **not** importable,
:func:`refresh_managed_adapters` raises
:class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured` — bundled/installed
without module source is not a supported context (AF7 fail-hard decision).
"""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
    ModuleWiringSpec,
    ResolverResult,
    assemble_wiring_spec,
    load_social_manifest,
    render_social_managed_init_module,
    render_social_managed_urls_module,
    render_social_managed_views_module,
    resolve_social_module_options,
    social_provider_supports_embeds,
)


def _social_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the social module via the manifest path.

    Settings: ``QUICKSCALE_SOCIAL_*`` keys derived from resolved options plus
    fixed path constants.
    URL includes: a single ``project_package``-qualified include pointing at
    ``{project_package}.quickscale_managed.social_urls``.
    Managed files: sourced from the manifest-declared ``managed_files``
    contract in the social ``module.yml``.  The assembler converts each
    declaration's ``output_path`` and ``renderer`` into a placeholder
    mapping; the post-resolution hook then replaces each renderer-ID
    placeholder with the actual rendered file content.  This keeps the
    managed-file inventory in the manifest as the single source of truth
    rather than hardcoding paths in the adapter.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: The generated project's Python package name.
            Required for the URL include qualification.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        social.

    Raises:
        ValueError: When *project_package* is ``None``.
    """
    if project_package is None:
        raise ValueError("project_package is required for managed social wiring")

    resolved = resolve_social_module_options(dict(options))
    provider_allowlist = list(resolved["provider_allowlist"])
    embed_provider_allowlist = [
        provider
        for provider in provider_allowlist
        if social_provider_supports_embeds(provider)
    ]

    derived_settings: dict[str, Any] = {
        "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED": bool(
            resolved.get("link_tree_enabled", True)
        ),
        "QUICKSCALE_SOCIAL_LAYOUT_VARIANT": str(resolved.get("layout_variant", "list")),
        "QUICKSCALE_SOCIAL_EMBEDS_ENABLED": bool(resolved.get("embeds_enabled", True)),
        "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": provider_allowlist,
        "QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST": embed_provider_allowlist,
        "QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS": int(
            resolved.get("cache_ttl_seconds", 300)
        ),
        "QUICKSCALE_SOCIAL_LINKS_PER_PAGE": int(resolved.get("links_per_page", 24)),
        "QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE": int(resolved.get("embeds_per_page", 12)),
        "QUICKSCALE_SOCIAL_LINK_TREE_PATH": SOCIAL_LINK_TREE_PATH,
        "QUICKSCALE_SOCIAL_EMBEDS_PATH": SOCIAL_EMBEDS_PATH,
        "QUICKSCALE_SOCIAL_INTEGRATION_BASE_PATH": SOCIAL_INTEGRATION_BASE_PATH,
        "QUICKSCALE_SOCIAL_INTEGRATION_EMBEDS_PATH": SOCIAL_INTEGRATION_EMBEDS_PATH,
    }

    # Load the manifest-declared wiring and managed_files contracts so the assembler
    # populates spec.managed_files with output_path -> renderer_id mappings
    # sourced from module.yml rather than hardcoding paths in this adapter.
    social_manifest = load_social_manifest()
    apps = _social_manifest_apps(social_manifest)
    managed_file_declarations = tuple(social_manifest.managed_files.values())

    result = ResolverResult(
        module_name="social",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=apps,
        middleware=(),
        url_includes=(
            (
                SOCIAL_INTEGRATION_BASE_PATH.lstrip("/"),
                f"{project_package}.quickscale_managed.social_urls",
            ),
        ),
        pre_home_url_includes=(),
        managed_files=managed_file_declarations,
    )

    # Post-resolution hook: replace renderer-ID placeholders (sourced from the
    # manifest-declared managed_files contract) with rendered content.
    def _social_managed_files_hook(
        spec: ModuleWiringSpec, resolved_opts: dict[str, Any]
    ) -> ModuleWiringSpec:
        # Dispatch table: renderer_id (from module.yml) -> rendered content.
        # The output_path keys come from spec.managed_files which the assembler
        # populated from the manifest declarations, not from hardcoded paths.
        renderer_dispatch: dict[str, str] = {
            "social.managed_init": render_social_managed_init_module(),
            "social.managed_urls": render_social_managed_urls_module(),
            "social.managed_views": render_social_managed_views_module(
                provider_allowlist,
                embed_provider_allowlist,
                layout_variant=str(resolved_opts.get("layout_variant", "list")),
                cache_ttl_seconds=int(resolved_opts.get("cache_ttl_seconds", 300)),
                links_per_page=int(resolved_opts.get("links_per_page", 24)),
                embeds_per_page=int(resolved_opts.get("embeds_per_page", 12)),
            ),
        }

        managed_content: dict[str, str] = {}
        for output_path, renderer_id in spec.managed_files.items():
            rendered = renderer_dispatch.get(renderer_id)
            if rendered is not None:
                managed_content[output_path] = rendered

        return ModuleWiringSpec(
            apps=spec.apps,
            middleware=spec.middleware,
            settings=spec.settings,
            pre_home_url_includes=spec.pre_home_url_includes,
            url_includes=spec.url_includes,
            managed_files=managed_content,
        )

    return assemble_wiring_spec(result, post_hook=_social_managed_files_hook)


def _social_manifest_apps(social_manifest: Any) -> tuple[str, ...]:
    """Return the sole validated static apps projection from the social manifest.

    The social adapter remains hand-built for its managed-file rendering, but
    the manifest owns the Django app declaration.  Fail closed when that
    contract is missing or malformed rather than allowing a second Python-side
    declaration to drift from ``module.yml``.
    """
    raw_projections = getattr(social_manifest, "wiring_projections", None)
    projections = (
        [
            projection
            for projection in raw_projections
            if isinstance(projection, dict) and projection.get("wiring_field") == "apps"
        ]
        if isinstance(raw_projections, list)
        else []
    )

    error_prefix = "Invalid social manifest apps projection"
    if len(projections) != 1:
        raise ValueError(
            f"{error_prefix}: expected exactly one projection, found {len(projections)}"
        )

    projection = projections[0]
    if projection.get("derivation_type") != "static":
        raise ValueError(f"{error_prefix}: projection must be static")

    expression = projection.get("expression")
    apps = expression.get("value") if isinstance(expression, dict) else None
    if (
        not isinstance(apps, list)
        or not apps
        or any(not isinstance(app, str) or not app.strip() for app in apps)
    ):
        raise ValueError(
            f"{error_prefix}: static expression.value must be a non-empty list "
            "of non-empty strings"
        )

    return tuple(apps)


def get_manifest_adapter() -> Any:
    """Return the social module's manifest adapter callable.

    The returned callable has the signature::

        (options: dict[str, Any], *, project_package: str | None = None) -> ModuleWiringSpec

    This is the sentinel that
    :func:`~quickscale_core.manifest.entry_point.refresh_managed_adapters`
    uses to discover module-owned adapters.
    """
    return _social_manifest_adapter
