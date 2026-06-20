"""Recovery-ledger schema and loader for QuickScale F12.1b.

The recovery ledger is a YAML file (``.quickscale/apply-recovery.yml``) that
extends the applied-state snapshot with optional *diagnostic* step-progress
information keyed by the stable :data:`~quickscale_core.apply.step.APPLY_STEPS`
step ids.

Design invariants
-----------------
* **Presence semantics are unchanged.**  Resume gating is driven purely by
  whether the ledger file *exists* (``recovery_state is not None``), matching
  the existing ``apply_command.py`` pattern.  The ``step_progress`` section
  is diagnostic-only and must never be used as a resume gate.
* **Fail-hard / no-legacy-fallback.**  A ledger file that is malformed,
  missing required applied-state fields, or that references an unknown step id
  raises :class:`LedgerError` immediately.  There is no silent degradation.
* **state.yml is a separate concern.**  The ``step_progress`` section only
  exists in the recovery ledger; the canonical ``state.yml`` schema is never
  extended with recovery-only fields.

Serialization convention
------------------------
* File path: ``<project_root>/.quickscale/apply-recovery.yml``
* Atomic write via ``.quickscale/apply-recovery.tmp`` (distinct from
  ``state.yml``'s ``.tmp``).
* PyYAML ``yaml.dump(..., default_flow_style=False, sort_keys=False)``.

No imports from ``quickscale_cli`` are permitted here; this module is pure
``quickscale_core`` domain code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from quickscale_core.apply.step import APPLY_STEPS
from quickscale_core.schema.state_schema import (
    ProjectState,
    QuickScaleState,
    StateError,
)

# ---------------------------------------------------------------------------
# Public error type
# ---------------------------------------------------------------------------

_VALID_STEP_IDS: frozenset[str] = frozenset(s.step_id for s in APPLY_STEPS)


class LedgerError(StateError):
    """Raised when the recovery ledger file is malformed or inconsistent.

    Subclasses :class:`~quickscale_core.schema.state_schema.StateError` so
    that callers that already catch ``StateError`` will also catch ledger
    failures without code changes.
    """

    pass


# ---------------------------------------------------------------------------
# Step-progress entry
# ---------------------------------------------------------------------------


@dataclass
class StepProgress:
    """Diagnostic progress record for a single apply step.

    This object is **diagnostic-only**.  It must never be used to gate
    resume behaviour.

    Attributes:
        step_id: Stable id from the :data:`~quickscale_core.apply.step.APPLY_STEPS`
            registry.
        status: Free-form status string, e.g. ``"completed"``, ``"failed"``,
            ``"skipped"``.
        detail: Optional human-readable detail message recorded at runtime.
    """

    step_id: str
    status: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a YAML-friendly mapping."""
        result: dict[str, Any] = {
            "step_id": self.step_id,
            "status": self.status,
        }
        if self.detail is not None:
            result["detail"] = self.detail
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepProgress":
        """Build a :class:`StepProgress` from a raw mapping.

        Raises:
            LedgerError: If required fields are missing or the step_id is not
                in the :data:`~quickscale_core.apply.step.APPLY_STEPS` registry.
        """
        if not isinstance(data, dict):
            raise LedgerError(
                f"Each step_progress entry must be a mapping, got {type(data).__name__}"
            )
        if "step_id" not in data:
            raise LedgerError("step_progress entry is missing required field 'step_id'")
        if "status" not in data:
            raise LedgerError("step_progress entry is missing required field 'status'")

        step_id = data["step_id"]
        if not isinstance(step_id, str) or not step_id:
            raise LedgerError(
                f"step_progress entry 'step_id' must be a non-empty string, "
                f"got {step_id!r}"
            )

        # Validate against the registry — fail hard on unknown ids.
        if step_id not in _VALID_STEP_IDS:
            raise LedgerError(
                f"step_progress references unknown step_id={step_id!r}. "
                f"Valid ids: {sorted(_VALID_STEP_IDS)}"
            )

        status = data["status"]
        if not isinstance(status, str) or not status:
            raise LedgerError(
                f"step_progress entry 'status' must be a non-empty string, "
                f"got {status!r}"
            )

        detail = data.get("detail")
        if detail is not None and not isinstance(detail, str):
            raise LedgerError(
                f"step_progress entry 'detail' must be a string or absent, "
                f"got {type(detail).__name__}"
            )

        return cls(step_id=step_id, status=status, detail=detail)


