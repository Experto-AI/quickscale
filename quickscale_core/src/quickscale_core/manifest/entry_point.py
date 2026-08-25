"""
Manifest-driven wiring spec entry point.

Provides :func:`build_manifest_wiring_spec` — the canonical entry point that
routes a module through its manifest adapter and the manifest assembler to
produce a complete :class:`~quickscale_core.module_wiring.ModuleWiringSpec`.

Module adapter registration
---------------------------
Manifest adapters are registered in :data:`MANIFEST_ADAPTER_REGISTRY` via one
of two paths:

1. **Inline registration** — modules registered directly at module load time
   (auth, orgs, and storage).  These are not affected
   by :func:`refresh_managed_adapters`.

2. **Managed origin** (AF7) — modules whose adapter is owned by the module
   package (analytics, backups, billing, blog, listings, CRM, forms,
   notifications, and social).  The
   registry entry is established by
   :func:`refresh_managed_adapters`, which imports the module-owned adapter
   from ``quickscale_modules_{name}.adapter`` and fails hard (raises
   :class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured`) when the module
   package is not importable.  Bundled/installed-without-module-source is
   not a supported context.

   Managed adapters are NOT registered at import time.  The caller (typically
   :func:`~quickscale_cli.utils.module_wiring_manager.regenerate_managed_wiring`)
   must invoke :func:`refresh_managed_adapters` explicitly before calling
   :func:`build_manifest_wiring_spec` for managed modules.

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
import sys
from typing import Any, cast

from quickscale_core.contracts.module_discovery import get_modules_base_path
from quickscale_core.manifest.assembler import (
    PostResolutionHook,
    assemble_wiring_spec,
)
from quickscale_core.manifest.derivation import build_schema_from_manifest
from quickscale_core.manifest.loader import load_manifest_from_path
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
    is used by the generic module-owned adapters as well as the remaining
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


def _build_manifest_wiring_schema(module_name: str) -> Any:
    """Build the typed wiring schema declared by a module's manifest."""
    manifest = load_module_manifest(module_name)
    return build_schema_from_manifest(
        manifest_name=module_name,
        wiring_projections=manifest.wiring_projections,
    )


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


def _is_package_module(module_name: str, package_name: str) -> bool:
    return module_name == package_name or module_name.startswith(f"{package_name}.")


def _snapshot_package_modules(package_name: str) -> dict[str, Any]:
    return {
        name: module
        for name, module in sys.modules.items()
        if _is_package_module(name, package_name)
    }


def _evict_package_modules(package_name: str) -> None:
    for name in list(sys.modules):
        if _is_package_module(name, package_name):
            sys.modules.pop(name, None)


