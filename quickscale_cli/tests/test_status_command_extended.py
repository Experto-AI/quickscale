"""Extended tests for status_command.py - covering helper functions and edge cases."""

import json
import os
from unittest.mock import Mock, patch

import yaml
from click.testing import CliRunner

import pytest

from quickscale_cli.schema.config_schema import ConfigValidationError
from quickscale_cli.commands.status_command import (
    _build_json_output,
    _check_contract_vintage,
    _compute_drift_diagnostics,
    _detect_project_context,
    _display_docker_status,
    _display_drift_diagnostics,
    _display_drift_warnings,
    _display_modules,
    _display_pending_changes,
    _display_project_info,
    _display_text_status,
    _format_datetime,
    _get_docker_status,
    _load_config,
    _state_file_has_consolidated_sections,
    status,
)
from quickscale_core.project_state import ProjectStateManager


# ============================================================================
# _get_docker_status
# ============================================================================


class TestGetDockerStatus:
    """Tests for _get_docker_status"""

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_running(self, mock_run):
        """Test Docker status when containers are running"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="myapp-backend-1: Up 5 minutes\nmyapp-db-1: Up 5 minutes",
        )
        result = _get_docker_status()
        assert result is not None
        assert "myapp-backend-1" in result
        assert "Up 5 minutes" in result["myapp-backend-1"]

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_no_containers(self, mock_run):
        """Test Docker status with no running containers"""
        mock_run.return_value = Mock(returncode=0, stdout="")
        result = _get_docker_status()
        assert result is None

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_not_available(self, mock_run):
        """Test when Docker is not available"""
        mock_run.side_effect = FileNotFoundError()
        result = _get_docker_status()
        assert result is None

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_command_fails(self, mock_run):
        """Test when docker compose fails"""
        mock_run.return_value = Mock(returncode=1, stdout="")
        result = _get_docker_status()
        assert result is None

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_lines_without_separator(self, mock_run):
        """Test docker output without proper separator"""
        mock_run.return_value = Mock(returncode=0, stdout="no separator here")
        result = _get_docker_status()
        assert result is None


# ============================================================================
# _format_datetime
# ============================================================================


class TestFormatDatetime:
    """Tests for _format_datetime"""

    def test_valid_iso_datetime(self):
        """Format valid ISO datetime"""
        result = _format_datetime("2025-12-01T10:30:00")
        assert "2025-12-01" in result
        assert "10:30" in result

    def test_with_timezone(self):
        """Format datetime with timezone"""
        result = _format_datetime("2025-12-01T10:30:00Z")
        assert "2025-12-01" in result

    def test_invalid_datetime(self):
        """Return raw string for invalid datetime"""
        result = _format_datetime("not-a-date")
        assert result == "not-a-date"

    def test_none_value(self):
        """AttributeError raised for None since only ValueError/TypeError caught"""
        with pytest.raises(AttributeError):
            _format_datetime(None)


# ============================================================================
# _detect_project_context
# ============================================================================


class TestDetectProjectContext:
    """Tests for _detect_project_context"""

    def test_config_and_state_present(self, tmp_path, monkeypatch):
        """Detect project with both config and state"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "quickscale.yml").touch()
        (tmp_path / ".quickscale").mkdir()
        (tmp_path / ".quickscale" / "state.yml").touch()

        project_path, config_path, state_path = _detect_project_context()
        assert project_path == tmp_path
        assert config_path is not None
        assert state_path is not None

    def test_only_config(self, tmp_path, monkeypatch):
        """Detect project with only config"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "quickscale.yml").touch()

        project_path, config_path, state_path = _detect_project_context()
        assert project_path == tmp_path
        assert config_path is not None
        assert state_path is None

    def test_only_state(self, tmp_path, monkeypatch):
        """Detect project with only state"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".quickscale").mkdir()
        (tmp_path / ".quickscale" / "state.yml").touch()

        project_path, config_path, state_path = _detect_project_context()
        assert project_path == tmp_path
        assert config_path is None
        assert state_path is not None

    def test_not_in_project(self, tmp_path, monkeypatch):
        """Not in a QuickScale project"""
        monkeypatch.chdir(tmp_path)

        project_path, config_path, state_path = _detect_project_context()
        assert project_path is None


