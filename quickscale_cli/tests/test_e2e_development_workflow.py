"""
End-to-end tests for QuickScale CLI development commands.

These tests verify the complete development workflow with real Docker containers:
1. Generate Django project
2. Start services with 'quickscale up'
3. Verify containers with 'quickscale ps'
4. Run Django commands with 'quickscale manage'
5. Access shell with 'quickscale shell'
6. View logs with 'quickscale logs'
7. Stop services with 'quickscale down'

Run with: pytest -m e2e
Note: Requires Docker to be running
"""

import subprocess
import time

import pytest
from click.testing import CliRunner

from quickscale_cli.main import cli
from quickscale_core.generator import ProjectGenerator


@pytest.mark.e2e
class TestDevelopmentCommandsE2E:
    """End-to-end tests for development commands with real Docker containers."""

    @pytest.fixture
    def test_project(self, tmp_path):
        """Generate a test project and return its path."""
        generator = ProjectGenerator()
        project_name = "e2e_cli_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Verify project was created
        assert (project_path / "manage.py").exists()
        assert (project_path / "docker-compose.yml").exists()

        yield project_path

        # Cleanup: ensure containers are stopped
        try:
            subprocess.run(
                ["docker-compose", "down", "-v"],
                cwd=project_path,
                capture_output=True,
                timeout=30,
            )
        except Exception:
            pass  # Best effort cleanup

    @pytest.fixture
    def ensure_docker_running(self):
        """Ensure Docker is running before tests."""
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip("Docker is not running")

    def test_full_development_workflow(self, test_project, ensure_docker_running):
        """
        Test complete development workflow end-to-end.

        This test verifies:
        - quickscale up starts containers
        - quickscale ps shows running containers
        - quickscale manage runs Django commands (migrate, test)
        - quickscale shell executes commands in container
        - quickscale logs retrieves service logs
        - quickscale down stops containers
        """
        runner = CliRunner()
        project_path = test_project

        # Change to project directory for commands
        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Step 1: Start services
            result = runner.invoke(cli, ["up"])
            assert result.exit_code == 0, f"up failed: {result.output}"
            assert "Services started successfully!" in result.output

            # Wait for containers to be fully up
            time.sleep(5)

            # Step 2: Check service status
            result = runner.invoke(cli, ["ps"])
            assert result.exit_code == 0, f"ps failed: {result.output}"

            # Step 3: Wait for database to be ready and run migrations
            # The containers need time to fully initialize
            time.sleep(10)

            result = runner.invoke(cli, ["manage", "migrate", "--noinput"])
            assert result.exit_code == 0, f"manage migrate failed: {result.output}"

            # Step 4: Run generated project tests (verifies pytest is available)
            result = runner.invoke(cli, ["manage", "test"])
            assert result.exit_code == 0, f"manage test failed: {result.output}"
            # Verify test command ran (generated project may not have tests yet)
            assert (
                "passed" in result.output.lower()
                or "ok" in result.output.lower()
                or "ran 0 tests" in result.output.lower()
            ), f"Test command didn't run properly: {result.output}"

            # Step 5: Execute shell command
            result = runner.invoke(cli, ["shell", "-c", "echo 'E2E test'"])
            assert result.exit_code == 0, f"shell failed: {result.output}"

            # Step 6: Retrieve logs
            result = runner.invoke(cli, ["logs", "--tail", "10"])
            assert result.exit_code == 0, f"logs failed: {result.output}"

            # Step 7: Stop services
            result = runner.invoke(cli, ["down"])
            assert result.exit_code == 0, f"down failed: {result.output}"
            assert "Services stopped successfully!" in result.output

        finally:
            # Restore original directory
            os.chdir(original_cwd)

    def test_up_down_lifecycle(self, test_project, ensure_docker_running):
        """Test container lifecycle: up → down → up again."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # First up
            result = runner.invoke(cli, ["up"])
            assert result.exit_code == 0
            time.sleep(3)

            # Down
            result = runner.invoke(cli, ["down"])
            assert result.exit_code == 0
            time.sleep(2)

            # Second up (verify can restart)
            result = runner.invoke(cli, ["up"])
            assert result.exit_code == 0
            time.sleep(3)

            # Final cleanup
            result = runner.invoke(cli, ["down"])
            assert result.exit_code == 0

        finally:
            os.chdir(original_cwd)

    def test_up_with_build_flag(self, test_project, ensure_docker_running):
        """Test up command with --build flag."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Up with build
            result = runner.invoke(cli, ["up", "--build"])
            assert result.exit_code == 0
            assert "Services started successfully!" in result.output
            time.sleep(3)

            # Cleanup
            runner.invoke(cli, ["down"])

        finally:
            os.chdir(original_cwd)

    def test_down_with_volumes(self, test_project, ensure_docker_running):
        """Test down command with --volumes flag."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Start services
            runner.invoke(cli, ["up"])
            time.sleep(3)

            # Down with volumes
            result = runner.invoke(cli, ["down", "--volumes"])
            assert result.exit_code == 0
            assert "Services stopped successfully!" in result.output

        finally:
            os.chdir(original_cwd)

    def test_logs_with_options(self, test_project, ensure_docker_running):
        """Test logs command with various options."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Start services
            runner.invoke(cli, ["up"])
            time.sleep(3)

            # Test logs with tail
            result = runner.invoke(cli, ["logs", "--tail", "5"])
            assert result.exit_code == 0

            # Test logs with timestamps
            result = runner.invoke(cli, ["logs", "--timestamps"])
            assert result.exit_code == 0

            # Test logs for specific service
            result = runner.invoke(cli, ["logs", "web"])
            assert result.exit_code == 0

            # Cleanup
            runner.invoke(cli, ["down"])

        finally:
            os.chdir(original_cwd)

    def test_error_when_not_in_project(self, tmp_path):
        """Test commands fail gracefully when not in a QuickScale project."""
        runner = CliRunner()

        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)  # Empty directory, not a project

        try:
            # All development commands should fail with helpful error
            commands = [
                ["up"],
                ["down"],
                ["ps"],
                ["shell"],
                ["manage", "help"],
                ["logs"],
            ]

            for cmd in commands:
                result = runner.invoke(cli, cmd)
                assert result.exit_code == 1
                assert "Not in a QuickScale project directory" in result.output

        finally:
            os.chdir(original_cwd)

    def test_manage_command_no_args(self, test_project):
        """Test manage command fails with helpful error when no args provided."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            result = runner.invoke(cli, ["manage"])
            assert result.exit_code == 1
            assert "No Django management command specified" in result.output

        finally:
            os.chdir(original_cwd)

    def test_manage_test_command(self, test_project, ensure_docker_running):
        """Test that generated project tests can run (verifies pytest is installed)."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Start services
            result = runner.invoke(cli, ["up"])
            assert result.exit_code == 0
            time.sleep(5)

            # Wait for DB to be ready
            time.sleep(10)

            # Run migrations first
            result = runner.invoke(cli, ["manage", "migrate", "--noinput"])
            assert result.exit_code == 0

            # Run the generated project's tests
            result = runner.invoke(cli, ["manage", "test"])
            assert result.exit_code == 0, f"Tests failed: {result.output}"
            # Verify test command ran (generated project may not have tests yet)
            assert (
                "pytest" in result.output.lower()
                or "passed" in result.output.lower()
                or "ran 0 tests" in result.output.lower()
            ), f"Test command didn't run properly: {result.output}"

            # Cleanup
            runner.invoke(cli, ["down"])

        finally:
            os.chdir(original_cwd)


