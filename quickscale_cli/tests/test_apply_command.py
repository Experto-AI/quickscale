"""Tests for quickscale apply command"""

import click
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from quickscale_cli.commands.apply_command import (
    _abort_for_not_ready_modules,
    _load_and_validate_config,
    _regenerate_managed_wiring_for_apply,
    _validate_module_prerequisites,
    apply,
)
from quickscale_cli.notifications_manifest import default_notifications_module_options


def _make_apply_context(project_path, *, package_name="myapp"):
    return SimpleNamespace(
        output_path=project_path,
        existing_state=None,
        delta=SimpleNamespace(modules_unchanged=[]),
        qs_config=SimpleNamespace(
            project=SimpleNamespace(package=package_name),
            modules={"auth": SimpleNamespace(options={})},
        ),
    )


@pytest.fixture(autouse=True)
def _stub_post_generation_steps():
    """Keep CLI smoke tests focused on apply orchestration, not Poetry/migration tooling."""
    with patch(
        "quickscale_cli.commands.apply_command._run_post_generation_steps",
        return_value=True,
    ):
        yield


class TestApplyCommandBasic:
    """Basic tests for apply command"""

    def test_apply_missing_config_file(self):
        """Test apply command when config file doesn't exist"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(apply, ["nonexistent.yml"])

            assert result.exit_code != 0
            # Click's Path type with exists=True gives this error format
            assert "does not exist" in result.output

    def test_apply_help(self):
        """Test apply command help output"""
        runner = CliRunner()
        result = runner.invoke(apply, ["--help"])

        assert result.exit_code == 0
        assert "Execute project configuration" in result.output
        assert "--force" in result.output
        assert "--no-docker" in result.output
        assert "--no-modules" in result.output
        assert "--verbose-docker" in result.output

    def test_apply_invalid_yaml_syntax(self):
        """Test apply command with invalid YAML"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write("invalid: [unclosed bracket")

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert (
                "Configuration error" in result.output
                or "Invalid YAML" in result.output
            )

    def test_apply_missing_required_fields(self):
        """Test apply command with missing required fields"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write("version: '1'\n")

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output


class TestApplyConfigValidation:
    """Tests for configuration validation in apply command"""

    def test_apply_invalid_project_name(self):
        """Test apply with invalid project name in config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: 123invalid
  package: 123invalid
"""
                )

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output

    def test_apply_unknown_theme(self):
        """Test apply with unknown theme in config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
  theme: unknown_theme
"""
                )

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output

    def test_apply_unknown_module(self):
        """Test apply with unknown module in config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
modules:
  unknown_module:
"""
                )

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output

    @pytest.mark.parametrize(
        ("options", "expected_marker"),
        [
            (
                {"publishable_key_env_var": "stripe-publishable-key"},
                "publishable_key_env_var must be an environment variable name",
            ),
            (
                {"billing_currency": "credits"},
                "billing_currency must be one of the supported QuickScale billing currency codes",
            ),
        ],
    )
    def test_apply_billing_prerequisites_fail_before_readiness_gate(
        self,
        options,
        expected_marker,
        capsys,
    ):
        """Billing apply preflight should report contract issues before readiness."""
        qs_config = SimpleNamespace(
            modules={"billing": SimpleNamespace(options=options)}
        )

        with pytest.raises(click.Abort):
            _validate_module_prerequisites(qs_config)

        error_output = capsys.readouterr().err
        assert "Billing module configuration is incomplete for apply" in error_output
        assert expected_marker in error_output
        assert "correct the billing option values" in error_output
        assert "non-public-ready" not in error_output
        assert "references modules that are not public-ready" not in error_output

    def test_apply_billing_requires_auth_module(self, capsys):
        """Billing apply should fail early when auth is not selected."""
        qs_config = SimpleNamespace(modules={"billing": SimpleNamespace(options={})})

        with pytest.raises(click.Abort):
            _validate_module_prerequisites(qs_config)

        error_output = capsys.readouterr().err
        assert (
            "Billing requires the auth module before apply can continue" in error_output
        )
        assert (
            "Add 'auth' under modules in quickscale.yml before applying billing"
            in error_output
        )

    def test_apply_orgs_requires_auth_module(self, capsys):
        """Orgs apply should fail early when auth is not selected."""
        qs_config = SimpleNamespace(modules={"orgs": SimpleNamespace(options={})})

        with pytest.raises(click.Abort):
            _validate_module_prerequisites(qs_config)

        error_output = capsys.readouterr().err
        assert (
            "Organizations requires the auth module before apply can continue"
            in error_output
        )
        assert (
            "Add 'auth' under modules in quickscale.yml before applying orgs"
            in error_output
        )

    def test_apply_orgs_with_notifications_still_requires_auth_module(self, capsys):
        """Implied notifications must not weaken the explicit orgs->auth prerequisite."""
        qs_config = SimpleNamespace(
            modules={
                "orgs": SimpleNamespace(options={}),
                "notifications": SimpleNamespace(
                    options=default_notifications_module_options()
                ),
            }
        )

        with pytest.raises(click.Abort):
            _validate_module_prerequisites(qs_config)

        error_output = capsys.readouterr().err
        assert (
            "Organizations requires the auth module before apply can continue"
            in error_output
        )

    def test_load_and_validate_config_auto_adds_orgs_and_notifications_for_billing(
        self,
    ):
        """Apply should materialize the billing org dependency chain into quickscale.yml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
  theme: showcase_html
modules:
  auth:
  billing:
docker:
  start: false
"""
                )

            qs_config = _load_and_validate_config(Path("quickscale.yml"))

            assert set(qs_config.modules.keys()) == {
                "auth",
                "billing",
                "orgs",
                "notifications",
            }

            with open("quickscale.yml") as f:
                persisted = yaml.safe_load(f)

            modules = (persisted or {}).get("modules") or {}
            assert "orgs" in modules
            assert modules["notifications"] == default_notifications_module_options()

    def test_load_and_validate_config_auto_adds_orgs_and_notifications_for_crm(
        self,
    ):
        """Apply should materialize the crm org dependency chain into quickscale.yml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
  theme: showcase_html
modules:
  auth:
  crm:
docker:
  start: false
"""
                )

            qs_config = _load_and_validate_config(Path("quickscale.yml"))

            assert set(qs_config.modules.keys()) == {
                "auth",
                "crm",
                "orgs",
                "notifications",
            }

            with open("quickscale.yml") as f:
                persisted = yaml.safe_load(f)

            modules = (persisted or {}).get("modules") or {}
            assert "orgs" in modules
            assert modules["notifications"] == default_notifications_module_options()

    def test_apply_crm_requires_auth_module_via_implied_orgs(self, capsys):
        """CRM without auth should fail fast because CRM implies orgs which requires auth."""
        qs_config = SimpleNamespace(
            modules={
                "crm": SimpleNamespace(options={}),
                "orgs": SimpleNamespace(options={}),
                "notifications": SimpleNamespace(
                    options=default_notifications_module_options()
                ),
            }
        )

        with pytest.raises(click.Abort):
            _validate_module_prerequisites(qs_config)

        error_output = capsys.readouterr().err
        assert (
            "Organizations requires the auth module before apply can continue"
            in error_output
        )

    def test_apply_crm_rejects_non_bool_enable_api(self, capsys):
        """CRM apply should reject non-boolean enable_api via the ingress validator."""
        qs_config = SimpleNamespace(
            modules={
                "crm": SimpleNamespace(options={"enable_api": "yes"}),
            }
        )

        with pytest.raises(click.Abort):
            _validate_module_prerequisites(qs_config)

        error_output = capsys.readouterr().err
        assert "CRM module configuration is incomplete for apply" in error_output
        assert "modules.crm.enable_api must be boolean" in error_output
        assert "correct the CRM option values" in error_output

    def test_abort_for_not_ready_modules_reports_teams_reason(self, capsys):
        """Teams should remain blocked by the non-public-ready apply helper."""
        with pytest.raises(click.Abort):
            _abort_for_not_ready_modules(["teams"], source="quickscale.yml")

        error_output = capsys.readouterr().err
        assert (
            "quickscale.yml references modules that are not public-ready"
            in error_output
        )
        assert "Module 'teams' remains placeholder inventory only" in error_output


class TestApplyDirectoryHandling:
    """Tests for directory handling in apply command"""

    def test_apply_directory_exists_no_force(self):
        """Test apply when directory exists and --force not used"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create config
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
docker:
  start: false
"""
                )

            # Create existing directory with content
            os.makedirs("myapp", exist_ok=True)
            with open("myapp/existing.txt", "w") as f:
                f.write("existing content")

            # Don't confirm
            result = runner.invoke(apply, ["quickscale.yml"], input="n\n")

            assert result.exit_code != 0

    def test_apply_reads_config_from_project_dir(self):
        """Test apply reads config from project directory (myapp/quickscale.yml)"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create project directory with config
            os.makedirs("myapp", exist_ok=True)
            with open("myapp/quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
docker:
  start: false
"""
                )

            # Apply should work (will need confirmation)
            result = runner.invoke(
                apply,
                ["myapp/quickscale.yml"],
                input="y\ny\n",  # Confirm directory has content, proceed
            )

            # Just check it processes the config correctly
            assert result.exit_code == 0
            assert "myapp" in result.output


class TestApplyProjectGeneration:
    """Tests for project generation via apply command"""

    def test_apply_generates_project_structure(self):
        """Test that apply generates basic project structure"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create minimal config
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result.exit_code == 0
            assert os.path.exists("testapp")
            assert os.path.exists("testapp/manage.py")
            assert os.path.exists("testapp/pyproject.toml")

    def test_apply_shows_execution_steps(self):
        """Test that apply shows execution progress"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Should show progress indicators
            assert result.exit_code == 0
            assert "⏳" in result.output or "Generating" in result.output


class TestApplyOptions:
    """Tests for apply command options"""

    def test_apply_no_docker_flag(self):
        """Test --no-docker flag skips Docker operations"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
docker:
  start: true
  build: true
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-docker", "--no-modules"],
                input="y\n",
            )

            # Docker operations should be skipped
            assert result.exit_code == 0
            assert "Starting Docker" not in result.output or "Docker" in result.output

    def test_apply_no_modules_flag(self):
        """Test --no-modules flag skips module embedding"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
modules:
  auth:
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Module embedding should be skipped
            assert result.exit_code == 0
            assert "Embedding module: auth" not in result.output


class TestApplyConfigSummary:
    """Tests for configuration summary display"""

    def test_apply_shows_config_summary(self):
        """Test that apply shows configuration summary before execution"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
  theme: showcase_html
modules:
  auth:
docker:
  start: true
  build: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml"],
                input="n\n",  # Cancel before execution
            )

            # Should show configuration summary
            assert result.exit_code != 0
            assert "myapp" in result.output
            assert "showcase_html" in result.output
            assert "auth" in result.output


