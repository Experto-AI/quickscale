"""Manifest-driven wiring spec entry point.

Provides :func:`build_manifest_wiring_spec` — an ADDITIVE entry point that
routes a module through its manifest adapter and the manifest assembler to
produce a complete :class:`~quickscale_core.module_wiring.ModuleWiringSpec`.

This entry point does **not** modify or replace
``build_module_wiring_specs`` (the legacy dispatch in
``quickscale_cli.commands.module_wiring_specs``).  The legacy builder
continues to own its dispatch table and its sole direct caller
(``quickscale_cli.utils.module_wiring_manager.regenerate_managed_wiring``).

Module adapter registration
----------------------------
Manifest adapters register themselves by populating
:data:`MANIFEST_ADAPTER_REGISTRY`.  Each entry is a callable that accepts
``(options, *, project_package)`` and returns a
:class:`~quickscale_core.module_wiring.ModuleWiringSpec`.

Analytics is registered at import time as the first migrated module.
Billing, blog, listings, CRM, forms, and backups are registered as C1-C7
migration adapters.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quickscale_core.module_wiring import ModuleWiringSpec


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

#: Registry mapping module name -> manifest adapter callable.
#:
#: Each callable must accept ``(options: dict[str, Any], *, project_package:
#: str | None) -> ModuleWiringSpec``.  New adapters register here during the
#: B-phase migrations (blog, listings, orgs, storage …).
MANIFEST_ADAPTER_REGISTRY: dict[
    str,
    Callable[..., ModuleWiringSpec],
] = {}


# ---------------------------------------------------------------------------
# Analytics adapter (first migrated module)
# ---------------------------------------------------------------------------


def _analytics_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the analytics module via the manifest path.

    Delegates to the existing ``analytics_manifest`` adapter in
    ``quickscale_cli`` (which already uses the manifest resolver + derivation
    schema internally).  This function is the bridge that lets
    :func:`build_manifest_wiring_spec` call the CLI-resident adapter without
    the CLI package needing to depend on this entry point.

    The import is deferred so that ``quickscale_core`` does not gain a
    circular dependency on ``quickscale_cli`` at module load time.

    PR-4 hazard: the legacy ``_analytics_wiring`` returns an EMPTY
    ``ModuleWiringSpec`` when ``enabled`` is ``False``.  We reproduce that
    short-circuit here via the post-resolution hook so parity holds for the
    disabled case.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for analytics; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        analytics.
    """
    # Deferred import avoids circular dependency: quickscale_core must not
    # import from quickscale_cli at module level.
    from quickscale_cli.analytics_manifest import (  # noqa: PLC0415
        resolve_analytics_module_options,
    )
    from quickscale_core.manifest.assembler import assemble_wiring_spec  # noqa: PLC0415
    from quickscale_core.manifest.derivation import (  # noqa: PLC0415
        DerivedSetting,
        ModuleDerivationSchema,
        OptionDerivation,
        WiringProjection,
    )
    from quickscale_core.manifest.resolver import ResolverResult  # noqa: PLC0415

    resolved = resolve_analytics_module_options(options)

    # PR-4 short-circuit: legacy returns an empty spec when disabled.
    if not bool(resolved.get("enabled", True)):
        return ModuleWiringSpec()

    # Build derivation schema with wiring projections for the enabled case.
    schema = ModuleDerivationSchema(
        module_name="analytics",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={"value": ["quickscale_modules_analytics"]},
                description="Analytics Django app label",
            ),
        ],
        option_derivations={
            "enabled": OptionDerivation(
                option_key="enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_ENABLED",
                        source_options=["enabled"],
                        derivation_type="direct",
                        expression={"option": "enabled"},
                    ),
                ],
            ),
            "provider": OptionDerivation(
                option_key="provider",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_PROVIDER",
                        source_options=["provider"],
                        derivation_type="direct",
                        expression={"option": "provider"},
                    ),
                ],
            ),
            "posthog_api_key_env_var": OptionDerivation(
                option_key="posthog_api_key_env_var",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
                        source_options=["posthog_api_key_env_var"],
                        derivation_type="direct",
                        expression={"option": "posthog_api_key_env_var"},
                    ),
                ],
            ),
            "posthog_host_env_var": OptionDerivation(
                option_key="posthog_host_env_var",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
                        source_options=["posthog_host_env_var"],
                        derivation_type="direct",
                        expression={"option": "posthog_host_env_var"},
                    ),
                ],
            ),
            "posthog_host": OptionDerivation(
                option_key="posthog_host",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_POSTHOG_HOST",
                        source_options=["posthog_host"],
                        derivation_type="direct",
                        expression={"option": "posthog_host"},
                    ),
                ],
            ),
            "exclude_debug": OptionDerivation(
                option_key="exclude_debug",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG",
                        source_options=["exclude_debug"],
                        derivation_type="direct",
                        expression={"option": "exclude_debug"},
                    ),
                ],
            ),
            "exclude_staff": OptionDerivation(
                option_key="exclude_staff",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_EXCLUDE_STAFF",
                        source_options=["exclude_staff"],
                        derivation_type="direct",
                        expression={"option": "exclude_staff"},
                    ),
                ],
            ),
            "anonymous_by_default": OptionDerivation(
                option_key="anonymous_by_default",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
                        source_options=["anonymous_by_default"],
                        derivation_type="direct",
                        expression={"option": "anonymous_by_default"},
                    ),
                ],
            ),
        },
    )

    # Build the wiring and derived settings from the schema against the
    # already-resolved options dict.
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        _project_all_derived_settings,
        _project_all_wiring,
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # The legacy wiring uses bool() coercion on the boolean fields; reproduce
    # that here so the settings dict has actual booleans, not raw values.
    for bool_key in (
        "QUICKSCALE_ANALYTICS_ENABLED",
        "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG",
        "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF",
        "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
    ):
        if bool_key in derived_settings:
            derived_settings[bool_key] = bool(derived_settings[bool_key])

    # The legacy wiring uses str(...).strip() or str(...).strip() or default
    # on string fields; resolve_analytics_module_options already applied those.
    for str_key in (
        "QUICKSCALE_ANALYTICS_PROVIDER",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    ):
        if str_key in derived_settings:
            derived_settings[str_key] = str(derived_settings[str_key]).strip()

    # Apply the same fallback defaults the legacy wiring applies.
    posthog_defaults = {
        "QUICKSCALE_ANALYTICS_PROVIDER": "posthog",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": "POSTHOG_API_KEY",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": "POSTHOG_HOST",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST": "https://us.i.posthog.com",
    }
    for key, fallback in posthog_defaults.items():
        if key in derived_settings and not derived_settings[key]:
            derived_settings[key] = fallback

    result = ResolverResult(
        module_name="analytics",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


# Register analytics as the first manifest-driven adapter.
MANIFEST_ADAPTER_REGISTRY["analytics"] = _analytics_manifest_adapter


# ---------------------------------------------------------------------------
# Billing adapter (C1)
# ---------------------------------------------------------------------------


def _billing_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the billing module via the manifest path.

    Mirrors ``_billing_wiring`` in ``module_wiring_specs.py`` exactly.
    Apps: ``("rest_framework", "quickscale_modules_billing")``.
    URL includes: ``[("", "quickscale_modules_billing.urls")]``.
    Settings: QUICKSCALE_BILLING_* keys derived from resolved options.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for billing; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        billing that is equal to the legacy ``_billing_wiring`` output.
    """
    from quickscale_cli.billing_manifest import (  # noqa: PLC0415
        DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
        DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
        DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
        DEFAULT_BILLING_CURRENCY,
    )
    from quickscale_core.manifest.assembler import assemble_wiring_spec  # noqa: PLC0415
    from quickscale_core.manifest.derivation import (  # noqa: PLC0415
        DerivedSetting,
        ModuleDerivationSchema,
        OptionDerivation,
        WiringProjection,
    )
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        ResolverResult,
        _project_all_derived_settings,
        _project_all_wiring,
    )
    from quickscale_cli.billing_manifest import resolve_billing_module_options  # noqa: PLC0415

    resolved = resolve_billing_module_options(options)

    schema = ModuleDerivationSchema(
        module_name="billing",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={"value": ["rest_framework", "quickscale_modules_billing"]},
                description="Billing Django app labels",
            ),
            WiringProjection(
                wiring_field="url_includes",
                derivation_type="static",
                expression={"value": [["", "quickscale_modules_billing.urls"]]},
                description="Billing URL includes",
            ),
        ],
        option_derivations={
            "enabled": OptionDerivation(
                option_key="enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_BILLING_ENABLED",
                        source_options=["enabled"],
                        derivation_type="direct",
                        expression={"option": "enabled"},
                    ),
                ],
            ),
            "publishable_key_env_var": OptionDerivation(
                option_key="publishable_key_env_var",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR",
                        source_options=["publishable_key_env_var"],
                        derivation_type="direct",
                        expression={"option": "publishable_key_env_var"},
                        default=DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
                    ),
                ],
            ),
            "secret_key_env_var": OptionDerivation(
                option_key="secret_key_env_var",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR",
                        source_options=["secret_key_env_var"],
                        derivation_type="direct",
                        expression={"option": "secret_key_env_var"},
                        default=DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
                    ),
                ],
            ),
            "webhook_secret_env_var": OptionDerivation(
                option_key="webhook_secret_env_var",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR",
                        source_options=["webhook_secret_env_var"],
                        derivation_type="direct",
                        expression={"option": "webhook_secret_env_var"},
                        default=DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
                    ),
                ],
            ),
            "billing_currency": OptionDerivation(
                option_key="billing_currency",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_BILLING_CURRENCY",
                        source_options=["billing_currency"],
                        derivation_type="direct",
                        expression={"option": "billing_currency"},
                        default=DEFAULT_BILLING_CURRENCY,
                    ),
                ],
            ),
        },
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # Reproduce legacy bool() coercion on the enabled flag.
    derived_settings["QUICKSCALE_BILLING_ENABLED"] = bool(
        derived_settings.get("QUICKSCALE_BILLING_ENABLED", True)
    )
    # Reproduce legacy str() coercion on string fields.
    for str_key in (
        "QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR",
        "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR",
        "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR",
        "QUICKSCALE_BILLING_CURRENCY",
    ):
        if str_key in derived_settings:
            derived_settings[str_key] = str(derived_settings[str_key])

    result = ResolverResult(
        module_name="billing",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["billing"] = _billing_manifest_adapter


# ---------------------------------------------------------------------------
# Blog adapter (C4)
# ---------------------------------------------------------------------------


def _blog_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the blog module via the manifest path.

    Mirrors ``_blog_wiring`` in ``module_wiring_specs.py`` exactly.
    Apps: ``("markdownx", "quickscale_modules_blog")``.
    URL includes: ``[("blog/", ...), ("markdownx/", ...)]``.
    Settings: BLOG_* + MARKDOWNX_* keys.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for blog; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        blog that is equal to the legacy ``_blog_wiring`` output.
    """
    from quickscale_cli.blog_manifest import (  # noqa: PLC0415
        resolve_blog_module_options,
        DEFAULT_BLOG_API_RATE_LIMIT,
    )
    from quickscale_core.manifest.assembler import assemble_wiring_spec  # noqa: PLC0415
    from quickscale_core.manifest.derivation import (  # noqa: PLC0415
        DerivedSetting,
        ModuleDerivationSchema,
        OptionDerivation,
        WiringProjection,
    )
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        ResolverResult,
        _project_all_derived_settings,
        _project_all_wiring,
    )

    resolved = resolve_blog_module_options(options)

    _MARKDOWNX_EXTENSIONS = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]

    schema = ModuleDerivationSchema(
        module_name="blog",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={"value": ["markdownx", "quickscale_modules_blog"]},
                description="Blog Django app labels",
            ),
            WiringProjection(
                wiring_field="url_includes",
                derivation_type="static",
                expression={
                    "value": [
                        ["blog/", "quickscale_modules_blog.urls"],
                        ["markdownx/", "markdownx.urls"],
                    ]
                },
                description="Blog URL includes",
            ),
        ],
        option_derivations={
            "posts_per_page": OptionDerivation(
                option_key="posts_per_page",
                derived_settings=[
                    DerivedSetting(
                        setting_key="BLOG_POSTS_PER_PAGE",
                        source_options=["posts_per_page"],
                        derivation_type="direct",
                        expression={"option": "posts_per_page"},
                        default=10,
                    ),
                ],
            ),
            "enable_rss": OptionDerivation(
                option_key="enable_rss",
                derived_settings=[
                    DerivedSetting(
                        setting_key="BLOG_ENABLE_RSS",
                        source_options=["enable_rss"],
                        derivation_type="direct",
                        expression={"option": "enable_rss"},
                        default=True,
                    ),
                ],
            ),
            "api_rate_limit": OptionDerivation(
                option_key="api_rate_limit",
                derived_settings=[
                    DerivedSetting(
                        setting_key="BLOG_API_RATE_LIMIT",
                        source_options=["api_rate_limit"],
                        derivation_type="direct",
                        expression={"option": "api_rate_limit"},
                        default=DEFAULT_BLOG_API_RATE_LIMIT,
                    ),
                ],
            ),
        },
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # Reproduce legacy int()/bool()/str() coercions.
    derived_settings["BLOG_POSTS_PER_PAGE"] = int(
        derived_settings.get("BLOG_POSTS_PER_PAGE", 10)
    )
    derived_settings["BLOG_ENABLE_RSS"] = bool(
        derived_settings.get("BLOG_ENABLE_RSS", True)
    )
    api_rate = str(derived_settings.get("BLOG_API_RATE_LIMIT", "")).strip()
    derived_settings["BLOG_API_RATE_LIMIT"] = api_rate or DEFAULT_BLOG_API_RATE_LIMIT

    # Add static markdownx settings (identical to legacy).
    derived_settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = _MARKDOWNX_EXTENSIONS
    derived_settings["MARKDOWNX_MEDIA_PATH"] = "blog/markdownx/"

    result = ResolverResult(
        module_name="blog",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["blog"] = _blog_manifest_adapter


# ---------------------------------------------------------------------------
# Listings adapter (C3)
# ---------------------------------------------------------------------------


def _listings_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the listings module via the manifest path.

    Mirrors ``_listings_wiring`` in ``module_wiring_specs.py`` exactly.
    Apps: ``("django_filters", "markdownx", "quickscale_modules_listings")``.
    URL includes: ``[("listings/", ...), ("markdownx/", ...)]``.
    Settings: LISTINGS_PER_PAGE + MARKDOWNX_MARKDOWN_EXTENSIONS.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for listings; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        listings that is equal to the legacy ``_listings_wiring`` output.
    """
    from quickscale_cli.listings_manifest import (  # noqa: PLC0415
        resolve_listings_module_options,
    )
    from quickscale_core.manifest.assembler import assemble_wiring_spec  # noqa: PLC0415
    from quickscale_core.manifest.derivation import (  # noqa: PLC0415
        DerivedSetting,
        ModuleDerivationSchema,
        OptionDerivation,
        WiringProjection,
    )
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        ResolverResult,
        _project_all_derived_settings,
        _project_all_wiring,
    )

    resolved = resolve_listings_module_options(options)

    _MARKDOWNX_EXTENSIONS = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]

    schema = ModuleDerivationSchema(
        module_name="listings",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={
                    "value": [
                        "django_filters",
                        "markdownx",
                        "quickscale_modules_listings",
                    ]
                },
                description="Listings Django app labels",
            ),
            WiringProjection(
                wiring_field="url_includes",
                derivation_type="static",
                expression={
                    "value": [
                        ["listings/", "quickscale_modules_listings.urls"],
                        ["markdownx/", "markdownx.urls"],
                    ]
                },
                description="Listings URL includes",
            ),
        ],
        option_derivations={
            "listings_per_page": OptionDerivation(
                option_key="listings_per_page",
                derived_settings=[
                    DerivedSetting(
                        setting_key="LISTINGS_PER_PAGE",
                        source_options=["listings_per_page"],
                        derivation_type="direct",
                        expression={"option": "listings_per_page"},
                        default=12,
                    ),
                ],
            ),
        },
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # Reproduce legacy int() coercion.
    derived_settings["LISTINGS_PER_PAGE"] = int(
        derived_settings.get("LISTINGS_PER_PAGE", 12)
    )

    # Add static markdownx settings (identical to legacy).
    derived_settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = _MARKDOWNX_EXTENSIONS

    result = ResolverResult(
        module_name="listings",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["listings"] = _listings_manifest_adapter


# ---------------------------------------------------------------------------
# CRM adapter (C6)
# ---------------------------------------------------------------------------


def _crm_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the CRM module via the manifest path.

    Mirrors ``_crm_wiring`` in ``module_wiring_specs.py`` exactly.
    Apps: ``("rest_framework", "django_filters", "quickscale_modules_crm")``.
    URL includes: ``[("", "quickscale_modules_crm.urls")]``.
    Settings: CRM_DEALS_PER_PAGE, CRM_CONTACTS_PER_PAGE, CRM_ENABLE_API.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for CRM; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        CRM that is equal to the legacy ``_crm_wiring`` output.
    """
    from quickscale_cli.crm_manifest import (  # noqa: PLC0415
        resolve_crm_module_options,
    )
    from quickscale_core.manifest.assembler import assemble_wiring_spec  # noqa: PLC0415
    from quickscale_core.manifest.derivation import (  # noqa: PLC0415
        DerivedSetting,
        ModuleDerivationSchema,
        OptionDerivation,
        WiringProjection,
    )
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        ResolverResult,
        _project_all_derived_settings,
        _project_all_wiring,
    )

    resolved = resolve_crm_module_options(options)

    schema = ModuleDerivationSchema(
        module_name="crm",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={
                    "value": [
                        "rest_framework",
                        "django_filters",
                        "quickscale_modules_crm",
                    ]
                },
                description="CRM Django app labels",
            ),
            WiringProjection(
                wiring_field="url_includes",
                derivation_type="static",
                expression={"value": [["", "quickscale_modules_crm.urls"]]},
                description="CRM URL includes",
            ),
        ],
        option_derivations={
            "deals_per_page": OptionDerivation(
                option_key="deals_per_page",
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_DEALS_PER_PAGE",
                        source_options=["deals_per_page"],
                        derivation_type="direct",
                        expression={"option": "deals_per_page"},
                        default=25,
                    ),
                ],
            ),
            "contacts_per_page": OptionDerivation(
                option_key="contacts_per_page",
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_CONTACTS_PER_PAGE",
                        source_options=["contacts_per_page"],
                        derivation_type="direct",
                        expression={"option": "contacts_per_page"},
                        default=50,
                    ),
                ],
            ),
            "enable_api": OptionDerivation(
                option_key="enable_api",
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_ENABLE_API",
                        source_options=["enable_api"],
                        derivation_type="direct",
                        expression={"option": "enable_api"},
                        default=True,
                    ),
                ],
            ),
        },
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # Reproduce legacy int()/bool() coercions.
    derived_settings["CRM_DEALS_PER_PAGE"] = int(
        derived_settings.get("CRM_DEALS_PER_PAGE", 25)
    )
    derived_settings["CRM_CONTACTS_PER_PAGE"] = int(
        derived_settings.get("CRM_CONTACTS_PER_PAGE", 50)
    )
    derived_settings["CRM_ENABLE_API"] = bool(
        derived_settings.get("CRM_ENABLE_API", True)
    )

    result = ResolverResult(
        module_name="crm",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["crm"] = _crm_manifest_adapter


# ---------------------------------------------------------------------------
# Forms adapter (C7)
# ---------------------------------------------------------------------------


def _forms_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the forms module via the manifest path.

    Mirrors ``_forms_wiring`` in ``module_wiring_specs.py`` exactly.
    Apps: ``("rest_framework", "django_filters", "quickscale_modules_forms")``.
    URL includes: ``[("", "quickscale_modules_forms.urls")]``.
    Settings: FORMS_* keys.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for forms; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        forms that is equal to the legacy ``_forms_wiring`` output.
    """
    from quickscale_cli.forms_manifest import (  # noqa: PLC0415
        resolve_forms_module_options,
        DEFAULT_FORMS_RATE_LIMIT,
    )
    from quickscale_core.manifest.assembler import assemble_wiring_spec  # noqa: PLC0415
    from quickscale_core.manifest.derivation import (  # noqa: PLC0415
        DerivedSetting,
        ModuleDerivationSchema,
        OptionDerivation,
        WiringProjection,
    )
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        ResolverResult,
        _project_all_derived_settings,
        _project_all_wiring,
    )

    resolved = resolve_forms_module_options(options)

    schema = ModuleDerivationSchema(
        module_name="forms",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={
                    "value": [
                        "rest_framework",
                        "django_filters",
                        "quickscale_modules_forms",
                    ]
                },
                description="Forms Django app labels",
            ),
            WiringProjection(
                wiring_field="url_includes",
                derivation_type="static",
                expression={"value": [["", "quickscale_modules_forms.urls"]]},
                description="Forms URL includes",
            ),
        ],
        option_derivations={
            "forms_per_page": OptionDerivation(
                option_key="forms_per_page",
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_PER_PAGE",
                        source_options=["forms_per_page"],
                        derivation_type="direct",
                        expression={"option": "forms_per_page"},
                        default=25,
                    ),
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
                        default=True,
                    ),
                ],
            ),
            "rate_limit": OptionDerivation(
                option_key="rate_limit",
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_RATE_LIMIT",
                        source_options=["rate_limit"],
                        derivation_type="direct",
                        expression={"option": "rate_limit"},
                        default=DEFAULT_FORMS_RATE_LIMIT,
                    ),
                ],
            ),
            "data_retention_days": OptionDerivation(
                option_key="data_retention_days",
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_DATA_RETENTION_DAYS",
                        source_options=["data_retention_days"],
                        derivation_type="direct",
                        expression={"option": "data_retention_days"},
                        default=365,
                    ),
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
                        default=True,
                    ),
                ],
            ),
        },
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # Reproduce legacy int()/bool()/str() coercions.
    derived_settings["FORMS_PER_PAGE"] = int(derived_settings.get("FORMS_PER_PAGE", 25))
    derived_settings["FORMS_SPAM_PROTECTION"] = bool(
        derived_settings.get("FORMS_SPAM_PROTECTION", True)
    )
    derived_settings["FORMS_RATE_LIMIT"] = str(
        derived_settings.get("FORMS_RATE_LIMIT", DEFAULT_FORMS_RATE_LIMIT)
    )
    derived_settings["FORMS_DATA_RETENTION_DAYS"] = int(
        derived_settings.get("FORMS_DATA_RETENTION_DAYS", 365)
    )
    derived_settings["FORMS_SUBMISSIONS_API"] = bool(
        derived_settings.get("FORMS_SUBMISSIONS_API", True)
    )

    result = ResolverResult(
        module_name="forms",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["forms"] = _forms_manifest_adapter


# ---------------------------------------------------------------------------
# Backups adapter (C5)
# ---------------------------------------------------------------------------


def _backups_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the backups module via the manifest path.

    Mirrors ``_backups_wiring`` in ``module_wiring_specs.py`` exactly.
    Apps: ``("quickscale_modules_backups",)``.
    Settings: QUICKSCALE_BACKUPS_* keys.

    The conditional private_remote env-var defaulting logic (the gnarly case
    that cannot be expressed declaratively) is reproduced via the
    post-resolution hook.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for backups; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        backups that is equal to the legacy ``_backups_wiring`` output.
    """
    from quickscale_cli.backups_manifest import (  # noqa: PLC0415
        normalize_backups_module_options,
        BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
        BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
        DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
        default_backups_module_options,
    )
    from quickscale_core.manifest.assembler import assemble_wiring_spec  # noqa: PLC0415
    from quickscale_core.manifest.derivation import (  # noqa: PLC0415
        ModuleDerivationSchema,
        WiringProjection,
    )
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        ResolverResult,
        _project_all_wiring,
    )

    # Reproduce the same resolution as the legacy _backups_wiring.
    defaults = default_backups_module_options()
    normalized = normalize_backups_module_options(options)
    resolved: dict[str, Any] = dict(defaults)
    resolved.update(normalized)

    # Reproduce legacy target_mode coercion + validation.
    retention_days = int(resolved.get("retention_days", 14))
    naming_prefix = str(resolved.get("naming_prefix", "db")).strip() or "db"
    target_mode = str(resolved.get("target_mode", "local")).strip().lower()
    if target_mode not in {"local", "private_remote"}:
        target_mode = "local"

    # Reproduce conditional env-var defaulting (the post-resolution hook case).
    access_key_id_env_var = str(
        resolved.get(BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION, "")
    ).strip()
    secret_access_key_env_var = str(
        resolved.get(BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION, "")
    ).strip()
    if target_mode == "private_remote" and not access_key_id_env_var:
        access_key_id_env_var = DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
    if target_mode == "private_remote" and not secret_access_key_env_var:
        secret_access_key_env_var = DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR

    schema = ModuleDerivationSchema(
        module_name="backups",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={"value": ["quickscale_modules_backups"]},
                description="Backups Django app label",
            ),
        ],
    )

    wiring = _project_all_wiring(schema, resolved)

    # Build derived settings directly (complex enough that direct assembly
    # is cleaner than a declarative schema for this module).
    derived_settings: dict[str, Any] = {
        "QUICKSCALE_BACKUPS_RETENTION_DAYS": retention_days,
        "QUICKSCALE_BACKUPS_NAMING_PREFIX": naming_prefix,
        "QUICKSCALE_BACKUPS_TARGET_MODE": target_mode,
        "QUICKSCALE_BACKUPS_LOCAL_DIRECTORY": str(
            resolved.get("local_directory", ".quickscale/backups")
        ).strip()
        or ".quickscale/backups",
        "QUICKSCALE_BACKUPS_AUTOMATION_ENABLED": bool(
            resolved.get("automation_enabled", False)
        ),
        "QUICKSCALE_BACKUPS_SCHEDULE": str(resolved.get("schedule", "0 2 * * *")),
        "QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME": str(
            resolved.get("remote_bucket_name", "")
        ).strip(),
        "QUICKSCALE_BACKUPS_REMOTE_PREFIX": str(
            resolved.get("remote_prefix", "backups/private")
        ).strip()
        or "backups/private",
        "QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL": str(
            resolved.get("remote_endpoint_url", "")
        ).strip(),
        "QUICKSCALE_BACKUPS_REMOTE_REGION_NAME": str(
            resolved.get("remote_region_name", "")
        ).strip(),
        "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR": access_key_id_env_var,
        "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR": secret_access_key_env_var,
    }

    result = ResolverResult(
        module_name="backups",
        defaults={},
        resolved=resolved,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["backups"] = _backups_manifest_adapter


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


class ManifestAdapterNotFound(KeyError):
    """Raised when no manifest adapter is registered for the requested module."""


def build_manifest_wiring_spec(
    module_name: str,
    options: dict[str, Any] | None,
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
    *module_name* via the manifest-driven path.

    Routes the module through its registered manifest adapter (which calls
    the manifest resolver and the assembler) and returns the assembled spec.

    This entry point is **additive**: it does not touch the legacy
    ``build_module_wiring_specs`` dispatch and does not modify any existing
    callers.

    Args:
        module_name: The module to build a spec for (e.g. ``"analytics"``).
        options: Module options from ``quickscale.yml`` or similar.  ``None``
            is treated as an empty dict.
        project_package: The generated project's Python package name.  Some
            adapters use this to qualify app labels or URL include paths.

    Returns:
        A frozen :class:`~quickscale_core.module_wiring.ModuleWiringSpec`.

    Raises:
        ManifestAdapterNotFound: When no manifest adapter is registered for
            *module_name*.  The caller should fall back to the legacy builder
            or handle the error.
    """
    adapter = MANIFEST_ADAPTER_REGISTRY.get(module_name)
    if adapter is None:
        raise ManifestAdapterNotFound(
            f"No manifest adapter registered for module '{module_name}'. "
            f"Registered modules: {sorted(MANIFEST_ADAPTER_REGISTRY)}"
        )

    return adapter(dict(options or {}), project_package=project_package)


__all__ = [
    "MANIFEST_ADAPTER_REGISTRY",
    "ManifestAdapterNotFound",
    "build_manifest_wiring_spec",
]
