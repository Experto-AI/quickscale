"""Tests for leftover Compose volume detection and its apply/up remediation.

Regression context: `quickscale apply` on a freshly generated project silently
attached to a Docker volume left behind by an earlier project of the same
directory name.  The stale database carried that project's migration history,
so `migrate` aborted with ``InconsistentMigrationHistory: Migration
admin.0001_initial is applied before its dependency
quickscale_modules_auth.0001_initial`` and nothing in the output pointed at the
real cause.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from quickscale_cli.utils.docker_utils import (
    compose_declared_volume_names,
    compose_project_name,
    find_stale_project_volumes,
    list_existing_volumes,
    remove_volumes,
)

COMPOSE_FILE = """\
services:
  db:
    image: postgres:18-alpine
    volumes:
      - postgres_data:/var/lib/postgresql
  backend:
    build: .
    volumes:
      - static_volume:/app/staticfiles
      - ./local:/app/local

volumes:
  postgres_data:
  static_volume:
  media_volume:
    driver: local
"""


def _project(tmp_path: Path, name: str = "test87") -> Path:
    project = tmp_path / name
    project.mkdir()
    (project / "docker-compose.yml").write_text(COMPOSE_FILE)
    return project


class TestComposeProjectName:
    """Compose's project-name normalization."""

    @pytest.mark.parametrize(
        "directory,expected",
        [
            ("test87", "test87"),
            ("Test87", "test87"),
            ("my.project", "my_project"),
            ("my project", "my_project"),
            ("_leading", "leading"),
            ("keeps-dash_and_underscore", "keeps-dash_and_underscore"),
        ],
    )
    def test_normalizes_directory_name(self, tmp_path, directory, expected):
        path = tmp_path / directory
        path.mkdir()
        assert compose_project_name(path) == expected


