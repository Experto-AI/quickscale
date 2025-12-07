"""Apply command for executing project configuration

Implements `quickscale apply [config]` - executes quickscale.yml configuration
"""

import subprocess
from datetime import datetime
from pathlib import Path

import click

from quickscale_cli.commands.module_commands import embed_module
from quickscale_cli.schema.config_schema import (
    ConfigValidationError,
    QuickScaleConfig,
    validate_config,
)
from quickscale_cli.schema.delta import ConfigDelta, compute_delta, format_delta
from quickscale_cli.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateManager,
)
from quickscale_core.generator import ProjectGenerator
from quickscale_core.manifest import ModuleManifest
from quickscale_core.manifest.loader import get_manifest_for_module
from quickscale_core.settings_manager import apply_mutable_config_changes


def _run_command(
    cmd: list[str],
    cwd: Path,
    description: str,
    capture: bool = True,
) -> tuple[bool, str]:
    """Run a shell command with progress output

    Args:
        cmd: Command and arguments
        cwd: Working directory
        description: Description for progress output
        capture: Whether to capture output

    Returns:
        Tuple of (success, output)

    """
    click.echo(f"⏳ {description}...")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            click.secho(f"✅ {description}", fg="green")
            return True, result.stdout if capture else ""
        else:
            click.secho(f"❌ {description} failed", fg="red")
            if capture and result.stderr:
                click.echo(result.stderr, err=True)
            return False, result.stderr if capture else ""
    except FileNotFoundError as e:
        click.secho(f"❌ Command not found: {cmd[0]}", fg="red", err=True)
        return False, str(e)
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        return False, str(e)


def _generate_project(config: QuickScaleConfig, output_path: Path) -> bool:
    """Generate project using ProjectGenerator"""
    try:
        click.echo(f"⏳ Generating project: {config.project.name}...")

        # Validate theme availability
        if config.project.theme in ["showcase_htmx", "showcase_react"]:
            click.secho(
                f"❌ Error: Theme '{config.project.theme}' is not yet implemented",
                fg="red",
                err=True,
            )
            click.echo(
                f"\n💡 The '{config.project.theme}' theme is planned for a future release:",
                err=True,
            )
            click.echo("   - showcase_htmx: Coming in v0.70.0", err=True)
            click.echo("   - showcase_react: Coming in v0.71.0", err=True)
            return False

        generator = ProjectGenerator(theme=config.project.theme)
        generator.generate(config.project.name, output_path)

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


def _init_git(project_path: Path) -> bool:
    """Initialize git repository"""
    success, _ = _run_command(
        ["git", "init"],
        project_path,
        "Initializing git repository",
    )
    return success


def _git_commit(project_path: Path, message: str) -> bool:
    """Create a git commit"""
    # Stage all files
    success, _ = _run_command(
        ["git", "add", "-A"],
        project_path,
        f"Staging files for: {message}",
    )
    if not success:
        return False

    # Commit
    success, _ = _run_command(
        ["git", "commit", "-m", message],
        project_path,
        f"Committing: {message}",
    )
    return success


def _embed_module(project_path: Path, module_name: str) -> bool:
    """Embed a module using the embed_module function with non-interactive mode"""
    click.echo(f"⏳ Embedding module: {module_name}...")

    try:
        success = embed_module(
            module=module_name,
            project_path=project_path,
            non_interactive=True,
        )

        if success:
            click.secho(f"✅ Module embedded: {module_name}", fg="green")
            return True
        else:
            click.secho(f"❌ Failed to embed module: {module_name}", fg="red", err=True)
            return False
    except Exception as e:
        click.secho(f"❌ Unexpected error embedding module: {e}", fg="red", err=True)
        return False


def _run_poetry_install(project_path: Path) -> bool:
    """Run poetry install in project"""
    return _run_command(
        ["poetry", "install"],
        project_path,
        "Installing dependencies (poetry install)",
    )[0]


def _run_migrations(project_path: Path) -> bool:
    """Run Django migrations"""
    return _run_command(
        ["poetry", "run", "python", "manage.py", "migrate"],
        project_path,
        "Running migrations",
    )[0]


