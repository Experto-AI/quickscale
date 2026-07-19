"""SA94 read-only theme validation preflight.

Independently parses and validates the ``theme`` field in every present
desired / state / recovery source before any operational mutation.
Only ``showcase_react`` is accepted.

Design invariants
-----------------
* **Read-only.**  This module never writes to the filesystem.
* **Fail-close.**  Malformed YAML, missing required structure, or
  unrecognised themes raise :class:`ThemeValidationError` immediately.
  There is no silent fallback or auto-conversion.
* **All sources checked independently.**  Config-first identity
  fallback must *not* mask an invalid authoritative or recovery source.
  If any present file carries an invalid theme, the preflight fails
  regardless of what other valid sources say.
* **Actionable remediation.**  Error messages name the file, the
  invalid value, and the only supported theme.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Public error type
# ---------------------------------------------------------------------------


class ThemeValidationError(ValueError):
    """Raised when theme validation fails for any source.

    The ``source_label`` attribute identifies which configuration source
    triggered the failure (e.g. ``quickscale.yml``, ``.quickscale/state.yml``,
    ``.quickscale/apply-recovery.yml``).  The ``theme`` attribute carries
    the invalid value when applicable.
    """

    def __init__(
        self,
        message: str,
        *,
        source_label: str | None = None,
        theme: str | None = None,
    ) -> None:
        self.source_label = source_label
        self.theme = theme
        super().__init__(message)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOLE_VALID_THEME = "showcase_react"

_CONFIG_FILE = "quickscale.yml"
_STATE_FILE = ".quickscale/state.yml"
_RECOVERY_FILE = ".quickscale/apply-recovery.yml"

_CONFIG_LABEL = "quickscale.yml (desired state)"
_STATE_LABEL = ".quickscale/state.yml (applied state)"
_RECOVERY_LABEL = ".quickscale/apply-recovery.yml (recovery ledger)"
_RECOVERY_CHECKPOINT_THEME = "__checkpoint__"


# ---------------------------------------------------------------------------
# Core preflight
# ---------------------------------------------------------------------------


def validate_theme_preflight(
    project_path: Path,
    *,
    config_path: Path | None = None,
    defer_config_errors: bool = False,
    allow_recovery_checkpoint: bool = False,
) -> None:
    """Validate the ``theme`` field in every present configuration source.

    Checks *all* of the following sources independently when they exist:

    * ``<config_path>`` or ``<project_path>/quickscale.yml`` — desired state
    * ``<project_path>/.quickscale/state.yml`` — applied state
    * ``<project_path>/.quickscale/apply-recovery.yml`` — recovery ledger

    The recovery ledger may temporarily use the ``__checkpoint__`` placeholder
    only when ``allow_recovery_checkpoint`` is explicitly enabled. The default
    remains fail-closed for every source, including the recovery ledger.

    Args:
        project_path: Root directory of the QuickScale project.
        config_path: Desired-state YAML path. State and recovery paths remain
            rooted at ``project_path``.
        defer_config_errors: Defer desired-state read, structure, absent-theme,
            and explicit-null errors. Unsupported non-null themes still fail.
        allow_recovery_checkpoint: Permit the recovery ledger's temporary
            ``__checkpoint__`` placeholder. This does not permit the
            placeholder in desired or applied state.

    Raises:
        ThemeValidationError: If any present source has a missing,
            malformed, or non-``showcase_react`` theme.
    """
    errors: list[str] = []

    desired_path = config_path or project_path / _CONFIG_FILE
    if desired_path.exists():
        error = _source_error(
            desired_path,
            _CONFIG_LABEL,
            _extract_config_theme,
            defer_errors=defer_config_errors,
        )
        if error:
            errors.append(error)

    # Applied state and recovery remain rooted at the project path.
    state_path = project_path / _STATE_FILE
    if state_path.exists():
        error = _source_error(state_path, _STATE_LABEL, _extract_state_theme)
        if error:
            errors.append(error)

    recovery_path = project_path / _RECOVERY_FILE
    if recovery_path.exists():
        error = _source_error(
            recovery_path,
            _RECOVERY_LABEL,
            _extract_state_theme,
            allow_recovery_checkpoint=allow_recovery_checkpoint,
        )
        if error:
            errors.append(error)

    if errors:
        raise ThemeValidationError(
            "\n".join(errors),
            source_label=_source_labels(desired_path, state_path, recovery_path),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _source_error(
    file_path: Path,
    source_label: str,
    extract_theme: Any,
    *,
    defer_errors: bool = False,
    allow_recovery_checkpoint: bool = False,
) -> str | None:
    try:
        _validate_source_theme(
            file_path,
            source_label,
            extract_theme,
            defer_errors=defer_errors,
            allow_recovery_checkpoint=allow_recovery_checkpoint,
        )
    except ThemeValidationError as exc:
        return str(exc)
    return None


def _source_labels(*paths: Path) -> str:
    labels = (_CONFIG_LABEL, _STATE_LABEL, _RECOVERY_LABEL)
    return ", ".join(label for label, path in zip(labels, paths) if path.exists())


def _validate_source_theme(
    file_path: Path,
    source_label: str,
    extract_theme: Any,
    *,
    defer_errors: bool = False,
    allow_recovery_checkpoint: bool = False,
) -> None:
    """Parse *file_path* and validate its theme."""
    try:
        raw = _load_yaml_source(file_path, source_label)
        _project_mapping(raw, source_label)
        theme = extract_theme(raw)
    except ThemeValidationError:
        if defer_errors:
            return
        raise
    except Exception as exc:
        if defer_errors:
            return
        raise ThemeValidationError(
            f"{source_label} could not be parsed: {exc}",
            source_label=source_label,
        ) from exc

    if theme is None:
        if defer_errors or source_label == _CONFIG_LABEL:
            return  # Absent -> default is React, which is valid.
        raise ThemeValidationError(
            f"{source_label} is missing the required 'project.theme' field",
            source_label=source_label,
        )

    _validate_theme_value(
        theme,
        source_label,
        allow_recovery_checkpoint=allow_recovery_checkpoint,
    )


def _load_yaml_source(file_path: Path, source_label: str) -> Any:
    try:
        return yaml.safe_load(file_path.read_text())
    except yaml.YAMLError as exc:
        raise ThemeValidationError(
            f"{source_label} contains invalid YAML and cannot be used: {exc}",
            source_label=source_label,
        ) from exc
    except OSError as exc:
        raise ThemeValidationError(
            f"{source_label} could not be read: {exc}",
            source_label=source_label,
        ) from exc


def _project_mapping(raw: Any, source_label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ThemeValidationError(
            f"{source_label} must be a YAML mapping (dictionary)",
            source_label=source_label,
        )
    project = raw.get("project")
    if not isinstance(project, dict):
        raise ThemeValidationError(
            f"{source_label} is missing the required 'project' section",
            source_label=source_label,
        )
    return project


def _validate_theme_value(
    theme: str,
    source_label: str,
    *,
    allow_recovery_checkpoint: bool = False,
) -> None:
    if theme == SOLE_VALID_THEME:
        return
    if (
        theme == _RECOVERY_CHECKPOINT_THEME
        and allow_recovery_checkpoint
        and source_label == _RECOVERY_LABEL
    ):
        return

    if theme == "showcase_html":
        hint = (
            f"Theme 'showcase_html' has been retired. "
            f"Change '{_path_label_for_source(source_label)}' project.theme "
            f"to '{SOLE_VALID_THEME}'."
        )
    else:
        hint = (
            f"Only '{SOLE_VALID_THEME}' is supported. "
            f"Change '{_path_label_for_source(source_label)}' project.theme "
            f"to '{SOLE_VALID_THEME}'."
        )

    raise ThemeValidationError(
        f"Invalid theme '{theme}' in {source_label}. {hint}",
        source_label=source_label,
        theme=theme,
    )


def _extract_config_theme(raw: dict) -> str | None:
    """Extract theme from a parsed quickscale.yml mapping.

    The caller (:func:`_validate_source_theme`) guarantees that
    ``raw["project"]`` is a :class:`dict`.

    Returns ``None`` when the ``theme`` key is absent (the schema-level
    default ``showcase_react`` applies).

    Raises:
        ThemeValidationError: When ``project.theme`` is explicitly set
            to ``null`` (which is invalid — the key should be omitted
            or set to ``showcase_react``).
    """
    project = _project_mapping(raw, _CONFIG_LABEL)
    # Must distinguish "key absent" (valid schema default) from
    # "key present with value null" (invalid — the user explicitly
    # wrote ``project.theme: null`` or ``project.theme:`` in YAML).
    if "theme" not in project:
        return None
    theme = project["theme"]
    if theme is None:
        raise ThemeValidationError(
            f"project.theme is explicitly set to null in "
            f"{_CONFIG_LABEL}. Remove the 'theme' line to use the "
            f"default '{SOLE_VALID_THEME}', or set it to "
            f"'{SOLE_VALID_THEME}'.",
            source_label=_CONFIG_LABEL,
        )
    return str(theme)


def _extract_state_theme(raw: dict) -> str | None:
    """Extract theme from a parsed state.yml or recovery-ledger mapping.

    The caller (:func:`_validate_source_theme`) guarantees that
    ``raw["project"]`` is a :class:`dict`.

    State and recovery files are expected to carry a ``project`` section
    with an explicit ``theme`` field.  Returns ``None`` when absent
    (which will be treated as a validation error by the caller).
    """
    project = _project_mapping(raw, _STATE_LABEL)
    theme = project.get("theme")
    if theme is None:
        return None
    return str(theme)


def _path_label_for_source(source_label: str) -> str:
    """Map a human-readable source label back to the config file path."""
    mapping = {
        _CONFIG_LABEL: _CONFIG_FILE,
        _STATE_LABEL: _STATE_FILE,
        _RECOVERY_LABEL: _RECOVERY_FILE,
    }
    return mapping.get(source_label, source_label)


__all__ = [
    "SOLE_VALID_THEME",
    "ThemeValidationError",
    "validate_theme_preflight",
]
