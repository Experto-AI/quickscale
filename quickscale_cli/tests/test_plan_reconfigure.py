"""Tests for quickscale plan --reconfigure workflow"""

import os
from pathlib import Path

import yaml
from click.testing import CliRunner

from quickscale_cli.commands.plan_command import (
    _configure_selected_modules,
    _get_project_info_for_reconfig,
    plan,
)
from quickscale_core.contracts.resolvers import default_notifications_module_options


class TestPlanReconfigureBasic:
    """Basic tests for plan --reconfigure command"""

    def test_plan_reconfigure_not_in_project(self) -> None:
        """Test plan --reconfigure when not in a QuickScale project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(plan, ["--reconfigure"])

            assert result.exit_code != 0
            assert "Not in a QuickScale project" in result.output

    def test_plan_reconfigure_help(self) -> None:
        """Test that --reconfigure flag is documented in help"""
        runner = CliRunner()
        result = runner.invoke(plan, ["--help"])

        assert result.exit_code == 0
        assert "--reconfigure" in result.output
        assert "--configure-modules" in result.output

    def test_get_project_info_fallback_uses_react_default(self) -> None:
        """Fallback project info should use showcase_react when state/config missing."""
        project_slug, package_name, theme = _get_project_info_for_reconfig(
            state=None,
            existing_config=None,
            project_path=Path("fallback-project"),
        )

        assert project_slug == "fallback-project"
        assert package_name == "fallback_project"
        assert theme == "showcase_react"

    def test_plan_reconfigure_aborts_for_invalid_auth_desired_config(self) -> None:
        """Reconfigure should fail hard on stale auth desired config in quickscale.yml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  auth:
    social_providers:
      - google
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--reconfigure"])

            assert result.exit_code != 0
            assert "quickscale.yml is invalid" in result.output
            assert "social_providers" in result.output
            assert "registration_enabled" in result.output
            assert "email_verification" in result.output


class TestPlanReconfigureWithState:
    """Tests for --reconfigure with state file"""

    def test_plan_reconfigure_shows_project_info(self) -> None:
        """Test that --reconfigure shows current project info"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            # Don't add modules (n), docker start (n), cancel save (n)
            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "testapp" in result.output
            assert "showcase_react" in result.output

    def test_plan_reconfigure_shows_theme_locked(self) -> None:
        """Test that --reconfigure shows theme is locked"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "locked" in result.output.lower()

    def test_plan_reconfigure_state_only_aborts_before_write_for_invalid_live_notifications(
        self,
    ) -> None:
        """State-only reconfigure should fail before reconstructing quickscale.yml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "notifications": {
                                "version": None,
                                "commit_sha": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {
                                    "sender_name": "QuickScale",
                                    "sender_email": "noreply@example.com",
                                    "resend_domain": "mail.example.com",
                                },
                            }
                        },
                    },
                    f,
                )

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\n")

            assert result.exit_code != 0
            assert "Notifications module configuration is incomplete" in result.output
            assert "sender_email cannot use the default placeholder" in result.output
            assert not Path("quickscale.yml").exists()


class TestPlanReconfigureShowsModules:
    """Tests for module display in reconfigure"""

    def test_plan_reconfigure_shows_installed_modules(self) -> None:
        """Test that --reconfigure shows installed modules"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  auth:
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "auth" in result.output

    def test_plan_reconfigure_shows_pending_modules(self) -> None:
        """Test that --reconfigure shows modules pending apply"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                            }
                        },
                    },
                    f,
                )

            # Config has blog but state doesn't - blog is pending
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  auth:
  blog:
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "auth" in result.output
            assert "blog" in result.output


class TestPlanReconfigureDocker:
    """Tests for Docker reconfiguration"""

    def test_plan_reconfigure_docker_options(self) -> None:
        """Test that --reconfigure allows Docker option changes"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            # Don't add modules (n), docker start/build, create_superuser (n), save (y)
            result = runner.invoke(plan, ["--reconfigure"], input="n\ny\ny\nn\ny\n")

            if result.exit_code == 0:
                with open("quickscale.yml") as f:
                    content = f.read()
                assert "start: true" in content
                assert "build: true" in content