def _start_docker(project_path: Path, build: bool = True) -> bool:
    """Start Docker services using quickscale up"""
    cmd = ["quickscale", "up"]
    if build:
        cmd.append("--build")

    success, _ = _run_command(
        cmd,
        project_path,
        "Starting Docker services",
    )
    return success


def _load_module_manifests(
    project_path: Path, module_names: list[str]
) -> dict[str, ModuleManifest]:
    """Load manifests for all installed modules"""
    manifests: dict[str, ModuleManifest] = {}
    for module_name in module_names:
        manifest = get_manifest_for_module(project_path, module_name)
        if manifest:
            manifests[module_name] = manifest
    return manifests


def _apply_mutable_config(
    project_path: Path,
    delta: ConfigDelta,
    manifests: dict[str, ModuleManifest],
) -> bool:
    """Apply mutable configuration changes to settings.py

    Returns True if all changes were applied successfully

    """
    if not delta.has_mutable_config_changes:
        return True

    click.echo("\n⏳ Applying mutable configuration changes...")

    all_success = True
    for module_name, change in delta.get_all_mutable_changes():
        if change.django_setting:
            results = apply_mutable_config_changes(
                project_path, module_name, {change.django_setting: change.new_value}
            )
            for setting_name, success, message in results:
                if success:
                    click.secho(f"  ✅ {message}", fg="green")
                else:
                    click.secho(f"  ❌ {message}", fg="red")
                    all_success = False

    if all_success:
        click.secho("✅ Mutable configuration changes applied", fg="green")

    return all_success


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

    click.echo("\n💡 To change immutable options:")
    modules_with_immutable = set(
        module_name for module_name, _ in delta.get_all_immutable_changes()
    )
    for module_name in modules_with_immutable:
        click.echo(f"   1. quickscale remove {module_name}")
        click.echo("   2. Update quickscale.yml with new options")
        click.echo("   3. quickscale apply")
        click.echo()

    return False


def _update_module_config_in_state(
    state: QuickScaleState,
    config: QuickScaleConfig,
    delta: ConfigDelta,
) -> None:
    """Update module options in state after mutable config changes"""
    for module_name, module_delta in delta.config_deltas.items():
        if module_delta.has_mutable_changes and module_name in state.modules:
            # Update options with new values
            current_options = state.modules[module_name].options or {}
            for change in module_delta.mutable_changes:
                current_options[change.option_name] = change.new_value
            state.modules[module_name].options = current_options