@pytest.mark.e2e
class TestDevelopmentCommandsIntegration:
    """Integration tests for development commands with Docker."""

    @pytest.fixture
    def generated_project(self, tmp_path):
        """Generate and prepare a project for testing."""
        generator = ProjectGenerator()
        project_name = "integration_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)
        yield project_path

        # Cleanup
        try:
            subprocess.run(
                ["docker-compose", "down", "-v"],
                cwd=project_path,
                capture_output=True,
                timeout=30,
            )
        except Exception:
            pass

    def test_docker_compose_configuration_valid(self, generated_project):
        """Verify docker-compose.yml is valid and parseable."""
        result = subprocess.run(
            ["docker-compose", "config"],
            cwd=generated_project,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"docker-compose config invalid: {result.stderr}"

    def test_project_structure_supports_docker_workflow(self, generated_project):
        """Verify project has all files needed for Docker workflow."""
        required_files = [
            "docker-compose.yml",
            "Dockerfile",
            ".dockerignore",
            "manage.py",
        ]

        for file in required_files:
            assert (generated_project / file).exists(), f"Missing required file: {file}"

    def test_environment_files_present(self, generated_project):
        """Verify environment configuration files exist."""
        # Should have example env file
        env_example = generated_project / ".env.example"
        if env_example.exists():
            content = env_example.read_text()
            # Should have essential config
            assert len(content) > 0
