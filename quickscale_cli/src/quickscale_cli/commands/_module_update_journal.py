"""Update journal for the module-set transaction (SA319 (b)).

``quickscale update`` records the module set it is about to pull in
``.quickscale/update-journal.yml`` before the first subtree pull.  The journal
is recovery intent only — it names the pre-update commit and each module's
target commit, never applied state.  ``.quickscale/state.yml`` stays the sole
applied-state owner (SA317).

A completed update clears the journal after its single set commit.  If the
process dies mid-set, the next update restores the transaction's tracking
files to the journal's pre-pull baseline, keeps every module already at its
recorded target, pulls the remaining modules, and finalizes the set with a
single state write and commit, so an interrupted run resumes without
re-pulling an already merged split commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml


UPDATE_JOURNAL_RELATIVE_PATH = Path(".quickscale") / "update-journal.yml"

_JOURNAL_VERSION = "1"
_TOP_LEVEL_KEYS = frozenset(
    {"version", "id", "pre_update_head", "started_at", "modules"}
)
_MODULE_KEYS = frozenset({"name", "version", "branch", "commit_sha"})


class _UpdateJournalError(RuntimeError):
    """The update journal is malformed or could not be written."""


@dataclass(frozen=True)
class _ModuleUpdateTarget:
    """One module's verified target in a journaled update set."""

    name: str
    version: str
    branch: str
    commit_sha: str


@dataclass(frozen=True)
class _UpdateJournal:
    """The recorded intent of one interrupted update transaction."""

    transaction_id: str
    pre_update_head: str
    targets: tuple[_ModuleUpdateTarget, ...]
    started_at: str


def _update_journal_path(project_path: Path) -> Path:
    """Return the journal path inside *project_path*."""
    return Path(project_path) / UPDATE_JOURNAL_RELATIVE_PATH


def _write_update_journal(
    project_path: Path,
    *,
    pre_update_head: str,
    targets: tuple[_ModuleUpdateTarget, ...],
    started_at: str | None = None,
    transaction_id: str | None = None,
) -> _UpdateJournal:
    """Write the transaction journal before the first module pull.

    Raises:
        _UpdateJournalError: When the journal cannot be written or records no
            module target.
    """
    if not targets:
        raise _UpdateJournalError(
            "Cannot write an update journal without a module target."
        )
    path = _update_journal_path(project_path)
    recorded = _UpdateJournal(
        transaction_id=transaction_id or uuid4().hex,
        pre_update_head=pre_update_head,
        targets=targets,
        started_at=started_at or datetime.now(timezone.utc).isoformat(),
    )
    payload = {
        "version": _JOURNAL_VERSION,
        "id": recorded.transaction_id,
        "pre_update_head": pre_update_head,
        "started_at": started_at or datetime.now(timezone.utc).isoformat(),
        "modules": [
            {
                "name": target.name,
                "version": target.version,
                "branch": target.branch,
                "commit_sha": target.commit_sha,
            }
            for target in targets
        ],
    }
    temp_path = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            yaml.safe_dump(payload, default_flow_style=False, sort_keys=False)
        )
        temp_path.replace(path)
    except OSError as error:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise _UpdateJournalError(
            f"Failed to write the update journal {path}: {error}"
        ) from error
    return recorded


def _load_update_journal(project_path: Path) -> _UpdateJournal | None:
    """Load and validate the journal, returning ``None`` when absent.

    Raises:
        _UpdateJournalError: When the journal exists but cannot be read or
            does not match the closed schema.
    """
    path = _update_journal_path(project_path)
    if not path.exists():
        return None

    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise _UpdateJournalError(
            f"Failed to read the update journal {path}: {error}. "
            "Fix or remove it before updating modules."
        ) from error

    if not isinstance(data, dict):
        raise _UpdateJournalError(
            f"The update journal {path} is not a YAML mapping. "
            "Fix or remove it before updating modules."
        )
    unknown_keys = set(data) - _TOP_LEVEL_KEYS
    if unknown_keys:
        raise _UpdateJournalError(
            f"The update journal {path} carries unknown keys: "
            f"{', '.join(sorted(unknown_keys))}. Fix or remove it before "
            "updating modules."
        )
    if data.get("version") != _JOURNAL_VERSION:
        raise _UpdateJournalError(
            f"The update journal {path} has an unsupported version "
            f"{data.get('version')!r}; expected {_JOURNAL_VERSION!r}."
        )

    transaction_id = data.get("id")
    if not isinstance(transaction_id, str) or not transaction_id.strip():
        raise _UpdateJournalError(
            f"The update journal {path} does not record a transaction id."
        )

    pre_update_head = data.get("pre_update_head")
    if not isinstance(pre_update_head, str) or not pre_update_head.strip():
        raise _UpdateJournalError(
            f"The update journal {path} does not record a pre-update commit."
        )
    started_at = data.get("started_at", "")
    if not isinstance(started_at, str):
        raise _UpdateJournalError(
            f"The update journal {path} records an invalid start time."
        )

    raw_modules = data.get("modules")
    if not isinstance(raw_modules, list) or not raw_modules:
        raise _UpdateJournalError(
            f"The update journal {path} does not record any module targets."
        )

    targets: list[_ModuleUpdateTarget] = []
    seen: set[str] = set()
    for raw_module in raw_modules:
        if not isinstance(raw_module, dict):
            raise _UpdateJournalError(
                f"The update journal {path} records a malformed module target."
            )
        unknown_module_keys = set(raw_module) - _MODULE_KEYS
        if unknown_module_keys:
            raise _UpdateJournalError(
                f"The update journal {path} records unknown module keys: "
                f"{', '.join(sorted(unknown_module_keys))}."
            )
        values: dict[str, str] = {}
        for key in _MODULE_KEYS:
            value = raw_module.get(key)
            if not isinstance(value, str) or not value.strip():
                raise _UpdateJournalError(
                    f"The update journal {path} records an incomplete module "
                    f"target: {key!r} is missing."
                )
            values[key] = value
        if values["name"] in seen:
            raise _UpdateJournalError(
                f"The update journal {path} records module "
                f"{values['name']!r} more than once."
            )
        seen.add(values["name"])
        targets.append(
            _ModuleUpdateTarget(
                name=values["name"],
                version=values["version"],
                branch=values["branch"],
                commit_sha=values["commit_sha"],
            )
        )

    return _UpdateJournal(
        transaction_id=transaction_id,
        pre_update_head=pre_update_head,
        targets=tuple(targets),
        started_at=started_at,
    )


def _clear_update_journal(project_path: Path) -> None:
    """Remove the journal after its transaction completed or rolled back.

    Raises:
        _UpdateJournalError: When the journal file cannot be removed.
    """
    path = _update_journal_path(project_path)
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise _UpdateJournalError(
            f"Failed to clear the update journal {path}: {error}"
        ) from error
