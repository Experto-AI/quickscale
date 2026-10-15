"""Module-owned social manifest adapter.

This is the **sole** social adapter for monorepo and embedded
``modules/`` contexts.  It is registered dynamically by
:func:`quickscale_core.manifest.entry_point.refresh_managed_adapters`
when the module package is importable.

When the module package is **not** importable,
:func:`refresh_managed_adapters` raises
:class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured` — bundled/installed
without module source is not a supported context (fail-hard decision).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quickscale_core.runtime.manifest import (
    ModuleWiringSpec,
    ResolvedOptions,
    build_generic_manifest_spec,
    render_social_managed_init_module,
    render_social_managed_urls_module,
    render_social_managed_views_module,
    social_provider_supports_embeds,
)

#: Renderer ID of the managed URLconf in the social manifest's managed_files.
_MANAGED_URLCONF_RENDERER = "social.managed_urls"


def _qualify_managed_url_includes(
    includes: tuple[tuple[str, str], ...],
    project_package: str,
    *,
    managed_files: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    """Qualify social's manifest-declared URL includes for the project package.

    The manifest owns the module's mount and declares social's URLconf
    project-relatively (``quickscale_managed.social_urls``); the generated
    project's package name reaches wiring only here, so the adapter supplies
    it.  A target that is not the managed URLconf social renders (the declared
    managed file whose renderer is :data:`_MANAGED_URLCONF_RENDERER`) fails
    closed instead of emitting an unimportable include.

    Args:
        includes: The ``(route, include_path)`` pairs projected from the
            social ``module.yml`` manifest.
        project_package: The generated project's Python package name.
        managed_files: The ``output_path -> renderer`` mapping projected from
            the same manifest, used to identify the rendered URLconf.

    Returns:
        The includes with every target qualified as
        ``{project_package}.{include_path}``.

    Raises:
        ValueError: When no include is declared or a target names no managed
            URLconf social renders.
    """
    if not includes:
        raise ValueError(
            "Invalid social manifest url_includes: expected the module's mount"
        )
    urlconf_modules = {
        output_path[: -len(".py")].replace("/", ".")
        for output_path, renderer in managed_files.items()
        if renderer == _MANAGED_URLCONF_RENDERER and output_path.endswith(".py")
    }
    qualified: list[tuple[str, str]] = []
    for route, include_path in includes:
        if include_path not in urlconf_modules:
            declared = ", ".join(sorted(urlconf_modules)) or "none declared"
            raise ValueError(
                "Invalid social manifest url_includes target "
                f"{include_path!r}: expected the managed URLconf social renders "
                f"({declared})"
            )
        qualified.append((route, f"{project_package}.{include_path}"))
    return tuple(qualified)


def _build_social_post_hook(project_package: str) -> Any:
    """Build the social post-resolution hook for one project package.

    The manifest owns the module's options, defaults, checks, projections,
    settings (fixed paths included), and managed-file inventory.  The hook
    contributes only what the declarative resolver cannot express: the
    embed-capable slice of the canonical provider allowlist, the
    project-package-qualified mount, and the rendered content of each
    rendered managed file.  Rule 1 (D3): off keeps the module installed —
    app, admin, settings, and managed files — and mounts none of its public
    URLs.
    """

    def _social_post_hook(
        spec: ModuleWiringSpec, resolved: ResolvedOptions
    ) -> ModuleWiringSpec:
        provider_allowlist = list(resolved.provider_allowlist)
        embed_provider_allowlist = [
            provider
            for provider in provider_allowlist
            if social_provider_supports_embeds(provider)
        ]

        settings = dict(spec.settings)
        settings["QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST"] = (
            embed_provider_allowlist
        )

        if resolved.enabled:
            url_includes = _qualify_managed_url_includes(
                spec.url_includes,
                project_package,
                managed_files=spec.managed_files,
            )
        else:
            url_includes = ()

        renderer_dispatch: dict[str, str] = {
            "social.managed_init": render_social_managed_init_module(),
            _MANAGED_URLCONF_RENDERER: render_social_managed_urls_module(),
            "social.managed_views": render_social_managed_views_module(
                provider_allowlist,
                embed_provider_allowlist,
                layout_variant=resolved.layout_variant,
                cache_ttl_seconds=resolved.cache_ttl_seconds,
                links_per_page=resolved.links_per_page,
                embeds_per_page=resolved.embeds_per_page,
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
            settings=settings,
            pre_home_url_includes=spec.pre_home_url_includes,
            url_includes=url_includes,
            spa_routes=spec.spa_routes,
            managed_files=managed_content,
        )

    return _social_post_hook


def _social_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the social module via the manifest path.

    Settings: the manifest's ``QUICKSCALE_SOCIAL_*`` projections plus the
    embed-capable provider allowlist the hook derives from the canonical
    provider allowlist.
    URL includes: the manifest-declared mount (``_quickscale/social/``) and
    its project-relative managed URLconf target, qualified with
    ``project_package`` into ``{project_package}.quickscale_managed.social_urls``.
    Managed files: the manifest-declared ``managed_files`` inventory; the
    post-resolution hook replaces each renderer-ID placeholder with the
    rendered file content.

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

    return build_generic_manifest_spec(
        "social",
        options,
        post_hook=_build_social_post_hook(project_package),
    )


def get_manifest_adapter() -> Any:
    """Return the social module's manifest adapter callable.

    The returned callable has the signature::

        (options: dict[str, Any], *, project_package: str | None = None) -> ModuleWiringSpec

    This is the sentinel that
    :func:`~quickscale_core.manifest.entry_point.refresh_managed_adapters`
    uses to discover module-owned adapters.
    """
    return _social_manifest_adapter
