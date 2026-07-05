"""
Manifest-driven wiring spec entry point.

Provides :func:`build_manifest_wiring_spec` — the canonical entry point that
routes a module through its manifest adapter and the manifest assembler to
produce a complete :class:`~quickscale_core.module_wiring.ModuleWiringSpec`.

Module adapter registration
---------------------------
Manifest adapters are registered in :data:`MANIFEST_ADAPTER_REGISTRY` via one
of two paths:

1. **Managed origin** (AF7) — modules whose adapter is owned by the module
   package (social, billing, CRM).  The registry entry is established by
   :func:`refresh_managed_adapters`, which imports the module-owned adapter
   from ``quickscale_modules_{name}.adapter`` and fails hard (raises
   :class:`~django.core.exceptions.ImproperlyConfigured`) when the module
   package is not importable.  Bundled/installed-without-module-source is
   not a supported context.

2. **Import-time** — modules registered directly at module load time
   (analytics, blog, listings, forms, backups, notifications, auth, orgs,
   storage).  These are not affected by :func:`refresh_managed_adapters`.

All catalog modules are registered: analytics, billing, blog, listings, CRM,
forms, backups, notifications, auth, orgs, storage, and social.

Batch A modules (analytics, billing, blog, listings, CRM, forms) use the
generic manifest-driven path that loads derivation rules from their
``module.yml`` manifest files (T2.3 Phase 3).  Post-resolution hooks in each
adapter handle module-specific type coercions and static settings that the
declarative resolver cannot express.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quickscale_core.contracts.module_discovery import get_modules_base_path
from quickscale_core.manifest.assembler import (
    PostResolutionHook,
    assemble_wiring_spec,
)
from quickscale_core.manifest.derivation import build_schema_from_manifest
from quickscale_core.manifest.loader import ManifestError, load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config
from quickscale_core.module_wiring import ModuleWiringSpec

# ---------------------------------------------------------------------------
# Generic manifest adapter helpers (T2.3 Phase 3)
# ---------------------------------------------------------------------------

# Modules base path: uses the configurable seam from module_discovery.
# Defaults to the maintainer-monorepo quickscale_modules/ layout, but can
# be overridden via module_discovery.set_modules_base_path() for installed
# or embedded-project contexts.

#: Weak cache of loaded manifests keyed by ``(module_name, base_path)`` so
#: that changing the modules base path at runtime (via
#: :func:`~quickscale_core.contracts.module_discovery.set_modules_base_path`)
#: does not return stale entries from a different context.
_manifest_cache: dict[tuple[str, str], Any] = {}


def load_module_manifest(module_name: str) -> Any:
    """
    Load the ``module.yml`` manifest for *module_name*.

    Uses a module-level cache keyed by ``(module_name, base_path_str)`` to
    avoid re-reading the YAML file on every adapter invocation while still
    remaining correct when the modules base path changes between contexts
    (e.g. installed/planner vs. embedded project).  Raises
    :class:`ManifestError` when the manifest file is missing or invalid.

    Args:
        module_name: The module name (e.g. ``"analytics"``).

    Returns:
        A :class:`~quickscale_core.manifest.schema.ModuleManifest`.
    """
    base_path = get_modules_base_path()
    cache_key = (module_name, str(base_path))
    cached = _manifest_cache.get(cache_key)
    if cached is not None:
        return cached

    manifest_path = base_path / module_name / "module.yml"
    manifest = load_manifest_from_path(manifest_path)
    _manifest_cache[cache_key] = manifest
    return manifest


# Backward-compat alias for in-repo callers that import the private name.
_load_module_manifest = load_module_manifest


def build_generic_manifest_spec(
    module_name: str,
    options: dict[str, Any] | None,
    *,
    project_package: str | None = None,
    post_hook: PostResolutionHook | None = None,
) -> ModuleWiringSpec:
    """
    Build a :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
    *module_name* using the declarative derivation rules in its ``module.yml``.

    This is the generic entry point for Batch A modules whose derivation
    rules (wiring projections, option derivations, derived settings) are
    declared in the module's manifest rather than hardcoded in Python.

    The caller can supply an optional *post_hook* for module-specific logic
    that the declarative resolver cannot express (type coercions, static
    settings, conditional branches).

    This function is the **public** version of the generic manifest path.  It
    is used by module-owned adapters (social, billing, CRM) as well as the
    import-time-registered modules.  The underscore-prefixed alias
    ``_build_generic_manifest_spec`` is preserved for backward compatibility.

    Args:
        module_name: The module name (e.g. ``"analytics"``).
        options: Module options (e.g. from ``quickscale.yml``).  ``None``
            is treated as an empty dict.
        project_package: Unused by generic path; present for signature
            parity with adapters that need it.
        post_hook: Optional post-resolution hook for module-specific
            coercions and static settings.

    Returns:
        A frozen :class:`~quickscale_core.module_wiring.ModuleWiringSpec`.

    Raises:
        ManifestError: If the module's manifest cannot be loaded or has no
            derivation section.
    """
    manifest = load_module_manifest(module_name)
    schema = build_schema_from_manifest(
        manifest_name=module_name,
        wiring_projections=manifest.wiring_projections,
        derived_settings=manifest.derived_settings,
        option_derivations=manifest.option_derivations,
        version="1",
    )

    result = resolve_module_config(
        manifest,
        schema,
        overrides=dict(options or {}),
    )

    return assemble_wiring_spec(result, post_hook=post_hook)


# Backward-compat alias for in-repo callers that import the private name.
_build_generic_manifest_spec = build_generic_manifest_spec


# ---------------------------------------------------------------------------
# Adapter registry + origin tracking
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

#: Set of module names whose registry entry is "managed" — auto-registered
#: by the system from module-owned adapters.  Custom entries added by end
#: users (or by extensions that are not part of the shipped catalog) are
#: **not** tracked here and survive :func:`refresh_managed_adapters` unchanged.
MANAGED_ADAPTER_ORIGINS: set[str] = set()


def refresh_managed_adapters() -> None:
    """
    Refresh managed adapter entries in :data:`MANIFEST_ADAPTER_REGISTRY`
    based on the current modules base path.

    For each module name in :data:`MANAGED_ADAPTER_ORIGINS`:

    * If the module has a ``module.yml`` at the active base path **and** the
      module-owned adapter package (``quickscale_modules_{name}.adapter``) is
      importable, the adapter is registered.  This is the primary path for
      monorepo development and embedded project ``modules/<name>/``
      directories.

    * If the module's ``module.yml`` is at the active base path but the
      module-owned adapter **cannot** be imported, an
      :class:`~django.core.exceptions.ImproperlyConfigured` exception is
      raised — bundled/installed-without-module-source is not a supported
      context.

    * If the module is **not** present at the active base path, it is
      removed from :data:`MANIFEST_ADAPTER_REGISTRY` to avoid stale entries,
      but kept in :data:`MANAGED_ADAPTER_ORIGINS` so it is re-evaluated
      when the base path changes.

    The :data:`MANIFEST_ADAPTER_REGISTRY` dict identity is preserved across
    refreshes so that existing references remain valid.  Custom entries
    (those not in :data:`MANAGED_ADAPTER_ORIGINS`) are **preserved** unchanged.

    Call this after :func:`~quickscale_core.contracts.module_discovery.set_modules_base_path`
    to keep the registry consistent with the current path context.

    Raises:
        ImproperlyConfigured: If a managed module's manifest is found at the
            active base path but its Python adapter package is not importable.
    """
    import importlib  # noqa: PLC0415

    from django.core.exceptions import ImproperlyConfigured  # noqa: PLC0415

    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        discover_shipped_module_names,
    )

    shipped_at_base = set(discover_shipped_module_names())

    for module_name in list(MANAGED_ADAPTER_ORIGINS):
        if module_name not in shipped_at_base:
            # Module is not available at the current base path — remove
            # from the registry so stale entries don't persist.  Keep the
            # name in MANAGED_ADAPTER_ORIGINS so it gets re-evaluated on
            # the next refresh (e.g. when base path changes to a context
            # where the module-owned adapter is available).
            MANIFEST_ADAPTER_REGISTRY.pop(module_name, None)
            continue

        # Module has a manifest at the active base path — the module-owned
        # adapter MUST be importable.  Fail hard if it is not.
        try:
            adapter_module = importlib.import_module(
                f"quickscale_modules_{module_name}.adapter"
            )
        except ImportError as exc:
            raise ImproperlyConfigured(
                f"Managed adapter for '{module_name}' not importable: "
                f"quickscale_modules_{module_name}.adapter could not be loaded. "
                f"The module package must be installed and importable."
            ) from exc

        sentinel = getattr(adapter_module, "get_manifest_adapter", None)
        if sentinel is not None:
            MANIFEST_ADAPTER_REGISTRY[module_name] = sentinel()
            continue

        raise ImproperlyConfigured(
            f"Managed adapter for '{module_name}' not importable: "
            f"quickscale_modules_{module_name}.adapter has no "
            f"get_manifest_adapter function."
        )


# ---------------------------------------------------------------------------
# Analytics adapter (first migrated module — uses generic manifest path)
# ---------------------------------------------------------------------------


def _analytics_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """
    Apply analytics-specific type coercions and fallback defaults.

    The generic resolver handles wiring projections and option derivations
    declared in ``module.yml``.  This hook reproduces the legacy boolean/string
    coercions and fallback defaults that the resolver cannot express
    declaratively.

    PR-4 hazard: when ``enabled`` is ``False``, the legacy wiring returns an
    EMPTY ``ModuleWiringSpec``.  This hook reproduces that behaviour.
    """
    # PR-4 short-circuit: legacy returns an empty spec when disabled.
    if not bool(resolved.get("enabled", True)):
        return ModuleWiringSpec()

    settings = dict(spec.settings)

    # Boolean coercions.
    for bool_key in (
        "QUICKSCALE_ANALYTICS_ENABLED",
        "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG",
        "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF",
        "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
    ):
        if bool_key in settings:
            settings[bool_key] = bool(settings[bool_key])

    # String coercions.
    for str_key in (
        "QUICKSCALE_ANALYTICS_PROVIDER",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    ):
        if str_key in settings:
            settings[str_key] = str(settings[str_key]).strip()

    # SA18.2: Fail-hard on empty-after-resolution analytics settings.
    # An empty result after resolution means the manifest derivation
    # produced an invalid result — raise descriptively instead of
    # silently defaulting to PostHog values.
    _required_nonempty = (
        "QUICKSCALE_ANALYTICS_PROVIDER",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    )
    empty_keys = [k for k in _required_nonempty if k in settings and not settings[k]]
    if empty_keys:
        raise ManifestError(
            f"Analytics manifest settings resolved to empty values: "
            f"{', '.join(sorted(empty_keys))}. "
            f"The manifest derivation produced an invalid result."
        )

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _analytics_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the analytics module via the manifest path.

    Uses the generic manifest-driven path that reads derivation rules
    (wiring projections, option derivations) from the analytics ``module.yml``
    manifest.  A post-resolution hook applies the type coercions and fallback
    defaults that the legacy ``analytics_contract.py`` used.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for analytics; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        analytics.
    """
    return _build_generic_manifest_spec(
        "analytics",
        options,
        post_hook=_analytics_post_hook,
    )