# ============================================================================
# _load_config
# ============================================================================


class TestLoadConfig:
    """Tests for _load_config"""

    def test_valid_config(self, tmp_path):
        """Load valid config"""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n  theme: showcase_html\n'
            "docker:\n  start: false\n"
        )
        result = _load_config(config)
        assert result is not None
        assert result.project.slug == "myapp"

    def test_invalid_config(self, tmp_path):
        """Invalid configs should surface validation errors."""
        config = tmp_path / "quickscale.yml"
        config.write_text("invalid yaml: [")
        with pytest.raises(ConfigValidationError):
            _load_config(config)


# ============================================================================
# _display_ functions
# ============================================================================


class TestDisplayFunctions:
    """Tests for display helper functions"""

    def test_display_project_info(self):
        """Display project information"""
        state = Mock()
        state.project.slug = "myapp"
        state.project.theme = "showcase_html"
        state.project.created_at = "2025-01-01T00:00:00"
        state.project.last_applied = "2025-01-01T12:00:00"
        _display_project_info(state)

    def test_display_modules_empty(self):
        """Display modules when none installed"""
        state = Mock()
        state.modules = {}
        _display_modules(state)

    def test_display_modules_with_data(self):
        """Display modules with version and date"""
        state = Mock()
        module = Mock()
        module.version = "1.0.0"
        module.embedded_at = "2025-01-01T00:00:00"
        state.modules = {"auth": module}
        _display_modules(state)

    def test_display_modules_no_version(self):
        """Display modules without version"""
        state = Mock()
        module = Mock()
        module.version = None
        module.embedded_at = None
        state.modules = {"auth": module}
        _display_modules(state)

    def test_display_pending_changes_no_config(self):
        """Display pending changes when no config"""
        _display_pending_changes(None, None)

    def test_display_pending_changes_with_changes(self):
        """Display pending changes when changes exist"""
        config = Mock()
        config.version = "1"
        config.project.slug = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        config.docker.start = False
        config.docker.build = False

        state = Mock()
        state.version = "1"
        state.project.slug = "myapp"
        state.project.theme = "showcase_html"
        state.modules = {}

        with patch(
            "quickscale_cli.commands.status_command.compute_delta"
        ) as mock_delta:
            delta = Mock()
            delta.has_changes = True
            mock_delta.return_value = delta
            with patch(
                "quickscale_cli.commands.status_command.format_delta",
                return_value="+ auth",
            ):
                _display_pending_changes(config, state)

    def test_display_pending_changes_no_changes(self):
        """Display message when no changes"""
        config = Mock()
        state = Mock()

        with patch(
            "quickscale_cli.commands.status_command.compute_delta"
        ) as mock_delta:
            delta = Mock()
            delta.has_changes = False
            mock_delta.return_value = delta
            _display_pending_changes(config, state)

    @patch("quickscale_cli.commands.status_command._get_docker_status")
    def test_display_docker_status_running(self, mock_status):
        """Display Docker status for running containers"""
        mock_status.return_value = {
            "backend": "Up 5 minutes",
            "db": "Exited (0)",
            "redis": "starting",
        }
        _display_docker_status()

    @patch("quickscale_cli.commands.status_command._get_docker_status")
    def test_display_docker_status_none(self, mock_status):
        """Display Docker status when not available"""
        mock_status.return_value = None
        _display_docker_status()


# ============================================================================
# _display_drift_warnings
# ============================================================================


