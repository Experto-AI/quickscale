"""Environment, deploy, and verification steps for the deploy command.

Implementation detail of :mod:`quickscale_cli.commands.deployment_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import secrets
import sys

import click

import quickscale_cli.commands.deployment_commands as _deployment_commands


def runtime_database_url(postgres_service: str, password: str) -> str:
    """Build RUNTIME_DATABASE_URL for the restricted runtime role.

    Host, port and database are Railway reference variables on the PostgreSQL
    service, resolved by Railway at deploy time. The generated start.sh creates
    the role from RUNTIME_DB_ROLE and RUNTIME_DB_PASSWORD before migrating.
    """
    ref = postgres_service
    return (
        f"postgresql://{_deployment_commands.RUNTIME_DB_ROLE}:{password}"
        f"@${{{{{ref}.PGHOST}}}}:${{{{{ref}.PGPORT}}}}/${{{{{ref}.PGDATABASE}}}}"
    )


def _existing_service_variables(app_service: str) -> dict[str, str]:
    """Return the app service's current Railway variables or fail hard."""
    try:
        variables = _deployment_commands.get_railway_variables(app_service)
    except Exception as exc:
        raise click.ClickException(
            f"Unable to read Railway variables for service '{app_service}': {exc}"
        ) from exc
    if variables is None:
        raise click.ClickException(
            f"Unable to read Railway variables for service '{app_service}'."
        )
    return variables


def _runtime_role_variables(
    postgres_service: str, existing: dict[str, str]
) -> dict[str, str]:
    """Return the runtime-role variables to set, honouring what already exists.

    - ``RUNTIME_DATABASE_URL`` set without ``RUNTIME_DB_PASSWORD``: the role is
      operator-managed, so nothing is written.
    - ``RUNTIME_DB_PASSWORD`` already set: it is reused, so a re-deploy never
      rotates the password underneath the container still serving traffic.
    - Otherwise a new URL-safe (hex) password is generated.
    """
    if existing.get("RUNTIME_DATABASE_URL") and not existing.get("RUNTIME_DB_PASSWORD"):
        return {}
    password = existing.get("RUNTIME_DB_PASSWORD") or secrets.token_hex(24)
    return {
        "RUNTIME_DB_ROLE": _deployment_commands.RUNTIME_DB_ROLE,
        "RUNTIME_DB_PASSWORD": password,
        "RUNTIME_DATABASE_URL": _deployment_commands.runtime_database_url(
            postgres_service, password
        ),
    }


def _configure_env_vars_step(
    app_service: str,
    domain_name: str | None,
    postgres_service: str = "Postgres",
    existing_vars: dict[str, str] | None = None,
) -> None:
    """Configure environment variables in batch, including the runtime DB role."""
    if existing_vars is None:
        raise click.ClickException(
            f"Railway variables for service '{app_service}' were not loaded."
        )

    click.echo(f"Setting variables for service: {app_service}")
    click.echo("💡 Setting all variables at once to minimize deployments")

    # Django settings module must reference a valid Python package path.
    django_package = app_service.replace("-", "_")

    env_vars = {
        "SECRET_KEY": existing_vars.get("SECRET_KEY")
        or _deployment_commands.generate_django_secret_key(),
        "DEBUG": "False",
        "DJANGO_SETTINGS_MODULE": f"{django_package}.settings.production",
    }

    runtime_vars = _deployment_commands._runtime_role_variables(
        postgres_service, existing_vars
    )
    env_vars.update(runtime_vars)

    if domain_name:
        env_vars["ALLOWED_HOSTS"] = domain_name

    success, failed_keys = _deployment_commands.set_railway_variables_batch(
        env_vars, service=app_service
    )

    if success:
        click.secho("✅ All environment variables configured successfully", fg="green")
        for key in env_vars:
            if key in ("SECRET_KEY", "RUNTIME_DB_PASSWORD"):
                state = "reused" if existing_vars.get(key) else "generated"
                click.echo(f"   • {key}=<{state}>")
            elif key == "RUNTIME_DATABASE_URL":
                click.echo(
                    f"   • {key}=<{_deployment_commands.RUNTIME_DB_ROLE} "
                    f"@ {postgres_service}>"
                )
            else:
                click.echo(f"   • {key}={env_vars[key]}")
        if not runtime_vars:
            click.echo(
                "   • RUNTIME_DATABASE_URL: operator-managed (RUNTIME_DB_PASSWORD unset), left unchanged"
            )
        click.echo(
            "💡 Variables are set without triggering a deployment. The deploy step below will start one."
        )
    else:
        click.secho(
            "❌ Error: Some environment variables could not be set — "
            "deployment aborted",
            fg="red",
            err=True,
        )
        if failed_keys:
            click.echo("Failed variables:", err=True)
            for key in failed_keys:
                click.echo(f"   • {key}", err=True)
        click.echo(
            "💡 Set variables securely with: railway variable set KEY --stdin",
            err=True,
        )
        sys.exit(1)