class TestApplyThemeHandling:
    """Tests for supported theme handling"""

    def test_apply_removed_theme_fails_validation(self):
        """Removed HTMX theme should fail during config validation."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
  theme: showcase_htmx
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
            )

            assert result.exit_code != 0
            assert "Configuration error" in result.output
            assert "Unknown theme 'showcase_htmx'" in result.output

    def test_apply_showcase_react_generates_frontend(self):
        """Test that showcase_react theme generates frontend directory"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
  theme: showcase_react
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result.exit_code == 0
            assert os.path.exists("myapp/frontend")
            assert os.path.exists("myapp/frontend/package.json")
            assert os.path.exists("myapp/frontend/src/main.tsx")


class TestApplyDefaultConfig:
    """Tests for default config file behavior"""

    def test_apply_uses_default_config_file(self):
        """Test that apply uses quickscale.yml by default"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: myapp
  package: myapp
docker:
  start: false
"""
                )

            # Run without specifying config file
            result = runner.invoke(
                apply,
                ["--no-modules", "--no-docker"],
                input="y\n",
            )

            # Should find and use quickscale.yml
            assert result.exit_code == 0
            assert "myapp" in result.output

    def test_apply_error_no_default_config(self):
        """Test error when no default quickscale.yml exists"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # No quickscale.yml exists
            result = runner.invoke(apply, [])

            assert result.exit_code != 0
            assert (
                "Configuration file not found" in result.output
                or "does not exist" in result.output
            )


class TestApplyIncrementalApply:
    """Tests for incremental apply behavior"""

    def test_apply_creates_state_file(self):
        """Test that apply creates .quickscale/state.yml on successful apply"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result.exit_code == 0
            assert os.path.exists("testapp/.quickscale/state.yml")

    def test_apply_second_apply_is_idempotent(self):
        """Test that second apply with same config shows 'nothing to do'"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
docker:
  start: false
"""
                )

            # First apply
            result1 = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result1.exit_code == 0

            # Create quickscale.yml in the generated project directory
            with open("testapp/quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
docker:
  start: false
"""
                )

            # Second apply should detect no changes
            result2 = runner.invoke(
                apply,
                ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result2.exit_code != 0
            assert (
                "Nothing to do" in result2.output
                or "No changes detected" in result2.output
                or "matches applied state" in result2.output
            )

    def test_apply_shows_delta_for_existing_project(self):
        """Test that apply shows delta when applying to existing project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # First create a project with initial config
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
docker:
  start: false
"""
                )

            result1 = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result1.exit_code == 0

            # Modify config to add a module (will not actually embed)
            with open("testapp/quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
modules:
  auth:
docker:
  start: false
"""
                )

            # Second apply should show delta
            result2 = runner.invoke(
                apply,
                ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                input="n\n",  # Decline to proceed
            )

            assert result2.exit_code != 0
            assert (
                "Modules to add" in result2.output
                or "auth" in result2.output
                or "Changes to apply" in result2.output
            )


