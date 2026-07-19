"""Presentation helpers for module-removal command output."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from quickscale_core.schema.state_schema import QuickScaleState


def _show_module_not_found_error(
    module_name: str, state: QuickScaleState | None
) -> None:
    """Display error when module is not found"""
    click.secho(
        f"❌ Module '{module_name}' is not installed in this project",
        fg="red",
        err=True,
    )
    click.echo("\n💡 Installed modules:", err=True)
    if state and state.modules:
        for name in state.modules:
            click.echo(f"   - {name}", err=True)
    else:
        click.echo("   (none)", err=True)


def _show_removal_warning(module_name: str, keep_data: bool) -> None:
    """Display warning about module removal"""
    click.secho(
        f"\n⚠️  WARNING: You are about to remove the '{module_name}' module",
        fg="yellow",
        bold=True,
    )
    click.echo("\nThis action will:")
    click.echo(f"  • Remove modules/{module_name}/ directory")
    click.echo("  • Update .quickscale/state.yml")
    click.echo("  • Update .quickscale/config.yml")
    click.echo("  • Update quickscale.yml (if exists)")
    click.echo("  • Update .quickscale/apply-recovery.yml (if pending)")
    click.echo("  • Regenerate managed module wiring files")

    if not keep_data:
        click.secho(
            "\n🚨 DATABASE WARNING: This does NOT remove database tables!",
            fg="red",
            bold=True,
        )
        click.echo("   Module migrations and data will remain in your database.")
        click.echo(
            "   To fully remove module data, run reverse migrations BEFORE removing:"
        )
        click.echo(f"   python manage.py migrate quickscale_modules_{module_name} zero")

    click.echo("\n💡 To change immutable options, re-embed after removal:")
    click.echo(f"   quickscale plan --add {module_name}")
    click.echo("   quickscale apply")


def _log_step_result(success: bool, message: str, is_error: bool = False) -> None:
    """Log the result of a removal step"""
    if is_error:
        icon = "✅" if success else "❌"
        color = "green" if success else "red"
    else:
        icon = "✅" if success else "⚠️ "
        color = "green" if success else "yellow"
    click.secho(f"  {icon} {message}", fg=color)


def _show_success_message(module_name: str, keep_data: bool) -> None:
    """Display success message and next steps"""
    click.secho(
        f"\n✅ Module '{module_name}' removed successfully!", fg="green", bold=True
    )

    click.echo("\n📋 Next steps:")
    click.echo("  1. Review managed wiring files for expected module list")
    click.echo("  2. Run quickscale apply to reconcile any remaining config drift")
    if not keep_data:
        click.echo(f"  3. If needed, manually remove database tables for {module_name}")
    click.echo("\n💡 To re-embed with different options:")
    click.echo(f"   quickscale plan --add {module_name}")
    click.echo("   quickscale apply")
