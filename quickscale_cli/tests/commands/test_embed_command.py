"""Integration tests for quickscale embed command"""

import subprocess

import pytest


@pytest.mark.integration
def test_embed_auth_module_no_circular_import(tmp_path):
    """Test that embedding auth module doesn't cause circular import issues

    This test validates the complete workflow:
    1. Generate a project with quickscale init
    2. Initialize git (required for embed)
    3. Embed the auth module
    4. Run Django migrations (would fail with circular import)

    Regression test for: ImportError circular dependency between
    quickscale_modules_auth.forms and allauth.account.forms
    """
    project_name = "testproject"
    project_path = tmp_path / project_name

    # Step 1: Generate project
    result = subprocess.run(
        ["quickscale", "init", project_name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Project generation failed: {result.stderr}"
    assert project_path.exists()

    # Step 2: Initialize git (required for embed)
    subprocess.run(["git", "init"], cwd=project_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=project_path,
        check=True,
    )

    # Step 3: Embed auth module with non-interactive config
    # Use echo to provide answers: y (registration), none (verification), email (method)
    embed_result = subprocess.run(
        ["bash", "-c", "echo -e 'y\nnone\nemail\n' | quickscale embed --module auth"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )
    assert (
        embed_result.returncode == 0
    ), f"Module embedding failed: {embed_result.stderr}\n{embed_result.stdout}"

    # Verify module was embedded
    module_path = project_path / "modules" / "auth"
    assert module_path.exists(), "Auth module directory not created"

    # Step 4: Run Django check (lighter than full migrate, catches import errors)
    # This would fail with ImportError if circular import exists
    check_result = subprocess.run(
        ["poetry", "run", "python", "manage.py", "check"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )

    # Check for the specific circular import error
    assert (
        "circular import" not in check_result.stderr.lower()
    ), f"Circular import detected:\n{check_result.stderr}"
    assert (
        "cannot import name 'SignupForm'" not in check_result.stderr
    ), f"SignupForm import error detected:\n{check_result.stderr}"

    # If check passed, the circular import issue is fixed
    if check_result.returncode != 0:
        # Some other error - print for debugging
        pytest.fail(
            f"Django check failed with unexpected error:\n"
            f"stdout: {check_result.stdout}\n"
            f"stderr: {check_result.stderr}"
        )


@pytest.mark.integration
@pytest.mark.slow
def test_embed_auth_module_full_migration(tmp_path):
    """Full test including database migrations

    This is a more comprehensive test that actually runs migrations.
    Marked as 'slow' since it takes longer to execute.
    """
    project_name = "testproject"
    project_path = tmp_path / project_name

    # Generate project
    subprocess.run(["quickscale", "init", project_name], cwd=tmp_path, check=True)

    # Initialize git
    subprocess.run(["git", "init"], cwd=project_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=project_path, check=True)

    # Embed auth module
    subprocess.run(
        ["bash", "-c", "echo -e 'y\nnone\nemail\n' | quickscale embed --module auth"],
        cwd=project_path,
        check=True,
        capture_output=True,
    )

    # Run full migration
    migrate_result = subprocess.run(
        ["poetry", "run", "python", "manage.py", "migrate"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )

    # Verify no circular import errors
    assert "circular import" not in migrate_result.stderr.lower()
    assert "cannot import name 'SignupForm'" not in migrate_result.stderr
    assert (
        migrate_result.returncode == 0
    ), f"Migration failed:\nstdout: {migrate_result.stdout}\nstderr: {migrate_result.stderr}"


@pytest.mark.integration
def test_embed_auth_after_migrations_shows_warning(tmp_path):
    """Test that embedding auth module after migrations shows warning and prevents conflicts

    This test validates that:
    1. If migrations have already been run
    2. Embedding auth module will detect this
    3. And show a warning about migration conflicts
    4. And prompt user to confirm
    """
    project_name = "testproject"
    project_path = tmp_path / project_name

    # Step 1: Generate project
    subprocess.run(["quickscale", "init", project_name], cwd=tmp_path, check=True)

    # Step 2: Initialize git (required for embed)
    subprocess.run(["git", "init"], cwd=project_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=project_path,
        check=True,
    )

    # Step 3: Install dependencies and run migrations BEFORE embedding auth
    subprocess.run(["poetry", "install"], cwd=project_path, check=True)
    migrate_result = subprocess.run(
        ["poetry", "run", "python", "manage.py", "migrate"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Applying admin.0001_initial... OK" in migrate_result.stdout

    # Step 4: Try to embed auth module (should show warning)
    # The warning appears before configurator, but n will be consumed by "Continue?" prompt
    # Use printf to provide proper newlines: n for "Continue?", then y/none/email for configurator if it proceeds
    embed_result = subprocess.run(
        ["bash", "-c", "printf 'n\n' | quickscale embed --module auth"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )

    # Verify warning was shown
    assert (
        "Warning: Django migrations have already been run" in embed_result.stdout
    ), f"Expected migration warning not found:\n{embed_result.stdout}"
    assert (
        "The auth module changes the User model" in embed_result.stdout
    ), f"Expected User model warning not found:\n{embed_result.stdout}"
    assert (
        "Embedding cancelled" in embed_result.stdout
    ), f"Expected cancellation message not found:\n{embed_result.stdout}\n{embed_result.stderr}"

    # Verify module was NOT embedded (since user declined)
    module_path = project_path / "modules" / "auth"
    assert (
        not module_path.exists()
    ), "Auth module should not be embedded when user declines"

    # Step 5: Test that user CAN continue if they choose to (with 'y')
    # First 'y' for "Continue?", then defaults for configurator (3 enters)
    embed_result_continue = subprocess.run(
        ["bash", "-c", "printf 'y\n\n\n\n' | quickscale embed --module auth"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )

    # Should show warning but continue
    assert (
        "Warning: Django migrations have already been run"
        in embed_result_continue.stdout
    )
    assert (
        embed_result_continue.returncode == 0
    ), f"Embed should succeed when user confirms:\n{embed_result_continue.stderr}"

    # Verify module WAS embedded (since user confirmed)
    assert module_path.exists(), "Auth module should be embedded when user confirms"

    # Step 6: Verify that running migrations now causes the expected conflict
    migrate_after_result = subprocess.run(
        ["poetry", "run", "python", "manage.py", "migrate"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )

    # Should fail with InconsistentMigrationHistory
    assert (
        migrate_after_result.returncode != 0
    ), "Migrations should fail after embedding auth post-migration"
    assert (
        "InconsistentMigrationHistory" in migrate_after_result.stderr
    ), f"Expected migration conflict error not found:\n{migrate_after_result.stderr}"
