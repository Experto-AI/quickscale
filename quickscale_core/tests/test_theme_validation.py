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


# CR-SA94-RESYNC-001: explicit null must be rejected.
def test_config_theme_explicit_null_raises(tmp_path: Path) -> None:
    """Explicit 'project.theme: null' must be rejected (not silently defaulted)."""
    _write_yml(
        tmp_path / "quickscale.yml",
        {
            "version": "1",
            "project": {"slug": "myapp", "package": "myapp", "theme": None},
        },
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "null" in str(excinfo.value)
    assert SOLE_VALID_THEME in str(excinfo.value)


def test_config_theme_explicit_null_yaml_empty_value_raises(tmp_path: Path) -> None:
    """YAML 'project.theme:' (empty value, parsed as null) must be rejected."""
    config_path = tmp_path / "quickscale.yml"
    config_path.write_text(
        "version: '1'\nproject:\n  slug: myapp\n  package: myapp\n  theme:\n"
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "null" in str(excinfo.value)
    assert SOLE_VALID_THEME in str(excinfo.value)


def test_custom_config_path_is_selected_without_changing_state_root(
    tmp_path: Path,
) -> None:
    custom_path = tmp_path / "config" / "desired.yml"
    _write_yml(custom_path, _react_config())
    _write_yml(tmp_path / "quickscale.yml", _html_config())
    _write_yml(
        tmp_path / ".quickscale" / "state.yml",
        _state_data(theme="showcase_html"),
    )

    with pytest.raises(ThemeValidationError, match="showcase_html"):
        validate_theme_preflight(tmp_path, config_path=custom_path)


@pytest.mark.parametrize(
    "data",
    [
        "not: valid: yaml: [",
        "version: '1'\n",
        "version: '1'\nproject: not-a-mapping\n",
        "version: '1'\nproject:\n  theme:\n",
    ],
)
def test_defer_config_errors_allows_apply_to_continue(
    tmp_path: Path, data: str
) -> None:
    config_path = tmp_path / "custom.yml"
    config_path.write_text(data)
    validate_theme_preflight(
        tmp_path,
        config_path=config_path,
        defer_config_errors=True,
    )


def test_defer_config_errors_does_not_defer_unsupported_theme(tmp_path: Path) -> None:
    config_path = tmp_path / "custom.yml"
    _write_yml(config_path, _html_config())

    with pytest.raises(ThemeValidationError, match="showcase_html"):
        validate_theme_preflight(
            tmp_path,
            config_path=config_path,
            defer_config_errors=True,
        )


def test_defer_config_errors_never_defers_state_errors(tmp_path: Path) -> None:
    _write_yml(
        tmp_path / ".quickscale" / "state.yml",
        {"version": "1", "project": {"theme": "showcase_html"}},
    )

    with pytest.raises(ThemeValidationError, match="showcase_html"):
        validate_theme_preflight(tmp_path, defer_config_errors=True)


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


def test_recovery_checkpoint_requires_opt_in(tmp_path: Path) -> None:
    """The recovery checkpoint placeholder remains invalid by default."""
    _write_yml(
        tmp_path / ".quickscale" / "apply-recovery.yml",
        _state_data(theme="__checkpoint__"),
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "__checkpoint__" in str(excinfo.value)


def test_recovery_checkpoint_opt_in_passes(tmp_path: Path) -> None:
    """The explicit opt-in permits the placeholder in the recovery ledger."""
    _write_yml(tmp_path / "quickscale.yml", _react_config())
    _write_yml(tmp_path / ".quickscale" / "state.yml", _state_data())
    _write_yml(
        tmp_path / ".quickscale" / "apply-recovery.yml",
        _state_data(theme="__checkpoint__"),
    )
    validate_theme_preflight(tmp_path, allow_recovery_checkpoint=True)


@pytest.mark.parametrize("state_path", ["quickscale.yml", ".quickscale/state.yml"])
def test_recovery_checkpoint_opt_in_does_not_allow_config_or_state(
    tmp_path: Path, state_path: str
) -> None:
    """The opt-in must not weaken desired or applied-state validation."""
    if state_path == "quickscale.yml":
        data = _react_config(theme="__checkpoint__")
    else:
        data = _state_data(theme="__checkpoint__")
    _write_yml(tmp_path / state_path, data)
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path, allow_recovery_checkpoint=True)
    assert "__checkpoint__" in str(excinfo.value)


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


# ---------------------------------------------------------------------------
# CR-SA94-REV-A-001: Missing / non-mapping project section fails closed
# ---------------------------------------------------------------------------


def test_config_missing_project_raises(tmp_path: Path) -> None:
    """Config without a 'project' key must fail closed (not default to React)."""
    _write_yml(tmp_path / "quickscale.yml", {"version": "1"})
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "missing the required 'project' section" in str(excinfo.value)


def test_config_non_dict_project_raises(tmp_path: Path) -> None:
    """Config where 'project' is not a dict must fail closed."""
    _write_yml(
        tmp_path / "quickscale.yml",
        {"version": "1", "project": "not-a-dict"},
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "missing the required 'project' section" in str(excinfo.value)


def test_state_missing_project_raises(tmp_path: Path) -> None:
    """State file without a 'project' key must fail closed."""
    _write_yml(tmp_path / ".quickscale" / "state.yml", {"version": "1"})
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "missing the required 'project' section" in str(excinfo.value)


def test_recovery_missing_project_raises(tmp_path: Path) -> None:
    """Recovery file without a 'project' key must fail closed."""
    _write_yml(
        tmp_path / ".quickscale" / "apply-recovery.yml",
        {"version": "1"},
    )
    with pytest.raises(ThemeValidationError) as excinfo:
        validate_theme_preflight(tmp_path)
    assert "missing the required 'project' section" in str(excinfo.value)