# Register analytics as the first manifest-driven adapter.
MANIFEST_ADAPTER_REGISTRY["analytics"] = _analytics_manifest_adapter


# ---------------------------------------------------------------------------
# Billing — managed adapter
# ---------------------------------------------------------------------------
# The billing adapter lives in ``quickscale_modules_billing.adapter`` and is
# auto-registered by :func:`refresh_managed_adapters`.

MANAGED_ADAPTER_ORIGINS.add("billing")


# ---------------------------------------------------------------------------
# Blog adapter (C4 — uses generic manifest path)
# ---------------------------------------------------------------------------


def _blog_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply blog-specific type coercions and static markdownx settings."""
    settings = dict(spec.settings)

    # Legacy int()/bool()/str() coercions.
    settings["BLOG_POSTS_PER_PAGE"] = int(settings.get("BLOG_POSTS_PER_PAGE", 10))
    settings["BLOG_ENABLE_RSS"] = bool(settings.get("BLOG_ENABLE_RSS", True))
    api_rate = str(settings.get("BLOG_API_RATE_LIMIT", "")).strip()
    settings["BLOG_API_RATE_LIMIT"] = api_rate or "5/hour"

    # Static markdownx settings (identical to legacy).
    settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]
    settings["MARKDOWNX_MEDIA_PATH"] = "blog/markdownx/"

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _blog_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the blog module via the manifest path.

    Uses the generic manifest-driven path that reads derivation rules from the
    blog ``module.yml`` manifest.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for blog; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        blog that is equal to the legacy ``_blog_wiring`` output.
    """
    return _build_generic_manifest_spec(
        "blog",
        options,
        post_hook=_blog_post_hook,
    )


