"""Fresh-generation and output-directory handling for apply.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click


from quickscale_core.schema.config_schema import (
    QuickScaleConfig,
)
from quickscale_core.schema.state_schema import (
    QuickScaleState,
)

# AF6 Phase 2 — core step bodies

import quickscale_core.generator as _generator


def _generate_project(config: QuickScaleConfig, output_path: Path) -> bool:
    """Generate project using ProjectGenerator

    Fresh-generation only. ``selected_modules`` is forwarded from
    ``config.modules.keys()`` so the React theme gating sees the same module
    selection the user declared in ``quickscale.yml``. Existing-project apply
    paths do not call this function, so the legacy ``selected_modules=None``
    behavior of :class:`ProjectGenerator` remains reachable for them.
    """
    try:
        click.echo(
            f"⏳ Generating project: {config.project.slug} "
            f"(package: {config.project.package})..."
        )

        generator = _generator.ProjectGenerator(
            theme=config.project.theme,
            selected_modules=list(config.modules.keys()),
        )
        # mypy can resolve an older installed quickscale-core signature here.
        generate_project = cast(Any, generator.generate)
        generate_project(
            config.project.slug,
            output_path,
            package_name=config.project.package,
        )

        click.secho(f"✅ Project generated: {output_path}", fg="green")
        return True
    except FileExistsError:
        click.secho(
            f"❌ Directory already exists: {output_path}",
            fg="red",
            err=True,
        )
        click.echo("   Use --force to overwrite or choose a different name", err=True)
        return False
    except ValueError as e:
        click.secho(f"❌ Invalid project configuration: {e}", fg="red", err=True)
        return False
    except Exception as e:
        click.secho(f"❌ Failed to generate project: {e}", fg="red", err=True)
        return False


def _determine_output_path(config_path: Path, project_slug: str) -> Path:
    """Determine output directory for project."""
    config_path = config_path.resolve()
    if config_path.parent.name == project_slug:
        return config_path.parent
    return Path.cwd() / project_slug


def _display_config_summary(qs_config: QuickScaleConfig) -> None:
    """Display configuration summary."""
    click.echo("\n🚀 Applying configuration:")
    click.echo(f"   Project slug: {qs_config.project.slug}")
    click.echo(f"   Python package: {qs_config.project.package}")
    click.echo(f"   Theme: {qs_config.project.theme}")
    if qs_config.modules:
        click.echo(f"   Modules: {', '.join(qs_config.modules.keys())}")
    else:
        click.echo("   Modules: (none)")
    click.echo(
        f"   Docker: start={qs_config.docker.start}, build={qs_config.docker.build}"
    )


def _check_output_directory(
    output_path: Path, existing_state: QuickScaleState | None, force: bool
) -> None:
    """Check if output directory is valid and handle existing content."""
    if not output_path.exists() or not any(output_path.iterdir()):
        click.echo(f"\n📁 Output directory: {output_path}")
        return

    if existing_state is not None:
        click.echo(f"\n📁 Existing project detected: {output_path}")
        click.echo("   Performing incremental apply (only changes will be made)")
        return

    existing_files = list(output_path.iterdir())
    if len(existing_files) == 1 and existing_files[0].name == "quickscale.yml":
        return

    if not force:
        click.secho(
            f"\n❌ Directory already exists and is not empty: {output_path}",
            fg="red",
            err=True,
        )
        click.echo(
            "   Use --force to overwrite or remove the directory first",
            err=True,
        )
        raise click.Abort()
    else:
        click.secho(
            f"\n⚠️  --force: Will overwrite existing content in {output_path}",
            fg="yellow",
        )


def _generate_new_project(
    qs_config: QuickScaleConfig, output_path: Path, force: bool
) -> None:
    """Generate project for new installations."""
    if output_path.exists():
        quickscale_yml_path = output_path / "quickscale.yml"
        if quickscale_yml_path.exists():
            _generate_with_existing_config(
                qs_config, output_path, quickscale_yml_path, force
            )
        else:
            if not _generate_project(qs_config, output_path):
                raise click.Abort()
    else:
        if not _generate_project(qs_config, output_path):
            raise click.Abort()


def _generate_with_existing_config(
    qs_config: QuickScaleConfig,
    output_path: Path,
    quickscale_yml_path: Path,
    force: bool,
) -> None:
    """Generate project when quickscale.yml already exists in output path."""
    import shutil
    import tempfile

    saved_config = quickscale_yml_path.read_text()

    temp_dir = Path(tempfile.mkdtemp(dir=str(output_path.parent)))
    temp_project = temp_dir / qs_config.project.slug

    if not _generate_project(qs_config, temp_project):
        shutil.rmtree(temp_dir)
        raise click.Abort()

    if force:
        # Backup+swap+rollback: move existing content to a same-filesystem backup
        # dir, swap staged files in, and restore the originals on failure.
        backup_dir = Path(tempfile.mkdtemp(dir=str(output_path.parent)))
        try:
            for item in output_path.iterdir():
                if item.name != "quickscale.yml":
                    shutil.move(str(item), str(backup_dir / item.name))
        except Exception:
            # Backup phase failed — restore whatever was moved to backup
            for item in backup_dir.iterdir():
                shutil.move(str(item), str(output_path / item.name))
            shutil.rmtree(backup_dir)
            shutil.rmtree(temp_dir)
            raise click.Abort()

        try:
            for item in temp_project.iterdir():
                dest = output_path / item.name
                shutil.move(str(item), str(dest))
        except Exception:
            # Staging swap failed — remove partially-moved files, restore originals
            for item in list(output_path.iterdir()):
                if item.name != "quickscale.yml":
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            for item in backup_dir.iterdir():
                shutil.move(str(item), str(output_path / item.name))
            shutil.rmtree(backup_dir)
            shutil.rmtree(temp_dir)
            raise click.Abort()

        shutil.rmtree(backup_dir)
    else:
        for item in temp_project.iterdir():
            dest = output_path / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))

    shutil.rmtree(temp_dir)

    quickscale_yml_path.write_text(saved_config)
    click.secho(f"✅ Project generated: {output_path}", fg="green")
