"""Tests for development commands."""

import subprocess
from unittest.mock import Mock, patch

from click.testing import CliRunner

from quickscale_cli.commands.development_commands import (
    down,
    logs,
    manage,
    ps,
    shell,
    up,
)


class TestUpCommand:
    """Tests for up command."""

    def test_up_success(self):
        """Test successful service startup."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.is_port_available"
                ) as mock_port:
                    with patch(
                        "quickscale_cli.commands.development_commands.get_docker_compose_command"
                    ) as mock_cmd:
                        with patch("subprocess.run") as mock_run:
                            mock_in_project.return_value = True
                            mock_docker.return_value = True
                            mock_port.return_value = True
                            mock_cmd.return_value = ["docker-compose"]
                            mock_run.return_value = Mock(returncode=0)

                            result = runner.invoke(up)

                            assert result.exit_code == 0
                            assert "Services started successfully!" in result.output

    def test_up_not_in_project(self):
        """Test up command when not in project directory."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            mock_in_project.return_value = False

            result = runner.invoke(up)

            assert result.exit_code == 1
            assert "Not in a QuickScale project directory" in result.output

    def test_up_docker_not_running(self):
        """Test up command when Docker is not running."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                mock_in_project.return_value = True
                mock_docker.return_value = False

                result = runner.invoke(up)

                assert result.exit_code == 1
                assert "Docker is not running" in result.output

    def test_up_with_build_flag(self):
        """Test up command with --build flag."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.is_port_available"
                ) as mock_port:
                    with patch(
                        "quickscale_cli.commands.development_commands.get_docker_compose_command"
                    ) as mock_cmd:
                        with patch("subprocess.run") as mock_run:
                            mock_in_project.return_value = True
                            mock_docker.return_value = True
                            mock_port.return_value = True
                            mock_cmd.return_value = ["docker-compose"]
                            mock_run.return_value = Mock(returncode=0)

                            result = runner.invoke(up, ["--build"])

                            assert result.exit_code == 0
                            # Verify --build was passed to docker-compose
                            call_args = mock_run.call_args[0][0]
                            assert "--build" in call_args

    def test_up_with_no_cache_flag(self):
        """Test up command with --no-cache flag."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.is_port_available"
                ) as mock_port:
                    with patch(
                        "quickscale_cli.commands.development_commands.get_docker_compose_command"
                    ) as mock_cmd:
                        with patch("subprocess.run") as mock_run:
                            mock_in_project.return_value = True
                            mock_docker.return_value = True
                            mock_port.return_value = True
                            mock_cmd.return_value = ["docker-compose"]
                            mock_run.return_value = Mock(returncode=0)

                            result = runner.invoke(up, ["--no-cache"])

                            assert result.exit_code == 0
                            # Verify --build and --no-cache were passed to docker-compose
                            call_args = mock_run.call_args[0][0]
                            assert "--build" in call_args
                            assert "--no-cache" in call_args


class TestDownCommand:
    """Tests for down command."""

    def test_down_success(self):
        """Test successful service shutdown."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(down)

                        assert result.exit_code == 0
                        assert "Services stopped successfully!" in result.output

    def test_down_with_volumes(self):
        """Test down command with volumes flag."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(down, ["--volumes"])

                        assert result.exit_code == 0
                        # Verify --volumes was passed to docker-compose
                        call_args = mock_run.call_args[0][0]
                        assert "--volumes" in call_args


class TestShellCommand:
    """Tests for shell command."""

    def test_shell_interactive(self):
        """Test interactive shell."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_web_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-web-1"
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(shell)

                        assert result.exit_code == 0

    def test_shell_with_command(self):
        """Test shell with single command."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_web_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-web-1"
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(shell, ["-c", "ls -la"])

                        assert result.exit_code == 0


class TestManageCommand:
    """Tests for manage command."""

    def test_manage_with_args(self):
        """Test manage command with Django args."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_web_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-web-1"
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(manage, ["migrate"])

                        assert result.exit_code == 0

    def test_manage_no_args(self):
        """Test manage command without args."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                mock_in_project.return_value = True
                mock_docker.return_value = True

                result = runner.invoke(manage)

                assert result.exit_code == 1
                assert "No Django management command specified" in result.output


class TestLogsCommand:
    """Tests for logs command."""

    def test_logs_all_services(self):
        """Test logs for all services."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(logs)

                        assert result.exit_code == 0

    def test_logs_specific_service(self):
        """Test logs for specific service."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(logs, ["web"])

                        assert result.exit_code == 0
                        # Verify service name was passed
                        call_args = mock_run.call_args[0][0]
                        assert "web" in call_args

    def test_logs_with_follow_flag(self):
        """Test logs command with --follow flag."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(logs, ["--follow"])

                        assert result.exit_code == 0
                        call_args = mock_run.call_args[0][0]
                        assert "--follow" in call_args

    def test_logs_with_tail_flag(self):
        """Test logs command with --tail flag."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(logs, ["--tail", "100"])

                        assert result.exit_code == 0
                        call_args = mock_run.call_args[0][0]
                        assert "--tail" in call_args
                        assert "100" in call_args

    def test_logs_with_timestamps_flag(self):
        """Test logs command with --timestamps flag."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(logs, ["--timestamps"])

                        assert result.exit_code == 0
                        call_args = mock_run.call_args[0][0]
                        assert "--timestamps" in call_args


class TestPsCommand:
    """Tests for ps command."""

    def test_ps_success(self):
        """Test successful ps command."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(ps)

                        assert result.exit_code == 0


class TestErrorHandling:
    """Tests for error handling in commands."""

    def test_up_docker_compose_fails(self):
        """Test up command when docker-compose fails."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.is_port_available"
                ) as mock_port:
                    with patch(
                        "quickscale_cli.commands.development_commands.get_docker_compose_command"
                    ) as mock_cmd:
                        with patch("subprocess.run") as mock_run:
                            mock_in_project.return_value = True
                            mock_docker.return_value = True
                            mock_port.return_value = True
                            mock_cmd.return_value = ["docker-compose"]
                            mock_run.side_effect = subprocess.CalledProcessError(
                                1, "docker-compose"
                            )

                            result = runner.invoke(up)

                            assert result.exit_code == 1
                            assert "Failed to start services" in result.output

    def test_down_docker_compose_fails(self):
        """Test down command when docker-compose fails."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, "docker-compose"
                        )

                        result = runner.invoke(down)

                        assert result.exit_code == 1
                        assert "Failed to stop services" in result.output

    def test_shell_container_not_running(self):
        """Test shell command when container is not running."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_web_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-web-1"
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, "docker"
                        )

                        result = runner.invoke(shell)

                        assert result.exit_code == 1
                        assert "Container not running" in result.output

    def test_manage_container_fails(self):
        """Test manage command when container operation fails."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_web_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-web-1"
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, "docker"
                        )

                        result = runner.invoke(manage, ["migrate"])

                        assert result.exit_code == 1

    def test_logs_docker_compose_fails(self):
        """Test logs command when docker-compose fails."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, "docker-compose"
                        )

                        result = runner.invoke(logs)

                        assert result.exit_code == 1
                        assert "Failed to retrieve logs" in result.output

    def test_ps_docker_compose_fails(self):
        """Test ps command when docker-compose fails."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project"
        ) as mock_in_project:
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running"
            ) as mock_docker:
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command"
                ) as mock_cmd:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_cmd.return_value = ["docker-compose"]
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, "docker-compose"
                        )

                        result = runner.invoke(ps)

                        assert result.exit_code == 1
                        assert "Failed to get service status" in result.output