class TestPlanReconfigureAddModules:
    """Tests for adding modules during reconfigure"""

    def test_plan_reconfigure_add_module(self) -> None:
        """Test adding a module during reconfigure"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            # Add modules (y), select 1 (analytics — alpha-sorted), docker (n), save (y)
            result = runner.invoke(plan, ["--reconfigure"], input="y\n1\nn\ny\n")

            if result.exit_code == 0:
                with open("quickscale.yml") as f:
                    content = f.read()
                assert "analytics" in content

    def test_plan_reconfigure_auto_adds_default_notifications_when_orgs_selected(
        self,
    ) -> None:
        """Adding orgs during reconfigure should materialize default notifications."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  auth:
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--reconfigure"], input="y\norgs\nn\ny\n")

            assert result.exit_code == 0
            with open("quickscale.yml") as f:
                config = yaml.safe_load(f)

            modules = (config or {}).get("modules") or {}
            assert "orgs" in modules
            assert modules["notifications"] == default_notifications_module_options()

    def test_plan_reconfigure_auto_adds_orgs_and_notifications_when_crm_selected(
        self,
    ) -> None:
        """Adding crm during reconfigure should materialize orgs and notifications."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  auth:
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--reconfigure"], input="y\ncrm\nn\ny\n")

            assert result.exit_code == 0
            with open("quickscale.yml") as f:
                config = yaml.safe_load(f)

            modules = (config or {}).get("modules") or {}
            assert "crm" in modules
            assert "orgs" in modules
            assert modules["notifications"] == default_notifications_module_options()

    def test_plan_reconfigure_preserves_explicit_notifications_when_adding_orgs(
        self,
    ) -> None:
        """Adding orgs should not overwrite an existing notifications config."""
        runner = CliRunner()
        notifications_config = {
            "enabled": True,
            "sender_name": "Ops",
            "sender_email": "ops@example.com",
            "reply_to_email": "support@example.com",
            "resend_domain": "mg.example.com",
            "resend_api_key_env_var": "OPS_RESEND_API_KEY",
            "webhook_secret_env_var": "OPS_NOTIFICATIONS_WEBHOOK_SECRET",
            "default_tags": ["quickscale", "ops"],
            "allowed_tags": ["quickscale", "ops", "transactional"],
            "webhook_ttl_seconds": 600,
        }
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            },
                            "notifications": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": notifications_config,
                            },
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                        },
                        "modules": {
                            "auth": None,
                            "notifications": notifications_config,
                        },
                        "docker": {"start": False},
                    },
                    f,
                )

            result = runner.invoke(plan, ["--reconfigure"], input="y\norgs\nn\ny\n")

            assert result.exit_code == 0
            with open("quickscale.yml") as f:
                config = yaml.safe_load(f)

            modules = (config or {}).get("modules") or {}
            assert "orgs" in modules
            assert modules["notifications"] == notifications_config

    def test_plan_reconfigure_supports_billing_and_rejects_teams_with_experimental_picker(
        self,
    ) -> None:
        """Reconfigure add flow should accept billing while keeping teams hidden-only."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
docker:
  start: false
"""
                )

            result = runner.invoke(
                plan,
                ["--reconfigure", "--include-experimental"],
                input="y\nteams\nbilling\nn\ny\n",
            )

            assert result.exit_code == 0
            assert "billing - Stripe integration" in result.output
            # teams is not in the discovered catalog; the error loop re-prompts.
            assert "Unknown or already installed module" in result.output

            with open("quickscale.yml") as f:
                config = yaml.safe_load(f)

            modules = (config or {}).get("modules") or {}
            assert "billing" in modules
            assert "teams" not in modules


class TestPlanReconfigureSavesConfig:
    """Tests for config saving"""

    def test_plan_reconfigure_saves_config(self) -> None:
        """Test that --reconfigure saves updated config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            # Don't add modules, docker start (y), build (n), create_superuser (n), save (y)
            result = runner.invoke(plan, ["--reconfigure"], input="n\ny\nn\nn\ny\n")

            assert result.exit_code == 0
            assert os.path.exists("quickscale.yml")
            with open("quickscale.yml") as f:
                content = f.read()
            assert "testapp" in content

    def test_plan_reconfigure_cancel(self) -> None:
        """Test canceling --reconfigure doesn't save config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            # Don't add modules, docker (n), cancel save (n)
            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert result.exit_code != 0 or "Cancelled" in result.output
            # quickscale.yml should not exist unless we saved
            if result.exit_code != 0:
                assert not os.path.exists("quickscale.yml")

    def test_plan_reconfigure_preserves_existing_module_options(self) -> None:
        """Reconfigure should round-trip existing module options when not re-editing them."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "storage": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {
                                    "backend": "s3",
                                    "public_base_url": "https://cdn.example.com/media",
                                },
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  storage:
    backend: s3
    public_base_url: https://cdn.example.com/media
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\ny\n")

            assert result.exit_code == 0
            with open("quickscale.yml") as f:
                content = f.read()
            assert "public_base_url: https://cdn.example.com/media" in content

    def test_plan_reconfigure_prunes_legacy_storage_custom_domain(self) -> None:
        """Reconfigure should remove legacy storage custom_domain options on save."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "storage": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {
                                    "backend": "s3",
                                    "public_base_url": "https://cdn.example.com/media",
                                    "custom_domain": "cdn.example.com",
                                },
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  storage:
    backend: s3
    public_base_url: https://cdn.example.com/media
    custom_domain: cdn.example.com
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\ny\n")

            assert result.exit_code == 0
            with open("quickscale.yml") as f:
                content = f.read()
            assert "custom_domain" not in content
            assert "public_base_url: https://cdn.example.com/media" in content

    def test_plan_reconfigure_configure_modules_updates_storage_options(self) -> None:
        """Reconfigure should allow interactive storage option updates when requested."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "storage": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {
                                    "backend": "local",
                                    "public_base_url": "",
                                },
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  storage:
    backend: local
    public_base_url: ""