MANIFEST_ADAPTER_REGISTRY["blog"] = _blog_manifest_adapter


# ---------------------------------------------------------------------------
# Listings adapter (C3 — uses generic manifest path)
# ---------------------------------------------------------------------------


def _listings_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply listings-specific int coercion and static markdownx settings."""
    settings = dict(spec.settings)

    # Legacy int() coercion.
    settings["LISTINGS_PER_PAGE"] = int(settings.get("LISTINGS_PER_PAGE", 12))

    # Static markdownx settings (identical to legacy).
    settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _listings_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the listings module via the manifest path.

    Uses the generic manifest-driven path that reads derivation rules from the
    listings ``module.yml`` manifest.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for listings; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        listings that is equal to the legacy ``_listings_wiring`` output.
    """
    return _build_generic_manifest_spec(
        "listings",
        options,
        post_hook=_listings_post_hook,
    )


MANIFEST_ADAPTER_REGISTRY["listings"] = _listings_manifest_adapter


# ---------------------------------------------------------------------------
# CRM — managed adapter
# ---------------------------------------------------------------------------
# The CRM adapter lives in ``quickscale_modules_crm.adapter`` and is
# auto-registered by :func:`refresh_managed_adapters`.

MANAGED_ADAPTER_ORIGINS.add("crm")