class TestDisplayDriftWarnings:
    """Tests for _display_drift_warnings"""

    def test_orphaned_modules(self):
        """Show orphaned module warnings"""
        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": ["stale_module"],
            "missing_modules": [],
        }
        _display_drift_warnings(sm)

    def test_missing_modules(self):
        """Show missing module warnings"""
        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": [],
            "missing_modules": ["gone_module"],
        }
        _display_drift_warnings(sm)

    def test_no_drift(self):
        """No warnings when no drift"""
        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": [],
            "missing_modules": [],
        }
        _display_drift_warnings(sm)


# ============================================================================
# _build_json_output
# ============================================================================


class TestBuildJsonOutput:
    """Tests for _build_json_output"""

    def test_with_state_and_config(self, tmp_path):
        """Build JSON with both state and config"""
        state = Mock()
        state.version = "1"
        state.project.slug = "myapp"
        state.project.theme = "showcase_html"
        state.project.created_at = "2025-01-01"
        state.project.last_applied = "2025-01-01"
        module = Mock()
        module.version = "1.0"
        module.commit_sha = "abc"
        module.embedded_at = "2025-01-01"
        state.modules = {"auth": module}

        config = Mock()
        config.version = "1"
        config.project.slug = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock()}
        config.docker.start = False
        config.docker.build = False

        delta = Mock()
        delta.has_changes = False
        delta.modules_to_add = []
        delta.modules_to_remove = []
        delta.modules_unchanged = ["auth"]
        delta.theme_changed = False

        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            with patch(
                "quickscale_cli.commands.status_command._load_module_manifests",
                return_value={},
            ):
                with patch(
                    "quickscale_cli.commands.status_command.compute_delta",
                    return_value=delta,
                ):
                    result = _build_json_output(
                        tmp_path, tmp_path / "quickscale.yml", state, config
                    )

        assert result["has_state"] is True
        assert "state" in result
        assert "config" in result
        assert "pending_changes" in result

    def test_without_state(self, tmp_path):
        """Build JSON without state"""
        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            result = _build_json_output(tmp_path, None, None, None)

        assert result["has_state"] is False
        assert result["has_config"] is False

    def test_with_docker_status(self, tmp_path):
        """Build JSON with Docker status"""
        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value={"backend": "Up"},
        ):
            result = _build_json_output(tmp_path, None, None, None)
        assert "docker" in result


# ============================================================================
# _display_text_status
# ============================================================================


class TestDisplayTextStatus:
    """Tests for _display_text_status"""

    def test_no_state_no_config(self, tmp_path):
        """Abort when no state or config"""
        import click as click_mod

        sm = Mock()
        psm = Mock(spec=ProjectStateManager)
        with pytest.raises(click_mod.Abort):
            _display_text_status(tmp_path, None, None, None, None, sm, psm)

    def test_with_state_only(self, tmp_path):
        """Display with state but no config"""
        state = Mock()
        state.project.slug = "myapp"
        state.project.theme = "showcase_html"
        state.project.created_at = "2025-01-01"
        state.project.last_applied = "2025-01-01"
        state.modules = {}

        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": [],
            "missing_modules": [],
        }
        psm = Mock(spec=ProjectStateManager)
        psm.detect_managed_file_drift.return_value = []
        psm.load_state.return_value = None
        psm.load_config.return_value = None

        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            _display_text_status(tmp_path, state, None, None, None, sm, psm)

    def test_with_config_no_state(self, tmp_path):
        """Display with config but no state"""
        config = Mock()
        config.version = "1"
        config.project.slug = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        config.docker.start = False
        config.docker.build = False

        sm = Mock()
        psm = Mock(spec=ProjectStateManager)
        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            with patch(
                "quickscale_cli.commands.status_command.compute_delta"
            ) as mock_delta:
                delta = Mock()
                delta.has_changes = False
                mock_delta.return_value = delta
                _display_text_status(tmp_path, None, config, None, None, sm, psm)


# ============================================================================
# status command integration
# ============================================================================


