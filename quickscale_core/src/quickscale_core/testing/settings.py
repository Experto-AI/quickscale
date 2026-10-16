"""The shared test-settings base for the module suites (decisions rule 18).

Each module's ``tests/settings.py`` imports the helpers it needs from this
module and defines every name in :data:`BASE_TEST_SETTINGS_KEYS`; the
module-conventions harness diffs each module's top-level keys against that
tuple, so a module cannot silently drift from the base.  The values that are
strictly mechanical -- the test database dictionary, the test secret key, the
compiled option schema -- are derived here instead of from a copy per module.
"""

from __future__ import annotations

import os
from pathlib import Path

from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.settings_schema import (
    SettingsSchema,
    compile_settings_schema,
)

__all__ = [
    "BASE_TEST_SETTINGS_KEYS",
    "module_settings_schema",
    "suite_database",
    "suite_secret_key",
]

#: Every key a module's ``tests/settings.py`` must define.  The
#: module-conventions harness reads this tuple from this file and reports a
#: violation for each key missing from a module's settings module.
BASE_TEST_SETTINGS_KEYS: tuple[str, ...] = (
    "DATABASES",
    "DEFAULT_AUTO_FIELD",
    "INSTALLED_APPS",
    "MIDDLEWARE",
    "MODULE_SETTINGS_SCHEMA",
    "ROOT_URLCONF",
    "SECRET_KEY",
    "TEMPLATES",
    "USE_TZ",
)


def suite_secret_key(module: str) -> str:
    """Return the suite's ``SECRET_KEY`` for ``module``.

    Test-only and never a shipped secret; one module name maps to one key so
    two suites in one process cannot silently share a signing key.  The name
    avoids pytest's ``test_*`` collection of imported helpers.
    """
    return f"test-secret-key-for-{module}-module"


def suite_database(
    module: str,
    *,
    user: str = "postgres",
    test_database_name: str | None = None,
) -> dict[str, object]:
    """Return the suite's single-database configuration for ``module``.

    The environment-variable names follow the ``QS_<MODULE>_DB_*`` contract
    every suite shares; ``user`` is the database role the connection runs as
    (``postgres`` where the suite provisions its own role,
    ``quickscale_test_role`` where it wants the restricted NOBYPASSRLS role).
    ``test_database_name`` adds the ``TEST`` block some suites pin so a rerun
    reuses the same database.
    """
    prefix = f"QS_{module.upper()}_DB"
    database: dict[str, object] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get(f"{prefix}_NAME", f"test_quickscale_{module}"),
        "USER": os.environ.get(f"{prefix}_USER", user),
        "PASSWORD": os.environ.get(f"{prefix}_PASSWORD", ""),
        "HOST": os.environ.get(f"{prefix}_HOST", "localhost"),
        "PORT": os.environ.get(f"{prefix}_PORT", "5432"),
    }
    if test_database_name is not None:
        database["TEST"] = {"NAME": test_database_name}
    return database


def module_settings_schema(
    modules_root: Path, *module_names: str
) -> dict[str, SettingsSchema]:
    """Compile the option schema for each of ``module_names``.

    ``modules_root`` is the directory holding the module checkouts; each
    module's schema is derived from its own ``module.yml`` so it can never
    drift from the declarations (rule 3).  Each entry is keyed by the
    manifest's declared name rather than the checkout directory's, so the map
    the runtime check reads keeps the stable module identity even when a
    checkout directory is named differently.
    """
    schema: dict[str, SettingsSchema] = {}
    for name in module_names:
        manifest = load_manifest_from_path(Path(modules_root) / name / "module.yml")
        schema[manifest.name] = compile_settings_schema(manifest)
    return schema
