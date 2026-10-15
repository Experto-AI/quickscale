"""Applied migration-content identity guards for the module update flow.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`; the
update flow re-exports every name defined here (Module Conventions rule 28),
so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import quickscale_core.migration_hashes as _migration_hashes


class _UpdateMigrationIdentityError(RuntimeError):
    """An equal-label update would replace applied migration content."""


def _collect_update_migration_identity(
    project_path: Path, module_prefix: str
) -> dict[str, str] | None:
    """Return a module tree's migration content identity, or ``None``.

    ``None`` marks content this check cannot identify (a missing source
    package or an unreadable migrations package), so the caller skips the
    comparison instead of reading it as a removal; an empty mapping stays
    reserved for a module that ships no migrations.
    """
    try:
        return _migration_hashes.compute_module_migration_hashes(
            project_path / module_prefix
        )
    except _migration_hashes.MigrationHashError, OSError:
        return None


def _get_update_migration_issues(
    applied_migration_hashes: Mapping[str, str] | None,
    embedded_migration_hashes: Mapping[str, str] | None,
) -> list[str]:
    """Return refusal issues for an applied migration content mismatch.

    Under an equal version label the update must keep every applied migration
    file byte-identical in the updated module; the pulled content may only add
    newer migrations for ``migrate`` to apply forward.  An unidentifiable
    applied identity leaves nothing to compare, while an updated module whose
    content cannot be identified is refused rather than read as empty.
    """
    if not applied_migration_hashes:
        return []
    if embedded_migration_hashes is None:
        return ["the updated module's migration content could not be identified"]
    issues: list[str] = []
    for filename in sorted(applied_migration_hashes):
        embedded_digest = embedded_migration_hashes.get(filename)
        if embedded_digest is None:
            issues.append(f"migration '{filename}' is no longer present")
        elif embedded_digest != applied_migration_hashes[filename]:
            issues.append(f"migration '{filename}' changed content")
    return issues