# ---------------------------------------------------------------------------
# Recovery ledger dataclass
# ---------------------------------------------------------------------------


@dataclass
class RecoveryLedger:
    """Parsed representation of ``.quickscale/apply-recovery.yml``.

    The ``applied_state`` portion reuses :class:`~quickscale_core.schema.state_schema.QuickScaleState`
    verbatim — the ledger file carries the same applied-state YAML structure
    that the canonical ``state.yml`` uses.  ``step_progress`` is an optional
    diagnostic section absent from ``state.yml``.

    Attributes:
        applied_state: The applied-state snapshot embedded in the ledger.
        step_progress: Optional mapping of step_id to
            :class:`StepProgress`.  May be empty or absent (``None``);
            both are treated as valid.  **Diagnostic-only.**
    """

    applied_state: QuickScaleState
    step_progress: dict[str, StepProgress] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a YAML-friendly mapping suitable for atomic write."""
        state = self.applied_state

        # Build the applied-state section using the same structure as
        # StateManager.save() so the format is consistent.
        from quickscale_core.config import normalize_installed_version
        from quickscale_core.contracts.module_options import sanitize_module_options

        data: dict[str, Any] = {
            "version": state.version,
            "project": {
                "slug": state.project.slug,
                "package": state.project.package,
                "theme": state.project.theme,
                "created_at": state.project.created_at,
                "last_applied": state.project.last_applied,
            },
        }

        if state.modules:
            data["modules"] = {
                name: {
                    k: v
                    for k, v in {
                        "version": normalize_installed_version(module.version),
                        "commit_sha": module.commit_sha,
                        "embedded_at": module.embedded_at,
                        "options": (
                            sanitize_module_options(name, module.options)
                            if module.options
                            else None
                        ),
                        "prefix": module.prefix,
                        "branch": module.branch,
                        "installed_at": module.installed_at,
                    }.items()
                    if v is not None
                }
                for name, module in state.modules.items()
            }

        if state.managed_files:
            data["managed_files"] = [
                record.to_dict() for record in state.managed_files.values()
            ]

        if self.step_progress:
            data["step_progress"] = [
                entry.to_dict() for entry in self.step_progress.values()
            ]

        return data


# ---------------------------------------------------------------------------
# Ledger manager
# ---------------------------------------------------------------------------

_LEDGER_FILENAME = "apply-recovery.yml"
_LEDGER_TMP_FILENAME = "apply-recovery.tmp"


class LedgerManager:
    """Manages the recovery-ledger file for a QuickScale project.

    The recovery ledger lives at ``<project_root>/.quickscale/apply-recovery.yml``.
    This manager provides three operations:

    * :meth:`load` — deserialise the ledger; returns ``None`` when the file
      is absent; raises :class:`LedgerError` on any malformed or inconsistent
      content.
    * :meth:`save` — serialise a :class:`RecoveryLedger` atomically via a
      temporary file.
    * :attr:`ledger_file` — the resolved :class:`~pathlib.Path` for the
      ledger file (useful for presence checks in callers).

    No writer wiring into apply/remove/module commands is performed here;
    that is F12.1d scope.
    """

    def __init__(self, project_path: Path) -> None:
        self._project_path = Path(project_path)
        self._state_dir = self._project_path / ".quickscale"
        self.ledger_file = self._state_dir / _LEDGER_FILENAME
        self._tmp_file = self._state_dir / _LEDGER_TMP_FILENAME

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load(self) -> RecoveryLedger | None:
        """Load and validate the recovery ledger.

        Returns:
            A parsed :class:`RecoveryLedger` if the file exists and is valid,
            or ``None`` if the file does not exist.

        Raises:
            LedgerError: If the file exists but is malformed or inconsistent.
                "Inconsistent" includes: not a YAML dict, missing required
                applied-state fields, or ``step_progress`` containing a step
                id that is not in the :data:`~quickscale_core.apply.step.APPLY_STEPS`
                registry.
        """
        if not self.ledger_file.exists():
            return None

        try:
            with open(self.ledger_file) as fh:
                raw = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise LedgerError(f"Failed to parse recovery ledger YAML: {exc}") from exc

        return _parse_ledger(raw)

    def save(self, ledger: RecoveryLedger) -> None:
        """Serialise *ledger* atomically to the recovery-ledger file.

        Uses the project YAML convention (``default_flow_style=False``,
        ``sort_keys=False``) and writes via ``.quickscale/apply-recovery.tmp``
        then POSIX atomic replace.

        Args:
            ledger: The :class:`RecoveryLedger` to persist.

        Raises:
            LedgerError: If the file cannot be written.
        """
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            data = ledger.to_dict()
            try:
                with open(self._tmp_file, "w") as fh:
                    yaml.dump(data, fh, default_flow_style=False, sort_keys=False)
                self._tmp_file.replace(self.ledger_file)
            except Exception:
                if self._tmp_file.exists():
                    self._tmp_file.unlink()
                raise
        except LedgerError:
            raise
        except Exception as exc:
            raise LedgerError(f"Failed to save recovery ledger: {exc}") from exc


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------


def _parse_ledger(raw: Any) -> RecoveryLedger:
    """Parse raw ``yaml.safe_load`` output into a :class:`RecoveryLedger`.

    Raises:
        LedgerError: On any structural or consistency violation.
    """
    if not isinstance(raw, dict):
        raise LedgerError(
            f"Recovery ledger must be a YAML mapping, got {type(raw).__name__}"
        )

    # --- Applied-state section -------------------------------------------
    applied_state = _parse_applied_state(raw)

    # --- Optional step_progress section ----------------------------------
    step_progress: dict[str, StepProgress] | None = None
    raw_sp = raw.get("step_progress")
    if raw_sp is not None:
        step_progress = _parse_step_progress(raw_sp)

    return RecoveryLedger(applied_state=applied_state, step_progress=step_progress)


def _parse_applied_state(raw: dict[str, Any]) -> QuickScaleState:
    """Extract and validate the applied-state fields from the raw ledger dict.

    Reuses the same validation logic that ``StateManager.load()`` applies to
    ``state.yml`` — missing or wrong-type required fields raise
    :class:`LedgerError`.

    Raises:
        LedgerError: If required applied-state fields are absent or invalid.
    """
    from datetime import datetime

    from quickscale_core.config import normalize_installed_version
    from quickscale_core.contracts.module_options import sanitize_module_options
    from quickscale_core.schema.state_schema import (
        ManagedFileRecord,
        ModuleState,
    )

    # version is optional (default "1") matching StateManager behaviour
    version = raw.get("version", "1")

    # project section is required
    project_data = raw.get("project")
    if not isinstance(project_data, dict):
        raise LedgerError(
            "Recovery ledger 'project' section must be a mapping; "
            f"got {type(project_data).__name__ if project_data is not None else 'absent'}"
        )

    slug = project_data.get("slug")
    package = project_data.get("package")
    theme = project_data.get("theme")

    if not isinstance(slug, str) or not slug:
        raise LedgerError(
            f"Recovery ledger project.slug must be a non-empty string, got {slug!r}"
        )
    if not isinstance(package, str) or not package:
        raise LedgerError(
            f"Recovery ledger project.package must be a non-empty string, got {package!r}"
        )
    if not isinstance(theme, str) or not theme:
        raise LedgerError(
            f"Recovery ledger project.theme must be a non-empty string, got {theme!r}"
        )

    project = ProjectState(
        slug=slug,
        package=package,
        theme=theme,
        created_at=project_data.get("created_at", datetime.now().isoformat()),
        last_applied=project_data.get("last_applied", datetime.now().isoformat()),
    )

    # modules section is optional
    modules_data = raw.get("modules", {})
    if not isinstance(modules_data, dict):
        raise LedgerError(
            f"Recovery ledger 'modules' section must be a mapping, "
            f"got {type(modules_data).__name__}"
        )

    modules: dict[str, ModuleState] = {}
    for module_name, module_info in modules_data.items():
        if not isinstance(module_info, dict):
            raise LedgerError(
                f"Recovery ledger module '{module_name}' state must be a mapping"
            )
        modules[module_name] = ModuleState(
            name=module_name,
            version=normalize_installed_version(module_info.get("version")),
            commit_sha=module_info.get("commit_sha"),
            embedded_at=module_info.get("embedded_at", datetime.now().isoformat()),
            options=sanitize_module_options(
                module_name,
                module_info.get("options") or {},
            ),
            prefix=module_info.get("prefix"),
            branch=module_info.get("branch"),
            installed_at=module_info.get("installed_at"),
        )

    # managed_files section is optional
    managed_files: dict[str, ManagedFileRecord] = {}
    managed_files_data = raw.get("managed_files")
    if managed_files_data is not None:
        if isinstance(managed_files_data, list):
            for entry in managed_files_data:
                if not isinstance(entry, dict):
                    raise LedgerError(
                        f"Each managed_files entry must be a mapping, "
                        f"got {type(entry).__name__}"
                    )
                try:
                    record = ManagedFileRecord.from_dict(entry)
                except (KeyError, TypeError, ValueError) as exc:
                    raise LedgerError(
                        f"Managed file record is missing required fields: {exc}"
                    ) from exc
                managed_files[record.path] = record
        elif isinstance(managed_files_data, dict):
            for file_path, file_info in managed_files_data.items():
                if not isinstance(file_info, dict):
                    raise LedgerError(
                        f"Managed file '{file_path}' value must be a mapping, "
                        f"got {type(file_info).__name__}"
                    )
                try:
                    record = ManagedFileRecord.from_dict(
                        {**file_info, "path": file_path}
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise LedgerError(
                        f"Managed file record for '{file_path}' is missing "
                        f"required fields: {exc}"
                    ) from exc
                managed_files[record.path] = record
        else:
            raise LedgerError(
                f"'managed_files' must be a list or mapping, "
                f"got {type(managed_files_data).__name__}"
            )

    return QuickScaleState(
        version=str(version),
        project=project,
        modules=modules,
        managed_files=managed_files,
    )


def _parse_step_progress(raw_sp: Any) -> dict[str, StepProgress]:
    """Parse and validate the ``step_progress`` section.

    Accepts either a list of step-progress entry dicts or a dict keyed by
    step_id (both formats round-trip correctly via :meth:`RecoveryLedger.to_dict`
    which serialises as a list).

    Raises:
        LedgerError: If the section format is unrecognised, any entry is
            malformed, or any step_id is not in the
            :data:`~quickscale_core.apply.step.APPLY_STEPS` registry.
    """
    result: dict[str, StepProgress] = {}

    if isinstance(raw_sp, list):
        for entry in raw_sp:
            sp = StepProgress.from_dict(entry)
            result[sp.step_id] = sp
    elif isinstance(raw_sp, dict):
        # Tolerate dict-keyed form (step_id -> {status, detail}) for
        # hand-authored ledger files.
        for step_id, entry_data in raw_sp.items():
            if not isinstance(entry_data, dict):
                raise LedgerError(
                    f"step_progress[{step_id!r}] must be a mapping, "
                    f"got {type(entry_data).__name__}"
                )
            merged = {"step_id": step_id, **entry_data}
            sp = StepProgress.from_dict(merged)
            result[sp.step_id] = sp
    else:
        raise LedgerError(
            f"'step_progress' must be a list or mapping, got {type(raw_sp).__name__}"
        )

    return result


__all__ = [
    "LedgerError",
    "LedgerManager",
    "RecoveryLedger",
    "StepProgress",
]