def _deploy_app_step(app_service: str) -> None:
    """Deploy application to Railway."""
    click.echo("💡 Using railway.json for build and deployment configuration")
    click.echo("💡 Migrations will run automatically at startup (via railway.json)")
    click.echo("This may take a few minutes...")

    try:
        result = _deployment_commands.deploy_railway_service(
            project_path=_deployment_commands.Path.cwd(),
            service_name=app_service,
            timeout=60,
        )

        if result.returncode != 0:
            click.secho("❌ Error: Deployment failed", fg="red", err=True)
            click.echo(f"\n{result.stderr}", err=True)
            click.echo("\n💡 Troubleshooting:", err=True)
            click.echo("   - Check build logs: railway logs", err=True)
            click.echo("   - Verify railway.json exists in project root", err=True)
            click.echo("   - Verify Dockerfile is present", err=True)
            click.echo("   - Check pyproject.toml dependencies", err=True)
            click.echo(
                "   - Ensure DATABASE_URL is linked to PostgreSQL service", err=True
            )
            sys.exit(1)

        click.secho("✅ Deployment started", fg="green")
        click.echo("💡 Railway is building and deploying your application...")
        click.echo("💡 The startCommand in railway.json will:")
        click.echo("   1. Run database migrations (requires DATABASE_URL)")
        click.echo("   2. Start Gunicorn server")
    except TimeoutError:
        click.secho("⚠️  Deployment command timed out", fg="yellow")


def _verify_deployment_step(app_service: str) -> bool:
    """Verify environment variables were set correctly."""
    try:
        deployed_vars = _deployment_commands.get_railway_variables(app_service)
    except Exception as exc:
        raise click.ClickException(
            f"Unable to verify Railway variables for service '{app_service}': {exc}"
        ) from exc
    if deployed_vars is None:
        raise click.ClickException(
            f"Unable to verify Railway variables for service '{app_service}'."
        )
    database_url_present = False

    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
        "DEBUG",
        "DJANGO_SETTINGS_MODULE",
        "ALLOWED_HOSTS",
    ]
    missing_vars: list[str] = []
    present_vars: list[tuple[str, str]] = []
    for var in required_vars:
        if var in deployed_vars and deployed_vars[var]:
            if var == "SECRET_KEY":
                present_vars.append((var, "<set>"))
            elif var == "DATABASE_URL":
                present_vars.append((var, "<linked to PostgreSQL>"))
                database_url_present = True
            else:
                value = deployed_vars[var]
                if len(value) > 50:
                    value = value[:50] + "..."
                present_vars.append((var, value))
        else:
            missing_vars.append(var)

    if not missing_vars:
        click.secho("✅ Environment variables verified", fg="green")
    else:
        click.secho(
            f"⚠️  Environment variables partially configured "
            f"({len(missing_vars)} missing)",
            fg="yellow",
        )
    for var, value in present_vars:
        click.echo(f"   • {var}={value}")
    for var in missing_vars:
        click.secho(f"   ⚠️  {var} not set", fg="yellow")

    return database_url_present


def _display_summary(
    app_service: str,
    domain_url: str | None,
    database_linked: bool,
    postgres_service: str,
) -> None:
    """Display deployment summary."""
    click.echo("\n" + "=" * 60)
    click.secho("🎉 DEPLOYMENT SUMMARY", fg="green", bold=True)
    click.echo("=" * 60)

    click.echo(f"\n📦 Project: {app_service}")
    if domain_url:
        click.echo(f"🌐 URL: {domain_url}")
        click.echo("💡 Note: First deployment may take 5-10 minutes")
    else:
        click.echo("🌐 URL: Get with 'railway status'")

    click.echo("\n✅ Services configured:")
    click.echo("   • PostgreSQL database")
    click.echo(f"   • {app_service} application")
    if database_linked:
        click.echo("   • DATABASE_URL linked")
    else:
        click.echo("   • DATABASE_URL not linked (manual action required)")
    click.echo("   • Public domain generated")

    click.echo("\n📋 Next steps:")
    click.echo(f"   1. Monitor deployment: railway logs --service {app_service}")
    click.echo("   2. Wait for deployment to complete (check Railway dashboard)")
    if domain_url:
        click.echo(f"   3. Visit your site: {domain_url}")
    else:
        click.echo("   3. Get URL: railway status")
    click.echo(
        "   4. Create superuser automatically: set DJANGO_SUPERUSER_USERNAME, "
        "DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD variables in Railway "
        "dashboard — start.sh will create it on next deploy"
    )
    click.echo(
        f"      Or manually: railway ssh --service {app_service} "
        f"python manage.py createsuperuser"
    )
    click.echo("   5. Configure custom domain (optional): railway domain")

    click.echo("\n⚠️  Important:")
    click.echo("   • Monitor logs for startup errors: railway logs")
    click.echo("   • Verify DATABASE_URL in Railway dashboard > Variables")
    if not database_linked:
        click.echo(
            "   • Link DB manually: railway variable set "
            f"'DATABASE_URL=${{{{{postgres_service}.DATABASE_URL}}}}' "
            f"--service {app_service}"
        )
    click.echo("   • Check healthcheck status in Railway dashboard")
    click.echo("   • Migrations run automatically on first deploy")
    click.echo(
        f"   • start.sh creates the restricted "
        f"'{_deployment_commands.RUNTIME_DB_ROLE}' database role "
        "before migrating"
    )

    click.echo("\n📖 Documentation:")
    click.echo("   • Railway: https://docs.railway.app")
    click.echo("   • QuickScale: docs/deployment/railway.md")

    click.echo("\n" + "=" * 60)
    click.secho("✅ Deployment process completed successfully!", fg="green", bold=True)
    click.echo("=" * 60)
