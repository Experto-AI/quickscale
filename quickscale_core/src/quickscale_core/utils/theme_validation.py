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

#: Paths whose presence triggers the preflight recovery-ledger check.
_RECOVERY_PROBE_PATHS = (
    ".quickscale",
    "apply-recovery.yml",
)


# ---------------------------------------------------------------------------
# Core preflight
# ---------------------------------------------------------------------------


def validate_theme_preflight(project_path: Path) -> None:
    """Validate the ``theme`` field in every present configuration source.

    Checks *all* of the following sources independently when they exist:

    * ``<project_path>/quickscale.yml`` — desired state
    * ``<project_path>/.quickscale/state.yml`` — applied state
    * ``<project_path>/.quickscale/apply-recovery.yml`` — recovery ledger

    Args:
        project_path: Root directory of the QuickScale project.

    Raises:
        ThemeValidationError: If any present source has a missing,
            malformed, or non-``showcase_react`` theme.
    """
    errors: list[str] = []

    # 1. Desired-state (quickscale.yml).
    config_path = project_path / _CONFIG_FILE
    if config_path.exists():
        try:
            _validate_source_theme(config_path, _CONFIG_LABEL, _extract_config_theme)
        except ThemeValidationError as exc:
            errors.append(str(exc))

    # 2. Applied state (.quickscale/state.yml).
    state_path = project_path / _STATE_FILE
    if state_path.exists():
        try:
            _validate_source_theme(state_path, _STATE_LABEL, _extract_state_theme)
        except ThemeValidationError as exc:
            errors.append(str(exc))

    # 3. Recovery ledger (.quickscale/apply-recovery.yml).
    recovery_path = project_path / _RECOVERY_FILE
    if recovery_path.exists():
        try:
            _validate_source_theme(recovery_path, _RECOVERY_LABEL, _extract_state_theme)
        except ThemeValidationError as exc:
            errors.append(str(exc))

    if errors:
        raise ThemeValidationError(
            "\n".join(errors),
            source_label=", ".join(
                label
                for label, _path in [
                    (_CONFIG_LABEL, config_path),
                    (_STATE_LABEL, state_path),
                    (_RECOVERY_LABEL, recovery_path),
                ]
                if _path.exists()
            ),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_source_theme(
    file_path: Path,
    source_label: str,
    extract_theme: Any,
) -> None:
    """Parse *file_path* and validate its theme is the sole valid value.

    Args:
        file_path: Absolute path to the source YAML file.
        source_label: Human-readable label for error messages.
        extract_theme: Callable ``(raw: dict) -> str | None`` that
            extracts the theme value from the parsed mapping.

    Raises:
        ThemeValidationError: On any validation failure.
    """
    try:
        raw: Any = yaml.safe_load(file_path.read_text())
    except yaml.YAMLError as exc:
        raise ThemeValidationError(
            f"{source_label} contains invalid YAML and cannot be used: {exc}",
            source_label=source_label,
        )
    except OSError as exc:
        raise ThemeValidationError(
            f"{source_label} could not be read: {exc}",
            source_label=source_label,
        )

    if not isinstance(raw, dict):
        raise ThemeValidationError(
            f"{source_label} must be a YAML mapping (dictionary)",
            source_label=source_label,
        )

    # SA94 Barrier A: fail closed when the ``project`` section is missing
    # or is not a mapping.  A missing or non-mapping ``project`` means
    # the file is structurally invalid and must not silently default
    # to React.
    project = raw.get("project")
    if not isinstance(project, dict):
        raise ThemeValidationError(
            f"{source_label} is missing the required 'project' section",
            source_label=source_label,
        )

    try:
        theme = extract_theme(raw)
    except ThemeValidationError:
        raise
    except Exception as exc:
        raise ThemeValidationError(
            f"{source_label} could not be parsed: {exc}",
            source_label=source_label,
        ) from exc

    if theme is None:
        # Theme is optional in desired config (defaults to showcase_react
        # at the schema level).  For state and recovery the theme must be
        # present when the file exists.
        if source_label == _CONFIG_LABEL:
            return  # Absent -> default is React, which is valid.
        raise ThemeValidationError(
            f"{source_label} is missing the required 'project.theme' field",
            source_label=source_label,
        )

    if theme == SOLE_VALID_THEME:
        return

    # Invalid theme — map known retired values to actionable message.
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
    """
    project = raw.get("project")
    theme = project.get("theme")  # type: ignore[union-attr]
    if theme is None:
        return None
    return str(theme)


def _extract_state_theme(raw: dict) -> str | None:
    """Extract theme from a parsed state.yml or recovery-ledger mapping.

    The caller (:func:`_validate_source_theme`) guarantees that
    ``raw["project"]`` is a :class:`dict`.

    State and recovery files are expected to carry a ``project`` section
    with an explicit ``theme`` field.  Returns ``None`` when absent
    (which will be treated as a validation error by the caller).
    """
    project = raw.get("project")
    theme = project.get("theme")  # type: ignore[union-attr]
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