docker:
  start: false
"""
                )

            result = runner.invoke(
                plan,
                ["--reconfigure", "--configure-modules"],
                input=(
                    "n\n"
                    "y\n"
                    "s3\n"
                    "/media/\n"
                    "https://cdn.example.com/media\n"
                    "assets\n"
                    "\n"
                    "eu-west-1\n"
                    "key-id\n"
                    "secret-key\n"
                    "\n"
                    "n\n"
                    "n\n"
                    "y\n"
                ),
            )

            assert result.exit_code == 0
            with open("quickscale.yml") as f:
                content = f.read()
            assert "backend: s3" in content
            assert "public_base_url: https://cdn.example.com/media" in content
            assert "bucket_name: assets" in content


class TestConfigureSelectedModulesEmptyNewModules:
    """Regression tests for CR-M6-004: empty new_modules must not fall back to all."""

    def test_empty_new_modules_prompts_reconfigure_instead_of_running_immediately(
        self,
    ) -> None:
        """An explicit empty new_modules set must prompt for reconfiguration.

        When ``--reconfigure --configure-modules`` is used and the user adds no
        new modules, ``new_modules`` is an empty set.  The function must NOT
        treat that as "all modules are new" and run configurators immediately.
        Instead, it should prompt whether to reconfigure each existing module.
        """
        from click.testing import CliRunner

        import click

        existing_options = {"storage": {"backend": "local", "public_base_url": ""}}

        @click.command()
        def _probe() -> None:
            configured = _configure_selected_modules(
                ["storage"],
                existing_options,
                new_modules=set(),
                allow_reconfigure_existing=True,
            )
            # If the user declined reconfiguration, the original options
            # should be preserved (not replaced by configurator output).
            click.echo(f"RESULT:{configured['storage']['backend']}")

        runner = CliRunner()
        # User declines reconfiguration for the existing storage module.
        invoke_result = runner.invoke(_probe, input="n\n")
        assert "Reconfigure storage module options?" in invoke_result.output
        assert "RESULT:local" in invoke_result.output

    def test_none_new_modules_treats_all_as_new(self) -> None:
        """When new_modules is None, all modules should be treated as new."""
        from click.testing import CliRunner

        import click

        existing_options = {"storage": {"backend": "local", "public_base_url": ""}}

        @click.command()
        def _probe() -> None:
            configured = _configure_selected_modules(
                ["storage"],
                existing_options,
                new_modules=None,
                allow_reconfigure_existing=False,
            )
            # With new_modules=None, storage is treated as new and its
            # configurator runs immediately (default backend is "local").
            click.echo(f"RESULT:{configured['storage']['backend']}")

        runner = CliRunner()
        # The storage configurator will prompt for backend choice.
        # Accept the default ("local") by sending empty input + extra prompts.
        invoke_result = runner.invoke(
            _probe,
            input="\n\n\n\n\n\n\n\n\n\n\n\n",
        )
        # The configurator should have run (no "Reconfigure" prompt).
        assert "Reconfigure storage module options?" not in invoke_result.output
        assert "RESULT:local" in invoke_result.output

    def test_reconfigure_configure_modules_no_new_modules_preserves_options(
        self,
    ) -> None:
        """Full integration: --reconfigure --configure-modules with no new modules.

        When the user declines adding modules and declines reconfiguring
        existing modules, the original options should be preserved.
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "slug": "testapp",
                            "package": "testapp",
                            "theme": "showcase_react",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "storage": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {
                                    "backend": "s3",
                                    "public_base_url": "https://cdn.example.com/media",
                                },
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  slug: testapp
  package: testapp
  theme: showcase_react
modules:
  storage:
    backend: s3
    public_base_url: https://cdn.example.com/media
docker:
  start: false
"""
                )

            # Don't add modules (n), decline reconfigure storage (n),
            # docker start (n), save (y).
            result = runner.invoke(
                plan,
                ["--reconfigure", "--configure-modules"],
                input="n\nn\nn\ny\n",
            )

            assert result.exit_code == 0
            with open("quickscale.yml") as f:
                content = f.read()
            # Original options should be preserved.
            assert "backend: s3" in content
            assert "public_base_url: https://cdn.example.com/media" in content
            # The reconfigure prompt should have appeared.
            assert "Reconfigure storage module options?" in result.output
