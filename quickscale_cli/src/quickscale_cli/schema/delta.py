"""Delta Detection for Plan/Apply System

Compares desired configuration (quickscale.yml) with applied state (.quickscale/state.yml)
to determine what changes need to be applied.
"""

from dataclasses import dataclass, field
from typing import Any

from quickscale_cli.schema.config_schema import QuickScaleConfig
from quickscale_cli.schema.state_schema import QuickScaleState


@dataclass
class ConfigChange:
    """A single configuration option change"""

    option_name: str
    old_value: Any
    new_value: Any
    django_setting: str | None = None
    is_mutable: bool = False


@dataclass
class ModuleConfigDelta:
    """Configuration changes for a single module"""

    module_name: str
    mutable_changes: list[ConfigChange] = field(default_factory=list)
    immutable_changes: list[ConfigChange] = field(default_factory=list)

    @property
    def has_mutable_changes(self) -> bool:
        """Check if there are mutable config changes"""
        return len(self.mutable_changes) > 0

    @property
    def has_immutable_changes(self) -> bool:
        """Check if there are immutable config changes"""
        return len(self.immutable_changes) > 0

    @property
    def has_changes(self) -> bool:
        """Check if there are any config changes"""
        return self.has_mutable_changes or self.has_immutable_changes


@dataclass
class ModuleDelta:
    """Delta for a single module"""

    name: str
    action: str  # 'add', 'remove', 'update', 'unchanged'
    old_options: dict = field(default_factory=dict)
    new_options: dict = field(default_factory=dict)


@dataclass
class ConfigDelta:
    """Complete delta between desired and applied state"""

    has_changes: bool
    modules_to_add: list[str] = field(default_factory=list)
    modules_to_remove: list[str] = field(default_factory=list)
    modules_unchanged: list[str] = field(default_factory=list)
    theme_changed: bool = False
    old_theme: str | None = None
    new_theme: str | None = None
    # v0.71.0: Config mutability tracking
    config_deltas: dict[str, ModuleConfigDelta] = field(default_factory=dict)

    @property
    def has_mutable_config_changes(self) -> bool:
        """Check if any module has mutable config changes"""
        return any(d.has_mutable_changes for d in self.config_deltas.values())

    @property
    def has_immutable_config_changes(self) -> bool:
        """Check if any module has immutable config changes"""
        return any(d.has_immutable_changes for d in self.config_deltas.values())

    def get_all_mutable_changes(self) -> list[tuple[str, ConfigChange]]:
        """Get all mutable changes across all modules as (module_name, change) tuples"""
        changes = []
        for module_name, delta in self.config_deltas.items():
            for change in delta.mutable_changes:
                changes.append((module_name, change))
        return changes

    def get_all_immutable_changes(self) -> list[tuple[str, ConfigChange]]:
        """Get all immutable changes across all modules as (module_name, change) tuples"""
        changes = []
        for module_name, delta in self.config_deltas.items():
            for change in delta.immutable_changes:
                changes.append((module_name, change))
        return changes