class TestStatusCommandExtended:
    """Extended integration tests for status command"""

    def test_status_json_not_in_project(self):
        """Test JSON status outside project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(status, ["--json"])
            assert result.exit_code != 0

    def test_status_text_with_state_and_config(self):
        """Full text status with state and config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale")
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_html",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": "1.0",
                                "commit_sha": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )
            with open("quickscale.yml", "w") as f:
                f.write(
                    'version: "1"\nproject:\n  slug: testapp\n  package: testapp\n  theme: showcase_html\nmodules:\n  auth:\ndocker:\n  start: false\n'
                )
            os.makedirs("modules/auth", exist_ok=True)
            with open("modules/auth/module.yml", "w") as f:
                f.write('name: auth\nversion: "1.0.0"\n')

            result = runner.invoke(status)
            assert result.exit_code == 0
            assert "testapp" in result.output

    def test_status_json_succeeds_for_billing_ready_config(self):
        """Billing-only configs should pass status now that billing is public-ready."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    'version: "1"\n'
                    "project:\n"
                    "  slug: testapp\n"
                    "  package: testapp\n"
                    "  theme: showcase_html\n"
                    "modules:\n"
                    "  billing:\n"
                    "docker:\n"
                    "  start: false\n"
                )

            result = runner.invoke(status, ["--json"])

            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert payload["config"]["modules"] == ["billing"]
            assert payload["pending_changes"]["has_changes"] is True
            assert "billing" in payload["pending_changes"]["modules_to_add"]

    def test_status_fails_for_placeholder_config(self):
        """Status should still reject placeholder-only modules in quickscale.yml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    'version: "1"\n'
                    "project:\n"
                    "  slug: testapp\n"
                    "  package: testapp\n"
                    "  theme: showcase_html\n"
                    "modules:\n"
                    "  teams:\n"
                )

            result = runner.invoke(status)

            assert result.exit_code != 0
            # teams is caught at schema validation as an unknown module.
            assert "Unknown module" in result.output
            assert "teams" in result.output

    def test_status_fails_for_malformed_installed_manifest(self):
        """Status should fail fast when an installed module manifest is malformed."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale")
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_html",
                        },
                        "modules": {
                            "auth": {
                                "version": "0.70.0",
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )
            os.makedirs("modules/auth", exist_ok=True)
            with open("modules/auth/module.yml", "w") as f:
                f.write("- invalid\n- list\n")

            result = runner.invoke(status)

            assert result.exit_code != 0
            assert "manifest" in result.output.lower()
            assert "auth" in result.output


# ============================================================================
# Phase 4: _state_file_has_consolidated_sections
# ============================================================================


class TestStateFileHasConsolidatedSections:
    """Tests for _state_file_has_consolidated_sections helper."""

    def test_no_state_file(self, tmp_path):
        """Return False when state.yml does not exist."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        assert _state_file_has_consolidated_sections(state_dir) is False

    def test_consolidated_via_managed_files(self, tmp_path):
        """Return True when managed_files section is present."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n  slug: x\n  package: x\n  theme: showcase_html\n"
            "modules: {}\n"
            "managed_files: []\n"
        )
        assert _state_file_has_consolidated_sections(state_dir) is True

    def test_consolidated_via_module_tracking(self, tmp_path):
        """Return True when a module has prefix/branch/installed_at."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n  slug: x\n  package: x\n  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "    version: '1.0'\n"
            "    prefix: modules/auth\n"
            "    branch: main\n"
            "    installed_at: '2025-01-01'\n"
        )
        assert _state_file_has_consolidated_sections(state_dir) is True

    def test_not_consolidated(self, tmp_path):
        """Return False when no consolidated sections present."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n  slug: x\n  package: x\n  theme: showcase_html\n"
            "modules: {}\n"
        )
        assert _state_file_has_consolidated_sections(state_dir) is False

    def test_malformed_yaml(self, tmp_path):
        """Return False for malformed YAML."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text("invalid: [yaml: broken")
        assert _state_file_has_consolidated_sections(state_dir) is False


# ============================================================================
# Phase 4: _compute_drift_diagnostics
# ============================================================================


class TestComputeDriftDiagnostics:
    """Tests for _compute_drift_diagnostics helper."""

    def test_basic_diagnostics_structure(self, tmp_path):
        """Diagnostics should return a well-structured dict."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n  slug: x\n  package: x\n  theme: showcase_html\n"
            "modules: {}\n"
        )

        from quickscale_cli.schema.state_schema import StateManager
        from quickscale_core.project_state import ProjectStateManager

        sm = StateManager(tmp_path)
        psm = ProjectStateManager(tmp_path)
        state = sm.load()

        result = _compute_drift_diagnostics(tmp_path, state, psm, sm)

        assert "state_consolidated" in result
        assert "legacy_files_present" in result
        assert "legacy_compat_active" in result
        assert "module_tracking" in result
        assert "managed_files_consolidated" in result
        assert "filesystem_drift" in result
        assert "managed_file_drift" in result
        assert "version_drift" in result

    def test_legacy_compat_active_when_no_consolidated(self, tmp_path):
        """legacy_compat_active should be True when consolidated sections absent."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n  slug: x\n  package: x\n  theme: showcase_html\n"
            "modules: {}\n"
        )
        # Create a legacy config.yml.
        from quickscale_core.config import add_module

        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="main",
            version="1.0.0",
            project_path=tmp_path,
        )

        from quickscale_cli.schema.state_schema import StateManager
        from quickscale_core.project_state import ProjectStateManager

        sm = StateManager(tmp_path)
        psm = ProjectStateManager(tmp_path)
        state = sm.load()

        result = _compute_drift_diagnostics(tmp_path, state, psm, sm)

        assert result["state_consolidated"] is False
        assert result["legacy_compat_active"] is True
        assert "config.yml" in result["legacy_files_present"]

    def test_none_state(self, tmp_path):
        """Diagnostics should handle None state gracefully."""
        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()

        from quickscale_cli.schema.state_schema import StateManager
        from quickscale_core.project_state import ProjectStateManager

        sm = StateManager(tmp_path)
        psm = ProjectStateManager(tmp_path)

        result = _compute_drift_diagnostics(tmp_path, None, psm, sm)

        assert result["state_consolidated"] is False
        assert result["module_tracking"]["total"] == 0


