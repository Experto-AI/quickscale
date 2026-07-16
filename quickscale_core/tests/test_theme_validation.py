"""Tests for quickscale_core.utils.theme_validation preflight."""

from pathlib import Path

import pytest
import yaml

from quickscale_core.utils.theme_validation import (
    SOLE_VALID_THEME,
    ThemeValidationError,
    validate_theme_preflight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def _react_config(**overrides: str) -> dict:
    return {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": SOLE_VALID_THEME,
            **overrides,
        },
    }


def _html_config(**overrides: str) -> dict:
    return {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": "showcase_html",
            **overrides,
        },
    }


def _state_data(**overrides: str) -> dict:
    return {
        "version": "1",
        "project": {
            "slug": "myapp",
            "package": "myapp",
            "theme": SOLE_VALID_THEME,
            **overrides,
        },
    }


# ---------------------------------------------------------------------------
# No files present
# ---------------------------------------------------------------------------


def test_empty_directory_passes(tmp_path: Path) -> None:
    """Preflight passes when no config/state/recovery files exist."""
    validate_theme_preflight(tmp_path)  # no exception


# ---------------------------------------------------------------------------
# Config only
# ---------------------------------------------------------------------------


def test_config_react_passes(tmp_path: Path) -> None:
    _write_yml(tmp_path / "quickscale.yml", _react_config())
    validate_theme_preflight(tmp_path)


def test_config_html_raises(tmp_path: Path) -> None:
    _write_yml(tmp_path / "quickscale.yml", _html_config())
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "showcase_html" in str(excinfo.value)
    assert "retired" in str(excinfo.value)
    assert SOLE_VALID_THEME in str(excinfo.value)


def test_config_unknown_theme_raises(tmp_path: Path) -> None:
    _write_yml(
        tmp_path / "quickscale.yml",
        {
            "version": "1",
            "project": {"slug": "myapp", "package": "myapp", "theme": "unicorn"},
        },
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "unicorn" in str(excinfo.value)
    assert SOLE_VALID_THEME in str(excinfo.value)


def test_config_theme_absent_with_default_passes(tmp_path: Path) -> None:
    """Absent theme in desired config uses schema default (React)."""
    _write_yml(
        tmp_path / "quickscale.yml",
        {"version": "1", "project": {"slug": "myapp", "package": "myapp"}},
    )
    validate_theme_preflight(tmp_path)


# ---------------------------------------------------------------------------
# State only
# ---------------------------------------------------------------------------


def test_state_react_passes(tmp_path: Path) -> None:
    _write_yml(tmp_path / ".quickscale" / "state.yml", _state_data())
    validate_theme_preflight(tmp_path)


def test_state_html_raises(tmp_path: Path) -> None:
    _write_yml(
        tmp_path / ".quickscale" / "state.yml",
        _state_data(theme="showcase_html"),
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "showcase_html" in str(excinfo.value)
    assert "retired" in str(excinfo.value)


def test_state_missing_theme_raises(tmp_path: Path) -> None:
    _write_yml(
        tmp_path / ".quickscale" / "state.yml",
        {"version": "1", "project": {"slug": "myapp", "package": "myapp"}},
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "missing the required" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Config-first fallback must not mask invalid state
# ---------------------------------------------------------------------------


def test_config_react_state_html_raises(tmp_path: Path) -> None:
    """Config with React must not mask invalid state theme."""
    _write_yml(tmp_path / "quickscale.yml", _react_config())
    _write_yml(
        tmp_path / ".quickscale" / "state.yml",
        _state_data(theme="showcase_html"),
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "showcase_html" in str(excinfo.value)


def test_config_react_state_html_recovery_html_raises(tmp_path: Path) -> None:
    """All sources are checked independently; all invalid themes reported."""
    _write_yml(tmp_path / "quickscale.yml", _react_config())
    _write_yml(
        tmp_path / ".quickscale" / "state.yml",
        _state_data(theme="showcase_html"),
    )
    _write_yml(
        tmp_path / ".quickscale" / "apply-recovery.yml",
        _state_data(theme="showcase_html"),
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "showcase_html" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Recovery ledger
# ---------------------------------------------------------------------------


def test_recovery_html_config_react_state_react_raises(tmp_path: Path) -> None:
    """Recovery ledger with HTML raises even when config and state are React."""
    _write_yml(tmp_path / "quickscale.yml", _react_config())
    _write_yml(tmp_path / ".quickscale" / "state.yml", _state_data())
    _write_yml(
        tmp_path / ".quickscale" / "apply-recovery.yml",
        _state_data(theme="showcase_html"),
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "showcase_html" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Malformed files
# ---------------------------------------------------------------------------


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    bad_path = tmp_path / "quickscale.yml"
    bad_path.write_text("{invalid: yaml: unquoted: yes")
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "invalid YAML" in str(excinfo.value)


def test_non_dict_yaml_raises(tmp_path: Path) -> None:
    bad_path = tmp_path / "quickscale.yml"
    bad_path.write_text("not_a_dict")
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "must be a YAML mapping" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Valid React normal order (all three sources)
# ---------------------------------------------------------------------------


def test_all_three_sources_react_passes(tmp_path: Path) -> None:
    _write_yml(tmp_path / "quickscale.yml", _react_config())
    _write_yml(tmp_path / ".quickscale" / "state.yml", _state_data())
    _write_yml(tmp_path / ".quickscale" / "apply-recovery.yml", _state_data())
    validate_theme_preflight(tmp_path)


# ---------------------------------------------------------------------------
# Error message structure
# ---------------------------------------------------------------------------


def test_error_message_includes_invalid_theme(tmp_path: Path) -> None:
    """Error message must name the invalid value and acceptable theme."""
    _write_yml(tmp_path / "quickscale.yml", _html_config())
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "showcase_html" in str(excinfo.value)
    assert SOLE_VALID_THEME in str(excinfo.value)


def test_error_source_label_is_present(tmp_path: Path) -> None:
    _write_yml(tmp_path / "quickscale.yml", _html_config())
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert excinfo.value.source_label is not None
    assert "quickscale.yml" in str(excinfo.value.source_label)