def compute_delta(
    desired: QuickScaleConfig,
    applied: QuickScaleState | None,
    manifests: dict | None = None,
) -> ConfigDelta:
    """Compute delta between desired configuration and applied state

    Args:
        desired: Desired configuration from quickscale.yml
        applied: Applied state from .quickscale/state.yml (None if no state exists)
        manifests: Optional dict of module_name -> ModuleManifest for config mutability

    Returns:
        ConfigDelta object describing required changes

    """
    if applied is None:
        # No state exists - everything is new
        return ConfigDelta(
            has_changes=True,
            modules_to_add=list(desired.modules.keys()),
            modules_to_remove=[],
            modules_unchanged=[],
            theme_changed=False,
            new_theme=desired.project.theme,
        )

    # Compare modules
    desired_modules = set(desired.modules.keys())
    applied_modules = set(applied.modules.keys())

    modules_to_add = list(desired_modules - applied_modules)
    modules_to_remove = list(applied_modules - desired_modules)
    modules_unchanged = list(desired_modules & applied_modules)

    # Check for theme changes
    theme_changed = desired.project.theme != applied.project.theme

    # v0.71.0: Compute config changes for unchanged modules
    config_deltas: dict[str, ModuleConfigDelta] = {}

    for module_name in modules_unchanged:
        desired_config = desired.modules[module_name]
        applied_state = applied.modules[module_name]

        desired_options = desired_config.options or {}
        applied_options = applied_state.options or {}

        # Detect option changes
        all_options = set(desired_options.keys()) | set(applied_options.keys())
        mutable_changes = []
        immutable_changes = []

        for option_name in all_options:
            old_value = applied_options.get(option_name)
            new_value = desired_options.get(option_name)

            if old_value != new_value:
                # Check if option is mutable via manifest
                is_mutable = False
                django_setting = None

                if manifests and module_name in manifests:
                    manifest = manifests[module_name]
                    is_mutable = manifest.is_option_mutable(option_name)
                    if is_mutable:
                        option = manifest.get_option(option_name)
                        if option:
                            django_setting = option.django_setting

                change = ConfigChange(
                    option_name=option_name,
                    old_value=old_value,
                    new_value=new_value,
                    django_setting=django_setting,
                    is_mutable=is_mutable,
                )

                if is_mutable:
                    mutable_changes.append(change)
                else:
                    immutable_changes.append(change)

        if mutable_changes or immutable_changes:
            config_deltas[module_name] = ModuleConfigDelta(
                module_name=module_name,
                mutable_changes=mutable_changes,
                immutable_changes=immutable_changes,
            )

    # Determine if there are any changes
    has_config_changes = bool(config_deltas)
    has_changes = bool(
        modules_to_add or modules_to_remove or theme_changed or has_config_changes
    )

    return ConfigDelta(
        has_changes=has_changes,
        modules_to_add=sorted(modules_to_add),
        modules_to_remove=sorted(modules_to_remove),
        modules_unchanged=sorted(modules_unchanged),
        theme_changed=theme_changed,
        old_theme=applied.project.theme if theme_changed else None,
        new_theme=desired.project.theme if theme_changed else None,
        config_deltas=config_deltas,
    )


def format_delta(delta: ConfigDelta) -> str:
    """Format delta as human-readable change summary

    Args:
        delta: ConfigDelta object

    Returns:
        Formatted string describing changes

    """
    if not delta.has_changes:
        return "No changes detected. Configuration matches applied state."

    lines = ["Changes to apply:"]

    if delta.theme_changed:
        lines.append(
            f"  ~ Theme: {delta.old_theme} → {delta.new_theme} "
            "(WARNING: Theme changes are not supported after initial generation)"
        )

    if delta.modules_to_add:
        lines.append(f"\nModules to add ({len(delta.modules_to_add)}):")
        for module in delta.modules_to_add:
            lines.append(f"  + {module}")

    if delta.modules_to_remove:
        lines.append(f"\nModules to remove ({len(delta.modules_to_remove)}):")
        for module in delta.modules_to_remove:
            lines.append(f"  - {module}")

    # v0.71.0: Show config changes
    if delta.config_deltas:
        mutable_changes = delta.get_all_mutable_changes()
        immutable_changes = delta.get_all_immutable_changes()

        if mutable_changes:
            lines.append(f"\nMutable config changes ({len(mutable_changes)}):")
            for module_name, change in mutable_changes:
                lines.append(
                    f"  ~ {module_name}.{change.option_name}: "
                    f"{change.old_value} → {change.new_value}"
                )
                if change.django_setting:
                    lines.append(
                        f"    (updates {change.django_setting} in settings.py)"
                    )

        if immutable_changes:
            lines.append(f"\nImmutable config changes ({len(immutable_changes)}):")
            for module_name, change in immutable_changes:
                lines.append(
                    f"  ✗ {module_name}.{change.option_name}: "
                    f"{change.old_value} → {change.new_value}"
                )
            lines.append(
                "\n⚠️  WARNING: Immutable options cannot be changed after embed."
            )
            lines.append(
                "   To change immutable options, run 'quickscale remove <module>' "
                "and re-embed with new config."
            )

    if delta.modules_unchanged and not delta.config_deltas:
        lines.append(
            f"\nModules unchanged ({len(delta.modules_unchanged)}): "
            f"{', '.join(delta.modules_unchanged)}"
        )

    return "\n".join(lines)