# ---------------------------------------------------------------------------
# Forms adapter (C7 — uses generic manifest path)
# ---------------------------------------------------------------------------


def _forms_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply forms-specific int/bool/str coercions."""
    settings = dict(spec.settings)

    # Legacy int()/bool()/str() coercions.
    settings["FORMS_PER_PAGE"] = int(settings.get("FORMS_PER_PAGE", 25))
    settings["FORMS_SPAM_PROTECTION"] = bool(
        settings.get("FORMS_SPAM_PROTECTION", True)
    )
    settings["FORMS_RATE_LIMIT"] = str(settings.get("FORMS_RATE_LIMIT", "5/hour"))
    settings["FORMS_DATA_RETENTION_DAYS"] = int(
        settings.get("FORMS_DATA_RETENTION_DAYS", 365)
    )
    settings["FORMS_SUBMISSIONS_API"] = bool(
        settings.get("FORMS_SUBMISSIONS_API", True)
    )

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _forms_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the forms module via the manifest path.

    Uses the generic manifest-driven path that reads derivation rules from the
    forms ``module.yml`` manifest.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for forms; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        forms that is equal to the legacy ``_forms_wiring`` output.
    """
    return _build_generic_manifest_spec(
        "forms",
        options,
        post_hook=_forms_post_hook,
    )


MANIFEST_ADAPTER_REGISTRY["forms"] = _forms_manifest_adapter


# ---------------------------------------------------------------------------
# Backups adapter (C5)
# ---------------------------------------------------------------------------


