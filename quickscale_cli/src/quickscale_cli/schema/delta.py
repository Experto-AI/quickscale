"""Delta Detection for Plan/Apply System

Compares desired configuration (quickscale.yml) with applied state (.quickscale/state.yml)
to determine what changes need to be applied.
"""

from dataclasses import dataclass, field

from quickscale_cli.schema.config_schema import QuickScaleConfig
from quickscale_cli.schema.state_schema import QuickScaleState


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


def compute_delta(
    desired: QuickScaleConfig, applied: QuickScaleState | None
) -> ConfigDelta:
    """Compute delta between desired configuration and applied state

    Args:
        desired: Desired configuration from quickscale.yml
        applied: Applied state from .quickscale/state.yml (None if no state exists)

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

    # Determine if there are any changes
    has_changes = bool(modules_to_add or modules_to_remove or theme_changed)

    return ConfigDelta(
        has_changes=has_changes,
        modules_to_add=sorted(modules_to_add),
        modules_to_remove=sorted(modules_to_remove),
        modules_unchanged=sorted(modules_unchanged),
        theme_changed=theme_changed,
        old_theme=applied.project.theme if theme_changed else None,
        new_theme=desired.project.theme if theme_changed else None,
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

    if delta.modules_unchanged:
        lines.append(
            f"\nModules unchanged ({len(delta.modules_unchanged)}): "
            f"{', '.join(delta.modules_unchanged)}"
        )

    return "\n".join(lines)
