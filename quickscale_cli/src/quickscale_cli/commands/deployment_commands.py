"""Deployment commands for production platforms."""

import sys

import click

from quickscale_cli.utils.railway_utils import (
    check_poetry_lock_consistency,
    check_railway_cli_version,
    check_uncommitted_changes,
    fix_poetry_lock,
    generate_django_secret_key,
    generate_railway_domain,
    get_app_service_name,
    get_railway_cli_version,
    get_railway_variables,
    install_railway_cli,
    is_npm_installed,
    is_railway_authenticated,
    is_railway_cli_installed,
    is_railway_project_initialized,
    link_database_to_service,
    login_railway_cli_browserless,
    run_railway_command,
    set_railway_variables_batch,
    upgrade_railway_cli,
    verify_dockerfile,
    verify_railway_dependencies,
    verify_railway_json,
)


@click.group()
def deploy() -> None:
    """Deployment commands for production platforms."""
    pass


@deploy.command()
@click.option(
    "--project-name", help="Railway project name (auto-detected if not provided)"
)
def railway(project_name: str | None) -> None:
    """
    Deploy project to Railway with automated setup.

    This command uses a config-first approach:
    - railway.json defines build and deployment configuration
    - Migrations and static files run automatically via startCommand
    - Public domain is auto-generated and ALLOWED_HOSTS is auto-configured
    """
    click.echo("🚀 Deploying to Railway...")

    # Determine the app service name for multi-service deployments
    app_service = get_app_service_name(project_name)

    # Step 0: Pre-flight checks
    click.echo("\n🔍 Running pre-flight checks...")

    # Check for uncommitted changes
    has_changes, status_output = check_uncommitted_changes()
    if has_changes:
        click.secho("⚠️  Warning: You have uncommitted changes:", fg="yellow")
        click.echo(status_output)
        click.echo("💡 Consider committing your changes before deployment")
        if not click.confirm("Continue anyway?", default=True):
            click.echo("Deployment cancelled")
            sys.exit(0)
    else:
        click.secho("✅ No uncommitted changes", fg="green")

    # Verify railway.json exists and is valid
    is_valid, error_msg = verify_railway_json()
    if not is_valid:
        click.secho(f"❌ Error: {error_msg}", fg="red", err=True)
        click.echo("💡 Railway needs railway.json to configure deployment", err=True)
        sys.exit(1)
    click.secho("✅ railway.json is valid", fg="green")

    # Verify Dockerfile exists
    dockerfile_exists, error_msg = verify_dockerfile()
    if not dockerfile_exists:
        click.secho(f"❌ Error: {error_msg}", fg="red", err=True)
        click.echo("💡 Railway uses Dockerfile to build your application", err=True)
        sys.exit(1)
    click.secho("✅ Dockerfile found", fg="green")

    # Verify required dependencies
    deps_ok, missing_deps = verify_railway_dependencies()
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

    # Check poetry.lock consistency
    is_consistent, lock_message = check_poetry_lock_consistency()
    if not is_consistent:
        click.secho(f"⚠️  Warning: {lock_message}", fg="yellow")
        if "not found" not in lock_message.lower():
            # Lock file exists but is inconsistent - offer to fix it
            click.echo(
                "💡 The lock file needs to be regenerated to match pyproject.toml"
            )
            if click.confirm("Run 'poetry lock --no-update' to fix?", default=True):
                click.echo("🔄 Updating poetry.lock...")
                success, fix_message = fix_poetry_lock()
                if success:
                    click.secho(f"✅ {fix_message}", fg="green")
                else:
                    click.secho(f"❌ Error: {fix_message}", fg="red", err=True)
                    click.echo(
                        "💡 Try running manually: poetry lock --no-update", err=True
                    )
                    if not click.confirm("Continue anyway?", default=False):
                        click.echo("Deployment cancelled")
                        sys.exit(0)
            else:
                click.echo("💡 Run 'poetry lock --no-update' before deploying")
                if not click.confirm("Continue without fixing?", default=False):
                    click.echo("Deployment cancelled")
                    sys.exit(0)
        else:
            # Lock file doesn't exist
            click.echo("💡 Run 'poetry lock' to create poetry.lock file")
            if not click.confirm("Continue anyway?", default=False):
                click.echo("Deployment cancelled")
                sys.exit(0)
    else:
        click.secho("✅ poetry.lock is consistent", fg="green")

    # Step 1: Check Railway CLI installation
    click.echo("\n🔧 Checking Railway CLI...")

    if not is_railway_cli_installed():
        click.secho("⚠️  Railway CLI is not installed", fg="yellow")

        # Check if npm is available
        if not is_npm_installed():
            click.secho("❌ Error: npm is not installed", fg="red", err=True)
            click.echo("\n💡 Install Node.js and npm first:", err=True)
            click.echo("   https://nodejs.org/", err=True)
            click.echo(
                "\nThen run this command again to auto-install Railway CLI", err=True
            )
            sys.exit(1)

        # Auto-install Railway CLI
        click.echo("📦 Installing Railway CLI via npm...")
        click.echo("   This may take a minute...")
        if install_railway_cli():
            click.secho("✅ Railway CLI installed successfully", fg="green")
        else:
            click.secho("❌ Error: Failed to install Railway CLI", fg="red", err=True)
            click.echo("\n💡 Try installing manually:", err=True)
            click.echo("   npm install -g @railway/cli", err=True)
            click.echo("📖 See: https://docs.railway.app/develop/cli", err=True)
            sys.exit(1)
    else:
        click.secho("✅ Railway CLI is installed", fg="green")

        # Check version and upgrade if needed
        current_version = get_railway_cli_version()
        if current_version:
            click.echo(f"   Current version: {current_version}")

            # Check if version is 4.0.0 or higher
            if not check_railway_cli_version("4.0.0"):
                click.secho(
                    f"⚠️  Railway CLI version {current_version} is outdated (need 4.0.0+)",
                    fg="yellow",
                )
                click.echo("📦 Upgrading Railway CLI via npm...")
                click.echo("   This may take a minute...")

                if upgrade_railway_cli():
                    new_version = get_railway_cli_version()
                    click.secho(f"✅ Railway CLI upgraded to {new_version}", fg="green")
                else:
                    click.secho(
                        "⚠️  Warning: Failed to upgrade Railway CLI", fg="yellow"
                    )
                    click.echo("💡 Try upgrading manually:", err=True)
                    click.echo("   npm update -g @railway/cli", err=True)
                    if not click.confirm(
                        "Continue with current version?", default=False
                    ):
                        sys.exit(1)
            else:
                click.secho("✅ Railway CLI version is up to date", fg="green")

    # Step 2: Check Railway authentication
    click.echo("\n🔐 Checking Railway authentication...")

    if not is_railway_authenticated():
        click.secho("⚠️  Not authenticated with Railway", fg="yellow")
        click.echo("\n🌐 Starting browserless authentication...")
        click.echo("   You will receive a URL and pairing code")
        click.echo("   Visit the URL in your browser and enter the code")
        click.echo("")

        if login_railway_cli_browserless():
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

    # Step 3: Initialize Railway project if needed
    if not is_railway_project_initialized():
        click.echo("\n📦 Initializing Railway project...")
        click.echo("💡 You can create a new project or link to an existing one")

        try:
            # Run init interactively so user can select/create project
            result = run_railway_command(["init"], timeout=60, interactive=True)

            if result.returncode != 0:
                click.secho(
                    "❌ Error: Failed to initialize Railway project", fg="red", err=True
                )
                sys.exit(1)

            click.secho("✅ Railway project initialized", fg="green")
        except FileNotFoundError as e:
            click.secho(f"❌ Error: {e}", fg="red", err=True)
            sys.exit(1)
        except TimeoutError as e:
            click.secho(f"❌ Error: {e}", fg="red", err=True)
            sys.exit(1)
    else:
        click.echo("✅ Railway project already initialized")

    # Step 4: Check for PostgreSQL service
    click.echo("\n🗄️  Setting up PostgreSQL database...")
    try:
        # Check if database already exists
        result = run_railway_command(["service"], timeout=10)

        if "postgres" in result.stdout.lower():
            click.echo("✅ PostgreSQL service already exists")
        else:
            # Add PostgreSQL service
            click.echo("Adding PostgreSQL service...")
            result = run_railway_command(["add", "--database", "postgres"], timeout=30)

            if result.returncode != 0:
                click.secho("⚠️  Warning: Could not auto-add PostgreSQL", fg="yellow")
                click.echo("💡 Add manually: railway add", err=True)
            else:
                click.secho("✅ PostgreSQL service added", fg="green")
    except Exception as e:
        click.secho(f"⚠️  Warning: Could not check database service: {e}", fg="yellow")

    # Step 5: Create app service
    click.echo(f"\n📦 Creating application service: {app_service}...")
    try:
        # Check if app service already exists
        result = run_railway_command(["service"], timeout=10)

        if app_service.lower() in result.stdout.lower():
            click.echo(f"✅ Service '{app_service}' already exists")
        else:
            # Create app service (Railway CLI v4 requires explicit service creation)
            result = run_railway_command(
                ["add", "--service", app_service], timeout=30, interactive=True
            )

            if result.returncode != 0:
                click.secho(
                    f"⚠️  Warning: Could not create service '{app_service}'", fg="yellow"
                )
                click.echo("💡 Create manually: railway add --service", err=True)
            else:
                click.secho(f"✅ Service '{app_service}' created", fg="green")
    except Exception as e:
        click.secho(f"⚠️  Warning: Could not create app service: {e}", fg="yellow")

    # Step 6: Link DATABASE_URL from PostgreSQL to app service
    click.echo("\n🔗 Linking DATABASE_URL to app service...")
    link_success, link_message = link_database_to_service(app_service)

    if link_success:
        click.secho(f"✅ {link_message}", fg="green")
    else:
        click.secho(f"⚠️  Warning: {link_message}", fg="yellow")
        click.echo("💡 You may need to link DATABASE_URL manually:")
        click.echo(
            f'   railway variables --set "DATABASE_URL=${{{{Postgres.DATABASE_URL}}}}" '
            f"--service {app_service}"
        )
        click.echo(
            "   Or link via Railway dashboard > Variables > New Variable > Reference"
        )

    # Step 7: Generate public domain first (before setting env vars)
    click.echo("\n🌐 Generating public domain...")
    domain_url = generate_railway_domain(app_service)

    if domain_url:
        click.secho(f"✅ Domain generated: {domain_url}", fg="green")
        # Extract domain without https://
        domain_name = domain_url.replace("https://", "").replace("http://", "")
    else:
        click.secho("⚠️  Warning: Could not auto-generate domain", fg="yellow")
        click.echo("💡 Generate manually: railway domain")
        click.echo("💡 Then set: railway variables --set ALLOWED_HOSTS=<your-domain>")
        domain_name = None

    # Step 8: Configure environment variables in batch (triggers only ONE deployment)
    click.echo("\n⚙️  Configuring environment variables...")
    click.echo(f"Setting variables for service: {app_service}")
    click.echo("💡 Setting all variables at once to minimize deployments")

    # Prepare all environment variables
    env_vars = {
        "SECRET_KEY": generate_django_secret_key(),
        "DEBUG": "False",
        "DJANGO_SETTINGS_MODULE": f"{app_service}.settings.production",
    }

    # Add ALLOWED_HOSTS if domain was generated
    if domain_name:
        env_vars["ALLOWED_HOSTS"] = domain_name

    # Set all variables in one batch command
    success, failed_keys = set_railway_variables_batch(env_vars, service=app_service)

    if success:
        click.secho("✅ All environment variables configured successfully", fg="green")
        for key in env_vars:
            if key == "SECRET_KEY":
                click.echo(f"   • {key}=<generated>")
            else:
                click.echo(f"   • {key}={env_vars[key]}")
        click.echo("💡 This triggers ONE deployment with all variables set")
    else:
        click.secho(
            "⚠️  Warning: Some environment variables could not be set", fg="yellow"
        )
        if failed_keys:
            click.echo("Failed variables:")
            for key in failed_keys:
                click.echo(f"   • {key}")
        click.echo("💡 Set manually using: railway variables --set KEY=VALUE")

    # Step 9: Deploy to app service (using railway.json config)
    click.echo("\n🚢 Deploying application...")
    click.echo("💡 Using railway.json for build and deployment configuration")
    click.echo("💡 Migrations will run automatically at startup (via railway.json)")
    click.echo("This may take a few minutes...")

    try:
        # Deploy to the specific app service
        # railway.json in project root configures the build and startCommand
        result = run_railway_command(
            ["up", "--service", app_service, "--detach"], timeout=60
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

    # Step 10: Verify environment variables were set correctly
    click.echo("\n🔍 Verifying environment configuration...")
    deployed_vars = get_railway_variables(app_service)

    if deployed_vars:
        click.secho("✅ Environment variables verified", fg="green")
        # Show which variables are configured (mask sensitive values)
        required_vars = [
            "DATABASE_URL",
            "SECRET_KEY",
            "DEBUG",
            "DJANGO_SETTINGS_MODULE",
            "ALLOWED_HOSTS",
        ]
        for var in required_vars:
            if var in deployed_vars:
                if var == "SECRET_KEY":
                    click.echo(f"   • {var}=<set>")
                elif var == "DATABASE_URL":
                    click.echo(f"   • {var}=<linked to PostgreSQL>")
                else:
                    value = deployed_vars[var]
                    # Truncate long values
                    if len(value) > 50:
                        value = value[:50] + "..."
                    click.echo(f"   • {var}={value}")
            else:
                click.secho(f"   ⚠️  {var} not set", fg="yellow")
    else:
        click.secho("⚠️  Warning: Could not verify environment variables", fg="yellow")
        click.echo("💡 Check manually: railway variables")

    # Step 11: Display deployment summary
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
    click.echo("   • DATABASE_URL linked")
    click.echo("   • Public domain generated")

    click.echo("\n📋 Next steps:")
    click.echo(f"   1. Monitor deployment: railway logs --service {app_service}")
    click.echo("   2. Wait for deployment to complete (check Railway dashboard)")
    if domain_url:
        click.echo(f"   3. Visit your site: {domain_url}")
    else:
        click.echo("   3. Get URL: railway status")
    click.echo(
        f"   4. Create superuser: railway run --service {app_service} "
        f"python manage.py createsuperuser"
    )
    click.echo("   5. Configure custom domain (optional): railway domain")

    click.echo("\n⚠️  Important:")
    click.echo("   • Monitor logs for startup errors: railway logs")
    click.echo("   • Verify DATABASE_URL in Railway dashboard > Variables")
    click.echo("   • Check healthcheck status in Railway dashboard")
    click.echo("   • Migrations run automatically on first deploy")

    click.echo("\n📖 Documentation:")
    click.echo("   • Railway: https://docs.railway.app")
    click.echo("   • QuickScale: docs/deployment/railway.md")

    click.echo("\n" + "=" * 60)
    click.secho("✅ Deployment process completed successfully!", fg="green", bold=True)
    click.echo("=" * 60)