class TestComposeDeclaredVolumeNames:
    """Top-level `volumes:` parsing."""

    def test_reads_only_top_level_named_volumes(self, tmp_path):
        project = _project(tmp_path)
        assert compose_declared_volume_names(project / "docker-compose.yml") == [
            "postgres_data",
            "static_volume",
            "media_volume",
        ]

    def test_missing_file_yields_no_volumes(self, tmp_path):
        assert compose_declared_volume_names(tmp_path / "nope.yml") == []

    def test_compose_without_volumes_block_yields_no_volumes(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services:\n  db:\n    image: postgres:18-alpine\n")
        assert compose_declared_volume_names(compose) == []


class TestFindStaleProjectVolumes:
    """Detection of pre-existing volumes for a project directory."""

    def test_reports_only_volumes_that_already_exist(self, tmp_path, monkeypatch):
        project = _project(tmp_path)
        monkeypatch.setattr(
            "quickscale_cli.utils.docker_utils.list_existing_volumes",
            lambda names: [n for n in names if n != "test87_media_volume"],
        )

        assert find_stale_project_volumes(project) == [
            "test87_postgres_data",
            "test87_static_volume",
        ]

    def test_clean_machine_reports_nothing(self, tmp_path, monkeypatch):
        project = _project(tmp_path)
        monkeypatch.setattr(
            "quickscale_cli.utils.docker_utils.list_existing_volumes",
            lambda names: [],
        )
        assert find_stale_project_volumes(project) == []

    def test_project_without_compose_file_reports_nothing(self, tmp_path):
        project = tmp_path / "no-compose"
        project.mkdir()
        assert find_stale_project_volumes(project) == []


class TestListExistingVolumes:
    """`docker volume ls` interpretation."""

    def test_intersects_docker_output_with_candidates(self, monkeypatch):
        monkeypatch.setattr(
            "quickscale_cli.utils.docker_utils.subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args, 0, stdout="other\ntest87_postgres_data\n", stderr=""
            ),
        )
        assert list_existing_volumes(["test87_postgres_data", "test87_media"]) == [
            "test87_postgres_data"
        ]

    def test_docker_unavailable_reports_nothing(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise FileNotFoundError("docker")

        monkeypatch.setattr("quickscale_cli.utils.docker_utils.subprocess.run", _boom)
        assert list_existing_volumes(["test87_postgres_data"]) == []

    def test_no_candidates_skips_docker_entirely(self, monkeypatch):
        def _fail(*args, **kwargs):  # pragma: no cover - must not be called
            raise AssertionError("docker must not be invoked")

        monkeypatch.setattr("quickscale_cli.utils.docker_utils.subprocess.run", _fail)
        assert list_existing_volumes([]) == []


class TestRemoveVolumes:
    """Volume removal reporting."""

    def test_splits_removed_and_failed(self, monkeypatch):
        def _run(cmd, **kwargs):
            code = 0 if cmd[-1] == "ok_volume" else 1
            return subprocess.CompletedProcess(cmd, code, stdout="", stderr="in use")

        monkeypatch.setattr("quickscale_cli.utils.docker_utils.subprocess.run", _run)
        removed, failed = remove_volumes(["ok_volume", "busy_volume"])
        assert removed == ["ok_volume"]
        assert failed == ["busy_volume"]

    def test_docker_failure_counts_as_failed(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="docker", timeout=30)

        monkeypatch.setattr("quickscale_cli.utils.docker_utils.subprocess.run", _boom)
        removed, failed = remove_volumes(["stuck_volume"])
        assert removed == []
        assert failed == ["stuck_volume"]


class TestUpMigrationFailureRemediation:
    """`quickscale up` explains an inconsistent migration history."""

    INCONSISTENT_STDERR = (
        "django.db.migrations.exceptions.InconsistentMigrationHistory: Migration "
        "admin.0001_initial is applied before its dependency "
        "quickscale_modules_auth.0001_initial on database 'default'.\n"
    )

    def test_detects_inconsistent_migration_history_in_either_stream(self):
        from quickscale_cli.commands.development_commands import (
            _is_inconsistent_migration_history,
        )

        on_stderr = subprocess.CalledProcessError(
            1, ["docker", "exec", "c", "python", "manage.py", "migrate"]
        )
        on_stderr.stderr = self.INCONSISTENT_STDERR
        on_stderr.stdout = ""
        assert _is_inconsistent_migration_history(on_stderr) is True

        on_stdout = subprocess.CalledProcessError(1, ["migrate"])
        on_stdout.stderr = ""
        on_stdout.stdout = self.INCONSISTENT_STDERR
        assert _is_inconsistent_migration_history(on_stdout) is True

        unrelated = subprocess.CalledProcessError(1, ["migrate"])
        unrelated.stderr = "OperationalError: could not connect\n"
        unrelated.stdout = ""
        assert _is_inconsistent_migration_history(unrelated) is False

    def test_up_points_at_the_leftover_volume(self, tmp_path, monkeypatch, capsys):
        """The failure names the stale volumes instead of the generic tip."""
        from click.testing import CliRunner

        from quickscale_cli.commands.development_commands import up

        project = _project(tmp_path)
        monkeypatch.chdir(project)

        migrate_error = subprocess.CalledProcessError(
            1, ["docker", "exec", "c", "python", "manage.py", "migrate"]
        )
        migrate_error.stderr = self.INCONSISTENT_STDERR
        migrate_error.stdout = ""

        module = "quickscale_cli.commands.development_commands"
        monkeypatch.setattr(f"{module}._validate_theme_preflight_for_up", lambda: None)
        monkeypatch.setattr(f"{module}._validate_project_and_docker", lambda: True)
        monkeypatch.setattr(f"{module}.get_project_config", lambda strict=True: None)
        monkeypatch.setattr(f"{module}.get_port_from_env", lambda: 8000)
        monkeypatch.setattr(f"{module}.is_port_available", lambda port: True)
        monkeypatch.setattr(
            f"{module}._require_docker_compose_command", lambda: ["docker", "compose"]
        )
        monkeypatch.setattr(
            f"{module}._run_docker_compose_up", lambda cmd, build, no_cache: None
        )

        def _raise_migrate() -> None:
            raise migrate_error

        monkeypatch.setattr(f"{module}._run_migrations_after_up", _raise_migrate)
        monkeypatch.setattr(
            f"{module}.find_stale_project_volumes",
            lambda path: ["test87_postgres_data"],
        )

        result = CliRunner().invoke(up)

        assert result.exit_code == 1
        assert "database migration failed" in result.output
        assert "test87_postgres_data" in result.output
        assert "docker volume rm" in result.output
        # The generic tip must not be the only guidance offered.
        assert "database predates the modules embedded" in result.output


class TestApplyStaleVolumePreflight:
    """`quickscale apply` refuses to start a new project on an old database."""

    def _patch_apply(self, monkeypatch, stale, removed=None, failed=None):
        module = "quickscale_cli.commands.apply_command"
        # The suite-wide destructive-confirm bypass would skip the prompt.
        monkeypatch.setattr(f"{module}._AF5_DESTRUCTIVE_CONFIRM_BYPASS", False)
        monkeypatch.setattr(f"{module}.find_stale_project_volumes", lambda path: stale)
        self.compose_down_calls = []
        monkeypatch.setattr(
            f"{module}.compose_down",
            lambda path: self.compose_down_calls.append(path) or True,
        )
        monkeypatch.setattr(
            f"{module}.remove_volumes",
            lambda names: (removed if removed is not None else names, failed or []),
        )
        return module

    def test_bypass_mode_warns_without_prompting(self, tmp_path, monkeypatch, capsys):
        """Non-interactive test mode reports the leftovers but never deletes."""
        import click

        from quickscale_cli.commands.apply_command import (
            _preflight_stale_docker_volumes,
        )

        module = self._patch_apply(monkeypatch, ["test87_postgres_data"])
        monkeypatch.setattr(f"{module}._AF5_DESTRUCTIVE_CONFIRM_BYPASS", True)

        def _no_prompt(*args, **kwargs):  # pragma: no cover - must not be called
            raise AssertionError("bypass mode must not prompt")

        monkeypatch.setattr(click, "confirm", _no_prompt)

        assert _preflight_stale_docker_volumes(tmp_path) is True
        assert "Leftover Docker volumes" in capsys.readouterr().out

    def test_clean_machine_passes_silently(self, tmp_path, monkeypatch, capsys):
        from quickscale_cli.commands.apply_command import (
            _preflight_stale_docker_volumes,
        )

        self._patch_apply(monkeypatch, [])
        assert _preflight_stale_docker_volumes(tmp_path) is True
        assert capsys.readouterr().out == ""

    def test_removes_volumes_when_confirmed(self, tmp_path, monkeypatch, capsys):
        import click

        from quickscale_cli.commands.apply_command import (
            _preflight_stale_docker_volumes,
        )

        self._patch_apply(monkeypatch, ["test87_postgres_data"])
        monkeypatch.setattr(click, "confirm", lambda *args, **kwargs: True)

        assert _preflight_stale_docker_volumes(tmp_path) is True
        output = capsys.readouterr().out
        assert "Leftover Docker volumes" in output
        assert "Removed volume: test87_postgres_data" in output

    def test_declining_stops_the_apply_with_instructions(
        self, tmp_path, monkeypatch, capsys
    ):
        import click

        from quickscale_cli.commands.apply_command import (
            _preflight_stale_docker_volumes,
        )

        self._patch_apply(monkeypatch, ["test87_postgres_data", "test87_media_volume"])
        monkeypatch.setattr(click, "confirm", lambda *args, **kwargs: False)

        assert _preflight_stale_docker_volumes(tmp_path) is False
        output = capsys.readouterr().out
        assert "InconsistentMigrationHistory" in output
        assert "docker volume rm test87_postgres_data test87_media_volume" in output

    def test_failed_removal_stops_the_apply(self, tmp_path, monkeypatch, capsys):
        import click

        from quickscale_cli.commands.apply_command import (
            _preflight_stale_docker_volumes,
        )

        self._patch_apply(
            monkeypatch,
            ["test87_postgres_data"],
            removed=[],
            failed=["test87_postgres_data"],
        )
        monkeypatch.setattr(click, "confirm", lambda *args, **kwargs: True)

        assert _preflight_stale_docker_volumes(tmp_path) is False
        captured = capsys.readouterr()
        assert "Could not remove" in captured.out + captured.err


class TestStaleVolumeCheckScope:
    """Which applies run the stale-volume preflight."""

    def _ctx(self, *, had_existing_state: bool, existing_state):
        from quickscale_cli.commands.apply_command import _should_check_stale_volumes

        class _Ctx:
            pass

        ctx = _Ctx()
        ctx.had_existing_state = had_existing_state
        ctx.existing_state = existing_state
        return _should_check_stale_volumes(ctx)

    def test_new_project_is_checked(self):
        assert self._ctx(had_existing_state=False, existing_state=None) is True

    def test_resumed_new_project_is_still_checked(self):
        """A recovery ledger populates existing_state but is not a real project state."""
        assert self._ctx(had_existing_state=False, existing_state=object()) is True

    def test_established_project_is_never_checked(self):
        """An existing project's volumes hold real data and must be left alone."""
        assert self._ctx(had_existing_state=True, existing_state=object()) is False


class TestComposeDown:
    """Releasing containers that hold the leftover volumes."""

    def test_preflight_releases_containers_before_removing(
        self, tmp_path, monkeypatch, capsys
    ):
        """`docker compose down` runs first, or removal fails on in-use volumes."""
        import click

        from quickscale_cli.commands.apply_command import (
            _preflight_stale_docker_volumes,
        )

        helper = TestApplyStaleVolumePreflight()
        helper._patch_apply(monkeypatch, ["test87_postgres_data"])
        monkeypatch.setattr(click, "confirm", lambda *args, **kwargs: True)

        assert _preflight_stale_docker_volumes(tmp_path) is True
        assert helper.compose_down_calls == [tmp_path]

    def test_compose_down_reports_failure(self, tmp_path, monkeypatch):
        from quickscale_cli.utils import docker_utils

        monkeypatch.setattr(
            docker_utils, "get_docker_compose_command", lambda: ["docker", "compose"]
        )
        monkeypatch.setattr(
            docker_utils.subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, "", "boom"),
        )
        assert docker_utils.compose_down(tmp_path) is False

    def test_compose_down_without_plugin_is_not_fatal(self, tmp_path, monkeypatch):
        from quickscale_cli.utils import docker_utils

        def _missing():
            raise docker_utils.DockerComposePluginRequiredError("no plugin")

        monkeypatch.setattr(docker_utils, "get_docker_compose_command", _missing)
        assert docker_utils.compose_down(tmp_path) is False
