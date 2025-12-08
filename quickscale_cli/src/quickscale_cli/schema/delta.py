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


def _get_option_mutability_info(
    module_name: str,
    option_name: str,
    manifests: dict | None,
) -> tuple[bool, str | None]:
    """Check if an option is mutable and get its django_setting

    Returns:
        Tuple of (is_mutable, django_setting)
    """
    if not manifests or module_name not in manifests:
        return False, None

    manifest = manifests[module_name]
    is_mutable = manifest.is_option_mutable(option_name)
    django_setting = None

    if is_mutable:
        option = manifest.get_option(option_name)
        if option:
            django_setting = option.django_setting

    return is_mutable, django_setting


def _compute_option_changes(
    desired_options: dict,
    applied_options: dict,
    module_name: str,
    manifests: dict | None,
) -> tuple[list[ConfigChange], list[ConfigChange]]:
    """Compute mutable and immutable option changes for a module

    Returns:
        Tuple of (mutable_changes, immutable_changes)
    """
    all_options = set(desired_options.keys()) | set(applied_options.keys())
    mutable_changes: list[ConfigChange] = []
    immutable_changes: list[ConfigChange] = []

    for option_name in all_options:
        old_value = applied_options.get(option_name)
        new_value = desired_options.get(option_name)

        if old_value == new_value:
            continue

        is_mutable, django_setting = _get_option_mutability_info(
            module_name, option_name, manifests
        )

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

    return mutable_changes, immutable_changes


def _compute_config_deltas(
    modules_unchanged: list[str],
    desired: QuickScaleConfig,
    applied: QuickScaleState,
    manifests: dict | None,
) -> dict[str, ModuleConfigDelta]:
    """Compute config changes for unchanged modules"""
    config_deltas: dict[str, ModuleConfigDelta] = {}

    for module_name in modules_unchanged:
        desired_config = desired.modules[module_name]
        applied_state = applied.modules[module_name]

        desired_options = desired_config.options or {}
        applied_options = applied_state.options or {}

        mutable_changes, immutable_changes = _compute_option_changes(
            desired_options, applied_options, module_name, manifests
        )

        if mutable_changes or immutable_changes:
            config_deltas[module_name] = ModuleConfigDelta(
                module_name=module_name,
                mutable_changes=mutable_changes,
                immutable_changes=immutable_changes,
            )

    return config_deltas


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
    config_deltas = _compute_config_deltas(
        modules_unchanged, desired, applied, manifests
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


def _format_theme_change(delta: ConfigDelta) -> list[str]:
    """Format theme change section"""
    if not delta.theme_changed:
        return []
    return [
        f"  ~ Theme: {delta.old_theme} → {delta.new_theme} "
        "(WARNING: Theme changes are not supported after initial generation)"
    ]


def _format_module_list(modules: list[str], label: str, prefix: str) -> list[str]:
    """Format a list of modules with a prefix symbol"""
    if not modules:
        return []
    lines = [f"\n{label} ({len(modules)}):"]
    for module in modules:
        lines.append(f"  {prefix} {module}")
    return lines


def _format_mutable_changes(
    mutable_changes: list[tuple[str, ConfigChange]],
) -> list[str]:
    """Format mutable config changes section"""
    if not mutable_changes:
        return []
    lines = [f"\nMutable config changes ({len(mutable_changes)}):"]
    for module_name, change in mutable_changes:
        lines.append(
            f"  ~ {module_name}.{change.option_name}: "
            f"{change.old_value} → {change.new_value}"
        )
        if change.django_setting:
            lines.append(f"    (updates {change.django_setting} in settings.py)")
    return lines


def _format_immutable_changes(
    immutable_changes: list[tuple[str, ConfigChange]],
) -> list[str]:
    """Format immutable config changes section with warning"""
    if not immutable_changes:
        return []
    lines = [f"\nImmutable config changes ({len(immutable_changes)}):"]
    for module_name, change in immutable_changes:
        lines.append(
            f"  ✗ {module_name}.{change.option_name}: "
            f"{change.old_value} → {change.new_value}"
        )
    lines.append("\n⚠️  WARNING: Immutable options cannot be changed after embed.")
    lines.append(
        "   To change immutable options, run 'quickscale remove <module>' "
        "and re-embed with new config."
    )
    return lines


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

    lines.extend(_format_theme_change(delta))
    lines.extend(_format_module_list(delta.modules_to_add, "Modules to add", "+"))
    lines.extend(_format_module_list(delta.modules_to_remove, "Modules to remove", "-"))

    # v0.71.0: Show config changes
    if delta.config_deltas:
        lines.extend(_format_mutable_changes(delta.get_all_mutable_changes()))
        lines.extend(_format_immutable_changes(delta.get_all_immutable_changes()))

    if delta.modules_unchanged and not delta.config_deltas:
        lines.append(
            f"\nModules unchanged ({len(delta.modules_unchanged)}): "
            f"{', '.join(delta.modules_unchanged)}"
        )

    return "\n".join(lines)
