"""Content hashes for a module's applied migration files.

The clean-break migration policy rewrites each model-bearing module's
``0001_initial`` in place every release, so a version label alone cannot
identify migration history: two revisions can carry the same label with
different content.  The repository therefore records a *content identity* —
the SHA-256 hash of each applied migration file — and this module owns it.

Three helpers build that identity:

* :func:`resolve_module_migrations_dir` maps a module directory to its
  migrations package (``None`` when the module ships none).
* :func:`compute_migration_hashes` hashes one migrations package.
* :func:`compute_module_migration_hashes` combines the two for a module
  directory.

``scripts/sync_migration_hashes.py`` generates the checked-in hash manifest
from the same helpers, so the manifest and every later comparison share one
implementation.  The identity is deliberately filesystem-based: it is
generated in CI without a database and recorded with every backup, while
which migrations ``migrate`` has applied stays Django's own record.  The
digest covers the file's raw bytes, so reformatting or rewriting a frozen
migration file changes its identity — the intended semantics for a freeze.
Missing or empty migration packages fail closed rather than hashing to an
empty mapping.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final

#: A migration file that carries an applied schema change: a four-digit
#: ordered prefix plus a name, matching Django's migration naming.
NUMBERED_MIGRATION_PATTERN: Final = re.compile(r"^\d{4}_.+\.py$")

#: Read chunk size for hashing.  64 KiB keeps memory low for large files.
_HASH_CHUNK_SIZE: Final[int] = 65536

_SOURCE_DIRNAME: Final[str] = "src"
_MIGRATIONS_DIRNAME: Final[str] = "migrations"
_PACKAGE_PREFIX: Final[str] = "quickscale_modules_"


class MigrationHashError(ValueError):
    """Raised when a module's migration files cannot be identified safely."""


def hash_migration_file(migration_path: Path) -> str:
    """Return the SHA-256 hex digest of one migration file's raw bytes.

    Args:
        migration_path: Absolute path to the migration file to hash.

    Returns:
        Hex digest string.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: For any other I/O error reading the file.

    """
    sha = hashlib.sha256()
    with open(migration_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
            sha.update(chunk)
    return sha.hexdigest()


def resolve_module_migrations_dir(module_path: Path) -> Path | None:
    """Return a module directory's migrations package, when it ships one.

    A module keeps its Django app package at
    ``<module>/src/quickscale_modules_<name>/`` — the same layout in the
    maintainer workspace and in a generated project's embedded ``modules/``
    workspace.

    Args:
        module_path: Module directory (the directory holding ``module.yml``).

    Returns:
        The module's ``migrations`` directory, or ``None`` when the module
        ships no migrations package (a service-style module).

    Raises:
        MigrationHashError: If the module's source package is missing.

    """
    module_path = Path(module_path)
    package_dir = module_path / _SOURCE_DIRNAME / f"{_PACKAGE_PREFIX}{module_path.name}"
    if not package_dir.is_dir():
        raise MigrationHashError(
            f"Module '{module_path.name}' has no source package at '{package_dir}'"
        )
    migrations_dir = package_dir / _MIGRATIONS_DIRNAME
    return migrations_dir if migrations_dir.is_dir() else None


def compute_migration_hashes(migrations_dir: Path) -> dict[str, str]:
    """Return ``{migration filename: sha256}``, ordered by filename.

    Only numbered migration files are hashed; ``__init__.py`` and any other
    file are not applied migrations.  Filename order is migration order: the
    four-digit, zero-padded prefixes sort lexicographically.

    Args:
        migrations_dir: The module's ``migrations`` package.

    Returns:
        Mapping of migration filename to SHA-256 hex digest, in migration
        order.

    Raises:
        MigrationHashError: If the directory is missing, or exists but holds
            no numbered migration files.

    """
    migrations_dir = Path(migrations_dir)
    if not migrations_dir.is_dir():
        raise MigrationHashError(f"Migrations directory not found: '{migrations_dir}'")
    migration_paths = sorted(
        path
        for path in migrations_dir.iterdir()
        if path.is_file() and NUMBERED_MIGRATION_PATTERN.match(path.name)
    )
    if not migration_paths:
        raise MigrationHashError(
            f"Migrations directory '{migrations_dir}' contains no numbered migration files"
        )
    return {path.name: hash_migration_file(path) for path in migration_paths}


def compute_module_migration_hashes(module_path: Path) -> dict[str, str]:
    """Return a module directory's applied-migration hashes, in order.

    A module that ships no migrations yields an empty mapping; a module whose
    migrations package exists but holds no numbered migration files fails
    closed.  Callers record one key per module, so an empty mapping and a
    missing record stay distinguishable.

    Args:
        module_path: Module directory (the directory holding ``module.yml``).

    Returns:
        Mapping of migration filename to SHA-256 hex digest, in migration
        order.

    Raises:
        MigrationHashError: If the module source package or its migrations
            package cannot be read.

    """
    migrations_dir = resolve_module_migrations_dir(module_path)
    if migrations_dir is None:
        return {}
    return compute_migration_hashes(migrations_dir)


__all__ = [
    "NUMBERED_MIGRATION_PATTERN",
    "MigrationHashError",
    "compute_migration_hashes",
    "compute_module_migration_hashes",
    "hash_migration_file",
    "resolve_module_migrations_dir",
]