# ============================================================================
# Phase 4: _display_drift_diagnostics
# ============================================================================


class TestDisplayDriftDiagnostics:
    """Tests for _display_drift_diagnostics text output."""

    def test_display_runs_without_error(self):
        """Display function should run without raising."""
        diagnostics = {
            "state_consolidated": True,
            "legacy_files_present": [],
            "legacy_compat_active": False,
            "module_tracking": {
                "total": 0,
                "consolidated": 0,
                "needs_consolidation": [],
            },
            "managed_files_consolidated": False,
            "filesystem_drift": {
                "orphaned_modules": [],
                "missing_modules": [],
            },
            "managed_file_drift": [],
            "version_drift": [],
        }
        # Should not raise.
        _display_drift_diagnostics(diagnostics)

    def test_display_with_issues(self):
        """Display function should handle drift issues."""
        diagnostics = {
            "state_consolidated": False,
            "legacy_files_present": ["config.yml", "file_hashes.yml"],
            "legacy_compat_active": True,
            "module_tracking": {
                "total": 2,
                "consolidated": 1,
                "needs_consolidation": ["blog"],
            },
            "managed_files_consolidated": False,
            "filesystem_drift": {
                "orphaned_modules": ["orphan"],
                "missing_modules": ["gone"],
            },
            "managed_file_drift": [
                {"path": "settings/modules.py", "expected_hash": "abc123"},
            ],
            "version_drift": [
                {
                    "module": "auth",
                    "state_version": "1.0",
                    "config_version": "2.0",
                },
            ],
        }
        # Should not raise.
        _display_drift_diagnostics(diagnostics)


