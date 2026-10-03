"""Pre-flight and Railway CLI setup steps for the deploy command.

Implementation detail of :mod:`quickscale_cli.commands.deployment_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import json
import sys

import click


import quickscale_cli.utils._railway_project as _railway_project
import quickscale_cli.utils._railway_cli as _railway_cli


def _check_uncommitted_changes_step() -> None:
    """Check for uncommitted git changes."""
    has_changes, status_output = _railway_project.check_uncommitted_changes()
    if has_changes:
        click.secho("⚠️  Warning: You have uncommitted changes:", fg="yellow")
        click.echo(status_output)
        click.echo("💡 Consider committing your changes before deployment")
        if not click.confirm("Continue anyway?", default=True):
            click.echo("Deployment cancelled")
            sys.exit(0)
    else:
        click.secho("✅ No uncommitted changes", fg="green")


def _verify_railway_files_step() -> None:
    """Verify railway.json and Dockerfile exist."""
    is_valid, error_msg = _railway_project.verify_railway_json()
    if not is_valid:
        click.secho(f"❌ Error: {error_msg}", fg="red", err=True)
        click.echo("💡 Railway needs railway.json to configure deployment", err=True)
        sys.exit(1)
    click.secho("✅ railway.json is valid", fg="green")

    dockerfile_exists, error_msg = _railway_project.verify_dockerfile()
    if not dockerfile_exists:
        click.secho(f"❌ Error: {error_msg}", fg="red", err=True)
        click.echo("💡 Railway uses Dockerfile to build your application", err=True)
        sys.exit(1)
    click.secho("✅ Dockerfile found", fg="green")


def _verify_dependencies_step() -> None:
    """Verify required Railway dependencies are present."""
    deps_ok, missing_deps = _railway_project.verify_railway_dependencies()
    if not deps_ok:
        click.secho("⚠️  Warning: Missing required Railway dependencies:", fg="yellow")
        for dep in missing_deps:
            click.echo(f"   - {dep}")
        click.echo("💡 Add these to pyproject.toml dependencies:")
        click.echo('   gunicorn = "^21.0"')
        click.echo('   psycopg2-binary = "^2.9"')
        click.echo('   dj-database-url = "^2.1"')
        click.echo('   whitenoise = "^6.6"')
        if not click.confirm("Continue anyway?", default=False):
            click.echo("Deployment cancelled")
            sys.exit(0)
    else:
        click.secho("✅ All required dependencies present", fg="green")


def _check_poetry_lock_step() -> None:
    """Check poetry.lock consistency and offer to fix."""
    is_consistent, lock_message = _railway_project.check_poetry_lock_consistency()
    if not is_consistent:
        click.secho(f"⚠️  Warning: {lock_message}", fg="yellow")
        if "not found" not in lock_message.lower():
            click.echo(
                "💡 The lock file needs to be regenerated to match pyproject.toml"
            )
            if click.confirm("Run 'poetry lock' to fix?", default=True):
                click.echo("🔄 Updating poetry.lock...")
                success, fix_message = _railway_project.fix_poetry_lock()
                if success:
                    click.secho(f"✅ {fix_message}", fg="green")
                else:
                    click.secho(f"❌ Error: {fix_message}", fg="red", err=True)
                    click.echo("💡 Try running manually: poetry lock", err=True)
                    if not click.confirm("Continue anyway?", default=False):
                        click.echo("Deployment cancelled")
                        sys.exit(0)
            else:
                click.echo("💡 Run 'poetry lock' before deploying")
                if not click.confirm("Continue without fixing?", default=False):
                    click.echo("Deployment cancelled")
                    sys.exit(0)
        else:
            click.echo("💡 Run 'poetry lock' to create poetry.lock file")
            if not click.confirm("Continue anyway?", default=False):
                click.echo("Deployment cancelled")
                sys.exit(0)
    else:
        click.secho("✅ poetry.lock is consistent", fg="green")


def _ensure_railway_cli_step() -> None:
    """Ensure Railway CLI is installed and up to date."""
    if not _railway_cli.is_railway_cli_installed():
        click.secho("⚠️  Railway CLI is not installed", fg="yellow")

        if not _railway_cli.is_npm_installed():
            click.secho("❌ Error: npm is not installed", fg="red", err=True)
            click.echo("\n💡 Install Node.js and npm first:", err=True)
            click.echo("   https://nodejs.org/", err=True)
            click.echo(
                "\nThen run this command again to auto-install Railway CLI", err=True
            )
            sys.exit(1)

        click.echo("📦 Installing Railway CLI via npm...")
        click.echo("   This may take a minute...")
        if _railway_cli.install_railway_cli():
            click.secho("✅ Railway CLI installed successfully", fg="green")
        else:
            click.secho("❌ Error: Failed to install Railway CLI", fg="red", err=True)
            click.echo("\n💡 Try installing manually:", err=True)
            click.echo("   npm install -g @railway/cli", err=True)
            click.echo("📖 See: https://docs.railway.app/develop/cli", err=True)
            sys.exit(1)
    else:
        click.secho("✅ Railway CLI is installed", fg="green")
        _check_and_upgrade_railway_cli()


def _check_and_upgrade_railway_cli() -> None:
    """Check Railway CLI version and upgrade if needed."""
    current_version = _railway_cli.get_railway_cli_version()
    if current_version:
        click.echo(f"   Current version: {current_version}")

        if not _railway_cli.check_railway_cli_version("4.0.0"):
            click.secho(
                f"⚠️  Railway CLI version {current_version} is outdated (need 4.0.0+)",
                fg="yellow",
            )
            click.echo("📦 Upgrading Railway CLI via npm...")
            click.echo("   This may take a minute...")

            if _railway_cli.upgrade_railway_cli():
                new_version = _railway_cli.get_railway_cli_version()
                click.secho(f"✅ Railway CLI upgraded to {new_version}", fg="green")
            else:
                click.secho("⚠️  Warning: Failed to upgrade Railway CLI", fg="yellow")
                click.echo("💡 Try upgrading manually:", err=True)
                click.echo("   npm update -g @railway/cli", err=True)
                if not click.confirm("Continue with current version?", default=False):
                    sys.exit(1)
        else:
            click.secho("✅ Railway CLI version is up to date", fg="green")


def _ensure_railway_auth_step() -> None:
    """Ensure Railway CLI is authenticated."""
    if not _railway_cli.is_railway_authenticated():
        click.secho("⚠️  Not authenticated with Railway", fg="yellow")
        click.echo("\n🌐 Starting browserless authentication...")
        click.echo("   You will receive a URL and pairing code")
        click.echo("   Visit the URL in your browser and enter the code")
        click.echo("")

        if _railway_cli.login_railway_cli_browserless():
            click.secho("✅ Successfully authenticated with Railway", fg="green")
        else:
            click.secho("❌ Error: Authentication failed", fg="red", err=True)
            click.echo("\n💡 Try authenticating manually:", err=True)
            click.echo("   railway login                    (opens browser)", err=True)
            click.echo(
                "   railway login --browserless      (for headless/remote systems)",
                err=True,
            )
            sys.exit(1)
    else:
        click.secho("✅ Already authenticated with Railway", fg="green")


def _init_railway_project_step() -> None:
    """Initialize Railway project if needed."""
    if not _railway_cli.is_railway_project_initialized():
        click.echo("\n📦 Initializing Railway project...")
        click.echo("💡 You can create a new project or link to an existing one")

        try:
            result = _railway_cli.run_railway_command(
                ["init"], timeout=60, interactive=True
            )

            if result.returncode != 0:
                click.secho(
                    "❌ Error: Failed to initialize Railway project", fg="red", err=True
                )
                sys.exit(1)

            click.secho("✅ Railway project initialized", fg="green")
        except (FileNotFoundError, TimeoutError) as e:
            click.secho(f"❌ Error: {e}", fg="red", err=True)
            sys.exit(1)
    else:
        click.echo("✅ Railway project already initialized")


def _list_railway_services() -> list[dict[str, object]]:
    """Return services in the linked Railway environment.

    Uses ``railway service list --json``.  A bare ``railway service`` is the
    deprecated interactive link prompt: once a project has services it waits
    for a selection and only ends at the command timeout.
    """
    result = _railway_cli.run_railway_command(["service", "list", "--json"], timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"railway service list failed: {(result.stderr or result.stdout).strip()}"
        )
    services = json.loads(result.stdout)
    if not isinstance(services, list) or not all(
        isinstance(service, dict) for service in services
    ):
        raise RuntimeError("railway service list returned an invalid JSON payload")
    return services


def _list_railway_service_names() -> list[str]:
    """Return the service names in the linked Railway environment."""
    return [str(service.get("name", "")) for service in _list_railway_services()]


def _postgres_service_matches(services: list[dict[str, object]]) -> list[str]:
    """Return PostgreSQL service names, preferring declared service types."""
    typed_matches: list[str] = []
    name_matches: list[str] = []
    for service in services:
        name = str(service.get("name", "")).strip()
        if not name:
            continue
        service_type = next(
            (
                str(service[key]).strip().casefold()
                for key in ("type", "serviceType", "service_type")
                if service.get(key)
            ),
            "",
        )
        if "postgres" in service_type:
            typed_matches.append(name)
        elif not service_type and "postgres" in name.casefold():
            name_matches.append(name)
    return typed_matches or name_matches


def _setup_postgres_step() -> str:
    """Return the one unambiguous PostgreSQL service name."""
    try:
        matches = _postgres_service_matches(_list_railway_services())
    except Exception as exc:
        raise click.ClickException(f"Unable to list Railway services: {exc}") from exc

    if not matches:
        click.echo("Adding PostgreSQL service...")
        result = _railway_cli.run_railway_command(
            ["add", "--database", "postgres"], timeout=30
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise click.ClickException(
                f"Unable to add a PostgreSQL service: {detail or 'unknown error'}"
            )
        try:
            matches = _postgres_service_matches(_list_railway_services())
        except Exception as exc:
            raise click.ClickException(
                f"Unable to confirm the PostgreSQL service: {exc}"
            ) from exc

    if len(matches) != 1:
        matched_names = ", ".join(matches) if matches else "none"
        raise click.ClickException(
            "Expected exactly one PostgreSQL service, "
            f"found {len(matches)} ({matched_names}). "
            "Create or remove Railway database services, then re-run the deploy."
        )

    click.echo(f"✅ PostgreSQL service found: {matches[0]}")
    return matches[0]


def _app_service_exists_step(app_service: str) -> bool:
    """Return whether the app service already exists, failing on unreadable state."""
    try:
        names = _list_railway_service_names()
    except Exception as exc:
        raise click.ClickException(f"Unable to list Railway services: {exc}") from exc
    exists = app_service.casefold() in (name.casefold() for name in names)
    if exists:
        click.echo(f"✅ Service '{app_service}' already exists")
    return exists


def _create_app_service_step(app_service: str) -> None:
    """Create application service."""
    try:
        names = _list_railway_service_names()

        if app_service.lower() in (name.lower() for name in names):
            click.echo(f"✅ Service '{app_service}' already exists")
        else:
            # Railway CLI 5.x prompts ("What do you need?", "Enter a variable")
            # whenever it sees a TTY, even with --service, and its TUI leaves the
            # terminal in raw mode on timeout. Run without a TTY so it never prompts.
            result = _railway_cli.run_railway_command(
                ["add", "--service", app_service], timeout=60, input_data=""
            )

            if result.returncode != 0:
                click.secho(
                    f"⚠️  Warning: Could not create service '{app_service}'", fg="yellow"
                )
                detail = (result.stderr or result.stdout or "").strip()
                if detail:
                    click.echo(f"   {detail}", err=True)
                click.echo("💡 Create manually: railway add --service", err=True)
            else:
                click.secho(f"✅ Service '{app_service}' created", fg="green")
    except Exception as e:
        click.secho(f"⚠️  Warning: Could not create app service: {e}", fg="yellow")


def _link_database_step(app_service: str, postgres_service: str) -> bool:
    """Link DATABASE_URL from PostgreSQL to app service."""
    try:
        link_success, link_message = _railway_project.link_database_to_service(
            app_service, postgres_service
        )
    except ValueError as exc:
        click.secho(f"❌ Error: {exc}", fg="red", err=True)
        sys.exit(1)

    if link_success:
        click.secho(f"✅ {link_message}", fg="green")
        return True
    else:
        click.secho(f"⚠️  Warning: {link_message}", fg="yellow")
        click.echo("💡 You may need to link DATABASE_URL manually:")
        click.echo(
            f"   railway variable set "
            f"'DATABASE_URL=${{{{{postgres_service}.DATABASE_URL}}}}' "
            f"--service {app_service}"
        )
        click.echo("   Use single quotes to prevent shell expansion errors")
        click.echo(
            "   Or link via Railway dashboard > Variables > New Variable > Reference"
        )
        return False


def _generate_domain_step(app_service: str) -> str | None:
    """Generate public domain and return the domain name."""
    try:
        domain_url = _railway_project.generate_railway_domain(app_service)
    except ValueError as exc:
        click.secho(f"❌ Error: {exc}", fg="red", err=True)
        sys.exit(1)

    if domain_url:
        click.secho(f"✅ Domain generated: {domain_url}", fg="green")
        return domain_url.replace("https://", "").replace("http://", "")
    else:
        click.secho("⚠️  Warning: Could not auto-generate domain", fg="yellow")
        click.echo("💡 Generate manually: railway domain")
        click.echo("💡 Then set: railway variable set ALLOWED_HOSTS=<your-domain>")
        return None
