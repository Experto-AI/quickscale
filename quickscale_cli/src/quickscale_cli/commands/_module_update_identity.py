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
    """An equal-label or post-freeze update would replace applied content."""


def _collect_update_migration_identity(
    project_path: Path, module_prefix: str
) -> dict[str, str] | None:
    """Return a module tree's migration content identity, or ``None``.

    ``None`` marks content this check cannot identify (a missing source
    package or an unreadable migrations package), so the caller decides by
    vintage instead of reading it as a removal: a frozen vintage refuses to
    pull without it, while a vintage before the freeze lets the pull repair
    such a tree.  An empty mapping stays reserved for a module that ships no
    migrations.
    """
    try:
        return _migration_hashes.compute_module_migration_hashes(
            project_path / module_prefix
        )
    except _migration_hashes.MigrationHashError, OSError:
        return None


def _is_frozen_update_vintage(applied_version: str | None) -> bool:
    """Return whether an applied vintage sits at or after the migration freeze.

    A frozen vintage keeps no fresh-database upgrade path, so a pull may not
    proceed without the applied content identity.
    """
    return applied_version is not None and _migration_hashes.is_frozen_vintage(
        applied_version
    )


def _update_migration_identity_reason(
    applied_version: str | None, installed_version: str | None
) -> str | None:
    """Return why this pull must keep the applied identity, or ``None``.

    Two keyings require every applied migration file to survive the pull
    byte-identical (SA204 (e), SA204 (g)): an unchanged version label, which
    the database recorded with that content, and an applied vintage at or
    after the migration freeze, from which a shipped migration file is
    immutable and only new files may apply forward.  A vintage before the
    freeze keeps the documented fresh-database path, so a label change there
    compares nothing.

    Returns:
        A clause naming the keying, for the refusal message, or ``None`` to
        skip the comparison.

    """
    if applied_version is None:
        return None
    if applied_version == installed_version:
        return f"under the equal version label '{applied_version}'"
    if _is_frozen_update_vintage(applied_version):
        return (
            f"across the version label change '{applied_version}' -> "
            f"'{installed_version}', at or after the migration freeze vintage"
        )
    return None


def _get_update_migration_issues(
    applied_migration_hashes: Mapping[str, str] | None,
    embedded_migration_hashes: Mapping[str, str] | None,
) -> list[str]:
    """Return refusal issues for an applied migration content mismatch.

    The update must keep every applied migration file byte-identical in the
    updated module — under an equal version label, and on every pull at or
    after the migration freeze — while the pulled content may only add newer
    migrations for ``migrate`` to apply forward.  An unidentifiable applied
    identity leaves nothing to compare, while an updated module whose content
    cannot be identified is refused rather than read as empty.
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