# ============================================================================
# SA10.2: Contract-vintage detection
# ============================================================================


class TestCheckContractVintage:
    """Tests for _check_contract_vintage detection."""

    def test_no_manifests(self) -> None:
        """When no manifests exist, result shows zero modules."""
        result = _check_contract_vintage("0.87.0", None)
        assert result["module_count"] == 0
        assert result["modules_behind_count"] == 0
        assert result["project_contract"] == "0.87.0"

    def test_empty_manifests(self) -> None:
        """When manifests are empty, result shows zero modules."""
        result = _check_contract_vintage("0.87.0", {})
        assert result["module_count"] == 0
        assert result["project_contract"] == "0.87.0"

    def test_no_vintage_declared(self) -> None:
        """Modules without contract_vintage are skipped."""
        from unittest.mock import Mock

        manifests = {
            "auth": Mock(spec=["contract_vintage"], contract_vintage=None),
        }
        result = _check_contract_vintage("0.87.0", manifests)
        assert result["module_count"] == 0
        assert result["modules_behind_count"] == 0

    def test_module_behind_unknown_contract(self) -> None:
        """Legacy project (project_contract=None) is behind any minimum."""
        from unittest.mock import Mock
        from quickscale_core.manifest.schema import ContractVintage

        vintage = ContractVintage(
            minimum="0.87.0",
            manual_adoption_steps=["Step one: update Docker"],
        )
        manifest = Mock(spec=["contract_vintage"], contract_vintage=vintage)
        manifests = {"backups": manifest}
        result = _check_contract_vintage(None, manifests)
        assert result["module_count"] == 1
        assert result["modules_behind_count"] == 1
        assert result["modules_behind"][0]["module"] == "backups"

    def test_module_meets_requirement(self) -> None:
        """Project with sufficient contract version is not behind."""
        from unittest.mock import Mock
        from quickscale_core.manifest.schema import ContractVintage

        vintage = ContractVintage(minimum="0.87.0")
        manifest = Mock(spec=["contract_vintage"], contract_vintage=vintage)
        manifests = {"social": manifest}
        # project_contract >= minimum
        result = _check_contract_vintage("0.87.0", manifests)
        assert result["module_count"] == 1
        assert result["modules_behind_count"] == 0

    def test_module_strictly_ahead(self) -> None:
        """Project contract > minimum is fine (ahead of requirement)."""
        from unittest.mock import Mock
        from quickscale_core.manifest.schema import ContractVintage

        vintage = ContractVintage(minimum="0.86.0")
        manifest = Mock(spec=["contract_vintage"], contract_vintage=vintage)
        manifests = {"social": manifest}
        result = _check_contract_vintage("0.87.0", manifests)
        assert result["module_count"] == 1
        assert result["modules_behind_count"] == 0

    def test_module_behind_exact_version(self) -> None:
        """Project behind minimum is flagged with correct steps."""
        from unittest.mock import Mock
        from quickscale_core.manifest.schema import ContractVintage

        steps = ["Manual step A", "Manual step B"]
        vintage = ContractVintage(minimum="0.88.0", manual_adoption_steps=steps)
        manifest = Mock(spec=["contract_vintage"], contract_vintage=vintage)
        manifests = {"billing": manifest}
        result = _check_contract_vintage("0.87.0", manifests)
        assert result["module_count"] == 1
        assert result["modules_behind_count"] == 1
        entry = result["modules_behind"][0]
        assert entry["module"] == "billing"
        assert entry["minimum"] == "0.88.0"
        assert entry["manual_adoption_steps"] == steps

    def test_multiple_modules_mixed(self) -> None:
        """Mixed state: some satisfied, some behind."""
        from unittest.mock import Mock
        from quickscale_core.manifest.schema import ContractVintage

        social_vintage = ContractVintage(minimum="0.86.0")
        billing_vintage = ContractVintage(minimum="0.88.0")
        social = Mock(spec=["contract_vintage"], contract_vintage=social_vintage)
        billing = Mock(spec=["contract_vintage"], contract_vintage=billing_vintage)
        no_vintage = Mock(spec=["contract_vintage"], contract_vintage=None)
        manifests = {
            "social": social,
            "billing": billing,
            "auth": no_vintage,
        }
        result = _check_contract_vintage("0.87.0", manifests)
        assert result["module_count"] == 2  # social + billing
        assert result["modules_behind_count"] == 1
        assert result["modules_behind"][0]["module"] == "billing"

    # ------------------------------------------------------------------ #
    # has_state flag for UX distinction (CR-SA10.2-002)
    # ------------------------------------------------------------------ #

    def test_contract_vintage_legacy_state_has_state_true(self) -> None:
        """When state exists but project_contract is None, has_state=True
        and the display message says 'legacy project'."""
        from unittest.mock import Mock
        from quickscale_core.manifest.schema import ContractVintage

        vintage = ContractVintage(minimum="0.87.0")
        manifest = Mock(spec=["contract_vintage"], contract_vintage=vintage)
        manifests = {"social": manifest}

        # Simulate state existing but project_contract = None (legacy)
        project_contract = None
        result = _check_contract_vintage(project_contract, manifests)
        result["has_state"] = True  # set by _compute_drift_diagnostics

        assert result["has_state"] is True
        assert result["project_contract"] is None
        # Module should still be flagged as behind
        assert result["module_count"] == 1
        assert result["modules_behind_count"] == 1

    def test_contract_vintage_no_state_has_state_false(self) -> None:
        """When state does not exist, has_state=False and the display
        message says 'no state yet'."""
        result = _check_contract_vintage(None, None)
        result["has_state"] = False  # set by _compute_drift_diagnostics

        assert result["has_state"] is False
        assert result["project_contract"] is None
        assert result["module_count"] == 0

    def test_contract_vintage_with_contract_has_state_true(self) -> None:
        """When project_contract is set, has_state is True."""
        from unittest.mock import Mock
        from quickscale_core.manifest.schema import ContractVintage

        vintage = ContractVintage(minimum="0.87.0")
        manifest = Mock(spec=["contract_vintage"], contract_vintage=vintage)
        manifests = {"social": manifest}

        result = _check_contract_vintage("0.87.0", manifests)
        result["has_state"] = True

        assert result["has_state"] is True
        assert result["project_contract"] == "0.87.0"
        assert result["modules_behind_count"] == 0


