"""Config loading, prerequisite validation, and immutable-change checks.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import click
import yaml


from quickscale_core.schema.config_schema import (
    QuickScaleConfig,
)
from quickscale_core.schema.delta import ConfigDelta
from quickscale_core.schema.state_schema import (
    QuickScaleState,
)
from quickscale_core.manifest import ModuleManifest
from quickscale_core.manifest.loader import ManifestError

# AF6 Phase 2 — core step bodies

import quickscale_core.contracts.module_catalog as _module_catalog
import quickscale_core.manifest.required_modules as _required_modules
import quickscale_core.schema.config_schema as _config_schema
import quickscale_core.manifest.option_validation as _option_validation
import quickscale_cli.commands.apply_support as _apply_support
import quickscale_core.contracts.resolvers as _resolvers
import quickscale_core.manifest.loader as _loader
import quickscale_core.contracts.module_options as _module_options


def _abort_for_not_ready_modules(module_names: list[str], *, source: str) -> None:
    """Abort apply when non-public-ready modules appear in config or applied state."""
    not_ready = _module_catalog.find_not_ready_modules(module_names)
    if not not_ready:
        return

    click.secho(
        f"\n❌ {source} references modules that are not public-ready:",
        fg="red",
        err=True,
        bold=True,
    )
    for module_name in not_ready:
        reason = _module_catalog.get_module_readiness_reason(module_name)
        if reason is not None:
            click.echo(f"  • {reason}", err=True)

    click.echo(
        "\n💡 Remove these modules from quickscale.yml or the unsupported project "
        "state before running 'quickscale apply'.",
        err=True,
    )
    raise click.Abort()


def _abort_for_manifest_error(error: ManifestError, *, command_name: str) -> None:
    """Abort apply/status with an actionable manifest validation message."""
    click.secho(
        f"\n❌ Installed module manifest error during '{command_name}':",
        fg="red",
        err=True,
        bold=True,
    )
    click.echo(f"  • {error}", err=True)
    click.echo(
        "\n💡 Fix the embedded module.yml or remove and re-embed the affected "
        f"module before running 'quickscale {command_name}' again.",
        err=True,
    )
    raise click.Abort()


def _load_module_manifests(
    project_path: Path,
    module_names: list[str],
    *,
    strict: bool = False,
) -> dict[str, ModuleManifest]:
    """Load manifests for all installed modules"""
    manifests: dict[str, ModuleManifest] = {}
    for module_name in module_names:
        manifest = _loader.get_manifest_for_module(
            project_path, module_name, strict=strict
        )
        if manifest:
            manifests[module_name] = manifest
    return manifests


def _check_immutable_config_changes(delta: ConfigDelta) -> bool:
    """Check for immutable config changes and show errors

    Returns True if there are no immutable changes (safe to proceed)
    Returns False if there are immutable changes (should abort)

    """
    if not delta.has_immutable_config_changes:
        return True

    click.secho(
        "\n❌ Cannot apply: Immutable configuration changes detected!",
        fg="red",
        bold=True,
    )
    click.echo("\nThe following options cannot be changed after embed:\n")

    for module_name, change in delta.get_all_immutable_changes():
        click.echo(f"  ✗ {module_name}.{change.option_name}:")
        click.echo(f"    Current: {change.old_value}")
        click.echo(f"    Desired: {change.new_value}")

    click.secho(
        "\n⚠️  DATA LOSS WARNING: the only safe path is remove + re-add,",
        fg="yellow",
        bold=True,
    )
    click.echo(
        "   which drops the module's database tables/migrations and discards\n"
        "   any user edits inside the module's managed files."
    )

    click.echo("\n💡 To change immutable options:")
    modules_with_immutable = set(
        module_name for module_name, _ in delta.get_all_immutable_changes()
    )
    for module_name in modules_with_immutable:
        click.echo(f"   1. quickscale remove {module_name}")
        click.echo("   2. Update quickscale.yml with new options")
        click.echo("   3. quickscale apply")
        click.echo()

    click.echo(
        "   `quickscale remove` snapshots every mutable file (module dir,\n"
        "   managed settings/urls, quickscale.yml, .quickscale state) before\n"
        "   mutating and rolls back automatically if removal fails, so it is\n"
        "   the safe path for changing an immutable option."
    )

    return False


def _abort_for_config_driven_module_removals(delta: ConfigDelta) -> None:
    """Reject desired-state removals that must go through quickscale remove."""
    if not delta.modules_to_remove:
        return

    click.secho(
        "\n❌ Cannot apply: config-driven module removals are not supported.",
        fg="red",
        bold=True,
    )
    click.echo("\nThe following installed modules were removed from quickscale.yml:\n")
    for module_name in delta.modules_to_remove:
        click.echo(f"  ✗ {module_name}")

    click.secho(
        "\n⚠️  DATA LOSS WARNING: deleting a module from quickscale.yml and",
        fg="yellow",
        bold=True,
    )
    click.echo(
        "   applying will not run the explicit remove path, so you would lose\n"
        "   `quickscale remove`'s built-in snapshot/rollback safety for the\n"
        "   module dir, managed settings/urls, quickscale.yml, and .quickscale\n"
        "   state. The explicit remove workflow is the safe path."
    )

    click.echo("\n💡 Use the explicit remove workflow instead:")
    for module_name in delta.modules_to_remove:
        click.echo(f"   1. quickscale remove {module_name}")
    click.echo("   2. Re-run quickscale apply")
    click.echo(
        "   `quickscale remove` snapshots every mutable file before mutating\n"
        "   and rolls back automatically if removal fails."
    )
    click.echo(
        "\nApply will not partially remove installed modules from managed wiring "
        "without also updating authoritative module state."
    )
    raise click.Abort()


def _update_module_config_in_state(
    state: QuickScaleState,
    config: QuickScaleConfig,
    delta: ConfigDelta,
) -> None:
    """Update module options in state after mutable config changes"""
    del config
    config_deltas = getattr(delta, "config_deltas", {})
    if not isinstance(config_deltas, Mapping):
        return

    for module_name, module_delta in config_deltas.items():
        if module_delta.has_mutable_changes and module_name in state.modules:
            # Update options with new values
            current_options = state.modules[module_name].options or {}
            for change in module_delta.mutable_changes:
                current_options[change.option_name] = change.new_value
            state.modules[
                module_name
            ].options = _module_options.sanitize_module_options(
                module_name,
                current_options,
            )


def _sanitize_loaded_module_configs(qs_config: QuickScaleConfig) -> list[str]:
    """Normalize module configs so legacy keys never persist after apply."""
    sanitized_modules: list[str] = []
    for module_name, module_config in qs_config.modules.items():
        normalized = _module_options.sanitize_module_options(
            module_name, module_config.options or {}
        )
        if normalized == (module_config.options or {}):
            continue
        module_config.options = normalized
        sanitized_modules.append(module_name)
    return sanitized_modules


def _materialize_required_module_configs(qs_config: QuickScaleConfig) -> list[str]:
    """Add explicit module config blocks required by selected modules."""
    required_configs = _required_modules.resolve_required_modules(
        qs_config.modules.keys()
    )
    if not required_configs:
        return []

    for module_name, options in required_configs.items():
        qs_config.modules[module_name] = _config_schema.ModuleConfig(
            name=module_name,
            options=_module_options.sanitize_module_options(module_name, options),
        )

    return list(required_configs.keys())


def _load_and_validate_config(config_path: Path) -> QuickScaleConfig:
    """Load and validate configuration from file."""
    if not config_path.exists():
        click.secho(
            f"❌ Configuration file not found: {config_path}", fg="red", err=True
        )
        click.echo(
            "\n💡 Create a configuration with: quickscale plan <project-slug>",
            err=True,
        )
        raise click.Abort()

    click.echo(f"\n📋 Reading configuration: {config_path}")
    try:
        yaml_content = config_path.read_text()
        qs_config = _config_schema.validate_config(yaml_content)
        original_data = yaml.safe_load(yaml_content) or {}
        original_modules = original_data.get("modules") or {}
        sanitized_modules = _sanitize_loaded_module_configs(qs_config)
        required_modules = _materialize_required_module_configs(qs_config)
        normalized_yaml = _config_schema.generate_yaml(qs_config)
        normalized_data = yaml.safe_load(normalized_yaml) or {}
        normalized_modules = normalized_data.get("modules") or {}
        if normalized_modules != original_modules:
            config_path.write_text(normalized_yaml)
            if sanitized_modules:
                click.secho(
                    "✅ Sanitized legacy module config keys in quickscale.yml",
                    fg="green",
                )
            if required_modules:
                click.secho(
                    "✅ Added required module config to quickscale.yml: "
                    + ", ".join(required_modules),
                    fg="green",
                )
        _validate_module_prerequisites(qs_config)
        return qs_config
    except _config_schema.ConfigValidationError as e:
        click.secho(f"\n❌ Configuration error:\n{e}", fg="red", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"\n❌ Failed to read configuration: {e}", fg="red", err=True)
        raise click.Abort()


def _abort_for_disabled_required_modules(qs_config: QuickScaleConfig) -> None:
    """Refuse a module switched off while an installed module requires it.

    Rule 1 (D3): ``apply`` refuses to switch a module off while an installed
    module lists it in ``required_modules``; wiring a dependent module against
    a switched-off foundation would leave its own URLs and runtime calls
    pointing at disabled surfaces.
    """
    installed_modules = set(qs_config.modules)
    offenders: list[tuple[str, str]] = []
    manifests: dict[str, Any] = {}
    for module_name in sorted(installed_modules):
        try:
            resolved = _resolved_module_options(
                module_name, qs_config.modules[module_name].options or {}
            )
        except _config_schema.ConfigValidationError:
            # A retired option key is refused by the existing prerequisite
            # checks with its authored message; this check only reads the
            # enabled flag.
            continue
        if bool(resolved.get("enabled", True)):
            continue
        for dependant in sorted(installed_modules - {module_name}):
            manifest = manifests.get(dependant)
            if manifest is None:
                manifest = _resolvers.load_module_manifest_with_fallback(dependant)
                manifests[dependant] = manifest
            if module_name in manifest.required_modules:
                offenders.append((module_name, dependant))

    if not offenders:
        return

    click.secho(
        "\n❌ Some configured modules are switched off while other installed "
        "modules require them:",
        fg="red",
        err=True,
    )
    for module_name, dependant in offenders:
        click.echo(
            f"  • '{module_name}' is switched off (enabled: false) but "
            f"'{dependant}' requires it.",
            err=True,
        )
    click.echo(
        "\n💡 Re-enable the switched-off module in quickscale.yml or remove "
        "the modules that require it.",
        err=True,
    )
    raise click.Abort()


def _validate_module_prerequisites(qs_config: QuickScaleConfig) -> None:
    """Validate actionable module-specific prerequisites before apply proceeds.

    A module's required modules were already materialized into the config, so
    the prerequisite checks here cover option values, module readiness, and
    the rule-1 refusal of a module switched off while an installed module
    requires it.
    """
    _abort_for_disabled_required_modules(qs_config)

    if "orgs" in qs_config.modules:
        orgs_issues = _option_validation.validate_module_options(
            _resolvers.load_module_manifest_with_fallback("orgs"),
            qs_config.modules["orgs"].options or {},
        )
        if orgs_issues:
            click.secho(
                "\n❌ Orgs module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in orgs_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the orgs option values.",
                err=True,
            )
            raise click.Abort()

    _abort_for_not_ready_modules(
        list(qs_config.modules.keys()), source="quickscale.yml"
    )

    storage_config = qs_config.modules.get("storage")
    if storage_config is not None:
        storage_issues = _option_validation.validate_module_options(
            _resolvers.load_module_manifest_with_fallback("storage"),
            storage_config.options or {},
        )
        if storage_issues:
            click.secho(
                "\n❌ Storage module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in storage_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the storage option values. "
                "Storage apply requires a valid backend and optional booleans.",
                err=True,
            )
            raise click.Abort()

    backups_config = qs_config.modules.get("backups")
    if backups_config is not None:
        backups_issues = _option_validation.validate_module_options(
            _resolvers.load_module_manifest_with_fallback("backups"),
            backups_config.options or {},
        )
        if backups_issues:
            click.secho(
                "\n❌ Backups module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in backups_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the backups option values.",
                err=True,
            )
            raise click.Abort()

    social_config = qs_config.modules.get("social")
    if social_config is not None:
        social_issues = _option_validation.validate_module_options(
            _resolvers.load_module_manifest_with_fallback("social"),
            social_config.options or {},
        )
        if social_issues:
            click.secho(
                "\n❌ Social module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in social_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the social settings. This phase wires the "
                "managed backend transport, and the canonical public paths remain "
                f"{_module_options.SOCIAL_LINK_TREE_PATH} and {_module_options.SOCIAL_EMBEDS_PATH} for fresh "
                "showcase_react generations or manual theme adoption.",
                err=True,
            )
            raise click.Abort()

    notifications_config = qs_config.modules.get("notifications")
    if notifications_config is None:
        return

    notifications_options = notifications_config.options or {}
    notification_issues = _option_validation.validate_module_options(
        _resolvers.load_module_manifest_with_fallback("notifications"),
        notifications_options,
    )
    if not notification_issues:
        return

    click.secho(
        "\n❌ Notifications module configuration is incomplete for apply:",
        fg="red",
        err=True,
    )
    for issue in notification_issues:
        click.echo(f"  • {issue}", err=True)
    notifications_adapter = _apply_support.notifications_adapter_module()
    if notifications_adapter is not None and (
        notifications_adapter.notifications_production_targeted(notifications_options)
    ):
        click.echo(
            "\n💡 This configuration targets live Resend delivery, so apply refuses "
            "to leave production on the console email backend. Complete the missing "
            "notifications settings first.",
            err=True,
        )
    else:
        click.echo(
            "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
            "quickscale.yml to correct the notifications values.",
            err=True,
        )
    raise click.Abort()


def _resolved_module_options(
    module_name: str,
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolved option values with a blank string falling back to the default.

    Operator guidance names the conventional value when a configured string is
    blank, the same way the manifest default applies at apply time.
    """
    resolved = _resolvers.resolve_manifest_module_options(module_name, options)
    defaults = _resolvers.resolve_manifest_module_options(module_name)
    return {
        key: (defaults.get(key, value) if value in ("", None) else value)
        for key, value in resolved.items()
    }
