"""Recovery-ledger schema and loader for QuickScale F12.1b.

The recovery ledger is a YAML file (``.quickscale/apply-recovery.yml``) that
records *where an interrupted apply stopped*: the resume checkpoint, the git
index checkpoint captured at the post-embed boundary, and optional diagnostic
step-progress entries keyed by the stable
:data:`~quickscale_core.apply.step.APPLY_STEPS` step ids.

Design invariants
-----------------
* **One state owner.**  ``.quickscale/state.yml`` is the sole authoritative
  applied-state store.  The recovery ledger never embeds a second applied-state
  snapshot; resume reads ``state.yml`` and uses the ledger only for the resume
  pointer and diagnostic progress.
* **Presence semantics are unchanged.**  Resume gating is driven purely by
  whether the ledger file *exists* (``recovery_state is not None``), matching
  the existing ``apply_command.py`` pattern.  The ``step_progress`` section
  is diagnostic-only and must never be used as a resume gate.
* **Fail-hard / no-legacy-fallback.**  A ledger file that is malformed or that
  references an unknown step id raises :class:`LedgerError` immediately.  There
  is no silent degradation.  Ledgers written before the single-owner change
  still load: this parser ignores their old applied-state section.  The CLI
  reads that section once, outside this module, only to migrate an interrupted
  pre-SA317 apply into ``state.yml``.
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
from quickscale_core.schema.state_schema import StateError

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
# AF5 resume-checkpoint entry
# ---------------------------------------------------------------------------


@dataclass
class ResumeCheckpoint:
    """AF5 resume/checkpoint metadata for the apply recovery ledger.

    This object stores the step-level resume checkpoint that the AF5 runner
    expansion (Phase 2+) will use to resume an interrupted apply pass from
    a specific step rather than re-running from the beginning.

    For Phase 1, the shape is defined and frozen here so that the recovery
    ledger YAML contract is stable before any runner code is written.
    Consumers that save or update the recovery ledger must carry the
    ``resume_checkpoint`` field forward when it is present in the existing
    ledger (caller parity / AF6-era compatibility).

    Attributes:
        resume_step_id: The stable step id (from
            :data:`~quickscale_core.apply.step.APPLY_STEPS`) from which
            resume should begin.  Step bodies with ``resume="idempotent-rerun"``
            are presence-gated and safe to re-run.
        suspend_after_step_id: Optional step id at which execution should
            pause after the resume pass completes.  When ``None`` the resume
            runs to completion.
        checkpoint_tree_id: The git tree id captured at checkpoint time.
            Mirrors the top-level ``git_index_checkpoint`` on the ledger but
            is duplicated here so that the resume checkpoint is self-describing.
    """

    resume_step_id: str
    suspend_after_step_id: str | None = None
    checkpoint_tree_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Serialise to a YAML-friendly mapping."""
        result: dict[str, str | None] = {
            "resume_step_id": self.resume_step_id,
        }
        if self.suspend_after_step_id is not None:
            result["suspend_after_step_id"] = self.suspend_after_step_id
        if self.checkpoint_tree_id is not None:
            result["checkpoint_tree_id"] = self.checkpoint_tree_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResumeCheckpoint":
        """Build a :class:`ResumeCheckpoint` from a raw mapping.

        Raises:
            LedgerError: If the ``resume_step_id`` field is absent or
                invalid, or if the step id is not recognised.
        """
        if not isinstance(data, dict):
            raise LedgerError(
                f"resume_checkpoint must be a mapping, got {type(data).__name__}"
            )

        if "resume_step_id" not in data:
            raise LedgerError(
                "resume_checkpoint is missing required field 'resume_step_id'"
            )

        resume_step_id = data["resume_step_id"]
        if not isinstance(resume_step_id, str) or not resume_step_id:
            raise LedgerError(
                f"resume_checkpoint 'resume_step_id' must be a non-empty string, "
                f"got {resume_step_id!r}"
            )

        # Validate against the registry — fail hard on unknown ids.
        if resume_step_id not in _VALID_STEP_IDS:
            raise LedgerError(
                f"resume_checkpoint references unknown step_id={resume_step_id!r}. "
                f"Valid ids: {sorted(_VALID_STEP_IDS)}"
            )

        suspend_after = data.get("suspend_after_step_id")
        if suspend_after is not None:
            if not isinstance(suspend_after, str) or not suspend_after:
                raise LedgerError(
                    f"resume_checkpoint 'suspend_after_step_id' must be a non-empty "
                    f"string, got {suspend_after!r}"
                )
            if suspend_after not in _VALID_STEP_IDS:
                raise LedgerError(
                    f"resume_checkpoint references unknown "
                    f"suspend_after_step_id={suspend_after!r}. "
                    f"Valid ids: {sorted(_VALID_STEP_IDS)}"
                )

        checkpoint_tree_id = data.get("checkpoint_tree_id")
        if checkpoint_tree_id is not None and (
            not isinstance(checkpoint_tree_id, str) or not checkpoint_tree_id
        ):
            raise LedgerError(
                f"resume_checkpoint 'checkpoint_tree_id' must be a non-empty "
                f"string, got {checkpoint_tree_id!r}"
            )

        return cls(
            resume_step_id=resume_step_id,
            suspend_after_step_id=suspend_after,
            checkpoint_tree_id=checkpoint_tree_id,
        )


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

    The ledger records recovery *metadata* only.  Applied state — project
    identity, modules, managed-file hashes, and adopted contract steps — lives
    in ``.quickscale/state.yml`` and is never duplicated here.

    Attributes:
        git_index_checkpoint: Git tree-id captured at the time the recovery
            ledger was written.  Records the current git-index state for
            diagnostic or recovery reference.  **Required — present ledgers
            must carry a non-empty string.**
        resume_checkpoint: Optional AF5 resume/checkpoint metadata.
            When present, the ledger carries a step-level checkpoint that
            the AF5 runner uses to resume from a specific step.  Absent in
            AF6-era ledgers; backward-compatible by default.
            **Preserved on save when present.**
        step_progress: Optional mapping of step_id to
            :class:`StepProgress`.  May be empty or absent (``None``);
            both are treated as valid.  **Diagnostic-only.**
    """

    git_index_checkpoint: str
    resume_checkpoint: ResumeCheckpoint | None = field(default=None)
    step_progress: dict[str, StepProgress] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a YAML-friendly mapping suitable for atomic write."""
        data: dict[str, Any] = {}

        if self.resume_checkpoint is not None:
            data["resume_checkpoint"] = self.resume_checkpoint.to_dict()

        if self.step_progress:
            data["step_progress"] = [
                entry.to_dict() for entry in self.step_progress.values()
            ]

        data["git_index_checkpoint"] = self.git_index_checkpoint

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
                "Inconsistent" includes: not a YAML mapping, missing the
                required ``git_index_checkpoint`` field, or ``step_progress``
                containing a step id that is not in the
                :data:`~quickscale_core.apply.step.APPLY_STEPS` registry.
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

    ``git_index_checkpoint`` is **required** — present ledgers that omit the
    field raise :class:`LedgerError`.  Older ledgers that still carry an
    applied-state section load with that section ignored; ``state.yml`` is the
    only source of applied state.

    Raises:
        LedgerError: On any structural or consistency violation.
    """
    if not isinstance(raw, dict):
        raise LedgerError(
            f"Recovery ledger must be a YAML mapping, got {type(raw).__name__}"
        )

    # --- Optional step_progress section ----------------------------------
    step_progress: dict[str, StepProgress] | None = None
    raw_sp = raw.get("step_progress")
    if raw_sp is not None:
        step_progress = _parse_step_progress(raw_sp)

    # --- Optional resume_checkpoint section (AF5, absent in AF6-era) ----
    resume_checkpoint: ResumeCheckpoint | None = None
    raw_rc = raw.get("resume_checkpoint")
    if raw_rc is not None:
        resume_checkpoint = _parse_resume_checkpoint(raw_rc)

    # --- Required git_index_checkpoint field ----------------------------
    raw_gic = raw.get("git_index_checkpoint")
    if not isinstance(raw_gic, str) or not raw_gic:
        raise LedgerError(
            f"'git_index_checkpoint' is required and must be a non-empty string, "
            f"got {raw_gic!r}"
        )

    return RecoveryLedger(
        resume_checkpoint=resume_checkpoint,
        step_progress=step_progress,
        git_index_checkpoint=raw_gic,
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


# ---------------------------------------------------------------------------
# Resume-checkpoint parser
# ---------------------------------------------------------------------------


def _parse_resume_checkpoint(raw_rc: Any) -> ResumeCheckpoint:
    """Parse and validate the ``resume_checkpoint`` section.

    Raises:
        LedgerError: If the section is not a mapping, required fields are
            missing, or referenced step ids are not in the
            :data:`~quickscale_core.apply.step.APPLY_STEPS` registry.
    """
    if not isinstance(raw_rc, dict):
        raise LedgerError(
            f"'resume_checkpoint' must be a mapping, got {type(raw_rc).__name__}"
        )
    return ResumeCheckpoint.from_dict(raw_rc)


__all__ = [
    "LedgerError",
    "LedgerManager",
    "RecoveryLedger",
    "ResumeCheckpoint",
    "StepProgress",
]
