"""Tests for development commands."""

from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

from click.testing import CliRunner

from quickscale_cli.commands.development_commands import (
    _load_up_config,
    down,
    logs,
    manage,
    ps,
    shell,
    up,
)


class TestUpCommand:
    """Tests for up command."""

    def _invoke_up_with_patched_steps(self, **overrides):
        """Invoke up with its external steps isolated for error-path tests."""
        from contextlib import ExitStack

        targets = {
            "_validate_theme_preflight_for_up": Mock(),
            "_validate_project_and_docker": Mock(),
            "get_project_config": Mock(return_value=None),
            "_backend_compose_environment": Mock(return_value={"QS_IMAGE": "test"}),
            "_dependencies_changed_since_last_build": Mock(return_value=False),
            "get_port_from_env": Mock(return_value=8000),
            "is_port_available": Mock(return_value=True),
            "_require_docker_compose_command": Mock(return_value=["docker", "compose"]),
            "_run_docker_compose_up": Mock(),
            "_update_last_build_timestamp": Mock(),
            "_run_migrations_after_up": Mock(),
            "_handle_superuser_after_up": Mock(),
        }
        targets.update(overrides)

        with ExitStack() as stack:
            for name, replacement in targets.items():
                stack.enter_context(
                    patch(
                        f"quickscale_cli.commands.development_commands.{name}",
                        replacement,
                    )
                )
            return CliRunner().invoke(up)

    def test_up_preserves_validation_warning_port_and_service_order(self):
        """Theme, validation, warning, port, and services retain their order."""
        events = []
        config = Mock(docker=None)

        def record(name, return_value=None):
            def callback(*args, **kwargs):
                events.append(name)
                return return_value

            return Mock(side_effect=callback)

        with patch(
            "quickscale_cli.commands.development_commands._validate_theme_preflight_for_up",
            record("theme"),
        ):
            with patch(
                "quickscale_cli.commands.development_commands._validate_project_and_docker",
                record("project"),
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.get_project_config",
                    record("config", config),
                ):
                    with patch(
                        "quickscale_cli.commands.development_commands._backend_compose_environment",
                        record("identity", {"QS_IMAGE": "test"}),
                    ):
                        with patch(
                            "quickscale_cli.commands.development_commands._dependencies_changed_since_last_build",
                            record("dependencies", False),
                        ):
                            with patch(
                                "quickscale_cli.commands.development_commands.get_port_from_env",
                                record("port", 8000),
                            ):
                                with patch(
                                    "quickscale_cli.commands.development_commands.is_port_available",
                                    record("port_available", True),
                                ):
                                    with patch(
                                        "quickscale_cli.commands.development_commands._run_up_services",
                                        record("services"),
                                    ) as mock_services:
                                        result = CliRunner().invoke(up)

        assert result.exit_code == 0
        assert events == [
            "theme",
            "project",
            "config",
            "identity",
            "dependencies",
            "port",
            "port_available",
            "services",
        ]
        mock_services.assert_called_once_with(
            config, False, False, {"QS_IMAGE": "test"}
        )

    def test_up_build_flag_overrides_config_default(self):
        """An explicit build flag wins over a false config default."""
        config = Mock(docker=Mock(build=False))

        with patch(
            "quickscale_cli.commands.development_commands.get_project_config",
            return_value=config,
        ):
            assert _load_up_config(True) == (config, True)

    def test_up_uses_config_build_default_when_flag_is_absent(self):
        """The project config controls builds when no explicit flag is given."""
        config = Mock(docker=Mock(build=True))

        with patch(
            "quickscale_cli.commands.development_commands.get_project_config",
            return_value=config,
        ):
            assert _load_up_config(False) == (config, True)

    def test_up_no_cache_keeps_build_arguments_and_timestamp_rule(self):
        """No-cache remains an independent compose option and does not imply timestamping."""
        runner = CliRunner()
        compose_environment = {"QS_IMAGE": "test"}
        with (
            patch(
                "quickscale_cli.commands.development_commands._validate_theme_preflight_for_up"
            ),
            patch(
                "quickscale_cli.commands.development_commands._validate_project_and_docker"
            ),
            patch(
                "quickscale_cli.commands.development_commands.get_project_config",
                return_value=None,
            ),
            patch(
                "quickscale_cli.commands.development_commands._backend_compose_environment",
                return_value=compose_environment,
            ),
            patch(
                "quickscale_cli.commands.development_commands.get_port_from_env",
                return_value=8000,
            ),
            patch(
                "quickscale_cli.commands.development_commands.is_port_available",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.development_commands._dependencies_changed_since_last_build",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.development_commands._require_docker_compose_command",
                return_value=["docker", "compose"],
            ),
            patch(
                "quickscale_cli.commands.development_commands._run_docker_compose_up"
            ) as mock_compose,
            patch(
                "quickscale_cli.commands.development_commands._update_last_build_timestamp"
            ) as mock_timestamp,
            patch(
                "quickscale_cli.commands.development_commands._run_migrations_after_up"
            ),
            patch(
                "quickscale_cli.commands.development_commands._handle_superuser_after_up"
            ),
        ):
            result = runner.invoke(up, ["--no-cache"])

        assert result.exit_code == 0
        mock_compose.assert_called_once_with(
            ["docker", "compose"],
            False,
            True,
            environment=compose_environment,
        )
        mock_timestamp.assert_not_called()

    def test_up_interrupt_exits_130(self):
        """An interrupt during service startup retains the documented exit."""
        result = self._invoke_up_with_patched_steps(
            _run_docker_compose_up=Mock(side_effect=KeyboardInterrupt)
        )

        assert result.exit_code == 130
        assert "Interrupted by user" in result.output

    def test_up_classifies_migration_failure(self):
        """Migration failures retain their dedicated remediation message."""
        error = subprocess.CalledProcessError(
            1,
            ["docker", "exec", "backend", "python", "manage.py", "migrate"],
            stderr="migration output",
        )
        result = self._invoke_up_with_patched_steps(
            _run_migrations_after_up=Mock(side_effect=error)
        )

        assert result.exit_code == 1
        assert "database migration failed" in result.output
        assert "migration output" in result.output

    def test_up_classifies_superuser_failure(self):
        """Superuser failures retain their dedicated remediation message."""
        error = subprocess.CalledProcessError(
            1,
            ["docker", "exec", "backend", "python", "manage.py", "createsuperuser"],
        )
        result = self._invoke_up_with_patched_steps(
            _handle_superuser_after_up=Mock(side_effect=error)
        )

        assert result.exit_code == 1
        assert "superuser creation failed" in result.output

    def test_up_classifies_port_conflict_from_compose_failure(self):
        """Compose port failures retain the port-specific remediation message."""
        error = subprocess.CalledProcessError(
            1,
            ["docker", "compose", "up"],
            stderr="Bind for 0.0.0.0:8000 failed: port is already allocated",
        )
        result = self._invoke_up_with_patched_steps(
            _run_docker_compose_up=Mock(side_effect=error)
        )

        assert result.exit_code == 1
        assert "Port 8000 is already in use" in result.output

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
                        with patch(
                            "quickscale_cli.commands.development_commands.get_backend_container_name"
                        ) as mock_backend:
                            with patch("subprocess.run") as mock_run:
                                mock_in_project.return_value = True
                                mock_docker.return_value = True
                                mock_port.return_value = True
                                mock_cmd.return_value = ["docker", "compose"]
                                mock_backend.return_value = "myproject-backend-1"
                                mock_run.return_value = Mock(returncode=0)

                                result = runner.invoke(up)

                                assert result.exit_code == 0
                                assert "Services started successfully!" in result.output
                                assert "Database migrations applied" in result.output

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

    def test_up_not_in_generated_project_shows_apply_tip(self):
        """Test tip when quickscale.yml exists but project is not generated yet."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("quickscale.yml").write_text(
                "version: '1'\nproject:\n  slug: test\n  package: test\n"
            )

            with patch(
                "quickscale_cli.commands.development_commands.is_in_quickscale_project"
            ) as mock_in_project:
                mock_in_project.return_value = False

                result = runner.invoke(up)

                assert result.exit_code == 1
                assert "Run 'quickscale apply' first" in result.output

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
                        with patch(
                            "quickscale_cli.commands.development_commands.get_backend_container_name"
                        ) as mock_backend:
                            with patch("subprocess.run") as mock_run:
                                mock_in_project.return_value = True
                                mock_docker.return_value = True
                                mock_port.return_value = True
                                mock_cmd.return_value = ["docker", "compose"]
                                mock_backend.return_value = "myproject-backend-1"
                                mock_run.return_value = Mock(returncode=0)

                                result = runner.invoke(up, ["--build"])

                                assert result.exit_code == 0
                                # Verify --build was passed in at least one docker compose call.
                                all_calls = [
                                    call.args[0] for call in mock_run.call_args_list
                                ]
                                assert any(
                                    "--build" in call_args for call_args in all_calls
                                )
                                assert any(
                                    "migrate" in call_args for call_args in all_calls
                                )

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
                        with patch(
                            "quickscale_cli.commands.development_commands.get_backend_container_name"
                        ) as mock_backend:
                            with patch("subprocess.run") as mock_run:
                                mock_in_project.return_value = True
                                mock_docker.return_value = True
                                mock_port.return_value = True
                                mock_cmd.return_value = ["docker", "compose"]
                                mock_backend.return_value = "myproject-backend-1"
                                mock_run.return_value = Mock(returncode=0)

                                result = runner.invoke(up, ["--no-cache"])

                                assert result.exit_code == 0
                                # Verify no-cache is a separate build command; Compose
                                # does not accept --no-cache on its up subcommand.
                                all_calls = [
                                    call.args[0] for call in mock_run.call_args_list
                                ]
                                no_cache_call = next(
                                    call_args
                                    for call_args in all_calls
                                    if "--no-cache" in call_args
                                )
                                up_call = next(
                                    call_args
                                    for call_args in all_calls
                                    if "up" in call_args and "--build" in call_args
                                )
                                assert "build" in no_cache_call
                                assert "up" not in no_cache_call
                                assert "--no-cache" not in up_call
                                assert any(
                                    "migrate" in call_args for call_args in all_calls
                                )


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
                        with patch(
                            "quickscale_cli.commands.development_commands.wait_for_port_release"
                        ) as mock_wait:
                            mock_in_project.return_value = True
                            mock_docker.return_value = True
                            mock_cmd.return_value = ["docker", "compose"]
                            mock_run.return_value = Mock(returncode=0)
                            mock_wait.return_value = True

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
                        with patch(
                            "quickscale_cli.commands.development_commands.wait_for_port_release"
                        ) as mock_wait:
                            mock_in_project.return_value = True
                            mock_docker.return_value = True
                            mock_cmd.return_value = ["docker", "compose"]
                            mock_run.return_value = Mock(returncode=0)
                            mock_wait.return_value = True

                            result = runner.invoke(down, ["--volumes"])

                            assert result.exit_code == 0
                            # Verify --volumes was passed to docker compose.
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
                    "quickscale_cli.commands.development_commands.get_backend_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-backend-1"
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
                    "quickscale_cli.commands.development_commands.get_backend_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-backend-1"
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
                    "quickscale_cli.commands.development_commands.get_backend_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-backend-1"
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
                        mock_cmd.return_value = ["docker", "compose"]
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
                        mock_cmd.return_value = ["docker", "compose"]
                        mock_run.return_value = Mock(returncode=0)

                        result = runner.invoke(logs, ["backend"])

                        assert result.exit_code == 0
                        # Verify service name was passed
                        call_args = mock_run.call_args[0][0]
                        assert "backend" in call_args

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
                        mock_cmd.return_value = ["docker", "compose"]
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
                        mock_cmd.return_value = ["docker", "compose"]
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
                        mock_cmd.return_value = ["docker", "compose"]
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
        """Test up command when docker compose fails."""
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
                            mock_cmd.return_value = ["docker", "compose"]
                            mock_run.side_effect = subprocess.CalledProcessError(
                                1, ["docker", "compose"]
                            )

                            result = runner.invoke(up)

                            assert result.exit_code == 1
                            assert "Failed to start services" in result.output

    def test_down_docker_compose_fails(self):
        """Test down command when docker compose fails."""
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
                        mock_cmd.return_value = ["docker", "compose"]
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, ["docker", "compose"]
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
                    "quickscale_cli.commands.development_commands.get_backend_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-backend-1"
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
                    "quickscale_cli.commands.development_commands.get_backend_container_name"
                ) as mock_container:
                    with patch("subprocess.run") as mock_run:
                        mock_in_project.return_value = True
                        mock_docker.return_value = True
                        mock_container.return_value = "myproject-backend-1"
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, "docker"
                        )

                        result = runner.invoke(manage, ["migrate"])

                        assert result.exit_code == 1

    def test_logs_docker_compose_fails(self):
        """Test logs command when docker compose fails."""
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
                        mock_cmd.return_value = ["docker", "compose"]
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, ["docker", "compose"]
                        )

                        result = runner.invoke(logs)

                        assert result.exit_code == 1
                        assert "Failed to retrieve logs" in result.output

    def test_ps_docker_compose_fails(self):
        """Test ps command when docker compose fails."""
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
                        mock_cmd.return_value = ["docker", "compose"]
                        mock_run.side_effect = subprocess.CalledProcessError(
                            1, ["docker", "compose"]
                        )

                        result = runner.invoke(ps)

                        assert result.exit_code == 1
                        assert "Failed to get service status" in result.output