def _backups_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the backups module via the manifest path.

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
    from quickscale_core.contracts.module_options import (  # noqa: PLC0415
        BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
        BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
        DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
        normalize_backups_module_options,
    )
    from quickscale_core.contracts.resolvers import (  # noqa: PLC0415
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
# Notifications adapter (M4 follow-up — Phase 1)
# ---------------------------------------------------------------------------


def _notifications_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the notifications module via the manifest path.

    Apps: ``("quickscale_modules_notifications",)`` with ``"anymail"`` prepended
    when the runtime email backend is the live Resend backend.
    URL includes: ``[("", "quickscale_modules_notifications.urls")]``.
    Settings: QUICKSCALE_NOTIFICATIONS_* keys plus conditional EMAIL_BACKEND,
    DEFAULT_FROM_EMAIL, and SERVER_EMAIL keys.

    The conditional anymail app and email-backend settings are applied via the
    assembler post-resolution hook because the generic resolver cannot express
    cross-option conditional wiring.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for notifications; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        notifications that is equal to the legacy ``_notifications_wiring``
        output.
    """
    from quickscale_core.contracts.module_options import (  # noqa: PLC0415
        NOTIFICATIONS_LIVE_EMAIL_BACKEND,
    )
    from quickscale_core.contracts.resolvers import (  # noqa: PLC0415
        notifications_runtime_email_backend,
        resolve_notifications_module_options,
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

    resolved = resolve_notifications_module_options(options)
    runtime_email_backend = notifications_runtime_email_backend(resolved)

    schema = ModuleDerivationSchema(
        module_name="notifications",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={"value": ["quickscale_modules_notifications"]},
                description="Notifications Django app label",
            ),
            WiringProjection(
                wiring_field="url_includes",
                derivation_type="static",
                expression={"value": [["", "quickscale_modules_notifications.urls"]]},
                description="Notifications URL includes",
            ),
        ],
        option_derivations={
            "enabled": OptionDerivation(
                option_key="enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_ENABLED",
                        source_options=["enabled"],
                        derivation_type="direct",
                        expression={"option": "enabled"},
                    ),
                ],
            ),
            "sender_name": OptionDerivation(
                option_key="sender_name",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_SENDER_NAME",
                        source_options=["sender_name"],
                        derivation_type="direct",
                        expression={"option": "sender_name"},
                    ),
                ],
            ),
            "sender_email": OptionDerivation(
                option_key="sender_email",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL",
                        source_options=["sender_email"],
                        derivation_type="direct",
                        expression={"option": "sender_email"},
                    ),
                ],
            ),
            "reply_to_email": OptionDerivation(
                option_key="reply_to_email",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL",
                        source_options=["reply_to_email"],
                        derivation_type="direct",
                        expression={"option": "reply_to_email"},
                    ),
                ],
            ),
            "resend_domain": OptionDerivation(
                option_key="resend_domain",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN",
                        source_options=["resend_domain"],
                        derivation_type="direct",
                        expression={"option": "resend_domain"},
                    ),
                ],
            ),
            "resend_api_key_env_var": OptionDerivation(
                option_key="resend_api_key_env_var",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR",
                        source_options=["resend_api_key_env_var"],
                        derivation_type="direct",
                        expression={"option": "resend_api_key_env_var"},
                    ),
                ],
            ),
            "webhook_secret_env_var": OptionDerivation(
                option_key="webhook_secret_env_var",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR",
                        source_options=["webhook_secret_env_var"],
                        derivation_type="direct",
                        expression={"option": "webhook_secret_env_var"},
                    ),
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
                    ),
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
                    ),
                ],
            ),
            "webhook_ttl_seconds": OptionDerivation(
                option_key="webhook_ttl_seconds",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS",
                        source_options=["webhook_ttl_seconds"],
                        derivation_type="direct",
                        expression={"option": "webhook_ttl_seconds"},
                    ),
                ],
            ),
        },
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # Reproduce legacy coercions exactly.
    derived_settings["QUICKSCALE_NOTIFICATIONS_ENABLED"] = bool(
        derived_settings.get("QUICKSCALE_NOTIFICATIONS_ENABLED", True)
    )
    for str_key in (
        "QUICKSCALE_NOTIFICATIONS_SENDER_NAME",
        "QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL",
        "QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL",
        "QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN",
        "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR",
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR",
    ):
        if str_key in derived_settings:
            derived_settings[str_key] = str(derived_settings[str_key]).strip()

    derived_settings["QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS"] = list(
        derived_settings.get("QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS", [])
    )
    derived_settings["QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS"] = list(
        derived_settings.get("QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS", [])
    )
    derived_settings["QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS"] = int(
        derived_settings.get("QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS", 300)
    )

    # Static setting that is not derived from any option.
    derived_settings["QUICKSCALE_NOTIFICATIONS_PROVIDER"] = "resend"

    result = ResolverResult(
        module_name="notifications",
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

    # Post-resolution hook: conditional anymail app and email settings.
    def _notifications_post_hook(
        spec: ModuleWiringSpec, resolved_opts: dict[str, Any]
    ) -> ModuleWiringSpec:
        from quickscale_core.module_wiring import (
            ModuleWiringSpec as _MWS,
        )

        apps = list(spec.apps)
        if runtime_email_backend == NOTIFICATIONS_LIVE_EMAIL_BACKEND:
            if "anymail" not in apps:
                apps.insert(0, "anymail")

        settings = dict(spec.settings)
        if runtime_email_backend is not None:
            settings["EMAIL_BACKEND"] = runtime_email_backend
            sender_email = settings.get("QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL", "")
            settings["DEFAULT_FROM_EMAIL"] = sender_email
            settings["SERVER_EMAIL"] = sender_email

        return _MWS(
            apps=tuple(apps),
            middleware=spec.middleware,
            settings=settings,
            pre_home_url_includes=spec.pre_home_url_includes,
            url_includes=spec.url_includes,
            managed_files=spec.managed_files,
        )

    return assemble_wiring_spec(result, post_hook=_notifications_post_hook)


MANIFEST_ADAPTER_REGISTRY["notifications"] = _notifications_manifest_adapter


# ---------------------------------------------------------------------------
# Auth adapter (Track 2 Phase 1.1-1.2 / M4 follow-up)
# ---------------------------------------------------------------------------


def _auth_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the auth module via the manifest path.

    Apps: ``("django.contrib.sites", "quickscale_modules_auth", "allauth",
    "allauth.account")``.
    Middleware: ``("allauth.account.middleware.AccountMiddleware",)``.
    URL includes: ``(("accounts/", "allauth.urls"),
    ("accounts/", "quickscale_modules_auth.urls"))``.
    Settings: allauth/auth-specific keys derived from resolved options,
    including login-method branching (``ACCOUNT_LOGIN_METHODS`` and
    ``ACCOUNT_SIGNUP_FIELDS``) and legacy ``allow_registration``
    normalisation fallback.

    The login-method branching (``authentication_method`` -> set of login
    methods + signup fields) is applied directly in the adapter because the
    generic derivation schema cannot express one-option-to-two-compound-
    setting projections.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for auth; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        auth that is equal to the legacy ``_auth_wiring`` output.
    """
    from quickscale_core.contracts.resolvers import (  # noqa: PLC0415
        resolve_auth_module_options,
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

    resolved = resolve_auth_module_options(options)

    # Login-method branching (same logic as legacy _auth_wiring).
    authentication_method = resolved.get("authentication_method", "email")
    if authentication_method == "username":
        login_methods: set[str] = {"username"}
        signup_fields: list[str] = ["username*", "password1*", "password2*"]
    elif authentication_method == "both":
        login_methods = {"email", "username"}
        signup_fields = ["email*", "username*", "password1*", "password2*"]
    else:
        login_methods = {"email"}
        signup_fields = ["email*", "password1*", "password2*"]

    # Build settings dict directly (compound values cannot use the generic
    # OptionDerivation -> DerivedSetting pipeline).
    derived_settings: dict[str, Any] = {
        "AUTHENTICATION_BACKENDS": [
            "django.contrib.auth.backends.ModelBackend",
            "allauth.account.auth_backends.AuthenticationBackend",
        ],
        "AUTH_USER_MODEL": "quickscale_modules_auth.User",
        "SITE_ID": 1,
        "ACCOUNT_LOGIN_METHODS": login_methods,
        "ACCOUNT_SIGNUP_FIELDS": signup_fields,
        "ACCOUNT_EMAIL_VERIFICATION": resolved.get("email_verification", "none"),
        "ACCOUNT_ALLOW_REGISTRATION": bool(resolved.get("registration_enabled", True)),
        "ACCOUNT_ADAPTER": (
            "quickscale_modules_auth.adapters.QuickscaleAccountAdapter"
        ),
        "ACCOUNT_SIGNUP_FORM_CLASS": ("quickscale_modules_auth.forms.SignupForm"),
        "LOGIN_REDIRECT_URL": "/accounts/profile/",
        "LOGOUT_REDIRECT_URL": "/",
        "SESSION_COOKIE_AGE": int(resolved.get("session_cookie_age", 1209600)),
    }

    schema = ModuleDerivationSchema(
        module_name="auth",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={
                    "value": [
                        "django.contrib.sites",
                        "quickscale_modules_auth",
                        "allauth",
                        "allauth.account",
                    ]
                },
                description="Auth Django app labels",
            ),
            WiringProjection(
                wiring_field="middleware",
                derivation_type="static",
                expression={"value": ["allauth.account.middleware.AccountMiddleware"]},
                description="Auth middleware",
            ),
            WiringProjection(
                wiring_field="url_includes",
                derivation_type="static",
                expression={
                    "value": [
                        ["accounts/", "allauth.urls"],
                        ["accounts/", "quickscale_modules_auth.urls"],
                    ]
                },
                description="Auth URL includes",
            ),
        ],
    )

    wiring = _project_all_wiring(schema, resolved)

    result = ResolverResult(
        module_name="auth",
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


MANIFEST_ADAPTER_REGISTRY["auth"] = _auth_manifest_adapter


# ---------------------------------------------------------------------------
# Orgs adapter (Track 2 Phase 1.1-1.2 / M4 follow-up)
# ---------------------------------------------------------------------------


def _orgs_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the orgs module via the manifest path.

    Apps: ``("quickscale_modules_orgs",)``.
    Middleware: ``("quickscale_modules_orgs.middleware.TenantMiddleware",)``.
    Settings: ``ACCOUNT_ADAPTER`` and ``QUICKSCALE_MODE`` derived from
    resolved options.

    The conditional URL wiring (``pre_home_url_includes`` for solo mode vs
    ``url_includes`` for saas mode) is applied via the assembler
    post-resolution hook because the generic resolver cannot express
    cross-option conditional wiring placement.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for orgs; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        orgs that is equal to the legacy ``_orgs_wiring`` output.
    """
    from quickscale_core.contracts.resolvers import (  # noqa: PLC0415
        resolve_orgs_module_options,
        validate_orgs_module_options,
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

    resolved = resolve_orgs_module_options(options)
    validation_issues = validate_orgs_module_options(options)
    mode = str(resolved.get("mode", "solo")).strip().lower()

    schema = ModuleDerivationSchema(
        module_name="orgs",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={"value": ["quickscale_modules_orgs"]},
                description="Orgs Django app label",
            ),
            WiringProjection(
                wiring_field="middleware",
                derivation_type="static",
                expression={
                    "value": ["quickscale_modules_orgs.middleware.TenantMiddleware"]
                },
                description="Orgs middleware",
            ),
        ],
        option_derivations={
            "mode": OptionDerivation(
                option_key="mode",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_MODE",
                        source_options=["mode"],
                        derivation_type="direct",
                        expression={"option": "mode"},
                    ),
                ],
            ),
        },
    )

    wiring = _project_all_wiring(schema, resolved)
    derived_settings = _project_all_derived_settings(schema, resolved)

    # Static setting that is not derived from any option.
    derived_settings["ACCOUNT_ADAPTER"] = (
        "quickscale_modules_orgs.adapters.OrgsAccountAdapter"
    )

    # Reproduce legacy str() coercion on QUICKSCALE_MODE.
    if "QUICKSCALE_MODE" in derived_settings:
        derived_settings["QUICKSCALE_MODE"] = str(
            derived_settings["QUICKSCALE_MODE"]
        ).strip()

    # Conditional URL wiring: solo → pre_home_url_includes, saas → url_includes.
    root_include = (("", "quickscale_modules_orgs.urls"),)
    if mode == "solo":
        pre_home: tuple[tuple[str, str], ...] = root_include
        post_home: tuple[tuple[str, str], ...] = ()
    else:
        pre_home = ()
        post_home = root_include

    result = ResolverResult(
        module_name="orgs",
        defaults={},
        resolved=resolved,
        validation_issues=validation_issues,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=post_home,
        pre_home_url_includes=pre_home,
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["orgs"] = _orgs_manifest_adapter


# ---------------------------------------------------------------------------
# Storage adapter (Track 2 Phase 1.1-1.2 / M4 follow-up)
# ---------------------------------------------------------------------------


def _storage_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """
    Build a ModuleWiringSpec for the storage module via the manifest path.

    Apps: ``("quickscale_modules_storage",)``.
    Settings: ``QUICKSCALE_STORAGE_BACKEND``, ``QUICKSCALE_STORAGE_PUBLIC_BASE_URL``,
    ``MEDIA_URL``, ``QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED``, plus conditional
    ``STORAGES`` and ``AWS_*`` keys when backend is ``"s3"`` or ``"r2"``.

    The conditional cloud-provider settings (STORAGES dict and AWS_* keys)
    are applied directly in the adapter because the generic derivation schema
    cannot express cross-option conditional settings.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for storage; present for signature parity.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
        storage that is equal to the legacy ``_storage_wiring`` output.
    """
    from quickscale_core.contracts.resolvers import (  # noqa: PLC0415
        resolve_storage_module_options,
        validate_storage_module_options,
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

    resolved = resolve_storage_module_options(options)
    validation_issues = validate_storage_module_options(options)
    backend = str(resolved.get("backend", "local")).lower()

    schema = ModuleDerivationSchema(
        module_name="storage",
        version="1",
        module_wiring_projections=[
            WiringProjection(
                wiring_field="apps",
                derivation_type="static",
                expression={"value": ["quickscale_modules_storage"]},
                description="Storage Django app label",
            ),
        ],
    )

    wiring = _project_all_wiring(schema, resolved)

    # Build derived settings directly (conditional cloud settings cannot use
    # the generic OptionDerivation -> DerivedSetting pipeline).
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
        access_key_id = str(resolved.get("access_key_id", "")).strip()
        secret_access_key = str(resolved.get("secret_access_key", "")).strip()
        default_acl = str(resolved.get("default_acl", "")).strip()
        querystring_auth = bool(resolved.get("querystring_auth", False))

        storage_options: dict[str, Any] = {
            "querystring_auth": querystring_auth,
        }
        if access_key_id:
            storage_options["access_key"] = access_key_id
        if secret_access_key:
            storage_options["secret_key"] = secret_access_key
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
        if access_key_id:
            derived_settings["AWS_ACCESS_KEY_ID"] = access_key_id
        if secret_access_key:
            derived_settings["AWS_SECRET_ACCESS_KEY"] = secret_access_key
        if default_acl:
            derived_settings["AWS_DEFAULT_ACL"] = default_acl

    result = ResolverResult(
        module_name="storage",
        defaults={},
        resolved=resolved,
        validation_issues=validation_issues,
        derived_settings=derived_settings,
        apps=tuple(wiring["apps"]),
        middleware=tuple(wiring["middleware"]),
        url_includes=tuple((str(a), str(b)) for a, b in wiring["url_includes"]),
        pre_home_url_includes=tuple(
            (str(a), str(b)) for a, b in wiring["pre_home_url_includes"]
        ),
    )

    return assemble_wiring_spec(result)


MANIFEST_ADAPTER_REGISTRY["storage"] = _storage_manifest_adapter


# ---------------------------------------------------------------------------
# Social — managed adapter
# ---------------------------------------------------------------------------
# The social adapter lives in ``quickscale_modules_social.adapter`` and is
# auto-registered by :func:`refresh_managed_adapters`.

MANAGED_ADAPTER_ORIGINS.add("social")

# ---------------------------------------------------------------------------
# Lazy initialisation guard
# ---------------------------------------------------------------------------
# The import-time refresh_managed_adapters() call below can fail due to a
# circular import when the import chain goes through contracts.resolvers
# before that module has finished loading (e.g. via module_wiring_manager).
# If it fails, the adapters are registered lazily on first use.

_ADAPTERS_INITIALIZED: bool = False


def _is_import_time_adapter_circular_import(error: Exception) -> bool:
    """
    Return True when *error* is the documented lazy-init circular import.

    The only tolerated import-time failures are the known partially-initialized
    core-module cycles encountered while module-owned adapters import
    ``build_generic_manifest_spec`` during entry-point initialisation.
    Recognised patterns:
    - ``quickscale_core.manifest.entry_point``
    - ``quickscale_core.contracts.resolvers``
    - ``quickscale_core.runtime``  (SA20 closeout — e.g. social adapter via
      backups admin autodiscovery)
    """
    cause = error.__cause__
    if not isinstance(cause, ImportError):
        return False

    message = str(cause)
    return (
        "partially initialized module" in message
        and "circular import" in message
        and (
            "quickscale_core.manifest.entry_point" in message
            or "quickscale_core.contracts.resolvers" in message
            or "quickscale_core.runtime" in message
        )
    )


def _ensure_adapters_initialized() -> None:
    """
    One-time lazy initialisation of managed adapters.

    Called by :func:`build_manifest_wiring_spec` when the import-time
    refresh failed (circular import during module initialisation).

    If the refresh fails (e.g. a managed module's Python adapter package
    is not importable), the ``_ADAPTERS_INITIALIZED`` flag is NOT set so
    that subsequent calls retry the initialisation and continue surfacing
    the real managed-adapter failure (CR-SA18.1-002).
    """
    global _ADAPTERS_INITIALIZED
    if not _ADAPTERS_INITIALIZED:
        refresh_managed_adapters()
        _ADAPTERS_INITIALIZED = True


def _initialize_managed_adapters_at_import() -> None:
    """
    Eagerly initialise managed adapters unless the known circular import hits.

    Broken adapter imports must fail at import time. Only the documented
    partially-initialized core-module circular import is deferred to
    :func:`build_manifest_wiring_spec`'s lazy initialisation path.
    """
    from django.core.exceptions import ImproperlyConfigured  # noqa: PLC0415

    global _ADAPTERS_INITIALIZED

    try:
        refresh_managed_adapters()
    except ImproperlyConfigured as exc:
        if _is_import_time_adapter_circular_import(exc):
            return
        raise

    _ADAPTERS_INITIALIZED = True


# Initialise all managed adapters (social, billing, CRM) in one pass so
# the registry is consistent at import time.  Gracefully handle circular
# imports during module initialisation (ImportError raised from adapter
# package imports, then re-raised as ImproperlyConfigured by
# refresh_managed_adapters) — the adapters are lazily initialised on the
# first call to :func:`build_manifest_wiring_spec`.
_initialize_managed_adapters_at_import()


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
    """
    Build a :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for
    *module_name* via the manifest-driven path.

    Routes the module through its registered manifest adapter (which calls
    the manifest resolver and the assembler) and returns the assembled spec.

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
    _ensure_adapters_initialized()
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
    "build_generic_manifest_spec",
    "build_manifest_wiring_spec",
    "load_module_manifest",
    "refresh_managed_adapters",
]
