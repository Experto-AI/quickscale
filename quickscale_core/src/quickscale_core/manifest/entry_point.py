"""
Manifest-driven wiring spec entry point.

Provides :func:`build_manifest_wiring_spec` — the canonical entry point that
routes a module through its manifest adapter and the manifest assembler to
produce a complete :class:`~quickscale_core.module_wiring.ModuleWiringSpec`.

All shipped module adapters are owned by their module packages.  The registry
is populated by :func:`refresh_managed_adapters`, which discovers the active
manifest inventory once, resolves every corresponding
``quickscale_modules_{name}.adapter`` sentinel, and commits the complete set
only after every import succeeds.  The refresh is fail-hard and atomic: a
missing sentinel or broken import leaves the prior registry, origins, and
package import state unchanged.

Managed adapters are not registered at import time.  Callers (typically
:func:`~quickscale_cli.utils.module_wiring_manager.regenerate_managed_wiring`)
must invoke :func:`refresh_managed_adapters` before calling
:func:`build_manifest_wiring_spec`.

Batch A modules use the generic manifest-driven path that loads derivation
rules from their ``module.yml`` manifest files.  Post-resolution hooks in
each module-owned adapter handle module-specific type coercions and static
settings that the declarative resolver cannot express.
"""

from __future__ import annotations

from collections.abc import Callable
import sys
from typing import Any, cast

from quickscale_core.contracts.module_discovery import (
    AUTHORITATIVE_MODULE_COUNT,
    get_modules_base_path,
)
from quickscale_core.manifest.assembler import (
    PostResolutionHook,
    assemble_wiring_spec,
)
from quickscale_core.manifest.derivation import build_schema_from_manifest
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config
from quickscale_core.module_wiring import ModuleWiringSpec

# ---------------------------------------------------------------------------
# Generic manifest adapter helpers
# ---------------------------------------------------------------------------

# Modules base path: uses the configurable seam from module_discovery.
# Defaults to the maintainer-monorepo quickscale_modules/ layout, but can
# be overridden via module_discovery.set_modules_base_path() for installed
# or embedded-project contexts.

#: Weak cache of loaded manifests keyed by ``(module_name, base_path)`` so
#: changing the modules base path at runtime does not return stale entries.
_manifest_cache: dict[tuple[str, str], Any] = {}


def load_module_manifest(module_name: str) -> Any:
    """Load and cache the ``module.yml`` manifest for *module_name*."""
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
    """Build a wiring spec from the derivation rules in ``module.yml``.

    ``project_package`` is accepted for signature parity with module-owned
    adapters.  The generic manifest path does not use it.
    """
    del project_package
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

#: Registry mapping module name -> manifest adapter callable.  Each callable
#: accepts ``(options, *, project_package)`` and is returned by a module-owned
#: ``get_manifest_adapter`` sentinel during an explicit refresh.
MANIFEST_ADAPTER_REGISTRY: dict[
    str,
    Callable[..., ModuleWiringSpec],
] = {}

#: Names currently represented by module-owned entries in the registry.
#: Custom entries outside the discovered shipped inventory are not tracked and
#: survive refreshes unchanged.
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
            "The module package must be installed and importable."
        ) from exc
    finally:
        sys.path[:] = original_sys_path
        _evict_package_modules(package_name)
        sys.modules.update(original_package_modules)


def refresh_managed_adapters() -> None:
    """Atomically refresh every adapter in the discovered shipped inventory.

    Discovery is performed exactly once per refresh.  The resulting inventory
    must contain the authoritative twelve shipped modules.  All sentinels are
    resolved before the live registry or origins are changed, preserving
    registry identity, custom entries, and the prior state on any failure.
    """
    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        ImproperlyConfigured,
        discover_shipped_module_names,
    )

    discovered_module_names = set(discover_shipped_module_names())
    if len(discovered_module_names) != AUTHORITATIVE_MODULE_COUNT:
        raise ImproperlyConfigured(
            "Authoritative module inventory count drift: expected "
            f"{AUTHORITATIVE_MODULE_COUNT}, found {len(discovered_module_names)}"
        )

    loaded_adapters: dict[str, Callable[..., ModuleWiringSpec]] = {}
    # Resolve every adapter before mutating the live registry.  A failed
    # refresh is fail-hard and atomic regardless of iteration order.
    for module_name in sorted(discovered_module_names):
        loaded_adapters[module_name] = _load_managed_adapter(module_name)

    if set(loaded_adapters) != discovered_module_names:
        raise ImproperlyConfigured(
            "Managed adapter resolution did not cover the discovered module "
            "inventory atomically."
        )

    # Commit only after the complete managed set resolved successfully.  Keep
    # custom entries and the registry object itself, while replacing stale
    # managed entries and synchronizing origins at one commit point.
    for module_name in MANAGED_ADAPTER_ORIGINS - discovered_module_names:
        MANIFEST_ADAPTER_REGISTRY.pop(module_name, None)
    MANAGED_ADAPTER_ORIGINS.clear()
    MANAGED_ADAPTER_ORIGINS.update(discovered_module_names)
    MANIFEST_ADAPTER_REGISTRY.update(loaded_adapters)


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
    """Build a module wiring spec through its registered adapter."""
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
