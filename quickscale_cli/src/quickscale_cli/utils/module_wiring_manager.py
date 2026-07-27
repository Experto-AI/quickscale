"""Managed module wiring orchestration for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from quickscale_core.contracts.module_discovery import (
    ImproperlyConfigured,
    get_modules_base_path,
    set_modules_base_path,
)
from quickscale_core.manifest.entry_point import (
    MANIFEST_ADAPTER_REGISTRY,
    ManifestAdapterNotFound,
    build_manifest_wiring_spec,
    load_module_manifest,
    refresh_managed_adapters,
)
from quickscale_core.manifest.loader import (
    ManifestError,
    ModuleVersionMismatchError,
    assert_manifest_version_matches_core,
)
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_core.schema.config_schema import validate_config
from quickscale_core.schema.state_schema import StateManager
from quickscale_core.module_wiring import write_managed_wiring
from quickscale_core.utils.project_identity import (
    ProjectIdentityResolutionError,
    resolve_project_identity,
)
from quickscale_core.utils.theme_validation import (
    ThemeValidationError,
    validate_theme_preflight,
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


def _resolve_package_name(
    project_path: Path, project_package: str | None
) -> tuple[str | None, str | None]:
    if project_package is not None:
        return project_package, None

    try:
        identity = resolve_project_identity(project_path, strict=True)
    except ProjectIdentityResolutionError as error:
        return None, str(error)
    except Exception as error:
        return None, f"Unable to resolve project identity: {error}"
    return identity.package, None


def _select_module_names(
    project_path: Path, module_names: list[str] | None
) -> list[str]:
    if module_names is None:
        return _discover_embedded_modules(project_path)
    return sorted(dict.fromkeys(module_names))


def _load_and_merge_module_options(
    project_path: Path,
    option_overrides: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    try:
        module_options = _load_module_options(project_path)
    except ManagedWiringContextError as error:
        return None, str(error)

    if option_overrides:
        module_options.update(
            {
                module_name: dict(options)
                for module_name, options in option_overrides.items()
            }
        )
    return module_options, None


def _get_prior_modules_base_path() -> Path | None:
    try:
        return get_modules_base_path()
    except ImproperlyConfigured:
        return None


def _has_embedded_manifests(project_path: Path) -> bool:
    modules_dir = project_path / "modules"
    return modules_dir.is_dir() and any(
        (modules_dir / entry.name / "module.yml").exists()
        for entry in modules_dir.iterdir()
    )


def _refresh_adapters() -> str | None:
    try:
        refresh_managed_adapters()
    except ImproperlyConfigured as error:
        return f"Managed adapter wiring failed: {error}"
    return None


def _prepare_modules_base_path(
    project_path: Path, prior_base_path: Path | None
) -> str | None:
    if _has_embedded_manifests(project_path):
        set_modules_base_path(project_path / "modules")
        return _refresh_adapters()
    if prior_base_path is not None:
        return _refresh_adapters()
    return (
        "Modules base path not configured and no embedded module manifests found. "
        "Run inside the maintainer monorepo, call set_modules_base_path(), or "
        "embed at least one module with a module.yml file."
    )


def _build_one_wiring_spec(
    module_name: str,
    options: Mapping[str, Any],
    package_name: str,
) -> tuple[ModuleWiringSpec | None, str | None]:
    try:
        return (
            build_manifest_wiring_spec(
                module_name,
                dict(options),
                project_package=package_name,
            ),
            None,
        )
    except (ManifestAdapterNotFound, ManifestError) as error:
        if isinstance(error, ManifestAdapterNotFound):
            return None, None
        if "Manifest file not found" in str(error):
            return None, None
        return None, str(error)
    except ValueError as error:
        return None, f"Unable to build managed wiring specs: {error}"
    except ImproperlyConfigured as error:
        return None, f"Managed adapter wiring failed: {error}"


def _build_wiring_specs(
    selected_modules: list[str],
    module_options: Mapping[str, Mapping[str, Any]],
    package_name: str,
) -> tuple[dict[str, ModuleWiringSpec] | None, str | None]:
    # SA117: pre-check manifest version compatibility for registered modules
    # in deterministic sorted order.  A dedicated mismatch surfaces before
    # any ManifestError from the spec builder.  Modules without a registered
    # adapter are skipped (the spec builder handles them with the existing
    # skip-unknown contract); missing or unreadable manifests are also
    # deferred to the spec builder.
    for module_name in selected_modules:
        if module_name not in MANIFEST_ADAPTER_REGISTRY:
            # No registered adapter — this is an unknown or unregistered
            # module; let the spec builder skip it silently.
            continue
        try:
            manifest = load_module_manifest(module_name)
            assert_manifest_version_matches_core(manifest.version, module_name)
        except ManifestError:
            # Missing or unreadable manifest — let the spec builder handle
            # it with the existing skip-unknown logic.
            continue
        except ModuleVersionMismatchError as exc:
            return None, str(exc)

    specs: dict[str, ModuleWiringSpec] = {}
    for module_name in selected_modules:
        spec, error = _build_one_wiring_spec(
            module_name,
            module_options.get(module_name, {}),
            package_name,
        )
        if error is not None:
            return None, error
        if spec is not None:
            specs[module_name] = spec
    return specs, None


def _write_wiring_files(
    project_path: Path,
    package_name: str,
    specs: Mapping[str, ModuleWiringSpec],
) -> tuple[bool, str]:
    package_dir = project_path / package_name
    if not package_dir.exists():
        return False, f"Python package directory not found: {package_dir}"

    try:
        write_managed_wiring(package_dir, specs)
    except Exception as error:
        return False, f"Failed to write managed wiring files: {error}"
    return True, "Managed wiring files regenerated"


def _restore_modules_context(prior_base_path: Path | None) -> None:
    set_modules_base_path(prior_base_path)
    if prior_base_path is None:
        return
    try:
        refresh_managed_adapters()
    except ImproperlyConfigured:
        # Best-effort restoration of the adapter registry. If the prior base
        # path no longer has importable managed adapters, there is no
        # meaningful recovery from the finally block.
        pass


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
    # Run read-only theme preflight before any mutation.
    try:
        validate_theme_preflight(project_path)
    except ThemeValidationError as exc:
        return False, str(exc)

    package_name, error = _resolve_package_name(project_path, project_package)
    if error is not None:
        return False, error
    assert package_name is not None

    selected_modules = _select_module_names(project_path, module_names)
    module_options, error = _load_and_merge_module_options(
        project_path, option_overrides
    )
    if error is not None:
        return False, error
    assert module_options is not None

    prior_base_path: Path | None = None
    try:
        prior_base_path = _get_prior_modules_base_path()
        error = _prepare_modules_base_path(project_path, prior_base_path)
        if error is not None:
            return False, error

        specs, error = _build_wiring_specs(
            selected_modules, module_options, package_name
        )
        if error is not None:
            return False, error
        assert specs is not None
        return _write_wiring_files(project_path, package_name, specs)
    finally:
        _restore_modules_context(prior_base_path)