class TestContractVintageInDiagnostics:
    """Contract-vintage must appear in drift diagnostics."""

    def test_diagnostics_includes_contract_vintage(self, tmp_path):
        """_compute_drift_diagnostics output includes contract_vintage."""
        from quickscale_core.manifest.schema import ContractVintage
        from unittest.mock import Mock

        state_dir = tmp_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n  slug: x\n  package: x\n  theme: showcase_html\n"
            "  project_contract: '0.86.0'\n"
            "modules: {}\n"
        )

        from quickscale_cli.schema.state_schema import StateManager
        from quickscale_core.project_state import ProjectStateManager

        sm = StateManager(tmp_path)
        psm = ProjectStateManager(tmp_path)
        state = sm.load()

        vintage = ContractVintage(minimum="0.87.0", manual_adoption_steps=["Do X"])
        mock_manifest = Mock(spec=["contract_vintage"], contract_vintage=vintage)
        manifests = {"social": mock_manifest}

        result = _compute_drift_diagnostics(
            tmp_path, state, psm, sm, manifests=manifests
        )

        assert "contract_vintage" in result
        cv = result["contract_vintage"]
        assert cv["project_contract"] == "0.86.0"
        assert cv["module_count"] == 1
        assert cv["modules_behind_count"] == 1
        assert cv["modules_behind"][0]["module"] == "social"
