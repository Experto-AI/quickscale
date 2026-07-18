"""Caller-sentinel tests for SA94 read-only theme preflight.

Tests verify that the preflight is invoked before operational mutation
seams across plan, apply, wiring, DR, and development commands.

These are **sentinel** tests — they verify that the correct error is
raised when an invalid theme exists, proving the preflight is wired
correctly.  They do not exercise every downstream code path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
import yaml
from click.testing import CliRunner

from quickscale_core.utils.theme_validation import (
    SOLE_VALID_THEME,
    ThemeValidationError,
    validate_theme_preflight,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def react_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with React theme."""
    config = {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": SOLE_VALID_THEME,
        },
    }
    config_path = tmp_path / "quickscale.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    return tmp_path


@pytest.fixture
def html_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with retired HTML theme."""
    config = {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": "showcase_html",
        },
    }
    config_path = tmp_path / "quickscale.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    return tmp_path


@pytest.fixture
def null_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with explicit project.theme: null."""
    config = {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": None,
        },
    }
    config_path = tmp_path / "quickscale.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    return tmp_path


@pytest.fixture
def html_state_project(tmp_path: Path) -> Path:
    """Project where state.yml has HTML but config has React."""
    config = {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": SOLE_VALID_THEME,
        },
    }
    state = {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": "showcase_html",
        },
    }
    (tmp_path / "quickscale.yml").write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".quickscale" / "state.yml").write_text(
        yaml.dump(state, default_flow_style=False, sort_keys=False)
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Core preflight sentinel
# ---------------------------------------------------------------------------


class TestCorePreflight:
    """Basic preflight validation (source-level tests)."""

    def test_react_passes(self, react_project: Path) -> None:
        validate_theme_preflight(react_project)

    def test_html_raises(self, html_project: Path) -> None:
        with pytest.raises(ThemeValidationError) as exc:
            validate_theme_preflight(html_project)
        assert "showcase_html" in str(exc.value)

    def test_html_state_raises(self, html_state_project: Path) -> None:
        """Config-first fallback must not mask invalid state."""
        with pytest.raises(ThemeValidationError) as exc:
            validate_theme_preflight(html_state_project)
        assert "showcase_html" in str(exc.value)

    def test_non_existent_project_passes(self, tmp_path: Path) -> None:
        """Preflight passes when no sources exist."""
        validate_theme_preflight(tmp_path)

    # CR-SA94-RESYNC-001: explicit null must be rejected.
    def test_null_theme_raises(self, null_project: Path) -> None:
        """Explicit project.theme: null must be rejected."""
        with pytest.raises(ThemeValidationError) as exc:
            validate_theme_preflight(null_project)
        assert "null" in str(exc.value)
        assert SOLE_VALID_THEME in str(exc.value)


# ---------------------------------------------------------------------------
# Plan command sentinel
# ---------------------------------------------------------------------------


class TestPlanPreflight:
    """Verify plan_command rejects projects with invalid themes.

    Tests that internal handler functions call the preflight.
    """

    def test_plan_reconfigure_html_rejected(
        self, html_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_handle_reconfigure must raise click.Abort for HTML."""
        from quickscale_cli.commands.plan_command import _handle_reconfigure

        with monkeypatch.context() as mp:
            mp.setattr("click.confirm", lambda *a, **kw: True)
            mp.setattr("click.prompt", lambda *a, **kw: "")
            with pytest.raises(click.Abort):
                _handle_reconfigure(html_project, existing_config=None)

    def test_plan_add_html_rejected(
        self, html_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_handle_add_modules must raise click.Abort for HTML."""
        from quickscale_cli.commands.plan_command import _handle_add_modules

        with monkeypatch.context() as mp:
            mp.setattr("click.confirm", lambda *a, **kw: True)
            mp.setattr("click.prompt", lambda *a, **kw: "")
            with pytest.raises(click.Abort):
                _handle_add_modules(html_project, existing_config=None)

    def test_plan_reconfigure_react_accepted(
        self, react_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_handle_reconfigure for React passes preflight (fails later on context)."""
        from quickscale_cli.commands.plan_command import _handle_reconfigure

        with monkeypatch.context() as mp:
            mp.setattr("click.confirm", lambda *a, **kw: True)
            mp.setattr("click.prompt", lambda *a, **kw: "")
            with pytest.raises(click.Abort) as excinfo:
                _handle_reconfigure(react_project, existing_config=None)
        # Must NOT be theme-related; it aborts on missing state/config context.
        assert "showcase_html" not in str(excinfo)
        assert "theme" not in str(excinfo).lower() or "No configuration" in str(excinfo)


# ---------------------------------------------------------------------------
# Apply command sentinel
# ---------------------------------------------------------------------------


class TestApplyPreflight:
    """Verify apply_command rejects invalid themes before mutation."""

    def test_validate_theme_preflight_called(self, html_project: Path) -> None:
        """The preflight raises for HTML; apply should abort."""
        with pytest.raises(ThemeValidationError):
            validate_theme_preflight(html_project)

    def test_apply_html_rejected(self, html_project: Path) -> None:
        """apply() must fail with theme validation for HTML."""
        from quickscale_cli.commands.apply_command import apply

        runner = CliRunner()
        config_path = html_project / "quickscale.yml"
        # Use invoke to avoid Click context issues with direct calls.
        result = runner.invoke(
            apply,
            [str(config_path)],
        )
        assert result.exit_code != 0
        assert "showcase_html" in (result.output or "")
        assert "retired" in (result.output or "")


# ---------------------------------------------------------------------------
# Wiring sentinel
# ---------------------------------------------------------------------------


class TestWiringPreflight:
    """Verify module_wiring_manager calls the preflight."""

    def test_regenerate_managed_wiring_html_rejected(self, html_project: Path) -> None:
        """regenerate_managed_wiring must return failure for HTML."""
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )

        success, message = regenerate_managed_wiring(html_project)
        assert not success
        assert "showcase_html" in message

    def test_regenerate_managed_wiring_react_accepted(
        self, react_project: Path
    ) -> None:
        """regenerate_managed_wiring with React may fail later but not on preflight."""
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )

        success, message = regenerate_managed_wiring(react_project)
        # May fail on later checks (no embedded modules, no manifests),
        # but must NOT fail with theme validation error.
        assert "showcase_html" not in message
        assert "invalid theme" not in message.lower()


# ---------------------------------------------------------------------------
# DR command sentinel
# ---------------------------------------------------------------------------


class TestDrPreflight:
    """Verify DR commands call preflight before _validate_project_and_docker."""

    def test_build_context_html_rejected(
        self, html_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_build_context must raise click.ClickException for HTML."""
        from quickscale_cli.commands.dr_commands import _build_context

        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.dr_commands.Path.cwd",
                lambda: html_project,
            )
            with pytest.raises(click.ClickException) as exc:
                _build_context(
                    "local-to-railway-develop",
                    source_service=None,
                    target_service=None,
                    source_railway_environment=None,
                    target_railway_environment=None,
                    include_target=False,
                )
            assert "showcase_html" in str(exc.value)

    def test_build_context_react_passes_preflight(
        self, react_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_build_context with React passes preflight (fails on Docker later)."""
        from quickscale_cli.commands.dr_commands import _build_context

        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.dr_commands.Path.cwd",
                lambda: react_project,
            )
            with pytest.raises(SystemExit) as exc:
                _build_context(
                    "local-to-railway-develop",
                    source_service=None,
                    target_service=None,
                    source_railway_environment=None,
                    target_railway_environment=None,
                    include_target=False,
                )
            # SystemExit(1) is from _validate_project_and_docker, not theme.
            # The preflight itself passed without error.
            assert exc.value.code == 1

    # CR-SA94-RESYNC-001: explicit null must be rejected before Docker probes.
    def test_build_context_null_rejected(
        self, null_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_build_context must reject null theme before any Docker probe."""
        from quickscale_cli.commands.dr_commands import _build_context

        mock_docker = Mock()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.dr_commands.Path.cwd",
                lambda: null_project,
            )
            mp.setattr(
                "quickscale_cli.commands.dr_commands._validate_project_and_docker",
                mock_docker,
            )
            with pytest.raises(click.ClickException) as exc:
                _build_context(
                    "local-to-railway-develop",
                    source_service=None,
                    target_service=None,
                    source_railway_environment=None,
                    target_railway_environment=None,
                    include_target=False,
                )
            assert "null" in str(exc.value)
            assert SOLE_VALID_THEME in str(exc.value)
        mock_docker.assert_not_called()


# ---------------------------------------------------------------------------
# Development up sentinel
# ---------------------------------------------------------------------------


class TestDevUpPreflight:
    """Verify 'quickscale up' calls preflight before Docker probes."""

    def test_up_html_rejected(
        self, html_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """up() must fail with HTML theme error."""
        from quickscale_cli.commands.development_commands import up

        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.development_commands.Path.cwd",
                lambda: html_project,
            )
            result = runner.invoke(up, [])
        assert result.exit_code != 0
        assert "showcase_html" in (result.output or "")

    def test_up_react_passes_preflight(
        self, react_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """up() with React passes preflight (fails on Docker context later)."""
        from quickscale_cli.commands.development_commands import up

        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.development_commands.Path.cwd",
                lambda: react_project,
            )
            result = runner.invoke(up, [])
        assert result.exit_code != 0
        # Error must NOT be theme-related
        assert "showcase_html" not in (result.output or "")

    # CR-SA94-RESYNC-001: explicit null must be rejected before Docker probes.
    def test_up_null_rejected(
        self, null_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """up() must reject null theme before any Docker/project probe."""
        from quickscale_cli.commands.development_commands import up

        mock_docker = Mock()
        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.development_commands.Path.cwd",
                lambda: null_project,
            )
            mp.setattr(
                "quickscale_cli.commands.development_commands._validate_project_and_docker",
                mock_docker,
            )
            result = runner.invoke(up, [])
        assert result.exit_code != 0
        assert "null" in (result.output or "")
        assert SOLE_VALID_THEME in (result.output or "")
        mock_docker.assert_not_called()

    def test_up_recovery_html_rejected_with_remediation(
        self, react_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """up() must reject a stale recovery ledger with remediation text."""
        from quickscale_cli.commands.development_commands import up

        recovery = {
            "version": "1",
            "project": {
                "slug": "myapp",
                "package": "myapp",
                "theme": "showcase_html",
            },
        }
        recovery_path = react_project / ".quickscale" / "apply-recovery.yml"
        recovery_path.parent.mkdir(parents=True, exist_ok=True)
        recovery_path.write_text(
            yaml.dump(recovery, default_flow_style=False, sort_keys=False)
        )

        mock_docker = Mock()
        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.development_commands.Path.cwd",
                lambda: react_project,
            )
            mp.setattr(
                "quickscale_cli.commands.development_commands._validate_project_and_docker",
                mock_docker,
            )
            result = runner.invoke(up, [])

        output = result.output or ""
        assert result.exit_code != 0
        assert "showcase_html" in output
        assert "retired" in output
        assert SOLE_VALID_THEME in output
        assert "apply-recovery.yml" in output
        mock_docker.assert_not_called()

    def test_up_recovery_checkpoint_proceeds_past_preflight(
        self, react_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """up() may proceed when only the recovery ledger has a checkpoint."""
        from quickscale_cli.commands.development_commands import up

        recovery = {
            "version": "1",
            "project": {
                "slug": "myapp",
                "package": "myapp",
                "theme": "__checkpoint__",
            },
        }
        recovery_path = react_project / ".quickscale" / "apply-recovery.yml"
        recovery_path.parent.mkdir(parents=True, exist_ok=True)
        recovery_path.write_text(
            yaml.dump(recovery, default_flow_style=False, sort_keys=False)
        )

        post_preflight = RuntimeError("post-preflight sentinel")
        mock_docker = Mock(side_effect=post_preflight)
        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.development_commands.Path.cwd",
                lambda: react_project,
            )
            mp.setattr(
                "quickscale_cli.commands.development_commands._validate_project_and_docker",
                mock_docker,
            )
            result = runner.invoke(up, [])

        assert result.exit_code != 0
        assert result.exception is post_preflight
        assert "Theme validation failed" not in (result.output or "")
        mock_docker.assert_called_once()


# ---------------------------------------------------------------------------
# CR-SA94-REV-A-002: Apply preflight with custom config path and output root
# ---------------------------------------------------------------------------


class TestApplyCustomConfigPreflight:
    """Verify apply_command preflight validates the supplied config file
    directly (regardless of filename) and state/recovery under the
    *actual* output root."""

    def test_apply_custom_config_filename_html_rejected(
        self, html_project: Path
    ) -> None:
        """Apply with a custom-named config file must still reject HTML."""
        from quickscale_cli.commands.apply_command import apply

        # Create a custom-named config (not quickscale.yml) with HTML theme
        custom_config = html_project / "my-custom-config.yml"
        custom_config.write_bytes((html_project / "quickscale.yml").read_bytes())
        # Remove the standard quickscale.yml so preflight must read custom name
        (html_project / "quickscale.yml").unlink()

        runner = CliRunner()
        result = runner.invoke(apply, [str(custom_config)])
        assert result.exit_code != 0
        assert "showcase_html" in (result.output or "")

    def test_apply_custom_config_html_with_react_state_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Apply must check output-root state even when the supplied
        config itself is valid React.  The output root is determined by
        the project slug, not by the config file location."""
        from quickscale_cli.commands.apply_command import apply

        # Mock CWD to tmp_path so output_root = tmp_path/slug
        monkeypatch.chdir(tmp_path)

        # Config in a subdirectory with a custom name.  Parent name
        # ("configs") does NOT match slug ("myapp"), so output root
        # will be tmp_path/myapp (cwd/slug).
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_path = config_dir / "custom-config.yml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "project": {
                        "slug": "myapp",
                        "package": "myapp",
                        "theme": SOLE_VALID_THEME,
                    },
                },
                default_flow_style=False,
                sort_keys=False,
            )
        )

        # State at the ACTUAL output root (tmp_path/myapp) with retired
        # theme — this must be caught even though the config is valid.
        output_root = tmp_path / "myapp"
        (output_root / ".quickscale").mkdir(parents=True, exist_ok=True)
        (output_root / ".quickscale" / "state.yml").write_text(
            yaml.dump(
                {
                    "version": "1",
                    "project": {
                        "slug": "myapp",
                        "package": "myapp",
                        "theme": "showcase_html",
                    },
                },
                default_flow_style=False,
                sort_keys=False,
            )
        )

        runner = CliRunner()
        result = runner.invoke(apply, [str(config_path)])
        assert result.exit_code != 0
        assert "showcase_html" in (result.output or "")
        assert "retired" in (result.output or "")


# ---------------------------------------------------------------------------
# CR-SA94-REV-A-003: Standalone embed / remove preflight sentinel
# ---------------------------------------------------------------------------


class TestStandaloneEmbedPreflight:
    """Verify standalone embed_module rejects retired theme before
    git/remote/subtree mutation."""

    def test_embed_module_html_rejected(self, html_project: Path) -> None:
        """Standalone embed_module must reject HTML before any git ops."""
        from quickscale_cli.commands.module_commands import embed_module

        with patch(
            "quickscale_cli.commands.module_commands._validate_git_environment"
        ) as mock_git:
            result = embed_module(
                module="auth",
                project_path=html_project,
                non_interactive=True,
            )
        assert result is False
        # Git validation must NOT have been called — preflight failed first.
        mock_git.assert_not_called()

    def test_embed_module_react_accepted(self, react_project: Path) -> None:
        """Standalone embed_module with React passes preflight (fails on
        later git validation, not theme)."""
        from quickscale_cli.commands.module_commands import embed_module

        with patch(
            "quickscale_cli.commands.module_commands._validate_git_environment",
            return_value=False,
        ) as mock_git:
            result = embed_module(
                module="auth",
                project_path=react_project,
                non_interactive=True,
            )
        assert result is False
        # Fails on git validation, not theme
        mock_git.assert_called_once()


class TestRemoveCommandPreflight:
    """Verify remove command rejects retired theme before any mutation."""

    def _make_removable_project(self, project_path: Path, theme: str) -> None:
        """Create a minimal project structure that remove can process."""
        # Package directory (needed for _resolve_project_package)
        pkg = project_path / "myapp"
        pkg.mkdir(exist_ok=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "settings").mkdir(exist_ok=True)
        (pkg / "settings" / "__init__.py").write_text("")
        (pkg / "settings" / "modules.py").write_text("")
        (pkg / "urls_modules.py").write_text("")
        (pkg / "quickscale_managed").mkdir(exist_ok=True)
        (pkg / "quickscale_managed" / "__init__.py").write_text("")

        # Desired config with the specified theme
        (project_path / "quickscale.yml").write_text(
            yaml.dump(
                {
                    "version": "1",
                    "project": {
                        "slug": "myapp",
                        "package": "myapp",
                        "theme": theme,
                    },
                },
                default_flow_style=False,
                sort_keys=False,
            )
        )

    def test_remove_html_config_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Remove command must fail when config has retired theme."""
        from quickscale_cli.commands.remove_command import remove

        self._make_removable_project(tmp_path, "showcase_html")

        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.remove_command.Path.cwd",
                lambda: tmp_path,
            )
            result = runner.invoke(remove, ["auth"])
        assert result.exit_code != 0
        assert "showcase_html" in (result.output or "")

    def test_remove_html_state_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Remove must reject retired theme in state even when config
        has React."""
        from quickscale_cli.commands.remove_command import remove

        self._make_removable_project(tmp_path, SOLE_VALID_THEME)

        # State has retired theme
        (tmp_path / ".quickscale").mkdir(exist_ok=True)
        (tmp_path / ".quickscale" / "state.yml").write_text(
            yaml.dump(
                {
                    "version": "1",
                    "project": {
                        "slug": "myapp",
                        "package": "myapp",
                        "theme": "showcase_html",
                    },
                },
                default_flow_style=False,
                sort_keys=False,
            )
        )

        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.remove_command.Path.cwd",
                lambda: tmp_path,
            )
            result = runner.invoke(remove, ["auth"])
        assert result.exit_code != 0
        assert "showcase_html" in (result.output or "")

    def test_remove_react_state_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Remove with React state passes preflight (may fail later on
        module-not-found, not theme)."""
        from quickscale_cli.commands.remove_command import remove

        self._make_removable_project(tmp_path, SOLE_VALID_THEME)

        runner = CliRunner()
        with monkeypatch.context() as mp:
            mp.setattr(
                "quickscale_cli.commands.remove_command.Path.cwd",
                lambda: tmp_path,
            )
            result = runner.invoke(remove, ["auth"])
        # May fail on other issues but NOT on theme validation
        assert "showcase_html" not in (result.output or "")
