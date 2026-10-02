"""Deployment commands for production platforms.

The implementation lives in private sibling modules grouped by concern
(``_deploy_steps``, ``_deploy_service_config``); this module owns the public
command surface and re-exports every name that previously lived here
(Module Conventions rule 28), so existing
``quickscale_cli.commands.deployment_commands`` imports and test patch targets
keep working unchanged.
"""

from __future__ import annotations

import json as json
import secrets as secrets
import sys as sys
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
from quickscale_cli.commands._deploy_steps import (
    _app_service_exists_step as _app_service_exists_step,
    _check_and_upgrade_railway_cli as _check_and_upgrade_railway_cli,
    _check_poetry_lock_step as _check_poetry_lock_step,
    _check_uncommitted_changes_step as _check_uncommitted_changes_step,
    _create_app_service_step as _create_app_service_step,
    _ensure_railway_auth_step as _ensure_railway_auth_step,
    _ensure_railway_cli_step as _ensure_railway_cli_step,
    _generate_domain_step as _generate_domain_step,
    _init_railway_project_step as _init_railway_project_step,
    _link_database_step as _link_database_step,
    _list_railway_service_names as _list_railway_service_names,
    _list_railway_services as _list_railway_services,
    _postgres_service_matches as _postgres_service_matches,
    _setup_postgres_step as _setup_postgres_step,
    _verify_dependencies_step as _verify_dependencies_step,
    _verify_railway_files_step as _verify_railway_files_step,
)
from quickscale_cli.commands._deploy_service_config import (
    _configure_env_vars_step as _configure_env_vars_step,
    _deploy_app_step as _deploy_app_step,
    _display_summary as _display_summary,
    _existing_service_variables as _existing_service_variables,
    _runtime_role_variables as _runtime_role_variables,
    _verify_deployment_step as _verify_deployment_step,
    runtime_database_url as runtime_database_url,
)


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
        state = ProjectStateManager(project_path).load_state()
    except (StateError, OSError) as error:
        raise click.ClickException(
            f"Unable to read project state for the contract-vintage check: {error}"
        ) from error
    enforce_shipped_contract_vintage(
        state,
        state.modules if state else (),
        operation="'quickscale deploy railway'",
        acknowledged=acknowledge_contract_vintage or confirm_contract_adoption,
    )

    click.echo("🚀 Deploying to Railway...")

    if project_name is None:
        project_name = Path.cwd().name
    app_service = get_app_service_name(project_name)

    # Step 0: Pre-flight checks
    click.echo("\n🔍 Running pre-flight checks...")
    _check_uncommitted_changes_step()
    # Record the confirmed adoption after the uncommitted-changes check, so the
    # operator is not warned about a change this command just made, and under
    # the project lock so the write cannot overwrite a concurrent change (SA207).
    if confirm_contract_adoption:
        record_confirmed_adoption(project_path, operation="deploy")
    _verify_railway_files_step()
    _verify_dependencies_step()
    _check_poetry_lock_step()

    # Step 1: Check Railway CLI installation
    click.echo("\n🔧 Checking Railway CLI...")
    _ensure_railway_cli_step()

    # Step 2: Check Railway authentication
    click.echo("\n🔐 Checking Railway authentication...")
    _ensure_railway_auth_step()

    # Step 3: Initialize Railway project if needed
    _init_railway_project_step()

    # Step 4: Read app state before any re-deploy mutation
    app_service_exists = _app_service_exists_step(app_service)
    existing_vars = (
        _existing_service_variables(app_service) if app_service_exists else None
    )

    # Step 5: Check for PostgreSQL service
    click.echo("\n🗄️  Setting up PostgreSQL database...")
    postgres_service = _setup_postgres_step()

    # Step 6: Create a first-deploy app service, then read its empty live state
    if not app_service_exists:
        click.echo(f"\n📦 Creating application service: {app_service}...")
        _create_app_service_step(app_service)
        existing_vars = _existing_service_variables(app_service)

    # Step 7: Link DATABASE_URL from PostgreSQL to app service
    click.echo("\n🔗 Linking DATABASE_URL to app service...")
    database_linked = _link_database_step(app_service, postgres_service)

    # Step 8: Generate public domain first
    click.echo("\n🌐 Generating public domain...")
    domain_name = _generate_domain_step(app_service)
    domain_url = f"https://{domain_name}" if domain_name else None

    # Step 9: Configure environment variables in batch
    click.echo("\n⚙️  Configuring environment variables...")
    _configure_env_vars_step(
        app_service,
        domain_name,
        postgres_service,
        existing_vars,
    )

    # Step 10: Deploy to app service
    click.echo("\n🚢 Deploying application...")
    _deploy_app_step(app_service)

    # Step 11: Verify environment variables
    click.echo("\n🔍 Verifying environment configuration...")
    _verify_deployment_step(app_service)

    # Step 12: Display deployment summary
    _display_summary(
        app_service,
        domain_url,
        database_linked,
        postgres_service,
    )
