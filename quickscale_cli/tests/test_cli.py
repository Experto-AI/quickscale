"""Tests for QuickScale CLI main commands."""

import sys
from pathlib import Path

import quickscale_cli
from quickscale_cli.main import cli


def test_cli_help(cli_runner):
    """Test CLI help command displays project information correctly"""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "QuickScale" in result.output
    assert "Compose your Django SaaS" in result.output


def test_cli_version_flag(cli_runner):
    """Test version flag returns current package version"""
    result = cli_runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "quickscale" in result.output.lower()
    assert quickscale_cli.__version__ in result.output


def test_version_command(cli_runner):
    """Test version command displays CLI and core package versions"""
    result = cli_runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "QuickScale CLI" in result.output
    assert quickscale_cli.__version__ in result.output


def test_init_command_help(cli_runner):
    """Test init command help displays correct information"""
    result = cli_runner.invoke(cli, ["init", "--help"])
    assert result.exit_code == 0
    assert "Generate a new Django project" in result.output
    assert "project_name" in result.output.lower()


def test_init_command_creates_project(cli_runner):
    """Test init command creates a project successfully"""
    project_name = "testproject"

    # Run CLI in isolated filesystem
    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["init", project_name], catch_exceptions=False)

        # Verify success
        assert result.exit_code == 0
        assert "Created project: testproject" in result.output
        assert "Next steps" in result.output
        assert "poetry install" in result.output

        # Verify project directory was created
        project_path = Path(project_name)
        assert project_path.exists()
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()


def test_init_command_missing_argument(cli_runner):
    """Test init command without project name shows error"""
    result = cli_runner.invoke(cli, ["init"])
    assert result.exit_code != 0
    assert "Error" in result.output or "Missing argument" in result.output


def test_init_command_invalid_project_name(cli_runner):
    """Test init command with invalid project name shows helpful error"""
    with cli_runner.isolated_filesystem():
        # Test with hyphen (not valid Python identifier)
        result = cli_runner.invoke(cli, ["init", "test-project"])
        assert result.exit_code != 0
        assert "Error" in result.output
        assert "valid Python identifier" in result.output

        # Test with number at start
        result = cli_runner.invoke(cli, ["init", "123project"])
        assert result.exit_code != 0
        assert "Error" in result.output


def test_init_command_existing_directory(cli_runner):
    """Test init command with existing directory shows error"""
    project_name = "existing_project"

    with cli_runner.isolated_filesystem():
        # Create directory first
        result = cli_runner.invoke(cli, ["init", project_name])
        assert result.exit_code == 0

        # Try to create again
        result = cli_runner.invoke(cli, ["init", project_name])
        assert result.exit_code != 0
        assert "already exists" in result.output
        assert "different name" in result.output


def test_init_command_with_underscores(cli_runner):
    """Test init command accepts project names with underscores"""
    project_name = "my_test_project"

    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["init", project_name], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Created project: my_test_project" in result.output


def test_init_command_output_messages(cli_runner):
    """Test init command displays all expected output messages"""
    project_name = "messagetest"

    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["init", project_name], catch_exceptions=False)

        assert result.exit_code == 0
        # Check for key output elements
        assert "Generating project:" in result.output
        assert "Created project:" in result.output
        assert "Next steps:" in result.output
        assert "cd messagetest" in result.output
        assert "poetry install" in result.output
        assert "python manage.py migrate" in result.output
        assert "python manage.py runserver" in result.output


def test_init_command_creates_correct_structure(cli_runner):
    """Test init command creates all expected files and directories"""
    project_name = "structuretest"

    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["init", project_name], catch_exceptions=False)
        assert result.exit_code == 0

        project_path = Path(project_name)

        # Verify key files exist
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / "poetry.lock").exists()
        assert (project_path / ".gitignore").exists()
        assert (project_path / "Dockerfile").exists()
        assert (project_path / "docker-compose.yml").exists()

        # Verify project package exists
        assert (project_path / project_name / "__init__.py").exists()
        assert (project_path / project_name / "urls.py").exists()
        assert (project_path / project_name / "wsgi.py").exists()
        assert (project_path / project_name / "asgi.py").exists()

        # Verify settings module exists
        assert (project_path / project_name / "settings" / "__init__.py").exists()
        assert (project_path / project_name / "settings" / "base.py").exists()
        assert (project_path / project_name / "settings" / "local.py").exists()
        assert (project_path / project_name / "settings" / "production.py").exists()

        # Verify templates and static directories
        assert (project_path / "templates").exists()
        assert (project_path / "static").exists()


def test_init_command_includes_all_required_dependencies(cli_runner):
    """Test that pyproject.toml includes all dependencies used in generated code"""
    project_name = "depstest"

    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["init", project_name], catch_exceptions=False)
        assert result.exit_code == 0

        project_path = Path(project_name)
        
        # Read pyproject.toml
        pyproject_content = (project_path / "pyproject.toml").read_text()
        
        # Critical dependencies that MUST be in pyproject.toml
        required_deps = [
            "Django",           # Core framework
            "python-decouple",  # Used in settings/base.py for config
            "whitenoise",       # Used in settings/base.py for static files
            "gunicorn",         # Production WSGI server
            "psycopg2-binary",  # PostgreSQL adapter
        ]
        
        # Verify each required dependency is declared
        for dep in required_deps:
            assert dep in pyproject_content, (
                f"Missing required dependency '{dep}' in pyproject.toml. "
                f"This dependency is imported in generated code and must be declared."
            )


def test_init_command_helpful_error_without_dependencies(cli_runner):
    """Test that manage.py shows helpful error when dependencies are missing"""
    import subprocess
    
    project_name = "nodepstest"

    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["init", project_name], catch_exceptions=False)
        assert result.exit_code == 0

        project_path = Path(project_name)
        
        # Try to run manage.py without installing dependencies
        # This simulates user running "python manage.py" without "poetry install"
        result = subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        
        # Should fail with helpful error message
        assert result.returncode != 0
        output = result.stderr + result.stdout
        
        # Verify helpful error message is shown
        assert "Missing required dependencies" in output or "python-decouple" in output
        assert "poetry install" in output
        assert "poetry run" in output


def test_generated_project_settings_imports(cli_runner):
    """Test that generated settings files only import declared dependencies"""
    project_name = "importstest"

    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["init", project_name], catch_exceptions=False)
        assert result.exit_code == 0

        project_path = Path(project_name)
        
        # Read settings files
        base_settings = (project_path / project_name / "settings" / "base.py").read_text()
        local_settings = (project_path / project_name / "settings" / "local.py").read_text()
        prod_settings = (project_path / project_name / "settings" / "production.py").read_text()
        
        # Read pyproject.toml to get declared dependencies
        pyproject_content = (project_path / "pyproject.toml").read_text()
        
        # Check that imports in settings match declared dependencies
        import_checks = [
            ("decouple", "python-decouple"),  # from decouple import config
            ("whitenoise", "whitenoise"),      # WhiteNoiseMiddleware in settings
        ]
        
        for import_name, dep_name in import_checks:
            if import_name in base_settings or import_name in local_settings or import_name in prod_settings:
                assert dep_name in pyproject_content, (
                    f"Settings import '{import_name}' but '{dep_name}' not in pyproject.toml"
                )
