"""Deployment commands for production platforms.

The implementation lives in private sibling modules grouped by concern
(``_deploy_steps``, ``_deploy_service_config``); this module owns the public command surface, re-exports public names for
unchanged import paths, and resolves collaborators through the sibling modules
that define them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from pathlib import Path as Path

import click as click

from quickscale_cli.commands.contract_vintage import (
    enforce_shipped_contract_vintage as enforce_shipped_contract_vintage,
    record_confirmed_adoption as record_confirmed_adoption,
)
from quickscale_core.generator.runtime_database import (
    RUNTIME_DB_ROLE as RUNTIME_DB_ROLE,
)
from quickscale_core.project_state import ProjectStateManager as ProjectStateManager
from quickscale_core.schema.state_schema import StateError as StateError

from quickscale_cli.utils.railway_utils import (
    check_poetry_lock_consistency as check_poetry_lock_consistency,
    check_railway_cli_version as check_railway_cli_version,
    check_uncommitted_changes as check_uncommitted_changes,
    deploy_railway_service as deploy_railway_service,
    fix_poetry_lock as fix_poetry_lock,
    generate_django_secret_key as generate_django_secret_key,
    generate_railway_domain as generate_railway_domain,
    get_app_service_name as get_app_service_name,
    get_railway_cli_version as get_railway_cli_version,
    get_railway_variables as get_railway_variables,
    install_railway_cli as install_railway_cli,
    is_npm_installed as is_npm_installed,
    is_railway_authenticated as is_railway_authenticated,
    is_railway_cli_installed as is_railway_cli_installed,
    is_railway_project_initialized as is_railway_project_initialized,
    link_database_to_service as link_database_to_service,
    login_railway_cli_browserless as login_railway_cli_browserless,
    run_railway_command as run_railway_command,
    set_railway_variables_batch as set_railway_variables_batch,
    upgrade_railway_cli as upgrade_railway_cli,
    verify_dockerfile as verify_dockerfile,
    verify_railway_dependencies as verify_railway_dependencies,
    verify_railway_json as verify_railway_json,
)
from quickscale_cli.commands._deploy_service_config import (
    runtime_database_url as runtime_database_url,
)
import quickscale_cli.commands.contract_vintage as _contract_vintage
import quickscale_core.project_state_manager as _project_state_manager
import quickscale_core.schema.state_schema as _state_schema
import quickscale_cli.utils._railway_project as _railway_project
import quickscale_cli.commands._deploy_steps as _deploy_steps
import quickscale_cli.commands._deploy_service_config as _deploy_service_config


@click.group()
def deploy() -> None:
    """Deployment commands for production platforms."""
    pass


@deploy.command()
@click.option(
    "--project-name",
    help="Railway project name (derived from directory name if not provided)",
)
@click.option(
    "--acknowledge-contract-vintage",
    is_flag=True,
    help="Proceed after manually adopting the required generated deployment files.",
)
@click.option(
    "--confirm-contract-adoption",
    is_flag=True,
    help=(
        "Record the generated-project contract adoption in .quickscale/state.yml "
        "and proceed."
    ),
)
def railway(
    project_name: str | None,
    acknowledge_contract_vintage: bool,
    confirm_contract_adoption: bool,
) -> None:
    """
    Deploy project to Railway with automated setup.

    This command uses a config-first approach:
    - railway.json defines build and deployment configuration
    - Migrations and static files run automatically via startCommand
    - Public domain is auto-generated and ALLOWED_HOSTS is auto-configured
    """
    project_path = Path.cwd()
    try:
        state = _project_state_manager.ProjectStateManager(project_path).load_state()
    except (_state_schema.StateError, OSError) as error:
        raise click.ClickException(
            f"Unable to read project state for the contract-vintage check: {error}"
        ) from error
    _contract_vintage.enforce_shipped_contract_vintage(
        state,
        state.modules if state else (),
        operation="'quickscale deploy railway'",
        acknowledged=acknowledge_contract_vintage or confirm_contract_adoption,
    )

    click.echo("🚀 Deploying to Railway...")

    if project_name is None:
        project_name = Path.cwd().name
    app_service = _railway_project.get_app_service_name(project_name)

    # Step 0: Pre-flight checks
    click.echo("\n🔍 Running pre-flight checks...")
    _deploy_steps._check_uncommitted_changes_step()
    # Record the confirmed adoption after the uncommitted-changes check, so the
    # operator is not warned about a change this command just made, and under
    # the project lock so the write cannot overwrite a concurrent change (SA207).
    if confirm_contract_adoption:
        _contract_vintage.record_confirmed_adoption(project_path, operation="deploy")
    _deploy_steps._verify_railway_files_step()
    _deploy_steps._verify_dependencies_step()
    _deploy_steps._check_poetry_lock_step()

    # Step 1: Check Railway CLI installation
    click.echo("\n🔧 Checking Railway CLI...")
    _deploy_steps._ensure_railway_cli_step()

    # Step 2: Check Railway authentication
    click.echo("\n🔐 Checking Railway authentication...")
    _deploy_steps._ensure_railway_auth_step()

    # Step 3: Initialize Railway project if needed
    _deploy_steps._init_railway_project_step()

    # Step 4: Read app state before any re-deploy mutation
    app_service_exists = _deploy_steps._app_service_exists_step(app_service)
    existing_vars = (
        _deploy_service_config._existing_service_variables(app_service)
        if app_service_exists
        else None
    )

    # Step 5: Check for PostgreSQL service
    click.echo("\n🗄️  Setting up PostgreSQL database...")
    postgres_service = _deploy_steps._setup_postgres_step()

    # Step 6: Create a first-deploy app service, then read its empty live state
    if not app_service_exists:
        click.echo(f"\n📦 Creating application service: {app_service}...")
        _deploy_steps._create_app_service_step(app_service)
        existing_vars = _deploy_service_config._existing_service_variables(app_service)

    # Step 7: Link DATABASE_URL from PostgreSQL to app service
    click.echo("\n🔗 Linking DATABASE_URL to app service...")
    database_linked = _deploy_steps._link_database_step(app_service, postgres_service)

    # Step 8: Generate public domain first
    click.echo("\n🌐 Generating public domain...")
    domain_name = _deploy_steps._generate_domain_step(app_service)
    domain_url = f"https://{domain_name}" if domain_name else None

    # Step 9: Configure environment variables in batch
    click.echo("\n⚙️  Configuring environment variables...")
    _deploy_service_config._configure_env_vars_step(
        app_service,
        domain_name,
        postgres_service,
        existing_vars,
    )

    # Step 10: Deploy to app service
    click.echo("\n🚢 Deploying application...")
    _deploy_service_config._deploy_app_step(app_service)

    # Step 11: Verify environment variables
    click.echo("\n🔍 Verifying environment configuration...")
    _deploy_service_config._verify_deployment_step(app_service)

    # Step 12: Display deployment summary
    _deploy_service_config._display_summary(
        app_service,
        domain_url,
        database_linked,
        postgres_service,
    )