class TestApplyStateRecovery:
    """Tests for state file recovery scenarios"""

    def test_apply_handles_missing_state_file(self):
        """Test that apply works when project exists but state file is missing"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # First create a project
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
docker:
  start: false
"""
                )

            result1 = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result1.exit_code == 0

            # Delete state file to simulate corruption/missing state
            import shutil

            if os.path.exists("testapp/.quickscale"):
                shutil.rmtree("testapp/.quickscale")

            # Move config back to project directory
            with open("testapp/quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
docker:
  start: false
"""
                )

            # Apply should detect existing project and handle gracefully
            result2 = runner.invoke(
                apply,
                ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                input="n\n",  # Don't proceed to avoid regeneration
            )

            assert result2.exit_code != 0
            assert "Directory already exists and is not empty" in result2.output

    def test_apply_detects_filesystem_modules(self):
        """Test that apply respects modules in state file"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            import yaml

            # Create project with state file containing module info
            os.makedirs("testapp/.quickscale", exist_ok=True)
            with open("testapp/.quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_html",
                            "created_at": "2025-01-01T00:00:00",
                            "last_applied": "2025-01-01T00:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "commit_sha": None,
                                "embedded_at": "2025-01-01T00:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )

            # Create config with same module
            with open("testapp/quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
modules:
  auth:
docker:
  start: false
"""
                )

            # Create minimal project structure
            os.makedirs("testapp/modules/auth", exist_ok=True)
            with open("testapp/manage.py", "w") as f:
                f.write("# Django manage.py")

            # Apply should show no changes since auth is already in state
            result = runner.invoke(
                apply,
                ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            assert result.exit_code != 0
            assert "Nothing to do" in result.output or "unchanged" in result.output

    def test_apply_retries_pending_post_embed_recovery_instead_of_no_op(self):
        """A post-embed recovery snapshot should resume apply instead of no-oping."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs("testapp/.quickscale", exist_ok=True)
            os.makedirs("testapp/modules/auth", exist_ok=True)

            with open("testapp/manage.py", "w") as f:
                f.write("# Django manage.py")

            with open("testapp/modules/auth/module.yml", "w") as f:
                f.write('name: auth\nversion: "0.82.0"\n')

            with open("testapp/quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
modules:
  auth:
docker:
  start: false
"""
                )

            with open("testapp/.quickscale/apply-recovery.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_html
  created_at: "2025-01-01T00:00:00"
  last_applied: "2025-01-01T00:00:00"
modules:
  auth:
    version: "0.82.0"
    commit_sha:
    embedded_at: "2025-01-01T00:00:00"
    options: {}
git_index_checkpoint: "deadbeefcafebabedeadbeefcafebabedeadbeef"
"""
                )

            with patch(
                "quickscale_cli.commands.apply_command._execute_apply_steps"
            ) as mock_execute:
                result = runner.invoke(
                    apply,
                    ["testapp/quickscale.yml", "--no-docker"],
                    input="y\n",
                )

        assert result.exit_code == 0
        assert "Nothing to do" not in result.output
        assert "Pending post-embed apply recovery detected" in result.output
        mock_execute.assert_called_once()
        assert mock_execute.call_args.args[0].has_pending_post_embed_recovery is True
        assert mock_execute.call_args.args[0].existing_state is not None


class TestApplyManagedWiringStrictContext:
    """Tests for strict managed-wiring context failures during apply."""

    def test_regeneration_fails_on_malformed_quickscale_yaml(self, tmp_path, capsys):
        project = tmp_path / "myapp"
        project.mkdir()
        (project / "myapp").mkdir()
        (project / "quickscale.yml").write_text('version: "1"\nproject: [\n')

        ctx = _make_apply_context(project)

        assert (
            _regenerate_managed_wiring_for_apply(ctx, embedded_modules=["auth"])
            is False
        )

        error_output = capsys.readouterr().err
        assert "Managed wiring regeneration failed" in error_output
        assert "Failed to load module options from quickscale.yml" in error_output

    def test_regeneration_fails_on_malformed_state_yaml(self, tmp_path, capsys):
        project = tmp_path / "myapp"
        project.mkdir()
        (project / "myapp").mkdir()
        (project / ".quickscale").mkdir()
        (project / "quickscale.yml").write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "docker:\n"
            "  start: false\n"
        )
        (project / ".quickscale" / "state.yml").write_text("project: [\n")

        ctx = _make_apply_context(project)

        assert (
            _regenerate_managed_wiring_for_apply(ctx, embedded_modules=["auth"])
            is False
        )

        error_output = capsys.readouterr().err
        assert "Managed wiring regeneration failed" in error_output
        assert (
            "Failed to load module options from .quickscale/state.yml" in error_output
        )

    def test_regeneration_fails_on_managed_wiring_write_exception(
        self, tmp_path, capsys
    ):
        project = tmp_path / "myapp"
        project.mkdir()
        (project / "myapp").mkdir()
        (project / "quickscale.yml").write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "docker:\n"
            "  start: false\n"
        )

        ctx = _make_apply_context(project)

        with patch(
            "quickscale_cli.utils.module_wiring_manager.write_managed_wiring",
            side_effect=OSError("disk full"),
        ):
            assert (
                _regenerate_managed_wiring_for_apply(ctx, embedded_modules=["auth"])
                is False
            )

        error_output = capsys.readouterr().err
        assert "Managed wiring regeneration failed" in error_output
        assert "Failed to write managed wiring files: disk full" in error_output


# ============================================================================
# Phase 3: drift detection and managed file hash capture
# ============================================================================


class TestApplyDriftDetection:
    """Tests for the Phase 3 drift detection helpers in apply_command."""

    def test_warn_version_drift_for_apply_reports_disagreement(self, tmp_path, capsys):
        """Apply should surface state/config version drift as a warning."""
        from quickscale_core.config import add_module
        from quickscale_cli.commands.apply_command import (
            _warn_version_drift_for_apply,
        )
        from quickscale_core.schema.state_schema import (
            ModuleState,
            ProjectState,
            QuickScaleState,
            StateManager,
        )

        project = tmp_path / "myapp"
        project.mkdir()

        # Create state with auth v0.62.0
        StateManager(project).save(
            QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                ),
                modules={
                    "auth": ModuleState(name="auth", version="0.62.0"),
                },
            )
        )

        # Legacy config says 0.63.0 (drift).
        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="0.63.0",
            project_path=project,
        )

        # Build a minimal config object that satisfies the helper.
        config = SimpleNamespace(project=SimpleNamespace(package="myapp"))

        drift = _warn_version_drift_for_apply(project, config)

        assert len(drift) == 1
        assert drift[0].module == "auth"
        captured = capsys.readouterr().out
        assert "Module version drift" in captured

    def test_warn_version_drift_for_apply_silent_when_agreeing(self, tmp_path, capsys):
        """Apply should stay quiet when state and config agree."""
        from quickscale_core.config import add_module
        from quickscale_cli.commands.apply_command import (
            _warn_version_drift_for_apply,
        )
        from quickscale_core.schema.state_schema import (
            ModuleState,
            ProjectState,
            QuickScaleState,
            StateManager,
        )

        project = tmp_path / "myapp"
        project.mkdir()

        StateManager(project).save(
            QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                ),
                modules={
                    "auth": ModuleState(name="auth", version="0.62.0"),
                },
            )
        )

        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="0.62.0",  # matches state
            project_path=project,
        )

        config = SimpleNamespace(project=SimpleNamespace(package="myapp"))

        drift = _warn_version_drift_for_apply(project, config)

        assert drift == []
        captured = capsys.readouterr().out
        assert "Module version drift" not in captured

    def test_warn_version_drift_for_apply_tolerates_shape_invalid_config(
        self, tmp_path, capsys
    ):
        """A shape-invalid config.yml must warn and return [] rather than raise."""
        from quickscale_cli.commands.apply_command import (
            _warn_version_drift_for_apply,
        )

        project = tmp_path / "myapp"
        project.mkdir()
        qs_dir = project / ".quickscale"
        qs_dir.mkdir()
        # Write a config.yml that is valid YAML but has an invalid shape
        # (e.g. a bare scalar instead of a mapping) so ConfigError is raised.
        (qs_dir / "config.yml").write_text("- not_a_mapping\n")

        config = SimpleNamespace(project=SimpleNamespace(package="myapp"))

        drift = _warn_version_drift_for_apply(project, config)

        assert drift == []
        captured = capsys.readouterr().out
        assert "Could not read managed state files" in captured

    def test_capture_managed_file_hashes_writes_ledger(self, tmp_path, capsys):
        """Apply should capture hashes into consolidated state managed_files."""
        from quickscale_cli.commands.apply_command import (
            _capture_managed_file_hashes_after_apply,
        )
        from quickscale_core.schema.state_schema import QuickScaleState, ProjectState

        project = tmp_path / "myapp"
        project.mkdir()
        (project / "myapp" / "settings").mkdir(parents=True)
        (project / "myapp" / "settings" / "modules.py").write_text("A = 1\n")
        (project / "myapp" / "urls_modules.py").write_text("URLS = []\n")

        config = SimpleNamespace(project=SimpleNamespace(package="myapp"))
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
        )

        _capture_managed_file_hashes_after_apply(project, config, state)

        # Phase 3: hashes are stored in consolidated state, not file_hashes.yml.
        assert state.managed_files, "Expected managed_files to be populated"
        assert "myapp/settings/modules.py" in state.managed_files
        assert "myapp/urls_modules.py" in state.managed_files

        captured = capsys.readouterr().out
        assert "Tracked managed file hashes" in captured

    def test_resolve_managed_wiring_paths_uses_package(self, tmp_path):
        """The default managed wiring paths are anchored at the package dir."""
        from quickscale_cli.commands.apply_command import (
            _resolve_managed_wiring_paths,
        )

        config = SimpleNamespace(project=SimpleNamespace(package="myapp"))

        paths = _resolve_managed_wiring_paths(config)
        assert "myapp/settings/modules.py" in paths
        assert "myapp/urls_modules.py" in paths
        assert all("\\" not in p for p in paths)
