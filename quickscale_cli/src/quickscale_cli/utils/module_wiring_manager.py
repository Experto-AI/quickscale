"""Managed module wiring orchestration for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from django.core.exceptions import ImproperlyConfigured

from quickscale_core.contracts.module_discovery import (
    get_modules_base_path,
    set_modules_base_path,
)
from quickscale_core.manifest.entry_point import (
    ManifestAdapterNotFound,
    build_manifest_wiring_spec,
    refresh_managed_adapters,
)
from quickscale_core.manifest.loader import ManifestError
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_cli.schema.config_schema import validate_config
from quickscale_cli.schema.state_schema import StateManager
from quickscale_core.module_wiring import write_managed_wiring
from quickscale_core.utils.project_identity import (
    ProjectIdentityResolutionError,
    resolve_project_identity,
)


class ManagedWiringContextError(ValueError):
    """Raised when managed wiring cannot derive required project context."""


def _discover_embedded_modules(project_path: Path) -> list[str]:
    modules_dir = project_path / "modules"
    if not modules_dir.exists():
        return []

    module_names = [
        path.name
        for path in modules_dir.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    return sorted(module_names)


def _load_options_from_config(project_path: Path) -> dict[str, dict[str, Any]]:
    config_path = project_path / "quickscale.yml"
    if not config_path.exists():
        return {}

    try:
        config = validate_config(config_path.read_text())
    except Exception as error:
        raise ManagedWiringContextError(
            f"Failed to load module options from quickscale.yml: {error}"
        ) from error

    return {
        module_name: (module_config.options or {})
        for module_name, module_config in config.modules.items()
    }


def _load_options_from_state(project_path: Path) -> dict[str, dict[str, Any]]:
    try:
        state = StateManager(project_path).load()
    except Exception as error:
        raise ManagedWiringContextError(
            f"Failed to load module options from .quickscale/state.yml: {error}"
        ) from error

    if state is None:
        return {}

    return {
        module_name: (module_state.options or {})
        for module_name, module_state in state.modules.items()
    }


def _load_module_options(project_path: Path) -> dict[str, dict[str, Any]]:
    options = _load_options_from_state(project_path)
    # Config is source-of-truth for desired options and should override state values.
    options.update(_load_options_from_config(project_path))
    return options


def regenerate_managed_wiring(
    project_path: Path,
    *,
    module_names: list[str] | None = None,
    option_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    project_package: str | None = None,
) -> tuple[bool, str]:
    """Regenerate managed wiring files from module selection + options.

    Returns:
        (success, message)
    """
    package_name = project_package
    if package_name is None:
        try:
            identity = resolve_project_identity(project_path, strict=True)
            package_name = identity.package
        except ProjectIdentityResolutionError as error:
            return False, str(error)
        except Exception as error:
            return False, f"Unable to resolve project identity: {error}"

    if module_names is None:
        selected_modules = _discover_embedded_modules(project_path)
    else:
        selected_modules = sorted(dict.fromkeys(module_names))

    try:
        module_options = _load_module_options(project_path)
    except ManagedWiringContextError as error:
        return False, str(error)

    if option_overrides:
        module_options.update(
            {
                module_name: dict(options)
                for module_name, options in option_overrides.items()
            }
        )

    # Point manifest loading at the embedded modules directory when this
    # context has a project with at least one real embedded manifest
    # (``modules/<name>/module.yml``).  Empty ``modules/`` directories
    # (e.g. in test fixtures) leave the default path active so that
    # shipped-module manifests from the bundled/installed fallback remain
    # available.
    # Save/restore the global base path so the override does not leak
    # across callers running in the same process.
    _prior_base_path: Path | None = None
    _has_real_manifests = False
    try:
        try:
            _prior_base_path = get_modules_base_path()
        except ImproperlyConfigured:
            # Absence of a prior base path is acceptable when embedded
            # modules are available — we override it below.  Set to
            # ``None`` so the finally block restores correctly.
            _prior_base_path = None

        modules_dir = project_path / "modules"
        _has_real_manifests = modules_dir.is_dir() and any(
            (modules_dir / entry.name / "module.yml").exists()
            for entry in modules_dir.iterdir()
        )

        if _has_real_manifests:
            set_modules_base_path(modules_dir)
            try:
                refresh_managed_adapters()
            except ImproperlyConfigured as error:
                return (
                    False,
                    f"Managed adapter wiring failed: {error}",
                )
        elif _prior_base_path is None:
            return (
                False,
                "Modules base path not configured and no embedded module "
                "manifests found. Run inside the maintainer monorepo, call "
                "set_modules_base_path(), or embed at least one module with "
                "a module.yml file.",
            )

        selected_options = {
            module_name: module_options.get(module_name, {})
            for module_name in selected_modules
        }

        specs: dict[str, ModuleWiringSpec] = {}
        for module_name, options in selected_options.items():
            try:
                specs[module_name] = build_manifest_wiring_spec(
                    module_name,
                    dict(options),
                    project_package=package_name,
                )
            except ManifestAdapterNotFound:
                # Skip discovered/forwarded modules that have no manifest adapter
                # registered yet.  This preserves the legacy skip-unknown behaviour
                # for non-registered module names (e.g. a modules/ directory that
                # contains a module without a manifest adapter).
                continue
            except ManifestError as exc:
                # When the embedded project's modules directory is set as the
                # base path (via set_modules_base_path below), a module name
                # may appear in selected_modules but not exist in the embedded
                # directory.  Silently skip it only for "Manifest file not
                # found" errors, matching the skip-unknown contract for
                # non-embedded modules.
                # Other ManifestError instances (e.g. invalid analytics
                # configuration from SA18.2) fail as (False, message),
                # consistent with the ValueError/ImproperlyConfigured
                # handlers in this loop.
                if "Manifest file not found" in str(exc):
                    continue
                return False, str(exc)
            except ValueError as error:
                return False, f"Unable to build managed wiring specs: {error}"
            except ImproperlyConfigured as error:
                return (
                    False,
                    f"Managed adapter wiring failed: {error}",
                )

        package_dir = project_path / package_name
        if not package_dir.exists():
            return (
                False,
                f"Python package directory not found: {package_dir}",
            )

        try:
            write_managed_wiring(package_dir, specs)
        except Exception as error:
            return False, f"Failed to write managed wiring files: {error}"

        return True, "Managed wiring files regenerated"
    finally:
        set_modules_base_path(_prior_base_path)
        if _prior_base_path is not None:
            try:
                refresh_managed_adapters()
            except ImproperlyConfigured:
                # Best-effort restoration of the adapter registry.
                # If the prior base path no longer has importable
                # managed adapters there is no meaningful recovery
                # from the finally block.
                pass