def _load_managed_adapter(module_name: str) -> Callable[..., ModuleWiringSpec]:
    """Load one adapter from the active base without leaking import state."""
    import importlib  # noqa: PLC0415

    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        ImproperlyConfigured,
    )

    package_name = f"quickscale_modules_{module_name}"
    adapter_name = f"{package_name}.adapter"
    adapter_src_path = get_modules_base_path() / module_name / "src"
    original_sys_path = sys.path.copy()
    original_package_modules = _snapshot_package_modules(package_name)
    try:
        _evict_package_modules(package_name)
        if adapter_src_path.is_dir():
            sys.path.insert(0, str(adapter_src_path))
        importlib.invalidate_caches()
        adapter_module = importlib.import_module(adapter_name)
        sentinel = getattr(adapter_module, "get_manifest_adapter", None)
        if sentinel is None:
            raise ImproperlyConfigured(
                f"Managed adapter for '{module_name}' not importable: "
                f"{adapter_name} has no get_manifest_adapter function."
            )
        return cast(Callable[..., ModuleWiringSpec], sentinel())
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"Managed adapter for '{module_name}' not importable: "
            f"{adapter_name} could not be loaded. "
            f"The module package must be installed and importable."
        ) from exc
    finally:
        sys.path[:] = original_sys_path
        _evict_package_modules(package_name)
        sys.modules.update(original_package_modules)


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
       :class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured` exception is
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
    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        discover_shipped_module_names,
    )

    shipped_at_base = set(discover_shipped_module_names())
    loaded_adapters: dict[str, Callable[..., ModuleWiringSpec]] = {}

    # Resolve every available managed adapter before mutating the live registry.
    # A failed refresh is fail-hard and atomic: callers retain the complete prior
    # registry rather than a set whose contents depend on iteration order.
    for module_name in sorted(MANAGED_ADAPTER_ORIGINS):
        if module_name not in shipped_at_base:
            continue

        # Module has a manifest at the active base path — load its adapter from
        # that exact source context.  Import state is transactional: neither a
        # successful nor a failed probe may leave package entries cached for a
        # later project/base-path refresh.
        loaded_adapters[module_name] = _load_managed_adapter(module_name)

    # Commit only after the complete managed set resolved successfully.  Dict
    # identity and custom entries are preserved while unavailable managed
    # entries are removed from the active context.
    for module_name in MANAGED_ADAPTER_ORIGINS - loaded_adapters.keys():
        MANIFEST_ADAPTER_REGISTRY.pop(module_name, None)
    MANIFEST_ADAPTER_REGISTRY.update(loaded_adapters)


# Analytics is module-owned and refreshed from its public sentinel.
MANAGED_ADAPTER_ORIGINS.add("analytics")


# ---------------------------------------------------------------------------
# Billing — managed adapter
# ---------------------------------------------------------------------------
# The billing adapter lives in ``quickscale_modules_billing.adapter`` and is
# auto-registered by :func:`refresh_managed_adapters`.

MANAGED_ADAPTER_ORIGINS.add("billing")


# Blog is module-owned and refreshed from its public sentinel.
MANAGED_ADAPTER_ORIGINS.add("blog")


# Listings is module-owned and refreshed from its public sentinel.
MANAGED_ADAPTER_ORIGINS.add("listings")


# ---------------------------------------------------------------------------
# CRM — managed adapter
# ---------------------------------------------------------------------------
# The CRM adapter lives in ``quickscale_modules_crm.adapter`` and is
# auto-registered by :func:`refresh_managed_adapters`.

MANAGED_ADAPTER_ORIGINS.add("crm")


# Forms is module-owned and refreshed from its public sentinel.
MANAGED_ADAPTER_ORIGINS.add("forms")


# Backups is module-owned and refreshed from its public sentinel.
MANAGED_ADAPTER_ORIGINS.add("backups")


# Notifications is module-owned and refreshed from its public sentinel.
MANAGED_ADAPTER_ORIGINS.add("notifications")


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

    Apps are declared by the auth manifest.
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

    manifest_schema = _build_manifest_wiring_schema("auth")
    schema = ModuleDerivationSchema(
        module_name="auth",
        version="1",
        module_wiring_projections=[
            *manifest_schema.module_wiring_projections,
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

    Apps are declared by the orgs manifest.
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

    manifest_schema = _build_manifest_wiring_schema("orgs")
    schema = ModuleDerivationSchema(
        module_name="orgs",
        version="1",
        module_wiring_projections=[
            *manifest_schema.module_wiring_projections,
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

    Apps are declared by the storage manifest.
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
    )
    from quickscale_core.manifest.resolver import (  # noqa: PLC0415
        ResolverResult,
        _project_all_wiring,
    )

    resolved = resolve_storage_module_options(options)
    validation_issues = validate_storage_module_options(options)
    backend = str(resolved.get("backend", "local")).lower()

    manifest_schema = _build_manifest_wiring_schema("storage")
    schema = ModuleDerivationSchema(
        module_name="storage",
        version="1",
        module_wiring_projections=[
            *manifest_schema.module_wiring_projections,
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
        default_acl = str(resolved.get("default_acl", "")).strip()
        querystring_auth = bool(resolved.get("querystring_auth", False))

        # SA29: credential options are now env-var name references. The
        # access key / secret key are NOT baked into the generated settings
        # module.  django-storages falls back to top-level Django settings
        # (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY), which are emitted as
        # os.environ.get() calls via the __QS_ENV__ marker below — so the
        # generated modules.py never stores credential material.
        from quickscale_core.contracts.module_options import (  # noqa: PLC0415
            DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
            DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
            STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
            STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        )

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
        # No access_key/secret_key in STORAGES OPTIONS — django-storages
        # falls through to the top-level AWS_ACCESS_KEY_ID setting (which
        # is now set via os.environ.get() below).
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
            *module_name*.  The caller must surface or handle the error
            explicitly; no legacy fallback path exists.
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
    "build_generic_manifest_spec",
    "build_manifest_wiring_spec",
    "load_module_manifest",
    "refresh_managed_adapters",
]
