"""Caller-sentinel tests for SA94 read-only theme preflight.

Tests verify that the preflight is invoked before operational mutation
seams across plan, apply, wiring, DR, and development commands.

These are **sentinel** tests — they verify that the correct error is
raised when an invalid theme exists, proving the preflight is wired
correctly.  They do not exercise every downstream code path.
"""

from __future__ import annotations

from pathlib import Path

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