@click.command()
@click.argument(
    "config",
    required=False,
    type=click.Path(exists=True),
    default="quickscale.yml",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing project directory",
)
@click.option(
    "--no-docker",
    is_flag=True,
    help="Skip Docker operations even if configured",
)
@click.option(
    "--no-modules",
    is_flag=True,
    help="Skip module embedding",
)
def apply(config: str, force: bool, no_docker: bool, no_modules: bool) -> None:
    """
    Execute project configuration from quickscale.yml.

    Generates a Django project based on the configuration file,
    embeds selected modules, and optionally starts Docker services.

    \b
    Examples:
      quickscale apply                    # Use quickscale.yml in current dir
      quickscale apply myapp/quickscale.yml  # Use specific config file
      quickscale apply --force            # Overwrite existing project
      quickscale apply --no-docker        # Skip Docker operations

    \b
    Execution Order:
      1. Validate configuration
      2. Generate project
      3. Initialize git + initial commit
      4. Embed modules (if configured)
      5. Run poetry install
      6. Run migrations
      7. Start Docker (if configured)
    """
    config_path = Path(config)

    # Check if config exists
    if not config_path.exists():
        click.secho(
            f"❌ Configuration file not found: {config_path}", fg="red", err=True
        )
        click.echo("\n💡 Create a configuration with: quickscale plan <name>", err=True)
        raise click.Abort()

    # Read and validate configuration
    click.echo(f"\n📋 Reading configuration: {config_path}")
    try:
        yaml_content = config_path.read_text()
        qs_config = validate_config(yaml_content)
    except ConfigValidationError as e:
        click.secho(f"\n❌ Configuration error:\n{e}", fg="red", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"\n❌ Failed to read configuration: {e}", fg="red", err=True)
        raise click.Abort()

    # Resolve config path to absolute path for reliable parent directory detection
    config_path = config_path.resolve()

    # Determine output path first (needed for state loading)
    # If config is in a project directory (e.g., myapp/quickscale.yml), use parent
    if config_path.parent.name == qs_config.project.name:
        output_path = config_path.parent
    else:
        output_path = Path.cwd() / qs_config.project.name

    # Load existing state if project exists
    state_manager = StateManager(output_path)
    existing_state = state_manager.load() if output_path.exists() else None

    # Load manifests for modules (needed for config change detection)
    manifests: dict[str, ModuleManifest] = {}
    if existing_state and existing_state.modules:
        manifests = _load_module_manifests(
            output_path, list(existing_state.modules.keys())
        )

    # Compute delta (with manifests for config change detection)
    delta = compute_delta(qs_config, existing_state, manifests)

    # Display configuration summary
    click.echo("\n🚀 Applying configuration:")
    click.echo(f"   Project: {qs_config.project.name}")
    click.echo(f"   Theme: {qs_config.project.theme}")
    if qs_config.modules:
        click.echo(f"   Modules: {', '.join(qs_config.modules.keys())}")
    else:
        click.echo("   Modules: (none)")
    click.echo(
        f"   Docker: start={qs_config.docker.start}, build={qs_config.docker.build}"
    )

    # Show delta if state exists
    if existing_state is not None:
        click.echo("\n📊 Change Detection:")
        click.echo(format_delta(delta))

        # If no changes and project exists, show message and exit
        if not delta.has_changes:
            click.secho(
                "\n✅ Nothing to do. Configuration matches applied state.", fg="green"
            )
            raise click.Abort()

        # Check for immutable config changes (abort if found)
        if not _check_immutable_config_changes(delta):
            raise click.Abort()

        # Warn about theme changes
        if delta.theme_changed:
            click.secho(
                "\n⚠️  WARNING: Theme changes are not supported after initial project generation!",
                fg="red",
                bold=True,
            )
            click.echo(
                "   Theme changes require regenerating the entire project from scratch.",
            )
            if not click.confirm("Continue anyway?", default=False):
                raise click.Abort()

    # Check if project directory already has content
    if output_path.exists() and any(output_path.iterdir()):
        # If we have a state file, this is an incremental apply
        if existing_state is not None:
            click.echo(f"\n📁 Existing project detected: {output_path}")
            click.echo("   Performing incremental apply (only changes will be made)")
        else:
            # No state file but directory exists
            existing_files = list(output_path.iterdir())
            # Allow if only quickscale.yml exists
            if not (
                len(existing_files) == 1 and existing_files[0].name == "quickscale.yml"
            ):
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
    else:
        click.echo(f"\n📁 Output directory: {output_path}")

    # Confirm before proceeding
    if not click.confirm("\n❓ Proceed with apply?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()

    click.echo("\n" + "=" * 50)
    click.echo("🔧 Starting apply process...")
    click.echo("=" * 50)

    # For incremental applies, skip project generation
    project_generated = False
    if existing_state is None:
        # Step 1: Generate project (only for new projects)
        # If output_path exists and has only quickscale.yml, we need to handle it differently
        if output_path.exists():
            quickscale_yml_path = output_path / "quickscale.yml"
            if quickscale_yml_path.exists():
                # Save quickscale.yml, remove other content, generate, restore
                saved_config = quickscale_yml_path.read_text()

                # Remove everything except quickscale.yml if force
                if force:
                    import shutil

                    for item in output_path.iterdir():
                        if item.name != "quickscale.yml":
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()

                # Generate project (will fail if dir exists with other content)
                # We need to generate to a temp location and move
                import tempfile

                temp_dir = Path(tempfile.mkdtemp())
                temp_project = temp_dir / qs_config.project.name

                if not _generate_project(qs_config, temp_project):
                    import shutil

                    shutil.rmtree(temp_dir)
                    raise click.Abort()

                # Move generated content to output_path
                import shutil

                for item in temp_project.iterdir():
                    dest = output_path / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    shutil.move(str(item), str(dest))
                shutil.rmtree(temp_dir)

                # Restore quickscale.yml
                quickscale_yml_path.write_text(saved_config)
                click.secho(f"✅ Project generated: {output_path}", fg="green")
            else:
                if not _generate_project(qs_config, output_path):
                    raise click.Abort()
        else:
            if not _generate_project(qs_config, output_path):
                raise click.Abort()
        project_generated = True
    else:
        click.echo("⏭️  Skipping project generation (project already exists)")

    # Step 2: Initialize git (only for new projects)
    if project_generated:
        if not _init_git(output_path):
            click.secho("⚠️  Git initialization failed, continuing...", fg="yellow")
        else:
            # Configure git user for commits (needed in CI/test environments)
            subprocess.run(
                ["git", "config", "user.email", "quickscale@example.com"],
                cwd=output_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "QuickScale"],
                cwd=output_path,
                capture_output=True,
            )

            # Step 3: Initial commit
            if not _git_commit(output_path, "Initial project structure"):
                click.secho("⚠️  Initial commit failed, continuing...", fg="yellow")

    # Step 4: Embed modules (only modules in delta.modules_to_add)
    modules_to_embed = (
        delta.modules_to_add if existing_state else list(qs_config.modules.keys())
    )
    embedded_modules = []

    if not no_modules and modules_to_embed:
        for module_name in modules_to_embed:
            if not _embed_module(output_path, module_name):
                click.secho(
                    f"⚠️  Module embedding failed for {module_name}, continuing...",
                    fg="yellow",
                )
            else:
                embedded_modules.append(module_name)
                # Commit after each module
                _git_commit(output_path, f"Add module: {module_name}")
    elif existing_state and not delta.modules_to_add:
        click.echo("⏭️  No new modules to embed")

    # Step 5: Run poetry install
    if not _run_poetry_install(output_path):
        click.secho("⚠️  Poetry install failed, continuing...", fg="yellow")

    # Step 6: Run migrations
    if not _run_migrations(output_path):
        click.secho("⚠️  Migrations failed, continuing...", fg="yellow")

    # Step 7: Apply mutable configuration changes
    if existing_state and delta.has_mutable_config_changes:
        if not _apply_mutable_config(output_path, delta, manifests):
            click.secho("⚠️  Some config changes failed to apply", fg="yellow")

    # Step 8: Start Docker
    if not no_docker and qs_config.docker.start:
        if not _start_docker(output_path, qs_config.docker.build):
            click.secho("⚠️  Docker start failed, continuing...", fg="yellow")

    # Step 9: Save state
    try:
        # Build new state
        if existing_state is None:
            # New project - create initial state
            new_state = QuickScaleState(
                version="1",
                project=ProjectState(
                    name=qs_config.project.name,
                    theme=qs_config.project.theme,
                    created_at=datetime.now().isoformat(),
                    last_applied=datetime.now().isoformat(),
                ),
                modules={},
            )
        else:
            # Existing project - update state
            new_state = existing_state
            new_state.project.last_applied = datetime.now().isoformat()

        # Add embedded modules to state
        for module_name in embedded_modules:
            new_state.modules[module_name] = ModuleState(
                name=module_name,
                version=None,  # TODO: Get from module metadata
                commit_sha=None,  # TODO: Get from git
                embedded_at=datetime.now().isoformat(),
                options=qs_config.modules[module_name].options,
            )

        # Also include modules that were already in state (not re-embedded)
        if existing_state:
            for module_name, module_state in existing_state.modules.items():
                if module_name not in new_state.modules:
                    new_state.modules[module_name] = module_state

        # Update options for modules with mutable config changes
        _update_module_config_in_state(new_state, qs_config, delta)

        state_manager.save(new_state)
        click.secho("✅ State saved to .quickscale/state.yml", fg="green")
    except Exception as e:
        click.secho(f"⚠️  Failed to save state: {e}", fg="yellow")

    # Success!
    click.echo("\n" + "=" * 50)
    click.secho("🎉 Apply complete!", fg="green", bold=True)
    click.echo("=" * 50)

    # Next steps
    click.echo("\n📋 Next steps:")
    if output_path != Path.cwd():
        click.echo(f"  cd {qs_config.project.name}")

    if qs_config.docker.start and not no_docker:
        click.echo("  # Docker services should be running")
        click.echo("  quickscale logs web  # View logs")
        click.echo("  quickscale ps        # Check status")
    else:
        click.echo("  quickscale up        # Start Docker services")
        click.echo("  # Or run without Docker:")
        click.echo("  poetry run python manage.py runserver")

    click.echo("\n  Visit: http://localhost:8000")
